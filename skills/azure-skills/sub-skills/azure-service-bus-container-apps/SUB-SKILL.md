---
name: azure-service-bus-container-apps
description: Use when wiring Azure Service Bus into Azure Container Apps deployments, including API and worker split, secrets and env vars, Managed Identity, KEDA azure-servicebus scale rules, worker replica limits, and smoke verification.
---

# Azure Service Bus Container Apps

Use this skill only for Container Apps deployments that send or consume Service Bus messages. Treat API and worker as separate runtime roles even if they share an image.

For general Container Apps deployment shape, target ports, ingress, replica policy, health checks, persistent files, and non-Service-Bus env review, use `azure-container-apps` first. Keep this skill focused on Service Bus secrets/env, KEDA `azure-servicebus` scaling, queue worker limits, and queue smoke verification.

## KaiSpan Defaults

- Azure runtime resources default to `Germany West Central` (`germanywestcentral`).
- API sends messages; worker receives messages and may also send retry or repair messages.
- Worker starts with `minReplicas=1,maxReplicas=1`.
- Increase worker replicas only after handler idempotency, duplicate delivery, DLQ reconciliation, provider rate limits, and integration tests are verified.
- Move worker to `minReplicas=0` only after accepting KEDA polling and cold-start latency.
- `/healthz` or API readiness does not prove workers are consuming Service Bus jobs.
- Use `pnpm --filter @kaispan/api service-bus:smoke` for a non-consuming queue peek smoke.

## Quick Checklist

For ACA secrets/env:

- Store connection strings as Container Apps secrets, not plain env values.
- For Managed Identity, leave `AZURE_SERVICE_BUS_CONNECTION_STRING` empty and set `AZURE_SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE`.
- Keep `AZURE_SERVICE_BUS_QUEUE_NAME=kaispan-jobs`.
- API and worker env must agree on queue name, namespace/connection-string source, and retry/repair timing.

Example Service Bus env:

```dotenv
JOB_QUEUE_PROVIDER=azure-service-bus
AZURE_SERVICE_BUS_CONNECTION_STRING=secretref:service-bus-connection-string
AZURE_SERVICE_BUS_QUEUE_NAME=kaispan-jobs
AZURE_SERVICE_BUS_LOCK_RENEWAL_INTERVAL_SECONDS=30
AZURE_SERVICE_BUS_REPAIR_INTERVAL_SECONDS=60
AZURE_SERVICE_BUS_RETRY_BASE_DELAY_SECONDS=30
AZURE_SERVICE_BUS_RETRY_MAX_DELAY_SECONDS=900
```

For KEDA scaling:

```bash
az containerapp update \
  --name kaispan-worker \
  --resource-group rg-kaispan-de-dev \
  --min-replicas 1 \
  --max-replicas 1 \
  --scale-rule-name servicebus-jobs \
  --scale-rule-type azure-servicebus \
  --scale-rule-metadata "queueName=kaispan-jobs" "namespace=kaispan-sb-de-dev" "messageCount=5"
```

Deployment verification:

- Confirm API and worker image tags.
- Confirm API and worker env/secrets.
- Run API readiness.
- Run Service Bus smoke; it only peeks and does not consume messages.
- For worker verification, enqueue a safe test job and confirm worker consumes it through DB/job logs, not just queue depth.

## When To Open Docs

For KaiSpan docs, first locate the KaiSpan repo root if the current workspace is not the KaiSpan repo, then open the relative path from that root.

- Container Apps scaling: <https://learn.microsoft.com/en-us/azure/container-apps/scale-app>
- KaiSpan ACA deployment notes: `docs/ops/GHCR-Azure-Container-Apps.md`
- KaiSpan migration runbook: `docs/ops/Migration-Runbook.md`
- KaiSpan Service Bus plan: `docs/superpowers/plans/2026-06-16-azure-service-bus-job-transport.md`
