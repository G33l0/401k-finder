from __future__ import annotations

import re
from pathlib import Path
from typing import Any


from app.dol.schedules.normalizer import (
    normalize_ein,
    normalize_plan_number,
    normalize_text,
)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def first_value(
    row: dict[str, Any],
    *names: str,
) -> Any:
    """
    Return the first non-empty value for the supplied column names.

    Matching is case-insensitive and ignores surrounding whitespace.
    """

    normalized = {
        str(key).strip().upper(): value
        for key, value in row.items()
    }

    for name in names:
        value = normalized.get(name.strip().upper())

        if value is None:
            continue

        if isinstance(value, str):
            if value.strip():
                return value
        else:
            text = str(value).strip()

            if text:
                return value

    return None


def get_exact_value(
    row: dict[str, Any],
    name: str,
) -> Any:
    """
    Return a value using an exact normalized field name.

    This is useful when working with authoritative DOL layouts.
    """

    return first_value(row, name)


# ---------------------------------------------------------------------------
# Core identity parsing
# ---------------------------------------------------------------------------

def parse_ein(
    row: dict[str, Any],
) -> str | None:
    """
    Extract and normalize the sponsor/DFE EIN.
    """

    value = first_value(
        row,
        "SPONS_DFE_EIN",
        "EIN",
        "SPONSOR_EIN",
        "SPONS_DFE_EIN_1",
    )

    return normalize_ein(value)


