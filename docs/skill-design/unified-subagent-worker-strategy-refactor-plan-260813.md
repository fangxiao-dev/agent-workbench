# 统一编排与多态 Worker 引用重构方案

## 1. 文档状态

- 日期：2026-08-13。
- 状态：已收敛，blind review 意见已处置，待实施。
- 目标仓库：`agent-workbench`。
- 变更类型：Impl-Package 调查、调度、派发与 worker 抽象重构。
- 实施边界：只修改 agent-workbench 的 Skill、worker adapter、调用方、测试、plugin manifest 与相关文档，不修改业务项目代码，不修改用户级 `~/.codex`、`~/.claude` 或 `~/.grok` 状态。
- 本文是本次重构的 canonical 方案；实施时不再新增旧 `route` 链路或并行兼容方法论，历史记录按既有生命周期自然退休。

## 2. 结论摘要

当前 `investigate-before-implement → subagent-driven-development → dispatch-bounded-task` 把一次执行判断拆成多个 activation boundary。上游调度合同只输出 `route`，具体 worker 直到下游 Skill 才出现；调查 Skill 又刻意不拥有 worker。这种文件级正交性使 agent 可以在每一层都局部合规，却遗漏真正需要执行的 worker 选择。

本次重构采用以下终态：

1. 保留并重写 `subagent-driven-development`，使其成为调查、实现、修复和验证的唯一编排入口。
2. 退役 active `investigate-before-implement` 与 `dispatch-bounded-task`；两者的有效合同按 mode 或条件 reference 吸收到统一入口。
3. 执行策略只包含 `mode`、`worker`、`schedule` 与 `review`，删除 downstream `route`。
4. `worker` 是统一的逻辑引用，可以解析到 `$skill`、`@agent`、直接 model/profile 或 prompt-backed worker；流程不依赖其底层实现类型。
5. 调查、实现与修复默认使用同一个 worker reference，但每个独立 bounded unit 仍启动 fresh invocation。
6. 复杂度不再切换 Implementer worker；复杂实现通过独立 `reviewer` gate 获得第二视角。
7. `call-grok` 收敛为全局 `$grok-worker`；编排层不指定 Grok model/effort，直接使用 worker Skill 已有设置；现有 `grok_task.py`、heartbeat、timeout 和 JSON envelope 继续作为该 worker 内部 executor adapter。

## 3. 问题与直接证据

### 3.1 决策被拆成二次激活

当前 `subagent-driven-development` 的有效输出是：

```text
Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED> · route=<route>
```

该合同可以在没有具体 worker 的情况下结束。`dispatch-bounded-task` 才拥有 Implementer、Fixer、Verifier 与 Grok/Luna 选择表。agent 必须成功加载第二个 Skill 才能看到 worker；context compaction、handoff 或直接调用原生 subagent 都可能截断这条链。

### 3.2 调查与 worker 完全分离

`investigate-before-implement` 只返回 `EVIDENCE_SUFFICIENT | EVIDENCE_GAP`，其测试明确禁止出现 worker、parallel admission 或 dispatch。结果是“使用调查方法”不等于“把调查交给 worker”，主 session 容易吸收全部调查过程与上下文。

### 3.3 复杂度被错误用于选择 worker

当前跨模块、接口、状态机、shared seam、安全、数据完整性、并发、migration 或外部副作用都会切换 worker。Impl-Package 中的大多数有价值单元天然满足至少一项，因此所谓普通 worker 路径很窄，而且复杂任务的质量保障依赖模型选择而非独立审查。

### 3.4 worker 配置存在多个事实源

当前 dispatch 固定 Grok model/effort，而 `call-grok` 另有自己的 Skill 设置；reviewer、do-review、discuss-ledger 与 thread-harness 分别引用 executor 名称和运行细节。配置更新后容易出现版本、fallback 与调用语义漂移。

### 3.5 测试正在保护旧结构

现有测试明确断言：

