"""
The report as a person reads it.

Plain text, so it can be printed, pasted into an email or sent to a
recordkeeper without anything being lost. Every conclusion carries the filing
it came from, because the reader may have to argue it with somebody.

One rule shapes the whole thing: say only what the filings say. Where the
recordkeeper was never filed the report says so in those words rather than
offering the next-largest name on the schedule.
"""

from __future__ import annotations

import textwrap

from app.core.constants import SOURCE_LABEL
from app.providers.directory import DISCLAIMER as CONTACT_DISCLAIMER
from app.reports.employer import EmployerReport, PlanHistory, latest_year
from app.reports.timeline import Timeline

RULE = "=" * 66
THIN = "-" * 66

NOT_IDENTIFIED = "Not conclusively identified"


def _wrap(text: str, indent: str = "", width: int = 66) -> list[str]:
    return textwrap.wrap(text, width=width, initial_indent=indent, subsequent_indent=indent) or [
        indent.rstrip()
    ]


def _money(value: float | None) -> str:
    if value is None:
        return "not reported"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:,.2f} billion"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.1f} million"
    return f"${value:,.0f}"


def render_report(report: EmployerReport) -> str:
    """The whole report, ready to print."""

    lines: list[str] = [RULE, "RETIREMENT PLAN REPORT", RULE, ""]

    if not report.found:
        return "\n".join(lines + _nothing_found(report))

    lines.extend(_employer_block(report))

    for plan_type, plans in report.by_type():
        lines.append(THIN)
        lines.append(plan_type.label.upper())
        lines.append(THIN)
        lines.append("")

        for plan in plans:
            lines.extend(_plan_block(plan, report))

    lines.extend(_footer(report))
    return "\n".join(lines)


def _nothing_found(report: EmployerReport) -> list[str]:
    query = report.query
    where = ", ".join(part for part in (query.city, query.state) if part)

    lines = [
        f"No plan was found for {query.name}" + (f" in {where}" if where else "") + ".",
        "",
    ]

    if report.alternatives:
        lines.append("These employers have similar names in the data held here:")
        lines.append("")
        for name in report.alternatives:
            lines.append(f"  {name}")
        lines.append("")

    lines.extend(
        [
            "A blank result is not proof there was no plan. In order of likelihood:",
            "",
            "  1. The years worked there are not imported. Load them from the Data",
            "     tab, or run '401k-finder index' for every year at once.",
            "  2. The employer filed under a different legal name. Try the name on",
            "     a payslip, the parent company, and any former name.",
            "  3. The employer never had to file. Government, church and",
            "     one-participant plans are outside this dataset entirely.",
            "",
            f"Source: {SOURCE_LABEL}",
        ]
    )
    return lines


def _employer_block(report: EmployerReport) -> list[str]:
    historical = [name for name in report.historical_names if name != report.current_name]

    lines = [
        "EMPLOYER",
        "",
        f"Company:            {report.employer_name}",
    ]

    if historical:
        lines.append(f"Historical Names:   {historical[0]}")
        for name in historical[1:]:
            lines.append(f"                    {name}")
    else:
        lines.append("Historical Names:   none recorded; the name did not change")

    lines.append(f"Current Name:       {report.current_name}")
    lines.append(f"EIN:                {report.ein or 'not reported'}")
    lines.append(f"Location:           {report.location or 'not reported'}")

    if report.years_held:
        span = f"{report.years_held[0]}-{report.years_held[-1]}"
        lines.append(f"Form years held:    {span} ({len(report.years_held)} year(s))")

    lines.append("")

    for note in report.notes:
        lines.extend(_wrap(f"Note: {note}"))
        lines.append("")

    return lines


