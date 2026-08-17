"""
A person's work history: the input to an account trace.

The unit is one job — an employer, roughly where, roughly when. That is all the
Form 5500 data can be matched against, and it is enough: the point of the trace
is to turn "I worked at a machine shop in Ohio around 2010" into a plan name, an
EIN, and the name of the firm that was holding the money at the time.

**No Social Security number is collected here, and none can be used.** Form 5500
is plan-level reporting; across all 448 published record layouts there is not one
field naming a participant. An SSN would have nothing to match against.

People will type one anyway, because every other lost-account service asks for
one. :func:`redact` and :func:`looks_like_ssn` exist for that moment: the number
is caught before it reaches the database, the log file or an exported report,
and the caller is told where an SSN genuinely does work — see
:mod:`app.trace.resources`.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.core.constants import US_STATES

#: A run of 9 digits, however it is grouped or separated. Deliberately broad:
#: the cost of a false positive is a prompt, and the cost of a miss is an SSN in
#: a log file.
_SSN = re.compile(r"\b(\d{3})[\s.\-–—]?(\d{2})[\s.\-–—]?(\d{4})\b")

#: Words that make a 9-digit run something else. An EIN is 9 digits too, and
#: sponsors legitimately appear with one.
_NOT_SSN_CONTEXT = re.compile(r"\b(ein|fein|tax\s*id|employer\s*id|plan\s*number)\b", re.I)

REDACTION = "[redacted]"


def looks_like_ssn(text: str) -> bool:
    """Whether the text contains something shaped like a Social Security number."""

    if not text or _NOT_SSN_CONTEXT.search(text):
        return False

    return _SSN.search(text) is not None


def redact(text: str) -> str:
    """
    Replace anything SSN-shaped with a marker.

    Applied on the way in, so a number typed into the wrong box cannot reach
    storage, the log, or an exported report. Redacting on the way out would be
    too late — it would already have been written down.
    """

    if not text or _NOT_SSN_CONTEXT.search(text):
        return text

    return _SSN.sub(REDACTION, text)


@dataclass(slots=True)
class Employment:
    """One job, as the person remembers it."""

    employer: str

    state: str | None = None
    city: str | None = None

    #: Calendar years worked. Either may be omitted; both omitted means "search
    #: every year on record", which is the right default for someone who cannot
    #: remember.
    start_year: int | None = None
    end_year: int | None = None

    #: Free text the person added, carried through to the report.
    note: str = ""

    def __post_init__(self) -> None:
        # Redaction happens at construction, so there is no path into the
        # application that skips it.
        self.employer = redact(self.employer.strip())
        self.note = redact(self.note.strip())

        if self.city:
            self.city = self.city.strip() or None
        if self.state:
            self.state = self.state.strip().upper()[:2] or None

        # People transpose these constantly, and a reversed range silently
        # matches nothing.
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
            return f"{self.start_year}–{self.end_year}"
        if self.start_year:
            return f"{self.start_year} onwards"
        if self.end_year:
            return f"until {self.end_year}"
        return ""

    def years(self, floor: int, ceiling: int) -> range:
        """
        The calendar years to look at, clamped to what has been imported.

        A form year and an employment year do not line up exactly — a plan year
        can straddle two calendar years, and a filing covering the year someone
        left is filed the year after. One year of slack on each side costs
        nothing and stops a genuine match being missed by a rounding error.
        """

        start = max((self.start_year or floor) - 1, floor)
        end = min((self.end_year or ceiling) + 1, ceiling)

        return range(start, end + 1) if start <= end else range(0)

    def overlaps(self, first_year: int | None, last_year: int | None) -> bool:
        """Whether this job could have overlapped a plan's filing history."""

        if first_year is None or last_year is None:
            return True

        # A year of slack each side, for the same reason `years` allows it: a
        # plan year straddles two calendar years and the final filing lands
        # after the person has already left.
        started_after = bool(self.start_year) and self.start_year > last_year + 1
        ended_before = bool(self.end_year) and self.end_year < first_year - 1

        return not (started_after or ended_before)


@dataclass(slots=True)
class WorkHistory:
    """Every job to search, in the order given."""

    jobs: list[Employment] = field(default_factory=list)

    #: Only ever used to head the printed report. Redacted like everything else.
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

    # ------------------------------------------------------------------

    @classmethod
    def from_csv(cls, path: Path, person: str = "") -> WorkHistory:
        """
        Read a work history from a CSV file.

        Expected headers, all optional but ``employer``:

            employer, city, state, start_year, end_year, note

        Written for a file someone typed by hand, so headers are matched
        case-insensitively and a row missing everything but a name still works.
        """

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

    # Tolerate "2010-01-01", "Jan 2010", "'10 " and similar.
    found = re.search(r"(19|20)\d{2}", value)
    return int(found.group(0)) if found else None
