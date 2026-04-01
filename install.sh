#!/bin/bash
# ForgeProof Skill Installer
# Run from your project root: ~/forgeproof-skill/install.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing ForgeProof skill..."

# 1. Copy commands
mkdir -p .claude/commands
cp "$SCRIPT_DIR/commands/"*.md .claude/commands/
echo "  Copied commands to .claude/commands/"

# 2. Copy lib
mkdir -p .forgeproof/lib
cp -r "$SCRIPT_DIR/lib/"* .forgeproof/lib/
echo "  Copied lib to .forgeproof/lib/"

# 3. Update .gitignore
GITIGNORE=".gitignore"
ENTRIES=(".forgeproof/lib/" ".forgeproof/ephemeral.*" ".forgeproof/last-run.json" ".forgeproof/decision-log.jsonl")
touch "$GITIGNORE"
for entry in "${ENTRIES[@]}"; do
    if ! grep -qxF "$entry" "$GITIGNORE"; then
        echo "$entry" >> "$GITIGNORE"
    fi
done
echo "  Updated .gitignore"

echo ""
echo "ForgeProof installed! Available commands:"
echo "  /forgeproof <issue-number>  - Generate code from a GitHub issue"
echo "  /forgeproof-push            - Create a PR with provenance"
echo "  /forgeproof-verify <path>   - Verify an .rpack bundle"
