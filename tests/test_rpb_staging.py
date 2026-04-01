"""Tests for rpb.staging — finalize_pack_metadata and staging helpers."""
import json
from pathlib import Path

import pytest

from rpb.canon import dumps_canonical
from rpb.staging import (
    DEFAULT_POLICY_FALLBACK,
    StagingError,
    finalize_pack_metadata,
    is_staged_pack_directory,
)


def _write_minimal_staging(tmp_path) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir()

    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "test",
        "claims": [],
        "environment": {"type": "agent", "image_digest": "sha256:" + "0" * 64, "os_arch": "linux/amd64", "toolchain": []},
        "commands": {"build": [], "tests": [], "proofs": []},
        "artifacts": [],
        "evidence": [],
        "policy": {"policy_id": "default-mvp", "policy_version": "0.1.0", "policy_sha256": "0" * 64},
        "signing": {"root_digest_sha256": "0" * 64, "signers": []},
        "redactions": [],
        "created_utc": "1970-01-01T00:00:00Z",
        "producer": {"name": "test", "version": "0.0.0", "build": "test"},
        "subject": {"name": "test", "version": "0.0.0", "vcs": {"type": "none"}},
    }
    (staging / "MANIFEST.json").write_bytes(dumps_canonical(manifest))
    (staging / "POLICY.json").write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))
    (staging / "SIGNATURES").mkdir()
    (staging / "VERIFY").mkdir()
    (staging / "VERIFY" / "verify_instructions.txt").write_text("v\n", encoding="utf-8")
    return staging


# ── is_staged_pack_directory ──────────────────────────────────────────────────


def test_is_staged_pack_directory_true_when_required_files_present(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    (staging / "HASHES.json").write_bytes(b"{}")
    assert is_staged_pack_directory(staging) is True


def test_is_staged_pack_directory_false_when_missing_file(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    # HASHES.json not written
    assert is_staged_pack_directory(staging) is False


def test_is_staged_pack_directory_false_for_nonexistent_path(tmp_path):
    assert is_staged_pack_directory(tmp_path / "nope") is False


# ── finalize_pack_metadata ────────────────────────────────────────────────────


def test_finalize_pack_metadata_creates_hashes_json(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    finalize_pack_metadata(staging)
    assert (staging / "HASHES.json").exists()


def test_finalize_pack_metadata_hashes_json_lists_manifest(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    finalize_pack_metadata(staging)
    hashes = json.loads((staging / "HASHES.json").read_text(encoding="utf-8"))
    paths = [e["path"] for e in hashes["files"]]
    assert "MANIFEST.json" in paths


def test_finalize_pack_metadata_hashes_json_excludes_hashes_json_itself(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    finalize_pack_metadata(staging)
    hashes = json.loads((staging / "HASHES.json").read_text(encoding="utf-8"))
    paths = [e["path"] for e in hashes["files"]]
    assert "HASHES.json" not in paths


def test_finalize_pack_metadata_hashes_json_excludes_signatures(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    (staging / "SIGNATURES" / "signer-1.sig").write_bytes(b"\x00" * 64)
    finalize_pack_metadata(staging)
    hashes = json.loads((staging / "HASHES.json").read_text(encoding="utf-8"))
    paths = [e["path"] for e in hashes["files"]]
    assert not any(p.startswith("SIGNATURES/") for p in paths)


def test_finalize_pack_metadata_root_digest_updated(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    finalize_pack_metadata(staging)
    manifest = json.loads((staging / "MANIFEST.json").read_text(encoding="utf-8"))
    root_digest = manifest["signing"]["root_digest_sha256"]
    assert root_digest != "0" * 64
    assert len(root_digest) == 64


def test_finalize_pack_metadata_raises_without_manifest(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "POLICY.json").write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))
    with pytest.raises(StagingError, match="missing MANIFEST.json"):
        finalize_pack_metadata(staging)


def test_finalize_pack_metadata_raises_without_policy(tmp_path):
    staging = _write_minimal_staging(tmp_path)
    (staging / "POLICY.json").unlink()
    with pytest.raises(StagingError, match="missing POLICY.json"):
        finalize_pack_metadata(staging)
