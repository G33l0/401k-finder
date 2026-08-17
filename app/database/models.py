from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Plan(Base):
    """
    A retirement or welfare plan, deduplicated across years.

    DOL identifies a plan by the pair (sponsor EIN, plan number). Everything a
    filing says about the plan is stored on ``Filing``; the columns here are the
    values from the most recent filing seen, so search results can be rendered
    without joining every year.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    ein: Mapped[str | None] = mapped_column(String(9), index=True)
    plan_number: Mapped[str | None] = mapped_column(String(3), index=True)

    plan_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    sponsor_name: Mapped[str | None] = mapped_column(String(500), index=True)
    sponsor_dba_name: Mapped[str | None] = mapped_column(String(500))

    sponsor_city: Mapped[str | None] = mapped_column(String(200))
    sponsor_state: Mapped[str | None] = mapped_column(String(2), index=True)
    sponsor_zip: Mapped[str | None] = mapped_column(String(12), index=True)
    sponsor_phone: Mapped[str | None] = mapped_column(String(30))
    business_code: Mapped[str | None] = mapped_column(String(6), index=True)

    plan_effective_date: Mapped[date | None] = mapped_column(Date)

    #: PlanCategory value derived from the benefit codes.
    plan_category: Mapped[str | None] = mapped_column(String(30), index=True)
    #: Sorted PlanFeature values, joined with "|" for cheap LIKE filtering.
    plan_features: Mapped[str | None] = mapped_column(String(400), index=True)
    #: Raw characteristics codes as filed, e.g. "2E|2G|2J".
    benefit_codes: Mapped[str | None] = mapped_column(String(200))

    is_retirement_plan: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    first_year: Mapped[int | None] = mapped_column(Integer, index=True)
    last_year: Mapped[int | None] = mapped_column(Integer, index=True)

    latest_participants: Mapped[int | None] = mapped_column(Integer, index=True)
    latest_active_participants: Mapped[int | None] = mapped_column(Integer)
    latest_total_assets: Mapped[float | None] = mapped_column(Float, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    filings: Mapped[list[Filing]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    parties: Mapped[list[PlanParty]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("ein", "plan_number", name="uq_plan_ein_pn"),
        Index("ix_plan_sponsor_state", "sponsor_name", "sponsor_state"),
        Index("ix_plan_retirement_year", "is_retirement_plan", "last_year"),
    )

    @property
    def plan_key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"

    def feature_list(self) -> list[str]:
        return [item for item in (self.plan_features or "").split("|") if item]

    def benefit_code_list(self) -> list[str]:
        return [item for item in (self.benefit_codes or "").split("|") if item]


class Filing(Base):
    """
    One Form 5500, 5500-SF or DCG filing, keyed by its DOL ACK_ID.

    ACK_ID is the join key for every schedule dataset, which is why it is
    unique and indexed rather than derived.
    """

    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    ack_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )

    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    plan_name: Mapped[str | None] = mapped_column(String(500))
    sponsor_name: Mapped[str | None] = mapped_column(String(500))
    ein: Mapped[str | None] = mapped_column(String(9), index=True)
    plan_number: Mapped[str | None] = mapped_column(String(3))

    plan_year_begin: Mapped[date | None] = mapped_column(Date)
    plan_year_end: Mapped[date | None] = mapped_column(Date)

    filing_status: Mapped[str | None] = mapped_column(String(60), index=True)
    date_received: Mapped[date | None] = mapped_column(Date)

    is_initial: Mapped[bool | None] = mapped_column(Boolean)
    is_amended: Mapped[bool | None] = mapped_column(Boolean)
    is_final: Mapped[bool | None] = mapped_column(Boolean)
    is_short_year: Mapped[bool | None] = mapped_column(Boolean)

    plan_entity_code: Mapped[str | None] = mapped_column(String(2))
    dfe_entity_code: Mapped[str | None] = mapped_column(String(2))
    business_code: Mapped[str | None] = mapped_column(String(6))

    pension_codes: Mapped[str | None] = mapped_column(String(200))
    welfare_codes: Mapped[str | None] = mapped_column(String(200))
    plan_category: Mapped[str | None] = mapped_column(String(30))
    plan_features: Mapped[str | None] = mapped_column(String(400))

    total_participants: Mapped[int | None] = mapped_column(Integer)
    active_participants: Mapped[int | None] = mapped_column(Integer)
    participants_with_balances: Mapped[int | None] = mapped_column(Integer)

    total_assets_boy: Mapped[float | None] = mapped_column(Float)
    total_assets_eoy: Mapped[float | None] = mapped_column(Float)
    net_assets_eoy: Mapped[float | None] = mapped_column(Float)
    employer_contributions: Mapped[float | None] = mapped_column(Float)
    participant_contributions: Mapped[float | None] = mapped_column(Float)

    admin_name: Mapped[str | None] = mapped_column(String(200))
    admin_ein: Mapped[str | None] = mapped_column(String(9))

    source_dataset: Mapped[str | None] = mapped_column(String(60))
    source_release: Mapped[str | None] = mapped_column(String(20))
    source_file: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="filings")

    schedule_records: Mapped[list[ScheduleRecord]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[Evidence]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_filing_plan_year", "plan_id", "form_year"),
        Index("ix_filing_year_type", "form_year", "form_type"),
    )


class Provider(Base):
    """
    An organisation named in a filing: recordkeeper, trustee, insurer, and so on.

    Providers are grouped by ``name_key`` — a punctuation- and suffix-stripped
    form of the filed name — so that the dozens of spellings of one firm across
    hundreds of thousands of filings resolve to a single entity, while the
    original filed text stays on each PlanParty row.
    """

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    name_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)

    ein: Mapped[str | None] = mapped_column(String(9), index=True)
    city: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str | None] = mapped_column(String(2), index=True)

    #: Best-guess canonical name for a well-known firm, when recognised.
    canonical_name: Mapped[str | None] = mapped_column(String(200), index=True)
    #: Dominant role across all of this provider's engagements.
    primary_role: Mapped[str | None] = mapped_column(String(60), index=True)

    plan_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    participant_count: Mapped[int] = mapped_column(Integer, default=0)
    assets_under_administration: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    parties: Mapped[list[PlanParty]] = relationship(
        back_populates="provider", cascade="all, delete-orphan"
    )


class PlanParty(Base):
    """
    A provider engaged by a plan in a particular role, for a particular year.

    This is the table that answers "who holds this 401(k)". Every row carries
    the schedule and field it came from so the answer stays auditable.
    """

    __tablename__ = "plan_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), index=True
    )

    role: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    #: The name exactly as filed, before name-key normalisation.
    reported_name: Mapped[str | None] = mapped_column(String(500))
    reported_ein: Mapped[str | None] = mapped_column(String(9))
    relationship_text: Mapped[str | None] = mapped_column(String(200))

    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    schedule_code: Mapped[str | None] = mapped_column(String(20), index=True)
    source_field: Mapped[str | None] = mapped_column(String(120))

    service_codes: Mapped[str | None] = mapped_column(String(120))
    direct_compensation: Mapped[float | None] = mapped_column(Float)
    indirect_compensation: Mapped[float | None] = mapped_column(Float)

    confidence: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="parties")
    provider: Mapped[Provider] = relationship(back_populates="parties")

    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "provider_id",
            "role",
            "form_year",
            "schedule_code",
            name="uq_party_plan_provider_role_year",
        ),
        Index("ix_party_plan_year_role", "plan_id", "form_year", "role"),
        Index("ix_party_provider_year", "provider_id", "form_year"),
    )

    def service_code_list(self) -> list[str]:
        return [item for item in (self.service_codes or "").split("|") if item]


class ScheduleRecord(Base):
    """
    A parsed schedule row, stored with its original columns intact.

    ``raw_data`` keeps the filed values so extraction rules can be improved and
    re-run later without re-downloading tens of gigabytes from DOL.
    """

    __tablename__ = "schedule_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    ack_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), index=True
    )

    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dataset: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    schedule_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    row_order: Mapped[int | None] = mapped_column(Integer)
    source_file: Mapped[str | None] = mapped_column(String(500))
    source_row: Mapped[int | None] = mapped_column(Integer)

    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    plan: Mapped[Plan | None] = relationship()
    filing: Mapped[Filing | None] = relationship(back_populates="schedule_records")

    __table_args__ = (
        UniqueConstraint("ack_id", "dataset", "row_order", name="uq_schedule_ack_dataset_row"),
        Index("ix_schedule_year_dataset", "form_year", "dataset"),
    )


class Evidence(Base):
    """
    The provenance record behind a stated result.

    Every provider attribution writes one of these, naming the dataset, file,
    row and field it came from, so any claim the application makes can be
    traced back to a specific line of a specific DOL file.
    """

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"), index=True
    )
    party_id: Mapped[int | None] = mapped_column(
        ForeignKey("plan_parties.id", ondelete="CASCADE"), index=True
    )

    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    ack_id: Mapped[str | None] = mapped_column(String(40), index=True)

    source_type: Mapped[str] = mapped_column(String(60), nullable=False)
    dataset: Mapped[str | None] = mapped_column(String(60))
    schedule_code: Mapped[str | None] = mapped_column(String(20), index=True)
    source_file: Mapped[str | None] = mapped_column(String(500))
    source_row: Mapped[int | None] = mapped_column(Integer)

    field_name: Mapped[str | None] = mapped_column(String(120))
    field_value: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(String(10))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    plan: Mapped[Plan] = relationship(back_populates="evidence")
    filing: Mapped[Filing | None] = relationship(back_populates="evidence")

    __table_args__ = (
        # One record per field of a source row. Without this, re-importing a
        # dataset appends a second copy of every citation, inflating the
        # evidence trail while telling the user nothing new.
        UniqueConstraint(
            "ack_id",
            "dataset",
            "source_row",
            "field_name",
            name="uq_evidence_source_field",
        ),
        Index("ix_evidence_plan_year", "plan_id", "form_year"),
    )


class ImportedDataset(Base):
    """
    Tracks which DOL datasets have been imported, so syncs are resumable.

    A dataset is only skipped on a later run when it completed successfully and
    the source file is unchanged; failed runs stay recorded with their error.
    """

    __tablename__ = "imported_datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    dataset: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    release: Mapped[str] = mapped_column(String(20), nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)

    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_file: Mapped[str | None] = mapped_column(String(500))
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    file_size: Mapped[int | None] = mapped_column(Integer)

    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    parties_created: Mapped[int] = mapped_column(Integer, default=0)

    error: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("form_year", "dataset", "release", name="uq_import_year_dataset_release"),
    )


class PlanTransfer(Base):
    """
    Assets moved from one plan to another, as reported on Schedule H Part 1.

    This is the only place the filings say **where the money went** when a plan
    is merged or wound up. A participant whose old plan no longer exists has one
    question, and this table is the answer to it: the receiving plan is named
    with its own EIN and plan number, which is enough to look it up and find who
    holds it now.

    ``to_plan_id`` is filled in when the receiving plan is also in this
    database. It stays null when it is not -- the transferee may be a plan that
    has never been imported, or one that files under a different EIN -- and the
    reported name, EIN and plan number are kept regardless, because they are
    still what a person quotes when they write to ask.
    """

    __tablename__ = "plan_transfers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    #: The plan the assets left.
    from_plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ack_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    form_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    #: The receiving plan, exactly as reported.
    to_name: Mapped[str | None] = mapped_column(String(500))
    to_ein: Mapped[str | None] = mapped_column(String(9), index=True)
    to_plan_number: Mapped[str | None] = mapped_column(String(3))

    #: Resolved to a row in `plans` when the receiving plan is held locally.
    to_plan_id: Mapped[int | None] = mapped_column(
        ForeignKey("plans.id", ondelete="SET NULL"), index=True
    )

    source_file: Mapped[str | None] = mapped_column(String(500))
    source_row: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    __table_args__ = (
        # One row per reported transfer. Re-importing a year must not duplicate
        # them, and the source row number is what makes each one distinct when a
        # plan reports several transfers on the same filing.
        UniqueConstraint(
            "ack_id", "source_row", "to_ein", "to_plan_number", name="uq_transfer_row"
        ),
        Index("ix_transfer_target", "to_ein", "to_plan_number"),
    )

    @property
    def target_key(self) -> str:
        return f"{self.to_ein or '?'}-{self.to_plan_number or '?'}"