- `subagent-driven-development` 必须输出 `route` 且不能输出 `mode`。
- `subagent-driven-development` 不能看到具体 model/worker。
- `investigate-before-implement` 不能引用调度或 worker。
- `dispatch-bounded-task` 独占 worker table、task template 与失败恢复。

因此本次不是文案压缩，而是一次行为合同和回归测试的原子迁移。

## 4. 目标拓扑

```text
dev-with-track / execution-preflight / thread-harness / direct caller
                              │
                              ▼
             subagent-driven-development
             ├─ mode=investigate
             ├─ mode=implement
             ├─ mode=fix
             └─ mode=verify
                              │
                   resolve worker reference
                              │
       ┌──────────────────────┼──────────────────────┐
       ▼                      ▼                      ▼
  $grok-worker           @luna-worker       gpt-5.6-terra/xhigh
  (Skill worker)         (agent worker)      (direct model profile)
       │
       ▼
  Grok executor adapter
                              │
                              ▼
                     WorkerOutcome
                              │
                complex implement/fix only
                              ▼
                    independent reviewer
                              │
                   ReviewedOutcome / finding
                              │
                              ▼
              main session integration and acceptance
```

`subagent-driven-development` 是唯一方法论 owner。worker resolver 只把统一引用变成一次真实执行；reviewer 只做独立审查。任何一层都不重新设计业务 Task、Ticket、授权或 acceptance。

## 5. 统一 Strategy 合同

每个被执行的 bounded unit 必须在启动前形成以下策略：

```yaml
mode: investigate | implement | fix | verify
worker: main-session | "$grok-worker" | "@luna-worker" | "gpt-5.6-terra/xhigh" | "prompt:<slug>"
schedule: local | serial | parallel
review: none | required
resources: <仅在存在共享资源、唯一顺序或 cleanup owner 时出现>
reuse: <仅在同一 source unit 依赖不可转移 live state 时出现>
reason: <local、blocked、显式 override 或非显然 review 判断时出现>
```

合同规则：

1. `route` 不再是合法字段。
2. `worker` 必须显式存在；主 session 本地执行使用 `main-session`，不能通过省略 worker 隐式表示。
3. `schedule=local` 只与 `worker=main-session` 组合，用于原子操作、紧耦合集成或不可隔离共享资源操作，并要求 `reason`。
4. `schedule=serial | parallel` 使用可解析的非本地 worker reference。存在两个以上互相隔离的 bounded units 才允许 `parallel`。
5. caller 显式指定 worker 时优先采信；未指定时主 worker 默认为 `$grok-worker`，其安全 executor fallback 固定为一次 fresh `@luna-worker`。fallback 是执行恢复，不改变 investigate → implement → fix 的逻辑 worker 策略；不得回退到 `main-session`，业务 `BLOCKED` 不触发 fallback。
6. 同一个工作流中的 investigate、implement 与 fix 继承同一 worker reference；继承的是 profile，不是同一进程或私有上下文。
7. 每个独立 source unit 默认 fresh invocation。只有 `reuse` 明确记录同一 source unit、worker identity 与不可转移 live state 时才复用；context compaction 后从 canonical input 启动 fresh invocation。
8. `review=required` 只表示实现结果必须先经过独立 reviewer，不能改变主 worker；执行中发现 material seam 时可把 `review=none` 升级为 `review=required`，已产生的变更进入 `PENDING_REVIEW`。

## 6. Mode 合同

### 6.1 `investigate`

当原因、影响面、既有方案或必要前置事实不足时使用。保留现有调查输出：

```text
Investigation: EVIDENCE_SUFFICIENT | EVIDENCE_GAP
cause:
blast radius:
existing solution:
boundary facts:
unresolved facts:
```

`EVIDENCE_SUFFICIENT` 允许同一工作流进入 `implement`；它不表示授权、实施或验收已经完成。`EVIDENCE_GAP` 返回最小下一项取证动作，不能靠实现试错掩盖未决边界。

