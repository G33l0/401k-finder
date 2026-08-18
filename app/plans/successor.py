"""Following a plan's assets from one plan to the next."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.database.models import Plan, PlanTransfer

logger = get_logger(__name__)

MAX_HOPS = 8


def resolve_transfers(session: Session) -> int:
    """Point every transfer at the receiving plan, where we hold it."""

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

    alternatives: int = 0

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
                f", one of {self.alternatives + 1} plans named that year, so the "
                f"balance may have been split"
            )

        return text


@dataclass(slots=True)
class SuccessorChain:
    """Every hop from a starting plan to wherever the assets ended up."""

    steps: list[SuccessorStep] = field(default_factory=list)

    looped: bool = False
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
    """Every transfer reported by one plan, best first."""

    return list(
        session.execute(
            select(PlanTransfer)
            .where(PlanTransfer.from_plan_id == plan_id)
            # A destination that resolved to a known plan sorts first, so the
            # chain follows a link it can actually walk.
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
    """Follow a plan's assets forward as far as the filings go."""

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
