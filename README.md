# agent-workbench

把 agent 的开发过程从“每次临场发挥”变成可复现的流程：需求有入口，实施有骨架，结果有证据，会话断了能接上。

仓库里的东西按用途分成三组，互不依赖，可以只取其中一组：

| 组 | 解决什么 | 入口 |
|----|----------|------|
| **开发主链** | 从想法到可验收交付的确定性流程 | [kickoff](skills/kickoff/SKILL.md) · [dev-loop](skills/dev-loop/SKILL.md) · [impl-package](plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md) |
| **Session 看板** | 同时看多个本机会话，知道谁在跑、谁卡住 | [session-board](skills/session-board/SKILL.md) |
| **独立能力 Skills** | 单点问题：调研、设计、审查、验证、专项域 | [能力介绍](docs/capabilities.md) |

安装不是重点：把仓库路径交给 agent，让它按 [安装规范](docs/workbench-design/04-install-spec.md) 执行即可。

---

## 开发主链

三者是一套系统的三层，不是三个并列的工具：

- **[kickoff](skills/kickoff/SKILL.md)** 是入口。新需求从研究材料、探索、方向对齐一路推进到“可以开工”，由状态机驱动，每个阶段有输入契约和门禁。
- **[dev-loop](skills/dev-loop/SKILL.md)** 是执行骨架。普通任务走“写方案 → 审 → 实施 → 复审 → 收尾”的轻量闭环；实施包走基于 `pipeline.json` 的开发 Pipeline，决定谁在什么阶段做什么。
- **[impl-package](plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md)** 是内部能力和状态层。它提供需求对齐、计划与 Ticket、独立审查、验收、稳定文档回刷，以及贯穿始终的 State / Evidence / Gate 记录。

整体在做一件事：**让每个阶段都有明确产物和下一位接手者能看懂的依据**。对话中断、换会话、换执行者，工作不会退回重来。上层（kickoff / dev-loop）负责流程推进，底层（impl-package）负责把过程留成可核对的事实。

常用入口：

- `/impl-package:dev-with-track`：跟踪一个实施包从计划到收口
- `/impl-package:do-review`：对固定版本做独立审查
- `/impl-package:req-align`：需求变化时更新 Decision / Spec
- `/impl-package:backfill-stable-docs`：把完成的工作回刷成长期文档

安装方式见 [安装规范](docs/workbench-design/04-install-spec.md)（Codex / Claude 原生 plugin）。

## Session 看板

独立工具，和上面的开发主链**没有关系**：它只做一件事——把本机的 Claude / Desktop 会话收进一个四栏看板（进行中 / 最近 / 已完成 / 暂不关注），支持标签、分组、AI 摘要和 token 用量，方便快速判断哪些会话还在跑、哪些需要处理。数据只留在本机。

```powershell
powershell -ExecutionPolicy Bypass -File skills\session-board\scripts\board.ps1 -Action start
```

启动、重启、远程访问和摘要配置见 [session-board](skills/session-board/SKILL.md) 与 [运行说明](docs/workbench-design/session-sidecar-board-usage.md)。

## 独立能力 Skills

按用途分组，按需链接到宿主；每组只列代表入口，完整说明见 [仓库能力介绍](docs/capabilities.md)。

| 用途 | 代表能力 | 什么时候用 |
|------|----------|------------|
| 调研与需求 | [research](skills/research/SKILL.md)、[req-discover](skills/req-discover/SKILL.md)、[grilling](skills/grilling/SKILL.md)、[business-alignment](skills/business-alignment/SKILL.md) | 先把问题、事实和分歧弄清楚，再谈方案 |
| 设计与架构 | [codebase-design](skills/codebase-design/SKILL.md)、[architecture-review](skills/architecture-review/SKILL.md)、[prototype](skills/prototype/SKILL.md)、[preview-design](skills/preview-design/SKILL.md) | 定模块边界、验证设计取舍、先看形状 |
| 实施与委派 | [dispatcher](skills/dispatcher/SKILL.md)、[backend-worker](skills/backend-worker/SKILL.md)、[frontend-worker](skills/frontend-worker/SKILL.md)、[tdd](skills/tdd/SKILL.md) | 把工作拆给多个执行者并回收结果 |
| 验证与排障 | [diagnosing-bugs](skills/diagnosing-bugs/SKILL.md)、[run-acceptance](skills/run-acceptance/SKILL.md)、[validation-harness](skills/validation-harness/SKILL.md)、[security-audit](skills/security-audit/SKILL.md) | 证明结果真的可用，或定位说不清的问题 |
| 界面与国际化 | [frontend-design](skills/frontend-design/SKILL.md)、[ui-commonsense](skills/ui-commonsense/SKILL.md)、[i18n-advisor](skills/i18n-advisor/SKILL.md) | 界面可用性、视觉质量和多语言 |
| 知识与协作 | [knowledge-manager](skills/knowledge-manager/SKILL.md)、[handoff](skills/handoff/SKILL.md)、[plain-language](skills/plain-language/SKILL.md)、[git-commit](skills/git-commit/SKILL.md) | 把过程沉淀成别人能用的材料 |
| 专项域 | [Azure](skills/azure-skills/using-azure/SKILL.md)、[Lark](skills/lark-skills/using-lark/SKILL.md)、[DATEV](skills/datev-tax-accounting/SKILL.md) | 特定平台的集成与领域知识 |

## 维护这个仓库

- **添加 Skill**：独立能力放 `skills/<name>/`，多 skill 套件放 `plugin-marketplace/plugins/<plugin>/`；格式见 [Skills 规范](docs/workbench-design/02-skills-spec.md)。
- **暴露给宿主**：`python scripts/link_skill.py <skill> --host claude codex`，只建链接，冲突时跳过并报告。
- **插件**：`plugin-marketplace/` 是独立发布根，用宿主原生 marketplace / plugin 命令安装；`link_skill.py` 不处理它。刷新、重装和审计按 [安装规范](docs/workbench-design/04-install-spec.md#plugin-生命周期agent-直接执行) 由 agent 直接执行原生 CLI。
- **检查安装态**：`python scripts/codex_setup.py pull-diff` 查看仓库增量，`audit` 生成报告，`apply --expect-report <sha>` 在状态未变时同步。
- **第三方资产**：[skills 清单](registry/third-party-skills.md) 与 [plugins / MCP 清单](registry/plugins.md) 只记录来源和重装方式，不记录本机状态。
- **归档**：`skills-deprecated/` 保存已退休的 skill，`archive/` 保存更早的脚本与测试；它们不是规范源，也不参与默认安装。
- **已退休**：Grok 宿主、ZCode 宿主、DSH 适配和 codex_harness 系列脚本不再维护，相关内容已删除或归档。

链接器或插件改动后，先跑对应测试：`python -m pytest tests/test_link_skill.py -q`、`python -m pytest tests/test_impl_package_plugin.py -q`。

## 文档地图

- [仓库能力介绍](docs/capabilities.md)：能做什么、各类能力如何配合
- [安装规范](docs/workbench-design/04-install-spec.md)：宿主差异、插件生命周期、安装态审计
- [Skills 规范](docs/workbench-design/02-skills-spec.md)：目录、frontmatter 与组织方式
- [AGENTS.md](AGENTS.md)：在这个仓库里工作的 agent 需要遵守的规则
