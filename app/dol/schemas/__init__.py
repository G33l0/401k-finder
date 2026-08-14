from importlib import import_module


def get_2025_form_5500_schema():
    return import_module(
        "app.dol.schemas.2025"
    )


__all__ = (
    "get_2025_form_5500_schema",
)