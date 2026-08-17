"""
Import DOL Form 5500 files into the local database.

The import runs in two passes because that is how the data is actually shaped:

    Pass 1  Filing datasets (F_5500, F_5500_SF, F_SCH_DCG) carry plan identity —
            sponsor EIN, plan number, plan name — and create the Plan and Filing
            rows. Every filing is keyed by its DOL ACK_ID.

    Pass 2  Schedule datasets carry no plan identity at all; a Schedule H row is
            just an ACK_ID and a hundred dollar amounts. They are joined to the
            filings from pass 1 by ACK_ID.

Running pass 2 without pass 1 would leave every schedule row unattached, which
is the failure the previous single-pass importer produced: it read plan identity
out of schedule rows that do not contain any, so every schedule row in a file
collapsed onto one placeholder "UNKNOWN PLAN".

Throughput matters here — a single form year is several million rows — so the
importer buffers rows and writes them with SQLAlchemy Core bulk inserts, holding
only the ACK_ID and provider maps in memory.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import insert, select, text, update
from sqlalchemy.orm import Session

from app.core.constants import PlanCategory, PlanFeature
from app.core.exceptions import ImportCancelled
from app.core.logging import get_logger
from app.database.models import (
    Evidence,
    Filing,
    Plan,
    PlanParty,
    PlanTransfer,
    Provider,
    ScheduleRecord,
)
from app.dol.catalog import DATASETS_BY_NAME, DatasetKind
from app.dol.csv_reader import read_csv_rows
from app.dol.filing_parser import (
    FIELD_MAPS,
    ParsedFiling,
    first_value,
    parse_ack_id,
    parse_filing_row,
    parse_row_order,
)
from app.dol.normalizer import normalize_indicator, parse_money
from app.dol.provider_extractor import ProviderCandidate, extract_providers
from app.dol.transfers import DATASET as TRANSFER_DATASET
from app.dol.transfers import extract_transfer
from app.plans.successor import resolve_transfers
from app.providers.normalizer import normalize_provider

logger = get_logger(__name__)

#: Called with (rows_processed, rows_total_estimate, message).
ProgressCallback = Callable[[int, int, str], None]

#: Called before each batch; returning True aborts the import.
CancelCallback = Callable[[], bool]


@dataclass(slots=True)
class ImportStats:
    """What one dataset import did."""

    dataset: str = ""
    form_year: int = 0

    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0

    plans_created: int = 0
    plans_updated: int = 0
    filings_created: int = 0
    schedule_rows: int = 0

    providers_created: int = 0
    parties_created: int = 0
    evidence_created: int = 0

    unmatched_ack_ids: int = 0
    transfers_recorded: int = 0
    errors: list[str] = field(default_factory=list)

    elapsed_seconds: float = 0.0

    @property
    def rows_per_second(self) -> float:
        return self.rows_read / self.elapsed_seconds if self.elapsed_seconds > 0 else 0.0

    def merge(self, other: ImportStats) -> None:
        self.rows_read += other.rows_read
        self.rows_imported += other.rows_imported
        self.rows_skipped += other.rows_skipped
        self.plans_created += other.plans_created
        self.plans_updated += other.plans_updated
        self.filings_created += other.filings_created
        self.schedule_rows += other.schedule_rows
        self.providers_created += other.providers_created
        self.parties_created += other.parties_created
        self.evidence_created += other.evidence_created
        self.unmatched_ack_ids += other.unmatched_ack_ids
        self.transfers_recorded += other.transfers_recorded
        self.errors.extend(other.errors)
        self.elapsed_seconds += other.elapsed_seconds

    def summary(self) -> str:
        return (
            f"{self.rows_read:,} rows read, {self.rows_imported:,} imported, "
            f"{self.rows_skipped:,} skipped; {self.plans_created:,} plans, "
            f"{self.filings_created:,} filings, {self.parties_created:,} provider "
            f"engagements, {self.transfers_recorded:,} asset transfers "
            f"in {self.elapsed_seconds:.1f}s "
            f"({self.rows_per_second:,.0f} rows/s)"
        )


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class DOLImporter:
    """
    Imports DOL CSV files into the database.

    One importer instance should be used for a whole form year: it caches the
    plan, filing and provider lookups it builds, so importing ten datasets costs
    one set of lookups rather than ten.
    """

    def __init__(
        self,
        session: Session,
        batch_size: int = 5000,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> None:
        self.session = session
        self.batch_size = max(batch_size, 100)
        self.progress = progress
        self.should_cancel = should_cancel

        # (ein, plan_number) -> plan id
        self._plan_ids: dict[tuple[str | None, str | None], int] = {}
        # ack_id -> (filing id, plan id)
        self._filing_ids: dict[str, tuple[int, int]] = {}
        # provider name key -> provider id
        self._provider_ids: dict[str, int] = {}

        self._caches_loaded = False

    # ------------------------------------------------------------------
    # Lookup caches
    # ------------------------------------------------------------------

    def load_caches(self) -> None:
        """
        Load the identity maps the import needs, once per session.

        Loading these up front turns what would be three SELECTs per row into a
        dictionary lookup, which is the difference between an import that takes
        minutes and one that takes days.
        """

        if self._caches_loaded:
            return

        started = time.perf_counter()

        for plan_id, ein, plan_number in self.session.execute(
            select(Plan.id, Plan.ein, Plan.plan_number)
        ):
            self._plan_ids[(ein, plan_number)] = plan_id

        for filing_id, ack_id, plan_id in self.session.execute(
            select(Filing.id, Filing.ack_id, Filing.plan_id)
        ):
            self._filing_ids[ack_id] = (filing_id, plan_id)

        for provider_id, name_key in self.session.execute(
            select(Provider.id, Provider.name_key)
        ):
            self._provider_ids[name_key] = provider_id

        # Engagements are deliberately not cached. There is one row per
        # plan-provider-role-year-schedule, which across a full form year runs
        # into the millions -- holding them all in a set costs more memory than
        # the rest of the import put together. The table's unique constraint
        # does the same job, enforced by INSERT OR IGNORE at write time.

        self._caches_loaded = True

        logger.info(
            "Loaded caches: %s plans, %s filings, %s providers (%.1fs)",
            len(self._plan_ids),
            len(self._filing_ids),
            len(self._provider_ids),
            time.perf_counter() - started,
        )

    def _check_cancelled(self) -> None:
        if self.should_cancel and self.should_cancel():
            raise ImportCancelled("Import cancelled.")

    def _report(self, done: int, total: int, message: str) -> None:
        if self.progress:
            self.progress(done, total, message)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def import_file(
        self,
        path: Path,
        dataset: str,
        form_year: int,
        release: str = "Latest",
        row_estimate: int = 0,
    ) -> ImportStats:
        """Import one DOL CSV file."""

        dataset = dataset.upper()
        spec = DATASETS_BY_NAME.get(dataset)

        stats = ImportStats(dataset=dataset, form_year=form_year)
        started = time.perf_counter()

        self.load_caches()

        is_filing_dataset = dataset in FIELD_MAPS and (
            spec is None or spec.kind is DatasetKind.FILING
        )

        try:
            if is_filing_dataset:
                self._import_filing_file(path, dataset, form_year, release, stats, row_estimate)
            else:
                self._import_schedule_file(path, dataset, form_year, stats, row_estimate)
        except ImportCancelled:
            self.session.rollback()
            raise
        except Exception as exc:  # noqa: BLE001 - recorded and re-raised by the caller
            self.session.rollback()
            stats.errors.append(f"{type(exc).__name__}: {exc}")
            stats.elapsed_seconds = time.perf_counter() - started
            raise

        stats.elapsed_seconds = time.perf_counter() - started
        logger.info("%s %s: %s", form_year, dataset, stats.summary())
        return stats

    # ------------------------------------------------------------------
    # Pass 1: filing datasets
    # ------------------------------------------------------------------

    def _import_filing_file(
        self,
        path: Path,
        dataset: str,
        form_year: int,
        release: str,
        stats: ImportStats,
        row_estimate: int,
    ) -> None:
        source_file = str(path)

        plan_buffer: list[dict[str, Any]] = []
        filing_buffer: list[dict[str, Any]] = []
        pending_providers: list[tuple[str, list[ProviderCandidate], int, str]] = []

        for row_number, row in read_csv_rows(path):
            stats.rows_read += 1

            if stats.rows_read % self.batch_size == 0:
                self._check_cancelled()
                self._flush_plans(plan_buffer, stats)
                self._flush_filings(filing_buffer, stats)
                self._flush_providers(pending_providers, form_year, source_file, stats)
                self._report(
                    stats.rows_read,
                    row_estimate,
                    f"{dataset}: {stats.rows_read:,} rows",
                )

            parsed = parse_filing_row(row, dataset, form_year)

            if not parsed.ack_id:
                stats.rows_skipped += 1
                continue

            if parsed.ack_id in self._filing_ids:
                # Already imported, e.g. re-running a partially completed year.
                stats.rows_skipped += 1
                continue

            plan_key = parsed.plan_key
            if plan_key[0] is None and plan_key[1] is None:
                # Without an EIN and plan number there is no stable identity to
                # merge this filing onto in later years, so key it by ACK_ID.
                plan_key = (None, f"ACK:{parsed.ack_id[:40]}")

            if plan_key not in self._plan_ids:
                plan_buffer.append(self._plan_values(parsed, plan_key))
            else:
                self._update_plan(self._plan_ids[plan_key], parsed, stats)

            filing_buffer.append((plan_key, self._filing_values(parsed, dataset, release, source_file)))  # type: ignore[arg-type]

            candidates = extract_providers(row, dataset)
            if candidates:
                pending_providers.append((parsed.ack_id, candidates, row_number, dataset))

            stats.rows_imported += 1

        self._check_cancelled()
        self._flush_plans(plan_buffer, stats)
        self._flush_filings(filing_buffer, stats)
        self._flush_providers(pending_providers, form_year, source_file, stats)
        self.session.commit()

        self._report(stats.rows_read, row_estimate or stats.rows_read, f"{dataset}: complete")

    def _plan_values(
        self,
        parsed: ParsedFiling,
        plan_key: tuple[str | None, str | None],
    ) -> dict[str, Any]:
        return {
            "_key": plan_key,
            "ein": plan_key[0],
            "plan_number": plan_key[1],
            "plan_name": parsed.plan_name,
            "sponsor_name": parsed.sponsor_name,
            "sponsor_dba_name": parsed.sponsor_dba_name,
            "sponsor_city": parsed.sponsor_city,
            "sponsor_state": parsed.sponsor_state,
            "sponsor_zip": parsed.sponsor_zip,
            "sponsor_phone": parsed.sponsor_phone,
            "business_code": parsed.business_code,
            "plan_effective_date": parsed.plan_effective_date,
            "plan_category": parsed.plan_category,
            "plan_features": "|".join(parsed.plan_features) or None,
            "benefit_codes": "|".join(parsed.pension_codes + parsed.welfare_codes) or None,
            "is_retirement_plan": parsed.is_retirement_plan,
            "first_year": parsed.form_year,
            "last_year": parsed.form_year,
            "latest_participants": parsed.total_participants,
            "latest_active_participants": parsed.active_participants,
            "latest_total_assets": parsed.total_assets_eoy,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }

    def _filing_values(
        self,
        parsed: ParsedFiling,
        dataset: str,
        release: str,
        source_file: str,
    ) -> dict[str, Any]:
        return {
            "ack_id": parsed.ack_id,
            "form_year": parsed.form_year,
            "form_type": parsed.form_type,
            "plan_name": parsed.plan_name,
            "sponsor_name": parsed.sponsor_name,
            "ein": parsed.ein,
            "plan_number": parsed.plan_number,
            "plan_year_begin": parsed.plan_year_begin,
            "plan_year_end": parsed.plan_year_end,
            "filing_status": parsed.filing_status,
            "date_received": parsed.date_received,
            "is_initial": parsed.is_initial,
            "is_amended": parsed.is_amended,
            "is_final": parsed.is_final,
            "is_short_year": parsed.is_short_year,
            "plan_entity_code": parsed.plan_entity_code,
            "dfe_entity_code": parsed.dfe_entity_code,
            "business_code": parsed.business_code,
            "pension_codes": "|".join(parsed.pension_codes) or None,
            "welfare_codes": "|".join(parsed.welfare_codes) or None,
            "plan_category": parsed.plan_category,
            "plan_features": "|".join(parsed.plan_features) or None,
            "total_participants": parsed.total_participants,
            "active_participants": parsed.active_participants,
            "participants_with_balances": parsed.participants_with_balances,
            "total_assets_boy": parsed.total_assets_boy,
            "total_assets_eoy": parsed.total_assets_eoy,
            "net_assets_eoy": parsed.net_assets_eoy,
            "employer_contributions": parsed.employer_contributions,
            "participant_contributions": parsed.participant_contributions,
            "admin_name": parsed.admin_name,
            "admin_ein": parsed.admin_ein,
            "source_dataset": dataset,
            "source_release": release,
            "source_file": source_file,
            "created_at": _utcnow(),
        }

    def _update_plan(self, plan_id: int, parsed: ParsedFiling, stats: ImportStats) -> None:
        """
        Fold a newer filing's values onto an existing plan.

        Only a filing at least as recent as what the plan already carries may
        overwrite its display fields, so importing 2019 after 2023 does not make
        the plan look stale.
        """

        plan = self.session.get(Plan, plan_id)
        if plan is None:
            return

        year = parsed.form_year
        plan.first_year = min(plan.first_year or year, year)
        is_newer = year >= (plan.last_year or year)
        plan.last_year = max(plan.last_year or year, year)

        if is_newer:
            plan.plan_name = parsed.plan_name
            plan.sponsor_name = parsed.sponsor_name or plan.sponsor_name
            plan.sponsor_dba_name = parsed.sponsor_dba_name or plan.sponsor_dba_name
            plan.sponsor_city = parsed.sponsor_city or plan.sponsor_city
            plan.sponsor_state = parsed.sponsor_state or plan.sponsor_state
            plan.sponsor_zip = parsed.sponsor_zip or plan.sponsor_zip
            plan.sponsor_phone = parsed.sponsor_phone or plan.sponsor_phone
            plan.business_code = parsed.business_code or plan.business_code
            plan.plan_effective_date = parsed.plan_effective_date or plan.plan_effective_date

            if parsed.plan_category != PlanCategory.UNKNOWN:
                plan.plan_category = parsed.plan_category
                plan.is_retirement_plan = parsed.is_retirement_plan

            if parsed.plan_features:
                plan.plan_features = "|".join(parsed.plan_features)
            if parsed.pension_codes or parsed.welfare_codes:
                plan.benefit_codes = "|".join(parsed.pension_codes + parsed.welfare_codes)

            if parsed.total_participants is not None:
                plan.latest_participants = parsed.total_participants
            if parsed.active_participants is not None:
                plan.latest_active_participants = parsed.active_participants
            if parsed.total_assets_eoy is not None:
                plan.latest_total_assets = parsed.total_assets_eoy

        stats.plans_updated += 1

    def _flush_plans(self, buffer: list[dict[str, Any]], stats: ImportStats) -> None:
        if not buffer:
            return

        # A file can name the same plan twice (an original and an amended
        # filing); keep the first and let the later one update it.
        unique: dict[tuple[str | None, str | None], dict[str, Any]] = {}
        for values in buffer:
            unique.setdefault(values["_key"], values)

        rows = [
            {key: value for key, value in values.items() if key != "_key"}
            for values in unique.values()
        ]

        # RETURNING gives back the generated ids in insert order, so the new
        # plans can be cached without a second lookup query. Selecting them back
        # by (ein, plan_number) instead would have to scan on plan_number, which
        # only has 999 distinct values and so matches almost the whole table.
        assigned = self.session.execute(
            insert(Plan).returning(Plan.id, Plan.ein, Plan.plan_number),
            rows,
        )

        for plan_id, ein, plan_number in assigned:
            self._plan_ids[(ein, plan_number)] = plan_id

        self.session.flush()
        stats.plans_created += len(rows)
        buffer.clear()

    def _flush_filings(
        self,
        buffer: list[tuple[tuple[str | None, str | None], dict[str, Any]]],
        stats: ImportStats,
    ) -> None:
        if not buffer:
            return

        rows: list[dict[str, Any]] = []
        for plan_key, values in buffer:
            plan_id = self._plan_ids.get(plan_key)
            if plan_id is None:
                stats.errors.append(
                    f"Filing {values['ack_id']} references a plan that was not created."
                )
                stats.rows_skipped += 1
                continue
            rows.append({**values, "plan_id": plan_id})

        if rows:
            assigned = self.session.execute(
                insert(Filing).returning(Filing.id, Filing.ack_id, Filing.plan_id),
                rows,
            )

            for filing_id, ack_id, plan_id in assigned:
                self._filing_ids[ack_id] = (filing_id, plan_id)

            self.session.flush()
            stats.filings_created += len(rows)

        buffer.clear()

    # ------------------------------------------------------------------
    # Schedule-sourced enrichment of filing-level facts
    # ------------------------------------------------------------------

    #: Schedule fields that fill in filing values the main form does not carry.
    #: A Form 5500 filing has no financial totals of its own — for a large plan
    #: those live on Schedule H, and for a small one on Schedule I — so without
    #: this step every Form 5500 plan would show no assets at all.
    _FILING_ENRICHMENT: dict[str, dict[str, tuple[str, ...]]] = {
        "F_SCH_H": {
            "total_assets_boy": ("TOT_ASSETS_BOY_AMT",),
            "total_assets_eoy": ("TOT_ASSETS_EOY_AMT",),
            "net_assets_eoy": ("NET_ASSETS_EOY_AMT",),
            "employer_contributions": ("EMPLR_CONTRIB_INCOME_AMT",),
            "participant_contributions": ("PARTICIPANT_CONTRIB_AMT",),
        },
        "F_SCH_I": {
            "total_assets_boy": ("SMALL_TOT_ASSETS_BOY_AMT",),
            "total_assets_eoy": ("SMALL_TOT_ASSETS_EOY_AMT",),
            "net_assets_eoy": ("SMALL_NET_ASSETS_EOY_AMT",),
            "employer_contributions": ("SMALL_EMPLR_CONTRIB_INCOME_AMT",),
            "participant_contributions": ("SMALL_PARTICIPANT_CONTRIB_AMT",),
        },
    }

    def _filing_enrichment(
        self,
        row: dict[str, Any],
        dataset: str,
        filing_id: int,
    ) -> dict[str, Any] | None:
        """Build a filing update from a schedule row, or None if it adds nothing."""

        mapping = self._FILING_ENRICHMENT.get(dataset)
        if mapping is None:
            return None

        values: dict[str, Any] = {}
        for attribute, columns in mapping.items():
            amount = parse_money(first_value(row, *columns))
            if amount is not None:
                values[attribute] = amount

        if not values:
            return None

        return {"id": filing_id, **values}

    def _flush_filing_updates(self, buffer: list[dict[str, Any]]) -> None:
        if not buffer:
            return

        # Later rows for the same filing win; DOL can emit more than one
        # schedule row per filing when a plan year was amended.
        merged: dict[int, dict[str, Any]] = {}
        for values in buffer:
            merged.setdefault(values["id"], {}).update(values)

        self.session.execute(update(Filing), list(merged.values()))
        self.session.flush()
        buffer.clear()

    def _schedule_r_features(self, row: dict[str, Any]) -> tuple[str, ...]:
        """Read plan features Schedule R confirms that the benefit codes may omit."""

        features: list[str] = []

        if normalize_indicator(first_value(row, "F_401K_PLAN_IND")):
            features.append(PlanFeature.K401.value)

        if any(
            normalize_indicator(first_value(row, name))
            for name in ("ESOP_PREF_IND", "ESOP_BACK_TO_BACK_IND", "ESOP_STOCK_NOT_TRADABLE_IND")
        ):
            features.append(PlanFeature.ESOP.value)

        return tuple(features)

    def _apply_schedule_r(self, plan_id: int, features: tuple[str, ...]) -> None:
        """Add Schedule R-confirmed features to a plan without dropping existing ones."""

        if not features:
            return

        plan = self.session.get(Plan, plan_id)
        if plan is None:
            return

        current = set(plan.feature_list())
        merged = current | set(features)

        if merged != current:
            plan.plan_features = "|".join(sorted(merged))

        if not plan.is_retirement_plan:
            plan.is_retirement_plan = True
            if plan.plan_category in (None, PlanCategory.UNKNOWN, PlanCategory.WELFARE):
                plan.plan_category = PlanCategory.DEFINED_CONTRIBUTION

    # ------------------------------------------------------------------
    # Pass 2: schedule datasets
    # ------------------------------------------------------------------

    def _import_schedule_file(
        self,
        path: Path,
        dataset: str,
        form_year: int,
        stats: ImportStats,
        row_estimate: int,
    ) -> None:
        spec = DATASETS_BY_NAME.get(dataset)
        schedule_code = spec.schedule_code if spec else dataset
        source_file = str(path)

        record_buffer: list[dict[str, Any]] = []
        transfer_buffer: list[dict[str, Any]] = []
        pending_providers: list[tuple[str, list[ProviderCandidate], int, str]] = []
        filing_updates: list[dict[str, Any]] = []
        seen_records: set[tuple[str, int | None]] = set()

        for row_number, row in read_csv_rows(path):
            stats.rows_read += 1

            if stats.rows_read % self.batch_size == 0:
                self._check_cancelled()
                self._flush_schedule_records(record_buffer, stats)
                self._flush_transfers(transfer_buffer, stats)
                self._flush_filing_updates(filing_updates)
                self._flush_providers(pending_providers, form_year, source_file, stats)

                # Scoped to the batch, not the file. A duplicate spanning two
                # batches is caught by the existence check in the flush, and a
                # file-wide set would grow to one entry per row -- hundreds of
                # megabytes on the larger schedules.
                seen_records.clear()

                self._report(
                    stats.rows_read,
                    row_estimate,
                    f"{dataset}: {stats.rows_read:,} rows",
                )

            ack_id = parse_ack_id(row)
            if not ack_id:
                stats.rows_skipped += 1
                continue

            link = self._filing_ids.get(ack_id)
            if link is None:
                # The schedule row belongs to a filing this database does not
                # have — normally because the matching filing dataset has not
                # been imported for this year. Keep the row so it links up when
                # the filing arrives, but do not invent a plan for it.
                stats.unmatched_ack_ids += 1
                filing_id, plan_id = None, None
            else:
                filing_id, plan_id = link

            row_order = parse_row_order(row)
            record_key = (ack_id, row_order)
            if record_key in seen_records:
                stats.rows_skipped += 1
                continue
            seen_records.add(record_key)

            record_buffer.append(
                {
                    "ack_id": ack_id,
                    "plan_id": plan_id,
                    "filing_id": filing_id,
                    "form_year": form_year,
                    "dataset": dataset,
                    "schedule_code": schedule_code,
                    "row_order": row_order,
                    "source_file": source_file,
                    "source_row": row_number,
                    "raw_data": {
                        key: value
                        for key, value in row.items()
                        if value not in (None, "") and key != "_EXTRA"
                    },
                    "created_at": _utcnow(),
                }
            )

            candidates = extract_providers(row, dataset)
            if candidates and plan_id is not None:
                pending_providers.append((ack_id, candidates, row_number, dataset))

            if dataset == TRANSFER_DATASET and plan_id is not None:
                target = extract_transfer(row)
                if target is not None:
                    transfer_buffer.append(
                        {
                            "from_plan_id": plan_id,
                            "ack_id": ack_id,
                            "form_year": form_year,
                            "to_name": target.name,
                            "to_ein": target.ein,
                            "to_plan_number": target.plan_number,
                            "to_plan_id": None,
                            "source_file": source_file,
                            "source_row": row_number,
                            "created_at": _utcnow(),
                        }
                    )

            if filing_id is not None:
                enrichment = self._filing_enrichment(row, dataset, filing_id)
                if enrichment is not None:
                    filing_updates.append(enrichment)

            if dataset == "F_SCH_R" and plan_id is not None:
                self._apply_schedule_r(plan_id, self._schedule_r_features(row))

            stats.rows_imported += 1

        self._check_cancelled()
        self._flush_schedule_records(record_buffer, stats)
        self._flush_transfers(transfer_buffer, stats)
        self._flush_filing_updates(filing_updates)
        self._flush_providers(pending_providers, form_year, source_file, stats)
        self.session.commit()

        if stats.unmatched_ack_ids:
            logger.warning(
                "%s %s: %s row(s) referenced filings not present in the database. "
                "Import the matching filing dataset (F_5500 / F_5500_SF) for this "
                "year and re-run to attach them.",
                form_year,
                dataset,
                stats.unmatched_ack_ids,
            )

        self._report(stats.rows_read, row_estimate or stats.rows_read, f"{dataset}: complete")

    def _flush_schedule_records(self, buffer: list[dict[str, Any]], stats: ImportStats) -> None:
        if not buffer:
            return

        # Guard the (ack_id, dataset, row_order) unique constraint against rows
        # already present from an earlier partial run.
        existing = set(
            self.session.execute(
                select(ScheduleRecord.ack_id, ScheduleRecord.row_order).where(
                    ScheduleRecord.dataset == buffer[0]["dataset"],
                    ScheduleRecord.ack_id.in_({row["ack_id"] for row in buffer}),
                )
            ).all()
        )

        rows = [
            row for row in buffer if (row["ack_id"], row["row_order"]) not in existing
        ]

        if rows:
            self.session.execute(insert(ScheduleRecord), rows)
            self.session.flush()
            stats.schedule_rows += len(rows)

        stats.rows_skipped += len(buffer) - len(rows)
        buffer.clear()

    # ------------------------------------------------------------------
    # Providers, parties and evidence
    # ------------------------------------------------------------------

    def _flush_providers(
        self,
        buffer: list[tuple[str, list[ProviderCandidate], int, str]],
        form_year: int,
        source_file: str,
        stats: ImportStats,
    ) -> None:
        if not buffer:
            return

        self._ensure_providers(buffer, stats)

        party_rows: list[dict[str, Any]] = []
        evidence_rows: list[dict[str, Any]] = []
        batch_party_keys: set[tuple[int, int, str, int, str]] = set()

        for ack_id, candidates, row_number, dataset in buffer:
            link = self._filing_ids.get(ack_id)
            if link is None:
                continue
            filing_id, plan_id = link

            spec = DATASETS_BY_NAME.get(dataset)
            schedule_code = spec.schedule_code if spec else dataset

            for candidate in candidates:
                identity = normalize_provider(candidate.name)
                provider_id = self._provider_ids.get(identity.name_key)
                if provider_id is None:
                    continue

                # Deduplicate within this batch; the unique constraint plus
                # INSERT OR IGNORE handles collisions with rows already stored.
                party_key = (plan_id, provider_id, candidate.role, form_year, schedule_code)
                if party_key in batch_party_keys:
                    continue
                batch_party_keys.add(party_key)

                party_rows.append(
                    {
                        "plan_id": plan_id,
                        "provider_id": provider_id,
                        "filing_id": filing_id,
                        "role": candidate.role,
                        "reported_name": candidate.name,
                        "reported_ein": candidate.ein,
                        "relationship_text": candidate.relationship,
                        "form_year": form_year,
                        "schedule_code": schedule_code,
                        "source_field": candidate.source_field,
                        "service_codes": "|".join(candidate.service_codes) or None,
                        "direct_compensation": candidate.direct_compensation,
                        "indirect_compensation": candidate.indirect_compensation,
                        "confidence": candidate.confidence,
                        "created_at": _utcnow(),
                    }
                )

                evidence_rows.append(
                    {
                        "plan_id": plan_id,
                        "filing_id": filing_id,
                        "form_year": form_year,
                        "ack_id": ack_id,
                        "source_type": "DOL_DATASET",
                        "dataset": dataset,
                        "schedule_code": schedule_code,
                        "source_file": source_file,
                        "source_row": row_number,
                        "field_name": candidate.source_field,
                        "field_value": candidate.name,
                        "notes": candidate.reason,
                        "confidence": candidate.confidence,
                        "created_at": _utcnow(),
                    }
                )

        # OR IGNORE lets a re-run skip rows already recorded without needing
        # every existing key held in memory first.
        if party_rows:
            stats.parties_created += self._insert_ignoring_duplicates(PlanParty, party_rows)

        if evidence_rows:
            stats.evidence_created += self._insert_ignoring_duplicates(Evidence, evidence_rows)

        if party_rows or evidence_rows:
            self.session.flush()

        buffer.clear()

    def _flush_transfers(self, buffer: list[dict[str, Any]], stats: ImportStats) -> None:
        """
        Write the plan-to-plan transfers collected from Schedule H Part 1.

        ``INSERT OR IGNORE`` against the unique constraint makes a re-import
        idempotent, which matters here because a year is commonly re-imported
        after the matching filing dataset arrives.
        """

        if not buffer:
            return

        stats.transfers_recorded += self._insert_ignoring_duplicates(PlanTransfer, buffer)
        buffer.clear()

    def _insert_ignoring_duplicates(self, model, rows: list[dict[str, Any]]) -> int:
        """
        Bulk-insert rows, skipping any that violate a unique constraint.

        Returns how many rows were actually written. An executemany result does
        not carry a usable rowcount, so SQLite's own change counter is read
        either side of the statement; where that is unavailable the count falls
        back to the number offered.
        """

        raw = getattr(self.session.connection().connection, "dbapi_connection", None)
        before = getattr(raw, "total_changes", None)

        self.session.execute(insert(model).prefix_with("OR IGNORE"), rows)

        after = getattr(raw, "total_changes", None)
        if before is None or after is None:
            return len(rows)

        return max(after - before, 0)

    def _ensure_providers(
        self,
        buffer: list[tuple[str, list[ProviderCandidate], int, str]],
        stats: ImportStats,
    ) -> None:
        """Create any provider records this batch needs, in one insert."""

        new_rows: dict[str, dict[str, Any]] = {}

        for _, candidates, _, _ in buffer:
            for candidate in candidates:
                identity = normalize_provider(candidate.name)
                if not identity.name_key or identity.name_key in self._provider_ids:
                    continue
                if identity.name_key in new_rows:
                    continue

                new_rows[identity.name_key] = {
                    "name": identity.display_name,
                    "name_key": identity.name_key,
                    "ein": candidate.ein,
                    "city": candidate.city,
                    "state": candidate.state,
                    "canonical_name": identity.canonical_name,
                    "primary_role": candidate.role,
                    "plan_count": 0,
                    "participant_count": 0,
                    "assets_under_administration": 0.0,
                    "created_at": _utcnow(),
                    "updated_at": _utcnow(),
                }

        if not new_rows:
            return

        assigned = self.session.execute(
            insert(Provider).returning(Provider.id, Provider.name_key),
            list(new_rows.values()),
        )

        for provider_id, name_key in assigned:
            self._provider_ids[name_key] = provider_id

        self.session.flush()
        stats.providers_created += len(new_rows)


def _drop_temp(session: Session, name: str) -> None:
    session.execute(text(f"DROP TABLE IF EXISTS temp.{name}"))


def refresh_provider_rollups(session: Session) -> int:
    """
    Recompute each provider's plan count, participants and assets.

    Run once after an import rather than per row: these are aggregates over
    every engagement, and maintaining them incrementally would mean re-reading
    every provider on every row that mentions it.

    The totals are built into an indexed temporary table first, then joined in.
    Expressing them as correlated subqueries directly against `plan_parties`
    makes SQLite rescan that table once per provider per column, which turns a
    one-second step into a multi-minute one on a real form year.

    Returns the number of providers updated.
    """

    _drop_temp(session, "provider_totals")

    session.execute(
        text(
            """
            CREATE TEMP TABLE provider_totals AS
            SELECT
                pp.provider_id AS provider_id,
                COUNT(DISTINCT pp.plan_id) AS plan_count,
                COALESCE(SUM(p.latest_participants), 0) AS participant_count,
                COALESCE(SUM(p.latest_total_assets), 0.0) AS assets
            FROM (SELECT DISTINCT provider_id, plan_id FROM plan_parties) pp
            LEFT JOIN plans p ON p.id = pp.plan_id
            GROUP BY pp.provider_id
            """
        )
    )
    session.execute(
        text("CREATE UNIQUE INDEX temp.ix_provider_totals ON provider_totals(provider_id)")
    )

    # The role a provider is engaged in most often across all its plans.
    _drop_temp(session, "provider_primary_role")
    session.execute(
        text(
            """
            CREATE TEMP TABLE provider_primary_role AS
            SELECT provider_id, role FROM (
                SELECT
                    provider_id,
                    role,
                    ROW_NUMBER() OVER (
                        PARTITION BY provider_id ORDER BY COUNT(*) DESC, role
                    ) AS rn
                FROM plan_parties
                GROUP BY provider_id, role
            )
            WHERE rn = 1
            """
        )
    )
    session.execute(
        text("CREATE UNIQUE INDEX temp.ix_provider_role ON provider_primary_role(provider_id)")
    )

    result = session.execute(
        text(
            """
            UPDATE providers
            SET plan_count = COALESCE(
                    (SELECT t.plan_count FROM provider_totals t
                     WHERE t.provider_id = providers.id), 0),
                participant_count = COALESCE(
                    (SELECT t.participant_count FROM provider_totals t
                     WHERE t.provider_id = providers.id), 0),
                assets_under_administration = COALESCE(
                    (SELECT t.assets FROM provider_totals t
                     WHERE t.provider_id = providers.id), 0.0),
                primary_role = COALESCE(
                    (SELECT r.role FROM provider_primary_role r
                     WHERE r.provider_id = providers.id), primary_role)
            """
        )
    )

    _drop_temp(session, "provider_totals")
    _drop_temp(session, "provider_primary_role")

    session.commit()
    return int(result.rowcount or 0)


def refresh_plan_rollups(session: Session) -> int:
    """
    Copy each plan's headline numbers down from its most recent filing.

    Schedule H and Schedule I carry the financials for Form 5500 filers, so a
    plan's asset total is only known once those schedules have been imported and
    folded into the filing. This step runs after every import to pick that up.

    The most recent filing per plan is materialised into an indexed temporary
    table rather than left as a CTE: an unindexed CTE is rescanned for every
    plan row, which on a real form year (220k plans, 230k filings) does not
    finish in any reasonable time.

    Returns the number of plans updated.
    """

    _drop_temp(session, "latest_filing")

    session.execute(
        text(
            """
            CREATE TEMP TABLE latest_filing AS
            SELECT plan_id, total_assets_eoy, total_participants, active_participants
            FROM (
                SELECT
                    plan_id,
                    total_assets_eoy,
                    total_participants,
                    active_participants,
                    ROW_NUMBER() OVER (
                        PARTITION BY plan_id
                        ORDER BY form_year DESC, date_received DESC, id DESC
                    ) AS rn
                FROM filings
            )
            WHERE rn = 1
            """
        )
    )
    session.execute(
        text("CREATE UNIQUE INDEX temp.ix_latest_filing ON latest_filing(plan_id)")
    )

    result = session.execute(
        text(
            """
            UPDATE plans
            SET latest_total_assets = COALESCE(
                    (SELECT l.total_assets_eoy FROM latest_filing l
                     WHERE l.plan_id = plans.id),
                    plans.latest_total_assets),
                latest_participants = COALESCE(
                    (SELECT l.total_participants FROM latest_filing l
                     WHERE l.plan_id = plans.id),
                    plans.latest_participants),
                latest_active_participants = COALESCE(
                    (SELECT l.active_participants FROM latest_filing l
                     WHERE l.plan_id = plans.id),
                    plans.latest_active_participants)
            WHERE EXISTS (SELECT 1 FROM latest_filing l WHERE l.plan_id = plans.id)
            """
        )
    )

    _drop_temp(session, "latest_filing")

    session.commit()
    return int(result.rowcount or 0)


#: Release label for files imported from disk rather than downloaded. Kept
#: distinct from DOL's own "Latest" and "All" so a local import never looks like
#: a completed sync of the published release.
LOCAL_RELEASE = "Local"


def _record_local_import(
    session: Session, form_year: int, dataset: str, path: Path, stats: ImportStats
) -> None:
    """
    Note that a dataset arrived, however it arrived.

    Without this, importing files from disk left no record, so anything asking
    "which years do we hold, and how completely" -- the Data tab, the coverage
    report the trace leans on -- saw nothing at all.
    """

    from app.database.models import ImportedDataset

    existing = session.execute(
        select(ImportedDataset).where(
            ImportedDataset.form_year == form_year,
            ImportedDataset.dataset == dataset,
            ImportedDataset.release == LOCAL_RELEASE,
        )
    ).scalar_one_or_none()

    record = existing or ImportedDataset(
        form_year=form_year, dataset=dataset, release=LOCAL_RELEASE
    )

    record.status = "COMPLETED"
    record.source_file = str(path)
    record.rows_read = stats.rows_read
    record.rows_imported = stats.rows_imported
    record.rows_skipped = stats.rows_skipped
    record.parties_created = stats.parties_created
    record.finished_at = _utcnow()
    record.error = None

    if existing is None:
        session.add(record)

    session.commit()


def import_directory(
    session: Session,
    directory: Path,
    form_year: int | None = None,
    datasets: Iterable[str] | None = None,
    batch_size: int = 5000,
    progress: ProgressCallback | None = None,
) -> ImportStats:
    """
    Import every DOL CSV found under a directory.

    Files are ordered so filing datasets import before schedules, which is what
    lets the schedule rows find their filings.
    """

    from app.dol.filing_parser import infer_dataset_from_filename

    total = ImportStats(form_year=form_year or 0)

    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    wanted = {name.upper() for name in datasets} if datasets else None

    discovered: list[tuple[Path, str, int]] = []
    for path in sorted(directory.rglob("*.csv")):
        dataset, year = infer_dataset_from_filename(path.name)
        if dataset is None or year is None:
            total.errors.append(f"Skipped unrecognised file: {path.name}")
            continue
        if form_year is not None and year != form_year:
            continue
        if wanted and dataset not in wanted:
            continue
        discovered.append((path, dataset, year))

    if not discovered:
        raise FileNotFoundError(f"No recognisable DOL CSV files under: {directory}")

    discovered.sort(key=lambda item: (item[1] not in FIELD_MAPS, item[2], item[1]))

    importer = DOLImporter(session, batch_size=batch_size, progress=progress)

    for path, dataset, year in discovered:
        try:
            stats = importer.import_file(path, dataset, year)
            total.merge(stats)
            _record_local_import(session, year, dataset, path, stats)
        except ImportCancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            total.errors.append(f"{path.name}: {exc}")
            logger.exception("Failed to import %s", path)

    # Rollups run last: they aggregate over everything just imported, and the
    # provider figures depend on the plan figures being current. Transfers are
    # resolved first because a transfer only links once both plans exist, and
    # the plan that received the assets may have arrived in this same run.
    resolve_transfers(session)
    refresh_plan_rollups(session)
    refresh_provider_rollups(session)

    return total
