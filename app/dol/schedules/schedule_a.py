"""Schedule A — insurance information, and Part 1 broker detail."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    built: list[ScheduleDefinition] = []

    if has_layout(form_year, "F_SCH_A"):
        built.append(
            ScheduleDefinition(
                code="A",
                name="Schedule A - Insurance Information",
                form_year=form_year,
                dataset="F_SCH_A",
                provider_columns=("INS_CARRIER_NAME",),
                notes=(
                    "Names the insurance company or HMO holding contracts for the "
                    "plan. For small plans and 403(b) arrangements this is often "
                    "the only place the asset holder is named."
                ),
                aliases=("SCH_A", "SCHEDULE_A"),
            )
        )

    if has_layout(form_year, "F_SCH_A_PART1"):
        built.append(
            ScheduleDefinition(
                code="A-1",
                name="Schedule A Part 1 - Insurance Brokers",
                form_year=form_year,
                dataset="F_SCH_A_PART1",
                provider_columns=("INS_BROKER_NAME",),
                notes="Agents and brokers paid commissions on the plan's contracts.",
                aliases=("SCH_A_PART1",),
            )
        )

    return tuple(built)
