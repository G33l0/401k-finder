"""The plan detail panel: providers, evidence, filings."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.codes import describe_characteristic, describe_service_code
from app.core.constants import EFAST_FILING_URL
from app.evidence.trail import PlanEvidence
from app.search.engine import PlanResult
from app.ui import theme
from app.ui.widgets.results_table import format_count, format_money

#: Roles shown under "Who holds this account", in order.
HEADLINE_ROLES = (
    "RECORDKEEPER",
    "TRUSTEE",
    "CUSTODIAN",
    "INSURER",
    "INVESTMENT_MANAGER",
    "TRUST",
    "INVESTMENT_VEHICLE",
)


def _title(value: str) -> str:
    return value.replace("_", " ").title()


class PlanDetailPanel(QWidget):
    """Shows everything known about one plan, with its sources."""

    export_requested = Signal(int)
    provider_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._plan: PlanResult | None = None
        self._evidence: PlanEvidence | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.tabs = QTabWidget()

        self.overview = QTextBrowser()
        self.overview.setOpenExternalLinks(True)
        self.overview.anchorClicked.connect(self._on_anchor)
        self.tabs.addTab(self.overview, "Overview")

        self.providers = QTextBrowser()
        self.providers.setOpenExternalLinks(True)
        self.providers.anchorClicked.connect(self._on_anchor)
        self.tabs.addTab(self.providers, "Providers")

        self.evidence_view = QTextBrowser()
        self.evidence_view.setOpenExternalLinks(True)
        self.tabs.addTab(self.evidence_view, "Evidence")

        self.filings_view = QTextBrowser()
        self.tabs.addTab(self.filings_view, "Filings")

        layout.addWidget(self.tabs)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        self.export_button = QPushButton("Export evidence report…")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._on_export)
        buttons.addWidget(self.export_button)

        layout.addLayout(buttons)

        self.clear()

    # ------------------------------------------------------------------

    def _placeholder(self, heading: str, message: str) -> str:
        return (
            f"{self._style()}<div class='empty'>"
            f"<h3>{heading}</h3><p>{message}</p></div>"
        )

    def _empty_html(self) -> str:
        return self._placeholder(
            "No plan selected",
            "Select a plan in the results list to see who holds and administers it, "
            "and the exact DOL filing field each answer comes from.",
        )

    def _loading_html(self) -> str:
        return self._placeholder("Loading…", "Reading the filings for this plan.")

    def clear(self) -> None:
        self._plan = None
        self._evidence = None
        self.export_button.setEnabled(False)

        placeholder = self._empty_html()
        for view in (self.overview, self.providers, self.evidence_view, self.filings_view):
            view.setHtml(placeholder)

    def set_summary(self, plan: PlanResult | None) -> None:
        """Render what is already known, before the full detail loads."""

        self.set_detail(plan, None)

    def set_detail(self, plan: PlanResult | None, evidence: PlanEvidence | None) -> None:
        """Render the full detail once the background load finishes."""

        self._plan = plan
        self._evidence = evidence

        if plan is None:
            self.clear()
            return

        self.overview.setHtml(self._overview_html(plan))
        self.providers.setHtml(self._providers_html(plan))
        self.export_button.setEnabled(evidence is not None)

        if evidence is not None:
            self.evidence_view.setHtml(self._evidence_html(evidence))
            self.filings_view.setHtml(self._filings_html(evidence))
        else:
            # Still loading, or the load failed. Repainting these rather than
            # leaving them is what stops a theme change from stranding two tabs
            # in the previous scheme.
            loading = self._loading_html()
            self.evidence_view.setHtml(loading)
            self.filings_view.setHtml(loading)

    def retheme(self) -> None:
        """
        Re-render after a theme change.

        The colours are baked into the HTML at render time, so unlike an
        ordinary widget these views do not update themselves when the
        application style sheet changes — they have to be drawn again.
        """

        self.set_detail(self._plan, self._evidence)

    # ------------------------------------------------------------------

    @staticmethod
    def _style() -> str:
        """
        The CSS every view on this panel is rendered with.

        Read from the active theme rather than written inline, because these
        panels are ``QTextBrowser`` widgets: Qt's rich-text engine ignores the
        application style sheet, so hard-coded colours here would paint white
        cards onto a dark window.
        """

        return theme.document_css(theme.current())

    @staticmethod
    def _confidence_class(confidence: str | None) -> str:
        return {"HIGH": "hi", "MEDIUM": "med"}.get(confidence or "", "low")

    def _overview_html(self, plan: PlanResult) -> str:
        features = "".join(
            f"<span class='tag'>&nbsp;{escape(_title(feature))}&nbsp;</span>&nbsp; "
            for feature in plan.features
        )

        codes = "".join(
            f"<tr><td class='k'>{escape(code)}</td><td>{escape(describe_characteristic(code))}</td></tr>"
            for code in plan.benefit_codes
        )

        headline = [
            party
            for role in HEADLINE_ROLES
            for party in plan.parties
            if party.role == role
        ]

        seen: set[tuple[int, str]] = set()
        holders = []
        for party in headline:
            key = (party.provider_id, party.role)
            if key in seen:
                continue
            seen.add(key)
            holders.append(
                f"<tr><td class='k'>{escape(_title(party.role))}</td>"
                f"<td><b>{escape(party.display_name)}</b>"
                f"<div class='src'>Reported on schedule {escape(party.schedule_code or '?')}, "
                f"field {escape(party.source_field or '?')} ({party.form_year})</div></td></tr>"
            )

        holders_html = (
            "".join(holders)
            or "<tr><td colspan='2'>No asset holder was named in the imported filings.</td></tr>"
        )

        return f"""{self._style()}
