"""Tests for rpb.hash — SHA-256 helpers and path normalisation."""
import hashlib
from pathlib import Path

import pytest

from rpb.hash import normalize_manifest_path, sha256_bytes, sha256_file


def test_sha256_bytes_known_vector():
    # echo -n "" | sha256sum
    assert sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_bytes_hello():
    expected = hashlib.sha256(b"hello").hexdigest()
    assert sha256_bytes(b"hello") == expected


def test_sha256_file_matches_bytes(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"test content")
    assert sha256_file(f) == sha256_bytes(b"test content")


def test_sha256_file_handles_path_string(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"abc")
    assert sha256_file(str(f)) == sha256_bytes(b"abc")


def test_sha256_file_empty(tmp_path):
    f = tmp_path / "empty"
    f.write_bytes(b"")
    assert sha256_file(f) == sha256_bytes(b"")


def test_normalize_manifest_path_forward_slashes():
    assert normalize_manifest_path("a/b/c") == "a/b/c"


def test_normalize_manifest_path_converts_backslashes():
    assert normalize_manifest_path("a\\b\\c") == "a/b/c"


def test_normalize_manifest_path_mixed():
    assert normalize_manifest_path("src\\sub/file.py") == "src/sub/file.py"


def test_normalize_manifest_path_accepts_path_object():
    result = normalize_manifest_path(Path("src") / "file.py")
    assert "/" in result or result == "src/file.py"
