"""
The window's calls into the background runner.

Three features shipped broken: Index every year, Provider changes and Find my
accounts each called ``TaskRunner.run(on_result=..., on_error=...)``. There is
no such method and there are no such arguments; the real ones are ``start``,
``on_finished`` and ``on_failed``. Clicking any of the three raised
AttributeError and the tab did nothing. Nothing caught it, because no test
drove the window and Python resolves an attribute only when the line runs.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.ui import workers
from app.ui.workers import TaskRunner

WINDOW = Path(workers.__file__).parent / "windows" / "main_window.py"


def _runner_calls() -> list[ast.Call]:
    """Every ``self.<something>_runner.<method>(...)`` in the window."""

    tree = ast.parse(WINDOW.read_text(encoding="utf-8"))
    found = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        target = node.func.value
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and target.attr.endswith("_runner")
        ):
            found.append(node)

    return found


def test_the_window_actually_calls_the_runner():
    assert len(_runner_calls()) >= 6


def test_every_runner_call_names_a_method_that_exists():
    for call in _runner_calls():
        method = call.func.attr
        assert hasattr(TaskRunner, method), (
            f"main_window.py:{call.lineno} calls TaskRunner.{method}(), "
            f"which does not exist"
        )


def test_every_runner_call_uses_arguments_that_exist():
    for call in _runner_calls():
        method = getattr(TaskRunner, call.func.attr, None)
        if method is None:
            continue

        accepted = set(inspect.signature(method).parameters)
        for keyword in call.keywords:
            if keyword.arg is None:
                continue
            assert keyword.arg in accepted, (
                f"main_window.py:{call.lineno} passes {keyword.arg}= to "
                f"TaskRunner.{call.func.attr}(), which takes {sorted(accepted - {'self'})}"
            )


def test_every_runner_call_supplies_the_required_arguments():
    for call in _runner_calls():
        method = getattr(TaskRunner, call.func.attr, None)
        if method is None:
            continue

        signature = inspect.signature(method)
        supplied = {keyword.arg for keyword in call.keywords} | {
            name
            for name, _ in zip(
                [p for p in signature.parameters if p != "self"],
                call.args,
                strict=False,
            )
        }
        required = {
            name
            for name, parameter in signature.parameters.items()
            if name != "self" and parameter.default is inspect.Parameter.empty
        }
        missing = required - supplied
        assert not missing, (
            f"main_window.py:{call.lineno} calls TaskRunner.{call.func.attr}() "
            f"without {sorted(missing)}"
        )


@pytest.mark.parametrize("name", ["start", "cancel", "stop", "shutdown", "busy"])
def test_the_runner_still_offers_what_the_window_expects(name):
    """If one of these is renamed, rename it at the call sites in the same commit."""

    assert hasattr(TaskRunner, name)


# ----------------------------------------------------------------------
# Driving the real tabs
# ----------------------------------------------------------------------



@pytest.fixture()
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication

    yield QApplication.instance() or QApplication([])


@pytest.fixture()
def window(qt_app, imported, monkeypatch):
    """A real window over the imported test data, with modal boxes silenced."""

    from PySide6.QtWidgets import QMessageBox

    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(
            QMessageBox, name, staticmethod(lambda *a, **k: QMessageBox.StandardButton.No)
        )

    from app.core.config import Settings
    from app.ui.windows.main_window import MainWindow

    built = MainWindow(Settings())
    settle(qt_app, built)

    yield built

    built.close()


def settle(app, window, seconds: float = 20.0) -> None:
    """Wait for every runner the window owns, not a list that can drift."""

    import time

    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        if not any(runner.busy for runner in window._runners()):
            break
        time.sleep(0.005)

    for _ in range(20):
        app.processEvents()


def test_find_my_accounts_produces_a_report(qt_app, window):
    """Clicking this raised AttributeError and left the panel blank."""

    from PySide6.QtWidgets import QTableWidgetItem

    window.trace_panel.table.setItem(0, 0, QTableWidgetItem("ACME MANUFACTURING"))
    window.trace_panel._on_trace()
    settle(qt_app, window)

    report = window.trace_panel.results.toPlainText()

    assert "ACME" in report.upper()
    assert "plan(s) found" in window.status_message.text()


def test_provider_changes_produces_a_report(qt_app, window):
    """Same fault, same silence."""

    window.changes_panel._on_search()
    settle(qt_app, window)

    assert window.changes_panel.summary.text()
    assert "change(s)" in window.status_message.text()


def test_a_plain_search_still_fills_the_table(qt_app, window):
    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    assert window.plan_table.model().rowCount() > 0


def test_selecting_a_result_loads_its_detail(qt_app, window):
    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    window.plan_table.selectRow(0)
    settle(qt_app, window)

    assert window.detail_panel.tabs.count() > 0


# ----------------------------------------------------------------------
# Exports
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("suggested", "expected"),
    [
        ("plans.csv", ".csv"),
        ("plans.json", ".json"),
        ("evidence-12-3456789-001.txt", ".txt"),
    ],
)
def test_a_typed_filename_keeps_its_extension(
    qt_app, window, monkeypatch, tmp_path, suggested, expected
):
    """
    Qt only appends the filter's suffix on some platforms. Somebody who typed
    "acme plans" over the suggested name got a file Windows would not open.
    """

    from PySide6.QtWidgets import QFileDialog

    typed = tmp_path / "acme plans"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(typed), ""))
    )

    chosen = window._ask_where_to_save("Export", suggested, "Any (*)")

    assert chosen is not None
    assert chosen.suffix == expected
    assert chosen.stem == "acme plans"


def test_an_extension_the_user_typed_is_respected(qt_app, window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    typed = tmp_path / "acme.tsv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(typed), ""))
    )

    assert window._ask_where_to_save("Export", "plans.csv", "Any (*)").suffix == ".tsv"


def test_cancelling_the_save_dialog_exports_nothing(qt_app, window, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))

    assert window._ask_where_to_save("Export", "plans.csv", "Any (*)") is None


def test_every_export_writes_a_readable_file(qt_app, window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    destination = tmp_path / "exports"
    destination.mkdir()
    written: list = []

    def save(*_a, **_k):
        target = destination / f"export-{len(written)}"
        written.append(target)
        return (str(target), "")

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(save))

    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    window.export_results_csv()
    window.export_results_json()

    produced = sorted(destination.iterdir())
    assert len(produced) == 2
    for path in produced:
        assert path.stat().st_size > 0
        assert path.suffix in {".csv", ".json"}
        path.read_text(encoding="utf-8-sig")


# ----------------------------------------------------------------------
# Service providers, and the companies that use them
# ----------------------------------------------------------------------


def test_the_plan_table_shows_providers_with_their_years(qt_app, window):
    """The point of the column: who held the money, and when."""

    from PySide6.QtCore import Qt

    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    model = window.plan_table.model()
    headers = [model.COLUMNS[i][0] for i in range(model.columnCount())]

    assert "Service providers by year" in headers
    assert "Contact" in headers

    column = headers.index("Service providers by year")
    texts = [
        model.data(model.index(row, column), Qt.DisplayRole) for row in range(model.rowCount())
    ]

    assert texts, "the search should have matched something"
    assert any("(" in text and ")" in text for text in texts), texts


def test_the_table_offers_a_contact_for_a_known_recordkeeper(qt_app, window):
    from PySide6.QtCore import Qt

    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    model = window.plan_table.model()
    headers = [model.COLUMNS[i][0] for i in range(model.columnCount())]
    column = headers.index("Contact")

    contacts = [
        model.data(model.index(row, column), Qt.DisplayRole) for row in range(model.rowCount())
    ]

    assert any("http" in (text or "") for text in contacts), contacts


def test_the_provider_tooltip_carries_the_disclaimer(qt_app, window):
    """Contact details the application added must never look like filed data."""

    from PySide6.QtCore import Qt

    from app.providers.directory import DISCLAIMER

    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)

    model = window.plan_table.model()
    tooltip = model.data(model.index(0, 7), Qt.ToolTipRole)

    assert DISCLAIMER in tooltip
    assert "holds or administers the money" in tooltip


def test_the_detail_panel_lists_the_years_each_firm_covered(qt_app, window):
    window.search_panel.query_input.setText("acme")
    window.search_panel._emit_search()
    settle(qt_app, window)
    window.plan_table.selectRow(0)
    settle(qt_app, window)

    text = window.detail_panel.providers.toPlainText()

    assert "Filed for:" in text
    assert "Telephone:" in text
    assert "Website:" in text


def test_selecting_a_provider_lists_every_company_using_it(qt_app, window):
    """The Providers tab answers this without leaving the tab."""

    window.provider_panel.search_input.setText("reliance")
    window.provider_panel._emit_search()
    settle(qt_app, window)

    assert window.provider_panel.table.model().rowCount() > 0

    window.provider_panel.table.selectRow(0)
    settle(qt_app, window)

    table = window.provider_panel.companies_table
    assert table.rowCount() > 0, window.provider_panel.companies_note.text()

    headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
    assert headers[:2] == ["Company", "Plan"]
    assert "Years" in headers

    companies = {table.item(row, 0).text() for row in range(table.rowCount())}
    assert len(companies) >= 1
    assert all(table.item(row, 4).text() for row in range(table.rowCount()))


def test_clearing_the_provider_search_clears_the_companies(qt_app, window):
    """A stale company list under a new search would be read as a result."""

    window.provider_panel.search_input.setText("reliance")
    window.provider_panel._emit_search()
    settle(qt_app, window)
    window.provider_panel.table.selectRow(0)
    settle(qt_app, window)

    assert window.provider_panel.companies_table.rowCount() > 0

    window.provider_panel.search_input.setText("nothing matches this")
    window.provider_panel._emit_search()
    settle(qt_app, window)

    assert window.provider_panel.companies_table.rowCount() == 0


def test_a_late_reply_for_another_provider_is_ignored(qt_app, window):
    """Selecting quickly must not leave one provider's plans under another's name."""

    from app.search.engine import PlanResult

    window.provider_panel.selected_provider = "Empower"
    stale = [
        PlanResult(
            plan_id=1, plan_name="STALE PLAN", sponsor_name="STALE CO", ein="1", plan_number="1",
            city=None, state=None, plan_category=None, features=(), benefit_codes=(),
            first_year=2020, last_year=2020, participants=1, total_assets=1.0,
        )
    ]

    window.provider_panel.set_companies("Fidelity Investments", stale)

    assert window.provider_panel.companies_table.rowCount() == 0


def test_every_background_runner_is_shut_down_on_close(qt_app, window):
    """Two hand-written copies of this list had drifted, leaking two threads."""

    from app.ui.workers import TaskRunner

    declared = {name for name, value in vars(window).items() if isinstance(value, TaskRunner)}
    covered = {
        name
        for name, value in vars(window).items()
        if isinstance(value, TaskRunner) and value in window._runners()
    }

    assert declared == covered
    assert len(declared) >= 8


# ----------------------------------------------------------------------
# The Company report tab
# ----------------------------------------------------------------------


def test_the_company_report_tab_exists(qt_app, window):
    labels = [window.tabs.tabText(index) for index in range(window.tabs.count())]

    assert "Company report" in labels


def test_a_company_name_alone_builds_a_report(qt_app, window):
    """No year, no EIN. The tab's whole reason for existing."""

    window.report_panel.company_input.setText("ACME MANUFACTURING")
    window.report_panel._emit()
    settle(qt_app, window)

    text = window.report_panel.report_text()

    assert "RETIREMENT PLAN REPORT" in text
    assert "HISTORICAL RECORDKEEPER TIMELINE" in text
    assert window.report_panel.export_button.isEnabled()


