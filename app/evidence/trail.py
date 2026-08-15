"""
Assemble the evidence behind a result.

Every provider attribution the importer makes writes an Evidence row naming the
dataset, file, row and field it came from. This module turns those rows into a
readable trail, so a user can answer "how do you know Fidelity is the
recordkeeper for this plan" without opening the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.codes import describe_service_code
from app.core.constants import DOL_FILE_BASE_URL, EFAST_FILING_URL
from app.database.models import Evidence, Filing, Plan, PlanParty, Provider


@dataclass(slots=True)
class EvidenceItem:
    """One traceable fact."""

    form_year: int
    ack_id: str | None
    dataset: str | None
    schedule_code: str | None
    field_name: str | None
    field_value: str | None
    source_file: str | None
    source_row: int | None
    notes: str | None
    confidence: str | None

    def citation(self) -> str:
        """A one-line citation naming exactly where this came from."""

        parts: list[str] = []

        if self.dataset and self.form_year:
            parts.append(f"{self.dataset} ({self.form_year})")
        if self.field_name:
            parts.append(f"field {self.field_name}")
        if self.source_row:
            parts.append(f"row {self.source_row}")
        if self.ack_id:
            parts.append(f"ACK_ID {self.ack_id}")

        return ", ".join(parts) or "unknown source"

    def source_url(self) -> str | None:
        """The DOL archive this evidence came from, when it can be derived."""

        if not self.dataset or not self.form_year:
            return None

        return (
            f"{DOL_FILE_BASE_URL}/{self.form_year}/Latest/"
            f"{self.dataset}_{self.form_year}_Latest.zip"
        )


@dataclass(slots=True)
class ProviderFinding:
    """One provider engagement, with everything supporting it."""

    provider_id: int
    provider_name: str
    canonical_name: str | None
    role: str
    reported_name: str | None
    reported_ein: str | None
    form_year: int
    schedule_code: str | None
    confidence: str | None
    service_codes: tuple[str, ...] = ()
    direct_compensation: float | None = None
    indirect_compensation: float | None = None
    evidence: list[EvidenceItem] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        return self.canonical_name or self.provider_name

    def service_descriptions(self) -> list[str]:
        return [describe_service_code(code) for code in self.service_codes]

    def explain(self) -> str:
        """A plain-language account of why this provider is attached to the plan."""

        lines = [
            f"{self.display_name} — {self.role.replace('_', ' ').title()} "
            f"({self.form_year}, confidence {self.confidence or 'unknown'})"
        ]

        if self.reported_name and self.reported_name != self.display_name:
            lines.append(f"  Reported on the filing as: {self.reported_name}")

        if self.reported_ein:
            lines.append(f"  EIN reported: {self.reported_ein}")

        for description in self.service_descriptions():
            lines.append(f"  Service reported: {description}")

        if self.direct_compensation:
            lines.append(f"  Direct compensation: ${self.direct_compensation:,.2f}")
        if self.indirect_compensation:
            lines.append(f"  Indirect compensation: ${self.indirect_compensation:,.2f}")

        for item in self.evidence:
            lines.append(f"  Source: {item.citation()}")
            if item.notes:
                lines.append(f"    {item.notes}")

        return "\n".join(lines)


@dataclass(slots=True)
class PlanEvidence:
    """The complete evidence package for one plan."""

    plan_id: int
    plan_name: str
    sponsor_name: str | None
    ein: str | None
    plan_number: str | None

    findings: list[ProviderFinding] = field(default_factory=list)
    filings: list[Filing] = field(default_factory=list)

    @property
    def plan_key(self) -> str:
        return f"{self.ein or '?'}-{self.plan_number or '?'}"

    def efast_search_url(self) -> str:
        """Where a user can pull the original filing images from EBSA."""

        return EFAST_FILING_URL

    def findings_by_role(self) -> dict[str, list[ProviderFinding]]:
        grouped: dict[str, list[ProviderFinding]] = {}
        for finding in self.findings:
            grouped.setdefault(finding.role, []).append(finding)
        return grouped

    def latest_year(self) -> int | None:
        years = [finding.form_year for finding in self.findings]
        return max(years) if years else None

    def explain(self) -> str:
        header = [
            f"{self.plan_name}",
            f"Sponsor: {self.sponsor_name or 'unknown'}",
            f"Plan key: EIN {self.plan_key}",
            "",
        ]

        if not self.findings:
            header.append(
                "No service providers were identified for this plan. The filings "
                "on record may not name one, or the schedules that carry provider "
                "information may not have been imported for these years."
            )
            return "\n".join(header)

        header.append("Providers identified:")
        header.append("")

        return "\n".join(header + [finding.explain() for finding in self.findings])


def build_plan_evidence(
    session: Session,
    plan_id: int,
    form_years: tuple[int, ...] = (),
    roles: tuple[str, ...] = (),
) -> PlanEvidence | None:
    """
    Collect every provider finding for a plan, each with its supporting evidence.
    """

    plan = session.get(Plan, plan_id)
    if plan is None:
        return None

    package = PlanEvidence(
        plan_id=plan.id,
        plan_name=plan.plan_name,
        sponsor_name=plan.sponsor_name,
        ein=plan.ein,
        plan_number=plan.plan_number,
    )

    party_statement = (
        select(PlanParty, Provider)
        .join(Provider, Provider.id == PlanParty.provider_id)
        .where(PlanParty.plan_id == plan_id)
        .order_by(PlanParty.form_year.desc(), PlanParty.role)
    )

    if form_years:
        party_statement = party_statement.where(PlanParty.form_year.in_(form_years))
    if roles:
        party_statement = party_statement.where(PlanParty.role.in_(roles))

    parties = list(session.execute(party_statement))

    # Evidence is matched to a finding by (year, schedule, field, value) because
    # the importer writes both from the same candidate.
    evidence_statement = select(Evidence).where(Evidence.plan_id == plan_id)
    if form_years:
        evidence_statement = evidence_statement.where(Evidence.form_year.in_(form_years))

    evidence_index: dict[tuple[int, str | None, str | None, str | None], list[Evidence]] = {}
    for row in session.execute(evidence_statement).scalars():
        key = (row.form_year, row.schedule_code, row.field_name, row.field_value)
        evidence_index.setdefault(key, []).append(row)

    for party, provider in parties:
        finding = ProviderFinding(
            provider_id=provider.id,
            provider_name=provider.name,
            canonical_name=provider.canonical_name,
            role=party.role,
            reported_name=party.reported_name,
            reported_ein=party.reported_ein,
            form_year=party.form_year,
            schedule_code=party.schedule_code,
            confidence=party.confidence,
            service_codes=tuple(party.service_code_list()),
            direct_compensation=party.direct_compensation,
            indirect_compensation=party.indirect_compensation,
        )

        key = (party.form_year, party.schedule_code, party.source_field, party.reported_name)
        for row in evidence_index.get(key, []):
            finding.evidence.append(
                EvidenceItem(
                    form_year=row.form_year,
                    ack_id=row.ack_id,
                    dataset=row.dataset,
                    schedule_code=row.schedule_code,
                    field_name=row.field_name,
                    field_value=row.field_value,
                    source_file=row.source_file,
                    source_row=row.source_row,
                    notes=row.notes,
                    confidence=row.confidence,
                )
            )

        package.findings.append(finding)

    filings_statement = select(Filing).where(Filing.plan_id == plan_id)
    if form_years:
        filings_statement = filings_statement.where(Filing.form_year.in_(form_years))

    package.filings = list(
        session.execute(filings_statement.order_by(Filing.form_year.desc())).scalars()
    )

    return package
