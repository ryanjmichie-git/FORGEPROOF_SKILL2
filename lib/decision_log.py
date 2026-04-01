#!/usr/bin/env python3
"""CLI for appending hash-chained entries to a ForgeProof decision log."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib/ to path for rpb imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes


def _last_entry_hash(log_path: Path) -> tuple[str, int]:
    """Read last entry's hash and seq from log file. Returns (hash, seq)."""
    if not log_path.exists():
        return "0" * 64, 0
    text = log_path.read_text(encoding="utf-8").strip()
    if not text:
        return "0" * 64, 0
    last_line = text.splitlines()[-1]
    entry = json.loads(last_line)
    return entry["entry_hash"], entry["seq"]


def _compute_entry_hash(entry_without_hash: dict) -> str:
    """SHA-256 of canonical JSON of entry (excluding entry_hash field)."""
    return sha256_bytes(dumps_canonical(entry_without_hash))


def append(log_path: Path, phase: str, action: str, detail: str) -> None:
    """Append a hash-chained entry to the decision log."""
    prev_hash, prev_seq = _last_entry_hash(log_path)
    entry = {
        "seq": prev_seq + 1,
        "phase": phase,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "prev_hash": prev_hash,
    }
    entry["entry_hash"] = _compute_entry_hash(entry)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="ForgeProof decision log")
    sub = parser.add_subparsers(dest="command")
    ap = sub.add_parser("append", help="Append a hash-chained entry")
    ap.add_argument("--log", required=True, help="Path to decision-log.jsonl")
    ap.add_argument("--phase", required=True, help="Pipeline phase (parse, generate, evaluate, package)")
    ap.add_argument("--action", required=True, help="Action performed")
    ap.add_argument("--detail", required=True, help="Human-readable detail")
    args = parser.parse_args()
    if args.command == "append":
        append(Path(args.log), args.phase, args.action, args.detail)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
