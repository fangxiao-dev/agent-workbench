---
name: subagent-driven-development
description: 当调查、实现、修复或验证需要主 session 与 worker 协作时使用；在启动前形成 mode、具体 worker 和 review 策略，并消费统一结果。
---

# Subagent-Driven Development

唯一 worker 编排入口：把已确定的 bounded unit 变成可执行策略并在主 session 集成前收口结果，不重写业务需求、Ticket、授权或验收。逻辑角色（investigate/implement/fix/review）→ provider 的映射与策略格式由 preset/orchestrator 承接，本 skill 只保留以下判断。

- **mode**：investigate 在事实不足时取证（返回 EVIDENCE_SUFFICIENT|EVIDENCE_GAP，只释放实施判断不释放授权/验收/Gate，禁 READY|BLOCKED）；implement 消费已释放单元；fix 只接已确认且边界化的 finding，必须 fresh invocation、不重新裁决、不宣称 closure；review 只跑既定无写副作用的检查。main-session 仅用于原子本地动作且须写明 reason；investigate/implement 可沿用同一逻辑 worker，复杂度只增 reviewer gate 不自动换 implementer，reuse 仅限同一 source unit 的不可转移 live state。
- **review**：shared seam、安全、数据完整性、并发、migration、不可逆外部副作用或 policy 要求时必选 required，scope 显式为 checkpoint|closure，非显然选 none 记 reason；不为每个文件或小动作加 checkpoint；reviewer 独立 fresh，finding 交 fresh fixer 按同一 scope 重审。
- **并行与失败**：共享可变运行资源必须隔离，不能隔离就串行并记录顺序/owner/cleanup，全部返回后由主 session 做集成验证；解析失败、授权不匹配或 brief 不完整时启动前 BLOCKED，不猜近似 worker；仅默认 worker 的 INCOMPLETE 允许一次 fresh fallback（进程已清理、diff 可归因），业务 BLOCKED 不 fallback，二次 INCOMPLETE 归一 BLOCKED。主 session 始终负责最终集成、证据采信、Ticket acceptance 与 Gate；worker 局部 DONE/review PASS 不代表 package 完成。
