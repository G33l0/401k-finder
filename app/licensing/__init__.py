"""
Licence keys for paid installations.

Off by default: with no public key configured in ``config.py`` every check
passes, which is what you want while developing. A release build sets one,
after which a key is required.

Keys are issued by the owner in reply to an email and checked entirely on the
customer's machine — there is no store, no payment provider and no licence
server. See ``docs/SELLING.md``.

    from app.licensing import get_gate

    status = get_gate().status()
    if not status.allows_use:
        ...
"""

from app.licensing.config import LicenseConfig, get_config
from app.licensing.fingerprint import machine_fingerprint, machine_label
from app.licensing.gate import LicenseGate, get_gate, reset_gate
from app.licensing.models import (
    ActivationResult,
    LicenseError,
    LicenseState,
    LicenseStatus,
)

__all__ = (
    "ActivationResult",
    "LicenseConfig",
    "LicenseError",
    "LicenseGate",
    "LicenseState",
    "LicenseStatus",
    "get_config",
    "get_gate",
    "machine_fingerprint",
    "machine_label",
    "reset_gate",
)
