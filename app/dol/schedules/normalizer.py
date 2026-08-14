from __future__ import annotations

import re
from typing import Any


def normalize_column_name(
    value: Any,
) -> str:
    if value is None:
        return ""

    text = str(value).strip().upper()

    text = re.sub(
        r"[^A-Z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def normalize_text(
    value: Any,
) -> str:
    if value is None:
        return ""

    text = str(value).replace(
        "\x00",
        "",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()