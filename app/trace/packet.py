"""
Turn a trace into something a person can act on.

A list of plan names is not much use to someone trying to recover money. What
they need is: this is the plan, this is its EIN and plan number, this firm was
holding it, here is the letter to send, and here is where to go if that fails.

Everything here is derived from the filings — no advice is invented, and where
the filings cannot answer something (whether a balance exists, where a
terminated plan's assets went) the report says so rather than guessing.
"""

from __future__ import annotations

import textwrap
from datetime import date

from app.core.constants import EFAST_FILING_URL
from app.trace.matcher import PlanMatch, TraceReport
from app.trace.resources import Audience, Resource, for_audience

RULE = "=" * 72
THIN = "-" * 72


def _money(value: float | None) -> str:
    if value is None:
        return "not reported"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f} billion"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f} million"
    return f"${value:,.0f}"


def next_steps(match: PlanMatch) -> list[str]:
    """What to do about one plan, in order."""

    steps: list[str] = []
    holder = match.best_holder()

    if match.terminated:
        steps.append(
            f"This plan filed a final return for {match.final_year}. It no longer "
            f"exists, so the money was moved — usually rolled into a successor "
            f"plan, transferred to an IRA opened in your name, or paid out. The "
            f"filings do not record where it went."
        )
        if holder:
            steps.append(
                f"Write to {holder.name}, which was the {holder.role_label.lower()} "
                f"when the plan wound up. They are the most likely record of where "
                f"your balance was sent."
            )
        steps.append(
            "Check the Retirement Savings Lost and Found and your state's "
            "unclaimed property office — a small balance from a wound-up plan "
            "often ends up in one of them."
        )
    elif holder:
        steps.append(
            f"Contact {holder.name} — the {holder.role_label.lower()} named in the "
            f"plan's {holder.form_year} filing ({holder.citation()}). Ask whether "
            f"they hold an account for you under plan number "
            f"{match.plan_number or '(not reported)'}, EIN {match.ein or '(not reported)'}."
        )
        steps.append(
            "If they will not deal with you directly, they will tell you who the "
            "plan administrator is. The administrator is obliged to respond to a "
            "written request from a participant."
        )
    else:
        steps.append(
            "No holder is named in the filings on record for this plan. Contact "
            "the employer's HR or benefits department and ask for the plan "
            "administrator's details."
        )

    if match.sponsor_name:
        steps.append(
            f"If the employer still exists, {match.sponsor_name} can also point you "
            f"at the administrator."
        )

    steps.append(
        f"To read the filings yourself, search EIN {match.ein or match.plan_name} at "
        f"{EFAST_FILING_URL}"
    )

    return steps


def claim_letter(match: PlanMatch, person: str = "") -> str:
    """A letter the participant can send, with the plan facts filled in."""

    holder = match.best_holder()
    addressee = holder.name if holder else "Plan Administrator"

    years = ""
    if match.first_year and match.last_year:
        years = f" (filings on record for {match.first_year}–{match.last_year})"

    return f"""\
To: {addressee}

Subject: Request for benefit information — {match.plan_name}

I am writing to ask whether you hold a retirement account in my name.

    Plan name:      {match.plan_name}
    Plan sponsor:   {match.sponsor_name or "not reported"}
    Employer EIN:   {match.ein or "not reported"}
    Plan number:    {match.plan_number or "not reported"}{years}

I was employed by this sponsor and believe I may have a vested balance
remaining in the plan.

Under ERISA I am entitled to a statement of my accrued benefit. Please
confirm whether an account exists in my name and, if so, provide its
current value and the options available to me.

If the plan has been terminated, merged or transferred, please tell me
where the assets were sent and who now holds them.

I can provide my Social Security number, dates of employment and proof of
identity through whatever secure channel you prefer. I have not included
my Social Security number in this letter.

    Name:            {person or "[your full name]"}
    Dates employed:  [from] to [to]
    Address:         [your address]
    Telephone:       [your telephone]

Thank you for your help.

{person or "[your signature]"}
"""


def _wrap(text: str, indent: str, width: int = 72) -> list[str]:
    """Wrap a sentence to the report width, keeping its indent."""

    return textwrap.wrap(
        text,
        width=width,
        initial_indent=indent,
        subsequent_indent=indent,
    ) or [indent.rstrip()]


def _match_block(match: PlanMatch, index: int) -> list[str]:
    location = ", ".join(part for part in (match.city, match.state) if part)
    participants = f"{match.participants:,}" if match.participants else "not reported"

    lines = [
        f"  {index}. {match.plan_name}",
        f"     Confidence:   {match.confidence} ({match.score:.0f}/100)",
        f"     Sponsor:      {match.sponsor_name or 'not reported'}",
        f"     EIN / plan:   {match.ein or '?'} / {match.plan_number or '?'}",
        f"     Location:     {location or 'not reported'}",
        f"     Filed for:    {match.first_year or '?'}–{match.last_year or '?'}",
        f"     Participants: {participants}",
        f"     Plan assets:  {_money(match.total_assets)}",
    ]

    if match.matched_as and match.matched_as != match.sponsor_name:
        lines.append(f"     Filed then as: {match.matched_as}")

    if match.terminated:
        lines.append(f"     ** Plan wound up — final return filed for {match.final_year} **")

    lines.append("")
    lines.append("     Why this matched:")
    for reason in match.reasons:
        lines.extend(_wrap(f"- {reason}", "       "))

    if match.holders_then:
        lines.append("")
        lines.append("     Who held the money while you were there:")
        for holder in match.holders_then[:5]:
            lines.append(f"       - {holder.role_label}: {holder.name}")
            lines.append(f"         source: {holder.citation()}")

    if match.holders_now and match.holders_now != match.holders_then:
        lines.append("")
        lines.append("     Who holds it on the most recent filing:")
        for holder in match.holders_now[:5]:
            lines.append(f"       - {holder.role_label}: {holder.name}")
            lines.append(f"         source: {holder.citation()}")

    lines.append("")
    lines.append("     What to do next:")
    for step in next_steps(match):
        lines.extend(_wrap(step, "       "))
        lines.append("")

    lines.append("")
    return lines


