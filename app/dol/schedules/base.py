from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    """
    Description of a Form 5500 schedule for a particular year.

    This class deliberately does not assume that a schedule exists
    for every year.
    """

    code: str
    name: str
    form_year: int

    required_columns: tuple[str, ...] = ()

    provider_columns: tuple[str, ...] = ()

    notes: str = ""

    aliases: tuple[str, ...] = field(default_factory=tuple)

    def matches_column(self, column_name: str) -> bool:
        """Return True when column_name is a known provider column."""

        normalized = column_name.strip().upper()

        return normalized in {
            column.strip().upper()
            for column in self.provider_columns
        }