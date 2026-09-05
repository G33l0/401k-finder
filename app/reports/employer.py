"""
Everything one employer's filings say about its retirement plans, over time.

The search a person actually performs is "where was my old 401(k)?", with a
company name and nothing else. This assembles the answer: find the employer,
gather every plan it filed in every year held locally, work out what kind of
plan each is, establish who kept the records year by year, and fold that into
periods with the changes between them.

Plan identity is the part worth being careful about. A plan is tracked by EIN
and plan number, not by name, because names change: a company renames itself
and the plan is renamed with it, and treating that as two plans would split one
career in half. Two plans that merely share a similar company name are left
separate, because merging them would invent a history that never happened.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import ConfidenceLevel
from app.database.models import Filing, Plan, PlanParty, Provider
from app.dol.normalizer import normalize_name_key
from app.plans.successor import follow_chain
from app.providers.directory import contact_for
from app.reports.classify import (
    PRIMARY_ROLE,
    SUPPORTING_ROLES,
    is_investment_vehicle,
    recordkeeper_confidence,
)
from app.reports.plan_types import PlanType, classify_plan, resolve_plan_type
from app.reports.timeline import Observation, Timeline, consolidate

#: How many employers a name search offers before asking for more detail.
MATCH_LIMIT = 25


@dataclass(slots=True)
class EmployerQuery:
    """What the user typed. Only the name is required."""

    name: str

    city: str | None = None
    state: str | None = None
    plan_type: str | None = None

    #: A year narrows the report without hiding the years around it, because a
    #: transition is only visible from both sides.
    form_year: int | None = None

    #: Every year, rather than periods. For somebody checking the workings.
    annual_detail: bool = False

    #: Investment managers, vehicles and funds, normally filtered out.
    include_investments: bool = False

    def resolved_type(self) -> PlanType | None:
        return resolve_plan_type(self.plan_type)


@dataclass(slots=True)
class SourceRecord:
    """One filing, as a line in the report's audit table."""

    form_year: int
    form_type: str
    ein: str
    plan_number: str
    plan_name: str
    recordkeeper: str
    source: str


@dataclass(slots=True)
class ServiceRole:
    """One firm in one supporting role, with the years it served."""

    name: str
    role: str
    timeline: Timeline

    @property
    def role_label(self) -> str:
        return self.role.replace("_", " ").title()


@dataclass(slots=True)
class PlanHistory:
    """One plan, tracked across every year the employer filed for it."""

    plan_id: int
    plan_type: PlanType

    plan_name: str
    plan_number: str
    ein: str

    first_year: int | None = None
    last_year: int | None = None
    filed_years: tuple[int, ...] = ()

    sponsor_names: tuple[str, ...] = ()
    plan_names: tuple[str, ...] = ()

    plan_name_history: Timeline | None = None
    sponsor_name_history: Timeline | None = None

    recordkeepers: Timeline | None = None
    supporting: list[ServiceRole] = field(default_factory=list)
    investments: list[ServiceRole] = field(default_factory=list)

    terminated: bool = False
    final_year: int | None = None
    successor: object | None = None

    participants: int | None = None
    total_assets: float | None = None

    sources: list[SourceRecord] = field(default_factory=list)

    @property
    def current_name(self) -> str:
        return self.plan_names[-1] if self.plan_names else self.plan_name

    @property
    def original_name(self) -> str:
        return self.plan_names[0] if self.plan_names else self.plan_name

    @property
    def status(self) -> str:
        if self.terminated:
            return f"Final return filed for {self.final_year}"
        return "Filing" if self.last_year else "Unknown"

    @property
    def recordkeeper_known(self) -> bool:
        return bool(self.recordkeepers and len(self.recordkeepers))

    def contact(self):  # noqa: ANN201 - providers.directory.Contact | None
        current = self.recordkeepers.current if self.recordkeepers else None
        return contact_for(current.value) if current else None


@dataclass(slots=True)
class EmployerReport:
    """The whole answer for one employer."""

    query: EmployerQuery

    employer_name: str = ""
    current_name: str = ""
    historical_names: tuple[str, ...] = ()
    ein: str = ""
    location: str = ""

    plans: list[PlanHistory] = field(default_factory=list)
    years_held: tuple[int, ...] = ()

    #: Other employers the name matched, when the search was not decisive.
    alternatives: tuple[str, ...] = ()
    notes: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.plans)

    def by_type(self) -> list[tuple[PlanType, list[PlanHistory]]]:
        """Plans grouped under their headings, in the taxonomy's own order."""

        grouped: dict[str, list[PlanHistory]] = {}
        for plan in self.plans:
            grouped.setdefault(plan.plan_type.key, []).append(plan)

        seen: list[tuple[PlanType, list[PlanHistory]]] = []
        for plan in self.plans:
            if plan.plan_type.key in grouped:
                seen.append((plan.plan_type, grouped.pop(plan.plan_type.key)))

        return seen


