"""Tests for rpb.sign — signing a staged pack directory."""
import json
import os
import tempfile
from pathlib import Path

import pytest

from rpb.canon import dumps_canonical
from rpb.ed25519 import derive_public_key, verify
from rpb.sign import SignError, load_private_key, write_signatures
from rpb.staging import DEFAULT_POLICY_FALLBACK, finalize_pack_metadata


def _minimal_staged_dir(tmp_path) -> Path:
    """Create a minimal valid staging directory ready to be signed."""
    staging = tmp_path / "staging"
    staging.mkdir()

    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "test-pack",
        "created_utc": "1970-01-01T00:00:00Z",
        "producer": {"name": "test", "version": "0.0.1", "build": "test"},
        "subject": {"name": "test", "version": "0.0.0", "vcs": {"type": "none"}},
        "claims": [{"claim_id": "C-1", "profile": "P0", "label": "integrity", "properties": []}],
        "environment": {"type": "agent", "image_digest": "sha256:" + "0" * 64, "os_arch": "linux/amd64", "toolchain": []},
        "commands": {"build": [], "tests": [], "proofs": []},
        "artifacts": [],
        "evidence": [],
        "policy": {"policy_id": "default-mvp", "policy_version": "0.1.0", "policy_sha256": "0" * 64},
        "signing": {"root_digest_sha256": "0" * 64, "signers": []},
        "redactions": [],
    }
    (staging / "MANIFEST.json").write_bytes(dumps_canonical(manifest))
    (staging / "POLICY.json").write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))
    (staging / "SIGNATURES").mkdir()
    (staging / "VERIFY").mkdir()
    (staging / "VERIFY" / "verify_instructions.txt").write_text("verify here\n", encoding="utf-8")
    finalize_pack_metadata(staging)
    return staging


def _write_tmp_key(tmp_path, key_bytes: bytes) -> Path:
    key_file = tmp_path / "test.key"
    key_file.write_bytes(key_bytes)
    return key_file


# ── Signature creation ────────────────────────────────────────────────────────


def test_write_signatures_creates_sig_file(tmp_path):
    staging = _minimal_staged_dir(tmp_path)
    priv = os.urandom(32)
    key_file = _write_tmp_key(tmp_path, priv)
    write_signatures(staging, key_file)
    assert (staging / "SIGNATURES" / "signer-1.sig").exists()


def test_write_signatures_creates_metadata_json(tmp_path):
    staging = _minimal_staged_dir(tmp_path)
    priv = os.urandom(32)
    key_file = _write_tmp_key(tmp_path, priv)
    write_signatures(staging, key_file)
    meta_path = staging / "SIGNATURES" / "signer-1.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["algorithm"] == "ed25519"
    assert "key_id" in meta


def test_write_signatures_creates_public_key_file(tmp_path):
    staging = _minimal_staged_dir(tmp_path)
    priv = os.urandom(32)
    key_file = _write_tmp_key(tmp_path, priv)
    write_signatures(staging, key_file)
    pub_path = staging / "SIGNATURES" / "signer-1.pub"
    assert pub_path.exists()
    assert len(pub_path.read_bytes()) == 32


def test_write_signatures_signature_is_valid(tmp_path):
    from rpb.root_digest import compute_root_digest
    from rpb.pack_loader import load_pack_directory

    staging = _minimal_staged_dir(tmp_path)
    priv = os.urandom(32)
    pub = derive_public_key(priv)
    key_file = _write_tmp_key(tmp_path, priv)
    write_signatures(staging, key_file)

    pack = load_pack_directory(staging)
    root_digest = compute_root_digest(pack.manifest, pack.hashes, pack.policy)
    sig = (staging / "SIGNATURES" / "signer-1.sig").read_bytes()
    assert verify(pub, bytes.fromhex(root_digest), sig)


# ── Error handling ────────────────────────────────────────────────────────────


def test_load_private_key_rejects_wrong_length(tmp_path):
    bad = tmp_path / "bad.key"
    bad.write_bytes(b"tooshort")
    with pytest.raises(SignError, match="invalid private key length"):
        load_private_key(bad)
