"""Licence keys for paid installations."""

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
