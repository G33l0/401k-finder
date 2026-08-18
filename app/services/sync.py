"""Fetch a form year from DOL and load it into the local database."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, dataset_directory, get_download_dir
from app.core.exceptions import DatasetError, DownloadError, ImportCancelled
from app.core.logging import get_logger
from app.database.models import ImportedDataset
from app.database.schema import analyze, rebuild_fts
from app.dol.archive import safe_extract_zip
from app.dol.catalog import DatasetRelease, Release, plan_sync, supported_years
from app.dol.csv_reader import count_rows, find_csv_files
from app.dol.downloader import DOLDownloader
from app.dol.importer import (
    DOLImporter,
    ImportStats,
    refresh_plan_rollups,
    refresh_provider_rollups,
)
from app.dol.validator import ValidationResult, validate_csv_file
from app.plans.successor import resolve_transfers

logger = get_logger(__name__)

STATUS_PENDING = "PENDING"
STATUS_DOWNLOADING = "DOWNLOADING"
STATUS_IMPORTING = "IMPORTING"
STATUS_COMPLETE = "COMPLETE"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"

SyncProgress = Callable[[str, str, int, int, str], None]
CancelCheck = Callable[[], bool]


@dataclass(slots=True)
class DatasetOutcome:
    dataset: str
    form_year: int
    status: str
    message: str = ""
    stats: ImportStats | None = None
    validation: ValidationResult | None = None

    @property
    def ok(self) -> bool:
        return self.status in {STATUS_COMPLETE, STATUS_SKIPPED}


@dataclass(slots=True)
class SyncReport:
    form_year: int
    release: str
    outcomes: list[DatasetOutcome] = field(default_factory=list)
    totals: ImportStats = field(default_factory=ImportStats)

    @property
    def succeeded(self) -> list[DatasetOutcome]:
        return [outcome for outcome in self.outcomes if outcome.ok]

    @property
    def failed(self) -> list[DatasetOutcome]:
        return [outcome for outcome in self.outcomes if not outcome.ok]

    def summary(self) -> str:
        return (
            f"{self.form_year} ({self.release}): "
            f"{len(self.succeeded)}/{len(self.outcomes)} datasets loaded. "
            f"{self.totals.summary()}"
        )


class SyncService:
    """Downloads and imports DOL datasets."""

    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        progress: SyncProgress | None = None,
        should_cancel: CancelCheck | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or Settings()
        self.progress = progress
        self.should_cancel = should_cancel
        self.downloader = DOLDownloader(timeout=self.settings.download_timeout)

    def _report(self, stage: str, dataset: str, done: int, total: int, message: str) -> None:
        if self.progress:
            self.progress(stage, dataset, done, total, message)
        logger.debug("%s %s: %s", stage, dataset, message)

    def _cancelled(self) -> bool:
        return bool(self.should_cancel and self.should_cancel())

    def _record(self, release: DatasetRelease) -> ImportedDataset:
        record = self.session.execute(
            select(ImportedDataset).where(
                ImportedDataset.form_year == release.form_year,
                ImportedDataset.dataset == release.name,
                ImportedDataset.release == release.release.value,
            )
        ).scalar_one_or_none()

        if record is None:
            record = ImportedDataset(
                form_year=release.form_year,
                dataset=release.name,
                release=release.release.value,
                status=STATUS_PENDING,
                source_url=release.archive_url,
            )
            self.session.add(record)
            self.session.commit()

        return record

    def download(self, release: DatasetRelease, force: bool = False) -> Path:
        """Download one dataset archive, reusing an existing complete file."""

        destination = get_download_dir() / str(release.form_year) / release.archive_name

        if destination.exists() and not force:
            self._report(
                "download", release.name, 1, 1, f"Using cached {release.archive_name}"
            )
            return destination

        def on_progress(done: int, total: int) -> None:
            self._report(
                "download",
                release.name,
                done,
                total,
                f"Downloading {release.archive_name}",
            )

        return self.downloader.download(
            release.archive_url,
            destination=destination,
            progress=on_progress,
            should_cancel=self.should_cancel,
        )

    def extract(self, release: DatasetRelease, archive: Path) -> tuple[Path, ...]:
        """Extract an archive into the dataset's data directory."""

        target = dataset_directory(release.form_year, release.name)

        existing = find_csv_files(target)
        if existing:
            self._report("extract", release.name, 1, 1, "Already extracted")
            return existing

        self._report("extract", release.name, 0, 1, f"Extracting {archive.name}")
        safe_extract_zip(archive, target)

        files = find_csv_files(target)
        if not files:
            raise DatasetError(f"{archive.name} contained no CSV files.")

        return files

    def validate(self, release: DatasetRelease, files: tuple[Path, ...]) -> ValidationResult:
        result = ValidationResult()

        for path in files:
            result.merge(validate_csv_file(path, release.name, release.form_year))

        self._report("validate", release.name, 1, 1, result.summary())
        return result

    def sync_dataset(
        self,
        release: DatasetRelease,
        importer: DOLImporter,
        force: bool = False,
    ) -> DatasetOutcome:
        """Run one dataset through download, extract, validate and import."""

        record = self._record(release)

        if record.status == STATUS_COMPLETE and not force:
            return DatasetOutcome(
                dataset=release.name,
                form_year=release.form_year,
                status=STATUS_SKIPPED,
                message="Already imported.",
            )

        record.status = STATUS_DOWNLOADING
        record.started_at = datetime.now(UTC).replace(tzinfo=None)
        record.error = None
        self.session.commit()

        try:
            archive = self.download(release, force=force)
            record.source_file = str(archive)
            record.file_size = archive.stat().st_size
            self.session.commit()

            files = self.extract(release, archive)
            validation = self.validate(release, files)

            if not validation.valid:
                raise DatasetError(
                    f"{release.name} failed validation: "
                    + "; ".join(issue.message for issue in validation.errors()[:3])
                )

            record.status = STATUS_IMPORTING
            self.session.commit()

            stats = ImportStats(dataset=release.name, form_year=release.form_year)

            for path in files:
                if self._cancelled():
                    raise ImportCancelled("Sync cancelled.")

                estimate = count_rows(path)
                file_stats = importer.import_file(
                    path,
                    dataset=release.name,
                    form_year=release.form_year,
                    release=release.release.value,
                    row_estimate=estimate,
                )
                stats.merge(file_stats)

            record.status = STATUS_COMPLETE
            record.rows_read = stats.rows_read
            record.rows_imported = stats.rows_imported
            record.rows_skipped = stats.rows_skipped
            record.parties_created = stats.parties_created
            record.finished_at = datetime.now(UTC).replace(tzinfo=None)
            self.session.commit()

            if not self.settings.keep_extracted:
                for path in files:
                    path.unlink(missing_ok=True)

            if not self.settings.keep_archives:
                archive.unlink(missing_ok=True)

            return DatasetOutcome(
                dataset=release.name,
                form_year=release.form_year,
                status=STATUS_COMPLETE,
                message=stats.summary(),
                stats=stats,
                validation=validation,
            )

        except ImportCancelled:
            record.status = STATUS_FAILED
            record.error = "Cancelled by user."
            self.session.commit()
            raise

        except (DatasetError, DownloadError, OSError) as exc:
            self.session.rollback()
            record = self._record(release)
            record.status = STATUS_FAILED
            record.error = str(exc)
            record.finished_at = datetime.now(UTC).replace(tzinfo=None)
            self.session.commit()

            # exception(), not error(): the traceback is the whole value of a
            # log a customer sends you after a download fails.
            logger.exception("%s %s failed", release.form_year, release.name)

            return DatasetOutcome(
                dataset=release.name,
                form_year=release.form_year,
                status=STATUS_FAILED,
                message=str(exc),
            )

    def sync_year(
        self,
        form_year: int,
        release: Release | None = None,
        datasets: tuple[str, ...] | None = None,
        core_only: bool | None = None,
        force: bool = False,
        index_only: bool = False,
    ) -> SyncReport:
        """Sync a whole form year."""

        chosen_release = release or Release(self.settings.release)
        use_core = self.settings.core_datasets_only if core_only is None else core_only

        selected = plan_sync(
            form_year,
            release=chosen_release,
            datasets=datasets,
            core_only=use_core,
            index_only=index_only,
        )

        if not selected:
            raise DatasetError(
                f"No matching datasets published for form year {form_year}."
            )

        report = SyncReport(form_year=form_year, release=chosen_release.value)
        importer = DOLImporter(
            self.session,
            batch_size=self.settings.import_batch_size,
            progress=lambda done, total, message: self._report(
                "import", message.split(":")[0], done, total, message
            ),
            should_cancel=self.should_cancel,
        )

        for index, item in enumerate(selected, start=1):
            if self._cancelled():
                raise ImportCancelled("Sync cancelled.")

            self._report(
                "dataset",
                item.name,
                index,
                len(selected),
                f"{item.name} ({index} of {len(selected)})",
            )

            outcome = self.sync_dataset(item, importer, force=force)
            report.outcomes.append(outcome)

            if outcome.stats:
                report.totals.merge(outcome.stats)

        self.finalize()
        logger.info(report.summary())

        return report

    def sync_index(
        self,
        years: Iterable[int] | None = None,
        release: Release | None = None,
        force: bool = False,
    ) -> list[SyncReport]:
        """Fetch the employer index for many years."""

        wanted = list(years) if years is not None else list(supported_years())
        reports: list[SyncReport] = []

        for position, form_year in enumerate(wanted, start=1):
            if self._cancelled():
                raise ImportCancelled("Sync cancelled.")

            self._report(
                "year", str(form_year), position, len(wanted),
                f"Indexing {form_year} ({position} of {len(wanted)})",
            )

            try:
                reports.append(
                    self.sync_year(
                        form_year, release=release, index_only=True, force=force
                    )
                )
            except DatasetError as exc:
                logger.info("Skipping %s: %s", form_year, exc)

        return reports

    def finalize(self) -> None:
        """Recompute rollups and search indexes after an import."""

        self._report("finalize", "", 0, 4, "Linking asset transfers")
        resolve_transfers(self.session)

        self._report("finalize", "", 1, 4, "Updating plan totals")
        refresh_plan_rollups(self.session)

        self._report("finalize", "", 2, 4, "Updating provider totals")
        refresh_provider_rollups(self.session)

        self._report("finalize", "", 3, 4, "Rebuilding search index")
        engine = self.session.get_bind()
        rebuild_fts(engine)
        analyze(engine)

        self._report("finalize", "", 4, 4, "Done")

    def status(self, form_year: int | None = None) -> list[ImportedDataset]:
        """Return what has been imported, newest year first."""

        statement = select(ImportedDataset)

        if form_year is not None:
            statement = statement.where(ImportedDataset.form_year == form_year)

        return list(
            self.session.execute(
                statement.order_by(
                    ImportedDataset.form_year.desc(), ImportedDataset.dataset
                )
            ).scalars()
        )
