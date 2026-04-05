# Harness VS Code Adaptation — Design Spec

**Date:** 2026-04-04
**Updated:** 2026-04-05
**Status:** Approved (revised after external review)
**Scope:** Adapt the three-agent harness to work as Claude Code slash commands in VS Code, with paths corrected for the FORGEPROOF_SKILL2 repo layout.

---

## Summary

The existing harness (`harness/`) implements Anthropic's three-agent architecture (Planner → Generator → Evaluator) for long-running autonomous coding sessions. It currently orchestrates via `run.sh` calling `claude` CLI subprocesses, which doesn't work in VS Code. This spec adapts the harness into four Claude Code slash commands that preserve the same file-based handoff pattern and context isolation.

Key changes from the original harness files:
- Slash commands replace `run.sh` as the invocation mechanism
- Sprint contracts added as a mandatory step before each major feature
- Simplification principle added — remove process weight that isn't load-bearing
- Self-evaluation softened to a quick sanity check, not a replacement for the Evaluator
- All file paths corrected for this repo's actual layout

---

## User Stories

1. **As a developer**, I run `/harness-plan "add MCP server layer"` and get a comprehensive `spec.md` without writing it myself.
2. **As a developer**, I run `/harness-generate` in a new conversation and Claude implements the spec autonomously with git commits, without drifting or asking for approvals.
3. **As a developer**, I run `/harness-evaluate` in a new conversation and get an honest, skeptical eval report with actionable bugs — not self-congratulatory praise.
4. **As a developer**, I run `/harness-fix` to address eval bugs, then re-evaluate until passing.

---

## Technical Architecture

### Orchestration: Slash Commands Replace Shell Script

```
User invokes slash command in VS Code
  → Command prompt loads (self-contained agent instructions)
    → Agent reads prerequisite files (spec.md, handoff.md, etc.)
      → Agent executes task
        → Agent writes output artifact (spec.md, handoff.md, eval-report.md)
          → Agent tells user what to run next
```

**Context isolation:** The user starts a new VS Code conversation between phases. Each command gets a fresh context window — the same clean-slate benefit that `run.sh` achieved by spawning separate `claude` processes. This is non-negotiable: the Anthropic blog is explicit that agents communicate via files, not inline conversation, and that context resets between phases make the generator-evaluator separation real.

**File-based communication:** Agents communicate exclusively via files:
- Planner writes `spec.md`
- Generator writes `sprint-contract.md` and `harness/handoff.md`
- Evaluator writes `harness/eval-report.md`

### Sprint Contracts

Before the Generator starts each major feature, it writes a sprint contract (`sprint-contract.md`) — an explicit list of what will be built and the specific, testable criteria that define success. Each criterion should be concrete enough that the independent Evaluator can verify it. Aim for high specificity.

The Evaluator tests against these exact criteria. A contracted item that isn't implemented is a Critical bug, not a "remaining work item."

### Context Management

Long sessions cause two failure modes: context degradation (losing coherence as the window fills) and context anxiety (prematurely wrapping up work because the model senses the limit approaching).

**How to handle this:**
- Communicate between phases via files, not inline conversation. Files are the continuity mechanism.
- If context is growing large within a phase, write a handoff artifact, tell the user to start a new conversation, and resume from the handoff.
- If the agent notices itself rushing to finish or cutting scope that the spec requires, that is context anxiety. Write a handoff, reset, resume.
- Do not simplify the spec to fit within a session.

### Simplification Principle

Every rule in the harness encodes an assumption about what the model cannot do reliably on its own. As the harness is used, notice when a rule is no longer load-bearing. If the Generator can sustain coherent multi-hour builds without sprint decomposition, skip it. If self-evaluation is catching real issues before handoff, reduce evaluator passes on simple features. Find the simplest process that maintains quality. Only add complexity when needed.

---

## File Plan

### New Files

| File | Description |
|------|-------------|
| `commands/harness-plan.md` | Planner slash command — converts brief to spec.md |
| `commands/harness-generate.md` | Generator slash command — implements spec.md |
| `commands/harness-evaluate.md` | Evaluator slash command — tests and grades implementation |
| `commands/harness-fix.md` | Generator fix pass — addresses bugs from eval-report.md |

Note: Placed in `commands/` alongside existing ForgeProof commands (`forgeproof.md`, `forgeproof-push.md`, `forgeproof-verify.md`) for consistency. The `.claude/` directory is not used for commands in this repo.

### New Artifacts (generated at runtime, not checked in)

| File | Created by | Purpose |
|------|-----------|---------|
| `spec.md` | Planner | Product specification |
| `sprint-contract.md` | Generator | Testable success criteria for current sprint |
| `harness/handoff.md` | Generator | Structured handoff between phases |
| `harness/eval-report.md` | Evaluator | Scores, PASS/FAIL, bug reports |

### Unchanged Files

| File | Reason |
|------|--------|
| `harness/harness-design-action-plan.md` | Source methodology reference — no changes needed |
| `harness/criteria.md` | Grading criteria are domain-correct for this repo |
| `harness/run.sh` | Kept for reference — no longer primary invocation method |

