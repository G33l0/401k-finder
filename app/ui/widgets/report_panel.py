"""Search by company name and read the whole plan history back."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import SOURCE_LABEL, US_STATES
from app.reports import PLAN_TYPES, EmployerQuery
from app.ui import theme


class ReportPanel(QWidget):
    """The company report: a name in, a plan history out."""

    report_requested = Signal(object)
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._report = None
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        intro = QLabel(
            "<b>Type a company name. Nothing else is required.</b><br>"
            "Every form year held on this computer is searched, the plans are "
            "grouped by type, and each one gets a timeline of who kept the "
            "records and when that changed."
            f"<br><span style='font-size:9pt'>Source: <b>{SOURCE_LABEL}</b></span>"
        )
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()

        self.company_input = QLineEdit()
        self.company_input.setPlaceholderText("e.g. Acme Manufacturing Inc")
        self.company_input.setClearButtonEnabled(True)
        self.company_input.returnPressed.connect(self._emit)
        row.addWidget(self.company_input, 3)

        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("City (optional)")
        self.city_input.returnPressed.connect(self._emit)
        row.addWidget(self.city_input, 1)

        self.state_combo = QComboBox()
        self.state_combo.addItem("Any state", "")
        for code in US_STATES:
            self.state_combo.addItem(code, code)
        row.addWidget(self.state_combo)

        self.type_combo = QComboBox()
        self.type_combo.addItem("All plan types", "")
        for plan_type in PLAN_TYPES:
            self.type_combo.addItem(plan_type.label, plan_type.key)
        row.addWidget(self.type_combo)

        self.run_button = QPushButton("Build report")
        self.run_button.clicked.connect(self._emit)
        row.addWidget(self.run_button)

        layout.addLayout(row)

        options = QHBoxLayout()

        self.annual = QCheckBox("Every year, not periods")
        self.annual.setToolTip(
            "List each form year separately instead of folding runs of identical "
            "years into one period."
        )
        options.addWidget(self.annual)

        self.investments = QCheckBox("Include investments")
        self.investments.setToolTip(
            "Also list funds, collective trusts and investment managers. These are "
            "never the plan's recordkeeper and are left out by default."
        )
        options.addWidget(self.investments)

        options.addStretch(1)

        self.export_button = QPushButton("Save report…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_requested)
        options.addWidget(self.export_button)

        layout.addLayout(options)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        layout.addWidget(self.view, 1)

        self.status = QLabel()
        self.status.setProperty("role", "muted")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.retheme()

    def build_query(self) -> EmployerQuery:
        return EmployerQuery(
            name=self.company_input.text().strip(),
            city=self.city_input.text().strip() or None,
            state=self.state_combo.currentData() or None,
            plan_type=self.type_combo.currentData() or None,
            annual_detail=self.annual.isChecked(),
            include_investments=self.investments.isChecked(),
        )

    def _emit(self) -> None:
        query = self.build_query()

        if not query.name:
            self.status.setText("Type a company name first.")
            return

        self.set_busy(True)
        self.report_requested.emit(query)

    def set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.run_button.setText("Building…" if busy else "Build report")
        if busy:
            self.status.setText("Searching every form year held here…")

    def retheme(self) -> None:
        palette = theme.current()
        self.view.setStyleSheet(
            f"QTextBrowser {{ font-family: {palette.mono_family}; font-size: 10pt; }}"
        )

    def show_report(self, report, text: str) -> None:  # noqa: ANN001 - EmployerReport
        self._report = report
        self.view.setPlainText(text)
        self.view.verticalScrollBar().setValue(0)
        self.set_busy(False)

        # Only a real result is worth saving. A file named "report" that says
        # nothing was found is the sort of thing somebody keeps by mistake.
        self.export_button.setEnabled(bool(report is not None and report.found))

        if report is None or not report.found:
            self.status.setText("Nothing matched. The report explains what to try next.")
            return

        plans = len(report.plans)
        types = len(report.by_type())
        span = (
            f"{report.years_held[0]}-{report.years_held[-1]}" if report.years_held else "no years"
        )
        self.status.setText(
            f"{plans} plan(s) across {types} plan type(s), form years {span}."
        )

    def report_text(self) -> str:
        return self.view.toPlainText()

    def report(self):  # noqa: ANN201
        return self._report

    def set_failed(self, message: str) -> None:
        self.set_busy(False)
        self.status.setText(message)
