from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    code: str
    name: str
    form_year: int

    required_columns: tuple[str, ...] = ()

    provider_columns: tuple[str, ...] = ()

    notes: str = ""

    aliases: tuple[str, ...] = field(
        default_factory=tuple
    )

    def matches_column(
        self,
        column_name: str,
    ) -> bool:
        normalized = column_name.strip().upper()

        return normalized in {
            column.strip().upper()
            for column in self.provider_columns
        }

    def has_required_column(
        self,
        column_name: str,
    ) -> bool:
        normalized = column_name.strip().upper()

        return normalized in {
            column.strip().upper()
            for column in self.required_columns
        }