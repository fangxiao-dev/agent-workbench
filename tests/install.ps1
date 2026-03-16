# Requires PowerShell 5.1+
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
function New-TestWorkspace {
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-workbench-test-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $root | Out-Null

    $project = Join-Path $root "project"
    $testHome = Join-Path $root "home"
    $workbench = Join-Path $root "workbench"

    New-Item -ItemType Directory -Path $project | Out-Null
    New-Item -ItemType Directory -Path $testHome | Out-Null
    Copy-Item -Path $RepoRoot -Destination $workbench -Recurse

    return @{
        Root = $root
        Project = $project
        Home = $testHome
        Workbench = $workbench
    }
}

function Remove-TestWorkspace($workspace) {
    if ($workspace -and (Test-Path $workspace.Root)) {
        Remove-Item -Path $workspace.Root -Recurse -Force
    }
}

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Assert-Contains {
    param(
        [string]$Haystack,
        [string]$Needle,
        [string]$Message
    )

    if (-not $Haystack.Contains($Needle)) {
        throw $Message
    }
}

function Convert-ToBashPath {
    param(
        [string]$WindowsPath
    )

    $normalized = $WindowsPath -replace "\\", "/"
    if ($normalized -match "^([A-Za-z]):/(.*)$") {
        $drive = $matches[1].ToLower()
        $rest = $matches[2]
        return "/mnt/$drive/$rest"
    }

    return $normalized
}

function Invoke-InstallPs1 {
    param(
        [hashtable]$Workspace,
        [string[]]$Arguments,
        [hashtable]$Environment = @{}
    )

    $installScript = Join-Path $Workspace.Workbench "install.ps1"
    $argList = @(
        "-NoProfile"
        "-ExecutionPolicy"
        "Bypass"
        "-File"
        $installScript
        $Workspace.Project
    ) + $Arguments

    $previousUserProfile = $env:USERPROFILE
    $previousValues = @{}
    try {
        $env:USERPROFILE = $Workspace.Home
        foreach ($entry in $Environment.GetEnumerator()) {
            $previousValues[$entry.Key] = [Environment]::GetEnvironmentVariable($entry.Key, "Process")
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
        }
        $output = & powershell.exe @argList 2>&1 | Out-String
        return @{
            Output = $output
            ExitCode = $LASTEXITCODE
        }
    }
    finally {
        $env:USERPROFILE = $previousUserProfile
        foreach ($entry in $Environment.GetEnumerator()) {
            [Environment]::SetEnvironmentVariable($entry.Key, $previousValues[$entry.Key], "Process")
        }
    }
}

function Invoke-InstallSh {
    param(
        [hashtable]$Workspace,
        [string[]]$Arguments,
        [hashtable]$Environment = @{}
    )

    $bash = Get-Command bash -ErrorAction SilentlyContinue
    if (-not $bash) {
        return $null
    }

    $escapedProject = Convert-ToBashPath $Workspace.Project
    $escapedScript = Convert-ToBashPath (Join-Path $Workspace.Workbench "install.sh")
    $escapedHome = Convert-ToBashPath $Workspace.Home
    $argString = ($Arguments | ForEach-Object { "'$_'" }) -join " "
    $envPrefix = "HOME='$escapedHome'"
    foreach ($entry in $Environment.GetEnumerator()) {
        $envPrefix += " $($entry.Key)='$($entry.Value)'"
    }
    $command = "$envPrefix bash '$escapedScript' '$escapedProject' $argString"
    $output = & $bash.Source -lc $command 2>&1 | Out-String
    return @{
        Output = $output
        ExitCode = $LASTEXITCODE
    }
}

function Test-JunctionSupport {
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-workbench-link-test-" + [System.Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $root | Out-Null
    try {
        $source = Join-Path $root "source"
        $link = Join-Path $root "link"
        New-Item -ItemType Directory -Path $source | Out-Null
        New-Item -ItemType Junction -Path $link -Target $source | Out-Null
        return $true
    }
    catch {
        return $false
    }
    finally {
        if (Test-Path $root) {
            Remove-Item -Path $root -Recurse -Force
        }
    }
}

