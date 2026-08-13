from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule G definition for a specific filing year."""

    return ScheduleDefinition(
        code="G",
        name="Schedule G",
        form_year=form_year,
        notes=(
            "Schedule G information. Exact columns vary by filing year."
        ),
    )