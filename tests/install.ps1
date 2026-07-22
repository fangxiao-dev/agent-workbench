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
    New-Item -ItemType Directory -Path $workbench | Out-Null

    $directoriesToCopy = @("agents", "commands", "docs", "registry", "scripts", "templates", "tests")
    foreach ($directory in $directoriesToCopy) {
        $source = Join-Path $RepoRoot $directory
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $workbench $directory) -Recurse
        }
    }

    $sourceSkills = Join-Path $RepoRoot "skills"
    $targetSkills = Join-Path $workbench "skills"
    New-Item -ItemType Directory -Path $targetSkills | Out-Null
    Get-ChildItem -LiteralPath $sourceSkills -Force | Where-Object {
        -not ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
    } | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $targetSkills $_.Name) -Recurse
    }

    $filesToCopy = @(".gitignore", "AGENTS.md", "install.ps1", "install.sh", "README.md", "pyproject.toml", "uv.lock")
    foreach ($file in $filesToCopy) {
        $source = Join-Path $RepoRoot $file
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $workbench $file)
        }
    }

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
        $claudeBundledSkill = Join-Path $workspace.Home ".claude\skills\feishu-skills\feishu-base\SKILL.md"
        $claudeGstackSkill = Join-Path $workspace.Home ".claude\skills\gstack\office-hours\SKILL.md"
        $codexSkill = Join-Path $workspace.Home ".codex\skills\api-integration-builder"
        $claudeCommand = Join-Path $workspace.Home ".claude\commands\audit.md"

        Assert-True (Test-Path $claudeSkill) "Claude skill link was not created."
        Assert-True (Test-Path $claudeBundledSkill) "Claude bundled Feishu skill was not exposed."
        Assert-True (Test-Path $claudeGstackSkill) "Claude bundled gstack skill was not exposed."
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
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".gemini") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @()
        $output = $result.Output

        $claudeSkill = Join-Path $workspace.Home ".claude\skills\api-integration-builder"
        $codexSkill = Join-Path $workspace.Home ".codex\skills\api-integration-builder"
        $geminiSkill = Join-Path $workspace.Home ".gemini\skills\api-integration-builder"

        Assert-True (Test-Path $claudeSkill) "Claude auto-discovery install failed."
        Assert-True (Test-Path $codexSkill) "Codex auto-discovery install failed."
        Assert-True (Test-Path $geminiSkill) "Gemini auto-discovery install failed."
        Assert-Contains $output "Hosts processed: 3" "Expected three processed hosts."
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
        $claudeHome = Join-Path $workspace.Home ".claude"
        New-Item -ItemType Directory -Path $claudeHome -Force | Out-Null

        $source = Join-Path $workspace.Workbench "skills"
        $target = Join-Path $claudeHome "skills"
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

