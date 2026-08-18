from __future__ import annotations

from dataclasses import dataclass

from app.dol.layouts import Layout, get_layout
from app.dol.normalizer import normalize_column_name


@dataclass(frozen=True, slots=True)
class ScheduleDefinition:
    """What the application knows about one dataset for one form year."""

    code: str
    name: str
    form_year: int
    dataset: str

    provider_columns: tuple[str, ...] = ()
    key_columns: tuple[str, ...] = ("ACK_ID",)
    notes: str = ""
    aliases: tuple[str, ...] = ()

    @property
    def layout(self) -> Layout | None:
        return get_layout(self.form_year, self.dataset)

    @property
    def columns(self) -> tuple[str, ...]:
        layout = self.layout
        return layout.field_names if layout else ()

    def has_column(self, column_name: str) -> bool:
        layout = self.layout
        return layout.has(column_name) if layout else False

    def is_provider_column(self, column_name: str) -> bool:
        normalized = normalize_column_name(column_name)
        return normalized in {normalize_column_name(name) for name in self.provider_columns}

    def missing_key_columns(self, columns: tuple[str, ...]) -> tuple[str, ...]:
        """Return the key columns absent from an actual CSV header."""

        present = {normalize_column_name(column) for column in columns}
        return tuple(
            column
            for column in self.key_columns
            if normalize_column_name(column) not in present
        )
