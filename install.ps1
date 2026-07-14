#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$WorkbenchDir = $PSScriptRoot
$KnownHosts = @{
    claude = Join-Path $env:USERPROFILE ".claude"
    codex = Join-Path $env:USERPROFILE ".codex"
    gemini = Join-Path $env:USERPROFILE ".gemini"
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

    if ($LinkType -eq "Copy") {
        if (Test-Path $Destination) {
            $dstItem = Get-Item -LiteralPath $Destination -Force
            if ($dstItem.PSIsContainer) {
                Write-ItemStatus -Level "WARN" -Message "$Label -> conflict, skipped ($Destination already exists as directory)"
                $script:SkippedCount++
                $script:ConflictCount++
                return
            }

            $same = $false
            try {
                $same = ((Get-FileHash -Algorithm SHA256 -LiteralPath $Source).Hash -eq (Get-FileHash -Algorithm SHA256 -LiteralPath $Destination).Hash)
            }
            catch {
                $same = $false
            }

            if ($same) {
                Write-ItemStatus -Level "*" -Message "$Label -> already copied, skipped"
                $script:SkippedCount++
                return
            }

            Write-ItemStatus -Level "WARN" -Message "$Label -> conflict, skipped ($Destination already exists with different content)"
            $script:SkippedCount++
            $script:ConflictCount++
            return
        }

        Copy-Item -LiteralPath $Source -Destination $Destination -Force
        Write-ItemStatus -Level "OK" -Message "$Label -> installed"
        $script:InstalledCount++
        return
    }

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

    try {
        New-Item -ItemType $LinkType -Path $Destination -Target $Source | Out-Null
        Write-ItemStatus -Level "OK" -Message "$Label -> installed"
        $script:InstalledCount++
        return
    }
    catch {
        $sourceItem = Get-Item -LiteralPath $Source -Force
        if (($LinkType -eq "SymbolicLink") -and (-not $sourceItem.PSIsContainer)) {
            try {
                New-Item -ItemType HardLink -Path $Destination -Target $Source | Out-Null
                Write-ItemStatus -Level "OK" -Message "$Label -> installed (hardlink fallback)"
                $script:InstalledCount++
                return
            }
            catch {
                Copy-Item -LiteralPath $Source -Destination $Destination -Force
                Write-ItemStatus -Level "OK" -Message "$Label -> installed (copy fallback)"
                $script:InstalledCount++
                return
            }
        }
        throw
    }
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
        Install-Link -Source $item.FullName -Destination $destination -Label $item.Name -LinkType $InstallMode
    }
}

function Remove-ManagedLegacyCodexBackfillLink {
    param(
        [string]$HostRoot
    )

    $skillsRoot = Join-Path $HostRoot "skills"
    $legacySource = Join-Path $WorkbenchDir "skills\backfill-stable-docs"
    $legacyDestination = Join-Path $skillsRoot "backfill-stable-docs"
    $skillsItem = Get-Item -LiteralPath $skillsRoot -Force -ErrorAction SilentlyContinue

    if ($skillsItem -and $skillsItem.LinkType -and $skillsItem.Target) {
        $skillsTarget = $skillsItem.Target
        if ($skillsTarget -is [System.Array]) {
            $skillsTarget = $skillsTarget[0]
        }
        if ($skillsTarget -eq (Join-Path $WorkbenchDir "skills")) {
            return
        }
    }

    $legacyItem = Get-Item -LiteralPath $legacyDestination -Force -ErrorAction SilentlyContinue
    if (-not $legacyItem) {
        return
    }

    $legacyTarget = $legacyItem.Target
    if ($legacyTarget -is [System.Array]) {
        $legacyTarget = $legacyTarget[0]
    }
    if ($legacyItem.LinkType -and ($legacyTarget -eq $legacySource)) {
        if ($legacyItem.PSIsContainer) {
            [System.IO.Directory]::Delete($legacyDestination, $false)
        }
        else {
            [System.IO.File]::Delete($legacyDestination)
        }
        Write-ItemStatus -Level "OK" -Message "legacy backfill-stable-docs link -> removed"
        $script:InstalledCount++
    }
}

function Get-ComparablePath {
    param(
        [string]$Path
    )

    if (-not $Path) {
        return $null
    }

    $candidate = $Path
    if ($candidate.StartsWith("\\?\")) {
        $candidate = $candidate.Substring(4)
    }

    try {
        $candidate = [System.IO.Path]::GetFullPath($candidate)
    }
    catch {
        return $null
    }

    return $candidate.TrimEnd([char[]]"\/").ToLowerInvariant()
}

function Invoke-CodexCommand {
    param(
        [System.Management.Automation.CommandInfo]$Command,
        [string[]]$Arguments
    )

    $stderrPath = [System.IO.Path]::GetTempFileName()
    $stdout = ""
    $stderr = ""
    $exitCode = 1
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $stdout = & $Command.Source @Arguments 2> $stderrPath | Out-String
        $exitCode = $LASTEXITCODE
        $stderr = Get-Content -LiteralPath $stderrPath -Raw -ErrorAction SilentlyContinue
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
        if (Test-Path -LiteralPath $stderrPath) {
            Remove-Item -LiteralPath $stderrPath -Force
        }
    }

    return @{
        Stdout = $stdout
        Stderr = $stderr
        ExitCode = $exitCode
    }
}

