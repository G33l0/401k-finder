"""
The historical employer report.

The question is "where was this company's 401(k) held over time?", answered
from a company name and nothing else. The failures worth guarding are the ones
that would mislead somebody: naming an investment manager as the recordkeeper,
losing a plan because the company renamed itself, and printing five identical
years where one period would do.

The fixture scripts one employer for exactly this: see
scripts/make_test_data.SCENARIO_INDEX. Vanguard 2019-2020, Fidelity from 2021,
company and plan both renamed in 2022.
"""

from __future__ import annotations

import pytest

from app.core.constants import ConfidenceLevel
from app.reports import (
    EmployerQuery,
    build_report,
    classify_plan,
    find_employers,
    is_investment_vehicle,
    render_report,
    resolve_plan_type,
)
from app.reports.timeline import Observation, consolidate
from scripts.make_test_data import (
    SCENARIO_NEW_PLAN,
    SCENARIO_NEW_SPONSOR,
    SCENARIO_OLD_PLAN,
    SCENARIO_OLD_SPONSOR,
    SCENARIO_RENAME_YEAR,
    SCENARIO_SWITCH_YEAR,
)

SCRIPTED = "ACME MANUFACTURING"


def scripted_plan(session):  # noqa: ANN001, ANN201
    report = build_report(session, EmployerQuery(name=SCRIPTED, plan_type="401k"))
    assert report.found, "the scripted employer should always be found"
    return report, report.plans[0]


# ----------------------------------------------------------------------
# Searching by name alone
# ----------------------------------------------------------------------


def test_a_company_name_alone_is_enough(history):
    """No year, no EIN, no plan number. That is the whole point."""

    report = build_report(history, EmployerQuery(name=SCRIPTED))

    assert report.found
    assert report.years_held == (2019, 2020, 2021, 2022, 2023)
    assert report.ein


def test_a_renamed_company_is_still_the_same_employer(history):
    """
    Anthem became Elevance. Searching the old name has to still find the plan,
    because the plan carries only its most recent sponsor name.
    """

    report, plan = scripted_plan(history)

    assert SCENARIO_OLD_SPONSOR in report.historical_names
    assert report.current_name == SCENARIO_NEW_SPONSOR
    assert plan.filed_years == (2019, 2020, 2021, 2022, 2023)


def test_the_new_company_name_finds_it_too(history):
    report = build_report(history, EmployerQuery(name=SCENARIO_NEW_SPONSOR, plan_type="401k"))

    assert report.found
    assert report.plans[0].filed_years == (2019, 2020, 2021, 2022, 2023)


def test_a_renamed_plan_is_one_plan_not_two(history):
    """Tracked on EIN and plan number, so a rename does not split the history."""

    _, plan = scripted_plan(history)

    assert plan.original_name == SCENARIO_OLD_PLAN
    assert plan.current_name == SCENARIO_NEW_PLAN
    assert plan.plan_name_history is not None

    changes = plan.plan_name_history.transitions
    assert len(changes) == 1
    assert changes[0].year == SCENARIO_RENAME_YEAR
    assert changes[0].before == SCENARIO_OLD_PLAN
    assert changes[0].after == SCENARIO_NEW_PLAN


def test_the_sponsor_rename_is_reported_with_its_year(history):
    _, plan = scripted_plan(history)

    changes = plan.sponsor_name_history.transitions
    assert [(item.before, item.after, item.year) for item in changes] == [
        (SCENARIO_OLD_SPONSOR, SCENARIO_NEW_SPONSOR, SCENARIO_RENAME_YEAR)
    ]


def test_a_similar_name_is_not_merged_into_this_employer(history):
    """Two companies sharing a word are two companies."""

    report = build_report(history, EmployerQuery(name=SCRIPTED))
    eins = {plan.ein for plan in report.plans}

    other = build_report(history, EmployerQuery(name="BLUE RIDGE HEALTHCARE"))
    assert other.found
    assert not eins & {plan.ein for plan in other.plans}


