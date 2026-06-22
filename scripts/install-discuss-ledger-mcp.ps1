#Requires -Version 5.1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkbenchDir = Split-Path -Parent $ScriptDir
$ServerPath = Join-Path $WorkbenchDir "skills\discuss-ledger\mcp_server.py"
$KnownHosts = @("claude", "codex")

$Target = $null
$RequestedHosts = @()

foreach ($arg in $args) {
    if ($KnownHosts -contains $arg) {
        $RequestedHosts += $arg
    }
    elseif (-not $Target) {
        $Target = $arg
    }
    else {
        throw "Unknown argument: $arg"
    }
}

if (-not $Target) {
    $Target = (Get-Location).Path
}
$Target = (Resolve-Path $Target).Path

if (-not $RequestedHosts) {
    $RequestedHosts = @("codex", "claude")
}

function Escape-TomlString {
    param([string]$Value)
    return $Value.Replace('\', '\\').Replace('"', '\"')
}

function Install-CodexMcp {
    $codexDir = Join-Path $Target ".codex"
    $configPath = Join-Path $codexDir "config.toml"
    New-Item -ItemType Directory -Force -Path $codexDir | Out-Null

    $server = Escape-TomlString $ServerPath
    $root = Escape-TomlString $Target
    $cwd = Escape-TomlString $WorkbenchDir
    $expected = @"
[mcp_servers.discussLedger]
command = "uv"
args = ["run", "python", "$server", "--root", "$root"]
cwd = "$cwd"
"@

    $content = ""
    if (Test-Path $configPath) {
        $content = Get-Content -LiteralPath $configPath -Raw
    }

    if ($content -match '(?m)^\[mcp_servers\.discussLedger\]') {
        if ($content.Contains($expected)) {
            Write-Host "[*] codex discussLedger MCP already configured, skipped"
            return
        }
        Write-Host "[WARN] codex discussLedger MCP exists with different settings, skipped"
        return
    }

    if ($content -and (-not $content.EndsWith("`n"))) {
        Add-Content -LiteralPath $configPath -Value ""
    }
    Add-Content -LiteralPath $configPath -Value $expected
    Write-Host "[OK] codex discussLedger MCP configured at $configPath"
}

function Write-ClaudeSnippet {
    $snippet = [ordered]@{
        mcpServers = [ordered]@{
            "discuss-ledger" = [ordered]@{
                command = "uv"
                args = @("run", "python", $ServerPath, "--root", $Target)
                cwd = $WorkbenchDir
            }
        }
    }
    Write-Host "[WARN] claude not found on PATH. Add this to project .mcp.json if needed:"
    $snippet | ConvertTo-Json -Depth 10
}

function Install-ClaudeMcp {
    $claude = Get-Command claude -ErrorAction SilentlyContinue
    if (-not $claude) {
        Write-ClaudeSnippet
        return
    }
    Push-Location $Target
    try {
        & claude mcp add --scope project discuss-ledger -- uv run python $ServerPath --root $Target
        if ($LASTEXITCODE -ne 0) {
            throw "claude mcp add failed with exit code $LASTEXITCODE"
        }
        Write-Host "[OK] claude discuss-ledger MCP registered"
    }
    finally {
        Pop-Location
    }
}

foreach ($hostName in $RequestedHosts) {
    if (-not ($KnownHosts -contains $hostName)) {
        throw "Unsupported host: $hostName"
    }
    if ($hostName -eq "codex") {
        Install-CodexMcp
    }
    elseif ($hostName -eq "claude") {
        Install-ClaudeMcp
    }
}
