"""Turn a raw filing row into the normalized values the database stores."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.core.codes import (
    MULTIEMPLOYER_ENTITY_CODE,
    MULTIPLE_EMPLOYER_ENTITY_CODE,
    PLAN_CHARACTERISTICS,
)
from app.core.constants import FormType, PlanCategory, PlanFeature
from app.dol.normalizer import (
    normalize_ein,
    normalize_indicator,
    normalize_plan_number,
    normalize_state,
    normalize_text,
    normalize_zip,
    parse_date,
    parse_int,
    parse_money,
    split_codes,
)

UNKNOWN_PLAN_NAME = "UNKNOWN PLAN"


@dataclass(slots=True)
class ParsedFiling:
    """One filing, normalized and ready to persist."""

    ack_id: str
    form_type: str
    form_year: int

    plan_name: str = UNKNOWN_PLAN_NAME
    plan_number: str | None = None
    ein: str | None = None

    sponsor_name: str | None = None
    sponsor_dba_name: str | None = None
    sponsor_city: str | None = None
    sponsor_state: str | None = None
    sponsor_zip: str | None = None
    sponsor_phone: str | None = None
    business_code: str | None = None

    plan_year_begin: date | None = None
    plan_year_end: date | None = None
    plan_effective_date: date | None = None
    date_received: date | None = None
    filing_status: str | None = None

    is_initial: bool | None = None
    is_amended: bool | None = None
    is_final: bool | None = None
    is_short_year: bool | None = None

    plan_entity_code: str | None = None
    dfe_entity_code: str | None = None

    pension_codes: tuple[str, ...] = ()
    welfare_codes: tuple[str, ...] = ()

    total_participants: int | None = None
    active_participants: int | None = None
    participants_with_balances: int | None = None

    total_assets_boy: float | None = None
    total_assets_eoy: float | None = None
    net_assets_eoy: float | None = None
    employer_contributions: float | None = None
    participant_contributions: float | None = None

    admin_name: str | None = None
    admin_ein: str | None = None
    preparer_firm_name: str | None = None
    trust_name: str | None = None
    trustee_custodian_name: str | None = None
    accountant_firm_name: str | None = None

    plan_category: str = PlanCategory.UNKNOWN
    plan_features: tuple[str, ...] = ()

    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def is_retirement_plan(self) -> bool:
        return self.plan_category in {
            PlanCategory.DEFINED_CONTRIBUTION,
            PlanCategory.DEFINED_BENEFIT,
            PlanCategory.BOTH,
        }

    @property
    def plan_key(self) -> tuple[str | None, str | None]:
        return (self.ein, self.plan_number)


@dataclass(frozen=True, slots=True)
class FieldMap:
    """Maps one filing dataset's column names onto ParsedFiling attributes."""

    form_type: str
    plan_name: tuple[str, ...]
    plan_number: tuple[str, ...]
    ein: tuple[str, ...]
    sponsor_name: tuple[str, ...]
    sponsor_dba_name: tuple[str, ...] = ()
    sponsor_city: tuple[str, ...] = ()
    sponsor_state: tuple[str, ...] = ()
    sponsor_zip: tuple[str, ...] = ()
    sponsor_phone: tuple[str, ...] = ()
    business_code: tuple[str, ...] = ()
    plan_year_begin: tuple[str, ...] = ()
    plan_year_end: tuple[str, ...] = ()
    plan_effective_date: tuple[str, ...] = ()
    date_received: tuple[str, ...] = ()
    filing_status: tuple[str, ...] = ()
    initial_ind: tuple[str, ...] = ()
    amended_ind: tuple[str, ...] = ()
    final_ind: tuple[str, ...] = ()
    short_year_ind: tuple[str, ...] = ()
    plan_entity_code: tuple[str, ...] = ()
    dfe_entity_code: tuple[str, ...] = ()
    pension_codes: tuple[str, ...] = ()
    welfare_codes: tuple[str, ...] = ()
    total_participants: tuple[str, ...] = ()
    active_participants: tuple[str, ...] = ()
    participants_with_balances: tuple[str, ...] = ()
    total_assets_boy: tuple[str, ...] = ()
    total_assets_eoy: tuple[str, ...] = ()
    net_assets_eoy: tuple[str, ...] = ()
    employer_contributions: tuple[str, ...] = ()
    participant_contributions: tuple[str, ...] = ()
    admin_name: tuple[str, ...] = ()
    admin_ein: tuple[str, ...] = ()
    preparer_firm_name: tuple[str, ...] = ()
    trust_name: tuple[str, ...] = ()
    trustee_custodian_name: tuple[str, ...] = ()
    accountant_firm_name: tuple[str, ...] = ()


