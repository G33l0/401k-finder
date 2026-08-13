from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScheduleRecordData:
    """
    Temporary in-memory representation of a schedule record.

    The importer converts this into the ScheduleRecord ORM object.
    """

    form_year: int
    schedule_code: str
    source_file: str | None
    source_row: int | None
    record_key: str | None
    raw_data: dict[str, Any]