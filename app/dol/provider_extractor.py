from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.dol.schedules.normalizer import normalize_column_name, normalize_text


@dataclass(slots=True)
class ProviderCandidate:
    name: str
    source_field: str
    confidence: str
    reason: str
    role: str


ROLE_FIELDS: dict[str, str] = {
    "INS_CARRIER_NAME": "INSURER",
    "ACCOUNTANT_FIRM_NAME": "ACCOUNTANT",
    "FDCRY_TRUST_NAME": "TRUST",
    "FDCRY_TRUSTEE_CUST_NAME": "TRUSTEE_CUSTODIAN",
}


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
    candidates: list[ProviderCandidate] = []
    seen: set[tuple[str, str]] = set()

    for field_name, value in row.items():
        normalized_field = normalize_column_name(
            field_name
        )

        role = ROLE_FIELDS.get(
            normalized_field
        )

        if role is None:
            continue

        provider_name = clean_provider_name(value)

        if not provider_name:
            continue

        key = (
            normalized_field,
            provider_name.upper(),
        )

        if key in seen:
            continue

        seen.add(key)

        candidates.append(
            ProviderCandidate(
                name=provider_name,
                source_field=field_name,
                confidence="HIGH",
                reason=(
                    f"DOL field {normalized_field} "
                    f"is explicitly mapped to provider role "
                    f"{role}."
                ),
                role=role,
            )
        )

    return candidates