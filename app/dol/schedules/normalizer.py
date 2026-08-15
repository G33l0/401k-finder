"""
Backwards-compatible alias for :mod:`app.dol.normalizer`.

The normalizers are used by the layout loader as well as by the schedule
definitions, so they live one level up to keep ``app.dol.layouts`` and
``app.dol.schedules`` from importing each other. This module keeps the original
import path working.
"""

from app.dol.normalizer import *  # noqa: F401,F403
from app.dol.normalizer import __all__  # noqa: F401
