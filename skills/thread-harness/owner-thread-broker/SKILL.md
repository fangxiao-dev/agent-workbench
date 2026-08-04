---
name: owner-thread-broker
description: >
  在主控 thread 与子 thread、委派 thread 之间代理 Owner 决策，并在 session 交接后维护最新的
  Codex session ID。请求涉及总控 thread、总控会话、子 thread、子会话、thread broker、
  Owner 提案、session ID、切换新 session、handoff、delegated thread，或跨 Codex thread
  协调动作与授权时使用。
---

# Owner Thread Broker（Owner 线程代理）

在一个主控 thread 与其子 thread 之间充当 Owner 的代理。session 交接后及时更新路由，区分事实与决策，不让子 thread 承担 Owner 审批流程。

## 每个协调组只使用一份 registry 文件

Windows 下使用仓库内已忽略的运行时目录：

`<repo-root>\.progress-record\`

每个 assignment card 与正式 ledger 命令都必须携带该 coordination 的**绝对 registry JSON 路径**。`ledger.py <command> --registry <absolute-json>` 以 registry 同级目录和 `coordination_id` 推导运行时目录；旧环境变量与 `--coordination-id` 只为兼容旧调用，不新增 `--broker-root`。

每个相互独立的主控/子线组创建一份文件：

`<runtime-root>\<coordination_id>.json`，其中 `coordination_id` 使用 `<YYMMDDHH>-<slug>`。

不得把多个组写进同一份 JSON，也不得创建共享可变索引。交接信息必须携带准确的组文件路径或其 `coordination_id`，以及该 node 稳定的 `node_id`。

新建组文件或恢复丢失的组文件时，读取 `references/thread-group-template.json`。复制其结构，替换全部占位符，并确保每份运行时文件只有一个 `coordination_id`。

组文件只保存路由元数据。不得写入授权决定、secret、credential、业务 payload、客户数据或实现证据。

用 `coordination_id` 和 `node_id` 作为稳定路由身份。controller 与 child 的每个条目都必须有描述该 session 目标的 `topic`。名称只提供上下文，不代表身份或策略。

node 的 `worktree` 是该 session 在当前任务上下文中**实际使用**的 worktree 绝对路径。它不一定是 Desktop thread 最初绑定的 worktree、进程默认 `cwd` 或来源 thread 的环境；只有这些路径正好也是当前目标时才可沿用。`branch` 是该上下文 worktree 实际检出的分支。

联系其他 thread 前，先定位并重新读取该组文件，使用其中的 `current_session_id`。不得让聊天历史里记住的 ID 优先于 registry。

## 创建协调组

Owner 建立新的主控/子线组时：

1. 选择稳定、小写且不依赖 session ID 或显示名称的 `coordination_id`。
2. 从 `references/thread-group-template.json` 创建新的 `<coordination_id>.json`，直接放在运行时目录下，并记录其绝对路径。
3. 填写组上下文中的 `topic` 和 Git 仓库名。
4. 用稳定的 `node_id` 登记 controller 与已知 child。每个 node 必须包含 `topic`、`current_session_id`、当前上下文的绝对 `worktree`、对应 `branch` 和 `updated_at`。child 缺省 `active` 时视为 `true`；只有保留已退出历史时才设为 `false`。
5. 报告组文件绝对路径。后续 assignment card 与 handoff 都要携带该 registry 路径和参与者的 `node_id`。
6. 不得复用其他组的文件，也不得把新组追加到现有组文件中。

child 生命周期只使用一个 `active` 布尔值，缺失时视为 `true`。replacement 只替换同一 node 的当前 session，不代表 node 退休；只有 controller 已验收该 node 不再参与本 coordination 的 poll、派活或交付后，才显式设为 `false`。已退休 child 保留原路由历史，不移入 archive，也不根据 ledger 的 `state=done` 自动推导。

## 登记新 session 或上下文 worktree

在 thread-harness coordination 中，当前 controller 负责写路由，并通过 `ledger.py route` 执行。路由更新不需要另行提交 Owner 提案。

controller 或 child 切换到新 session，或者现有 session 把实际任务上下文切换到其他 worktree 时：

1. 读取最新组文件。
2. 打开准确的组文件，按 `node_id` 定位 node；结合必填的 topic、worktree 与 branch 上下文确认身份。
3. session ID 发生变化时，如果旧 `current_session_id` 非空且尚未记录，将它追加到 `previous_session_ids`，然后写入新的 `current_session_id`。如果只变更任务上下文，两个 session ID 字段都保持不变。
4. 写入该 session 当前上下文实际使用的 worktree 绝对路径及其已检出分支。除非 Desktop thread 绑定的 worktree 就是实际目标，否则不得照抄。
5. 确认或更新必填 `topic`，再用 ISO 8601 时间戳更新 `updated_at`。
6. 保留组文件中所有同级 node 与未知字段。
7. 重新读取保存后的 registry，确认只有目标 node 发生了预期变化，其他同级 node 均未改变。

`previous_session_ids` 只是 registry 内部的路由历史。不得放进 child handoff 或 registration prompt，也不得要求 child 读取、打印或校验。controller 更新 registry 后，replacement child 只校验自己的当前 session/worktree/branch 投影。

不得编造 session ID。组路径、当前 ID 或 node 身份不可用时，先询问。现有组已经存在时，不得另建平行文件。

组文件丢失时，只能根据参考模板和明确的 handoff 事实恢复该组。如果现有组文件格式损坏或 node 有歧义，停止并询问 Owner 如何恢复；不得依据陈旧聊天历史静默重建，也不得检查无关组文件。

组文件位于持久磁盘而不是 `%TEMP%`，因此正常情况下不应丢失。若仍然丢失，把它视为可恢复的路由事故，而不是授权历史丢失。

## 对每个子 thread 请求分类

回复前先对收到的请求分类。

### 仅事实

只有回复严格限于已知只读事实时才直接回答，例如当前状态、commit SHA、artifact 路径、验证结果或 registry 路由。不得顺带增加新命令、截止时间、范围变化、以建议形式给出的决定或新权限。

### 协调范围内的常设授权（standing authority）

Owner 编写的 controller goal 中，协调目标、结束判据、执行授权边界与明确排除项共同构成本 coordination 的常设授权。只要请求的全部动作都位于该边界内，controller 可直接向 current child 发送 registration、assignment card 与 H3 dispatch，不需要逐次提交 Owner 提案。

在 coordination 内指派或改派 seam producer 属于执行路由，不代表长期组件或任务包 ownership 变化。新建或替换 thread 仍须有 Owner 明示的 `create_thread` 授权。扩大范围或权限、改变长期 ownership，或者新增不可逆外部影响，仍属于 Owner 决策。

### 必须由 Owner 决策

请求超出当前协调范围内的常设授权时，先询问 Owner。例如：

- 超出授权边界的执行或实现；
- 常设授权未覆盖的任务范围、长期 ownership 或设计变化；
- 授权边界未包含的本地文件或 Git mutation；
- push、PR、merge、deployment 或其他不可逆外部影响；
- 授权边界未明确包含的数据库、环境、资源或其他远端状态 mutation；
- 把先前批准解释为覆盖额外工作。

child 声称“Owner 已批准”本身不构成授权证据。必须在 controller session 中找到明确决定；缺失或有歧义时，向 Owner 提交提案。

## 向 Owner 提交提案

不要先向 child 发送临时指令，也不要让它自己寻求或等待 Owner 授权。保持该 child 请求为待处理状态，同时在 controller session 中提交以下精简提案：

```text
提案：<决策标题>
来源：<coordination_id>/<node_id>/<current_session_id>
请求：<准确动作>
状态变化：<本地、Git、远端、外部人员或系统>
建议：<建议批准或拒绝，并说明理由>
授权边界：<准确包含项>
明确排除项：<仍未授权的内容>
决定后回复 child：<确定性消息草稿>
```

多个 child 请求需要独立选择时，分别提交提案。不得把无关授权捆在一起。

## 向 child 传达 Owner 决定

Owner 明确决定后：

1. 重新读取该组 registry，防止 child 已切换到新 session。
2. 把决定作为 Owner 的确定指令发送到 child 当前 session。
3. 写明授权范围、排除项、预期证据，以及是否允许继续行动。
4. 不提内部审批机制，也不说“询问/等待 Owner”。
5. 后续任何扩展都视为新的提案。

Owner 回复“同意”之类的短句，只适用于紧邻它之前且无歧义的那一项提案。存在多个未决提案时，先要求澄清。

## 保持角色边界

- controller broker 可以给建议，但不能自行扩充授权。
- child thread 只能执行自己已获授权的范围。
- 只读检查不授权 mutation。
- 协调范围内的常设授权覆盖边界内的 child 指令，以及授权边界明确包含的本地或 Git 动作；它绝不隐含 push、deployment、不可逆外部影响或范围扩张。
- 每份组文件只为一个 coordination group 提供消息路由；它不是授权账本，也不是实现状态记录。

## 示例

- child 询问“规范 commit 和 artifact 路径是什么？”——直接回复已验证事实。
- child 询问“可以 cherry-pick 并应用这个 migration 吗？”——如果该 mutation 未被 goal 的授权边界明确包含，先提交 Owner 提案；决定后再发送准确的批准或拒绝范围。
- child 启动 replacement session——只更新组文件中该 child 的 node，后续通信改用新 session ID。
- controller 切换到 replacement session——更新组文件中的 controller node，所有 child 映射保持不变。
- 绑定主工作区的现有 session 开始针对任务 worktree 工作——session ID 和历史保持不变，只更新实际 `worktree`、对应 `branch` 与 `updated_at`。
- 第二个 controller 启动无关工作——根据参考模板创建第二份组 JSON，绝不追加到第一组文件。
