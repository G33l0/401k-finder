"""
Background workers.

Every database or network operation runs on a QThread so the window stays
responsive: a full-year sync takes hours, and a search over millions of plans
can take seconds. Each worker owns its own session, because a SQLAlchemy session
is not safe to share across threads.
"""

from __future__ import annotations

import contextlib
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

    Dropping the last Python reference to a running QThread makes Qt abort with
    "QThread: Destroyed while thread is still running", so a thread is only
    released once it has actually stopped — either during ``stop``, or later
    from the ``_retiring`` list.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        # Signals actually connected for the current worker. Disconnecting one
        # that was never connected makes PySide emit a RuntimeWarning.
        self._connected: list[str] = []
        # Threads that were asked to stop but had not finished yet. They are
        # held here purely to keep a Python reference alive until Qt is done
        # with them; see _drain.
        self._retiring: list[QThread] = []

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

        connected = ["finished", "failed"]

        if on_progress is not None:
            worker.progress.connect(on_progress)
            connected.append("progress")

        self._thread = thread
        self._worker = worker
        self._connected = connected

        thread.start()

    def cancel(self) -> None:
        """Ask the running task to stop at its next checkpoint."""

        if self._worker is not None:
            self._worker.cancel()

    def stop(self, wait_ms: int = 250) -> None:
        """
        Cancel the current task and let it wind down.

        The wait is deliberately short. This runs on the UI thread, and a search
        is replaced every time the user types — blocking here for the length of
        the previous query would freeze the window for exactly as long as that
        query takes. A task that has not stopped within ``wait_ms`` is moved to
        ``_retiring`` and finishes in its own time; its result is discarded
        because the signals were disconnected first.
        """

        thread, self._thread = self._thread, None
        worker, self._worker = self._worker, None

        if thread is None:
            return

        connected, self._connected = self._connected, []

        if worker is not None:
            worker.cancel()

            # Detach the callbacks so a late result cannot overwrite the newer
            # task's output. Only signals that were connected are touched.
            for name in connected:
                # RuntimeError/TypeError here means the C++ object is already
                # gone, which is exactly the case we no longer need to detach.
                with contextlib.suppress(RuntimeError, TypeError):
                    getattr(worker, name).disconnect()

        thread.quit()

        if not thread.wait(wait_ms):
            self._retiring.append(thread)

        self._drain()

    def _drain(self) -> None:
        """Release threads that have since finished."""

        self._retiring = [thread for thread in self._retiring if thread.isRunning()]

    def shutdown(self, wait_ms: int = 10_000) -> None:
        """
        Stop everything and wait properly. For application exit only.

        Here a long wait is correct: the process is going away, and killing a
        thread mid-transaction would risk the database.
        """

        self.stop(wait_ms=0)

        for thread in self._retiring:
            thread.quit()
            if not thread.wait(wait_ms):
                logger.warning("A background task did not stop before shutdown.")

        self._retiring.clear()


# ----------------------------------------------------------------------
# Task factories
# ----------------------------------------------------------------------


def search_plans_task(query: PlanQuery, options: QueryOptions) -> WorkFunction:
    def work(session, _worker) -> tuple[int, bool, list[PlanResult]]:  # noqa: ANN001
        engine = SearchEngine(session)
        total, capped = engine.count_plans_detailed(query)
        return total, capped, engine.search_plans(query, options)

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


def index_task(settings: Settings, force: bool = False) -> WorkFunction:
    """Fetch the employer index for every published form year."""

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
        return service.sync_index(force=force)

    return work


def changes_task(query) -> WorkFunction:  # noqa: ANN001 - providers.ChangeQuery
    """Find plans that changed provider between filed years."""

    from app.providers.changes import ChangeDetector

    def work(session, _worker):  # noqa: ANN001
        return ChangeDetector(session).find(query)

    return work


def trace_task(history) -> WorkFunction:  # noqa: ANN001 - app.trace.WorkHistory
    """Trace a work history. Imported lazily so the UI module stays light."""

    from app.trace import AccountTracer

    def work(session, _worker):  # noqa: ANN001
        return AccountTracer(session).trace(history)

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
