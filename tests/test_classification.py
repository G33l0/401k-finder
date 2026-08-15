"""
Plan classification from the filed characteristics codes.

The code meanings are taken from the official Form 5500 instructions and have
been stable across the 2009-2025 datasets, except that 2U-2X were introduced
for 2022. These tests pin the mappings that matter most, because getting 2L/2M
wrong would silently mislabel every 403(b) plan in the database.
"""

from __future__ import annotations

import pytest

from app.core.codes import PLAN_CHARACTERISTICS, SERVICE_CODES, role_for_service_code
from app.core.constants import PlanCategory, PlanFeature, ProviderRole
from app.dol.filing_parser import classify_plan


def classify(codes: str, **kwargs):
    from app.dol.normalizer import split_codes

    return classify_plan(split_codes(codes), (), **kwargs)


@pytest.mark.parametrize(
    ("codes", "expected_feature"),
    [
        ("2J", PlanFeature.K401),
        ("2L", PlanFeature.B403),
        ("2M", PlanFeature.B403),
        ("2N", PlanFeature.SEP_SIMPLE_408),
        ("2E", PlanFeature.PROFIT_SHARING),
        ("2C", PlanFeature.MONEY_PURCHASE),
        ("2B", PlanFeature.TARGET_BENEFIT),
        ("2I", PlanFeature.STOCK_BONUS),
        ("2O", PlanFeature.ESOP),
        ("2P", PlanFeature.ESOP),
        ("2Q", PlanFeature.ESOP),
        ("1C", PlanFeature.CASH_BALANCE),
        ("1A", PlanFeature.PENSION_DB),
        ("2G", PlanFeature.PARTICIPANT_DIRECTED),
        ("2W", PlanFeature.POOLED_EMPLOYER),
    ],
)
def test_code_maps_to_feature(codes, expected_feature):
    _, features = classify(codes)
    assert expected_feature.value in features


def test_403b_codes_are_not_401k():
    """2L and 2M are 403(b) arrangements, not 401(k) — an easy mapping to get wrong."""

    _, features = classify("2L2M")
    assert PlanFeature.B403.value in features
    assert PlanFeature.K401.value not in features


def test_401m_is_not_403b():
    """2K is a 401(m) arrangement, not 403(b)(1)."""

    _, features = classify("2K")
    assert PlanFeature.B403.value not in features


@pytest.mark.parametrize(
    ("codes", "expected"),
    [
        ("2E2G2J", PlanCategory.DEFINED_CONTRIBUTION),
        ("1A1I", PlanCategory.DEFINED_BENEFIT),
        ("1A2E", PlanCategory.BOTH),
        ("", PlanCategory.UNKNOWN),
    ],
)
def test_category(codes, expected):
    category, _ = classify(codes)
    assert category == expected.value


def test_welfare_only_plan_is_welfare():
    category, _ = classify_plan((), ("4A", "4D"))
    assert category == PlanCategory.WELFARE.value


def test_dfe_filing_is_categorised_as_dfe():
    category, _ = classify_plan(("2E",), (), dfe_entity_code="M")
    assert category == PlanCategory.DFE.value


def test_schedule_r_indicator_rescues_uncoded_401k():
    """
    Some filings leave the characteristics codes blank but tick the Schedule R
    401(k) box. Those plans are still 401(k) plans.
    """

    category, features = classify_plan((), (), schedule_r_401k=True)
    assert PlanFeature.K401.value in features
    assert category == PlanCategory.DEFINED_CONTRIBUTION.value


def test_457_plans_are_detected_by_name():
    """457(b) plans have no characteristics code of their own."""

    _, features = classify_plan(
        (), (), plan_name="CITY OF SPRINGFIELD 457(B) DEFERRED COMPENSATION PLAN"
    )
    assert PlanFeature.B457.value in features


def test_457_detection_does_not_fire_on_unrelated_numbers():
    _, features = classify_plan((), (), plan_name="ACME 4570 EMPLOYEES PLAN")
    assert PlanFeature.B457.value not in features


def test_plan_entity_code_sets_employer_structure():
    """
    TYPE_PLAN_ENTITY_CD is 1 = multiemployer, 2 = single-employer,
    3 = multiple-employer, 4 = DFE — the reverse of the checkbox order on the
    form. Reading 1 and 2 the other way round labels almost every plan in the
    country as multiemployer, which is how this was originally caught.
    """

    _, multiemployer = classify_plan(("2E",), (), plan_entity_code="1")
    assert PlanFeature.MULTIEMPLOYER.value in multiemployer

    _, single = classify_plan(("2E",), (), plan_entity_code="2")
    assert PlanFeature.MULTIEMPLOYER.value not in single
    assert PlanFeature.MULTIPLE_EMPLOYER.value not in single

    _, multiple = classify_plan(("2E",), (), plan_entity_code="3")
    assert PlanFeature.MULTIPLE_EMPLOYER.value in multiple


def test_plan_entity_code_table_matches_dol_documentation():
    from app.core.codes import PLAN_ENTITY_CODES

    assert PLAN_ENTITY_CODES["1"] == "Multiemployer plan"
    assert PLAN_ENTITY_CODES["2"] == "Single-employer plan"
    assert PLAN_ENTITY_CODES["3"] == "Multiple-employer plan"


def test_unknown_codes_are_ignored_not_fatal():
    category, features = classify("9Z")
    assert category == PlanCategory.UNKNOWN.value
    assert features == ()


# ----------------------------------------------------------------------
# Schedule C service codes
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_role"),
    [
        ("15", ProviderRole.RECORDKEEPER),
        ("21", ProviderRole.TRUSTEE),
        ("19", ProviderRole.CUSTODIAN),
        ("28", ProviderRole.INVESTMENT_MANAGER),
        ("10", ProviderRole.ACCOUNTANT),
        ("11", ProviderRole.ACTUARY),
        ("29", ProviderRole.ATTORNEY),
        ("23", ProviderRole.INSURER),
        ("33", ProviderRole.BROKER),
    ],
)
def test_service_code_role(code, expected_role):
    assert role_for_service_code(code) is expected_role


def test_service_codes_cover_the_published_range():
    for code in ("10", "15", "21", "28", "49", "50", "64", "99"):
        assert code in SERVICE_CODES


def test_compensation_codes_are_flagged():
    """Codes 50-99 describe payment, not the service performed."""

    assert SERVICE_CODES["64"].is_compensation_code
    assert not SERVICE_CODES["15"].is_compensation_code


def test_characteristics_table_has_no_duplicate_codes():
    codes = [entry.code for entry in PLAN_CHARACTERISTICS.values()]
    assert len(codes) == len(set(codes))


def test_codes_added_in_2022_are_marked():
    for code in ("2U", "2V", "2W", "2X"):
        assert PLAN_CHARACTERISTICS[code].since == 2022
