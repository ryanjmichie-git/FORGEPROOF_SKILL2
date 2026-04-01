from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from rpb.hash import sha256_file
from rpb.root_digest import compute_root_digest
from rpb import exit_codes
from rpb.ed25519 import verify
from rpb.models import SignerStatus, VerificationResult
from rpb.pack_loader import PackLoadError, load_pack_directory
from rpb.sign import candidate_public_keys_from_file, load_public_key


@dataclass
class VerificationOutcome:
    result: VerificationResult
    exit_code: int


def _unique_append(target: list[str], value: str) -> None:
    if value not in target:
        target.append(value)


def _safe_hash_path(pack_root: Path, manifest_path: str) -> Path:
    normalized = manifest_path.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError(f"invalid absolute path in HASHES.json: {manifest_path}")

    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        raise ValueError(f"invalid traversal path in HASHES.json: {manifest_path}")
    if parts and parts[0].endswith(":"):
        raise ValueError(f"invalid drive-qualified path in HASHES.json: {manifest_path}")

    candidate = pack_root.joinpath(*parts)
    root_resolved = pack_root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"invalid extraction boundary path in HASHES.json: {manifest_path}")
    return candidate


def verify_hashes(pack_root: Path, hashes_obj: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if hashes_obj.get("hash_algo") != "sha256":
        failures.append("unsupported_hash_algorithm")
        return failures

    files = hashes_obj.get("files")
    if not isinstance(files, list):
        failures.append("hashes_missing_files_array")
        return failures

    for entry in files:
        if not isinstance(entry, dict):
            failures.append("hash_entry_not_object")
            continue

        manifest_path = entry.get("path")
        expected = entry.get("sha256")
        expected_size = entry.get("size_bytes")
        if not isinstance(manifest_path, str) or not isinstance(expected, str):
            failures.append("hash_entry_missing_fields")
            continue

        try:
            file_path = _safe_hash_path(pack_root, manifest_path)
        except ValueError as exc:
            failures.append(str(exc))
            continue

        if not file_path.exists() or not file_path.is_file():
            failures.append(f"missing_hashed_file:{manifest_path}")
            continue

        actual_hash = sha256_file(file_path)
        if actual_hash != expected.lower():
            failures.append(f"hash_mismatch:{manifest_path}")
            continue

        if isinstance(expected_size, int) and file_path.stat().st_size != expected_size:
            failures.append(f"size_mismatch:{manifest_path}")

    return failures


def _load_signer_metadata(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid signer metadata object: {path.name}")
    return payload


def _resolve_public_key_candidates(
    *,
    signatures_dir: Path,
    metadata: dict[str, Any],
    cli_pubkey: str | Path | None,
) -> list[bytes]:
    if cli_pubkey:
        return candidate_public_keys_from_file(cli_pubkey)

    public_key_hex = metadata.get("public_key_hex")
    if isinstance(public_key_hex, str):
        raw = bytes.fromhex(public_key_hex)
        if len(raw) != 32:
            raise ValueError("signer metadata public_key_hex must decode to 32 bytes")
        return [raw]

    public_key_file = metadata.get("public_key_file")
    if isinstance(public_key_file, str):
        path = signatures_dir / public_key_file
        if not path.exists():
            raise ValueError(
                f"missing public key file '{public_key_file}'; provide --pubkey or include signer public key"
            )
        return [load_public_key(path)]

    fallback = signatures_dir / "signer-1.pub"
    if fallback.exists():
        return [load_public_key(fallback)]
    raise ValueError(
        "missing public key for signer; provide --pubkey or include SIGNATURES/signer-1.pub"
    )


def _verify_signatures(
    *,
    pack_root: Path,
    root_digest_sha256: str,
    pubkey_path: str | Path | None,
) -> tuple[list[SignerStatus], int, int, list[str]]:
    signatures_dir = pack_root / "SIGNATURES"
    statuses: list[SignerStatus] = []
    failed_checks: list[str] = []
    valid_count = 0
    invalid_count = 0

    if not signatures_dir.exists() or not signatures_dir.is_dir():
        return statuses, valid_count, invalid_count, ["missing_signatures_directory"]

    metadata_files = sorted(signatures_dir.glob("*.json"), key=lambda p: p.name)
    if not metadata_files:
        return statuses, valid_count, invalid_count, ["missing_signer_metadata"]

    root_digest_bytes = bytes.fromhex(root_digest_sha256)
    for metadata_path in metadata_files:
        try:
            metadata = _load_signer_metadata(metadata_path)
            key_id = str(metadata.get("key_id", metadata_path.stem))
            algorithm = metadata.get("algorithm")
            if algorithm != "ed25519":
                raise ValueError("unsupported signer algorithm")

            referenced_digest = metadata.get("root_digest_sha256")
            if isinstance(referenced_digest, str) and referenced_digest != root_digest_sha256:
                raise ValueError("signer metadata root digest does not match computed root digest")

            signature_file = metadata.get("signature_file")
            if not isinstance(signature_file, str):
                signature_file = f"{metadata_path.stem}.sig"
            signature_path = signatures_dir / signature_file
            if not signature_path.exists() or not signature_path.is_file():
                raise FileNotFoundError(f"missing signature bytes file: {signature_file}")
            signature_bytes = signature_path.read_bytes()
            public_key_candidates = _resolve_public_key_candidates(
                signatures_dir=signatures_dir,
                metadata=metadata,
                cli_pubkey=pubkey_path,
            )
            is_valid = any(
                verify(public_key_bytes, root_digest_bytes, signature_bytes)
                for public_key_bytes in public_key_candidates
            )
            if is_valid:
                statuses.append(SignerStatus(key_id=key_id, status="valid"))
                valid_count += 1
            else:
                statuses.append(
                    SignerStatus(
                        key_id=key_id,
                        status="invalid",
                        reason="ed25519 signature verification failed",
                    )
                )
                invalid_count += 1
                _unique_append(failed_checks, f"signature_invalid:{key_id}")
        except Exception as exc:
            key_id = metadata_path.stem
            statuses.append(
                SignerStatus(
                    key_id=key_id,
                    status="invalid",
                    reason=str(exc),
                )
            )
            invalid_count += 1
            _unique_append(failed_checks, f"signature_error:{metadata_path.name}")

    return statuses, valid_count, invalid_count, failed_checks


def _has_required_path(pack_root: Path, requirement: str) -> bool:
    normalized = requirement.replace("\\", "/")
    parts = [part for part in PurePosixPath(normalized).parts if part not in ("", ".")]
    candidate = pack_root.joinpath(*parts)
    if requirement.endswith("/"):
        return candidate.exists() and candidate.is_dir()
    return candidate.exists()


def _profile_requirements_failures(
    *,
    claim: dict[str, Any],
    profile: str,
    policy_obj: dict[str, Any],
    manifest_obj: dict[str, Any],
    pack_root: Path,
) -> list[str]:
    failures: list[str] = []

    requirements = policy_obj.get("requirements")
    if not isinstance(requirements, dict):
        return ["policy_missing_requirements"]
    profile_requirements = requirements.get(profile)
    if not isinstance(profile_requirements, dict):
        return [f"policy_missing_profile_requirements:{profile}"]

    for required_path in profile_requirements.get("must_include_paths", []):
        if isinstance(required_path, str) and not _has_required_path(pack_root, required_path):
            failures.append(f"policy_required_path_missing:{required_path}")

    commands = manifest_obj.get("commands")
    if not isinstance(commands, dict):
        commands = {}
    for required_cmd in profile_requirements.get("must_have_commands", []):
        command_list = commands.get(required_cmd)
        if not isinstance(command_list, list) or not command_list:
            failures.append(f"policy_required_command_missing:{required_cmd}")

    evidence = manifest_obj.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    for required_type in profile_requirements.get("must_have_evidence_types", []):
        has_valid_evidence = any(
            isinstance(item, dict)
            and item.get("type") == required_type
            and isinstance(item.get("exit_code"), int)
            and int(item.get("exit_code")) == 0
            for item in evidence
        )
        if not has_valid_evidence:
            failures.append(f"policy_required_evidence_missing:{required_type}")

    if bool(profile_requirements.get("must_reference_spec_properties", False)):
        properties = claim.get("properties")
        if not isinstance(properties, list) or not properties:
            failures.append("policy_required_spec_properties_missing")

    return failures


def _evaluate_claims(
    pack_root: Path,
    manifest_obj: dict[str, Any],
    policy_obj: dict[str, Any],
    valid_signatures: int,
) -> tuple[list[str], list[str], list[str]]:
    claims_verified: list[str] = []
    claims_rejected: list[str] = []
    failed_checks: list[str] = []

    claims = manifest_obj.get("claims")
    if not isinstance(claims, list):
        return claims_verified, claims_rejected, ["manifest_claims_missing_or_invalid"]

    profiles = policy_obj.get("profiles")
    thresholds = policy_obj.get("signature_thresholds")
    if not isinstance(profiles, dict) or not isinstance(thresholds, dict):
        return claims_verified, claims_rejected, ["policy_missing_profiles_or_thresholds"]

    for index, claim in enumerate(claims):
        claim_id = f"claim[{index}]"
        profile = None
        if isinstance(claim, dict):
            claim_id = str(claim.get("claim_id", claim_id))
            profile = claim.get("profile")
        if not isinstance(profile, str):
            claims_rejected.append(claim_id)
            _unique_append(failed_checks, "claim_missing_profile")
            continue

        if not bool(profiles.get(profile, False)):
            claims_rejected.append(claim_id)
            _unique_append(failed_checks, f"policy_profile_disabled:{profile}")
            continue

        threshold = thresholds.get(profile)
        if not isinstance(threshold, int) or threshold < 1:
            claims_rejected.append(claim_id)
            _unique_append(failed_checks, f"policy_invalid_signature_threshold:{profile}")
            continue

        requirement_failures = _profile_requirements_failures(
            claim=claim if isinstance(claim, dict) else {},
            profile=profile,
            policy_obj=policy_obj,
            manifest_obj=manifest_obj,
            pack_root=pack_root,
        )
        if requirement_failures:
            claims_rejected.append(claim_id)
            for item in requirement_failures:
                _unique_append(failed_checks, item)
            continue

        if valid_signatures >= threshold:
            claims_verified.append(claim_id)
        else:
            claims_rejected.append(claim_id)
            _unique_append(failed_checks, f"signature_threshold_not_met:{profile}")
            if valid_signatures == 0:
                _unique_append(failed_checks, f"missing_required_signatures:{profile}")

    return claims_verified, claims_rejected, failed_checks


def verify_pack_directory(
    pack_dir: str | Path,
    *,
    pubkey_path: str | Path | None = None,
) -> VerificationOutcome:
    result = VerificationResult(verified=False)

    try:
        pack = load_pack_directory(pack_dir)
    except PackLoadError as exc:
        result.failed_checks.append(str(exc))
        return VerificationOutcome(result=result, exit_code=exit_codes.POLICY_VIOLATION)

    hash_failures = verify_hashes(pack.root_dir, pack.hashes)
    if hash_failures:
        result.failed_checks.extend(hash_failures)
        return VerificationOutcome(result=result, exit_code=exit_codes.HASH_MISMATCH)

    root_digest_sha256 = compute_root_digest(pack.manifest, pack.hashes, pack.policy)
    statuses, valid_count, invalid_count, signature_checks = _verify_signatures(
        pack_root=pack.root_dir,
        root_digest_sha256=root_digest_sha256,
        pubkey_path=pubkey_path,
    )
    result.signers = statuses
    result.failed_checks.extend(signature_checks)

    claims_verified, claims_rejected, policy_checks = _evaluate_claims(
        pack.root_dir,
        pack.manifest, pack.policy, valid_count
    )
    result.claims_verified = claims_verified
    result.claims_rejected = claims_rejected
    result.failed_checks.extend(policy_checks)

    if invalid_count > 0:
        return VerificationOutcome(result=result, exit_code=exit_codes.SIGNATURE_INVALID)

    if result.failed_checks:
        return VerificationOutcome(result=result, exit_code=exit_codes.POLICY_VIOLATION)

    result.verified = True
    return VerificationOutcome(result=result, exit_code=exit_codes.VERIFY_PASSED)