def _plan_block(plan: PlanHistory, report: EmployerReport) -> list[str]:
    newest = latest_year(report)

    lines = [
        f"Plan Name:          {plan.current_name}",
    ]

    if plan.original_name != plan.current_name:
        lines.append(f"Formerly:           {plan.original_name}")

    lines.extend(
        [
            f"Plan Number:        {plan.plan_number or 'not reported'}",
            f"EIN:                {plan.ein or 'not reported'}",
            f"Plan Sponsor:       {plan.sponsor_names[-1] if plan.sponsor_names else 'not reported'}",
            f"Plan Status:        {plan.status}",
            f"Filed for:          {_span(plan)}",
        ]
    )

    if plan.participants is not None:
        lines.append(f"Participants:       {plan.participants:,}")
    if plan.total_assets is not None:
        lines.append(f"Plan Assets:        {_money(plan.total_assets)}")

    lines.append("")
    lines.extend(_recordkeeper_block(plan, newest, annual=report.query.annual_detail))
    lines.extend(_transitions_block(plan))
    lines.extend(_supporting_block(plan, newest))
    lines.extend(_name_changes_block(plan))
    lines.extend(_successor_block(plan))
    lines.extend(_sources_block(plan, report))

    lines.append("")
    return lines


def _span(plan: PlanHistory) -> str:
    if not plan.filed_years:
        return "not reported"
    if len(plan.filed_years) == 1:
        return str(plan.filed_years[0])
    return f"{plan.filed_years[0]}-{plan.filed_years[-1]} ({len(plan.filed_years)} filings)"


def _recordkeeper_block(
    plan: PlanHistory, newest: int | None, *, annual: bool = False
) -> list[str]:
    lines = ["HISTORICAL RECORDKEEPER TIMELINE", ""]

    timeline = plan.recordkeepers
    if timeline is None or not len(timeline):
        lines.extend(
            [
                f"Recordkeeper: {NOT_IDENTIFIED}",
                "",
            ]
        )
        lines.extend(
            _wrap(
                "No firm is filed as this plan's recordkeeper in the years held "
                "here. An investment manager or a fund named in the filings is "
                "not the recordkeeper and is not offered as one.",
                "  ",
            )
        )
        lines.append("")
        return lines

    if annual:
        for period in timeline:
            for year in period.years:
                mark = " (carried across)" if year in period.inferred_years else ""
                lines.append(f"{year}")
                lines.append(f"  Recordkeeper: {period.value}{mark}")
                lines.append(f"  Confidence:   {period.confidence}")
                lines.append("")

        if timeline.unknown_years:
            for year in timeline.unknown_years:
                lines.append(f"{year}")
                lines.append(f"  Recordkeeper: {NOT_IDENTIFIED}")
                lines.append("")

        return lines

    for period in timeline:
        lines.append(period.label(newest))
        lines.append(f"  Recordkeeper: {period.value}")
        lines.append(f"  Confidence:   {period.confidence}")

        if period.inferred_years:
            years = ", ".join(str(year) for year in period.inferred_years)
            lines.extend(
                _wrap(
                    f"{years} named nobody; carried across because the years "
                    f"either side agree.",
                    "  ",
                )
            )

        for source in period.sources[:2]:
            if source:
                lines.append(f"  Source:       {source}")

        lines.append("")

    if timeline.unknown_years:
        years = ", ".join(str(year) for year in timeline.unknown_years)
        lines.extend(_wrap(f"No recordkeeper filed for: {years}"))
        lines.append("")

    return lines


def _transitions_block(plan: PlanHistory) -> list[str]:
    timeline = plan.recordkeepers
    if timeline is None or not timeline.transitions:
        return []

    lines = ["PROVIDER CHANGES", ""]

    for change in timeline.transitions:
        lines.append(f"{change.year}")
        lines.append(f"  {change.before}")
        lines.append("      |")
        lines.append("      v")
        lines.append(f"  {change.after}")
        lines.extend(
            _wrap(
                "First reported in the filing for this form year. Form 5500 "
                "records no date for a provider change, so this is the year it "
                "was first filed rather than the day it took effect.",
                "  ",
            )
        )
        lines.append("")

    return lines


