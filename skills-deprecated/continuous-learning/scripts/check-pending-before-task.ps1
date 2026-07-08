#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot
$ConfigFile = Join-Path (Split-Path -Parent $ScriptDir) "config.json"
python "$ScriptDir\pending_manager.py" --config $ConfigFile state
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
