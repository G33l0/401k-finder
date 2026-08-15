"""
Background workers.

Every database or network operation runs on a QThread so the window stays
responsive: a full-year sync takes hours, and a search over millions of plans
can take seconds. Each worker owns its own session, because a SQLAlchemy session
is not safe to share across threads.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from app.core.config import Settings
from app.core.exceptions import ImportCancelled
from app.core.logging import get_logger
from app.database.session import create_session
from app.evidence.trail import PlanEvidence, build_plan_evidence
from app.search.engine import PlanResult, ProviderResult, SearchEngine
from app.search.query import PlanQuery, ProviderQuery, QueryOptions

logger = get_logger(__name__)

#: Work runs on a background thread and is handed a fresh session plus the
#: worker itself, so long-running tasks can report progress and poll for
#: cancellation without the caller having to wire either up.
WorkFunction = Callable[[Any, "Worker"], object]


class Worker(QObject):
    """
    Runs one callable on a background thread and reports the result.

    Errors are delivered on ``failed`` rather than raised, so a failure in a
    worker surfaces in the UI instead of tearing down the thread silently.
    """

    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, work: WorkFunction) -> None:
        super().__init__()
        self._work = work
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        session = None
        try:
            session = create_session()
            result = self._work(session, self)
            self.finished.emit(result)
        except ImportCancelled:
            self.failed.emit("Cancelled.")
        except Exception as exc:  # noqa: BLE001 - reported to the user
            logger.exception("Background task failed")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if session is not None:
                session.close()


class TaskRunner(QObject):
    """
    Owns a worker and its thread, and keeps them alive until the work is done.

    The references are deliberately *not* cleared when the thread finishes.
    Dropping the last Python reference to a running QThread makes Qt abort with
    "QThread: Destroyed while thread is still running", and a ``finished``
    handler runs while the thread is still winding down — so the previous
    thread is only released once the next ``start`` has waited for it to stop.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: Worker | None = None

    @property
    def busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def start(
        self,
        work: WorkFunction,
        on_finished: Callable[[object], None],
        on_failed: Callable[[str], None] | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> None:
        """Start a task, cancelling and waiting for any task already running."""

        self.stop()

        thread = QThread()
        worker = Worker(work)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(on_finished)
        worker.finished.connect(thread.quit)

        if on_failed is not None:
            worker.failed.connect(on_failed)
        worker.failed.connect(thread.quit)

        if on_progress is not None:
            worker.progress.connect(on_progress)

        self._thread = thread
        self._worker = worker

        thread.start()

    def cancel(self) -> None:
        """Ask the running task to stop at its next checkpoint."""

        if self._worker is not None:
            self._worker.cancel()

    def stop(self, wait_ms: int = 10_000) -> None:
        """
        Cancel the current task and block until its thread has actually stopped.

        A task that ignores cancellation — a long single query, say — is given
        ``wait_ms`` and then left to finish on its own rather than being killed,
        since terminating a thread mid-transaction would risk the database.
        """

        thread, self._thread = self._thread, None
        self._worker, worker = None, self._worker

        if thread is None:
            return

        if worker is not None:
            worker.cancel()

        thread.quit()

        if not thread.wait(wait_ms):
            logger.warning("Background task did not stop within %s ms.", wait_ms)
            # Hold the reference so Qt does not abort on a still-running thread.
            self._thread = thread
            self._worker = worker


# ----------------------------------------------------------------------
# Task factories
# ----------------------------------------------------------------------


def search_plans_task(query: PlanQuery, options: QueryOptions) -> WorkFunction:
    def work(session, _worker) -> tuple[int, list[PlanResult]]:  # noqa: ANN001
        engine = SearchEngine(session)
        return engine.count_plans(query), engine.search_plans(query, options)

    return work


def search_providers_task(query: ProviderQuery) -> WorkFunction:
    def work(session, _worker) -> list[ProviderResult]:  # noqa: ANN001
        return SearchEngine(session).search_providers(query)

    return work


def plan_detail_task(plan_id: int) -> WorkFunction:
    def work(session, _worker) -> tuple[PlanResult | None, PlanEvidence | None]:  # noqa: ANN001
        engine = SearchEngine(session)
        return engine.get_plan(plan_id), build_plan_evidence(session, plan_id)

    return work


def summary_task() -> WorkFunction:
    from app.services.stats import database_summary

    def work(session, _worker):  # noqa: ANN001
        return database_summary(session)

    return work


def sync_task(
    form_year: int,
    settings: Settings,
    datasets: tuple[str, ...] | None = None,
    core_only: bool = True,
    force: bool = False,
) -> WorkFunction:
    """Build a sync task that reports progress and honours cancellation."""

    from app.dol.catalog import Release
    from app.services.sync import SyncService

    def work(session, worker):  # noqa: ANN001
        def on_progress(stage: str, dataset: str, done: int, total: int, message: str) -> None:
            worker.progress.emit(done, total, f"{stage}: {message}")

        service = SyncService(
            session,
            settings=settings,
            progress=on_progress,
            should_cancel=worker.is_cancelled,
        )

        return service.sync_year(
            form_year,
            release=Release(settings.release),
            datasets=datasets,
            core_only=core_only,
            force=force,
        )

    return work


def import_task(
    directory: Path,
    form_year: int | None,
    settings: Settings,
) -> WorkFunction:
    """Build a local-import task that reports progress."""

    from app.dol.importer import import_directory

    def work(session, worker):  # noqa: ANN001
        def on_progress(done: int, total: int, message: str) -> None:
            worker.progress.emit(done, total, message)

        return import_directory(
            session,
            directory,
            form_year=form_year,
            batch_size=settings.import_batch_size,
            progress=on_progress,
        )

    return work
