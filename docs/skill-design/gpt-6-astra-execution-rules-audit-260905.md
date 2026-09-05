# GPT-6-Astra 执行规则审阅建议

审阅日期：2026-09-05。下文保留原始 16 项审阅建议及其读取时的位置。Owner 已批准其中 12 项修改，明确保留第 9、13、14、15 项；源码修改由主控执行，subagent 只做独立检查。已批准 12 项的源码修改、定向验证和独立问题复核已收口；安装缓存同步与发布未开展。

## Owner 取舍与实施范围

| 项目 | 已确认决定 |
| --- | --- |
| 1 | AGENTS 仅保留“结合当前消息与本会话已有授权确定范围。” |
| 2 | leaf 自行落盘完整 finding 证据、影响和建议；取消权限层只读，保持业务代码与源 Git 状态不变 |
| 3 | terminal A/B/C＋按需 Safety；A 最终 HEAD 重审，B/C/Safety 在同 ReviewRun 内有据复用旧 PASS |
| 4 | 主控写业务文档并裁决语义；一个记账 subagent 串行执行 CLI 写运行状态与投影，通常异步，依赖落盘或收口时等待 |
| 5、6、8 | 按原因恢复 INCOMPLETE；统一 execution-boundaries 入口；已知 CLI 成功不完整 Restore |
| 7 | 消费返回后立即检查并补派已解锁的独立动作，不等待无关 worker |
| 10 | 未提交 review 使用临时隔离内容快照，不要求提交用户工作区 |
| 11、12 | 复用明确 batch/patch 授权；本轮 apply 的机械错误在同一授权内修复重验 |
| 16 | AC 为可独立验收用户终态，展示、编辑或拒绝结果无需新权威记录 |
| 9、13、14、15 | 保留现有步骤粒度、等待规则、统计失败阻断和 reviewer 模型配置 |

用户最终指令为“改”；随后明确由主控修改、subagent 检查。两个曾派出的实现 subagent 在写入前已停止，没有留下实现改动。实施期间另一个会话推进了 workbench HEAD，包含 runtime-protocol 的部分更新；保留这些提交并在当前工作树继续核对。

## 范围与判断依据

- KaiSpan 当前工作区：`D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation`。文件系统递归清单与 Git tracked/untracked 清单均只发现一份项目自有 `AGENTS.md`；依赖、Git 元数据和构建输出不计入项目规则。
- Impl Package 源码：`D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package`，排除 `dsh-*`。对全量 167 个非缓存文件建立清单并检索规则，重点交叉阅读现役技能、references、agent 定义、处境表、运行时和相关 eval。并非对全部脚本开展逐行正确性审查。
- 安装版：`C:/Users/Xiao/.codex/plugins/cache/agent-workbench/impl-package/0.4.2`。上述 167 个文件与源码逐文件哈希一致，忽略 `__pycache__` 后未发现额外安装文件；因此以下插件问题也存在于当前安装版。
- Dispatcher：`D:/CodeSpace/agent-workbench/skills/dispatcher`，包含正文、rubric 和相关 eval。
- 源码 Git HEAD：`26a9381dfe940d67300f200d8e2e883b3289a369`；KaiSpan Git HEAD：`3c27c5512eb6b956f3437da1546bbcc3d9c5287d`。审阅对象是读取时的工作树内容；两个工作区原本均有其他改动，尤其 workbench 的 monitor-progress 相关文件，并未被本次审阅接管。
- 使用三个 GPT-6-Astra/medium 子代理分别检查调度、审阅链和需求/回刷链，主控检查项目入口、执行状态与跨文件冲突。没有运行实现、review ledger、环境验证或插件安装流程。

