from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule R definition for a specific filing year."""

    return ScheduleDefinition(
        code="R",
        name="Schedule R",
        form_year=form_year,
        notes=(
            "Schedule R retirement-plan information. Exact columns "
            "vary by filing year."
        ),
    )