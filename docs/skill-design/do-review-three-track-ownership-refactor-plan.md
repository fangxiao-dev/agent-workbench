# `do-review` 三轨 Ownership 重构方案

## 1. 文档状态

- 状态：已对齐，待实施。
- 目标仓库：`agent-workbench`。
- 变更类型：review skill Ownership 与调度拓扑重构。
- 实施边界：只修改 agent-workbench 的 skill、reviewer 配置、脚本、测试和相关文档，不修改任何业务项目代码。
- 本文是本次重构的 canonical 方案；实施时不得另建并行方案或保留旧双轴拓扑作为兼容路径。

## 2. 背景与问题

当前 `do-review` 对外声明为双轨编排器，默认外层轨道是 `code-review` 与 `module-review`，但 `module-review` 内部又要求 Standards reviewer 与 Spec reviewer 两个 subagent。名义拓扑是两条 reviewer-skill track，实际执行拓扑却是三个 leaf reviewer。为了执行这个模型，`do-review` 必须知道 `module-review` 的内部双轴结构、提前展开其两个 reviewer、计算嵌套容量，并在 ledger 中使用 `module-review/Standards` 与 `module-review/Spec` 这样的嵌套来源标签。

这个结构的核心问题不是 Standards、Spec 或 Code 三个审查轴本身的质量，而是 Ownership 错位：`module-review` 名义上是 reviewer，实际上同时承担局部 orchestrator；`do-review` 名义上是唯一 orchestrator，却必须依赖并复制另一个 skill 的内部拓扑知识。由此产生双重调度语义、容量计算复杂化、source label 嵌套、custom reviewer 分支复杂化，以及默认轨道数量与真实 reviewer 数量不一致。

本次重构只修复 Ownership。三个审查轴当前各自采用什么审查方法、检查哪些细节、如何表达具体 finding，不在本轮重新设计。特别是，现有 `module-review` 的 Standards 与 Spec 两轴应尽量原样迁移；现有 `code-review` 即使与 Standards 存在部分职责重叠，本轮也不收敛。

## 3. 目标

### 3.1 目标拓扑

```text
do-review（唯一 orchestrator）
├─ Track A: code-review
├─ Track B: standards-review
└─ Track C: spec-review
```

默认一次 review 运行三条并列轨道：

- Track A：`code-review`。
- Track B：`standards-review`。
- Track C：`spec-review`。

三条轨道审查同一份完整 diff，使用同一个已经固定的 comparison point、base SHA 与 head SHA。三条轨道在同一轮内独立工作，不接收其他轨道的中途结论。最终报告并列呈现三轨结果，任一轨通过不得掩盖另一轨失败。

### 3.2 Ownership 目标

`do-review` 是唯一 orchestrator，独占以下职责：

- 确定 review target、mode、round/cap 与完整 change unit。
- 解析并固定 comparison point、base SHA、head SHA、完整 diff 与 commit 列表。
- 收集并准备三轨共享的仓库、需求、Decision、Spec、Plan、DAG 和约束上下文。
- 解析默认或用户显式指定的 reviewer selection。
- 通过 canonical registry 完成 reviewer path preflight。
- 根据 resolved leaf reviewer 数量进行容量规划与 phased dispatch。
- 生成 leaf prompt，并保证同轮 reviewer 结论隔离。
- 维护跨轮、跨轨的 canonical finding ledger。
- 按 broken invariant 或 observable failure 去重，而不是按文件路径去重。
- 复核 P1、P2 与 blocker finding 的证据和范围。
- 决定 classification、closure verdict、overall verdict 与 loop 是否收敛。
- 生成最终并列报告。

每个 dispatched reviewer 都是 leaf reviewer，只承担被分配 skill 的审查职责。leaf reviewer 不得调用 `do-review`，不得调度 subagent，不得重新推导 reviewer topology，不得重新计算容量，不得决定跨轨最终分类。

## 4. 非目标

本次重构明确不包含以下工作：

- 不修改 `code-review` 的内部审查设计、checklist、职责范围或输出方法。
- 不消除 `code-review` 与 Standards 之间当前可能存在的职责重叠。
- 不重新设计 Fowler code-smell baseline。
- 不重新设计 module interface、depth、leverage、locality、seam 或 adapter 的判断方法。
- 不重新设计 issue、Decision、Spec、Plan 或 DAG 的 contract fidelity 判断方法。
- 不修改 `safety-review` 的内部职责、触发信号、严重性或 fail-closed 规则。
- 不引入 leaf reviewer metadata、capability negotiation、运行时 topology protocol 或额外认证机制。
- 不把 reviewer registry 扩展成通用 plugin framework。
- 不修改业务项目代码。
- 不在本轮执行后续的 reviewer 内容质量优化。

## 5. Reviewer 职责边界

### 5.1 Track A：`code-review`

