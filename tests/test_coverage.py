"""
Knowing what has been imported, and how completely.

The point of this is a single distinction: a search that finds nothing because
the year was never fetched, versus one that finds nothing because there is
nothing to find. Confusing the two sends somebody away believing there is no
account when nobody has looked yet.
"""

from __future__ import annotations

import pytest

from app.database.models import ImportedDataset
from app.dol.catalog import CORE_DATASET_NAMES, INDEX_DATASET_NAMES, plan_sync
from app.services.coverage import (
    Depth,
    YearCoverage,
    coverage,
    provider_schedules,
    summarise,
    years_without_providers,
)

# ----------------------------------------------------------------------
# The index set
# ----------------------------------------------------------------------


def test_the_index_is_only_the_filing_forms():
    """Anything more and it stops being small enough to run for every year."""

    assert set(INDEX_DATASET_NAMES) == {"F_5500", "F_5500_SF"}


def test_the_index_is_a_subset_of_core():
    assert set(INDEX_DATASET_NAMES) <= set(CORE_DATASET_NAMES)


def test_index_only_planning_selects_just_those():
    selected = [item.name for item in plan_sync(2023, index_only=True)]

    assert sorted(selected) == sorted(INDEX_DATASET_NAMES)


def test_index_only_is_far_smaller_than_core():
    """The whole argument for this feature is the size difference."""

    assert len(plan_sync(2023, index_only=True)) < len(plan_sync(2023, core_only=True))


def test_explicit_datasets_still_win_over_index_only():
    selected = [item.name for item in plan_sync(2023, datasets=("F_SCH_H",), index_only=True)]

    assert selected == ["F_SCH_H"]


def test_provider_schedules_excludes_the_filing_forms():
    """
    Otherwise every index-only year would count as having provider detail,
    which is the exact thing this is meant to distinguish.
    """

    schedules = provider_schedules()

    assert schedules
    assert not schedules & set(INDEX_DATASET_NAMES)
    assert "F_SCH_C_PART1_ITEM2" in schedules


# ----------------------------------------------------------------------
# Depth
# ----------------------------------------------------------------------


def _record(session, form_year: int, dataset: str, status: str = "COMPLETED") -> None:
    session.add(
        ImportedDataset(
            form_year=form_year, dataset=dataset, release="Latest", status=status
        )
    )
    session.commit()


def test_a_year_with_only_filing_forms_is_index_depth(session):
    for dataset in INDEX_DATASET_NAMES:
        _record(session, 2015, dataset)

    entry = coverage(session)[0]

    assert entry.form_year == 2015
    assert entry.depth is Depth.INDEX
    assert not entry.has_providers


def test_a_year_with_a_provider_schedule_has_provider_detail(session):
    _record(session, 2016, "F_5500")
    _record(session, 2016, "F_SCH_C_PART1_ITEM2")

    entry = next(item for item in coverage(session) if item.form_year == 2016)

    assert entry.depth is Depth.CORE
    assert entry.has_providers


def test_a_year_is_not_downgraded_for_a_dataset_dol_never_published(session):
    """
    DCG and MEP only exist for recent years. Requiring the whole core set would
    report a complete 2011 as thin, and send somebody re-downloading it.
    """

    _record(session, 2011, "F_5500")
    _record(session, 2011, "F_SCH_H")
    _record(session, 2011, "F_SCH_C_PART1_ITEM2")

    entry = next(item for item in coverage(session) if item.form_year == 2011)

    assert entry.has_providers


def test_schedules_without_a_filing_dataset_are_not_coverage(session):
    """Those rows have no filing to attach to, so nothing is searchable."""

    _record(session, 2014, "F_SCH_H")

    assert not [item for item in coverage(session) if item.form_year == 2014]


def test_a_failed_import_is_not_counted(session):
    _record(session, 2013, "F_5500", status="FAILED")

    assert not [item for item in coverage(session) if item.form_year == 2013]


def test_coverage_is_ordered_oldest_first(session):
    for year in (2020, 2012, 2018):
        _record(session, year, "F_5500")

    assert [item.form_year for item in coverage(session)] == [2012, 2018, 2020]


def test_a_local_import_is_recorded(session, imported):
    """
    Importing files from disk used to leave no trace, so everything asking
    "what do we hold" saw an empty database.
    """

    entries = coverage(session)

    assert entries
    assert any(entry.has_providers for entry in entries)


# ----------------------------------------------------------------------
# What it says
# ----------------------------------------------------------------------


def test_an_empty_database_says_so():
    assert summarise([]) == "no form years imported"


def test_a_thin_run_is_described_honestly():
    entries = [YearCoverage(year, Depth.INDEX, 2) for year in (2009, 2010, 2011)]

    text = summarise(entries)

    assert "3 year(s) searchable" in text
    assert "2009–2011" in text
    assert "none with the schedules that name providers" in text


def test_a_mixed_run_names_both_numbers():
    entries = [
        YearCoverage(2009, Depth.INDEX, 2),
        YearCoverage(2010, Depth.INDEX, 2),
        YearCoverage(2023, Depth.CORE, 11),
    ]

    text = summarise(entries)

    assert "provider detail for 1 of them" in text
    assert years_without_providers(entries) == [2009, 2010]


def test_a_complete_run_says_so():
    entries = [YearCoverage(year, Depth.FULL, 20) for year in (2022, 2023)]

    assert "all with provider detail" in summarise(entries)


@pytest.mark.parametrize("depth", list(Depth))
def test_every_depth_has_a_label(depth):
    assert depth.label


# ----------------------------------------------------------------------
# The trace leans on this
# ----------------------------------------------------------------------


def test_the_trace_report_warns_about_index_only_years(session, imported):
    from app.trace import AccountTracer, WorkHistory
    from app.trace.packet import render_report

    # An older year held at index depth only, alongside the fully imported one.
    for dataset in INDEX_DATASET_NAMES:
        _record(session, 2011, dataset)

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC")

    report = AccountTracer(session).trace(history)

    assert 2011 in report.index_only_years

    flowed = " ".join(render_report(report).split())
    assert "employer and plan records only" in flowed
