"""
The "Find my accounts" tab: a work history in, a trace out.

Someone using this is not researching plans — they are trying to recover their
own money, usually with no idea what a Form 5500 is. So the panel asks for the
only thing they reliably know (where they worked, roughly when), and answers
with the plan's identity, the firm that was holding it, and what to say.

The one thing it deliberately does not ask for is a Social Security number.
Nothing in Form 5500 identifies a participant, so an SSN could only ever fail —
and it would fail after being typed into a box. People will still try, because
every other lost-account service asks for one, so the employer field watches for
it, refuses to search, and points at the registries where an SSN genuinely
works.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.constants import SOURCE_LABEL, US_STATES
from app.trace import WorkHistory, looks_like_ssn
from app.trace.matcher import TraceReport
from app.trace.resources import RESOURCES
from app.ui import theme

COLUMNS = ("Employer", "City", "State", "From", "To")

#: Blank rows kept at the bottom so there is always somewhere to type.
SPARE_ROWS = 3


class TracePanel(QWidget):
    """Collects a work history and shows what the filings say about it."""

    trace_requested = Signal(object)
    export_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._report: TraceReport | None = None
        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        intro = QLabel(
            "<b>Looking for a retirement account from an old job?</b><br>"
            "List the employers you have worked for. This searches the official "
            "filings each one made, and reports the plan they ran and the firm "
            "that was holding the money — the details you need before a "
            f"recordkeeper will look you up.<br>"
            f"<span style='font-size:9pt'>Source: <b>{SOURCE_LABEL}</b></span>"
        )
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        splitter = QSplitter(Qt.Vertical)

        # --- Work history --------------------------------------------
        top = QWidget()
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.cellChanged.connect(self._on_cell_changed)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, len(COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)

        top_layout.addWidget(self.table)

        hint = QLabel(
            "Fill in what you remember — the employer's name is the only part that "
            "is needed. A state and rough years make the match far more reliable."
        )
        hint.setWordWrap(True)
        hint.setProperty("role", "muted")
        top_layout.addWidget(hint)

        buttons = QHBoxLayout()

        self.trace_button = QPushButton("Find my accounts")
        self.trace_button.setDefault(True)
        self.trace_button.clicked.connect(self._on_trace)
        buttons.addWidget(self.trace_button)

        add_row = QPushButton("Add row")
        add_row.clicked.connect(lambda: self._append_blank_rows(1))
        buttons.addWidget(add_row)

        load = QPushButton("Load from CSV…")
        load.setToolTip("Columns: employer, city, state, start_year, end_year, note")
        load.clicked.connect(self._load_csv)
        buttons.addWidget(load)

        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        buttons.addWidget(clear)

        buttons.addStretch(1)

        self.export_button = QPushButton("Save report…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export)
        buttons.addWidget(self.export_button)

        top_layout.addLayout(buttons)
        splitter.addWidget(top)

        # --- Results --------------------------------------------------
        self.results = QTextBrowser()
        # External links are deliberately not opened from here; every anchor is
        # an internal action. See _resources_html.
        self.results.setOpenExternalLinks(False)
        self.results.anchorClicked.connect(self._on_anchor)
        splitter.addWidget(self.results)

        splitter.setSizes([260, 520])
        layout.addWidget(splitter, 1)

        self._append_blank_rows(SPARE_ROWS)
        self.show_intro()

    # ------------------------------------------------------------------
    # The table
    # ------------------------------------------------------------------

    def _append_blank_rows(self, count: int) -> None:
        self.table.blockSignals(True)
        for _ in range(count):
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column in range(len(COLUMNS)):
                self.table.setItem(row, column, QTableWidgetItem(""))
        self.table.blockSignals(False)

    def _cell(self, row: int, column: int) -> str:
        item = self.table.item(row, column)
        return item.text().strip() if item else ""

    def _on_cell_changed(self, row: int, column: int) -> None:
        # Typing in the last row means more room is needed.
        if row == self.table.rowCount() - 1 and self._cell(row, 0):
            self._append_blank_rows(1)

        if column == 0 and looks_like_ssn(self._cell(row, 0)):
            self._reject_ssn(row)

    def _reject_ssn(self, row: int) -> None:
        """Refuse an SSN before it is stored, and say where one does work."""

        self.table.blockSignals(True)
        self.table.item(row, 0).setText("")
        self.table.blockSignals(False)

        QMessageBox.information(
            self,
            "That looks like a Social Security number",
            "It has not been searched for, saved or logged.\n\n"
            "This tool searches Form 5500 — what employers file about their plans. "
            "It names plans, not people: there is no participant list, no Social "
            "Security number and no individual balance anywhere in it, so an SSN "
            "has nothing to match against here.\n\n"
            "Enter the employer's name instead. The results panel links to the "
            "Department of Labor's Retirement Savings Lost and Found and the other "
            "registries that can be searched by Social Security number.",
        )

    def clear(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        self.table.blockSignals(False)

        self._append_blank_rows(SPARE_ROWS)
        self._report = None
        self.export_button.setEnabled(False)
        self.show_intro()

    def build_history(self) -> WorkHistory:
        """Read the table into a work history, skipping blank rows."""

        history = WorkHistory()

        for row in range(self.table.rowCount()):
            employer = self._cell(row, 0)
            if not employer:
                continue

            history.add(
                employer,
                city=self._cell(row, 1) or None,
                state=self._cell(row, 2) or None,
                start_year=_year(self._cell(row, 3)),
                end_year=_year(self._cell(row, 4)),
            )

        return history

    def load_history(self, history: WorkHistory) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for job in history:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, value in enumerate(
                (
                    job.employer,
                    job.city or "",
                    job.state or "",
                    str(job.start_year or ""),
                    str(job.end_year or ""),
                )
            ):
                self.table.setItem(row, column, QTableWidgetItem(value))

        self.table.blockSignals(False)
        self._append_blank_rows(SPARE_ROWS)

    # ------------------------------------------------------------------

    def _on_trace(self) -> None:
        history = self.build_history()

        if not len(history):
            QMessageBox.information(
                self,
                "Nothing to search",
                "Add at least one employer you have worked for.",
            )
            return

        unknown = [job.state for job in history if job.state and job.state not in US_STATES]
        if unknown:
            QMessageBox.warning(
                self,
                "Check the state",
                f"{', '.join(sorted(set(unknown)))} is not a two-letter state code. "
                f"Leave it blank to search every state.",
            )
            return

        self.set_busy(True)
        self.trace_requested.emit(history)

    def set_busy(self, busy: bool) -> None:
        self.trace_button.setEnabled(not busy)
        self.trace_button.setText("Searching…" if busy else "Find my accounts")

    def _on_export(self) -> None:
        if self._report is not None:
            self.export_requested.emit(self._report)

    def _load_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load work history", "", "CSV files (*.csv);;All files (*)"
        )
        if not path:
            return

        from pathlib import Path

        try:
            history = WorkHistory.from_csv(Path(path))
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not read that file", str(exc))
            return

        self.load_history(history)

    def _on_anchor(self, url) -> None:  # noqa: ANN001
        text = url.toString()

        if text.startswith("copy:"):
            value = text.removeprefix("copy:")
            QGuiApplication.clipboard().setText(value)
            self.window().statusBar().showMessage(f"Copied {value}", 4000)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def show_intro(self) -> None:
        self.results.setHtml(_intro_html())

    def show_report(self, report: TraceReport) -> None:
        self._report = report
        self.export_button.setEnabled(True)
        self.set_busy(False)
        self.results.setHtml(_report_html(report))

    def retheme(self) -> None:
        """Re-render, since the colours are baked into the HTML."""

        if self._report is None:
            self.show_intro()
        else:
            self.results.setHtml(_report_html(self._report))


def _year(value: str) -> int | None:
    import re

    found = re.search(r"(19|20)\d{2}", value)
    return int(found.group(0)) if found else None


# ----------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------


def _style() -> str:
    return theme.document_css(theme.current())


def _resources_html() -> str:
    """
    The registries, named rather than linked.

    No web address is shown and nothing here opens a browser. "Copy web
    address" puts it on the clipboard so the person pastes it in themselves,
    which is the habit worth building anyway: the one reliable defence against
    a retirement-account scam is never following a link somebody handed you.
    """

    rows = []
    for resource in RESOURCES:
        phone = f"<div class='src'>Telephone: {resource.phone}</div>" if resource.phone else ""
        caveat = f"<div class='src'>{resource.caveat}</div>" if resource.caveat else ""
        rows.append(
            f"<table class='card'><tr><td>"
            f"<span class='role'>{resource.name}</span>"
            f"<div class='src'>{resource.holds}</div>"
            f"<div class='src'><b>You need:</b> {resource.needs}</div>"
            f"{phone}{caveat}"
            f"<div class='src'><a href='copy:{resource.url}'>Copy web address</a></div>"
            f"</td></tr></table>"
        )

    return "".join(rows)


def _intro_html() -> str:
    return f"""{_style()}
