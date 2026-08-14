# 工具库能力全景

安装后可用的模块、每个 skill 的定位，以及典型使用场景。

---

## 使用场景

### 场景 A：接手裸仓库

```
1. python3 scripts/link_skill.py <skill> --host claude  → 把 skill link 到宿主 skills/
2. 说 "init-project-context"          → 梳理项目目标、交付物、技术边界
3. /audit [path]                      → 定点审查已有 agent setup，获得改进建议
```

### 场景 B：多任务并行开发（主力场景）

```
trunk 终端：
  说 "wt-pm" 或 "开始新任务"    → 引导进入流程
  说 "wt-plan"                 → 任务定义对话 → 生成 plan 三文件 → 建 worktree

worktree 终端：
  说 "开工"                    → wt-dev 接管：
                                  加载 plan 上下文
                                  → 环境初始化（首次）
                                  → 实现功能
                                  → [PAUSE] 等待人工测试确认
                                  → regression gate
                                  → merge 回 trunk + 标记 DONE + 清理 worktree
```

### 场景 C：单任务复杂实现

不需要 worktree 隔离时，直接用 `planning-with-files` 管理任务状态和 plan 文件，支持多 session 续接。

### 场景 D：换机器 / 重装

```
git clone <agent-workbench-repo>
python agent-workbench/scripts/link_skill.py --all --host claude codex grok
# 顶层 skills 以 junction/symlink 恢复到各宿主
```

---

## 模块能力

### 模块一：项目环境审查

| 组件 | 类型 | 说明 |
|------|------|------|
| `audit-agent-setup` | skill（知识库）| 定点 setup 审计范围、规则库与示例 |
| `audit-agent-setup` | subagent | 按范围执行只读 setup 审计 |
| `audit` | command | `/audit [path]` 触发入口 |

**能力**：默认审查指定文件；未指定时只审根 `AGENTS.md`、`CLAUDE.md`。它判断已有 setup 的可执行性、安全边界和跨宿主冲突，并输出带证据的改进方向。`--full` 才审项目级 setup，`--include-global [host ...]` 才审指定的用户级宿主状态，并同步收窄项目级专属宿主目录。

**触发**：`/audit [path]`、`/audit --full`，或明确要求审查已有 agent setup、AGENTS/CLAUDE 指令或跨宿主配置。

---

### 模块二：WT-PM 多任务并行开发工作流

三个 skill 分层协作，覆盖从任务定义到合并完成的全生命周期：

| Skill | 运行终端 | 职责 |
|-------|----------|------|
| `wt-pm` | 任意 | 流程导航入口：识别当前阶段，引导至正确 skill 和终端 |
| `wt-plan` | trunk | 规划侧：任务定义对话 → plan 三文件 → commit → 建 worktree → 同步配置 |
| `wt-dev` | worktree | 执行侧：加载 plan 上下文 → 实现 → 人工测试暂停 → regression gate → merge 回 trunk → 标记 DONE |

**核心机制**：
- 每个 task 对应一个独立 git worktree，文件系统级隔离
- plan 三文件（`task_plan` / `findings` / `progress`）作为 AI 的持久化外部记忆，续接时读取即可恢复完整上下文
- `plan_tracker.py` 管理 task 状态机（UNPLANNED → PLANNED → DONE）

**知识库**（`wt-pm` skill 目录）：`references/`（工作流设计文档）、`rules/`（协作边界、DoD、planning 规范）、`scripts/`（plan_tracker.py、sync_worktree_config）、`templates/`（workplans/README 模板）

---

### 模块三：文件化 Planning

**`planning-with-files`** skill

不需要 worktree 隔离时的轻量任务管理：task tracker（`plans/todo_current.md`）+ plan 三文件结构，支持状态机管理、多 task 并行绑定、会话续接。

---

### 模块四：新项目上下文初始化

**`init-project-context`** skill

新项目文档空白、方向模糊时，引导梳理：项目目标、交付物边界、候选技术方向。先稳固项目定义，再进入实现规划。

---

### 模块五：Workbench 自管理

**安装器规范**

Agent 按 [`docs/workbench-design/04-install-spec.md`](workbench-design/04-install-spec.md) 直接执行宿主原生 CLI，处理插件安装、升级、重装、缓存刷新与 standalone Skill 链接验证；仓库不维护额外的管理 Skill 或 lifecycle 包装器。

---

