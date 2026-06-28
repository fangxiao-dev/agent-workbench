<#
"""
Sync shared config files from current worktree to other worktrees.
Supports dry-run by default and apply mode via -Apply.
"""
#>

[CmdletBinding()]
param(
    [switch]$Apply,
    [string[]]$Exclude = @()
)

$ErrorActionPreference = "Stop"

$syncItems = @(
    ".agents/",
    ".claude/rules/",
    ".claude/skills/",
    ".env",
    ".env.docker",
    "frontend/.env.local"
)

$src = (git rev-parse --show-toplevel).Trim()
if ([string]::IsNullOrWhiteSpace($src)) {
    throw "Cannot resolve git repo root."
}

Write-Host "Source: $src"
Write-Host ("Mode:   " + ($(if ($Apply) { "APPLY" } else { "DRY-RUN (use -Apply to execute)" })))
Write-Host ""

$worktreeLines = git worktree list --porcelain | Where-Object { $_ -like "worktree *" }
$targets = @()
foreach ($line in $worktreeLines) {
    $wt = $line.Substring("worktree ".Length).Trim()
    if ($wt -eq $src) { continue }
    $base = Split-Path $wt -Leaf
    if ($Exclude -contains $base) {
        Write-Host "  SKIP: $wt (excluded)"
        continue
    }
    $targets += $wt
}

if ($targets.Count -eq 0) {
    Write-Host "No target worktrees found."
    exit 0
}

Write-Host "Targets:"
foreach ($t in $targets) {
    Write-Host "  $t"
}
Write-Host ""

$changed = 0
foreach ($target in $targets) {
    Write-Host ("-- Syncing to: " + (Split-Path $target -Leaf) + " --")
    foreach ($item in $syncItems) {
        $normalized = $item.TrimEnd("/")
        $srcFull = Join-Path $src $normalized
        $dstFull = Join-Path $target $normalized
        if (-not (Test-Path $srcFull)) {
            Write-Host "  SKIP: $item (not found in source)"
            continue
        }

        $isDir = (Get-Item $srcFull).PSIsContainer
        if (-not $Apply) {
            if ($isDir) {
                Write-Host "  [dry-run] copy dir $srcFull -> $dstFull"
            } else {
                Write-Host "  [dry-run] copy file $srcFull -> $dstFull"
            }
            $changed++
            continue
        }

        if ($isDir) {
            New-Item -ItemType Directory -Path $dstFull -Force | Out-Null
            Copy-Item -Path (Join-Path $srcFull "*") -Destination $dstFull -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "  COPIED dir: $srcFull -> $dstFull"
        } else {
            New-Item -ItemType Directory -Path (Split-Path $dstFull -Parent) -Force | Out-Null
            Copy-Item -Path $srcFull -Destination $dstFull -Force
            Write-Host "  COPIED file: $srcFull -> $dstFull"
        }
        $changed++
    }
    Write-Host ""
}

if (-not $Apply) {
    Write-Host "Dry-run complete. $changed item(s) would be synced."
    Write-Host "Run with -Apply to execute."
} else {
    Write-Host "Done. $changed item(s) synced."
}
