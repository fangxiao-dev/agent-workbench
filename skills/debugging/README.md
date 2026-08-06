# Debugging Skills

本目录按调试生命周期聚合普通 skill，不提供总路由，也不包含 `SKILL.md`。

- `skills/diagnosing-bugs/` 是唯一诊断入口，负责建立 feedback loop、复现、最小化、确认 root cause、选择正确 test seam，并在最后复验原始症状。
- `skills/diagnosing-bugs/sub-skills/bug-fix-tdd/SUB-SKILL.md` 是诊断后的修复执行器，仅在 root cause 与正确自动化 seam 已确认后执行 RED–GREEN–REFACTOR。
- `skills/diagnosing-bugs/references/` 保存只在特定症状出现时读取的 technique，避免主 skill 被低频细节淹没。

`systematic-debugging` 原版已 retire；完整内容保存在 deprecated Superpowers 归档中。
