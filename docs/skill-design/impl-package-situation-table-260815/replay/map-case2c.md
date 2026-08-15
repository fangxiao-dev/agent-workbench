# 回放映射 · case2c

## 整体判断

本片覆盖案例 2 的第 3/4 片，时间线序号为 `4075–6191`，共 35 个主控决策点：26 个命中处境表、9 个 `unmatched`，主命中率为 **74.3%**；12 个决策点存在多重候选命中。被回放的 DMI-05/package 在本片结束时仍为 `BLOCKED`、Gate 未关闭；本片只完成 replay/extract/mapping 报告阶段，不代表源任务 closed。下一 session 只承接最后一个具名 P1 的修复、同 revision 验证和终审，最终 Gate 仍需 owner 评估；本片没有新增未决的产品合同选项。

这里的“完成”只指本报告的回放映射阶段。由于这是分片，本片开始前的 Ticket 初始化、首次 investigate、既有 evidence 与早期状态转换不在证据范围内；对这些事项不作跨片推断，统一标为 `insufficient-evidence`。

## 1. 案例概况

- **整体阶段**：案例 2 共 9 个 session；本片处于 DMI-05 终审发现与多轮修复之后、正式 checkpoint/handoff 和下一 session 恢复的阶段。它不是初始实现片，也不是 Gate 收口片。
- **任务包**：DATEV Mandant Import，当前焦点为 DMI-05 的 `precommit_contract_unsupported` 恢复/重校验、同 key replay、stale 判定、用户安全错误文案，以及 approved + active precommit 的 persistence/state seam。
- **worktree / branch**：`D:\CodeSpace\kaispan-dev\.worktrees\260812-datev-mandant-profile-import-planning` / `260812-datev-mandant-profile-import-planning`。
- **package**：`docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import`。
- **current attempt / Ticket**：`20260813-1907-terminal-review-provenance` / `DMI-05`。
- **本片 session**：
  - `ccaea2f3`（完整 ID 在交接材料中为 `019fff77-5074-7521-aeca-b58fccaea2f3`），主要完成终审 findings 消费、Grok 修复、多次同 revision 验证、合同决策和 checkpoint 准备。
  - `421b50d6`（新 session `01a000a4-abb7-7bf3-9ceb-4abb421b50d6`），只完成规范化 anchor 检查和从 `ER-011` 恢复的入口准备。
- **时间范围**：按时间戳最早为 `2026-08-14T11:25:48.834Z`（seq 4075），最晚为 `2026-08-14T14:23:17.081Z`（seq 6191）。两个 session 的事件在时间线上交错；`seq` 是本报告的定位依据，不用相邻 seq 的时间戳推断跨 session 因果。
- **本片末状态**：Grok 在 `d2ee9a404194fad4e880514caa7ba8119433f552` 的独立终审确认新的 P1：`approved + active precommit` 仍可经 `approved→draft` 的 source/parse 路径绕过 `validate` 清理旧绑定。父 session 建立/确认 `ER-011`，新 session anchor 最终 PASS，但 DMI-05/package 仍 BLOCKED，Gate 未关闭。

## 2. 抽取口径

“决策点”定义为主控实际选择下一动作，或消费一个 worker/reviewer 回执后改变路线；纯读取、重复状态播报、单纯测试命令和没有改变路线的轮询不另计。跨 session 的恢复、交接、交接纠错计入。

映射按处境表优先级取一个主 slug；同时明显成立的候选在“多重命中”单列，不重复计入总数。时间线的工具输出和 reasoning 有截断，内部 `state/trail/evidenceIndex` 字段也没有完整呈现；当某个机械条件无法从本片证据确认时，不把自然语言相似误写成确定命中。

## 3. 决策点与映射

