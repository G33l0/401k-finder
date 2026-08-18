from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatasetMetadata:
    """Metadata describing one locally managed DOL dataset."""

    form_year: int
    dataset_type: str
    source_url: str | None = None
    filename: str | None = None
    description: str | None = None


def validate_dataset_metadata(
    metadata: DatasetMetadata,
) -> None:
    """Validate dataset metadata."""

    if not 2009 <= metadata.form_year <= 2025:
        raise ValueError(
            f"Unsupported form year: {metadata.form_year}"
        )

    allowed_types = {
        "ALL",
        "LATEST",
    }

    if metadata.dataset_type.upper() not in allowed_types:
        raise ValueError(
            "dataset_type must be ALL or LATEST."
        )