FORM_5500_MAP = FieldMap(
    form_type=FormType.FORM_5500,
    plan_name=("PLAN_NAME",),
    plan_number=("SPONS_DFE_PN",),
    ein=("SPONS_DFE_EIN",),
    sponsor_name=("SPONSOR_DFE_NAME", "SPONS_DFE_NAME"),
    sponsor_dba_name=("SPONS_DFE_DBA_NAME",),
    sponsor_city=("SPONS_DFE_LOC_US_CITY", "SPONS_DFE_MAIL_US_CITY"),
    sponsor_state=("SPONS_DFE_LOC_US_STATE", "SPONS_DFE_MAIL_US_STATE"),
    sponsor_zip=("SPONS_DFE_LOC_US_ZIP", "SPONS_DFE_MAIL_US_ZIP"),
    sponsor_phone=("SPONS_DFE_PHONE_NUM",),
    business_code=("BUSINESS_CODE",),
    plan_year_begin=("FORM_PLAN_YEAR_BEGIN_DATE",),
    plan_year_end=("FORM_TAX_PRD",),
    plan_effective_date=("PLAN_EFF_DATE",),
    date_received=("DATE_RECEIVED",),
    filing_status=("FILING_STATUS",),
    initial_ind=("INITIAL_FILING_IND",),
    amended_ind=("AMENDED_IND",),
    final_ind=("FINAL_FILING_IND",),
    short_year_ind=("SHORT_PLAN_YR_IND",),
    plan_entity_code=("TYPE_PLAN_ENTITY_CD",),
    dfe_entity_code=("TYPE_DFE_PLAN_ENTITY_CD",),
    pension_codes=("TYPE_PENSION_BNFT_CODE",),
    welfare_codes=("TYPE_WELFARE_BNFT_CODE",),
    total_participants=("TOT_PARTCP_BOY_CNT", "TOT_ACT_RTD_SEP_BENEF_CNT"),
    active_participants=("TOT_ACTIVE_PARTCP_CNT", "TOT_ACT_PARTCP_BOY_CNT"),
    participants_with_balances=("PARTCP_ACCOUNT_BAL_CNT",),
    admin_name=("ADMIN_NAME",),
    admin_ein=("ADMIN_EIN",),
    preparer_firm_name=("PREPARER_FIRM_NAME",),
)

FORM_5500_SF_MAP = FieldMap(
    form_type=FormType.FORM_5500_SF,
    plan_name=("SF_PLAN_NAME",),
    plan_number=("SF_PLAN_NUM",),
    ein=("SF_SPONS_EIN",),
    sponsor_name=("SF_SPONSOR_NAME",),
    sponsor_dba_name=("SF_SPONSOR_DFE_DBA_NAME",),
    sponsor_city=("SF_SPONS_LOC_US_CITY", "SF_SPONS_US_CITY"),
    sponsor_state=("SF_SPONS_LOC_US_STATE", "SF_SPONS_US_STATE"),
    sponsor_zip=("SF_SPONS_LOC_US_ZIP", "SF_SPONS_US_ZIP"),
    sponsor_phone=("SF_SPONS_PHONE_NUM",),
    business_code=("SF_BUSINESS_CODE",),
    plan_year_begin=("SF_PLAN_YEAR_BEGIN_DATE",),
    plan_year_end=("SF_TAX_PRD",),
    plan_effective_date=("SF_PLAN_EFF_DATE",),
    date_received=("DATE_RECEIVED",),
    filing_status=("FILING_STATUS",),
    initial_ind=("SF_INITIAL_FILING_IND",),
    amended_ind=("SF_AMENDED_IND",),
    final_ind=("SF_FINAL_FILING_IND",),
    short_year_ind=("SF_SHORT_PLAN_YR_IND",),
    plan_entity_code=("SF_PLAN_ENTITY_CD",),
    pension_codes=("SF_TYPE_PENSION_BNFT_CODE",),
    welfare_codes=("SF_TYPE_WELFARE_BNFT_CODE",),
    total_participants=("SF_TOT_PARTCP_BOY_CNT", "SF_TOT_ACT_RTD_SEP_BENEF_CNT"),
    active_participants=("SF_TOT_ACT_PARTCP_BOY_CNT", "SF_TOT_ACT_PARTCP_EOY_CNT"),
    participants_with_balances=("SF_PARTCP_ACCOUNT_BAL_CNT",),
    total_assets_boy=("SF_TOT_ASSETS_BOY_AMT",),
    total_assets_eoy=("SF_TOT_ASSETS_EOY_AMT",),
    net_assets_eoy=("SF_NET_ASSETS_EOY_AMT",),
    employer_contributions=("SF_EMPLR_CONTRIB_INCOME_AMT",),
    participant_contributions=("SF_PARTICIP_CONTRIB_INCOME_AMT",),
    admin_name=("SF_ADMIN_NAME",),
    admin_ein=("SF_ADMIN_EIN",),
    preparer_firm_name=("SF_PREPARER_FIRM_NAME",),
    trust_name=("SF_FDCRY_TRUST_NAME",),
    trustee_custodian_name=("SF_FDCRY_TRUSTE_CUST_NAME",),
)

