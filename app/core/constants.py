from __future__ import annotations

from enum import StrEnum


class FormType(StrEnum):
    """The filing form a record came from."""

    FORM_5500 = "5500"
    FORM_5500_SF = "5500-SF"
    FORM_5500_DCG = "5500-DCG"


class FilingStatus(StrEnum):
    FILING_RECEIVED = "FILING_RECEIVED"
    PROCESSING_STOPPED = "PROCESSING_STOPPED"
    FILING_ERROR = "FILING_ERROR"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(StrEnum):
    """How directly a result is supported by a filed DOL field."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PlanCategory(StrEnum):
    """Top-level retirement-plan category derived from the benefit codes."""

    DEFINED_CONTRIBUTION = "DEFINED_CONTRIBUTION"
    DEFINED_BENEFIT = "DEFINED_BENEFIT"
    BOTH = "DB_AND_DC"
    WELFARE = "WELFARE"
    DFE = "DFE"
    UNKNOWN = "UNKNOWN"


class PlanFeature(StrEnum):
    """Specific retirement-account types a plan can carry."""

    K401 = "401K"
    B403 = "403B"
    B457 = "457B"
    SEP_SIMPLE_408 = "408_SEP_SIMPLE"
    PROFIT_SHARING = "PROFIT_SHARING"
    MONEY_PURCHASE = "MONEY_PURCHASE"
    TARGET_BENEFIT = "TARGET_BENEFIT"
    STOCK_BONUS = "STOCK_BONUS"
    ESOP = "ESOP"
    CASH_BALANCE = "CASH_BALANCE"
    PENSION_DB = "DEFINED_BENEFIT"
    PARTICIPANT_DIRECTED = "PARTICIPANT_DIRECTED"
    ERISA_404C = "ERISA_404C"
    MULTIPLE_EMPLOYER = "MULTIPLE_EMPLOYER"
    MULTIEMPLOYER = "MULTIEMPLOYER"
    POOLED_EMPLOYER = "POOLED_EMPLOYER"
    DEFINED_CONTRIB_GROUP = "DCG"


class ProviderRole(StrEnum):
    """The role an organisation plays for a plan."""

    RECORDKEEPER = "RECORDKEEPER"
    TRUSTEE = "TRUSTEE"
    CUSTODIAN = "CUSTODIAN"
    INSURER = "INSURER"
    INVESTMENT_MANAGER = "INVESTMENT_MANAGER"
    INVESTMENT_ADVISOR = "INVESTMENT_ADVISOR"
    BROKER = "BROKER"
    ADMINISTRATOR = "ADMINISTRATOR"
    THIRD_PARTY_ADMIN = "THIRD_PARTY_ADMINISTRATOR"
    ACCOUNTANT = "ACCOUNTANT"
    ACTUARY = "ACTUARY"
    ATTORNEY = "ATTORNEY"
    CONSULTANT = "CONSULTANT"
    PREPARER = "PREPARER"
    TRUST = "TRUST"
    INVESTMENT_VEHICLE = "INVESTMENT_VEHICLE"
    POOLED_PLAN_PROVIDER = "POOLED_PLAN_PROVIDER"
    PAYOR = "INDIRECT_COMPENSATION_PAYOR"
    SERVICE_PROVIDER = "SERVICE_PROVIDER"
    TERMINATED_ACCOUNTANT = "TERMINATED_ACCOUNTANT_OR_ACTUARY"


CUSTODIAL_ROLES: tuple[str, ...] = (
    ProviderRole.RECORDKEEPER,
    ProviderRole.TRUSTEE,
    ProviderRole.CUSTODIAN,
    ProviderRole.INSURER,
    ProviderRole.INVESTMENT_MANAGER,
)

ROLE_PRIORITY: tuple[str, ...] = (
    ProviderRole.RECORDKEEPER,
    ProviderRole.TRUSTEE,
    ProviderRole.CUSTODIAN,
    ProviderRole.INSURER,
    ProviderRole.INVESTMENT_MANAGER,
    ProviderRole.INVESTMENT_ADVISOR,
    ProviderRole.THIRD_PARTY_ADMIN,
    ProviderRole.ADMINISTRATOR,
    ProviderRole.POOLED_PLAN_PROVIDER,
    ProviderRole.TRUST,
    ProviderRole.INVESTMENT_VEHICLE,
    ProviderRole.BROKER,
    ProviderRole.CONSULTANT,
    ProviderRole.ACCOUNTANT,
    ProviderRole.ACTUARY,
    ProviderRole.ATTORNEY,
    ProviderRole.PREPARER,
    ProviderRole.PAYOR,
    ProviderRole.SERVICE_PROVIDER,
    ProviderRole.TERMINATED_ACCOUNTANT,
)


SUPPORTED_FORM_YEARS: tuple[int, ...] = tuple(range(2009, 2026))

EARLIEST_FORM_YEAR = SUPPORTED_FORM_YEARS[0]

LATEST_FORM_YEAR = SUPPORTED_FORM_YEARS[-1]

DOL_DATASET_PAGE_URL = (
    "https://www.dol.gov/agencies/ebsa/about-ebsa/"
    "our-activities/public-disclosure/foia/form-5500-datasets"
)

DOL_FILE_BASE_URL = "https://askebsa.dol.gov/FOIA%20Files"

EFAST_FILING_URL = "https://www.efast.dol.gov/5500search/"

USER_AGENT = "401K-Finder-Pro (DOL public-data research client)"


US_STATES: tuple[str, ...] = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
)


SOURCE_LABEL = "Department of Labour Database, USA"

#: Shown in a table cell or detail row when the filing left the field blank.
NOT_REPORTED = "Not reported"

#: The same idea in a dense table, where a full phrase would crowd the column.
BLANK_CELL = "-"


def year_span(first: int | None, last: int | None, *, joiner: str = "-") -> str:
    """A run of form years, collapsed when it covers only one."""

    if first is None and last is None:
        return "?"
    if first is None or last is None:
        return str(first if first is not None else last)
    if first == last:
        return str(first)

    return f"{first}{joiner}{last}"
