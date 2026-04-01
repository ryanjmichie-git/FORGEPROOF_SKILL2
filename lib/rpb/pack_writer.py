from __future__ import annotations

import tarfile
from pathlib import Path

from rpb.hash import normalize_manifest_path


FIXED_MTIME = 0
FIXED_UID = 0
FIXED_GID = 0
DIR_MODE = 0o755
FILE_MODE = 0o644
EXEC_FILE_MODE = 0o755


class PackWriteError(ValueError):
    """Raised when creating an `.rpack` archive fails."""


def _iter_staged_entries(staging_dir: Path) -> list[tuple[str, Path]]:
    entries: list[tuple[str, Path]] = []
    for source in staging_dir.rglob("*"):
        relative = source.relative_to(staging_dir)
        normalized = normalize_manifest_path(relative)
        entries.append((normalized, source))
    entries.sort(key=lambda item: item[0])
    return entries


def _file_mode(source: Path) -> int:
    return EXEC_FILE_MODE if (source.stat().st_mode & 0o111) else FILE_MODE


def _base_tarinfo(name: str) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name=name)
    info.mtime = FIXED_MTIME
    info.uid = FIXED_UID
    info.gid = FIXED_GID
    info.uname = ""
    info.gname = ""
    return info


def create_rpack(staging_dir: str | Path, out_path: str | Path) -> Path:
    """Create a deterministic `.rpack` TAR archive from an unpacked staging directory."""

    staging_root = Path(staging_dir)
    if not staging_root.exists():
        raise PackWriteError(f"staging directory does not exist: {staging_root}")
    if not staging_root.is_dir():
        raise PackWriteError(f"staging path is not a directory: {staging_root}")

    destination = Path(out_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    entries = _iter_staged_entries(staging_root)
    with tarfile.open(destination, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for arc_name, source in entries:
            if source.is_symlink():
                raise PackWriteError(f"symlink entries are not supported in staging dir: {arc_name}")

            if source.is_dir():
                info = _base_tarinfo(arc_name)
                info.type = tarfile.DIRTYPE
                info.mode = DIR_MODE
                info.size = 0
                archive.addfile(info)
                continue

            if source.is_file():
                info = _base_tarinfo(arc_name)
                info.mode = _file_mode(source)
                info.size = source.stat().st_size
                with source.open("rb") as handle:
                    archive.addfile(info, fileobj=handle)
                continue

            raise PackWriteError(f"unsupported staging entry type: {arc_name}")

    return destination
