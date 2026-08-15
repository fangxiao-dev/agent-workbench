# 回放映射 · case1

## 证据边界与统计口径

- 唯一输入是 `.test-tmp/replay-timelines/timeline-case1.jsonl`；没有读取原始 rollout。
- 本案是完整时间线，不是分片；但它只覆盖整体任务的 **T2 收口 → T3 验证、构建 finding 修复与再次收口**，不覆盖 T1 的实际执行，也不覆盖整个 Package 的最终 Gate。
- `seq` 是决策定位主键。两个 session 的记录在时间上有轻微交错，因此不以跨 session 的时间戳单独推断先后。
- “决策点”合并重复的 `wait`、文件读取、轮询和同一动作的重试；只有主控改变 worker mode、Ticket/attempt 记录、finding 路由、review、checkpoint、judgment、Gate 或交接路径时才计一条。
- 时间线截断了 worker 输出、状态字段和部分长指令。严格命中只在处境条件与实际动作都能由时间线支持时计入；不能安全判定的单列 `insufficient-evidence`，不猜测。

## 1. 概况

任务是在 `D:\CodeSpace\kaispan-dev\.worktrees\mobile-photo-capture-ocr-poc` 中推进 Daily Cash 移动拍照集成 Package：

`docs/domains/finance-assistant/implementations/2026-08-13-daily-cash-mobile-photo-capture/`

- session：2 个，`a99be3f0`、`70e843c2`。
- 时间跨度：`2026-08-13T20:30:08.687Z` → `2026-08-13T22:17:15.932Z`；时间线摘要给出的跨度约 1 小时 47 分。
- 入口状态：T1 已 SATISFIED，T2 ready；Attempt active，Gate open。
- 第一段：T2 implement → 四轨 initial review → F-001/F-002/F-003 fix → closure review → evidence/judgment → T2 SATISFIED，并写入 T3 checkpoint。
- 第二段：T3 verify worker 返回 `INCOMPLETE`，独立 review 判定 Next/Turbopack 的 `fs` 构建缺陷；用户随后授权 `start-env dev`，主控修复构建 finding，重新 build/test/browser 验证并提交。
- 最终状态：T2 SATISFIED；T3 仍 `PENDING`；Gate 仍 `open`；缺少 iOS Safari、Android Chrome 真机证据，且本轮没有触发相机、上传、OCR 或“提交并识别”。修复提交为 `c0278381`，未 push、未创建 PR；整体 Package **未 closed**。

## 2. 总读数

| 指标 | 数量 | 说明 |
| --- | ---: | --- |
| 决策点总数 | 22 | 按上面的合并口径 |
| 严格命中 | 11 | 50.0% |
| 明确 `unmatched` | 10 | 没有现有行能准确承接实际决定 |
| `insufficient-evidence` | 1 | 候选是 C1，但缺少 `trail.has_investigate/evidence.count` |
| 有效未覆盖数 | 11 | `unmatched` + `insufficient-evidence` |
| 多重命中/潜在多重命中 | 5 | 其中 2 个可直接确认，3 个受截断或边界条件影响 |

因此本报告的严格命中率为 `11 / 22 = 50.0%`；若把唯一的 `insufficient-evidence` 也强行当命中，会得到 54.5%，但不采用该读数。

### 按环节的严格命中分布

| 环节 | 命中数 | 命中点 | 备注 |
| --- | ---: | --- | --- |
| `record` | 3 | D01、D07、D11 | 恢复、evidence 入账、跨 session 恢复 |
| `readiness` | 0 | — | 正常的单一 ready Ticket 没有专门行 |
| `investigate` | 0 | — | D02 只到 C1 候选，条件不足 |
| `route` | 1 | D15 | reviewer 明确将构建失败路由为 implementation defect |
| `implement` | 0 | — | D13 的 `INCOMPLETE` 被现有 implement 行机械吸引，但语义不适用 |
| `fix` | 2 | D04、D16 | reviewer findings 的 T2 fix；T3 构建 finding 的主控直接 fix |
| `verify` | 1 | D12 | T3 safety-invariant 未有完整证据，派 verify worker |
| `review` | 2 | D03、D18 | T2 initial review；T3 review coverage 不完整时的处置 |
| `accept` | 1 | D08 | T2 satisfy |
| `rework` | 0 | — | 没有已 SATISFIED Ticket 被新证据推翻 |
| `disposition` | 0 | — | 没有 retire 或 finding grading/triage 的实际状态动作 |
| `gate` | 1 | D21 | `verdict` 未决；实际选择是保持 open，未选表内四种 verdict |
| **合计** | **11** |  |  |

