"""
How to reach a provider, for someone chasing their own account.

No DOL dataset carries a website. Across all 448 published record layouts and
1,278 distinct field names there is not one URL field, and the only telephone
numbers are for the plan administrator, the sponsor, the trustee or custodian
of a small plan, and a terminated accountant. None of those is the participant
service line a person actually needs.

So this is a curated directory, shipped as data. It is the application's
addition, not something filed with the Department of Labor, and everything
that displays it has to say so. A wrong number for somebody's retirement money
is worse than no number, which is why each entry carries the firm's own website
alongside the telephone: the website is the thing to check the number against.

`successor` matters more than it looks. A 2012 filing naming Prudential
Retirement is not a dead end; that business is Empower now, and Empower holds
the record. Somebody tracing a twenty-year career needs to be told that.
"""

from __future__ import annotations

from dataclasses import dataclass

#: When these entries were last checked against the firms' own websites.
LAST_REVIEWED = "2026-08"

DISCLAIMER = (
    "Contact details are added by this application, not filed with the "
    "Department of Labor. Check them on the firm's own website before you call."
)


@dataclass(frozen=True, slots=True)
class Contact:
    """Where a participant reaches one firm."""

    #: Matches Brand.canonical_name in app.providers.normalizer.
    canonical_name: str

    website: str = ""
    #: The participant line where the firm publishes one, not the switchboard.
    phone: str = ""
    #: What the site is for, when the name alone does not say.
    note: str = ""
    #: The firm that took the retirement business over, and when.
    successor: str = ""

    @property
    def has_details(self) -> bool:
        return bool(self.website or self.phone)


