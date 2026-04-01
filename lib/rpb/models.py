from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SignerStatus:
    key_id: str
    status: str
    reason: str = ""


@dataclass
class VerificationResult:
    verified: bool
    failed_checks: list[str] = field(default_factory=list)
    claims_verified: list[str] = field(default_factory=list)
    claims_rejected: list[str] = field(default_factory=list)
    signers: list[SignerStatus] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signers"] = [asdict(signer) for signer in self.signers]
        return payload
