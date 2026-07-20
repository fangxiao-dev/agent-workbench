# Independent Eng Plan Review 设计工作区

本目录保存 `eng-plan-review` 的设计期材料。它用于 proposal 修订、旧版语义对照、eval 记录和实现前的临时分析，不是正式 skill 的运行时目录。

## 当前文档

- `independent-eng-plan-review-skill-plan.md`：当前设计与实施 proposal，是本专题的主文档。
- `parity-matrix.md`：现有 gstack `plan-eng-review` 到新 skill 的语义保真与 eval 映射；只服务设计和验收，不进入正式 skill prompt。
- `eval-notes/`：需要保存对照运行、blind comparison 或人工裁决记录时按需创建。

## 边界

- 正式 skill 计划创建在 `skills/eng-plan-review/`。
- Runtime Review Ledger 始终写入用户 OS temp 下的 `eng-plan-review/`，不得写入本目录。
- 其他 7 个 gstack skills 的 deprecated 迁移是 proposal Phase 0 的独立仓库治理变更，不在本目录中直接执行。
- 临时分析在形成稳定结论后应合并回主 proposal、parity matrix 或 eval 结果；不要让本目录成为新的运行时依赖。