function Test-ListVisibleSkillsIncludesBundledSkills {
    $workspace = New-TestWorkspace
    try {
        $script = Join-Path $workspace.Workbench "scripts\list-visible-skills.ps1"
        $skillsRoot = Join-Path $workspace.Workbench "skills"
        $emptyRoot = Join-Path $workspace.Root "empty-skills"
        New-Item -ItemType Directory -Path $emptyRoot | Out-Null

        $output = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $script `
            -ClaudeSkillsRoot $skillsRoot `
            -CodexSkillsRoot $emptyRoot `
            -GeminiSkillsRoot $emptyRoot `
            -CodexSuperpowersRoot $emptyRoot `
            -AgentsSkillsRoot $emptyRoot `
            -Format Json 2>&1 | Out-String
        $report = $output | ConvertFrom-Json
        $claude = $report.Hosts | Where-Object { $_.Host -eq "Claude" } | Select-Object -First 1
        $names = @($claude.MergedSkills | ForEach-Object { $_.Name })

        Assert-True ($names -contains "feishu-shared") "Expected bundled Feishu shared skill to be visible."
        Assert-True ($names -contains "using-feishu") "Expected bundled Feishu router skill to be visible."
        Assert-True ($names -contains "lark-intl-shared") "Expected bundled Lark shared skill to remain visible."
        Assert-True ($names -contains "using-azure") "Expected bundled Azure router skill to be visible."
        Assert-True ($names -contains "azure-container-apps") "Expected bundled Azure Container Apps skill to be visible."
        Assert-True ($names -contains "office-hours") "Expected bundled gstack office-hours skill to be visible."
        Assert-True ($names -contains "impl-package") "Expected Impl-Package entry skill to be visible."
        Assert-True ($names -contains "backfill-stable-docs") "Expected nested Impl-Package backfill skill to be visible."
        Assert-True (-not ($names -contains "feishu-skills")) "Bundle root without SKILL.md should not be listed as a skill."
        $feishuShared = $claude.MergedSkills | Where-Object { $_.Name -eq "feishu-shared" } | Select-Object -First 1
        Assert-True ($feishuShared.Sources[0].RelativePath -eq "feishu-skills/feishu-shared") "Expected bundled Feishu shared skill relative path."
        $azureContainerApps = $claude.MergedSkills | Where-Object { $_.Name -eq "azure-container-apps" } | Select-Object -First 1
        Assert-True ($azureContainerApps.Sources[0].RelativePath -eq "azure-skills/azure-container-apps") "Expected bundled Azure Container Apps skill relative path."
        $gstackOfficeHours = $claude.MergedSkills | Where-Object { $_.Name -eq "office-hours" } | Select-Object -First 1
        Assert-True ($gstackOfficeHours.Sources[0].RelativePath -eq "gstack/office-hours") "Expected bundled gstack office-hours skill relative path."
        $backfillSkill = $claude.MergedSkills | Where-Object { $_.Name -eq "backfill-stable-docs" } | Select-Object -First 1
        Assert-True ($backfillSkill.Sources[0].RelativePath -eq "impl-package/backfill-stable-docs") "Expected Impl-Package backfill skill relative path."
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
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".gemini") | Out-Null

        $result = Invoke-InstallSh -Workspace $workspace -Arguments @()
        $output = $result.Output
        $claudeBundledSkill = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\feishu-skills\feishu-base\SKILL.md")
        $claudeAzureRouter = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\azure-skills\using-azure\SKILL.md")
        $claudeAzureContainerApps = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\azure-skills\azure-container-apps\SKILL.md")
        $claudeGstackSkill = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\gstack\office-hours\SKILL.md")
        $flatFeishuSkill = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\feishu-base")
        $listScript = Convert-ToBashPath (Join-Path $workspace.Workbench "scripts\list-visible-skills.sh")
        $claudeSkillsRoot = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills")

        Assert-Contains $output "Hosts processed: 3" "Expected three processed hosts for bash installer."
        & $bash.Source -lc "test -f '$claudeBundledSkill'"
        Assert-True ($LASTEXITCODE -eq 0) "Bash installer should expose bundled Feishu skill through bundle link."
        & $bash.Source -lc "test -f '$claudeAzureRouter' && test -f '$claudeAzureContainerApps'"
        Assert-True ($LASTEXITCODE -eq 0) "Bash installer should expose bundled Azure skills through bundle link."
        & $bash.Source -lc "test -f '$claudeGstackSkill'"
        Assert-True ($LASTEXITCODE -eq 0) "Bash installer should expose bundled gstack skill through bundle link."
        & $bash.Source -lc "test ! -e '$flatFeishuSkill'"
        Assert-True ($LASTEXITCODE -eq 0) "Bash installer should not create flat bundled skill links."
        $visibleSkills = & $bash.Source -lc "bash '$listScript' '$claudeSkillsRoot'" 2>&1 | Out-String
        Assert-Contains $visibleSkills "using-azure -> azure-skills/using-azure" "Bash visible-skills script should list Azure router skill."
        Assert-Contains $visibleSkills "azure-container-apps -> azure-skills/azure-container-apps" "Bash visible-skills script should list Azure Container Apps skill."
        Assert-Contains $visibleSkills "office-hours -> gstack/office-hours" "Bash visible-skills script should list bundled gstack office-hours skill."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellExplicitGeminiInstall {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping gemini explicit install test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".gemini") | Out-Null

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("gemini")
        $output = $result.Output

        $geminiSkill = Join-Path $workspace.Home ".gemini\skills\api-integration-builder"
        $claudeSkill = Join-Path $workspace.Home ".claude\skills\api-integration-builder"
        Assert-True (Test-Path $geminiSkill) "Gemini explicit install failed."
        Assert-True (-not (Test-Path $claudeSkill)) "Claude should not be installed when gemini is selected."
        Assert-Contains $output "Host: gemini" "Expected gemini host output."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

$tests = @(
    @{ Name = "ps1 explicit host install"; Action = { Test-PowerShellExplicitHostInstall } }
    @{ Name = "ps1 explicit gemini install"; Action = { Test-PowerShellExplicitGeminiInstall } }
    @{ Name = "ps1 auto-discovers hosts"; Action = { Test-PowerShellAutoDiscoversHosts } }
    @{ Name = "ps1 skips conflicts"; Action = { Test-PowerShellSkipsConflicts } }
    @{ Name = "ps1 skips existing links"; Action = { Test-PowerShellSkipsExistingLinks } }
    @{ Name = "ps1 project gitignore init"; Action = { Test-PowerShellProjectGitignoreInitializationStillWorks } }
    @{ Name = "ps1 commands are copied"; Action = { Test-PowerShellCommandsAreCopied } }
    @{ Name = "list-visible includes bundled skills"; Action = { Test-ListVisibleSkillsIncludesBundledSkills } }
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
