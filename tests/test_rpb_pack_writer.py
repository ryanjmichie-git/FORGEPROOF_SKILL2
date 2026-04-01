"""Tests for rpb.pack_writer — deterministic TAR archive creation."""
import tarfile

import pytest

from rpb.pack_writer import PackWriteError, create_rpack
from rpb.pack_reader import extract_rpack


def _make_staging(tmp_path, files: dict[str, bytes]) -> "pathlib.Path":
    from pathlib import Path

    staging = tmp_path / "staging"
    staging.mkdir()
    for rel, content in files.items():
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
    return staging


# ── Basic creation ───────────────────────────────────────────────────────────


def test_create_rpack_produces_file(tmp_path):
    staging = _make_staging(tmp_path, {"MANIFEST.json": b"{}"})
    out = tmp_path / "out.rpack"
    create_rpack(staging, out)
    assert out.exists()
    assert out.stat().st_size > 0


def test_create_rpack_is_valid_tar(tmp_path):
    staging = _make_staging(tmp_path, {"a.txt": b"hello"})
    out = tmp_path / "out.rpack"
    create_rpack(staging, out)
    assert tarfile.is_tarfile(str(out))


def test_create_rpack_roundtrip(tmp_path):
    staging = _make_staging(
        tmp_path,
        {
            "MANIFEST.json": b'{"x":1}',
            "sub/file.txt": b"content",
        },
    )
    out = tmp_path / "out.rpack"
    create_rpack(staging, out)

    extracted = tmp_path / "extracted"
    extract_rpack(out, extracted)
    assert (extracted / "MANIFEST.json").read_bytes() == b'{"x":1}'
    assert (extracted / "sub" / "file.txt").read_bytes() == b"content"


def test_create_rpack_deterministic(tmp_path):
    """Same staging directory produces identical archives."""
    staging = _make_staging(tmp_path, {"f.txt": b"data"})
    out1 = tmp_path / "a.rpack"
    out2 = tmp_path / "b.rpack"
    create_rpack(staging, out1)
    create_rpack(staging, out2)
    assert out1.read_bytes() == out2.read_bytes()


# ── Error cases ──────────────────────────────────────────────────────────────


def test_create_rpack_raises_for_missing_staging_dir(tmp_path):
    with pytest.raises(PackWriteError, match="does not exist"):
        create_rpack(tmp_path / "nonexistent", tmp_path / "out.rpack")


def test_create_rpack_raises_for_file_as_staging_dir(tmp_path):
    f = tmp_path / "not_a_dir"
    f.write_bytes(b"x")
    with pytest.raises(PackWriteError, match="not a directory"):
        create_rpack(f, tmp_path / "out.rpack")
