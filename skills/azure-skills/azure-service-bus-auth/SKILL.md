---
name: azure-service-bus-auth
description: Use when configuring Azure Service Bus authentication and authorization, including queue-level SAS connection strings, Managed Identity, RBAC roles, API sender permissions, worker receiver permissions, and secret handling.
---

# Azure Service Bus Auth

Use this skill to choose and configure Service Bus credentials. Prefer least privilege and do not print or commit connection strings, SAS keys, tenant IDs, or subscription IDs.

## KaiSpan Defaults

- Local and early smoke can use a queue-level SAS connection string stored only in local or deployment secrets.
- Production should move toward Managed Identity plus Azure RBAC.
- API needs `Azure Service Bus Data Sender` when it sends job messages.
- Worker needs `Azure Service Bus Data Receiver`; if it performs retry or repair sends, it also needs `Azure Service Bus Data Sender`.
- Queue-level scope is preferred over namespace/resource-group/subscription scope when practical.
- App env for Managed Identity uses `AZURE_SERVICE_BUS_CONNECTION_STRING=` empty, `AZURE_SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE=<namespace>.servicebus.windows.net`, and `AZURE_SERVICE_BUS_QUEUE_NAME=kaispan-jobs`.

## Quick Checklist

For SAS connection strings:

- Do not use `RootManageSharedAccessKey` for application runtime except temporary emergency diagnostics.
- Create a queue-level authorization rule.
- Use rights `Send` for API-only credentials.
- Use rights `Listen` plus `Send` for a worker that receives, retries, and repairs.
- Store the connection string in a secret store, not in repo files or logs.

```bash
az servicebus queue authorization-rule create \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --queue-name kaispan-jobs \
  --name kaispan-worker \
  --rights Send Listen

az servicebus queue authorization-rule keys list \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --queue-name kaispan-jobs \
  --name kaispan-worker \
  --query primaryConnectionString \
  --output tsv
```

For Managed Identity:

- Enable the identity on the compute resource first, such as Azure Container Apps or VM.
- Assign `Azure Service Bus Data Sender` and/or `Azure Service Bus Data Receiver` at queue scope where possible.
- Expect RBAC propagation delays; allow several minutes before declaring failure.
- Restart long-running apps after removing roles so cached tokens expire sooner.

Environment shape:

```dotenv
JOB_QUEUE_PROVIDER=azure-service-bus
AZURE_SERVICE_BUS_CONNECTION_STRING=
AZURE_SERVICE_BUS_FULLY_QUALIFIED_NAMESPACE=kaispan-sb-de-dev.servicebus.windows.net
AZURE_SERVICE_BUS_QUEUE_NAME=kaispan-jobs
```

## When To Open Docs

For KaiSpan docs, first locate the KaiSpan repo root if the current workspace is not the KaiSpan repo, then open the relative path from that root.

- Managed identities for Service Bus: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-managed-service-identity>
- Service Bus SAS: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-sas>
- Queue authorization rules: <https://learn.microsoft.com/en-us/cli/azure/servicebus/queue/authorization-rule?view=azure-cli-latest>
- KaiSpan creation guide: `docs/project/Azure-Service-Bus-Create.md`
- KaiSpan tech stack: `docs/project/Tech-Stack.md`