## 3. 决策点与映射

| # | 时间（UTC） | 主控决定（timeline seq） | 映射 | 判定依据 |
| --- | --- | --- | --- | --- |
| D01 | 20:32:24 | 从 active checkpoint 恢复 T2，并以 `Preflight: READY` 作为本轮入口（seq 21、46） | `attempt.record.session-resumed` | 明确是 continuation、读取最小权威记录且没有重做历史，符合 A3。 |
| D02 | 20:36:42–20:37:01 | T2 直接派 `mode=implement` 的 `@luna-worker`，同时要求 review（seq 87、89） | `insufficient-evidence`；候选 `ticket.investigate.no-carrier`；另有 `ticket.review.required-trigger` | 直接实施与 C1 的 escape 一致，且明确说明 scope-token/data-integrity 风险；但截断输入没有同时给出 `trail.has_investigate=false` 与 `evidence.count=0`，不能把 C1 当严格命中。 |
| D03 | 20:50:48–20:53:47 | worker 返回 `DONE / PENDING_REVIEW` 后固定 comparison revision，启动四轨独立 initial review（seq 180、208、214–220、228） | `ticket.review.awaiting-reviewer` | `DONE`、`review=required` 和不可变 comparison point 均在时间线中明确，符合 C6。 |
| D04 | 21:03:19–21:07:59 | initial review 的 F-001/F-002/F-003 路由到 fresh fix invocation（seq 255、280、281） | `finding.fix.reviewer-returned` | finding 来源是 reviewer，主控选择 fresh follow-up fix，符合 E1 的默认路由。 |
| D05 | 21:12:50–21:19:01 | fix worker 保持 `PENDING_REVIEW` 后，启动同 scope 的 finding-closure review（seq 302、347、379） | `unmatched`；建议 `finding.review.closure-awaiting` | E1 只描述“reviewer finding → fixer”，E2 只覆盖 Track C/source recheck；fix 后等待 closure reviewer 的实际处境没有自己的行，C6 又要求 `last_outcome=DONE`。 |
| D06 | 21:21:43–21:22:37 | `package validate` 因旧的 Runtime Acceptance projection 失败，删除该 projection block 后重验（seq 429、443） | `unmatched`；建议 `package.record.projection-stale` | 真实问题是 Ticket 文档中的 retired projection；A2 的 manual reason 明确只讨论 progress/state drift，不能把两者等同。该点另受版本干扰，见第 8 节。 |
| D07 | 21:25:06 | 将 T2 直接证据 JSONL 加入 evidence index（seq 492；结果 seq 499） | `ticket.record.evidence-unfiled` | worker 直接证据先形成 artifact，直到此处才入账，符合 C8；在 satisfy 前可能同时像 C13，但 acceptance-edge 状态未完整显示。 |
| D08 | 21:25:54 | 执行 `ticket satisfy T2-daily-integration --expect PENDING --revision ... --environment ...`（seq 500–501） | `ticket.accept.satisfiable` | evidence 已入账，命令成功将 T2 置为 SATISFIED，符合 C15。 |
| D09 | 21:26:15 | 为 T2 写 recovery judgment，记录“finding closure 后 satisfied”（seq 506–507） | `unmatched`；建议 `ticket.record.judgment-written` | 表有 evidence record，但没有 judgment 写入/判断已落账这一记录处境；本次是显式的主控判断，不应隐含吞掉。 |
| D10 | 21:26:26–21:26:39 | 写 T3 active checkpoint，准备跨 session 继续 browser/network 验证（seq 509、511） | `unmatched`；建议 `attempt.record.checkpoint-refresh` | 实际是已有 checkpoint 的推进/刷新；G1 的条件是 active checkpoint 缺失，时间线没有证明该条件成立。 |
| D11 | 21:28:41–21:28:50 | 通过 T3 handoff 在新 session 恢复同一 Package，并把 T3 verify 作为下一动作（seq 579、581；交接卡片 seq 554） | `attempt.record.session-resumed` | 新 session、active checkpoint、只恢复最小上下文，符合 A3。 |
| D12 | 21:31:08–21:31:38 | 针对 T3 的未证实安全不变量派只读 `mode=verify` worker（seq 621、629） | `ticket.verify.safety-invariant-unfalsified` | T3 的后续 review 明确有 3 个 safety invariants 缺少完整证据；本次派 verify 正是 C9 的默认动作。 |
| D13 | 21:39:10–21:39:57 | verify worker 返回 `INCOMPLETE`，主控启动独立 review 来判断 build blocker（seq 744、756、757） | `unmatched`；建议 `ticket.verify.worker-incomplete-first` | 这是 verify worker 的 `INCOMPLETE`，实际下一步是 review；现有 C10/C11 的 slug 固定在 `implement`，机械上可能命中 C9/C10，但其动作会错误地导向 verify/implement，不能承接实际决定。 |
| D14 | 21:41:46–21:42:06 | 用户新增 `dev` 授权后，停止 Next-only 并启动 canonical `start-env dev`（seq 779、782、788） | `unmatched`；建议 `attempt.verify.environment-authorized` | 这是授权后的验证环境切换，属于 attempt-level verify；现有表没有环境权限/验证 profile 变化这一处境。 |
| D15 | 21:50:01–21:51:28 | 独立 review 将 `@techstark/opencv-js` 的 `fs` 解析失败定为 implementation defect，而不是继续归为环境 blocker（seq 915、937） | `ticket.route.sources-uniquely-decide` | reviewer、构建错误和浏览器复现共同唯一裁决修复路线，符合 C4 的语义；T3 仍未 satisfy。 |
| D16 | 21:51:52–21:58:20 | 主控诊断并直接应用最小 `fs` browser alias/shim，复跑 build、browser、390×844、tests（seq 945、984、988–989、1032） | `finding.fix.reviewer-returned`（chosen escape）；次像 `ticket.route.sources-uniquely-decide` | finding 来自 reviewer，但实际由主控直接修复，没有再派 fresh fixer；E1 能识别 finding 来源，却不能接受这个明确的 owner-authorized direct-fix 动作。 |
| D17 | 22:05:02–22:05:05 | 对未提交的 build fix 派独立只读审查（seq 1089、1090） | `unmatched`；建议 `finding.review.closure-awaiting` | 这是 fix 后的 closure review，不是 E2 的 source recheck；该 reviewer 后续没有在时间线内成功返回 closure 结果。 |
| D18 | 22:12:24–22:12:45 | closure reviewer 超时后关闭它，主控记录 build finding 已验证，但明确不关闭 T3（seq 1155、1160） | `attempt.review.terminal-coverage-incomplete`（chosen escape） | 没有成功的 terminal/closure coverage 结果，符合 F3 的缺口条件；实际没有再次 `do-review`，而是以已有 build/test/browser 证据继续记录。 |
| D19 | 22:13:19 | 将 T3 build finding closure 写为 recovery judgment（seq 1171–1172） | `unmatched`；建议 `ticket.record.judgment-written` | 判断已明确写入，但表没有“finding closure judgment 已落账”这一 record 行。内容同时明确 T3 仍 pending，因此不是 satisfy。 |
| D20 | 22:13:47 | 更新 active checkpoint，下一步仍是授权范围内 browser/390×844，之后停在真机边界（seq 1178–1179） | `unmatched`；建议 `attempt.record.checkpoint-refresh` | 这是 checkpoint refresh，不是“checkpoint missing”；对象/环节可合法组合，但现有状况行缺失。 |
| D21 | 22:14:16–22:17:15 | 保持 T3 `PENDING`、Gate `open`，不执行 satisfy 或 Gate verdict（seq 1187、1214–1217） | `attempt.gate.verdict-undecided`（chosen escape） | Gate 没有 pass/blocked/fail/defer 的实际命令；“继续 open 等待证据”是 F6 能看到但动作矩阵没有表达的状态。`gate blocked --help`/`gate defer --help` 只是帮助查询，不是状态转换。 |
| D22 | 22:15:53–22:16:53 | 应用户请求，将 OpenCV fix 与同一验证/追踪记录合并提交（seq 1194、1196、1209、1211） | `unmatched`；建议 `attempt.record.change-committed` | Git commit 是交付边界决策，但 42 行表没有 commit/landing 处境；不应把它误记成 Gate pass 或 Package closed。 |

