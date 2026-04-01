#!/usr/bin/env python3
"""CLI for building, signing, and packing ForgeProof .rpack provenance bundles."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Ensure lib/ is on sys.path so rpb imports work when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from rpb.canon import dumps_canonical
from rpb.ed25519 import generate_ephemeral_keypair
from rpb.hash import sha256_bytes
from rpb.pack_writer import create_rpack
from rpb.sign import write_signatures
from rpb.staging import DEFAULT_POLICY_FALLBACK, finalize_pack_metadata


VERIFY_INSTRUCTIONS = (
    "Offline verify: run `rpb verify <pack.rpack>` or extract and inspect HASHES.json manually.\n"
    "Each file listed in HASHES.json must match its sha256 digest.\n"
    "The SIGNATURES/ directory contains Ed25519 signatures over the root digest.\n"
)


def _read_json_file(path: Path) -> dict:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl_file(path: Path) -> list[dict]:
    """Read a JSONL file and return list of parsed objects."""
    entries = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def _build_claims(run_state: dict) -> list[dict]:
    """Build claims list based on run state (tests passed -> P2)."""
    claims = [
        {
            "claim_id": "CLAIM-INTEGRITY-001",
            "profile": "P0",
            "label": "Integrity: contents match signed hashes",
            "properties": [],
        }
    ]
    tests_passed = run_state.get("tests_passed", 0)
    tests_total = run_state.get("tests_total", 0)
    if tests_total > 0 and tests_passed == tests_total:
        claims.append(
            {
                "claim_id": "CLAIM-TESTS-001",
                "profile": "P2",
                "label": f"All {tests_total} tests passed",
                "properties": [],
            }
        )
    return claims


def _build_evidence(run_state: dict) -> list[dict]:
    """Build evidence entries from run state."""
    evidence = []
    tests_passed = run_state.get("tests_passed", 0)
    tests_total = run_state.get("tests_total", 0)
    if tests_total > 0:
        evidence.append(
            {
                "type": "tests",
                "label": f"Test results: {tests_passed}/{tests_total} passed",
                "path": "DECISION_LOG/decision-log.jsonl",
            }
        )
    return evidence


def _build_commands(run_state: dict) -> dict:
    """Build commands dict from run state."""
    commands: dict[str, list] = {"build": [], "tests": [], "proofs": []}
    tests_total = run_state.get("tests_total", 0)
    if tests_total > 0:
        commands["tests"] = ["tests"]
    return commands


def _build_manifest(run_state: dict, config: dict) -> dict:
    """Build the MANIFEST.json content from run state and config."""
    issue_number = run_state.get("issue_number", 0)
    pack_id = f"issue-{issue_number}"

    return {
        "schema_version": "rpb-manifest-0.1",
        "pack_id": pack_id,
        "created_utc": run_state.get("timestamp", "1970-01-01T00:00:00Z"),
        "producer": {
            "name": "forgeproof",
            "version": "0.1.0",
            "build": "skill-provenance",
        },
        "subject": {
            "name": run_state.get("repo", "unknown"),
            "version": "0.0.0",
            "vcs": {
                "type": "git",
                "branch": run_state.get("branch", "unknown"),
            },
        },
        "claims": _build_claims(run_state),
        "environment": {
            "type": "agent",
            "image_digest": "sha256:" + "0" * 64,
            "os_arch": "linux/amd64",
            "toolchain": [],
        },
        "commands": _build_commands(run_state),
        "artifacts": [],
        "evidence": _build_evidence(run_state),
        "policy": {
            "policy_id": "default-mvp",
            "policy_version": "0.1.0",
            "policy_sha256": sha256_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK)),
        },
        "signing": {
            "root_digest_sha256": "0" * 64,
            "signers": [],
        },
        "redactions": [
            {"pattern": ".env", "reason": "Prevent secret leakage"},
            {"pattern": "**/*_key*", "reason": "Prevent private key inclusion"},
        ],
        "run_metadata": {
            "issue_number": run_state.get("issue_number"),
            "issue_title": run_state.get("issue_title"),
            "repo": run_state.get("repo"),
            "branch": run_state.get("branch"),
            "files_changed": run_state.get("files_changed", []),
            "requirements": run_state.get("requirements", []),
            "requirements_met": run_state.get("requirements_met", 0),
            "requirements_total": run_state.get("requirements_total", 0),
            "tests_passed": run_state.get("tests_passed", 0),
            "tests_total": run_state.get("tests_total", 0),
        },
    }


def build(args: argparse.Namespace) -> None:
    """Execute the build subcommand: stage, sign, and pack an .rpack bundle."""

    # 1. Read inputs
    run_state_path = Path(args.run_state)
    decision_log_path = Path(args.decision_log)
    output_path = Path(args.output)

    run_state = _read_json_file(run_state_path)

    # 3. Load config (optional)
    config_path = Path(args.config) if args.config else None
    config = load_config(config_path)

    # 4. Create staging directory
    staging_dir = tempfile.mkdtemp(prefix="forgeproof-staging-")
    staging_root = Path(staging_dir)

    try:
        # Write MANIFEST.json
        manifest = _build_manifest(run_state, config)
        manifest_path = staging_root / "MANIFEST.json"
        manifest_path.write_bytes(dumps_canonical(manifest))

        # Write POLICY.json
        policy_path = staging_root / "POLICY.json"
        policy_path.write_bytes(dumps_canonical(DEFAULT_POLICY_FALLBACK))

        # Create directories
        (staging_root / "SIGNATURES").mkdir(parents=True, exist_ok=True)
        (staging_root / "VERIFY").mkdir(parents=True, exist_ok=True)
        (staging_root / "DECISION_LOG").mkdir(parents=True, exist_ok=True)

        # Copy decision log
        shutil.copy2(decision_log_path, staging_root / "DECISION_LOG" / "decision-log.jsonl")

        # Write verify instructions
        (staging_root / "VERIFY" / "verify_instructions.txt").write_text(
            VERIFY_INSTRUCTIONS, encoding="utf-8"
        )

        # 5. Finalize pack metadata (computes HASHES.json and root digest)
        finalize_pack_metadata(staging_root)

        # 6-8. Generate ephemeral key, sign, delete key
        key_path_config = config.get("signing", {}).get("key_path")
        if key_path_config and Path(key_path_config).exists():
            # Use configured key
            sig_meta = write_signatures(staging_root, key_path_config)
        else:
            # Generate ephemeral keypair
            private_key, public_key = generate_ephemeral_keypair()
            key_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".key")
            key_tmp_path = Path(key_tmp.name)
            try:
                key_tmp.write(private_key)
                key_tmp.close()
                sig_meta = write_signatures(staging_root, key_tmp_path)
            finally:
                # Always delete ephemeral private key
                if key_tmp_path.exists():
                    key_tmp_path.unlink()

        # 9. Create .rpack bundle
        output_path.parent.mkdir(parents=True, exist_ok=True)
        create_rpack(staging_root, output_path)

        # 10. Print JSON summary to stdout
        summary = {
            "status": "ok",
            "rpack": str(output_path),
            "pack_id": manifest.get("pack_id"),
            "claims": [c["profile"] for c in manifest.get("claims", [])],
            "signature": {
                "key_id": sig_meta.get("key_id"),
                "algorithm": sig_meta.get("algorithm"),
            },
        }
        print(json.dumps(summary, indent=2))

    finally:
        # Clean up staging directory
        shutil.rmtree(staging_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="provenance",
        description="ForgeProof provenance CLI -- build and sign .rpack bundles",
    )
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="Build a signed .rpack bundle")
    build_parser.add_argument(
        "--run-state", required=True, help="Path to last-run.json"
    )
    build_parser.add_argument(
        "--decision-log", required=True, help="Path to decision-log.jsonl"
    )
    build_parser.add_argument(
        "--config", default=None, help="Path to .forgeproof.toml (optional)"
    )
    build_parser.add_argument(
        "--output", required=True, help="Output .rpack file path"
    )
    build_parser.add_argument(
        "--repo-root", required=True, help="Repo root for resolving file paths"
    )

    args = parser.parse_args()

    if args.command == "build":
        build(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
