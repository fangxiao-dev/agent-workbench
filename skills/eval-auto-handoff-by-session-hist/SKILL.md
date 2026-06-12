---
name: eval-auto-handoff-by-session-hist
description: >
  Evaluate whether a multi-session auto-handoff orchestration chain actually ran
  as designed, by auditing Codex session rollout histories against the skill
  contracts it claimed to follow (handoff-new-session, orchestrator, etc.).
  Use whenever the user provides Codex session ids, a handoff slug, or a time
  range and asks to 评价 / 复盘 / 审计 agent 调度是否按预期, review an
  orchestration relay chain, find stuck points or abandoned work across
  sessions, or grade handoff quality — even if they only say "看看这几个
  session 跑得怎么样". Reads conversation histories and handoff docs, never
  business code.
---

# Eval Auto-Handoff By Session History

把一条 auto-handoff 多 session 编排链的真实执行历史，对照其声称遵循的 skill 契约做元评审，产出证据可溯的评价报告：哪里卡壳、哪里偏离契约、哪里做得好、哪里值得简化。

评审对象是"调度行为"，不是业务代码质量。

## When To Use

- 用户给出一组 Codex session id（或 handoff slug / 时间范围），要求评价 agent 调度是否按预期。
- 用户要复盘一次 orchestrator / handoff-new-session 驱动的接力执行：卡壳点、放弃点、亮点、优化建议。

不要路由到这里：

- 只想总结单个 session 的内容：直接解析该文件即可，不需要本 skill 的链路还原与核验流程。
- 想沉淀可复用知识：用 `project-knowledge-curator`。
- 想审查 AGENTS.md / skill 文档本身的质量：用 `audit-agent-setup`。

## Core Principles

这些原则来自实战教训，是本 skill 的价值所在：

1. **用户声称的链序只是假设。** 实战案例：owner 给出的 5-session 清单实际是 6 环，且最后两环顺序颠倒——人对自己编排链的记忆不可靠。链路必须从证据重建，再反馈给用户。
2. **信封 lineage 不可信。** delegation prompt 里手写的 `source_thread_id` 可能每一跳都是上一环复制残留（实战案例里 6 跳全错，且每环的 handoff reviewer 都漏检了）。父侧 `create_thread` 的返回值与子侧 `session_meta.thread_source` 才是硬证据，二者应双向互证。
3. **主 session 只管调度与综合，digest 派给 subagent。** rollout 文件常达 ~1MB/个，全量进主上下文会挤掉综合分析的空间。每 session 一个并行分析员：digest 落盘、紧凑摘要回传。
4. **subagent 摘要是证词，实物才是证据。** 综合前必须亲自核验 commit 链、handoff 文件新鲜度、外部 tracker 状态。报告里每个论断都要能指向某个 digest 文件或实物。
5. **诚实规则。** 没问题不硬凑问题；同样重要的是把"未发现的问题类型"明确写出（如：无放弃方向、无 compaction、无死循环）——这是结论的一部分，不是废话。
6. **不读业务源代码。** 评的是调度，不是实现。真需要了解变更时从 commit message / diff stat 开始，而不是打开代码文件。

## Workflow

### 1. Ground

- 收集输入：session id 列表（标记为"声称顺序"）、工作 repo 路径、链条声称遵循的 skill。
- 定位 rollout 文件：`~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<session-id>.jsonl`，记录每个文件的创建时间与大小。session id 是 UUIDv7、按创建时间有序，可作首轮 sanity check——id 序与声称序矛盾时，标记待查证，不要直接替用户"纠正"。
- 建立 expected-behavior 基线：必读 `handoff-new-session` 的 SKILL.md；session 中实际引用的其他 skill（如 `orchestrator`）动态加入基线。把基线提炼成检查项清单，例如：commit-before-handoff、fresh git facts、handoff reviewer gate、create_thread-before-final、child First Progress Update、runner 只调度不实现。
- 创建评审工作目录：`<project-root>/agent-eval-<yyyymmdd>/`（放在 git 工作树之外，避免污染仓库），先写 `00-notes.md` 骨架，结构见 `templates/report-structure.md`。