## 4. 多重命中

共列 5 个多重命中或潜在多重命中点：

1. **D02（seq 87–89）**：直接实现同时像 `ticket.investigate.no-carrier` 的 escape 和 `ticket.review.required-trigger`。优先级应先消化“无调查载体”，再谈 review；但 C1 的两个机械谓词未在截断输入中出现。
2. **D03（seq 180–220）**：`ticket.review.awaiting-reviewer` 与 `ticket.review.required-trigger` 同时成立；前者按优先级承接“DONE 后等待 reviewer”，后者保留“shared seam/data-integrity 触发 review”的旁命中。
3. **D07（seq 492）**：`ticket.record.evidence-unfiled` 消费 evidence 返回，同时可能处于 `ticket.accept.acceptance-edge-held`；后者的 edge 状态没有完整输出，标为 `insufficient-evidence`。
4. **D13（seq 744–757）**：当前 T3 verify worker 的 `INCOMPLETE` 机械上会撞到 `ticket.implement.worker-incomplete-first`，同时 T3 safety claim 仍未证实会撞到 C9；优先级与动作都无法导出实际的“转独立 review”。这是最清楚的模式边界缺陷。
5. **D16（seq 945–1032）**：reviewer-returned finding 的 `finding.fix.reviewer-returned` 与 `ticket.route.sources-uniquely-decide` 同时像；实际选择是主控直接 fix，既不是 E1 默认 fresh fixer，也不是 C4 字面上的 dispatch implement。

