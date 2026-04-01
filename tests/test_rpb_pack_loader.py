"""Tests for rpb.pack_loader — loading and validating pack directories."""
import pytest

from rpb.canon import dumps_canonical
from rpb.pack_loader import PackLoadError, load_pack_directory, validate_required_top_level_files
from rpb.staging import DEFAULT_POLICY_FALLBACK


def _write_valid_pack(tmp_path):
    staging = tmp_path / "pack"
    staging.mkdir()
    manifest = {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": "test",
    }
    (staging / "MANIFEST.json").write_bytes(dumps_canonical(manifest))
    (staging / "HASHES.json").write_bytes(dumps_canonical({"hash_algo": "sha256", "files": []}))
    (staging / "POLICY.json").write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))
    return staging


def test_load_pack_directory_succeeds_for_valid_pack(tmp_path):
    staging = _write_valid_pack(tmp_path)
    pack = load_pack_directory(staging)
    assert pack.manifest["pack_id"] == "test"
    assert pack.hashes["hash_algo"] == "sha256"


def test_load_pack_directory_raises_for_missing_manifest(tmp_path):
    staging = _write_valid_pack(tmp_path)
    (staging / "MANIFEST.json").unlink()
    with pytest.raises(PackLoadError, match="MANIFEST.json"):
        load_pack_directory(staging)


def test_load_pack_directory_raises_for_missing_hashes(tmp_path):
    staging = _write_valid_pack(tmp_path)
    (staging / "HASHES.json").unlink()
    with pytest.raises(PackLoadError, match="HASHES.json"):
        load_pack_directory(staging)


def test_load_pack_directory_raises_for_invalid_policy(tmp_path):
    staging = _write_valid_pack(tmp_path)
    (staging / "POLICY.json").write_bytes(dumps_canonical({"bad": "policy"}))
    with pytest.raises(PackLoadError):
        load_pack_directory(staging)


def test_load_pack_directory_raises_for_nonexistent_dir(tmp_path):
    with pytest.raises(PackLoadError, match="does not exist"):
        load_pack_directory(tmp_path / "missing")


def test_validate_required_top_level_files_raises_for_non_directory(tmp_path):
    f = tmp_path / "not_a_dir"
    f.write_bytes(b"x")
    with pytest.raises(PackLoadError, match="not a directory"):
        validate_required_top_level_files(f)