### 2. Reconstruct The Chain

- 链路还原以双向硬证据为准：父侧 `create_thread` 返回的 thread id ↔ 子侧 `session_meta` 的 `thread_source` / 外层 delegation 信封。digest 分析员负责提取这些字段（见 step 3 的 prompt 模板）。
- 对账后产出链路表：环号 / session id / 运行窗口 / 时长 / 主要产出。
- 发现缺环（某环 spawn 的 id 不在用户清单里）：补派一个 digest 分析员处理缺环文件，链补全后再综合。
- 链头之前可能还有未提供的 session（比如运行 orchestrator 做规划/发 issue 的那个）。不在清单内就在报告中明确声明"未审计"，不要装作评过。

### 3. Parallel Digests

- 每个 session 派一个 general-purpose subagent，prompt 用 `templates/digest-subagent-prompt.md` 填充占位符；一条消息并行发出全部分析员。
- 分析员约束（必须写进 prompt）：用 Python 解析 JSONL（单行可超长，禁止用 Read 直读原始文件）；不读业务源代码；不嵌套派 subagent；digest 落盘到评审目录 + 回传 ≤600 字紧凑摘要。
- rollout 文件格式细节见 `references/codex-rollout-format.md`；可以让分析员自己读该文件，或把要点内联进 prompt。
- 摘要回传后，把关键事实（链位证据、摩擦点、合规结论）随手记入 `00-notes.md`，避免综合阶段回忆失真。

### 4. Independent Physical Verification

亲自核验，不转派——这是把"证词"升级为"证据"的一步：

- commit 链：`git log` 工作分支，逐条比对各环声称的 commit hash / message / 时间序。
- handoff 新鲜度：rolling handoff 文件的最后修改时间应早于且接近链尾 spawn 时间。
- 外部状态：`gh issue list` / `gh pr list` 核对护栏声称（如"issue 全部保持 OPEN、未 push、无 PR"）。
- HEAD 一致性：worktree 当前 HEAD vs handoff 声称的 expected HEAD。
- 公平性检查：批评"缺少 X"之前，先打开实物确认它真的没有 X（例如断言 rolling handoff 缺 lineage 记录前，先读它的全文结构）。

### 5. Synthesize The Report

- 三层产出，顺序固定：先在 `00-notes.md` 完成综合分析（findings 编号 F/G/R），再写正式 `REPORT.md`，最后在 chat 给完整报告。结构模板见 `templates/report-structure.md`。
- 排序与定性：问题按严重度排，并区分【系统性 / 一次性事故 / 轻微噪声】——一个每跳都复现的记账错误比一次自愈的工具失败严重得多，混在一起会稀释报告。
- 亮点必须有实证（reviewer 抓到了什么真缺陷、护栏在哪条命令上守住了），否则像客套。
- 建议（R*）标注成本，并指向它针对的 finding。
- headline finding 优先：如果链路还原本身推翻了用户的认知（缺环、倒序），把它放在报告最前面讲清楚。

## Output Contract

最终回复包含：

- 真实链路表，与声称清单的差异显式标出。
- 不好的（F*，按严重度）/ 好的（G*，有实证）/ 建议（R*，标成本）。
- 明确的"未发现"清单与"未审计"范围声明。
- 评审目录路径（`00-notes.md`、`session-*.md` digests、`REPORT.md`）。

## Quality Red Lines

- 不要按声称顺序直接开评——先重建链路。
- 不要没做实物核验就引用 subagent 结论下定论。
- 不要为了显得有洞察而放大轻微噪声；也不要为了客气而淡化系统性缺陷。
- 不要读业务源代码。
- 不要把范围外的 session 包装成已评审。
