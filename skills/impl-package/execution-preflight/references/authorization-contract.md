# Authorization Contract

Owner authorization 至少明确：目标、范围/write-set、允许的 mutation、禁区、验收和需要 HITL 的动作。

任务生命周期授权需要区分：创建新产物、更新既有产物、恢复先前 Attempt，以及是否允许外部 mutation。对 destructive、production/shared mutation、push、merge、release 和数据迁移分别取得明确授权；一个动作的批准不向其他动作扩张。

同 session 中，清晰 approval 可直接沿用到未变化的 candidate。跨 session 时记录批准所在 Git commit，并比较当前 diff：

- 只影响已授权实现细节：可继续；
- 改变 Decision/Spec/Plan、public contract、数据/安全边界或外部 mutation：重新请求 owner；
- 无法确认：停下并报告缺口。

本合同不建立第二套内容身份或 approval 状态。Git commit 和实际 diff 已足以承担版本边界。

委派执行仍由 `$subagent-driven-development` 编排；本合同只传递任务特定授权，不定义 worker 角色或业务 prompt。
