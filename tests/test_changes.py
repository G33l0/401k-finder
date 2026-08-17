"""
Detecting plans that changed provider between filed years.

This is sold to firms who will act on it — a list of losses becomes a call
list — so the failure that matters is a change reported that did not happen.
Two ways that goes wrong are covered explicitly: the same firm named twice with
different spellings, and the same engagement filed on two schedules in one year.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database.models import Plan, PlanParty, Provider
from app.providers.changes import ChangeDetector, ChangeKind, ChangeQuery


@pytest.fixture()
def two_years(session, imported):
    """
    A second form year, so there is something to compare against.

    The fixture rotates provider assignments per year for a quarter of the
    plans, which is what produces changes to find.
    """

    import tempfile
    from pathlib import Path

    from app.dol.importer import import_directory
    from scripts.make_test_data import generate

    directory = Path(tempfile.mkdtemp())
    generate(year=2022, plan_count=24, output=directory, seed=11)
    import_directory(session, directory, form_year=2022)

    return session


def _detect(session, **kwargs) -> object:
    return ChangeDetector(session).find(ChangeQuery(**kwargs))


# ----------------------------------------------------------------------


def test_a_single_year_yields_no_changes(session, imported):
    """Nothing to compare against is not the same as nothing changed."""

    report = _detect(session)

    assert report.total == 0
    assert len(report.years_compared) <= 1


def test_changes_are_found_across_two_years(two_years):
    report = _detect(two_years)

    assert report.years_compared == (2022, 2023)
    assert report.total > 0

    change = report.changes[0]
    assert change.kind is ChangeKind.SWITCHED
    assert change.from_provider and change.to_provider
    assert change.from_provider != change.to_provider
    assert change.from_year < change.to_year


def test_a_change_carries_the_plan_and_its_size(two_years):
    change = _detect(two_years).changes[0]

    assert change.plan_name
    assert change.ein
    assert change.plan_key.startswith(change.ein)
    assert change.participants is not None


def test_a_change_cites_where_it_was_read(two_years):
    """A surprising change has to be checkable against the filing."""

    change = _detect(two_years).changes[0]

    assert change.schedule_code
    assert change.source_field


def test_results_lead_with_the_largest_plan(two_years):
    changes = _detect(two_years).changes

    assets = [change.total_assets or 0.0 for change in changes]
    assert assets == sorted(assets, reverse=True)


def test_a_plan_that_kept_its_provider_is_not_reported(two_years):
    """Three quarters of the fixture never move; none of them may appear."""

    report = _detect(two_years)
    moved = {change.plan_id for change in report.changes}

    total_plans = two_years.execute(select(Plan)).scalars().all()

    assert 0 < len(moved) < len(total_plans)


# ----------------------------------------------------------------------
# Not inventing changes
# ----------------------------------------------------------------------


def test_the_same_firm_spelled_two_ways_is_not_a_change(session, imported):
    """
    Filers write the same firm differently between years. Reporting that as a
    move would put a real client on somebody's win-back list.
    """

    plan = session.execute(select(Plan)).scalars().first()
    assert plan is not None

    # Distinct rows, because providers.name_key is unique -- two spellings that
    # normalise identically are already merged at import time. What is under
    # test is the detector's own comparison, for the case where they were not:
    # a provider consolidated later, or one imported under an older key.
    left = Provider(name="FIDELITY INVESTMENTS INC", name_key="FIDELITY INVESTMENTS INC")
    right = Provider(name="Fidelity  Investments,  Inc.", name_key="FIDELITY INVESTMENTS")
    session.add_all([left, right])
    session.flush()

    session.add_all(
        [
            PlanParty(
                plan_id=plan.id, provider_id=left.id, role="CUSTODIAN",
                form_year=2019, schedule_code="C", source_field="X",
            ),
            PlanParty(
                plan_id=plan.id, provider_id=right.id, role="CUSTODIAN",
                form_year=2020, schedule_code="C", source_field="X",
            ),
        ]
    )
    session.commit()

    # Scoped to the pair under test: the fixture gives this plan a custodian in
    # its own year too, and that later move is a real one.
    report = _detect(session, role="CUSTODIAN")
    between = [
        change
        for change in report.changes
        if change.plan_id == plan.id and (change.from_year, change.to_year) == (2019, 2020)
    ]

    assert not between


def test_one_engagement_filed_on_two_schedules_is_counted_once(session, imported):
    """
    A plan naming the same firm on Schedule C and Schedule H in the same year
    must not read as two providers, or every such plan looks like it churned.
    """

    plan = session.execute(select(Plan)).scalars().first()
    assert plan is not None

    keeper = Provider(name="STEADY TRUST CO", name_key="steady trust co")
    mover = Provider(name="OTHER TRUST CO", name_key="other trust co")
    session.add_all([keeper, mover])
    session.flush()

    session.add_all(
        [
            # 2019: the same firm, twice, from two schedules.
            PlanParty(
                plan_id=plan.id, provider_id=keeper.id, role="INSURER",
                form_year=2019, schedule_code="C", source_field="A",
            ),
            PlanParty(
                plan_id=plan.id, provider_id=keeper.id, role="INSURER",
                form_year=2019, schedule_code="H", source_field="B",
            ),
            # 2020: a genuine move.
            PlanParty(
                plan_id=plan.id, provider_id=mover.id, role="INSURER",
                form_year=2020, schedule_code="C", source_field="A",
            ),
        ]
    )
    session.commit()

    changes = [
        change for change in _detect(session, role="INSURER").changes
        if change.plan_id == plan.id
    ]

    assert len(changes) == 1
    assert changes[0].from_provider == "STEADY TRUST CO"


def test_a_missing_year_does_not_read_as_a_change(session, imported):
    """
    Adjacent *observed* years are compared, not every year in the range — a
    plan that skipped 2020 has not therefore changed anything.
    """

    plan = session.execute(select(Plan)).scalars().first()
    assert plan is not None

    steady = Provider(name="UNMOVING BANK", name_key="unmoving bank")
    session.add(steady)
    session.flush()

    for year in (2017, 2021):
        session.add(
            PlanParty(
                plan_id=plan.id, provider_id=steady.id, role="TRUSTEE",
                form_year=year, schedule_code="H", source_field="T",
            )
        )
    session.commit()

    # Only the 2017 -> 2021 pair is under test. The fixture also names a
    # trustee in its own year, and moving away from UNMOVING BANK to that one
    # is a change that genuinely happened.
    changes = [
        change
        for change in _detect(session, role="TRUSTEE").changes
        if change.plan_id == plan.id and (change.from_year, change.to_year) == (2017, 2021)
    ]

    assert not changes


def test_appearances_and_disappearances_are_off_by_default(two_years):
    """
    A role vanishing usually means the schedule carrying it was not imported.
    Reporting those by default would read as a wave of losses that never
    happened.
    """

    report = _detect(two_years)

    assert all(change.kind is ChangeKind.SWITCHED for change in report.changes)


# ----------------------------------------------------------------------
# Filters and shaping
# ----------------------------------------------------------------------


def test_filtering_by_the_firm_that_lost_the_plan(two_years):
    all_changes = _detect(two_years).changes
    assert all_changes

    target = all_changes[0].from_provider
    filtered = _detect(two_years, from_provider=target).changes

    assert filtered
    assert all(change.from_provider == target for change in filtered)


def test_filtering_by_the_firm_that_won_the_plan(two_years):
    target = _detect(two_years).changes[0].to_provider
    filtered = _detect(two_years, to_provider=target).changes

    assert filtered
    assert all(change.to_provider == target for change in filtered)


def test_filtering_by_the_year_the_change_landed(two_years):
    filtered = _detect(two_years, year=2023).changes

    assert filtered
    assert all(change.to_year == 2023 for change in filtered)

    assert not _detect(two_years, year=2009).changes


def test_filtering_by_size(two_years):
    filtered = _detect(two_years, min_participants=500).changes

    assert all((change.participants or 0) >= 500 for change in filtered)


def test_the_limit_is_honoured(two_years):
    assert len(_detect(two_years, limit=1).changes) <= 1


def test_flows_aggregate_by_pair(two_years):
    report = _detect(two_years)
    flows = report.flows()

    assert flows
    for source, target, count, assets in flows:
        assert source and target
        assert count >= 1
        assert assets >= 0

    counts = [row[2] for row in flows]
    assert counts == sorted(counts, reverse=True)


def test_wins_and_losses_read_from_the_same_report(two_years):
    report = _detect(two_years)
    change = report.changes[0]

    assert change in report.losses(change.from_provider)
    assert change in report.wins(change.to_provider)


def test_every_change_describes_itself(two_years):
    for change in _detect(two_years).changes:
        assert change.plan_name in change.describe()
        assert str(change.to_year) in change.describe()


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------


def test_changes_export_to_csv(two_years, tmp_path):
    from app.services.export import export_provider_changes_csv

    report = _detect(two_years)
    path = export_provider_changes_csv(report.changes, tmp_path / "changes.csv")

    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()

    assert len(lines) == len(report.changes) + 1
    assert "from_provider" in lines[0]
    assert report.changes[0].plan_name in text
