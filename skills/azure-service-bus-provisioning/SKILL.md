---
name: azure-service-bus-provisioning
description: Use when creating, reviewing, or verifying Azure Service Bus namespaces and queues, especially KaiSpan job transport queues. Covers region, SKU, duplicate detection, TTL, lock duration, DLQ-on-expiration, CLI commands, and post-create checks.
---

# Azure Service Bus Provisioning

Use this skill for Service Bus resource creation and configuration review. Do not run real `az servicebus` create/update/delete commands unless the user explicitly asks for live Azure changes.

## KaiSpan Defaults

- Region: `Germany West Central` (`germanywestcentral`). Verify Azure resource metadata `location`; do not infer residency from DNS, env values, or names.
- Resource group example: `rg-kaispan-de-dev`.
- Namespace example: `kaispan-sb-de-dev`; namespace names are globally unique, so add a customer/env prefix if needed.
- Queue: `kaispan-jobs`.
- SKU: Standard for Phase 1. Basic is not acceptable for production because duplicate detection is not supported.
- Queue settings: duplicate detection enabled, duplicate window `PT1H`, lock duration `PT5M`, default TTL `P14D`, max delivery 10, dead-letter on expiration enabled, sessions disabled, partitioning disabled.
- Service Bus is transport only. Postgres `jobs` remains the source of truth.

## Quick Checklist

Before creation:

- Run `az account show` and confirm the target subscription.
- Run `az group list` and reuse the approved Germany/EU resource group when appropriate.
- Check namespace availability with `az servicebus namespace exists --name <namespace>`.
- Confirm the queue name matches app env `AZURE_SERVICE_BUS_QUEUE_NAME`.

Creation shape:

```bash
az group create \
  --name rg-kaispan-de-dev \
  --location germanywestcentral

az servicebus namespace create \
  --resource-group rg-kaispan-de-dev \
  --name kaispan-sb-de-dev \
  --location germanywestcentral \
  --sku Standard \
  --minimum-tls-version 1.2 \
  --public-network-access Enabled

az servicebus queue create \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --name kaispan-jobs \
  --enable-duplicate-detection true \
  --duplicate-detection-history-time-window PT1H \
  --lock-duration PT5M \
  --max-delivery-count 10 \
  --enable-dead-lettering-on-message-expiration true \
  --default-message-time-to-live P14D \
  --enable-session false \
  --enable-partitioning false
```

Verification:

```bash
az servicebus namespace show \
  --resource-group rg-kaispan-de-dev \
  --name kaispan-sb-de-dev \
  --query "{name:name, location:location, sku:sku.name}" \
  --output table

az servicebus queue show \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --name kaispan-jobs \
  --query "{name:name,status:status,lockDuration:lockDuration,maxDeliveryCount:maxDeliveryCount,defaultMessageTimeToLive:defaultMessageTimeToLive,requiresDuplicateDetection:requiresDuplicateDetection,duplicateDetectionHistoryTimeWindow:duplicateDetectionHistoryTimeWindow,deadLetteringOnMessageExpiration:deadLetteringOnMessageExpiration,requiresSession:requiresSession,enablePartitioning:enablePartitioning}" \
  --output table
```

Expected: `location` is Germany West Central / `germanywestcentral`; queue is `Active`; duplicate detection is true; lock is `PT5M`; duplicate window is `PT1H`; TTL is `P14D`; max delivery is 10; expiration DLQ is true; sessions and partitioning are false.

## When To Open Docs

- Azure CLI namespace reference: <https://learn.microsoft.com/en-us/cli/azure/servicebus/namespace?view=azure-cli-latest>
- Azure CLI queue reference: <https://learn.microsoft.com/en-us/cli/azure/servicebus/queue?view=azure-cli-latest>
- Duplicate detection behavior: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/duplicate-detection>
- Enable duplicate detection: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/enable-duplicate-detection>
- KaiSpan creation guide: `D:\CodeSpace\kaispan-dev\docs\project\Azure-Service-Bus-Create.md`
- KaiSpan Service Bus plan: `D:\CodeSpace\kaispan-dev\docs\superpowers\plans\2026-06-16-azure-service-bus-job-transport.md`
