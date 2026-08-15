"""
Query objects for plan and provider search.

Keeping the query as a value object means the CLI, the UI and the tests all
build searches the same way, and a saved search is just a serialisable record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

from app.core.constants import PlanCategory, PlanFeature
from app.dol.normalizer import normalize_ein, normalize_plan_number, normalize_state

#: Anything that is nine digits once punctuation is removed is treated as an EIN.
_EIN_PATTERN = re.compile(r"^\s*\d{2}\s*-?\s*\d{7}\s*$")
#: 12-3456789-001 and 123456789/001 both address one plan directly.
_PLAN_KEY_PATTERN = re.compile(r"^\s*(\d{2}-?\d{7})\s*[/\- ]\s*(\d{1,3})\s*$")


class SortOrder(StrEnum):
    RELEVANCE = "relevance"
    PLAN_NAME = "plan_name"
    SPONSOR_NAME = "sponsor_name"
    PARTICIPANTS = "participants"
    ASSETS = "assets"
    YEAR = "year"


@dataclass(slots=True)
class PlanQuery:
    """A plan search. Every field is optional; an empty query browses."""

    text: str = ""

    ein: str | None = None
    plan_number: str | None = None
    state: str | None = None
    city: str | None = None

    form_years: tuple[int, ...] = ()
    categories: tuple[str, ...] = ()
    features: tuple[str, ...] = ()

    provider_name: str | None = None
    provider_id: int | None = None
    roles: tuple[str, ...] = ()

    min_participants: int | None = None
    max_participants: int | None = None
    min_assets: float | None = None
    max_assets: float | None = None

    retirement_only: bool = True
    active_only: bool = False

    sort: SortOrder = SortOrder.RELEVANCE
    limit: int = 200
    offset: int = 0

    def is_empty(self) -> bool:
        return not any(
            (
                self.text.strip(),
                self.ein,
                self.plan_number,
                self.state,
                self.city,
                self.categories,
                self.features,
                self.provider_name,
                self.provider_id,
                self.roles,
                self.min_participants,
                self.max_participants,
                self.min_assets,
                self.max_assets,
            )
        )

    @classmethod
    def parse(cls, text: str, **overrides) -> PlanQuery:
        """
        Build a query from a single search box.

        Typing an EIN, or an EIN and plan number, addresses a plan directly
        rather than running a text search, which is what someone holding a
        statement or a plan document will do first. A trailing two-letter state
        token (``acme retirement TX``) is lifted into a state filter.
        """

        raw = text.strip()

        # An explicitly supplied filter always wins over one inferred from the
        # text, so `--state NY` is not silently overridden by a trailing token.
        def build(**inferred) -> PlanQuery:
            merged = {**inferred}
            merged.update({key: value for key, value in overrides.items() if value is not None})
            return cls(**merged)

        plan_key = _PLAN_KEY_PATTERN.match(raw)
        if plan_key:
            return build(
                ein=normalize_ein(plan_key.group(1)),
                plan_number=normalize_plan_number(plan_key.group(2)),
            )

        if _EIN_PATTERN.match(raw):
            return build(ein=normalize_ein(raw))

        tokens = raw.split()
        state = None
        if len(tokens) > 1:
            candidate = normalize_state(tokens[-1])
            if candidate:
                state = candidate
                tokens = tokens[:-1]

        return build(text=" ".join(tokens), state=state)


@dataclass(slots=True)
class ProviderQuery:
    """A provider search."""

    text: str = ""
    role: str | None = None
    state: str | None = None
    min_plans: int | None = None
    canonical_only: bool = False

    sort: str = "plans"
    limit: int = 200
    offset: int = 0


@dataclass(slots=True)
class QueryOptions:
    """Presentation choices that do not change which rows match."""

    include_parties: bool = True
    include_filings: bool = False
    include_evidence: bool = False
    max_parties: int = 25
    roles_of_interest: tuple[str, ...] = field(default_factory=tuple)


def known_categories() -> tuple[str, ...]:
    return tuple(category.value for category in PlanCategory)


def known_features() -> tuple[str, ...]:
    return tuple(feature.value for feature in PlanFeature)