def test_an_empty_company_name_asks_rather_than_searching(qt_app, window):
    window.report_panel.company_input.setText("   ")
    window.report_panel._emit()
    settle(qt_app, window)

    assert "company name" in window.report_panel.status.text().lower()
    assert window.report_panel.report_text() == ""


def test_a_company_that_matched_nothing_says_so(qt_app, window):
    window.report_panel.company_input.setText("NO SUCH EMPLOYER ANYWHERE AT ALL")
    window.report_panel._emit()
    settle(qt_app, window)

    assert "No plan was found" in window.report_panel.report_text()
    assert not window.report_panel.export_button.isEnabled()


def test_the_plan_type_filter_is_offered(qt_app, window):
    from app.reports import PLAN_TYPES

    combo = window.report_panel.type_combo
    offered = {combo.itemData(index) for index in range(combo.count())}

    assert "" in offered, "there must be an all-types option"
    for plan_type in PLAN_TYPES:
        assert plan_type.key in offered


def test_the_report_saves_with_its_extension(qt_app, window, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    window.report_panel.company_input.setText("ACME MANUFACTURING")
    window.report_panel._emit()
    settle(qt_app, window)

    target = tmp_path / "acme report"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), ""))
    )

    window.export_employer_report()

    written = target.with_suffix(".txt")
    assert written.is_file()
    assert "RETIREMENT PLAN REPORT" in written.read_text(encoding="utf-8")
