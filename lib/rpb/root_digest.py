from __future__ import annotations

from typing import Any

from rpb.canon import dumps_canonical
from rpb.hash import sha256_bytes


def compute_root_digest(manifest_obj: Any, hashes_obj: Any, policy_obj: Any) -> str:
    """Compute root digest from canonical MANIFEST/HASHES/POLICY bytes."""

    payload = dumps_canonical(manifest_obj) + dumps_canonical(hashes_obj) + dumps_canonical(policy_obj)
    return sha256_bytes(payload)