## 5. `unmatched` / `insufficient-evidence` 清单

以下 11 个点是严格统计中没有安全命中现有表的点；建议 slug 均遵守三段式、允许矩阵和相邻环节判定线。重复出现的建议 slug 表示同一缺口在不同阶段再次发生。

| 决策点 | 真实发生 | 建议 slug | 证据缺口/边界 |
| --- | --- | --- | --- |
| D02 | T2 直接 implement | `ticket.investigate.no-carrier`（候选） | `has_investigate` 与 evidence count 未在 timeline 中同时出现，所以标 `insufficient-evidence`，不把它算严格命中。 |
| D05 | fix 后等待同 scope finding-closure review | `finding.review.closure-awaiting` | finding.review 允许矩阵合法，但现有 E2 只覆盖一次性 source recheck。 |
| D06 | 旧 Runtime Acceptance projection 阻断 validate，随后删除 | `package.record.projection-stale` | A2 的 progress/state drift 定义不适用；且可能只是旧版 projection 遗留。 |
| D09 | 写 T2 judgment | `ticket.record.judgment-written` | 表没有 judgment record 状况。 |
| D10 | 为 handoff 刷新 T3 checkpoint | `attempt.record.checkpoint-refresh` | G1 只写 missing；本案已有 active checkpoint，不能猜成 missing。 |
| D13 | verify worker `INCOMPLETE` 后转 independent review | `ticket.verify.worker-incomplete-first` | 现有 C10/C11 错把 worker outcome 绑定到 implement 环节。 |
| D14 | 获授权后切换 dev verification environment | `attempt.verify.environment-authorized` | 环境授权与 profile 切换不在表内。 |
| D17 | build fix 后等待 closure review 结果 | `finding.review.closure-awaiting` | 没有成功返回的 post-fix closure reviewer 结果。 |
| D19 | 写 T3 finding-closure judgment | `ticket.record.judgment-written` | 与 D09 同一 record 缺口，不能当作 satisfy。 |
| D20 | 更新 checkpoint 继续 T3 | `attempt.record.checkpoint-refresh` | 与 D10 同一 checkpoint refresh 缺口。 |
| D22 | commit fix 与追踪记录 | `attempt.record.change-committed` | 表没有 Git landing/commit 环节；这是可能的范围外事件，不应虚构 Gate 命中。 |

## 6. 跳步检测

| 检测项 | 次数 | seq 定位 | 结论 |
| --- | ---: | --- | --- |
| 没有任何调查载体就直接进入实现 | 1 次观察到的 direct-implement dispatch | seq 87、89 | 行为确实是从 T2 ready 直接进入 implement；但 C1 的 `has_investigate=false/evidence.count=0` 未完整显示，因此条件状态仍是 `insufficient-evidence`。 |
| worker 返回后未记 evidence 就推进 | 2 | T2：seq 180 → commit/review seq 201、208 → evidence add seq 492；T3：seq 744 → review/fix/browser/commit seq 757、984、1211，未出现实际 evidence add | T2 明确先推进后入账；T3 更明显，只有 judgment/checkpoint 引用 evidence artifact，没有看到 `evidence add` 状态动作。 |
| 未经独立 review 就宣称完成或 satisfy | 0 次完整 Ticket 级命中 | T2 review 在 seq 214–220、closure 在 seq 347 之后，satisfy 在 seq 500；T3 从未 satisfy，最终仍 PENDING | 严格口径不能记 1 次。另有 1 次 sub-finding 级 near-miss：post-fix closure reviewer 在 seq 1155 超时后，seq 1160/1171 仍记录 finding closure，但没有成功的独立 closure review 结果。 |
| 已 SATISFIED Ticket 被新证据触及时是否处置 | 0 | T2 satisfy seq 500；之后的 OpenCV finding归属于 T3，不见 `evidence invalidate`、`needs-revalidation`、retire 或 successor | 没有证据证明 T2 的 required claim 被新证据触及；不能把同 Package 的后续修复算作 T2 rework。 |

