"""
The official places an individual can look for a lost retirement account.

This application searches Form 5500, which is plan-level: it names employers,
plans and the firms that hold the money, and it is the fastest way to work out
*who to write to*. It contains no participant records at all, so it can never
answer "is there an account in my name" directly.

The registries below can, because they hold participant-level data this
application has no access to. Several of them identify you by Social Security
number, which is exactly where an SSN belongs — behind government identity
verification, not typed into a desktop application.

Presenting these alongside the search results is not a disclaimer. For a
participant whose old employer was acquired, dissolved, or terminated its plan,
one of these is usually the answer, and the Form 5500 search is what tells them
which one to try.

.. note::

   Government URLs and phone numbers drift. Check them before a release —
   ``python -m scripts.check_resources`` fetches each one and reports what it
   got.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Audience(StrEnum):
    """Who a resource is useful to, so the UI can lead with the right ones."""

    #: Everyone should try this.
    EVERYONE = "EVERYONE"
    #: The plan was terminated, or the employer no longer exists.
    TERMINATED = "TERMINATED"
    #: A defined benefit pension rather than an account balance.
    PENSION = "PENSION"
    #: Small balances that were cashed out and handed to the state.
    ESCHEATED = "ESCHEATED"


@dataclass(frozen=True, slots=True)
class Resource:
    """One place to look, and what it can actually tell you."""

    name: str
    url: str
    audience: Audience

    #: What this holds that Form 5500 does not.
    holds: str
    #: What the person needs in order to use it.
    needs: str
    #: The honest limitation.
    caveat: str = ""
    phone: str = ""

    @property
    def uses_ssn(self) -> bool:
        return "Social Security number" in self.needs


#: Ordered by how often they are the answer.
RESOURCES: tuple[Resource, ...] = (
    Resource(
        name="Retirement Savings Lost and Found (U.S. Department of Labor)",
        url="https://lostandfound.dol.gov/",
        audience=Audience.EVERYONE,
        holds=(
            "A federal registry of retirement benefits owed to people who have left "
            "an employer, built from what plans report to the government. Created by "
            "the SECURE 2.0 Act and run by EBSA."
        ),
        needs=(
            "A Login.gov account and your Social Security number, entered on the "
            "government's own site after it verifies your identity."
        ),
        caveat=(
            "It is new, and populated from data plans have only recently been "
            "required to report, so an older account may not appear yet. A blank "
            "result is not proof that nothing is owed to you."
        ),
    ),
    Resource(
        name="National Registry of Unclaimed Retirement Benefits",
        url="https://www.unclaimedretirementbenefits.com/",
        audience=Audience.EVERYONE,
        holds="Unclaimed balances that plan administrators have chosen to list.",
        needs="Your Social Security number. Searching is free.",
        caveat=(
            "Private and voluntary — a plan only appears if its administrator "
            "signed up, so this covers a fraction of plans."
        ),
    ),
    Resource(
        name="PBGC — find an unclaimed pension",
        url="https://www.pbgc.gov/workers-retirees/find-unclaimed-retirement-benefits/search-unclaimed",
        audience=Audience.TERMINATED,
        holds=(
            "Benefits from terminated plans whose sponsors handed them to the "
            "Pension Benefit Guaranty Corporation, including terminated defined "
            "contribution plans since 2018."
        ),
        needs="Your name and the employer's name. Searchable without an SSN.",
        caveat="Only plans that actually transferred benefits to PBGC.",
        phone="1-800-400-7242",
    ),
    Resource(
        name="Social Security Administration — potential private pension benefits",
        url="https://www.ssa.gov/",
        audience=Audience.EVERYONE,
        holds=(
            "Notices derived from Form 8955-SSA, which plans file with the IRS "
            "listing separated participants who left a vested benefit behind. This "
            "is the one government record that ties a person to a specific plan."
        ),
        needs="Your Social Security number, in a request to SSA.",
        caveat=(
            "Form 8955-SSA is filed with the IRS and is not public, so no third "
            "party can search it for you — you have to ask SSA yourself. SSA "
            "normally sends the notice automatically when you claim benefits."
        ),
        phone="1-800-772-1213",
    ),
    Resource(
        name="Your state's unclaimed property office",
        url="https://unclaimed.org/",
        audience=Audience.ESCHEATED,
        holds=(
            "Small balances that were cashed out of a plan and turned over to the "
            "state, and abandoned IRAs. A common resting place for accounts under "
            "$1,000 left behind at a job you held briefly."
        ),
        needs="Your name and the states you have lived in.",
        caveat="Search every state you have lived or worked in, not just the current one.",
    ),
    Resource(
        name="EBSA Benefits Advisors (free help from the Department of Labor)",
        url="https://www.askebsa.dol.gov/",
        audience=Audience.EVERYONE,
        holds=(
            "People whose job is to help participants get benefits out of a plan "
            "that is not responding. They can contact a plan administrator on your "
            "behalf."
        ),
        needs="Your account of what happened, and the plan's name and EIN.",
        caveat="Worth using once a plan has ignored you, not before.",
        phone="1-866-444-3272",
    ),
    Resource(
        name="EFAST2 — read the plan's own filings",
        url="https://www.efast.dol.gov/5500search/",
        audience=Audience.EVERYONE,
        holds=(
            "The complete Form 5500 filings behind everything this application "
            "shows, including the signed originals and attachments."
        ),
        needs="The plan's name or the sponsor's EIN — both shown in your results.",
        caveat="Plan-level only. Like this application, it holds no participant records.",
    ),
)


def for_audience(*audiences: Audience) -> tuple[Resource, ...]:
    """The resources relevant to a situation, always including the universal ones."""

    wanted = set(audiences) | {Audience.EVERYONE}
    return tuple(resource for resource in RESOURCES if resource.audience in wanted)
