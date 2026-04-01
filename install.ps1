# ForgeProof Skill Installer (Windows / PowerShell)
# Run from your project root: & "$env:USERPROFILE\forgeproof-skill\install.ps1"
#
# Requirements: PowerShell 5.1+, Python 3.11+, gh CLI authenticated.

$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "Installing ForgeProof skill..."

# 1. Copy commands
$CommandsDest = Join-Path $PWD ".claude\commands"
New-Item -ItemType Directory -Force -Path $CommandsDest | Out-Null
Copy-Item -Path (Join-Path $ScriptDir "commands\*.md") -Destination $CommandsDest -Force
Write-Host "  Copied commands to .claude\commands\"

# 2. Copy lib
$LibDest = Join-Path $PWD ".forgeproof\lib"
New-Item -ItemType Directory -Force -Path $LibDest | Out-Null
Copy-Item -Path (Join-Path $ScriptDir "lib\*") -Destination $LibDest -Recurse -Force
Write-Host "  Copied lib to .forgeproof\lib\"

# 3. Update .gitignore
$GitIgnore = Join-Path $PWD ".gitignore"
if (-not (Test-Path $GitIgnore)) { New-Item -ItemType File -Path $GitIgnore | Out-Null }

$Entries = @(
    ".forgeproof/lib/",
    ".forgeproof/ephemeral.*",
    ".forgeproof/last-run.json",
    ".forgeproof/decision-log.jsonl"
)

$Existing = Get-Content $GitIgnore -ErrorAction SilentlyContinue
foreach ($Entry in $Entries) {
    if ($Existing -notcontains $Entry) {
        Add-Content -Path $GitIgnore -Value $Entry
    }
}
Write-Host "  Updated .gitignore"

Write-Host ""
Write-Host "ForgeProof installed! Available commands:"
Write-Host "  /forgeproof <issue-number>  - Generate code from a GitHub issue"
Write-Host "  /forgeproof-push            - Create a PR with provenance"
Write-Host "  /forgeproof-verify <path>   - Verify an .rpack bundle"
