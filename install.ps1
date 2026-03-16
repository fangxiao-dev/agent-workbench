#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$WorkbenchDir = $PSScriptRoot
$KnownHosts = @{
    claude = Join-Path $env:USERPROFILE ".claude"
    codex = Join-Path $env:USERPROFILE ".codex"
}

$Target = $null
$RequestedHosts = @()

foreach ($arg in $args) {
    if ($KnownHosts.ContainsKey($arg)) {
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
    foreach ($hostName in $KnownHosts.Keys) {
        $hostRoot = $KnownHosts[$hostName]
        if (Test-Path $hostRoot) {
            $RequestedHosts += $hostName
        }
    }
}

$InstalledCount = 0
$SkippedCount = 0
$ConflictCount = 0
$HostsProcessed = 0

function Write-ItemStatus {
    param(
        [string]$Level,
        [string]$Message
    )

    Write-Host "  [$Level] $Message"
}

function Install-Link {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label,
        [string]$LinkType = "SymbolicLink"
    )

    if (Test-Path $Destination) {
        $item = Get-Item -LiteralPath $Destination -Force
        $linkType = $item.LinkType
        $targetValue = $null
        if ($item.PSObject.Properties.Name -contains "Target") {
            $targetValue = $item.Target
        }

        if ((($linkType -eq "SymbolicLink") -or ($linkType -eq "Junction")) -and $targetValue) {
            if ($targetValue -is [System.Array]) {
                $targetValue = $targetValue[0]
            }

            if ($targetValue -eq $Source) {
                Write-ItemStatus -Level "*" -Message "$Label -> already linked, skipped"
                $script:SkippedCount++
                return
            }
        }

        Write-ItemStatus -Level "WARN" -Message "$Label -> conflict, skipped ($Destination already exists)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    New-Item -ItemType $LinkType -Path $Destination -Target $Source | Out-Null
    Write-ItemStatus -Level "OK" -Message "$Label -> installed"
    $script:InstalledCount++
}

function Install-FileCopy {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Label
    )

    if (Test-Path $Destination) {
        $destinationHash = (Get-FileHash -LiteralPath $Destination).Hash
        $sourceHash = (Get-FileHash -LiteralPath $Source).Hash
        if ($destinationHash -eq $sourceHash) {
            Write-ItemStatus -Level "*" -Message "$Label -> already copied, skipped"
            $script:SkippedCount++
            return
        }

        Write-ItemStatus -Level "WARN" -Message "$Label -> conflict, skipped ($Destination already exists)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    Copy-Item -LiteralPath $Source -Destination $Destination
    Write-ItemStatus -Level "OK" -Message "$Label -> installed"
    $script:InstalledCount++
}

function Install-Collection {
    param(
        [string]$HostRoot,
        [string]$ChildName,
        [string]$SourcePath,
        [string]$ItemKind,
        [string]$InstallMode
    )

    $destinationDir = Join-Path $HostRoot $ChildName
    New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null
    Write-Host "${ChildName}:"

    $items = Get-ChildItem -Path $SourcePath -ErrorAction SilentlyContinue
    if (-not $items) {
        Write-ItemStatus -Level "*" -Message "no entries"
        return
    }

    foreach ($item in $items) {
        if (($ItemKind -eq "Directory") -and (-not $item.PSIsContainer)) {
            continue
        }
        if (($ItemKind -eq "File") -and $item.PSIsContainer) {
            continue
        }

        $destination = Join-Path $destinationDir $item.Name
        if ($InstallMode -eq "Copy") {
            Install-FileCopy -Source $item.FullName -Destination $destination -Label $item.Name
        }
        else {
            Install-Link -Source $item.FullName -Destination $destination -Label $item.Name -LinkType $InstallMode
        }
    }
}

Write-Host "[INFO] Workbench: $WorkbenchDir"
Write-Host "[INFO] Target project: $Target"
Write-Host ""

if (-not $RequestedHosts) {
    Write-Host "[WARN] No known host directories detected. Skipping host installation."
}
else {
    foreach ($hostName in $RequestedHosts) {
        $hostRoot = $KnownHosts[$hostName]
        $HostsProcessed++
        Write-Host "Host: $hostName"
        Write-Host "Root: $hostRoot"
        Install-Collection -HostRoot $hostRoot -ChildName "skills" -SourcePath (Join-Path $WorkbenchDir "skills") -ItemKind "Directory" -InstallMode "Junction"
        Install-Collection -HostRoot $hostRoot -ChildName "agents" -SourcePath (Join-Path $WorkbenchDir "agents") -ItemKind "Directory" -InstallMode "Junction"
        Install-Collection -HostRoot $hostRoot -ChildName "commands" -SourcePath (Join-Path $WorkbenchDir "commands") -ItemKind "File" -InstallMode "Copy"
        Write-Host ""
    }
}

$gitignore = Join-Path $Target ".gitignore"
if (-not (Test-Path $gitignore)) {
    New-Item -ItemType File -Force -Path $gitignore | Out-Null
}
$content = Get-Content $gitignore -Raw -ErrorAction SilentlyContinue
if (-not ($content | Select-String -Pattern "\.claude/settings\.local\.json" -Quiet)) {
    Add-Content -Path $gitignore -Value ".claude/settings.local.json"
    Write-Host "[OK] .gitignore updated"
}
else {
    Write-Host "[*] .gitignore already contains .claude/settings.local.json"
}

Write-Host ""
Write-Host "Summary:"
Write-Host "Hosts processed: $HostsProcessed"
Write-Host "Installed: $InstalledCount"
Write-Host "Skipped: $SkippedCount"
Write-Host "Conflicts: $ConflictCount"
