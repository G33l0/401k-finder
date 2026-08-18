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

RUNNERS = (
    "search_runner",
    "detail_runner",
    "provider_runner",
    "data_runner",
    "summary_runner",
    "trace_runner",
    "changes_runner",
)


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
    import time

    deadline = time.time() + seconds
    while time.time() < deadline:
        app.processEvents()
        if not any(getattr(window, name).busy for name in RUNNERS):
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