def _supporting_block(plan: PlanHistory, newest: int | None) -> list[str]:
    if not plan.supporting and not plan.investments:
        return []

    lines = ["OTHER SERVICE PROVIDERS", ""]

    if plan.supporting:
        for entry in plan.supporting:
            spans = ", ".join(period.label(newest) for period in entry.timeline)
            lines.append(f"  {entry.role_label + ':':22} {entry.name}  [{spans}]")
    else:
        lines.append("  None filed besides the recordkeeper.")

    lines.append("")

    if plan.investments:
        lines.append("INVESTMENTS AND MANAGERS")
        lines.extend(
            _wrap(
                "Shown because investment detail was asked for. None of these is "
                "the plan's recordkeeper.",
                "  ",
            )
        )
        lines.append("")
        for entry in plan.investments:
            spans = ", ".join(period.label(newest) for period in entry.timeline)
            lines.append(f"  {entry.role_label + ':':22} {entry.name}  [{spans}]")
        lines.append("")

    return lines


def _name_changes_block(plan: PlanHistory) -> list[str]:
    history: Timeline | None = plan.plan_name_history
    if history is None or not history.transitions:
        return []

    lines = ["PLAN NAME CHANGES", ""]

    for change in history.transitions:
        lines.append(f"  {change.before}")
        lines.append("      |")
        lines.append("      v")
        lines.append(f"  {change.after}")
        lines.append(f"  First filed under the new name for form year {change.year}.")
        lines.append("")

    sponsors: Timeline | None = plan.sponsor_name_history
    if sponsors is not None and sponsors.transitions:
        lines.append("SPONSOR NAME CHANGES")
        lines.append("")
        for change in sponsors.transitions:
            lines.append(f"  {change.before}")
            lines.append("      |")
            lines.append("      v")
            lines.append(f"  {change.after}")
            lines.append(f"  First filed under the new name for form year {change.year}.")
            lines.append("")

    return lines


def _successor_block(plan: PlanHistory) -> list[str]:
    if not plan.terminated:
        return []

    lines = ["PLAN WOUND UP", "", f"  A final return was filed for {plan.final_year}."]

    chain = plan.successor
    narrate = getattr(chain, "narrate", None)
    if callable(narrate):
        for step in narrate():
            lines.extend(_wrap(step, "  "))
    else:
        lines.extend(
            _wrap(
                "The filings do not record a plan that received the assets. The "
                "balance was most likely paid out or rolled into an IRA.",
                "  ",
            )
        )

    lines.append("")
    return lines


def _sources_block(plan: PlanHistory, report: EmployerReport) -> list[str]:
    if not plan.sources:
        return []

    lines = ["SOURCE RECORDS", ""]

    header = f"  {'Year':<6}{'Form':<10}{'EIN':<12}{'Plan':<7}{'Recordkeeper':<30}Source"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))

    for record in plan.sources:
        recordkeeper = record.recordkeeper or NOT_IDENTIFIED
        lines.append(
            f"  {record.form_year:<6}{record.form_type:<10}{record.ein:<12}"
            f"{record.plan_number:<7}{recordkeeper[:29]:<30}{record.source}"
        )

    lines.append("")
    return lines


def _footer(report: EmployerReport) -> list[str]:
    return [
        THIN,
        "",
        f"Source: {SOURCE_LABEL}",
        "",
        *_wrap(
            "Only the recordkeeper is reported as the plan's provider. Investment "
            "managers, collective trusts, separate accounts and funds are filtered "
            "out of the provider timeline, because a firm managing a fund inside a "
            "plan is not the firm that holds a participant's account."
        ),
        "",
        *_wrap(CONTACT_DISCLAIMER),
        "",
        *_wrap(
            "This describes what public Form 5500 filings say. It is not financial, "
            "legal or tax advice, and it is not confirmation that any account exists "
            "in your name."
        ),
        "",
        THIN,
        "END REPORT",
        THIN,
    ]
