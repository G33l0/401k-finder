"""Schedule C: service provider information, and its Part 1-3 detail tables."""

from __future__ import annotations

from app.dol.layouts import has_layout
from app.dol.schedules.base import ScheduleDefinition

_PARTS: tuple[tuple[str, str, str, tuple[str, ...], str], ...] = (
    (
        "F_SCH_C",
        "C",
        "Schedule C - Service Provider Information",
        (),
        "Base Schedule C record. The provider detail lives in the Part 1-3 "
        "tables, which is why this dataset carries no provider name column.",
    ),
    (
        "F_SCH_C_PART1_ITEM1",
        "C-1-1",
        "Schedule C Part 1 Item 1 - Eligible Indirect Compensation",
        ("PROVIDER_ELIGIBLE_NAME",),
        "Providers receiving only eligible indirect compensation.",
    ),
    (
        "F_SCH_C_PART1_ITEM2",
        "C-1-2",
        "Schedule C Part 1 Item 2 - Service Providers and Compensation",
        ("PROVIDER_OTHER_NAME",),
        "The richest provider source in the whole dataset: each row names a "
        "provider, its service codes and what the plan paid it. Service codes "
        "distinguish recordkeeper from trustee, custodian and investment manager.",
    ),
    (
        "F_SCH_C_PART1_ITEM3",
        "C-1-3",
        "Schedule C Part 1 Item 3 - Indirect Compensation Detail",
        ("PROVIDER_INDIRECT_NAME", "PROVIDER_PAYOR_NAME"),
        "Providers receiving indirect compensation, and who paid it.",
    ),
    (
        "F_SCH_C_PART2",
        "C-2",
        "Schedule C Part 2 - Providers Failing to Supply Information",
        ("PROVIDER_FAIL_NAME",),
        "Providers that did not supply the compensation information required.",
    ),
    (
        "F_SCH_C_PART3",
        "C-3",
        "Schedule C Part 3 - Terminated Accountants and Actuaries",
        ("PROVIDER_TERM_NAME",),
        "Accountants and actuaries terminated during the plan year.",
    ),
)


def definitions(form_year: int) -> tuple[ScheduleDefinition, ...]:
    return tuple(
        ScheduleDefinition(
            code=code,
            name=name,
            form_year=form_year,
            dataset=dataset,
            provider_columns=providers,
            notes=notes,
            aliases=(dataset.removeprefix("F_"),),
        )
        for dataset, code, name, providers, notes in _PARTS
        if has_layout(form_year, dataset)
    )
