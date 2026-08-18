"""Plan and provider search over the local database."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import Select, and_, func, or_, select, text
from sqlalchemy.orm import Session

from app.core.constants import ROLE_PRIORITY
from app.core.logging import get_logger
from app.database.models import Filing, Plan, PlanParty, Provider
from app.database.schema import FTS_TABLE
from app.search.query import PlanQuery, ProviderQuery, QueryOptions, SortOrder

logger = get_logger(__name__)

_FTS_SPECIALS = re.compile(r'[":\^\*\(\)\-]+')

TEXT_MATCH_CAP = 5000


@dataclass(slots=True)
class PartyResult:
    """One provider engagement attached to a plan result."""

    provider_id: int
    provider_name: str
    canonical_name: str | None
    role: str
    reported_name: str | None
    form_year: int
    schedule_code: str | None
    source_field: str | None
    service_codes: tuple[str, ...]
    direct_compensation: float | None
    indirect_compensation: float | None
    confidence: str | None

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.provider_name


@dataclass(slots=True)
class PlanResult:
    """A plan as presented to the user."""

    plan_id: int
    plan_name: str
    sponsor_name: str | None
    ein: str | None
    plan_number: str | None
    city: str | None
    state: str | None

    plan_category: str | None
    features: tuple[str, ...]
    benefit_codes: tuple[str, ...]

    first_year: int | None
    last_year: int | None
    participants: int | None
    total_assets: float | None

    parties: list[PartyResult] = field(default_factory=list)
    filing_count: int = 0

    @property
    def plan_key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"

    def parties_by_role(self) -> dict[str, list[PartyResult]]:
        grouped: dict[str, list[PartyResult]] = {}
        for party in self.parties:
            grouped.setdefault(party.role, []).append(party)
        return grouped

    def primary_providers(self) -> list[PartyResult]:
        """The parties that answer "who holds this account", most relevant first."""

        seen: set[tuple[int, str]] = set()
        ordered: list[PartyResult] = []

        for role in ROLE_PRIORITY:
            for party in self.parties:
                if party.role != role:
                    continue
                key = (party.provider_id, party.role)
                if key in seen:
                    continue
                seen.add(key)
                ordered.append(party)

        for party in self.parties:
            key = (party.provider_id, party.role)
            if key not in seen:
                seen.add(key)
                ordered.append(party)

        return ordered


@dataclass(slots=True)
class ProviderResult:
    provider_id: int
    name: str
    canonical_name: str | None
    primary_role: str | None
    state: str | None
    plan_count: int
    participant_count: int
    assets_under_administration: float

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.name


def _fts_available(session: Session) -> bool:
    row = session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": FTS_TABLE},
    ).fetchone()
    return row is not None


def build_match_expression(raw: str) -> str:
    """Turn user text into an FTS5 MATCH expression."""

    cleaned = _FTS_SPECIALS.sub(" ", raw)
    terms = [term for term in cleaned.split() if term]

    if not terms:
        return ""

    quoted = [f'"{term}"' for term in terms[:-1]]
    quoted.append(f'"{terms[-1]}"*')

    return " AND ".join(quoted)


class SearchEngine:
    """Runs plan and provider searches against a session."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._use_fts = _fts_available(session)

    def _text_filtered_ids(self, raw: str) -> list[int] | None:
        """Return plan ids matching the text, or None when there is no text."""

        if not raw.strip():
            return None

        if self._use_fts:
            expression = build_match_expression(raw)
            if not expression:
                return None
            try:
                rows = self.session.execute(
                    text(
                        f"SELECT plan_id FROM {FTS_TABLE} "  # noqa: S608 - table name is a constant
                        f"WHERE {FTS_TABLE} MATCH :q ORDER BY rank LIMIT {TEXT_MATCH_CAP}"
                    ),
                    {"q": expression},
                ).scalars()
                return [int(value) for value in rows]
            except Exception as exc:  # noqa: BLE001 - malformed MATCH, fall back
                logger.debug("FTS query failed (%s); falling back to LIKE.", exc)

        pattern = f"%{raw.strip()}%"
        rows = self.session.execute(
            select(Plan.id)
            .where(
                or_(
                    Plan.plan_name.like(pattern),
                    Plan.sponsor_name.like(pattern),
                    Plan.sponsor_dba_name.like(pattern),
                )
            )
            .limit(TEXT_MATCH_CAP)
        ).scalars()
        return [int(value) for value in rows]

    def _apply_filters(self, statement: Select, query: PlanQuery) -> Select:
        conditions = []

        if query.ein:
            conditions.append(Plan.ein == query.ein)
        if query.plan_number:
            conditions.append(Plan.plan_number == query.plan_number)
        if query.state:
            conditions.append(Plan.sponsor_state == query.state)
        if query.city:
            conditions.append(Plan.sponsor_city.like(f"%{query.city}%"))

        if query.retirement_only:
            conditions.append(Plan.is_retirement_plan.is_(True))
        if query.categories:
            conditions.append(Plan.plan_category.in_(query.categories))

        for feature in query.features:
            conditions.append(
                or_(
                    Plan.plan_features == feature,
                    Plan.plan_features.like(f"{feature}|%"),
                    Plan.plan_features.like(f"%|{feature}|%"),
                    Plan.plan_features.like(f"%|{feature}"),
                )
            )

        if query.min_participants is not None:
            conditions.append(Plan.latest_participants >= query.min_participants)
        if query.max_participants is not None:
            conditions.append(Plan.latest_participants <= query.max_participants)
        if query.min_assets is not None:
            conditions.append(Plan.latest_total_assets >= query.min_assets)
        if query.max_assets is not None:
            conditions.append(Plan.latest_total_assets <= query.max_assets)

        if query.form_years:
            conditions.append(
                and_(
                    Plan.first_year <= max(query.form_years),
                    Plan.last_year >= min(query.form_years),
                )
            )

        if query.active_only:
            conditions.append(Plan.last_year >= (max(query.form_years) if query.form_years else 0))

        if query.provider_id is not None or query.provider_name or query.roles:
            party = select(PlanParty.plan_id)

            if query.provider_id is not None:
                party = party.where(PlanParty.provider_id == query.provider_id)

            if query.provider_name:
                pattern = f"%{query.provider_name}%"
                party = party.join(Provider, Provider.id == PlanParty.provider_id).where(
                    or_(
                        Provider.name.like(pattern),
                        Provider.canonical_name.like(pattern),
                        PlanParty.reported_name.like(pattern),
                    )
                )

            if query.roles:
                party = party.where(PlanParty.role.in_(query.roles))

            if query.form_years:
                party = party.where(PlanParty.form_year.in_(query.form_years))

            conditions.append(Plan.id.in_(party))

        if conditions:
            statement = statement.where(and_(*conditions))

        return statement

    def _apply_sort(self, statement: Select, query: PlanQuery) -> Select:
        """Apply an explicit sort."""

        if query.sort is SortOrder.PLAN_NAME:
            return statement.order_by(Plan.plan_name)
        if query.sort is SortOrder.SPONSOR_NAME:
            return statement.order_by(Plan.sponsor_name)
        if query.sort is SortOrder.PARTICIPANTS:
            return statement.order_by(Plan.latest_participants.desc().nulls_last())
        if query.sort is SortOrder.ASSETS:
            return statement.order_by(Plan.latest_total_assets.desc().nulls_last())
        if query.sort is SortOrder.YEAR:
            return statement.order_by(Plan.last_year.desc().nulls_last())

        return statement.order_by(Plan.latest_participants.desc().nulls_last())

    def search_plans(
        self,
        query: PlanQuery,
        options: QueryOptions | None = None,
    ) -> list[PlanResult]:
        """Run a plan search and return hydrated results."""

        options = options or QueryOptions()

        matched_ids = self._text_filtered_ids(query.text)

        statement = select(Plan)
        if matched_ids is not None:
            if not matched_ids:
                return []
            statement = statement.where(Plan.id.in_(matched_ids))

        statement = self._apply_filters(statement, query)

        ranked = query.sort is SortOrder.RELEVANCE and bool(matched_ids)
        if not ranked:
            statement = self._apply_sort(statement, query)
            statement = statement.limit(query.limit).offset(query.offset)

        plans = list(self.session.execute(statement).scalars())

        if ranked:
            rank = {plan_id: position for position, plan_id in enumerate(matched_ids or [])}
            plans.sort(key=lambda plan: rank.get(plan.id, len(rank)))
            plans = plans[query.offset : query.offset + query.limit]

        if not plans:
            return []

        results = [
            PlanResult(
                plan_id=plan.id,
                plan_name=plan.plan_name,
                sponsor_name=plan.sponsor_name,
                ein=plan.ein,
                plan_number=plan.plan_number,
                city=plan.sponsor_city,
                state=plan.sponsor_state,
                plan_category=plan.plan_category,
                features=tuple(plan.feature_list()),
                benefit_codes=tuple(plan.benefit_code_list()),
                first_year=plan.first_year,
                last_year=plan.last_year,
                participants=plan.latest_participants,
                total_assets=plan.latest_total_assets,
            )
            for plan in plans
        ]

        if options.include_parties:
            self._attach_parties(results, query, options)

        if options.include_filings:
            self._attach_filing_counts(results)

        return results

    def _attach_parties(
        self,
        results: list[PlanResult],
        query: PlanQuery,
        options: QueryOptions,
    ) -> None:
        """Load every result's providers in one query rather than one per plan."""

        by_id = {result.plan_id: result for result in results}

        statement = (
            select(PlanParty, Provider)
            .join(Provider, Provider.id == PlanParty.provider_id)
            .where(PlanParty.plan_id.in_(list(by_id)))
            .order_by(PlanParty.form_year.desc(), PlanParty.role)
        )

        if query.form_years:
            statement = statement.where(PlanParty.form_year.in_(query.form_years))

        if options.roles_of_interest:
            statement = statement.where(PlanParty.role.in_(options.roles_of_interest))

        for party, provider in self.session.execute(statement):
            result = by_id.get(party.plan_id)
            if result is None or len(result.parties) >= options.max_parties:
                continue

            result.parties.append(
                PartyResult(
                    provider_id=provider.id,
                    provider_name=provider.name,
                    canonical_name=provider.canonical_name,
                    role=party.role,
                    reported_name=party.reported_name,
                    form_year=party.form_year,
                    schedule_code=party.schedule_code,
                    source_field=party.source_field,
                    service_codes=tuple(party.service_code_list()),
                    direct_compensation=party.direct_compensation,
                    indirect_compensation=party.indirect_compensation,
                    confidence=party.confidence,
                )
            )

    def _attach_filing_counts(self, results: list[PlanResult]) -> None:
        by_id = {result.plan_id: result for result in results}

        rows = self.session.execute(
            select(Filing.plan_id, func.count(Filing.id))
            .where(Filing.plan_id.in_(list(by_id)))
            .group_by(Filing.plan_id)
        )

        for plan_id, count in rows:
            by_id[plan_id].filing_count = int(count)

    def count_plans(self, query: PlanQuery) -> int:
        """Count matches without hydrating them."""

        return self.count_plans_detailed(query)[0]

    def count_plans_detailed(self, query: PlanQuery) -> tuple[int, bool]:
        """Return ``(count, is_lower_bound)``."""

        matched_ids = self._text_filtered_ids(query.text)
        capped = matched_ids is not None and len(matched_ids) >= TEXT_MATCH_CAP

        statement = select(func.count(Plan.id))
        if matched_ids is not None:
            if not matched_ids:
                return 0, False
            statement = statement.where(Plan.id.in_(matched_ids))

        statement = self._apply_filters(statement, query)
        return int(self.session.execute(statement).scalar() or 0), capped

    def get_plan(self, plan_id: int, options: QueryOptions | None = None) -> PlanResult | None:
        """Load one plan with everything attached."""

        options = options or QueryOptions(
            include_parties=True, include_filings=True, max_parties=500
        )

        plan = self.session.get(Plan, plan_id)
        if plan is None:
            return None

        result = PlanResult(
            plan_id=plan.id,
            plan_name=plan.plan_name,
            sponsor_name=plan.sponsor_name,
            ein=plan.ein,
            plan_number=plan.plan_number,
            city=plan.sponsor_city,
            state=plan.sponsor_state,
            plan_category=plan.plan_category,
            features=tuple(plan.feature_list()),
            benefit_codes=tuple(plan.benefit_code_list()),
            first_year=plan.first_year,
            last_year=plan.last_year,
            participants=plan.latest_participants,
            total_assets=plan.latest_total_assets,
        )

        self._attach_parties([result], PlanQuery(), options)
        self._attach_filing_counts([result])

        return result

    def get_filings(self, plan_id: int) -> list[Filing]:
        """Return a plan's filings, newest first."""

        return list(
            self.session.execute(
                select(Filing)
                .where(Filing.plan_id == plan_id)
                .order_by(Filing.form_year.desc(), Filing.id.desc())
            ).scalars()
        )

    def search_providers(self, query: ProviderQuery) -> list[ProviderResult]:
        statement = select(Provider)

        if query.text.strip():
            pattern = f"%{query.text.strip()}%"
            statement = statement.where(
                or_(Provider.name.like(pattern), Provider.canonical_name.like(pattern))
            )

        if query.role:
            statement = statement.where(
                Provider.id.in_(select(PlanParty.provider_id).where(PlanParty.role == query.role))
            )

        if query.state:
            statement = statement.where(Provider.state == query.state)

        if query.min_plans is not None:
            statement = statement.where(Provider.plan_count >= query.min_plans)

        if query.canonical_only:
            statement = statement.where(Provider.canonical_name.is_not(None))

        if query.sort == "name":
            statement = statement.order_by(Provider.name)
        elif query.sort == "assets":
            statement = statement.order_by(Provider.assets_under_administration.desc())
        elif query.sort == "participants":
            statement = statement.order_by(Provider.participant_count.desc())
        else:
            statement = statement.order_by(Provider.plan_count.desc())

        statement = statement.limit(query.limit).offset(query.offset)

        return [
            ProviderResult(
                provider_id=provider.id,
                name=provider.name,
                canonical_name=provider.canonical_name,
                primary_role=provider.primary_role,
                state=provider.state,
                plan_count=provider.plan_count,
                participant_count=provider.participant_count,
                assets_under_administration=provider.assets_under_administration,
            )
            for provider in self.session.execute(statement).scalars()
        ]

    def provider_roles(self, provider_id: int) -> list[tuple[str, int]]:
        """Return the roles a provider serves and how many plans in each."""

        rows = self.session.execute(
            select(PlanParty.role, func.count(func.distinct(PlanParty.plan_id)))
            .where(PlanParty.provider_id == provider_id)
            .group_by(PlanParty.role)
            .order_by(func.count(func.distinct(PlanParty.plan_id)).desc())
        )
        return [(role, int(count)) for role, count in rows]
