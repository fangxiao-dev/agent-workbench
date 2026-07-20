---
target: skills/deprecated/module-review
updated: 2026-07-20
status: deprecated
---

## Deprecated compatibility archive

- 本目录仅保存旧 module-review 双轴 workflow，不能作为 active reviewer 使用。
- 新 review 必须由 `do-review` 调度 `standards-review` 与 `spec-review`；不得把本目录加入 active registry、preflight 默认值或 harness manifest。
- 原双轴职责保真保留：Standards 负责仓库规范与 codebase-design judgement baseline，Spec 负责需求与 contract fidelity。
- 原 workflow 要求调用者提供 fixed comparison point；两个轴独立输出，不能合并 findings。
