# SKILL 降载基线（2026-08 起）

改造前实测行数（md 文件；evals/scripts/assets/tests 除外）。目标：主文件 ~860 → ~230 行；references 改按需读。

| SKILL | 主文件（前） | 目录 md 合计（前） | 主文件（后） | 组 |
| --- | --- | --- | --- | --- |
| dev-with-track | 67 | 118 | 9 | A |
| subagent-driven-development | 37 | 153 | 9 | A |
| do-review | 70 | 323 | 24 | B |
| review-code | 28 | 327 | 17 | E |
| review-code-by-standards | 43 | 225 | 17 | E |
| review-code-by-spec | 23 | 36 | 13 | E |
| safety-review | 47 | 58 | 18 | E |
| req-align (+2 sub-skills 59) | 34 | 320 | 13 | C |
| impl-planning + to-tickets | 39+15 | 84 | 16 | C |
| plan-review | 40 | 136 | 13 | C |
| execution-preflight + standing-bookkeeper + verification-before-completion | 43+41+51 | 185 | 19 | D |
| backfill-stable-docs | 25 | 160 | 10 | F |
| grill-me-smartly | 170 | 170 | 30 | F |
| impl-package 入口 + grilling + create-task-dag | 55+37+14 | 248 | 23 | G |
| **合计** | **~860** | **~2,700** | **231（-73%）** | |

插件级 references：situation-inputs.md 864（renderer 字典，主 session 永不读）、current-state.md 61、composition-contract.md 60、progressive-system-evidence.md 58（按需）。

**2026-08 完成**：14 文件全部落盘，测试全绿（仓库级 14 + 插件 evals 22 + do-review tests 12 + grill src）。被合并的旧 SKILL.md 已删（references/rubric/evals 保留按需）；DSH 侧新增 4 个只读 reviewer presets + do-review-orchestrator。