调查可以由 `main-session` 或任意 worker reference 执行。非原子、跨模块或高回显调查默认交给已选 worker，避免主 session 吸收大量过程上下文。

### 6.2 `implement`

用于批准来源已经释放、scope/ownership/authority/acceptance 明确的新增实现。worker 返回变更、文件、局部验证与 residual risk；局部 `DONE` 不表示 Ticket accepted。

若调查阶段存在且结论为 `EVIDENCE_SUFFICIENT`，implementation brief 必须继承其 `cause`、`blast radius`、`existing solution` 和 `boundary facts`，不要求 worker重新调查同一问题。

### 6.3 `fix`

只消费已确认且已边界化的 review finding。输入必须包含 finding ID/来源、comparison point、broken invariant、scope、期望修复和验证入口。`fix` 继承当前策略的 worker reference；不得因为 finding 复杂而切换 worker。

fix 的局部 `DONE` 不表示 finding closure。原 reviewer 必须重新检查固定后的 comparison point，或按 reviewer 自身合同启动 fresh closure run。

### 6.4 `verify`

只执行既定检查并返回压缩证据。长时间或高回显的只读测试使用非本地 worker；单条快速、输出有界的原子检查可以使用 `main-session`。会重写 snapshot、generated file 或其他工作区内容的命令不属于只读 verify，应按真实写 ownership 进入 implement/fix 或本地集成。

## 7. Worker 引用与 Resolver

### 7.1 引用范式

`worker` 是 opaque logical reference，前缀只决定 resolver：

| 形式 | 解析方式 | 示例 |
| --- | --- | --- |
| `$<skill>` | 加载对应 worker Skill，并按其调用合同执行 | `$grok-worker` |
| `@<agent>` | 使用宿主原生 agent profile 启动 fresh subagent | `@luna-worker` |
| `<model>/<effort>` | 使用宿主原生默认 agent 加 model/effort override | `gpt-5.6-terra/xhigh` |
| `prompt:<slug>` | 使用当前宿主默认 agent 与 canonical prompt profile | `prompt:bounded-worker` |
| `main-session` | 当前 session 本地执行 | `main-session` |

resolver 找不到唯一实体、宿主不支持对应 invocation、授权不匹配或 prompt profile 缺失时，在启动前返回 `BLOCKED`；不得猜测近似 worker。

### 7.2 Registry 边界

v1 不引入新的必经 worker registry。`$skill`、`@agent` 与直接 model/profile 已由宿主目录和 active catalog 提供解析事实；额外 registry 会复制这些可查询信息。

未来若需要 alias、capability metadata 或跨宿主映射，可以增加 registry，但它只能引用已经定义的 worker，不得成为另一个 activation boundary，也不得复制 worker 的 model、prompt、timeout、heartbeat 或 output 默认。v1 的默认 `$grok-worker` 与一次 `@luna-worker` fallback 直接写在统一入口的主路径中，不另建配置文件。

### 7.3 `$grok-worker`

`$grok-worker` 是逻辑 worker reference，0.2.9 暂由现有 `skills/call-grok/` Skill 实现；本轮不改物理目录、Skill 名称或 adapter 文件名：

- `SKILL.md` 改为 role-neutral worker 合同，接收完整 bounded brief、workdir、authority/tools、mode 与期望输出。
- `scripts/grok_task.py` 继续作为 Grok CLI executor adapter。
- `references/caller-contract.md` 继续拥有后台启动、heartbeat、stall/timeout、PowerShell quoting 和 terminal envelope 细节。
- worker Skill 不拥有调查、实施、修复或 review 方法；这些由 caller 的 `mode` 与 task brief 决定。
- worker Skill 不固定业务 role prompt，只校验 caller 提供了完整 prompt/brief。
- 编排层不传入 model/effort override；`$grok-worker` 直接读取并遵循其 Skill 当前已有设置，其他 Skill 只引用 `$grok-worker`，不复制或重述模型版本。
- native JSON envelope 在 worker 边界映射为统一 `WorkerOutcome`。

