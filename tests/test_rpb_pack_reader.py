"""Tests for rpb.pack_reader — safe TAR extraction."""
import io
import tarfile

import pytest

from rpb.pack_reader import PackReadError, extract_rpack


def _make_rpack(tmp_path, members: dict[str, bytes]) -> "pathlib.Path":
    """Build a minimal .rpack TAR containing the given name→bytes mapping."""
    from pathlib import Path

    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / "test.rpack"
    with tarfile.open(str(out), "w:") as arc:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            arc.addfile(info, io.BytesIO(content))
    return out


# ── Basic extraction ─────────────────────────────────────────────────────────


def test_extract_rpack_recovers_files(tmp_path):
    rpack = _make_rpack(tmp_path / "src", {"a.txt": b"hello", "sub/b.txt": b"world"})
    out = tmp_path / "out"
    extract_rpack(rpack, out)
    assert (out / "a.txt").read_bytes() == b"hello"
    assert (out / "sub" / "b.txt").read_bytes() == b"world"


def test_extract_rpack_creates_output_dir(tmp_path):
    rpack = _make_rpack(tmp_path / "src", {"f.txt": b"x"})
    out = tmp_path / "new_dir"
    assert not out.exists()
    extract_rpack(rpack, out)
    assert out.is_dir()


def test_extract_rpack_missing_file_raises(tmp_path):
    with pytest.raises(PackReadError, match="does not exist"):
        extract_rpack(tmp_path / "missing.rpack", tmp_path / "out")


# ── Path traversal protection ────────────────────────────────────────────────


def test_extract_rpack_blocks_path_traversal(tmp_path):
    rpack = _make_rpack(tmp_path / "src", {"../escape.txt": b"bad"})
    out = tmp_path / "out"
    with pytest.raises(PackReadError):
        extract_rpack(rpack, out)


def test_extract_rpack_blocks_absolute_paths(tmp_path):
    rpack = _make_rpack(tmp_path / "src", {"/etc/passwd": b"bad"})
    out = tmp_path / "out"
    with pytest.raises(PackReadError):
        extract_rpack(rpack, out)


def test_extract_rpack_blocks_drive_qualified_paths(tmp_path):
    rpack = _make_rpack(tmp_path / "src", {"C:/bad.txt": b"bad"})
    out = tmp_path / "out"
    with pytest.raises(PackReadError):
        extract_rpack(rpack, out)
