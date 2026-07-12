[CmdletBinding()]
param()

# Human-in-the-loop reproduction loop for Windows PowerShell.
# Copy this file, edit the steps below, and run it.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\hitl-loop.template.ps1
#   pwsh -File .\hitl-loop.template.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Instruction
    )

    Write-Host ""
    Write-Host ">>> $Instruction"
    [void](Read-Host "    Press Enter when done")
}

function Read-Capture {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Question
    )

    Write-Host ""
    Write-Host ">>> $Question"
    return Read-Host "    >"
}

# --- edit below ---------------------------------------------------------

Invoke-Step "Open the app at http://localhost:3000 and sign in."

$Errored = Read-Capture "Click the 'Export' button. Did it throw an error? (y/n)"

$ErrorMessage = Read-Capture "Paste the error message (or 'none'):"

# --- edit above ---------------------------------------------------------

Write-Output ""
Write-Output "--- Captured ---"
Write-Output "ERRORED=$Errored"
Write-Output "ERROR_MSG=$ErrorMessage"