编排层和 active caller 使用 `$grok-worker` 逻辑引用；resolver 将其解析到现有 `call-grok` Skill。物理重命名没有足够收益，不属于 0.2.9 范围。

## 8. WorkerOutcome 与失败恢复

所有 resolver 统一返回：

```text
Outcome: DONE | BLOCKED | INCOMPLETE
mode:
worker:
source unit:
changes/evidence:
cleanup:
residue:
residual risk/blocker:
```

规则：

- `DONE` 表示 bounded unit 和其局部证据完成，不表示 review、Ticket acceptance、Gate 或 package closure。
- `BLOCKED` 表示合同、authority、scope、worker resolution 或业务事实未决；原样上交，不触发 fallback。
- `INCOMPLETE` 表示 executor 未完成。只有进程已退出或清理、residue 可归因且原调用可以安全重放时，才允许一次 fresh retry；默认 `$grok-worker` 的 retry/fallback 使用 `@luna-worker`，不回到 `main-session`。
- fallback 只发生一次；第二次 `INCOMPLETE`、cleanup 未知或 residue 不可归因时统一返回 `BLOCKED`。
- worker native status 只由对应 resolver/adapter解释，不渗透统一编排主路径。

## 9. Complexity 与 Reviewer Gate

复杂度只决定 `review`：

- 触及 shared seam、安全、数据完整性、并发、migration 或不可逆外部副作用；
- caller、Plan 或 safety policy 明确要求独立 review。

单纯跨文件、跨模块或接口变化不自动触发 review；只有能指出上述 material risk，或 Plan 明确要求时，implement/fix 才使用 `review=required`。`review=none` 在非显然场景下必须记录理由。其流程为：

```text
worker implement/fix
  -> Outcome DONE
  -> independent reviewer
     -> PASS: 形成 ReviewedOutcome，交 main session 集成和验收
     -> finding: 同一 worker reference 进入 fix，再由 reviewer closure
     -> UNCERTAIN/BLOCKED: 上交 main session，不得声称完成
```

reviewer 使用现有薄 `reviewer` Skill；它接收显式 reviewer worker，默认沿用 `$grok-worker`，以 fresh invocation 固定 comparison point 并返回 verdict。它不复用 implementation 进程或私有上下文，但不另起一套 worker 选择策略。

复杂任务中，worker 的原始 `DONE` 只能进入 `PENDING_REVIEW`，main session 不得直接把它判为实施收口。main session 仍拥有集成、证据采信、Ticket acceptance 和 Gate 判断，但只在 reviewer PASS/closure 后消费规范化的 `ReviewedOutcome`。

普通任务使用 `review=none`，main session 可以直接消费规范化 `WorkerOutcome` 并完成局部复验。

## 10. Skill 与文件迁移

### 10.1 保留并重写

- `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md`
- `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/evals/evals.json`
- `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/rubric.md`
- `plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md`

`subagent-driven-development/SKILL.md` 正文上限为 180 行。正文只保留原则、主流程、Strategy 合同和 mode router；task template、failure recovery、parallel admission、resolver 细节和示例全部按触发条件放入 references。方法论用引导式问题和判定词表达，只有绝对的字段、选择和 fail-closed 条件写成确定性规则。

### 10.2 吸收后退役

退役以下 active Skill；旧记录不新增恢复协议，按既有生命周期自然退休：

- `plugin-marketplace/plugins/impl-package/skills/investigate-before-implement/`
- `plugin-marketplace/plugins/impl-package/skills/dispatch-bounded-task/`

迁移规则：

