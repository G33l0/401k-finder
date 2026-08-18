"""Schedules DCG and MEP: group and multiple-employer arrangements (2023 onward)."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    built: list[ScheduleDefinition] = []

    if has_layout(form_year, "F_SCH_DCG"):
        built.append(
            ScheduleDefinition(
                code="DCG",
                name="Schedule DCG - Individual Plan Information",
                form_year=form_year,
                dataset="F_SCH_DCG",
                provider_columns=("DCG_ADMIN_NAME", "DCG_ACCOUNTANT_FIRM_NAME"),
                notes=(
                    "Introduced for the 2023 form year. Each row is one plan "
                    "inside a defined contribution group arrangement, so a single "
                    "5500 filing can cover hundreds of individual plans. Treated "
                    "as a filing dataset, not a schedule, because each row "
                    "identifies its own plan."
                ),
                aliases=("SCH_DCG",),
            )
        )

    if has_layout(form_year, "F_SCH_MEP"):
        built.append(
            ScheduleDefinition(
                code="MEP",
                name="Schedule MEP - Multiple-Employer Plan Information",
                form_year=form_year,
                dataset="F_SCH_MEP",
                notes=(
                    "Introduced for the 2023 form year. Identifies pooled employer "
                    "plans and links to the pooled plan provider's own filing "
                    "through MEP_PR_ACK_ID."
                ),
                aliases=("SCH_MEP",),
            )
        )

    return tuple(built)