function Install-CodexPlugin {
    param(
        [string]$HostRoot
    )

    Write-Host "plugin:"
    $marketplaceManifest = Join-Path $WorkbenchDir ".agents\plugins\marketplace.json"
    if (-not (Test-Path -LiteralPath $marketplaceManifest)) {
        Write-ItemStatus -Level "WARN" -Message "stable-docs-backfill -> skipped (marketplace manifest is missing)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    $codexCommand = Get-Command codex -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $codexCommand) {
        Write-ItemStatus -Level "WARN" -Message "stable-docs-backfill -> skipped (Codex CLI not found)"
        $script:SkippedCount++
        return
    }

    $marketplaceListResult = Invoke-CodexCommand -Command $codexCommand -Arguments @("plugin", "marketplace", "list", "--json")
    if ($marketplaceListResult.ExitCode -ne 0) {
        $detail = [string]$marketplaceListResult.Stderr
        if (-not $detail) {
            $detail = [string]$marketplaceListResult.Stdout
        }
        $detail = $detail.Trim()
        Write-ItemStatus -Level "WARN" -Message "agent-workbench marketplace -> conflict, skipped (could not inspect marketplaces: $detail)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    $marketplaceListOutput = $marketplaceListResult.Stdout
    try {
        $marketplaceList = $marketplaceListOutput | ConvertFrom-Json
    }
    catch {
        Write-ItemStatus -Level "WARN" -Message "agent-workbench marketplace -> conflict, skipped (Codex CLI returned invalid marketplace JSON)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    $existingMarketplace = @($marketplaceList.marketplaces | Where-Object { $_.name -eq "agent-workbench" }) | Select-Object -First 1
    if ($existingMarketplace) {
        $existingRoot = Get-ComparablePath -Path $existingMarketplace.root
        $workbenchRoot = Get-ComparablePath -Path $WorkbenchDir
        if ((-not $existingRoot) -or ($existingRoot -ne $workbenchRoot)) {
            $configuredRoot = $existingMarketplace.root
            Write-ItemStatus -Level "WARN" -Message "agent-workbench marketplace -> conflict, skipped (already points to $configuredRoot)"
            $script:SkippedCount++
            $script:ConflictCount++
            return
        }

        Write-ItemStatus -Level "*" -Message "agent-workbench marketplace -> already registered"
        $script:SkippedCount++
    }
    else {
        $marketplaceResult = Invoke-CodexCommand -Command $codexCommand -Arguments @("plugin", "marketplace", "add", $WorkbenchDir, "--json")
        if ($marketplaceResult.ExitCode -ne 0) {
            $detail = [string]$marketplaceResult.Stderr
            if (-not $detail) {
                $detail = [string]$marketplaceResult.Stdout
            }
            $detail = $detail.Trim()
            Write-ItemStatus -Level "WARN" -Message "agent-workbench marketplace -> conflict, skipped ($detail)"
            $script:SkippedCount++
            $script:ConflictCount++
            return
        }

        Write-ItemStatus -Level "OK" -Message "agent-workbench marketplace -> registered"
        $script:InstalledCount++
    }

    $pluginResult = Invoke-CodexCommand -Command $codexCommand -Arguments @("plugin", "add", "stable-docs-backfill@agent-workbench", "--json")
    if ($pluginResult.ExitCode -ne 0) {
        $detail = [string]$pluginResult.Stderr
        if (-not $detail) {
            $detail = [string]$pluginResult.Stdout
        }
        $detail = $detail.Trim()
        Write-ItemStatus -Level "WARN" -Message "stable-docs-backfill -> conflict, skipped ($detail)"
        $script:SkippedCount++
        $script:ConflictCount++
        return
    }

    Write-ItemStatus -Level "OK" -Message "stable-docs-backfill -> installed/refreshed"
    $script:InstalledCount++
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
        Install-Link -Source (Join-Path $WorkbenchDir "skills") -Destination (Join-Path $hostRoot "skills") -Label "skills" -LinkType "Junction"
        Install-Collection -HostRoot $hostRoot -ChildName "agents" -SourcePath (Join-Path $WorkbenchDir "agents") -ItemKind "Directory" -InstallMode "Junction"
        Install-Collection -HostRoot $hostRoot -ChildName "commands" -SourcePath (Join-Path $WorkbenchDir "commands") -ItemKind "File" -InstallMode "Copy"
        if ($hostName -eq "codex") {
            Remove-ManagedLegacyCodexBackfillLink -HostRoot $hostRoot
            Install-CodexPlugin -HostRoot $hostRoot
        }
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
