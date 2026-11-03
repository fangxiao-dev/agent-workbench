---
name: call-ds-by-codexcli
description: Use only when the user asks to run a one-shot task through DeepSeek via the configured Codex CLI and Magpie gateway, or to delegate a bounded task to a DeepSeek subagent in the current conversation.
---

# call-ds-by-codexcli

Run the requested task through the mode the user named: a separate Codex CLI session or a subagent in the current conversation. Do not silently substitute one for the other.

Use the user's requested model ID. If none is specified, use `deepseek/deepseek-flash`. If the model is not exposed in the Codex model catalog named by `CODEX_HOME/config.toml` (default `%USERPROFILE%\.codex\config.toml`), report that instead of selecting another model or provider.

## CLI one-shot

Use this mode when the user asks for a separate Codex CLI session, or explicitly references `codex exec`.

1. Carry over only the relevant request, constraints, and context from this conversation. The CLI cannot see this chat automatically. Run it from the requested project directory, or the current workspace when none is specified.
2. Invoke `codex exec --model <deepseek-model-id> <prompt>`. Keep the user's existing Codex sandbox and approval settings; do not change global Codex or Magpie configuration, add keys, or use approval/sandbox bypass flags.
3. Make one CLI invocation per request. If the gateway, model, or CLI fails, report the error and stop; do not retry, switch to direct vendor API calls, or fall back to another model without the user's direction.
4. Return the CLI's result and identify the model used. Treat file changes and other effects according to the user's original request and the CLI's configured permissions.

## Current-session subagent

Use this mode when the user asks to call a DeepSeek subagent in the current conversation.

1. Call `collaboration.spawn_agent` with the requested DeepSeek `model` and `reasoning_effort: "high"` by default. Use a lower effort only when the user explicitly prioritizes cost or latency. Use `fork_turns: "none"` when overriding the model, so the child receives an explicit, bounded brief rather than an implicit copy of this chat. Prefer `agent_type: "default"`: role-pinned workers such as `luna-worker` lock another model and can reject a DeepSeek override.
2. Give the child the outcome, relevant context, allowed paths or side effects, completion criteria, and required return format. The child cannot infer missing context from this conversation.
3. For a capability probe, require one exact marker and consume the child's return with `collaboration.wait_agent`. Do not claim subagent support merely because the tool is present; the marker must arrive from the child.
4. If the model, gateway, or spawn fails, report the error and stop; do not silently switch model, provider, mode, or worker profile.
5. Report the model used, the collaboration tools called, and the child's returned result. Verify file changes and other effects according to the original request.
