"""The provider browser: which firms hold the most plans, and which plans."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import ProviderRole
from app.search.query import ProviderQuery
from app.ui.widgets.results_table import ProviderTable

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
    export_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        intro = QLabel(
            "Firms named across the imported filings, ranked by how many plans "
            "they serve. Double-click a provider to see its plans."
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

        self.table = ProviderTable()
        self.table.provider_activated.connect(
            lambda result: self.plans_requested.emit(result.display_name)
        )
        layout.addWidget(self.table, 1)

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
