from __future__ import annotations

import re
from typing import Any


def normalize_column_name(value: str) -> str:
    """
    Normalize a CSV column name for comparisons.

    Example:
        "Plan Name " -> "PLAN_NAME"
        "plan-name"  -> "PLAN_NAME"
    """

    value = value.strip().upper()
    value = re.sub(r"[^A-Z0-9]+", "_", value)
    return value.strip("_")


def normalize_text(value: Any) -> str | None:
    """Convert a source value to clean text."""

    if value is None:
        return None

    text = str(value).strip()

    return text if text else None


def normalize_ein(value: Any) -> str | None:
    """Normalize an EIN while retaining the conventional 9 digits."""

    text = normalize_text(value)

    if text is None:
        return None

    digits = re.sub(r"\D", "", text)

    if len(digits) != 9:
        return text

    return f"{digits[:2]}-{digits[2:]}"


def normalize_plan_number(value: Any) -> str | None:
    """Normalize a plan number."""

    text = normalize_text(value)

    if text is None:
        return None

    digits = re.sub(r"\D", "", text)

    if digits:
        return digits.zfill(3)

    return text