from __future__ import annotations

from app.dol.schedules.base import ScheduleDefinition


FORM_YEAR = 2025
CODE = "C"
NAME = "Schedule C - Service Provider Information"


REQUIRED_COLUMNS: tuple[str, ...] = (
    "ACK_ID",
    "PROVIDER_EXCLUDE_IND",
)


PROVIDER_COLUMNS: tuple[str, ...] = ()


def definition(form_year: int) -> ScheduleDefinition:
    """
    Return the official 2025 Schedule C definition.

    The 2025 Schedule C base dataset layout contains:
        ACK_ID
        PROVIDER_EXCLUDE_IND

    Provider/service-provider detail is represented by the associated
    Schedule C Part 1 tables in the DOL dataset. We therefore do not
    invent a provider-name column in the base Schedule C definition.
    """

    if form_year != FORM_YEAR:
        raise ValueError(
            f"Schedule C is currently defined only for {FORM_YEAR}."
        )

    return ScheduleDefinition(
        code=CODE,
        name=NAME,
        form_year=FORM_YEAR,
        required_columns=REQUIRED_COLUMNS,
        provider_columns=PROVIDER_COLUMNS,
        notes=(
            "Official 2025 DOL Schedule C base layout. "
            "Provider detail is handled by Schedule C Part 1 "
            "dataset tables."
        ),
        aliases=("SCH_C", "SCHEDULE_C"),
    )