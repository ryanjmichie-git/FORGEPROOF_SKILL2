from __future__ import annotations

import hashlib


# RFC 8032 parameters for edwards25519.
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_D = (-121665 * _inv(121666)) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = (4 * _inv(5)) % _Q
_BX = _xrecover(_BY)
_BASE = (_BX, _BY)
_IDENTITY = (0, 1)


def _sha512(payload: bytes) -> bytes:
    return hashlib.sha512(payload).digest()


def _point_add(p: tuple[int, int], q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2)
    return (x3 % _Q, y3 % _Q)


def _scalar_mult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    result = _IDENTITY
    addend = point
    k = scalar
    while k > 0:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _encode_int(value: int) -> bytes:
    return value.to_bytes(32, "little")


def _decode_int(payload: bytes) -> int:
    return int.from_bytes(payload, "little")


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    packed = y | ((x & 1) << 255)
    return packed.to_bytes(32, "little")


def _is_on_curve(point: tuple[int, int]) -> bool:
    x, y = point
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _decode_point(payload: bytes) -> tuple[int, int]:
    if len(payload) != 32:
        raise ValueError("ed25519 point must be 32 bytes")
    y = int.from_bytes(payload, "little") & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((payload[31] >> 7) & 1):
        x = _Q - x
    point = (x, y)
    if not _is_on_curve(point):
        raise ValueError("invalid ed25519 point")
    return point


def _secret_scalar_and_prefix(private_key: bytes) -> tuple[int, bytes]:
    if len(private_key) != 32:
        raise ValueError("ed25519 private key must be 32 bytes")
    digest = bytearray(_sha512(private_key))
    digest[0] &= 248
    digest[31] &= 63
    digest[31] |= 64
    scalar = int.from_bytes(digest[:32], "little")
    prefix = bytes(digest[32:])
    return scalar, prefix


def derive_public_key(private_key: bytes) -> bytes:
    scalar, _prefix = _secret_scalar_and_prefix(private_key)
    public_point = _scalar_mult(_BASE, scalar)
    return _encode_point(public_point)


def sign(private_key: bytes, message: bytes) -> bytes:
    scalar, prefix = _secret_scalar_and_prefix(private_key)
    public_key = derive_public_key(private_key)
    nonce = int.from_bytes(_sha512(prefix + message), "little") % _L
    r_point = _scalar_mult(_BASE, nonce)
    r_encoded = _encode_point(r_point)
    challenge = int.from_bytes(_sha512(r_encoded + public_key + message), "little") % _L
    s = (nonce + challenge * scalar) % _L
    return r_encoded + _encode_int(s)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False

    try:
        a_point = _decode_point(public_key)
        r_point = _decode_point(signature[:32])
    except ValueError:
        return False

    s = _decode_int(signature[32:])
    if s >= _L:
        return False

    challenge = int.from_bytes(_sha512(signature[:32] + public_key + message), "little") % _L
    left = _scalar_mult(_BASE, s)
    right = _point_add(r_point, _scalar_mult(a_point, challenge))
    return left == right


def generate_ephemeral_keypair() -> tuple[bytes, bytes]:
    """Generate a random Ed25519 keypair. Returns (private_key, public_key)."""
    import os
    private_key = os.urandom(32)
    public_key = derive_public_key(private_key)
    return private_key, public_key

