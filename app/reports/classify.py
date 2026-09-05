"""
Telling a service provider apart from an investment.

A plan's Form 5500 names everything the money touches. Schedule D alone lists
every collective trust and separate account the plan holds, and Schedule C
lists whoever was paid. Reporting all of that as "the 401(k) provider" is the
mistake this module exists to prevent: BlackRock managing a fund inside a plan
is not the firm a participant rings about their balance.

Two filters, because either alone lets something through:

* **By role.** Only a recordkeeper is the plan's provider. An investment
  manager, an investment vehicle and the plan's own trust are not, however
  large the name on them.
* **By name.** Roles are inferred from filed fields, and filers put funds in
  the wrong box often enough to matter. A name that reads as a fund is treated
  as one whatever role it arrived under.

Nothing here guesses upward. When no recordkeeper was filed the answer is that
none was filed, never the biggest name on the schedule.
"""

from __future__ import annotations

import re

from app.core.constants import ConfidenceLevel, ProviderRole

#: The one role that answers "who is the 401(k) provider".
PRIMARY_ROLE = ProviderRole.RECORDKEEPER

#: Worth naming next to the recordkeeper, because they hold or run the plan.
SUPPORTING_ROLES: tuple[str, ...] = (
    ProviderRole.TRUSTEE,
    ProviderRole.CUSTODIAN,
    ProviderRole.THIRD_PARTY_ADMIN,
    ProviderRole.ADMINISTRATOR,
    ProviderRole.INSURER,
    ProviderRole.POOLED_PLAN_PROVIDER,
)

#: Never a service provider, whatever the filing called it.
INVESTMENT_ROLES: frozenset[str] = frozenset(
    {
        ProviderRole.INVESTMENT_VEHICLE,
        ProviderRole.TRUST,
        ProviderRole.PAYOR,
    }
)

#: An investment professional, which is not the same as the plan's provider.
ADVISORY_ROLES: frozenset[str] = frozenset(
    {
        ProviderRole.INVESTMENT_MANAGER,
        ProviderRole.INVESTMENT_ADVISOR,
        ProviderRole.BROKER,
    }
)

#: Advisers to the plan rather than holders of it.
PROFESSIONAL_ROLES: frozenset[str] = frozenset(
    {
        ProviderRole.ACCOUNTANT,
        ProviderRole.ACTUARY,
        ProviderRole.ATTORNEY,
        ProviderRole.CONSULTANT,
        ProviderRole.PREPARER,
        ProviderRole.TERMINATED_ACCOUNTANT,
    }
)

#: Schedule C service code 15 is recordkeeping, filed against the firm doing it.
RECORDKEEPING_SERVICE_CODES: frozenset[str] = frozenset({"15"})

#: Phrases that make a name an investment rather than an organisation. Kept
#: specific: "TRUST" alone would catch Matrix Trust Company, a real trustee.
_VEHICLE_PHRASES: tuple[str, ...] = (
    "COLLECTIVE INVESTMENT TRUST",
    "COLLECTIVE INVESTMENT FUND",
    "COLLECTIVE TRUST",
    "COMMINGLED FUND",
    "COMMINGLED TRUST",
    "POOLED SEPARATE ACCOUNT",
    "SEPARATE ACCOUNT",
    "TARGET DATE",
    "TARGET RETIREMENT",
    "TARGET BENEFIT FUND",
    "INDEX FUND",
    "MONEY MARKET",
    "STABLE VALUE",
    "GUARANTEED INCOME FUND",
    "LIFECYCLE",
    "LIFEPATH",
    "LIFESTRATEGY",
    "FREEDOM FUND",
    "GROWTH FUND",
    "INCOME FUND",
    "BOND FUND",
    "EQUITY FUND",
    "STOCK FUND",
    "BALANCED FUND",
    "MUTUAL FUND",
    "EXCHANGE TRADED",
    "MASTER TRUST INVESTMENT",
    "INVESTMENT PORTFOLIO",
    "UNIT TRUST",
)

#: Suffixes that only an investment carries.
_VEHICLE_SUFFIXES: tuple[str, ...] = (
    " FUND",
    " FUNDS",
    " PORTFOLIO",
    " ETF",
    " CIT",
    " LP FUND",
)

#: A four-digit year in a name is a target-date vintage, not a company.
_VINTAGE = re.compile(r"\b(19|20)\d{2}\b")

#: Endings that mark a real organisation, so a vintage inside them is a red
#: herring rather than a fund.
_ORGANISATION_TAIL = re.compile(
    r"\b(TRUST COMPANY|TRUST CO|BANK|BANK NA|COMPANY|CORP|CORPORATION|INC|LLC|LLP|"
    r"PLC|LTD|GROUP|ASSOCIATES|PARTNERS|SERVICES|SOLUTIONS|ADVISORS|ADVISERS|"
    r"INSURANCE|ASSURANCE|NATIONAL ASSOCIATION|NA)\.?$"
)


def _tidy(name: str | None) -> str:
    return re.sub(r"[^A-Z0-9 ]+", " ", (name or "").upper()).strip()


def is_investment_vehicle(name: str | None, role: str | None = None) -> bool:
    """
    Whether this is a fund or an account rather than a firm to contact.

    Checked by name as well as by role, because a filer can put a collective
    trust in the trustee box and a report that trusted the role alone would
    print it as the plan's trustee.
    """

    if role is not None and str(role) in INVESTMENT_ROLES:
        return True

    text = _tidy(name)
    if not text:
        return False

    if any(phrase in text for phrase in _VEHICLE_PHRASES):
        return True

    if any(text.endswith(suffix.strip()) for suffix in (" FUND", " FUNDS", " PORTFOLIO", " ETF")):
        return True

    if any(text.endswith(suffix) for suffix in _VEHICLE_SUFFIXES):
        return True

    # A vintage year in something that does not end like a company is a fund:
    # "FREEDOM 2045" is, "JOHN HANCOCK LIFE INSURANCE COMPANY USA" is not.
    return bool(_VINTAGE.search(text)) and not _ORGANISATION_TAIL.search(text)


def is_service_provider(name: str | None, role: str | None) -> bool:
    """Whether this belongs in a report about who services the plan."""

    return not is_investment_vehicle(name, role)


def is_supporting(role: str | None) -> bool:
    return str(role) in SUPPORTING_ROLES


def recordkeeper_confidence(
    service_codes: tuple[str, ...] | list[str] | None,
    schedule_code: str | None,
    filed_confidence: str | None,
) -> str:
    """
    How firmly this firm is the recordkeeper.

    HIGH is reserved for a filing that says so: Schedule C service code 15 is
    recordkeeping, reported against the firm performing it. Anything softer
    stays MEDIUM so a reader can see the difference.
    """

    codes = {str(code) for code in (service_codes or ())}

    if codes & RECORDKEEPING_SERVICE_CODES:
        return ConfidenceLevel.HIGH

    if filed_confidence == ConfidenceLevel.HIGH and schedule_code:
        return ConfidenceLevel.MEDIUM

    return ConfidenceLevel.LOW


def describe_role(role: str | None) -> str:
    return str(role or "").replace("_", " ").title()
