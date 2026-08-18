"""Fuzzy provider matching, used at search time rather than at import time."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Provider
from app.providers.normalizer import normalize_provider, strip_noise

try:
    from rapidfuzz import fuzz, process

    _HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover - optional dependency
    _HAVE_RAPIDFUZZ = False


@dataclass(slots=True)
class ProviderMatch:
    provider_id: int
    name: str
    canonical_name: str | None
    score: float
    plan_count: int

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.name


def _fallback_score(needle: str, candidate: str) -> float:
    """A cheap containment score used when rapidfuzz is unavailable."""

    if not needle or not candidate:
        return 0.0
    if needle == candidate:
        return 100.0
    if candidate.startswith(needle) or needle.startswith(candidate):
        return 92.0
    if needle in candidate or candidate in needle:
        return 85.0

    needle_tokens = set(needle.split())
    candidate_tokens = set(candidate.split())
    if not needle_tokens or not candidate_tokens:
        return 0.0

    overlap = len(needle_tokens & candidate_tokens)
    return 100.0 * overlap / max(len(needle_tokens), len(candidate_tokens))


def find_similar_providers(
    session: Session,
    name: str,
    limit: int = 10,
    threshold: float = 82.0,
) -> list[ProviderMatch]:
    """Return providers whose names are close to ``name``."""

    identity = normalize_provider(name)
    needle = strip_noise(identity.name_key)

    if not needle:
        return []

    first_token = needle.split()[0]

    candidates = list(
        session.execute(
            select(Provider.id, Provider.name, Provider.name_key, Provider.canonical_name, Provider.plan_count)
            .where(Provider.name_key.like(f"{first_token}%"))
            .order_by(Provider.plan_count.desc())
            .limit(2000)
        )
    )

    if not candidates:
        return []

    keys = [strip_noise(row[2]) for row in candidates]

    if _HAVE_RAPIDFUZZ:
        scored = process.extract(
            needle,
            keys,
            scorer=fuzz.token_set_ratio,
            limit=limit * 3,
            score_cutoff=threshold,
        )
        picked = [(candidates[index], score) for _, score, index in scored]
    else:
        picked = [
            (row, _fallback_score(needle, key))
            for row, key in zip(candidates, keys, strict=True)
        ]
        picked = [item for item in picked if item[1] >= threshold]
        picked.sort(key=lambda item: item[1], reverse=True)

    matches = [
        ProviderMatch(
            provider_id=row[0],
            name=row[1],
            canonical_name=row[3],
            score=float(score),
            plan_count=int(row[4]),
        )
        for row, score in picked
    ]

    matches.sort(key=lambda match: (-match.score, -match.plan_count))
    return matches[:limit]


def expand_provider_ids(session: Session, name: str, threshold: float = 88.0) -> list[int]:
    """Return provider ids to search as one firm."""

    matches = find_similar_providers(session, name, limit=50, threshold=threshold)
    return [match.provider_id for match in matches]


def consolidation_report(
    session: Session,
    min_plans: int = 5,
    threshold: float = 90.0,
    limit: int = 200,
) -> list[tuple[ProviderMatch, list[ProviderMatch]]]:
    """Find provider records that probably describe the same firm."""

    anchors = list(
        session.execute(
            select(Provider.id, Provider.name, Provider.name_key, Provider.canonical_name, Provider.plan_count)
            .where(Provider.plan_count >= min_plans)
            .order_by(Provider.plan_count.desc())
            .limit(limit)
        )
    )

    report: list[tuple[ProviderMatch, list[ProviderMatch]]] = []
    claimed: set[int] = set()

    for row in anchors:
        if row[0] in claimed:
            continue

        anchor = ProviderMatch(row[0], row[1], row[3], 100.0, int(row[4]))
        similar = [
            match
            for match in find_similar_providers(session, row[1], limit=25, threshold=threshold)
            if match.provider_id != row[0] and match.provider_id not in claimed
        ]

        if not similar:
            continue

        claimed.add(row[0])
        claimed.update(match.provider_id for match in similar)
        report.append((anchor, similar))

    return report
