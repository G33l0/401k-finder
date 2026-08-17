"""
Match a work history against filed plans.

This is the part that earns its keep. Given "a machine shop in Ohio, around
2010", it finds the plan, names the firm that was holding the money *at the
time*, and cites the filing that says so — which is the information a
participant needs before anyone will talk to them.

Three things make this more than a name search:

**Historical sponsor names.** Employers get acquired and renamed. The plans
table carries the name from the most recent filing, so an employer that no
longer exists under the name the person remembers would never match. Every
filing keeps the sponsor name as filed *that year*, so those are searched too —
and when the match comes from an old name, the report says which one, because
"we found it, it is called something else now" is the answer.

**The provider as of the right year.** The recordkeeper in 2010 is often not the
recordkeeper today. Engagements are stored per form year, so the trace reports
who held the money during the employment, and separately who holds it now.

**Whether the plan still exists.** A final filing changes the advice completely:
the money went somewhere, and the destination is a different search. That is
detected rather than left for the reader to notice.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import ROLE_PRIORITY
from app.core.logging import get_logger
from app.database.models import Filing, Plan, PlanParty, Provider
from app.dol.normalizer import normalize_name_key
from app.plans.successor import SuccessorChain, follow_chain
from app.trace.history import Employment, WorkHistory

logger = get_logger(__name__)

try:
    from rapidfuzz import fuzz

    _HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - optional dependency
    _HAVE_RAPIDFUZZ = False

#: Roles that answer "who is holding the money", best first.
HOLDER_ROLES: tuple[str, ...] = (
    "RECORDKEEPER",
    "TRUSTEE",
    "CUSTODIAN",
    "INSURER",
    "INVESTMENT_MANAGER",
    "TRUST",
    "INVESTMENT_VEHICLE",
    "THIRD_PARTY_ADMIN",
    "ADMINISTRATOR",
)

#: Below this, a candidate is noise. Deliberately permissive — a participant
#: would rather scan ten plans than miss the one that is theirs.
MIN_SCORE = 55.0

#: Candidate rows pulled from the database per job before scoring.
CANDIDATE_LIMIT = 400

#: Words that carry no identifying weight in an employer name.
_NOISE = frozenset(
    # fmt: off
    (
        "inc", "incorporated", "co", "company", "corp", "corporation", "llc",
        "llp", "lp", "ltd", "limited", "plc", "holdings", "holding", "group",
        "the", "and", "of", "a", "an", "service", "services", "systems",
        "enterprises", "industries", "international", "intl", "usa", "us",
        "america", "american", "national",
    )
    # fmt: on
)


def _tokens(value: str) -> set[str]:
    return {word for word in normalize_name_key(value).split() if word not in _NOISE}


def _similarity(needle: str, candidate: str) -> float:
    """How alike two employer names are, 0–100."""

    left, right = normalize_name_key(needle), normalize_name_key(candidate)

    if not left or not right:
        return 0.0
    if left == right:
        return 100.0

    if _HAVE_RAPIDFUZZ:
        # token_set_ratio handles "Acme Manufacturing" against "Acme
        # Manufacturing Company Inc Retirement Plan" — a containment case that
        # plain ratio scores badly and that happens constantly here, because
        # plan names embed the sponsor name.
        return max(
            fuzz.token_set_ratio(left, right),
            fuzz.partial_ratio(left, right) * 0.95,
        )

    distinct_left, distinct_right = _tokens(needle), _tokens(candidate)
    if not distinct_left or not distinct_right:
        return 0.0

    if distinct_left <= distinct_right or distinct_right <= distinct_left:
        return 94.0

    overlap = len(distinct_left & distinct_right)
    return 100.0 * overlap / max(len(distinct_left), len(distinct_right))


@dataclass(slots=True)
class Holder:
    """A firm that held or administered the money, in a given year."""

    name: str
    role: str
    form_year: int
    schedule_code: str | None
    source_field: str | None
    confidence: str | None

    @property
    def role_label(self) -> str:
        return self.role.replace("_", " ").title()

    def citation(self) -> str:
        return (
            f"Schedule {self.schedule_code or '?'}, "
            f"field {self.source_field or '?'}, form year {self.form_year}"
        )


@dataclass(slots=True)
class PlanMatch:
    """One plan that may hold an account for this person."""

    plan_id: int
    plan_name: str
    sponsor_name: str | None
    ein: str | None
    plan_number: str | None
    city: str | None
    state: str | None

    plan_category: str | None
    features: tuple[str, ...]

    first_year: int | None
    last_year: int | None
    participants: int | None
    total_assets: float | None

    score: float
    reasons: list[str] = field(default_factory=list)

    #: The name the employer filed under during the employment, when it differs
    #: from the name on the plan today.
    matched_as: str | None = None

    #: Holders during the years worked, best role first.
    holders_then: list[Holder] = field(default_factory=list)
    #: Holders on the most recent filing.
    holders_now: list[Holder] = field(default_factory=list)

    #: The plan filed a final return in this year, so it no longer exists.
    final_year: int | None = None

    #: Where the assets went, when the filings say. Populated for any plan that
    #: reported a transfer, not only terminated ones -- a plan can move part of
    #: its assets and carry on.
    successor: SuccessorChain | None = None

    #: Who holds the plan at the end of the chain. This is the answer for
    #: somebody whose own plan no longer exists.
    successor_holders: list[Holder] = field(default_factory=list)

    @property
    def plan_key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"

    @property
    def terminated(self) -> bool:
        return self.final_year is not None

    @property
    def moved(self) -> bool:
        """Whether the filings say the assets went somewhere else."""

        return bool(self.successor)

    @property
    def confidence(self) -> str:
        if self.score >= 88:
            return "STRONG"
        return "POSSIBLE" if self.score >= 70 else "WEAK"

    def best_holder(self) -> Holder | None:
        """Who to contact: whoever held it while they were there, else today's."""

        return next(iter(self.holders_then or self.holders_now), None)


