"""
The policy layer: may this installation be used right now?

Everything else in this package reports facts. This decides what to do with
them, and the decisions are deliberately biased towards letting a paying
customer work:

* An unreachable licence server never blocks use. It starts a grace period.
* A revoked key does block use, because that is a refund or a chargeback.
* A seat limit blocks activation, not an activation already granted.

The reasoning is simple: wrongly blocking someone who paid costs a refund and a
bad review, while wrongly allowing someone for a few more days costs almost
nothing.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.licensing import storage
from app.licensing.config import LicenseConfig, get_config
from app.licensing.fingerprint import machine_fingerprint, machine_label
from app.licensing.models import (
    ActivationResult,
    LicenseNetworkError,
    LicenseState,
    LicenseStatus,
    utcnow,
)
from app.licensing.providers import build_provider
from app.licensing.storage import ActivationRecord

logger = get_logger(__name__)


class LicenseGate:
    """Answers whether the application is licensed, and activates it."""

    def __init__(self, config: LicenseConfig | None = None) -> None:
        self.config = config or get_config()
        self.provider = build_provider(self.config)

    # ------------------------------------------------------------------

    def status(self, force_check: bool = False) -> LicenseStatus:
        """
        Report the current licensing position.

        The store is only contacted when the local record is stale, so ordinary
        start-ups cost nothing and work offline.
        """

        if not self.config.enforced:
            return LicenseStatus(
                state=LicenseState.ACTIVE,
                message="Licensing is not enabled in this build.",
            )

        record = storage.load()

        if record is None:
            return LicenseStatus(
                state=LicenseState.UNLICENSED,
                message="No licence has been activated on this machine.",
            )

        age = record.days_since_validation()

        if not force_check and age < self.config.revalidate_days:
            return self._status_from(record, LicenseState.ACTIVE)

        try:
            result = self.provider.validate(record.key, record.instance_id)
        except LicenseNetworkError as exc:
            logger.info("Licence server unreachable (%s); continuing on the grace period.", exc)
            return self._grace_status(record)

        if result.state is LicenseState.REVOKED:
            # Stop trusting a key the store has disowned, but keep the record so
            # the customer sees which key was refused rather than a bare prompt.
            return self._status_from(record, LicenseState.REVOKED, result.message)

        if not result.ok:
            return self._status_from(record, LicenseState.UNLICENSED, result.message)

        record.touch()
        if result.customer_email:
            record.customer_email = result.customer_email
        if result.activation_limit is not None:
            record.activation_limit = result.activation_limit
        if result.activation_count is not None:
            record.activation_count = result.activation_count

        storage.save(record)

        return self._status_from(record, LicenseState.ACTIVE)

    def allows_use(self) -> bool:
        return self.status().allows_use

    # ------------------------------------------------------------------

    def activate(self, key: str) -> ActivationResult:
        """Activate a licence key on this machine."""

        key = key.strip()

        if not key:
            return ActivationResult(False, LicenseState.UNLICENSED, "Enter a licence key.")

        if not self.config.enforced:
            return ActivationResult(
                True, LicenseState.ACTIVE, "Licensing is not enabled in this build."
            )

        fingerprint = machine_fingerprint()

        try:
            result = self.provider.activate(key, fingerprint, machine_label())
        except LicenseNetworkError as exc:
            # Activation genuinely needs the network — there is nothing stored
            # yet to fall back on — so say so plainly rather than blaming the key.
            return ActivationResult(
                False,
                LicenseState.UNLICENSED,
                f"Could not reach the licence server. Check your connection and try again. ({exc})",
            )

        if not result.ok:
            return result

        now = utcnow().isoformat()
        storage.save(
            ActivationRecord(
                key=key,
                fingerprint=fingerprint,
                activated_at=now,
                last_validated=now,
                instance_id=result.instance_id,
                customer_email=result.customer_email,
                activation_limit=result.activation_limit,
                activation_count=result.activation_count,
            )
        )

        logger.info("Licence activated on this machine.")
        return result

    def deactivate(self) -> ActivationResult:
        """
        Release this machine's activation so the licence can be used elsewhere.

        The local record is removed even when the store cannot be reached: the
        customer asked to stop using it here, and refusing would leave them
        unable to move machines while offline.
        """

        record = storage.load()

        if record is None:
            return ActivationResult(
                True, LicenseState.UNLICENSED, "No licence is active on this machine."
            )

        message = "Licence released from this machine."

        if self.config.enforced and record.instance_id:
            try:
                result = self.provider.deactivate(record.key, record.instance_id)
                message = result.message
            except LicenseNetworkError:
                message = (
                    "Removed from this machine, but the licence server could not be "
                    "reached — the seat may still show as in use until it is checked again."
                )

        storage.clear()
        return ActivationResult(True, LicenseState.UNLICENSED, message)

    # ------------------------------------------------------------------

    def _status_from(
        self,
        record: ActivationRecord,
        state: LicenseState,
        message: str = "",
    ) -> LicenseStatus:
        return LicenseStatus(
            state=state,
            message=message,
            key_suffix=record.key_suffix,
            customer_email=record.customer_email,
            activation_limit=record.activation_limit,
            activation_count=record.activation_count,
            last_validated=record.validated_at(),
        )

    def _grace_status(self, record: ActivationRecord) -> LicenseStatus:
        age = record.days_since_validation()
        remaining = self.config.grace_days - age

        if remaining <= 0:
            return self._status_from(
                record,
                LicenseState.EXPIRED_GRACE,
                (
                    f"This licence has not been confirmed for {int(age)} days. "
                    f"Connect to the internet to continue."
                ),
            )

        status = self._status_from(record, LicenseState.GRACE)
        status.grace_days_remaining = max(int(remaining), 0)
        return status


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
