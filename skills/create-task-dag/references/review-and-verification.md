# Review 与验证

worker 返回后或关闭 slice 时读本文件。

## Review 层次

- **任务 spec review**：确认 worker 满足了其有界任务契约。
- **任务质量 review**：确认 worker 的 patch 可维护且经过本地测试。
- **Whole-slice review**：确认集成后的 vertical slice 满足原始 slice
  来源。

不要只凭任务级通过就关闭 slice。任务级通过会漏掉断裂的 seam、重复的
fallback 策略、缺失的 route prop、i18n 漂移和外部 smoke 缺口。

## Main Session 集成检查

最终 review 前，main session 验证：

- 共享契约仍然只有一个含义；
- 没有两个 worker 实现了互相竞争的 fallback 规则；
- route/page prop 和共享导出只接线一次；
- i18n key 在每个 locale 都存在且语义未漂移；
- 测试覆盖 slice 级行为，不只是孤立 helper；
- process/progress/handoff/tracking 记录与实际运行一致。

## 验证 Gate

worker 跑各自 ownership 的聚焦测试；main session 在集成后跑 slice 矩阵。

UI 改动：

- 在真实浏览器中验证改动的 route；
- 未指定 viewport 时覆盖 desktop 和受限 viewport；
- header、drawer、菜单或浮层变化时记录 sticky/floating 元素几何；
- 表格/列表布局变化时记录横向 overflow 状态。

外部系统：

- 外部 smoke 只在本地和浏览器证据之后运行；
- mutation 前打印并确认非生产目标身份；
- 使用唯一 marker；
- 记录创建/更新的 record ID；
- 回读被证明的字段/行为；
- 清理，或记录保留的残留及清理失败原因。

## 最终报告形状

slice 完成时报告：

- 已提交的改动或脏文件；
- worker cohort 和 main session 处理的 seam；
- 运行的命令和结果；
- 浏览器证据；
- 外部 smoke 运行与否及原因；
- 残余风险；
- 最终 whole-slice review 状态。

## 持久化

standalone 模式下，review 和验证证据可留在对话内、当前 plan 或用户指定的
handoff/进度产物中。

存在 `dev-with-track` workspace 时，按 `SKILL.md` 的持久化映射落盘；任务
局部的 review finding 写入 `tasks/Tn-progress.md`。
