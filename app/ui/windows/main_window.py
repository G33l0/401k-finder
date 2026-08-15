"""The application's main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.core.config import Settings, get_app_data_dir, get_database_path
from app.core.constants import DOL_DATASET_PAGE_URL
from app.core.logging import get_logger
from app.database.init_db import initialize_database, reset_database
from app.search.query import PlanQuery, ProviderQuery, QueryOptions
from app.services import export as export_service
from app.ui.widgets.data_manager import DataManagerPanel
from app.ui.widgets.plan_detail import PlanDetailPanel
from app.ui.widgets.provider_panel import ProviderPanel
from app.ui.widgets.results_table import PlanTable
from app.ui.widgets.search_panel import SearchPanel
from app.ui.workers import (
    TaskRunner,
    import_task,
    plan_detail_task,
    search_plans_task,
    search_providers_task,
    summary_task,
    sync_task,
)

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    The main window: search on the left, results and detail on the right.

    Each long-running concern gets its own TaskRunner, so a sync in the
    background never blocks a search in the foreground.
    """

    def __init__(self) -> None:
        super().__init__()

        self.settings = Settings.load()

        self.search_runner = TaskRunner(self)
        self.detail_runner = TaskRunner(self)
        self.provider_runner = TaskRunner(self)
        self.data_runner = TaskRunner(self)
        self.summary_runner = TaskRunner(self)

        self.setWindowTitle(f"401K Finder Pro {__version__}")
        self.resize(1500, 900)

        self._build_ui()
        self._build_menu()

        # Let the window paint before touching the database, so a slow first
        # open does not look like a hang.
        QTimer.singleShot(0, self._startup)

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.tabs = QTabWidget()

        # --- Search tab -----------------------------------------------
        search_tab = QWidget()
        search_layout = QVBoxLayout(search_tab)
        search_layout.setContentsMargins(0, 0, 0, 0)

        outer = QSplitter(Qt.Horizontal)

        self.search_panel = SearchPanel()
        self.search_panel.search_requested.connect(self.run_search)
        self.search_panel.clear_requested.connect(self.clear_results)
        self.search_panel.setMinimumWidth(300)
        self.search_panel.setMaximumWidth(430)
        outer.addWidget(self.search_panel)

        inner = QSplitter(Qt.Vertical)

        self.plan_table = PlanTable()
        self.plan_table.selection_changed.connect(self.on_plan_selected)
        self.plan_table.plan_activated.connect(self.load_plan_detail)
        inner.addWidget(self.plan_table)

        self.detail_panel = PlanDetailPanel()
        self.detail_panel.export_requested.connect(self.export_evidence)
        self.detail_panel.provider_selected.connect(self.search_by_provider)
        inner.addWidget(self.detail_panel)

        inner.setSizes([420, 480])
        outer.addWidget(inner)
        outer.setSizes([380, 1120])

        search_layout.addWidget(outer)
        self.tabs.addTab(search_tab, "Find plans")

        # --- Providers tab --------------------------------------------
        self.provider_panel = ProviderPanel()
        self.provider_panel.search_requested.connect(self.run_provider_search)
        self.provider_panel.plans_requested.connect(self.search_by_provider)
        self.provider_panel.export_requested.connect(self.export_providers)
        self.tabs.addTab(self.provider_panel, "Providers")

        # --- Data tab -------------------------------------------------
        self.data_panel = DataManagerPanel()
        self.data_panel.sync_requested.connect(self.run_sync)
        self.data_panel.import_requested.connect(self.run_import)
        self.data_panel.cancel_requested.connect(self.cancel_data_task)
        self.data_panel.refresh_requested.connect(self.refresh_status)
        self.tabs.addTab(self.data_panel, "Data")

        self.setCentralWidget(self.tabs)

        status = QStatusBar()
        self.status_message = QLabel("Starting…")
        status.addWidget(self.status_message, 1)
        self.database_label = QLabel()
        status.addPermanentWidget(self.database_label)
        self.setStatusBar(status)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        export_csv = QAction("Export results to &CSV…", self)
        export_csv.setShortcut(QKeySequence("Ctrl+E"))
        export_csv.triggered.connect(self.export_results_csv)
        file_menu.addAction(export_csv)

        export_json = QAction("Export results to &JSON…", self)
        export_json.triggered.connect(self.export_results_json)
        file_menu.addAction(export_json)

        file_menu.addSeparator()

        open_folder = QAction("Open data &folder", self)
        open_folder.triggered.connect(self.open_data_folder)
        file_menu.addAction(open_folder)

        file_menu.addSeparator()

        quit_action = QAction("E&xit", self)
        quit_action.setShortcut(QKeySequence.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        search_menu = self.menuBar().addMenu("&Search")

        focus = QAction("&Focus search box", self)
        focus.setShortcut(QKeySequence("Ctrl+F"))
        focus.triggered.connect(self._focus_search)
        search_menu.addAction(focus)

        clear = QAction("&Clear filters", self)
        clear.triggered.connect(self.search_panel.clear)
        search_menu.addAction(clear)

        data_menu = self.menuBar().addMenu("&Data")

        refresh = QAction("&Refresh statistics", self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh_status)
        data_menu.addAction(refresh)

        rebuild = QAction("Rebuild &database…", self)
        rebuild.triggered.connect(self.rebuild_database)
        data_menu.addAction(rebuild)

        help_menu = self.menuBar().addMenu("&Help")

        about = QAction("&About", self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)

    # ------------------------------------------------------------------

    def _startup(self) -> None:
        try:
            version = initialize_database()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(
                self,
                "Database error",
                f"The local database could not be opened:\n\n{exc}\n\n"
                f"Location: {get_database_path()}",
            )
            self.status_message.setText("Database unavailable.")
            return

        self.database_label.setText(f"schema v{version}")
        self.refresh_status()
        self.run_provider_search(self.provider_panel.build_query())
        self._focus_search()

    def _focus_search(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.search_panel.focus()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def run_search(self, query: PlanQuery) -> None:
        if query.is_empty():
            self.clear_results()
            self.status_message.setText(
                "Type an employer, plan name or EIN, or set a filter, to search."
            )
            return

        self.status_message.setText("Searching…")

        options = QueryOptions(include_parties=True, include_filings=True, max_parties=60)

        self.search_runner.start(
            search_plans_task(query, options),
            on_finished=self._on_search_finished,
            on_failed=self._on_task_failed,
        )

    def _on_search_finished(self, payload: object) -> None:
        total, results = payload  # type: ignore[misc]

        self.plan_table.set_results(results)

        if not results:
            self.status_message.setText(
                "No plans matched. Check the Data tab to confirm a form year has been imported."
            )
            self.detail_panel.clear()
        else:
            shown = len(results)
            self.status_message.setText(
                f"{total:,} plan(s) matched"
                + (f"; showing the first {shown:,}." if total > shown else ".")
            )

    def clear_results(self) -> None:
        self.plan_table.set_results([])
        self.detail_panel.clear()
        self.status_message.setText("Ready.")

    def on_plan_selected(self, result: object) -> None:
        if result is None:
            self.detail_panel.clear()
            return

        # Show what the result row already carries immediately, then load the
        # full evidence in the background.
        self.detail_panel.set_summary(result)  # type: ignore[arg-type]
        self.load_plan_detail(result.plan_id)  # type: ignore[attr-defined]

    def load_plan_detail(self, plan_id: int) -> None:
        self.detail_runner.start(
            plan_detail_task(plan_id),
            on_finished=self._on_detail_finished,
            on_failed=self._on_task_failed,
        )

    def _on_detail_finished(self, payload: object) -> None:
        plan, evidence = payload  # type: ignore[misc]
        self.detail_panel.set_detail(plan, evidence)

    def search_by_provider(self, provider_name: str) -> None:
        self.tabs.setCurrentIndex(0)
        self.search_panel.set_provider(provider_name)

    # ------------------------------------------------------------------
    # Providers
    # ------------------------------------------------------------------

    def run_provider_search(self, query: ProviderQuery) -> None:
        self.provider_runner.start(
            search_providers_task(query),
            on_finished=lambda results: self.provider_panel.set_results(results),  # type: ignore[arg-type]
            on_failed=self._on_task_failed,
        )

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def run_sync(self, form_year: int, core_only: bool, force: bool) -> None:
        if self.data_runner.busy:
            QMessageBox.information(self, "Busy", "A data task is already running.")
            return

        self.data_panel.set_running(True)
        self.data_panel.append_log(f"Starting sync of form year {form_year}…")

        self.data_runner.start(
            sync_task(form_year, self.settings, core_only=core_only, force=force),
            on_finished=self._on_sync_finished,
            on_failed=self._on_data_failed,
            on_progress=self.data_panel.set_progress,
        )

    def run_import(self, directory: Path, form_year: int | None) -> None:
        if self.data_runner.busy:
            QMessageBox.information(self, "Busy", "A data task is already running.")
            return

        self.data_panel.set_running(True)
        self.data_panel.append_log(f"Importing from {directory}…")

        self.data_runner.start(
            import_task(directory, form_year, self.settings),
            on_finished=self._on_import_finished,
            on_failed=self._on_data_failed,
            on_progress=self.data_panel.set_progress,
        )

    def cancel_data_task(self) -> None:
        self.data_panel.append_log("Cancelling…")
        self.data_runner.cancel()

    def _on_sync_finished(self, report: object) -> None:
        self.data_panel.set_running(False)
        self.data_panel.append_log(report.summary())  # type: ignore[attr-defined]

        for outcome in report.failed:  # type: ignore[attr-defined]
            self.data_panel.append_log(f"FAILED {outcome.dataset}: {outcome.message}")

        self.refresh_status()
        self.run_provider_search(self.provider_panel.build_query())

    def _on_import_finished(self, stats: object) -> None:
        self.data_panel.set_running(False)
        self.data_panel.append_log(stats.summary())  # type: ignore[attr-defined]

        if stats.unmatched_ack_ids:  # type: ignore[attr-defined]
            self.data_panel.append_log(
                f"{stats.unmatched_ack_ids:,} schedule rows had no matching filing. "  # type: ignore[attr-defined]
                "Import the Form 5500 and 5500-SF files for the same year, then re-run."
            )

        for error in stats.errors[:10]:  # type: ignore[attr-defined]
            self.data_panel.append_log(error)

        from app.database.engine import get_engine
        from app.database.schema import rebuild_fts

        rebuild_fts(get_engine())

        self.refresh_status()
        self.run_provider_search(self.provider_panel.build_query())

    def _on_data_failed(self, message: str) -> None:
        self.data_panel.set_running(False)
        self.data_panel.append_log(message)

        if message != "Cancelled.":
            QMessageBox.warning(self, "Data task failed", message)

    def refresh_status(self) -> None:
        self.summary_runner.start(
            summary_task(),
            on_finished=self._on_summary_finished,
            on_failed=self._on_task_failed,
        )

        from app.database.session import read_session
        from app.services.sync import SyncService

        with read_session() as session:
            self.data_panel.set_datasets(SyncService(session).status())

    def _on_summary_finished(self, summary: object) -> None:
        if summary.is_empty:  # type: ignore[attr-defined]
            self.status_message.setText(
                "No data imported yet. Open the Data tab to download a form year "
                "from the Department of Labor."
            )
            return

        years = ", ".join(str(year) for year in summary.years)  # type: ignore[attr-defined]
        self.status_message.setText(
            f"{summary.plans:,} plans · {summary.providers:,} providers · "  # type: ignore[attr-defined]
            f"{summary.parties:,} provider engagements · years {years}"
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_results_csv(self) -> None:
        results = self.plan_table.results()

        if not results:
            QMessageBox.information(self, "Nothing to export", "Run a search first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export results", "plans.csv", "CSV files (*.csv)"
        )

        if path:
            written = export_service.export_plans_csv(results, Path(path))
            self.status_message.setText(f"Exported {len(results):,} plan(s) to {written}")

    def export_results_json(self) -> None:
        results = self.plan_table.results()

        if not results:
            QMessageBox.information(self, "Nothing to export", "Run a search first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export results", "plans.json", "JSON files (*.json)"
        )

        if path:
            written = export_service.export_plans_json(results, Path(path))
            self.status_message.setText(f"Exported {len(results):,} plan(s) to {written}")

    def export_providers(self) -> None:
        results = self.provider_panel.results()

        if not results:
            QMessageBox.information(self, "Nothing to export", "Run a provider search first.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export providers", "providers.csv", "CSV files (*.csv)"
        )

        if path:
            written = export_service.export_providers_csv(results, Path(path))
            self.status_message.setText(f"Exported {len(results):,} provider(s) to {written}")

    def export_evidence(self, plan_id: int) -> None:
        from app.database.session import read_session
        from app.evidence.trail import build_plan_evidence

        with read_session() as session:
            package = build_plan_evidence(session, plan_id)

        if package is None:
            QMessageBox.information(self, "Nothing to export", "That plan is no longer available.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export evidence report",
            f"evidence-{package.plan_key}.txt",
            "Text files (*.txt)",
        )

        if path:
            written = export_service.export_evidence_report(package, Path(path))
            self.status_message.setText(f"Wrote evidence report to {written}")

    # ------------------------------------------------------------------

    def open_data_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(get_app_data_dir())))

    def rebuild_database(self) -> None:
        confirm = QMessageBox.warning(
            self,
            "Rebuild database",
            "This deletes every plan, provider and filing imported so far and "
            "starts from an empty database.\n\n"
            "The Department of Labor source files are public and can be "
            "downloaded again, so nothing is permanently lost — but re-importing "
            "them takes as long as the original import did.\n\n"
            "Rebuild the database now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if confirm != QMessageBox.Yes:
            return

        for runner in (
            self.search_runner,
            self.detail_runner,
            self.provider_runner,
            self.data_runner,
            self.summary_runner,
        ):
            runner.stop()

        try:
            reset_database()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Rebuild failed", str(exc))
            return

        self.clear_results()
        self.provider_panel.set_results([])
        self.refresh_status()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About 401K Finder Pro",
            f"<h3>401K Finder Pro {__version__}</h3>"
            "<p>Searches U.S. Department of Labor Form 5500 filings to find "
            "retirement plans — 401(k), 403(b), 457(b), SEP and SIMPLE, ESOP, "
            "profit sharing, money purchase and defined benefit pensions — and "
            "the firms that hold and administer them.</p>"
            "<p>All data comes from EBSA's public Form 5500 datasets and is "
            "stored locally. Every result cites the dataset, field and row it "
            "came from.</p>"
            f"<p>Source: <a href='{DOL_DATASET_PAGE_URL}'>Form 5500 datasets</a></p>"
            f"<p>Data folder: {get_app_data_dir()}</p>",
        )

    def _on_task_failed(self, message: str) -> None:
        logger.error("Task failed: %s", message)
        self.status_message.setText(message)

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        if self.data_runner.busy:
            confirm = QMessageBox.question(
                self,
                "Data task running",
                "A download or import is still running. Stop it and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                event.ignore()
                return

        for runner in (
            self.search_runner,
            self.detail_runner,
            self.provider_runner,
            self.data_runner,
            self.summary_runner,
        ):
            runner.stop()

        self.settings.save()
        event.accept()
