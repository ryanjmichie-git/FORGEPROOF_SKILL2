# Harness VS Code Adaptation — Design Spec

**Date:** 2026-04-04
**Status:** Approved
**Scope:** Adapt the three-agent harness to work as Claude Code slash commands in VS Code, with paths corrected for the FORGEPROOF_SKILL2 repo layout.

---

## Summary

The existing harness (`harness/`) implements Anthropic's three-agent architecture (Planner → Generator → Evaluator) for long-running autonomous coding sessions. It currently orchestrates via `run.sh` calling `claude` CLI subprocesses, which doesn't work in VS Code. This spec adapts the harness into four Claude Code slash commands that preserve the same file-based handoff pattern and context isolation.

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

**Context isolation:** The user starts a new VS Code conversation between phases. Each command gets a fresh context window — the same clean-slate benefit that `run.sh` achieved by spawning separate `claude` processes.

**File-based communication:** Agents communicate exclusively via files, not inline conversation:
- Planner writes `spec.md`
- Generator writes `harness/handoff.md`
- Evaluator writes `harness/eval-report.md`

### No Changes to Agent Logic

The Planner, Generator, and Evaluator roles are unchanged. Only the invocation mechanism and file paths change.

---

## File Plan

### New Files

| File | Description |
|------|-------------|
| `.claude/commands/harness-plan.md` | Planner slash command — converts brief to spec.md |
| `.claude/commands/harness-generate.md` | Generator slash command — implements spec.md |
| `.claude/commands/harness-evaluate.md` | Evaluator slash command — tests and grades implementation |
| `.claude/commands/harness-fix.md` | Generator fix pass — addresses bugs from eval-report.md |

### Unchanged Files

| File | Reason |
|------|--------|
| `harness/harness-design-action-plan.md` | Source methodology reference — no changes needed |
| `harness/criteria.md` | Grading criteria are domain-correct for this repo |
| `harness/handoff-template.md` | Handoff format is good as-is |
| `harness/planner.md` | Kept as reference doc (canonical version is now the slash command) |
| `harness/generator.md` | Kept as reference doc |
| `harness/evaluator.md` | Kept as reference doc |
| `harness/run.sh` | Kept for reference — no longer primary invocation method |

### Modified Files

| File | Change |
|------|--------|
| `CLAUDE.md` | Add Harness Commands section documenting the workflow |

---

## Command Specifications

### `/harness-plan <brief>`

**Argument:** `$ARGUMENTS` — the brief description (1-4 sentences)

**Pre-flight:** None (this is the entry point)

**Prompt structure:**
1. Role: "You are a product architect specializing in developer tools and CLI plugins."
2. Project context: ForgeProof skill description, repo layout, tech constraints (Python 3.11+ stdlib only)
3. Instructions: Read CLAUDE.md, explore current codebase structure, then produce spec.md
4. Spec format: Summary, User Stories, Technical Architecture, File Plan, API/CLI Surface, Edge Cases, Testing Strategy, Acceptance Criteria
5. Rules: Focus on WHAT/WHY not HOW. Stdlib only. Respect existing code. Every acceptance criterion must be testable.
6. Exit: "Review spec.md. When ready, start a new conversation and run `/harness-generate`"

**Output artifact:** `spec.md` in project root

### `/harness-generate`

**Pre-flight:** Verify `spec.md` exists. If not, tell user to run `/harness-plan` first.

**Prompt structure:**
1. Role: "You are a senior Python engineer implementing a Claude Code skill."
2. Project context: Repo layout with correct paths (`lib/`, `lib/rpb/`, `commands/`, `templates/`)
3. Tech constraints: Python 3.11+ stdlib only, `from rpb.X import Y` imports, TOML config via tomllib
4. Code style: Type hints, one-line docstrings on public functions, no classes where functions suffice, pathlib, f-strings, no bare except
5. Git discipline: Commit after each feature, conventional prefixes (feat:/fix:/etc.), never commit broken code
6. Instructions: Read spec.md, implement in order, test as you go, commit after each feature
7. Handoff: After each major feature, write/update `harness/handoff.md` using the template from `harness/handoff-template.md`
8. Anti-rules: Do NOT modify files outside this repo. Do NOT add pip dependencies. Do NOT self-evaluate. Do NOT wrap up early.
9. Exit: "Start a new conversation and run `/harness-evaluate`"

