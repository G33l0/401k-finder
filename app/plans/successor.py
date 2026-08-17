"""
Following a plan's assets from one plan to the next.

When a plan merges or winds up, Schedule H Part 1 names the plan that received
its assets. Chained together, those rows answer the question a participant of a
dissolved plan actually has — *where did my money go* — and the answer is often
two or three hops away from where they started.

Two jobs live here:

:func:`resolve_transfers`
    Turns the reported EIN and plan number into a link to a plan this database
    already holds, so the chain can be walked. Runs after an import.

:func:`follow_chain`
    Walks the links, guarding against the cycles that real filings contain.
    Plans do report transfers to each other, and a naive walk over that hangs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Plan, PlanTransfer

logger = get_logger(__name__)

#: How far to follow a chain of mergers. Real chains are one or two hops; this
#: is a guard against pathological data, not a real limit.
MAX_HOPS = 8


def resolve_transfers(session: Session) -> int:
    """
    Point every transfer at the receiving plan, where we hold it.

    Matching is on (EIN, plan number), which is how DOL identifies a plan. A
    transfer whose target is not in the database keeps its reported name, EIN
    and plan number — that is still enough for a person to write to, and the
    link resolves by itself once the missing year is imported.

    Returns the number of transfers newly linked.
    """

    # A correlated subquery per row would rescan the plans table for every
    # transfer. One indexed join over the unresolved rows does it in a single
    # pass, which matters when a year brings tens of thousands of them.
    matched = (
        select(PlanTransfer.id.label("transfer_id"), Plan.id.label("plan_id"))
        .join(
            Plan,
            (Plan.ein == PlanTransfer.to_ein)
            & (Plan.plan_number == PlanTransfer.to_plan_number),
        )
        .where(
            PlanTransfer.to_plan_id.is_(None),
            PlanTransfer.to_ein.is_not(None),
            PlanTransfer.to_plan_number.is_not(None),
            # A plan reporting a transfer to itself is a filing error, and
            # linking it would build a self-loop for the walker to trip over.
            Plan.id != PlanTransfer.from_plan_id,
        )
        .subquery()
    )

    result = session.execute(
        update(PlanTransfer)
        .where(PlanTransfer.id == matched.c.transfer_id)
        .values(to_plan_id=matched.c.plan_id)
    )

    session.commit()

    linked = int(result.rowcount or 0)
    if linked:
        logger.info("Linked %s asset transfer(s) to plans held locally.", linked)

    return linked


@dataclass(slots=True)
class SuccessorStep:
    """One hop: assets left ``from_plan`` and arrived somewhere."""

    form_year: int

    to_name: str | None
    to_ein: str | None
    to_plan_number: str | None

    #: How many other transfers the same plan reported that year. A plan can
    #: split its assets across several, and a chain that silently picks one
    #: would present a guess as a fact.
    alternatives: int = 0

    #: Set when the receiving plan is in this database.
    to_plan_id: int | None = None
    to_plan_name: str | None = None
    to_sponsor_name: str | None = None
    to_last_year: int | None = None
    to_is_terminated: bool = False

    @property
    def key(self) -> str:
        return f"{self.to_ein or '?'}-{self.to_plan_number or '?'}"

    @property
    def resolved(self) -> bool:
        return self.to_plan_id is not None

    @property
    def display_name(self) -> str:
        return self.to_plan_name or self.to_name or self.key

    def describe(self) -> str:
        where = f"{self.display_name} (EIN {self.to_ein or '?'}, plan {self.to_plan_number or '?'})"
        text = f"In {self.form_year} the assets were transferred to {where}"

        if self.alternatives:
            text += (
                f", one of {self.alternatives + 1} plans named that year — the "
                f"balance may have been split"
            )

        return text


@dataclass(slots=True)
class SuccessorChain:
    """Every hop from a starting plan to wherever the assets ended up."""

    steps: list[SuccessorStep] = field(default_factory=list)

    #: True when the walk stopped because it came back to a plan already seen.
    looped: bool = False
    #: True when the walk stopped at MAX_HOPS rather than at an end.
    truncated: bool = False

    def __bool__(self) -> bool:
        return bool(self.steps)

    def __len__(self) -> int:
        return len(self.steps)

    @property
    def final(self) -> SuccessorStep | None:
        return self.steps[-1] if self.steps else None

    @property
    def ends_locally(self) -> bool:
        """Whether the last hop lands on a plan we can say something about."""

        return bool(self.final and self.final.resolved)

    def narrate(self) -> list[str]:
        """The chain in plain sentences, for a report."""

        lines = [step.describe() for step in self.steps]

        if self.looped:
            lines.append(
                "The filings then point back to a plan already in this chain, so "
                "the trail stops here."
            )
        elif self.truncated:
            lines.append(
                f"The chain continues beyond {MAX_HOPS} transfers and was not "
                f"followed further."
            )

        return lines


def transfers_from(session: Session, plan_id: int) -> list[PlanTransfer]:
    """
    Every transfer reported by one plan, best first.

    Ordered by year descending, then by whether the target is a plan we
    actually hold. A plan that reports several transfers in one year has split
    its assets, and of the destinations the traceable one is the only one this
    application can say anything further about — so it leads. Taking them in
    file order instead meant a followable chain could be abandoned in favour of
    a dead end that merely happened to be listed first.
    """

    return list(
        session.execute(
            select(PlanTransfer)
            .where(PlanTransfer.from_plan_id == plan_id)
            .order_by(
                PlanTransfer.form_year.desc(),
                PlanTransfer.to_plan_id.is_(None),
                PlanTransfer.id,
            )
        ).scalars()
    )


def _build_step(session: Session, transfer: PlanTransfer) -> SuccessorStep:
    step = SuccessorStep(
        form_year=transfer.form_year,
        to_name=transfer.to_name,
        to_ein=transfer.to_ein,
        to_plan_number=transfer.to_plan_number,
        to_plan_id=transfer.to_plan_id,
    )

    if transfer.to_plan_id is None:
        return step

    plan = session.get(Plan, transfer.to_plan_id)
    if plan is None:  # pragma: no cover - the foreign key makes this unreachable
        return step

    step.to_plan_name = plan.plan_name
    step.to_sponsor_name = plan.sponsor_name
    step.to_last_year = plan.last_year

    return step


def follow_chain(session: Session, plan_id: int, max_hops: int = MAX_HOPS) -> SuccessorChain:
    """
    Follow a plan's assets forward as far as the filings go.

    At each hop the most recent transfer is taken, because a plan winding up
    over two years reports the final destination last. Plans that have been
    visited are remembered: filings do contain loops, and without this the walk
    does not terminate.
    """

    chain = SuccessorChain()
    seen = {plan_id}
    current = plan_id

    for _ in range(max_hops):
        transfers = transfers_from(session, current)
        if not transfers:
            return chain

        step = _build_step(session, transfers[0])
        step.alternatives = sum(
            1
            for other in transfers[1:]
            if other.form_year == transfers[0].form_year
        )
        chain.steps.append(step)

        if step.to_plan_id is None:
            # The trail leaves the data we hold. The reported name and EIN are
            # still on the step, which is what the person writes to.
            return chain

        if step.to_plan_id in seen:
            chain.looped = True
            return chain

        seen.add(step.to_plan_id)
        current = step.to_plan_id

    chain.truncated = True
    return chain


def transfer_counts(session: Session) -> tuple[int, int]:
    """(total transfers recorded, how many resolve to a plan held locally)."""

    total = session.execute(select(func.count()).select_from(PlanTransfer)).scalar() or 0
    resolved = (
        session.execute(
            select(func.count())
            .select_from(PlanTransfer)
            .where(PlanTransfer.to_plan_id.is_not(None))
        ).scalar()
        or 0
    )

    return int(total), int(resolved)
