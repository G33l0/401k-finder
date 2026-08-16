"""
Licence activation for paid installations.

Off by default: with no store configured in ``config.py`` every check passes,
which is what you want while developing. A release build sets a provider and a
product id, after which the application requires activation.

    from app.licensing import get_gate

    status = get_gate().status()
    if not status.allows_use:
        ...
"""

from app.licensing.config import LicenseConfig, Provider, get_config
from app.licensing.fingerprint import machine_fingerprint, machine_label
from app.licensing.gate import LicenseGate, get_gate, reset_gate
from app.licensing.models import (
    ActivationResult,
    LicenseError,
    LicenseNetworkError,
    LicenseState,
    LicenseStatus,
)

__all__ = (
    "ActivationResult",
    "LicenseConfig",
    "LicenseError",
    "LicenseGate",
    "LicenseNetworkError",
    "LicenseState",
    "LicenseStatus",
    "Provider",
    "get_config",
    "get_gate",
    "machine_fingerprint",
    "machine_label",
    "reset_gate",
)
