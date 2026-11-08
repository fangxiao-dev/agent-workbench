---
name: call-ds-in-claude
description: 把一个任务交给 DeepSeek 驱动的 `claude -p` 子进程执行,当 subagent 用;输出过程日志(工具调用/结果/最终回答),不含 thinking。用户要求用 DeepSeek 跑任务、外包调研/整理/批量读码时使用。
---

# call-ds-in-claude

起一次性 `claude -p`,模型走 DeepSeek 的 Anthropic 兼容端点(默认 `deepseek-v4-flash`)。
环境变量只设在子进程内;默认每次是新进程,上下文必须写进 prompt;要延续上下文用 `-Resume`(会话历史会存在本机 `.claude/projects`)。
同一任务 scope 内上下文可复用时(追问、补改、基于它刚读过的材料继续、超时后续跑),优先 `-Resume` 而不是起新进程重新交代背景;换了任务或旧上下文已经污染/过长时再起新的。

## 调用

```powershell
pwsh -NoProfile -File "$HOME\.claude\skills\call-ds-in-claude\scripts\call-ds.ps1" -Prompt "<任务>" -Cwd "<目录>"
```

prompt 长或含引号时用 `-PromptFile <文件>`。耗时长就用 Bash/PowerShell 的 `run_in_background`,完成会通知。

## 参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `-Prompt` / `-PromptFile` | 必填其一 | 任务文本 |
| `-Cwd` | 当前目录 | 子进程工作目录,它能读到这里的文件 |
| `-Model` | `deepseek-v4-flash` | 同时映射到 Haiku/Sonnet/Opus 与子代理档 |
| `-Permission` | `acceptEdits` | 要让它无人值守跑 Bash 用 `bypassPermissions`;只读任务用 `plan` |
| `-Tools` | 全部默认工具 | 如 `Read,Grep,Glob` 限制为只读 |
| `-Resume` | 无 | 续接上次会话:传 `[done]` 行里的 `session=` 值,且 `-Cwd` 必须与上次相同 |
| `-ClipChars` | `400` | 日志里每条工具结果的截断长度 |
| `-IdleTimeoutSec` | `900` | 连续这么久没有任何输出行就杀掉子进程树并退出(exit 2),`[timeout]` 行带 `session=` 可 `-Resume` 续跑;`0` = 不限 |
| `-HeartbeatSec` | `60` | 静默超过该秒数输出一行 `[hb] elapsed/idle/events`;`0` = 关闭 |

## 输出

按时间顺序逐行:`[init]` 模型与目录 → `[tool]` 调用 → `[result]` 工具结果(截断) → `[text]` 中间文字 →
`[done]` 耗时与实际模型 → `---` 后是最终回答。异常结束(无结果)也会补一行 `[done] error=True no-result`,退出码非 0。thinking 不输出。

## 注意

- 内容会发给 DeepSeek 服务端:不要给它 `.env`、密钥、真实客户数据。用 `-Tools Read,Grep,Glob` 时先确认 `-Cwd` 范围。
- 它的结论按外部输入核对后再采纳,不直接写入权威文档或代码。
- Key 读 `DEEPSEEK_API_KEY`,否则读 `~\.claude\secrets\deepseek.key`;不要打印。
- claude 可执行文件:优先 PATH(非 Volta),否则取桌面应用自带的最新版;可用 `CLAUDE_EXE` 覆盖。
