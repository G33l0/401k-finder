"""Result tables for plans and providers."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView, QWidget

from app.core.constants import BLANK_CELL, year_span
from app.providers.directory import DISCLAIMER as DIRECTORY_DISCLAIMER
from app.providers.servicing import ServicingHistory, servicing_history
from app.search.engine import PlanResult, ProviderResult


def format_money(value: float | None) -> str:
    if value is None:
        return BLANK_CELL
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:,.0f}K"
    return f"${value:,.0f}"


def format_count(value: int | None) -> str:
    return BLANK_CELL if value is None else f"{value:,}"


def _title(role: str) -> str:
    return role.replace("_", " ").title()


class PlanTableModel(QAbstractTableModel):
    """Presents plan results, with the providers folded into columns."""

    COLUMNS = (
        ("Plan", 280),
        ("Sponsor", 200),
        ("EIN / PN", 115),
        ("State", 55),
        ("Type", 130),
        ("Recordkeeper", 190),
        ("Trustee / Custodian", 190),
        ("Service providers by year", 300),
        ("Contact", 180),
        ("Participants", 95),
        ("Assets", 95),
        ("Years", 85),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[PlanResult] = []
        self._servicing: dict[int, ServicingHistory] = {}

    def set_results(self, results: list[PlanResult]) -> None:
        self.beginResetModel()
        self._results = results
        self._servicing.clear()
        self.endResetModel()

    def servicing(self, result: PlanResult) -> ServicingHistory:
        """Folded once per plan; data() is called for every cell and repaint."""

        history = self._servicing.get(result.plan_id)
        if history is None:
            history = servicing_history(result.parties)
            self._servicing[result.plan_id] = history
        return history

    def result_at(self, row: int) -> PlanResult | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self.COLUMNS[section][0]

    def _providers(self, result: PlanResult, *roles: str) -> str:
        """The firms in these roles, each with the years it was filed for."""

        entries = [item for item in self.servicing(result) if item.role in roles]
        return ", ".join(item.summary() for item in entries) if entries else BLANK_CELL

    def _contact(self, result: PlanResult) -> str:
        """Where to reach whoever is most likely to hold the money."""

        best = self.servicing(result).best_contact()
        if best is None or best.contact is None:
            return BLANK_CELL

        parts = [best.contact.phone, best.contact.website]
        return "  ".join(part for part in parts if part) or BLANK_CELL

    def _servicing_tooltip(self, result: PlanResult) -> str:
        """Every firm, its years, and how to reach it."""

        history = self.servicing(result)
        if not len(history):
            return "No service provider is named in the filings held for this plan."

        lines = [f"{result.plan_name}", ""]

        for item in history:
            marker = "*" if item.holds_money else " "
            lines.append(f"{marker} {item.role_label}: {item.name}  [{item.span}]")

            if item.contact is not None:
                if item.contact.phone:
                    lines.append(f"      Telephone: {item.contact.phone}")
                if item.contact.website:
                    lines.append(f"      Website:   {item.contact.website}")
                if item.contact.successor:
                    lines.append(f"      Note:      {item.contact.successor}")

        lines.append("")
        lines.append("* holds or administers the money, so worth contacting first.")
        lines.append(DIRECTORY_DISCLAIMER)

        return "\n".join(lines)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        result = self._results[index.row()]
        column = index.column()

        if role == Qt.DisplayRole:
            match column:
                case 0:
                    return result.plan_name
                case 1:
                    return result.sponsor_name or BLANK_CELL
                case 2:
                    return result.plan_key
                case 3:
                    return result.state or BLANK_CELL
                case 4:
                    return ", ".join(
                        feature.replace("_", " ").title() for feature in result.features[:3]
                    ) or (result.plan_category or BLANK_CELL).replace("_", " ").title()
                case 5:
                    return self._providers(result, "RECORDKEEPER")
                case 6:
                    return self._providers(result, "TRUSTEE", "CUSTODIAN", "TRUST")
                case 7:
                    return self.servicing(result).column_text(limit=4) or BLANK_CELL
                case 8:
                    return self._contact(result)
                case 9:
                    return format_count(result.participants)
                case 10:
                    return format_money(result.total_assets)
                case 11:
                    return year_span(result.first_year, result.last_year)

        elif role == Qt.TextAlignmentRole and column in (9, 10):
            return int(Qt.AlignRight | Qt.AlignVCenter)

        elif role == Qt.FontRole and column == 0:
            font = QFont()
            font.setBold(True)
            return font

        elif role == Qt.ToolTipRole:
            if column in (5, 6, 7, 8):
                return self._servicing_tooltip(result)

            lines = [result.plan_name, f"Sponsor: {result.sponsor_name or 'unknown'}"]
            if result.features:
                lines.append("Type: " + ", ".join(result.features))
            if result.benefit_codes:
                lines.append("Filed codes: " + ", ".join(result.benefit_codes))
            for party in result.primary_providers()[:8]:
                lines.append(f"{_title(party.role)}: {party.display_name}")
            return "\n".join(lines)

        return None


class PlanTable(QTableView):
    """Plan results table."""

    plan_activated = Signal(int)
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model = PlanTableModel(self)
        self.setModel(self._model)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.setWordWrap(False)

        for index, (_, width) in enumerate(PlanTableModel.COLUMNS):
            self.setColumnWidth(index, width)

        self.doubleClicked.connect(self._on_double_click)

    def set_results(self, results: list[PlanResult]) -> None:
        self._model.set_results(results)
        if results:
            self.selectRow(0)
            self.selection_changed.emit(results[0])
        else:
            self.selection_changed.emit(None)

    def current_result(self) -> PlanResult | None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.result_at(indexes[0].row())

    def selectionChanged(self, selected, deselected) -> None:  # noqa: ANN001, N802
        super().selectionChanged(selected, deselected)
        self.selection_changed.emit(self.current_result())

    def _on_double_click(self, index: QModelIndex) -> None:
        result = self._model.result_at(index.row())
        if result is not None:
            self.plan_activated.emit(result.plan_id)

    def results(self) -> list[PlanResult]:
        return list(self._model._results)  # noqa: SLF001 - same module contract


class ProviderTableModel(QAbstractTableModel):
    COLUMNS = (
        ("Provider", 320),
        ("Primary role", 190),
        ("State", 60),
        ("Plans", 90),
        ("Participants", 120),
        ("Assets under administration", 200),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[ProviderResult] = []

    def set_results(self, results: list[ProviderResult]) -> None:
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def result_at(self, row: int) -> ProviderResult | None:
        if 0 <= row < len(self._results):
            return self._results[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._results)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        return self.COLUMNS[section][0]

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        result = self._results[index.row()]

        if role == Qt.DisplayRole:
            match index.column():
                case 0:
                    return result.display_name
                case 1:
                    return _title(result.primary_role or BLANK_CELL)
                case 2:
                    return result.state or BLANK_CELL
                case 3:
                    return f"{result.plan_count:,}"
                case 4:
                    return f"{result.participant_count:,}"
                case 5:
                    return format_money(result.assets_under_administration)

        elif role == Qt.TextAlignmentRole and index.column() in (3, 4, 5):
            return int(Qt.AlignRight | Qt.AlignVCenter)

        elif role == Qt.ToolTipRole and result.canonical_name:
            return f"Filed name: {result.name}"

        return None


class ProviderTable(QTableView):
    """Provider results table."""

    provider_activated = Signal(object)
    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._model = ProviderTableModel(self)
        self.setModel(self._model)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)

        for index, (_, width) in enumerate(ProviderTableModel.COLUMNS):
            self.setColumnWidth(index, width)

        self.doubleClicked.connect(self._on_double_click)

    def set_results(self, results: list[ProviderResult]) -> None:
        self._model.set_results(results)
        self.selection_changed.emit(None)

    def results(self) -> list[ProviderResult]:
        return list(self._model._results)  # noqa: SLF001

    def current_result(self) -> ProviderResult | None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._model.result_at(indexes[0].row())

    def _on_double_click(self, index: QModelIndex) -> None:
        result = self._model.result_at(index.row())
        if result is not None:
            self.provider_activated.emit(result)

    def selectionChanged(self, selected, deselected) -> None:  # noqa: ANN001, N802
        super().selectionChanged(selected, deselected)
        self.selection_changed.emit(self.current_result())