| # | 时间 / seq | 主控决定 | 主映射 | 判定依据 |
| ---: | --- | --- | --- | --- |
| 1 | 11:29:29Z / `4113` | 四条终审 track 长时间没有最终 envelope，要求它们压缩并返回当前最终 findings。 | `attempt.review.terminal-coverage-incomplete` | 终审覆盖尚未齐全，动作仍是消费/收束 terminal review；符合 F3。 |
| 2 | 11:30:26Z / `4125–4133` | 第一条终审报告具名 P1 后，把候选 P1 交给 Grok 核验并修复，不在主控本地并行改 seam。 | `finding.fix.reviewer-returned` | reviewer 返回 finding，随后派 fresh repair worker；符合 E1。 |
| 3 | 11:34:40Z / `4180–4183` | 前两条候选 P1 被 Grok 否定后，依据三条终审共同指出的无 receipt/DB trigger seam，重新收窄修复请求。 | `finding.fix.reviewer-returned` | 仍是在消费 reviewer finding 后重新派 fresh fixer；不是新的初始实现。 |
| 4 | 11:39:13Z / `4225–4279` | Grok 提交 `b0c8b6b2` 后，先做同 revision 全套验证，再启动精确 HEAD 的四轨独立终审。 | `ticket.review.awaiting-reviewer` | worker 修复已返回且下一步明确进入 required review；同时 terminal coverage 尚未完成。 |
| 5 | 11:50:09Z / `4357–4364` | 四轨复审给出同 key replay P2 与 live PostgreSQL 证据缺口，把两项交给 Grok 确认/修复。 | `finding.fix.reviewer-returned` | reviewer 结果触发 fresh repair/confirmation；live DB 缺口的具体对象和 manual owner 在本片不可完全确认，单独列入版本/证据边界。 |
| 6 | 11:55:29Z / `4427–4498` | Grok 提交 `81af513f` 后重新跑同 revision 验证，并启动最后一轮独立终审。 | `ticket.review.awaiting-reviewer` | 修复回执后继续 required review；同时 terminal coverage 重新打开。 |
| 7 | 12:06:02Z / `4541` | 终审代理首个 120 秒窗口未返回，要求压缩并给出当前最终证据。 | `unmatched` | 现有 F3 只能说 coverage incomplete，不能区分正常等待、reviewer 超时和 ReviewRun 已不可采信。候选 slug：`attempt.review.reviewer-unavailable`。 |
| 8 | 12:10:29Z / `4592` | 多条 P2 互有重叠，先交 Grok 统一对照权威 contract，再决定是否分散修补。 | `ticket.verify.contradictory-unresolved` | 多个 review 结果无法直接归并为同一缺陷，先处置矛盾证据再改代码，符合 C14；也接近 sources-conflicting。 |
| 9 | 12:24:13Z / `4740–4793` | Grok 按 A–D 统一修复并同步 contract/spec，提交 `64ff6f55`；主控重跑完整同 revision 验证和终审。 | `finding.fix.reviewer-returned` | reviewer finding → fresh fixer → 同范围复审，符合 E1；review 的再次开启另列为多重命中。 |
| 10 | 12:37:33Z / `4885–4890` | 终审确认 same-key completed dry-run replay 非纯投影，按授权立即启动 Grok 修复。 | `finding.fix.reviewer-returned` | 新 P1 来自独立 reviewer，主控按 finding 进入 fresh fix。该修复随后被用户要求中止。 |
| 11 | 12:38:47Z / `4895–4912` | 用户要求先分析 Spec/contract、不要打补丁；主控停止已启动的 Grok 修复，转为只读合同一致性复审。 | `ticket.route.sources-conflicting` | 实现缺口与合同语义是否需要改变尚未分清，先回 req-align/合同核对，不继续派修复，符合 C5。 |
| 12 | 12:42:21Z / `4947–5006` | 将合同传播和实现一致性问题交给 Grok 做一次只读盲审，禁止改文件。 | `ticket.review.awaiting-reviewer` | 当前动作是对已暴露合同/实现边界做独立 review；内部 `review_required` 字段未完整呈现，但 review 触发事实明确。 |
| 13 | 12:48:49Z / `5051–5055` | 把唯一 owner 决策收敛为：`precommit_contract_unsupported` 后，new key 是否可以沿用旧 approval 直接创建新 dry-run。 | `ticket.route.multiple-business-outcomes` | 存在两个合理业务结果，主控请求 owner decision；符合 C3。 |
| 14 | 13:04:17Z / `5094–5101` | 用户同意“只暴露安全 reason + nextAction”；主控锁定系统更新/重新确认/联系管理员三类最小用户合同。 | `ticket.route.multiple-business-outcomes` | 用户可见行为仍有多个合理设计，owner 选择后才进入实现；内部 contract/version/hash 不进入普通 UI。 |
| 15 | 13:04:53Z / `5101–5154` | 按已选合同落 API 稳定 machine code 到 UI 安全文案的映射，并补同 surface 回归测试。 | `ticket.route.sources-uniquely-decide` | owner 选择和现有 Spec/contract 已裁决路线，主控进入实现并重验，符合 C4。 |
| 16 | 13:12:30Z / `5208–5216` | 本轮 UI/replay 修复完成后，启动只读 closure review，范围锁定四个业务代码/测试文件。 | `ticket.review.awaiting-reviewer` | implementation 结束且 review scope 明确，进入 required closure review。 |
| 17 | 13:23:42Z / `5284–5292` | 静态复审又发现事项列表和未知错误泄露技术码，收窄 UI 文案并用目标 spec 重验，避免无关慢测污染结论。 | `finding.fix.main-session-discovered` | finding 由主控自己的复审/grep 暴露，可直接进入 fresh/direct fix，符合 E3。 |
| 18 | 13:25:58Z / `5321–5339` | closure review 认定新增的 contract-unsupported + dry-run 特殊文案分支不可达，撤回该分支，只保留既有稳定合同。 | `finding.fix.reviewer-returned` | 独立 review 返回可执行 finding 后修正并再次核对，符合 E1。 |
| 19 | 13:27:05Z / `5344–5355` | 只提交四个业务代码/测试文件，明确不带入受保护 `plan.md` 和 package 状态，并继续声明 package BLOCKED。 | `unmatched` | staged scope/commit boundary/“代码完成但 package 未闭合”没有专门行。候选 slug：`attempt.record.revision-scope-fixed`。 |
| 20 | 13:29:00Z / `5360–5363` | 在用户询问“需要我干嘛”后，再次请求并收到“new key 必须重新 validate → approve”的明确确认。 | `ticket.route.multiple-business-outcomes` | 原冻结 attempt 复用与重新批准是 owner judgment；确认后才允许改变合同，符合 C3。 |
| 21 | 13:38:25Z / `5396–5495` | 将已批准语义传播到 Spec、contract-design、DMI-03 AC、API/UI 和测试：新 key 不直接绕过旧 approval，validate 原子清绑定后才可 approve/dry-run。 | `attempt.rework.contract-changed` | 合同语义相对前一轮实现发生实际变化，保留未受影响证据并在新 revision 重验，符合 D4。 |
| 22 | 13:46:26Z / `5528–5545` | 10 个目标文件静态/契约回归通过后创建 commit，做 claim audit，再交给 Grok 做新 commit 的只读终审。 | `ticket.review.awaiting-reviewer` | 新 revision 的实现已完成，独立 review 是下一道 required gate；commit scope 同时构成记录层候选。 |
| 23 | 13:53:44Z / `5683–5844` | 独立终审发现 CAS allowlist/SQL trigger 仍挡住“approved + active precommit → validate 清绑定”，主控在当前 session 直接修 persistence/state seam，并补边界测试。 | `finding.fix.reviewer-returned` | reviewer 返回具名 P1，处境符合 E1；但实际没有派 fresh fixer，而是主控直接 `apply_patch`，属于命中后偏离默认动作，不把 P1 当作 Gate 可直接通过。 |
| 24 | 14:02:24Z / `5844–5932` | 防线补上后先验证 DB CAS/迁移、API、Web 三个 seam；确认本机无 5432/5433 PostgreSQL，不伪造 live-DB 证据。 | `ticket.verify.safety-invariant-unfalsified` | 这是对 data-integrity/state safety seam 的具体重验，符合 C9 的“不得推迟安全不变量验证”；实跑 DB 结果仍缺失。 |
| 25 | 14:09:01Z / `5943` | 提交前只保留 10 个目标文件，隔离受保护 `plan.md`；把没有 live PostgreSQL 结果的事实保留下来，不以静态检查替代。 | `unmatched` | 该决定同时包含 revision-scoped commit 和外部验证不可用；后者不是已知 manual owner 场景。候选 slug：`attempt.verify.external-evidence-unavailable`。 |
| 26 | 14:09:39Z / `5950–5951` | 用户要求下一个业务实现前先做好 checkpoint；主控承诺先完成同 revision 验证/复审，再创建新 local session。 | `attempt.record.checkpoint-missing` | 交接/长任务边界已触发 G1；checkpoint 需先 durable 落盘。 |
| 27 | 14:10:07Z / `5960–5975` | 同 revision 全量 DB/API/Web 验证通过后，补 typecheck/lint、claim audit，并启动 terminal-final 独立 review。 | `ticket.review.awaiting-reviewer` | 不能把全量测试当作 closure，仍按 review-required 进入 terminal review。 |
| 28 | 14:13:43Z / `6025–6041` | 发现本 session 被禁止修改 progress/gate/execution-record/evidence，改把 checkpoint candidate、HEAD 和证据发回 owner session，继续等待完整 review envelope。 | `attempt.record.checkpoint-missing` | G1 的记录需求仍存在，但由于记录权限边界，本 session 没有完成写入；不是把 continuation prompt 当作 durable checkpoint。 |
| 29 | 14:19:18Z / `6093–6095` | 用户指出 checkpoint 应发给新 session 而非旧 session；主控纠正 handoff 目标，要求先消费完整 Grok 结果，再只创建一个新 local session。 | `unmatched` | 现有 G1/A3 没有交接目标误投后的纠错状态。候选 slug：`attempt.record.handoff-target-corrected`。 |
| 30 | 14:19:34Z / `6100` | Grok 在新 HEAD 上判 FAIL、确认新的 P1；主控不在当前 session 打下一业务补丁，先把具名 blocker 和 checkpoint 交给新 session。 | `unmatched` | 这是“review finding 延后到下一 session”的处置，既不是 C12 的业务 BLOCKED，也不是 Gate verdict。候选 slug：`attempt.rework.finding-deferred`。 |
| 31 | 14:19:57Z / `6109` | 新 session 已创建但重命名返回 `No Codex thread found`，按 handoff skill 停在 title 阶段，不创建重复 session、不发送 continuation。 | `unmatched` | 现有表没有 handoff infrastructure/metadata 失败的处境。候选 slug：`attempt.record.handoff-incomplete`。 |
| 32 | 14:20:26Z / `6123–6130` | 发现旧 session 的异步动作改写了 checkpoint projection，不覆盖它，先只读核对最新正式 `ER-011` 再恢复。 | `unmatched` | 这是 checkpoint projection race/并发交接卫生，不是 A3 的正常恢复。候选 slug：`attempt.record.checkpoint-projection-race`。 |
| 33 | 14:21:42Z / `6135–6154` | 新 session anchor PASS 后才发送基于 `ER-011` 的 continuation；旧 session 不再接收任务，下一 session 承接 P1。 | `unmatched` | checkpoint 已存在，因此 G1 的“checkpoint missing”条件不成立；表没有“已验证 anchor 后发送 continuation”的正常 handoff 行。候选 slug：`attempt.record.handoff-continuation-sent`。 |
| 34 | 14:20:10Z / `6162–6164` | 新 session 首次 anchor 因 Windows 路径分隔符比较失败，主控规范化绝对路径后重跑，得到 anchor PASS。 | `unmatched` | 这是表示层/规范化误报，不是 package state invalid。候选 slug：`attempt.record.anchor-representation-mismatch`。seq 与时间戳交错，按 seq 归属本片。 |
| 35 | 14:22:10Z / `6165–6168` | 新 session 从 entry point 和 `ER-011` 的最小记录恢复，不回溯完整历史，开始处理具名 P1。 | `attempt.record.session-resumed` | active checkpoint 已存在且恢复 session 尚无后续工作，符合 A3。 |

