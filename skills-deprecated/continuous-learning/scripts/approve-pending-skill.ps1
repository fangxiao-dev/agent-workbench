#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$SkillDir = Split-Path -Parent $ScriptDir
$RepoRoot = Split-Path -Parent (Split-Path -Parent $SkillDir)
$ConfigFile = Join-Path $SkillDir "config.json"
$InstallScript = Join-Path $RepoRoot "install.ps1"

$argsList = @("$ScriptDir\pending_manager.py", "--config", $ConfigFile, "approve")
if ($args.Count -gt 0 -and $args[0]) {
    $argsList += @("--proposal", $args[0])
}
if ($args.Count -gt 1 -and $args[1]) {
    $argsList += @("--skill-name", $args[1])
}

python @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

powershell -ExecutionPolicy Bypass -File $InstallScript
