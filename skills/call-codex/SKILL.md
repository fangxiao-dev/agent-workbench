---
name: call-codex
description: Recommend effective Codex CLI collaboration — resume continuation, streaming isolation, timely prompt adjustment, small-step discipline, fallback probing — and expose a programmatic envelope for downstream executors. This is collaboration guidance, not a thin CLI re-wrap.
---

# call-codex

本 skill 的定位是「**推荐与 codex CLI 更好的合作方式**」，不是「把 CLI 再包一遍」。协作模式全部来自 2026-08-24 fork 会话实测（见各节案例）；`scripts/call_codex.py` 仅保留给需要程序化 envelope 的一次性调用（如 discuss-ledger 的 downstream executor），协作场景一律走原生 CLI。

## 协作模式

### 1. 会话模型：exec 一次性 vs resume 续接

- `codex exec <prompt>`：一次性会话。适合短任务、探针、连接验证。
- `codex exec resume <session-id> <新prompt>`：**续接已有会话**，保留 in-context 状态（不用重读全部材料）。
- `codex exec resume --last [prompt]`：恢复最近会话；**并行多个会话时不可靠**（可能恢复到错误的会话），尽量用显式 session id。

**何时选 resume**：任务中断要续跑；发现方向/范围需要调整而上下文有价值（重新读材料成本高）；想在同一会话里追加指令。

### 2. 及时调整 prompt（发现不对就改，别等）

推荐流程（案例：B2A 整包 20 分钟零写入 → kill → resume 改三步小步，首提交 ee946ef2）：

1. 派发时定好「干预线」：例如连续 N 跳（tick）无 progress 行、无 commit，或与预期偏差明显；
2. 到线后**停掉 job**（`job_kill`）；
3. 取 session id：job 输出头部（`session id: <uuid>`），或 `~/.codex/sessions/<yyyy>/<mm>/<dd>/rollout-<ts>-<sessionid>.jsonl`（用文件名时间或内容 prompt 标记 grep 定位）；
4. `codex exec resume <id> "<调整后的 prompt>"`：明确「继续原任务 + 本次调整点」（如：改小步、换范围、补真实契约）。

案例 B2B：给语义契约但缺真实类型时，worker 正确拒绝猜接口——**不要让它猜**；等上游契约落地（commit）后 resume 带真实类型。

### 3. 流式与上下文隔离

- `codex exec --json`：stdout 为 **JSONL 事件流**（含 `message_delta` 增量）。
- **后台 job 运行即隔离**：输出进 job 的 stdout，主 session 只读尾部，不会污染对话上下文——**不需要为了隔离再包一层 subagent**（除非还要自动重试/解析归纳逻辑）。

### 4. 小步合作纪律（给 worker 的 brief 要求）

- progress-file：每完成一个 bounded 步骤**立即**追加一行（不要最后才写）；主 session 靠它判断死活；
- commit 小步：每步可独立验证即提交，避免巨型未提交变更；
- brief 必备：source_unit、成功条件、禁改路径、文件列表、一条验证命令、禁区、最终 envelope 格式；
- 缺真实接口类型时让 worker 停下报告，不要猜（见案例 B2B）。

### 5. 降级与探针

- subagent/会话卡顿 → `codex exec` 直连（本会话实测：probe 秒级响应）；
- 连接探针：极简 prompt（如 "Reply with exactly: PROBE_OK <cwd>"）验证模型后端连通，区分「连接问题」与「worker 会话问题」。

## 参数事实表（已实测，codex 0.149.0）

| 用法 | 结果 |
| --- | --- |
| `-m gpt-5.6-luna` | 模型选择有效 |
| `-c 'service_tier="fast"'` | fast tier 有效 |
| `--approve-for-me` | 自动批准（自带 workspace-write 沙箱）；**与 `-s <mode>` 互斥**，不能同用 |
| 默认（无 `-s`） | workspace-write 沙箱 + approval on-request/auto_review（依 `~/.codex/config.toml`） |
| `--enable subagents` / `--enable threads` | 0.149.0 未知 flag（`Unknown feature flag`）；不要依赖 CLI 内建线程，fan-out 走编排层 |
| `--json` | JSONL 事件流（流式） |
| `--skip-git-repo-check` | 跳过 git 仓库检查（只读 review 等场景可用） |
| 只读审查 | `-s read-only`（与 `--approve-for-me` 互斥，二选一） |

