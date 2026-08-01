---
name: call-claude
description: >
  Run one short-lived Claude CLI task for another skill. Use when a caller needs
  Claude execution with an explicit prompt and model configuration, without
  adding roles, permissions, or task-specific prompting. Slash: /call-claude.
---

# call-claude

Run `scripts/call_claude.py` when another skill needs one non-interactive
Claude CLI invocation. Each invocation starts a new process; context must be
passed explicitly in the prompt or caller-owned artifacts.

**调用流程：**启动 `call_claude.py` 后让它后台运行，主 session 立即继续执行不冲突工作，不要同步等待其最终 JSON。
只有在依赖 Claude 结果或到达验证控制点时才轮询/读取完成状态。

## Invoke

```powershell
python "<repo>\skills\call-claude\scripts\call_claude.py" `
  --cwd "<target-repo>" `
  --executable "<claude-executable>" `
  --prompt "Summarize this change." `
  --timeout-s 300 `
  --model claude-opus-4-6 `
  --effort high `
  --tools "" `
  --system-prompt "Return only the requested result." `
  --json-schema '{"type":"object"}' `
  --no-session-persistence
```

Provide exactly one of `--prompt` or `--prompt-file`. `--executable` (or
`CLAUDE_EXECUTABLE` in the repository-local `.env` or process environment)
pins a CLI; otherwise PATH discovery is used. All model configuration flags are
optional and are passed only when supplied. This skill does not set a role, tool
policy, sandbox, system prompt, schema, or persistence policy.

## Output contract

stdout contains exactly one JSON envelope:

```json
{
  "ok": true,
  "status": "completed",
  "text": "Claude's final result text",
  "usage": {},
  "exit_code": 0,
  "error": null
}
```

On CLI, authentication, timeout, permission, or output failures, `ok` is
false and `error` contains a stable `code` and diagnostic `message`. stderr is
reserved for child diagnostics. The caller owns any business-schema validation
or retry policy.
