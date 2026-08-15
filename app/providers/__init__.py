"""
Provider identity: grouping filed organisation names into recognisable firms.
"""

from app.providers.normalizer import (
    BRANDS,
    Brand,
    NormalizedProvider,
    normalize_provider,
)

__all__ = ("BRANDS", "Brand", "NormalizedProvider", "normalize_provider")
