from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import configure_logging
from app.database.models import (
    Evidence,
    Filing,
    Plan,
    PlanParty,
    Provider,
    ScheduleRecord,
)
from app.dol.csv_reader import read_csv_rows
from app.dol.filing_parser import (
    extract_identity,
    infer_schedule_code,
)
from app.dol.provider_extractor import (
    extract_provider_candidates,
)
from app.dol.schedules.registry import ScheduleRegistry
from app.dol.schedules.normalizer import normalize_column_name


logger = configure_logging()


def normalize_provider_name(value: str) -> str:
    normalized = normalize_column_name(value)
    return normalized.replace("_", " ").strip()


def build_record_key(
    form_year: int,
    schedule_code: str,
    row: dict[str, Any],
) -> str:
    relevant = "|".join(
        f"{normalize_column_name(key)}="
        f"{str(value).strip()}"
        for key, value in sorted(row.items())
        if value is not None
    )

    payload = (
        f"{form_year}|"
        f"{schedule_code.upper()}|"
        f"{relevant}"
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


class DOLImporter:

    def __init__(
        self,
        session: Session,
        registry: ScheduleRegistry,
    ) -> None:
        self.session = session
        self.registry = registry

    def import_csv(
        self,
        path: Path,
        form_year: int,
        schedule_code: str | None = None,
        dataset_name: str = "unknown",
    ) -> int:

        if not 2009 <= form_year <= 2025:
            raise ValueError(
                "Form 5500 year must be between 2009 and 2025."
            )

        inferred_code = (
            schedule_code
            or infer_schedule_code(path.name)
            or "FORM5500"
        ).upper()

        definition = self.registry.get(
            form_year,
            inferred_code,
        )

        if definition is not None:
            logger.info(
                "Using schema for %s Schedule %s",
                form_year,
                inferred_code,
            )

        processed = 0

        for row_number, row in read_csv_rows(path):
            self._import_row(
                row=row,
                row_number=row_number,
                source_file=str(path),
                form_year=form_year,
                schedule_code=inferred_code,
                dataset_name=dataset_name,
            )
            processed += 1

        self.session.commit()

        logger.info(
            "Imported %s rows from %s",
            processed,
            path,
        )

        return processed

    def _find_or_create_plan(
        self,
        identity: dict[str, str | None],
        form_year: int,
    ) -> Plan:

        plan_number = identity.get("plan_number")
        sponsor_ein = identity.get("sponsor_ein")
        plan_name = identity.get("plan_name")
        sponsor_name = identity.get("sponsor_name")

        if sponsor_ein and plan_number:
            query = select(Plan).where(
                Plan.sponsor_ein == sponsor_ein,
                Plan.plan_number == plan_number,
            )
        else:
            query = select(Plan).where(
                Plan.plan_name == (
                    plan_name or "UNKNOWN PLAN"
                ),
                Plan.sponsor_name == sponsor_name,
            )

        plan = self.session.execute(
            query.limit(1)
        ).scalar_one_or_none()

        if plan is None:
            plan = Plan(
                plan_number=plan_number,
                plan_name=plan_name or "UNKNOWN PLAN",
                sponsor_name=sponsor_name,
                sponsor_ein=sponsor_ein,
                sponsor_city=identity.get("sponsor_city"),
                sponsor_state=identity.get("sponsor_state"),
                sponsor_zip=identity.get("sponsor_zip"),
                first_year=form_year,
                last_year=form_year,
            )

            self.session.add(plan)
            self.session.flush()

        else:
            if plan.first_year is None:
                plan.first_year = form_year
            else:
                plan.first_year = min(
                    plan.first_year,
                    form_year,
                )

            if plan.last_year is None:
                plan.last_year = form_year
            else:
                plan.last_year = max(
                    plan.last_year,
                    form_year,
                )

        return plan

    def _find_or_create_filing(
        self,
        plan: Plan,
        identity: dict[str, str | None],
        form_year: int,
        source_file: str,
        dataset_name: str,
    ) -> Filing:

        filing_id = identity.get("filing_id")

        if filing_id:
            filing = self.session.execute(
                select(Filing).where(
                    Filing.form_year == form_year,
                    Filing.filing_id == filing_id,
                )
            ).scalar_one_or_none()

            if filing:
                return filing

        filing = Filing(
            plan_id=plan.id,
            form_year=form_year,
            filing_id=filing_id,
            filing_type=identity.get("filing_type"),
            filing_status=identity.get("filing_status"),
            filing_received_date=identity.get(
                "filing_received_date"
            ),
            source_dataset=dataset_name,
            source_file=source_file,
        )

        self.session.add(filing)
        self.session.flush()

        return filing

    def _import_row(
        self,
        row: dict[str, Any],
        row_number: int,
        source_file: str,
        form_year: int,
        schedule_code: str,
        dataset_name: str,
    ) -> None:

        identity = extract_identity(row)

        plan = self._find_or_create_plan(
            identity,
            form_year,
        )

        filing = self._find_or_create_filing(
            plan,
            identity,
            form_year,
            source_file,
            dataset_name,
        )

        record_key = build_record_key(
            form_year,
            schedule_code,
            row,
        )

        existing = self.session.execute(
            select(ScheduleRecord).where(
                ScheduleRecord.form_year == form_year,
                ScheduleRecord.schedule_code == schedule_code,
                ScheduleRecord.record_key == record_key,
            )
        ).scalar_one_or_none()

        if existing:
            return

        schedule_record = ScheduleRecord(
            plan_id=plan.id,
            filing_id=filing.id,
            form_year=form_year,
            schedule_code=schedule_code,
            source_file=source_file,
            source_row=row_number,
            record_key=record_key,
            raw_data=dict(row),
        )

        self.session.add(schedule_record)

        candidates = extract_provider_candidates(row)

        for candidate in candidates:
            provider = self._find_or_create_provider(
                candidate.name
            )

            existing_party = self.session.execute(
                select(PlanParty).where(
                    PlanParty.plan_id == plan.id,
                    PlanParty.provider_id == provider.id,
                    PlanParty.form_year == form_year,
                    PlanParty.schedule_code == schedule_code,
                    PlanParty.role == candidate.role,
                )
            ).scalar_one_or_none()

            if existing_party is None:
                self.session.add(
                    PlanParty(
                        plan_id=plan.id,
                        provider_id=provider.id,
                        role=candidate.role,
                        role_detail=candidate.reason,
                        form_year=form_year,
                        schedule_code=schedule_code,
                        source_filing_id=identity.get(
                            "filing_id"
                        ),
                        confidence=candidate.confidence,
                    )
                )

            self.session.add(
                Evidence(
                    plan_id=plan.id,
                    filing_id=filing.id,
                    form_year=form_year,
                    source_type="DOL_SCHEDULE",
                    schedule_code=schedule_code,
                    source_file=source_file,
                    source_row=row_number,
                    field_name=candidate.source_field,
                    field_value=candidate.name,
                    source_reference=identity.get(
                        "filing_id"
                    ),
                    notes=candidate.reason,
                    confidence=candidate.confidence,
                )
            )

    def _find_or_create_provider(
        self,
        name: str,
    ) -> Provider:

        normalized = normalize_provider_name(name)

        provider = self.session.execute(
            select(Provider).where(
                Provider.normalized_name == normalized
            )
        ).scalar_one_or_none()

        if provider:
            return provider

        provider = Provider(
            name=name,
            normalized_name=normalized,
        )

        self.session.add(provider)
        self.session.flush()

        return provider


def import_dataset(
    session: Session,
    registry: ScheduleRegistry,
    directory: Path,
    form_year: int,
    dataset_name: str = "unknown",
    schedule_code: str | None = None,
) -> int:

    if not directory.exists():
        raise FileNotFoundError(
            f"Dataset directory does not exist: {directory}"
        )

    csv_files = sorted(
        directory.rglob("*.csv")
    )

    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files found under: {directory}"
        )

    importer = DOLImporter(
        session=session,
        registry=registry,
    )

    total = 0

    for csv_file in csv_files:
        total += importer.import_csv(
            path=csv_file,
            form_year=form_year,
            schedule_code=schedule_code,
            dataset_name=dataset_name,
        )

    return total