- investigation contract 进入统一入口的 `investigate` mode。
- bounded task templates 迁入统一入口的条件 reference，并按 `mode` 组织。
- worker failure recovery 迁入统一入口的条件 reference。
- 原三个 Skill 的 rubric 决策合并到统一入口 rubric；明确记录被本方案取代的旧正交性原则。
- Git 历史已经保存旧实现；本轮不新增 compatibility wrapper、legacy route 解析或额外退休 gate。

### 10.3 Worker 引用收敛

- `skills/call-grok/`、`tests/test_call_grok.py` 和现有安装/链接路径本轮保持不动。
- `SKILL.md`、README、调用方和测试只在策略层使用 `$grok-worker` 逻辑引用；resolver/adapter 测试继续覆盖现有 `call-grok` 实现。
- 未来如需物理重命名，另立独立迁移，不与本次编排合同变更绑定。

### 10.4 调用方迁移

以下 active caller 只指向统一入口，不复制策略字段或旧 Skill 名称：

- 根 `AGENTS.md`。
- `impl-package/skills/dev-with-track/SKILL.md`。
- `impl-package/skills/execution-preflight/SKILL.md` 与 authorization reference。
- `impl-package/skills/impl-package/SKILL.md`。
- `skills/handoff-to-new-session/SKILL.md`。
- `skills/handoff/references/task-execution.md`。
- `skills/thread-harness/SKILL.md` 及 role/design references。

handoff、Execution Record 或 Task handoff 可以保存已经解析的 `mode / worker / schedule / review`，但不能复制统一入口的选择方法。旧记录若只有 `route`，随旧生命周期自然退休；本轮不新增恢复、拒绝或猜测协议。

## 11. Plugin 与版本

本次统一 worker 入口并收敛 invocation/output contract，Impl-Package 版本从 `0.2.8` 提升为 `0.2.9`。按 owner 决策，本轮视为小改维护发布，不作为新的破坏性主版本处理。实施时同步更新：

`0.2.9` 是本轮 owner 明确指定的小改维护版本。下游应按本方案的统一入口和 output contract 更新，不再新增旧 route 或旧 Skill 的 active 依赖。

- `plugin-marketplace/plugins/impl-package/.codex-plugin/plugin.json`
- `plugin-marketplace/plugins/impl-package/.claude-plugin/plugin.json`
- `plugin-marketplace/.claude-plugin/marketplace.json`
- `tests/test_impl_package_plugin.py`

`.agents/plugins/marketplace.json` 不复制 plugin version，保持现有 source 关系。两个 host manifest 必须指向同一版本与同一 skill tree。

## 12. 行为测试与 Evals

### 12.1 必须覆盖的策略场景

统一入口 eval 至少覆盖：

1. 原因未知：选择 `mode=investigate`、具体 worker，无 route；证据充分后进入 implement。
2. 原子本地操作：`worker=main-session`、`schedule=local` 且有 reason。
3. 普通 bounded implementation：使用默认 worker、`review=none`。
4. 触及 shared seam 或不可逆数据边界的 implementation：仍使用同一主 worker、`review=required`，不得因复杂度切换主 worker；普通跨模块改动可保持 `review=none` 并记录理由。
5. reviewer finding：使用同一 worker reference 进入 fix，并重新 review closure。
6. `$skill`、`@agent`、direct model/profile 与 prompt-backed reference 能被正确区分。
7. 无法解析的 worker 在启动前 `BLOCKED`。
8. 两个隔离单元允许 parallel；共享 browser/database/generated output 时 serial。
9. context compaction 后从 canonical input fresh invocation，不复用旧 worker 私有上下文。
10. 长时间高回显只读检查使用 verify worker；有写副作用的命令不能伪装为 verify。
11. 默认 `$grok-worker` 的 executor `INCOMPLETE` 只允许一次 fresh `@luna-worker` fallback；业务 `BLOCKED` 不 retry，也不回退到 main session。
12. 复杂 worker `DONE` 未经 reviewer 时只能是 `PENDING_REVIEW`，不能被 main session直接收口。

### 12.2 契约测试迁移

重点改写：

