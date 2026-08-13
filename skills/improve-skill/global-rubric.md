---
target: global
updated: 2026-08-13
---
## 原则

- [已确认] 仓库自写、或对本地 skill 新增和改写的内容统一使用中文行文，保留英文术语 token（如 spec.md、NEEDS_SEAM、Granularity、slug）。
- [已确认] 外部引入的第三方 skill 默认保留上游语言，不因纳入本仓库而强制中文化；已经完成的本地化不要求回退。
- [已确认] Markdown 自然语言不按代码 80 字符硬折行；一个逻辑段落或列表项保持一物理行，换行只表达语义块边界，不能把术语、inline code 或链接拆开。
- [已确认] 低影响操作直接执行；只有风险、不可逆性、语义实质变化或真实设计选择才升级流程。
- [已确认] 优化任何 skill 时，`SKILL.md` 只保留所有调用共需的主路径、路由与完成条件；低频或条件分支下沉到有明确读取条件的 reference，避免为对称性拆分或让主路径依赖未加载细则。
- [待验证] `worker` 是统一的逻辑引用，可解析到 `$skill`、`@agent`、直接 model/profile 或纯 prompt；流程只消费统一 worker contract，不依赖其底层实现类型。（证据: R8）
- [待验证] registry 只登记 worker 引用、resolver 类型与能力元数据；具体 Skill、agent profile、model 或 prompt 各自拥有运行默认和执行细节，流程不得复制。（证据: R8）
- [待验证] 方法论与实际 worker 定义分离；调查、实现和修复可以复用同一 worker，复杂度只增加独立 reviewer gate，不切换主 worker。（证据: R7）
- [待验证] 默认 `$grok-worker` 失败时只允许一次 fresh `@luna-worker` fallback，不回退到主会话；主路径正文保持短小，方法论优先，细节渐进披露。（证据: R9）

## 决策记录（滚动，最近 ≤5 轮）
### R4 · 2026-07-15
- 采纳「低影响直接做」为跨 Skill 原则 — 用户明确要求仅在风险、不可逆、语义实质变化或真实设计选择时升级流程。

### R5 · 2026-07-25
- 采纳「主路径最小化与条件渐进披露」为跨 Skill 原则 — 用户明确要求该优化原则全局适用；本体承载共需流程，条件化低频细则按明确 pointer 下沉。

### R6 · 2026-08-13
- 采纳把 worker 直接定义为类似 `@luna-worker` 的全局可见实体；registry 可以保留，但只引用已定义实体，不承担额外发现层。
- 采纳 `call-grok` 继续作为 executor adapter，保留后台运行、heartbeat 与 JSON envelope 等运行合同。

### R7 · 2026-08-13
- 采纳调查、实现和修复统一使用同一个实际 worker；复杂任务不切换 worker，而是在实现之后增加独立 reviewer gate。
- 采纳继续分离流程方法与 worker 定义；方法论消费 `mode`、`worker` 和 review strategy，不再输出无实际执行价值的 downstream `route`。

### R8 · 2026-08-13
- 修正把 worker 限定为全局 agent entity 的表述；worker 是统一代号，可以由 TOML agent、Skill wrapper、直接 model/profile 或语言 prompt 实现。
- 采纳在同一字段中使用带 namespace 的引用，例如 `$grok-worker`、`@luna-worker`、`gpt-5.6-terra/xhigh`；流程只理解统一合同，resolver 负责实际调用。

### R9 · 2026-08-13
- 采纳默认 Grok worker 的一次 Luna fallback；不回退到 main session。
- 采纳主路径 Skill 正文不超过 180 行，原则和流程优先，条件细节使用渐进披露。
- 采纳 legacy route 自然退休，不新增恢复/拒绝协议；`call-grok` 物理目录暂不重命名。