def test_an_unknown_company_reports_nothing_and_suggests(history):
    report = build_report(history, EmployerQuery(name="NO SUCH EMPLOYER ANYWHERE"))

    assert not report.found
    assert "No plan was found" in render_report(report)


def test_find_employers_offers_the_historical_name(history):
    matches = find_employers(history, SCRIPTED)

    assert any(SCENARIO_OLD_SPONSOR in name or SCENARIO_NEW_SPONSOR in name
               for name, _, _ in matches)


# ----------------------------------------------------------------------
# The recordkeeper timeline
# ----------------------------------------------------------------------


def test_identical_consecutive_years_become_one_period(history):
    """Five filings, two periods. Not five rows saying nearly the same thing."""

    _, plan = scripted_plan(history)
    periods = list(plan.recordkeepers)

    assert len(periods) == 2

    first, second = periods
    assert first.start == 2019 and first.end == 2020
    assert second.start == SCENARIO_SWITCH_YEAR and second.end == 2023
    assert "Vanguard" in first.value
    assert "Fidelity" in second.value


def test_the_change_is_reported_with_the_year_it_was_filed(history):
    _, plan = scripted_plan(history)

    changes = plan.recordkeepers.transitions
    assert len(changes) == 1
    assert changes[0].year == SCENARIO_SWITCH_YEAR
    assert "Vanguard" in changes[0].before
    assert "Fidelity" in changes[0].after


def test_the_latest_period_reads_as_present(history):
    report, plan = scripted_plan(history)
    newest = report.years_held[-1]

    assert plan.recordkeepers.current.label(newest).endswith("present")
    assert plan.recordkeepers.periods[0].label(newest) == "2019-2020"


def test_a_recordkeeper_from_schedule_c_is_high_confidence(history):
    """Service code 15 is recordkeeping, filed against the firm doing it."""

    _, plan = scripted_plan(history)

    assert all(period.confidence == ConfidenceLevel.HIGH for period in plan.recordkeepers)


def test_a_plan_with_no_filed_recordkeeper_says_so(history):
    """Never substituted, never guessed upward from an investment manager."""

    report = build_report(history, EmployerQuery(name=SCRIPTED))
    unnamed = [plan for plan in report.plans if not plan.recordkeeper_known]

    assert unnamed, "the fixture has a plan that names no recordkeeper"

    text = render_report(report)
    assert "Not conclusively identified" in text


def test_annual_detail_lists_every_year(history):
    query = EmployerQuery(name=SCRIPTED, plan_type="401k", annual_detail=True)
    text = render_report(build_report(history, query))

    for year in (2019, 2020, 2021, 2022, 2023):
        assert f"\n{year}\n" in text


# ----------------------------------------------------------------------
# Plan types
# ----------------------------------------------------------------------


def test_without_a_type_the_plans_are_grouped(history):
    report = build_report(history, EmployerQuery(name=SCRIPTED))
    grouped = report.by_type()

    assert len(grouped) >= 2
    assert len({plan_type.key for plan_type, _ in grouped}) == len(grouped)


def test_asking_for_401k_returns_only_401k(history):
    report = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k"))

    assert report.found
    assert {plan.plan_type.key for plan in report.plans} == {"401k"}


def test_a_pension_plan_is_not_mixed_into_the_401k_section(history):
    everything = build_report(history, EmployerQuery(name=SCRIPTED))
    pensions = [plan for plan in everything.plans if plan.plan_type.key == "pension"]

    assert pensions, "the fixture files a pension plan for this employer"

    only401k = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k"))
    assert all(plan.plan_type.key == "401k" for plan in only401k.plans)


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("401k", "401k"),
        ("401(k)", "401k"),
        ("401K", "401k"),
        ("403b", "403b"),
        ("403(b)", "403b"),
        ("457(b)", "457b"),
        ("pension", "pension"),
        ("defined benefit", "pension"),
        ("esop", "esop"),
        ("profit sharing", "profit-sharing"),
        ("cash balance", "cash-balance"),
        ("", None),
        (None, None),
        ("nonsense", None),
    ],
)
def test_a_plan_type_is_recognised_however_it_is_typed(typed, expected):
    resolved = resolve_plan_type(typed)

    assert (resolved.key if resolved else None) == expected


