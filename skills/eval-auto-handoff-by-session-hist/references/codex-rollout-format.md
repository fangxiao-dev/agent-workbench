# Codex Rollout File Format Notes

供 digest 分析员解析 Codex CLI session 历史文件时参考。schema 随 CLI 版本演进，**先抽样几行核实，再写提取脚本**——以下是已验证可用的要点，不是冻结规范。

## 定位

- 路径模式：`~/.codex/sessions/YYYY/MM/DD/rollout-<ISO时间戳>-<session-id>.jsonl`
- session id 为 UUIDv7：id 字典序 ≈ 创建时间序，可作链序 sanity check。
- 文件创建时间 = session 启动时间；大小常见 200KB–1MB。

## 行结构

每行一个 JSON 对象，典型字段：`{"timestamp": "...", "type": "...", "payload": {...}}`。

常见 `type`：

- `session_meta`：session 元信息——`cwd`、originator、CLI 版本、**`thread_source`**（`user` = 人工启动，`subagent` = 被派生）、**`source_thread_id`**（父 thread id）。链路还原的子侧硬证据在这里。
- `turn_context`：每 turn 的模型/配置上下文。
- `response_item`：模型侧条目，`payload.type` 细分：
  - `message`：`role` 为 `user`（含 owner 插话与 delegation 信封）或 `assistant`（可见回复），`content` 为数组。
  - `function_call`：工具调用，`name` + `arguments`（如 shell、apply_patch、update_plan、multi_agent 系列、`create_thread`）。
  - `function_call_output`：工具结果。**`create_thread` 的 output 含新 thread id——链路还原的父侧硬证据。**
  - `reasoning`：推理摘要（可能为空，空摘要本身是审计性 finding）。
- `event_msg`：事件流（`user_message` / `agent_message` / `token_count` 等），与 response_item 部分冗余；token_count 可用于评估上下文压力。
- `compacted`：上下文压缩事件——出现即是重要摩擦信号。

## Lineage 证据等级

| 证据 | 位置 | 可信度 |
| --- | --- | --- |
| `create_thread` 返回的 thread id | 父 session 的 function_call_output | 硬证据 |
| `session_meta.thread_source` / `source_thread_id` | 子 session 首行附近 | 硬证据 |
| delegation 信封里手写的 `source_thread_id` | 子 session 首条 user message 正文 | **不可信**——实战中曾出现整条链每一跳都是上一环复制残留 |

双向互证：父侧 create_thread 返回值应等于子 session id；对不上或缺环时以父侧返回值为准。

## 解析要点

- 单行可极长（嵌入整份文档/diff），不要用文件读取工具直读；用 Python 逐行 `json.loads`，输出时截断长字段（如 >500 字符）。
- 建议流程：① 统计各 type/payload.type 分布 → ② 全量提取 user message（owner 插话 + 信封）→ ③ 提取 function_call 名称 + 截断参数、function_call_output 截断结果 → ④ 按 timestamp 重建时间线，标注相邻事件的异常间隔（worker 长跑 / wait 超时的信号）。
- 摩擦信号检索词：错误码、`timed out`、`compacted`、重复出现的同一失败命令、`Unknown projectId`（create_thread 拒绝未注册路径）。

## 扩展点

本 reference 只覆盖 Codex rollout。若需评审 Claude Code session（`~/.claude/projects/<project-slug>/*.jsonl`），格式不同，需先抽样调研后另写解析要点，不要套用本文件的字段名。
