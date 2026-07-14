---
name: audit-stable-docs
description: Perform the read-only phase of a stable-docs backfill. Use when scanning current truth, completed Implementation Packages, pending registers, gate omissions, or unowned commits to produce an itemized audit without changing canonical documentation.
---

# Audit Stable Docs

只读盘点 durable delta、现有覆盖与 authority 冲突。Audit 完成只代表报告可供 owner 审阅，不代表候选已 apply、验证已通过或整个 backfill 已 closed。

## 输入与基线

1. 解析项目根目录以及显式 `--config`；没有显式路径时读取项目根 `.stable-docs-backfill.json`。先运行 `python ../../scripts/validate_config.py --project-root <root> [--config <path>]`，失败即记录 blocker。
2. 冻结 branch、Source HEAD、dirty paths、Project Source Watermark、carry-forward、canonical home 清单、pending、compaction state 和 Implementation Package 根路径。
3. 从 `../../.codex-plugin/plugin.json` 读取 `plugin name + version` 作为 Method Activation Ref。不得要求 method checkout commit，不持久化本机 Plugin 路径。
4. Project Source Watermark 必须在目标项目内解析为 Source HEAD 的 ancestor；缺少可信 watermark 时不得猜测下界。Bootstrap 只接受 owner 明确给出的有界 source manifest。

完整来源选择与 carry-forward 合同见 [`../../references/source-selection-and-dual-anchor.md`](../../references/source-selection-and-dual-anchor.md)。约束提取、authority 顺序与目的地分流见 [`../../references/constraint-extraction-and-routing.md`](../../references/constraint-extraction-and-routing.md)。

## 只读边界

来源仓库只读。交互式运行唯一允许写入配置的 compaction 目录中新报告；Automation 或外部审阅运行可以把产物写到用户明确给出的外部 output directory，但不得因此修改来源仓库。不得改 canonical docs、清 pending、推进 watermark、修链接、提交或推送。

## 工作流

1. 运行 collector 固定机械 inventory：`python ../../scripts/collect_sources.py --mode steady-state --project-root <root> --source-head <sha> --project-watermark <sha> [--config <path>] [--carry-forward <package>]`。Collector 只盘点来源，不判断 durability。
2. 对 eligible Implementation Packages 默认只把 `design.md` 和 `spec.md` 作为 semantic sources；`findings.md` 仅在设计引用、evidence gap 或 authority conflict 时定点读取；gate、pending 与 commits 只做 closure/coverage 对账。
3. 逐 canonical module 检查 current truth、禁止事项、信任边界、数值精度/归一化、外部 provider 义务与负依赖；代码只能证明 current behavior，不能单独证明 product intent。
4. 对每条原子 statement 应用 intent/observable behavior litmus，拆开 why 与 how，并按 current authority 去重。冲突交给 owner，不自行选边。
5. 遵从 tombstone 的最终目标；断链、循环或语义不等价只报告，不在 audit 修复。
6. 检查受影响顶层知识只描述当前合同：退役历史留在 provenance；future TODO 只有在 owner 已批准、明确 non-current、含 owner/目标/前提时才可保留。
7. 为每个 module 给出 `candidate`、`already-covered`、`conflict` 或 `no-delta`，不能只列有发现的模块。

## Item ID 与产物合同

每个 audit item 使用 `SDB-<12 hex>`。通过 `python ../../scripts/make_item_id.py --source <relative-source> --destination <relative-destination-or-none> --statement <atomic-statement>` 生成；同一 source、destination 和规范化 statement 必须得到相同 ID，禁止按表格序号重新编号。

交互式默认按 [`../../templates/report-template.md`](../../templates/report-template.md) 写入 compaction 目录。若用户或 Automation 指定外部 output directory，同一次运行必须输出：

- `audit.json`：canonical machine record，包含 Method Activation Ref、固定基线、完整 item ID、module coverage、pending/carry-forward 和 blockers；遵循 [`../../references/audit-json-contract.md`](../../references/audit-json-contract.md)。
- `human-report.md`：面向 owner 的业务报告，可省略内部 item ID/hash，但结论和计数必须与 `audit.json` 对账。

## 完成标准与回复

所有 configured modules、pending、合格 gate、eligible/removed package 与无主 commit 都有 disposition；来源仓库除允许的报告位置外无 diff。最终回复报告 audit 阶段、Method Activation Ref、Source HEAD、产物路径、四类计数、carry-forward、水位线状态、blocker 和仍需 owner 决策的 item ID。
