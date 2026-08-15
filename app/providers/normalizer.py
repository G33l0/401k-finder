"""
Resolve the many spellings of one firm onto a single provider record.

Across a form year the same recordkeeper appears as "FIDELITY INVESTMENTS
INSTITUTIONAL OPERAT", "Fidelity Investments Institutional Operations Co",
"FIDELITY INVESTMENTS INST. OPS. CO., INC." and dozens of further variants —
Schedule C truncates the name field to 35 characters, which guarantees ragged
spellings for any firm with a long name.

Two mechanisms handle this:

* a **name key** (punctuation folded, legal suffixes dropped) groups exact
  variants cheaply and deterministically during import;
* a **canonical brand table** maps known keys onto a single display name, so
  results group under "Fidelity" rather than under twelve subsidiaries.

Fuzzy matching is deliberately *not* used during import — it is O(n²) against
hundreds of thousands of distinct names and would make a full-year import
impractical. It is offered instead as a search-time affordance in
:mod:`app.providers.matcher`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.constants import ProviderRole
from app.dol.normalizer import normalize_name_key, normalize_text

#: Noise tokens that survive suffix stripping but carry no identity.
_NOISE_TOKENS = frozenset(
    {
        "GROUP",
        "SERVICES",
        "SERVICE",
        "SOLUTIONS",
        "HOLDINGS",
        "AMERICA",
        "AMERICAS",
        "USA",
        "US",
        "NATIONAL",
        "NATIONWIDE",
    }
)


@dataclass(frozen=True, slots=True)
class Brand:
    """A well-known provider and the patterns that identify it."""

    canonical_name: str
    patterns: tuple[str, ...]
    default_role: ProviderRole | None = None


#: Recognised brands, matched against the name key as a prefix or word run.
#: This list makes results readable; it is never required for correctness, and
#: an unrecognised provider is stored under its filed name exactly as reported.
BRANDS: tuple[Brand, ...] = (
    Brand("Fidelity Investments", ("FIDELITY INVESTMENTS", "FIDELITY MANAGEMENT", "FMR "), ProviderRole.RECORDKEEPER),
    Brand("Empower", ("EMPOWER", "GREAT WEST LIFE", "GREAT WEST TRUST", "PRUDENTIAL RETIREMENT"), ProviderRole.RECORDKEEPER),
    Brand("Vanguard", ("VANGUARD",), ProviderRole.RECORDKEEPER),
    Brand("Principal Financial Group", ("PRINCIPAL LIFE", "PRINCIPAL FINANCIAL", "PRINCIPAL TRUST"), ProviderRole.RECORDKEEPER),
    Brand("Voya Financial", ("VOYA", "ING LIFE"), ProviderRole.RECORDKEEPER),
    Brand("TIAA", ("TIAA", "TEACHERS INSURANCE ANNUITY"), ProviderRole.RECORDKEEPER),
    Brand("Charles Schwab", ("CHARLES SCHWAB", "SCHWAB RETIREMENT"), ProviderRole.RECORDKEEPER),
    Brand("T. Rowe Price", ("T ROWE PRICE", "TROWE PRICE"), ProviderRole.RECORDKEEPER),
    Brand("John Hancock", ("JOHN HANCOCK",), ProviderRole.INSURER),
    Brand("Nationwide", ("NATIONWIDE LIFE", "NATIONWIDE TRUST", "NATIONWIDE RETIREMENT"), ProviderRole.INSURER),
    Brand("Transamerica", ("TRANSAMERICA",), ProviderRole.INSURER),
    Brand("Lincoln Financial", ("LINCOLN NATIONAL", "LINCOLN LIFE", "LINCOLN RETIREMENT"), ProviderRole.INSURER),
    Brand("MassMutual", ("MASSMUTUAL", "MASSACHUSETTS MUTUAL"), ProviderRole.INSURER),
    Brand("Securian Financial", ("SECURIAN", "MINNESOTA LIFE"), ProviderRole.INSURER),
    Brand("Ameritas", ("AMERITAS",), ProviderRole.INSURER),
    Brand("Equitable", ("EQUITABLE", "AXA EQUITABLE"), ProviderRole.INSURER),
    Brand("MetLife", ("METLIFE", "METROPOLITAN LIFE"), ProviderRole.INSURER),
    Brand("Guardian Life", ("GUARDIAN INSURANCE", "GUARDIAN LIFE"), ProviderRole.INSURER),
    Brand("Mutual of America", ("MUTUAL OF AMERICA",), ProviderRole.INSURER),
    Brand("Standard Insurance", ("STANDARD INSURANCE", "STANCORP"), ProviderRole.INSURER),
    Brand("American Funds / Capital Group", ("AMERICAN FUNDS", "CAPITAL GROUP", "CAPITAL BANK TRUST"), ProviderRole.RECORDKEEPER),
    Brand("Bank of America / Merrill", ("BANK OF AMERICA", "MERRILL LYNCH", "MERRILL"), ProviderRole.TRUSTEE),
    Brand("Wells Fargo", ("WELLS FARGO",), ProviderRole.TRUSTEE),
    Brand("JPMorgan Chase", ("JPMORGAN", "JP MORGAN", "CHASE BANK"), ProviderRole.TRUSTEE),
    Brand("State Street", ("STATE STREET",), ProviderRole.TRUSTEE),
    Brand("Northern Trust", ("NORTHERN TRUST",), ProviderRole.TRUSTEE),
    Brand("BNY Mellon", ("BNY MELLON", "BANK OF NEW YORK", "MELLON BANK"), ProviderRole.TRUSTEE),
    Brand("Matrix Trust / Broadridge", ("MATRIX TRUST", "MG TRUST", "BROADRIDGE"), ProviderRole.CUSTODIAN),
    Brand("Mid Atlantic Trust", ("MID ATLANTIC TRUST", "MID ATLANTIC CAPITAL"), ProviderRole.CUSTODIAN),
    Brand("Pershing", ("PERSHING",), ProviderRole.CUSTODIAN),
    Brand("Ascensus", ("ASCENSUS",), ProviderRole.RECORDKEEPER),
    Brand("Paychex", ("PAYCHEX",), ProviderRole.RECORDKEEPER),
    Brand("ADP", ("ADP ", "ADP RETIREMENT", "AUTOMATIC DATA PROCESSING"), ProviderRole.RECORDKEEPER),
    Brand("Alight Solutions", ("ALIGHT",), ProviderRole.RECORDKEEPER),
    Brand("Milliman", ("MILLIMAN",), ProviderRole.RECORDKEEPER),
    Brand("Sentinel Benefits", ("SENTINEL BENEFITS", "SENTINEL PENSION"), ProviderRole.THIRD_PARTY_ADMIN),
    Brand("Newport Group", ("NEWPORT GROUP", "NEWPORT RETIREMENT"), ProviderRole.RECORDKEEPER),
    Brand("Guideline", ("GUIDELINE",), ProviderRole.RECORDKEEPER),
    Brand("Betterment", ("BETTERMENT",), ProviderRole.RECORDKEEPER),
    Brand("Human Interest", ("HUMAN INTEREST",), ProviderRole.RECORDKEEPER),
    Brand("Vestwell", ("VESTWELL",), ProviderRole.RECORDKEEPER),
    Brand("July Business Services", ("JULY BUSINESS", "JULY SERVICES"), ProviderRole.THIRD_PARTY_ADMIN),
    Brand("Pentegra", ("PENTEGRA",), ProviderRole.THIRD_PARTY_ADMIN),
    Brand("Edward Jones", ("EDWARD JONES", "EDWARD D JONES"), ProviderRole.BROKER),
    Brand("Raymond James", ("RAYMOND JAMES",), ProviderRole.BROKER),
    Brand("Morgan Stanley", ("MORGAN STANLEY",), ProviderRole.BROKER),
    Brand("UBS", ("UBS FINANCIAL", "UBS SECURITIES"), ProviderRole.BROKER),
    Brand("LPL Financial", ("LPL FINANCIAL",), ProviderRole.BROKER),
    Brand("Deloitte", ("DELOITTE",), ProviderRole.ACCOUNTANT),
    Brand("PwC", ("PRICEWATERHOUSECOOPERS", "PWC ",), ProviderRole.ACCOUNTANT),
    Brand("EY", ("ERNST YOUNG", "ERNST AND YOUNG"), ProviderRole.ACCOUNTANT),
    Brand("KPMG", ("KPMG",), ProviderRole.ACCOUNTANT),
    Brand("RSM", ("RSM US", "MCGLADREY"), ProviderRole.ACCOUNTANT),
    Brand("CliftonLarsonAllen", ("CLIFTONLARSONALLEN", "CLIFTON LARSON ALLEN", "CLA "), ProviderRole.ACCOUNTANT),
    Brand("BDO", ("BDO USA", "BDO SEIDMAN"), ProviderRole.ACCOUNTANT),
    Brand("Aon", ("AON HEWITT", "AON CONSULTING", "HEWITT ASSOCIATES"), ProviderRole.CONSULTANT),
    Brand("Mercer", ("MERCER",), ProviderRole.CONSULTANT),
    Brand("Willis Towers Watson", ("WILLIS TOWERS", "TOWERS WATSON", "WATSON WYATT"), ProviderRole.CONSULTANT),
    Brand("Marsh McLennan", ("MARSH MCLENNAN", "MARSH USA"), ProviderRole.CONSULTANT),
    Brand("BlackRock", ("BLACKROCK",), ProviderRole.INVESTMENT_MANAGER),
    Brand("Invesco", ("INVESCO",), ProviderRole.INVESTMENT_MANAGER),
    Brand("Federated Hermes", ("FEDERATED HERMES", "FEDERATED INVESTORS"), ProviderRole.INVESTMENT_MANAGER),
    Brand("PIMCO", ("PIMCO", "PACIFIC INVESTMENT MANAGEMENT"), ProviderRole.INVESTMENT_MANAGER),
    Brand("Wilmington Trust", ("WILMINGTON TRUST",), ProviderRole.TRUSTEE),
    Brand("Reliance Trust", ("RELIANCE TRUST",), ProviderRole.TRUSTEE),
)


@dataclass(frozen=True, slots=True)
class NormalizedProvider:
    """The identity assigned to a filed provider name."""

    name: str
    name_key: str
    canonical_name: str | None = None
    suggested_role: ProviderRole | None = None

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.name


def _load_seed_brands() -> tuple[Brand, ...]:
    """
    Load extra brands from ``database/seeds/known_providers.json``.

    This lets an installation recognise regional firms the built-in table does
    not know about without editing code. A malformed or missing seed file is
    ignored rather than fatal — a bad seed should never stop the tool starting.
    """

    import json
    from pathlib import Path

    seed = Path(__file__).resolve().parents[2] / "database" / "seeds" / "known_providers.json"

    if not seed.exists():
        return ()

    try:
        document = json.loads(seed.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    loaded: list[Brand] = []

    for entry in document.get("providers", []):
        if not isinstance(entry, dict) or entry.get("enabled") is False:
            continue

        name = entry.get("canonical_name")
        patterns = entry.get("patterns")

        if not name or not isinstance(patterns, list) or not patterns:
            continue

        role = None
        raw_role = entry.get("role")
        if raw_role:
            try:
                role = ProviderRole(raw_role)
            except ValueError:
                role = None

        loaded.append(
            Brand(
                canonical_name=str(name),
                patterns=tuple(str(pattern).strip().upper() for pattern in patterns),
                default_role=role,
            )
        )

    return tuple(loaded)


#: Seed brands are consulted first so an installation can override a built-in
#: mapping it disagrees with.
_ALL_BRANDS: tuple[Brand, ...] = _load_seed_brands() + BRANDS


def _brand_for_key(name_key: str) -> Brand | None:
    padded = f"{name_key} "
    for brand in _ALL_BRANDS:
        for pattern in brand.patterns:
            candidate = pattern.strip()
            if padded.startswith(f"{candidate} ") or f" {candidate} " in padded:
                return brand
    return None


_MULTI_SPACE = re.compile(r"\s+")


def normalize_provider(name: str) -> NormalizedProvider:
    """
    Assign a grouping key and, where recognised, a canonical brand to a name.

    The filed name is preserved verbatim as ``name``; nothing here rewrites what
    the plan actually reported.
    """

    filed = normalize_text(name)
    key = normalize_name_key(filed)

    if not key:
        # Nothing survived normalisation (a name of only punctuation or legal
        # suffixes). Fall back to the filed text so the row is still traceable.
        key = _MULTI_SPACE.sub(" ", filed.upper()).strip()

    brand = _brand_for_key(key)

    return NormalizedProvider(
        name=filed,
        name_key=key,
        canonical_name=brand.canonical_name if brand else None,
        suggested_role=brand.default_role if brand else None,
    )


def strip_noise(name_key: str) -> str:
    """
    Drop generic tokens from a name key, for looser grouping.

    Used by the fuzzy matcher rather than by import, since dropping "SERVICES"
    from "PENSION SERVICES" would over-merge distinct small firms.
    """

    tokens = [token for token in name_key.split() if token not in _NOISE_TOKENS]
    return " ".join(tokens) or name_key


def canonical_names() -> tuple[str, ...]:
    return tuple(sorted({brand.canonical_name for brand in BRANDS}))