SCH_DCG_MAP = FieldMap(
    form_type=FormType.FORM_5500_DCG,
    plan_name=("DCG_PLAN_NAME", "SCH_DCG_NAME"),
    plan_number=("DCG_PLAN_NUM", "SCH_DCG_PLAN_NUM"),
    ein=("DCG_SPONS_EIN", "SCH_DCG_EIN"),
    sponsor_name=("DCG_SPONSOR_NAME", "SCH_DCG_SPONSOR_NAME"),
    sponsor_dba_name=("DCG_SPONS_DBA_NAME",),
    sponsor_city=("DCG_SPONS_US_CITY",),
    sponsor_state=("DCG_SPONS_US_STATE",),
    sponsor_zip=("DCG_SPONS_US_ZIP",),
    sponsor_phone=("DCG_SPONS_PHONE_NUM",),
    business_code=("DCG_BUSINESS_CODE",),
    plan_year_begin=("SCH_DCG_PLAN_YEAR_BEGIN_DATE",),
    plan_year_end=("SCH_DCG_TAX_PRD",),
    plan_effective_date=("DCG_PLAN_EFF_DATE",),
    initial_ind=("DCG_INITIAL_FILING_IND",),
    amended_ind=("DCG_AMENDED_IND",),
    final_ind=("DCG_FINAL_IND",),
    plan_entity_code=("DCG_PLAN_TYPE",),
    pension_codes=("DCG_TYPE_PENSION_BNFT_CODE",),
    total_participants=("DCG_TOT_PARTCP_BOY_CNT", "DCG_TOT_ACT_RTD_SEP_BENEF_CNT"),
    active_participants=("DCG_TOT_ACT_PARTCP_EOY_CNT", "DCG_TOT_ACT_PARTCP_BOY_CNT"),
    participants_with_balances=("DCG_PARTCP_ACCOUNT_BAL_EOY_CNT",),
    total_assets_boy=("DCG_TOT_ASSETS_BOY_AMT",),
    total_assets_eoy=("DCG_TOT_ASSETS_EOY_AMT",),
    net_assets_eoy=("DCG_NET_ASSETS_EOY_AMT",),
    admin_name=("DCG_ADMIN_NAME",),
    admin_ein=("DCG_ADMIN_EIN",),
    accountant_firm_name=("DCG_ACCOUNTANT_FIRM_NAME",),
)

FIELD_MAPS: dict[str, FieldMap] = {
    "F_5500": FORM_5500_MAP,
    "F_5500_SF": FORM_5500_SF_MAP,
    "F_SCH_DCG": SCH_DCG_MAP,
}


def first_value(row: dict[str, Any], *names: str) -> Any:
    """Return the first non-empty value among the named columns."""

    for name in names:
        value = row.get(name)
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value
        else:
            return value
    return None