本轮保留现有 `skills/reviews/code-review/SKILL.md`，不修改其内部设计。`do-review` 将它作为一条独立 leaf track 调度，并通过统一 leaf prompt 禁止其发起二次编排。

本次 Ownership 方案使用以下高层职责描述作为调度说明，但不据此重写现有 skill：可达代码路径、局部业务不变量、错误处理、回归测试与本地/mock 行为风险。

### 5.2 Track B：`standards-review`

新建 `skills/reviews/standards-review/`。其内容从当前 `skills/reviews/module-review/` 的 Standards 轴复制并提炼，内部审查方法尽量保持不变。

`standards-review` 保留：

- 仓库规范来源发现与优先级，包括 `AGENTS.md`、`CODING_STANDARDS.md`、`CONTRIBUTING.md` 及同类约定。
- 仓库明确规范优先于通用 baseline 的规则。
- Fowler code-smell baseline 及其当前 smell 清单。
- hard violation 与 judgement call 的区分。
- 不重复报告工具已经可靠执行的规则。
- `/codebase-design` 的 deep module vocabulary，包括 interface、depth、leverage、locality、seam 与 adapter。
- interface 不仅包含类型签名，还包含调用者必须知道的 invariant、错误模式和顺序约束。
- 逐 file/hunk 引用证据的要求。
- 现有 Standards 轴的输出约束和 finding 表达方式。

`standards-review` 删除或不继承以下 orchestrator 职责：

- 选择、询问或重新解析 comparison point。
- 自行决定完整 change unit。
- 定位或调度 Spec 来源。
- 调度 Standards 或 Spec subagent。
- 计算 reviewer 容量。
- 汇总另一条轨道的结果。
- 决定跨轨分类或 overall verdict。

`standards-review` 接收 `do-review` 已准备好的 immutable base/head、完整 diff、commit 列表、仓库规范来源和 known ledger，只执行 Standards 审查。

### 5.3 Track C：`spec-review`

新建 `skills/reviews/spec-review/`。其内容从当前 `skills/reviews/module-review/` 的 Spec 轴复制并提炼，内部审查方法尽量保持不变。

`spec-review` 保留：

- 对 issue、Decision、Spec、Plan 与 DAG 的合同忠实度审查。
- 缺失或部分实现需求的识别。
- scope creep 的识别。
- 看似实现但实际行为错误的识别。
- interface、seam 与 module boundary 是否忠实遵守声明合同的检查。
- 兼容窗口、状态机、跨 slice seam 与跨模块 seam 的检查。
- 每项 finding 引用需求来源或稳定证据的要求。
- 现有 Spec 轴的输出约束和 finding 表达方式。

`spec-review` 删除或不继承以下 orchestrator 职责：

- 选择、询问或重新解析 comparison point。
- 自行决定完整 change unit。
- 调度 Standards reviewer。
- 调度任何 subagent。
- 计算 reviewer 容量。
- 汇总 Standards 或 Code 结果。
- 决定跨轨分类或 overall verdict。

`spec-review` 接收 `do-review` 已准备好的 immutable base/head、完整 diff、commit 列表、issue/Decision/Spec/Plan/DAG 来源和 known ledger，只执行 Spec 审查。

当可用 Spec 证据不足时，默认 topology 仍必须 dispatch `spec-review`，leaf reviewer 返回 `UNCERTAIN` 或明确的 evidence gap。证据缺失本身不能成为 `do-review` 自动跳过 Track C 的理由。只有用户显式指定了不含 `spec-review` 的 reviewer 名单，或者用户明确批准 named degraded topology 时，Track C 才可以省略。leaf reviewer 不得自行改变 topology。

## 6. `module-review` 的终态

`module-review` 在两个新 leaf skill 建立并通过迁移验证后从 active tree 移出，完整内容移动到 `skills-deprecated/module-review/` 作为只读历史兼容归档。归档必须标记 `deprecated: true`、禁止模型自动调用，且不进入 active registry、preflight、harness 或默认 topology；不得把它恢复为可执行的旧双轴调度入口。

需要删除的活跃实体包括：

- `skills/reviews/module-review/SKILL.md` 移到 `skills-deprecated/module-review/SKILL.md`。
- `skills/reviews/module-review/rubric.md` 移到 deprecated 归档。
- `skills/reviews/module-review/evals/evals.json` 与 `review_contract_tests.py` 一并保留在 deprecated 归档。

历史 provenance 通过更新后的 `registry/third-party-skills.md` 表达：`standards-review` 与 `spec-review` 均源自原本基于 `mattpocock/skills` engineering code-review 的本地迁移内容；deprecated 归档只作为退役记录，不是可安装、调用或解析的 active `module-review` 条目。

完成迁移后，所有活跃 skill、脚本、测试、fixture 与文档都不得把 `module-review` 当作当前 reviewer。唯一允许的现存副本是 `skills-deprecated/module-review/` 退役归档，不能被 active path、registry 或运行时调用。

## 7. Canonical reviewer registry

