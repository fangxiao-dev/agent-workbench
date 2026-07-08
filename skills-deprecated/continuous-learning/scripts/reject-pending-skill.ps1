#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$ConfigFile = Join-Path (Split-Path -Parent $ScriptDir) "config.json"

$argsList = @("$ScriptDir\pending_manager.py", "--config", $ConfigFile, "reject")
if ($args.Count -gt 0 -and $args[0]) {
    $argsList += @("--proposal", $args[0])
}

python @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
