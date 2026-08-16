"""
The policy layer: may this installation be used right now?

The whole check is local. A key is a signature over the machine it was issued
for, so verifying it needs nothing but the public key compiled into the build —
no network, no account, no server to keep running. That removes the failure
this layer used to have to work around entirely: there is no outage that can
lock out someone who has paid, because there is nothing to be down.
"""

from __future__ import annotations

from datetime import date

from app.core.logging import get_logger
from app.licensing import keys, storage
from app.licensing.config import LicenseConfig, get_config
from app.licensing.fingerprint import machine_fingerprint
from app.licensing.models import ActivationResult, LicenseState, LicenseStatus

logger = get_logger(__name__)


class LicenseGate:
    """Answers whether the application is licensed, and installs a key."""

    def __init__(self, config: LicenseConfig | None = None) -> None:
        self.config = config or get_config()

    # ------------------------------------------------------------------

    def status(self, today: date | None = None) -> LicenseStatus:
        """Report the current licensing position."""

        if not self.config.enforced:
            return LicenseStatus(
                state=LicenseState.ACTIVE,
                message="Licensing is not enabled in this build.",
            )

        stored = storage.load()

        if stored is None:
            return LicenseStatus(
                state=LicenseState.UNLICENSED,
                message="No licence key has been entered on this computer.",
            )

        outcome = keys.check(
            stored.key, self.config.public_key, machine_fingerprint(), today=today
        )

        return LicenseStatus(
            state=outcome.state,
            message=outcome.message,
            label=outcome.key.label or None if outcome.key else None,
            expires=outcome.key.expires if outcome.key else None,
            days_remaining=outcome.key.days_remaining(today) if outcome.key else None,
            activated_at=stored.activated(),
        )

    def allows_use(self) -> bool:
        return self.status().allows_use

    # ------------------------------------------------------------------

    def activate(self, key: str, today: date | None = None) -> ActivationResult:
        """
        Install a licence key on this machine.

        The key is stored only if it checks out, so a bad paste cannot leave
        the application in a state where it refuses to start and offers no way
        back in.
        """

        if not key.strip():
            return ActivationResult(False, LicenseState.UNLICENSED, "Enter your licence key.")

        if not self.config.enforced:
            return ActivationResult(
                True, LicenseState.ACTIVE, "Licensing is not enabled in this build."
            )

        outcome = keys.check(key, self.config.public_key, machine_fingerprint(), today=today)

        if not outcome.ok:
            return ActivationResult(False, outcome.state, outcome.message)

        storage.save(key)
        logger.info("Licence key accepted on this machine.")

        return ActivationResult(
            True,
            LicenseState.ACTIVE,
            "Licence activated.",
            label=outcome.key.label or None if outcome.key else None,
            expires=outcome.key.expires if outcome.key else None,
        )

    def deactivate(self) -> ActivationResult:
        """Remove the stored key from this machine."""

        if storage.load() is None:
            return ActivationResult(
                True, LicenseState.UNLICENSED, "No licence is installed on this computer."
            )

        storage.clear()
        return ActivationResult(
            True, LicenseState.UNLICENSED, "Licence removed from this computer."
        )


_gate: LicenseGate | None = None


def get_gate() -> LicenseGate:
    """Return the shared gate."""

    global _gate

    if _gate is None:
        _gate = LicenseGate()

    return _gate


def reset_gate() -> None:
    """Drop the shared gate. Used by the test suite."""

    global _gate
    _gate = None
