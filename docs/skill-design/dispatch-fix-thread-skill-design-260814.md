# `dispatch-fix-thread` Skill 设计

## 1. 文档状态

- 日期：2026-08-14。
- 状态：已被 [`dispatch-fix-skill-design-260814.md`](dispatch-fix-skill-design-260814.md) 取代；旧 Skill 保存在 `skills-deprecated/dispatch-fix-thread/`。
- 目标仓库：`agent-workbench`。
- 目标 Skill：`skills/dispatch-fix-thread/`。
- 当前阶段：历史设计，仅用于审计独立 fixer task 方案。

## 2. 目的

当 parent thread 在开发和 review 后得到一组已确认 bugs 时，允许它把完整修复活动交给一个新的 fixer thread。fixer thread 独立承担分组、worktree 隔离、subagent 派发、聚焦验收和 fix branch 集成；parent 保留容量，只在交付时接回 fixer branch 并运行尚未覆盖的剩余验证。

本 Skill 解决的是一次有界修复活动的委派与回收，不是通用 thread 编排系统。

## 3. 直接背景

现有一次实际流程中：

- parent task `019ffd37-c4e4-7de3-b2a8-cb9de82b36c5` 在 terminal review 后派发 fixer task；
- fixer task `019fff77-5074-7521-aeca-b58fccaea2f3` 使用四个 `@luna-worker` 并行修复七个 findings；
- 四个 worker 没有获得显式隔离的 group worktree，commit 和中间 dirty diff 直接出现在 fixer 当前分支/工作树；
- 其中一个 worker 在 commit 已落入当前分支后仍未提供完整交付说明。

这说明 fresh subagent invocation 不等于 Git 隔离。新的 Skill 必须显式建立 fixer worktree 与 group worktree，而不能把隔离寄托在 subagent runtime 的默认行为上。

## 4. 已确认的设计选择

1. 使用独立 fixer thread，原因是保护 parent 的上下文与执行容量。
2. 不依赖 `thread-harness`，也不读取其 registry、profile、H1、poll、seam 或 budget 合同。
3. 主要复用：
   - `subagent-driven-development` 的 worker strategy、parallel admission、fresh invocation 与结构化交付结果；
   - `git-workflow` 的 integration base、dirty-state、branch ownership、冲突与安全边界。
4. `git-workflow` 不负责 worktree 创建、cherry-pick、commit 或把 task branch merge 回 parent；本次修复需要的这些动作由本 Skill 在明确边界内拥有。
5. fixer branch 始终从 parent review 时的 immutable `reviewed_head` 创建。
6. parent worktree 中的未提交内容不复制、不 stash、不清理，也不进入 fixer 的修复分支。
7. group 是并行调度、worktree ownership、commit range、cherry-pick 和聚焦验收单位。
8. bug 是 group 内的 acceptance point，不要求每个 bug 独立 commit 或独立 cherry-pick。
9. live bookkeeping 位于当前用户的临时目录，由 fixer 单写；subagent 不写，parent 在 dispatch 后只读。
10. 先运行轻量 v1。规则和脚本向 agent 提供工具、边界与判断依据，不把流程编码成逐步教学或复杂状态机。

## 5. 目标

- parent 只需显式调用 `$dispatch-fix-thread` 即可把这次修复交给 fixer thread。
- fixer thread 可以只靠 immutable request、当前 state 和 Git anchors 恢复工作。
- 每个并行 group 使用独立 branch 和 worktree；任何两个写 worker 不共享工作树。
- fixer 可以为每个 group 调用 `subagent-driven-development`，并在 group 结果返回后做聚焦验收。
- fixer 把已接受的 group commit range 集成到自己的 fix branch。
- 所有 group 被接受后，fixer 在 bookkeeping 中记录最终 commit range，并向 parent 发送简短完成消息。
- parent 根据 terminal receipt 接回 fix branch，不重复 fixer 已取得的聚焦验证，只运行事先保留的剩余验证。

## 6. 非目标

- 不做通用 thread controller、task DAG、心跳服务或常驻监控器。
- 不实现 `thread-harness` 的精简版或兼容层。
- 不把 bookkeeping 设计成 event-sourced workflow engine。
- 不要求 parent 持续调用 thread API 观察 fixer 或 subagent。
- 不跨主机共享 temp ledger 或 worktree；v1 仅支持同一台本地主机。
- 不授权 push、PR、deployment、远程数据库、真实 provider 或其他外部副作用。
- 不在 v1 自动删除修复分支；清理由后续明确动作处理。

## 7. Skill 形状与上下文隔离

建议目录：

```text
skills/dispatch-fix-thread/
├── SKILL.md
├── references/
│   ├── parent.md
│   └── fixer.md
└── scripts/
    └── bookkeeping.py
```

### 7.1 根 `SKILL.md`

