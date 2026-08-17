"""Schedule H — large plan financial information."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    built: list[ScheduleDefinition] = []

    if has_layout(form_year, "F_SCH_H"):
        built.append(
            ScheduleDefinition(
                code="H",
                name="Schedule H - Financial Information (Large Plans)",
                form_year=form_year,
                dataset="F_SCH_H",
                provider_columns=(
                    "FDCRY_TRUSTEE_CUST_NAME",
                    "FDCRY_TRUST_NAME",
                    "ACCOUNTANT_FIRM_NAME",
                ),
                notes=(
                    "Filed by plans with 100 or more participants. Names the "
                    "trustee or custodian holding plan assets and the auditing "
                    "accountant, and carries the full asset and fee breakdown."
                ),
                aliases=("SCH_H", "SCHEDULE_H"),
            )
        )

    if has_layout(form_year, "F_SCH_H_PART1"):
        built.append(
            ScheduleDefinition(
                code="H-1",
                name="Schedule H Part 1 - Transfers to Other Plans",
                form_year=form_year,
                dataset="F_SCH_H_PART1",
                # Deliberately no provider columns. The name here is another
                # *plan*, not a firm the plan paid, and filing it as a provider
                # both polluted the provider list and discarded the EIN and plan
                # number that make the transferee findable. It is read by
                # app.dol.transfers into plan_transfers instead.
                provider_columns=(),
                notes=(
                    "Names the plan that assets were transferred to. The only "
                    "statement in the dataset about where a wound-up plan's "
                    "money went."
                ),
                aliases=("SCH_H_PART1",),
            )
        )

    return tuple(built)
