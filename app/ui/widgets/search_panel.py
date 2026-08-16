"""The search form: a single query box plus the filters that matter most."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import PlanFeature, ProviderRole
from app.dol.catalog import supported_years
from app.search.query import PlanQuery, SortOrder

US_STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

#: The account types someone actually searches for, in the order they matter.
FEATURE_LABELS: tuple[tuple[str, str], ...] = (
    ("", "Any retirement account type"),
    (PlanFeature.K401.value, "401(k)"),
    (PlanFeature.B403.value, "403(b)"),
    (PlanFeature.B457.value, "457(b) deferred compensation"),
    (PlanFeature.SEP_SIMPLE_408.value, "SEP / SIMPLE (Code section 408)"),
    (PlanFeature.PROFIT_SHARING.value, "Profit sharing"),
    (PlanFeature.MONEY_PURCHASE.value, "Money purchase"),
    (PlanFeature.TARGET_BENEFIT.value, "Target benefit"),
    (PlanFeature.ESOP.value, "ESOP"),
    (PlanFeature.STOCK_BONUS.value, "Stock bonus"),
    (PlanFeature.PENSION_DB.value, "Defined benefit pension"),
    (PlanFeature.CASH_BALANCE.value, "Cash balance"),
    (PlanFeature.POOLED_EMPLOYER.value, "Pooled employer plan (PEP)"),
    (PlanFeature.MULTIEMPLOYER.value, "Multiemployer"),
    (PlanFeature.MULTIPLE_EMPLOYER.value, "Multiple employer"),
    (PlanFeature.PARTICIPANT_DIRECTED.value, "Participant-directed"),
)

ROLE_LABELS: tuple[tuple[str, str], ...] = (
    ("", "Any provider role"),
    (ProviderRole.RECORDKEEPER.value, "Recordkeeper"),
    (ProviderRole.TRUSTEE.value, "Trustee"),
    (ProviderRole.CUSTODIAN.value, "Custodian"),
    (ProviderRole.INSURER.value, "Insurance carrier"),
    (ProviderRole.INVESTMENT_MANAGER.value, "Investment manager"),
    (ProviderRole.INVESTMENT_ADVISOR.value, "Investment advisor"),
    (ProviderRole.THIRD_PARTY_ADMIN.value, "Third-party administrator"),
    (ProviderRole.ADMINISTRATOR.value, "Plan administrator"),
    (ProviderRole.ACCOUNTANT.value, "Accountant / auditor"),
    (ProviderRole.BROKER.value, "Broker"),
)

SORT_LABELS: tuple[tuple[SortOrder, str], ...] = (
    (SortOrder.RELEVANCE, "Best match"),
    (SortOrder.PARTICIPANTS, "Most participants"),
    (SortOrder.ASSETS, "Largest assets"),
    (SortOrder.PLAN_NAME, "Plan name"),
    (SortOrder.SPONSOR_NAME, "Sponsor name"),
    (SortOrder.YEAR, "Most recent filing"),
)


class SearchPanel(QWidget):
    """Collects search criteria and emits a PlanQuery."""

    search_requested = Signal(object)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Searching on every keystroke would queue a query per character, so
        # typing is debounced and only the last one runs.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._emit_search)

        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        prompt = QLabel(
            "Search by employer, plan name, or EIN. "
            "An EIN such as <b>12-3456789</b> or <b>12-3456789/001</b> "
            "goes straight to that plan."
        )
        prompt.setWordWrap(True)
        prompt.setTextFormat(Qt.RichText)
        layout.addWidget(prompt)

        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("e.g. Acme Manufacturing, or 12-3456789")
        self.query_input.setClearButtonEnabled(True)
        self.query_input.returnPressed.connect(self._emit_search)
        self.query_input.textChanged.connect(self._on_text_changed)
        row.addWidget(self.query_input, 1)

        self.search_button = QPushButton("Search")
        self.search_button.setDefault(True)
        self.search_button.clicked.connect(self._emit_search)
        row.addWidget(self.search_button)

        layout.addLayout(row)

        filters = QGroupBox("Filters")
        form = QFormLayout(filters)
        form.setLabelAlignment(Qt.AlignRight)

        self.feature_combo = QComboBox()
        for value, label in FEATURE_LABELS:
            self.feature_combo.addItem(label, value)
        form.addRow("Account type:", self.feature_combo)

        self.provider_input = QLineEdit()
        self.provider_input.setPlaceholderText("e.g. Fidelity, Empower, Principal")
        self.provider_input.returnPressed.connect(self._emit_search)
        form.addRow("Provider:", self.provider_input)

        self.role_combo = QComboBox()
        for value, label in ROLE_LABELS:
            self.role_combo.addItem(label, value)
        form.addRow("Provider role:", self.role_combo)

        self.state_combo = QComboBox()
        self.state_combo.addItem("Any state", "")
        for code in US_STATES:
            self.state_combo.addItem(code, code)
        form.addRow("State:", self.state_combo)

        self.year_combo = QComboBox()
        self.year_combo.addItem("Any year", 0)
        for year in reversed(supported_years()):
            self.year_combo.addItem(str(year), year)
        form.addRow("Form year:", self.year_combo)

        self.min_participants = QSpinBox()
        self.min_participants.setRange(0, 10_000_000)
        self.min_participants.setSingleStep(50)
        self.min_participants.setSpecialValueText("No minimum")
        self.min_participants.setGroupSeparatorShown(True)
        form.addRow("Min participants:", self.min_participants)

        self.min_assets = QSpinBox()
        self.min_assets.setRange(0, 2_000_000_000)
        self.min_assets.setSingleStep(1_000_000)
        self.min_assets.setSpecialValueText("No minimum")
        self.min_assets.setGroupSeparatorShown(True)
        self.min_assets.setPrefix("$")
        form.addRow("Min assets:", self.min_assets)

        self.sort_combo = QComboBox()
        for value, label in SORT_LABELS:
            self.sort_combo.addItem(label, value)
        form.addRow("Sort by:", self.sort_combo)

        # Short label, full explanation on hover: the panel is narrow, and the
        # long form was being clipped mid-word rather than wrapped.
        self.retirement_only = QCheckBox("Retirement plans only")
        self.retirement_only.setToolTip("Exclude health and welfare plans from results.")
        self.retirement_only.setChecked(True)
        form.addRow("", self.retirement_only)

        layout.addWidget(filters)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        clear = QPushButton("Clear filters")
        clear.clicked.connect(self.clear)
        buttons.addWidget(clear)
        layout.addLayout(buttons)

        layout.addStretch(1)

    # ------------------------------------------------------------------

    def _on_text_changed(self, text: str) -> None:
        # Two characters is too little to be worth a query against millions of
        # plans; below that, wait for an explicit Search.
        if len(text.strip()) >= 3 or not text.strip():
            self._debounce.start()

    def _emit_search(self) -> None:
        self._debounce.stop()
        self.search_requested.emit(self.build_query())

    def build_query(self, limit: int = 200) -> PlanQuery:
        feature = self.feature_combo.currentData()
        role = self.role_combo.currentData()
        state = self.state_combo.currentData()
        year = self.year_combo.currentData()

        return PlanQuery.parse(
            self.query_input.text(),
            state=state or None,
            form_years=(year,) if year else (),
            features=(feature,) if feature else (),
            roles=(role,) if role else (),
            provider_name=self.provider_input.text().strip() or None,
            min_participants=self.min_participants.value() or None,
            min_assets=float(self.min_assets.value()) or None,
            retirement_only=self.retirement_only.isChecked(),
            sort=self.sort_combo.currentData(),
            limit=limit,
        )

    def clear(self) -> None:
        self.query_input.clear()
        self.provider_input.clear()
        self.feature_combo.setCurrentIndex(0)
        self.role_combo.setCurrentIndex(0)
        self.state_combo.setCurrentIndex(0)
        self.year_combo.setCurrentIndex(0)
        self.min_participants.setValue(0)
        self.min_assets.setValue(0)
        self.sort_combo.setCurrentIndex(0)
        self.retirement_only.setChecked(True)
        self.clear_requested.emit()

    def set_provider(self, name: str) -> None:
        """Pre-fill the provider filter, used when drilling in from a provider."""

        self.provider_input.setText(name)
        self._emit_search()

    def focus(self) -> None:
        self.query_input.setFocus()
        self.query_input.selectAll()
