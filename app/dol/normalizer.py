from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_NON_DIGIT = re.compile(r"\D+")

_LEGAL_SUFFIXES = frozenset(
    {
        "INC",
        "INCORPORATED",
        "LLC",
        "LLP",
        "LP",
        "LTD",
        "CO",
        "CORP",
        "CORPORATION",
        "COMPANY",
        "PC",
        "PA",
        "PLLC",
        "NA",
        "FSB",
        "THE",
        "AND",
        "OF",
    }
)

_TRUE_INDICATORS = frozenset({"1", "Y", "YES", "TRUE", "T", "X"})
_FALSE_INDICATORS = frozenset({"0", "N", "NO", "FALSE", "F", ""})

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
    "%Y%m%d",
    "%d-%b-%Y",
    "%Y-%m-%d %H:%M:%S",
    "%m/%d/%Y %H:%M:%S",
)


def normalize_column_name(value: Any) -> str:
    """Fold a column name to the canonical ``UPPER_SNAKE`` DOL form."""

    if value is None:
        return ""

    text = _NON_ALNUM.sub("_", str(value).strip().upper())
    return text.strip("_")


def normalize_text(value: Any) -> str:
    """Collapse whitespace and strip control characters from a raw CSV value."""

    if value is None:
        return ""

    text = str(value).replace("\x00", "")
    return _WHITESPACE.sub(" ", text).strip()


def normalize_ein(value: Any) -> str | None:
    """Return a nine-digit EIN, or None when the value is not a usable EIN."""

    text = normalize_text(value)
    if not text:
        return None

    digits = _NON_DIGIT.sub("", text)
    if not digits or len(digits) > 9:
        return None

    digits = digits.zfill(9)
    if digits == "000000000":
        return None

    return digits


def normalize_plan_number(value: Any) -> str | None:
    """Return a three-digit plan number (``PN``), or None."""

    text = normalize_text(value)
    if not text:
        return None

    digits = _NON_DIGIT.sub("", text)
    if not digits or len(digits) > 3:
        return None

    number = int(digits)
    if number <= 0:
        return None

    return f"{number:03d}"


def normalize_state(value: Any) -> str | None:
    """Return a two-letter US state/territory code, or None."""

    text = normalize_text(value).upper()
    if len(text) != 2 or not text.isalpha():
        return None
    return text


def normalize_zip(value: Any) -> str | None:
    """Return a 5-digit or ZIP+4 postal code, or None."""

    text = normalize_text(value)
    if not text:
        return None

    digits = _NON_DIGIT.sub("", text)
    if len(digits) >= 9:
        return f"{digits[:5]}-{digits[5:9]}"
    if len(digits) == 5:
        return digits
    if 0 < len(digits) < 5:
        return digits.zfill(5)
    return None


def normalize_name_key(value: Any) -> str:
    """Build the matching key used to deduplicate organisation names."""

    text = normalize_text(value).upper()
    if not text:
        return ""

    text = _NON_ALNUM.sub(" ", text)
    tokens = [token for token in text.split() if token]

    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()

    meaningful = [token for token in tokens if token not in _LEGAL_SUFFIXES]
    if meaningful:
        tokens = meaningful

    return " ".join(tokens)


def normalize_indicator(value: Any) -> bool | None:
    """Interpret a DOL ``*_IND`` field."""

    if value is None:
        return None

    text = normalize_text(value).upper()
    if text in _TRUE_INDICATORS:
        return True
    if text in _FALSE_INDICATORS:
        return None if text == "" else False
    return None


def parse_int(value: Any) -> int | None:
    """Parse a DOL count field, tolerating commas and stray decimals."""

    text = normalize_text(value)
    if not text:
        return None

    text = text.replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    try:
        parsed = int(Decimal(text))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None

    return -parsed if negative else parsed


def parse_decimal(value: Any) -> Decimal | None:
    """Parse a DOL amount field into an exact Decimal."""

    text = normalize_text(value)
    if not text:
        return None

    text = text.replace(",", "").replace("$", "")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]

    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None

    return -parsed if negative else parsed


def parse_money(value: Any) -> float | None:
    """Parse a DOL amount into a float for storage and aggregation."""

    parsed = parse_decimal(value)
    return None if parsed is None else float(parsed)


def parse_date(value: Any) -> date | None:
    """Parse the several date shapes that appear across DOL dataset years."""

    text = normalize_text(value)
    if not text or text.startswith("0000"):
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    return None


def parse_year(value: Any) -> int | None:
    """Extract a four-digit year from a date-like value."""

    parsed = parse_date(value)
    if parsed is not None:
        return parsed.year

    text = normalize_text(value)
    match = re.search(r"(19|20)\d{2}", text)
    return int(match.group(0)) if match else None


def split_codes(value: Any) -> tuple[str, ...]:
    """Split a DOL packed code field into individual codes."""

    text = normalize_text(value).upper()
    if not text:
        return ()

    separated = re.split(r"[\s,;/|]+", text)
    codes: list[str] = []

    for chunk in separated:
        chunk = chunk.strip()
        if not chunk:
            continue
        if re.fullmatch(r"(?:\d[A-Z])+", chunk):
            codes.extend(re.findall(r"\d[A-Z]", chunk))
        else:
            codes.append(chunk)

    seen: set[str] = set()
    unique: list[str] = []
    for code in codes:
        if code not in seen:
            seen.add(code)
            unique.append(code)

    return tuple(unique)


def split_numeric_codes(value: Any, width: int = 2) -> tuple[str, ...]:
    """Split a packed numeric code field, such as Schedule C service codes."""

    text = normalize_text(value)
    if not text:
        return ()

    if re.search(r"[\s,;/|]", text):
        parts = [part.strip() for part in re.split(r"[\s,;/|]+", text)]
        return tuple(part.zfill(width) for part in parts if part.isdigit())

    digits = _NON_DIGIT.sub("", text)
    if not digits or len(digits) % width:
        return (digits,) if digits else ()

    return tuple(digits[i : i + width] for i in range(0, len(digits), width))


__all__ = (
    "normalize_column_name",
    "normalize_ein",
    "normalize_indicator",
    "normalize_name_key",
    "normalize_plan_number",
    "normalize_state",
    "normalize_text",
    "normalize_zip",
    "parse_date",
    "parse_decimal",
    "parse_int",
    "parse_money",
    "parse_year",
    "split_codes",
    "split_numeric_codes",
)
