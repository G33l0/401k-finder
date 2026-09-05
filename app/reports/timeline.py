"""
Turning a row per year into a period.

Five filings naming the same recordkeeper are one fact, not five. This folds
consecutive years carrying the same value into a single period, and reports the
boundaries between periods as transitions, which is the thing a reader is
actually looking for.

Two rules keep it honest. A gap in the years is a gap, not a continuation: a
plan that filed in 2015 and again in 2019 has not been shown to have kept the
same recordkeeper in between, so those are separate periods unless the gap is
explicitly bridged. And a period only reads as running to the present when it
reaches the last year the plan filed *and* that is as recent as the data goes.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.core.constants import ConfidenceLevel


@dataclass(frozen=True, slots=True)
class Observation:
    """One year's answer, and how firmly it was established."""

    year: int
    value: str
    confidence: str = ConfidenceLevel.HIGH
    source: str = ""

    #: True when this year was filled from the years either side rather than
    #: read from a filing of its own.
    inferred: bool = False

    @property
    def is_known(self) -> bool:
        return bool(self.value)


@dataclass(slots=True)
class Period:
    """A run of consecutive years carrying one value."""

    value: str
    start: int
    end: int

    confidence: str = ConfidenceLevel.HIGH
    years: tuple[int, ...] = ()
    sources: tuple[str, ...] = ()

    #: Set when the years inside the run were not all filed, and the value was
    #: carried across because the years either side agreed.
    inferred_years: tuple[int, ...] = ()

    @property
    def single_year(self) -> bool:
        return self.start == self.end

    def label(self, latest_known: int | None = None) -> str:
        if self.single_year:
            return str(self.start)

        if latest_known is not None and self.end >= latest_known:
            return f"{self.start}-present"

        return f"{self.start}-{self.end}"

    def covers(self, year: int) -> bool:
        return self.start <= year <= self.end


@dataclass(frozen=True, slots=True)
class Transition:
    """The boundary between two periods."""

    year: int
    before: str
    after: str

    #: What the filing itself says about when the year began. Form 5500 records
    #: no date for a provider change, so this is the closest honest anchor.
    plan_year_begin: str = ""
    source: str = ""

    def describe(self) -> str:
        return f"{self.before} -> {self.after}"


@dataclass(slots=True)
class Timeline:
    """Every period for one thing, oldest first."""

    periods: list[Period] = field(default_factory=list)
    transitions: list[Transition] = field(default_factory=list)

    #: Years the plan filed but for which nothing was found.
    unknown_years: tuple[int, ...] = ()

    def __iter__(self):
        return iter(self.periods)

    def __len__(self) -> int:
        return len(self.periods)

    @property
    def current(self) -> Period | None:
        return self.periods[-1] if self.periods else None

    @property
    def values(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(period.value for period in self.periods))

    def at(self, year: int) -> Period | None:
        for period in self.periods:
            if period.covers(year):
                return period
        return None


def consolidate(
    observations: Iterable[Observation],
    *,
    filed_years: Iterable[int] = (),
    bridge_gaps: bool = True,
) -> Timeline:
    """
    Fold per-year observations into periods, and report the changes between.

    ``filed_years`` is every year the plan filed. A year in that list with no
    observation is a genuine unknown, and is reported as one rather than being
    quietly absorbed into the period on either side.
    """

    known = sorted(
        (item for item in observations if item.is_known), key=lambda item: item.year
    )
    every_year = sorted({int(year) for year in filed_years})

    if not known:
        return Timeline(unknown_years=tuple(every_year))

    by_year: dict[int, Observation] = {}
    for item in known:
        # A later, stronger reading of the same year wins.
        existing = by_year.get(item.year)
        if existing is None or _rank(item.confidence) > _rank(existing.confidence):
            by_year[item.year] = item

    if bridge_gaps:
        by_year = _bridge(by_year, every_year)

    ordered = [by_year[year] for year in sorted(by_year)]

    periods: list[Period] = []
    for item in ordered:
        current = periods[-1] if periods else None

        if (
            current is not None
            and current.value == item.value
            and _contiguous(current.end, item.year, every_year)
        ):
            current.end = item.year
            current.years = (*current.years, item.year)
            if item.source and item.source not in current.sources:
                current.sources = (*current.sources, item.source)
            if _rank(item.confidence) < _rank(current.confidence):
                current.confidence = item.confidence
            if item.inferred:
                current.inferred_years = (*current.inferred_years, item.year)
            continue

        periods.append(
            Period(
                value=item.value,
                start=item.year,
                end=item.year,
                confidence=item.confidence,
                years=(item.year,),
                sources=(item.source,) if item.source else (),
                inferred_years=(item.year,) if item.inferred else (),
            )
        )

    transitions = [
        Transition(
            year=later.start,
            before=earlier.value,
            after=later.value,
            source=later.sources[0] if later.sources else "",
        )
        for earlier, later in zip(periods, periods[1:], strict=False)
    ]

    missing = tuple(year for year in every_year if year not in by_year)

    return Timeline(periods=periods, transitions=transitions, unknown_years=missing)


_RANKS = {ConfidenceLevel.HIGH: 3, ConfidenceLevel.MEDIUM: 2, ConfidenceLevel.LOW: 1}


def _rank(confidence: str | None) -> int:
    return _RANKS.get(str(confidence or ""), 0)


def _contiguous(previous: int, current: int, filed_years: list[int]) -> bool:
    """
    Whether nothing sits between two years that would break a run.

    Consecutive years are contiguous. So are years separated only by form years
    the plan never filed, because a plan that skipped 2016 did not change
    provider in 2016; it simply did not file.
    """

    if current <= previous + 1:
        return True

    if not filed_years:
        return False

    return not any(previous < year < current for year in filed_years)


def _bridge(by_year: dict[int, Observation], filed_years: list[int]) -> dict[int, Observation]:
    """
    Fill a filed year that named nobody, when the years either side agree.

    A plan whose Schedule C was not imported for one year in the middle of a
    run has not changed provider that year. Filling it keeps the report from
    showing a spurious break, and the filled year is marked so it can be
    reported as inferred rather than filed.
    """

    if not filed_years:
        return by_year

    filled = dict(by_year)
    observed = sorted(by_year)

    for earlier, later in zip(observed, observed[1:], strict=False):
        if by_year[earlier].value != by_year[later].value:
            continue

        gap = [year for year in filed_years if earlier < year < later and year not in by_year]
        for year in gap:
            filled[year] = Observation(
                year=year,
                value=by_year[earlier].value,
                confidence=ConfidenceLevel.MEDIUM,
                source="carried across from the years either side",
                inferred=True,
            )

    return filled
