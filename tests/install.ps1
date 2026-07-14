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

    $directoriesToCopy = @("agents", "commands", "docs", "plugins", "registry", "scripts", "templates", "tests")
    foreach ($directory in $directoriesToCopy) {
        $source = Join-Path $RepoRoot $directory
        if (Test-Path -LiteralPath $source) {
            Copy-Item -LiteralPath $source -Destination (Join-Path $workbench $directory) -Recurse
        }
    }

    $marketplaceSource = Join-Path $RepoRoot ".agents\plugins\marketplace.json"
    if (Test-Path -LiteralPath $marketplaceSource) {
        $marketplaceTarget = Join-Path $workbench ".agents\plugins"
        New-Item -ItemType Directory -Path $marketplaceTarget -Force | Out-Null
        Copy-Item -LiteralPath $marketplaceSource -Destination (Join-Path $marketplaceTarget "marketplace.json")
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

function New-PowerShellCodexStub {
    param(
        [hashtable]$Workspace
    )

    $bin = Join-Path $Workspace.Root "codex-stub-bin"
    $log = Join-Path $Workspace.Root "codex-stub.log"
    $state = Join-Path $Workspace.Root "codex-stub-marketplace-state"
    New-Item -ItemType Directory -Path $bin | Out-Null
    $stubPath = Join-Path $bin "codex.cmd"
    $stub = @'
@echo off
echo %*>>"%CODEX_STUB_LOG%"
if "%CODEX_STUB_WARNING%"=="1" echo WARNING: proceeding despite a benign Codex warning 1>&2
if "%1 %2 %3"=="plugin marketplace list" (
  if "%CODEX_STUB_MARKETPLACE_CONFLICT%"=="1" (
    echo {"marketplaces":[{"name":"agent-workbench","root":"C:/other/workbench"}]}
    exit /b 0
  )
  if not "%CODEX_STUB_MARKETPLACE_STATE%"=="" if exist "%CODEX_STUB_MARKETPLACE_STATE%" (
    echo {"marketplaces":[{"name":"agent-workbench","root":"%CODEX_STUB_MARKETPLACE_ROOT%"}]}
    exit /b 0
  )
  echo {"marketplaces":[]}
  exit /b 0
)
if "%1 %2 %3"=="plugin marketplace add" (
  if not "%CODEX_STUB_MARKETPLACE_STATE%"=="" type nul > "%CODEX_STUB_MARKETPLACE_STATE%"
  echo {"marketplaceName":"agent-workbench","alreadyAdded":false}
  exit /b 0
)
if "%1 %2"=="plugin add" (
  echo {"pluginId":"stable-docs-backfill@agent-workbench"}
  exit /b 0
)
echo unexpected codex stub arguments: %* 1>&2
exit /b 2
'@
    Set-Content -LiteralPath $stubPath -Value $stub -Encoding ASCII

    return @{
        Bin = $bin
        Log = $log
        State = $state
    }
}

function New-BashCodexStub {
    param(
        [hashtable]$Workspace
    )

    $bash = Get-Command bash -ErrorAction SilentlyContinue
    if (-not $bash) {
        return $null
    }

    $bin = Join-Path $Workspace.Root "bash-codex-stub-bin"
    $log = Join-Path $Workspace.Root "bash-codex-stub.log"
    $state = Join-Path $Workspace.Root "bash-codex-stub-marketplace-state"
    New-Item -ItemType Directory -Path $bin | Out-Null
    $stubPath = Join-Path $bin "codex"
    $stub = @'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$CODEX_STUB_LOG"
if [ "${CODEX_STUB_WARNING:-}" = "1" ]; then
  printf '%s\n' "WARNING: proceeding despite a benign Codex warning" >&2
fi
if [ "$1 $2 $3" = "plugin marketplace list" ]; then
  if [ "${CODEX_STUB_MARKETPLACE_CONFLICT:-}" = "1" ]; then
    printf '%s\n' '{"marketplaces":[{"name":"agent-workbench","root":"/other/workbench"}]}'
    exit 0
  fi
  if [ -n "${CODEX_STUB_MARKETPLACE_STATE:-}" ] && [ -f "$CODEX_STUB_MARKETPLACE_STATE" ]; then
    printf '%s\n' "{\"marketplaces\":[{\"name\":\"agent-workbench\",\"root\":\"$CODEX_STUB_MARKETPLACE_ROOT\"}]}"
    exit 0
  fi
  printf '%s\n' '{"marketplaces":[]}'
  exit 0
fi
if [ "$1 $2 $3" = "plugin marketplace add" ]; then
  if [ -n "${CODEX_STUB_MARKETPLACE_STATE:-}" ]; then
    : > "$CODEX_STUB_MARKETPLACE_STATE"
  fi
  printf '%s\n' '{"marketplaceName":"agent-workbench","alreadyAdded":false}'
  exit 0
fi
if [ "$1 $2" = "plugin add" ]; then
  printf '%s\n' '{"pluginId":"stable-docs-backfill@agent-workbench"}'
  exit 0
fi
printf '%s\n' "unexpected codex stub arguments: $*" >&2
exit 2
'@
    [System.IO.File]::WriteAllText($stubPath, ($stub -replace "`r`n", "`n"), [System.Text.UTF8Encoding]::new($false))
    $bashStubPath = Convert-ToBashPath $stubPath
    & $bash.Source -lc "chmod +x '$bashStubPath'"
    Assert-True ($LASTEXITCODE -eq 0) "Could not make the bash Codex stub executable."

    return @{
        Bin = $bin
        Log = $log
        State = $state
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
        $claudeGstackSkill = Join-Path $workspace.Home ".claude\skills\gstack\plan-eng-review\SKILL.md"
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

        $stub = New-PowerShellCodexStub -Workspace $workspace
        $environment = @{
            PATH = $stub.Bin + ";" + $env:PATH
            CODEX_STUB_LOG = $stub.Log
            CODEX_STUB_MARKETPLACE_STATE = $stub.State
            CODEX_STUB_MARKETPLACE_ROOT = $workspace.Workbench.Replace("\", "/")
            CODEX_STUB_WARNING = "1"
        }
        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @() -Environment $environment
        $output = $result.Output

        $claudeSkill = Join-Path $workspace.Home ".claude\skills\api-integration-builder"
        $codexSkill = Join-Path $workspace.Home ".codex\skills\api-integration-builder"
        $geminiSkill = Join-Path $workspace.Home ".gemini\skills\api-integration-builder"

        Assert-True (Test-Path $claudeSkill) "Claude auto-discovery install failed."
        Assert-True (Test-Path $codexSkill) "Codex auto-discovery install failed."
        Assert-True (Test-Path $geminiSkill) "Gemini auto-discovery install failed."
        Assert-Contains $output "Hosts processed: 3" "Expected three processed hosts."
        Assert-Contains $output "stable-docs-backfill -> installed/refreshed" "Expected Codex plugin installation during auto-discovery."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellCodexPluginInstallAndRefresh {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping Codex plugin test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".codex") | Out-Null
        $stub = New-PowerShellCodexStub -Workspace $workspace
        $environment = @{
            PATH = $stub.Bin + ";" + $env:PATH
            CODEX_STUB_LOG = $stub.Log
            CODEX_STUB_MARKETPLACE_STATE = $stub.State
            CODEX_STUB_MARKETPLACE_ROOT = $workspace.Workbench.Replace("\", "/")
            CODEX_STUB_WARNING = "1"
        }

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("codex") -Environment $environment
        $output = $result.Output
        $log = Get-Content -LiteralPath $stub.Log -Raw

        Assert-True ($result.ExitCode -eq 0) "Codex installer should succeed with a valid marketplace."
        Assert-Contains $output "agent-workbench marketplace -> registered" "Expected marketplace registration status."
        Assert-Contains $output "stable-docs-backfill -> installed/refreshed" "Expected plugin install/refresh status."
        Assert-Contains $log "plugin marketplace add" "Expected marketplace add command."
        Assert-Contains $log "plugin add stable-docs-backfill@agent-workbench --json" "Expected namespaced plugin add command."

        $secondResult = Invoke-InstallPs1 -Workspace $workspace -Arguments @("codex") -Environment $environment
        $secondLog = Get-Content -LiteralPath $stub.Log -Raw
        $marketplaceAdds = @($secondLog -split "`r?`n" | Where-Object { $_ -like "plugin marketplace add*" })
        $pluginAdds = @($secondLog -split "`r?`n" | Where-Object { $_ -like "plugin add stable-docs-backfill@agent-workbench*" })
        Assert-True ($secondResult.ExitCode -eq 0) "Repeated Codex plugin installation should succeed."
        Assert-Contains $secondResult.Output "agent-workbench marketplace -> already registered" "Repeated install should reuse the same marketplace root."
        Assert-True ($marketplaceAdds.Count -eq 1) "Repeated install should register the marketplace only once."
        Assert-True ($pluginAdds.Count -eq 2) "Repeated install should refresh the plugin on every run."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellCodexMarketplaceConflictIsSafe {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping Codex marketplace conflict test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".codex") | Out-Null
        $stub = New-PowerShellCodexStub -Workspace $workspace
        $environment = @{
            PATH = $stub.Bin + ";" + $env:PATH
            CODEX_STUB_LOG = $stub.Log
            CODEX_STUB_MARKETPLACE_STATE = $stub.State
            CODEX_STUB_MARKETPLACE_ROOT = $workspace.Workbench.Replace("\", "/")
            CODEX_STUB_MARKETPLACE_CONFLICT = "1"
        }

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("codex") -Environment $environment
        $output = $result.Output
        $log = Get-Content -LiteralPath $stub.Log -Raw

        Assert-True ($result.ExitCode -eq 0) "Marketplace conflict should not fail unrelated installation."
        Assert-Contains $output "agent-workbench marketplace -> conflict, skipped" "Expected marketplace conflict status."
        Assert-True (-not $log.Contains("plugin add stable-docs-backfill@agent-workbench")) "Plugin add must not run after a marketplace conflict."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellCodexCliAbsenceIsSafe {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping Codex CLI absence test."
            return
        }
        New-Item -ItemType Directory -Path (Join-Path $workspace.Home ".codex") | Out-Null
        $safePath = $PSHOME + ";" + (Join-Path $env:SystemRoot "System32")

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("codex") -Environment @{ PATH = $safePath }
        $output = $result.Output

        Assert-True ($result.ExitCode -eq 0) "Missing Codex CLI should not fail base host installation."
        Assert-Contains $output "stable-docs-backfill -> skipped (Codex CLI not found)" "Expected safe Codex CLI absence status."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-PowerShellRemovesOnlyManagedLegacyCodexLink {
    $workspace = New-TestWorkspace
    try {
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] junctions unavailable; skipping legacy Codex link test."
            return
        }
        $codexHome = Join-Path $workspace.Home ".codex"
        $codexSkills = Join-Path $codexHome "skills"
        $legacySource = Join-Path $workspace.Workbench "skills\backfill-stable-docs"
        $legacyDestination = Join-Path $codexSkills "backfill-stable-docs"
        New-Item -ItemType Directory -Path $codexSkills -Force | Out-Null
        New-Item -ItemType Directory -Path $legacySource -Force | Out-Null
        New-Item -ItemType Junction -Path $legacyDestination -Target $legacySource | Out-Null
        $stub = New-PowerShellCodexStub -Workspace $workspace
        $environment = @{
            PATH = $stub.Bin + ";" + $env:PATH
            CODEX_STUB_LOG = $stub.Log
            CODEX_STUB_MARKETPLACE_STATE = $stub.State
            CODEX_STUB_MARKETPLACE_ROOT = $workspace.Workbench.Replace("\", "/")
        }

        $result = Invoke-InstallPs1 -Workspace $workspace -Arguments @("codex") -Environment $environment

        Assert-True (-not (Test-Path -LiteralPath $legacyDestination)) "Managed legacy Codex backfill link should be removed."
        Assert-Contains $result.Output "legacy backfill-stable-docs link -> removed" "Expected managed legacy link removal status."
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
        Assert-True ($names -contains "plan-eng-review") "Expected bundled gstack engineering review skill to be visible."
        Assert-True (-not ($names -contains "feishu-skills")) "Bundle root without SKILL.md should not be listed as a skill."
        $feishuShared = $claude.MergedSkills | Where-Object { $_.Name -eq "feishu-shared" } | Select-Object -First 1
        Assert-True ($feishuShared.Sources[0].RelativePath -eq "feishu-skills/feishu-shared") "Expected bundled Feishu shared skill relative path."
        $azureContainerApps = $claude.MergedSkills | Where-Object { $_.Name -eq "azure-container-apps" } | Select-Object -First 1
        Assert-True ($azureContainerApps.Sources[0].RelativePath -eq "azure-skills/azure-container-apps") "Expected bundled Azure Container Apps skill relative path."
        $gstackPlanEngReview = $claude.MergedSkills | Where-Object { $_.Name -eq "plan-eng-review" } | Select-Object -First 1
        Assert-True ($gstackPlanEngReview.Sources[0].RelativePath -eq "gstack/plan-eng-review") "Expected bundled gstack engineering review skill relative path."
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

        $stub = New-BashCodexStub -Workspace $workspace
        $stubBin = Convert-ToBashPath $stub.Bin
        $stubLog = Convert-ToBashPath $stub.Log
        $environment = @{
            PATH = $stubBin + ":/usr/local/bin:/usr/bin:/bin"
            CODEX_STUB_LOG = $stubLog
            CODEX_STUB_MARKETPLACE_STATE = Convert-ToBashPath $stub.State
            CODEX_STUB_MARKETPLACE_ROOT = Convert-ToBashPath $workspace.Workbench
            CODEX_STUB_WARNING = "1"
        }
        $result = Invoke-InstallSh -Workspace $workspace -Arguments @() -Environment $environment
        $output = $result.Output
        $claudeBundledSkill = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\feishu-skills\feishu-base\SKILL.md")
        $claudeAzureRouter = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\azure-skills\using-azure\SKILL.md")
        $claudeAzureContainerApps = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\azure-skills\azure-container-apps\SKILL.md")
        $claudeGstackSkill = Convert-ToBashPath (Join-Path $workspace.Home ".claude\skills\gstack\plan-eng-review\SKILL.md")
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
        Assert-Contains $visibleSkills "plan-eng-review -> gstack/plan-eng-review" "Bash visible-skills script should list bundled gstack engineering review skill."
        Assert-Contains $output "stable-docs-backfill -> installed/refreshed" "Bash installer should install/refresh the Codex plugin."
        $codexLog = Get-Content -LiteralPath $stub.Log -Raw
        Assert-Contains $codexLog "plugin marketplace add" "Bash installer should register the marketplace."
        Assert-Contains $codexLog "plugin add stable-docs-backfill@agent-workbench --json" "Bash installer should add the namespaced plugin."
    }
    finally {
        Remove-TestWorkspace $workspace
    }
}

function Test-BashCodexPluginSafetyScenarios {
    $workspace = New-TestWorkspace
    try {
        $bash = Get-Command bash -ErrorAction SilentlyContinue
        if (-not $bash) {
            Write-Host "[SKIP] bash not available; skipping focused Codex install.sh tests."
            return
        }
        if (-not (Test-JunctionSupport)) {
            Write-Host "[SKIP] symbolic links unavailable; skipping focused Codex install.sh tests."
            return
        }

        $stub = New-BashCodexStub -Workspace $workspace
        $stubBin = Convert-ToBashPath $stub.Bin
        $marketplaceRoot = Convert-ToBashPath $workspace.Workbench

        $repeatHome = Join-Path $workspace.Root "repeat-home"
        New-Item -ItemType Directory -Path (Join-Path $repeatHome ".codex") -Force | Out-Null
        $repeatWorkspace = @{
            Root = $workspace.Root
            Project = $workspace.Project
            Home = $repeatHome
            Workbench = $workspace.Workbench
        }
        $repeatLog = Join-Path $workspace.Root "bash-repeat.log"
        $repeatState = Join-Path $workspace.Root "bash-repeat-state"
        $repeatEnvironment = @{
            PATH = $stubBin + ":/usr/local/bin:/usr/bin:/bin"
            CODEX_STUB_LOG = Convert-ToBashPath $repeatLog
            CODEX_STUB_MARKETPLACE_STATE = Convert-ToBashPath $repeatState
            CODEX_STUB_MARKETPLACE_ROOT = $marketplaceRoot
            CODEX_STUB_WARNING = "1"
        }

        $firstResult = Invoke-InstallSh -Workspace $repeatWorkspace -Arguments @("codex") -Environment $repeatEnvironment
        $secondResult = Invoke-InstallSh -Workspace $repeatWorkspace -Arguments @("codex") -Environment $repeatEnvironment
        $repeatCommands = Get-Content -LiteralPath $repeatLog
        $marketplaceAdds = @($repeatCommands | Where-Object { $_ -like "plugin marketplace add*" })
        $pluginAdds = @($repeatCommands | Where-Object { $_ -like "plugin add stable-docs-backfill@agent-workbench*" })
        Assert-True (($firstResult.ExitCode -eq 0) -and ($secondResult.ExitCode -eq 0)) "Repeated Bash Codex plugin installation should succeed."
        Assert-Contains $secondResult.Output "agent-workbench marketplace -> already registered" "Repeated Bash install should reuse the same marketplace root."
        Assert-True ($marketplaceAdds.Count -eq 1) "Repeated Bash install should register the marketplace only once."
        Assert-True ($pluginAdds.Count -eq 2) "Repeated Bash install should refresh the plugin on every run."

        $conflictHome = Join-Path $workspace.Root "conflict-home"
        New-Item -ItemType Directory -Path (Join-Path $conflictHome ".codex") -Force | Out-Null
        $conflictWorkspace = @{
            Root = $workspace.Root
            Project = $workspace.Project
            Home = $conflictHome
            Workbench = $workspace.Workbench
        }
        $conflictLog = Join-Path $workspace.Root "bash-conflict.log"
        $conflictEnvironment = @{
            PATH = $stubBin + ":/usr/local/bin:/usr/bin:/bin"
            CODEX_STUB_LOG = Convert-ToBashPath $conflictLog
            CODEX_STUB_MARKETPLACE_STATE = Convert-ToBashPath (Join-Path $workspace.Root "bash-conflict-state")
            CODEX_STUB_MARKETPLACE_ROOT = $marketplaceRoot
            CODEX_STUB_MARKETPLACE_CONFLICT = "1"
        }
        $conflictResult = Invoke-InstallSh -Workspace $conflictWorkspace -Arguments @("codex") -Environment $conflictEnvironment
        $conflictCommands = Get-Content -LiteralPath $conflictLog -Raw
        Assert-True ($conflictResult.ExitCode -eq 0) "Bash marketplace conflict should not fail unrelated installation."
        Assert-Contains $conflictResult.Output "agent-workbench marketplace -> conflict, skipped" "Expected Bash marketplace conflict status."
        Assert-True (-not $conflictCommands.Contains("plugin add stable-docs-backfill@agent-workbench")) "Bash plugin add must not run after a marketplace conflict."

        $absentHome = Join-Path $workspace.Root "absent-home"
        New-Item -ItemType Directory -Path (Join-Path $absentHome ".codex") -Force | Out-Null
        $absentWorkspace = @{
            Root = $workspace.Root
            Project = $workspace.Project
            Home = $absentHome
            Workbench = $workspace.Workbench
        }
        $absentResult = Invoke-InstallSh -Workspace $absentWorkspace -Arguments @("codex") -Environment @{ PATH = "/usr/bin:/bin" }
        Assert-True ($absentResult.ExitCode -eq 0) "Missing Codex CLI should not fail Bash base host installation."
        Assert-Contains $absentResult.Output "stable-docs-backfill -> skipped (Codex CLI not found)" "Expected Bash Codex CLI absence status."

        $legacyHome = Join-Path $workspace.Root "legacy-home"
        $legacySkills = Join-Path $legacyHome ".codex\skills"
        $legacySource = Join-Path $workspace.Workbench "skills\backfill-stable-docs"
        $legacyDestination = Join-Path $legacySkills "backfill-stable-docs"
        New-Item -ItemType Directory -Path $legacySkills -Force | Out-Null
        New-Item -ItemType Directory -Path $legacySource -Force | Out-Null
        $bashLegacySource = Convert-ToBashPath $legacySource
        $bashLegacyDestination = Convert-ToBashPath $legacyDestination
        & $bash.Source -lc "ln -s '$bashLegacySource' '$bashLegacyDestination'"
        Assert-True ($LASTEXITCODE -eq 0) "Could not create the Bash legacy Codex skill link fixture."
        $legacyWorkspace = @{
            Root = $workspace.Root
            Project = $workspace.Project
            Home = $legacyHome
            Workbench = $workspace.Workbench
        }
        $legacyEnvironment = @{
            PATH = $stubBin + ":/usr/local/bin:/usr/bin:/bin"
            CODEX_STUB_LOG = Convert-ToBashPath (Join-Path $workspace.Root "bash-legacy.log")
            CODEX_STUB_MARKETPLACE_STATE = Convert-ToBashPath (Join-Path $workspace.Root "bash-legacy-state")
            CODEX_STUB_MARKETPLACE_ROOT = $marketplaceRoot
        }
        $legacyResult = Invoke-InstallSh -Workspace $legacyWorkspace -Arguments @("codex") -Environment $legacyEnvironment
        & $bash.Source -lc "test ! -L '$bashLegacyDestination'"
        Assert-True ($LASTEXITCODE -eq 0) "Managed legacy Bash Codex backfill link should be removed."
        Assert-Contains $legacyResult.Output "legacy backfill-stable-docs link -> removed" "Expected Bash managed legacy link removal status."
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
    @{ Name = "ps1 codex plugin install and refresh"; Action = { Test-PowerShellCodexPluginInstallAndRefresh } }
    @{ Name = "ps1 codex marketplace conflict is safe"; Action = { Test-PowerShellCodexMarketplaceConflictIsSafe } }
    @{ Name = "ps1 codex cli absence is safe"; Action = { Test-PowerShellCodexCliAbsenceIsSafe } }
    @{ Name = "ps1 removes managed legacy codex link"; Action = { Test-PowerShellRemovesOnlyManagedLegacyCodexLink } }
    @{ Name = "ps1 skips conflicts"; Action = { Test-PowerShellSkipsConflicts } }
    @{ Name = "ps1 skips existing links"; Action = { Test-PowerShellSkipsExistingLinks } }
    @{ Name = "ps1 project gitignore init"; Action = { Test-PowerShellProjectGitignoreInitializationStillWorks } }
    @{ Name = "ps1 commands are copied"; Action = { Test-PowerShellCommandsAreCopied } }
    @{ Name = "list-visible includes bundled skills"; Action = { Test-ListVisibleSkillsIncludesBundledSkills } }
    @{ Name = "sh auto-discovers hosts"; Action = { Test-BashAutoDiscoversHosts } }
    @{ Name = "sh codex plugin safety scenarios"; Action = { Test-BashCodexPluginSafetyScenarios } }
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
