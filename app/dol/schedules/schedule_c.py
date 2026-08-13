from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule C definition for a specific filing year."""

    return ScheduleDefinition(
        code="C",
        name="Schedule C",
        form_year=form_year,
        notes=(
            "Service-provider and compensation information. Exact "
            "columns vary by filing year."
        ),
    )