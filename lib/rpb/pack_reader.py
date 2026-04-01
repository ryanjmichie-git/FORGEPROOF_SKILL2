from __future__ import annotations

import shutil
import tarfile
from pathlib import Path, PurePosixPath


class PackReadError(ValueError):
    """Raised when reading/extracting an `.rpack` archive fails."""


def _member_parts(member_name: str) -> list[str]:
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("\\"):
        raise PackReadError(f"blocked absolute archive path: {member_name}")

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise PackReadError(f"blocked archive path traversal: {member_name}")
    if parts and parts[0].endswith(":"):
        raise PackReadError(f"blocked archive drive-qualified path: {member_name}")
    return parts


def _safe_destination(root: Path, member_name: str) -> Path:
    parts = _member_parts(member_name)
    destination = root.joinpath(*parts)

    root_resolved = root.resolve()
    destination_resolved = destination.resolve()
    if destination_resolved != root_resolved and root_resolved not in destination_resolved.parents:
        raise PackReadError(f"blocked archive extraction outside output dir: {member_name}")
    return destination


def extract_rpack(rpack_path: str | Path, out_dir: str | Path) -> Path:
    """Safely extract a `.rpack` TAR archive into `out_dir`."""

    archive_path = Path(rpack_path)
    if not archive_path.exists():
        raise PackReadError(f"archive does not exist: {archive_path}")
    if not archive_path.is_file():
        raise PackReadError(f"archive path is not a file: {archive_path}")

    destination_root = Path(out_dir)
    destination_root.mkdir(parents=True, exist_ok=True)

    try:
        with tarfile.open(archive_path, mode="r:*") as archive:
            for member in archive.getmembers():
                if member.name in ("", "."):
                    continue

                destination = _safe_destination(destination_root, member.name)

                if member.issym() or member.islnk():
                    raise PackReadError(f"blocked archive link member: {member.name}")

                if member.isdir():
                    destination.mkdir(parents=True, exist_ok=True)
                    continue

                if not member.isfile():
                    raise PackReadError(f"unsupported archive member type: {member.name}")

                destination.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise PackReadError(f"failed to extract archive member: {member.name}")

                with extracted, destination.open("wb") as output_handle:
                    shutil.copyfileobj(extracted, output_handle)
    except tarfile.ReadError as exc:
        raise PackReadError(f"invalid archive format: {archive_path}") from exc

    return destination_root
