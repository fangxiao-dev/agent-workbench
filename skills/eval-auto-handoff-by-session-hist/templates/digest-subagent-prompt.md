# Digest Subagent Prompt Template

每个 session 派一个 general-purpose subagent，用本模板填充占位符。一条消息并行发出全部分析员。

占位符：

- `{CHAIN_POSITION}`：本环在链中的声称位置，如 `链中第 2 环（用户声称顺序）`；若声称位置与文件创建时间矛盾，在此处写明矛盾并要求分析员优先还原真实链位。
- `{SESSION_FILE_PATH}`：rollout JSONL 绝对路径。
- `{CHAIN_TABLE}`：全链 session id + 文件创建时间列表（用于交叉核对 thread id）。
- `{REPO_PATH}`：工作 repo 根路径（含 worktree 说明，如有）。
- `{BASELINE_CHECKLIST}`：从基线 skill 提炼的契约检查项（Ground 阶段产出）。
- `{ROLLOUT_FORMAT_REF}`：本 skill `references/codex-rollout-format.md` 的绝对路径。
- `{DIGEST_OUTPUT_PATH}`：digest 落盘路径，如 `<eval-dir>/session-2-<id前8位>.md`。

---

## Prompt 模板

```text
你是一次 AI agentic engineering 元评审的分析员。任务：深度消化一个 Codex CLI session 历史文件，产出结构化 digest。这是 {CHAIN_POSITION}。

## 目标文件
{SESSION_FILE_PATH}

## 编排链上下文（用于交叉核对 thread id）
{CHAIN_TABLE}
请特别留意本 session 中 create_thread / fork_thread 调用返回的 thread id，以及 session_meta 的 thread_source / source_thread_id，用于还原真实交接链。信封里手写的 source_thread_id 可能是复制残留，不可直接采信。

## 方法要求
- 文件是 JSONL，单行可能极长。不要用 Read 工具直接读原始文件；用 Python 脚本解析（json.loads 每行，截断长字段）。先抽样几行搞清 schema，再写提取脚本；格式要点见 {ROLLOUT_FORMAT_REF}。
- 不要读业务源代码文件。可以只读 session 中引用到的 markdown 文档（docs/exchange/handoffs/*、plans/* 等）作为佐证，repo 在 {REPO_PATH}。
- 不要再派 subagent。

## 需要提取的内容
1. session_meta：cwd、model、起止时间、thread_source、source_thread_id、总 turn 数。
2. 首条 user prompt 要点；若是 handoff continuation prompt，对照以下基线契约逐项判断：
{BASELINE_CHECKLIST}
3. 之后每条 user（owner）插话：时间 + 内容摘要——这反映人工干预程度。
4. 时间线：主要阶段（带时间戳），做了什么。
5. child 行为符合度：第一条可见回复是否 First Progress Update？是否先验证 git status/log 与 handoff expected HEAD 一致？之后是否自动持续推进而不是停下等指令？实现是否派给 subagent 而主 session 只做调度/seaming？
6. Subagent / multi_agent 调用清单：角色（worker/reviewer/explorer）、任务、结果、返工轮次、是否 wait/send_input、用完是否 close。
7. create_thread / fork_thread 调用及返回的 thread id（链路硬证据）。
8. 外部副作用：git commit（messages）、gh issue/PR 操作、关键文档写入（尤其 rolling handoff 的更新）。
9. 摩擦信号（重点）：报错、同一命令反复失败（≥2 次）、权限/审批阻塞、wait 超时、上下文 compaction 事件、token 压力、放弃的尝试（开了头又丢掉的方向）、明显绕路、长时间停顿（相邻事件 timestamp 间隔异常）、lineage/source_thread_id 记账错误。
10. 结束状态：最后的 assistant 汇报内容、handoff 收口是否合规（commit before handoff、fresh git facts、reviewer gate、create_thread before final）、遗留项、本环是否链终点。

## 输出
1. 详细 digest（建议 150-400 行，带时间戳时间线 + 上述各节）写入：
   {DIGEST_OUTPUT_PATH}
2. 最终回复返回 ≤600 字中文紧凑摘要：mission、实际链位（被谁 spawn / spawn 了谁，附证据）、Top3 摩擦点、Top3 亮点、对照基线契约的符合度结论。
```
