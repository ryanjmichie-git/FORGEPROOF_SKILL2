# ForgeProof

Turn GitHub issues into working code with cryptographically signed provenance bundles.

When you invoke ForgeProof, Claude reads a GitHub issue, extracts requirements, plans an implementation, writes code and tests, then packages everything into a tamper-evident `.rpack` bundle. The bundle proves what was done, why, and that nothing was altered after signing.

## Requirements

- **Python 3.11+** (stdlib only — no pip dependencies)
- **OpenSSH 8.0+** (provides `ssh-keygen` for Ed25519 signing)
- **GitHub CLI** (`gh`) authenticated to your account — [install](https://cli.github.com/)

Verify your setup:
```bash
/forgeproof preflight
```

## Supported Languages

ForgeProof auto-detects your project's language and toolchain:

| Language | Config file | Test runner | Linter |
|----------|-------------|-------------|--------|
| Python | `pyproject.toml`, `setup.cfg` | pytest | ruff, flake8 |
| TypeScript/JavaScript | `package.json` | jest, vitest, mocha | eslint |
| Go | `go.mod` | go test | golangci-lint |

## Usage

### Generate code from an issue

```
/forgeproof 42
```

Runs the full pipeline: fetch issue → extract requirements → plan → generate code → run tests → sign `.rpack` bundle. You'll be asked to approve the plan before code generation begins.

Browse your assigned issues instead:
```
/forgeproof
```

### Push to a PR

```
/forgeproof-push
```

Creates a git branch and opens a pull request with the provenance summary embedded in the PR description.

### Verify a bundle

```
/forgeproof-verify .forgeproof/issue-42.rpack
```

Checks the Ed25519 signature, hash chain integrity, and artifact hashes. Reports whether the bundle has been tampered with.

### Clean up state

```
/forgeproof-reset 42
```

Removes provenance chains, bundles, ephemeral keys, and branches for a specific issue. Use `--all` to clean everything.

### Re-running on the same issue

ForgeProof handles re-runs gracefully. Running `/forgeproof 42` again will:
- Clean up the previous chain and bundle (via `--force`)
- Delete and recreate the local branch
- Push with `--force-with-lease` if the remote branch exists
- Update the existing PR instead of creating a duplicate

## How It Works

ForgeProof operates in four phases:

1. **Parse & Plan** — Fetches the GitHub issue, extracts structured requirements (REQ-1, REQ-2, ...), scans the repo, and proposes a plan. Waits for your approval.
2. **Generate** — Writes implementation and tests. Every file edit and decision is logged to a SHA-256 hash chain with Ed25519 signatures.
3. **Evaluate** — Runs your project's test suite and linter. Maps results back to requirements. Attempts one auto-fix if something fails.
4. **Package** — Builds the `.rpack` provenance bundle: manifest, artifact hashes, requirement coverage, decision log, and a root Ed25519 signature. The ephemeral private key is deleted after signing.

## The .rpack Bundle

The `.rpack` file is a JSON document containing:

- **Issue metadata** — number, title, URL
- **Requirements** — extracted from the issue, with coverage status
- **Artifacts** — every file created or modified, with SHA-256 hashes
- **Decisions** — why Claude chose each approach
- **Evaluation** — test results, lint results, coverage percentage
- **Signature** — Ed25519 signature over a root digest of all the above

The evaluation status is one of:
- `pass` — all requirements covered, all tests pass
- `partial` — some requirements uncovered or tests failing (details included)
- `fail` — critical failures

Bundles are always produced regardless of status. The status tells reviewers whether to trust the bundle at a glance.

## Security Model

- **Ephemeral keys** — a new Ed25519 keypair is generated per bundle. The private key is deleted after signing. The public key is embedded in the `.rpack` for self-contained verification.
- **Tamper evidence** — modifying any field in the bundle, any block in the chain, or any artifact file causes verification to fail.
- **No external data transmission** — all data stays local. ForgeProof only calls `gh` CLI (which uses your existing GitHub auth) and `ssh-keygen`.

## Privacy

ForgeProof stores provenance data locally in the `.forgeproof/` directory at your project root. No data is sent to external servers beyond what `gh` CLI sends to GitHub (issue reads, PR creation). No telemetry, no analytics, no third-party services.

## Troubleshooting

**"No chain found for issue N"** — Run `/forgeproof N` first to initialize the chain.

**"No ephemeral key found"** — The key is session-scoped. If you initialized the chain in a previous session, you'll need to re-run `/forgeproof N` to generate a new key.

**"ssh-keygen failed"** — Ensure OpenSSH 8.0+ is installed. On macOS, the built-in ssh-keygen works. On Linux, install `openssh-client`.

**"gh issue list failed"** — Run `gh auth status` to check authentication. Run `gh auth login` if needed.

**Verification fails with "Root digest mismatch"** — The bundle contents were modified after signing. This is the tamper detection working as intended.

**Verification warns "Artifact not found"** — Normal when verifying a bundle from a different checkout or branch. The artifact hashes can only be checked against files that exist locally.

## Known Limitations

- **Post-rebase commit SHA mismatch** — If you rebase a forgeproof branch after finalization, the `commit_sha` in the bundle no longer matches the branch HEAD. Verification still passes (it checks artifacts and chain integrity, not git commits). Workaround: re-run `/forgeproof` after rebasing.
- **Ephemeral keys are session-scoped** — The Ed25519 private key exists only in `/tmp` for the current session. If the session ends before finalization, re-run `/forgeproof` to generate a new key.
- **No `.gitignore` enforcement** — ForgeProof warns if no `.gitignore` exists but does not create one. Ensure your project has one to avoid committing `__pycache__/` and other generated files.

## Changelog

### 0.2.0
- **Fix:** Replaced `git add -A` with explicit file staging to prevent committing `__pycache__/` and other junk
- **Fix:** Added re-run detection — handles existing branches, remote branches, and PRs gracefully
- **New:** `/forgeproof-reset` skill for cleaning up provenance state and branches
- **New:** `--force` flag on `init` to overwrite existing chains
- **New:** `reset` subcommand in the provenance engine
- **New:** 38 tests covering all subcommands, chain integrity, verification, and E2E pipeline
- **Improved:** Hook error messages now direct users to the correct workflow
- **Improved:** README with re-run documentation, known limitations, and changelog
- **Documented:** Post-rebase provenance gap in chain-format.md

### 0.1.0
- Initial release with `/forgeproof`, `/forgeproof-push`, `/forgeproof-verify`
- Ed25519-signed SHA-256 hash chain provenance engine
- Multi-language toolchain detection (Python, TypeScript/JavaScript, Go)
- PreToolUse hook to gate PR creation on bundle existence
- PostToolUse hook for linting on every file edit