OpenAI 的 Astra 指南明确提示：模型更敏感地遵循 skills/AGENTS.md 中的指令，含糊或冲突规则可能使其提前停下；小改动也可能出现过量验证。因此本报告重点检查具体触发条件与实际执行路径，不以“新模型更强”作为撤销安全措施的依据。[官方 Astra 指南](https://developers.openai.com/api/docs/guides/latest-model)

标记说明：**规则冲突**表示现有文本或代码不能给出一致行为；**流程取舍**表示规则原本有意如此，但日常开销值得重新权衡。以下影响来自静态推演，未测量改动前后耗时，也不能证明每条规则最初都是为旧模型加入。已读取 global 与相关 skill rubric；本轮用户明确要求重新审阅历史限制，因此没有用旧的“已确认”偏好隐藏问题。涉及推翻历史取舍的项目会单独说明。

## 按影响排序的建议

### 1. 项目入口把“当前消息”当作授权上限，并把普通状态变化列为暂停理由

**类型：规则冲突；影响：高频，可能阻断整条已授权任务。**

**文件位置 →** [KaiSpan AGENTS.md:11](D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/AGENTS.md:11)

**原指令 →** “handle only the smallest scope the current user message clearly authorizes, and pause to define boundaries before short, ambiguous, or state-changing actions instead of extending historical plans or execution momentum into action.”

**可能造成的影响 →** 用户已经批准实施方案，随后说“继续”或中途询问状态，模型仍可能只按最新一句话判断授权；普通编辑、测试准备和状态记录也都是 state-changing，因而被要求再次停下划边界。这与插件沿用 initial approval 的规则相冲突。问题在于暂停条件过宽，不在于限制未经授权的扩张。

**建议修改方式 →** 改为：“结合当前消息与本会话已有授权确定范围；短回复不自动撤销既有授权。范围明确时继续完成已授权工作；只有缺失信息会实质改变业务结果、目标、权限或不可逆影响，且无法从现有上下文确定时才询问。”

**保留 →** 不扩张任务目标；明确的停止、缩小范围和撤销授权立即生效；生产/共享环境、破坏性操作仍核实精确授权。

### 2. Reviewer 既不能写完整证据，也不能把完整证据返回

**类型：规则冲突；影响：每次产生 finding 都可能额外往返或丢失证据。**

**文件位置 →** [review-track-code.md:32](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/agents/review-track-code.md:32)、[同文件:45](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/agents/review-track-code.md:45)、[subagent-briefs.md:37](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md:37)。其余三个 track agent 有同形规则。

**原指令 →** “Use Bash only for read-only inspection and checks.”；“Full evidence, impact, suggested handoff, and any necessary quotation belong in the parent-supplied review report artifact. Return only this compact index”；common brief 同时要求 “Do not mutate files, issues, git state, data, or external systems.”

**可能造成的影响 →** reviewer 找到问题后无法合法交付完整证据：落盘违反只读合同，返回正文违反 compact-only 合同。主控只能拿短索引重新查证或追问。Codex 安装器也投影这些正文，因此不是仅其他宿主的权限模式问题。

**建议修改方式 →** 让 leaf 直接返回支持 finding 所需的证据、影响和建议，由 parent 统一落盘；删除“只能返回短索引”的硬限制。无需新增报告协议或放宽业务文件写权限。

**保留 →** reviewer 对业务代码、Git 和外部系统只读；同轮独立；parent 负责归类、去重和最终采信。

### 3. 终审正文允许条件 Safety，运行时却要求四轨派发，且未核对返回结果

**类型：文本与运行时冲突；影响：收尾误阻断，并存在提前判定 coverage complete 的风险。**

**文件位置 →** [do-review/SKILL.md:49](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:49)、[review-topology.md:34](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/references/review-topology.md:34)、[situation.py:44](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/scripts/situation.py:44)、[situation.py:2457](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/scripts/situation.py:2457)。

**原指令 →** 正文：“terminal_tracks（Track A/B/C）……按 Safety admission 条件追加 Safety”；运行时：`REVIEW_TRACK_VALUES = ("Track A", "Track B", "Track C", "Track D")`，随后 `if not REVIEW_TRACKS <= tracks: return False`。

**可能造成的影响 →** 未提供显式 coverage fact、尚无 terminal Gate 时，合法的不含 Safety 三轨终审会被机械判断为 coverage 不完整；允许沿用的旧 PASS 也没有被这段代码作为结果证据消费。反过来，这段判定只收集 `dispatch` 并检查 HEAD/source delta，四轨刚派出、尚未返回也可能得到 true。这里指处境层的 coverage 判断，不能直接等同于整个 Gate 已被放行。

**建议修改方式 →** runtime 消费本次已经解析的 required topology 与有效审阅结果；合法复用的 PASS 连同 revision/delta 依据一起判断。不要通过固定四个标签或只数 dispatch 证明审阅覆盖。同步修正文档和锁定旧行为的合同检查。

**保留 →** Safety 适用时必须覆盖；最终 revision 或可解释 delta；required 结果缺失、失败或不确定不能成为 terminal PASS。

### 4. 需求与计划技能仍把日常写文档交给已退役的常驻 bookkeeper 模式

**类型：旧架构残留造成 ownership 冲突；影响：日常需求更新反复转交。**

**文件位置 →** [req-align/SKILL.md:22](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md:22)、[同文件:24](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md:24)、[impl-planning/SKILL.md:43](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md:43)、[execution-boundaries/SKILL.md:64](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:64)、[同文件:102](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:102)。

**原指令 →** req-align：“主 thread 先把已确认的结论、必要依据和依赖性发送给 bound execution-boundaries；由其……写入 canonical artifact”；impl-planning：“主 thread 不直接编辑当前 package 的 Ticket 或 `.impl-package/state.json`”；execution-boundaries：“日常结构化写入由主 thread 直接调用现有语义 CLI”；“Decision、Spec……的日常物理写入由对应 owning stage 的主 thread 执行”。

**可能造成的影响 →** req-align 等待辅助角色落盘，辅助角色却应把日常工作退回主控。主控需要自行解释谁来写，可能重新启动不必要的角色或停在未交付文档。这里有明确的新旧规则分叉，不是抽象的“角色太多”。

**建议修改方式 →** req-align 与 impl-planning 统一采用现行 ownership：owning-stage 主控写 Decision/Spec/Plan/Ticket；state 通过语义 CLI 更新。execution-boundaries 只提供按需的 preflight、异常对账和 completion audit。同步清理交付说明及相关模板中的旧绑定语句。

**保留 →** state 单写者、语义 CLI、owner 的业务裁决和异常证据对账。

### 5. 正文取消固定 fallback 次数，处境表仍在第二次 INCOMPLETE 时默认 BLOCKED

**类型：旧恢复补丁未同步退役；影响：可恢复工作被错误停住。**

**文件位置 →** [runtime-protocol.md:33](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md:33)、[situations.yaml:282](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml:282)、[situations.yaml:297](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml:297)、[dispatcher/SKILL.md:35](D:/CodeSpace/agent-workbench/skills/dispatcher/SKILL.md:35)。

**原指令 →** 正文：“不套固定 fallback 次数……上下文可信则同 lane 继续”；表中第一次：“INCOMPLETE 视为上下文污染/持续卡住……允许一次 fallback”；第二次默认执行 `ticket block`，effect 为“停止第二次 INCOMPLETE 的 fallback”。Dispatcher 则要求先进行 foundation investigation。

**可能造成的影响 →** 同一恢复情形同时得到“继续原 worker”“换 fresh worker”“重新调查”和“BLOCKED”几种答案。表没有把上下文确已失真或安全恢复已耗尽作为第二次阻塞的前置条件。即使可用 escape，主控也要额外解释为何不按旧默认动作执行。

**建议修改方式 →** 以实际原因、上下文可信度和是否存在安全恢复路径判定；重复 INCOMPLETE 触发原因调查，不直接等于业务 BLOCKED。处境表、protocols、正文和 eval 使用同一规则。

**保留 →** 不无限盲目重试；不可归因结果不采信；缺授权、真实外部依赖或无安全路径时如实阻塞。

### 6. Ticket preflight 指向不存在的技能入口

**类型：失效路由；影响：声明 Evidence Lane Contract 的 Ticket 首次激活。**

**文件位置 →** [dev-with-track/SKILL.md:45](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md:45)、[execution-boundaries/SKILL.md:25](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md:25)。

**原指令 →** “调用 `/impl-package:execution-preflight` 核 URL identity、端口 owner、库分离和 cleanup owner”。

**可能造成的影响 →** 当前插件没有这个独立 skill 的 SKILL.md 或可调用入口；其职责已经合入 execution-boundaries。严格遵循者会搜索缺失技能、报告能力不足或请求用户处理，而现有流程已能执行该检查。

**建议修改方式 →** 直接路由 `/impl-package:execution-boundaries` 的“Ticket 首次激活”部分；检查同类旧技能名的引用，不再新增兼容包装技能。

**保留 →** URL/数据库身份、端口 owner、库隔离和 cleanup owner 四项检查原样保留。

### 7. 整批收齐才重扫，使无依赖工作等待最慢 worker

**类型：流程取舍兼正文冲突；影响：并行任务的关键路径被人为拉长。**

**文件位置 →** [dispatcher/SKILL.md:30](D:/CodeSpace/agent-workbench/skills/dispatcher/SKILL.md:30)、[同文件:33](D:/CodeSpace/agent-workbench/skills/dispatcher/SKILL.md:33)、[dev-with-track/SKILL.md:16](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md:16)。

**原指令 →** “当前批次的 receipt 与 return 全部确认或消除歧义后，再全局扫描候选并形成下一批”；同时要求“只有不延迟已解锁的独立动作时才合并”。

**可能造成的影响 →** A 的调查 2 分钟结束并解锁 A2，无关 B 的验证还需 30 分钟；主控可以消费 A，却不能形成下一批释放 A2。后续工作被绑定到 B 的耗时，而不是实际 dependency。

**建议修改方式 →** 消费一个 return 后检查受影响候选，允许补充派发；整批结束或准备 idle 时再全局扫描。无需新增队列、资源矩阵或持久调度对象。

**保留 →** 结果有歧义的执行继续占用其资源；真正依赖与共享可变资源仍阻塞相关步骤。

**历史取舍 →** dispatcher rubric 明确确认过 batch drain；此项是在保留低主控负担目标下重新权衡，不应只改正文而保留相反 eval。

### 8. 每次自身 state mutation 后都完整恢复，把正常写入变成恢复成本

**类型：过宽触发条件；影响：高频主控额外读取与校验。**

**文件位置 →** [dev-with-track/SKILL.md:39](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md:39)、[runtime-protocol.md:9](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md:9)、[impl_package_hooks.py:311](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py:311)。

**原指令 →** “任何 state mutation 之后，执行下方完整恢复顺序”；该顺序包含 validate、打开 progress、重选动作、admission 和材料读取。Capsule 另提示：“Before dispatch or trail mutation, rerun situation.py render without --no-write-credential.”

**可能造成的影响 →** 主控刚通过语义 CLI 成功登记 evidence 或状态，下一轮仍要按失配恢复处理；hook 的提示又把 render 前置扩大到所有 trail mutation，而 runtime 的 digest 校验针对 dispatch。自己的成功写入不断触发额外流程。

**建议修改方式 →** 区分“旧 Capsule 已过期”和“当前主控事实已失效”：成功 CLI 返回后消费更新结果、按需刷新投影；完整恢复留给 session 恢复、未知并发变化、CAS 失败、部分写入或身份漂移。digest 在实际需要的 dispatch 边界刷新，不为每条 fact/worker-return 重渲染。

**保留 →** mutation 校验、CAS、projection 一致性、真实 dispatch credential，以及出现未知状态变化时的完整恢复。

### 9. Baby step 按主控 return point 切分，却没有明确哪些中间结果真的需要决策

**类型：流程取舍，eval 进一步固化；影响：主控重复组织 prompt、验收和再授权。**

**文件位置 →** [dispatcher/SKILL.md:16](D:/CodeSpace/agent-workbench/skills/dispatcher/SKILL.md:16)、[SDD/SKILL.md:41](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md:41)、[SDD evals.json:98](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/evals/evals.json:98)。

**原指令 →** “当前派发不跨越第二个主控 return point”；eval 要求“四段分别形成 baby step……每段都先 return 并由主控验收后再授权下一段”。

**可能造成的影响 →** 已批准的纵向功能即使接口、write-set 和验证目标都明确，仍容易按事务、DTO/contracts、UI 等技术段切开。所谓 return point 可以被任意设置，导致“完整 coherent outcome”原则失效。这里是主控部再授权，文本不等于要求每次问用户。内

**建议修改方式 →** return point 仅指尚未裁决、必须消费中间结果才能决定后续工作的边界；方向、接口和写集稳定的有界 outcome 可以一次交付。只有中间结果会改变授权、ownership、业务选择或实际并行释放时才拆分，并同步修订无条件按技术层切分的 eval。

**保留 →** 禁止跨越真正未决的业务/权限边界；worker 局部交付不自动成为 Ticket 或 package 验收。

**历史取舍 →** 这是对 rubric 已确认的 return-point 粒度重新权衡，不建议取消 Topic 或必要主控决策。

### 10. 普通只读 review 被强制绑定到创建 Git commit

**类型：流程取舍兼授权冲突；影响：审阅未提交改动前增加 Git 操作或停顿。**

**文件位置 →** [do-review/SKILL.md:21](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:21)、[同文件:76](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:76)。

**原指令 →** “ReviewRun 创建前先提交完整 review unit……review 相关未提交改动阻断”；末尾又要求“除明确要求外不修改……Git state”。

**可能造成的影响 →** 用户只要求“审一下当前改动”，流程要先整理提交范围、改变 Git 或询问授权。固定审阅对象是合理目标，但本地 commit 不是所有只读审阅的唯一办法。

**建议修改方式 →** 已有 PR/commit 使用固定 SHA；未提交审阅允许固定内容快照，明确 base、diff 和纳入的 untracked 文件。没有稳定快照能力时准确说明限制；不要默认把审阅请求升级为提交请求。最终 package Gate 仍可要求其所需的 committed comparison。

**保留 →** 审阅对象不可漂移、完整 change unit、明确 out-of-scope 和来源证据。

**历史取舍 →** do-review rubric 的 R8 明确批准过 commit 前置；采纳本项需要同步替代该规则及相关合同检查，而非偷偷绕过。

### 11. 清楚的既有授权仍被要求换一种格式再确认

**类型：流程取舍与缺少授权复用条件；影响：用户重复确认。**

**文件位置 →** [backfill apply-runbook.md:3](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/apply-runbook.md:3)、[req-align/SKILL.md:31](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md:31)。

**原指令 →** “禁止把‘将报告全部处理’解释为批准”；“存在可 patch 的相关 package 时，必须先询问 Owner 是否进入 patch 模式”。

**可能造成的影响 →** 第一处即使报告已固定、候选无冲突且全是普通更新，用户明确说“全部应用”仍不被接受，必须逐 ID 重述。第二处没有明确先消费“对 package X 做 patch”这类当前请求，容易在已有清楚授权时再问一次；其风险是措辞诱导重复确认，不是说所有实现都会如此解释。

**建议修改方式 →** 先核对用户是否已经明确授权目标和操作；对已展示且未变化的有限报告，允许把自然语言批量批准解析并记录为精确 item ID。只有目标、集合或操作仍不明确才询问。

**保留 →** 仅发现相关 package 不等于允许改写；冲突项、未决业务选择、删除/退休和新增外部副作用不能被普通批量授权自动吸收。

**历史取舍 →** 保留 backfill 内部精确 ID，改变的是用户必须按机器 ID 表述批准的负担。

### 12. Verify 只读被扩大为禁止修复已授权 apply 自己造成的错误

**类型：流程取舍；影响：任务停在本可自行修正的不合格结果。**

**文件位置 →** [backfill-stable-docs/SKILL.md:61](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md:61)、[verify-runbook.md:3](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/verify-runbook.md:3)。

**原指令 →** “失败只报告，不自动修复”；“Verification never repairs failures automatically.”

**可能造成的影响 →** 本轮批准的文档更新写错链接或 done record 格式，修正不改变语义、不扩大 destination，流程仍停住。把检查器保持只读与编排者能否回到已授权 apply 混为一谈。

**建议修改方式 →** verifier 保持只读；编排者可回到同一已授权 apply，修复本轮造成的机械缺陷并重跑 verify。只在新增语义、destination、无关问题或破坏范围变化时请求缺失决定。

**保留 →** 不让验证脚本自行改文件；不顺手修复既有无关问题；不扩大原批准 item 集合。

### 13. 等待规则既规定最低分钟数，又否认合法的等待下一动作

**类型：含糊且互相牵制的执行约束；影响：无必要等待、轮询或补做无关工作。**

**文件位置 →** [SDD/SKILL.md:22](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md:22)、[dev-with-track/SKILL.md:20](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md:20)。

**原指令 →** “普通实现至少观察 15 分钟，shared seam 调研至少观察 30 分钟”；“判断是否异常只看有没有可观察的活跃信号”；另有“等待 review、fix 或长时验证返回不构成下一动作”。

**可能造成的影响 →** 明确失败或反复同错的 worker 仍可能被要求等满时限；反之，持续输出不代表实际进展。所有独立工作已经释放时，主控又不能把等待剩余验证视为合法下一动作，容易继续检索、额外开 worktree 或重复检查以满足文字要求。

**建议修改方式 →** 删除固定最低分钟数；依据宿主状态、最后有效进展和明确错误决定查询或中断。全局扫描没有可独立推进动作时，允许“等待指定在途结果”成为下一动作，并用宿主事件等待；不为保持忙碌创造工作。

**保留 →** 时间长本身不能成为抢做、重复派发或中断依据；重派前核实旧执行状态和资源；仍有独立工作时继续推进。

### 14. 统计记录失败被提升为审阅本身 INCOMPLETE

**类型：不必要的硬耦合；影响：主控为交付已有结论先修统计链。**

**文件位置 →** [do-review/SKILL.md:64](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:64)。

**原指令 →** canonical ledger 原子更新后必须记录 `review.canonical_summary`；“记录失败使本轮 canonicalization INCOMPLETE，不得只留下 Markdown ledger”。

**可能造成的影响 →** reviewer 结果与 parent 的证据核对都已结束，trail 的路径、锁或输入校验故障仍使整轮被视为不完整。主控需要先修统计基础设施，或再次处理本已确定的审阅结果。

**建议修改方式 →** 区分“审阅结论已形成”与“package 记录待补齐”。保留待重试输入并补记，不因统计失败抹掉有效结论；若 package Gate 要求记录齐全，保留该独立收口条件，不重跑 reviewer。

**保留 →** canonical ledger、finding 稳定 ID、完整证据和缺证据不 PASS；未补齐的记录如实可见。

### 15. Reviewer 模型被安装器锁定，宿主或 Owner 的模型选择难以生效

**类型：配置与方法规则不一致；影响：指定 Astra 时可能卡在固定角色配置。**

**文件位置 →** [install_codex_agents.py:21](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py:21)、[同文件:123](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py:123)、[do-review/SKILL.md:50](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:50)。

**原指令 →** 四个 reviewer profile 全部硬编码 `gpt-5.6-sol` 和固定 effort，并无条件写入 Codex role；正文却说 worker 选择使用宿主 defaults 并受显式约束。

**可能造成的影响 →** 主控在 Astra 上运行并不意味着 reviewer 必须换模型，Sol 本身也不是问题。但当用户明确要求 Astra/medium reviewer 时，mandatory matching leaf 与不可覆盖的旧 profile 会冲突；主控只能违背模型选择或停下来处理角色配置。

**建议修改方式 →** 保留角色职责和 skill 映射，模型默认继承宿主，或由单一宿主配置来源覆盖；显式用户选择优先。不要仅把硬编码从 Sol 改成 Astra。同步调整锁定具体旧模型元组的安装器检查。

**保留 →** 独立 reviewer、所需审阅职责、宿主实际支持的模型/effort 约束；不声称 Astra 一定更便宜或能减少必要审阅。

### 16. Spec Gate 把“每条 AC 产生新权威记录”设成通用要求

**类型：验收合同冲突，不是权限问题；影响：正常展示或拒绝路径被迫扩张设计。**

**文件位置 →** [spec-gate.md:18](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md:18)、[spec 模板:91](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md:91)、[impl-planning/SKILL.md:45](D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md:45)。

**原指令 →** “每条 AC 恰好覆盖一个权威转换：用户完成一个动作、成功后系统产生一份新的权威记录，下游从此读取它”。下游 planning 却允许不产生新权威记录的展示/编辑终态。

**可能造成的影响 →** 只读展示、权限拒绝或预览 AC 无法满足 Spec Gate。主控可能返回需求阶段反复改写，或为了通过流程而发明持久记录，给本来不需要 mutation 的功能增加实现负担。

**建议修改方式 →** 复用已有“可验收用户终态”的表达：每条 AC 对应一个可独立验证的可观察结果；只有发生权威状态转换时才要求明确唯一记录、producer 与下游消费。

**保留 →** oracle、唯一 authority、权限拒绝证据、真实发生 mutation 时的幂等/并发/恢复合同。

## 必须保留的安全与验收边界

- 初始任务或明确新增风险所需的授权；未授权的生产/共享环境 mutation、部署、迁移、删除、消息发送等外部副作用不因模型升级而豁免。已经给出的精确授权应复用，不机械重复申请。
- tenant isolation、RBAC、文件安全、隐私脱敏、金额与幂等约束；真实资源冲突和未稳定业务依赖不能被“提高并行度”绕过。
- 必要的实现/审阅独立性；required review 没返回不能当 PASS；worker DONE 不等于 Ticket 或 package 验收。
- state 的单写者与语义校验、不可归因证据不采信、completion claim 不宽于 evidence、terminal 后如实保留历史。
- stale 或冲突证据只影响相关范围；依赖没有变化的有效 evidence 可复用。现有规则中这类增量验证与授权复用设计值得保留。

## 建议采用顺序与验证边界

1. **先修确定冲突：1–6。** 统一有效授权、证据交付、终审判定、写入 ownership、恢复规则和路由。优先收益是消除执行者必须自行裁决的互斥指令。
2. **再调主控成本：7–13。** 允许按实际依赖补充派发，降低自身状态写入后的恢复成本，以真实决策点拆步骤，并使明确授权与合法等待能够被直接消费。
3. **最后处理耦合与合同：14–16。** 分离记录故障与审阅结论，解除模型配置硬绑定，修正通用 AC 的过窄定义。

若后续批准修改，应同步更新直接约束这些行为的 references、处境表、宿主投影和 eval，避免只改 SKILL.md 留下第二套执行规则。验证优先用具体反例：无 Safety 三轨、review 尚未返回、固定输入下复用 PASS、无可写 artifact 的 finding、连续可恢复 INCOMPLETE、A 返回但 B 仍运行、明确批量授权、已授权 apply 的机械修复、只读展示 AC。无需为了本次建议新增预算、模板、持久队列或另一套审批系统。

原始建议不是性能实测。上方 Owner 取舍记录了后续明确批准的变更范围；仅执行该范围的源码修改与验证，不包含安装、合入或发布。


## 实施验证记录 · 2026-09-05

- 主控完成已批准 12 项源码修改；第 9、13、14、15 项与审阅基线的受保护规则逐句核对，保持不变。实现 subagent 在写入前已停止，后续 subagent 均为只读检查。
- 定向套件：`python -m pytest plugin-marketplace/plugins/impl-package/skills/do-review/tests tests/test_situation_render.py tests/test_dispatcher_contract.py tests/test_standing_bookkeeper_contract.py tests/test_impl_package_hooks.py tests/test_dev_with_track_situations_review_vocabulary.py tests/test_impl_package_agents.py tests/test_dispatch_fix_contract.py tests/test_impl_package_step8_evals.py tests/test_role_skill_contract.py tests/test_low_impact_skill_paths.py tests/test_impl_package_plugin.py -q --tb=short`：175 passed。
- 邻接 CLI 套件：`python -m pytest tests/test_impl_package_state.py tests/test_review_track_stats.py tests/test_dispatch_audit.py -q --tb=short`：70 passed。
- 独立检查后补测：terminal coverage / terminal Gate 场景 10 passed；`skills/do-review/tests/test_review_ledger.py` 16 passed。它们与前两组部分重叠，不累加为独立测试数量。
- 已修复独立检查发现的 Gate 短路、report 重复冒充 Track、失败快照残留，以及统计写入绕过记账单写者的问题。统计失败仍保留 INCOMPLETE。
- Skill 格式校验与 `git diff --check` 通过；检查未涉及 monitor-progress 既有改动的行为验收。
- 未执行插件安装/缓存同步、用户分支提交、push、merge 或发布；ReviewRun 的临时快照提交仅发生在隔离临时仓库。

- 最终独立只读复核：R1–R6 全部 PASS；未新增阻断问题。当前 10 个修改技能通过格式校验，安装缓存仍有 40 个相关源码文件不同，缓存同步不在本轮执行范围。

## 实际修改文件与逐行审核入口

当前未提交部分：workbench 本次 46 个已跟踪文件，已排除 11 个原有 monitor/dashboard 文件；另有本报告和 KaiSpan AGENTS.md。逐行差异见 [本次差异](gpt-6-astra-execution-rules-changes-260905.diff)。该文件只供审核，跨两个仓库，不作为统一 apply 补丁。

`dev-with-track/references/runtime-protocol.md` 的本次更新已被另一个会话在 82055d8 中一并提交，因此不出现在当前未提交 diff；它仍属于本次核对范围，其中轻量 delta review 的其他变化属于该并行会话。

需要特别审核的实现选择：

- 第 3 项新增 `review.terminal_summary` structured fact，并要求各 report 前四行含 verdict、reviewed-head、review-run、review-track；renderer 校验结果、独占报告路径及复用证据。它没有新增 state schema 或第二份 ledger，但增加了 report 的格式要求。
- 第 10 项新增 `--working-tree` / `--include-untracked`，在临时 Git clone 内复制工作树改动并创建快照 commit，保持源分支、index 和工作文件不变；采集期间变化或后续校验失败时清理本次快照。
- 第 4 项是流程职责调整：复用现有 subagent 与语义 CLI，未新增常驻服务、队列或后台调度代码。

实际待提交文件：

- `plugin-marketplace/plugins/impl-package/agents/review-track-code.md`
- `plugin-marketplace/plugins/impl-package/agents/review-track-safety.md`
- `plugin-marketplace/plugins/impl-package/agents/review-track-spec.md`
- `plugin-marketplace/plugins/impl-package/agents/review-track-standards.md`
- `plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py`
- `plugin-marketplace/plugins/impl-package/references/codex-hooks.md`
- `plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md`
- `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md`
- `plugin-marketplace/plugins/impl-package/references/plan-apply-runbook.md`
- `plugin-marketplace/plugins/impl-package/references/situation-inputs.md`
- `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json`
- `plugin-marketplace/plugins/impl-package/scripts/situation.py`
- `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/apply-runbook.md`
- `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/references/verify-runbook.md`
- `plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/control-flow.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`
- `plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md`
- `plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md`
- `plugin-marketplace/plugins/impl-package/skills/do-review/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py`
- `plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_review_ledger.py`
- `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/execution-boundaries/references/role.md`
- `plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/impl-planning/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/plan-review/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/decision/SUB-SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/spec/SUB-SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/review-code/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/evals/evals.json`
- `skills/dispatcher/SKILL.md`
- `skills/dispatcher/evals/evals.json`
- `skills/dispatcher/rubric.md`
- `tests/test_dispatcher_contract.py`
- `tests/test_situation_render.py`
- `tests/test_standing_bookkeeper_contract.py`