## 4. 读数

### 4.1 总读数

| 指标 | 数值 |
| --- | ---: |
| 决策点总数 | 35 |
| 有主 slug 命中 | 26 |
| `unmatched` | 9 |
| 命中率 | 26 / 35 = **74.3%** |
| 多重命中点 | 12 |
| 主命中中 `cli` basis | 1（`ticket.verify.contradictory-unresolved`） |
| 主命中中 `prose` basis | 25 |

命中率按主 slug 计算；多重命中只增加诊断信息，不把一个决策点复制成两个样本。

### 4.2 按环节的主命中分布

| 环节 | 命中次数 |
| --- | ---: |
| `record` | 3 |
| `readiness` | 0 |
| `investigate` | 0 |
| `route` | 5 |
| `implement` | 0 |
| `fix` | 8 |
| `verify` | 2 |
| `review` | 7 |
| `accept` | 0 |
| `rework` | 1 |
| `disposition` | 0 |
| `gate` | 0 |
| **合计** | **26** |

本片的重心是 `review → fix → review` 循环和跨 session `record`，没有进入 `readiness`/初始 `investigate`，也没有出现新的 `accept` 或 `gate` verdict。初始调查是否存在、Ticket 是否曾有 `SATISFIED`/`NEEDS-REVALIDATION` 状态，均在本片外，不能倒推。

