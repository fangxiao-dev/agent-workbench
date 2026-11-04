# SKILL 降载审校清单（主控自核，不外包）

改动 Impl-Package SKILL 后按此清单逐项过一遍。任何一项缺失/变味 → 打回或主控补写。

## 语义正确性（必须逐项保留）

- [ ] **Gate 三态**：blocked 保持 active（记录 gap+next）；pass 需 earned Ticket/验证/review/manual acceptance/findings closure 全满足；fail/defer 如实终结、后续走 patch Attempt
- [ ] **terminal Gate Stage 7**：Durable Delta + `_pending.md`/truth pointer，或 `--no-durable-delta-reason` 明确无增量；terminal 后 state/checkpoint/ER 冻结
- [ ] **SATISFIED 前提**：当前 revision+environment、覆盖全部 required claims、无未处置 contradictory/inconclusive、acceptance revision == comparison commit
- [ ] **RETIRED**：waived 可释放边；superseded 需 successor 且 successor 满足释放条件
- [ ] **escape 写法规格**：偏离建议或处境表未覆盖 → 一行 kind=escape 轨迹（subject/deviation/reason）；escape 是唯一不产生产物、不可推导的事件
- [ ] **trail 只追加**：不重写历史；写错补 fact/说明
- [ ] **checkpoint 语义**：只记录下一动作+恢复证据，不授权派发、不释放依赖；BLOCKED/retry/跨 session/交接时写
- [ ] **P0/P1/P2 fail-closed**（safety-review）：P0 block；P1 合入前修复或 owner 接受缓解；P2 补证或记录接受
- [ ] **fast path 条件**（req-align）：business result/Acceptance Semantics/security-data constraints/mutation authority 均未变化；删除改变 promise 即 contract-impacting
- [ ] **Safety admission 六类边界**（do-review）：auth/授权与租户隔离、数据完整性/钱/库存/订单/客户状态、并发/事务/幂等、schema 迁移、外部副作用；记录匹配边界与证据；不把关键字当充分证据
- [ ] **finding 分类**：blocker（业务数据/安全/运行时可见）、follow-up、backlog；去重按 broken invariant 而非路径/reviewer
- [ ] **Loop 收敛**：最新轮无新 accepted + 全部 track dormant；clean 需连续两轮；dormant 非永久移除
- [ ] **closure 不替代 terminal-final**：terminal 需最终 HEAD 上完整 applicable topology
- [ ] **Track C source recheck**：接受并归类为 Spec fidelity 后的一次性独立检查；结论三选一（sources 唯一裁决/req-align/owner）
- [ ] **claim-evidence 五条**（verification）：直接执行/检查、同 worktree/revision/environment、晚于最后影响变化、含 command/exit/failure count/artifact、覆盖 gate；相邻 evidence 不能替代
- [ ] **真实状态报告**：implemented, not verified / Integrated, gate open 等，不得把 confidence 当 completion
- [ ] **READY/BLOCKED 边界**（preflight）：缺授权/下一步不安全破坏性/安全路径耗尽才 BLOCKED；子代理不得判 lane 生死
- [ ] **bookkeeper 边界**：主 thread 唯一 state.json writer；slow path 只返回结构化修复输入，不直接写 state
- [ ] **admission backstop**（impl-planning）：缺合同（behavior/data identity/permission/concurrency/recovery/public shape 或幂等/CAS/跨存储/声明值 vs 检测值）→ 停止 planning 路由 req-align
- [ ] **worker mode 语义**：investigate 禁 READY|BLOCKED、固定 6 行；fix 只消费已确认 finding、fresh invocation、不重新裁决；reviewer 只读、checkpoint≠closure
- [ ] **grill 停止证明**：全分支收敛 / 剩余需真用户 / 重复问题；单个收敛问题不结束 review；Apply 需用户明确批准

## 结构要求

- [ ] frontmatter name/description 保留（合并文件的 name 说明映射）
- [ ] 每个删段在对照表有承接（工具/命令/协议 slug/CLI 校验/orchestrator/preset/按需读），无孤儿
- [ ] 指针宿主无关（不出现 DSH/pre-step/typed 工具等专属词；写"语义 CLI/处境注入"）
- [ ] 不新增方法论（只删机械、压缩判断）
- [ ] 行数 ≤ 目标（对照 baseline-skill-sizes.md）
- [ ] 语言与原文一致

## 跨文件一致性

- [ ] do-review 压缩版引用的 reviewer skill 名与 4 个 leaf frontmatter name 一致
- [ ] dev-with-track 压缩版的处境指针与 Python 侧协议表 slug 一致（协议表在 `scripts/impl_package_runtime/protocols.json`，render 输出 `selected.protocol`，DSH 不本地加载）
- [ ] 合并组内无重复段落（D 组三节、G 组三节各自独立）
- [ ] 原 SKILL 引用的 references 路径在压缩版中仍有效（按需读的保留路径）

## 教训补录（跨宿主与适配层）

- [ ] **跨宿主断指针检查**：被删段若只被 DSH 机制承接，而它的引用路径（SUB-SKILL 显式路径、writer/ownership 边界、legacy 边界、fail-closed canonical wording）对无原生路由的宿主是断链——压缩版必须保留显式路径或回补。
- [ ] **判断规则不误下沉**：fail-closed 聚合规则这类"规则本身是判断、执行是机械"的半判断项，规则文本必须留在 SKILL（DSH orchestrator 只作执行设施，两者分支逐条对应）。
- [ ] **trail schema 是适配层与 Python engine 的共享契约**：impl-tools 的 dispatch/worker-return 构造器必须与 engine `_validate_trail_event` 逐字段核对（dispatch：dispatch_id/candidate_id/mode 四值/chosen/receipt；worker-return：of/return_id + 可选 code_delta+consumption_id 配对）；smoke test 对 mode enum 做 Python 源 parity 断言——Python 侧改 schema 时同步改构造器与测试。
- [ ] **命令表以 impl-package/SKILL.md 的 native entry 列为准**：路由合并（execution-boundaries/dispatcher）后旧入口不保留；移除前确认目标 skill 在 DSH catalog 仍可达（用户根 `~/.agents/skills` 或 customSkillDir），已删 SKILL.md 的 stage 不得作为 steer 目标。
- [ ] **预设形状以现行 builtin `standard` 为 diff 基线**：上游 breaking 不全写进 release 标题（persona prefix/suffix 拆分、preset 默认工具行变化），重适配时先取 upstream `packages/preset/agent-presets/presets/standard/agent.cordis.yml` 逐行对照。
- [ ] **机器路径不得进 preset 源文件**：统一 `{{WORKBENCH_ROOT}}` 标记 + lib 同步代换（`AGENT_WORKBENCH_ROOT` 覆盖；解析失败时 hook/tools 优雅回落祖先树解析）；新增机器专属配置（如 CLI 可执行路径）优先 env 插值，并登记进 README 首次真机验证清单。
- [ ] **宿主包名不可提前采用**：未发布到目标线的包名（如 `dsh-workflow-ptc`）一旦写进 preset 会让整个 preset broken；以 npm dist-tags 的 `latest` 为准，alpha 线差异单独列表。
- [ ] **boot 期 import 才是组合的真关卡**：`--dump-config` 只组树、不 import 模块，缺包/坏行会假阴性（exit 0）；profile roster 行是硬依赖——0.1.5-rc.1 实测缺 `@deepseek-ai/dsh-subagent-codex` 时整个 profile 无法启动。验收用一次性 headless 任务（`dsh --profile <p> "Reply with exactly: BOOT-OK"`）做无头预检，不要只看 dump-config。
