# ForgeProof — Issue to Code with Provenance

You are executing the ForgeProof pipeline. This converts a GitHub issue into working code with a cryptographically signed provenance bundle.

The user provided an issue number: $ARGUMENTS

---

## Phase 0: Pre-flight

Run these checks before anything else. If any fail, stop and tell the user.

1. Run `gh auth status` — if it fails, say: "ForgeProof requires `gh` CLI to be installed and authenticated. Run `gh auth login` first."
2. Run `gh repo view --json nameWithOwner -q .nameWithOwner` to get the repo identifier. Save this as REPO_NAME.
3. Check for `.forgeproof.toml` in the repo root. If it exists, note its presence. If not, defaults will be used.
4. Run `python3 --version` and verify it's 3.11+. If not, say: "ForgeProof requires Python 3.11+ (for stdlib tomllib)."
5. Verify `.forgeproof/lib/rpb/ed25519.py` exists. If not, say: "ForgeProof is not installed. Run the install script first."

## Phase 1: Parse & Plan

1. Run: `gh issue view $ARGUMENTS --json title,body,labels,assignees`
2. Read the issue body and extract a numbered list of requirements: REQ-1, REQ-2, etc.
3. Scan the repo structure using Glob and Read to understand existing code, tests, and dependencies.
4. Produce a plan: which files to create/modify, what each change accomplishes, which requirement each change satisfies.
5. Log the decision:
   ```
   python .forgeproof/lib/decision_log.py append --log .forgeproof/decision-log.jsonl --phase parse --action planned --detail "N requirements extracted, M files planned"
   ```
6. **Present the plan to the user and WAIT for approval before proceeding.** Show:
   - Issue title and requirements list
   - Files to create/modify
   - Which requirements each file addresses

## Phase 2: Generate

After the user approves the plan:

1. Write implementation files using Write/Edit tools.
2. Write test files using Write/Edit tools.
3. If `.forgeproof.toml` exists, respect `paths.allowed` and `paths.denied`. Otherwise use defaults: allowed = `src/**/*`, `lib/**/*`, `app/**/*`, `tests/**/*`; denied = `.env`, `**/*.key`, `**/*.pem`, `.github/**`.
4. After writing each file, log it:
   ```
   python .forgeproof/lib/decision_log.py append --log .forgeproof/decision-log.jsonl --phase generate --action wrote_file --detail "path/to/file.py (N lines)"
   ```

## Phase 3: Evaluate

1. Detect test commands:
   - If `.forgeproof.toml` has `evaluation.commands`, use those.
   - Otherwise auto-detect: if `tests/` or `conftest.py` exists, use `python -m pytest -q`; if `pyproject.toml` has `[tool.ruff]`, use `python -m ruff check .`
2. Run each test/lint command via Bash. Capture stdout, stderr, and exit code.
3. Map test results back to requirements (REQ-1 covered by test_X, etc.).
4. If a required command fails, attempt ONE fix:
   - Read the error output
   - Fix the issue in the code
   - Re-run the command
5. If a required command still fails after the fix attempt, STOP. Tell the user:
   - What command failed
   - The error output
   - Suggestion for manual fix
   - Phase 4 will not execute.
6. Log evaluation results:
   ```
   python .forgeproof/lib/decision_log.py append --log .forgeproof/decision-log.jsonl --phase evaluate --action tested --detail "N/M tests passed, lint clean/N issues"
   ```
7. Write `.forgeproof/last-run.json` using the Write tool with this structure:
   ```json
   {
     "issue_number": <N>,
     "issue_title": "<title>",
     "repo": "<owner/repo>",
     "branch": "forgeproof/issue-<N>",
     "files_changed": ["<path1>", "<path2>"],
     "requirements": ["REQ-1 description", "REQ-2 description"],
     "requirements_met": <count>,
     "requirements_total": <total>,
     "tests_passed": <count>,
     "tests_total": <total>,
     "rpack_path": ".forgeproof/issue-<N>.rpack",
     "timestamp": "<ISO 8601 UTC>"
   }
   ```

## Phase 4: Package

1. Run the provenance builder:
   ```bash
   python .forgeproof/lib/provenance.py build \
     --run-state .forgeproof/last-run.json \
     --decision-log .forgeproof/decision-log.jsonl \
     --output .forgeproof/issue-$ARGUMENTS.rpack \
     --repo-root .
   ```
   If `.forgeproof.toml` exists, add: `--config .forgeproof.toml`

2. Report the summary to the user:
   - Files changed (with line counts)
   - Tests: N/M passed
   - Requirements: N/M met
   - Provenance bundle: `.forgeproof/issue-$ARGUMENTS.rpack`
   - Next step: "Review the changes, then run `/forgeproof-push` to create a PR."
