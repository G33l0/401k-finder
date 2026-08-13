from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule I definition for a specific filing year."""

    return ScheduleDefinition(
        code="I",
        name="Schedule I",
        form_year=form_year,
        notes=(
            "Schedule I financial information for small plans. "
            "Exact columns vary by filing year."
        ),
    )