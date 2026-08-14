from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


FORM_YEAR = 2025
CODE = "D"
NAME = "Schedule D"

FIELDS: tuple[str, ...] = (
    "ACK_ID",
    "SCH_D_PLAN_YEAR_BEGIN_DATE",
    "SCH_D_TAX_PRD",
    "SCH_D_PN",
    "SCH_D_EIN",
)


def definition(form_year: int) -> ScheduleDefinition:
    if form_year != FORM_YEAR:
        raise ValueError(
            f"Schedule D is currently defined only for {FORM_YEAR}."
        )

    return ScheduleDefinition(
        code=CODE,
        name=NAME,
        form_year=FORM_YEAR,
        required_columns=FIELDS,
        provider_columns=(),
        notes="2025 DOL Schedule D layout.",
        aliases=("SCH_D", "SCHEDULE_D"),
    )