根文件是薄路由，只包含：

- Skill 的 job、显式触发方式和共同安全边界；
- invocation 的 role/action 判定；
- 指向唯一角色文件的条件 pointer；
- 每条路径的可观察完成条件。

根文件不内联 parent 和 fixer 的完整流程，也不复制 `subagent-driven-development` 或 `git-workflow` 的合同。

### 7.2 角色路由

```text
role=parent, action=dispatch
  -> 只读取 references/parent.md 的 dispatch 分支

role=fixer, action=run|resume
  -> 只读取 references/fixer.md

role=parent, action=integrate
  -> 只读取 references/parent.md 的 integrate 分支
```

fixer 不读取 parent 的派发或最终集成设置。parent 不读取 fixer 的分组、subagent、返工或中间 Git 操作。subagent 不加载本 Skill，只接收当前 group 的 bounded brief。

如果实现时发现 `parent.md` 的两个分支仍造成明显无关上下文加载，再按 invocation 拆为 `parent-dispatch.md` 与 `parent-integrate.md`；v1 不为文件数量预先拆分。

## 8. Invocation 与授权

本 Skill 默认只接受显式调用，因为它会创建 Codex task、branch 和 worktree。

### 8.1 调用门槛

默认只在 review 去重后确认至少四个需要修改业务代码的 bugs 时使用。parent 用它释放上下文和执行容量，把整组修复交给 fixer thread。

以下情况默认留在 parent 处理：

- 三个以内的 P2 小 bug；
- 只修改文档、证据或进度记录；
- 单个局部、可以快速完成的修复；
- findings 尚未确认，仍需调查或裁决。

少量 P1 或高风险 bug 不自动触发，但 Owner 可以显式调用覆盖默认门槛。计数只包含去重后的业务代码 bugs，不包含文档修正或重复 finding。

### 8.2 Parent dispatch 输入

parent 必须能提供或解析：

- repository root；
- immutable `reviewed_head`；
- parent 当前 branch 与 thread id；
- 已确认 findings 的稳定 ID、摘要和 acceptance points；
- findings 的来源路径（存在权威文档时）；
- fixer 可以修改的范围；
- fixer 负责的聚焦验证；
- parent 保留的剩余验证；
- 明确排除的本地、远程和外部副作用。

`request.json` 保存上述 finding 内容本身，不能只保存一个以后可能变化的文档路径。

显式 dispatch 授权以下本地动作：

- 从 `reviewed_head` 创建一个 fixer branch/worktree；
- 创建一个正常的本地 Codex fixer task，并把它锚定到 fixer worktree；
- fixer 为已接收 findings 创建 group branches/worktrees；
- fixer 在 group worktree 中派发 subagent；
- fixer 将被接受的 group commit range cherry-pick 到 fixer branch。

该授权不包含 parent 最终 merge。parent 在收到 terminal receipt 后显式调用 `action=integrate`，才授权把 fixer branch 本地集成回当前 parent branch。

用户在 parent 中只写 `$dispatch-fix-thread` 时默认执行 dispatch。fixer thread 收到的任务说明必须显式带上 `role=fixer` 和本次修复记录目录；parent 最终接回时显式使用 `action=integrate` 和记录目录。

## 9. Parent 合同

### 9.1 Dispatch

parent 的职责止于建立可靠交付边界：

- 验证 `reviewed_head`、repository 和 dirty-state 边界；
- 创建 immutable request；
- 创建 fixer branch/worktree 和正常 fixer task；
- 把 request 路径、fixer worktree、expected HEAD 与 parent thread id 交给 fixer；
- 在 fixer 确认锚点后结束主动协调。

dispatch 成功的可观察结果是：parent 获得 `fix_id`、记录目录绝对路径、fixer thread id、fixer branch/worktree 和已确认的 anchor receipt。

修复分支/worktree 已创建但 fixer task 创建失败时，parent 报告派发未完成并保留这些内容供重试，不再创建第二套。fixer task 已创建但锚点未确认时，不发送修复任务正文。

### 9.2 正常等待

parent 不启动 poll loop，也不读取 subagent 状态。后续只有三类入口：

- fixer 主动发来 ready 或 blocked 消息；
- Owner 主动询问进度；
- parent 因其他原因被唤醒并选择读取 bookkeeping。

没有 heartbeat 时，`updated_at` 只能在 parent 被唤醒后用于判断停滞，不能提供主动挂死检测。

### 9.3 Integrate

parent 只消费脚本输出的 terminal projection：

- 本次修复状态；
- `reviewed_head`、fixer branch、fixer head 与 commit range；
- group acceptance 摘要；
- fixer 已运行的聚焦验证；
- parent 仍需运行的剩余验证；
- blocker（若有）。

