"""Tests for rpb.ed25519 — pure-Python Ed25519 implementation."""
import os

import pytest

from rpb.ed25519 import derive_public_key, generate_ephemeral_keypair, sign, verify


# ── Key generation ───────────────────────────────────────────────────────────


def test_ephemeral_keypair_produces_32_byte_keys():
    priv, pub = generate_ephemeral_keypair()
    assert len(priv) == 32
    assert len(pub) == 32


def test_ephemeral_keypair_is_random():
    priv1, _ = generate_ephemeral_keypair()
    priv2, _ = generate_ephemeral_keypair()
    assert priv1 != priv2


def test_derive_public_key_is_deterministic():
    priv = os.urandom(32)
    assert derive_public_key(priv) == derive_public_key(priv)


def test_derive_public_key_matches_keypair():
    priv, pub = generate_ephemeral_keypair()
    assert derive_public_key(priv) == pub


# ── Sign / verify ────────────────────────────────────────────────────────────


def test_sign_verify_roundtrip():
    priv, pub = generate_ephemeral_keypair()
    message = b"hello forgeproof"
    sig = sign(priv, message)
    assert verify(pub, message, sig)


def test_sign_produces_64_byte_signature():
    priv, _ = generate_ephemeral_keypair()
    sig = sign(priv, b"msg")
    assert len(sig) == 64


def test_verify_rejects_wrong_message():
    priv, pub = generate_ephemeral_keypair()
    sig = sign(priv, b"correct message")
    assert not verify(pub, b"wrong message", sig)


def test_verify_rejects_tampered_signature():
    priv, pub = generate_ephemeral_keypair()
    sig = sign(priv, b"data")
    tampered = bytes([sig[0] ^ 0xFF]) + sig[1:]
    assert not verify(pub, b"data", tampered)


def test_verify_rejects_wrong_public_key():
    priv1, _ = generate_ephemeral_keypair()
    _, pub2 = generate_ephemeral_keypair()
    sig = sign(priv1, b"data")
    assert not verify(pub2, b"data", sig)


def test_verify_rejects_short_signature():
    _, pub = generate_ephemeral_keypair()
    assert not verify(pub, b"data", b"tooshort")


def test_sign_same_key_and_message_is_deterministic():
    # Ed25519 uses a deterministic nonce (RFC 8032).
    priv = os.urandom(32)
    msg = b"deterministic"
    assert sign(priv, msg) == sign(priv, msg)
