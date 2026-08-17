"""
Which plans changed provider, and who they moved between.

Every engagement is already stored with the form year it was filed for, so the
history is sitting in the database — this reads it rather than adding anything.
Compare a plan's provider in one year against the next and you get the question
a recordkeeper, third-party administrator or advisory firm actually pays to have
answered:

    43 plans changed recordkeeper. 19 of them left you. Here is where they went,
    with assets and participants.

**What this can and cannot say.** A change here means *the filings named a
different firm*. That is usually a real move, but not always: a plan can rename,
a filer can spell the same firm two ways, or the answer can come from a
different schedule in the second year. Provider names are consolidated first,
which removes most of it, and every change carries the schedule and field it was
read from so a surprising one can be checked rather than argued about.

The gaps are worth stating too. A plan that skips a year, or whose year has not
been imported, produces no change — not a "no change". :class:`ChangeQuery`
compares adjacent *observed* years per plan rather than assuming the whole range
is present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Plan, PlanParty, Provider
from app.dol.normalizer import normalize_name_key

logger = get_logger(__name__)


class ChangeKind(StrEnum):
    """What happened to a role between two years."""

    #: A different firm in the later year.
    SWITCHED = "SWITCHED"
    #: The role appears for the first time.
    GAINED = "GAINED"
    #: The role was filed before and is now absent.
    LOST = "LOST"

    @property
    def label(self) -> str:
        return {
            ChangeKind.SWITCHED: "switched",
            ChangeKind.GAINED: "appointed",
            ChangeKind.LOST: "no longer filed",
        }[self]


@dataclass(frozen=True, slots=True)
class ProviderChange:
    """One role on one plan changing hands between two filed years."""

    plan_id: int
    plan_name: str
    sponsor_name: str | None
    ein: str | None
    plan_number: str | None
    state: str | None

    role: str
    kind: ChangeKind

    from_year: int
    to_year: int

    from_provider: str | None
    to_provider: str | None

    participants: int | None
    total_assets: float | None

    #: Where the later observation was read from, so a surprising change can be
    #: checked against the filing rather than taken on trust.
    schedule_code: str | None = None
    source_field: str | None = None

    @property
    def plan_key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"

    @property
    def role_label(self) -> str:
        return self.role.replace("_", " ").title()

    def describe(self) -> str:
        match self.kind:
            case ChangeKind.SWITCHED:
                return (
                    f"{self.plan_name}: {self.role_label} moved from "
                    f"{self.from_provider} to {self.to_provider} "
                    f"({self.from_year} → {self.to_year})"
                )
            case ChangeKind.GAINED:
                return (
                    f"{self.plan_name}: {self.to_provider} appointed as "
                    f"{self.role_label} in {self.to_year}"
                )
            case _:
                return (
                    f"{self.plan_name}: {self.from_provider} no longer filed as "
                    f"{self.role_label} after {self.from_year}"
                )


@dataclass(slots=True)
class ChangeQuery:
    """What to look for."""

    #: Restrict to one role. Recordkeeper is the one people ask about.
    role: str = "RECORDKEEPER"

    #: Only changes whose later year is this. None means every year on record.
    year: int | None = None

    #: Only plans that moved away from this provider.
    from_provider: str | None = None
    #: Only plans that moved to this provider.
    to_provider: str | None = None

    state: str | None = None
    min_participants: int | None = None
    min_assets: float | None = None

    #: Whether to report roles appearing and disappearing, or only true swaps.
    #: Off by default: a role vanishing usually means the schedule that carried
    #: it was not imported, which would read as a wave of losses that never
    #: happened.
    include_gained: bool = False
    include_lost: bool = False

    limit: int = 500

    @property
    def kinds(self) -> set[ChangeKind]:
        wanted = {ChangeKind.SWITCHED}
        if self.include_gained:
            wanted.add(ChangeKind.GAINED)
        if self.include_lost:
            wanted.add(ChangeKind.LOST)
        return wanted


@dataclass(slots=True)
class ChangeReport:
    query: ChangeQuery
    changes: list[ProviderChange] = field(default_factory=list)

    #: Years actually compared, so an empty result can be read correctly.
    years_compared: tuple[int, ...] = ()

    @property
    def total(self) -> int:
        return len(self.changes)

    def losses(self, provider: str) -> list[ProviderChange]:
        """Plans that moved away from a named provider."""

        key = normalize_name_key(provider)
        return [
            change
            for change in self.changes
            if change.from_provider and normalize_name_key(change.from_provider) == key
        ]

    def wins(self, provider: str) -> list[ProviderChange]:
        key = normalize_name_key(provider)
        return [
            change
            for change in self.changes
            if change.to_provider and normalize_name_key(change.to_provider) == key
        ]

    def flows(self) -> list[tuple[str, str, int, float]]:
        """
        Where plans moved, aggregated: (from, to, plans, assets), biggest first.

        This is the shape people want on a slide.
        """

        totals: dict[tuple[str, str], list[float]] = {}

        for change in self.changes:
            if change.kind is not ChangeKind.SWITCHED:
                continue
            if not change.from_provider or not change.to_provider:
                continue

            entry = totals.setdefault((change.from_provider, change.to_provider), [0, 0.0])
            entry[0] += 1
            entry[1] += change.total_assets or 0.0

        return sorted(
            ((left, right, int(count), assets) for (left, right), (count, assets) in totals.items()),
            key=lambda row: (-row[2], -row[3]),
        )


class ChangeDetector:
    """Finds provider changes by comparing a plan's filed years."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def find(self, query: ChangeQuery | None = None) -> ChangeReport:
        wanted = query or ChangeQuery()
        report = ChangeReport(query=wanted)

        observations = self._observations(wanted)
        if not observations:
            return report

        years: set[int] = set()

        for (plan_id, role), by_year in observations.items():
            ordered = sorted(by_year)
            years.update(ordered)

            for earlier, later in zip(ordered, ordered[1:], strict=False):
                change = self._compare(plan_id, role, earlier, later, by_year)

                if change is None or change.kind not in wanted.kinds:
                    continue
                if wanted.year is not None and change.to_year != wanted.year:
                    continue
                if not self._matches_providers(change, wanted):
                    continue

                report.changes.append(change)

        report.years_compared = tuple(sorted(years))

        # Biggest plans first: a firm reviewing a list of losses cares about the
        # $400m one long before the $2m one.
        report.changes.sort(key=lambda item: (-(item.total_assets or 0.0), item.plan_name))
        report.changes = report.changes[: wanted.limit]

        self._attach_plan_details(report)
        return report

    # ------------------------------------------------------------------

    def _observations(
        self, query: ChangeQuery
    ) -> dict[tuple[int, str], dict[int, tuple[str, str | None, str | None]]]:
        """
        Every (plan, role, year) → provider seen, deduplicated.

        A plan can name the same firm on several schedules in one year. The
        first is kept; they are the same engagement filed twice, and counting
        them separately would invent changes that did not happen.
        """

        statement = (
            select(
                PlanParty.plan_id,
                PlanParty.role,
                PlanParty.form_year,
                PlanParty.schedule_code,
                PlanParty.source_field,
                Provider.name,
                Provider.canonical_name,
            )
            .join(Provider, Provider.id == PlanParty.provider_id)
            .join(Plan, Plan.id == PlanParty.plan_id)
            .where(Plan.is_retirement_plan.is_(True))
            .order_by(PlanParty.plan_id, PlanParty.form_year, PlanParty.id)
        )

        if query.role:
            statement = statement.where(PlanParty.role == query.role.upper())
        if query.state:
            statement = statement.where(Plan.sponsor_state == query.state.upper())
        if query.min_participants:
            statement = statement.where(Plan.latest_participants >= query.min_participants)
        if query.min_assets:
            statement = statement.where(Plan.latest_total_assets >= query.min_assets)

        found: dict[tuple[int, str], dict[int, tuple[str, str | None, str | None]]] = {}

        for row in self.session.execute(statement):
            by_year = found.setdefault((row.plan_id, row.role), {})
            by_year.setdefault(
                row.form_year,
                (row.canonical_name or row.name, row.schedule_code, row.source_field),
            )

        return found

    @staticmethod
    def _compare(
        plan_id: int,
        role: str,
        earlier: int,
        later: int,
        by_year: dict[int, tuple[str, str | None, str | None]],
    ) -> ProviderChange | None:
        before, _, _ = by_year[earlier]
        after, schedule, source_field = by_year[later]

        if normalize_name_key(before) == normalize_name_key(after):
            return None

        return ProviderChange(
            plan_id=plan_id,
            plan_name="",
            sponsor_name=None,
            ein=None,
            plan_number=None,
            state=None,
            role=role,
            kind=ChangeKind.SWITCHED,
            from_year=earlier,
            to_year=later,
            from_provider=before,
            to_provider=after,
            participants=None,
            total_assets=None,
            schedule_code=schedule,
            source_field=source_field,
        )

    @staticmethod
    def _matches_providers(change: ProviderChange, query: ChangeQuery) -> bool:
        if query.from_provider:
            key = normalize_name_key(query.from_provider)
            if not change.from_provider or key not in normalize_name_key(change.from_provider):
                return False

        if query.to_provider:
            key = normalize_name_key(query.to_provider)
            if not change.to_provider or key not in normalize_name_key(change.to_provider):
                return False

        return True

    def _attach_plan_details(self, report: ChangeReport) -> None:
        """
        Fill in the plan facts, in one query.

        Deliberately after the trim to ``limit``: joining plan columns into the
        scan would carry them for every engagement in the database, and only a
        few hundred rows are ever shown.
        """

        if not report.changes:
            return

        plan_ids = {change.plan_id for change in report.changes}

        plans = {
            row.id: row
            for row in self.session.execute(
                select(
                    Plan.id,
                    Plan.plan_name,
                    Plan.sponsor_name,
                    Plan.ein,
                    Plan.plan_number,
                    Plan.sponsor_state,
                    Plan.latest_participants,
                    Plan.latest_total_assets,
                ).where(Plan.id.in_(plan_ids))
            )
        }

        filled: list[ProviderChange] = []
        for change in report.changes:
            plan = plans.get(change.plan_id)
            if plan is None:  # pragma: no cover - the join guarantees this
                continue

            filled.append(
                ProviderChange(
                    plan_id=change.plan_id,
                    plan_name=plan.plan_name,
                    sponsor_name=plan.sponsor_name,
                    ein=plan.ein,
                    plan_number=plan.plan_number,
                    state=plan.sponsor_state,
                    role=change.role,
                    kind=change.kind,
                    from_year=change.from_year,
                    to_year=change.to_year,
                    from_provider=change.from_provider,
                    to_provider=change.to_provider,
                    participants=plan.latest_participants,
                    total_assets=plan.latest_total_assets,
                    schedule_code=change.schedule_code,
                    source_field=change.source_field,
                )
            )

        filled.sort(key=lambda item: (-(item.total_assets or 0.0), item.plan_name))
        report.changes = filled