<h2>Find a retirement account from an old job</h2>
<p class='sub'>List your employers on the left, then choose <b>Find my accounts</b>.</p>

<h3>What this can tell you</h3>
<p>Every employer-sponsored retirement plan covered by ERISA files a Form 5500
each year. From your work history this finds:</p>
<ul>
<li>the plan your employer ran, with its exact name, EIN and plan number;</li>
<li>the recordkeeper, trustee or custodian holding the money <b>in the years you
worked there</b> — often not the same firm as today;</li>
<li>whether the plan still exists, or was wound up and the money moved;</li>
<li>a letter you can send, with the plan's details filled in.</li>
</ul>

<h3>What it cannot tell you</h3>
<p>Whether <b>you personally</b> have a balance. Form 5500 is what an employer
files about a plan, not about its members: across all 448 published record
layouts there is no participant name, no Social Security number and no
individual balance. <b>Do not enter a Social Security number here</b> — it has
nothing to match against, and this tool will refuse it.</p>

<p>Only the plan's own recordkeeper, or one of the registries below, can confirm
an account in your name. What this gives you is who to ask, and the plan details
they will want.</p>
<p class='src'>Source: {SOURCE_LABEL}</p>

<h3>Where a Social Security number does work</h3>
{_resources_html()}
"""


def _holders_html(holders, heading: str) -> str:  # noqa: ANN001
    if not holders:
        return ""

    rows = "".join(
        f"<tr><td class='k'>{holder.role_label}</td>"
        f"<td><b>{holder.name}</b>"
        f"<div class='src'>{holder.citation()}</div></td></tr>"
        for holder in holders[:6]
    )

    return f"<div class='sub'><b>{heading}</b></div><table>{rows}</table>"


def _match_html(match, index: int) -> str:  # noqa: ANN001
    from html import escape

    from app.trace.packet import next_steps

    badge = {"STRONG": "hi", "POSSIBLE": "med"}.get(match.confidence, "low")

    terminated = (
        f"<div class='src'><b>This plan was wound up</b> — a final return was filed "
        f"for {match.final_year}, so the money was moved elsewhere.</div>"
        if match.terminated
        else ""
    )

    renamed = (
        f"<div class='src'>Filed at the time as “{escape(match.matched_as)}”.</div>"
        if match.matched_as and match.matched_as != match.sponsor_name
        else ""
    )

    reasons = "".join(f"<div class='src'>· {escape(reason)}</div>" for reason in match.reasons)
    steps = "".join(f"<li>{escape(step)}</li>" for step in next_steps(match))

    return f"""<table class='card'><tr><td>