- `tests/test_impl_package_plugin.py`
- `tests/test_subagent_driven_development_contract.py`
- `tests/test_role_skill_contract.py`
- `tests/test_thread_harness_contract.py`
- `tests/test_call_grok.py` 的现有 adapter 测试
- `tests/test_link_skill.py`
- `plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_three_track_contract.py`

删除保护旧结构的断言，新增以下不可回归条件：

- active tree 不再把 `investigate-before-implement` 与 `dispatch-bounded-task` 作为可调用入口；历史文档和旧记录可自然保留。
- 统一入口合同包含 `mode / worker / schedule / review`，不包含 `route`。
- complexity 只影响 review，不影响 worker。
- `$grok-worker` 内部 adapter 默认只有一个权威来源。
- active caller 的策略层使用 `$grok-worker`；旧 Skill 名和 route 不再进入新的策略合同，历史引用不强制清理。
- `subagent-driven-development/SKILL.md` 不超过 180 行，mode-specific 细节通过条件 reference 渐进披露。
- `AGENTS.md` 与 Impl-Package 入口各保留一行最小不变量：启动非本地 bounded work 前先形成 `mode / worker / schedule / review`。
- reviewer gate 对复杂 implement/fix 为 fail-closed。

### 12.3 验证命令

实施后至少运行：

```powershell
python -m pytest tests/test_impl_package_plugin.py tests/test_subagent_driven_development_contract.py tests/test_role_skill_contract.py tests/test_thread_harness_contract.py -q
python -m pytest tests/test_call_grok.py tests/test_link_skill.py -q
python -m pytest plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_three_track_contract.py -q
```

再运行仓库现有完整相关测试，并用固定字符串检查 active tree：

```powershell
git grep -n -F -e "investigate-before-implement" -e "dispatch-bounded-task" -e "route=dispatch-bounded-task" -e "call-grok"
```

扫描结果用于确认新 active workflow 不再依赖旧入口；历史设计、旧 handoff、现有 `call-grok` adapter 和自然退休记录可以保留，不做全仓字符串清理。

因为本次改变触发、workflow 与 output contract，实施验证采用重型路径：以旧版 Skill 为 baseline，对上述策略场景进行 with-skill/old-skill 对比。量化断言至少验证 worker 显式性、无 route、复杂度不换 worker、review fail-closed 和统一三态 outcome；人工审查重点判断主 session 是否仍会绕过 worker 或 reviewer。

## 13. 实施顺序

1. 先冻结 `$grok-worker` 到现有 `call-grok` Skill 的逻辑解析与 `$grok-worker → @luna-worker` fallback，保证统一入口有稳定 worker 可引用。
2. 重写 `subagent-driven-development` 的 Strategy、mode、resolver、outcome 与 reviewer gate。
3. 迁移 investigation、task template 和 failure recovery 内容，随后删除两个旧 active Skill。
 4. 原子更新所有调用方、AGENTS 最小不变量、thread-harness 和 reviewer/discussion 对 `$grok-worker` 的策略引用；旧 handoff 不新增恢复协议。
5. 更新 eval、契约测试、link/install 文档与 plugin manifests，提升版本到 `0.2.9`。
6. 运行 focused tests、完整相关测试、active-reference scan 与重型行为对比。
7. 只有所有 acceptance criteria 同 revision 成立后，才能宣称重构 implementation 阶段完成。

## 14. Acceptance Criteria

重构只有在以下条件全部成立时才可关闭：

