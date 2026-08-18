"""Schedules MB and SB: actuarial information for defined benefit plans."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition

_PARTS: tuple[tuple[str, str, str, str], ...] = (
    (
        "F_SCH_MB",
        "MB",
        "Schedule MB - Multiemployer Defined Benefit Actuarial Information",
        "Funding status and actuarial assumptions for multiemployer DB plans.",
    ),
    (
        "F_SCH_MB_PART1",
        "MB-1",
        "Schedule MB Part 1 - Withdrawn Employer Detail",
        "Employers that withdrew from a multiemployer plan.",
    ),
    (
        "F_SCH_SB",
        "SB",
        "Schedule SB - Single-Employer Defined Benefit Actuarial Information",
        "Funding target, effective interest rate and minimum required "
        "contribution for single-employer DB plans.",
    ),
    (
        "F_SCH_SB_PART1",
        "SB-1",
        "Schedule SB Part 1 - Amortization Bases",
        "Amortization bases underlying the minimum required contribution.",
    ),
)


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    return tuple(
        ScheduleDefinition(
            code=code,
            name=name,
            form_year=form_year,
            dataset=dataset,
            notes=notes,
            aliases=(dataset.removeprefix("F_"),),
        )
        for dataset, code, name, notes in _PARTS
        if has_layout(form_year, dataset)
    )
