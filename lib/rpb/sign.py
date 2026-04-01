from __future__ import annotations

from pathlib import Path
from typing import Any

from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes
from rpb.root_digest import compute_root_digest
from rpb.ed25519 import derive_public_key, sign
from rpb.pack_loader import load_pack_directory


SIGNER_BASENAME = "signer-1"
SIGNATURE_ALGORITHM = "ed25519"
DETERMINISTIC_CREATED_UTC = "1970-01-01T00:00:00Z"


class SignError(ValueError):
    """Raised when signing cannot be completed."""


def load_private_key(path: str | Path) -> bytes:
    key_path = Path(path)
    raw = key_path.read_bytes()
    if len(raw) != 32:
        raise SignError(f"invalid private key length in {key_path}: expected 32 bytes")
    return raw


def load_public_key(path: str | Path) -> bytes:
    key_path = Path(path)
    raw = key_path.read_bytes()
    if len(raw) != 32:
        raise SignError(f"invalid public key length in {key_path}: expected 32 bytes")
    return raw


def candidate_public_keys_from_file(path: str | Path) -> list[bytes]:
    """Return possible public keys from a 32-byte raw key file.

    The file may hold either:
    - raw Ed25519 public key bytes, or
    - raw Ed25519 private seed bytes (from which a public key can be derived).
    """

    raw = load_public_key(path)
    derived = derive_public_key(raw)
    if derived == raw:
        return [raw]
    return [raw, derived]


def compute_key_id(public_key_bytes: bytes) -> str:
    fingerprint = sha256_bytes(public_key_bytes)
    return f"ed25519:{fingerprint[:16]}"


def sign_root_digest(private_key_bytes: bytes, root_digest_bytes: bytes) -> bytes:
    if len(root_digest_bytes) != 32:
        raise SignError("root digest payload for signing must be 32 bytes")
    return sign(private_key_bytes, root_digest_bytes)


def _write_public_key(public_key_bytes: bytes, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(public_key_bytes)


def _signature_metadata(
    *,
    key_id: str,
    root_digest_sha256: str,
    signature_file: str,
    public_key_file: str,
    public_key_bytes: bytes,
) -> dict[str, Any]:
    return {
        "key_id": key_id,
        "algorithm": SIGNATURE_ALGORITHM,
        "created_utc": DETERMINISTIC_CREATED_UTC,
        "root_digest_sha256": root_digest_sha256,
        "signature_file": signature_file,
        "public_key_file": public_key_file,
        "public_key_hex": public_key_bytes.hex(),
    }


def write_signatures(
    staging_dir: str | Path,
    private_key_path: str | Path,
    pubkey_out: str | Path | None = None,
) -> dict[str, Any]:
    """Write signer metadata/signature files for a staged unpacked pack directory."""

    pack = load_pack_directory(staging_dir)
    root_digest_sha256 = compute_root_digest(pack.manifest, pack.hashes, pack.policy)
    root_digest_bytes = bytes.fromhex(root_digest_sha256)

    private_key_bytes = load_private_key(private_key_path)
    public_key_bytes = derive_public_key(private_key_bytes)
    key_id = compute_key_id(public_key_bytes)

    signature_bytes = sign_root_digest(private_key_bytes, root_digest_bytes)
    signatures_dir = Path(staging_dir) / "SIGNATURES"
    signatures_dir.mkdir(parents=True, exist_ok=True)

    signature_file = f"{SIGNER_BASENAME}.sig"
    metadata_file = f"{SIGNER_BASENAME}.json"
    public_key_file = f"{SIGNER_BASENAME}.pub"

    (signatures_dir / signature_file).write_bytes(signature_bytes)
    _write_public_key(public_key_bytes, signatures_dir / public_key_file)
    if pubkey_out:
        _write_public_key(public_key_bytes, Path(pubkey_out))

    metadata = _signature_metadata(
        key_id=key_id,
        root_digest_sha256=root_digest_sha256,
        signature_file=signature_file,
        public_key_file=public_key_file,
        public_key_bytes=public_key_bytes,
    )
    (signatures_dir / metadata_file).write_bytes(dumps_canonical(metadata))
    return metadata
