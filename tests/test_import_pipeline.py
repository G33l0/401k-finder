"""
End-to-end tests of the import pipeline against synthetic files that carry the
real DOL layout column sets.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.constants import PlanCategory, ProviderRole
from app.database.models import Evidence, Filing, Plan, PlanParty, Provider, ScheduleRecord


def test_import_creates_plans_and_filings(session, imported):
    assert imported.rows_read > 0
    assert imported.errors == []

    plans = session.execute(select(func.count(Plan.id))).scalar()
    filings = session.execute(select(func.count(Filing.id))).scalar()

    assert plans > 0
    assert filings == plans  # one filing per plan in the fixture


def test_schedule_rows_attach_to_their_filings(session, imported):
    """
    The central fix: schedule rows carry no plan identity and must be joined to
    filings by ACK_ID. If that join fails they end up orphaned.
    """

    assert imported.unmatched_ack_ids == 0

    orphans = session.execute(
        select(func.count(ScheduleRecord.id)).where(ScheduleRecord.plan_id.is_(None))
    ).scalar()

    assert orphans == 0


def test_schedule_rows_do_not_collapse_into_one_placeholder_plan(session, imported):
    """
    Regression guard. Reading plan identity out of schedule rows, which do not
    contain any, produced a single "UNKNOWN PLAN" that swallowed every row.
    """

    unknown = session.execute(
        select(func.count(Plan.id)).where(Plan.plan_name == "UNKNOWN PLAN")
    ).scalar()

    assert unknown == 0


def test_plans_are_keyed_by_ein_and_plan_number(session, imported):
    rows = session.execute(select(Plan.ein, Plan.plan_number)).all()
    assert len(rows) == len(set(rows)), "plan identity is not unique"

    for ein, plan_number in rows:
        assert ein is not None
        assert plan_number is not None


def test_ack_ids_are_unique(session, imported):
    ack_ids = session.execute(select(Filing.ack_id)).scalars().all()
    assert len(ack_ids) == len(set(ack_ids))


def test_large_plan_assets_come_from_schedule_h(session, imported):
    """
    Form 5500 itself carries no financial totals; they are on Schedule H. A
    plan filed on the main form must still end up with assets.
    """

    plans = session.execute(
        select(Plan)
        .join(Filing, Filing.plan_id == Plan.id)
        .where(Filing.form_type == "5500")
    ).scalars().all()

    assert plans, "fixture produced no Form 5500 filers"

    for plan in plans:
        assert plan.latest_total_assets is not None
        assert plan.latest_total_assets > 0


def test_providers_are_extracted_with_roles(session, imported):
    roles = set(session.execute(select(PlanParty.role).distinct()).scalars())

    assert ProviderRole.RECORDKEEPER.value in roles
    assert ProviderRole.TRUSTEE.value in roles
    assert ProviderRole.INSURER.value in roles
    assert ProviderRole.ACCOUNTANT.value in roles


def test_recordkeeper_comes_from_schedule_c_with_service_codes(session, imported):
    party = session.execute(
        select(PlanParty).where(PlanParty.role == ProviderRole.RECORDKEEPER.value).limit(1)
    ).scalar_one()

    assert party.schedule_code == "C-1-2"
    assert party.service_codes
    assert party.direct_compensation is not None
    assert party.confidence == "HIGH"


def test_placeholder_provider_names_were_not_stored(session, imported):
    names = set(session.execute(select(Provider.name)).scalars())
    for junk in ("N/A", "NONE", "SAME AS ABOVE", "-", "0"):
        assert junk not in names


def test_every_party_has_evidence(session, imported):
    parties = session.execute(select(func.count(PlanParty.id))).scalar()
    evidence = session.execute(select(func.count(Evidence.id))).scalar()

    assert evidence >= parties


def test_evidence_records_cite_a_dataset_field_and_row(session, imported):
    record = session.execute(select(Evidence).limit(1)).scalar_one()

    assert record.dataset
    assert record.field_name
    assert record.source_row is not None
    assert record.ack_id


def test_plans_are_classified(session, imported):
    categories = set(session.execute(select(Plan.plan_category).distinct()).scalars())

    assert PlanCategory.DEFINED_CONTRIBUTION.value in categories
    assert PlanCategory.UNKNOWN.value not in categories


def test_401k_plans_are_flagged(session, imported):
    count = session.execute(
        select(func.count(Plan.id)).where(Plan.plan_features.like("%401K%"))
    ).scalar()

    assert count > 0


def test_provider_rollups_are_populated(session, imported):
    provider = session.execute(
        select(Provider).order_by(Provider.plan_count.desc()).limit(1)
    ).scalar_one()

    assert provider.plan_count > 0
    assert provider.primary_role is not None


def test_reimport_is_idempotent(session, dol_files, imported):
    """Re-running an import must not duplicate plans, filings or engagements."""

    from app.dol.importer import import_directory

    before = (
        session.execute(select(func.count(Plan.id))).scalar(),
        session.execute(select(func.count(Filing.id))).scalar(),
        session.execute(select(func.count(PlanParty.id))).scalar(),
        session.execute(select(func.count(ScheduleRecord.id))).scalar(),
    )

    import_directory(session, dol_files, form_year=2023)

    after = (
        session.execute(select(func.count(Plan.id))).scalar(),
        session.execute(select(func.count(Filing.id))).scalar(),
        session.execute(select(func.count(PlanParty.id))).scalar(),
        session.execute(select(func.count(ScheduleRecord.id))).scalar(),
    )

    assert before == after
