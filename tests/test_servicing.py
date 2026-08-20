"""
Who serviced a plan, folded by firm and role with the years attached.

This is the question the product exists to answer: a person who left a job in
2014 needs the firm that held the money in 2014, not the one that holds it now.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.providers.directory import CONTACTS, contact_for, known_names
from app.providers.normalizer import canonical_names
from app.providers.servicing import ASSET_HOLDING_ROLES, ServicingHistory, servicing_history


@dataclass
class FakeParty:
    """The shape both PartyResult and PlanParty present."""

    provider_id: int
    display_name: str
    role: str
    form_year: int
    service_codes: tuple[str, ...] = ()
    schedule_code: str | None = "C-1-2"
    confidence: str | None = "HIGH"


def party(name, role, year, provider_id=1, **kwargs):  # noqa: ANN001, ANN201
    return FakeParty(provider_id, name, role, year, **kwargs)


def test_one_firm_over_many_years_becomes_one_row():
    history = servicing_history(
        [party("Fidelity Investments", "RECORDKEEPER", year) for year in (2015, 2016, 2017)]
    )

    assert len(history) == 1
    entry = history.providers[0]
    assert entry.years == (2015, 2016, 2017)
    assert entry.span == "2015-2017"
    assert entry.summary() == "Fidelity Investments (2015-2017)"


def test_a_single_year_is_not_written_as_a_range():
    history = servicing_history([party("Vanguard", "RECORDKEEPER", 2020)])

    assert history.providers[0].summary() == "Vanguard (2020)"


def test_the_same_firm_in_two_roles_stays_two_rows():
    """Fidelity as recordkeeper and as investment manager are different facts."""

    history = servicing_history(
        [
            party("Fidelity Investments", "RECORDKEEPER", 2023),
            party("Fidelity Investments", "INVESTMENT_MANAGER", 2023),
        ]
    )

    assert len(history) == 2
    assert {item.role for item in history} == {"RECORDKEEPER", "INVESTMENT_MANAGER"}


def test_gaps_in_the_years_are_kept():
    """A firm that served, left and came back has not served continuously."""

    history = servicing_history(
        [party("Empower", "RECORDKEEPER", year) for year in (2011, 2012, 2019, 2020)]
    )

    entry = history.providers[0]
    assert entry.years == (2011, 2012, 2019, 2020)
    assert entry.covers(2012)
    assert not entry.covers(2015)
    assert entry.span == "2011-2020"


def test_money_holders_come_first():
    """A person chasing a balance needs the recordkeeper, not the auditor."""

    history = servicing_history(
        [
            party("CliftonLarsonAllen", "ACCOUNTANT", 2023, provider_id=1),
            party("Fidelity Investments", "RECORDKEEPER", 2023, provider_id=2),
            party("Deloitte", "PREPARER", 2023, provider_id=3),
            party("State Street", "TRUSTEE", 2023, provider_id=4),
        ]
    )

    assert [item.name for item in history][:2] == ["Fidelity Investments", "State Street"]
    assert history.best_contact().name == "Fidelity Investments"


def test_the_most_recent_engagement_leads_within_a_role():
    history = servicing_history(
        [
            party("Old Recordkeeper", "RECORDKEEPER", 2010, provider_id=1),
            party("New Recordkeeper", "RECORDKEEPER", 2023, provider_id=2),
        ]
    )

    assert history.providers[0].name == "New Recordkeeper"


@pytest.mark.parametrize("role", sorted(ASSET_HOLDING_ROLES))
def test_asset_holding_roles_are_flagged(role):
    history = servicing_history([party("Somebody", role, 2023)])

    assert history.providers[0].holds_money


@pytest.mark.parametrize("role", ["ACCOUNTANT", "PREPARER", "ATTORNEY", "ACTUARY", "CONSULTANT"])
def test_advisers_are_not_flagged_as_holding_money(role):
    history = servicing_history([party("Somebody", role, 2023)])

    assert not history.providers[0].holds_money


def test_service_codes_and_schedules_are_merged_across_years():
    history = servicing_history(
        [
            party("Fidelity Investments", "RECORDKEEPER", 2022, service_codes=("15",),
                  schedule_code="C-1-2"),
            party("Fidelity Investments", "RECORDKEEPER", 2023, service_codes=("16", "15"),
                  schedule_code="H"),
        ]
    )

    entry = history.providers[0]
    assert entry.service_codes == ("15", "16")
    assert entry.schedule_codes == ("C-1-2", "H")


def test_the_strongest_evidence_is_kept():
    history = servicing_history(
        [
            party("Fidelity Investments", "RECORDKEEPER", 2022, confidence="LOW"),
            party("Fidelity Investments", "RECORDKEEPER", 2023, confidence="HIGH"),
        ]
    )

    assert history.providers[0].confidence == "HIGH"


def test_overlap_answers_the_question_a_person_actually_asks():
    """I worked there from 2013 to 2016. Who held the money then?"""

    history = servicing_history(
        [
            party("Old Recordkeeper", "RECORDKEEPER", year, provider_id=1)
            for year in (2010, 2011, 2012, 2013, 2014)
        ]
        + [
            party("New Recordkeeper", "RECORDKEEPER", year, provider_id=2)
            for year in (2015, 2016, 2017)
        ]
    )

    matched = [item.name for item in history if item.overlaps(2013, 2016)]
    assert sorted(matched) == ["New Recordkeeper", "Old Recordkeeper"]

    assert [item.name for item in history if item.overlaps(2010, 2011)] == ["Old Recordkeeper"]
    assert [item.name for item in history if item.overlaps(2017, 2020)] == ["New Recordkeeper"]


def test_an_open_ended_span_still_matches():
    history = servicing_history([party("Empower", "RECORDKEEPER", 2016)])

    assert history.providers[0].overlaps(None, None)
    assert history.providers[0].overlaps(2010, None)
    assert not history.providers[0].overlaps(None, 2015)


def test_a_reversed_span_is_read_the_way_it_was_meant():
    """Somebody who typed the years the wrong way round still gets an answer."""

    history = servicing_history([party("Empower", "RECORDKEEPER", 2016)])

    assert history.providers[0].overlaps(2020, 2012)


def test_the_column_summary_leads_with_the_money_holders():
    history = servicing_history(
        [
            party("CliftonLarsonAllen", "ACCOUNTANT", 2023, provider_id=1),
            party("Fidelity Investments", "RECORDKEEPER", 2023, provider_id=2),
        ]
    )

    assert history.column_text().startswith("Fidelity Investments (2023)")
    assert "CliftonLarsonAllen" not in history.column_text()


def test_the_column_summary_says_how_many_it_left_out():
    history = servicing_history(
        [party(f"Trustee {index}", "TRUSTEE", 2023, provider_id=index) for index in range(6)]
    )

    text = history.column_text(limit=2)
    assert text.endswith("+4 more")


def test_a_plan_with_only_advisers_still_summarises():
    """With no money-holder at all, showing the auditor beats showing nothing."""

    history = servicing_history([party("CliftonLarsonAllen", "ACCOUNTANT", 2023)])

    assert "CliftonLarsonAllen" in history.column_text()
    assert history.best_contact().name == "CliftonLarsonAllen"


def test_nothing_in_nothing_out():
    history = servicing_history([])

    assert len(history) == 0
    assert history.column_text() == ""
    assert history.best_contact() is None
    assert history.years == ()
    assert isinstance(history, ServicingHistory)


def test_a_party_with_no_name_is_dropped():
    history = servicing_history([party("", "RECORDKEEPER", 2023)])

    assert len(history) == 0


def test_for_year_selects_the_firms_serving_then():
    history = servicing_history(
        [
            party("Old", "RECORDKEEPER", 2012, provider_id=1),
            party("New", "RECORDKEEPER", 2020, provider_id=2),
        ]
    )

    assert [item.name for item in history.for_year(2012)] == ["Old"]
    assert history.for_year(2015) == []


# ----------------------------------------------------------------------
# The contact directory
# ----------------------------------------------------------------------


def test_the_directory_is_attached_to_the_folded_entry():
    history = servicing_history([party("Fidelity Investments", "RECORDKEEPER", 2023)])

    contact = history.providers[0].contact
    assert contact is not None
    assert contact.website.startswith("https://")
    assert contact.phone


def test_a_firm_not_in_the_directory_simply_has_none():
    history = servicing_history([party("SMALLTOWN PENSION SERVICES LLC", "TRUSTEE", 2023)])

    assert history.providers[0].contact is None


def test_every_directory_entry_names_a_real_brand():
    """A typo here would silently attach contact details to nothing."""

    brands = set(canonical_names())
    orphans = [c.canonical_name for c in CONTACTS if c.canonical_name not in brands]

    assert not orphans, f"{orphans} are not canonical provider names"


def test_no_directory_entry_is_duplicated():
    names = [contact.canonical_name for contact in CONTACTS]

    assert len(names) == len(set(names))


@pytest.mark.parametrize("contact", CONTACTS, ids=lambda c: c.canonical_name)
def test_every_entry_is_usable(contact):
    assert contact.has_details, f"{contact.canonical_name} carries neither website nor phone"

    if contact.website:
        assert contact.website.startswith("https://"), "plain http sends a login over the wire"
        assert " " not in contact.website

    if contact.phone:
        assert any(character.isdigit() for character in contact.phone)


def test_lookup_tolerates_nothing_and_nonsense():
    assert contact_for(None) is None
    assert contact_for("") is None
    assert contact_for("   ") is None
    assert contact_for("No Such Firm") is None


def test_lookup_ignores_surrounding_space():
    assert contact_for("  Fidelity Investments  ") is not None


def test_the_big_recordkeepers_are_covered():
    """These are the firms most people's money actually sits with."""

    names = set(known_names())
    for expected in ("Fidelity Investments", "Empower", "Vanguard", "TIAA",
                     "Principal Financial Group", "Voya Financial"):
        assert expected in names


def test_firms_that_were_taken_over_say_so():
    """A 2012 filing naming Prudential is not a dead end; Empower holds it now."""

    empower = contact_for("Empower")
    assert "Prudential" in empower.successor

    wells = contact_for("Wells Fargo")
    assert "Principal" in wells.successor
