# SKILL 降载基线（2026-08 起）

改造前实测行数（md 文件；evals/scripts/assets/tests 除外）。目标：主文件 ~860 → ~230 行；references 改按需读。

| SKILL | 主文件 | 目录 md 合计 | 目标 | 组 |
| --- | --- | --- | --- | --- |
| dev-with-track | 67 | 118 | ~12 | A |
| subagent-driven-development | 37 | 153 | ~10 | A |
| do-review | 70 | 323 | ~18 | B |
| review-code | 28 | 327 | ~15 | E |
| review-code-by-standards | 43 | 225 | ~15 | E |
| review-code-by-spec | 23 | 36 | ~12 | E |
| safety-review | 47 | 58 | ~15 | E |
| req-align (+2 sub-skills 59) | 34 | 320 | ~18 | C |
| impl-planning + to-tickets | 39+15 | 84 | ~20 | C |
| plan-review | 40 | 136 | ~12 | C |
| execution-preflight + standing-bookkeeper + verification-before-completion | 43+41+51 | 185 | ~35 | D |
| backfill-stable-docs | 25 | 160 | ~12 | F |
| grill-me-smartly | 170 | 170 | ~35 | F |
| impl-package 入口 + grilling + create-task-dag | 55+37+14 | 248 | ~25 | G |
| **合计** | **~860** | **~2,700** | **~230** | |

插件级 references：situation-inputs.md 864（renderer 字典，主 session 永不读）、current-state.md 61、composition-contract.md 60、progressive-system-evidence.md 58（按需）。
