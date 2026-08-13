from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule D definition for a specific filing year."""

    return ScheduleDefinition(
        code="D",
        name="Schedule D",
        form_year=form_year,
        notes=(
            "Schedule D information. Exact columns must be obtained "
            "from the applicable DOL data dictionary."
        ),
    )