### 4.3 多重命中清单

以下 12 个点同时符合多个候选，按当前优先级取表中主 slug：

1. **#4 / seq 4225–4279**：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。worker 修复回执已消费，但 terminal review 尚未齐全。
2. **#6 / seq 4427–4498**：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。同样是新 revision 的 review 重开。
3. **#8 / seq 4592**：`ticket.verify.contradictory-unresolved` + `ticket.route.sources-conflicting`。多个 review 结果重叠且需要按权威 contract 重新裁决。
4. **#9 / seq 4740–4793**：`finding.fix.reviewer-returned` + `ticket.review.awaiting-reviewer`。finding 修复完成后马上重建独立 review 门。
5. **#11 / seq 4895–4912**：`ticket.route.sources-conflicting` + `ticket.verify.contradictory-unresolved`。同一 P1 究竟是实现缺陷还是合同应变更尚未定性。
6. **#12 / seq 4947–5006**：`ticket.review.awaiting-reviewer` + `ticket.route.sources-conflicting`。合同漂移在进入修复前先做独立只读审查。
7. **#15 / seq 5101–5154**：`ticket.route.sources-uniquely-decide` + `ticket.review.required-trigger`。安全错误传播和公开 UI 合同已定，但仍需独立 review。
8. **#16 / seq 5208–5216**：`ticket.review.awaiting-reviewer` + `ticket.review.required-trigger`。closure review 是已确定的 required gate。
9. **#21 / seq 5396–5495**：`attempt.rework.contract-changed` + `ticket.route.sources-uniquely-decide`。owner 改变合同后，路线已裁决再做实现。
10. **#22 / seq 5528–5545**：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。新 commit 的独立审查尚未结束。
11. **#23 / seq 5683–5844**：`finding.fix.reviewer-returned` + `ticket.verify.safety-invariant-unfalsified`。reviewer P1 直接触及 persistence/data-integrity seam。
12. **#26 / seq 5950–5951**：`attempt.record.checkpoint-missing` + `attempt.review.terminal-coverage-incomplete`。交接前仍有终审进行中，checkpoint 不能用口头摘要替代。

