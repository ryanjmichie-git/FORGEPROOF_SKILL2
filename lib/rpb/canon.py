from __future__ import annotations

import json
from typing import Any


def dumps_canonical(obj: Any) -> bytes:
    """Return canonical JSON bytes for deterministic hashing/signing.

    Canonicalization strategy:
    - UTF-8 encoding
    - Lexicographic key ordering for all objects
    - No insignificant whitespace
    - Array order is preserved by JSON encoder behavior
    - Floats are encoded with Python's deterministic JSON float formatter;
      non-finite floats are rejected (`allow_nan=False`)
    """

    text = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return text.encode("utf-8")


def loads_json(payload: bytes) -> Any:
    """Decode UTF-8 JSON bytes into Python objects."""

    return json.loads(payload.decode("utf-8"))
