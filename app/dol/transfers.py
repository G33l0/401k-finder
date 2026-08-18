"""Reading Schedule H Part 1: where a plan's assets went."""

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
        """Whether this is worth storing."""

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
