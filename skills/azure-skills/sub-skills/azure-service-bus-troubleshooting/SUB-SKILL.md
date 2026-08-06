---
name: azure-service-bus-troubleshooting
description: Use when diagnosing Azure Service Bus failures, including failed smoke tests, missing duplicate detection, wrong queue names, EntityPath mismatches, SAS or RBAC permission errors, region drift, lock timeout redelivery, DLQ growth, and leaked secret risk.
---

# Azure Service Bus Troubleshooting

Use this skill to narrow Service Bus incidents quickly. Start with resource identity, region, queue settings, auth, and safe smoke before changing application code.

## KaiSpan Defaults

- Correct region is `Germany West Central` (`germanywestcentral`), verified from Azure resource metadata.
- Correct queue is `kaispan-jobs` unless the current environment explicitly says otherwise.
- Standard SKU is expected for production because duplicate detection is required.
- Smoke command is `pnpm --filter @kaispan/api service-bus:smoke`; it peeks only and must not consume messages.
- Do not paste connection strings, SAS keys, tenant IDs, subscription IDs, or raw message bodies into chat, logs, docs, or PRs.

## Quick Checklist

First identify the target:

- Confirm subscription with `az account show`.
- Confirm resource group, namespace, queue name, and queue status.
- Confirm namespace `location` is Germany West Central / `germanywestcentral`.
- Confirm app env queue name matches Azure queue name.

Common diagnoses:

- Duplicate detection missing: namespace is probably Basic, or the queue was created without duplicate detection. Create a new Standard queue; do not assume it can be toggled later.
- App says queue not found: check `AZURE_SERVICE_BUS_QUEUE_NAME`, namespace, and whether a queue-level SAS connection string has an `EntityPath` for a different queue.
- Send fails: API credential needs `Send` or RBAC `Azure Service Bus Data Sender`.
- Receive, complete, abandon, or dead-letter fails: worker credential needs `Listen` or RBAC `Azure Service Bus Data Receiver`.
- Managed Identity recently changed: wait for role propagation and restart long-running apps if roles were removed.
- Repeated redelivery: lock duration or renewal may be too short; KaiSpan target lock is `PT5M` and renew interval is typically 30 seconds for short test locks.
- DLQ grows: inspect DLQ reason, reconcile DB jobs, and do not clear evidence before recording the operational reason.
- Smoke fails after deployment: check secret value presence, queue name, permissions, network/firewall/private endpoint, and namespace region.

Safe verification:

```bash
az servicebus namespace show \
  --resource-group rg-kaispan-de-dev \
  --name kaispan-sb-de-dev \
  --query "{name:name,location:location,sku:sku.name}" \
  --output table

az servicebus queue show \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --name kaispan-jobs \
  --query "{status:status,requiresDuplicateDetection:requiresDuplicateDetection,lockDuration:lockDuration,maxDeliveryCount:maxDeliveryCount,deadLetter:countDetails.deadLetterMessageCount}" \
  --output table
```

## When To Open Docs

For KaiSpan docs, first locate the KaiSpan repo root if the current workspace is not the KaiSpan repo, then open the relative path from that root.

- Service Bus SAS: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-sas>
- Managed identities for Service Bus: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity>
- Dead-letter queues: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues>
- Service Bus network security: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/network-security>
- Azure CLI queue reference: <https://learn.microsoft.com/en-us/cli/azure/servicebus/queue?view=azure-cli-latest>
- KaiSpan creation guide: `docs/project/Azure-Service-Bus-Create.md`
- KaiSpan migration runbook: `docs/ops/Migration-Runbook.md`