注：`--enable <feature>` 的合法 feature 名随版本变化，用前先验证；未在本表的行为以 `codex exec --help` 为准。

## 程序化 envelope 用法（保留，供 downstream executor）

`scripts/call_codex.py` 为需要**统一 JSON envelope**（`ok/status/text/usage/exit_code/error`）的一次性调用提供服务（discuss-ledger orchestrator 等下游 executor 依赖该契约）。它是 **ephemeral 一次性通道**（永不 resume）——**协作模式走原生 CLI，不要用 wrapper 包 resume/流式**。

```powershell
python "<repo>\skills\call-codex\scripts\call_codex.py" `
  --cwd "<target-repo>" `
  --prompt-file "<prompt-file>" `
  --timeout-s 1800 `
  --model "gpt-5.6-luna" `
  --config 'model_reasoning_effort="max"' `
  --config 'service_tier="fast"' `
  --sandbox read-only `
  --ephemeral `
  --output-schema "<schema.json>"
```

Pass exactly one of `--prompt` or `--prompt-file`. Repeat `--config` for multiple Codex `-c` settings.

**Do not pass `--executable` unless you have a specific reason.** Discovery already picks
the right CLI, in this order: `CODEX_EXECUTABLE` (repository-local `.env` or process
environment) -> a PATH `codex.cmd` / `codex` that is not the non-executable WindowsApps
package resource -> the newest per-user Desktop binary under
`%LOCALAPPDATA%\OpenAI\Codex\bin\`, including its hashed subdirs. Where Codex is
installed through Volta, PATH resolves to the Volta shim, which is what you want.

In particular, never hardcode `%LOCALAPPDATA%\OpenAI\Codex\bin\codex.exe`. That top-level
file is a stale leftover; the desktop app self-updates its real binary inside a hashed
subdir. Pinning the stale one produces misleading failures that all look like config
errors: a valid `~/.codex/config.toml` gets rejected key by key
(`model_reasoning_effort`, `service_tier`, `[agents]`), and newer models fail with HTTP
400 `"requires a newer version of Codex"`. If a config value is rejected, suspect the
binary version before editing the user's config. The wrapper emits exactly one JSON envelope on stdout; diagnostics go to stderr. Each invocation launches a new Codex process and never resumes or shares a session.

## Background launch guardrail

When launching the wrapper with PowerShell `Start-Process`, the wrapper script
must be the first item in `-ArgumentList`. Do not pass wrapper flags directly to
`python`; that starts Python itself and produces errors such as `unknown option
--prompt` without invoking this skill.

```powershell
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$wrapper = Join-Path $repo 'skills\call-codex\scripts\call_codex.py'
if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) { throw "Missing wrapper: $wrapper" }

$wrapperArgs = @(
  $wrapper,
  '--cwd', $targetRepo,
  '--prompt-file', $promptFile,
  '--timeout-s', '1800'
)
if ($wrapperArgs[0] -ne $wrapper) { throw 'Wrapper path must be the first Python argument' }

Start-Process -FilePath $pythonExe -ArgumentList $wrapperArgs -WindowStyle Hidden -PassThru
```

Prefer `--prompt-file` for background calls so PowerShell quoting and multiline
prompt content cannot change the argument vector. Check the returned envelope
and process exit code before treating the task as dispatched or completed.

## 变更说明

- 2026-08-24：定位从「CLI 包装」重定位为「Codex 协作模式推荐」（resume 续接、流式隔离、及时调整 prompt、小步纪律、降级探针；全部来自 fork 会话实测）。wrapper 与 envelope 契约零改动，仍服务 discuss-ledger 等 downstream executor。
