[CmdletBinding()]
param(
    [string]$RepositoryRoot,
    [switch]$ValidateOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RequiredPath {
    param(
        [string]$BasePath,
        [string]$RelativePath
    )

    $path = Join-Path $BasePath $RelativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required file is missing: $path"
    }

    return $path
}

function Get-JsonEvents {
    param(
        [string]$Path
    )

    $events = @()
    foreach ($line in (Get-Content -LiteralPath $Path)) {
        try {
            $event = $line | ConvertFrom-Json
            if ($event.PSObject.Properties.Match("item").Count -gt 0) {
                $events += $event
            }
        }
        catch {
            # Codex diagnostics are retained in the raw log but are not JSON events.
        }
    }

    return $events
}

function Get-ChildThreadIds {
    param(
        [object[]]$Events
    )

    $ids = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($event in $Events) {
        $item = $event.item
        if (($null -eq $item) -or ($item.type -ne "collab_tool_call") -or ($item.tool -ne "spawn_agent")) {
            continue
        }

        foreach ($id in @($item.receiver_thread_ids)) {
            if ($id) {
                [void]$ids.Add([string]$id)
            }
        }
    }

    return @($ids)
}

$exitCode = 1
try {
    if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
        $RepositoryRoot = Split-Path -Parent $PSScriptRoot
    }

    $resolvedRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
    $projectConfig = Get-RequiredPath -BasePath $resolvedRoot -RelativePath ".codex\config.toml"
    $parentProfile = Get-RequiredPath -BasePath $resolvedRoot -RelativePath ".codex\harness\parent.toml"
    $executionProfilesPath = Get-RequiredPath -BasePath $resolvedRoot -RelativePath "skills\codex-harness\assets\codex-harness-execution-profiles.v0.json"
    [void](Get-RequiredPath -BasePath $resolvedRoot -RelativePath "skills\codex-harness\SKILL.md")

    $parentProfileContent = Get-Content -LiteralPath $parentProfile -Raw
    $profileIdMatch = [regex]::Match($parentProfileContent, '(?m)^execution_profile\s*=\s*"([^"]+)"\s*$')
    if (-not $profileIdMatch.Success -or $parentProfileContent.IndexOf('developer_instructions = ', [System.StringComparison]::Ordinal) -lt 0) {
        throw "Parent profile must define execution_profile and developer_instructions: $parentProfile"
    }
    $executionProfiles = Get-Content -LiteralPath $executionProfilesPath -Raw | ConvertFrom-Json
    $parentExecutionProfile = @($executionProfiles.profiles | Where-Object { $_.id -eq $profileIdMatch.Groups[1].Value -and $_.role -eq "parent" })
    if ($parentExecutionProfile.Count -ne 1) {
        throw "Parent execution profile is missing or not a parent profile: $($profileIdMatch.Groups[1].Value)"
    }
    $parentModel = [string]$parentExecutionProfile[0].model
    $parentReasoningEffort = [string]$parentExecutionProfile[0].reasoning_effort

    $configContent = Get-Content -LiteralPath $projectConfig -Raw
    if ($configContent.IndexOf("max_threads = 4", [System.StringComparison]::Ordinal) -lt 0) {
        throw "Project config must define the Harness resource safety cap max_threads=4. This cap does not assign child roles or acceptance semantics."
    }

    if ($ValidateOnly) {
        Write-Output "[OK] Codex parent-agent harness pilot configuration is valid."
        $exitCode = 0
    }
    else {
        $codex = Get-Command codex -ErrorAction Stop
        $artifactDirectory = Join-Path $resolvedRoot ".codex\harness-runs"
        New-Item -ItemType Directory -Force -Path $artifactDirectory | Out-Null

        $runId = Get-Date -Format "yyyyMMdd-HHmmss"
        $rawLogPath = Join-Path $artifactDirectory ("{0}.jsonl" -f $runId)
        $summaryPath = Join-Path $artifactDirectory ("{0}.summary.json" -f $runId)
        $statusBefore = (& git -C $resolvedRoot status --porcelain=v1 | Out-String).TrimEnd()
        $prompt = @'
 Act as the parent execution agent for a read-only Codex Harness smoke task. Read AGENTS.md, .codex/config.toml, skills/codex-harness/SKILL.md, and skills/codex-harness/references/codex-harness-guide.md, then summarize the parent-only control boundary in those files. You own the execution method, including whether and how to use native subagents; the Harness does not assign child roles or accept child activity as proof. The max_threads value is a Harness-supplied resource safety cap, not a child-role or acceptance requirement. Do not modify files or use network access. Report a boundary violation only for an actual violation during this run. Return only one JSON object with schema_version="codex-harness.parent-result.v0", status="succeeded" or "failed", a concise summary, and boundary_violations as an array of strings.
'@
        $prompt = "Parent role profile:`n$parentProfileContent`n`nAssigned work:`n$prompt"
        $arguments = @(
            "exec",
            "--json",
            "--ignore-user-config",
            "--enable", "multi_agent",
            "--config", 'approval_policy="never"',
            "--model", $parentModel,
            "--config", ('model_reasoning_effort="{0}"' -f $parentReasoningEffort),
            "--sandbox", "read-only",
            "--cd", $resolvedRoot,
            $prompt
        )

        Write-Output "[INFO] Starting persistent Codex CLI session for native subagent verification."
        $previousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & $codex.Source @arguments 2>&1 | ForEach-Object {
                $line = $_.ToString()
                Add-Content -LiteralPath $rawLogPath -Value $line
                Write-Output $line
            }
            $codexExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
        $statusAfter = (& git -C $resolvedRoot status --porcelain=v1 | Out-String).TrimEnd()
        $events = @(Get-JsonEvents -Path $rawLogPath)
        $childThreadIds = @(Get-ChildThreadIds -Events $events)
        $spawnEventCount = @($events | Where-Object {
                ($null -ne $_.item) -and ($_.item.type -eq "collab_tool_call") -and ($_.item.tool -eq "spawn_agent")
            }).Count
        $agentMessages = @($events | Where-Object {
                ($null -ne $_.item) -and ($_.item.type -eq "agent_message")
            })
        $finalMessage = ""
        if ($agentMessages.Count -gt 0) {
            $finalMessage = [string]$agentMessages[-1].item.text
        }
        $rawLog = Get-Content -LiteralPath $rawLogPath -Raw
        $worktreeChanged = $statusBefore -ne $statusAfter
        $parentResult = $null
        try {
            $parentResult = $finalMessage | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            $parentResult = $null
        }
        $parentResultValid = ($null -ne $parentResult) -and
            ($parentResult.schema_version -eq "codex-harness.parent-result.v0") -and
            ($parentResult.status -eq "succeeded") -and
            ($null -ne $parentResult.boundary_violations) -and
            (@($parentResult.boundary_violations).Count -eq 0)
        $passed = ($codexExitCode -eq 0) -and $parentResultValid -and (-not $worktreeChanged)
        $summary = [ordered]@{
            run_id = $runId
            status = if ($passed) { "passed" } else { "failed" }
            codex_exit_code = $codexExitCode
            parent_profile = "codex_harness_parent"
            parent_model = $parentModel
            parent_reasoning_effort = $parentReasoningEffort
            native_spawn_event_count = $spawnEventCount
            child_thread_count = $childThreadIds.Count
            child_thread_ids = $childThreadIds
            parent_result_valid = $parentResultValid
            parent_result = $parentResult
            worktree_changed = $worktreeChanged
            final_message = $finalMessage
            raw_log = $rawLogPath
        }
        $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding utf8

        if ($passed) {
            Write-Output "[OK] Parent-agent harness pilot passed. Summary: $summaryPath"
            $exitCode = 0
        }
        else {
            Write-Error "Parent-agent harness pilot did not produce a valid bounded parent result. Summary: $summaryPath"
            $exitCode = 2
        }
    }
}
catch {
    Write-Error $_
    $exitCode = 1
}

exit $exitCode
