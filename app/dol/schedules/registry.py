from __future__ import annotations

from collections.abc import Iterable, Iterator

from app.dol.layouts import available_years
from app.dol.schedules.base import ScheduleDefinition


class ScheduleRegistry:
    """Lookup of schedule definitions by (form year, dataset or schedule code)."""

    def __init__(self, definitions: Iterable[ScheduleDefinition] = ()) -> None:
        self._by_dataset: dict[tuple[int, str], ScheduleDefinition] = {}
        self._by_code: dict[tuple[int, str], ScheduleDefinition] = {}

        for definition in definitions:
            self.register(definition)

    def register(self, definition: ScheduleDefinition) -> None:
        if definition.form_year not in available_years():
            raise ValueError(
                f"No vendored DOL layouts for form year {definition.form_year}."
            )

        dataset = definition.dataset.strip().upper()
        code = definition.code.strip().upper()

        if not dataset or not code:
            raise ValueError("Schedule definitions need both a dataset and a code.")

        self._by_dataset[(definition.form_year, dataset)] = definition
        self._by_code[(definition.form_year, code)] = definition

        for alias in definition.aliases:
            self._by_dataset[(definition.form_year, alias.strip().upper())] = definition

    def get(self, form_year: int, key: str) -> ScheduleDefinition | None:
        """Look up by dataset name, alias or schedule code."""

        needle = key.strip().upper()
        return self._by_dataset.get((form_year, needle)) or self._by_code.get(
            (form_year, needle)
        )

    def require(self, form_year: int, key: str) -> ScheduleDefinition:
        definition = self.get(form_year, key)

        if definition is None:
            raise KeyError(f"No schedule definition for {form_year} / {key}.")

        return definition

    def exists(self, form_year: int, key: str) -> bool:
        return self.get(form_year, key) is not None

    def for_year(self, form_year: int) -> tuple[ScheduleDefinition, ...]:
        seen: dict[int, ScheduleDefinition] = {}
        for (year, _), definition in self._by_dataset.items():
            if year == form_year:
                seen[id(definition)] = definition
        return tuple(sorted(seen.values(), key=lambda item: item.dataset))

    def all(self) -> tuple[ScheduleDefinition, ...]:
        seen: dict[int, ScheduleDefinition] = {
            id(definition): definition for definition in self._by_dataset.values()
        }
        return tuple(
            sorted(seen.values(), key=lambda item: (item.form_year, item.dataset))
        )

    def __iter__(self) -> Iterator[ScheduleDefinition]:
        return iter(self.all())

    def __len__(self) -> int:
        return len({id(definition) for definition in self._by_dataset.values()})
