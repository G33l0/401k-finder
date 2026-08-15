from __future__ import annotations

from functools import lru_cache

from app.dol.layouts import available_years
from app.dol.schedules import (
    schedule_a,
    schedule_actuarial,
    schedule_c,
    schedule_d,
    schedule_form,
    schedule_g,
    schedule_group,
    schedule_h,
    schedule_i,
    schedule_r,
)
from app.dol.schedules.registry import ScheduleRegistry

#: Each module reports the datasets it covers for a given year, skipping the
#: ones DOL did not publish that year.
_MODULES = (
    schedule_form,
    schedule_a,
    schedule_c,
    schedule_d,
    schedule_g,
    schedule_h,
    schedule_i,
    schedule_r,
    schedule_actuarial,
    schedule_group,
)


def build_registry(form_years: tuple[int, ...] | None = None) -> ScheduleRegistry:
    """Build a registry covering the requested years, or every vendored year."""

    years = form_years if form_years is not None else available_years()
    registry = ScheduleRegistry()

    for year in years:
        for module in _MODULES:
            for definition in module.definitions(year):
                registry.register(definition)

    return registry


@lru_cache(maxsize=1)
def build_default_registry() -> ScheduleRegistry:
    """Return the shared registry for every year this build supports."""

    return build_registry()
