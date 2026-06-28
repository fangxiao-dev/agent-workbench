# Dev With Track Control Flow

状态：通用参考
用途：指导小型切片如何用 `process.md` / `findings.md` / `gate.md` 记录状态、证据、发现和下一步。

## 适用边界

适合：

- 需要跨多轮恢复现场的小切片；
- 有明确 phase / gate / evidence 的工作；
- 需要记录发现、风险、候选后续动作；
- 暂时不适合拆成 GitHub issue 的探索 / 迁移 / 实现工作。

不负责：

- 定义某个领域的设计流程；
- 选择视觉风格；
- 替代项目 `AGENTS.md`、roadmap 或验证文档；
- 自动 commit、创建 PR、发布或清理工作目录。

## 核心文件分工

- `roadmap`：定义总路径、phase、gate、红线。
- `process.md`：记录当前走到哪、gate 哪些已满足、下一步是什么。
- `findings.md`：记录过程中发现的问题、判断、候选后续动作。
- `gate.md`：承接当前切片或阶段的验收、待判断项和后续候选动作。
- `evidence README`：记录本轮证据入口、截图 / 日志 / 命令 / 几何检查等结果。
- `issue / PR`：只在 finding 已经拆到可直接执行的任务边界后再使用。

## 工作流

### 1. 从 Roadmap / Plan 进入

每次开工先看当前项目的 roadmap 或用户给出的计划：

- 当前 phase 是什么；
- 本 phase 的目标是什么；
- 本 phase 的 gate 是什么；
- 当前问题属于本 phase、下一 phase、还是 backlog。

不要直接“看见问题就改”。先判断问题属于哪个阶段。

### 2. 从 Process 恢复现场

`process.md` 是状态入口。它回答：

- 当前在哪个 phase；
- 上次做到哪；
- 哪些 gate 已过；
- 哪些验证还没跑；
- 下一步推荐做什么。

如果聊天上下文丢失，应优先从 `process.md` 恢复，而不是依赖记忆。

### 3. 执行当前切片

执行动作来自项目 roadmap、领域 skill 或用户要求。`dev-with-track` 只要求切片边界清楚：

- scope 写清楚；
- safety boundary 写清楚；
- evidence 形式写清楚；
- verification 方式写清楚；
- 人工 review 是否需要写清楚。

### 4. 发现写入 Findings

测试、截图、review 或实现中暴露的问题必须写入 `findings.md`。

典型 finding：

- 某个布局或行为风险；
- 某个 gate 仍缺证据；
- 某个能力边界不清；
- 某个 follow-up 尚不足以升级为 issue。

如果 finding 已经足够可执行，再考虑转成 issue / PR。早期探索阶段不要为了“显得正式”强行发 issue。

### 5. 用 Gate 控制前进

不以“看起来差不多”进入下一阶段。

Gate 应回答：

- scope 是否覆盖到位；
- evidence 是否存在；
- safety boundary 是否被守住；
- findings 是否记录并分类；
- 自动验证是否通过或明确阻塞；
- 是否需要人工 review。

只有 gate 满足或用户明确接受 defer，才允许进入下一 phase。

### 6. 回写状态

每轮工作结束后：

- `process.md` 更新当前 phase、gate 状态、下一步；
- `findings.md` 更新新发现、风险、候选后续动作；
- `gate.md` 更新阶段验收、人工判断项和 evidence；
- `roadmap` 只在阶段规则、gate、红线变化时更新，不写流水账；
- issue / PR 只在任务边界已经足够清晰时记录具体 Done Gate 和验证结果。

## 结束语义

保持这些状态不同：

- `slice shaped`：形态或方向已经初步成形；
- `automated verification closed`：自动验证已收口；
- `manual review pending`：仍等人工判断；
- `gate passed`：当前 gate 已满足；
- `ready for next phase`：可以进入下一阶段；
- `done`：只有项目自己的完成定义满足时才使用。
