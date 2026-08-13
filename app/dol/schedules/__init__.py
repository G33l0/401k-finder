"""
Form 5500 schedule processing.

Schedule availability and field definitions vary by filing year.
The schedule system therefore separates:

1. schedule identification,
2. year-specific metadata,
3. raw record preservation,
4. normalized provider extraction.
"""

from app.dol.schedules.base import ScheduleDefinition
from app.dol.schedules.registry import ScheduleRegistry

__all__ = [
    "ScheduleDefinition",
    "ScheduleRegistry",
]