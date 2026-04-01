"""Tests for rpb.verify_signatures — end-to-end verification of a signed pack."""
import json
import os
from pathlib import Path

import pytest

from rpb.canon import dumps_canonical
from rpb.ed25519 import derive_public_key
from rpb.staging import DEFAULT_POLICY_FALLBACK, finalize_pack_metadata
from rpb.sign import write_signatures
from rpb.verify_signatures import verify_hashes, verify_pack_directory


def _minimal_signed_pack(tmp_path) -> tuple[Path, bytes]:
    """Return (staging_dir, private_key_bytes) for a fully signed valid pack."""
    from rpb.sign import write_signatures as _ws

    staging = tmp_path / "staging"
    staging.mkdir()

    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "test-pack",
        "created_utc": "1970-01-01T00:00:00Z",
        "producer": {"name": "test", "version": "0.0.1", "build": "test"},
        "subject": {"name": "test", "version": "0.0.0", "vcs": {"type": "none"}},
        "claims": [{"claim_id": "C-1", "profile": "P0", "label": "integrity", "properties": []}],
        "environment": {
            "type": "agent",
            "image_digest": "sha256:" + "0" * 64,
            "os_arch": "linux/amd64",
            "toolchain": [],
        },
        "commands": {"build": [], "tests": [], "proofs": []},
        "artifacts": [],
        "evidence": [],
        "policy": {
            "policy_id": "default-mvp",
            "policy_version": "0.1.0",
            "policy_sha256": "0" * 64,
        },
        "signing": {"root_digest_sha256": "0" * 64, "signers": []},
        "redactions": [],
    }
    (staging / "MANIFEST.json").write_bytes(dumps_canonical(manifest))
    (staging / "POLICY.json").write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))
    (staging / "SIGNATURES").mkdir()
    (staging / "VERIFY").mkdir()
    (staging / "VERIFY" / "verify_instructions.txt").write_text("verify\n", encoding="utf-8")
    finalize_pack_metadata(staging)

    priv = os.urandom(32)
    key_file = tmp_path / "key.bin"
    key_file.write_bytes(priv)
    _ws(staging, key_file)
    # Do NOT call finalize_pack_metadata after signing — it would update
    # MANIFEST.json (artifacts) and invalidate the signatures.
    return staging, priv


# ── verify_hashes ─────────────────────────────────────────────────────────────


def test_verify_hashes_passes_on_correct_pack(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    from rpb.pack_loader import load_pack_directory
    pack = load_pack_directory(staging)
    failures = verify_hashes(pack.root_dir, pack.hashes)
    assert failures == []


def test_verify_hashes_detects_tampered_file(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    # Tamper with a file after hashes were computed.
    (staging / "VERIFY" / "verify_instructions.txt").write_text("tampered\n", encoding="utf-8")
    from rpb.pack_loader import load_pack_directory
    pack = load_pack_directory(staging)
    failures = verify_hashes(pack.root_dir, pack.hashes)
    assert any("hash_mismatch" in f for f in failures)


# ── verify_pack_directory ─────────────────────────────────────────────────────


def test_verify_pack_directory_passes_valid_pack(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    outcome = verify_pack_directory(staging)
    assert outcome.result.verified is True
    assert outcome.result.failed_checks == []
    assert any(s.status == "valid" for s in outcome.result.signers)


def test_verify_pack_directory_fails_with_tampered_content(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    (staging / "VERIFY" / "verify_instructions.txt").write_text("tampered\n", encoding="utf-8")
    outcome = verify_pack_directory(staging)
    assert outcome.result.verified is False
    assert any("hash_mismatch" in f for f in outcome.result.failed_checks)


def test_verify_pack_directory_fails_missing_signatures_dir(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    import shutil
    shutil.rmtree(staging / "SIGNATURES")
    (staging / "SIGNATURES").mkdir()  # empty dir, no sig files
    outcome = verify_pack_directory(staging)
    assert outcome.result.verified is False


def test_verify_pack_directory_claims_verified_includes_p0(tmp_path):
    staging, _ = _minimal_signed_pack(tmp_path)
    outcome = verify_pack_directory(staging)
    assert "C-1" in outcome.result.claims_verified
