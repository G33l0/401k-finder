"""
Tracing a work history to the plans that could hold someone's account.

Two things are load-bearing here and both are tested hard:

* **No Social Security number reaches storage.** Not because of a policy, but
  because Form 5500 has nothing to match one against — so a number typed into
  the wrong box is pure liability with no upside.
* **A match is only useful if it names who to contact.** A plan name alone
  leaves the person exactly where they started.
"""

from __future__ import annotations

import pytest

from app.trace import AccountTracer, Employment, WorkHistory, looks_like_ssn, redact
from app.trace.history import REDACTION
from app.trace.packet import claim_letter, next_steps, render_report
from app.trace.resources import RESOURCES, Audience, for_audience

# ----------------------------------------------------------------------
# The Form 5500 data holds no participants. This is the premise.
# ----------------------------------------------------------------------


def test_no_published_layout_contains_participant_identity():
    """
    The reason this feature cannot take an SSN, asserted against the vendored
    layouts rather than left as a claim in a docstring. If DOL ever publishes a
    participant-level field, this fails and the design should be revisited.
    """

    import re

    from app.dol.layouts.loader import iter_layouts

    identifying = re.compile(
        r"SSN|SOCIAL_SEC|PARTICIPANT_NAME|PARTCP_NAME|EMPLOYEE_NAME"
        r"|MEMBER_NAME|DATE_OF_BIRTH|\bDOB\b"
    )

    offenders = {
        f"{layout.dataset} {layout.form_year}: {field.name}"
        for layout in iter_layouts()
        for field in layout.fields
        if identifying.search(field.name.upper())
    }

    assert not offenders, f"participant-level fields appeared: {sorted(offenders)[:5]}"


# ----------------------------------------------------------------------
# Keeping an SSN out
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "123-45-6789",
        "123 45 6789",
        "123456789",
        "078.05.1120",
        "my number is 111-22-3333 thanks",
        "123–45–6789",
    ],
)
def test_ssn_shapes_are_detected(text):
    assert looks_like_ssn(text)


@pytest.mark.parametrize(
    "text",
    [
        "Acme Manufacturing",
        "",
        "1234",
        "2008-2012",
        "EIN 12-3456789",
        "Employer ID 123456789",
    ],
)
def test_ordinary_text_is_not_flagged(text):
    """An EIN is nine digits too, and sponsors legitimately carry one."""

    assert not looks_like_ssn(text)


def test_an_ssn_never_survives_into_an_employment_record():
    job = Employment("123-45-6789")

    assert REDACTION in job.employer
    assert "123" not in job.employer
    assert "6789" not in job.employer


def test_an_ssn_in_a_note_is_redacted_too():
    job = Employment("Acme", note="ssn 078-05-1120 if you need it")

    assert "078" not in job.note
    assert REDACTION in job.note


def test_the_person_name_is_redacted():
    history = WorkHistory(person="Jane Doe 123-45-6789")

    assert "6789" not in history.person


def test_redaction_leaves_an_ein_alone():
    assert redact("EIN 12-3456789") == "EIN 12-3456789"


def test_no_ssn_reaches_a_rendered_report(session):
    history = WorkHistory(person="Jane 123-45-6789")
    history.add("456-78-9012 Machine Shop", state="OH")

    report = AccountTracer(session).trace(history)
    text = render_report(report, letters=True)

    for fragment in ("123-45-6789", "456-78-9012", "6789", "9012"):
        assert fragment not in text


def test_the_claim_letter_tells_the_reader_not_to_post_their_ssn(session, imported):
    """The letter is sent to a stranger, so it must not invite one."""

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC")

    report = AccountTracer(session).trace(history)
    match = report.traces[0].strongest
    assert match is not None

    letter = claim_letter(match, "Jane Doe")

    assert "have not included" in letter
    assert "Social Security number" in letter


# ----------------------------------------------------------------------
# Employment
# ----------------------------------------------------------------------


def test_a_reversed_year_range_is_corrected():
    """People transpose these, and a reversed range silently matches nothing."""

    job = Employment("Acme", start_year=2012, end_year=2008)

    assert (job.start_year, job.end_year) == (2008, 2012)