def test_the_most_specific_type_wins():
    """
    457 plans have no characteristics code of their own, so a plan flagged 457
    was flagged from its own name. That beats a loosely filed 2J.
    """

    assert classify_plan(("401K", "457B"), "DEFINED_CONTRIBUTION").key == "457b"
    assert classify_plan(("401K", "PROFIT_SHARING"), "DEFINED_CONTRIBUTION").key == "401k"
    assert classify_plan((), "DEFINED_BENEFIT").key == "pension"
    assert classify_plan((), None).key == "other"


def test_a_type_the_report_does_not_know_shows_everything(history):
    report = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="cryptocurrency"))

    assert report.found
    assert any("not a plan type" in note for note in report.notes)


# ----------------------------------------------------------------------
# Investment vehicles
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "VANGUARD TARGET RETIREMENT 2040 FUND",
        "FIDELITY 500 INDEX FUND",
        "T ROWE PRICE RETIREMENT 2045 TRUST",
        "BLACKROCK LIFEPATH INDEX 2050",
        "STATE STREET GLOBAL ADVISORS COLLECTIVE TRUST",
        "METLIFE POOLED SEPARATE ACCOUNT",
        "GROWTH FUND OF AMERICA",
        "SOMETHING STABLE VALUE",
        "A COMMINGLED FUND",
        "AN EXCHANGE TRADED PRODUCT",
    ],
)
def test_a_fund_is_recognised_as_an_investment(name):
    assert is_investment_vehicle(name)


@pytest.mark.parametrize(
    "name",
    [
        "FIDELITY INVESTMENTS INSTITUTIONAL OPERAT",
        "MATRIX TRUST COMPANY",
        "VANGUARD FIDUCIARY TRUST COMPANY",
        "RELIANCE TRUST COMPANY",
        "WELLS FARGO BANK NA",
        "JOHN HANCOCK LIFE INSURANCE COMPANY USA",
        "EMPOWER ANNUITY INSURANCE COMPANY OF AMER",
        "ASCENSUS LLC",
        "CHARLES SCHWAB BANK",
    ],
)
def test_a_real_firm_is_not_mistaken_for_a_fund(name):
    """A trust company is a trustee. Matching on "TRUST" alone would break this."""

    assert not is_investment_vehicle(name)


def test_the_role_alone_can_mark_an_investment():
    assert is_investment_vehicle("ANYTHING AT ALL", "INVESTMENT_VEHICLE")
    assert is_investment_vehicle("ACME INC RETIREMENT TRUST", "TRUST")


def test_investments_are_left_out_of_the_report_by_default(history):
    report = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k"))
    plan = report.plans[0]

    assert plan.investments == []

    for entry in plan.supporting:
        assert not is_investment_vehicle(entry.name, entry.role)


def test_investments_appear_only_when_asked_for(history):
    query = EmployerQuery(name=SCRIPTED, plan_type="401k", include_investments=True)
    report = build_report(history, query)

    text = render_report(report)
    assert "INVESTMENTS AND MANAGERS" in text
    assert "None of these is" in text


def test_no_investment_manager_is_ever_named_as_the_recordkeeper(history):
    """The single most important rule in the whole report."""

    report = build_report(history, EmployerQuery(name=SCRIPTED))

    for plan in report.plans:
        for period in plan.recordkeepers or ():
            assert not is_investment_vehicle(period.value)


# ----------------------------------------------------------------------
# Timeline folding, on its own
# ----------------------------------------------------------------------


def test_a_run_of_identical_years_folds():
    timeline = consolidate(
        [Observation(year=year, value="Vanguard") for year in (2018, 2019, 2020)]
        + [Observation(year=year, value="Fidelity") for year in (2021, 2022)],
        filed_years=range(2018, 2023),
    )

    assert [(p.start, p.end, p.value) for p in timeline] == [
        (2018, 2020, "Vanguard"),
        (2021, 2022, "Fidelity"),
    ]
    assert [(t.year, t.before, t.after) for t in timeline.transitions] == [
        (2021, "Vanguard", "Fidelity")
    ]