def _text(row: dict[str, Any], names: tuple[str, ...]) -> str | None:
    return normalize_text(first_value(row, *names)) or None


def classify_plan(
    pension_codes: tuple[str, ...],
    welfare_codes: tuple[str, ...],
    plan_entity_code: str | None = None,
    dfe_entity_code: str | None = None,
    form_type: str | None = None,
    schedule_r_401k: bool | None = None,
    plan_name: str | None = None,
) -> tuple[str, tuple[str, ...]]:
    """Derive the plan category and feature set from the filed characteristics codes."""

    features: set[str] = set()
    saw_dc = False
    saw_db = False
    saw_welfare = False

    for code in pension_codes:
        entry = PLAN_CHARACTERISTICS.get(code)
        if entry is None:
            continue
        if entry.category is PlanCategory.DEFINED_CONTRIBUTION:
            saw_dc = True
        elif entry.category is PlanCategory.DEFINED_BENEFIT:
            saw_db = True
        features.update(feature.value for feature in entry.features)

    for code in welfare_codes:
        if code in PLAN_CHARACTERISTICS:
            saw_welfare = True

    if dfe_entity_code:
        category = PlanCategory.DFE
    elif saw_dc and saw_db:
        category = PlanCategory.BOTH
    elif saw_dc:
        category = PlanCategory.DEFINED_CONTRIBUTION
    elif saw_db:
        category = PlanCategory.DEFINED_BENEFIT
    elif saw_welfare:
        category = PlanCategory.WELFARE
    else:
        category = PlanCategory.UNKNOWN

    if schedule_r_401k:
        features.add(PlanFeature.K401.value)
        if category in {PlanCategory.UNKNOWN, PlanCategory.WELFARE}:
            category = PlanCategory.DEFINED_CONTRIBUTION

    if plan_name and _looks_like_457(plan_name):
        features.add(PlanFeature.B457.value)
        if category is PlanCategory.UNKNOWN:
            category = PlanCategory.DEFINED_CONTRIBUTION

    if plan_entity_code == MULTIEMPLOYER_ENTITY_CODE:
        features.add(PlanFeature.MULTIEMPLOYER.value)
    elif plan_entity_code == MULTIPLE_EMPLOYER_ENTITY_CODE:
        features.add(PlanFeature.MULTIPLE_EMPLOYER.value)

    if form_type == FormType.FORM_5500_DCG:
        features.add(PlanFeature.DEFINED_CONTRIB_GROUP.value)
        if category is PlanCategory.UNKNOWN:
            category = PlanCategory.DEFINED_CONTRIBUTION

    return category.value, tuple(sorted(features))


_457_PATTERN = re.compile(
    r"\b457\s*(?:\(\s*[bfg]\s*\)|[bfg]\b)|\b457\b",
    re.IGNORECASE,
)


def _looks_like_457(plan_name: str) -> bool:
    return bool(_457_PATTERN.search(plan_name))


