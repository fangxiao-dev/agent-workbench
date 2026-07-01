---
name: azure-service-bus-observability
description: Use when setting up or reviewing Azure Service Bus monitoring, metrics, logs, diagnostic settings, backlog and DLQ alerts, network restrictions, private endpoints, and Premium tier triggers.
---

# Azure Service Bus Observability

Use this skill for operational visibility and network/security review. Service Bus health should be correlated with app logs, DB `jobs`, and deployment state.

## KaiSpan Defaults

- Alert on DLQ growth and sustained backlog, not only application exceptions.
- Correlate HTTP request, DB job, Service Bus message, worker handler, and audit logs using `requestId`, `correlationId`, `jobId`, and trace metadata.
- Do not log full message bodies when they might contain tenant identifiers or accidental payloads.
- Use Germany/EU region policy for Azure resources and verify `location` from resource metadata.
- Consider Premium only when customer requirements demand private networking, stricter isolation, predictable throughput, or advanced enterprise controls.

## Quick Checklist

Metrics and alerts to consider:

- Active message count sustained above expected backlog.
- Dead-letter message count greater than zero or increasing.
- Incoming/outgoing messages unexpectedly flat during known job traffic.
- Server errors, throttling, or authorization failures.
- Worker app running but no successful job completions.

Diagnostics:

- Enable diagnostic settings to the approved log sink when production monitoring is in scope.
- Keep Sentry/OpenObserve/audit responsibilities separate: Sentry for code errors, OpenObserve for runtime logs, DB audit logs for business audit.
- Do not treat Azure Portal queue depth as product truth; Postgres `jobs` remains the product source of truth.

Network/security review:

- Confirm public network access policy matches the environment.
- If using private endpoint or restricted firewall, verify API/worker egress can still reach Service Bus.
- Verify Managed Identity roles after network changes; auth and network failures can look similar in app logs.

## When To Open Docs

- Monitor Service Bus: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/monitor-service-bus>
- Supported Service Bus metrics: <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-metrics/microsoft-servicebus-namespaces-metrics>
- Supported Service Bus logs: <https://learn.microsoft.com/en-us/azure/azure-monitor/reference/supported-logs/microsoft-servicebus-namespaces-logs>
- Service Bus network security: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/network-security>
- Service Bus Private Link: <https://learn.microsoft.com/en-us/azure/service-bus-messaging/private-link-service>
- KaiSpan observability design: `D:\CodeSpace\kaispan-dev\docs\architecture\Observability-Logging-Tracing-Design.md`
- KaiSpan tech stack: `D:\CodeSpace\kaispan-dev\docs\project\Tech-Stack.md`
