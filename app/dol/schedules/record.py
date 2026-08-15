from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScheduleRecordData:
    """
    A schedule row in flight, before it becomes a ScheduleRecord.

    The importer buffers these and writes them in batches, so keeping them as a
    plain dataclass rather than an ORM object keeps memory flat across the
    millions of rows in a full form year.
    """

    ack_id: str
    form_year: int
    dataset: str
    schedule_code: str
    raw_data: dict[str, Any]

    row_order: int | None = None
    source_file: str | None = None
    source_row: int | None = None

    plan_id: int | None = None
    filing_id: int | None = None

    def as_insert(self) -> dict[str, Any]:
        """Return the row mapping used for a bulk INSERT."""

        return {
            "ack_id": self.ack_id,
            "plan_id": self.plan_id,
            "filing_id": self.filing_id,
            "form_year": self.form_year,
            "dataset": self.dataset,
            "schedule_code": self.schedule_code,
            "row_order": self.row_order,
            "source_file": self.source_file,
            "source_row": self.source_row,
            "raw_data": self.raw_data,
        }
