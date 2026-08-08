#Requires -Version 5.1
# Compatibility entry for AGENTS.md: run link_skill tests.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $RepoRoot
python -m pytest tests/test_link_skill.py -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "[OK] link_skill tests passed"
