"""The main filing datasets: Form 5500 and Form 5500-SF."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    built: list[ScheduleDefinition] = []

    if has_layout(form_year, "F_5500"):
        built.append(
            ScheduleDefinition(
                code="5500",
                name="Form 5500 - Annual Return/Report of Employee Benefit Plan",
                form_year=form_year,
                dataset="F_5500",
                provider_columns=("ADMIN_NAME", "PREPARER_FIRM_NAME"),
                notes=(
                    "The main form. Establishes plan identity (EIN + plan number), "
                    "the plan characteristics codes that classify the plan, and "
                    "which schedules were attached."
                ),
                aliases=("5500", "FORM_5500"),
            )
        )

    if has_layout(form_year, "F_5500_SF"):
        built.append(
            ScheduleDefinition(
                code="5500-SF",
                name="Form 5500-SF - Short Form Annual Return/Report",
                form_year=form_year,
                dataset="F_5500_SF",
                provider_columns=(
                    "SF_FDCRY_TRUSTE_CUST_NAME",
                    "SF_FDCRY_TRUST_NAME",
                    "SF_ADMIN_NAME",
                    "SF_PREPARER_FIRM_NAME",
                ),
                notes=(
                    "Filed by small plans. Self-contained: it carries plan "
                    "identity, financials and the trustee/custodian name without "
                    "any attached schedule, so it is the single most productive "
                    "dataset for small-employer 401(k) plans."
                ),
                aliases=("5500_SF", "FORM_5500_SF"),
            )
        )

    return tuple(built)
