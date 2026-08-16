"""
The licence key format: what a key contains, and how it is checked.

A key is a small signed record. It carries the machine it was issued for, an
optional expiry, and a label naming the customer, all covered by an Ed25519
signature made with the owner's private key. The application holds only the
public half, so it can check a key but nobody can make one from the binary.

    payload
      1 byte    format version
      10 bytes  the machine tag: the first 10 bytes of the fingerprint
      4 bytes   expiry, days since 1970-01-01, big-endian; 0 means perpetual
      1 byte    label length
      n bytes   label, UTF-8

    key text
      base32(payload + 64-byte signature), in dash-separated groups

Ten bytes of machine tag is 80 bits, far past any chance of two customers
colliding, and shorter than the fingerprint so the key stays a manageable size.

Nothing here reaches the network. A key is verified entirely on the machine it
was issued for, which is the whole point: there is no licence server to run, to
pay for, or to be down when a customer is trying to work.
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from datetime import date

from app.licensing import ed25519
from app.licensing.models import LicenseState

#: Bump when the payload layout changes. Old keys then fail to parse rather
#: than being misread, and the customer is asked for a new one.
FORMAT_VERSION = 1

#: Bytes of the machine fingerprint carried in a key.
MACHINE_BYTES = 10

#: Longest customer label a key can carry.
MAX_LABEL = 48

_EPOCH = date(1970, 1, 1)

#: base32 without padding: A-Z and 2-7. No 0/1/8/9, so there is nothing to
#: confuse with O, I, B or g when a key is read aloud down a phone.
_ALPHABET = re.compile(r"[^A-Z2-7]")

_GROUP = 8


@dataclass(frozen=True, slots=True)
class LicenseKey:
    """A parsed licence key. Parsed is not the same as valid — see `check`."""

    machine: bytes
    expires: date | None
    label: str

    @property
    def perpetual(self) -> bool:
        return self.expires is None

    def days_remaining(self, today: date | None = None) -> int | None:
        if self.expires is None:
            return None
        return (self.expires - (today or date.today())).days


@dataclass(frozen=True, slots=True)
class KeyCheck:
    """The outcome of checking a key against this machine."""

    state: LicenseState
    message: str
    key: LicenseKey | None = None

    @property
    def ok(self) -> bool:
        return self.state is LicenseState.ACTIVE


# ----------------------------------------------------------------------
# Encoding
# ----------------------------------------------------------------------


def machine_tag(fingerprint: str) -> bytes:
    """The part of a machine fingerprint that a key commits to."""

    try:
        return bytes.fromhex(fingerprint)[:MACHINE_BYTES]
    except ValueError:
        # A fingerprint is always hex in practice; being defensive here keeps a
        # surprising platform from turning into a crash at start-up.
        return fingerprint.encode("utf-8")[:MACHINE_BYTES].ljust(MACHINE_BYTES, b"\0")


def _build_payload(fingerprint: str, expires: date | None, label: str) -> bytes:
    encoded = label.strip().encode("utf-8")[:MAX_LABEL]
    days = 0 if expires is None else (expires - _EPOCH).days

    if days < 0 or days > 0xFFFFFFFF:
        raise ValueError("Expiry date is out of range.")

    return b"".join(
        (
            bytes([FORMAT_VERSION]),
            machine_tag(fingerprint),
            days.to_bytes(4, "big"),
            bytes([len(encoded)]),
            encoded,
        )
    )


def format_key(raw: bytes) -> str:
    """Group the encoded bytes so a human can read and re-type them."""

    text = base64.b32encode(raw).decode("ascii").rstrip("=")
    return "-".join(text[at : at + _GROUP] for at in range(0, len(text), _GROUP))


def normalise(text: str) -> str:
    """
    Strip a pasted key back to its alphabet.

    Keys travel through email, so they arrive wrapped across lines, with soft
    hyphens, non-breaking spaces or quotation marks attached. Everything
    outside the alphabet is dropped rather than rejected — refusing a key
    because the customer's mail client wrapped it would be its own support
    problem.
    """

    return _ALPHABET.sub("", text.strip().upper())


def issue(
    fingerprint: str,
    seed: bytes,
    *,
    expires: date | None = None,
    label: str = "",
) -> str:
    """
    Create a licence key. **Owner side** — needs the private seed.

    The application never calls this; it lives here so the format is defined
    once and the issuing tool cannot drift from the checker.
    """

    payload = _build_payload(fingerprint, expires, label)
    return format_key(payload + ed25519.sign(payload, seed))


# ----------------------------------------------------------------------
# Decoding and checking
# ----------------------------------------------------------------------


def _split(text: str) -> tuple[bytes, bytes] | None:
    """Decode to (payload, signature), or None if the text is not a key."""

    cleaned = normalise(text)
    if not cleaned:
        return None

    padded = cleaned + "=" * (-len(cleaned) % 8)

    try:
        raw = base64.b32decode(padded)
    except (ValueError, TypeError):
        return None

    # 1 version + 10 machine + 4 expiry + 1 length, then the signature.
    if len(raw) < 16 + 64:
        return None

    payload, signature = raw[:-64], raw[-64:]

    if payload[0] != FORMAT_VERSION:
        return None

    if 16 + payload[15] != len(payload):
        return None

    return payload, signature


def decode(text: str) -> LicenseKey | None:
    """Parse a key without checking its signature. Never trust this alone."""

    parts = _split(text)
    if parts is None:
        return None

    payload, _ = parts

    days = int.from_bytes(payload[11:15], "big")

    try:
        expires = None if days == 0 else _EPOCH.fromordinal(_EPOCH.toordinal() + days)
        label = payload[16:].decode("utf-8")
    except (ValueError, OverflowError, UnicodeDecodeError):
        return None

    return LicenseKey(machine=payload[1:11], expires=expires, label=label)


def check(
    text: str,
    public_key: str,
    fingerprint: str,
    today: date | None = None,
) -> KeyCheck:
    """
    Check a key against a public key and this machine.

    The order matters. The signature is verified *before* the machine and the
    expiry are looked at, so an unsigned key cannot produce a message that
    reveals anything about what a valid one would have to contain.
    """

    parts = _split(text)
    if parts is None:
        return KeyCheck(
            LicenseState.INVALID,
            "That does not look like a licence key. Copy the whole key from the email.",
        )

    payload, signature = parts

    try:
        key_bytes = bytes.fromhex(public_key)
    except ValueError:
        key_bytes = b""

    if not ed25519.verify(payload, signature, key_bytes):
        return KeyCheck(
            LicenseState.INVALID,
            "This licence key is not valid. Check it was copied in full, "
            "with no characters missing from either end.",
        )

    parsed = decode(text)
    if parsed is None:  # pragma: no cover - a signed key always parses
        return KeyCheck(LicenseState.INVALID, "This licence key could not be read.")

    if parsed.machine != machine_tag(fingerprint):
        return KeyCheck(
            LicenseState.WRONG_MACHINE,
            "This licence key was issued for a different computer.",
            parsed,
        )

    if parsed.expires is not None and parsed.expires < (today or date.today()):
        return KeyCheck(
            LicenseState.EXPIRED,
            f"This licence expired on {parsed.expires:%d %B %Y}.",
            parsed,
        )

    return KeyCheck(LicenseState.ACTIVE, "Licence confirmed.", parsed)
