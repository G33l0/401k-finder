"""Types shared across the licensing layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum


class LicenseState(StrEnum):
    """What the application may do right now."""

    #: A valid key for this machine is installed.
    ACTIVE = "ACTIVE"
    #: No licence key has been entered on this machine.
    UNLICENSED = "UNLICENSED"
    #: The text is not a key, or its signature does not check out.
    INVALID = "INVALID"
    #: A genuine key, issued for a different computer.
    WRONG_MACHINE = "WRONG_MACHINE"
    #: A genuine key for this computer, past its expiry date.
    EXPIRED = "EXPIRED"

    @property
    def allows_use(self) -> bool:
        return self is LicenseState.ACTIVE


@dataclass(slots=True)
class LicenseStatus:
    """The current licensing position, as the UI and CLI should present it."""

    state: LicenseState
    message: str = ""

    label: str | None = None
    expires: date | None = None
    days_remaining: int | None = None
    activated_at: datetime | None = None

    @property
    def allows_use(self) -> bool:
        return self.state.allows_use

    def headline(self) -> str:
        """A single line suitable for a status bar or `license status`."""

        match self.state:
            case LicenseState.ACTIVE:
                who = f"Licensed to {self.label}" if self.label else "Licensed"
                if self.expires is None:
                    return who
                return f"{who} — expires {self.expires:%d %B %Y}"
            case LicenseState.WRONG_MACHINE:
                return "This licence key belongs to a different computer"
            case LicenseState.EXPIRED:
                return "This licence has expired"
            case LicenseState.INVALID:
                return "This licence key is not valid"
            case _:
                return "Not activated"


@dataclass(slots=True)
class ActivationResult:
    """What an activation attempt produced."""

    ok: bool
    state: LicenseState
    message: str
    label: str | None = None
    expires: date | None = None


class LicenseError(Exception):
    """Raised when the licence layer cannot complete an operation."""


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
