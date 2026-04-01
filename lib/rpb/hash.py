from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from rpb.canon import dumps_canonical


def sha256_bytes(payload: bytes) -> str:
    """Return lowercase SHA-256 hex digest for bytes."""

    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Return lowercase SHA-256 hex digest for file content."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_manifest_path(path: str | Path) -> str:
    """Normalize a path to manifest-safe POSIX separators."""

    as_text = str(path)
    return as_text.replace("\\", "/")


def write_hashes_json(file_paths: Iterable[str | Path], out_path: str | Path) -> dict[str, Any]:
    """Write HASHES.json structure for file paths and return the payload object."""

    entries: list[dict[str, Any]] = []
    for candidate in file_paths:
        source = Path(candidate)
        stat = source.stat()
        entries.append(
            {
                "path": normalize_manifest_path(candidate),
                "sha256": sha256_file(source),
                "size_bytes": stat.st_size,
            }
        )

    entries.sort(key=lambda item: item["path"])
    payload = {
        "hash_algo": "sha256",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "files": entries,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(dumps_canonical(payload))
    return payload
