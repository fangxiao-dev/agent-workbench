# Report Structure

三层产出，顺序固定：00-notes.md（过程）→ REPORT.md（正式）→ chat 报告（交付）。digest 文件由分析员直接落盘，不在此列。

## 评审目录布局

```
<project-root>/agent-eval-<yyyymmdd>/
├── 00-notes.md            # 工作笔记：基线、链路表、逐环摘要要点、综合分析
├── session-<n>-<id8>.md   # 每环 digest（分析员写入）
└── REPORT.md              # 正式报告
```

## 00-notes.md 骨架

```markdown
# Agent Orchestration Evaluation — Working Notes

Date / Evaluator / Scope

## Session chain (user-claimed order)
| # | Session ID | File created | Size |
（声称序与文件时间矛盾时在此标 ⚠️ 待查证）

## Expected behavior baseline (from SKILL.md)
（基线 skill 名 → 提炼出的契约检查项清单）

## Evaluation dimensions
1. 卡壳/放弃点  2. 流程符合度  3. 交接质量  4. 调度纪律  5. 简化/优化建议

## Per-session digests
（指向 session-*.md；摘要回传后随手记关键事实）

## Synthesis (evidence-backed)
### Real chain (reconstructed via thread evidence)
### Cross-verified facts        # 实物核验结果，逐条
### Findings (bad)   F1..Fn     # 每条标【系统性/一次性/轻微】
### Findings (good)  G1..Gn     # 每条附实证
### Recommendations  R1..Rn     # 每条指向 F*，标成本
```

## REPORT.md 骨架

```markdown
# Agentic Orchestration Evaluation Report
## <链名> — <基线 skills> 调度链评审

- 日期 / 评审对象 / 方法（分析员数量、核验方式）/ 证据文件清单

## 0. 总评
一段话：核心承诺是否兑现 + 最重要的一两个缺陷 + 实物核验是否吻合（有无虚报）。

## 1. 真实链路还原（headline finding）
链路表：| 环 | Session ID | 运行窗口 | 时长 | 主要产出 |
与声称清单的差异（缺环/倒序）及其根因。
范围声明：清单外的 session（如链头之前的规划 session）明确"未审计"。

## 2. 不好的地方（按严重度）
### F1（系统性）...
### F2（一次性事故）...
...
**如实说明**：未发现的问题类型（无放弃方向 / 无 compaction / 无死循环 / 无虚报等）。

## 3. 好的地方
### G1 ... （每条给实证：抓到了什么真缺陷、哪条护栏在哪里守住了）

## 4. 优化建议
| # | 建议 | 针对 | 成本 |

## 5. 结论
直接回答用户的原始问题（"调度是否真的按预期"），一句话收束 + 性价比最高的下一步。
```

## Chat 报告要点

- 与 REPORT.md 同结构但更紧凑；headline finding（缺环/倒序这类推翻用户认知的）放最前。
- 每个论断可指向 digest 文件或实物证据（commit、文件 mtime、gh 输出）。
- 结尾给出评审目录路径，方便用户复查证据链。
