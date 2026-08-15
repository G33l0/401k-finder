from __future__ import annotations

import pytest

from app.core.constants import ProviderRole
from app.dol.provider_extractor import (
    EXTRACTION_RULES,
    clean_provider_name,
    extract_providers,
    is_placeholder_name,
    role_from_service_codes,
)
from app.providers.normalizer import normalize_provider


@pytest.mark.parametrize(
    "value",
    ["N/A", "n/a", "NONE", "None.", "SAME AS ABOVE", "-", "0", "000", "XXX", "  "],
)
def test_placeholder_names_are_rejected(value):
    """
    These appear tens of thousands of times across a form year. Storing them
    would create the largest "providers" in the database.
    """

    assert clean_provider_name(value) is None


@pytest.mark.parametrize(
    "value",
    ["Fidelity Investments", "MATRIX TRUST COMPANY", "J.P. Morgan", "ADP, LLC"],
)
def test_real_names_are_kept(value):
    assert clean_provider_name(value) is not None


def test_placeholder_detection_requires_letters():
    assert is_placeholder_name("12345")
    assert not is_placeholder_name("A1 Pension Services")


def test_schedule_c_service_codes_pick_the_role():
    """Service code 15 is recordkeeping; the row's role should follow it."""

    row = {
        "ACK_ID": "X1",
        "PROVIDER_OTHER_NAME": "BIG RECORDKEEPER LLC",
        "PROVIDER_OTHER_SRVC_CODES": "1564",
    }

    candidates = extract_providers(row, "F_SCH_C_PART1_ITEM2")

    assert len(candidates) == 1
    assert candidates[0].role == ProviderRole.RECORDKEEPER.value
    assert candidates[0].service_codes == ("15", "64")


def test_service_code_priority_prefers_recordkeeper_over_generic():
    role = role_from_service_codes(("49", "15"), ProviderRole.SERVICE_PROVIDER)
    assert role is ProviderRole.RECORDKEEPER


def test_compensation_only_codes_are_a_last_resort():
    """A provider reporting only how it was paid still gets a sensible role."""

    role = role_from_service_codes(("64",), ProviderRole.SERVICE_PROVIDER)
    assert role is ProviderRole.RECORDKEEPER


def test_service_codes_absent_falls_back_to_rule_role():
    row = {"ACK_ID": "X1", "PROVIDER_OTHER_NAME": "SOME FIRM LLC"}
    candidates = extract_providers(row, "F_SCH_C_PART1_ITEM2")
    assert candidates[0].role == ProviderRole.SERVICE_PROVIDER.value


def test_schedule_h_yields_trustee_trust_and_accountant():
    row = {
        "ACK_ID": "X1",
        "FDCRY_TRUSTEE_CUST_NAME": "MATRIX TRUST COMPANY",
        "FDCRY_TRUST_NAME": "ACME RETIREMENT TRUST",
        "FDCRY_TRUST_EIN": "12-3456789",
        "ACCOUNTANT_FIRM_NAME": "CLIFTONLARSONALLEN LLP",
    }

    roles = {candidate.role for candidate in extract_providers(row, "F_SCH_H")}

    assert roles == {
        ProviderRole.TRUSTEE.value,
        ProviderRole.TRUST.value,
        ProviderRole.ACCOUNTANT.value,
    }


def test_schedule_a_yields_the_insurance_carrier():
    row = {"ACK_ID": "X1", "INS_CARRIER_NAME": "JOHN HANCOCK LIFE INSURANCE CO"}
    candidates = extract_providers(row, "F_SCH_A")

    assert candidates[0].role == ProviderRole.INSURER.value
    assert candidates[0].confidence == "HIGH"


def test_schedule_d_yields_the_investment_vehicle():
    row = {
        "ACK_ID": "X1",
        "DFE_P1_ENTITY_NAME": "VANGUARD TARGET RETIREMENT TRUST",
        "DFE_P1_SPONS_NAME": "VANGUARD FIDUCIARY TRUST COMPANY",
    }

    roles = {candidate.role for candidate in extract_providers(row, "F_SCH_D_PART1")}
    assert ProviderRole.INVESTMENT_VEHICLE.value in roles


def test_preparer_is_low_confidence():
    """A form preparer is attached to the plan but does not hold its assets."""

    row = {"ACK_ID": "X1", "PREPARER_FIRM_NAME": "SMALL CPA FIRM PC"}
    candidates = extract_providers(row, "F_5500")

    assert candidates[0].role == ProviderRole.PREPARER.value
    assert candidates[0].confidence == "LOW"


def test_unknown_dataset_yields_nothing():
    assert extract_providers({"ACK_ID": "X"}, "F_SCH_SB") == []


def test_every_rule_names_a_field_the_layout_defines():
    """A rule pointing at a field that does not exist would silently never fire."""

    from app.dol.layouts import get_layout

    problems: list[str] = []

    for dataset, rules in EXTRACTION_RULES.items():
        layout = get_layout(2023, dataset)
        if layout is None:
            continue

        for rule in rules:
            for attribute in (
                "name_field",
                "ein_field",
                "city_field",
                "state_field",
                "relationship_field",
                "service_code_field",
                "direct_comp_field",
                "indirect_comp_field",
            ):
                field = getattr(rule, attribute)
                if field and not layout.has(field):
                    problems.append(f"{dataset}.{attribute}={field}")

    assert not problems, f"extraction rules reference unknown fields: {problems}"


# ----------------------------------------------------------------------
# Provider identity
# ----------------------------------------------------------------------


def test_known_brands_get_a_canonical_name():
    assert normalize_provider("FIDELITY INVESTMENTS INSTITUTIONAL OPERAT").canonical_name == (
        "Fidelity Investments"
    )
    assert normalize_provider("GREAT WEST TRUST COMPANY LLC").canonical_name == "Empower"


def test_unknown_provider_keeps_its_filed_name():
    identity = normalize_provider("SPRINGFIELD PENSION ADVISORS LLC")
    assert identity.canonical_name is None
    assert identity.display_name == "SPRINGFIELD PENSION ADVISORS LLC"


def test_name_variants_share_a_key():
    keys = {
        normalize_provider(name).name_key
        for name in (
            "MATRIX TRUST COMPANY",
            "Matrix Trust Company",
            "MATRIX TRUST CO.",
        )
    }
    assert len(keys) <= 2  # "CO" is a stripped suffix; "COMPANY" is too