只有 `status=ready` 且 Git anchors 一致时才允许本地集成。parent 只做机械检查：所有 findings 都有结论、source/integrated commits 能对应、fixer diff 没有越出允许范围、fixer worktree clean。这些检查不重复执行聚焦测试。

parent 通过本地 merge 接回 fixer branch，具体采用 fast-forward 还是 merge commit 服从目标仓库惯例。parent worktree 有未提交内容或 merge 发生冲突时，按 `git-workflow` 停止并报告，不自动 stash、clean 或猜测解决方式。若 parent 在 `reviewed_head` 之后修改了 fixer 涉及的相同路径，parent 需要重跑受影响的 focused checks；没有路径重叠时只运行 remaining verification。parent 继续拥有最终 acceptance、Gate、merge 后记录和发布判断。

## 10. Fixer 合同

fixer 是修复活动的 controller，但不是新的需求 owner。它消费 parent 已确认的 findings，不重新裁决需求、扩大范围或修改 parent 的验收边界。

fixer 应达到以下结果，而不是照读固定步骤：

- findings 被组织成可以安全并行或串行处理的 groups；
- 每个并行 group 有独立 branch/worktree、明确 acceptance points 和 write ownership；
- 每个 group 通过 `subagent-driven-development` 获得具体 worker strategy；
- worker 结果的 commit range、scope 和局部证据可以归因；
- fixer 对 group 的全部 bug acceptance points 做聚焦验收；
- accepted group 被集成到 fixer branch；
- bookkeeping 在有意义的事实变化后更新；
- 本次修复最终为 `ready` 或带具名原因的 `blocked`。

### 10.1 Group 与 bug

- group 是一个共享 worktree/branch 和一次聚焦验收的边界。
- bug 是 group 内需要逐项确认的 acceptance point。
- group 可以有一个或多个 commits，交付时必须给出连续、可验证的 commit range。
- group 任一 acceptance point 未满足，整个 group 尚未 accepted。

### 10.2 Worker

fixer 为每个 group 形成 `subagent-driven-development` strategy。worker brief 至少包含：

- group id 与 bug acceptance points；
- exact worktree 与 branch；
- write ownership 和明确排除项；
- 预期聚焦验证；
- 完整交付说明与 commit range 要求。

完整交付说明只要求 commit 列表、修改范围、验证结果，以及每个 bug acceptance point 的结论。subagent 没有提供这些内容时，fixer 不合入结果：已有 commits 可以交给 fresh subagent 在干净 worktree 重新检查；只有未提交修改时保留原 worktree，并另开干净 worktree 重做。

worker 不读取本次修复的记录文件，不联系 parent，也不更新 fixer branch。返工使用 fresh invocation；工作上下文通过 group worktree、Git 和新的 bounded brief 传递，不依赖旧 worker 的私有上下文。

### 10.3 Git 集成

- fixer branch 以 `reviewed_head` 为唯一初始基点。
- 每个 group 记录自己创建时的 Git base；同时运行的 groups 必须具有互不重叠的 write ownership 和可变资源。
- fixer 在接受 group 前验证 commit range、write scope 和聚焦证据。
- group 通过后，fixer 将其 commit range cherry-pick 到 fixer branch，并在 fixer worktree 做 group-focused acceptance。
- group worktree 中的 source commits 与 cherry-pick 后 fixer branch 上的 integrated commits 分开记录，并保持顺序对应。
- cherry-pick 冲突时中止该 cherry-pick，保留干净 fixer branch，把冲突事实作为新的 bounded repair 输入交给 fresh worker。
- cherry-pick 后的聚焦验收若失败，fixer 暂停继续集成其他 groups，并让 fresh worker 提供纠正 commits；不把当前 fixer branch 交给 parent。

这些是安全边界和结果要求，不要求 agent 严格按固定命令序列执行。具体 Git 命令继续受 repository instructions 与 `git-workflow` 约束。

## 11. Bookkeeping

### 11.1 位置与 ownership

运行目录：

```text
%TEMP%\dispatch-fix-thread\<fix-id>\
```

文件：

```text
request.json   # parent 创建一次，之后 immutable
state.json     # fixer 创建并单写
```

subagent 不写任何记录文件。parent 在 dispatch 后只读 `state.json`。

### 11.2 轻量状态

不定义完整状态机。`state.json` 只保存当前可恢复事实：

```json
{
  "fix_id": "<id>",
  "status": "working | ready | blocked",
  "updated_at": "<ISO-8601>",
  "fixer": {
    "thread_id": "<id>",
    "worktree": "<absolute-path>",
    "branch": "<branch>",
    "head": "<sha>"
  },
  "groups": [
    {
      "id": "<stable-id>",
      "bugs": ["<finding-id>"],
      "base": "<sha>",
      "worktree": "<absolute-path>",
      "branch": "<branch>",
      "worker": "<logical-reference-or-session>",
      "source_commits": ["<sha>"],
      "integrated_commits": ["<sha>"],
      "result": "working | accepted | blocked",
      "conclusion": "<short-fact>"
    }
  ],
  "focused_verification": [],
  "remaining_verification": [],
  "blocker": null
}
```