<span class='role'>{index}. {escape(match.plan_name)}</span>
<span class='{badge}'> &nbsp;{match.confidence}</span>
<div class='src'>{escape(match.sponsor_name or 'Sponsor not reported')}
&nbsp;·&nbsp; EIN {escape(match.ein or '?')} / plan {escape(match.plan_number or '?')}
&nbsp;·&nbsp; {escape(match.city or '')} {escape(match.state or '')}
&nbsp;·&nbsp; filed {match.first_year or '?'}–{match.last_year or '?'}</div>
{renamed}{terminated}
<p><a href='copy:{escape(match.ein or "")}'>Copy EIN</a></p>
{_holders_html(match.holders_then, "Holding the money while you were there")}
{_holders_html(
    match.holders_now if match.holders_now != match.holders_then else [],
    "Holding it on the most recent filing",
)}
<div class='sub'><b>Why this matched</b></div>{reasons}
<div class='sub'><b>What to do next</b></div><ol>{steps}</ol>
</td></tr></table>"""


def _report_html(report: TraceReport) -> str:
    from html import escape

    years = (
        f"{report.years_searched[0]}–{report.years_searched[-1]}"
        if report.years_searched
        else "none imported yet"
    )

    blocks = [
        f"{_style()}<h2>Results</h2>",
        f"<p class='sub'>{report.total_matches} plan(s) found across "
        f"{len(report.jobs_with_matches)} of {len(report.history)} job(s). "
        f"Form years held locally: {years}.<br>"
        f"Source: <b>{SOURCE_LABEL}</b></p>",
    ]

    for trace in report.traces:
        blocks.append(f"<h3>{escape(trace.job.label)}</h3>")

        if not trace.found:
            blocks.append(
                "<p>No plan matched this employer in the form years you have "
                "imported.</p>"
                "<p class='sub'>That does not mean there was no plan. The years you "
                "worked there may not be imported yet; the employer may have filed "
                "under a different legal name; small and one-participant plans file "
                "forms that are not in this dataset; and government and many church "
                "employers do not file at all. The registries at the end do not "
                "depend on the employer having filed.</p>"
            )
            continue

        for index, match in enumerate(trace.matches, start=1):
            blocks.append(_match_html(match, index))

    blocks.append("<h3>Where to search by Social Security number</h3>")
    blocks.append(
        "<p class='sub'>Nothing above can confirm an account exists in your name — "
        "Form 5500 holds no participant records. These registries do, and are the "
        "only places your Social Security number belongs.</p>"
    )
    blocks.append(_resources_html())

    return "".join(blocks)
