"""Types shared across the licensing layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class LicenseState(StrEnum):
    """What the application may do right now."""

    #: Activated and confirmed by the store within the revalidation window.
    ACTIVE = "ACTIVE"
    #: Activated, but the store has not been reachable recently. Still usable
    #: until the grace period runs out — a customer must never be locked out
    #: because the seller's infrastructure is unreachable.
    GRACE = "GRACE"
    #: No licence has been activated on this machine.
    UNLICENSED = "UNLICENSED"
    #: The store says this key is no longer valid: refunded, charged back or
    #: revoked by hand.
    REVOKED = "REVOKED"
    #: The key is valid but already activated on as many machines as allowed.
    SEAT_LIMIT = "SEAT_LIMIT"
    #: Offline for longer than the grace period allows.
    EXPIRED_GRACE = "EXPIRED_GRACE"

    @property
    def allows_use(self) -> bool:
        return self in {LicenseState.ACTIVE, LicenseState.GRACE}


@dataclass(slots=True)
class LicenseStatus:
    """The current licensing position, as the UI and CLI should present it."""

    state: LicenseState
    message: str = ""

    key_suffix: str | None = None
    customer_email: str | None = None
    activation_limit: int | None = None
    activation_count: int | None = None
    last_validated: datetime | None = None
    grace_days_remaining: int | None = None

    @property
    def allows_use(self) -> bool:
        return self.state.allows_use

    @property
    def is_activated(self) -> bool:
        return self.state not in {LicenseState.UNLICENSED, LicenseState.REVOKED}

    def headline(self) -> str:
        """A single line suitable for a status bar or `license status`."""

        match self.state:
            case LicenseState.ACTIVE:
                return f"Licensed to {self.customer_email or 'this machine'}"
            case LicenseState.GRACE:
                days = self.grace_days_remaining
                return (
                    "Licensed — could not reach the licence server"
                    + (f", {days} day(s) of offline use remaining" if days is not None else "")
                )
            case LicenseState.SEAT_LIMIT:
                return "This licence is already in use on the maximum number of machines"
            case LicenseState.REVOKED:
                return "This licence is no longer valid"
            case LicenseState.EXPIRED_GRACE:
                return "Offline for too long — reconnect to confirm the licence"
            case _:
                return "Not activated"


@dataclass(slots=True)
class ActivationResult:
    """What an activation attempt produced."""

    ok: bool
    state: LicenseState
    message: str
    instance_id: str | None = None
    customer_email: str | None = None
    activation_limit: int | None = None
    activation_count: int | None = None
    raw: dict = field(default_factory=dict)


class LicenseError(Exception):
    """Raised when the licence layer cannot complete an operation."""


class LicenseNetworkError(LicenseError):
    """
    The licence server could not be reached.

    Kept separate from other failures because it must never be treated as "not
    licensed" — that is the difference between a grace period and locking a
    paying customer out.
    """


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
