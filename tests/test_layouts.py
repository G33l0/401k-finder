"""
The vendored layouts are the application's source of truth, so they are checked
for structural integrity rather than assumed correct.
"""

from __future__ import annotations

import pytest

from app.dol.catalog import DATASETS, dataset_names_for_year, plan_sync, resolve
from app.dol.layouts import available_years, get_layout, iter_layouts, load_year


def test_expected_years_are_vendored():
    years = available_years()
    assert years, "no layouts were vendored"
    assert min(years) <= 2009
    assert max(years) >= 2023
    assert list(years) == list(range(min(years), max(years) + 1))


def test_every_layout_has_ack_id():
    """ACK_ID joins schedules to filings; a layout without it cannot be linked."""

    missing = [
        f"{layout.dataset} {layout.form_year}"
        for layout in iter_layouts()
        if not layout.has("ACK_ID")
    ]
    assert not missing, f"layouts without ACK_ID: {missing}"


def test_field_positions_are_contiguous():
    for layout in iter_layouts():
        positions = [field.position for field in layout.fields]
        assert positions == list(range(1, len(positions) + 1)), (
            f"{layout.dataset} {layout.form_year} has non-contiguous positions"
        )


def test_field_names_are_unique_within_a_layout():
    for layout in iter_layouts():
        names = [field.name for field in layout.fields]
        assert len(names) == len(set(names)), (
            f"{layout.dataset} {layout.form_year} has duplicate field names"
        )


def test_field_types_are_known():
    for layout in iter_layouts():
        for field in layout.fields:
            assert field.field_type in {"TEXT", "NUMERIC"}, (
                f"{layout.dataset} {layout.form_year}.{field.name}: {field.field_type}"
            )


@pytest.mark.parametrize("year", [2009, 2015, 2020, 2023, 2025])
def test_core_datasets_present_for_year(year):
    datasets = set(dataset_names_for_year(year))
    assert "F_5500" in datasets or "F_5500_SF" in datasets
    assert "F_SCH_A" in datasets


def test_form_5500_identity_fields_stable_across_years():
    """The fields the parser depends on must exist in every year it claims."""

    required = ("ACK_ID", "PLAN_NAME", "SPONS_DFE_PN", "SPONS_DFE_EIN", "SPONSOR_DFE_NAME")

    for year in available_years():
        layout = get_layout(year, "F_5500")
        if layout is None:
            continue
        for name in required:
            assert layout.has(name), f"F_5500 {year} is missing {name}"


def test_form_5500_sf_identity_fields_stable_across_years():
    required = ("ACK_ID", "SF_PLAN_NAME", "SF_PLAN_NUM", "SF_SPONS_EIN", "SF_SPONSOR_NAME")

    for year in available_years():
        layout = get_layout(year, "F_5500_SF")
        if layout is None:
            continue
        for name in required:
            assert layout.has(name), f"F_5500_SF {year} is missing {name}"


def test_schedule_c_provider_fields_present():
    """Schedule C Part 1 Item 2 is the main provider source; its fields must exist."""

    for year in available_years():
        layout = get_layout(year, "F_SCH_C_PART1_ITEM2")
        if layout is None:
            continue
        assert layout.has("PROVIDER_OTHER_NAME")
        assert layout.has("PROVIDER_OTHER_SRVC_CODES")


def test_dcg_and_mep_only_from_2023():
    """Schedule DCG and MEP were introduced for the 2023 form year."""

    for year in available_years():
        datasets = set(dataset_names_for_year(year))
        if year < 2023:
            assert "F_SCH_DCG" not in datasets
            assert "F_SCH_MEP" not in datasets


def test_catalog_urls_match_dol_naming():
    item = resolve(2023, "F_SCH_C_PART1_ITEM2")
    assert item.archive_url == (
        "https://askebsa.dol.gov/FOIA%20Files/2023/Latest/"
        "F_SCH_C_PART1_ITEM2_2023_Latest.zip"
    )
    assert item.layout_url.endswith("_layout.txt")


def test_sync_plan_orders_filings_first():
    """
    Schedules attach to filings by ACK_ID, so the filing datasets have to be
    imported first or every schedule row is orphaned.
    """

    order = [item.name for item in plan_sync(2023, core_only=True)]
    filing_positions = [order.index(name) for name in ("F_5500", "F_5500_SF") if name in order]
    schedule_positions = [
        order.index(name) for name in order if name.startswith("F_SCH_") and name != "F_SCH_DCG"
    ]

    assert max(filing_positions) < min(schedule_positions)


def test_every_catalog_dataset_has_a_layout_somewhere():
    known = {layout.dataset for layout in iter_layouts()}
    missing = [spec.name for spec in DATASETS if spec.name not in known]
    assert not missing, f"catalog lists datasets with no vendored layout: {missing}"


def test_load_year_is_cached():
    assert load_year(2023) is load_year(2023)