`skills/do-review/references/reviewer-registry.json` 成为默认 review topology 与 canonical reviewer path 的单一配置来源。建议结构如下：

```json
{
  "default_tracks": [
    {
      "label": "Track A",
      "skill": "code-review"
    },
    {
      "label": "Track B",
      "skill": "standards-review"
    },
    {
      "label": "Track C",
      "skill": "spec-review"
    }
  ],
  "reviewers": {
    "code-review": {
      "canonical_skill_path": "skills/reviews/code-review/SKILL.md"
    },
    "standards-review": {
      "canonical_skill_path": "skills/reviews/standards-review/SKILL.md"
    },
    "spec-review": {
      "canonical_skill_path": "skills/reviews/spec-review/SKILL.md"
    },
    "safety-review": {
      "canonical_skill_path": "skills/reviews/safety-review/SKILL.md"
    }
  }
}
```

配置规则：

- `default_tracks` 的顺序决定默认 Track A、B、C。
- `reviewers` 只描述 canonical skill path，不描述 leaf capability 或内部 topology。
- `module-review` 不出现在新 registry 中。
- `safety-review` 保持已注册但非默认轨道，本轮不改变其现有业务语义。
- Python 脚本不得再维护独立的默认 reviewer 名单。
- Markdown 中可以展示默认拓扑，但可执行默认值必须来自 registry。

## 8. Reviewer selection

Reviewer selection 使用最小规则集：

- 用户未指定 reviewer 时，读取 registry 的 `default_tracks`，运行 `code-review`、`standards-review` 与 `spec-review`。
- 用户明确指定 reviewer 名单时，严格按用户给出的名字与顺序解析，不重复 reviewer，不自动补齐默认 reviewer，不推测用户意图。
- 显式 reviewer 必须通过 registry 或 active skill catalog 解析到唯一 canonical `SKILL.md`。
- 无法唯一解析、文件缺失、文件不可读或 frontmatter name 不匹配时，dispatch 前 fail fast。
- Track label 按 resolved reviewer 顺序分配；默认运行固定使用 A、B、C。

本轮不为未发生的模糊 selection 设计额外策略，也不建立可变 topology 协议。

## 9. Scope 与 shared context

`do-review` 在 dispatch 前只解析一次 scope，并将同一份 immutable context 发送给每个 reviewer。共享上下文至少包含：

```text
Review target:
Repo/worktree:
Mode:
Round:
Comparison point input:
Resolved base SHA:
Resolved head SHA:
Diff command/range:
Included commits:
Scope source/package roots:
Known constraints:
Out of scope:
Repository standards sources:
Issue/Decision/Spec/Plan/DAG sources:
Known findings ledger from prior rounds:
User classification policy:
Assigned track label:
Assigned reviewer skill:
Assigned canonical SKILL.md path:
```

完整 requested change unit 规则保持由 `do-review` 所有：用户指定 base、PR base、branch、tag 或 issue set 时使用用户输入；plan/implementation package review 覆盖整个 package 关联 commit range；普通 branch/PR 使用 integration branch 或 PR base 的 merge base；无法可靠确定时在 dispatch 前询问，不以 `HEAD^` 静默降级。

三轨必须收到相同的 resolved base SHA、head SHA、diff range 与 included commits。每轨可以根据自己的 skill 忽略不相关上下文字段，但不得重新选择范围。

## 10. Leaf dispatch prompt contract

`do-review` 给每个 dispatched reviewer 的 prompt 必须包含统一 leaf contract。具体文本可以适配宿主格式，但语义不得缺失：

```text
You are <Track label> using reviewer skill <skill-name>.

You are a leaf reviewer in a topology already resolved by the parent do-review run.
Do not invoke do-review.
Do not dispatch subagents.
Do not re-evaluate reviewer topology or capacity.
Perform only the review role defined by the assigned reviewer skill.

Read and use exactly this canonical reviewer skill:
<absolute SKILL.md path>

Review exactly the supplied complete diff and fixed comparison point.
Do not inspect, request, or use findings produced by other tracks in the current round.
If this round is executed in phases, treat other same-round track results as unavailable.

Return findings in the supplied ledger schema.
Do not make the final cross-track classification or overall verdict.
```

本轮只通过 prompt 明确 leaf 行为，不增加 registry metadata、静态 capability 声明或运行时 enforcement。相关测试验证 prompt template 包含上述约束即可。

## 11. 容量规划与 phased dispatch

容量规划按 resolved leaf reviewer 数量计算。默认 topology 有三个 leaf reviewer，不再存在“两个 outer tracks 加 module-review 两个内部 reviewer”的嵌套计算。

默认优先并行调度三轨。如果当前 runtime 无法同时容纳全部 leaf reviewer，但允许安全分阶段运行，`do-review` 可以 phased dispatch；分阶段只改变开始时间，不改变输入、职责和独立性。

Phased dispatch 必须满足：

