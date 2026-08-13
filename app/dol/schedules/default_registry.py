from __future__ import annotations

from app.core.constants import SUPPORTED_FORM_YEARS
from app.dol.schedules.registry import ScheduleRegistry
from app.dol.schedules.schedule_a import definition as schedule_a
from app.dol.schedules.schedule_c import definition as schedule_c
from app.dol.schedules.schedule_d import definition as schedule_d
from app.dol.schedules.schedule_g import definition as schedule_g
from app.dol.schedules.schedule_h import definition as schedule_h
from app.dol.schedules.schedule_i import definition as schedule_i
from app.dol.schedules.schedule_r import definition as schedule_r


def build_default_registry() -> ScheduleRegistry:
    """
    Build the initial schedule registry.

    This registers schedule identities without falsely claiming that
    every schedule existed with identical fields in every year.
    """

    registry = ScheduleRegistry()

    factories = (
        schedule_a,
        schedule_c,
        schedule_d,
        schedule_g,
        schedule_h,
        schedule_i,
        schedule_r,
    )

    for year in SUPPORTED_FORM_YEARS:
        for factory in factories:
            registry.register(factory(year))

    return registry