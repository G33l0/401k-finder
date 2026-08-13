from __future__ import annotations

from enum import StrEnum


class FilingType(StrEnum):
    FORM_5500 = "5500"
    FORM_5500_SF = "5500-SF"


class FilingStatus(StrEnum):
    FILING_RECEIVED = "FILING_RECEIVED"
    PROCESSING_STOPPED = "PROCESSING_STOPPED"
    FILING_ERROR = "FILING_ERROR"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


SUPPORTED_FORM_YEARS = tuple(range(2009, 2026))

LATEST_SUPPORTED_FORM_YEAR = 2025

DOL_DATASET_URL = (
    "https://www.dol.gov/agencies/ebsa/about-ebsa/"
    "our-activities/public-disclosure/foia/form-5500-datasets"
)