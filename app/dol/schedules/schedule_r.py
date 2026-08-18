"""Schedule R: retirement plan information."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    built: list[ScheduleDefinition] = []

    if has_layout(form_year, "F_SCH_R"):
        built.append(
            ScheduleDefinition(
                code="R",
                name="Schedule R - Retirement Plan Information",
                form_year=form_year,
                dataset="F_SCH_R",
                notes=(
                    "Confirms 401(k) status (F_401K_PLAN_IND), ESOP features, "
                    "nondiscrimination testing method and the plan's asset "
                    "allocation. Used to refine plan classification rather than "
                    "to identify providers."
                ),
                aliases=("SCH_R", "SCHEDULE_R"),
            )
        )

    if has_layout(form_year, "F_SCH_R_PART1"):
        built.append(
            ScheduleDefinition(
                code="R-1",
                name="Schedule R Part 1 - Contributing Employers",
                form_year=form_year,
                dataset="F_SCH_R_PART1",
                notes="Employers contributing to a multiemployer plan.",
                aliases=("SCH_R_PART1",),
            )
        )

    return tuple(built)