# ----------------------------------------------------------------------
# Finding the employer
# ----------------------------------------------------------------------


def find_employers(
    session: Session, name: str, *, city: str | None = None, state: str | None = None
) -> list[tuple[str, str, int]]:
    """
    Employers whose filings match a name, as (sponsor name, EIN, plan count).

    Matched on the normalised name so punctuation and suffixes do not decide
    the answer: "ANTHEM, INC." and "ANTHEM INC" are one employer.
    """

    wanted = normalize_name_key(name)
    if not wanted:
        return []

    statement = select(
        Plan.sponsor_name, Plan.ein, func.count(Plan.id), Plan.sponsor_state, Plan.sponsor_city
    ).where(Plan.sponsor_name.is_not(None))

    if state:
        statement = statement.where(Plan.sponsor_state == state.strip().upper()[:2])
    if city:
        statement = statement.where(Plan.sponsor_city.ilike(f"%{city.strip()}%"))

    statement = statement.group_by(Plan.ein, Plan.sponsor_name)

    matches: list[tuple[str, str, int]] = []
    for sponsor, ein, count, _state, _city in session.execute(statement):
        key = normalize_name_key(sponsor)
        if key == wanted or wanted in key or key.startswith(wanted):
            matches.append((sponsor, ein or "", int(count)))

    # A renamed employer answers only to its newest name in `plans`, so offer
    # the names it filed under as well.
    known = {normalize_name_key(name) for name, _, _ in matches}
    for plan_id in _plans_filed_under(session, wanted):
        plan = session.get(Plan, plan_id)
        if plan is None or normalize_name_key(plan.sponsor_name) in known:
            continue
        if state and (plan.sponsor_state or "") != state.strip().upper()[:2]:
            continue
        if city and city.strip().lower() not in (plan.sponsor_city or "").lower():
            continue
        matches.append((plan.sponsor_name or "", plan.ein or "", 1))
        known.add(normalize_name_key(plan.sponsor_name))

    matches.sort(key=lambda item: (-item[2], item[0]))
    return matches[:MATCH_LIMIT]


def _employer_plans(
    session: Session, query: EmployerQuery
) -> tuple[list[Plan], tuple[str, ...]]:
    """Every plan filed by employers matching the name, plus the near misses."""

    wanted = normalize_name_key(query.name)
    if not wanted:
        return [], ()

    statement = select(Plan)
    if query.state:
        statement = statement.where(Plan.sponsor_state == query.state.strip().upper()[:2])
    if query.city:
        statement = statement.where(Plan.sponsor_city.ilike(f"%{query.city.strip()}%"))

    statement = statement.where(
        or_(Plan.sponsor_name.is_not(None), Plan.sponsor_dba_name.is_not(None))
    )

    chosen: list[Plan] = []
    near: set[str] = set()
    seen: set[int] = set()

    for plan in session.execute(statement).scalars():
        keys = [normalize_name_key(plan.sponsor_name), normalize_name_key(plan.sponsor_dba_name)]
        if any(key and (key == wanted or wanted in key) for key in keys):
            chosen.append(plan)
            seen.add(plan.id)
        elif plan.sponsor_name and any(
            key and (key.startswith(wanted[:8]) or wanted[:8] in key) for key in keys
        ):
            near.add(plan.sponsor_name)

    # A plan carries only its most recent sponsor name, so a company that
    # renamed itself no longer answers to the name the user remembers. The
    # filings keep every name it ever used, which is where the old one lives.
    for plan_id in _plans_filed_under(session, wanted):
        if plan_id in seen:
            continue
        plan = session.get(Plan, plan_id)
        if plan is None or not _within_scope(plan, query):
            continue
        chosen.append(plan)
        seen.add(plan_id)

    # Other plans of the same employer, found by EIN rather than by name.
    eins = {plan.ein for plan in chosen if plan.ein}
    if eins:
        for plan in session.execute(select(Plan).where(Plan.ein.in_(eins))).scalars():
            if plan.id not in seen:
                chosen.append(plan)
                seen.add(plan.id)

    return chosen, tuple(sorted(near)[:10])


def _within_scope(plan: Plan, query: EmployerQuery) -> bool:
    """Whether a plan found by an old name still satisfies the city and state."""

    if query.state and (plan.sponsor_state or "") != query.state.strip().upper()[:2]:
        return False

    return not (
        query.city and query.city.strip().lower() not in (plan.sponsor_city or "").lower()
    )


