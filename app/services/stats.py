"""
Summary statistics over the local database, for the status view and dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Evidence, Filing, Plan, PlanParty, Provider, ScheduleRecord


@dataclass(slots=True)
class DatabaseSummary:
    plans: int = 0
    retirement_plans: int = 0
    filings: int = 0
    providers: int = 0
    parties: int = 0
    schedule_records: int = 0
    evidence: int = 0

    years: tuple[int, ...] = ()
    by_category: list[tuple[str, int]] = field(default_factory=list)
    by_feature: list[tuple[str, int]] = field(default_factory=list)
    by_role: list[tuple[str, int]] = field(default_factory=list)

    total_participants: int = 0
    total_assets: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.plans == 0


def _count(session: Session, model) -> int:  # noqa: ANN001
    return int(session.execute(select(func.count()).select_from(model)).scalar() or 0)


def database_summary(session: Session) -> DatabaseSummary:
    """Collect the headline numbers describing what has been loaded."""

    summary = DatabaseSummary(
        plans=_count(session, Plan),
        filings=_count(session, Filing),
        providers=_count(session, Provider),
        parties=_count(session, PlanParty),
        schedule_records=_count(session, ScheduleRecord),
        evidence=_count(session, Evidence),
    )

    summary.retirement_plans = int(
        session.execute(
            select(func.count()).select_from(Plan).where(Plan.is_retirement_plan.is_(True))
        ).scalar()
        or 0
    )

    summary.years = tuple(
        int(year)
        for year in session.execute(
            select(Filing.form_year).distinct().order_by(Filing.form_year)
        ).scalars()
    )

    summary.by_category = [
        (category or "UNKNOWN", int(count))
        for category, count in session.execute(
            select(Plan.plan_category, func.count())
            .group_by(Plan.plan_category)
            .order_by(func.count().desc())
        )
    ]

    summary.by_role = [
        (role, int(count))
        for role, count in session.execute(
            select(PlanParty.role, func.count())
            .group_by(PlanParty.role)
            .order_by(func.count().desc())
        )
    ]

    summary.total_participants = int(
        session.execute(select(func.sum(Plan.latest_participants))).scalar() or 0
    )
    summary.total_assets = float(
        session.execute(select(func.sum(Plan.latest_total_assets))).scalar() or 0.0
    )

    summary.by_feature = feature_counts(session)

    return summary


def feature_counts(session: Session) -> list[tuple[str, int]]:
    """Count plans carrying each retirement account type."""

    from app.core.constants import PlanFeature

    counts: list[tuple[str, int]] = []

    for feature in PlanFeature:
        value = feature.value
        total = int(
            session.execute(
                select(func.count())
                .select_from(Plan)
                .where(
                    (Plan.plan_features == value)
                    | (Plan.plan_features.like(f"{value}|%"))
                    | (Plan.plan_features.like(f"%|{value}|%"))
                    | (Plan.plan_features.like(f"%|{value}"))
                )
            ).scalar()
            or 0
        )

        if total:
            counts.append((value, total))

    counts.sort(key=lambda item: item[1], reverse=True)
    return counts


def top_providers(session: Session, role: str | None = None, limit: int = 20):
    """Return the largest providers, optionally within one role."""

    statement = select(Provider).order_by(Provider.plan_count.desc()).limit(limit)

    if role:
        statement = statement.where(
            Provider.id.in_(select(PlanParty.provider_id).where(PlanParty.role == role))
        )

    return list(session.execute(statement).scalars())


def year_coverage(session: Session) -> list[tuple[int, int, int]]:
    """Return ``(form_year, filings, plans)`` for each imported year."""

    rows = session.execute(
        select(
            Filing.form_year,
            func.count(Filing.id),
            func.count(func.distinct(Filing.plan_id)),
        )
        .group_by(Filing.form_year)
        .order_by(Filing.form_year.desc())
    )

    return [(int(year), int(filings), int(plans)) for year, filings, plans in rows]