## 5. `unmatched` 清单

| 决策点 | 真实处境 | 建议 slug | 判定说明 |
| --- | --- | --- | --- |
| #7 / `4541` | review 首个窗口超时/未封装最终 envelope，主控要求压缩返回。 | `attempt.review.reviewer-unavailable` | `attempt.review` 在允许矩阵内；状况区分正常等待与 reviewer 已不可采信。 |
| #19 / `5344` | 只提交目标业务文件，保护 `plan.md`/package records，固定 revision scope。 | `attempt.record.revision-scope-fixed` | 当前表没有 commit/staged-scope 的记录处境，不能伪造 `accept` 或 `gate`。 |
| #25 / `5943` | live PostgreSQL 不可用，主控明确不伪造 integration 证据，同时做受保护文件隔离提交审计。 | `attempt.verify.external-evidence-unavailable` | `attempt.verify` 合法；现有 F1 只覆盖已知 manual owner，不足以吸收本场景。 |
| #29 / `6095` | checkpoint candidate 误发旧上游 session，用户纠正后改发新 session。 | `attempt.record.handoff-target-corrected` | A3/G1 没有“目标选择错误后纠正”的状态。 |
| #30 / `6100` | reviewer P1 被有意延后到下一 session，当前 session 不继续打补丁。 | `attempt.rework.finding-deferred` | 不是业务 worker `BLOCKED`，也没有新的 Gate verdict。 |
| #31 / `6109` | 新 thread metadata/title 操作失败，handoff 停在 title 阶段。 | `attempt.record.handoff-incomplete` | 这是交接基础设施失败，不是普通 checkpoint missing。 |
| #32 / `6123` | 旧 session 异步改写 checkpoint projection，主控选择不覆盖并先核对正式记录。 | `attempt.record.checkpoint-projection-race` | 现有 G1 只表达“需写 checkpoint”，不表达并发 projection 冲突。 |
| #33 / `6135–6154` | 新 session anchor PASS 后发送 continuation，checkpoint 已存在。 | `attempt.record.handoff-continuation-sent` | 正常 handoff 的完成动作没有单独行；G1 的 missing 条件不成立。 |
| #34 / `6162–6164` | 实际 worktree/HEAD 正确，但路径分隔符比较造成首次 anchor FAIL，规范化后 PASS。 | `attempt.record.anchor-representation-mismatch` | 属于记录/恢复锚点表示层误差，不能归为 `package.record.state-missing`。 |