def _plans_filed_under(session: Session, wanted: str) -> set[int]:
    """Plan ids whose filings carry this employer name in any year."""

    found: set[int] = set()

    rows = session.execute(
        select(Filing.plan_id, Filing.sponsor_name)
        .where(Filing.sponsor_name.is_not(None), Filing.plan_id.is_not(None))
        .distinct()
    ).all()

    for plan_id, sponsor in rows:
        key = normalize_name_key(sponsor)
        if key and (key == wanted or wanted in key):
            found.add(int(plan_id))

    return found


# ----------------------------------------------------------------------
# Building one plan's history
# ----------------------------------------------------------------------


def _filings(session: Session, plan_id: int) -> list[Filing]:
    return list(
        session.execute(
            select(Filing).where(Filing.plan_id == plan_id).order_by(Filing.form_year)
        ).scalars()
    )


def _parties(session: Session, plan_id: int) -> list[tuple[PlanParty, Provider]]:
    return list(
        session.execute(
            select(PlanParty, Provider)
            .join(Provider, Provider.id == PlanParty.provider_id)
            .where(PlanParty.plan_id == plan_id)
            .order_by(PlanParty.form_year)
        ).all()
    )


def _name_timeline(pairs: Iterable[tuple[int, str | None]], filed_years) -> Timeline:  # noqa: ANN001
    return consolidate(
        (
            Observation(year=year, value=(value or "").strip())
            for year, value in pairs
            if (value or "").strip()
        ),
        filed_years=filed_years,
        bridge_gaps=False,
    )


def _recordkeeper_timeline(
    parties: list[tuple[PlanParty, Provider]], filed_years: tuple[int, ...]
) -> Timeline:
    """
    Who kept the records, year by year.

    Only a filed recordkeeper counts. Nothing is promoted into the role: a plan
    that named an investment manager and nobody else has no recordkeeper on
    record, and the report says exactly that.
    """

    observations: list[Observation] = []

    for party, provider in parties:
        if str(party.role) != PRIMARY_ROLE:
            continue

        name = provider.canonical_name or provider.name
        if is_investment_vehicle(name, party.role):
            continue

        codes = party.service_code_list()
        observations.append(
            Observation(
                year=party.form_year,
                value=name,
                confidence=recordkeeper_confidence(codes, party.schedule_code, party.confidence),
                source=f"Schedule {party.schedule_code or '?'}, field {party.source_field or '?'}",
            )
        )

    return consolidate(observations, filed_years=filed_years)


def _supporting_roles(
    parties: list[tuple[PlanParty, Provider]],
    filed_years: tuple[int, ...],
    *,
    include_investments: bool,
) -> tuple[list[ServiceRole], list[ServiceRole]]:
    """The other firms worth naming, and the investments held back from them."""

    keep: dict[tuple[str, str], list[Observation]] = {}
    funds: dict[tuple[str, str], list[Observation]] = {}

    for party, provider in parties:
        role = str(party.role)
        if role == PRIMARY_ROLE:
            continue

        name = provider.canonical_name or provider.name
        if not name:
            continue

        observation = Observation(
            year=party.form_year,
            value=name,
            confidence=party.confidence or ConfidenceLevel.MEDIUM,
            source=f"Schedule {party.schedule_code or '?'}",
        )

        if is_investment_vehicle(name, role):
            funds.setdefault((name, role), []).append(observation)
        elif role in SUPPORTING_ROLES:
            keep.setdefault((name, role), []).append(observation)
        elif include_investments:
            funds.setdefault((name, role), []).append(observation)

    def build(source: dict) -> list[ServiceRole]:  # noqa: ANN001
        built = [
            ServiceRole(
                name=name,
                role=role,
                timeline=consolidate(items, filed_years=filed_years),
            )
            for (name, role), items in source.items()
        ]
        built.sort(key=lambda item: (SUPPORTING_ORDER.get(item.role, 99), item.name.lower()))
        return built

    return build(keep), (build(funds) if include_investments else [])


SUPPORTING_ORDER = {role: index for index, role in enumerate(SUPPORTING_ROLES)}


