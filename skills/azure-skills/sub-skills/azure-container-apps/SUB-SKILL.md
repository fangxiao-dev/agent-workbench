---
name: azure-container-apps
description: "Use for general Azure Container Apps deployment work: ports, ingress, replicas, health checks, multi-app rollouts, secrets/env, persistent file mounts, and runtime verification. For Service Bus KEDA or queue worker wiring, route to azure-service-bus-container-apps."
---

# Azure Container Apps

Use this skill for general Azure Container Apps deployment shape. Keep queue-specific Service Bus behavior in `azure-service-bus-container-apps`.

## Deployment Shape

For an HTTP backend in Container Apps:

- Expose the process on `HOST=0.0.0.0`.
- Match Container Apps target port to the container port.
- Verify ingress mode matches the intended exposure: external for public APIs, internal for private environment-only traffic.
- Keep `max-replicas=1` when the app uses in-memory queues, in-memory request state, or local filesystem state that has not been made shared.
- Use `min-replicas=1` if losing process memory after idle scale-to-zero is unacceptable.
- If `min-replicas=0`, expect cold starts and loss of process memory after scale-to-zero or restart.

## Multi-App Rollouts

Some environments are made of multiple Container Apps, for example an HTTP API app plus a worker app. Treat the environment as the deployment unit, not the API app alone.

Checklist:

- Discover all Container Apps that participate in the environment before changing images or env.
- If API image/env changes affect workers, update worker image/env in the same rollout.
- Verify image tags, integration names, storage mounts, runtime config paths, and health endpoints match the intended deployment.
- `/healthz` only proves the process serving that endpoint is alive; it does not prove background workers or downstream integrations are healthy.
- Keep env-only changes distinct from image rollouts. Do not report an env-only update as a full backend deployment.

## Secrets And Env

- Store secrets as Container Apps secrets, not plain env values.
- Verify secret presence without printing secret values.
- Confirm env values on every app role that needs them; API and worker apps often drift.
- Restart or create a new revision when a secret/env change requires the process to reread configuration.
- Use placeholder env only as an explicit deployment shell, for example `DATABASE_URL=<to-be-filled>` or `EXTERNAL_STORAGE_BUCKET=<to-be-filled>`.

## Persistent Files

Do not assume container filesystem writes survive restarts. If the code writes relative paths such as `outputs/...` and the container `WORKDIR` is `/app`, mount Azure Files at:

```text
/app/outputs
```

Move dynamic runtime config writes into the mounted path when possible, for example:

```text
APP_CONFIG_PATH=/app/outputs/config/app.json
```

## Verification

After deployment, verify concrete runtime state:

- Container App revision and image tag.
- Target port and ingress.
- Relevant env var names and secret references, without dumping secret values.
- Health endpoint through the real hostname.
- Mounted files by writing or uploading a small safe file.
- Logs for startup errors after the new revision starts.

Use Azure CLI output or portal metadata for final confirmation; do not rely only on local deployment command output.

## When To Open Docs

- Container Apps overview: <https://learn.microsoft.com/en-us/azure/container-apps/overview>
- Container Apps ingress: <https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview>
- Container Apps scaling: <https://learn.microsoft.com/en-us/azure/container-apps/scale-app>
- Container Apps secrets: <https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets>
- Azure Files volume mounts: <https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts>