CONTACTS: tuple[Contact, ...] = (
    Contact(
        "Fidelity Investments",
        website="https://nb.fidelity.com",
        phone="1-800-835-5097",
        note="NetBenefits is where most Fidelity workplace plans are viewed.",
    ),
    Contact(
        "Empower",
        website="https://participant.empower-retirement.com",
        phone="1-855-756-4738",
        successor=(
            "Empower now holds the plans once run by Great-West, "
            "Prudential Retirement (2022) and MassMutual's retirement business (2021)."
        ),
    ),
    Contact("Vanguard", website="https://retirementplans.vanguard.com", phone="1-800-523-1188"),
    Contact("Principal Financial Group", website="https://www.principal.com", phone="1-800-547-7754",
            successor="Principal took over Wells Fargo's institutional retirement business in 2019."),
    Contact("Voya Financial", website="https://my.voya.com", phone="1-800-584-6001",
            successor="Voya was ING's U.S. retirement business until it was renamed in 2014."),
    Contact("TIAA", website="https://www.tiaa.org", phone="1-800-842-2252",
            note="Common for university, hospital and non-profit 403(b) plans."),
    Contact("Charles Schwab", website="https://workplace.schwab.com", phone="1-800-724-7526"),
    Contact("T. Rowe Price", website="https://rps.troweprice.com", phone="1-800-922-9945"),
    Contact("John Hancock", website="https://myplan.johnhancock.com", phone="1-800-395-1113"),
    Contact("Nationwide", website="https://www.nationwide.com/personal/investing/retirement-plans",
            phone="1-800-772-2182"),
    Contact("Transamerica", website="https://www.transamerica.com", phone="1-800-755-5801"),
    Contact("Lincoln Financial", website="https://www.lincolnfinancial.com", phone="1-800-234-3500"),
    Contact("MassMutual", website="https://www.massmutual.com", phone="1-800-272-2216",
            successor="MassMutual's retirement plan business moved to Empower in 2021."),
    Contact("Equitable", website="https://equitable.com", phone="1-800-628-6673",
            successor="Known as AXA Equitable until 2020."),
    Contact("MetLife", website="https://www.metlife.com", phone="1-800-638-5433"),
    Contact("Mutual of America", website="https://www.mutualofamerica.com", phone="1-800-468-3785"),
    Contact("Securian Financial", website="https://www.securian.com", phone="1-800-233-2881"),
    Contact("American Funds / Capital Group", website="https://www.capitalgroup.com",
            phone="1-800-421-4120"),
    Contact("Ascensus", website="https://www.ascensus.com", phone="1-800-345-6363",
            successor="Ascensus acquired the Newport Group in 2022."),
    Contact("Newport Group", website="https://www.ascensus.com", phone="1-800-345-6363",
            successor="Newport Group became part of Ascensus in 2022."),
    Contact("Paychex", website="https://www.paychexflex.com", phone="1-877-244-1771"),
    Contact("ADP", website="https://www.mykplan.com", phone="1-800-695-7526"),
    Contact("Alight Solutions", website="https://www.alight.com", phone="",
            note="Alight runs each employer's plan under that employer's own site and number."),
    Contact("Milliman", website="https://www.millimanbenefits.com", phone="1-866-767-1212"),
    Contact("Pentegra", website="https://www.pentegra.com", phone="1-800-872-3473"),
    Contact("Guideline", website="https://www.guideline.com", phone="1-888-228-3491"),
    Contact("Betterment", website="https://www.betterment.com/work", phone="1-855-906-5281"),
    Contact("Human Interest", website="https://humaninterest.com", phone="1-855-622-7824"),
    Contact("Vestwell", website="https://www.vestwell.com"),
    Contact("Bank of America / Merrill", website="https://www.benefits.ml.com", phone="1-800-228-4015"),
    Contact("Wells Fargo", website="https://www.principal.com", phone="1-800-547-7754",
            successor="Wells Fargo's institutional retirement business moved to Principal in 2019."),
    Contact("Edward Jones", website="https://www.edwardjones.com", phone="1-800-441-2357"),
    Contact("Morgan Stanley", website="https://www.morganstanley.com/atwork", phone="1-888-756-2436"),
    Contact("Raymond James", website="https://www.raymondjames.com", phone="1-800-248-8863"),
    Contact("LPL Financial", website="https://www.lpl.com", phone="1-800-558-7567"),
    Contact("Northern Trust", website="https://www.northerntrust.com", phone="1-312-630-6000",
            note="A custodian. It holds plan assets and rarely deals with participants directly."),
    Contact("State Street", website="https://www.statestreet.com", phone="1-617-786-3000",
            note="A custodian. It holds plan assets and rarely deals with participants directly."),
    Contact("BNY Mellon", website="https://www.bny.com", phone="1-212-495-1784",
            note="A custodian. It holds plan assets and rarely deals with participants directly."),
    Contact("Matrix Trust / Broadridge", website="https://www.broadridge.com", phone="1-800-521-7003",
            note="A custodian, usually reached through whoever runs the plan."),
    Contact("Mid Atlantic Trust", website="https://www.macg.com", phone="1-800-693-7800",
            note="A custodian, usually reached through whoever runs the plan."),
    Contact("Pershing", website="https://www.pershing.com", phone="1-201-413-3333",
            note="A custodian, usually reached through your broker or adviser."),
    Contact("Wilmington Trust", website="https://www.wilmingtontrust.com", phone="1-800-982-4620",
            note="A trustee. It holds plan assets rather than servicing participants."),
    Contact("Reliance Trust", website="https://www.reliance-trust.com", phone="1-800-373-9698",
            note="A trustee. It holds plan assets rather than servicing participants."),
    Contact("JPMorgan Chase", website="https://www.jpmorgan.com", phone="1-800-935-9935",
            note="A trustee and custodian rather than a participant service."),
    Contact("Ameritas", website="https://www.ameritas.com", phone="1-800-745-1112",
            note="Annuity contracts, common in 403(b) plans for teachers."),
    Contact("Guardian Life", website="https://www.guardianlife.com", phone="1-888-482-7342",
            note="Annuity contracts, common in 403(b) plans."),
    Contact("Standard Insurance", website="https://www.standard.com", phone="1-800-858-5420",
            note="Annuity contracts, common in 403(b) and small pension plans."),
    Contact("Sentinel Benefits", website="https://www.sentinelgroup.com", phone="1-888-762-6088",
            note="A third-party administrator; it runs the plan for the employer."),
    Contact("July Business Services", website="https://www.julyservices.com", phone="1-888-333-5859",
            note="A third-party administrator; it runs the plan for the employer."),
)


_BY_NAME: dict[str, Contact] = {contact.canonical_name: contact for contact in CONTACTS}


def contact_for(canonical_name: str | None) -> Contact | None:
    """The directory entry for a consolidated provider name, if there is one."""

    if not canonical_name:
        return None

    return _BY_NAME.get(canonical_name.strip())


def known_names() -> tuple[str, ...]:
    return tuple(sorted(_BY_NAME))
