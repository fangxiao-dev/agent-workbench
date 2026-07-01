---
name: azure-service-bus-runtime
description: Use when designing or reviewing Azure Service Bus runtime behavior, including JavaScript SDK usage, queue vs topic decisions, peek-lock receive, settlement, renew lock, scheduled retry, duplicate detection, message IDs, and sessions.
---

# Azure Service Bus Runtime

Use this skill for application code and architecture decisions around Service Bus message flow. Keep Azure SDK usage behind an adapter; business services should depend on a queue port.

## KaiSpan Defaults

- Phase 1 uses a Queue, not Topic/subscription. Topic/subscription is future work for fan-out business events.
- Sessions remain disabled unless the product explicitly requires strict per-organization serial processing.
- Use `@azure/service-bus` and `@azure/identity` for Node/NestJS implementations.
- Use peek-lock mode, not receive-and-delete.
- Service Bus messages contain only lightweight pointers: `jobId`, `organizationId`, `type`, `generation`, timestamps, and trace metadata.
- Never put OCR text, invoice body, file bytes, signed URLs, tokens, IBAN, full prompts, or full personal contact data into the message body.
- `messageId` should be deterministic, for example `${jobId}:${generation}`, so duplicate detection can suppress resend uncertainty.
- DB `jobs.attempts/maxAttempts` is the business retry counter; Service Bus delivery count is only a crash/lock-expiry safety net.

## Quick Checklist

Sending:

- Create or update the durable DB job before sending Service Bus.
- For initial send and repair resend, use the same generation and same `messageId`.
- For retry, increment generation and send a scheduled next-generation message.
- Set `correlationId`, `subject`, and application properties for `organizationId`, job type, generation, and trace metadata.

Receiving:

- Receive in peek-lock mode.
- Parse and validate the pointer before doing tenant writes.
- Load the DB job by `organizationId + jobId`.
- Complete stale lower-generation messages without running the handler.
- Complete duplicate messages when the DB job is already terminal.
- Claim queued jobs with a DB compare-and-set and only then run a handler.
- Pair Service Bus lock renewal with DB `lockedUntil` renewal. If either renewal fails, stop processing and let redelivery happen.

Settlement:

- On success, write DB completed state before `completeMessage`.
- On retryable failure, schedule the next generation and mark transport enqueue success before completing the current message.
- On final failure or malformed input, use dead-letter with a structured reason and description.

## When To Open Docs

For KaiSpan docs, first locate the KaiSpan repo root if the current workspace is not the KaiSpan repo, then open the relative path from that root.

- Queues, topics, and subscriptions: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-queues-topics-subscriptions>
- ServiceBusClient JS SDK: <https://learn.microsoft.com/en-us/javascript/api/@azure/service-bus/servicebusclient?view=azure-node-latest>
- Message transfers, locks, and settlement: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-transfers-locks-settlement>
- Message sessions: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/message-sessions>
- Duplicate detection: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/duplicate-detection>
- KaiSpan job transport plan: `docs/superpowers/plans/2026-06-16-azure-service-bus-job-transport.md`
- KaiSpan transaction boundaries: `docs/architecture/Transaction-And-Side-Effect-Boundaries.md`
