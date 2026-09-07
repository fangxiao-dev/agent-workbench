# Impl Planning 常见误判

只在 admission、Ticket 拆分/发布、bundle review、state 初始化或 acceptance 投影需要判断时读取。本页承载执行提醒；行为回归只放在 `../evals/evals.json`，不把 eval 当运行时清单。

## 权威规则与真重复

Composition 与 Plan/Ticket ownership 的真重复以 `../../../references/impl-package-composition-contract.md` 和本 Skill 正文为准，本页不再复述。

## Admission 与计划

- 只用已批准且仍适用的 Decision/Spec 写 Plan；未批准或过期事实只能回到 req-align。
- Plan 不补齐 Spec 留白；可观察行为、数据 identity、权限、并发、恢复或 public shape 未冻结时停止 planning，不另造 DTO/schema。
- Patch 只写相对上次 terminal gate 的实际 delta，不重述未变化的 evidence、gate 或历史范围。
- Bundle review 要联合核对全部 Ticket 的 coverage、ownership、order、typed dependency 和 evidence feasibility，不只读 Plan 正文。

## Ticket 合同与证据

- 纵向 Ticket 按可验收终态切分，不按文件或层切半条路径；独立 UI 形状/组件复用若本身可验收，才单独赚取 UI Ticket。
- 每个 Ticket 固定 ID、Attempt、owner 和 typed dependency；到达路径明确标 `EXISTS`/`NEW`，避免把待建设入口当成已有能力。
- Contract reference 指向具体章节；引用 `contract-design.md` 还要点名 Operation/Aggregate/DTO/Seam/Projection 或函数/类 entry point。
- Evidence 要给入口、owner 和 coverage；不同可失败结论或不同 oracle/evidence lane 拆成 stable claims，同一不可分割 oracle 的场景不强拆。
- 只让后端接线通过不能证明 UI 形状或组件复用正确；真实 app shell/fixture 的可观察结果仍需验收。
- 旧 Task `DONE`、一次 early falsification 或部分 claim evidence 都不等于 Ticket 满足；保留 remaining-completion 与第一条路径的 tenant、RBAC、privacy、幂等和数据完整性证据。

## State 与执行边界

- Plan/Ticket 获批前不初始化 runtime state；获批后先 `package init` 再 `package validate`，结果不满足就不进入执行。
- `/impl-package:execution-boundaries` 承接授权、write-set 和完成前 evidence gate；Plan/Ticket 业务文档写入归 owning-stage 主 thread。
- Ticket 发布后不把 Phase、Next、worker、implementation progress 或 runtime acceptance projection 写回 Ticket；进度与验收状态由既有 projection/state 维护。

## 仅进 evals 的回归价值

`../evals/evals.json` 只验证上述规则在模型行为中仍成立，例如缺合同时回 req-align、stable claim 原子化、不可分拆 oracle、真实依赖与轻量调度判断；它不替代本页的执行提醒。