def parse_plan_number(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the plan number.

    SPONS_DFE_PN is the authoritative 2025 Form 5500 field.
    """

    value = first_value(
        row,
        "SPONS_DFE_PN",
        "PN",
        "PLAN_NUMBER",
        "PLAN_NO",
        "PLAN_NUM",
    )

    return normalize_plan_number(value)


def parse_plan_name(
    row: dict[str, Any],
) -> str:
    """
    Extract the plan name.
    """

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
    """
    Extract the sponsor/DFE name.

    SPONSOR_DFE_NAME is the authoritative 2025 field.
    """

    value = first_value(
        row,
        "SPONSOR_DFE_NAME",
        "SPONS_DFE_NAME",
        "SPONSOR_NAME",
        "SPONS_DFE_NAME_1",
        "SPONS_DFE_NAME_2",
    )

    return normalize_text(value)


def parse_sponsor_dba_name(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the sponsor/DFE doing-business-as name.
    """

    value = first_value(
        row,
        "SPONS_DFE_DBA_NAME",
        "SPONSOR_DBA_NAME",
        "DBA_NAME",
    )

    return normalize_text(value)


def parse_city(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the sponsor/DFE US location city.
    """

    value = first_value(
        row,
        "SPONS_DFE_LOC_US_CITY",
        "SPONS_DFE_CITY",
        "SPONSOR_CITY",
        "CITY",
    )

    return normalize_text(value)


def parse_state(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the sponsor/DFE US location state.
    """

    value = first_value(
        row,
        "SPONS_DFE_LOC_US_STATE",
        "SPONS_DFE_STATE",
        "SPONSOR_STATE",
        "STATE",
    )

    return normalize_text(value)


def parse_zip(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the sponsor/DFE US ZIP/postal code.
    """

    value = first_value(
        row,
        "SPONS_DFE_LOC_US_ZIP",
        "SPONS_DFE_ZIP",
        "SPONSOR_ZIP",
        "ZIP",
    )

    return normalize_text(value)


# ---------------------------------------------------------------------------
# Filing metadata
# ---------------------------------------------------------------------------

def parse_filing_id(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the DOL filing acknowledgement ID.

    For Form 5500 this is ACK_ID.
    """

    value = first_value(
        row,
        "ACK_ID",
        "FILING_ID",
        "FILINGID",
        "ACKID",
    )

    return normalize_text(value)


def parse_form_plan_year_begin_date(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the beginning date of the plan year.
    """

    value = first_value(
        row,
        "FORM_PLAN_YEAR_BEGIN_DATE",
        "PLAN_YEAR_BEGIN_DATE",
        "PLAN_YEAR_START_DATE",
    )

    return normalize_text(value)


def parse_tax_period(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the tax period.

    IMPORTANT:
    FORM_TAX_PRD is a tax-period field, not a generic filing type.
    """

    value = first_value(
        row,
        "FORM_TAX_PRD",
        "TAX_PERIOD",
    )

    return normalize_text(value)


def parse_plan_effective_date(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the plan effective date.
    """

    value = first_value(
        row,
        "PLAN_EFF_DATE",
        "PLAN_EFFECTIVE_DATE",
    )

    return normalize_text(value)


def parse_filing_status(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the filing status.
    """

    value = first_value(
        row,
        "FILING_STATUS",
        "STATUS",
        "FILING_STATUS_CODE",
    )

    return normalize_text(value)


def parse_date_received(
    row: dict[str, Any],
) -> str | None:
    """
    Extract the DOL date received.
    """

    value = first_value(
        row,
        "DATE_RECEIVED",
        "RECEIVED_DATE",
    )

    return normalize_text(value)


def parse_form_type(
    row: dict[str, Any],
) -> str | None:
    """
    Extract an explicit form type when the source provides one.

    This deliberately does NOT use FORM_TAX_PRD because that field
    represents the tax period rather than the filing/form type.
    """

    value = first_value(
        row,
        "FORM_TYPE",
        "FILING_TYPE",
    )

    return normalize_text(value)


# ---------------------------------------------------------------------------
# Schedule attachment information
# ---------------------------------------------------------------------------

SCHEDULE_ATTACHMENT_FIELDS: tuple[tuple[str, str], ...] = (
    ("SCH_A_ATTACHED_IND", "A"),
    ("SCH_C_ATTACHED_IND", "C"),
    ("SCH_D_ATTACHED_IND", "D"),
    ("SCH_G_ATTACHED_IND", "G"),
    ("SCH_H_ATTACHED_IND", "H"),
    ("SCH_I_ATTACHED_IND", "I"),
    ("SCH_R_ATTACHED_IND", "R"),
    ("SCH_DCG_ATTACHED_IND", "DCG"),
    ("SCH_MEP_ATTACHED_IND", "MEP"),
    ("SCH_MB_ATTACHED_IND", "MB"),
    ("SCH_SB_ATTACHED_IND", "SB"),
)


def is_attached_indicator(value: Any) -> bool:
    """
    Interpret common DOL attachment indicator values.

    The function intentionally accepts several representations because
    CSV exports and future datasets may represent boolean indicators
    differently.
    """

    if value is None:
        return False

    text = str(value).strip().upper()

    return text in {
        "1",
        "Y",
        "YES",
        "TRUE",
        "T",
    }


def extract_schedule_attachments(
    row: dict[str, Any],
) -> tuple[str, ...]:
    """
    Return the schedule codes marked as attached.

    This identifies an attachment indicator only. It does NOT mean
    that a provider has been identified on that schedule.
    """

    attached: list[str] = []

    for field_name, schedule_code in SCHEDULE_ATTACHMENT_FIELDS:
        value = get_exact_value(row, field_name)

        if is_attached_indicator(value):
            attached.append(schedule_code)

    return tuple(attached)


def parse_schedule_attachments(
    row: dict[str, Any],
) -> dict[str, bool]:
    """
    Return all supported schedule attachment indicators.
    """

    return {
        field_name: is_attached_indicator(
            get_exact_value(row, field_name)
        )
        for field_name, _ in SCHEDULE_ATTACHMENT_FIELDS
    }


# ---------------------------------------------------------------------------
# 2025 Form 5500 identity
# ---------------------------------------------------------------------------

def extract_2025_identity(
    row: dict[str, Any],
) -> dict[str, str | None]:
    """
    Extract authoritative 2025 Form 5500 identity fields.

    This function uses the actual 2025 DOL field names supplied in
    the 2025 Form 5500 layout.
    """

    return {
        "ack_id": parse_filing_id(row),
        "plan_number": parse_plan_number(row),
        "plan_name": parse_plan_name(row),
        "sponsor_name": parse_sponsor_name(row),
        "sponsor_dba_name": parse_sponsor_dba_name(row),
        "sponsor_ein": parse_ein(row),
        "sponsor_city": parse_city(row),
        "sponsor_state": parse_state(row),
        "sponsor_zip": parse_zip(row),
        "plan_year_begin": parse_form_plan_year_begin_date(row),
        "tax_period": parse_tax_period(row),
        "plan_effective_date": parse_plan_effective_date(row),
        "filing_status": parse_filing_status(row),
        "date_received": parse_date_received(row),
    }


# ---------------------------------------------------------------------------
# Generic identity interface
# ---------------------------------------------------------------------------

def extract_identity(
    row: dict[str, Any],
) -> dict[str, str | None]:
    """
    Extract common filing identity information.

    This remains backward-compatible with the existing application
    while using the authoritative 2025 field names when available.
    """

    return {
        "plan_number": parse_plan_number(row),
        "plan_name": parse_plan_name(row),
        "sponsor_name": parse_sponsor_name(row),
        "sponsor_ein": parse_ein(row),
        "sponsor_city": parse_city(row),
        "sponsor_state": parse_state(row),
        "sponsor_zip": parse_zip(row),
        "filing_id": parse_filing_id(row),
        "filing_type": parse_form_type(row),
        "filing_status": parse_filing_status(row),
    }


# ---------------------------------------------------------------------------
# Filename schedule detection
# ---------------------------------------------------------------------------

def infer_schedule_code(
    filename: str,
) -> str | None:
    """
    Attempt to identify a schedule code from a filename.

    This is only a filename hint.

    It must NOT be treated as authoritative if dataset metadata
    identifies the schedule differently.
    """

    name = Path(filename).name.upper()

    # Examples:
    #   SCHEDULE_C
    #   SCHEDULE-C
    #   SCHEDULE C
    #   SCH_C
    #   SCH-C
    #   SCH C

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


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_2025_identity(
    row: dict[str, Any],
) -> tuple[str, ...]:
    """
    Validate the minimum fields needed to identify a 2025 filing.

    Returns a tuple containing validation errors.

    This does not reject a filing merely because optional information
    is absent.
    """

    errors: list[str] = []

    ack_id = parse_filing_id(row)
    plan_name = normalize_text(
        first_value(row, "PLAN_NAME")
    )
    sponsor_name = parse_sponsor_name(row)

    if not ack_id:
        errors.append("Missing ACK_ID")

    if not plan_name:
        errors.append("Missing PLAN_NAME")

    if not sponsor_name:
        errors.append("Missing SPONSOR_DFE_NAME")

    return tuple(errors)