def _plan_history(
    session: Session, plan: Plan, query: EmployerQuery
) -> PlanHistory | None:
    filings = _filings(session, plan.id)
    if not filings:
        return None

    filed_years = tuple(sorted({filing.form_year for filing in filings}))
    parties = _parties(session, plan.id)

    plan_type = classify_plan(plan.plan_features, plan.plan_category)

    wanted = query.resolved_type()
    if wanted is not None and plan_type.key != wanted.key:
        return None

    recordkeepers = _recordkeeper_timeline(parties, filed_years)
    supporting, investments = _supporting_roles(
        parties, filed_years, include_investments=query.include_investments
    )

    plan_names = _name_timeline(
        ((filing.form_year, filing.plan_name) for filing in filings), filed_years
    )
    sponsor_names = _name_timeline(
        ((filing.form_year, filing.sponsor_name) for filing in filings), filed_years
    )

    final = next((filing for filing in reversed(filings) if filing.is_final), None)

    history = PlanHistory(
        plan_id=plan.id,
        plan_type=plan_type,
        plan_name=plan.plan_name,
        plan_number=plan.plan_number or "",
        ein=plan.ein or "",
        first_year=plan.first_year or (filed_years[0] if filed_years else None),
        last_year=plan.last_year or (filed_years[-1] if filed_years else None),
        filed_years=filed_years,
        plan_names=plan_names.values,
        sponsor_names=sponsor_names.values,
        plan_name_history=plan_names,
        sponsor_name_history=sponsor_names,
        recordkeepers=recordkeepers,
        supporting=supporting,
        investments=investments,
        terminated=final is not None,
        final_year=final.form_year if final else None,
        participants=plan.latest_participants,
        total_assets=plan.latest_total_assets,
    )

    if history.terminated:
        try:
            history.successor = follow_chain(session, plan.id)
        except Exception:  # noqa: BLE001 - a missing chain must not sink the report
            history.successor = None

    history.sources = [
        SourceRecord(
            form_year=filing.form_year,
            form_type=str(filing.form_type or ""),
            ein=filing.ein or history.ein,
            plan_number=filing.plan_number or history.plan_number,
            plan_name=filing.plan_name or history.plan_name,
            recordkeeper=_recordkeeper_for(recordkeepers, filing.form_year),
            source=str(filing.source_dataset or ""),
        )
        for filing in filings
    ]

    return history


def _recordkeeper_for(timeline: Timeline, year: int) -> str:
    period = timeline.at(year)
    return period.value if period else ""


# ----------------------------------------------------------------------
# The report
# ----------------------------------------------------------------------


def build_report(session: Session, query: EmployerQuery) -> EmployerReport:
    """Assemble the whole history for one employer."""

    report = EmployerReport(query=query)

    plans, near = _employer_plans(session, query)
    report.alternatives = near

    if not plans:
        return report

    histories = [
        history
        for history in (_plan_history(session, plan, query) for plan in plans)
        if history is not None
    ]

    if query.form_year is not None:
        histories = [
            history for history in histories if query.form_year in history.filed_years
        ]

    histories.sort(
        key=lambda item: (
            _TYPE_ORDER.get(item.plan_type.key, 99),
            -(item.last_year or 0),
            item.plan_number,
        )
    )

    report.plans = histories

    every_name: list[str] = []
    for history in histories:
        for name in history.sponsor_names:
            if name not in every_name:
                every_name.append(name)

    report.historical_names = tuple(every_name)
    report.employer_name = every_name[0] if every_name else query.name
    report.current_name = every_name[-1] if every_name else query.name

    eins = sorted({history.ein for history in histories if history.ein})
    report.ein = ", ".join(eins)

    first = plans[0]
    report.location = ", ".join(
        part for part in (first.sponsor_city, first.sponsor_state) if part
    )

    report.years_held = tuple(
        sorted({year for history in histories for year in history.filed_years})
    )

    if query.plan_type and query.resolved_type() is None:
        report.notes.append(
            f"'{query.plan_type}' is not a plan type this report knows, so every "
            f"type is shown."
        )

    unresolved = [
        history for history in histories if not history.recordkeeper_known
    ]
    if unresolved:
        report.notes.append(
            f"{len(unresolved)} of {len(histories)} plan(s) name no recordkeeper in "
            f"the years held. That is what the filings say, not a guess withheld."
        )

    return report


_TYPE_ORDER = {
    plan_type.key: index
    for index, plan_type in enumerate(
        resolve_plan_type(key) or PlanType(key, key)
        for key in (
            "401k",
            "403b",
            "457b",
            "profit-sharing",
            "esop",
            "money-purchase",
            "cash-balance",
            "pension",
            "sep-simple",
            "other-dc",
            "other",
        )
    )
}


def latest_year(report: EmployerReport) -> int | None:
    """The most recent year anything was filed, for labelling 'present'."""

    return report.years_held[-1] if report.years_held else None


__all__ = [
    "EmployerQuery",
    "EmployerReport",
    "PlanHistory",
    "ServiceRole",
    "SourceRecord",
    "build_report",
    "find_employers",
    "latest_year",
]
