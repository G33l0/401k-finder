"""Schedule D — DFE and participating-plan information."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition

_PARTS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "F_SCH_D",
        "D",
        "Schedule D - DFE/Participating Plan Information",
        (),
        "Base Schedule D record.",
    ),
    (
        "F_SCH_D_PART1",
        "D-1",
        "Schedule D Part 1 - Interests in Direct Filing Entities",
        ("DFE_P1_ENTITY_NAME", "DFE_P1_SPONS_NAME"),
        "Master trusts, collective trusts, pooled separate accounts and 103-12 "
        "investment entities the plan holds an interest in. This is where the "
        "asset holder appears for plans that invest through a pooled vehicle.",
    ),
    (
        "F_SCH_D_PART2",
        "D-2",
        "Schedule D Part 2 - Participating Plans",
        ("DFE_P2_PLAN_SPONS_NAME",),
        "For a DFE filing, the plans that participate in it.",
    ),
)


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    return tuple(
        ScheduleDefinition(
            code=code,
            name=name,
            form_year=form_year,
            dataset=dataset,
            provider_columns=providers,
            notes=notes,
            aliases=(dataset.removeprefix("F_"),),
        )
        for dataset, code, name, providers, notes in _PARTS
        if has_layout(form_year, dataset)
    )
