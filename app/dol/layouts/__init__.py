"""
Authoritative DOL Form 5500 record layouts.

Every dataset published on the EBSA Form 5500 dataset page ships with a
machine-readable layout file::

    https://askebsa.dol.gov/FOIA Files/<year>/Latest/<dataset>_<year>_Latest_layout.txt

    FIELD_POSITION,FIELD_NAME,TYPE,SIZE (only for text fields)
    ===========================================
    1,ACK_ID,TEXT,30
    2,FORM_PLAN_YEAR_BEGIN_DATE,TEXT,10
    ...

Those files are the single source of truth for this application. They are
vendored under ``layouts/data/<year>.json`` so the application can parse,
validate and import DOL data with no network access, and refreshed by
``scripts/refresh_layouts.py``.
"""

from app.dol.layouts.loader import (
    FieldDefinition,
    Layout,
    available_datasets,
    available_years,
    get_layout,
    has_layout,
    iter_layouts,
    load_year,
)

__all__ = (
    "FieldDefinition",
    "Layout",
    "available_datasets",
    "available_years",
    "get_layout",
    "has_layout",
    "iter_layouts",
    "load_year",
)