## 6. 跳步检测

### 6.1 没有调查载体就直接进入实现：0 次可确认；跨片 `insufficient-evidence`

本片从已有终审/finding 修复开始，没有出现一个 PENDING、无 investigate 载体且无 evidence 的新 Ticket。seq `5101`、`5396` 的实现都建立在本片已经存在的合同复审、owner decision、测试和 review 证据上，不能倒判为 C1 的“无载体直接实现”。

本片之前是否曾出现 C1、是否因为没有 investigate 载体直接进入第一次实现，无法由本片确认。

### 6.2 worker/reviewer 返回后未记 evidence 就推进：11 批可观测转移

本片没有找到 `evidence add`、`evidenceIndex` mutation、`needs-revalidation` 或 `evidence invalidate` 命令。以下 11 批都能看到回执/直接证据返回后，主控立即进入下一动作；这表示“本时间线没有可见的落账动作”，不等同于证明外部 package state 一定没有写入。

1. seq `4123–4144` → `4125/4180`：多条终审返回 P1/P2 后直接进入 Grok 修复。
2. seq `4225` → `4242/4273`：Grok `b0c8b6b2` 返回后直接同 revision 验证和重审。
3. seq `4344–4355` → `4357`：终审返回 P2/证据缺口后直接交 Grok 确认/修复。
4. seq `4427` → `4483/4498`：Grok `81af513f` 返回后直接重验和重审。
5. seq `4557–4591` → `4592`：多个 reviewer 返回 P2 后直接做统一裁决/修复路由。
6. seq `4740` → `4793`：Grok `64ff6f55` 返回后直接完整验证和终审。
7. seq `4884` → `4885–4890`：reviewer 返回 same-key P1 后直接启动 Grok fix；虽随后被用户中止，仍发生了路线推进。
8. seq `4947–5006` → `5051/5055`：只读合同审查返回后直接进入 owner decision，而无可见 evidence 入账。
9. seq `5321` → `5339/5344`：closure review 返回不可达分支后直接删除分支并提交。
10. seq `5683` → `5844`：终审返回 persistence P1 后直接进入 seam 修复。
11. seq `6100` → `6109/6130`：终审 FAIL 返回后直接进入 checkpoint/handoff，而非在本 session 新增 evidence 记录。

