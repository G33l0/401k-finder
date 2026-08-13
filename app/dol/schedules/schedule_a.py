from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


def definition(form_year: int) -> ScheduleDefinition:
    """Return the Schedule A definition for a specific filing year."""

    return ScheduleDefinition(
        code="A",
        name="Schedule A",
        form_year=form_year,
        notes=(
            "Insurance information. Exact columns must be interpreted "
            "according to the applicable DOL data dictionary."
        ),
    )