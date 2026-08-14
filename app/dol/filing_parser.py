from __future__ import annotations

from typing import Any

from app.dol.schedules.normalizer import (
    normalize_ein,
    normalize_plan_number,
    normalize_text,
)


def get_value(
    row: dict[str, Any],
    field_name: str,
) -> Any:
    """Read an exact DOL field name."""

    if field_name in row:
        return row[field_name]

    # Defensive fallback for CSV headers containing whitespace.
    for key, value in row.items():
        if key.strip() == field_name:
            return value

    return None


def parse_2025_identity(
    row: dict[str, Any],
) -> dict[str, str | None]:
    """
    Parse the authoritative 2025 Form 5500 identity fields.
    """

    return {
        "ack_id": normalize_text(
            get_value(row, "ACK_ID")
        ),
        "plan_name": normalize_text(
            get_value(row, "PLAN_NAME")
        ),
        "plan_number": normalize_plan_number(
            get_value(row, "SPONS_DFE_PN")
        ),
        "sponsor_name": normalize_text(
            get_value(row, "SPONSOR_DFE_NAME")
        ),
        "sponsor_dba_name": normalize_text(
            get_value(row, "SPONS_DFE_DBA_NAME")
        ),
        "sponsor_ein": normalize_ein(
            get_value(row, "SPONS_DFE_EIN")
        ),
        "plan_year_begin": normalize_text(
            get_value(row, "FORM_PLAN_YEAR_BEGIN_DATE")
        ),
        "tax_period": normalize_text(
            get_value(row, "FORM_TAX_PRD")
        ),
        "plan_effective_date": normalize_text(
            get_value(row, "PLAN_EFF_DATE")
        ),
        "filing_status": normalize_text(
            get_value(row, "FILING_STATUS")
        ),
        "date_received": normalize_text(
            get_value(row, "DATE_RECEIVED")
        ),
    }


def parse_2025_schedule_attachments(
    row: dict[str, Any],
) -> dict[str, str | None]:
    """
    Extract the actual schedule attachment indicators
    from the 2025 Form 5500.
    """

    fields = (
        "SCH_R_ATTACHED_IND",
        "SCH_MB_ATTACHED_IND",
        "SCH_SB_ATTACHED_IND",
        "SCH_H_ATTACHED_IND",
        "SCH_I_ATTACHED_IND",
        "SCH_A_ATTACHED_IND",
        "SCH_C_ATTACHED_IND",
        "SCH_D_ATTACHED_IND",
        "SCH_G_ATTACHED_IND",
        "SCH_DCG_ATTACHED_IND",
        "SCH_MEP_ATTACHED_IND",
    )

    return {
        field: normalize_text(
            get_value(row, field)
        )
        for field in fields
    }


def attached_schedules_2025(
    row: dict[str, Any],
) -> tuple[str, ...]:
    """
    Return schedules marked as attached by the filing.

    The returned schedule names are only attachment indicators.
    They do not by themselves establish that a particular provider
    appears on that schedule.
    """

    mapping = (
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

    result: list[str] = []

    for field_name, schedule_code in mapping:
        value = normalize_text(
            get_value(row, field_name)
        )

        if value and value.upper() in {
            "1",
            "Y",
            "YES",
            "TRUE",
        }:
            result.append(schedule_code)

    return tuple(result)