from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Plan(Base):
    """
    Normalized retirement-plan record.

    A plan may have multiple filings across multiple years.
    """

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_number: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
    )

    plan_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    sponsor_name: Mapped[str | None] = mapped_column(
        String(500),
        index=True,
    )

    sponsor_ein: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
    )

    sponsor_city: Mapped[str | None] = mapped_column(
        String(200),
    )

    sponsor_state: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
    )

    sponsor_zip: Mapped[str | None] = mapped_column(
        String(20),
    )

    first_year: Mapped[int | None] = mapped_column(Integer)

    last_year: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    filings: Mapped[list["Filing"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    parties: Mapped[list["PlanParty"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    schedule_records: Mapped[list["ScheduleRecord"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_plan_sponsor_name_state",
            "sponsor_name",
            "sponsor_state",
        ),
    )


class Filing(Base):
    """
    A single Form 5500/5500-SF filing.

    One plan can have multiple filings over its lifetime.
    """

    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    form_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    filing_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )

    filing_type: Mapped[str | None] = mapped_column(
        String(30),
    )

    filing_status: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )

    filing_received_date: Mapped[str | None] = mapped_column(
        String(30),
    )

    filing_version: Mapped[str | None] = mapped_column(
        String(100),
    )

    source_dataset: Mapped[str | None] = mapped_column(
        String(50),
    )

    source_file: Mapped[str | None] = mapped_column(
        String(500),
    )

    raw_identifier: Mapped[str | None] = mapped_column(
        String(500),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="filings",
    )

    schedule_records: Mapped[list["ScheduleRecord"]] = relationship(
        back_populates="filing",
        cascade="all, delete-orphan",
    )

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="filing",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "form_year",
            "filing_id",
            name="uq_filing_year_filing_id",
        ),
    )


class Provider(Base):
    """Financial institution or other retirement-plan service provider."""

    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    normalized_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
    )

    provider_type: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )

    website: Mapped[str | None] = mapped_column(
        String(1000),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    parties: Mapped[list["PlanParty"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class PlanParty(Base):
    """
    Links a plan to an organization/person serving a particular role.

    Examples of roles:
        trustee
        administrator
        recordkeeper
        investment_manager
        custodian
        accountant
        insurer
        service_provider
    """

    __tablename__ = "plan_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider_id: Mapped[int] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    role_detail: Mapped[str | None] = mapped_column(
        Text,
    )

    form_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    schedule_code: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
    )

    source_filing_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
    )

    confidence: Mapped[str | None] = mapped_column(
        String(20),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="parties",
    )

    provider: Mapped["Provider"] = relationship(
        back_populates="parties",
    )

    __table_args__ = (
        Index(
            "ix_party_plan_year_role",
            "plan_id",
            "form_year",
            "role",
        ),
    )


class ScheduleRecord(Base):
    """
    Raw/normalized representation of an individual schedule record.

    raw_data preserves the original parsed columns so that future
    extraction rules can be improved without losing source information.
    """

    __tablename__ = "schedule_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filing_id: Mapped[int] = mapped_column(
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    form_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    schedule_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    source_file: Mapped[str | None] = mapped_column(
        String(500),
    )

    source_row: Mapped[int | None] = mapped_column(
        Integer,
    )

    record_key: Mapped[str | None] = mapped_column(
        String(500),
        index=True,
    )

    raw_data: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="schedule_records",
    )

    filing: Mapped["Filing"] = relationship(
        back_populates="schedule_records",
    )

    __table_args__ = (
        Index(
            "ix_schedule_year_code",
            "form_year",
            "schedule_code",
        ),
    )


class Evidence(Base):
    """
    Evidence supporting a normalized result.

    Every important provider result should be traceable back to
    a filing/schedule and, when possible, an individual source field.
    """

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    filing_id: Mapped[int | None] = mapped_column(
        ForeignKey("filings.id", ondelete="SET NULL"),
        index=True,
    )

    form_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    schedule_code: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
    )

    source_file: Mapped[str | None] = mapped_column(
        String(500),
    )

    source_row: Mapped[int | None] = mapped_column(
        Integer,
    )

    field_name: Mapped[str | None] = mapped_column(
        String(250),
    )

    field_value: Mapped[str | None] = mapped_column(
        Text,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000),
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
    )

    confidence: Mapped[str | None] = mapped_column(
        String(20),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="evidence",
    )

    filing: Mapped["Filing | None"] = relationship(
        back_populates="evidence",
    )