- 所有 reviewer 使用调度前固定的同一 base/head SHA 和完整 diff。
- 后启动 reviewer 不接收本轮先完成 reviewer 的 finding、摘要或 verdict。
- 主会话在本轮所有 resolved reviewer 完成前不执行跨轨 dedupe 或分类并回传给仍未执行的 reviewer。
- 所有 required reviewer 均完成后，该轮才算 completed。
- 任何 reviewer 被省略都必须是用户明确授权的 degraded topology，不能因容量不足静默省略。

如果 subagent 完全不可用、被禁止或需要额外授权，`do-review` 在实际审查前停止并请求用户选择停止或明确授权 degraded single-session review。

## 12. 同轮隔离与跨轮 ledger

同轮隔离与跨轮共享必须明确区分。

同一轮内：

- Track A、B、C 独立审查。
- reviewer 不共享中途结论。
- phased dispatch 也不改变隔离规则。
- 主会话不把先完成轨道的输出注入后启动轨道。

从第二轮开始：

- 每个 reviewer 接收上一轮结束后由主会话生成的 canonical ledger。
- canonical ledger 已完成跨轨去重、source attribution 和必要的证据复核。
- reviewer 使用 ledger 避免重复，只在出现不同 broken invariant、不同 observable failure、不同 owner/release impact、severity 改变或 materially new evidence 时新增或 refine finding。
- reviewer 不接收其他轨道未经主会话处理的原始输出。

这保证同轮判断独立，同时保留 N-round 与 loop 模式的跨轮收敛能力。

## 13. Ledger 与 source labels

默认三轨 source label 固定为：

```text
Track A (code-review)
Track B (standards-review)
Track C (spec-review)
```

通用 finding record 保持以下字段：

```text
ID:
Title:
Severity: P0/P1/P2/P3
Classification: blocker / follow-up / backlog / no issue
Source: Track <label> (<skill>) / fused / main-session
Contributing sources:
Status: new / duplicate / refined / disputed / accepted / downgraded / fixed-verified
Evidence:
Issue class:
Impact:
Recommended action:
Related issue/PR:
Main-session decision:
```

去重按 broken invariant 或 observable failure 进行，不按 file path 或 reviewer 名称进行。多个轨道报告同一问题时使用 `Source: fused`，同时在 `Contributing sources` 中保留所有贡献轨道，不能因融合丢失 provenance。

`main-session` 不作为第四 reviewer。只有在证据复核、去重、分类或范围判断产生主会话决策时才使用 `main-session` 来源。

## 14. 高严重性证据复核与分类

主会话在最终报告任何 P1、P2 或 blocker finding 前必须：

1. 读取 target revision 上的 cited evidence。
2. 确认引用存在且支持 claim。
3. 确认 finding 属于固定 scope。
4. 使用用户 policy 或默认 policy 判断 classification。
5. 对证据不足项标记 `disputed`、`downgraded` 或 `UNCERTAIN`，不得把未验证 claim 当成已确认 blocker。

P0 如果映射为 blocker，同样适用 blocker evidence verification；本轮不另行修改现有 severity taxonomy。

默认 classification 保持：

- `blocker`：可能破坏未来业务数据、资金、库存、订单/客户状态、安全边界或 runtime-visible product data。
- `follow-up`：存在真实风险，但在已声明 release constraint 下不阻塞。
- `backlog`：历史清理、自动化便利、可选 hardening 或无即时业务风险的环境治理。
- `no issue`：重复、已修复、超出范围或证据不支持。

## 15. Mode 与 loop 收敛

现有三种 mode 保持：

- N rounds：严格执行 N 轮，默认一轮。
- Loop：直到收敛或达到 cap，默认 cap 10。
- Closure verification：只验证指定 issue/finding 是否关闭，不扩大为新问题搜索。

每轮必须收到所有 resolved reviewer 的结果，才允许主会话更新 canonical ledger。默认三轨运行时，一轮缺少任一 Track A、B、C 结果都不算该轮完成，除非用户明确批准 named degraded topology。

Loop 收敛定义保持以 finding class 为中心：最新一轮没有新增 distinct blocker/follow-up issue class，或者只剩 duplicate/refinement 时收敛。不能因为某一轨 PASS 或无新 finding，就提前跳过其他轨道或宣称整体收敛。

## 16. 最终输出

正常 review report 至少包含：

- Target、base/head、mode、rounds、stop reason 与 overall verdict。
- Blockers、follow-ups、backlog/not blocking findings。
- 每条 finding 的 source、evidence 与主会话 decision。
- Source Coverage 中的 Track A、B、C、fused 与 main-session。
- 每轨独立 verdict。
- 推荐下一步。

默认三轨 verdict 并列展示：

```text
Track A (code-review): PASS / FAIL / UNCERTAIN
Track B (standards-review): PASS / FAIL / UNCERTAIN
Track C (spec-review): PASS / FAIL / UNCERTAIN
Overall: PASS / FAIL / UNCERTAIN
```