这 11 批主要说明旧版执行形态里“自然语言 evidence 很丰富，但机械 evidence indexing 不可见”。由于本片明确存在“本 session 不得改 package records/Gate”的边界（seq `6025`），不能把它直接解释为新版 CLI 的实际漏写。

### 6.3 未经独立 review 就宣称完成或 satisfy：0 次可确认

- 没有 `ticket satisfy`、`gate pass` 或同等状态写入。
- seq `5355`、`6130`、`6154` 都明确说业务代码/修复已结束但 package 仍 BLOCKED、Gate 未关闭，或下一 session 仍需修复/终审。
- commit、focused/full test 通过和 worker DONE 均没有被主控当作 package closed。

### 6.4 已 `SATISFIED` Ticket 被新证据触及时的处置：0 次可见；跨片 `insufficient-evidence`

本片没有出现 Ticket 从 `SATISFIED` 被新 claim 触及时的 `evidence invalidate`、`ticket needs-revalidation`、独立 finding 或 superseded 处置。DMI-05 在本片明确是 BLOCKED；更早是否存在 SATISFIED Ticket、以及该 Ticket 的新证据是否在前两片处理，无法猜测。

## 7. 表本身的问题

1. **reviewer 不可用与正常等待没有分界。** seq `4091–4113`、`4541`、`6041–6078` 都出现长时间等待/超时/heartbeat；F3 可以吸收“coverage incomplete”，但不能表达“压缩结果、重开 ReviewRun、取消旧 reviewer”这类动作。建议单独评估 `attempt.review.reviewer-unavailable`。

2. **live integration evidence 缺口没有精确行。** `127.0.0.1:5433` P1001 和无本地 PostgreSQL 在 seq `4273`、`4483`、`4855`、`5932` 反复出现。F1 只有“manual owner 已计划但无结果”的条件；本片没有完整的 planned-owner 字段，因此既不能硬映射 F1，也没有“外部验证不可用但静态证据已足够继续”的处境。

3. **finding 的实现缺陷与合同歧义边界不清。** seq `4885` 先按 reviewer P1 进入 `finding.fix.reviewer-returned`，用户马上要求停止 patch、先判断 Spec/contract（seq `4895–4912`）。当前表没有清楚表达“finding 已返回，但是否真的是 implementation defect 尚未裁决，先转 route/req-align”的边界；E1 与 C5 的交界会依赖主控解释。

4. **跨 session checkpoint 的目标、投影和完成动作缺行。** seq `6026` 误发旧 session，seq `6093–6095` 纠正目标，seq `6123` 又出现异步 projection 改写，seq `6162` 首次 anchor 还因路径表示误报失败。G1/A3 只覆盖 missing checkpoint 与正常恢复，无法精确读出 handoff target、projection race、anchor normalization。

