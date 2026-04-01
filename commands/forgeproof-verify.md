# ForgeProof Verify — Check .rpack Bundle Integrity

You are verifying a ForgeProof provenance bundle.

The user provided a path: $ARGUMENTS

---

## Steps

1. **Validate input:** Check that the file at `$ARGUMENTS` exists and ends with `.rpack`. If not, say: "Please provide a path to an .rpack file."

2. **Verify `.forgeproof/lib/` exists.** If not, say: "ForgeProof is not installed. Run the install script first."

3. **Extract and verify** by running:
   ```bash
   python3 -c "
   import sys, json, tempfile
   sys.path.insert(0, '.forgeproof/lib')
   from rpb.pack_reader import extract_rpack
   from rpb.verify_signatures import verify_pack_directory

   with tempfile.TemporaryDirectory(prefix='fp-verify-') as tmp:
       extract_rpack('$ARGUMENTS', tmp)
       outcome = verify_pack_directory(tmp)
       result = outcome.result
       print(json.dumps({
           'verified': result.verified,
           'exit_code': outcome.exit_code,
           'signers': [{'key_id': s.key_id, 'status': s.status, 'reason': s.reason} for s in result.signers],
           'claims_verified': result.claims_verified,
           'claims_rejected': result.claims_rejected,
           'failed_checks': result.failed_checks,
       }, indent=2))
   "
   ```

4. **Present results** to the user:
   - **Overall:** VERIFIED or FAILED
   - **Signers:** List each signer with key_id and status (valid/invalid)
   - **Claims:** Which claims were verified vs rejected
   - **Failed checks:** Any issues found (hash mismatches, missing signatures, policy violations)

   If verified, say: "Bundle integrity confirmed. The provenance chain is intact."
   If failed, explain which checks failed and what they mean.
