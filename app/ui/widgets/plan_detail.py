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
from app.core.constants import NOT_REPORTED, SOURCE_LABEL, year_span
from app.evidence.trail import PlanEvidence
from app.providers.directory import DISCLAIMER as DIRECTORY_DISCLAIMER
from app.providers.servicing import servicing_history
from app.search.engine import PlanResult
from app.ui import theme
from app.ui.widgets.results_table import format_count, format_money

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


def _years_text(item) -> str:  # noqa: ANN001 - providers.ServiceProvider
    """Every year listed when there are a few, a span when there are many."""

    if not item.years:
        return "not recorded"
    if len(item.years) <= 6:
        return ", ".join(str(year) for year in item.years)

    return f"{item.span} ({len(item.years)} years)"


class PlanDetailPanel(QWidget):
    """Shows everything known about one plan, with its sources."""

    export_requested = Signal(int)
    provider_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._plan: PlanResult | None = None
        self._filed: dict = {}
        self._filed_all: list = []
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

    def _placeholder(self, heading: str, message: str) -> str:
        return (
            f"{self._style()}<div class='empty'>"
            f"<h3>{heading}</h3><p>{message}</p></div>"
        )

    def _empty_html(self) -> str:
        return self._placeholder(
            "No plan selected",
            "Select a plan in the results list to see who holds and administers it, "
            "and the exact filing field each answer comes from.",
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

        self.set_detail(plan, None, ())

    def set_detail(
        self,
        plan: PlanResult | None,
        evidence: PlanEvidence | None,
        filed=(),  # noqa: ANN001 - providers.filed_contacts.FiledContact
    ) -> None:
        """Render the full detail once the background load finishes."""

        self._plan = plan
        self._evidence = evidence
        self._filed = {contact.name.upper(): contact for contact in filed or ()}
        self._filed_all = list(filed or ())

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
            loading = self._loading_html()
            self.evidence_view.setHtml(loading)
            self.filings_view.setHtml(loading)

    def retheme(self) -> None:
        """Re-render after a theme change."""

        self.set_detail(self._plan, self._evidence)

    @staticmethod
    def _style() -> str:
        """The CSS every view on this panel is rendered with."""

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
<tr><td class='k'>Sponsor EIN</td><td>{escape(plan.ein or NOT_REPORTED)}</td></tr>
<tr><td class='k'>Plan number</td><td>{escape(plan.plan_number or NOT_REPORTED)}</td></tr>
<tr><td class='k'>Category</td><td>{escape(_title(plan.plan_category or 'Unknown'))}</td></tr>
<tr><td class='k'>Filing years</td><td>{year_span(plan.first_year, plan.last_year, joiner=' to ')}</td></tr>
<tr><td class='k'>Participants</td><td>{format_count(plan.participants)}</td></tr>
<tr><td class='k'>Total assets</td><td>{format_money(plan.total_assets)}</td></tr>
<tr><td class='k'>Filings on record</td><td>{plan.filing_count or NOT_REPORTED}</td></tr>
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

        history = servicing_history(plan.parties)
        by_key = {(party.provider_id, party.role): party for party in plan.parties}

        cards = []
        for item in history:
            party = by_key.get((item.provider_id, item.role))

            services = "".join(
                f"<div class='src'>· {escape(describe_service_code(code))}</div>"
                for code in item.service_codes
            )

            compensation = ""
            if party is not None and party.direct_compensation:
                compensation += (
                    f"<div class='src'>Direct compensation: "
                    f"{format_money(party.direct_compensation)}</div>"
                )
            if party is not None and party.indirect_compensation:
                compensation += (
                    f"<div class='src'>Indirect compensation: "
                    f"{format_money(party.indirect_compensation)}</div>"
                )

            reported = ""
            if party is not None and party.reported_name and party.reported_name != item.name:
                reported = f"<div class='src'>Filed as: {escape(party.reported_name)}</div>"

            held = (
                "<div class='src'><b>Holds or administers the money.</b> "
                "This is who can look you up.</div>"
                if item.holds_money
                else ""
            )

            cards.append(
                f"<table class='card'><tr><td>"
                f"<span class='role'>{escape(item.role_label)}</span> &nbsp;"
                f"<a href='provider:{escape(item.name)}'>{escape(item.name)}</a>"
                f"<span class='{self._confidence_class(item.confidence)}'> "
                f"&nbsp;{escape(item.confidence or '')}</span>"
                f"<div class='src'>Filed for: <b>{escape(_years_text(item))}</b></div>"
                f"{held}{reported}{services}{compensation}"
                f"{self._contact_html(item)}"
                f"<div class='src'>Source: schedule "
                f"{escape(', '.join(item.schedule_codes) or '?')}, "
                f"form year {escape(_years_text(item))}</div>"
                f"</td></tr></table>"
            )

        return (
            f"{self._style()}<h2>Providers</h2>"
            "<p class='sub'>Every firm named in the filings held for this plan, with the "
            "years each one covered. Click a name to find every other plan it serves.</p>"
            + "".join(cards)
            + self._filed_only_html(history)
            + f"<p class='sub'>A telephone number marked <b>(filed)</b> is from the "
            f"filings themselves. {escape(DIRECTORY_DISCLAIMER)}</p>"
        )

    def _filed_only_html(self, history) -> str:  # noqa: ANN001 - ServicingHistory
        """
        Numbers the employer filed for people who are not service providers.

        The plan administrator is the important one: they are obliged to answer
        a participant's written request, and they are often the only contact a
        small plan gives at all.
        """

        named = {item.name.upper() for item in history}
        extra = [
            contact
            for contact in getattr(self, "_filed_all", [])
            if contact.name.upper() not in named
        ]

        if not extra:
            return ""

        rows = []
        for contact in extra:
            rows.append(
                f"<table class='card'><tr><td>"
                f"<span class='role'>{escape(contact.role_label)}</span> &nbsp;"
                f"{escape(contact.name)}"
                f"<div class='src'>Telephone (filed): <b>{escape(contact.phone)}</b></div>"
                f"<div class='src'>Source: {escape(contact.citation())}</div>"
                f"</td></tr></table>"
            )

        return (
            "<h3>Also filed for this plan</h3>"
            "<p class='sub'>Telephone numbers the employer filed. The plan "
            "administrator has to answer a written request from a participant.</p>"
            + "".join(rows)
        )

    def _contact_html(self, item) -> str:  # noqa: ANN001 - providers.ServiceProvider
        """Website and telephone, where the application knows them."""

        filed = getattr(self, "_filed", {}).get(item.name.upper())
        contact = item.contact

        rows = []

        # A number the employer filed beats anything curated: it names this
        # plan's own office rather than a national queue.
        if filed is not None:
            rows.append(
                f"<div class='src'>Telephone (filed): <b>{escape(filed.phone)}</b> "
                f"<span class='sub'>{escape(filed.citation())}</span></div>"
            )

        if contact is None or not contact.has_details:
            return "".join(rows)

        if contact.phone and filed is None:
            rows.append(
                f"<div class='src'>Telephone: <b>{escape(contact.phone)}</b></div>"
            )
        if contact.website:
            rows.append(
                f"<div class='src'>Website: "
                f"<a href='copy:{escape(contact.website)}'>{escape(contact.website)}</a>"
                f" (click to copy)</div>"
            )
        if contact.note:
            rows.append(f"<div class='src'>{escape(contact.note)}</div>")
        if contact.successor:
            rows.append(f"<div class='src'><b>{escape(contact.successor)}</b></div>")

        return "".join(rows)

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
<p class='sub'>Every statement above traces to a named field of a named row of the
source data. Quote the sponsor EIN <b>{escape(evidence.plan_key)}</b> when asking a
plan or its recordkeeper for the underlying filing.</p>
<p class='src'>Source: {SOURCE_LABEL}</p>
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
                f"· Status: {escape(filing.filing_status or NOT_REPORTED)}</div>"
                f"<div class='src'>Source: {escape(filing.source_dataset or '?')} "
                f"({escape(filing.source_release or '?')})</div></td></tr>"
            )

        return f"""{self._style()}
<h2>Filings on record</h2>
<table>{"".join(rows) or "<tr><td>No filings recorded.</td></tr>"}</table>
"""

    def _on_anchor(self, url) -> None:  # noqa: ANN001
        text = url.toString()
        if text.startswith("provider:"):
            self.provider_selected.emit(text.removeprefix("provider:"))

    def _on_export(self) -> None:
        if self._plan is not None:
            self.export_requested.emit(self._plan.plan_id)
