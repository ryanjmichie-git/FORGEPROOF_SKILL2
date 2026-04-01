"""Tests for rpb.models — dataclasses for verification results."""
from rpb.models import SignerStatus, VerificationResult


def test_signer_status_defaults():
    s = SignerStatus(key_id="ed25519:abc", status="valid")
    assert s.reason == ""


def test_verification_result_defaults():
    r = VerificationResult(verified=True)
    assert r.failed_checks == []
    assert r.claims_verified == []
    assert r.claims_rejected == []
    assert r.signers == []


def test_verification_result_to_dict():
    s = SignerStatus(key_id="k1", status="valid")
    r = VerificationResult(verified=True, signers=[s])
    d = r.to_dict()
    assert d["verified"] is True
    assert d["signers"] == [{"key_id": "k1", "status": "valid", "reason": ""}]


def test_verification_result_failed_is_not_verified():
    r = VerificationResult(verified=False, failed_checks=["hash_mismatch:foo"])
    assert not r.verified
    assert "hash_mismatch:foo" in r.failed_checks