def test_years_allow_slack_for_plan_years_that_straddle():
    job = Employment("Acme", start_year=2010, end_year=2012)

    covered = list(job.years(2009, 2025))

    assert covered[0] == 2009, "a filing for the year before can still cover the job"
    assert covered[-1] == 2013


def test_years_are_clamped_to_what_was_imported():
    job = Employment("Acme", start_year=1975, end_year=2050)

    assert list(job.years(2020, 2023)) == [2020, 2021, 2022, 2023]


def test_a_job_with_no_dates_searches_everything():
    assert list(Employment("Acme").years(2020, 2023)) == [2020, 2021, 2022, 2023]


@pytest.mark.parametrize(
    "start,end,first,last,expected",
    [
        (2008, 2012, 2009, 2023, True),
        (2020, 2023, 2009, 2015, False),
        (1990, 1995, 2009, 2023, False),
        (2008, 2012, 2013, 2020, True),  # one year of slack
        (None, None, 2009, 2023, True),
    ],
)
def test_overlap(start, end, first, last, expected):
    job = Employment("Acme", start_year=start, end_year=end)

    assert job.overlaps(first, last) is expected


def test_states_are_normalised_and_collected():
    history = WorkHistory()
    history.add("A", state="oh")
    history.add("B", state="Tx")
    history.add("C", state="ZZ")

    assert history.states == ["OH", "TX"], "ZZ is not a state and must not be offered"


# ----------------------------------------------------------------------
# The CSV
# ----------------------------------------------------------------------


def test_a_hand_typed_csv_is_read(tmp_path):
    path = tmp_path / "history.csv"
    path.write_text(
        "Employer,State,Start_Year,End_Year\n"
        "Acme Manufacturing,OH,2008,2012\n"
        "\n"
        "Beta Foods,tx,Jan 2015,2019-12-31\n",
        encoding="utf-8",
    )

    history = WorkHistory.from_csv(path)

    assert len(history) == 2
    assert history.jobs[0].state == "OH"
    assert history.jobs[1].start_year == 2015
    assert history.jobs[1].end_year == 2019


def test_a_csv_without_an_employer_column_says_so(tmp_path):
    path = tmp_path / "wrong.csv"
    path.write_text("company,state\nAcme,OH\n", encoding="utf-8")

    with pytest.raises(ValueError, match="employer"):
        WorkHistory.from_csv(path)


