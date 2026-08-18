"""Extract service providers from DOL filing and schedule rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.codes import SERVICE_CODES
from app.core.constants import ConfidenceLevel, ProviderRole
from app.dol.normalizer import (
    normalize_ein,
    normalize_indicator,
    normalize_state,
    normalize_text,
    parse_money,
    split_numeric_codes,
)

_PLACEHOLDER_NAMES = frozenset(
    {
        "N/A",
        "NA",
        "NONE",
        "NO",
        "NOT APPLICABLE",
        "NOT APPLICABLE.",
        "NONE.",
        "N A",
        "N/A.",
        "SAME",
        "SAME AS ABOVE",
        "SAME AS SPONSOR",
        "SEE ATTACHED",
        "SEE ATTACHMENT",
        "VARIOUS",
        "UNKNOWN",
        "TBD",
        "X",
        "XX",
        "XXX",
        "XXXX",
        "-",
        "--",
        "0",
        "00",
        "000",
        "NOT APPLICABLE - N/A",
        "NO PROVIDER",
        "SELF",
        "SELF ADMINISTERED",
        "EMPLOYER",
        "PLAN SPONSOR",
    }
)


@dataclass(slots=True)
class ProviderCandidate:
    """One organisation found in one row, with the reason it was picked up."""

    name: str
    role: str
    source_field: str
    confidence: str
    reason: str

    ein: str | None = None
    city: str | None = None
    state: str | None = None
    relationship: str | None = None
    service_codes: tuple[str, ...] = ()
    direct_compensation: float | None = None
    indirect_compensation: float | None = None

    def dedupe_key(self) -> tuple[str, str]:
        return (self.name.upper(), self.role)


@dataclass(frozen=True, slots=True)
class ExtractionRule:
    """A single field-to-role mapping for one dataset."""

    name_field: str
    role: ProviderRole
    confidence: ConfidenceLevel
    reason: str

    ein_field: str | None = None
    city_field: str | None = None
    state_field: str | None = None
    relationship_field: str | None = None
    service_code_field: str | None = None
    direct_comp_field: str | None = None
    indirect_comp_field: str | None = None
    require_indicator: str | None = None
    require_absent: tuple[str, ...] = ()
    role_from_service_codes: bool = False


def _rules(*rules: ExtractionRule) -> tuple[ExtractionRule, ...]:
    return rules


EXTRACTION_RULES: dict[str, tuple[ExtractionRule, ...]] = {
    "F_5500": _rules(
        ExtractionRule(
            "ADMIN_NAME",
            ProviderRole.ADMINISTRATOR,
            ConfidenceLevel.MEDIUM,
            "Named as the plan administrator on Form 5500 line 3a.",
            ein_field="ADMIN_EIN",
            city_field="ADMIN_US_CITY",
            state_field="ADMIN_US_STATE",
        ),
        ExtractionRule(
            "SPONSOR_DFE_NAME",
            ProviderRole.ADMINISTRATOR,
            ConfidenceLevel.MEDIUM,
            "The filing reports the plan administrator as the same entity as "
            "the sponsor (ADMIN_NAME_SAME_SPON_IND), so the plan is "
            "administered by the employer rather than an outside firm.",
            ein_field="SPONS_DFE_EIN",
            city_field="SPONS_DFE_LOC_US_CITY",
            state_field="SPONS_DFE_LOC_US_STATE",
            require_indicator="ADMIN_NAME_SAME_SPON_IND",
            require_absent=("ADMIN_NAME",),
        ),
        ExtractionRule(
            "PREPARER_FIRM_NAME",
            ProviderRole.PREPARER,
            ConfidenceLevel.LOW,
            "Named as the preparer firm on Form 5500.",
            city_field="PREPARER_US_CITY",
            state_field="PREPARER_US_STATE",
        ),
    ),
    "F_5500_SF": _rules(
        ExtractionRule(
            "SF_FDCRY_TRUSTE_CUST_NAME",
            ProviderRole.TRUSTEE,
            ConfidenceLevel.HIGH,
            "Named as the trustee or custodian on Form 5500-SF.",
        ),
        ExtractionRule(
            "SF_FDCRY_TRUST_NAME",
            ProviderRole.TRUST,
            ConfidenceLevel.HIGH,
            "Named as the plan's fiduciary trust on Form 5500-SF.",
            ein_field="SF_FDCRY_TRUST_EIN",
        ),
        ExtractionRule(
            "SF_ADMIN_NAME",
            ProviderRole.ADMINISTRATOR,
            ConfidenceLevel.MEDIUM,
            "Named as the plan administrator on Form 5500-SF.",
            ein_field="SF_ADMIN_EIN",
            city_field="SF_ADMIN_US_CITY",
            state_field="SF_ADMIN_US_STATE",
        ),
        ExtractionRule(
            "SF_SPONSOR_NAME",
            ProviderRole.ADMINISTRATOR,
            ConfidenceLevel.MEDIUM,
            "The filing reports the plan administrator as the same entity as "
            "the sponsor (SF_ADMIN_NAME_SAME_SPON_IND), so the plan is "
            "administered by the employer rather than an outside firm.",
            ein_field="SF_SPONS_EIN",
            city_field="SF_SPONS_LOC_US_CITY",
            state_field="SF_SPONS_LOC_US_STATE",
            require_indicator="SF_ADMIN_NAME_SAME_SPON_IND",
            require_absent=("SF_ADMIN_NAME",),
        ),
        ExtractionRule(
            "SF_PREPARER_FIRM_NAME",
            ProviderRole.PREPARER,
            ConfidenceLevel.LOW,
            "Named as the preparer firm on Form 5500-SF.",
            city_field="SF_PREPARER_US_CITY",
            state_field="SF_PREPARER_US_STATE",
        ),
    ),
    "F_SCH_DCG": _rules(
        ExtractionRule(
            "DCG_ADMIN_NAME",
            ProviderRole.ADMINISTRATOR,
            ConfidenceLevel.MEDIUM,
            "Named as the plan administrator on Schedule DCG.",
            ein_field="DCG_ADMIN_EIN",
        ),
        ExtractionRule(
            "DCG_ACCOUNTANT_FIRM_NAME",
            ProviderRole.ACCOUNTANT,
            ConfidenceLevel.HIGH,
            "Named as the independent qualified public accountant on Schedule DCG.",
            ein_field="DCG_ACCOUNTANT_FIRM_EIN",
        ),
    ),
    "F_SCH_A": _rules(
        ExtractionRule(
            "INS_CARRIER_NAME",
            ProviderRole.INSURER,
            ConfidenceLevel.HIGH,
            "Named as the insurance carrier on Schedule A, which reports the "
            "insurance and annuity contracts holding plan assets.",
            ein_field="INS_CARRIER_EIN",
        ),
    ),
    "F_SCH_A_PART1": _rules(
        ExtractionRule(
            "INS_BROKER_NAME",
            ProviderRole.BROKER,
            ConfidenceLevel.HIGH,
            "Named as an insurance broker receiving commissions on Schedule A Part 1.",
            city_field="INS_BROKER_US_CITY",
            state_field="INS_BROKER_US_STATE",
            direct_comp_field="INS_BROKER_COMM_PD_AMT",
        ),
    ),
    "F_SCH_C_PART1_ITEM1": _rules(
        ExtractionRule(
            "PROVIDER_ELIGIBLE_NAME",
            ProviderRole.SERVICE_PROVIDER,
            ConfidenceLevel.MEDIUM,
            "Reported on Schedule C Part 1 Item 1 as receiving only eligible "
            "indirect compensation.",
            ein_field="PROVIDER_ELIGIBLE_EIN",
            city_field="PROVIDER_ELIGIBLE_US_CITY",
            state_field="PROVIDER_ELIGIBLE_US_STATE",
        ),
    ),
    "F_SCH_C_PART1_ITEM2": _rules(
        ExtractionRule(
            "PROVIDER_OTHER_NAME",
            ProviderRole.SERVICE_PROVIDER,
            ConfidenceLevel.HIGH,
            "Reported on Schedule C Part 1 Item 2 as a service provider paid by the plan.",
            ein_field="PROVIDER_OTHER_EIN",
            city_field="PROVIDER_OTHER_US_CITY",
            state_field="PROVIDER_OTHER_US_STATE",
            relationship_field="PROVIDER_OTHER_RELATION",
            service_code_field="PROVIDER_OTHER_SRVC_CODES",
            direct_comp_field="PROVIDER_OTHER_DIRECT_COMP_AMT",
            indirect_comp_field="PROV_OTHER_TOT_IND_COMP_AMT",
            role_from_service_codes=True,
        ),
    ),
    "F_SCH_C_PART1_ITEM3": _rules(
        ExtractionRule(
            "PROVIDER_INDIRECT_NAME",
            ProviderRole.SERVICE_PROVIDER,
            ConfidenceLevel.MEDIUM,
            "Reported on Schedule C Part 1 Item 3 as receiving indirect compensation.",
            service_code_field="PROVIDER_INDIRECT_SRVC_CODES",
            indirect_comp_field="PROVIDER_INDIRECT_COMP_AMT",
            role_from_service_codes=True,
        ),
        ExtractionRule(
            "PROVIDER_PAYOR_NAME",
            ProviderRole.PAYOR,
            ConfidenceLevel.LOW,
            "Named on Schedule C Part 1 Item 3 as the source of a provider's "
            "indirect compensation.",
            ein_field="PROVIDER_PAYOR_EIN",
            city_field="PROVIDER_PAYOR_US_CITY",
            state_field="PROVIDER_PAYOR_US_STATE",
        ),
    ),
    "F_SCH_C_PART2": _rules(
        ExtractionRule(
            "PROVIDER_FAIL_NAME",
            ProviderRole.SERVICE_PROVIDER,
            ConfidenceLevel.MEDIUM,
            "Reported on Schedule C Part 2 as a provider that failed to supply "
            "required compensation information.",
            ein_field="PROVIDER_FAIL_EIN",
            city_field="PROVIDER_FAIL_US_CITY",
            state_field="PROVIDER_FAIL_US_STATE",
            service_code_field="PROVIDER_FAIL_SRVC_CODE",
            role_from_service_codes=True,
        ),
    ),
    "F_SCH_C_PART3": _rules(
        ExtractionRule(
            "PROVIDER_TERM_NAME",
            ProviderRole.TERMINATED_ACCOUNTANT,
            ConfidenceLevel.HIGH,
            "Reported on Schedule C Part 3 as a terminated accountant or actuary.",
            ein_field="PROVIDER_TERM_EIN",
            city_field="PROVIDER_TERM_US_CITY",
            state_field="PROVIDER_TERM_US_STATE",
            relationship_field="PROVIDER_TERM_POSITION",
        ),
    ),
    "F_SCH_D_PART1": _rules(
        ExtractionRule(
            "DFE_P1_ENTITY_NAME",
            ProviderRole.INVESTMENT_VEHICLE,
            ConfidenceLevel.HIGH,
            "Named on Schedule D Part 1 as a master trust, collective trust, "
            "pooled separate account or 103-12 IE holding plan assets.",
            ein_field="DFE_P1_PLAN_EIN",
        ),
        ExtractionRule(
            "DFE_P1_SPONS_NAME",
            ProviderRole.INVESTMENT_MANAGER,
            ConfidenceLevel.MEDIUM,
            "Named on Schedule D Part 1 as the sponsor of an investment entity "
            "the plan holds an interest in.",
        ),
    ),
    "F_SCH_H": _rules(
        ExtractionRule(
            "FDCRY_TRUSTEE_CUST_NAME",
            ProviderRole.TRUSTEE,
            ConfidenceLevel.HIGH,
            "Named as the trustee or custodian on Schedule H.",
        ),
        ExtractionRule(
            "FDCRY_TRUST_NAME",
            ProviderRole.TRUST,
            ConfidenceLevel.HIGH,
            "Named as the plan's fiduciary trust on Schedule H.",
            ein_field="FDCRY_TRUST_EIN",
        ),
        ExtractionRule(
            "ACCOUNTANT_FIRM_NAME",
            ProviderRole.ACCOUNTANT,
            ConfidenceLevel.HIGH,
            "Named as the independent qualified public accountant on Schedule H.",
            ein_field="ACCOUNTANT_FIRM_EIN",
        ),
    ),
    "F_SCH_I": _rules(
        ExtractionRule(
            "FDCRY_TRUSTEE_CUST_NAME",
            ProviderRole.TRUSTEE,
            ConfidenceLevel.HIGH,
            "Named as the trustee or custodian on Schedule I.",
        ),
        ExtractionRule(
            "FDCRY_TRUST_NAME",
            ProviderRole.TRUST,
            ConfidenceLevel.HIGH,
            "Named as the plan's fiduciary trust on Schedule I.",
            ein_field="FDCRY_TRUST_EIN",
        ),
    ),
}


def is_placeholder_name(text: str) -> bool:
    """Return whether a name field holds filler rather than an organisation."""

    stripped = text.strip().upper().rstrip(".")
    if stripped in _PLACEHOLDER_NAMES or f"{stripped}." in _PLACEHOLDER_NAMES:
        return True
    return not any(character.isalpha() for character in stripped)


def clean_provider_name(value: Any) -> str | None:
    """Normalize a filed organisation name, rejecting filler values."""

    text = normalize_text(value)
    if len(text) < 3:
        return None
    if is_placeholder_name(text):
        return None

    return text.strip(" .,;:-")or None


def role_from_service_codes(codes: tuple[str, ...], fallback: ProviderRole) -> ProviderRole:
    """Pick the role a Schedule C provider plays from its service codes."""

    if not codes:
        return fallback

    priority = (
        ProviderRole.RECORDKEEPER,
        ProviderRole.TRUSTEE,
        ProviderRole.CUSTODIAN,
        ProviderRole.INSURER,
        ProviderRole.INVESTMENT_MANAGER,
        ProviderRole.INVESTMENT_ADVISOR,
        ProviderRole.THIRD_PARTY_ADMIN,
        ProviderRole.ADMINISTRATOR,
        ProviderRole.ACTUARY,
        ProviderRole.ACCOUNTANT,
        ProviderRole.BROKER,
        ProviderRole.CONSULTANT,
        ProviderRole.ATTORNEY,
        ProviderRole.SERVICE_PROVIDER,
    )

    service_roles: set[ProviderRole] = set()
    compensation_roles: set[ProviderRole] = set()

    for code in codes:
        entry = SERVICE_CODES.get(code.zfill(2))
        if entry is None or entry.role is None:
            continue
        if entry.is_compensation_code:
            compensation_roles.add(entry.role)
        else:
            service_roles.add(entry.role)

    chosen = service_roles or compensation_roles
    if not chosen:
        return fallback

    for role in priority:
        if role in chosen:
            return role

    return fallback


def _apply_rule(
    row: dict[str, Any],
    rule: ExtractionRule,
) -> ProviderCandidate | None:
    if rule.require_indicator and not normalize_indicator(row.get(rule.require_indicator)):
        return None

    if any(normalize_text(row.get(field)) for field in rule.require_absent):
        return None

    name = clean_provider_name(row.get(rule.name_field))
    if name is None:
        return None

    codes: tuple[str, ...] = ()
    if rule.service_code_field:
        codes = split_numeric_codes(row.get(rule.service_code_field))

    role = rule.role
    reason = rule.reason

    if rule.role_from_service_codes and codes:
        role = role_from_service_codes(codes, rule.role)
        described = ", ".join(
            SERVICE_CODES[code.zfill(2)].description
            for code in codes
            if code.zfill(2) in SERVICE_CODES
        )
        if described:
            reason = f"{rule.reason} Service codes reported: {described}."

    return ProviderCandidate(
        name=name,
        role=role.value,
        source_field=rule.name_field,
        confidence=rule.confidence.value,
        reason=reason,
        ein=normalize_ein(row.get(rule.ein_field)) if rule.ein_field else None,
        city=normalize_text(row.get(rule.city_field)) or None if rule.city_field else None,
        state=normalize_state(row.get(rule.state_field)) if rule.state_field else None,
        relationship=(
            normalize_text(row.get(rule.relationship_field)) or None
            if rule.relationship_field
            else None
        ),
        service_codes=codes,
        direct_compensation=(
            parse_money(row.get(rule.direct_comp_field)) if rule.direct_comp_field else None
        ),
        indirect_compensation=(
            parse_money(row.get(rule.indirect_comp_field)) if rule.indirect_comp_field else None
        ),
    )


def extract_providers(row: dict[str, Any], dataset: str) -> list[ProviderCandidate]:
    """Return every provider named in one row of one dataset."""

    rules = EXTRACTION_RULES.get(dataset.upper())
    if not rules:
        return []

    candidates: list[ProviderCandidate] = []
    seen: set[tuple[str, str]] = set()

    for rule in rules:
        candidate = _apply_rule(row, rule)
        if candidate is None:
            continue

        key = candidate.dedupe_key()
        if key in seen:
            continue

        seen.add(key)
        candidates.append(candidate)

    return candidates


def datasets_with_providers() -> tuple[str, ...]:
    """Return the datasets that can yield providers."""

    return tuple(sorted(EXTRACTION_RULES))


@dataclass(slots=True)
class ExtractionStats:
    """Counts collected while extracting providers, for import reporting."""

    rows: int = 0
    candidates: int = 0
    by_role: dict[str, int] = field(default_factory=dict)

    def record(self, candidates: list[ProviderCandidate]) -> None:
        self.rows += 1
        self.candidates += len(candidates)
        for candidate in candidates:
            self.by_role[candidate.role] = self.by_role.get(candidate.role, 0) + 1
