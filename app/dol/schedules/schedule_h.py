from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule H definition for a specific filing year."""

    return ScheduleDefinition(
        code="H",
        name="Schedule H",
        form_year=form_year,
        notes=(
            "Schedule H financial information for large plans. "
            "Exact columns vary by filing year."
        ),
    )