<h2>{escape(plan.plan_name)}</h2>
<p class='sub'>{escape(plan.sponsor_name or 'Sponsor not reported')}
&nbsp;·&nbsp; {escape(plan.city or '')} {escape(plan.state or '')}</p>
<p>{features}</p>

<h3>Who holds this account</h3>
<table>{holders_html}</table>

<h3>Plan identity</h3>
<table>
<tr><td class='k'>Sponsor EIN</td><td>{escape(plan.ein or '—')}</td></tr>
<tr><td class='k'>Plan number</td><td>{escape(plan.plan_number or '—')}</td></tr>
<tr><td class='k'>Category</td><td>{escape(_title(plan.plan_category or 'Unknown'))}</td></tr>
<tr><td class='k'>Filing years</td><td>{plan.first_year or '—'} – {plan.last_year or '—'}</td></tr>
<tr><td class='k'>Participants</td><td>{format_count(plan.participants)}</td></tr>
<tr><td class='k'>Total assets</td><td>{format_money(plan.total_assets)}</td></tr>
<tr><td class='k'>Filings on record</td><td>{plan.filing_count or '—'}</td></tr>
</table>

<h3>Plan characteristics as filed</h3>
<table>{codes or "<tr><td>No characteristics codes were reported.</td></tr>"}</table>
"""

    def _providers_html(self, plan: PlanResult) -> str:
        if not plan.parties:
            return (
                f"{self._style()}<h2>Providers</h2>"
                "<p>No service providers were identified for this plan.</p>"
                "<p class='sub'>The filings on record may not name one, or the schedules "
                "that carry provider information (Schedule A, C, D, H and I) may not have "
                "been imported for these years.</p>"
            )

        cards = []
        for party in plan.primary_providers():
            services = "".join(
                f"<div class='src'>· {escape(describe_service_code(code))}</div>"
                for code in party.service_codes
            )

            compensation = ""
            if party.direct_compensation:
                compensation += f"<div class='src'>Direct compensation: {format_money(party.direct_compensation)}</div>"
            if party.indirect_compensation:
                compensation += f"<div class='src'>Indirect compensation: {format_money(party.indirect_compensation)}</div>"

            reported = ""
            if party.reported_name and party.reported_name != party.display_name:
                reported = f"<div class='src'>Filed as: {escape(party.reported_name)}</div>"

            cards.append(
                f"<table class='card'><tr><td>"
                f"<span class='role'>{escape(_title(party.role))}</span> &nbsp;"
                f"<a href='provider:{escape(party.display_name)}'>{escape(party.display_name)}</a>"
                f"<span class='{self._confidence_class(party.confidence)}'> "
                f"&nbsp;{escape(party.confidence or '')}</span>"
                f"{reported}{services}{compensation}"
                f"<div class='src'>Source: schedule {escape(party.schedule_code or '?')}, "
                f"field {escape(party.source_field or '?')}, form year {party.form_year}</div>"
                f"</td></tr></table>"
            )

        return (
            f"{self._style()}<h2>Providers</h2>"
            "<p class='sub'>Click a provider name to find every other plan it serves.</p>"
            + "".join(cards)
        )

    def _evidence_html(self, evidence: PlanEvidence) -> str:
        blocks = []

        for finding in evidence.findings:
            items = "".join(
                f"<div class='src'>{escape(item.citation())}"
                + (f"<br>{escape(item.notes)}" if item.notes else "")
                + "</div>"
                for item in finding.evidence
            )

            sources = items or "<div class='src'>No source record was stored.</div>"

            blocks.append(
                f"<table class='card'><tr><td>"
                f"<span class='role'>{escape(_title(finding.role))}</span> "
                f"{escape(finding.display_name)} "
                f"<span class='{self._confidence_class(finding.confidence)}'>"
                f"{escape(finding.confidence or '')}</span>"
                f"{sources}"
                f"</td></tr></table>"
            )

        return f"""{self._style()}
<h2>Evidence</h2>
<p class='sub'>Every statement above traces to a named field of a named DOL dataset row.
The original filing images can be retrieved from EBSA's public search using the
sponsor EIN {escape(evidence.plan_key)}.</p>
<p><a href='{EFAST_FILING_URL}'>Open the EFAST public filing search</a></p>
{"".join(blocks) or "<p>No evidence records were stored for this plan.</p>"}
"""

    def _filings_html(self, evidence: PlanEvidence) -> str:
        rows = []
        for filing in evidence.filings:
            rows.append(
                f"<tr><td class='k'>{filing.form_year}</td>"
                f"<td><b>{escape(filing.form_type)}</b>"
                f"<div class='src'>ACK_ID {escape(filing.ack_id)}</div>"
                f"<div class='src'>Participants: {format_count(filing.total_participants)} "
                f"· Assets: {format_money(filing.total_assets_eoy)} "
                f"· Status: {escape(filing.filing_status or '—')}</div>"
                f"<div class='src'>Source: {escape(filing.source_dataset or '?')} "
                f"({escape(filing.source_release or '?')})</div></td></tr>"
            )

        return f"""{self._style()}
<h2>Filings on record</h2>
<table>{"".join(rows) or "<tr><td>No filings recorded.</td></tr>"}</table>
"""

    # ------------------------------------------------------------------

    def _on_anchor(self, url) -> None:  # noqa: ANN001
        text = url.toString()
        if text.startswith("provider:"):
            self.provider_selected.emit(text.removeprefix("provider:"))

    def _on_export(self) -> None:
        if self._plan is not None:
            self.export_requested.emit(self._plan.plan_id)