def parse_filing_row(
    row: dict[str, Any],
    dataset: str,
    form_year: int,
) -> ParsedFiling:
    """Parse one row of a filing dataset."""

    mapping = FIELD_MAPS.get(dataset.upper())
    if mapping is None:
        raise KeyError(f"{dataset} is not a filing dataset.")

    ack_id = normalize_text(first_value(row, "ACK_ID"))

    parsed = ParsedFiling(
        ack_id=ack_id,
        form_type=mapping.form_type,
        form_year=form_year,
    )

    if not ack_id:
        parsed.errors.append("Missing ACK_ID")

    parsed.plan_name = _text(row, mapping.plan_name) or UNKNOWN_PLAN_NAME
    if parsed.plan_name == UNKNOWN_PLAN_NAME:
        parsed.errors.append("Missing plan name")

    parsed.plan_number = normalize_plan_number(first_value(row, *mapping.plan_number))
    parsed.ein = normalize_ein(first_value(row, *mapping.ein))
    if parsed.ein is None:
        parsed.errors.append("Missing or unusable sponsor EIN")

    parsed.sponsor_name = _text(row, mapping.sponsor_name)
    parsed.sponsor_dba_name = _text(row, mapping.sponsor_dba_name)
    parsed.sponsor_city = _text(row, mapping.sponsor_city)
    parsed.sponsor_state = normalize_state(first_value(row, *mapping.sponsor_state))
    parsed.sponsor_zip = normalize_zip(first_value(row, *mapping.sponsor_zip))
    parsed.sponsor_phone = _text(row, mapping.sponsor_phone)
    parsed.business_code = _text(row, mapping.business_code)

    parsed.plan_year_begin = parse_date(first_value(row, *mapping.plan_year_begin))
    parsed.plan_year_end = parse_date(first_value(row, *mapping.plan_year_end))
    parsed.plan_effective_date = parse_date(first_value(row, *mapping.plan_effective_date))
    parsed.date_received = parse_date(first_value(row, *mapping.date_received))
    parsed.filing_status = _text(row, mapping.filing_status)

    parsed.is_initial = normalize_indicator(first_value(row, *mapping.initial_ind))
    parsed.is_amended = normalize_indicator(first_value(row, *mapping.amended_ind))
    parsed.is_final = normalize_indicator(first_value(row, *mapping.final_ind))
    parsed.is_short_year = normalize_indicator(first_value(row, *mapping.short_year_ind))

    parsed.plan_entity_code = _text(row, mapping.plan_entity_code)
    parsed.dfe_entity_code = _text(row, mapping.dfe_entity_code)

    parsed.pension_codes = split_codes(first_value(row, *mapping.pension_codes))
    parsed.welfare_codes = split_codes(first_value(row, *mapping.welfare_codes))

    parsed.total_participants = parse_int(first_value(row, *mapping.total_participants))
    parsed.active_participants = parse_int(first_value(row, *mapping.active_participants))
    parsed.participants_with_balances = parse_int(
        first_value(row, *mapping.participants_with_balances)
    )

    parsed.total_assets_boy = parse_money(first_value(row, *mapping.total_assets_boy))
    parsed.total_assets_eoy = parse_money(first_value(row, *mapping.total_assets_eoy))
    parsed.net_assets_eoy = parse_money(first_value(row, *mapping.net_assets_eoy))
    parsed.employer_contributions = parse_money(first_value(row, *mapping.employer_contributions))
    parsed.participant_contributions = parse_money(
        first_value(row, *mapping.participant_contributions)
    )

    parsed.admin_name = _text(row, mapping.admin_name)
    parsed.admin_ein = normalize_ein(first_value(row, *mapping.admin_ein))
    parsed.preparer_firm_name = _text(row, mapping.preparer_firm_name)
    parsed.trust_name = _text(row, mapping.trust_name)
    parsed.trustee_custodian_name = _text(row, mapping.trustee_custodian_name)
    parsed.accountant_firm_name = _text(row, mapping.accountant_firm_name)

    schedule_r_401k = normalize_indicator(first_value(row, "SF_401K_PLAN_IND"))

    parsed.plan_category, parsed.plan_features = classify_plan(
        pension_codes=parsed.pension_codes,
        welfare_codes=parsed.welfare_codes,
        plan_entity_code=parsed.plan_entity_code,
        dfe_entity_code=parsed.dfe_entity_code,
        form_type=parsed.form_type,
        schedule_r_401k=schedule_r_401k,
        plan_name=parsed.plan_name,
    )

    return parsed


def parse_ack_id(row: dict[str, Any]) -> str:
    """Return the ACK_ID that joins a schedule row to its filing."""

    return normalize_text(first_value(row, "ACK_ID"))


def parse_row_order(row: dict[str, Any]) -> int | None:
    """Return the ROW_ORDER of a repeating schedule row, if present."""

    return parse_int(first_value(row, "ROW_ORDER", "FORM_ID"))


_SCHEDULE_FILENAME = re.compile(
    r"^F_(?P<name>5500(?:_SF)?|SCH_[A-Z0-9]+(?:_PART\d+)?(?:_ITEM\d+)?)_(?P<year>\d{4})_",
    re.IGNORECASE,
)


def infer_dataset_from_filename(filename: str) -> tuple[str | None, int | None]:
    """Recover ``(dataset, form_year)`` from a DOL CSV filename."""

    match = _SCHEDULE_FILENAME.match(Path(filename).name)
    if not match:
        return None, None

    return f"F_{match.group('name').upper()}", int(match.group("year"))