### Modified Files

| File | Change |
|------|--------|
| `CLAUDE.md` | Add Harness Commands section documenting the workflow |
| `harness/planner.md` | Update stale paths to match this repo layout (reference doc, not canonical) |
| `harness/generator.md` | Update stale paths and codebase layout tree (reference doc, not canonical) |
| `harness/evaluator.md` | Update stale paths in smoke tests and integration tests (reference doc, not canonical) |
| `harness/handoff-template.md` | Update `forgeproof-skill/lib/` → `lib/` in example commands |

Note: The slash commands in `commands/` are canonical. The `harness/*.md` files are updated to avoid confusion but serve as reference docs only.

---

## Command Specifications

### `/harness-plan <brief>`

**Argument:** `$ARGUMENTS` — the brief description (1-4 sentences)

**Pre-flight:** None (this is the entry point)

**Prompt structure:**
1. Role: "You are a product architect specializing in developer tools and CLI plugins."
2. Project context: ForgeProof skill description, repo layout, tech constraints (Python 3.11+ stdlib only)
3. Instructions: Read CLAUDE.md, explore current codebase structure, then produce spec.md
4. Spec format: Overview, Feature List, Technical Approach, Data Model, Definition of Done
5. Rules: Focus on deliverables and high-level technical strategy. Do NOT specify granular implementation steps — those cascade errors downstream. Stdlib only. Respect existing code. Identify AI-powered feature opportunities. Every acceptance criterion must be testable.
6. Exit: "Review spec.md. When ready, start a new conversation and run `/harness-generate`"

**Output artifact:** `spec.md` in project root

### `/harness-generate`

**Arguments:** None

**Pre-flight:** Verify `spec.md` exists. If not, tell user to run `/harness-plan` first.

**Prompt structure:**
1. Role: "You are a senior Python engineer implementing a Claude Code skill."
2. Project context: Embed this corrected repo layout tree:
   ```
   FORGEPROOF_SKILL2/
   ├── commands/               # Claude Code command prompts (.md)
   ├── lib/                    # Python helper scripts (stdlib only)
   │   ├── rpb/                # Crypto/signing library (Ed25519, SHA-256, .rpack)
   │   ├── provenance.py       # CLI: builds + signs .rpack bundles
   │   ├── decision_log.py     # CLI: appends hash-chained audit log entries
   │   └── config.py           # Loads .forgeproof.toml with defaults
   ├── harness/                # Agent prompts, criteria, handoff template
   ├── templates/              # PR description template
   ├── install.sh / install.ps1
   ├── spec.md                 # Written by Planner, you implement this
   └── CLAUDE.md               # Project instructions
   ```
3. Tech constraints: Python 3.11+ stdlib only, `from rpb.X import Y` imports, TOML config via tomllib
4. Code style: Type hints, one-line docstrings on public functions, no classes where functions suffice, pathlib, f-strings, no bare except
5. Git discipline: Commit after each feature, conventional prefixes (feat:/fix:/etc.), never commit broken code
6. Sprint contracts: Before starting each major feature, write a sprint contract to `sprint-contract.md` — a list of what you will build and the specific, testable criteria that define success. Each criterion should be concrete enough that an independent Evaluator can verify it.
7. Self-check: Do a quick self-check against the sprint contract before writing the handoff. Fix anything obviously broken. This is not a substitute for independent evaluation — proceed to the Evaluator regardless of what you find.
8. Instructions: Read spec.md, implement in order, test as you go, commit after each feature
9. Handoff: After each major feature, write/update `harness/handoff.md` using the template from `harness/handoff-template.md`
10. Context anxiety: If you notice yourself rushing to finish or cutting scope, stop. Write a handoff artifact and tell the user to start a new conversation and re-run `/harness-generate`.
11. Anti-rules: Do NOT modify files outside this repo. Do NOT add pip dependencies. Do NOT wrap up early. Do NOT simplify the spec to fit within a session.
12. Exit: "Start a new conversation and run `/harness-evaluate`"

**Output artifacts:** Implementation code + `sprint-contract.md` + `harness/handoff.md`

### `/harness-evaluate`

**Arguments:** None

**Pre-flight:** Verify `spec.md` and `harness/handoff.md` exist.

**Prompt structure:**
1. Role: "You are a skeptical QA engineer. Your job is to find problems, not praise. Default stance: assume it's broken until proven otherwise."
2. Context loading: Read `spec.md`, `sprint-contract.md`, `harness/criteria.md`, `harness/handoff.md`
3. Step 1 — Smoke test:
   - `python -m ruff check lib/`
   - `python -c "import sys; sys.path.insert(0, 'lib'); from rpb.ed25519 import sign, derive_public_key; print('RPB OK')"`
   - `python lib/provenance.py --help`
   - `python lib/decision_log.py --help`
   - Tests: `python -m pytest "c:\Dev\ForgeProof\tests" -q -k "test_skill"` (tests live in parent repo — this is a machine-local path; portability is a known limitation until tests move into this repo)
