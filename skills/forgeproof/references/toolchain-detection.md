# Toolchain Detection

ForgeProof auto-detects the project's language and toolchain by scanning for configuration files at the project root.

## Supported Languages

### Python
- **Config files**: `pyproject.toml`, `setup.cfg`, `setup.py`, `requirements.txt`
- **Test runners** (checked in order): pytest
- **Linters** (checked in order): ruff, flake8
- **Runtime check**: `python --version` (falls back to `python3 --version`)

### TypeScript / JavaScript
- **Config files**: `package.json`
- **Test runners** (checked in order): jest, vitest, mocha
- **Linters** (checked in order): eslint
- **Runtime check**: `which node`

### Go
- **Config files**: `go.mod`
- **Test runners**: go test
- **Linters** (checked in order): golangci-lint
- **Runtime check**: `which go`

## Detection Logic

The `forgeproof.py detect` command:
1. Scans the project root for config files from each language
2. For each detected language, checks if the runtime is available
3. For each detected language, finds the first available test runner and linter
4. Outputs JSON with the detection results

Multi-language projects (e.g., a repo with both `pyproject.toml` and `package.json`) will detect all languages. The skill should run tests and linting for all detected languages.

## Fallback

If no language is detected, the skill asks the user to manually specify:
- The command to run tests
- The command to run the linter

These commands are used directly in Phase 3 (Evaluate).
