"""Ed25519 signing and verification, in pure Python."""

from __future__ import annotations

import hashlib
import os

P = 2**255 - 19
L = 2**252 + 27742317777372353535851937790883648493

_D = -121665 * pow(121666, P - 2, P) % P
_SQRT_MINUS_1 = pow(2, (P - 1) // 4, P)

Point = tuple[int, int]


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _recover_x(y: int, sign: int) -> int | None:
    """Recover the x coordinate of a point from y and the sign bit."""

    if y >= P:
        return None

    numerator = (y * y - 1) % P
    denominator = (_D * y * y + 1) % P

    x = numerator * pow(denominator, P - 2, P) % P
    x = pow(x, (P + 3) // 8, P)

    if (x * x - numerator * pow(denominator, P - 2, P)) % P != 0:
        x = x * _SQRT_MINUS_1 % P

    if (x * x * denominator - numerator) % P != 0:
        return None

    if x == 0 and sign:
        return None

    return P - x if x & 1 != sign else x


def _add(point: Point, other: Point) -> Point:
    """Twisted Edwards addition. Complete for this curve, so no special cases."""

    x1, y1 = point
    x2, y2 = other

    common = _D * x1 * x2 % P * y1 % P * y2 % P

    x3 = (x1 * y2 + x2 * y1) * pow(1 + common, P - 2, P) % P
    y3 = (y1 * y2 + x1 * x2) * pow(1 - common, P - 2, P) % P

    return x3, y3


def _multiply(point: Point, scalar: int) -> Point:
    result: Point = (0, 1)  # The identity.
    addend = point

    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1

    return result


_BASE_Y = 4 * pow(5, P - 2, P) % P
_BASE: Point = (_recover_x(_BASE_Y, 0), _BASE_Y)  # type: ignore[assignment]


def _encode_point(point: Point) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _decode_point(data: bytes) -> Point | None:
    if len(data) != 32:
        return None

    value = int.from_bytes(data, "little")
    y = value & ((1 << 255) - 1)

    x = _recover_x(y, value >> 255)
    return None if x is None else (x, y)


def _clamp(seed_hash: bytes) -> int:
    """Prune the scalar as RFC 8032 §5.1.5 requires."""

    scalar = bytearray(seed_hash[:32])
    scalar[0] &= 248
    scalar[31] &= 127
    scalar[31] |= 64
    return int.from_bytes(scalar, "little")


def generate_seed() -> bytes:
    """A new 32-byte private seed, from the OS random source."""

    return os.urandom(32)


def public_key(seed: bytes) -> bytes:
    """Derive the 32-byte public key from a 32-byte private seed."""

    if len(seed) != 32:
        raise ValueError("An Ed25519 seed must be exactly 32 bytes.")

    return _encode_point(_multiply(_BASE, _clamp(_sha512(seed))))


def sign(message: bytes, seed: bytes) -> bytes:
    """Sign a message, returning the 64-byte signature."""

    if len(seed) != 32:
        raise ValueError("An Ed25519 seed must be exactly 32 bytes.")

    digest = _sha512(seed)
    scalar = _clamp(digest)
    prefix = digest[32:]

    key = _encode_point(_multiply(_BASE, scalar))

    nonce = int.from_bytes(_sha512(prefix + message), "little") % L
    commitment = _encode_point(_multiply(_BASE, nonce))

    challenge = int.from_bytes(_sha512(commitment + key + message), "little") % L

    return commitment + ((nonce + challenge * scalar) % L).to_bytes(32, "little")


def verify(message: bytes, signature: bytes, key: bytes) -> bool:
    """Check a signature. Returns False rather than raising on anything malformed."""

    if len(signature) != 64 or len(key) != 32:
        return False

    commitment = _decode_point(signature[:32])
    point = _decode_point(key)

    if commitment is None or point is None:
        return False

    scalar = int.from_bytes(signature[32:], "little")
    if scalar >= L:
        return False

    challenge = int.from_bytes(_sha512(signature[:32] + key + message), "little") % L

    return _multiply(_BASE, scalar) == _add(commitment, _multiply(point, challenge))
