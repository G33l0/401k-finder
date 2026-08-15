from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

from app.dol.normalizer import normalize_column_name

DATA_PACKAGE = "app.dol.layouts.data"


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """One field of a DOL dataset, exactly as published in its layout file."""

    position: int
    name: str
    field_type: str
    size: int | None = None

    @property
    def is_numeric(self) -> bool:
        return self.field_type.upper() == "NUMERIC"

    @property
    def is_text(self) -> bool:
        return self.field_type.upper() == "TEXT"


@dataclass(frozen=True, slots=True)
class Layout:
    """The full field layout of a single dataset for a single form year."""

    form_year: int
    dataset: str
    source: str
    fields: tuple[FieldDefinition, ...]

    @property
    def field_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields)

    @property
    def normalized_names(self) -> frozenset[str]:
        return frozenset(normalize_column_name(field.name) for field in self.fields)

    def get(self, name: str) -> FieldDefinition | None:
        wanted = normalize_column_name(name)
        for field in self.fields:
            if normalize_column_name(field.name) == wanted:
                return field
        return None

    def has(self, name: str) -> bool:
        return self.get(name) is not None

    def numeric_names(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.is_numeric)

    def missing_from(self, columns: object) -> tuple[str, ...]:
        """Return layout fields absent from an iterable of CSV column names."""

        present = {normalize_column_name(column) for column in columns}  # type: ignore[union-attr]
        return tuple(
            field.name
            for field in self.fields
            if normalize_column_name(field.name) not in present
        )

    def unexpected_in(self, columns: object) -> tuple[str, ...]:
        """Return CSV column names that the published layout does not define."""

        known = self.normalized_names
        return tuple(
            str(column)
            for column in columns  # type: ignore[union-attr]
            if normalize_column_name(column) not in known
        )


@cache
def _load_year_document(form_year: int) -> dict[str, Any]:
    try:
        handle = resources.files(DATA_PACKAGE).joinpath(f"{form_year}.json")
        text = handle.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise KeyError(f"No vendored DOL layouts for form year {form_year}.") from exc

    document: dict[str, Any] = json.loads(text)
    return document


@cache
def available_years() -> tuple[int, ...]:
    """Return every form year with a vendored layout, oldest first."""

    years: list[int] = []
    for entry in resources.files(DATA_PACKAGE).iterdir():
        name = entry.name
        if name.endswith(".json") and name[:-5].isdigit():
            years.append(int(name[:-5]))
    return tuple(sorted(years))


def available_datasets(form_year: int) -> tuple[str, ...]:
    """Return every dataset name published for a form year."""

    try:
        document = _load_year_document(form_year)
    except KeyError:
        return ()
    return tuple(sorted(document["datasets"]))


@cache
def load_year(form_year: int) -> dict[str, Layout]:
    """Return every layout for a form year, keyed by dataset name."""

    document = _load_year_document(form_year)
    source = document.get("source", "")

    layouts: dict[str, Layout] = {}
    for dataset, raw_fields in document["datasets"].items():
        fields = tuple(
            FieldDefinition(
                position=int(entry["p"]),
                name=str(entry["n"]),
                field_type=str(entry["t"]),
                size=int(entry["s"]) if entry.get("s") is not None else None,
            )
            for entry in raw_fields
        )
        layouts[dataset.upper()] = Layout(
            form_year=form_year,
            dataset=dataset.upper(),
            source=source,
            fields=fields,
        )

    return layouts


def get_layout(form_year: int, dataset: str) -> Layout | None:
    """Return one dataset layout, or None when it was not published that year."""

    try:
        return load_year(form_year).get(dataset.upper())
    except KeyError:
        return None


def has_layout(form_year: int, dataset: str) -> bool:
    return get_layout(form_year, dataset) is not None


def iter_layouts() -> Iterator[Layout]:
    """Yield every vendored layout across every year."""

    for year in available_years():
        yield from load_year(year).values()
