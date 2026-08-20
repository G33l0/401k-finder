"""
Who serviced a plan, and in which years.

The filings record one row per firm per role per year, which is the right shape
for an audit trail and the wrong shape for a person asking "who do I call about
the money I left at this job in 2014?". This folds those rows into one line per
firm and role, carrying the years it covered, so a career-long answer fits on
a single row.

Roles are ordered by who actually holds the money. A recordkeeper or trustee
can look somebody up; the plan's auditor cannot.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from app.core.constants import ROLE_PRIORITY, ProviderRole, year_span
from app.providers.directory import Contact, contact_for

#: Roles that hold or administer the money, so worth contacting about a balance.
ASSET_HOLDING_ROLES: frozenset[str] = frozenset(
    {
        ProviderRole.RECORDKEEPER,
        ProviderRole.TRUSTEE,
        ProviderRole.CUSTODIAN,
        ProviderRole.INSURER,
        ProviderRole.THIRD_PARTY_ADMIN,
        ProviderRole.ADMINISTRATOR,
        ProviderRole.POOLED_PLAN_PROVIDER,
    }
)

_RANK = {role: index for index, role in enumerate(ROLE_PRIORITY)}


@dataclass(slots=True)
class ServiceProvider:
    """One firm in one role, across every year it was filed for this plan."""

    provider_id: int
    name: str
    role: str

    years: tuple[int, ...] = ()
    service_codes: tuple[str, ...] = ()
    schedule_codes: tuple[str, ...] = ()
    confidence: str | None = None

    contact: Contact | None = None

    @property
    def role_label(self) -> str:
        return self.role.replace("_", " ").title()

    @property
    def span(self) -> str:
        if not self.years:
            return "?"
        return year_span(self.years[0], self.years[-1])

    @property
    def holds_money(self) -> bool:
        return self.role in ASSET_HOLDING_ROLES

    @property
    def first_year(self) -> int | None:
        return self.years[0] if self.years else None

    @property
    def last_year(self) -> int | None:
        return self.years[-1] if self.years else None

    def covers(self, year: int) -> bool:
        return year in self.years

    def overlaps(self, start: int | None, end: int | None) -> bool:
        """
        Whether this engagement covers any part of a span of employment.

        A missing bound is open, not the firm's own first or last year. Someone
        who knows only that they left in 2015 must not be shown a firm that
        arrived in 2016.
        """

        if not self.years:
            return False

        low, high = start, end
        if low is not None and high is not None and low > high:
            low, high = high, low

        return any(
            (low is None or year >= low) and (high is None or year <= high)
            for year in self.years
        )

    def summary(self) -> str:
        return f"{self.name} ({self.span})"


@dataclass(slots=True)
class ServicingHistory:
    """Every firm that served one plan, best contact first."""

    providers: list[ServiceProvider] = field(default_factory=list)

    def __iter__(self):
        return iter(self.providers)

    def __len__(self) -> int:
        return len(self.providers)

    @property
    def holders(self) -> list[ServiceProvider]:
        return [item for item in self.providers if item.holds_money]

    @property
    def years(self) -> tuple[int, ...]:
        seen: set[int] = set()
        for item in self.providers:
            seen.update(item.years)
        return tuple(sorted(seen))

    def for_year(self, year: int) -> list[ServiceProvider]:
        return [item for item in self.providers if item.covers(year)]

    def best_contact(self) -> ServiceProvider | None:
        """The firm most likely to be able to look a participant up."""

        for item in self.providers:
            if item.holds_money:
                return item
        return self.providers[0] if self.providers else None

    def column_text(self, limit: int = 3) -> str:
        """A one-line summary for a results table."""

        if not self.providers:
            return ""

        ranked = self.holders or self.providers
        shown = [item.summary() for item in ranked[:limit]]
        remaining = len(ranked) - len(shown)

        if remaining > 0:
            shown.append(f"+{remaining} more")

        return ", ".join(shown)


def _sort_key(item: ServiceProvider) -> tuple:
    """Money-holders first, then the most recent engagement, then the name."""

    return (
        _RANK.get(item.role, len(_RANK)),
        -(item.last_year or 0),
        item.name.lower(),
    )


def servicing_history(parties: Iterable) -> ServicingHistory:  # noqa: ANN001
    """
    Fold per-year engagement rows into one entry per firm and role.

    Takes anything with provider_id, display_name, role, form_year,
    service_codes, schedule_code and confidence, which is what both
    PartyResult and PlanParty provide.
    """

    grouped: dict[tuple[int, str], ServiceProvider] = {}
    years: dict[tuple[int, str], set[int]] = {}
    codes: dict[tuple[int, str], set[str]] = {}
    schedules: dict[tuple[int, str], set[str]] = {}

    for party in parties:
        name = getattr(party, "display_name", None) or getattr(party, "provider_name", "")
        if not name:
            continue

        key = (getattr(party, "provider_id", 0), str(party.role))

        entry = grouped.get(key)
        if entry is None:
            entry = ServiceProvider(
                provider_id=key[0],
                name=name,
                role=key[1],
                confidence=getattr(party, "confidence", None),
            )
            grouped[key] = entry
            years[key] = set()
            codes[key] = set()
            schedules[key] = set()

        year = getattr(party, "form_year", None)
        if isinstance(year, int):
            years[key].add(year)

        for code in getattr(party, "service_codes", ()) or ():
            codes[key].add(str(code))

        schedule = getattr(party, "schedule_code", None)
        if schedule:
            schedules[key].add(str(schedule))

        # Keep the strongest evidence seen for this engagement.
        if _stronger(getattr(party, "confidence", None), entry.confidence):
            entry.confidence = getattr(party, "confidence", None)

    for key, entry in grouped.items():
        entry.years = tuple(sorted(years[key]))
        entry.service_codes = tuple(sorted(codes[key]))
        entry.schedule_codes = tuple(sorted(schedules[key]))
        entry.contact = contact_for(entry.name)

    ordered = sorted(grouped.values(), key=_sort_key)
    return ServicingHistory(providers=ordered)


_CONFIDENCE_RANK = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _stronger(candidate: str | None, current: str | None) -> bool:
    return _CONFIDENCE_RANK.get(candidate or "", 0) > _CONFIDENCE_RANK.get(current or "", 0)