**Output artifacts:** Implementation code + `harness/handoff.md`

### `/harness-evaluate`

**Pre-flight:** Verify `spec.md` and `harness/handoff.md` exist.

**Prompt structure:**
1. Role: "You are a skeptical QA engineer. Your job is to find problems, not praise. Default stance: assume it's broken until proven otherwise."
2. Context loading: Read `spec.md`, `harness/criteria.md`, `harness/handoff.md`
3. Step 1 — Smoke test:
   - `python -m ruff check lib/`
   - `python -c "import sys; sys.path.insert(0, 'lib'); from rpb.ed25519 import sign, derive_public_key; print('RPB OK')"`
   - `python lib/provenance.py --help`
   - `python lib/decision_log.py --help`
   - Tests: `python -m pytest "c:\Dev\ForgeProof\tests" -q -k "test_skill"` (tests live in parent repo)
4. Step 2 — Unit test coverage check
5. Step 3 — Integration tests (decision log hash chain, Ed25519 round-trip, config loading)
6. Step 4 — Command prompt review (read `commands/*.md`, verify correctness)
7. Step 5 — Grade against `harness/criteria.md` (5 criteria, scored 1-10)
8. Output: Write `harness/eval-report.md` with scores table, PASS/FAIL, and bug reports
9. Anti-patterns: No praise without evidence, no skipping tests, no trusting the handoff, no grading on effort
10. Exit: "If FAIL, run `/harness-fix`. If PASS, you're done."

**Output artifact:** `harness/eval-report.md`

### `/harness-fix`

**Pre-flight:** Verify `harness/eval-report.md` exists.

**Prompt structure:**
1. Role: Same as Generator
2. Context: Read `spec.md`, `harness/eval-report.md`, and source files referenced in bugs
3. Instructions: Fix all bugs listed in eval-report.md, prioritizing Critical → Major → Minor → Nit
4. Git discipline: Same as Generator (commit after each fix)
5. Output: Update `harness/handoff.md`
6. Exit: "Start a new conversation and run `/harness-evaluate` to re-verify"

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
- `/harness-generate` — Generator: implements spec.md, writes harness/handoff.md
- `/harness-evaluate` — Evaluator: tests implementation, writes harness/eval-report.md
- `/harness-fix` — Generator fix pass: addresses bugs from eval-report.md

**Workflow:** Plan → review spec → Generate → Evaluate → Fix (if needed) → re-Evaluate
**Key rule:** Start a new conversation between phases for clean context.
```

---

## Non-Goals

- **Automatic chaining** — we do NOT auto-run the next phase. User controls sequencing.
- **Playwright/browser testing** — ForgeProof is a CLI skill, not a web app. Evaluator uses CLI commands.
- **Sprint contracts** — useful for multi-sprint builds, but overkill for initial deployment. Can add later.
- **Modifying harness/*.md files** — they stay as reference. Slash commands are canonical.

---

## Testing Strategy

- **Manual testing:** Run each command in VS Code and verify output artifacts are created correctly
- **Pre-flight validation:** Each command checks prerequisites and gives clear error if missing
- **Eval report format:** Verify the Evaluator produces parseable reports with scores and bug format

---

## Acceptance Criteria

1. `/harness-plan "test brief"` produces a well-structured `spec.md` with all required sections
2. `/harness-generate` reads `spec.md` and implements code with git commits and `harness/handoff.md`
3. `/harness-evaluate` runs smoke tests, grades against criteria, writes `harness/eval-report.md`
4. `/harness-fix` reads eval-report bugs and fixes them with commits
5. Each command's pre-flight check rejects missing prerequisites with a helpful message
6. Each command ends with clear next-step instructions
7. All file paths in commands reference this repo's actual layout (`lib/`, `lib/rpb/`, `commands/`)
8. CLAUDE.md documents the harness workflow
