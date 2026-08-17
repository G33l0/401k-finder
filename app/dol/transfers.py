"""
Reading Schedule H Part 1: where a plan's assets went.

A plan that merges into another, or winds up and hands its assets over, reports
the receiving plan here — by name, EIN and plan number. That triple is the only
statement in the whole Form 5500 dataset about *where the money went*, and it is
what turns "your plan no longer exists" into "your plan became this one, and
here is who holds it now".

It was previously read as a service provider, which was wrong in a way that
mattered: a transferee is not a firm the plan paid, it is another plan, and
filing it as a provider both polluted the provider list and threw away the EIN
and plan number that make it findable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.dol.normalizer import normalize_ein, normalize_plan_number, normalize_text

DATASET = "F_SCH_H_PART1"

NAME_COLUMN = "PLAN_TRANSFER_NAME"
EIN_COLUMN = "PLAN_TRANSFER_EIN"
PLAN_NUMBER_COLUMN = "PLAN_TRANSFER_PN"


@dataclass(frozen=True, slots=True)
class TransferTarget:
    """The plan named as receiving the assets."""

    name: str | None
    ein: str | None
    plan_number: str | None

    @property
    def is_identifiable(self) -> bool:
        """
        Whether this is worth storing.

        A name on its own is still worth keeping — it is what the person writes
        to. A row with nothing in it at all is not.
        """

        return bool(self.name or self.ein)

    @property
    def key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"


def extract_transfer(row: dict[str, Any]) -> TransferTarget | None:
    """Read one Schedule H Part 1 row, or None if it names nothing."""

    target = TransferTarget(
        name=normalize_text(row.get(NAME_COLUMN)) or None,
        ein=normalize_ein(row.get(EIN_COLUMN)),
        plan_number=normalize_plan_number(row.get(PLAN_NUMBER_COLUMN)),
    )

    return target if target.is_identifiable else None
