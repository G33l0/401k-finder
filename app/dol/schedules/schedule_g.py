"""Schedule G — financial transaction schedules (defaults and non-exempt transactions)."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition

_PARTS: tuple[tuple[str, str, str], ...] = (
    ("F_SCH_G", "G", "Schedule G - Financial Transaction Schedules"),
    ("F_SCH_G_PART1", "G-1", "Schedule G Part 1 - Loans or Fixed Income in Default"),
    ("F_SCH_G_PART2", "G-2", "Schedule G Part 2 - Leases in Default or Uncollectible"),
    ("F_SCH_G_PART3", "G-3", "Schedule G Part 3 - Non-exempt Transactions"),
)


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    return tuple(
        ScheduleDefinition(
            code=code,
            name=name,
            form_year=form_year,
            dataset=dataset,
            notes="Reported irregularities. Kept for plan due diligence rather "
            "than provider identification.",
            aliases=(dataset.removeprefix("F_"),),
        )
        for dataset, code, name in _PARTS
        if has_layout(form_year, dataset)
    )
