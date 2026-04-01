"""Tests for rpb.root_digest — deterministic root digest computation."""
from rpb.root_digest import compute_root_digest


_MANIFEST = {"schema_version": "rpb-manifest-0.1", "pack_id": "test"}
_HASHES = {"hash_algo": "sha256", "files": []}
_POLICY = {"schema_version": "rpb-policy-0.1", "policy_id": "default"}


def test_compute_root_digest_returns_64_char_hex():
    result = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_compute_root_digest_is_deterministic():
    d1 = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    d2 = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    assert d1 == d2


def test_changing_manifest_changes_digest():
    d1 = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    d2 = compute_root_digest({**_MANIFEST, "pack_id": "other"}, _HASHES, _POLICY)
    assert d1 != d2


def test_changing_hashes_changes_digest():
    d1 = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    d2 = compute_root_digest(
        _MANIFEST, {**_HASHES, "files": [{"path": "f", "sha256": "a" * 64}]}, _POLICY
    )
    assert d1 != d2


def test_changing_policy_changes_digest():
    d1 = compute_root_digest(_MANIFEST, _HASHES, _POLICY)
    d2 = compute_root_digest(_MANIFEST, _HASHES, {**_POLICY, "policy_id": "other"})
    assert d1 != d2