@dataclass(slots=True)
class JobTrace:
    """Everything found for one job."""

    job: Employment
    matches: list[PlanMatch] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.matches)

    @property
    def strongest(self) -> PlanMatch | None:
        return next(iter(self.matches), None)


@dataclass(slots=True)
class TraceReport:
    """The result of tracing a whole work history."""

    history: WorkHistory
    traces: list[JobTrace] = field(default_factory=list)

    #: Form years present in the database, so the report can say what was
    #: actually searched rather than implying it covered everything.
    years_searched: tuple[int, ...] = ()

    #: How completely each year is held. An index-only year can match an
    #: employer but can never name a provider, and a reader who is not told
    #: that reads "no holder named" as "nobody holds it".
    coverage: list = field(default_factory=list)

    @property
    def total_matches(self) -> int:
        return sum(len(trace.matches) for trace in self.traces)

    @property
    def jobs_with_matches(self) -> list[JobTrace]:
        return [trace for trace in self.traces if trace.found]

    @property
    def jobs_without_matches(self) -> list[JobTrace]:
        return [trace for trace in self.traces if not trace.found]

    @property
    def any_terminated(self) -> bool:
        return any(
            match.terminated for trace in self.traces for match in trace.matches
        )

    @property
    def index_only_years(self) -> list[int]:
        """Years searchable by employer but carrying no provider detail."""

        return [entry.form_year for entry in self.coverage if not entry.has_providers]

    @property
    def has_defined_benefit(self) -> bool:
        return any(
            "PENSION_DB" in match.features or "CASH_BALANCE" in match.features
            for trace in self.traces
            for match in trace.matches
        )


