# Live package reference：处境提示与 terminal Gate 阻断

日期：2026-08-21  
范围：`impl-package` 的 situation renderer、`dev-with-track` 处境表、protocol 注入和 `command_gate`。

## S1 盘点：fact 体系与边界

- `plugin-marketplace/plugins/impl-package/scripts/situation.py` 的 `Fact`/`Fact.as_json()` 是 renderer 的事实输出形状；`WHEN_PARSERS` 是 YAML `when` key 的实现注册表，`_derive()` 负责按 package/attempt/ticket/finding subject 求值，`_situation_digest()` 只投影命中的 candidate。
- `PackageReader` 已统一处理当前 worktree 与 `--at` Git commit 的 package-relative 读取；因此新事实应扫描现有 `decision.md`、`spec.md`、`plan.md`、`tickets/**.md`，而不是添加 `inheritsFrom` 或其它 package 字段。
- `docs/implementations/retired.json` 是退休判定的唯一输入；当前仅有 1 个 `packages[].package_id`，`.stable-docs-backfill.json` 不存在且不作为本任务依赖。缺失的 package 文档按“没有引用”处理为 known `false`；真正读失败或退休清单不可读才返回 unknown（U）。
- `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:command_gate` 先完成现有 state、commit、durable delta、Ticket/evidence 校验，再写入 terminal Gate；live-reference 检查必须只放在 `verdict == pass` 的 terminal 路径，不能影响 `blocked`/`fail`/`defer` 或 U。
- 基线为 52 个既有 `tests/fixtures/situations/*/expected.json`；实现后逐个复核，预期所有既有 fixture 的新事实均为 known `false`，因此既有 expected、undetermined 计数和 digest 不变。另构造独立 live-reference fixture/临时 package 验证 true → 处境命中 → pass Gate 拒绝。
- 3.4 恢复/迁移合同虽存在，但当前 3.5 state 没有 owner 明确授权的可判据标记；不硬造豁免，阶段文档最终记录该豁免暂未实现。

## S2 fact、处境行与协议

- 新增 computed fact：`package.references.live_package`。它扫描 `decision.md`、`spec.md`、`plan.md` 与 `tickets/**.md` 中的 `docs/implementations/<id>/` 路径；当前 package 自引用忽略，`retired.json` 中的 package 忽略，其余引用返回 known `true`。
- 取值方向已固定为：合同文档不存在不构成错误，扫描无 live hit 返回 known `false`；文档 I/O 错误、Git 读取错误或 `docs/implementations/retired.json` 缺失/非法返回 U。true 的 `Fact.reason` 保留 `文件: 路径` 条目，供 renderer JSON 和 Gate 错误复用。
- 同一 helper 同时支持 worktree 与 `--at` commit 读取；未新增 package 字段、trail fact 字段或 `inheritsFrom`。
- 新增处境 `package.record.live-package-reference`（P0，与 `package.record.*` 同层），默认动作 `/impl-package:backfill-stable-docs`，要求先吸收被引用条目再改当前 package 引用 stable docs，`escape: true`。
- `protocols.json` 已加入同 slug 的一行判断：活体可被 patch attempt 改动，引用方不会收到通知。
- S2 局部验证：`py_compile` 通过；`situation.py check` 通过（60 situations、70 implemented when keys）；协议 JSON 可解析。

## S3 terminal Gate

- `engine.command_gate` 在已有 pass 的 Ticket/release/evidence 校验之后、清空 checkpoint 与写 `gate.md` 之前调用同一 computed fact。只有 known `true` 才抛出 `StateError`；U 不阻断，非 pass verdict 不调用该拒绝逻辑。
- 新增 `tests/test_live_package_reference.py` 构造临时 Git package，使用真实 `situation.py render --json` 与 state CLI `gate pass` 做回归。实际输出如下（digest 为本次临时 package 的运行值）：

  ```text
  RENDER_OUTPUT={"digest":"df6c6df68c13","selected":"package.record.live-package-reference","fact":{"value":true,"status":"known","reason":"发现活体 package 引用：spec.md: docs/implementations/260801-live-contract/"}}
  GATE_OUTPUT=pass Gate rejected: 发现活体 package 引用：spec.md: docs/implementations/260801-live-contract/；先将每条引用通过 /impl-package:backfill-stable-docs 吸收进 stable docs，再把当前 package 改为引用 stable docs
  ```

- 独立回归测试结果：`1 passed`。Gate rejection 未写入 terminal Gate；错误信息同时包含具体文件/路径与 `/impl-package:backfill-stable-docs` 路由。

## S4 验证

待实现。
