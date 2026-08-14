from __future__ import annotations

from app.dol.schedules.registry import ScheduleRegistry
from app.dol.schedules.schedule_a import definition as schedule_a
from app.dol.schedules.schedule_c import definition as schedule_c
from app.dol.schedules.schedule_d import definition as schedule_d
from app.dol.schedules.schedule_h import definition as schedule_h
from app.dol.schedules.schedule_i import definition as schedule_i
from app.dol.schedules.schedule_r import definition as schedule_r


def build_default_registry() -> ScheduleRegistry:
    registry = ScheduleRegistry()

    factories = (
        schedule_a,
        schedule_c,
        schedule_d,
        schedule_h,
        schedule_i,
        schedule_r,
    )

    for factory in factories:
        registry.register(factory(2025))

    return registry