def _resource_block(report: TraceReport) -> list[str]:
    audiences = [Audience.ESCHEATED]
    if report.any_terminated:
        audiences.append(Audience.TERMINATED)
    if report.has_defined_benefit:
        audiences.append(Audience.PENSION)

    lines = [
        RULE,
        "WHERE TO SEARCH BY SOCIAL SECURITY NUMBER",
        RULE,
        "",
        "This report is built from Form 5500, which employers file about their",
        "plans. It records plans, not people: there is no participant list, no",
        "Social Security number and no individual balance anywhere in it. That is",
        "why nothing above can confirm an account exists in your name — only the",
        "plan's own recordkeeper, or one of the registries below, can do that.",
        "",
        "These hold participant-level data and can be searched by name or SSN:",
        "",
    ]

    for resource in for_audience(*audiences):
        lines.append(f"  {resource.name}")
        lines.append(f"    {resource.url}")
        if resource.phone:
            lines.append(f"    Telephone: {resource.phone}")
        lines.extend(_wrap(f"Holds:  {resource.holds}", "    "))
        lines.extend(_wrap(f"Needs:  {resource.needs}", "    "))
        if resource.caveat:
            lines.extend(_wrap(f"Note:   {resource.caveat}", "    "))
        lines.append("")

    if report.history.states:
        lines.extend(
            _wrap(
                f"Search the unclaimed property office of every state you have "
                f"lived or worked in — from your history that includes: "
                f"{', '.join(report.history.states)}.",
                "  ",
            )
        )
        lines.append("")

    return lines


def render_report(report: TraceReport, *, letters: bool = False) -> str:
    """The whole trace as plain text, ready to print or email."""

    history = report.history
    lines = [
        RULE,
        "RETIREMENT ACCOUNT TRACE",
        RULE,
        "",
    ]

    if history.person:
        lines.append(f"Prepared for:   {history.person}")
    lines.append(f"Prepared on:    {date.today():%d %B %Y}")
    lines.append(f"Jobs searched:  {len(history)}")

    if report.years_searched:
        span = f"{report.years_searched[0]}–{report.years_searched[-1]}"
        lines.append(f"Form years held locally: {span}")
    else:
        lines.append("Form years held locally: none — no data has been imported yet")

    lines.append(f"Plans found:    {report.total_matches}")
    lines.append("")

    lines.append("What this is")
    lines.append(THIN)
    lines.extend(
        [
            "Every employer-sponsored retirement plan covered by ERISA files a",
            "Form 5500 each year, and the Department of Labor publishes them. This",
            "report matches your work history against those filings to identify the",
            "plans your employers ran, and the firms that held the money.",
            "",
            "It cannot tell you whether you personally have a balance. Form 5500",
            "carries no participant records at all. What it gives you is the plan's",
            "exact identity and who to ask — which is what you need before anyone",
            "will look you up.",
            "",
        ]
    )

    for trace in report.traces:
        lines.append(RULE)
        lines.append(f"JOB: {trace.job.label}")
        if trace.job.note:
            lines.append(f"     note: {trace.job.note}")
        lines.append(RULE)
        lines.append("")

        if not trace.found:
            lines.extend(
                [
                    "  No plan matched this employer in the form years held locally.",
                    "",
                    "  That does not mean there was no plan. Common reasons:",
                    "    - The years you worked there are not imported. Import them",
                    "      from the Data tab and run the trace again.",
                    "    - The employer filed under a different legal name.",
                    "    - Small plans with fewer than 100 participants file the",
                    "      short Form 5500-SF, and one-participant plans file Form",
                    "      5500-EZ with the IRS, which is not public.",
                    "    - Government and many church employers are exempt from",
                    "      filing altogether.",
                    "",
                    "  Try the registries at the end of this report, which do not",
                    "  depend on the employer having filed.",
                    "",
                ]
            )
            continue

        lines.append(f"  {len(trace.matches)} plan(s) could cover this job:")
        lines.append("")

        for index, match in enumerate(trace.matches, start=1):
            lines.extend(_match_block(match, index))

    lines.extend(_resource_block(report))

    if letters:
        lines.append(RULE)
        lines.append("LETTERS TO SEND")
        lines.append(RULE)
        lines.append("")
        for trace in report.jobs_with_matches:
            strongest = trace.strongest
            if strongest is None:
                continue
            lines.append(THIN)
            lines.append(f"For: {strongest.plan_name}")
            lines.append(THIN)
            lines.append("")
            lines.append(claim_letter(strongest, history.person))
            lines.append("")

    lines.extend(
        [
            RULE,
            "IMPORTANT",
            RULE,
            "",
            "This report describes what public Form 5500 filings say. It is not",
            "financial, legal or tax advice, and it is not confirmation that any",
            "account exists in your name.",
            "",
            "Never send your Social Security number in an email, and never give it",
            "to anyone who contacted you first. The registries listed above are the",
            "only places it belongs, and you reach them by typing their address",
            "into your browser yourself.",
            "",
        ]
    )

    return "\n".join(lines)


def resource_summary() -> list[Resource]:
    """Every registry, for the UI panel."""

    return list(for_audience(*Audience))