1. 任一非本地 bounded work 在启动前都有显式 `mode / worker / schedule / review`。
2. active workflow 中不存在 downstream `route` 或二次 dispatch activation。
3. investigation 可以使用 worker，并能把证据合同直接传给 implementation。
4. investigate、implement 与 fix 使用同一 worker reference；复杂度不改变 worker。
5. 复杂 implement/fix 的 worker `DONE` 必须先经过独立 reviewer，main session 只对 `ReviewedOutcome` 做最终集成与验收。
6. `$grok-worker` 是全局 Skill worker；Grok 的 model 选择直接遵循该 Skill 已有设置，heartbeat、timeout 与 terminal envelope 也只由该 worker/adapter 合同拥有。
7. `$skill`、`@agent`、direct model/profile、prompt-backed worker 与 `main-session` 都通过同一 Strategy/Outcome 范式表达。
8. 默认 `$grok-worker` executor incomplete 只允许一次 fresh `@luna-worker` fallback，业务 blocker 不 retry，也不回退到 main session。
9. 旧两个 Skill 不再出现在 active plugin tree；所有 active caller 已迁移。
10. Codex 与 Claude plugin manifest 同步为 `0.2.9`，相关测试与行为 eval 通过，未修改用户级 host state。

## 15. 非目标

- 不重新设计 Task、Ticket、DAG、Execution Record、acceptance 或 Gate ownership。
- 不把 reviewer 扩展成新的多轨 review framework；继续复用现有薄 reviewer。
- 不让复杂度选择另一个 Implementer/Fixer worker。
- 不引入必经 worker registry、capability negotiation 或动态 worker marketplace。
- 不把 worker-specific model、prompt、heartbeat、timeout 或 retry 细节复制回流程 Skill。
- 不新增旧 `route` 兼容层或恢复协议；legacy 按既有生命周期自然退休。
- 不自动安装、修改或验证用户级 agent TOML。
- 不在本轮优化 Grok、Luna、Terra 或 reviewer 的模型质量。

## 16. Owner Review Gate

本文已落实 owner 明确确认的方向：版本固定为 `0.2.9`、Grok 不接受编排层 model/effort override、调查/实现/修复复用同一逻辑 worker、默认失败时 fresh fallback 到 `@luna-worker`、正文上限 180 行、删除 downstream `route`、本轮不改 `call-grok` 物理目录。Blind review 的其余意见已按下一节收敛；目标 Skill、plugin manifest 和调用方已进入 implementation。

## 17. Blind Review Record

本轮使用 `discuss-ledger` 的 Blind Opening 模式，参与者为 Claude 与 Grok，使用 `medium` Claude effort；两方只读取同一份方案，不接收对方中间结论。原始 Markdown 结果：

`C:\Users\Xiao\AppData\Local\Temp\discuss-ledger\blind-unified-subagent-worker-strategy-260813-d23606a6.md`

### 已由 owner 定案的意见

- 版本保持 `0.2.9`，并在方案中说明这是 owner 指定的小改维护版本。
- `$grok-worker` 不接受编排层传入 model/effort；直接使用 worker Skill 已有设置。
- 调查、实现和修复复用同一逻辑 worker；复杂度只决定是否追加 reviewer gate。
- `route` 不再进入策略合同。

### 本轮收敛处置

1. 默认 `$grok-worker` 的安全 fallback 固定为一次 fresh `@luna-worker`；不回退到 main session，业务 `BLOCKED` 不 fallback。
2. worker 可以在执行中报告 material seam escalation；编排层把结果置为 `PENDING_REVIEW`，不引入新的 outcome 状态。
3. complexity 门槛收窄到 material seam、安全、数据完整性、并发、migration、不可逆副作用或显式 Plan/safety 要求；普通跨模块变化可 `review=none`，但非显然时要记录理由。
4. 统一入口正文上限 180 行，方法论优先，分支细节渐进披露到 references。
5. `AGENTS.md` 与 Impl-Package 入口增加一行最小策略不变量，不复制完整方法论。
6. legacy route 和旧 handoff 不新增恢复或拒绝协议，按既有生命周期自然退休。
7. `$grok-worker` 继续逻辑解析到现有 `call-grok` Skill；本轮不改物理目录、测试文件名或安装链接。

Blind Opening 到此结束；本轮没有把上述分歧自动合并成新的设计，也没有开始 implementation。
