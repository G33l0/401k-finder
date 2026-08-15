"""Schedule I — small plan financial information."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    if not has_layout(form_year, "F_SCH_I"):
        return ()

    return (
        ScheduleDefinition(
            code="I",
            name="Schedule I - Financial Information (Small Plans)",
            form_year=form_year,
            dataset="F_SCH_I",
            provider_columns=("FDCRY_TRUSTEE_CUST_NAME", "FDCRY_TRUST_NAME"),
            notes=(
                "Filed by plans with fewer than 100 participants that do not use "
                "the 5500-SF. Names the trustee or custodian holding plan assets."
            ),
            aliases=("SCH_I", "SCHEDULE_I"),
        ),
    )
