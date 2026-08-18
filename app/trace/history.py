"""A person's work history: the input to an account trace."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.constants import US_STATES, year_span

_SSN = re.compile(r"\b(\d{3})[\s.\-–—]?(\d{2})[\s.\-–—]?(\d{4})\b")

_NOT_SSN_CONTEXT = re.compile(r"\b(ein|fein|tax\s*id|employer\s*id|plan\s*number)\b", re.I)

REDACTION = "[redacted]"


def looks_like_ssn(text: str) -> bool:
    """Whether the text contains something shaped like a Social Security number."""

    if not text or _NOT_SSN_CONTEXT.search(text):
        return False

    return _SSN.search(text) is not None


def redact(text: str) -> str:
    """Replace anything SSN-shaped with a marker."""

    if not text or _NOT_SSN_CONTEXT.search(text):
        return text

    return _SSN.sub(REDACTION, text)


@dataclass(slots=True)
class Employment:
    """One job, as the person remembers it."""

    employer: str

    state: str | None = None
    city: str | None = None

    start_year: int | None = None
    end_year: int | None = None

    note: str = ""

    def __post_init__(self) -> None:
        self.employer = redact(self.employer.strip())
        self.note = redact(self.note.strip())

        if self.city:
            self.city = self.city.strip() or None
        if self.state:
            self.state = self.state.strip().upper()[:2] or None

        if self.start_year and self.end_year and self.start_year > self.end_year:
            self.start_year, self.end_year = self.end_year, self.start_year

    @property
    def label(self) -> str:
        where = ", ".join(part for part in (self.city, self.state) if part)
        when = self.year_range
        parts = [self.employer]
        if where:
            parts.append(f"({where})")
        if when:
            parts.append(when)
        return " ".join(parts)

    @property
    def year_range(self) -> str:
        if self.start_year and self.end_year:
            return year_span(self.start_year, self.end_year)
        if self.start_year:
            return f"{self.start_year} onwards"
        if self.end_year:
            return f"until {self.end_year}"
        return ""

    def years(self, floor: int, ceiling: int) -> range:
        """The calendar years to look at, clamped to what has been imported."""

        start = max((self.start_year or floor) - 1, floor)
        end = min((self.end_year or ceiling) + 1, ceiling)

        return range(start, end + 1) if start <= end else range(0)

    def overlaps(self, first_year: int | None, last_year: int | None) -> bool:
        """Whether this job could have overlapped a plan's filing history."""

        if first_year is None or last_year is None:
            return True

        started_after = bool(self.start_year) and self.start_year > last_year + 1
        ended_before = bool(self.end_year) and self.end_year < first_year - 1

        return not (started_after or ended_before)


@dataclass(slots=True)
class WorkHistory:
    """Every job to search, in the order given."""

    jobs: list[Employment] = field(default_factory=list)

    person: str = ""

    def __post_init__(self) -> None:
        self.person = redact(self.person.strip())

    def __iter__(self):
        return iter(self.jobs)

    def __len__(self) -> int:
        return len(self.jobs)

    def add(self, employer: str, **rest) -> Employment:
        job = Employment(employer=employer, **rest)
        self.jobs.append(job)
        return job

    @property
    def states(self) -> list[str]:
        """Every state named, for the unclaimed-property advice."""

        seen = {job.state for job in self.jobs if job.state}
        return sorted(state for state in seen if state in US_STATES)

    @classmethod
    def from_csv(cls, path: Path, person: str = "") -> WorkHistory:
        """Read a work history from a CSV file."""

        history = cls(person=person)

        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)

            if reader.fieldnames is None:
                raise ValueError(f"{path} is empty.")

            headers = {name.strip().lower(): name for name in reader.fieldnames if name}

            if "employer" not in headers:
                raise ValueError(
                    f"{path} needs an 'employer' column. "
                    f"Found: {', '.join(sorted(headers)) or 'nothing'}"
                )

            for row in reader:
                employer = (row.get(headers["employer"]) or "").strip()
                if not employer:
                    continue

                history.add(
                    employer,
                    city=_text(row, headers, "city"),
                    state=_text(row, headers, "state"),
                    start_year=_year(row, headers, "start_year"),
                    end_year=_year(row, headers, "end_year"),
                    note=_text(row, headers, "note") or "",
                )

        if not history.jobs:
            raise ValueError(f"{path} lists no employers.")

        return history


def _text(row: dict, headers: dict, key: str) -> str | None:
    value = (row.get(headers.get(key, ""), "") or "").strip()
    return value or None


def _year(row: dict, headers: dict, key: str) -> int | None:
    value = _text(row, headers, key)
    if not value:
        return None

    found = re.search(r"(19|20)\d{2}", value)
    return int(found.group(0)) if found else None