补充：seq 937 的自然语言说“记录 T3 blocked”，但时间线中没有执行 `ticket block`；最终状态仍是 T3 `PENDING`、Gate `open`。只出现 `ticket block --help` 和 Gate 帮助查询，不能算状态转换。

## 7. 表本身的问题

1. **缺少“单一 ready Ticket 正常开工”**：表只有 `multiple-ready-tickets` 和“所有 implementation edges 被挡”，D01 后的 T2 是 ready 且没有选择歧义；正常选择落不到 readiness 行。
2. **worker outcome 与环节没有绑定**：D13 的 verify worker `INCOMPLETE` 会机械撞到 `ticket.implement.worker-incomplete-first`，且优先级还可能被 C9 抢占；应至少把 worker mode 纳入判据，或补 `ticket.verify.worker-incomplete-first`，否则默认动作可能错误地回 implement。
3. **fix 后的 finding closure review 没有处境行**：E1 能说“修复后由同 scope reviewer 重审”，但不能表示“正在等待这次重审”或“重审结果缺失”。D05、D17 都落在这个空档；E2 的 source-recheck 不能替代它。
4. **record 只覆盖 evidence，不覆盖 judgment 与 checkpoint refresh**：本案两次显式 judgment、两次 active checkpoint 更新都是真实主控决定；`evidence-unfiled`、`checkpoint-missing` 不能准确表达“结论/检查点已存在但需要刷新或确认”。
5. **Gate 没有“保持 open 等待 pending Ticket”动作**：F6 只列 pass/blocked/fail/defer；本案明确不能关闭且最终保持 open。若 `defer` 是该状态的规范表达，应在 timeline 中执行并记录 reason；若不是，应补 `attempt.gate.pending-open`。
6. **reviewer-returned finding 的 direct-fix 边界含糊**：E1 要求 fresh fixer，但用户授权后主控直接修复 reviewer 已指出的 implementation defect。现有 `finding.fix.main-session-discovered` 又只适用于主控自己发现的 finding；两行边界和 escape 责任不清。
7. **projection stale 与 projection drift 不是同一问题**：D06 的旧 Runtime Acceptance block 使 CLI validate 失败，但 A2 的定义专门排除了仅凭列出来源判定 progress/state drift；这是版本/投影合同冲突，不应直接把 A2 basis 升为 observed。

## 8. 版本干扰

- session 1 先尝试读取 `impl-package` 缓存 `0.2.9`，随后定位到 `0.3.0`；session 2 也重复出现旧路径与当前路径切换。相关 seq 包括 23–29、317–331、584–598、1123–1144。路径错误、帮助命令失败和重定位本身不应映射为流程处境。
- seq 429 的 `retired Runtime Acceptance projection` 校验失败随后在 seq 443 被删除，主控明确按 3.5 current-state 规则处理。这更像旧版 artifact 与新版 validator 的干扰，不足以证明 `package.record.projection-drift` 覆盖真实场景。
- initial review、closure review 使用了不同的 reviewer/tool 路径；部分结果文件为空、等待超时，后续还有手工 ledger 写入。对 D17/D18，只能说“没有在 timeline 中看到成功的 post-fix closure result”，不能进一步猜测 reviewer 实际未执行了所有检查。
- seq 770–782 的环境边界发生了真实授权变化：最初 DB/Auth/API/provider 被排除，用户随后明确授权 `dev`。后续 `start-env dev` 不应被判作越权；它是 owner 授权后的验证动作。
- 最终只保持 Gate open，没有实际 `gate pass/blocked/fail/defer`。不要把帮助查询或自然语言“blocked”升级成 `attempt.gate.verdict-undecided` 之外的具体 verdict。

## 9. 最值得注意的三个发现

1. **表对“verify worker INCOMPLETE”会给出错误方向**：这是最直接的可执行性问题，当前优先级可能把它吸到 verify/implement 行，却没有“转独立 review”的合法落点。
2. **真实流程最明显的跳步是 evidence 入账滞后**：T2 在 review/commit 后才 `evidence add`，T3 的 verify 返回后直到结束也没有看到实际 evidence add；这不是单纯命名问题，而是表的 prose 规则在真实流程中没有被强制。
3. **“finding 已闭环”与“Ticket/Package 已关闭”被成功区分，但 closure review 证据链仍不完整**：主控没有把 T3 误写成 satisfied，保留了 T3 pending/Gate open；同时 post-fix reviewer 超时后仍写了 finding judgment，这使 finding-level closure 的独立审查覆盖需要单独建模。
