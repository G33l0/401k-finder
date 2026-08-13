from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.dol.schedules.normalizer import (
    normalize_column_name,
    normalize_text,
)


@dataclass(slots=True)
class ProviderCandidate:
    name: str
    source_field: str
    confidence: str
    reason: str


_PROVIDER_HINTS = (
    "PROVIDER",
    "SERVICE_PROVIDER",
    "SERVICEPROVIDER",
    "TRUSTEE",
    "TRUST",
    "CUSTODIAN",
    "INVESTMENT_MANAGER",
    "INVESTMENT_MGR",
    "RECORDKEEPER",
    "ADMINISTRATOR",
    "ADMIN",
    "INSURANCE",
    "INSURER",
    "BROKER",
    "FUND",
    "BANK",
)


def looks_like_provider_field(
    field_name: str,
) -> bool:
    normalized = normalize_column_name(field_name)

    return any(
        hint in normalized
        for hint in _PROVIDER_HINTS
    )


def clean_provider_name(
    value: Any,
) -> str | None:
    text = normalize_text(value)

    if not text:
        return None

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if len(text) < 2:
        return None

    return text


def extract_provider_candidates(
    row: dict[str, Any],
) -> list[ProviderCandidate]:
    """
    Extract candidate provider names from a schedule row.

    This is intentionally a candidate extractor, not a final classifier.
    """

    candidates: list[ProviderCandidate] = []

    for field_name, value in row.items():
        if not looks_like_provider_field(field_name):
            continue

        provider_name = clean_provider_name(value)

        if not provider_name:
            continue

        candidates.append(
            ProviderCandidate(
                name=provider_name,
                source_field=field_name,
                confidence="MEDIUM",
                reason=(
                    "Column name contains a known provider/service "
                    "indicator."
                ),
            )
        )

    return candidates