from __future__ import annotations

import re
from typing import Any

from app.dol.schedules.normalizer import (
    normalize_ein,
    normalize_plan_number,
    normalize_text,
)


def first_value(
    row: dict[str, Any],
    *names: str,
) -> Any:
    """
    Return the first non-empty value for the supplied column names.
    """

    normalized = {
        key.strip().upper(): value
        for key, value in row.items()
    }

    for name in names:
        value = normalized.get(name.upper())

        if value is not None:
            text = str(value).strip()

            if text:
                return value

    return None


def parse_ein(row: dict[str, Any]) -> str | None:
    value = first_value(
        row,
        "EIN",
        "SPONS_DFE_EIN",
        "SPONSOR_EIN",
        "SPONS_DFE_EIN_1",
    )

    return normalize_ein(value)


def parse_plan_number(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "PN",
        "PLAN_NUMBER",
        "PLAN_NO",
    )

    return normalize_plan_number(value)


def parse_plan_name(
    row: dict[str, Any],
) -> str:
    value = first_value(
        row,
        "PLAN_NAME",
        "PLAN_NAME_1",
        "PLAN_NAME_2",
    )

    normalized = normalize_text(value)

    return normalized or "UNKNOWN PLAN"


def parse_sponsor_name(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "SPONS_DFE_NAME",
        "SPONSOR_NAME",
        "SPONS_DFE_NAME_1",
        "SPONS_DFE_NAME_2",
    )

    return normalize_text(value)


def parse_state(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "SPONS_DFE_LOC_US_STATE",
        "SPONS_DFE_STATE",
        "SPONSOR_STATE",
        "STATE",
    )

    return normalize_text(value)


def parse_city(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "SPONS_DFE_LOC_US_CITY",
        "SPONS_DFE_CITY",
        "SPONSOR_CITY",
        "CITY",
    )

    return normalize_text(value)


def parse_zip(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "SPONS_DFE_LOC_US_ZIP",
        "SPONS_DFE_ZIP",
        "SPONSOR_ZIP",
        "ZIP",
    )

    return normalize_text(value)


def parse_filing_id(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "ACK_ID",
        "FILING_ID",
        "FILINGID",
        "ACKID",
    )

    return normalize_text(value)


def parse_filing_type(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "FORM_TAX_PRD",
        "FORM_TYPE",
        "FILING_TYPE",
    )

    return normalize_text(value)


def parse_status(
    row: dict[str, Any],
) -> str | None:
    value = first_value(
        row,
        "FILING_STATUS",
        "STATUS",
        "FILING_STATUS_CODE",
    )

    return normalize_text(value)


def extract_identity(
    row: dict[str, Any],
) -> dict[str, str | None]:
    """Extract the common filing identity fields."""

    return {
        "plan_number": parse_plan_number(row),
        "plan_name": parse_plan_name(row),
        "sponsor_name": parse_sponsor_name(row),
        "sponsor_ein": parse_ein(row),
        "sponsor_city": parse_city(row),
        "sponsor_state": parse_state(row),
        "sponsor_zip": parse_zip(row),
        "filing_id": parse_filing_id(row),
        "filing_type": parse_filing_type(row),
        "filing_status": parse_status(row),
    }


def infer_schedule_code(
    filename: str,
) -> str | None:
    """
    Attempt to identify a schedule code from a filename.

    This is only a filename hint.

    It must NOT be treated as authoritative if the dataset metadata
    identifies the schedule differently.
    """

    name = filename.upper()

    match = re.search(
        r"(?:^|[_\-\s])SCHEDULE[_\-\s]?([A-Z])(?:[_\-\s.]|$)",
        name,
    )

    if match:
        return match.group(1)

    match = re.search(
        r"(?:^|[_\-\s])SCH[_\-\s]?([A-Z])(?:[_\-\s.]|$)",
        name,
    )

    if match:
        return match.group(1)

    return None