---
name: using-azure
description: Use this Azure router when a task mentions Azure CLI, ACR, Container Apps, Service Bus, Azure Files, Azure AI services, provider registration, or local Windows/macOS/Linux Azure deployment. Route detailed work to focused Azure skills.
---

# Using Azure

Use this as the Azure entry map. Route detailed work to focused Azure skills, and prefer current Azure state over memorized commands.

## Azure Skill Map

- Use `azure-container-registry` for ACR remote builds, minimal Docker build contexts, `az acr build`, and cross-platform context helper usage.
- Use `azure-container-apps` for general Azure Container Apps deployment shape, ports, replicas, health checks, multi-app rollouts, secrets/env review, and persistent files.
- Use `azure-service-bus-provisioning` for namespace/queue creation, Germany West Central region checks, Standard SKU, duplicate detection, TTL, lock duration, max delivery 10, and CLI verification.
- Use `azure-service-bus-auth` for queue-level SAS, connection strings, Managed Identity, RBAC roles, API sender permissions, worker receiver permissions, and secret handling.
- Use `azure-service-bus-runtime` for JS SDK usage, queue vs topic decisions, peek-lock, settlement, explicit lock renewal, scheduled retry, duplicate detection, message IDs, and sessions.
- Use `azure-service-bus-dlq` for dead-letter queue inspection, `MaxDeliveryCountExceeded`, malformed messages, final failures, DB reconciliation, and safe settlement.
- Use `azure-service-bus-container-apps` for Service Bus-specific Container Apps wiring: API/worker queue env, secrets, KEDA `azure-servicebus` scaling, worker replica limits, and queue smoke verification.
- Use `azure-service-bus-observability` for Azure Monitor metrics/logs, diagnostic settings, DLQ/backlog alerts, network restrictions, private endpoints, and Premium tier triggers.
- Use `azure-service-bus-troubleshooting` for smoke failures, Basic tier limitations, duplicate detection mistakes, queue name or `EntityPath` mismatches, auth errors, region drift, lock timeouts, and DLQ growth.

## Azure CLI On Local Workstation

If `az` is not found after installation, first check whether this skill directory has a machine-local `.env` file with `AZURE_CLI_DEFAULT_PATH`. Do not commit that file. Start from `.env.example` if needed.

PowerShell:

```powershell
$SkillDirs = @(
    (Join-Path $HOME ".codex/skills/azure-skills/using-azure")
    (Join-Path $HOME ".claude/skills/azure-skills/using-azure")
    (Join-Path $HOME ".gemini/skills/azure-skills/using-azure")
    "skills/azure-skills/using-azure"
)
$SkillEnvPath = $SkillDirs | ForEach-Object { Join-Path $_ ".env" } | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($SkillEnvPath) {
    $AzureCliPath = (Get-Content $SkillEnvPath | Where-Object { $_ -match '^AZURE_CLI_DEFAULT_PATH=' } | Select-Object -First 1) -replace '^AZURE_CLI_DEFAULT_PATH=', ''
}
if ($AzureCliPath -and (Test-Path $AzureCliPath)) {
    & $AzureCliPath account show
} elseif (Get-Command az -ErrorAction SilentlyContinue) {
    az account show
}
```

bash/zsh:

```bash
skill_env_path=""
for skill_dir in \
  "$HOME/.codex/skills/azure-skills/using-azure" \
  "$HOME/.claude/skills/azure-skills/using-azure" \
  "$HOME/.gemini/skills/azure-skills/using-azure" \
  "skills/azure-skills/using-azure"
do
  if [ -f "$skill_dir/.env" ]; then
    skill_env_path="$skill_dir/.env"
    break
  fi
done

if [ -n "$skill_env_path" ]; then
  azure_cli_path="$(awk -F= '/^AZURE_CLI_DEFAULT_PATH=/ {print $2; exit}' "$skill_env_path")"
fi
if [ -n "$azure_cli_path" ] && [ -x "$azure_cli_path" ]; then
  "$azure_cli_path" account show
elif command -v az >/dev/null 2>&1; then
  az account show
fi
```

If `.env` is missing, empty, or points to a non-existent path, find the installed Azure CLI using the current OS and shell conventions. If Azure CLI is not installed, install it first, then retry discovery.

Use `az login --use-device-code` when browser callback login is awkward inside an agent or remote terminal.

## Resource Discovery Before Creation

Before creating resources, inspect the active subscription, resource groups, and relevant existing resources. When a project already uses Azure AI or Document Intelligence, prefer placing related Container Apps, ACR, Storage, and messaging resources in the same approved resource group and compatible region unless there is a clear reason not to.

## Provider Registration

If Azure reports `MissingSubscriptionRegistration`, register the relevant provider with `az provider register --namespace <namespace> --wait`, then retry the failed command. Common providers include `Microsoft.ContainerRegistry`, `Microsoft.App`, `Microsoft.Storage`, and `Microsoft.ServiceBus`.

## Verification

After builds and deployments, verify the concrete artifact or endpoint:

- ACR: list repositories and tags, not just build output.
- Container App: call the real health endpoint and confirm target port, image tag, env, and secrets.
- Service Bus: verify namespace `location`, queue settings, auth scope, active/DLQ counts, and app env queue names.
- Mounted files: upload or write a small file and confirm it lands under the mounted path.
- CORS: test through the real frontend origin, not only localhost.