4. Step 2 — Unit test coverage check
5. Step 3 — Integration tests (decision log hash chain, Ed25519 round-trip, config loading)
6. Step 4 — Command prompt review (read `commands/*.md` — both ForgeProof skill commands and harness commands)
7. Step 5 — Sprint contract verification: test every criterion in `sprint-contract.md`. Do not skip criteria or mark them as passed without direct verification. A contracted item that isn't implemented is a Critical bug.
8. Step 6 — Grade against `harness/criteria.md` using these 5 criteria (scored 1-10):

   | Criterion | Weight | Threshold | What it measures |
   |-----------|--------|-----------|-----------------|
   | Correctness | High | 8/10 | Code does what spec says, tests pass, crypto verifies |
   | Reliability | High | 7/10 | Graceful error handling, no crashes on bad input |
   | Integrity | High | 9/10 | Cryptographic provenance is tamper-evident and trustworthy |
   | Usability | Medium | 7/10 | Developer can install and use without reading source |
   | Code Quality | Medium | 7/10 | Clean, typed, ruff-clean, meaningful tests |

9. Output: Write `harness/eval-report.md` with scores table, PASS/FAIL, and bug reports
10. Anti-patterns: No praise without evidence, no skipping tests, no trusting the handoff, no grading on effort, no softening findings
11. Exit: "If FAIL, run `/harness-fix`. If PASS, you're done." If all criteria pass but there are remaining spec features, return to `/harness-generate`.

**Output artifact:** `harness/eval-report.md`

### `/harness-fix`

**Arguments:** None

**Pre-flight:** Verify `harness/eval-report.md` exists.

**Prompt structure:**
1. Role: Same as Generator
2. Context: Read `spec.md`, `sprint-contract.md`, `harness/eval-report.md`, and source files referenced in bugs
3. Instructions: Fix all bugs listed in eval-report.md, prioritizing Critical → Major → Minor → Nit
4. Git discipline: Same as Generator (commit after each fix)
5. Self-check: Quick sanity check against the sprint contract after fixes. Not a substitute for re-evaluation.
6. Output: Update `harness/handoff.md`
7. Exit: "Start a new conversation and run `/harness-evaluate` to re-verify"

**Output artifact:** Updated `harness/handoff.md`

---

## Path Mapping

| Harness reference (old) | This repo (new) |
|---|---|
| `forgeproof-skill/lib/` | `lib/` |
| `forgeproof-skill/lib/rpb/` | `lib/rpb/` |
| `forgeproof-skill/commands/` | `commands/` |
| `Replication-Pack/internal/rpb/` | *(removed — no external source)* |
| `src/forgeproof/` | *(removed — doesn't exist)* |
| `docs/superpowers/specs/...` | External ref: `c:\Dev\ForgeProof\docs\superpowers\specs\` |
| `tests/` | External: `c:\Dev\ForgeProof\tests\test_skill_*.py` |
| `forgeproof-skill/install.sh` | `install.sh` / `install.ps1` |

---

## CLAUDE.md Update

Add the following section:

```markdown
## Harness Commands (Three-Agent Architecture)

- `/harness-plan <brief>` — Planner: converts brief into spec.md
- `/harness-generate` — Generator: implements spec.md, writes sprint-contract.md + harness/handoff.md
- `/harness-evaluate` — Evaluator: tests against sprint contract + criteria, writes harness/eval-report.md
- `/harness-fix` — Generator fix pass: addresses bugs from eval-report.md

**Workflow:** Plan → review spec → Generate (with sprint contracts) → Evaluate → Fix (if needed) → re-Evaluate
**Key rule:** Start a new conversation between phases for clean context.
```

---

## Non-Goals

- **Automatic chaining** — we do NOT auto-run the next phase. User controls sequencing.
- **Playwright/browser testing** — ForgeProof is a CLI skill, not a web app. Evaluator uses CLI commands, pytest, and ruff.
- **Artifact archival** — previous `spec.md` / `eval-report.md` are overwritten on re-run. Archival is a future consideration.

---

## Testing Strategy

- **Manual testing:** Run each command in VS Code and verify output artifacts are created correctly
- **Pre-flight validation:** Each command checks prerequisites and gives clear error if missing
- **Sprint contract verification:** Evaluator tests every contracted criterion
- **Eval report format:** Verify the Evaluator produces parseable reports with scores and bug format

---

## Acceptance Criteria

1. `/harness-plan "test brief"` produces a well-structured `spec.md` with all required sections
2. `/harness-generate` reads `spec.md`, writes `sprint-contract.md` before building, implements code with git commits, and writes `harness/handoff.md`
3. `/harness-evaluate` reads sprint contract, runs smoke tests, grades against 5 domain criteria, writes `harness/eval-report.md`
4. `/harness-fix` reads eval-report bugs and fixes them with commits
5. Each command's pre-flight check rejects missing prerequisites with a helpful message
6. Each command ends with clear next-step instructions including "start a new conversation"
7. All file paths in commands reference this repo's actual layout (`lib/`, `lib/rpb/`, `commands/`)
8. CLAUDE.md documents the harness workflow
9. Generator includes context anxiety detection and handoff instructions
10. Evaluator tests every sprint contract criterion and fails unimplemented items as Critical bugs
