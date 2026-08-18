"""What has actually been imported, and how completely."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import year_span
from app.database.models import ImportedDataset
from app.dol.catalog import CORE_DATASET_NAMES, INDEX_DATASET_NAMES
from app.dol.schedules import build_registry

COMPLETED = "COMPLETED"


def provider_schedules() -> frozenset[str]:
    """The schedules that name an asset holder."""

    return frozenset(
        definition.dataset
        for definition in build_registry(None).all()
        if definition.provider_columns and definition.dataset not in INDEX_DATASET_NAMES
    )


class Depth(StrEnum):
    """How much of a form year is held."""

    NONE = "NONE"
    INDEX = "INDEX"
    CORE = "CORE"
    FULL = "FULL"

    @property
    def has_providers(self) -> bool:
        return self in {Depth.CORE, Depth.FULL}

    @property
    def label(self) -> str:
        return {
            Depth.NONE: "not imported",
            Depth.INDEX: "employers and plans; no provider schedules",
            Depth.CORE: "employers, plans and providers",
            Depth.FULL: "everything published for the year",
        }[self]


@dataclass(frozen=True, slots=True)
class YearCoverage:
    form_year: int
    depth: Depth
    datasets: int

    @property
    def has_providers(self) -> bool:
        return self.depth.has_providers


def _depth_for(names: set[str]) -> Depth:
    if not names & set(INDEX_DATASET_NAMES):
        return Depth.NONE

    if not names & provider_schedules():
        return Depth.INDEX

    return Depth.FULL if len(names) > len(CORE_DATASET_NAMES) else Depth.CORE


def coverage(session: Session) -> list[YearCoverage]:
    """Every form year held locally, oldest first."""

    rows = session.execute(
        select(ImportedDataset.form_year, ImportedDataset.dataset).where(
            ImportedDataset.status == COMPLETED
        )
    ).all()

    by_year: dict[int, set[str]] = {}
    for form_year, dataset in rows:
        by_year.setdefault(int(form_year), set()).add(dataset)

    return [
        YearCoverage(form_year=year, depth=_depth_for(names), datasets=len(names))
        for year, names in sorted(by_year.items())
        if _depth_for(names) is not Depth.NONE
    ]


def summarise(entries: list[YearCoverage]) -> str:
    """One line describing what is held, for a status bar or a report header."""

    if not entries:
        return "no form years imported"

    indexed = [entry.form_year for entry in entries]
    detailed = [entry.form_year for entry in entries if entry.has_providers]

    span = year_span(min(indexed), max(indexed))
    text = f"{len(indexed)} year(s) searchable ({span})"

    if not detailed:
        return f"{text}; none with the schedules that name providers"

    if len(detailed) == len(indexed):
        return f"{text}, all with provider detail"

    detail_span = (
        year_span(min(detailed), max(detailed))
    )
    return f"{text}; provider detail for {len(detailed)} of them ({detail_span})"


def years_without_providers(entries: list[YearCoverage]) -> list[int]:
    """Years that would gain an asset holder if imported more deeply."""

    return [entry.form_year for entry in entries if not entry.has_providers]
