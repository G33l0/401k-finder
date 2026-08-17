"""The data manager: download DOL years, import local files, see what is loaded."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import LATEST_FORM_YEAR, SOURCE_LABEL
from app.dol.catalog import CORE_DATASET_NAMES, dataset_names_for_year, supported_years


class DataManagerPanel(QWidget):
    """Controls for getting DOL data into the local database."""

    sync_requested = Signal(int, bool, bool)  # form_year, core_only, force
    import_requested = Signal(object, object)  # directory, form_year
    cancel_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._running = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        intro = QLabel(
            "This application works from the official public Form 5500 filings. "
            "Download a form year below, or import files you already have."
            f"<br><br>Source: <b>{SOURCE_LABEL}</b>"
        )
        intro.setWordWrap(True)
        intro.setOpenExternalLinks(True)
        intro.setTextFormat(Qt.RichText)
        layout.addWidget(intro)

        # --- Download -------------------------------------------------
        download = QGroupBox("Download a form year")
        download_layout = QVBoxLayout(download)

        row = QHBoxLayout()
        row.addWidget(QLabel("Form year:"))

        self.year_combo = QComboBox()
        for year in reversed(supported_years()):
            self.year_combo.addItem(str(year), year)
        default = self.year_combo.findData(LATEST_FORM_YEAR - 1)
        if default >= 0:
            self.year_combo.setCurrentIndex(default)
        self.year_combo.currentIndexChanged.connect(self._update_estimate)
        row.addWidget(self.year_combo)

        self.core_only = QCheckBox("Core datasets only")
        self.core_only.setChecked(True)
        self.core_only.setToolTip(
            "The core set carries every provider field: the two main forms plus "
            "Schedules A, C Part 1 Item 2, D Part 1, H, I, R, DCG and MEP. "
            "Unchecking downloads all published datasets, which is several times "
            "larger and adds little for provider research."
        )
        self.core_only.stateChanged.connect(self._update_estimate)
        row.addWidget(self.core_only)

        self.force = QCheckBox("Re-download")
        self.force.setToolTip("Fetch and re-import even datasets already marked complete.")
        row.addWidget(self.force)

        row.addStretch(1)

        self.sync_button = QPushButton("Download and import")
        self.sync_button.clicked.connect(self._on_sync)
        row.addWidget(self.sync_button)

        download_layout.addLayout(row)

        self.estimate_label = QLabel()
        self.estimate_label.setWordWrap(True)
        self.estimate_label.setProperty("role", "muted")
        download_layout.addWidget(self.estimate_label)

        layout.addWidget(download)

        # --- Local import ---------------------------------------------
        local = QGroupBox("Import files already on this computer")
        local_layout = QHBoxLayout(local)
        local_layout.addWidget(
            QLabel("Choose a folder of source CSV files, named as they are published.")
        )
        local_layout.addStretch(1)

        self.import_button = QPushButton("Choose folder…")
        self.import_button.clicked.connect(self._on_import)
        local_layout.addWidget(self.import_button)

        layout.addWidget(local)

        # --- Progress -------------------------------------------------
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel()
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.cancel_requested)
        layout.addWidget(self.cancel_button, alignment=Qt.AlignRight)

        # --- What is loaded -------------------------------------------
        loaded = QGroupBox("Imported datasets")
        loaded_layout = QVBoxLayout(loaded)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Year", "Dataset", "Release", "Status", "Rows"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        loaded_layout.addWidget(self.table)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_requested)
        loaded_layout.addWidget(refresh, alignment=Qt.AlignRight)

        layout.addWidget(loaded, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        self.log.setPlaceholderText("Import activity appears here.")
        layout.addWidget(self.log)

        self._update_estimate()

    # ------------------------------------------------------------------

    def _update_estimate(self) -> None:
        year = self.year_combo.currentData()
        available = set(dataset_names_for_year(year))

        if self.core_only.isChecked():
            count = len(available & set(CORE_DATASET_NAMES))
            note = (
                "The core set is typically a few gigabytes compressed and takes "
                "roughly 15–60 minutes to download and import."
            )
        else:
            count = len(available)
            note = (
                "The full set can exceed 10 GB compressed and take several hours. "
                "Most of the extra volume is actuarial and financial detail that "
                "carries no provider information."
            )

        self.estimate_label.setText(f"{count} dataset(s) will be fetched for {year}. {note}")

    def _on_sync(self) -> None:
        year = self.year_combo.currentData()

        confirm = QMessageBox.question(
            self,
            "Download data",
            f"Download and import form year {year} from the {SOURCE_LABEL}?\n\n"
            f"This transfers a large amount of data and can take a long time. "
            f"You can keep using the application while it runs, and cancel at any point.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if confirm == QMessageBox.Yes:
            self.sync_requested.emit(year, self.core_only.isChecked(), self.force.isChecked())

    def _on_import(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Choose a folder of source CSV files")
        if directory:
            self.import_requested.emit(Path(directory), None)

    # ------------------------------------------------------------------

    def set_running(self, running: bool) -> None:
        self._running = running

        self.sync_button.setEnabled(not running)
        self.import_button.setEnabled(not running)
        self.year_combo.setEnabled(not running)
        self.core_only.setEnabled(not running)
        self.force.setEnabled(not running)

        self.progress.setVisible(running)
        self.status_label.setVisible(running)
        self.cancel_button.setVisible(running)

        if not running:
            self.progress.setValue(0)

    def set_progress(self, done: int, total: int, message: str) -> None:
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(min(done, total))
        else:
            # Unknown length: show a busy indicator rather than a false 0%.
            self.progress.setRange(0, 0)

        self.status_label.setText(message)

    def append_log(self, message: str) -> None:
        self.log.append(message)

    def set_datasets(self, records) -> None:  # noqa: ANN001
        self.table.setRowCount(len(records))

        for row, record in enumerate(records):
            for column, value in enumerate(
                (
                    str(record.form_year),
                    record.dataset,
                    record.release,
                    record.status,
                    f"{record.rows_imported:,}",
                )
            ):
                item = QTableWidgetItem(value)
                if column == 3 and record.status == "FAILED" and record.error:
                    item.setToolTip(record.error)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
