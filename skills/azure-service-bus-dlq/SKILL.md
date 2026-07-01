---
name: azure-service-bus-dlq
description: Use when inspecting, reconciling, or designing Azure Service Bus dead-letter queue behavior, including DLQ reasons, MaxDeliveryCountExceeded, malformed messages, final failures, and safe settlement after DB reconciliation.
---

# Azure Service Bus DLQ

Use this skill when Service Bus messages are dead-lettered or when designing DLQ handling. Treat DLQ as operational evidence; product state still belongs in Postgres `jobs`.

## KaiSpan Defaults

- Queue expiration should dead-letter, not silently drop messages.
- `max delivery 10` is the broker safety net, not the logical retry policy.
- Malformed messages, unknown jobs, and final failures should be dead-lettered with structured reason and description.
- A DLQ reconciler must mark non-terminal DB jobs failed or raise alertable logs.
- Complete a DLQ message only after DB reconciliation succeeds or after confirming the DB job is already terminal.
- Leave ambiguous malformed DLQ messages for manual inspection when dropping them would lose evidence.

## Quick Checklist

When investigating DLQ:

- Identify the queue and namespace from deployment env, not from memory.
- Check active and dead-letter message counts.
- Inspect DLQ reason and description without dumping sensitive message bodies.
- For `MaxDeliveryCountExceeded`, check whether DB job is still `processing` or `queued`.
- Reconcile DB state first, then settle the DLQ message.
- If repeated malformed messages appear, add rate-limited logs and a manual drain runbook before production release.

Application rules:

- Keep DLQ receive/complete/abandon operations inside the Service Bus transport adapter.
- Do not inject the Azure SDK client directly into product or reconciler services.
- Never expose raw Service Bus DLQ operations to customer-facing admin UI; show business-readable job summaries instead.

Useful CLI inspection pattern:

```bash
az servicebus queue show \
  --resource-group rg-kaispan-de-dev \
  --namespace-name kaispan-sb-de-dev \
  --name kaispan-jobs \
  --query "{active:countDetails.activeMessageCount,deadLetter:countDetails.deadLetterMessageCount,transferDeadLetter:countDetails.transferDeadLetterMessageCount}" \
  --output table
```

## When To Open Docs

- Dead-letter queues: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues>
- Advanced Service Bus features: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/advanced-features-overview>
- KaiSpan migration runbook: `D:\CodeSpace\kaispan-dev\docs\ops\Migration-Runbook.md`
- KaiSpan job transport plan: `D:\CodeSpace\kaispan-dev\docs\superpowers\plans\2026-06-16-azure-service-bus-job-transport.md`
