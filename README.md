# ForgeProof Skill

A Claude Code skill that converts GitHub issues into working code with cryptographically signed provenance bundles (.rpack).

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and authenticated
- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated
- Python 3.11+

## Installation

```bash
git clone https://github.com/ryanjmichie-git/forgeproof-skill ~/forgeproof-skill
cd your-project
~/forgeproof-skill/install.sh
```

## Usage

### Generate code from a GitHub issue

```
/forgeproof 42
```

Reads issue #42, generates implementation + tests, runs evaluation, and creates a signed `.rpack` provenance bundle. All changes are local — review before committing.

### Create a PR with provenance

```
/forgeproof-push
```

Creates a branch, commits changes + `.rpack` bundle, pushes, and opens a PR.

### Verify a provenance bundle

```
/forgeproof-verify .forgeproof/issue-42.rpack
```

Extracts and verifies the `.rpack` bundle's Ed25519 signatures and SHA-256 hash chain.

## Configuration

Optional. Create `.forgeproof.toml` in your project root:

```toml
[paths]
allowed = ["src/**/*", "tests/**/*"]
denied = [".env", "**/*.key"]

[[evaluation.commands]]
name = "tests"
run = "pytest -q"
required = true

[signing]
ephemeral = true
```

If no config exists, sensible defaults are used.