5. **revision-scoped commit/review anchor 没有独立记录处境。** seq `4225`、`4427`、`4740`、`5528`、`5943` 反复执行“固定 exact HEAD → 同 revision 验证 → 独立 review”；当前表有 D2/F7 的 divergence/mismatch，但没有“scope 固定且等待新 revision review”的正常记录行。该缺口容易把 commit boundary 误归到 accept 或 gate。

6. **C8 的 prose 规则在旧执行形态中没有即时信号。** 11 批 return→next-action 都没有可见 evidence indexing，但主控仍能继续修复、提交和交接。若不把 `evidence.indexed=false` 接到 renderer 或记录检查，C8 只能事后解释，不能在推进前形成可操作阻断。

7. **E1 的 fresh fixer 约束没有被稳定执行。** seq `5683–5844` 明确是 reviewer 返回的 P1，但主控直接在当前 session 修改 tenant CAS、migration、API/UI 和测试；表能识别 finding 来源，却不能从轨迹中清楚区分“处境命中”与“默认 fresh fixer 动作被绕过”。

## 8. 版本干扰与结论边界

- 本片使用的是演进中的旧版 skill/tool 形态：seq `6169` 先尝试工作树里的 `subagent-driven-development`，seq `6171` 尝试缓存 `0.3.0`，seq `6177` 最终读取缓存 `0.3.1`；seq `6183` 还在读取 `execution-preflight`、`dev-with-track` 和协作 references。
- 时间线没有处境表 renderer、三段式 `situation` slug、`trail.jsonl` 尾部聚合或显式 `evidence add` 的运行记录。worker/reviewer 主要通过 `multi_agent_v1`、Grok wrapper、自然语言 envelope 和受保护 package 边界协作。
- seq `6025` 明确本 session 不能修改 `progress/gate/execution-record/evidence`；因此本片中 evidence/checkpoint 的“未见落账”同时受权限边界影响，不能据此改写表的 `basis` 或断言新版 CLI 漏记。
- 时间线工具输出、user continuation、reasoning 都有截断；对完整 `state.json`、`trail`、Ticket state、planned manual owner 的判断只能使用本片显式文字。初始 C1/C2、SATISFIED 触证和早期 Gate 行为应留作 `insufficient-evidence`，不要跨片补全。
- `precommit_contract_unsupported` 的恢复路径经历了 owner 语义澄清：先讨论 new key 是否沿用旧 approval，再确认“旧版本可恢复则原 attempt 重试；切换新版本必须重新 validate/approve”。这些是本片真实业务决策，但不能直接说明处境表某行的 `basis` 已应升为 `observed`。

## 9. 结论

本片对“review/finding 循环、合同歧义转 owner decision、合同变更后的 rework、同 revision 验证和恢复 session”有 26/35 的主覆盖；12 个多重命中说明 review、route、verify、record 之间的边界确实会同时出现，但当前优先级仍能给出稳定主 slug。

最值得保留的三个发现是：

1. **表能识别大多数 review→fix→review 业务循环，却无法精确表达 reviewer 不可用和 live integration 证据不可得。** 这两类情境被 F3/F1 部分吸收，但动作和继续条件不同。
2. **record 层是本片最明显的真实缺口。** 11 批回执后推进都没有可见 `evidence add`，且 checkpoint 受权限边界、误投、projection race 和 anchor 表示差异影响；旧版流程的 durable 记录并不等于聊天 continuation。
3. **合同歧义会把同一 reviewer finding 在 fix 与 route 之间来回切换。** seq `4885–5055` 证明“先修实现”不是总是合法的下一步；需要先决定是原 claim 被证伪，还是合同/产品语义需要 owner 重定。

本报告只报告真实处境与当前表的覆盖，不修改 `situations.yaml`、设计文档或其它仓库文件。
