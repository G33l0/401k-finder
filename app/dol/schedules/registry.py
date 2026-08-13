from __future__ import annotations

from collections.abc import Iterable

from app.core.constants import SUPPORTED_FORM_YEARS
from app.dol.schedules.base import ScheduleDefinition


class ScheduleRegistry:
    """
    Registry for year-specific schedule definitions.

    The registry intentionally starts conservative. Definitions should
    be populated from the official DOL data dictionaries rather than
    guessed.
    """

    def __init__(
        self,
        definitions: Iterable[ScheduleDefinition] = (),
    ) -> None:
        self._definitions: dict[tuple[int, str], ScheduleDefinition] = {}

        for definition in definitions:
            self.register(definition)

    def register(self, definition: ScheduleDefinition) -> None:
        """Register or replace a schedule definition."""

        if definition.form_year not in SUPPORTED_FORM_YEARS:
            raise ValueError(
                f"Unsupported Form 5500 year: {definition.form_year}"
            )

        code = definition.code.strip().upper()

        if not code:
            raise ValueError("Schedule code cannot be empty.")

        self._definitions[(definition.form_year, code)] = definition

    def get(
        self,
        form_year: int,
        schedule_code: str,
    ) -> ScheduleDefinition | None:
        """Return a definition, if registered."""

        return self._definitions.get(
            (form_year, schedule_code.strip().upper())
        )

    def exists(
        self,
        form_year: int,
        schedule_code: str,
    ) -> bool:
        """Check whether a schedule is registered."""

        return self.get(form_year, schedule_code) is not None

    def for_year(
        self,
        form_year: int,
    ) -> tuple[ScheduleDefinition, ...]:
        """Return all registered schedules for a year."""

        return tuple(
            definition
            for (year, _), definition in self._definitions.items()
            if year == form_year
        )

    def all(self) -> tuple[ScheduleDefinition, ...]:
        """Return all registered definitions."""

        return tuple(self._definitions.values())