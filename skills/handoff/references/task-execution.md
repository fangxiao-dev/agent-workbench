# 执行型 handoff

只在下一 session 要继续代码、测试、implementation package、migration、审计收口或其他 live worktree 任务时读取。目标是交付一个可验证的 bootstrap packet，让新 session 锚定后立即进入当前执行面，而不是重放历史。

## Bootstrap packet

默认把 handoff 控制在一屏左右；复杂任务也只增加会改变首轮执行判断的事实。包含：

- exact worktree、branch、HEAD/expected HEAD、package、sidecar digests、current binding；
- dirty count + porcelain metadata digest，不列完整文件名，也不把它误作内容一致性证明；
- Ticket/任务状态计数、gate 数量和 package closed 状态；
- preflight 是否已完成、授权是否变化，以及本轮是 restore validation 还是新建/更新授权包；
- 当前授权、仍禁止的 mutation、必须串行化的资源；
- 当前 active seam、首个动作、不要重复和暂不读取的材料；
- aborted/timeout/partial 操作，以及它们是否产生可用 evidence。

不要在 handoff 中枚举后续可能使用的 skills。只写首轮必须立即进入的唯一 entry point；延后 skill 由实际执行 seam 触发，避免新 session 因显式名称提前加载多个 skill。

需要记录 delegation 时，只记录当前 bounded task 的单一入口：investigate / implement 使用 `$investigate-before-implement`，独立 review 使用 `$reviewer`；路由、模型与推理强度采用全局 skills 定义，不在 handoff 中重复。

## 分层读取

### Wave 1：anchor / preflight

handoff 默认是权威可信的 task-scoped owner input，可直接承载事实、控制图和授权边界。Machine anchor 只检查 freshness，不负责重新证明 handoff 的授权来源。Exact worktree、HEAD、package、binding、sidecar digest 与 runtime counts 匹配时，直接使用 control map；只读取当前 entry point、runtime sidecar 和 current binding，不为重复证明而展开 decision/spec/plan、Ticket 全文、历史 ER、evidence、investigations 或 registry。若 handoff 已记录 preflight 完成且授权 envelope 未变化，本轮是 restore validation，不重复读取授权 contract；只有新建/更新授权包或出现授权缺口时才加载。Machine anchor 不匹配时降级核查对应来源。

优先运行 `scripts/compact_anchor.py`，只把 compact JSON 放进上下文。`porcelainDigest` 哈希 Git porcelain v2 的状态、mode、OID 与路径 metadata，不证明工作区文件内容一致，也不作为 restore authorization 条件。首次不输出 dirty 文件列表；只有 digest 不匹配、发现 write-set 冲突、需要定位具体文件或 owner 明确要求时才展开 `git status --short --untracked-files=all`。脚本只运行只读的 canonical `contract-status`，并在 package transaction journal 活跃或前后快照不一致时 fail-closed；可能写入 Git object 或恢复/清理 registration journal 的 `validate --working-tree` / `validate --committed` 延后到正式执行 wave。

若本轮要求“锚定/preflight 后暂停”，当前执行单元就是 anchor/preflight；Node/package manager、DB/container/port、`.env`、browser/provider identity 等未来执行资源不是本轮启动前置，除非 plan 或 owner 明确要求在暂停前检查。

### Wave 2：正式执行 control map

Owner 触发正式执行后，Decision、Spec、Plan 和全部 Ticket 必须进入主 session 的控制面，但不等于一次性读取全部正文和历史。按当前 revision 提取：

- Decision：当前 scope、non-goals、owner decisions、禁止边界；
- Spec：acceptance semantics、authority/recovery、安全边界和 AC → Ticket 映射；
- Plan：当前执行策略、依赖、验证/收口职责、最新 resume/start ER；历史 ER 只按需查证；
- Tickets：先建立全局 metadata matrix（ID、状态、依赖、AC、evidence entry），只展开当前 active Ticket 正文。

把上述内容压成一份内存 control map；不要创建第二份 canonical 文档，也不要在后续轮次重复加载未变化的章节。

首次执行依赖 binding 的写操作、ER、Ticket acceptance 或 gate 前，运行对应上下文的 canonical `validate --working-tree` / `validate --committed`，只保留 compact verdict。

### Wave 3：按 Ticket 增量展开

开始某个 Ticket、acceptance、claim audit 或 gate 时，再读取对应 spec 章节、Ticket 正文、源码/测试和 evidence。`evidence/`、`investigations/`、registry、历史日志与 provider artifacts 只在当前验收或 seam 需要时加载。Node/package manager、DB target、fixture namespace 和 cleanup owner 只在对应测试 wave 前检查。

## Compact anchor

运行：

```text
<python> <handoff-skill>/scripts/compact_anchor.py --worktree <absolute-worktree> --expected-head <sha> --package-path <package-relative-path>
```

`<python>` 表示宿主机的 Python 3 launcher（Windows 通常为 `python`，POSIX 通常为 `python3`）；skill 不提供 host-specific wrapper。输出只包含 anchor、dirty counts/porcelain digest、sidecar digests、current binding、runtime Ticket/gate counts 与只读 canonical contract-status verdict，不包含文件名、secret 或连接串。需要审查实际 diff 时再展开路径。

## 阶段语义

- `implemented`：代码或文档已经存在，不代表运行通过；
- `verified`：指定命令在当前 revision 通过，不代表 Ticket acceptance；
- `accepted`：主 session 已按 Ticket 规则登记 direct evidence；
- `closed`：claim audit、terminal gate、最终集成等要求均完成，machine state 已关闭。

优先报告计数和 machine-state 来源。上游阶段完成不能改写为整个任务完成。

## 不匹配与停止条件

权威 handoff fast path 在 HEAD、package containment、binding、sidecar digests、runtime counts 与只读 canonical contract-status verdict 一致时成立；dirty `porcelainDigest` 只决定是否需要展开路径。发生不匹配时，先展开冲突对应的 artifact，不自动全量重读。产品语义冲突、目标环境不明、shared/production mutation 或超出授权时停止并请求 owner。Ticket acceptance、claim audit、gate 和最终集成仍由主 session 收口。
