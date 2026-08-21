"""
Telephone numbers that are actually in the filings.

The curated directory in app.providers.directory covers the national
recordkeepers. Most plans are not served by one of those, and for a small plan
the filings themselves carry a number: Schedule I and the 5500-SF both record
the telephone of the trustee or custodian holding the assets, and both filing
forms record the plan administrator's.

Those beat anything curated, because the employer filed them under penalty and
they name the specific office rather than a national queue. Nothing here needs
a re-import: the importer already stores every non-empty column of a schedule
row, so these numbers are in the database of anyone who has imported the year.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import ProviderRole
from app.database.models import Filing, Plan, ScheduleRecord
from app.dol.provider_extractor import is_placeholder_name

#: (dataset, name column, telephone column, role) for the asset holders.
HOLDER_FIELDS: tuple[tuple[str, str, str, str], ...] = (
    ("F_SCH_I", "FDCRY_TRUSTEE_CUST_NAME", "FDCRY_TRUST_CUST_PHONE_NUM", ProviderRole.TRUSTEE),
    (
        "F_SCH_C_PART3",
        "PROVIDER_TERM_NAME",
        "PROVIDER_TERM_PHONE_NUM",
        ProviderRole.TERMINATED_ACCOUNTANT,
    ),
)



@dataclass(frozen=True, slots=True)
class FiledContact:
    """A telephone number an employer filed, and who it belongs to."""

    name: str
    phone: str
    role: str
    form_year: int
    dataset: str
    field: str

    @property
    def role_label(self) -> str:
        return self.role.replace("_", " ").title()

    def citation(self) -> str:
        return f"{self.dataset}, field {self.field}, form year {self.form_year}"


def format_phone(value: str | None) -> str:
    """Group a filed number so a person can read it back over a phone."""

    if not value:
        return ""

    digits = "".join(character for character in str(value) if character.isdigit())

    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"1-{digits[1:4]}-{digits[4:7]}-{digits[7:]}"

    return str(value).strip()


def _rows(session: Session, plan_id: int, dataset: str) -> list[ScheduleRecord]:
    return list(
        session.execute(
            select(ScheduleRecord)
            .where(ScheduleRecord.plan_id == plan_id, ScheduleRecord.dataset == dataset)
            .order_by(ScheduleRecord.form_year.desc())
        ).scalars()
    )


def for_plan(session: Session, plan_id: int) -> list[FiledContact]:
    """
    Every telephone number filed for one plan, most recent first.

    One entry per name and role: a plan filing the same trustee for ten years
    should produce one line, not ten.
    """

    found: dict[tuple[str, str], FiledContact] = {}

    def keep(name, phone, role, year, dataset, field) -> None:  # noqa: ANN001
        cleaned = format_phone(phone)
        label = (name or "").strip()
        if not cleaned or not label or is_placeholder_name(label):
            return

        key = (label.upper(), str(role))
        existing = found.get(key)
        if existing is None or year > existing.form_year:
            found[key] = FiledContact(label, cleaned, str(role), year, dataset, field)

    for dataset, name_field, phone_field, role in HOLDER_FIELDS:
        for row in _rows(session, plan_id, dataset):
            keep(
                row.raw_data.get(name_field),
                row.raw_data.get(phone_field),
                role,
                row.form_year,
                dataset,
                phone_field,
            )

    # The filing forms do not go through schedule_records, so these come off
    # the filing row itself. They are empty until the year is imported again
    # under schema 6, and a blank simply means "not filed".
    filings = session.execute(
        select(Filing).where(Filing.plan_id == plan_id).order_by(Filing.form_year.desc())
    ).scalars()

    for filing in filings:
        keep(
            filing.admin_name,
            filing.admin_phone,
            ProviderRole.ADMINISTRATOR,
            filing.form_year,
            filing.source_dataset or "F_5500",
            "ADMIN_PHONE_NUM",
        )
        keep(
            _trustee_name(session, filing),
            filing.trustee_custodian_phone,
            ProviderRole.TRUSTEE,
            filing.form_year,
            filing.source_dataset or "F_5500_SF",
            "SF_FDCRY_TRUSTE_CUST_PHONE_NUM",
        )

    sponsor = session.get(Plan, plan_id)
    if sponsor is not None and sponsor.sponsor_phone:
        year = sponsor.last_year or 0
        keep(
            sponsor.sponsor_name,
            sponsor.sponsor_phone,
            "SPONSOR",
            year,
            "F_5500",
            "SPONS_DFE_PHONE_NUM",
        )

    return sorted(found.values(), key=lambda item: (-item.form_year, item.role_label))


def _trustee_name(session: Session, filing: Filing) -> str:
    """The trustee this filing named, for attaching its telephone to."""

    for party in getattr(filing.plan, "parties", ()) or ():
        if party.role == ProviderRole.TRUSTEE and party.form_year == filing.form_year:
            return party.provider.name if party.provider else (party.reported_name or "")

    return ""


def phone_for(session: Session, plan_id: int, provider_name: str) -> FiledContact | None:
    """The filed number for one firm, when the plan filed one."""

    wanted = (provider_name or "").strip().upper()
    if not wanted:
        return None

    for contact in for_plan(session, plan_id):
        if contact.name.upper() == wanted:
            return contact

    return None


def administrator(session: Session, plan_id: int) -> FiledContact | None:
    """
    The plan administrator, who has to answer a participant in writing.

    When nobody else is reachable this is the one contact with an obligation.
    """

    for contact in for_plan(session, plan_id):
        if contact.role == ProviderRole.ADMINISTRATOR:
            return contact

    return None
