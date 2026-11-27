---
name: dev-loop
description: 开发任务的统一闭环：普通任务走“写方案 → 单人审 → 实施 → 同人复审 → 收尾”的轻量循环；实施包（Impl-Package）走由本 Skill 目录下 `scripts/dev_loop.py` 驱动的开发 Pipeline（包级主线、Ticket 概览、审阅批次、agent 与模型路由）。开工时、任何“改完要审一下”的场景，或用户输入 /dev-loop、说“按 loop 来”时使用。
---

# Dev Loop

同一份 Skill 覆盖两种开发场景，先判断在哪一种，再走对应模式：

- **模式一：普通任务**（不在实施包里）：线上 bug、小改动、单个 PR、汇报材料等，走下面的轻量 5 步闭环。
- **模式二：实施包**（Impl-Package）：已批准 Plan 与 Ticket 的交付，走 `scripts/dev_loop.py` 的流程视图，配合 `dev-with-track`、`do-review` 与 package engine 使用。

判断依据只有一条：任务是否已进入一个带 `tickets/` 与 `.impl-package/state.json` 的实施包目录。不确定时按模式一，先用 3–5 行向 Owner 复述理解。

两种模式共享同一条底线：审阅独立于实施、修复者与审阅者全程续用、结论以证据为准。模式二只是把这条底线接进实施包已有的权威记录，不另立一套。

## 模式一：普通任务

核心习惯：任何有改动的任务都走审阅闭环，同一批人从头跟到尾，不等 Owner 提醒。

### 0. 判断与复述

- 先确认任务不在实施包内；若其实在包里，切到模式二，不要用本模式绕开 Ticket、Evidence 与 Gate。
- 不在包里：用 3–5 行告诉 Owner 要改什么、方案要点、谁实现、谁审。Owner 已批准方向的，复述一句即开工。

### 1. 方案

根因、改法、影响面（先 grep 调用方）、验证方式。小改动三五行即可。

### 2. 方案审

审阅者用 `magpie-terra-high` 或 `magpie-sol-high` 二选一（UI 用 terra high；终审 / 安全边界用 sol high），记下 agentId 供后续复用。有问题改方案再审，直到通过。

### 3. 实施

写方案的人实施（有上下文）；机械活交 DeepSeek，复杂逻辑 Sonnet high；主控自己写的就自己改。记下修复者 agentId，后续修复用 SendMessage 续派同一人，不新开代理。

### 4. 复审 loop

- 提交后立即交同一审阅者，简报写明“聚焦审这个提交 / 只核实关闭 + 是否引入新问题”，附已接受的取舍。
- 不等测试：测试与复审并行，失败并入下一轮；修复者后台跑测试时挂 Monitor 盯分支新提交。
- 分诊：只修用户可见行为和数据安全问题；过度设计的意见拒掉并说明理由。
- 同一处第二次要修 → 停下从根上收窄，不逐点打补丁。
- 循环到审阅者确认关闭。

### 5. 收尾

只跑方案点名的测试 + build/lint/contracts，不跑全量。汇报改了什么、审了几轮、拒了哪些意见及理由、没验证的部分。push / PR / 线上操作前再问 Owner。

### 派发前自检

- 审阅者、修复者是不是还是同一个？
- 修复是不是已经交给审阅者了，还是我在空等？
- 有没有在问 Owner 本可以自己判断的事？

## 模式二：实施包（Impl-Package）

`DEV_LOOP` 指本 Skill 目录下的 `scripts/dev_loop.py`（纯 Python stdlib 模块化 CLI，流程定义位于同目录 `pipeline.json`，无后台常驻），例如 `python <skill-dir>/scripts/dev_loop.py status --package <pkg>`。它只做流程聚合与提醒，不替主控做业务判断，也不自行派发、审阅或推进 Gate。

### 统一入口

```bash
DEV_LOOP status  --package <pkg> [--json]
DEV_LOOP config  show|set-route --package <pkg> ...
DEV_LOOP agent   register|update|replace|list --package <pkg> ...
DEV_LOOP batch   register|update|close|list --package <pkg> ...
```

- `status`：包级主线（接入 / 恢复 → Ticket 推进 → 包级终审 → 最终验证 → Gate → 收尾）、Ticket 概览、活跃审阅批次与轮次、未派审 return、可续用 agent 与模型路由提示、下一步推荐命令。只读现有权威事实自动推导，不要求手动 `advance`。
- `config`：查看 / 设置本包按职责的模型路由建议（`implementer`、`reviewer`、`fixer` 等），只影响后续推荐，不改写已有 agent 记录。
- `agent`：登记、补录、替代 agent 与本次自填的模型 / 强度；宿主未返回可恢复 ID 时记 `unconfirmed`，续用推荐优先原实现者与原审阅者。
- `batch`：登记 / 更新 / 关闭跨 Ticket 的多返回组合审阅批次，记录受审版本、快照类型与逐票备注；未纳入任何批次的 return 继续显示欠审。

本包只额外保存 `.impl-package/development-pipeline.json`（routing、agents、batches）；Ticket、Evidence、Gate 与审阅轮次仍读原处。写入成功后直接输出刷新后的状态。

### 主线状态

每个主线节点由现有事实推导为 `done` / `active` / `pending` / `blocked` / `attention` 之一：依赖未释放是 `blocked`，信息缺失或矛盾是 `attention`。多张 Ticket 与多个审阅批次可以同时为 `active`，不强制全局串行。

### 接入与恢复

- 新包从已批准的 Plan 和初始化后的 package 状态接入。
- 进行中的包直接按只读视图恢复：Attempt、Ticket、trail、审阅与证据能可靠关联的沿用，无法证明的部分标 `unconfirmed`，允许主控核对后补录。
- 没有 `.impl-package/development-pipeline.json` 是正常情况，不阻断接入。
- 读取失败、`.rounds.json` 缺失或损坏时只降级对应对象，不崩溃、不阻断无关 Ticket。

### 职责边界

- **`dev-with-track`**：业务裁决、Ticket readiness、语义取舍、State / Evidence / Gate 的合同与写入。
- **`do-review`**：审阅方法、审阅轨选择、轮次与 finding 收敛规则；pipeline 只读 `.rounds.json`，不改写轮次状态。它在实施包外仍可独立用于 PR 或代码审阅。
- **package engine（`impl_package_state.py` / `situation.py`）**：Ticket、依赖、Evidence、Gate 的权威状态与校验；pipeline 不复制、不重算验收条件。
- **`dev-loop`**：流程状态聚合、缺失标注与下一步命令指引；是否推进、派谁、如何分诊仍由主控决定。

### 使用节奏

1. `status` 看主线位置、可推进 Ticket、欠审项与可续用 agent。
2. 按提示派发或续用 agent；返回后登记 return，或把多个返回纳入同一 `batch` 组合审阅。
3. 本轮审阅轨收齐并关轮后再统一分诊；修复交回原执行者，复验交原审阅组。轨道未收齐不提前分诊；出现 `UNCERTAIN` / `INCOMPLETE` 或缺少有效 verdict 时明确标为未收敛，不以“无 finding”冒充 PASS。
4. `isolated` 快照或 `reviewed_head` 与当前 HEAD 不一致时，先核对影响范围并按票补 `evidence add`。
5. 记录缺失、`.rounds.json` 损坏或事实不可推导时标 `unconfirmed`，只限制受影响的收口，其他 Ticket 照常推进。

## 升级规则

只在业务取舍、范围扩大、外部写入（push / PR / Staging / 生产）时停下找 Owner；其余自行推进，最后按模式一的收尾格式汇报。
