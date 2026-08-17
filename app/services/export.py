"""
Export search results and evidence to files the user can keep.

CSV for spreadsheets, JSON for downstream tooling, and a plain-text evidence
report meant to be read by a person or attached to a file.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_export_dir
from app.core.constants import SOURCE_LABEL
from app.evidence.trail import PlanEvidence
from app.search.engine import PlanResult, ProviderResult

PLAN_COLUMNS = (
    "plan_name",
    "sponsor_name",
    "ein",
    "plan_number",
    "city",
    "state",
    "plan_category",
    "features",
    "benefit_codes",
    "first_year",
    "last_year",
    "participants",
    "total_assets",
    "recordkeeper",
    "trustee_custodian",
    "insurer",
    "administrator",
    "accountant",
)

PROVIDER_COLUMNS = (
    "provider_name",
    "canonical_name",
    "primary_role",
    "state",
    "plan_count",
    "participant_count",
    "assets_under_administration",
)


def _timestamped(prefix: str, suffix: str) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return get_export_dir() / f"{prefix}-{stamp}.{suffix}"


def _role_names(result: PlanResult, *roles: str) -> str:
    """Join the distinct provider names a plan has in the given roles."""

    names: list[str] = []
    for party in result.parties:
        if party.role in roles and party.display_name not in names:
            names.append(party.display_name)
    return "; ".join(names)


def _plan_row(result: PlanResult) -> dict[str, object]:
    return {
        "plan_name": result.plan_name,
        "sponsor_name": result.sponsor_name or "",
        "ein": result.ein or "",
        "plan_number": result.plan_number or "",
        "city": result.city or "",
        "state": result.state or "",
        "plan_category": result.plan_category or "",
        "features": "|".join(result.features),
        "benefit_codes": "|".join(result.benefit_codes),
        "first_year": result.first_year or "",
        "last_year": result.last_year or "",
        "participants": result.participants if result.participants is not None else "",
        "total_assets": (
            f"{result.total_assets:.2f}" if result.total_assets is not None else ""
        ),
        "recordkeeper": _role_names(result, "RECORDKEEPER"),
        "trustee_custodian": _role_names(result, "TRUSTEE", "CUSTODIAN", "TRUST"),
        "insurer": _role_names(result, "INSURER"),
        "administrator": _role_names(result, "ADMINISTRATOR", "THIRD_PARTY_ADMINISTRATOR"),
        "accountant": _role_names(result, "ACCOUNTANT"),
    }


def export_plans_csv(results: list[PlanResult], path: Path | None = None) -> Path:
    """Write plan results as CSV, one row per plan with providers flattened."""

    target = path or _timestamped("plans", "csv")
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PLAN_COLUMNS))
        writer.writeheader()
        for result in results:
            writer.writerow(_plan_row(result))

    return target


def export_plans_json(results: list[PlanResult], path: Path | None = None) -> Path:
    """Write plan results as JSON, keeping every provider engagement intact."""

    target = path or _timestamped("plans", "json")
    target.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": SOURCE_LABEL,
        "plan_count": len(results),
        "plans": [
            {
                "plan_id": result.plan_id,
                "plan_name": result.plan_name,
                "sponsor_name": result.sponsor_name,
                "ein": result.ein,
                "plan_number": result.plan_number,
                "city": result.city,
                "state": result.state,
                "plan_category": result.plan_category,
                "features": list(result.features),
                "benefit_codes": list(result.benefit_codes),
                "first_year": result.first_year,
                "last_year": result.last_year,
                "participants": result.participants,
                "total_assets": result.total_assets,
                "providers": [
                    {
                        "provider_id": party.provider_id,
                        "name": party.display_name,
                        "reported_name": party.reported_name,
                        "role": party.role,
                        "form_year": party.form_year,
                        "schedule": party.schedule_code,
                        "source_field": party.source_field,
                        "service_codes": list(party.service_codes),
                        "direct_compensation": party.direct_compensation,
                        "indirect_compensation": party.indirect_compensation,
                        "confidence": party.confidence,
                    }
                    for party in result.parties
                ],
            }
            for result in results
        ],
    }

    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


def export_providers_csv(results: list[ProviderResult], path: Path | None = None) -> Path:
    target = path or _timestamped("providers", "csv")
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(PROVIDER_COLUMNS))
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "provider_name": result.name,
                    "canonical_name": result.canonical_name or "",
                    "primary_role": result.primary_role or "",
                    "state": result.state or "",
                    "plan_count": result.plan_count,
                    "participant_count": result.participant_count,
                    "assets_under_administration": f"{result.assets_under_administration:.2f}",
                }
            )

    return target


#: One row per plan that changed hands. Ordered so the columns a reader scans
#: first -- who left whom, and how big -- come before the provenance.
CHANGE_COLUMNS: tuple[str, ...] = (
    "plan_name",
    "sponsor_name",
    "ein",
    "plan_number",
    "state",
    "role",
    "change",
    "from_year",
    "to_year",
    "from_provider",
    "to_provider",
    "participants",
    "total_assets",
    "schedule_code",
    "source_field",
)


def export_provider_changes_csv(changes: list, path: Path | None = None) -> Path:
    """Write provider changes as CSV, for a spreadsheet or a CRM import."""

    target = path or _timestamped("provider-changes", "csv")
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CHANGE_COLUMNS))
        writer.writeheader()

        for change in changes:
            writer.writerow(
                {
                    "plan_name": change.plan_name,
                    "sponsor_name": change.sponsor_name or "",
                    "ein": change.ein or "",
                    "plan_number": change.plan_number or "",
                    "state": change.state or "",
                    "role": change.role,
                    "change": change.kind.value,
                    "from_year": change.from_year,
                    "to_year": change.to_year,
                    "from_provider": change.from_provider or "",
                    "to_provider": change.to_provider or "",
                    "participants": change.participants or "",
                    "total_assets": (
                        f"{change.total_assets:.2f}" if change.total_assets else ""
                    ),
                    "schedule_code": change.schedule_code or "",
                    "source_field": change.source_field or "",
                }
            )

    return target


def export_evidence_report(package: PlanEvidence, path: Path | None = None) -> Path:
    """Write a readable evidence report for one plan."""

    target = path or _timestamped(f"evidence-{package.plan_key}", "txt")
    target.parent.mkdir(parents=True, exist_ok=True)

    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "=" * 78,
        "RETIREMENT PLAN PROVIDER EVIDENCE REPORT",
        "=" * 78,
        f"Generated: {generated}",
        f"Source: {SOURCE_LABEL}",
        "",
        package.explain(),
        "",
        "-" * 78,
        "FILINGS ON RECORD",
        "-" * 78,
    ]

    for filing in package.filings:
        lines.append(
            f"  {filing.form_year}  {filing.form_type:8}  ACK_ID {filing.ack_id}  "
            f"participants={filing.total_participants or '-'}  "
            f"assets={filing.total_assets_eoy or '-'}"
        )

    lines += [
        "",
        "-" * 78,
        "VERIFYING THIS REPORT",
        "-" * 78,
        "Every line above cites the dataset, field and row it came from, in the",
        f"{SOURCE_LABEL}.",
        "",
        "The plan is identified by the sponsor EIN and plan number shown above.",
        "That pair is what any administrator, recordkeeper or regulator will ask",
        "for, and is enough to retrieve the original filing from the source.",
        "",
    ]

    target.write_text("\n".join(lines), encoding="utf-8")
    return target
