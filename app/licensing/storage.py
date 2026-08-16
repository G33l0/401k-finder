"""
The activation record kept on the customer's machine.

The record is bound to the machine fingerprint by an HMAC, so copying the file
to a second machine invalidates it. That closes the obvious way to share a
purchase — hand over a file rather than a key — and nothing more.

It is worth being plain about the limit: the signing key lives inside the
application, on a machine the customer controls, in a Python build that can be
unpacked. Anyone willing to read the code can forge a record. This raises the
effort of sharing from "copy a file" to "reverse-engineer the application",
which is the honest goal of client-side licensing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import get_app_data_dir
from app.core.logging import get_logger
from app.licensing.fingerprint import machine_fingerprint
from app.licensing.models import utcnow

logger = get_logger(__name__)

#: Changing this invalidates every stored activation, forcing a re-check
#: against the store. Bump it if the record format changes meaningfully.
_SECRET = b"401k-finder-pro/activation/v1"

FILENAME = "license.json"


@dataclass(slots=True)
class ActivationRecord:
    """What is remembered between runs about an activated licence."""

    key: str
    fingerprint: str
    activated_at: str
    last_validated: str

    instance_id: str | None = None
    customer_email: str | None = None
    activation_limit: int | None = None
    activation_count: int | None = None

    @property
    def key_suffix(self) -> str:
        """The tail of the key, safe to display and enough to identify it."""

        return self.key[-4:] if len(self.key) >= 4 else self.key

    def validated_at(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.last_validated)
        except (TypeError, ValueError):
            return None

    def days_since_validation(self) -> float:
        checked = self.validated_at()
        if checked is None:
            return float("inf")
        return max((utcnow() - checked).total_seconds() / 86400.0, 0.0)

    def touch(self) -> None:
        self.last_validated = utcnow().isoformat()


def license_path() -> Path:
    return get_app_data_dir() / FILENAME


def _sign(payload: str, fingerprint: str) -> str:
    """
    Sign the record with a key derived from the machine it belongs to.

    Deriving from the fingerprint is what makes the record non-portable: on
    another machine the derived key differs and the signature will not match.
    """

    derived = hashlib.pbkdf2_hmac("sha256", _SECRET, fingerprint.encode("utf-8"), 10_000)
    digest = hmac.new(derived, payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def save(record: ActivationRecord) -> Path:
    """Write the activation record, signed for this machine."""

    payload = json.dumps(asdict(record), sort_keys=True, separators=(",", ":"))
    document = {"payload": payload, "signature": _sign(payload, record.fingerprint)}

    target = license_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    return target


def load() -> ActivationRecord | None:
    """
    Read the activation record, or None if there is not a valid one.

    Anything unreadable, unsigned, or signed for a different machine is treated
    as absent rather than as an error — the customer is then asked to activate,
    which is a recoverable state.
    """

    target = license_path()

    if not target.exists():
        return None

    try:
        document = json.loads(target.read_text(encoding="utf-8"))
        payload = document["payload"]
        signature = document["signature"]
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("The stored licence record could not be read; re-activation is required.")
        return None

    fingerprint = machine_fingerprint()

    if not hmac.compare_digest(signature, _sign(payload, fingerprint)):
        logger.warning(
            "The stored licence record does not belong to this machine; "
            "re-activation is required."
        )
        return None

    try:
        data = json.loads(payload)
        record = ActivationRecord(**data)
    except (ValueError, TypeError):
        return None

    if record.fingerprint != fingerprint:
        return None

    return record


def clear() -> None:
    """Remove the stored activation."""

    license_path().unlink(missing_ok=True)