def test_a_year_that_was_never_filed_does_not_break_a_run():
    """A plan that skipped 2016 did not change provider in 2016."""

    timeline = consolidate(
        [Observation(year=2015, value="A"), Observation(year=2017, value="A")],
        filed_years=[2015, 2017],
    )

    assert [(p.start, p.end) for p in timeline] == [(2015, 2017)]


def test_a_filed_year_naming_nobody_is_carried_across_and_marked():
    timeline = consolidate(
        [Observation(year=2015, value="A"), Observation(year=2017, value="A")],
        filed_years=[2015, 2016, 2017],
    )

    period = timeline.periods[0]
    assert (period.start, period.end) == (2015, 2017)
    assert period.inferred_years == (2016,)
    assert period.confidence == ConfidenceLevel.MEDIUM


def test_a_gap_between_two_different_providers_is_left_unknown():
    timeline = consolidate(
        [Observation(year=2015, value="A"), Observation(year=2017, value="B")],
        filed_years=[2015, 2016, 2017],
    )

    assert [(p.start, p.end, p.value) for p in timeline] == [(2015, 2015, "A"), (2017, 2017, "B")]
    assert timeline.unknown_years == (2016,)


def test_nothing_observed_is_reported_as_nothing():
    timeline = consolidate([], filed_years=[2019, 2020])

    assert len(timeline) == 0
    assert timeline.current is None
    assert timeline.unknown_years == (2019, 2020)


def test_a_single_year_is_labelled_as_one_year():
    timeline = consolidate([Observation(year=2021, value="A")], filed_years=[2021])

    assert timeline.periods[0].label(2021) == "2021"


def test_present_is_only_used_when_the_period_reaches_the_newest_year():
    timeline = consolidate(
        [Observation(year=year, value="A") for year in (2019, 2020)], filed_years=[2019, 2020]
    )

    assert timeline.periods[0].label(2023) == "2019-2020"
    assert timeline.periods[0].label(2020) == "2019-present"


# ----------------------------------------------------------------------
# The rendered report
# ----------------------------------------------------------------------


def test_the_report_has_the_sections_it_promises(history):
    text = render_report(build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k")))

    for heading in (
        "RETIREMENT PLAN REPORT",
        "EMPLOYER",
        "HISTORICAL RECORDKEEPER TIMELINE",
        "PROVIDER CHANGES",
        "OTHER SERVICE PROVIDERS",
        "PLAN NAME CHANGES",
        "SOURCE RECORDS",
        "END REPORT",
    ):
        assert heading in text, heading


def test_every_conclusion_carries_its_source(history):
    text = render_report(build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k")))

    assert "Schedule C-1-2" in text
    assert "SOURCE RECORDS" in text
    assert "Department of Labour Database" in text


def test_the_report_does_not_claim_an_effective_date_it_does_not_have(history):
    """Form 5500 records no date for a provider change. Saying so beats inventing one."""

    text = render_report(build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k")))

    assert "records no date for a provider change" in text


def test_the_trustee_is_reported_apart_from_the_recordkeeper(history):
    report = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k"))
    plan = report.plans[0]

    trustees = [entry for entry in plan.supporting if entry.role == "TRUSTEE"]
    assert trustees

    recordkeepers = {period.value for period in plan.recordkeepers}
    assert not recordkeepers & {entry.name for entry in trustees}


def test_a_year_narrows_without_hiding_the_transition(history):
    """A transition is only visible from both sides, so the timeline stays whole."""

    report = build_report(history, EmployerQuery(name=SCRIPTED, plan_type="401k", form_year=2022))

    assert report.found
    plan = report.plans[0]
    assert plan.filed_years == (2019, 2020, 2021, 2022, 2023)
    assert len(plan.recordkeepers.transitions) == 1
