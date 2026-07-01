---
name: using-azure
description: Use this skill when working with Azure CLI, Azure Container Registry, Azure Container Apps, Azure Files, Azure AI services, or deployment from a local Windows/Codex workspace. This skill captures practical Azure deployment lessons, especially ACR remote build behavior, provider registration, resource discovery, and avoiding local workspace noise during Docker context packaging.
---

# Using Azure

Use this as an operational checklist, not as a command encyclopedia. Prefer project scripts and current Azure state over memorized commands.

## Index

- Azure CLI on Windows
- Resource discovery before creation
- ACR remote builds from local workspaces
- Container Apps deployment shape
- Split runtime / multi-Container-App deployments
- Persistent files
- Provider registration
- Verification

## Azure CLI On Windows

If `az` is not found after installation, do not require an app restart. First check whether this skill directory has a local `.env` file with an explicit Azure CLI path:

```powershell
$AzureCliPath = $null
$SkillEnvPath = Join-Path $PWD "skills/using-azure/.env"

if (Test-Path $SkillEnvPath) {
    Get-Content $SkillEnvPath | ForEach-Object {
        if ($_ -match '^AZURE_CLI_DEFAULT_PATH=(.+)$') {
            $AzureCliPath = $Matches[1].Trim()
        }
    }
}

if ($AzureCliPath -and (Test-Path $AzureCliPath)) {
    & $AzureCliPath account show
}
```

If `.env` is missing, empty, or points to a non-existent path, find the installed Azure CLI using the current OS and shell conventions. If Azure CLI is not installed, install it first, then retry discovery.

Use `az login --use-device-code` when browser callback login is awkward inside Codex Desktop.

## Resource Discovery Before Creation

Before creating resources, inspect what already exists:

- `az account show`
- `az group list`
- `az cognitiveservices account list`
- `az acr list`

When a project already uses Azure AI or Document Intelligence, prefer placing related Container Apps, ACR, and Storage resources in the same resource group and compatible region unless there is a clear reason not to.

## ACR Remote Builds From Local Workspaces

ACR remote build can fail or hang before queuing when the local workspace has heavy or unusual folders such as agent caches, worktrees, generated outputs, browser artifacts, virtual environments, or nested tooling state.

Before running `az acr build`, check for a project helper script:

```powershell
if (Test-Path .\scripts\build_acr_context.ps1) {
    $context = .\scripts\build_acr_context.ps1
} else {
    # Fall back to manually creating a minimal temporary Docker context.
}
```

The minimal context should include only what the Dockerfile actually copies, for example:

- `Dockerfile`
- `.dockerignore`
- `pyproject.toml`
- `README.md` when `pyproject.toml` declares `readme = "README.md"`
- `src/`
- `config/app_config.json`
- frontend build inputs such as `frontend/package.json`, lockfile, config files, and `frontend/src/`

Submit the generated context, not the noisy repository root, when root packaging is unreliable.

## Container Apps Deployment Shape

For a FastAPI backend in Container Apps:

- Expose the app on `HOST=0.0.0.0`.
- Match Container Apps target port to the container port.
- Keep `max-replicas=1` when the app uses in-memory queues or in-memory request state.
- Use `min-replicas=1` if losing in-memory state after idle scale-to-zero is unacceptable.

If `min-replicas=0`, expect cold starts and loss of process memory after scale-to-zero or restart.

## Split Runtime / Multi-Container-App Deployments

Some environments are made of multiple Container Apps, for example an HTTP API app plus a queue worker app. Treat the environment as the deployment unit, not the API app alone.

Checklist:

- Discover all Container Apps that participate in the environment before changing images or env.
- If API image/env changes affect queued work, update the worker image/env in the same rollout.
- Verify API and worker image tags, queue names, storage mounts, and runtime config paths match the intended deployment.
- `/healthz` only proves the API process is alive; it does not prove async workers are consuming queued jobs.
- Include a smoke that queues one job and confirms the worker consumes it, even if the job later fails at business processing.
- Keep CORS/env-only changes distinct from image rollouts. Do not report an env-only API update as a full backend deployment.

## Persistent Files

Do not assume container filesystem writes survive restarts. If the code writes relative paths such as `outputs/...` and the container `WORKDIR` is `/app`, mount Azure Files at:

```text
/app/outputs
```

Move dynamic runtime config writes into the mounted path when possible, for example:

```text
STATISTICS_CONFIG_PATH=/app/outputs/config/statistics_config.json
```

## Provider Registration

If Azure reports `MissingSubscriptionRegistration`, register the provider and retry. Common examples:

- `Microsoft.ContainerRegistry`
- `Microsoft.App`
- `Microsoft.Storage`

Use `az provider register --namespace <namespace> --wait` before retrying the failed creation command.

## Verification

After builds and deployments, verify the concrete artifact or endpoint:

- ACR: list repositories and tags, not just build output.
- Container app: call `/healthz`.
- Mounted files: upload or write a small file and confirm it lands under the mounted path.
- CORS: test through the real frontend origin, not only localhost.
