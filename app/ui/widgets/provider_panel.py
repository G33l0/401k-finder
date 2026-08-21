"""The provider browser: which firms hold the most plans, and which plans."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import BLANK_CELL, ProviderRole, year_span
from app.providers.directory import DISCLAIMER as DIRECTORY_DISCLAIMER
from app.providers.directory import contact_for
from app.search.query import ProviderQuery
from app.ui import theme
from app.ui.widgets.results_table import ProviderTable, format_count, format_money

ROLE_CHOICES: tuple[tuple[str, str], ...] = (
    ("", "All roles"),
    (ProviderRole.RECORDKEEPER.value, "Recordkeepers"),
    (ProviderRole.TRUSTEE.value, "Trustees"),
    (ProviderRole.CUSTODIAN.value, "Custodians"),
    (ProviderRole.INSURER.value, "Insurance carriers"),
    (ProviderRole.INVESTMENT_MANAGER.value, "Investment managers"),
    (ProviderRole.INVESTMENT_ADVISOR.value, "Investment advisors"),
    (ProviderRole.THIRD_PARTY_ADMIN.value, "Third-party administrators"),
    (ProviderRole.ADMINISTRATOR.value, "Plan administrators"),
    (ProviderRole.ACCOUNTANT.value, "Accountants and auditors"),
    (ProviderRole.BROKER.value, "Brokers"),
    (ProviderRole.INVESTMENT_VEHICLE.value, "Investment vehicles"),
)

COMPANY_COLUMNS: tuple[tuple[str, int], ...] = (
    ("Company", 230),
    ("Plan", 300),
    ("State", 60),
    ("Role", 190),
    ("Years", 100),
    ("Participants", 100),
    ("Assets", 100),
)


def _title(value: str) -> str:
    return value.replace("_", " ").title()


SORT_CHOICES: tuple[tuple[str, str], ...] = (
    ("plans", "Most plans"),
    ("assets", "Largest assets"),
    ("participants", "Most participants"),
    ("name", "Name"),
)


class ProviderPanel(QWidget):
    """Search and browse providers, and jump to the plans they serve."""

    search_requested = Signal(object)
    plans_requested = Signal(str)
    companies_requested = Signal(str)
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.selected_provider = ""
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        intro = QLabel(
            "Firms named across the imported filings, ranked by how many plans "
            "they serve. Select one to list every company that uses it."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Provider name…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._emit_search)
        controls.addWidget(self.search_input, 1)

        self.role_combo = QComboBox()
        for value, label in ROLE_CHOICES:
            self.role_combo.addItem(label, value)
        self.role_combo.currentIndexChanged.connect(self._emit_search)
        controls.addWidget(self.role_combo)

        self.sort_combo = QComboBox()
        for value, label in SORT_CHOICES:
            self.sort_combo.addItem(label, value)
        self.sort_combo.currentIndexChanged.connect(self._emit_search)
        controls.addWidget(self.sort_combo)

        controls.addWidget(QLabel("Min plans:"))
        self.min_plans = QSpinBox()
        self.min_plans.setRange(0, 1_000_000)
        self.min_plans.setSpecialValueText("Any")
        self.min_plans.setSingleStep(5)
        controls.addWidget(self.min_plans)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self._emit_search)
        controls.addWidget(search_button)

        layout.addLayout(controls)

        split = QSplitter(Qt.Vertical)

        self.table = ProviderTable()
        self.table.provider_activated.connect(
            lambda result: self.plans_requested.emit(result.display_name)
        )
        self.table.selection_changed.connect(self._on_provider_selected)
        split.addWidget(self.table)

        split.addWidget(self._build_companies())
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 4)
        layout.addWidget(split, 1)

        footer = QHBoxLayout()
        self.count_label = QLabel()
        self.count_label.setProperty("role", "muted")
        footer.addWidget(self.count_label)
        footer.addStretch(1)

        plans_button = QPushButton("Show this provider's plans")
        plans_button.clicked.connect(self._on_show_plans)
        footer.addWidget(plans_button)

        export_button = QPushButton("Export to CSV…")
        export_button.clicked.connect(self.export_requested)
        footer.addWidget(export_button)

        layout.addLayout(footer)

    def _build_companies(self) -> QWidget:
        """Every company using the selected provider, with contact details."""

        panel = QWidget()
        column = QVBoxLayout(panel)
        column.setContentsMargins(0, 8, 0, 0)

        self.companies_heading = QLabel("Companies using this provider")
        self.companies_heading.setProperty("role", "heading")
        column.addWidget(self.companies_heading)

        self.contact_label = QLabel()
        self.contact_label.setWordWrap(True)
        self.contact_label.setTextFormat(Qt.RichText)
        self.contact_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.contact_label.setVisible(False)
        column.addWidget(self.contact_label)

        self.companies_table = QTableWidget(0, len(COMPANY_COLUMNS))
        self.companies_table.setHorizontalHeaderLabels([name for name, _ in COMPANY_COLUMNS])
        self.companies_table.verticalHeader().setVisible(False)
        self.companies_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.companies_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.companies_table.setAlternatingRowColors(True)
        for index, (_, width) in enumerate(COMPANY_COLUMNS):
            self.companies_table.setColumnWidth(index, width)
        self.companies_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        column.addWidget(self.companies_table, 1)

        self.companies_note = QLabel("Select a provider above.")
        self.companies_note.setProperty("role", "muted")
        self.companies_note.setWordWrap(True)
        column.addWidget(self.companies_note)

        return panel

    def _on_provider_selected(self, result) -> None:  # noqa: ANN001 - ProviderResult
        if result is None:
            self.selected_provider = ""
            self.companies_heading.setText("Companies using this provider")
            self.contact_label.setVisible(False)
            self.companies_table.setRowCount(0)
            self.companies_note.setText("Select a provider above.")
            return

        name = result.display_name
        self.selected_provider = name
        self.companies_heading.setText(f"Companies using {name}")
        self._show_contact(name)
        self.companies_table.setRowCount(0)
        self.companies_note.setText("Looking…")
        self.companies_requested.emit(name)

    def _show_contact(self, name: str) -> None:
        contact = contact_for(name)

        if contact is None or not contact.has_details:
            self.contact_label.setVisible(False)
            return

        palette = theme.current()
        parts = []
        if contact.phone:
            parts.append(f"Telephone: <b>{contact.phone}</b>")
        if contact.website:
            parts.append(f"Website: <b>{contact.website}</b>")

        extra = ""
        if contact.successor:
            extra = f"<br><b>{contact.successor}</b>"
        elif contact.note:
            extra = f"<br>{contact.note}"

        self.contact_label.setText(
            f"{' &nbsp;·&nbsp; '.join(parts)}{extra}"
            f"<br><span style='color:{palette.text_faint}'>{DIRECTORY_DISCLAIMER}</span>"
        )
        self.contact_label.setVisible(True)

    def set_companies(self, provider_name: str, results) -> None:  # noqa: ANN001
        """Fill the lower pane, ignoring a reply for a provider no longer selected."""

        if provider_name != getattr(self, "selected_provider", ""):
            return

        self.companies_table.setRowCount(len(results))

        for row, plan in enumerate(results):
            mine = [
                party
                for party in plan.parties
                if party.display_name == provider_name
            ]
            roles = sorted({_title(party.role) for party in mine})
            years = sorted({party.form_year for party in mine})

            values = (
                plan.sponsor_name or BLANK_CELL,
                plan.plan_name,
                plan.state or BLANK_CELL,
                ", ".join(roles) or BLANK_CELL,
                year_span(years[0], years[-1]) if years else BLANK_CELL,
                format_count(plan.participants),
                format_money(plan.total_assets),
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (5, 6):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.companies_table.setItem(row, column, item)

        if results:
            self.companies_note.setText(
                f"{len(results):,} plan(s) name {provider_name} in the form years imported. "
                f"Double-click the provider above to open these in Find plans."
            )
        else:
            self.companies_note.setText(
                f"No plan in the imported form years names {provider_name}. "
                f"Import more years from the Data tab to widen the search."
            )

    def _emit_search(self) -> None:
        self.search_requested.emit(self.build_query())

    def build_query(self) -> ProviderQuery:
        return ProviderQuery(
            text=self.search_input.text().strip(),
            role=self.role_combo.currentData() or None,
            min_plans=self.min_plans.value() or None,
            sort=self.sort_combo.currentData(),
            limit=500,
        )

    def _on_show_plans(self) -> None:
        result = self.table.current_result()
        if result is not None:
            self.plans_requested.emit(result.display_name)

    def set_results(self, results) -> None:  # noqa: ANN001
        self.table.set_results(results)
        self.count_label.setText(f"{len(results):,} provider(s)")

    def results(self):
        return self.table.results()