class AccountTracer:
    """Traces a work history against the imported filings."""

    def __init__(self, session: Session, *, min_score: float = MIN_SCORE) -> None:
        self.session = session
        self.min_score = min_score

    # ------------------------------------------------------------------

    def trace(self, history: WorkHistory, limit_per_job: int = 8) -> TraceReport:
        from app.services.coverage import coverage

        report = TraceReport(
            history=history,
            years_searched=self._imported_years(),
            coverage=coverage(self.session),
        )

        for job in history:
            report.traces.append(
                JobTrace(job=job, matches=self.trace_job(job, limit=limit_per_job))
            )

        return report

    def trace_job(self, job: Employment, limit: int = 8) -> list[PlanMatch]:
        """Find the plans that could cover one job, best first."""

        if not job.employer.strip():
            return []

        scored: dict[int, PlanMatch] = {}

        for plan, matched_as in self._candidates(job):
            match = self._score(job, plan, matched_as)

            if match is None:
                continue

            # A plan can surface from both its current and a historical name.
            # Keep whichever scored better, but prefer to remember the old name,
            # since that is the part the reader needs explaining.
            existing = scored.get(plan.id)
            if existing is None or match.score > existing.score:
                if existing is not None and existing.matched_as and not match.matched_as:
                    match.matched_as = existing.matched_as
                scored[plan.id] = match

        ranked = sorted(scored.values(), key=lambda found: -found.score)[:limit]

        for match in ranked:
            self._attach_holders(match, job)
            self._attach_termination(match)
            self._attach_successor(match)

        return ranked

    # ------------------------------------------------------------------

    def _imported_years(self) -> tuple[int, ...]:
        rows = self.session.execute(
            select(Filing.form_year).distinct().order_by(Filing.form_year)
        ).scalars()
        return tuple(rows)

    def _candidates(self, job: Employment) -> list[tuple[Plan, str | None]]:
        """
        Pull plausible plans out of the database, cheaply.

        Two passes: the plans table for the employer as it is known now, and
        the filings table for the name it filed under at the time. The second
        is what finds a company that has since been acquired.
        """

        found: list[tuple[Plan, str | None]] = []
        seen: set[int] = set()

        for plan in self._by_current_name(job):
            if plan.id not in seen:
                seen.add(plan.id)
                found.append((plan, None))

        for plan, historical in self._by_historical_name(job):
            if plan.id not in seen:
                seen.add(plan.id)
                found.append((plan, historical))

        return found

    def _name_terms(self, job: Employment) -> list[str]:
        """The distinctive words to search on."""

        words = [word for word in _tokens(job.employer) if len(word) > 2]
        # Longest first: the rarest token is the most selective, and SQLite will
        # use the index on the first LIKE it can.
        return sorted(words, key=len, reverse=True)[:3] or [
            normalize_name_key(job.employer)
        ]

    def _by_current_name(self, job: Employment) -> list[Plan]:
        statement = select(Plan).where(Plan.is_retirement_plan.is_(True))

        patterns = [f"%{term}%" for term in self._name_terms(job)]
        if not patterns:
            return []

        statement = statement.where(
            or_(
                *[func.lower(Plan.sponsor_name).like(pattern) for pattern in patterns],
                *[func.lower(Plan.plan_name).like(pattern) for pattern in patterns],
                *[
                    func.lower(Plan.sponsor_dba_name).like(pattern)
                    for pattern in patterns
                ],
            )
        )

        if job.state:
            statement = statement.where(Plan.sponsor_state == job.state)

        statement = statement.order_by(Plan.latest_participants.desc()).limit(
            CANDIDATE_LIMIT
        )

        return list(self.session.execute(statement).scalars())

    def _by_historical_name(self, job: Employment) -> list[tuple[Plan, str]]:
        """Plans whose *filings* name this employer, under any past name."""

        patterns = [f"%{term}%" for term in self._name_terms(job)]
        if not patterns:
            return []

        statement = (
            select(Filing.plan_id, Filing.sponsor_name, Filing.form_year)
            .where(
                or_(*[func.lower(Filing.sponsor_name).like(p) for p in patterns]),
            )
            .order_by(Filing.form_year.desc())
            .limit(CANDIDATE_LIMIT)
        )

        if job.start_year or job.end_year:
            years = job.years(1990, 2100)
            if years:
                statement = statement.where(
                    Filing.form_year >= years.start, Filing.form_year < years.stop
                )

        rows = list(self.session.execute(statement))
        if not rows:
            return []

        by_plan = {row.plan_id: row.sponsor_name for row in rows}

        plans = self.session.execute(
            select(Plan).where(
                Plan.id.in_(by_plan), Plan.is_retirement_plan.is_(True)
            )
        ).scalars()

        return [(plan, by_plan[plan.id]) for plan in plans]

    # ------------------------------------------------------------------

    def _score(
        self, job: Employment, plan: Plan, matched_as: str | None
    ) -> PlanMatch | None:
        """Score one candidate, or None if it is not worth showing."""

        if not job.overlaps(plan.first_year, plan.last_year):
            return None

        reasons: list[str] = []

        # The name is the bulk of the score. A plan name usually contains the
        # sponsor name, so it is scored too, at a discount — matching "Acme" in
        # "Acme 401(k) Plan" is real evidence but weaker than matching the
        # sponsor field itself.
        candidates = [
            (plan.sponsor_name, 1.00, "sponsor name"),
            (matched_as, 1.00, "sponsor name as filed at the time"),
            (plan.sponsor_dba_name, 0.98, "trading name"),
            (plan.plan_name, 0.90, "plan name"),
        ]

        best = 0.0
        best_why = ""
        for value, weight, why in candidates:
            if not value:
                continue
            scored = _similarity(job.employer, value) * weight
            if scored > best:
                best, best_why = scored, why

        if best < self.min_score:
            return None

        score = best
        reasons.append(f"Employer name matches the {best_why}")

        if matched_as and normalize_name_key(matched_as) != normalize_name_key(
            plan.sponsor_name or ""
        ):
            reasons.append(
                f"Filed as “{matched_as}” at the time; now “{plan.sponsor_name}”"
            )

        if job.state and plan.sponsor_state == job.state:
            score += 6
            reasons.append(f"Sponsor is in {job.state}")
        elif job.state and plan.sponsor_state:
            score -= 10
            reasons.append(
                f"Sponsor is in {plan.sponsor_state}, not {job.state} — "
                f"the plan may be filed from a head office"
            )

        if (
            job.city
            and plan.sponsor_city
            and job.city.strip().lower() == plan.sponsor_city.strip().lower()
        ):
            score += 4
            reasons.append(f"Sponsor is in {plan.sponsor_city}")

        features = tuple((plan.plan_features or "").split("|")) if plan.plan_features else ()
        features = tuple(value for value in features if value)

        # An account balance is what someone is looking for; a defined benefit
        # pension is a different conversation but still worth surfacing.
        if plan.plan_category == "DEFINED_CONTRIBUTION":
            score += 5
            reasons.append("Defined contribution — an account with a balance")
        elif plan.plan_category == "DEFINED_BENEFIT":
            reasons.append("Defined benefit pension, not an account balance")

        if job.start_year or job.end_year:
            covered = self._years_covered(job, plan)
            if covered:
                score += 5
                reasons.append(
                    f"Filed for {covered[0]}–{covered[-1]}, covering when you were there"
                )
            else:
                score -= 15
                reasons.append("No filing covers the years you gave")

        return PlanMatch(
            plan_id=plan.id,
            plan_name=plan.plan_name,
            sponsor_name=plan.sponsor_name,
            ein=plan.ein,
            plan_number=plan.plan_number,
            city=plan.sponsor_city,
            state=plan.sponsor_state,
            plan_category=plan.plan_category,
            features=features,
            first_year=plan.first_year,
            last_year=plan.last_year,
            participants=plan.latest_participants,
            total_assets=plan.latest_total_assets,
            score=min(score, 100.0),
            reasons=reasons,
            matched_as=matched_as,
        )

    @staticmethod
    def _years_covered(job: Employment, plan: Plan) -> list[int]:
        if plan.first_year is None or plan.last_year is None:
            return []

        wanted = job.years(plan.first_year, plan.last_year)
        return [year for year in wanted if plan.first_year <= year <= plan.last_year]

    # ------------------------------------------------------------------

    _PRIORITY = {role: index for index, role in enumerate(ROLE_PRIORITY)}

    def _holder_rows(self, plan_id: int) -> list:
        """Every asset-holding engagement on a plan, newest year first."""

        return list(
            self.session.execute(
                select(
                    PlanParty.role,
                    PlanParty.form_year,
                    PlanParty.schedule_code,
                    PlanParty.source_field,
                    PlanParty.confidence,
                    Provider.name,
                    Provider.canonical_name,
                )
                .join(Provider, Provider.id == PlanParty.provider_id)
                .where(
                    PlanParty.plan_id == plan_id,
                    PlanParty.role.in_(HOLDER_ROLES),
                )
                .order_by(PlanParty.form_year.desc())
            )
        )

    @classmethod
    def _rank(cls, holder: Holder) -> tuple[int, int]:
        return (cls._PRIORITY.get(holder.role, 99), -holder.form_year)

    @staticmethod
    def _build_holder(row) -> Holder:  # noqa: ANN001
        return Holder(
            name=row.canonical_name or row.name,
            role=row.role,
            form_year=row.form_year,
            schedule_code=row.schedule_code,
            source_field=row.source_field,
            confidence=row.confidence,
        )

    def _holders_for(self, plan_id: int) -> list[Holder]:
        """Who holds a plan on its most recent filing."""

        rows = self._holder_rows(plan_id)
        if not rows:
            return []

        latest = max(row.form_year for row in rows)

        return self._dedupe(
            sorted(
                (self._build_holder(row) for row in rows if row.form_year == latest),
                key=self._rank,
            )
        )

    def _attach_holders(self, match: PlanMatch, job: Employment) -> None:
        """Who held the money then, and who holds it now."""

        rows = self._holder_rows(match.plan_id)
        if not rows:
            return

        wanted = set(job.years(match.first_year or 0, match.last_year or 9999))

        match.holders_then = self._dedupe(
            sorted(
                (self._build_holder(row) for row in rows if row.form_year in wanted),
                key=self._rank,
            )
        )
        match.holders_now = self._holders_for(match.plan_id)

    @staticmethod
    def _dedupe(holders: list[Holder]) -> list[Holder]:
        """One entry per firm and role — the same engagement is filed on several schedules."""

        seen: set[tuple[str, str]] = set()
        kept: list[Holder] = []

        for holder in holders:
            key = (normalize_name_key(holder.name), holder.role)
            if key in seen:
                continue
            seen.add(key)
            kept.append(holder)

        return kept

    def _attach_successor(self, match: PlanMatch) -> None:
        """
        Follow the assets forward, and find who holds them at the far end.

        This is the payoff of reading Schedule H Part 1: a participant whose
        plan was wound up gets told which plan it became and who administers
        that one, rather than being left to guess.
        """

        chain = follow_chain(self.session, match.plan_id)
        if not chain:
            return

        match.successor = chain

        final = chain.final
        if final is None or final.to_plan_id is None:
            return

        holders = self._holders_for(final.to_plan_id)
        match.successor_holders = holders

        match.reasons.append(
            f"Assets were transferred to {final.display_name}"
            + (f", now administered by {holders[0].name}" if holders else "")
        )

    def _attach_termination(self, match: PlanMatch) -> None:
        """A final filing means the plan no longer exists — the advice changes."""

        final_year = self.session.execute(
            select(func.max(Filing.form_year)).where(
                Filing.plan_id == match.plan_id, Filing.is_final.is_(True)
            )
        ).scalar()

        if final_year is not None:
            match.final_year = int(final_year)
            # Deliberately says only that it wound up. Whether the destination
            # is known is decided by _attach_successor, which runs next.
            match.reasons.append(
                f"The plan filed a final return for {final_year} and no longer exists"
            )