Overall 使用 fail-closed 聚合：

- 任一 required track 为 FAIL，则 Overall 为 FAIL。
- 没有 FAIL，但至少一个 required track 为 UNCERTAIN，则 Overall 为 UNCERTAIN。
- 所有 required track 均为 PASS，Overall 才为 PASS。

任一轨 PASS 不得覆盖、抵消或降级另一轨 FAIL。finding 数量不能作为轨道投票权重。

Closure verification report 保留逐 issue 的 PASS/FAIL/UNCERTAIN，但仍需记录各 resolved track 的覆盖结果，避免一个 reviewer 的 PASS 代表整个 topology。

## 17. 文件级实施清单

### 17.1 新建

- `skills/reviews/standards-review/SKILL.md`：迁移 Standards 轴方法，改为 leaf contract。
- `skills/reviews/standards-review/rubric.md`：记录 Ownership、comparison point 由调用者提供及 Standards-only 决策。
- `skills/reviews/standards-review/evals/evals.json`：从原 module Standards 场景迁移。
- `skills/reviews/standards-review/evals/review_contract_tests.py`：验证 Standards-only、leaf、无 subagent dispatch。
- `skills/reviews/spec-review/SKILL.md`：迁移 Spec 轴方法，改为 leaf contract。
- `skills/reviews/spec-review/rubric.md`：记录 Ownership、comparison point 由调用者提供及 Spec-only 决策。
- `skills/reviews/spec-review/evals/evals.json`：从原 module Spec 场景迁移。
- `skills/reviews/spec-review/evals/review_contract_tests.py`：验证 Spec-only、leaf、无 subagent dispatch。
- `skills/do-review/scripts/test_verify_reviewer_skills.py` 或仓库现有测试约定下的等价测试：验证 registry-driven preflight。
- `skills/do-review/evals/` 下的 topology contract 测试，若当前仓库约定允许 do-review 自带 eval；否则放入现有顶层 tests。

### 17.2 修改

- `skills/do-review/SKILL.md`：双轨改为默认三轨，删除 module 内部 topology knowledge，吸收共享总纲，更新 selection、capacity、dispatch、ledger、loop 与输出规则。
- `skills/do-review/references/reviewer-registry.json`：增加 `default_tracks` 与 `reviewers`，注册两个新 leaf，移除 module。
- `skills/do-review/scripts/verify-reviewer-skills.py`：从 registry 读取默认 reviewer，支持新 schema，删除默认 reviewer 名称硬编码。
- `skills/do-review/references/subagent-briefs.md`：删除 module addendum，加入通用 leaf、同轮隔离、phased isolation 与新轨道说明。
- `skills/do-review/references/output-templates.md`：增加 Track C、三轨 coverage、三轨 verdict 与新 source label。
- `skills/do-review/rubric.md`：用三轨 Ownership 决策替换旧双轨/module 双轴决策。
- `scripts/codex_harness_prepare.py`：从 canonical reviewer config 解析活跃默认 review skill paths，不再硬编码 module。
- `examples/datev-accounting-rules.pre-3.2-upgrade-fixture.toml`：替换 active skill 列表。
- `registry/third-party-skills.md`：删除 active module 条目，登记 standards/spec 的共同上游 provenance。
- `skills/impl-package/SKILL.md`：更新 reviewer 路由名称与 Ownership 描述。
- `skills/impl-package/dev-with-track/SKILL.md`：更新 review 调用与闭环描述，不改变三个 reviewer 的内部方法。
- `skills/impl-package/references/impl-package-system-design.md`：删除 module 双轴现状描述，改为 do-review 三个 leaf reviewer。
- `skills/impl-package/verification-before-completion/SKILL.md`：更新 review evidence owner 名称。
- `skills/impl-package/assets/impl-package-intro.html`：将可视化说明中的 active module-review 条件路由替换为 standards-review 与 spec-review 的成对路由，保持原触发信号不变。
- `tests/test_impl_package_step8_evals.py`：用 standards/spec eval 替换 module eval，更新断言。
- 所有仍把 `module-review` 当作 active reviewer 或把默认 topology 描述为 dual-track 的相关文档与测试。

Impl-Package 文档与脚本只更新 reviewer 名称和 Ownership：

- 原 `module-review` 条件路由必须在原位置一对二映射为 `standards-review` 与 `spec-review`，两个 leaf 使用同一个既有触发信号；不得只替换其中一个，也不得借迁移把原条件路由改成无条件常开。
- `do-review` 在调用者没有显式 reviewer selection 时仍使用 registry 的默认三轨；Impl-Package 已有的显式条件路由属于调用者 selection，继续保留原触发语义。
- 不趁本次迁移重写各轴触发逻辑或审查标准。
- `safety-review` 保持原有条件触发语义。

### 17.3 删除与归档

