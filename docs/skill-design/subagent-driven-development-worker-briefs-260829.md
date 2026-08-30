# subagent-driven-development worker briefs 执行摘要（2026-08-29）

范围：按指定顺序完成目标 Skill 的四份内容文件与 `rubric.md`，共 5 个目标文件；`evals.json` 无需同步。本记录只总结内容与验证边界，不代表发布或安装。

改动：新增 `references/worker-briefs.md`，补齐 `investigate`/`implement`/`fix` 的 prompt 内容边界；`parallel-work-admission.md` 去重三类 dependency 定义并保留 resource 细节；`SKILL.md` 增加 pointer 和 eval id=3 worked example；`review-gate.md` 补七类 material-risk 判断启发式；`rubric.md` 增加 R14。

验证：SDD focused contract `10 passed`；plugin 资源/统一入口/行数定向项 `3 passed`；Skill validator 输出 `Skill is valid!`；eval JSON 解析及逐条一致性审计 `10/10`；L1 相邻合同测试 `57 passed`；DSH `coverage-check` 为 `60/60`。

边界：`do-review`、`skills/dispatcher` 和其它 impl-package Skill 无改动，未运行全仓测试。DSH smoke 未能完成：当前 sandbox 下 Node 的 `spawnSync('python')` 返回 `EPERM`；升级重跑因可能触及用户级 `.agent-presets` 状态被安全边界拒绝，未绕过。除这一项环境性验证缺口外，没有偏离本 prompt 的要求。