fixer 在以下事实发生变化时更新即可：完成分组、派发 group、得到 group 结论、完成集成验收、进入 ready 或 blocked。脚本不要求每条命令或每次 worker heartbeat 都写状态。

### 11.3 脚本边界

`bookkeeping.py` 是 agent 的机械工具，只负责：

- 创建并校验 immutable request；
- 原子写入和读取 state；
- 校验必要字段与 anchor 一致性；
- 输出 fixer 全视图或 parent terminal projection。

脚本不执行 Git、不创建 task、不派发 worker、不决定 group、不推进预设状态机，也不告诉 agent 下一步做什么。

## 12. 消息合同

fixer 只在 material terminal 时主动联系 parent：

- `ready`：给出 fix id、记录目录、fixer branch/head 和一句摘要；详细内容由记录文件提供。
- `blocked`：给出 fix id、记录目录、具名 blocker，以及是否存在尚未交付的部分 commits。

parent task/thread id 来自 immutable request。fixer 使用宿主原生 `send_message_to_thread` 发送消息；消息只用于唤醒与定位，详细事实仍以记录文件为准。

## 13. 恢复与停滞

- 一次修复工作同时只能有一个活跃 fixer thread。
- fixer thread 中断后，先确认旧 thread 已停止，再由新的 fixer thread 使用 request、state、fixer worktree 和 Git anchors 继续。
- state 与 Git 不一致时，fixer先记录 `blocked` 或修正可验证的 state；不得依据聊天历史猜测 commits 已被接受。
- temp ledger 丢失时，thread history 只能提供人工恢复线索，不能自动重建已接受结论。
- v1 不实现主动 heartbeat。parent 读取状态时可根据 `updated_at` 识别疑似停滞，但不自动采取动作。

## 14. 验证设计

实现后至少验证以下真实场景：

1. **上下文隔离**：结构测试确认根 Skill 只包含条件 pointer，parent/fixer reference 不互相引用，subagent brief 不引用本 Skill。
2. **dirty parent**：parent 有受保护未提交文件时，fixer branch 仍从 `reviewed_head` 创建且不携带该文件。
3. **并行隔离**：两个 groups 获得不同 branch/worktree，写入不会直接出现在 fixer worktree。
4. **不完整交付**：subagent 没有提供 commit 列表、修改范围、验证结果或 bug 结论时，fixer 不集成其 diff。
5. **group 验收**：一个 group 包含多个 bug acceptance points，任何一点失败时 group 不标记 accepted。
6. **ready receipt**：全部 groups accepted 后，parent projection 包含固定 fixer head、完整 commit range和 remaining verification。
7. **blocked receipt**：冲突或无法归因的 residue 产生具名 blocker，不伪造 ready。
8. **恢复**：fresh fixer session 能仅凭 request、state 与 Git anchors继续工作。

## 15. v1 延后项

- 自动 heartbeat、超时调度或挂死恢复。
- 跨主机 ledger 与 worktree 迁移。
- 自动删除 group/fixer branches。
- 通用 DAG、seam、profile 或 budget controller。
- branch manifest、event log 或双写持久化。
- 自动将 fixer 结果写入 Impl-Package Gate 或其他业务记录。

## 16. Blind Opening 评审

2026-08-14 使用 `discuss-ledger --mode blind --agents codex,claude --claude-effort medium` 完成独立评审。原始结果：

`%TEMP%\discuss-ledger\blind-dispatch-fix-thread-skill-design-260814-613932c7.md`

处置结论：

- 接受轻量数据修正：`state.json` 改为真实 JSON；request 保存 finding 内容，不只保存路径；group 记录 base、source commits 和 integrated commits。
- 接受隔离边界：不完整交付不合入，未提交修改留在原 worktree；返工使用新的干净 worktree。
- 接受 parent 接回检查：核对 findings 覆盖、commit 对应、diff scope 和 clean state；parent 修改了相同路径时才重跑受影响的 focused checks。
- 接受结构化上下文隔离测试和派发失败保留原修复分支/worktree的规则。
- 删除 `campaign`、`batch` 和 `envelope` 等不必要术语，不增加 `schema_version`。
- 不增加 event log、heartbeat、lease、writer election、DAG 或自动抢占；一次修复工作只允许一个活跃 fixer thread。
- parent 不逐个重新验收 bug，也不重复 fixer 已取得且未被后续同路径修改影响的聚焦验证。

Blind Opening 没有推翻已确认的 Skill 形状，也没有留下 v1 实施前尚未裁决的事项。
