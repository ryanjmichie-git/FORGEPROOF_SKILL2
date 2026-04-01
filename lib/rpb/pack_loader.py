from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rpb.canon import loads_json


class PackLoadError(ValueError):
    """Raised when an unpacked pack directory is structurally invalid."""


REQUIRED_TOP_LEVEL_FILES = ("MANIFEST.json", "HASHES.json", "POLICY.json")


@dataclass(frozen=True)
class PackContents:
    root_dir: Path
    manifest: dict[str, Any]
    hashes: dict[str, Any]
    policy: dict[str, Any]


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = loads_json(path.read_bytes())
    except OSError as exc:  # pragma: no cover - surfaced by higher-level tests
        raise PackLoadError(f"unable to read '{path.name}': {exc}") from exc
    except Exception as exc:
        raise PackLoadError(f"invalid JSON in '{path.name}': {exc}") from exc

    if not isinstance(payload, dict):
        raise PackLoadError(f"invalid JSON structure in '{path.name}': expected object")
    return payload


def validate_required_top_level_files(pack_dir: str | Path) -> Path:
    root = Path(pack_dir)
    if not root.exists():
        raise PackLoadError(f"pack directory does not exist: {root}")
    if not root.is_dir():
        raise PackLoadError(f"pack path is not a directory: {root}")

    for filename in REQUIRED_TOP_LEVEL_FILES:
        candidate = root / filename
        if not candidate.exists():
            raise PackLoadError(f"missing required top-level file: {filename}")
        if not candidate.is_file():
            raise PackLoadError(f"required path is not a file: {filename}")
    return root


def load_manifest_from_dir(pack_dir: str | Path) -> dict[str, Any]:
    root = validate_required_top_level_files(pack_dir)
    return _load_json_object(root / "MANIFEST.json")


def _validate_policy(policy: dict[str, Any]) -> None:
    required_fields = ("schema_version", "policy_id", "policy_version", "profiles")
    for field_name in required_fields:
        if field_name not in policy:
            raise PackLoadError(f"POLICY.json missing required field: {field_name}")

    profiles = policy["profiles"]
    if not isinstance(profiles, dict):
        raise PackLoadError("POLICY.json field 'profiles' must be an object")
    for profile in ("P0", "P1", "P2", "P3"):
        if profile not in profiles:
            raise PackLoadError(f"POLICY.json missing profile flag: {profile}")
        if not isinstance(profiles[profile], bool):
            raise PackLoadError(f"POLICY.json profile flag must be boolean: {profile}")


def load_policy_from_dir(pack_dir: str | Path) -> dict[str, Any]:
    root = validate_required_top_level_files(pack_dir)
    policy = _load_json_object(root / "POLICY.json")
    _validate_policy(policy)
    return policy


def load_pack_directory(pack_dir: str | Path) -> PackContents:
    root = validate_required_top_level_files(pack_dir)
    manifest = _load_json_object(root / "MANIFEST.json")
    hashes = _load_json_object(root / "HASHES.json")
    policy = _load_json_object(root / "POLICY.json")
    _validate_policy(policy)
    return PackContents(
        root_dir=root.resolve(),
        manifest=manifest,
        hashes=hashes,
        policy=policy,
    )