- 整个 active `skills/reviews/module-review/`，其内容移动到 `skills-deprecated/module-review/` 归档。
- 所有只服务于 module 双 subagent topology 的活跃测试、fixture 字段、prompt addendum 和 source label。
- 活跃文档中的 `module-review` reviewer 路由与兼容说明。

移动后不创建 active alias、shim 或 compatibility route；deprecated 归档是唯一允许的历史副本。

## 18. 配置化脚本要求

`verify-reviewer-skills.py` 的默认行为从 registry 读取 `default_tracks`。显式 `--skills` 仍可覆盖默认 selection，`--skill-path NAME=PATH` 仍用于 active skill catalog 已解析的 custom reviewer。验证内容保持文件存在、可读、路径不逃逸与 frontmatter name 匹配。

`scripts/codex_harness_prepare.py` 不再维护 `reviews/code-review`、`reviews/module-review`、`reviews/safety-review` 这样的独立 review bundle 常量。它应复用 canonical registry 中的 active reviewer path；如果 safety 的加入仍由 Impl-Package 条件决定，则只保留该条件逻辑，不复制默认三轨清单。

本轮配置化只消除 reviewer 名称和 canonical path 的重复硬编码。不得趁机建立通用 manifest engine、动态 dependency resolver 或跨 host plugin registry。

## 19. 迁移顺序

实施必须按以下顺序进行，避免出现 active module 已删除但新 reviewer 尚不可验证的中间状态：

1. 从当前 `module-review` 提取完整 Standards 与 Spec 内容清单，建立迁移对照表。
2. 新建 `standards-review`，复制 Standards 轴内容，只删除 orchestrator 职责并加入 leaf contract。
3. 新建 `spec-review`，复制 Spec 轴内容，只删除 orchestrator 职责并加入 leaf contract。
4. 将原 module eval 场景按轴迁移到两个新 skill，确认没有丢失原 Standards/Spec 行为要求。
5. 更新 reviewer registry schema 与 preflight，使三个新默认 reviewer 可解析。
6. 更新 `do-review` 的 scope、selection、capacity、dispatch、ledger、loop 与输出合同。
7. 更新 subagent briefs 与 output templates。
8. 更新 harness，使默认 reviewer path 来自配置。
9. 更新 Impl-Package、HTML 介绍资产、fixture、third-party registry、rubric 和相关测试；所有原 `module-review` 条件路由原位一对二映射为 `standards-review + spec-review`，保留既有触发信号。
10. 将整个 active `module-review` 目录移动到 `skills-deprecated/module-review/`，并清除所有 active module topology 引用。
11. 执行 repository-wide legacy scan，任何 active `module-review` reviewer 路由、dual-track 默认规则或嵌套 source label 都视为迁移未完成。
12. 运行所有相关测试、自检与 `git diff --check`。

## 20. 测试计划

### 20.1 新 leaf contract 测试

`standards-review` 测试至少覆盖：

- skill frontmatter name 为 `standards-review`。
- 保留仓库规范优先级。
- 保留 Fowler smell baseline。
- 保留 hard violation 与 judgement call 区分。
- 保留 codebase-design 的 interface/depth/leverage/locality/seam/adapter 基线。
- 不包含 Spec review 职责。
- 不派发 subagent。
- 不调用 `do-review`。
- 不重新确定 topology、capacity 或 comparison point。

`spec-review` 测试至少覆盖：

- skill frontmatter name 为 `spec-review`。
- 保留 issue/Decision/Spec/Plan/DAG contract fidelity。
- 保留遗漏需求、partial implementation 与 scope creep。
- 保留兼容窗口、状态机与跨模块 seam。
- 不包含 Standards review 职责。
- 不派发 subagent。
- 不调用 `do-review`。
- 不重新确定 topology、capacity 或 comparison point。

### 20.2 `do-review` topology 测试

- 默认 registry 精确返回 Track A/code-review、Track B/standards-review、Track C/spec-review。
- 默认 topology 不包含 module-review。
- custom reviewer 使用明确给出的名单与顺序，不重复、不补齐。
- 所有 resolved reviewer 在 dispatch 前完成 canonical path preflight。
- leaf prompt 包含禁止调用 do-review、禁止 subagent、禁止 topology/capacity 重算。
- leaf prompt 包含完整 diff、fixed comparison point 与同轮隔离规则。
- phased dispatch 不把同轮先完成输出加入后启动 prompt。
- round 2 以后加入上一轮 canonical ledger。
- 一轮缺少 required track 结果时不得标记 round completed。
- source label 精确使用新的 A/B/C 格式。
- fused finding 保留 contributing sources。
- output template 并列显示三轨 coverage 与 verdict。
- Overall 聚合不能让单轨 PASS 掩盖另一轨 FAIL。

### 20.3 Preflight 测试

- 无 `--skills` 时从 registry `default_tracks` 读取默认值。
- 显式 `--skills` 时只验证显式 reviewer。
- custom `--skill-path` 正常工作。
- missing file fail fast。
- unreadable file fail fast。
- frontmatter name mismatch fail fast。
- canonical path 逃逸 workbench root 时 fail fast。
- registry 中不存在 reviewer 时 fail fast。

