from __future__ import annotations

from collections.abc import Iterable

from app.core.constants import SUPPORTED_FORM_YEARS
from app.dol.schedules.base import ScheduleDefinition


class ScheduleRegistry:
    def __init__(
        self,
        definitions: Iterable[ScheduleDefinition] = (),
    ) -> None:
        self._definitions: dict[
            tuple[int, str],
            ScheduleDefinition,
        ] = {}

        for definition in definitions:
            self.register(definition)

    def register(
        self,
        definition: ScheduleDefinition,
    ) -> None:
        if definition.form_year not in SUPPORTED_FORM_YEARS:
            raise ValueError(
                f"Unsupported Form 5500 year: "
                f"{definition.form_year}"
            )

        code = definition.code.strip().upper()

        if not code:
            raise ValueError(
                "Schedule code cannot be empty."
            )

        self._definitions[
            (definition.form_year, code)
        ] = definition

    def get(
        self,
        form_year: int,
        schedule_code: str,
    ) -> ScheduleDefinition | None:
        return self._definitions.get(
            (
                form_year,
                schedule_code.strip().upper(),
            )
        )

    def require(
        self,
        form_year: int,
        schedule_code: str,
    ) -> ScheduleDefinition:
        definition = self.get(
            form_year,
            schedule_code,
        )

        if definition is None:
            raise KeyError(
                f"No schedule definition registered for "
                f"{form_year} Schedule {schedule_code}."
            )

        return definition

    def exists(
        self,
        form_year: int,
        schedule_code: str,
    ) -> bool:
        return self.get(
            form_year,
            schedule_code,
        ) is not None

    def for_year(
        self,
        form_year: int,
    ) -> tuple[ScheduleDefinition, ...]:
        return tuple(
            definition
            for (year, _),
            definition in self._definitions.items()
            if year == form_year
        )

    def all(
        self,
    ) -> tuple[ScheduleDefinition, ...]:
        return tuple(
            self._definitions.values()
        )