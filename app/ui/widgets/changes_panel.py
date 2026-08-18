"""The "Provider changes" tab: which plans moved, and between whom."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import BLANK_CELL, US_STATES, ProviderRole, year_span
from app.dol.catalog import supported_years
from app.providers.changes import ChangeQuery, ChangeReport
from app.ui.widgets.results_table import format_count, format_money

COLUMNS = (
    "Plan",
    "Sponsor",
    "EIN / plan",
    "State",
    "Moved from",
    "Moved to",
    "Year",
    "Participants",
    "Assets",
)

ROLE_LABELS: tuple[tuple[str, str], ...] = (
    (ProviderRole.RECORDKEEPER.value, "Recordkeeper"),
    (ProviderRole.TRUSTEE.value, "Trustee"),
    (ProviderRole.CUSTODIAN.value, "Custodian"),
    (ProviderRole.INSURER.value, "Insurance carrier"),
    (ProviderRole.INVESTMENT_MANAGER.value, "Investment manager"),
    (ProviderRole.THIRD_PARTY_ADMIN.value, "Third-party administrator"),
    (ProviderRole.ACCOUNTANT.value, "Accountant / auditor"),
)


class ChangesPanel(QWidget):
    """Finds and shows plans that changed provider."""

    search_requested = Signal(object)
    export_requested = Signal(object)
    plan_selected = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._report: ChangeReport | None = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        intro = QLabel(
            "<b>Which plans changed provider, and to whom.</b><br>"
            "Compares each plan's filed provider from one year to the next. Needs "
            "at least two form years imported with the schedules that name "
            "providers."
        )
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        form.setLabelAlignment(Qt.AlignRight)

        self.role_combo = QComboBox()
        for value, label in ROLE_LABELS:
            self.role_combo.addItem(label, value)
        form.addRow("Role:", self.role_combo)

        self.from_input = QLineEdit()
        self.from_input.setPlaceholderText("e.g. Fidelity, to list plans that left this firm")
        self.from_input.returnPressed.connect(self._on_search)
        form.addRow("Moved away from:", self.from_input)

        self.to_input = QLineEdit()
        self.to_input.setPlaceholderText("e.g. Empower, to list plans that moved to this firm")
        self.to_input.returnPressed.connect(self._on_search)
        form.addRow("Moved to:", self.to_input)

        self.year_combo = QComboBox()
        self.year_combo.addItem("Any year", 0)
        for year in reversed(supported_years()):
            self.year_combo.addItem(str(year), year)
        form.addRow("Change landed in:", self.year_combo)

        self.state_combo = QComboBox()
        self.state_combo.addItem("Any state", "")
        for code in US_STATES:
            self.state_combo.addItem(code, code)
        form.addRow("State:", self.state_combo)

        self.min_participants = QSpinBox()
        self.min_participants.setRange(0, 10_000_000)
        self.min_participants.setSingleStep(100)
        self.min_participants.setSpecialValueText("No minimum")
        self.min_participants.setGroupSeparatorShown(True)
        form.addRow("Min participants:", self.min_participants)

        self.min_assets = QDoubleSpinBox()
        self.min_assets.setRange(0, 5_000_000_000)
        self.min_assets.setSingleStep(1_000_000)
        self.min_assets.setDecimals(0)
        self.min_assets.setSpecialValueText("No minimum")
        self.min_assets.setGroupSeparatorShown(True)
        self.min_assets.setPrefix("$")
        form.addRow("Min assets:", self.min_assets)

        layout.addWidget(filters)

        buttons = QHBoxLayout()

        self.search_button = QPushButton("Find changes")
        self.search_button.setDefault(True)
        self.search_button.clicked.connect(self._on_search)
        buttons.addWidget(self.search_button)

        buttons.addStretch(1)

        self.export_button = QPushButton("Export to CSV…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export)
        buttons.addWidget(self.export_button)

        layout.addLayout(buttons)

        self.summary = QLabel("No search run yet.")
        self.summary.setWordWrap(True)
        self.summary.setProperty("role", "muted")
        layout.addWidget(self.summary)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._on_activated)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for column in range(2, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

        layout.addWidget(self.table, 1)

        self.flows = QLabel()
        self.flows.setWordWrap(True)
        self.flows.setTextFormat(Qt.RichText)
        layout.addWidget(self.flows)

    def build_query(self) -> ChangeQuery:
        return ChangeQuery(
            role=self.role_combo.currentData(),
            year=self.year_combo.currentData() or None,
            from_provider=self.from_input.text().strip() or None,
            to_provider=self.to_input.text().strip() or None,
            state=self.state_combo.currentData() or None,
            min_participants=self.min_participants.value() or None,
            min_assets=self.min_assets.value() or None,
        )

    def _on_search(self) -> None:
        self.set_busy(True)
        self.search_requested.emit(self.build_query())

    def set_busy(self, busy: bool) -> None:
        self.search_button.setEnabled(not busy)
        self.search_button.setText("Searching…" if busy else "Find changes")

    def _on_export(self) -> None:
        if self._report is not None:
            self.export_requested.emit(self._report)

    def _on_activated(self, index) -> None:  # noqa: ANN001
        if self._report is None:
            return

        row = index.row()
        if 0 <= row < len(self._report.changes):
            self.plan_selected.emit(self._report.changes[row].plan_id)

    def changes(self) -> list:
        return list(self._report.changes) if self._report else []

    def show_report(self, report: ChangeReport) -> None:
        self._report = report
        self.set_busy(False)
        self.export_button.setEnabled(bool(report.changes))

        self._fill_table(report)
        self._fill_summary(report)
        self._fill_flows(report)

    def _fill_table(self, report: ChangeReport) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(report.changes))

        for row, change in enumerate(report.changes):
            values = (
                change.plan_name,
                change.sponsor_name or BLANK_CELL,
                change.plan_key,
                change.state or BLANK_CELL,
                change.from_provider or BLANK_CELL,
                change.to_provider or BLANK_CELL,
                f"{change.from_year} → {change.to_year}",
                format_count(change.participants),
                format_money(change.total_assets),
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (7, 8):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setToolTip(
                    f"Read from schedule {change.schedule_code or '?'}, "
                    f"field {change.source_field or '?'}"
                )
                self.table.setItem(row, column, item)

        self.table.setSortingEnabled(True)

    def _fill_summary(self, report: ChangeReport) -> None:
        if not report.years_compared:
            self.summary.setText(
                "Nothing to compare. Provider changes need at least two form years "
                "imported, with the schedules that name providers. Check the Data tab."
            )
            return

        span = year_span(report.years_compared[0], report.years_compared[-1])
        role = report.query.role.replace("_", " ").lower()

        if not report.changes:
            self.summary.setText(
                f"No {role} changes matched, across {span}. "
                f"Widen the filters, or import more form years."
            )
            return

        assets = sum(change.total_assets or 0.0 for change in report.changes)
        self.summary.setText(
            f"{len(report.changes):,} {role} change(s) across {span}, "
            f"covering {format_money(assets)} in plan assets. "
            f"Double-click a row to open the plan."
        )

    def _fill_flows(self, report: ChangeReport) -> None:
        flows = report.flows()

        if not flows:
            self.flows.clear()
            return

        rows = "".join(
            f"<li><b>{source}</b> → <b>{target}</b>: "
            f"{count} plan(s), {format_money(assets)}</li>"
            for source, target, count, assets in flows[:10]
        )
        self.flows.setText(f"<b>Where plans moved</b><ul>{rows}</ul>")

    def clear(self) -> None:
        self._report = None
        self.table.setRowCount(0)
        self.flows.clear()
        self.export_button.setEnabled(False)
        self.summary.setText("No search run yet.")