### 20.4 Integration/document contract 测试

- harness 准备 review task 时解析新的 active reviewer paths。
- Impl-Package 测试读取 standards/spec eval，不再读取 module eval。
- Impl-Package 中每个原 module-review 条件路由都映射为 standards-review 与 spec-review 两个 leaf，并保留原触发条件。
- `skills/impl-package/assets/impl-package-intro.html` 不再展示 active module-review，且展示 Standards 与 Spec 的成对条件路由。
- third-party registry 对两个新 skill 的 provenance 可验证。
- 文档与 fixture 不再宣称 module-review 是 active reviewer。
- `skills/reviews/module-review/` 不存在。
- `skills-deprecated/module-review/` 存在且明确标记 deprecated，但不在 active registry、preflight 或 harness 中。

## 21. 验证命令

实施者应根据实际新增测试路径运行至少以下验证；命令路径可随最终测试布局调整，但覆盖范围不得缩减：

```powershell
python skills/do-review/scripts/verify-reviewer-skills.py --workbench-root .
python skills/do-review/scripts/test_verify_reviewer_skills.py
python skills/reviews/standards-review/evals/review_contract_tests.py
python skills/reviews/spec-review/evals/review_contract_tests.py
python tests/test_impl_package_step8_evals.py
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1
git diff --check
```

还需要使用仓库规定的 Git-tracked 搜索方式执行 legacy scan：

```powershell
git grep -n -F -e "module-review" -e "dual-track" -e "exactly two outer tracks" -e "module-review/Standards" -e "module-review/Spec"
```

搜索结果必须逐项分类：Git 历史不可搜索，当前 canonical 文档中的迁移背景可以保留必要名称，但任何 active routing、active registry、active test expectation、active skill prompt、fixture 或使用说明中的旧 topology 都必须清零。若为了说明删除对象而在本方案中出现 `module-review`，不构成 active legacy；实现完成后不得另有可执行或可调用 legacy。

## 22. 验收标准

本次 Ownership 重构只有同时满足以下条件才能称为 implementation closed：

1. 默认 review topology 是三个并列 leaf reviewer：code、standards、spec。
2. `do-review` 是唯一 orchestrator，所有 topology、capacity、dispatch、ledger、classification、loop 与 final report 决策都由它负责。
3. 三轨收到相同完整 diff 与 immutable comparison point。
4. 同一轮三轨不共享中途结论，phased dispatch 也保持隔离。
5. 第二轮开始只共享上一轮 canonical ledger。
6. `standards-review` 完整保留原 Standards 轴方法，但不包含 orchestrator 或 Spec 职责。
7. `spec-review` 完整保留原 Spec 轴方法，但不包含 orchestrator 或 Standards 职责。
8. `code-review` 内部设计未在本轮被修改。
9. active `module-review` skill、兼容入口与 legacy 调度全部不存在；仅允许 `skills-deprecated/module-review/` 作为明确标记的退役归档。
10. 默认 topology 与 canonical paths 由 reviewer registry 配置，Python 不维护第二份硬编码默认清单。
11. source label 使用 `Track A (code-review)`、`Track B (standards-review)` 与 `Track C (spec-review)`。
12. 最终报告并列保留三轨 verdict，任一轨 PASS 不得掩盖另一轨 FAIL。
13. reviewer registry、preflight、briefs、templates、harness、Impl-Package、fixtures、tests 与 docs 全部完成适配。
14. 新 leaf contract 测试、do-review topology 测试、preflight 测试和相关 integration tests 全部通过。
15. repository-wide legacy scan 没有发现 active module-review 或旧双轨调度残留。
16. `git diff --check` 通过。

## 23. 原双轴迁移保真对照

本节是实施时的内容保真基线。拆分工作可以调整标题、leaf 输入说明和文件组织，但不得因为从一个 skill 拆成两个 skill 而压缩、合并或删除本节列出的原有审查方法。只有原 `module-review` 的 orchestrator 行为应从 leaf 中移除并由 `do-review` 接管。

### 23.1 Standards 轴必须完整迁移的内容

仓库规范来源必须保留：收集仓库中所有描述代码应如何编写的文件，包括 `AGENTS.md`、`CODING_STANDARDS.md`、`CONTRIBUTING.md` 及同类规则文件。

Fowler baseline 的解释规则必须保留：

- 仓库规范优先；仓库明确认可的写法覆盖通用 baseline，不报告冲突 smell。
- smell 始终是 judgement call，不能自动当成硬性违规。
- 工具已经可靠执行的规则不重复报告。
- baseline 是 Standards 轴内部的启发式，不形成额外 reviewer 或额外 track。

以下 smell 清单及当前建议动作必须完整迁移：

