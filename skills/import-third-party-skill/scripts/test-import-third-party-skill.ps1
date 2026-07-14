#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$ImportScript = Join-Path $PSScriptRoot "import-third-party-skill.py"
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("import-third-party-skill-tests-" + [System.Guid]::NewGuid().ToString("N"))

function Assert-True($Condition, $Message) {
    if (-not $Condition) {
        throw $Message
    }
}

try {
    New-Item -ItemType Directory -Path $TempRoot | Out-Null
    $FakeHome = Join-Path $TempRoot "home"
    New-Item -ItemType Directory -Path $FakeHome | Out-Null
    $env:USERPROFILE = $FakeHome
    $env:HOME = $FakeHome

    $RegistryMd = Join-Path $RepoRoot "registry\third-party-skills.md"
    $RegistryMdBackup = [System.IO.File]::ReadAllBytes($RegistryMd)

    $FakeInstaller = Join-Path $TempRoot "fake-installer.ps1"
    @'
param([string]$Package, [string]$Flag1, [string]$Flag2)
$skillName = ($Package -split "@", 2)[1]
$target = Join-Path $env:USERPROFILE ".codex\skills\$skillName"
New-Item -ItemType Directory -Path $target -Force | Out-Null
Set-Content -Path (Join-Path $target "SKILL.md") -Value "---`nname: $skillName`n---" -Encoding UTF8
Set-Content -Path (Join-Path $target "manifest.txt") -Value "fixture" -Encoding UTF8
'@ | Set-Content -Path $FakeInstaller -Encoding UTF8

    @'
# Third-party Skills

| Skill | 来源 | 获取方式 | 备注 |
|-------|------|----------|------|

## 说明
- 只登记第三方 skills，不登记本仓库自建 skills。
'@ | Set-Content -Path $RegistryMd -Encoding UTF8

    & python $ImportScript `
        --skill-name "frontend-design-fixture" `
        --package "anthropics/skills@frontend-design-fixture" `
        --skip-review `
        --approve `
        --install-command "powershell -ExecutionPolicy Bypass -File $FakeInstaller" | Out-Null

    $vendoredPath = Join-Path $RepoRoot "skills\frontend-design-fixture\SKILL.md"
    Assert-True (Test-Path $vendoredPath) "install mode should copy skill into repo skills"

    $mdText = Get-Content $RegistryMd -Raw
    Assert-True ($mdText.Contains("| frontend-design-fixture | ``anthropics/skills``")) "markdown registry should record source"
    Assert-True ($mdText.Contains("skills/frontend-design-fixture/")) "markdown registry should record repo skill path"
    Assert-True (-not ($mdText -match "registry/skills\.lock\.json")) "markdown registry should not mention removed lock file"

    $conflictOutput = & python $ImportScript `
        --skill-name "frontend-design-fixture" `
        --package "vercel-labs/agent-skills@frontend-design-fixture" `
        --skip-review `
        --approve `
        --install-command "powershell -ExecutionPolicy Bypass -File $FakeInstaller"

    Assert-True (($conflictOutput -join "`n") -match "Conflict detected\. Installation skipped\.") "same-name install should skip on conflict"

    & python $ImportScript `
        --skill-name "gstack-fixture" `
        --package "garrytan/gstack@gstack-fixture" `
        --target-dir "skills/gstack-test-bundle" `
        --skip-review `
        --approve `
        --install-command "powershell -ExecutionPolicy Bypass -File $FakeInstaller" | Out-Null

    $bundledPath = Join-Path $RepoRoot "skills\gstack-test-bundle\gstack-fixture\SKILL.md"
    Assert-True (Test-Path $bundledPath) "explicit target dir should copy skill into a repo bundle"

    $mdText = Get-Content $RegistryMd -Raw
    Assert-True ($mdText.Contains("skills/gstack-test-bundle/gstack-fixture/")) "markdown registry should record bundled repo skill path"

    Write-Host "All import-third-party-skill tests passed."
}
finally {
    if (Test-Path (Join-Path $RepoRoot "skills\frontend-design-fixture")) {
        Remove-Item (Join-Path $RepoRoot "skills\frontend-design-fixture") -Recurse -Force
    }
    if (Test-Path (Join-Path $RepoRoot "skills\gstack-test-bundle")) {
        Remove-Item (Join-Path $RepoRoot "skills\gstack-test-bundle") -Recurse -Force
    }
    if ($RegistryMdBackup) {
        [System.IO.File]::WriteAllBytes($RegistryMd, $RegistryMdBackup)
    }
    if (Test-Path $TempRoot) {
        Remove-Item $TempRoot -Recurse -Force
    }
}
