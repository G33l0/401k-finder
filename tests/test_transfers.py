"""
Following a plan's assets when it merges or winds up.

Schedule H Part 1 is the only place the filings say where the money went. The
failure that matters is not "the chain is one hop short" — it is telling a
participant "we do not know" when the answer was in a file we already had, or
hanging on a chain that loops.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.database.models import Plan, PlanTransfer
from app.dol.transfers import extract_transfer
from app.plans import follow_chain, resolve_transfers, transfer_counts, transfers_from
from app.plans.successor import MAX_HOPS

# ----------------------------------------------------------------------
# Reading the dataset
# ----------------------------------------------------------------------


def test_a_transfer_row_is_read():
    target = extract_transfer(
        {
            "PLAN_TRANSFER_NAME": "  ACME HOLDINGS 401(K) PLAN ",
            "PLAN_TRANSFER_EIN": "12-3456789",
            "PLAN_TRANSFER_PN": "2",
        }
    )

    assert target is not None
    assert target.name == "ACME HOLDINGS 401(K) PLAN"
    assert target.ein == "123456789"
    assert target.plan_number == "002", "plan numbers are three digits everywhere else"


def test_a_name_without_an_ein_is_still_worth_keeping():
    """It is what the person writes to, even if we cannot look it up."""

    target = extract_transfer({"PLAN_TRANSFER_NAME": "SOME SUCCESSOR PLAN"})

    assert target is not None
    assert target.name == "SOME SUCCESSOR PLAN"
    assert not target.is_identifiable or target.ein is None


def test_an_empty_row_is_discarded():
    assert extract_transfer({}) is None
    assert (
        extract_transfer(
            {"PLAN_TRANSFER_NAME": "", "PLAN_TRANSFER_EIN": "", "PLAN_TRANSFER_PN": ""}
        )
        is None
    )


def test_the_transferee_is_not_filed_as_a_provider():
    """
    It is another plan, not a firm the plan paid. Filing it as a provider both
    polluted the provider list and threw away the EIN that makes it findable.
    """

    from app.dol.schedules.schedule_h import definitions

    part1 = next(item for item in definitions(2023) if item.dataset == "F_SCH_H_PART1")

    assert part1.provider_columns == ()


def test_the_dataset_is_downloaded_by_default():
    """A core sync must fetch it, or the feature never has data to work with."""

    from app.dol.catalog import CORE_DATASET_NAMES

    assert "F_SCH_H_PART1" in CORE_DATASET_NAMES


# ----------------------------------------------------------------------
# Against real imported filings
# ----------------------------------------------------------------------


def test_transfers_are_recorded_on_import(session, imported):
    total, resolved = transfer_counts(session)

    assert total > 0, "the fixture files a wind-up chain"
    assert resolved > 0
    assert imported.transfers_recorded == total


def test_a_transfer_resolves_to_the_receiving_plan(session, imported):
    transfer = session.execute(
        select(PlanTransfer).where(PlanTransfer.to_plan_id.is_not(None))
    ).scalars().first()

    assert transfer is not None

    receiving = session.get(Plan, transfer.to_plan_id)
    assert receiving is not None
    assert receiving.ein == transfer.to_ein
    assert receiving.plan_number == transfer.to_plan_number


def test_a_transfer_to_an_unknown_plan_keeps_what_it_knows(session, imported):
    """
    The transferee is often a plan whose year has never been imported. Its name
    and EIN are still what the person writes to.
    """

    unresolved = session.execute(
        select(PlanTransfer).where(PlanTransfer.to_plan_id.is_(None))
    ).scalars().first()

    assert unresolved is not None
    assert unresolved.to_name
    assert unresolved.to_ein


def test_the_chain_is_followed_across_hops(session, imported):
    """The fixture merges one plan into a second, and that one into a third."""

    heads = [
        transfer.from_plan_id
        for transfer in session.execute(select(PlanTransfer)).scalars()
        if len(follow_chain(session, transfer.from_plan_id)) > 1
    ]

    assert heads, "no multi-hop chain in the fixture"

    chain = follow_chain(session, heads[0])

    assert len(chain) >= 2
    assert chain.ends_locally
    assert chain.final is not None
    assert chain.final.to_plan_name, "the far end resolves to a plan we hold"


def test_a_plan_with_no_transfer_has_no_chain(session, imported):
    plan = session.execute(
        select(Plan).where(
            Plan.id.not_in(select(PlanTransfer.from_plan_id))
        )
    ).scalars().first()

    assert plan is not None
    assert not follow_chain(session, plan.id)


def test_resolution_is_idempotent(session, imported):
    """It runs after every import, including ones that change nothing."""

    before = transfer_counts(session)

    assert resolve_transfers(session) == 0
    assert transfer_counts(session) == before


def test_reimporting_does_not_duplicate_transfers(session, dol_files, imported):
    from app.dol.importer import import_directory

    before, _ = transfer_counts(session)
    import_directory(session, dol_files, form_year=2023)
    after, _ = transfer_counts(session)

    assert after == before


def test_transfers_from_returns_newest_first(session, imported):
    ids = {transfer.from_plan_id for transfer in session.execute(select(PlanTransfer)).scalars()}
    rows = transfers_from(session, next(iter(ids)))

    assert rows
    assert rows == sorted(rows, key=lambda row: -row.form_year)


# ----------------------------------------------------------------------
# The walk has to terminate
# ----------------------------------------------------------------------


def _plan_pair(session) -> tuple[Plan, Plan]:
    plans = list(session.execute(select(Plan).limit(2)).scalars())
    assert len(plans) == 2
    return plans[0], plans[1]


def test_a_loop_is_detected_rather_than_followed_forever(session, imported):
    """
    Filings do contain mutual transfers. Without the guard the walk never
    returns, which in the desktop application is a frozen window.
    """

    left, right = _plan_pair(session)

    session.add_all(
        [
            PlanTransfer(
                from_plan_id=left.id,
                ack_id="LOOP-A",
                form_year=2023,
                to_ein=right.ein,
                to_plan_number=right.plan_number,
                to_plan_id=right.id,
                source_row=1,
            ),
            PlanTransfer(
                from_plan_id=right.id,
                ack_id="LOOP-B",
                form_year=2023,
                to_ein=left.ein,
                to_plan_number=left.plan_number,
                to_plan_id=left.id,
                source_row=1,
            ),
        ]
    )
    session.commit()

    chain = follow_chain(session, left.id)

    assert chain.looped
    assert len(chain) <= MAX_HOPS


def test_a_self_transfer_is_never_linked(session, imported):
    """A plan naming itself is a filing error, and a self-loop for the walker."""

    plan = session.execute(select(Plan)).scalars().first()
    assert plan is not None

    session.add(
        PlanTransfer(
            from_plan_id=plan.id,
            ack_id="SELF-1",
            form_year=2023,
            to_ein=plan.ein,
            to_plan_number=plan.plan_number,
            source_row=99,
        )
    )
    session.commit()

    resolve_transfers(session)

    stored = session.execute(
        select(PlanTransfer).where(PlanTransfer.ack_id == "SELF-1")
    ).scalar_one()

    assert stored.to_plan_id is None


def test_a_long_chain_is_truncated(session, imported):
    """A pathological chain must stop, and say that it stopped."""

    # Only plans that report nothing already, or the fixture's own transfers
    # join the chain and it ends early for a legitimate reason.
    plans = list(
        session.execute(
            select(Plan)
            .where(Plan.id.not_in(select(PlanTransfer.from_plan_id)))
            .limit(MAX_HOPS + 3)
        ).scalars()
    )

    if len(plans) < MAX_HOPS + 2:
        pytest.skip("fixture too small for a chain longer than the hop limit")

    for position, (source, target) in enumerate(zip(plans, plans[1:], strict=False)):
        session.add(
            PlanTransfer(
                from_plan_id=source.id,
                ack_id=f"LONG-{position}",
                form_year=2023,
                to_ein=target.ein,
                to_plan_number=target.plan_number,
                to_plan_id=target.id,
                source_row=500 + position,
            )
        )
    session.commit()

    chain = follow_chain(session, plans[0].id)

    assert len(chain) == MAX_HOPS
    assert chain.truncated
    assert "not followed further" in " ".join(chain.narrate())


# ----------------------------------------------------------------------
# What the participant is told
# ----------------------------------------------------------------------


def test_the_trace_reports_where_the_money_went(session, imported):
    from app.trace import AccountTracer, WorkHistory
    from app.trace.packet import next_steps

    moved = [
        transfer.from_plan_id
        for transfer in session.execute(select(PlanTransfer)).scalars()
        if transfer.to_plan_id is not None
    ]
    assert moved

    plan = session.get(Plan, moved[0])
    assert plan is not None

    history = WorkHistory()
    history.add(plan.sponsor_name or plan.plan_name)

    report = AccountTracer(session).trace(history, limit_per_job=5)
    match = next(
        (item for trace in report.traces for item in trace.matches if item.plan_id == plan.id),
        None,
    )

    assert match is not None
    assert match.moved
    assert match.successor is not None

    steps = " ".join(next_steps(match))
    assert "transferred to" in steps


def test_a_wound_up_plan_with_no_transfer_still_gets_advice(session, imported):
    """The old behaviour has to survive for plans that really did just stop."""

    from app.trace.matcher import PlanMatch
    from app.trace.packet import next_steps

    match = PlanMatch(
        plan_id=-1,
        plan_name="GONE PLAN",
        sponsor_name="Gone Inc",
        ein="123456789",
        plan_number="001",
        city=None,
        state=None,
        plan_category="DEFINED_CONTRIBUTION",
        features=(),
        first_year=2010,
        last_year=2015,
        participants=None,
        total_assets=None,
        score=90.0,
        final_year=2015,
    )

    steps = " ".join(next_steps(match))

    assert "final return" in steps
    assert "unclaimed property" in steps.lower()