- **Mysterious Name**：名称无法说明职责或内容；建议重命名，若无法诚实命名则指出设计仍含糊。
- **Duplicated Code**：多个 hunk 或文件出现相同逻辑形状；建议抽取共享形状。
- **Feature Envy**：方法访问其他对象的数据多于自身数据；建议把行为移到它依赖的数据一侧。
- **Data Clumps**：相同字段或参数组合反复同行；建议提炼为一个类型。
- **Primitive Obsession**：primitive/string 代替值得命名的领域概念；建议建立小型领域类型。
- **Repeated Switches**：同一类型的 switch 或条件链重复出现；建议用多态或共享映射集中表达。
- **Shotgun Surgery**：一个逻辑变化迫使许多文件分散修改；建议把共同变化收进一个 module。
- **Divergent Change**：一个文件因多个无关原因被修改；建议按变化原因拆分。
- **Speculative Generality**：加入 spec 未要求的抽象、参数或 hook；建议删除并收回到真实需求。
- **Message Chains**：调用者依赖很长的导航链；建议在起点隐藏导航细节。
- **Middle Man**：class/function 主要只向后转发；建议移除中间层并直接调用真正目标。
- **Refused Bequest**：子类或实现者忽略、覆盖大部分继承合同；建议放弃继承并使用组合。

`codebase-design` vocabulary 必须完整迁移：

- 检查 module interface 是否以较小表面承载足够行为，即 depth 与 leverage。
- 检查知识与验证是否保持在合适 seam，以维持 locality。
- 检查新增 adapter 是否有真实可变性依据。
- interface 包含调用者必须了解的 invariant、错误模式和顺序约束，不得缩窄为类型签名。
- 这些内容仍属于 Standards 设计基线，不形成新的 drift reviewer。

Standards 输出合同必须保留：

- 对完整 diff 逐 file/hunk 审查。
- 仓库规范硬性违规引用规则文件。
- baseline smell 点名具体 smell 并引用相关 hunk。
- 区分 hard violation 与 judgement call。
- 仓库规范覆盖 baseline。
- 跳过工具已经可靠执行的规则。
- 保留原有 400 words 输出上限，除非后续独立任务明确修改该 reviewer 的输出设计。

### 23.2 Spec 轴必须完整迁移的内容

Spec 来源语义必须保留：issue、用户提供的路径、与 branch/feature 对应的 PRD/spec，以及 Impl-Package 中的 Decision、Spec、Plan 与 DAG 都可以作为 contract evidence。来源定位与共享上下文准备改由 `do-review` 所有，但 `spec-review` 仍必须使用收到的全部适用来源。

Spec 审查内容必须完整迁移：

- 缺失需求。
- 部分实现需求。
- diff 中未被要求的 scope creep。
- 看似实现但实际行为错误的需求。
- implementation interface 与 seam 是否忠实遵守声明合同。
- module boundary 是否忠实遵守 spec、plan 或 DAG。
- 兼容窗口。
- 状态机。
- 跨 slice seam。
- 跨模块 seam。

Spec 输出合同必须保留：

- 每项 finding 引用 spec 原文或稳定 contract evidence。
- 保留原有 400 words 输出上限，除非后续独立任务明确修改该 reviewer 的输出设计。
- Spec reviewer 独立输出，不与 Standards finding 预先合并。

### 23.3 从原双轴总纲迁入 `do-review` 的内容

以下内容不得留在 leaf reviewer 中重新编排，必须由 `do-review` 统一实现：

- 只确定一次 fixed comparison point。
- 验证 comparison ref 可解析、diff 范围明确且 change unit 完整。
- 记录完整 diff 命令和 commit 列表。
- 准备 Standards 与 Spec 所需来源。
- 调度独立 reviewer。
- 保证 Standards 与 Spec 不共享同轮中途结论。
- 并列保留两轨结果，不跨轴预合并、预排序或选出单一“最严重轴”。
- 汇总每轨 finding 数量与各轨最严重问题。
- 把三轨 finding 送入统一 ledger 后再执行跨轨 dedupe、证据复核与最终分类。

原 module 设计中“Standards pass 不能掩盖 Spec fail、Spec pass 不能掩盖 Standards fail”的原则扩展到默认三轨：任一 required track 的通过不得掩盖另一 required track 的失败。

## 24. 后续独立工作

以下内容可以在本次 Ownership 重构 closed 后另立任务，不得混入本轮实施：

- 收敛 `code-review` 与 `standards-review` 的内容重叠。
- 重新校准三轨 severity 与 finding schema。
- 评估 safety-review 与默认三轨的组合策略。
- 优化 reviewer prompt 长度或上下文成本。
- 引入更强的 leaf enforcement 或 reviewer capability metadata。
- 基于实际 review 数据调整 loop 收敛策略。

后续任务不得作为本轮验收的隐含前置条件。本轮成功标准只看 Ownership、三轨调度、原双轴内容迁移、配置化和 legacy 清除是否完成。
