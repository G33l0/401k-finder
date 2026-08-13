from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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
    """Normalized retirement/welfare plan record."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_number: Mapped[str | None] = mapped_column(String(20), index=True)

    plan_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)

    sponsor_name: Mapped[str | None] = mapped_column(
        String(500),
        index=True,
    )

    sponsor_ein: Mapped[str | None] = mapped_column(
        String(20),
        index=True,
    )

    sponsor_city: Mapped[str | None] = mapped_column(String(200))
    sponsor_state: Mapped[str | None] = mapped_column(String(50), index=True)
    sponsor_zip: Mapped[str | None] = mapped_column(String(20))

    plan_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    filing_type: Mapped[str | None] = mapped_column(String(20))

    filing_status: Mapped[str | None] = mapped_column(
        String(50),
        index=True,
    )

    plan_type: Mapped[str | None] = mapped_column(String(100), index=True)

    participants: Mapped[int | None] = mapped_column(Integer)

    total_assets: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2)
    )

    total_income: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 2)
    )

    source_form_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    source_filing_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
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

    providers: Mapped[list["PlanProvider"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "source_form_year",
            "source_filing_id",
            name="uq_plan_source_filing",
        ),
        Index(
            "ix_plan_sponsor_year",
            "sponsor_name",
            "plan_year",
        ),
    )


class Provider(Base):
    """Financial institution/service provider."""

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

    website: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plans: Mapped[list["PlanProvider"]] = relationship(
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class PlanProvider(Base):
    """Association between a plan and a financial institution."""

    __tablename__ = "plan_providers"

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

    source_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    schedule: Mapped[str | None] = mapped_column(
        String(50)
    )

    service_description: Mapped[str | None] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="providers"
    )

    provider: Mapped["Provider"] = relationship(
        back_populates="plans"
    )

    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "provider_id",
            "source_year",
            "schedule",
            name="uq_plan_provider_year_schedule",
        ),
    )


class Evidence(Base):
    """Source information supporting a search result."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_reference: Mapped[str | None] = mapped_column(
        String(1000)
    )

    field_name: Mapped[str | None] = mapped_column(
        String(200)
    )

    field_value: Mapped[str | None] = mapped_column(
        Text
    )

    notes: Mapped[str | None] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="evidence"
    )