from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rpb.canon import dumps_canonical, loads_json
from rpb.hash import normalize_manifest_path, sha256_bytes, sha256_file
from rpb.root_digest import compute_root_digest
from rpb.pack_loader import REQUIRED_TOP_LEVEL_FILES


FIXED_UTC = "1970-01-01T00:00:00Z"
ZERO_SHA256_HEX = "0" * 64
DEFAULT_IMAGE_DIGEST = f"sha256:{ZERO_SHA256_HEX}"

DEFAULT_POLICY_FALLBACK: dict[str, Any] = {
    "schema_version": "rpb-policy-0.1",
    "policy_id": "default-mvp",
    "policy_version": "0.1.0",
    "profiles": {"P0": True, "P1": True, "P2": True, "P3": False},
    "signature_thresholds": {"P0": 1, "P1": 1, "P2": 1, "P3": 2},
    "requirements": {
        "P0": {
            "must_include_paths": ["MANIFEST.json", "HASHES.json", "SIGNATURES/"],
            "must_have_commands": [],
            "must_have_evidence_types": [],
            "must_reference_spec_properties": False,
        },
        "P1": {
            "must_include_paths": ["VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
            "must_have_commands": [],
            "must_have_evidence_types": [],
            "must_reference_spec_properties": False,
        },
        "P2": {
            "must_include_paths": ["EVIDENCE/TESTS/", "VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
            "must_have_commands": ["tests"],
            "must_have_evidence_types": ["tests"],
            "must_reference_spec_properties": False,
        },
        "P3": {
            "must_include_paths": ["SPEC/", "EVIDENCE/PROOFS/", "VERIFY/", "MANIFEST.json", "HASHES.json", "SIGNATURES/"],
            "must_have_commands": ["proofs"],
            "must_have_evidence_types": ["proofs"],
            "must_reference_spec_properties": True,
        },
    },
    "allowed_tools": {
        "build": ["bash", "make", "python"],
        "tests": ["pytest", "go test", "cargo test", "npm test"],
        "proofs": ["lean", "coqc", "isabelle", "tlc", "apalache", "z3"],
    },
}


class StagingError(ValueError):
    """Raised when preparing a staging pack directory fails."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_staged_pack_directory(path: str | Path) -> bool:
    root = Path(path)
    if not root.exists() or not root.is_dir():
        return False
    return all((root / name).is_file() for name in REQUIRED_TOP_LEVEL_FILES)


def _copy_directory_contents(source_dir: Path, destination_dir: Path) -> None:
    destination_dir.mkdir(parents=True, exist_ok=True)
    for item in sorted(source_dir.iterdir(), key=lambda path: path.name):
        if item.is_symlink():
            raise StagingError(f"input contains unsupported symlink: {item}")

        target = destination_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        elif item.is_file():
            shutil.copy2(item, target)
        else:
            raise StagingError(f"input contains unsupported entry type: {item}")


def _load_default_policy() -> dict[str, Any]:
    policy_path = _repo_root() / "schemas" / "POLICY.json"
    if not policy_path.exists() or not policy_path.is_file():
        return DEFAULT_POLICY_FALLBACK.copy()

    payload = loads_json(policy_path.read_bytes())
    if not isinstance(payload, dict):
        raise StagingError("schemas/POLICY.json must contain a JSON object")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps_canonical(payload))


def _read_json(path: Path) -> dict[str, Any]:
    payload = loads_json(path.read_bytes())
    if not isinstance(payload, dict):
        raise StagingError(f"invalid JSON object at {path}")
    return payload


def _rel_posix(root: Path, path: Path) -> str:
    return normalize_manifest_path(path.relative_to(root))


def _build_hashes(staging_root: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for file_path in sorted((path for path in staging_root.rglob("*") if path.is_file()), key=lambda p: _rel_posix(staging_root, p)):
        rel_path = _rel_posix(staging_root, file_path)
        if rel_path == "HASHES.json":
            continue
        if rel_path.startswith("SIGNATURES/"):
            continue

        entries.append(
            {
                "path": rel_path,
                "sha256": sha256_file(file_path),
                "size_bytes": file_path.stat().st_size,
            }
        )

    return {
        "hash_algo": "sha256",
        "generated_utc": FIXED_UTC,
        "files": entries,
    }


def _kind_for_path(rel_path: str) -> str:
    if rel_path == "MANIFEST.json":
        return "manifest"
    if rel_path == "HASHES.json":
        return "hashlist"
    if rel_path.startswith("SOURCE/"):
        return "source"
    if rel_path.startswith("VERIFY/"):
        return "other"
    if rel_path == "POLICY.json":
        return "policy"
    if rel_path.startswith("EVIDENCE/TESTS/"):
        return "test_result"
    if rel_path.startswith("SIGNATURES/"):
        return "signature"
    return "other"


def _build_artifacts(staging_root: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for file_path in sorted((path for path in staging_root.rglob("*") if path.is_file()), key=lambda p: _rel_posix(staging_root, p)):
        rel_path = _rel_posix(staging_root, file_path)
        artifacts.append(
            {
                "path": rel_path,
                "sha256": sha256_file(file_path),
                "size_bytes": file_path.stat().st_size,
                "kind": _kind_for_path(rel_path),
            }
        )
    return artifacts


def _deterministic_pack_id(source_root: Path) -> str:
    file_paths = [
        normalize_manifest_path(path.relative_to(source_root))
        for path in sorted((candidate for candidate in source_root.rglob("*") if candidate.is_file()), key=lambda p: normalize_manifest_path(p.relative_to(source_root)))
    ]
    digest = sha256_bytes(dumps_canonical({"source_paths": file_paths}))
    return f"pack-{digest[:24]}"


def _manifest_skeleton(
    *,
    source_name: str,
    policy_obj: dict[str, Any],
    policy_sha256: str,
    artifacts: list[dict[str, Any]],
    pack_id: str,
) -> dict[str, Any]:
    return {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": pack_id,
        "created_utc": FIXED_UTC,
        "producer": {
            "name": "rpb",
            "version": "0.1.0",
            "build": "mvp-autostage",
        },
        "subject": {
            "name": source_name or "input",
            "version": "0.0.0",
            "vcs": {"type": "none"},
        },
        "claims": [
            {
                "claim_id": "CLAIM-INTEGRITY-001",
                "profile": "P0",
                "label": "Integrity: contents match signed hashes",
                "properties": [],
            }
        ],
        "environment": {
            "type": "container",
            "image_digest": DEFAULT_IMAGE_DIGEST,
            "os_arch": "linux/amd64",
            "toolchain": [],
        },
        "commands": {"build": [], "tests": [], "proofs": []},
        "artifacts": artifacts,
        "evidence": [],
        "policy": {
            "policy_id": str(policy_obj.get("policy_id", "default-mvp")),
            "policy_version": str(policy_obj.get("policy_version", "0.1.0")),
            "policy_sha256": policy_sha256,
        },
        "signing": {
            "root_digest_sha256": ZERO_SHA256_HEX,
            "signers": [],
        },
        "redactions": [
            {"pattern": ".env", "reason": "Prevent secret leakage"},
            {"pattern": "**/*_key*", "reason": "Prevent private key inclusion"},
        ],
    }


def _ensure_verify_stub(staging_root: Path) -> None:
    verify_dir = staging_root / "VERIFY"
    verify_dir.mkdir(parents=True, exist_ok=True)
    instructions = verify_dir / "verify_instructions.txt"
    if not instructions.exists():
        instructions.write_text(
            "Offline verify: run `rpb verify <pack.rpack>` or extract and verify locally.\n",
            encoding="utf-8",
        )


def _stage_normal_directory(input_dir: Path, staging_root: Path) -> None:
    source_root = staging_root / "SOURCE"
    source_root.mkdir(parents=True, exist_ok=True)
    _copy_directory_contents(input_dir, source_root)
    (staging_root / "SIGNATURES").mkdir(parents=True, exist_ok=True)
    _ensure_verify_stub(staging_root)

    policy_obj = _load_default_policy()
    _write_json(staging_root / "POLICY.json", policy_obj)

    pack_id = _deterministic_pack_id(source_root)
    policy_sha256 = sha256_bytes(dumps_canonical(policy_obj))
    manifest_obj = _manifest_skeleton(
        source_name=input_dir.name,
        policy_obj=policy_obj,
        policy_sha256=policy_sha256,
        artifacts=[],
        pack_id=pack_id,
    )
    _write_json(staging_root / "MANIFEST.json", manifest_obj)
    finalize_pack_metadata(staging_root)


def finalize_pack_metadata(staging_dir: str | Path) -> None:
    """Refresh manifest artifacts, policy hash, root digest field, and HASHES.json."""

    staging_root = Path(staging_dir)
    manifest_path = staging_root / "MANIFEST.json"
    policy_path = staging_root / "POLICY.json"
    hashes_path = staging_root / "HASHES.json"

    if not manifest_path.exists():
        raise StagingError("missing MANIFEST.json in staging directory")
    if not policy_path.exists():
        raise StagingError("missing POLICY.json in staging directory")

    manifest = _read_json(manifest_path)
    policy = _read_json(policy_path)
    policy_sha256 = sha256_bytes(dumps_canonical(policy))

    if not isinstance(manifest.get("policy"), dict):
        manifest["policy"] = {}
    manifest["policy"]["policy_id"] = str(policy.get("policy_id", "default-mvp"))
    manifest["policy"]["policy_version"] = str(policy.get("policy_version", "0.1.0"))
    manifest["policy"]["policy_sha256"] = policy_sha256

    if not isinstance(manifest.get("commands"), dict):
        manifest["commands"] = {"build": [], "tests": [], "proofs": []}
    manifest["commands"].setdefault("build", [])
    manifest["commands"].setdefault("tests", [])
    manifest["commands"].setdefault("proofs", [])

    if not isinstance(manifest.get("evidence"), list):
        manifest["evidence"] = []

    if not isinstance(manifest.get("signing"), dict):
        manifest["signing"] = {"root_digest_sha256": ZERO_SHA256_HEX, "signers": []}
    manifest["signing"].setdefault("signers", [])
    manifest["signing"]["root_digest_sha256"] = ZERO_SHA256_HEX

    _write_json(manifest_path, manifest)
    _write_json(hashes_path, _build_hashes(staging_root))

    # Best-effort field refresh for manifest signing metadata.
    hashes_obj = _read_json(hashes_path)
    manifest = _read_json(manifest_path)
    manifest["signing"]["root_digest_sha256"] = compute_root_digest(manifest, hashes_obj, policy)
    _write_json(manifest_path, manifest)

    # Refresh artifacts and hashes after manifest updates.
    manifest = _read_json(manifest_path)
    manifest["artifacts"] = _build_artifacts(staging_root)
    _write_json(manifest_path, manifest)
    _write_json(hashes_path, _build_hashes(staging_root))


def prepare_staging_directory(input_dir: str | Path, staging_dir: str | Path) -> Path:
    """Prepare a full pack staging directory from either staged or plain input."""

    source_root = Path(input_dir)
    if not source_root.exists():
        raise StagingError(f"input directory does not exist: {source_root}")
    if not source_root.is_dir():
        raise StagingError(f"input path is not a directory: {source_root}")

    staging_root = Path(staging_dir)
    if staging_root.exists():
        raise StagingError(f"staging directory already exists: {staging_root}")

    if is_staged_pack_directory(source_root):
        shutil.copytree(source_root, staging_root)
        return staging_root

    staging_root.mkdir(parents=True, exist_ok=False)
    _stage_normal_directory(source_root, staging_root)
    return staging_root