function Test-PowerShellExplicitHostInstall {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping creation test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".claude") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("claude")
        $output = $result.Output

        $claudeSkill = Join-Path $workspace.Home ".claude\skills\api-integration-builder"
        $codexSkill = Join-Path $workspace.Home ".codex\skills\api-integration-builder"
        $claudeCommand = Join-Path $workspace.Home ".claude\commands\audit.md"

        Assert-True (Test-Path $claudeSkill) "Claude skill link was not created."
        Assert-True (-not (Test-Path $codexSkill)) "Codex should not be installed when not selected."
        Assert-True (Test-Path $claudeCommand) "Claude command copy was not created."
        Assert-Contains $output "Host: claude" "Expected claude host output."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellAutoDiscoversHosts {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping creation test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".claude") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".codex") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @()
        $output = $result.Output

        $claudeSkill = Join-Path $workspace.Home ".claude\skills\api-integration-builder"
        $codexSkill = Join-Path $workspace.Home ".codex\skills\api-integration-builder"

        Assert-True (Test-Path $claudeSkill) "Claude auto-discovery install failed."
        Assert-True (Test-Path $codexSkill) "Codex auto-discovery install failed."
        Assert-Contains $output "Hosts processed: 2" "Expected two processed hosts."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellSkipsConflicts {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping conflict test."
            return
        }
        $claudeHome = Join-Path $workspace.Home ".claude"
        $skillDir = Join-Path $claudeHome "skills"
        New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $skillDir "api-integration-builder") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("claude")
        $output = $result.Output

        Assert-Contains $output "conflict, skipped" "Expected conflict skip output."
        $item = Get-Item (Join-Path $skillDir "api-integration-builder")
        Assert-True ($item.PSIsContainer) "Existing conflict directory should remain untouched."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellSkipsExistingLinks {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping existing-link test."
            return
        }
        $claudeSkills = Join-Path $workspace.Home ".claude\skills"
        New-Item -ItemType Directory -Path $claudeSkills -Force | Out-Null

        $source = Join-Path $workspace.Workbench "skills\api-integration-builder"
        $target = Join-Path $claudeSkills "api-integration-builder"
        New-Item -ItemType Junction -Path $target -Target $source | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("claude")
        $output = $result.Output
        Assert-Contains $output "already linked, skipped" "Expected already-linked skip output."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellProjectGitignoreInitializationStillWorks {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping project init integration test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".claude") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("claude")
        $output = $result.Output

        $gitignore = Join-Path $workspace.Project ".gitignore"
        Assert-True (-not (Test-Path (Join-Path $workspace.Project "CLAUDE.md"))) "CLAUDE.md should not be generated by install."
        Assert-True (Test-Path $gitignore) ".gitignore was not created."
        Assert-Contains (Get-Content $gitignore -Raw) ".claude/settings.local.json" "Expected .gitignore patch."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellCommandsAreCopied {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping command copy test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".claude") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("claude")
        $output = $result.Output

        $source = Join-Path $workspace.Workbench "commands\audit.md"
        $target = Join-Path $workspace.Home ".claude\commands\audit.md"
        Assert-True (Test-Path $target) "Expected copied command file."
        Assert-True (-not ((Get-Item -LiteralPath $target -Force).LinkType)) "Command file should be copied, not linked."
        Assert-Contains (Get-Content $target -Raw) (Get-Content $source -Raw) "Copied command content mismatch."
        Assert-Contains $output "audit.md -> installed" "Expected installed status for copied command."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-BashAutoDiscoversHosts {
    $workspace = New-TestWorkspace
    try {
        $bash = Get-Command bash -ErrorAction SilentlyContinue
        if (-not $bash) {
            Write-Host "[SKIP] bash not available; skipping install.sh tests."
            return
        }
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] symbolic links unavailable; skipping bash creation test."
            return
        }

        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".claude") | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".codex") | Out-Null

        $result = Invoke-InstallSh -Workspace $workspace -Arguments @()
        $output = $result.Output
        Assert-Contains $output "Hosts processed: 2" "Expected two processed hosts for bash installer."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

$tests = @(
    @{ Name = "ps1 explicit host install"; Action = { Test-PowerShellExplicitHostInstall } }
    @{ Name = "ps1 auto-discovers hosts"; Action = { Test-PowerShellAutoDiscoversHosts } }
    @{ Name = "ps1 skips conflicts"; Action = { Test-PowerShellSkipsConflicts } }
    @{ Name = "ps1 skips existing links"; Action = { Test-PowerShellSkipsExistingLinks } }
    @{ Name = "ps1 project gitignore init"; Action = { Test-PowerShellProjectGitignoreInitializationStillWorks } }
    @{ Name = "ps1 commands are copied"; Action = { Test-PowerShellCommandsAreCopied } }
    @{ Name = "sh auto-discovers hosts"; Action = { Test-BashAutoDiscoversHosts } }
)

$failures = @()
foreach ($test in $tests) {
    try {
        & $test.Action
        Write-Host "[PASS] $($test.Name)"
    }
    catch {
        $failures += "$($test.Name): $($_.Exception.Message)"
        Write-Host "[FAIL] $($test.Name)"
        Write-Host $_.Exception.Message
    }
}

if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "Failures:"
    $failures | ForEach-Object { Write-Host " - $_" }
    exit 1
}

Write-Host ""
Write-Host "[OK] All installer tests passed."
