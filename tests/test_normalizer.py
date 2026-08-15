from __future__ import annotations

import pytest

from app.dol.normalizer import (
    normalize_column_name,
    normalize_ein,
    normalize_indicator,
    normalize_name_key,
    normalize_plan_number,
    normalize_state,
    normalize_zip,
    parse_date,
    parse_int,
    parse_money,
    split_codes,
    split_numeric_codes,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("12-3456789", "123456789"),
        ("123456789", "123456789"),
        (" 12 3456789 ", "123456789"),
        ("1234567", "001234567"),
        ("", None),
        (None, None),
        ("000000000", None),
        ("00-0000000", None),
        ("1234567890", None),
        ("not an ein", None),
    ],
)
def test_normalize_ein(raw, expected):
    assert normalize_ein(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", "001"), ("01", "001"), ("001", "001"), ("333", "333"), ("0", None), ("", None), ("9999", None)],
)
def test_normalize_plan_number(raw, expected):
    assert normalize_plan_number(raw) == expected


def test_plan_number_variants_collapse():
    """1, 01 and 001 must resolve to one plan, or a plan splits across years."""

    assert normalize_plan_number("1") == normalize_plan_number("01") == normalize_plan_number("001")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FIDELITY INVESTMENTS INSTITUTIONAL, INC.", "FIDELITY INVESTMENTS INSTITUTIONAL"),
        ("Fidelity Investments Institutional Inc", "FIDELITY INVESTMENTS INSTITUTIONAL"),
        ("Vanguard Group, LLC", "VANGUARD GROUP"),
        ("The Northern Trust Company", "NORTHERN TRUST"),
        ("", ""),
    ],
)
def test_normalize_name_key(raw, expected):
    assert normalize_name_key(raw) == expected


def test_name_key_groups_punctuation_variants():
    variants = [
        "PRINCIPAL LIFE INSURANCE CO.",
        "Principal Life Insurance Co",
        "PRINCIPAL LIFE INSURANCE COMPANY",
    ]
    assert len({normalize_name_key(name) for name in variants}) == 1


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1", True), ("Y", True), ("yes", True), ("0", False), ("N", False), ("", None), (None, None)],
)
def test_normalize_indicator(raw, expected):
    assert normalize_indicator(raw) is expected


def test_indicator_distinguishes_blank_from_no():
    """A blank box and a box filed 'no' are different facts."""

    assert normalize_indicator("") is None
    assert normalize_indicator("0") is False


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2E2G2J", ("2E", "2G", "2J")),
        ("2E 2G 2J", ("2E", "2G", "2J")),
        ("2E,2G,2J", ("2E", "2G", "2J")),
        ("2J", ("2J",)),
        ("2J2J", ("2J",)),
        ("", ()),
    ],
)
def test_split_codes(raw, expected):
    assert split_codes(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1521", ("15", "21")),
        ("1537645038", ("15", "37", "64", "50", "38")),
        ("15 21", ("15", "21")),
        ("15,21", ("15", "21")),
        ("", ()),
    ],
)
def test_split_numeric_codes(raw, expected):
    assert split_numeric_codes(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2023-12-31", (2023, 12, 31)),
        ("12/31/2023", (2023, 12, 31)),
        ("20231231", (2023, 12, 31)),
        ("", None),
        ("0000-00-00", None),
        ("garbage", None),
    ],
)
def test_parse_date(raw, expected):
    result = parse_date(raw)
    if expected is None:
        assert result is None
    else:
        assert (result.year, result.month, result.day) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1,234.56", 1234.56), ("$1,234", 1234.0), ("(500)", -500.0), ("", None), ("-", None)],
)
def test_parse_money(raw, expected):
    assert parse_money(raw) == expected


def test_parse_int_handles_thousands_separators():
    assert parse_int("1,234") == 1234
    assert parse_int("") is None


def test_normalize_state_rejects_non_states():
    assert normalize_state("tx") == "TX"
    assert normalize_state("TEX") is None
    assert normalize_state("") is None


def test_normalize_zip_forms():
    assert normalize_zip("62701") == "62701"
    assert normalize_zip("627010000") == "62701-0000"
    assert normalize_zip("") is None


def test_normalize_column_name():
    assert normalize_column_name(" ack id ") == "ACK_ID"
    assert normalize_column_name("SPONS_DFE_EIN") == "SPONS_DFE_EIN"