def test_an_empty_csv_is_rejected(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("employer,state\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no employers"):
        WorkHistory.from_csv(path)


# ----------------------------------------------------------------------
# Matching against real imported filings
# ----------------------------------------------------------------------


def test_a_known_employer_is_found(session, imported):
    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL")

    report = AccountTracer(session).trace(history)

    assert report.total_matches > 0

    match = report.traces[0].strongest
    assert match is not None
    assert "ACME" in match.plan_name.upper()
    assert match.confidence == "STRONG"
    assert match.ein


def test_a_match_names_who_to_contact(session, imported):
    """A plan name alone leaves the person where they started."""

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL")

    match = AccountTracer(session).trace(history).traces[0].strongest
    assert match is not None

    holder = match.best_holder()
    assert holder is not None
    assert holder.name
    assert holder.role in {"RECORDKEEPER", "TRUSTEE", "CUSTODIAN", "INSURER"}
    # Everything traces back to a named field of a named schedule.
    assert holder.schedule_code
    assert str(holder.form_year) in holder.citation()


def test_a_fictional_employer_finds_nothing(session, imported):
    history = WorkHistory()
    history.add("Entirely Fictional Bakery Of Nowhere", state="ZZ")

    report = AccountTracer(session).trace(history)

    assert report.total_matches == 0
    assert report.jobs_without_matches


def test_a_partial_name_still_matches(session, imported):
    """People remember "Acme", not "ACME MANUFACTURING INC"."""

    history = WorkHistory()
    history.add("Acme")

    assert AccountTracer(session).trace(history).total_matches > 0


def test_matching_explains_itself(session, imported):
    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL", start_year=2023, end_year=2023)

    match = AccountTracer(session).trace(history).traces[0].strongest
    assert match is not None
    assert match.reasons, "a match with no explanation cannot be judged by the reader"
    assert any("IL" in reason for reason in match.reasons)


def test_a_job_outside_the_imported_years_is_not_matched(session, imported):
    """The fixture is 2023 only, so a 1990s job cannot resolve to it."""

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL", start_year=1990, end_year=1995)

    assert AccountTracer(session).trace(history).total_matches == 0


def test_the_report_states_which_years_were_searched(session, imported):
    """Otherwise "nothing found" reads as "nothing exists"."""

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC")

    report = AccountTracer(session).trace(history)

    assert report.years_searched
    assert 2023 in report.years_searched


def test_an_empty_employer_is_skipped(session):
    assert AccountTracer(session).trace_job(Employment("   ")) == []


# ----------------------------------------------------------------------
# The report
# ----------------------------------------------------------------------


def test_the_report_says_what_it_cannot_do(session, imported):
    """
    Someone reading this must not come away thinking a blank result proves no
    account exists.
    """

    history = WorkHistory()
    history.add("ACME MANUFACTURING INC")

    text = render_report(AccountTracer(session).trace(history))

    # The report is hard-wrapped, so a sentence spans lines. Normalise before
    # asserting on wording, or the test breaks whenever the width changes.
    flowed = " ".join(text.split())

    assert "no participant records" in flowed.lower()
    assert "Lost and Found" in flowed
    assert "not financial, legal or tax advice" in flowed


def test_the_report_lists_where_an_ssn_does_work(session, imported):
    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL")

    text = render_report(AccountTracer(session).trace(history))

    assert "WHERE TO SEARCH BY SOCIAL SECURITY NUMBER" in text
    for resource in for_audience(Audience.ESCHEATED):
        assert resource.url in text


def test_a_report_with_no_matches_still_helps(session):
    history = WorkHistory()
    history.add("Nothing Matches This At All")

    flowed = " ".join(render_report(AccountTracer(session).trace(history)).split())

    assert "No plan matched" in flowed
    assert "Lost and Found" in flowed
    assert "5500-EZ" in flowed, "the exempt-filer explanation is the useful part"


def test_next_steps_change_when_a_plan_was_wound_up(session, imported):
    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL")

    match = AccountTracer(session).trace(history).traces[0].strongest
    assert match is not None

    # Same match, forced into the terminated branch.
    match.final_year = 2019
    steps = " ".join(next_steps(match))

    assert "final return" in steps
    assert "unclaimed property" in steps.lower()


def test_the_letter_carries_the_facts_a_recordkeeper_will_ask_for(session, imported):
    history = WorkHistory()
    history.add("ACME MANUFACTURING INC", state="IL")

    match = AccountTracer(session).trace(history).traces[0].strongest
    assert match is not None

    letter = claim_letter(match, "Jane Doe")

    assert match.plan_name in letter
    assert (match.ein or "") in letter
    assert "Jane Doe" in letter


def test_report_renders_with_letters(session, imported):
    history = WorkHistory(person="Jane Doe")
    history.add("ACME MANUFACTURING INC", state="IL")

    text = render_report(AccountTracer(session).trace(history), letters=True)

    assert "LETTERS TO SEND" in text
    assert "Request for benefit information" in text


# ----------------------------------------------------------------------
# The resource list
# ----------------------------------------------------------------------


def test_every_resource_is_complete():
    for resource in RESOURCES:
        assert resource.name
        assert resource.url.startswith("https://")
        assert resource.holds and resource.needs


def test_the_dol_registry_is_offered_to_everyone():
    """It is the one an ordinary person should try first."""

    universal = for_audience()

    assert any("Lost and Found" in resource.name for resource in universal)


def test_at_least_one_route_takes_an_ssn():
    """The whole point of listing these is to answer the SSN question."""

    assert any(resource.uses_ssn for resource in RESOURCES)
