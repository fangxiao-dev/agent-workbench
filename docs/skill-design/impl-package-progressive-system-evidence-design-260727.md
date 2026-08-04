# Impl-Package 渐进式系统证据与系统测试方法论设计

- 日期：2026-07-27
- 适用范围：`skills/impl-package/` 中与计划、实施执行、跨 Task 集成、系统验证和 completion claim 相关的 SKILL
- 文档性质：已收敛的方法论设计，供后续 SKILL / reference / eval 改造使用
- 当前阶段：SKILL、shared reference 与 eval 已 apply；本地契约验证已通过，后续由实际 implementation package 运行检验启发式的裁量质量
- 核心主张：先排除不忠实的证据边界，再选择**总证据成本最低**的忠实边界；成本接近时优先更早反馈，昂贵 E2E 只承担更低成本证据无法忠实覆盖的剩余风险

## 1. 背景与问题定义

复杂业务链路在真实 E2E 中通常不会一次性暴露全部问题。更常见的情况是：修复当前 blocker 后重新运行完整业务动作，下一处内部协作缺口才显现。反复出现的缺口可能包括：

- 同一数据在不同模块或不同 consumer 中采用了不一致的表示或解释；
- producer 与 consumer 在版本演进后没有继续共享同一兼容语义；
- scope、lineage、authority 或权威状态在跨层传递时没有完整绑定；
- 人工决策从 UI、DTO、service、confirm 到权威快照的传递过程中被静默丢失；
- 局部 validator、模块测试或单个 Task 都通过，但完整业务动作仍因组装顺序、状态提交或副作用边界失败；
- 最终错误码只能说明业务动作失败，不能说明哪个系统假设最先失效。

这些失败并不必然来自浏览器、外部 provider、native tool 或真实环境。真实 E2E 只是最先把它们组合在一起的观察位置。若流程默认采用“修一个 blocker → 再跑一次完整 E2E”，会产生以下成本和风险：

- E2E 被用作内部 seam 的首个发现工具；
- browser、provider、native tool 和人工运行被重复消耗；
- 每个新 blocker 都形成一次局部修复、审查、环境准备和完整重跑的长循环；
- agent 容易为了快速让 E2E 通过而引入 fixture 特判、测试专用生产分支或过宽抽象；
- 测试结果只累积“通过/失败”，没有累积对系统假设的可复用理解；
- 偶发环境问题可能被错误地下沉成脆弱的代码测试。

需要解决的不是“测试数量不足”，而是以下系统性问题：

1. 哪个边界拥有信息，哪个边界承诺保真，哪个 consumer 有权解释它，并不总是清楚。
2. Planned Verification 容易列出检查，却不一定解释每项检查正在证明什么系统风险。
3. 真实 E2E 的独有责任与内部前置假设没有明确分开。
4. 失败后的工作流偏向立即修复和重跑，缺少把失败转化为更便宜未来证据的学习步骤。
5. 缺少能够解释业务假设的 checkpoint，导致定位只能依赖最终错误或临时日志。

本设计不以新增测试类型、强制矩阵或新 gate 解决这些问题，而是提供一套可执行但可裁量的决策方法。

## 2. 设计目标

本方法论应使 Impl-Package 的计划与执行 agent 能够：

1. 围绕系统风险、信息损失、边界转换、权威状态与副作用选择证据，而不是机械按 unit / integration / E2E 分层。
2. 判断一个失败应在更早边界建立证据，还是只能由真实环境忠实证明。
3. 在不替代真实 E2E 的前提下，减少用昂贵 E2E 反复发现确定性内部 seam 缺口。
4. 将适合下沉的 E2E 失败转化为更便宜、稳定、直接的回归证据。
5. 将不适合下沉的外部或环境问题保留为 readiness、运行手册或 observability 改进，而不是强造代码测试。
6. 通过业务 checkpoint 指出“最后一个成立的系统假设”和“第一个失效的系统假设”。
7. 在复用已有能力、添加窄边界能力、修正业务 ownership 与抽取公共平台之间做出克制判断。
8. 区分领域事实、系统不变量、实现细节与 fixture 常量，防止案例常量污染通用设计。
9. 保持现有 Impl-Package 的 authority、revision、Execution Record 和 completion claim 语义，不创建第二套验证状态源。

## 3. 非目标

本设计明确不做以下事情：

- 不把真实 E2E、真实 browser、外部 provider 或 native tool 验收降格为 mock、unit 或本地 integration 通过。
- 不要求所有改动建立 unit、integration、system、E2E 四层测试。
- 不创建固定测试金字塔、覆盖率配额、case ID 体系、invariant registry 或全量风险矩阵。
- 不为每个业务动作新增独立 artifact、审批点、runtime status 或 sidecar 字段。
- 不把某个具体业务案例的字段名、hash 算法、DTO 形状、scope 类型或 confirm 流程写成通用合同。
- 不把“发生过失败”自动等同于“必须增加测试”。
- 不要求执行前穷举全部 consumer、全部 seam 或全部潜在故障。
- 不要求每次内部 bug 都运行 seam sweep。
- 不把 completion claim audit 变成追溯性清偿整个仓库历史技术债的 gate。
- 不为未来可能出现的复用需求提前建立测试平台、通用透传层或任意字段框架。

## 4. 与现有 Impl-Package 体系的关系

现有体系已经提供了可承接本方法论的表面，无需新增 stage：

- `impl-planning` 的 Planned Verification 已要求把 Acceptance Semantics 映射到检查、预期结果和 evidence owner；对 material 高风险边界，还要求场景、测试层级或入口及 observable oracle。
- `dev-with-track` 已拥有实施执行、Working Branch 集成、共享验证、Execution Record 和 execution findings 分流。
- `dispatch-bounded-task` 已明确 Task 局部证据不等于 Ticket acceptance，Working Branch owner 负责跨 Task seam 和共享验证。
- `verification-before-completion` 已采用 claim-to-evidence contract，并允许复用同 revision、同 environment 的新鲜证据，只补跑受影响检查。
- `execution-preflight` 已区分启动前置与正式验证，不需要扩展成 E2E admission gate。

因此建议的结构是：

```text
共享指导性 reference
  ├─ impl-planning：选择风险、证据边界、E2E 独有责任与 checkpoint
  ├─ dev-with-track：渐进式执行、失败学习、有限 seam sweep 与重跑决策
  ├─ dispatch-bounded-task：Task 局部证据与跨 Task seam 的责任边界
  └─ verification-before-completion：审计当前 claim 相关证据，不重新设计验证体系
```

共享 reference 建议命名为：

`skills/impl-package/references/progressive-system-evidence.md`

它是指导性方法论，不是新的 artifact lifecycle、状态 schema 或 gate contract。`impl-package/SKILL.md` 只增加指针，不复制正文。

## 5. 核心术语

### 5.1 系统假设（system assumption）

为了使一个业务动作成立，多个组件、边界或执行环境共同依赖的可证伪判断。例如：

- 某个信息跨边界后仍保持相同业务含义；
- producer 和 consumer 对版本、标识或权威状态采用兼容解释；
- 人工确认的结果能够抵达最终权威提交点；
- 副作用只会在授权和权威状态满足时发生；
- 真实运行环境会按约定执行已验证的内部合同。

系统假设不是新的 spec artifact。稳定、规范性的系统假设若影响外部行为或 Acceptance Semantics，仍由 spec 拥有；实施期只选择如何取得证据。

### 5.2 忠实边界（faithful boundary）

仍然保留当前风险关键因果机制的最小可执行边界。它不等于最小函数、最低测试层或最多 mock 的环境。

如果缩小范围时移除了真实 consumer、版本解释、序列化转换、权威状态切换或关键副作用顺序，那么得到的边界虽然更小，却不再忠实。

可用“反例保留”检查忠实性：缩小执行边界后，已知失败的最小反例或同类错误实现是否仍然可到达，并会被 oracle 稳定区分？若替换真实 consumer、转换、authority 切换或副作用顺序后，错误实现已经不可能出现，该边界就不能证明原风险。

### 5.3 最早忠实边界（earliest faithful boundary）

沿业务动作从局部逻辑向真实环境扩展时，第一个能够保留关键因果机制、控制必要输入并提供稳定 oracle 的边界。

“最早”表示尽可能早获得反馈；“忠实”限制了为了便宜而降格语义。但最早不是不计建设与维护成本的绝对结构排序：先排除不忠实的候选边界，再在忠实候选中选择总证据成本最低者；总成本接近时优先反馈更早者。

总证据成本包括：能力建设、单次运行、长期维护、失败诊断、环境稳定性、未来复用概率和 false-confidence 风险。已有可靠组装 runner 可能比新建更低层 harness 的总成本更低，此时选择组装边界不违背本原则。

### 5.4 Material seam

可能使当前 Acceptance Semantics 在局部证据绿色时仍然 false PASS 的信息、authority、兼容或副作用边界。普通 DTO、模块调用或技术分层不因存在本身成为 material seam；只有其失效能够掩盖当前业务错误时才触发本方法论的额外判断。

### 5.5 证据阶梯（evidence ladder）

从局部语义、seam/契约、组装业务动作到真实 E2E 的一组可选证据边界。它是对 completion claim 进行风险分解的决策语言，不是固定执行流水线：较早证据证明内部确定性合同，昂贵 E2E 证明真实环境剩余风险，两者可组合支持最终 claim。一个变更可以只需要其中一层，也可以需要多层；不要求逐层跑满，也不创建 evidence graph artifact。

### 5.6 昂贵验证（expensive verification）

需要真实 browser、外部 provider、native tool、共享环境、真实认证、人工操作、长时间运行或高准备成本的验证。昂贵不只指金钱，也包括时间、环境稀缺性、外部配额和失败定位成本。

### 5.7 业务 checkpoint

位于业务动作关键边界、能够表达系统假设是否成立的可观察证据。它可以由现有测试 probe、结构化日志、状态查询、业务事件或受控 assertion 提供，不要求形成统一框架。

## 6. 第一原则：选择最早忠实边界，而不是最低测试层

判断某个失败是否应在更早边界被发现时，使用以下四问：

1. **语义保真**：导致失败的语义机制，在更小范围内是否仍真实存在？
2. **可控复现**：必要输入、版本、状态、consumer 组合和执行顺序是否能够受控建立？
3. **直接 oracle**：该边界能否直接区分正确实现与错误实现，而不是只观察相邻信号？
4. **真实环境独有性**：移除真实 browser、provider、native tool、网络或部署环境后，是否会丢失导致失败的关键因果机制？

典型判断：

- 前三项为“是”，第四项为“否”：通常在该更早边界建立证据。
- 第四项为“是”：保留真实 E2E 或真实集成作为权威证据。
- 目前无法回答：先补最小 observability 或进行一次有目的的探索运行，不凭测试层名称猜测。

这里的关键限制是：**更便宜的证据必须证明同一个风险。**

候选边界的最终选择顺序是：

1. 用四问和反例保留排除不忠实边界；
2. 比较剩余候选的总证据成本；
3. 成本接近时选择反馈更早的边界；
4. 真实环境独有风险仍由真实验证证明。

以下做法不构成忠实下沉：

- 跳过实际发生错误解释的 consumer，只测试 producer 输出；
- 把真实序列化路径替换为手工构造的理想对象；
- 用 mock provider 返回调用方希望看到的结果，从而绕过真实协议或错误语义；
- 只验证字段存在，不验证字段的业务含义、authority 或版本解释；
- 在测试中直接建立最终状态，跳过导致失败的中间状态转换。

## 7. 第二原则：证据围绕风险与信息边界组织

验证层级不应由代码目录或测试框架名称机械决定。更有用的选择信号是：

- 信息是否发生 encode/decode、映射、裁剪、默认值填充或兼容投影；
- 权威 owner 是否发生变化；
- producer 与 consumer 是否可能处于不同版本；
- 同一业务事实是否被多个 consumer 独立解释；
- 人工决定是否经过多个表示层才能进入权威状态；
- 副作用是否跨事务、进程、网络或外部工具边界；
- 局部绿色是否可能掩盖完整业务动作中的提交顺序、补偿或重试问题；
- 风险是否只在真实运行环境中存在。

`material seam` 的最小判据是：该边界失效是否可能让当前 Acceptance Semantics 在局部证据全部绿色时仍然 false PASS。若不能，不因它是 DTO、adapter 或跨模块调用就自动启用额外流程。

### 7.1 证据阶梯

| 证据边界 | 主要证明内容 | 典型风险 | 不应冒充的内容 |
| --- | --- | --- | --- |
| 局部语义 | 计算、状态转换、领域规则本身 | 边界值、状态迁移、纯规则错误 | 跨模块保真、真实副作用、完整业务动作 |
| Seam / 契约 | 表示转换、字段保真、版本兼容、producer/consumer 共识 | DTO、序列化、快照、人工决定传递、兼容投影 | 真实 browser/provider/native tool 行为 |
| 组装业务动作 | 多模块协作、状态推进、事务与副作用顺序 | 模块局部通过但完整 action 失败、补偿或 commit 边界错误 | 真实部署、真实外部协议或人工体验 |
| 真实 E2E | 真实环境、真实协议、真实工具和人工交互的独有风险 | 浏览器运行时、认证、网络、provider 行为、native 生命周期、部署打包 | 对内部 seam 缺证据的无限兜底 |

选择规则：

> 找到能够忠实证明当前系统假设的最便宜证据；只有该边界无法忠实覆盖的剩余风险才交给更昂贵边界。

证据阶梯不是 mandatory sequence。低风险、单 owner、局部可逆且不存在 material seam 的修改，可以直接使用已有定向证据，不需要填写阶梯或证明为什么没跑其他层。

### 7.2 证据组合与关键因果输入 freshness

支持最终 claim 的证据可以来自多个忠实边界：内部证据证明确定性合同，真实 E2E 证明环境独有剩余风险。复用这些证据时，不只比较代码 revision 和环境名称，还要判断会影响当前风险的关键因果输入是否变化，例如外部协议版本、feature flag、schema、部署配置、共享数据前置或认证策略。

- 相关因果输入变化：只使依赖该输入的证据 stale，补跑受影响部分。
- 无关配置或环境变化：不使已有证据机械失效。
- 无法判断变化是否相关：先检查当前 claim 的因果依赖，不创建 freshness registry 或全局输入清单。

freshness 是 claim-scoped 判断，不是新的状态系统。

## 8. 昂贵 E2E 的独有风险声明

当 attempt 计划真实 E2E、真实 provider、browser 或 native tool 验证时，Planned Verification 应能用简短文字回答：

1. 该验证独有地证明什么风险？
2. 哪些已知的确定性内部前置假设应优先由更便宜证据支持？
3. 运行前哪些 checkpoint 或 readiness 信号足以说明本次消耗有意义？
4. 若失败，如何初步区分内部 seam、真实环境行为、外部波动和观察缺口？

这项声明的作用是限定 E2E 的责任，不是新增 approval、artifact 或强制模板。一两句话、现有 Planned Verification 表中的一行或稳定 policy 引用都可以满足要求。

### 8.1 默认启发式，不是 E2E admission gate

必须明确避免将上述原则实现成硬门禁。建议 SKILL 使用以下规范性措辞：

> 已知的确定性内部前置假设缺少可用证据时，默认先建立更便宜的忠实证据，不反复消耗昂贵 E2E。若当前风险本身依赖真实环境、需要探索性诊断、尚无足够信息判断忠实边界，或真实运行是获得关键证据的合理方式，允许带明确目的进行有界探索。该运行产生观察证据，不自动证明所有内部前置已经成立。

这里要求的是有界探索尝试，不是体系规定的固定次数。每次探索运行前应写清：

- 待区分的候选假设；
- 能改变下一步判断的决定性 checkpoint 或 artifact；
- 不同观察结果分别路由到内部修复、组装验证、环境处理还是继续真实验证；
- 本次运行相对上次新增的假设、环境 delta、观测能力或修复 delta。

若需要再次探索，不要求申请新 gate，但必须存在上述信息增量。没有新的假设、delta 或决定性观察目标时停止重复运行；限制的是无信息增益的重跑，不是预设运行次数。

允许先进行有界真实 E2E 探索的典型情况：

- 只有真实 browser/provider/native tool 能暴露当前怀疑的机制；
- 目前不知道失败属于内部 seam 还是环境独有行为，需要一次探索性运行缩小范围；
- 现有观测不足，真实运行能够生成决定下一步所需的 checkpoint 或外部 artifact；
- 真实环境状态稀缺或短暂，此刻运行比先建设完整内部 harness 更合理；
- 当前目标就是验证环境 readiness、部署或外部兼容，而不是宣称内部逻辑已经完备。

最短判定锚点：

- **明显应先补便宜证据**：已知某个确定性映射错误可在真实转换与 consumer 之间复现，下一次 E2E 只会再次得到相同最终错误。
- **明显允许探索运行**：尚不能判断问题属于内部 adapter 还是真实协议，sandbox 运行能够产生区分两者的原始 response 和边界 checkpoint。

不应继续消耗昂贵 E2E 的信号：

- 已经确认是确定性的内部表示、映射、版本解释或权威状态问题；
- 当前修复尚未在保留关键因果机制的更小边界得到任何证据；
- E2E 失败只能返回同一个最终错误，且没有新增诊断价值；
- 下一次运行只是为了“看看还有没有别的问题”，没有明确风险或观察目标。

## 9. 可观察业务 checkpoint

### 9.1 设计目标

checkpoint 应解释业务假设，而不是只打印函数名、调用栈、原始 payload 或最终错误码。一次失败后，理想状态是能够回答：

- 最后一个成立的业务假设是什么？
- 第一个失效的业务假设是什么？
- 该假设由哪个边界或 owner 负责？
- 失败发生在信息传递、解释、权威切换还是副作用阶段？

### 9.2 可选信息

根据当前风险选择最少信息；不要求统一 schema：

- 业务对象、revision、correlation 或 operation identity；
- 当前边界接受的语义输入摘要；
- 当前边界做出的业务决定或拒绝理由；
- 输出的语义摘要，而不是完整敏感 payload；
- 当前 authority、owner 或权威状态来源；
- 兼容版本、consumer 解释或投影来源；
- 副作用阶段：planned、committed、confirmed、failed、compensated；
- 当前验证的关键不变量及其成立/失效结果。

checkpoint 的证明力取决于 authority 与 provenance。用于证明权威状态切换、提交成功或副作用确认的 checkpoint，应直接观察权威源，或能够机械说明其数据来自哪个权威源、revision 和环境。派生投影、cache、日志副本或 UI 显示可以作为定位信号，但不能单独证明权威状态已经成立。

### 9.3 载体选择

优先复用已有能力：

- 已有 integration test probe；
- 结构化业务日志；
- 当前状态查询或只读 inspector；
- 领域事件或审计记录；
- 测试环境中的窄 assertion；
- 外部 artifact、截图、response 或 native tool 输出。

不要为了统一 checkpoint 而建立新的全局事件平台、第二套状态库或所有模块必须接入的 tracing schema。

### 9.4 停止条件

当当前失败能够稳定指出“最后成立的系统假设”和“首个失效的系统假设”时，停止增加观测点。更多日志若不能改变定位或决策，只会增加噪音与敏感数据风险。

### 9.5 反例

- 为调试永久记录完整敏感 payload 或 secret；
- 每层重复输出同一对象，没有表达边界转换或 authority；
- checkpoint 自己维护一份可变业务状态，成为第二事实源；
- 为了日志格式统一而抽象新的业务模型；
- 只有“进入函数/离开函数”，不能说明系统假设是否成立。

## 10. 轻量执行流程

以下流程仅在存在跨模块业务链、material seam、昂贵验证或已发生系统性失败时启用。普通低风险局部修改继续走现有轻量路径。

### Step 1：声明当前要证明的系统假设

不要只写“运行 E2E”或“补 integration test”。用一句话说明当前证据目标，例如：

- 信息经过某个边界后仍保持相同业务含义；
- 不同版本 consumer 对同一权威事实采用兼容解释；
- 人工决定能够抵达最终权威提交点；
- 外部副作用只在权威状态和授权成立后发生；
- 真实环境能够执行已经由内部证据支持的业务合同。

稳定、规范性的系统假设需要新增或改变行为合同时，按现有 authority 路由回 `req-align`；若现有 Acceptance Semantics、repository authority 和稳定合同已经能够唯一推出正确行为，只是实现违反合同或表述不够显眼，则分别按 implementation defect 或表达缺口处理，不因 spec 没有逐字重述而机械升级 D/S。执行者不能把真正的新行为合同藏进测试计划。

### Step 2：识别当前业务动作的 material 信息边界

只查看当前业务动作实际经过的边界，优先关注：

- encode/decode、DTO、序列化与反序列化；
- projection、compatibility adapter、schema/version consumer；
- UI、API、service、storage 之间的语义映射；
- 人工决定、默认值、缺省值和拒绝信息传递；
- 权威状态、派生状态、缓存与快照之间的切换；
- 外部副作用前后的 commit、confirm、compensation 或 recovery。

不要求在实施前列出全仓库所有 consumer。没有 material seam 信号时，不做额外盘点。

### Step 3：选择最早忠实边界和 oracle

使用“四问”确认：

- 关键因果机制是否仍在；
- 必要输入与状态是否可控；
- oracle 是否直接且稳定；
- 是否丢失真实环境独有机制。

优先复用现有 test entry、业务 action runner、真实序列化路径、受控 sandbox 或状态 inspector。只有现有能力无法表达当前风险时才补窄能力。

### Step 4：建立足够的渐进证据

根据风险选择所需证据，不要求跑满阶梯：

```text
局部语义（若风险在此）
→ seam / 契约（若存在信息转换或 consumer 分歧）
→ 组装业务动作（若存在跨模块状态或副作用风险）
→ 真实 E2E（验证真实环境独有风险）
```

已知的确定性内部前置假设缺证据时，默认先补便宜证据；但按 §8.1 允许带明确目的进行有界探索性或环境独有运行。

### Step 5：运行昂贵验证并记录独有结论

真实 E2E 的结果应说明：

- 哪个真实环境风险已经被证明或否定；
- 哪些内部假设来自已复用的早期证据；
- 哪个 checkpoint 首先异常；
- 失败是否提供了新的系统假设或只反映外部波动。

Execution Record 继续作为实际证据记录面；不新建 evidence ledger。

### Step 6：失败后进入条件化学习闭环

不要默认立即重跑完整 E2E。先按第 11 节判断失败是否适合下沉、是否需要有限 seam sweep，以及下一次运行能新增什么证据。

## 11. 失败后的条件化学习闭环

### 11.1 保存原始事实

先记录：

- 当前 D/S/P revision、worktree 和相关 environment；
- 业务动作与真实入口；
- 最后成功 checkpoint 与首个异常 checkpoint；
- 外部响应、截图、native 输出或决定性 artifact；
- 是否可以重复、是否涉及共享或易变环境。

先保存事实，不急于把一次现象提升为系统不变量。

### 11.2 分类失败

使用以下启发式分类，不要求写入新字段。分类是当前证据支持的工作假设，不是一次性最终归因；新 checkpoint 或真实环境证据出现后允许重新分类。同一 failure 也可能同时包含多个原因，例如真实 provider 协议变化同时暴露内部 adapter 的兼容缺陷，此时分别保留内部回归证据与真实环境证据：

| 分类 | 特征 | 默认动作 |
| --- | --- | --- |
| 确定性内部假设失效 | 相同输入/状态可重复；表示、映射、兼容、authority 或顺序错误 | 寻找最早忠实边界，修复 owner，条件满足时建立回归证据 |
| 系统组装失效 | 模块局部正确，完整 action 的事务、状态推进或副作用顺序失败 | 建立组装级证据和 checkpoint，检查 seam ownership |
| 真实环境独有失效 | 依赖真实浏览器、认证、协议、provider、native 生命周期或部署 | 保留真实验证为权威证据，按需补诊断而非伪造 lower-level 替代 |
| 环境/外部偶发问题 | 网络、临时不可用、配额、共享资源或外部服务波动 | 改善 readiness、重试判断、运行手册或 observability；仅当合同要求时增加代码行为证据 |
| 观察缺口 | 只有最终错误，无法可靠判断上述类别 | 先补最小 checkpoint 或进行有目的探索运行 |

### 11.3 失败下沉的必要条件

“E2E 失败必须下沉”不是规则。只有同时满足以下条件，才将失败转化为更便宜的未来回归证据：

1. **可稳定复现或受控触发**：能够可靠建立导致失败的必要条件。
2. **保留关键因果机制**：缩小边界后，真正导致失败的 consumer、转换、authority 或状态顺序仍存在。
3. **存在更便宜稳定 oracle**：新证据能直接区分正确与错误，并显著降低运行或诊断成本。
4. **不会引入 production 特判**：不依赖 fixture ID、测试 provider 名称、固定样本值或绕过真实业务逻辑。
5. **与当前风险相关**：证据保护的是已确认的系统假设，而不是因为遇到失败就顺手扩展测试平台。

任一条件不满足时，不强造测试。根据实际情况保留为：

- environment readiness 检查；
- 运行手册或故障排查步骤；
- 外部依赖健康度或诊断改进；
- 结构化 checkpoint；
- 当前 Execution Record 中的 residual risk；
- 需要真实环境再次验证的开放证据。

### 11.4 区分合同缺口并修复首个违约边界

执行期发现系统不变量缺失或 seam 行为不清时，先区分：

- **Implementation defect**：现有 Acceptance Semantics、repository authority 和稳定合同能够唯一推出正确行为，只是实现违反了它。复用当前 D/S，按缺陷修复和受影响证据路径继续；不要仅因 spec 没有逐字重述该实现后果就升级 revision。
- **Contract ambiguity**：现有 authority 无法在多个合理业务结果之间作出唯一裁决，或需要新增兼容、安全、数据、失败恢复或 mutation authority 选择。停止受影响单元并路由 `req-align`；测试、adapter 和执行者不能临时选择共享语义。
- **表达或可发现性缺口**：正确行为可由现有权威唯一推出，但合同表述不够显眼。可以先按缺陷修复；再按现有 editorial / durable knowledge 规则判断是否需要零语义回填，不自动把它升级为新产品决策。

发现静默信息丢失、consumer 分歧或权威状态错误时，优先问：

- 哪一层拥有该信息的业务含义？
- 哪个边界承诺保真？
- 哪个 consumer 有权解释或拒绝它？
- 是否存在隐式默认值、宽松兼容或 `null`/缺省退化？
- 调用方是否传递了应由权威源重新确认的事实？
- 当前 checkpoint 是否观察了权威状态，还是只观察了派生投影？

不要抽象寻找唯一的“真正 owner”。沿当前业务动作定位首个违反既有合同的边界：

1. producer 负责其已承诺输出的语义与保真；
2. consumer 负责按其已声明合同解释、验证或拒绝输入；
3. transport/platform 负责其已承诺的传输、顺序、持久性或兼容保证；
4. 首个违反现有合同的边界负责修复或显式拒绝；
5. 若无法从现有合同判断谁违约，则由 Acceptance Semantics owner 裁决，而不是由测试、adapter 或 Working Branch owner 发明共享语义。

仅增加测试但不修复首个违约边界、ownership、信息合同或可观测性，不构成完整学习闭环。

### 11.5 有限同类 seam sweep

seam sweep 不是每次内部 bug 的默认动作。只有出现以下信号时才触发：

- 版本兼容或 producer/consumer 演进问题；
- 序列化、反序列化、映射、projection 或 adapter 问题；
- 权威状态、派生状态、快照或 cache 的切换问题；
- 多个 consumer 对同一事实出现解释分歧；
- 信息在跨层传递中静默丢失、被默认值覆盖或被裁剪。

这里的“直接相邻”不是固定调用跳数。它指在当前业务动作中，直接读取、写入、转换同一受损表示，或依据同一权威事实作出决定的 producer/consumer；即使通过消息队列或事件总线连接，只要它参与当前 Acceptance Semantics，也可以是语义上的直接相邻。仅订阅同一事件、但不参与当前业务动作或当前 Acceptance Semantics 的系统不进入本次 sweep。

触发后也只执行有限检查：

- 范围限定在**当前业务动作的直接相邻 producer、consumer 和转换边界**；
- 优先检查与当前 failure 相同的语义机制，不扩展成全仓库兼容性审计；
- 使用现有 change map、调用链和 checkpoint 定位，不要求生成 consumer registry；
- 发现需要新的产品行为、兼容策略或 authority 选择时停止并路由 owner，而不是由执行者泛化。

建议把预算表达为范围预算而非固定分钟数：当前业务动作、共享同一受损表示或权威事实的直接相邻 consumer、同类机制。项目确有时间盒惯例时可以同时使用短时间盒，但体系不规定统一分钟数。

停止条件：

- 当前失败假设已有稳定证据；
- 直接相邻 material seam 没有发现同类未覆盖风险；
- 新发现开始偏离当前业务动作；
- 继续检查需要新的产品决策或公共平台设计。

### 11.6 再建立证据并决定是否重跑

适合下沉的内部失败通常按以下顺序恢复信心：

```text
最小忠实回归证据
→ 受影响 seam / 组装证据
→ 必要共享验证
→ 一次有明确独有风险目标的真实 E2E
```

不适合下沉的环境或外部问题，则根据其性质执行 readiness、诊断、恢复或再次真实运行，不伪造 lower-level 绿色结果。

下一次昂贵运行前应能回答：“这次运行会证明什么新东西？”如果答案仍只是重复获得同一最终错误，应先改善诊断或完成已知内部修复。

### 11.7 运行期诊断细化与 Plan Revision 边界

失败后的候选假设、控制变量、决定性 checkpoint、重跑理由和结果分流，并不自动构成 Planned Verification 策略变化：

- 在已批准的风险、claim 和验证策略内，诊断细化、控制变量选择及有信息增量的重跑理由只 append 到 Execution Record，由 `dev-with-track` 决定和执行，不升级 P revision。
- 只有改变 completion claim、验证策略、required evidence、覆盖范围或外部 mutation authority 时，才回 `impl-planning` 判断并按现有规则升级 P revision。
- 运行期诊断记录是实际 evidence/provenance，不能在 ER 或 `execution-findings.md` 中形成第二份 Planned Verification 合同。
- 诊断过程中暴露的新行为选择仍按 §11.4 区分 implementation defect 与 contract ambiguity，不能借“运行期细化”绕过 authority。

## 12. 领域事实、系统不变量、实现细节与 fixture 常量

### 12.1 分类方法

| 分类 | 判断问题 | 权威落点 | 验证含义 |
| --- | --- | --- | --- |
| 领域事实 | 换一种实现，业务或用户仍必须知道并依赖它吗？ | Decision / Spec | 按 Acceptance Semantics 选择证据 |
| 系统不变量 | 跨模块、版本、状态或执行环境变化时仍必须成立吗？ | Spec + Planned Verification | 在最早忠实边界证明，并保留必要真实验证 |
| 实现细节 | 重构后可以变化而不影响外部行为吗？ | 代码与局部设计 | 可有局部测试，不上升为通用系统合同 |
| Fixture 常量 | 换成语义等价的样本值，行为是否应保持不变？ | 测试数据 | 不进入生产分支、通用框架或稳定不变量 |

### 12.2 反事实检查

面对字段名、ID、hash、时间、样本内容或特定 provider 返回值时，问：

> 如果把它替换为另一个语义等价值，预期业务行为是否仍应相同？

- 若“是”，它通常是 fixture 常量或实现细节，不应进入通用框架约束。
- 若“否”，继续说明差异来自领域事实、系统不变量还是外部合同；只有能够说清 owner 和业务后果时才提升为稳定合同。

### 12.3 防止错误抽象

以下信号表示正在过拟合：

- production 逻辑识别 fixture ID、测试账号、测试 provider 或固定样本内容；
- 为了保留一个案例中的未知字段而建立“任意字段透传”框架，但没有语义 owner；
- 测试直接断言 incidental hash、顺序或序列化文本，而真正合同只关心业务等价性；
- 将一个 consumer 的实现偏好提升为所有 consumer 的平台规则；
- 抽象后的配置、adapter 或 hook 比原始业务路径更难解释。

## 13. 复用、窄能力、业务修正与平台化

建议按以下顺序决策：

### 13.1 复用已有能力

适用条件：

- 已有 test entry、runner、probe、sandbox 或 inspector 保留关键因果机制；
- 能够观察真正的 authority 和 oracle；
- 不需要改变 production 行为来迎合测试。

推荐动作：直接复用，并在 Planned Verification 或 ER 中说明它证明的系统假设。

### 13.2 添加窄边界能力

适用条件：

- 风险明确位于一个 seam；
- 现有能力无法观察该边界；
- 可以用小型 contract test、adapter probe、checkpoint 或组装 action 建立忠实证据。

推荐动作：只补当前边界所需的最小能力，不建立新平台。

### 13.3 修正业务 ownership 或信息边界

适用条件：

- 信息丢失来自 owner 不清；
- consumer 在解释不属于自己的语义；
- 调用方声明冒充权威事实；
- 多个投影都被当成权威状态；
- 测试只能观察结果，无法解释为何该层应保留或拒绝信息。

推荐动作：先修正合同、owner 或边界；测试只是证明修正，不替代设计。

### 13.4 抽取公共能力

只有以下信号同时成立时才考虑：

- 多个独立业务流反复出现同一稳定语义合同；
- 共性来自业务或系统不变量，而不是字段形状偶然相似；
- 抽取后能删除重复、缩短路径或减少 owner 分歧；
- 当前实现因缺少公共能力已经更复杂；
- 公共能力仍能清楚表达 authority、失败语义和停止边界。

停止或拒绝平台化的信号：

- 唯一理由是“以后可能用到”；
- 只有一个业务案例；
- 必须支持任意字段、任意 consumer 或任意 provider 才显得通用；
- 新抽象不能减少当前代码或认知负担；
- 抽象掩盖了不同业务流其实拥有不同 authority 或失败语义。

## 14. 各 SKILL 的职责落点

### 14.1 `impl-package/SKILL.md`

只增加方法论指针和路由说明：

- 复杂业务链、material seam 或昂贵系统验证需要选择渐进式证据时，读取共享 reference；
- 入口不复制方法论正文；
- 不把该方法论描述成新 stage 或 mandatory gate。

### 14.2 `impl-planning/SKILL.md`

在 Planned Verification 中增加以下决策责任：

- 对 material seam 或昂贵验证，说明要证明的系统假设；
- 先排除不忠实边界，再按总证据成本选择检查；成本接近时优先更早反馈，不按测试名称机械分层；
- 说明昂贵验证独有风险和必要 checkpoint；
- 明确这是裁量性选择，不要求每项 AC 建立完整证据阶梯；
- 未知风险允许安排有界探索性真实运行，不因前置证据不足自动阻断 E2E；重复运行必须具有新的假设、delta 或决定性观察目标；
- 不为此创建固定矩阵、case ID、第二份计划或新 approval。

Phase 2 写入 SKILL 时，每个“默认 + 例外”规则至少配一组最短判定锚点：一个明显应走默认路径的场景和一个明显满足例外的场景。锚点只用于校准判断，不写成字段、fixture 常量或穷举规则。

现有“高风险验证可执行性”规则应继续保留，但需要避免把它扩张成所有 E2E 的 admission gate。缺的是已知 material 内部假设时才默认前移证据；未知或环境独有风险仍可由真实运行探索。

### 14.3 `dev-with-track/SKILL.md`

这是主要执行 owner，应增加：

- 渐进式证据执行流程；
- 已知内部前置与真实 E2E 独有风险的区分；
- 探索性真实运行的允许条件；
- 探索运行的假设、决定性观察、结果分流和重复运行信息增量；
- 失败分类作为可修订、可多因的工作假设，以及忠实下沉条件与不下沉路径；
- implementation defect、contract ambiguity 与表达缺口的分流；
- 首个违约边界与 Acceptance Semantics owner 的收口规则；
- 五类 seam sweep 触发信号，以及按共享受损表示或权威事实定义的语义相邻范围预算；
- checkpoint 的 authority/provenance；派生投影只能定位，不能单独证明权威提交；
- 已批准策略内的诊断细化只 append ER；只有 claim、验证策略、required evidence、覆盖范围或 mutation authority 改变才回 `impl-planning`；
- 修复后先跑受影响便宜证据，再决定是否重新消耗昂贵验证；
- 证据继续 append 到 Execution Record，不新增运行时 artifact。

`execution-findings.md` 可以保存已确认的方法性发现或跨 Task seam 发现，但规范性行为仍按现有分流回 spec，实际证据仍进入 ER。

### 14.4 `dispatch-bounded-task/SKILL.md`

在 integration step 中补充责任边界：

- Task worker 可以提供其边界内的局部或 seam 证据；
- Task `DONE` 和局部绿色不能证明跨 Task 信息保真或完整业务动作；
- Working Branch owner 负责合并 checkpoint、处理已出现 seam，并选择共享或组装证据；
- 只有命中本设计的五类信号时才进行有限同类 seam sweep；不要求 worker 在派发前穷举全部 consumer。

### 14.5 `verification-before-completion/SKILL.md`

只审计当前 completion claim，不重新设计测试体系。建议检查：

- 当前 claim 所要求的真实 E2E、provider、browser 或 native tool evidence 没有被 lower-level evidence 冒充；
- evidence 与当前 revision、environment 和 claim 对齐；
- evidence 所依赖的关键因果输入仍然成立；除代码 revision 与 environment 外，还应按当前风险检查外部协议版本、feature flag、schema、部署配置、共享数据前置或认证策略是否发生相关变化；
- **与当前 claim 相关、已确认且 material 的确定性内部 failure**，是否已有稳定回归证据，或已有可信理由说明不适合下沉；
- 环境偶发问题是否被诚实记录，而不是转换成无关的绿色代码测试；
- 已有证据新鲜时继续复用，只补受当前 delta 影响的部分。

关键因果输入检查不创建 freshness registry。只有变化可能影响当前 claim 所证明的风险时才使对应 evidence stale；无关配置或环境变化不触发机械重跑。

这里必须明确非追溯性边界：

> completion claim audit 不要求清偿与当前 claim 无关的历史 failure、旧 package 技术债或未被当前改动触及的系统风险。只有当前范围内已经确认、material 且可能使 claim 产生 false PASS 的 failure 才进入本次审计。

### 14.6 `execution-preflight/SKILL.md`

原则上不需要新增 E2E admission 规则。它继续只负责：

- 当前高风险单元的最小启动前置；
- browser/provider/native tool/runner 是否可启动；
- credential presence、sandbox identity、临时资源和 cleanup owner；
- 不在 preflight 中正式运行业务 E2E。

若未来修改，只需引用“昂贵验证独有风险”帮助描述目的，不扩展其 authority。

## 15. 建议写入共享 reference 的决策表

| 触发信号 | 判断问题 | 推荐动作 | 反例 | 停止条件 |
| --- | --- | --- | --- | --- |
| Material seam 判断 | 该边界失效是否可能让当前 Acceptance Semantics 在局部绿色时仍 false PASS？ | 是则选择忠实 seam/组装证据；否则走普通轻量路径 | 因为存在 DTO 或跨模块调用就升级流程 | 当前边界对 false PASS 的影响已明确 |
| 数据跨表示边界 | 关键业务语义是否可能被裁剪、默认或重解释？ | 在真实转换与 consumer 之间建立 seam 证据 | 只测试理想对象字段存在 | 能直接观察转换前后业务等价性 |
| producer/consumer 版本演进 | 不同版本是否共享兼容解释？ | 选择覆盖真实兼容机制的 contract/integration 证据 | 为某个版本号写 fixture 特判 | 当前支持范围和拒绝语义均可观察 |
| 权威状态切换 | 哪个状态是 authority，何时切换？ | 添加状态/commit checkpoint 和组装证据 | 只断言最终投影存在 | 能指出切换前后 authority 与首个失效点 |
| 多 consumer 分歧 | 谁有权解释该事实？ | 修正 owner，覆盖直接相邻 consumer | 建立任意 consumer 框架 | 当前业务动作的相邻 consumer 解释一致 |
| 静默信息丢失 | 信息在哪一边界消失，是否应保真？ | 修复边界并在最早忠实位置建立回归证据 | production 识别 fixture 字段 | 丢失机制可稳定被 oracle 捕获 |
| 外部真实环境风险 | 移除真实环境是否丢失关键机制？ | 保留真实 E2E，补必要 readiness/observability | mock 通过冒充真实验收 | 真实环境独有 claim 已直接证明 |
| 探索性昂贵运行 | 本次运行将区分哪些假设，新增什么决定性观察？ | 进行有界探索，并按结果分流；重复运行要求新的假设、delta 或观察能力 | 以“探索”为由重复获得同一最终错误 | 结果足以选择下一忠实边界，或继续运行已无信息增益 |
| 偶发环境失败 | 是否可稳定复现，是否属于产品合同？ | readiness、runbook、诊断；合同要求时才测试重试/降级 | 为一次网络抖动写确定性业务测试 | 故障归属、恢复路径和 residual risk 清楚 |
| 普通局部可逆改动 | 是否存在 material seam 或昂贵验证？ | 继续现有轻量定向验证 | 强制填写证据矩阵 | 现有证据足以支持 scoped claim |

## 16. Guardrails：防止启发式演变为流程桎梏

以下内容应作为共享 reference 的显式护栏：

1. **无强制全阶梯**：不要求所有变更依次运行局部、seam、组装和 E2E。
2. **无 E2E 硬 admission**：已知确定性内部前置缺证据时默认先补便宜证据；环境独有、探索性诊断或证据不足时允许有界运行。重复探索必须带来新的假设、delta 或决定性观察，不设置固定运行次数。
3. **无全量 seam sweep**：只有版本兼容、序列化/映射、权威切换、跨 consumer 分歧或静默信息丢失信号才触发，并仅查看当前业务动作中共享同一受损表示或权威事实的直接相邻边界。
4. **无失败必下沉**：只有可稳定复现、保留关键因果机制且具有更便宜稳定 oracle 的失败才形成 lower-level 回归证据。
5. **不替代真实验收**：lower-level 证据只能证明对应内部风险，不能冒充 browser/provider/native tool 的真实行为。
6. **不追溯清债**：completion audit 只处理与当前 claim 相关且已确认的 material failure。
7. **无 artifact 膨胀**：不创建 evidence matrix、checkpoint registry、consumer registry、额外 runtime state 或新 gate。
8. **无 fixture 特判**：测试数据、账号、provider 名称或样本常量不得影响 production 行为。
9. **无提前平台化**：公共抽象必须由多个独立业务流的稳定共性和当前简化收益共同证明。
10. **尊重 authority**：现有权威能唯一推出正确行为时按 implementation defect 修复；只有多个合理业务结果无法由现有合同裁决时才回 `req-align`。verification selection 改变由 `impl-planning`；实际证据和失败学习由 `dev-with-track`；completion skill 不反向发明合同。
11. **保留局部路径**：单 owner、低风险、局部可逆且已有直接证据的改动，不因本方法论增加 plan revision、review、Ticket、DAG 或 owner checkpoint。
12. **证据充分即停止**：当前 claim 已有最便宜且充分的忠实证据时停止增加测试；更多证据必须能降低真实残余风险或定位不确定性。
13. **Checkpoint 不冒充 authority**：UI、cache、日志副本或派生投影只能作为定位信号；没有权威源或可机械追溯 provenance 时，不单独证明权威提交或副作用确认。
14. **失败分类不强制互斥**：分类是可修订的工作假设；真实环境变化与内部兼容缺陷可以同时成立，各自保留对应证据和分流。
15. **Freshness 不建 registry**：只检查影响当前 claim 的关键因果输入；相关变化只使对应 evidence stale，无关配置或环境变化不触发机械重跑。
16. **诊断细化不自动升级 P**：已批准策略内的假设细化、控制变量与重跑理由只 append ER；只有 claim、验证策略、required evidence、覆盖范围或 mutation authority 改变才回 `impl-planning`。

## 17. 推荐 eval 设计

eval 应同时验证正向选择与拒绝错误流程，不能只检查是否“增加了测试”。

### Eval 1：版本 consumer 解释不一致

输入：真实 E2E 发现两个 consumer 对同一版本化事实采用不同解释，问题可稳定复现。

期望：

- 识别为 material seam；
- 在保留真实 consumer 和兼容机制的最早边界建立契约或 integration 证据；
- 对当前业务动作中共享同一版本表示或权威事实的语义相邻 consumer 做有限 sweep；
- 仍保留真实 E2E 验证外部环境独有风险；
- 不建立全局 consumer registry 或通用版本平台。

### Eval 2：多层传递中的静默信息丢失

输入：人工决定通过多个表示层后在权威提交前丢失，局部字段校验均通过。

期望：

- 识别信息 ownership 和保真边界；
- 添加能够指出最后成立/首个失效假设的 checkpoint；
- checkpoint 观察权威源或提供可机械追溯的 provenance；拒绝用 UI、cache 或派生投影单独证明权威提交成功；
- 在真实转换链或组装 action 建立稳定证据；
- 不为特定字段或 fixture 写 production 特判；
- 不把“所有未知字段透传”泛化为通用框架。

### Eval 3：浏览器或 native tool 独有行为

输入：失败只在真实 browser lifecycle、真实 native 文件交互或部署打包中出现，本地逻辑无法忠实复现。

期望：

- 判断真实环境是关键因果机制；
- 保留真实 E2E 为权威证据；
- 只补 readiness 或 observability；
- 拒绝用 mock/unit 通过宣称完整验收。

### Eval 4：外部 provider 临时超时

输入：一次 E2E 因 provider 临时不可用失败，无法稳定复现，产品合同未承诺特定重试行为。

期望：

- 不强造确定性代码测试；
- 记录 environment/readiness 或运行手册改进；
- 若需要再次运行，说明目的和条件；
- 不将 provider 偶发问题错误归为内部逻辑回归。

变体输入：provider 协议变化同时暴露内部 adapter 的兼容缺陷。

变体期望：

- 将失败分类保持为可修订、可多因的工作假设；
- 对 provider 真实协议变化保留真实环境证据；
- 对可稳定复现的 adapter 缺陷建立内部回归证据；
- 不强迫选择一个互斥的“唯一根因”。

### Eval 5：探索性真实运行

输入：当前无法判断失败属于内部 seam 还是真实环境，早期证据不足，但一次 sandbox E2E 可产生决定性 artifact。

期望：

- 允许带明确诊断目的进行有界运行；
- 不因缺少全部内部前置证据而硬阻断；
- 将结果视为观察证据，不自动宣称内部前置成立；
- 运行前声明候选假设、决定性 artifact 和结果分流；
- 根据新证据再选择忠实边界；若重复运行，要求新的假设、delta 或观测能力，而不是固定限制为一次。

### Eval 6：低风险局部修改

输入：单 owner、局部可逆、无共享 contract/状态/外部副作用，已有定向测试。

期望：

- 不触发证据阶梯 ceremony；
- 不要求昂贵测试独有风险声明；
- 不新增 plan revision、Ticket、DAG、矩阵或 review gate；
- 继续现有轻量验证和 scoped completion claim。

### Eval 7：内部 bug 但不命中 seam sweep 信号

输入：稳定的局部算法边界错误，不涉及版本、序列化/映射、权威切换、多 consumer 或静默丢失。

期望：

- 在局部忠实边界建立回归证据；
- 不运行 seam sweep；
- 不扫描相邻 consumer 或扩大业务动作范围。

### Eval 8：completion claim 遇到无关历史 failure

输入：当前 package 的 claim 证据完整，但仓库历史上另一个 package 有未下沉的内部 failure。

期望：

- 不要求当前 package 清偿无关历史技术债；
- 只审计当前 claim 相关、已确认且 material 的 failure；
- 不扩大 verification scope。

### Eval 9：fixture 常量诱导错误抽象

输入：测试样本使用固定 ID/hash/时间，agent 提议把它写入通用兼容规则。

期望：

- 使用反事实检查识别 fixture 常量；
- 拒绝 production 特判和错误平台化；
- 只保留真正的业务等价或兼容不变量。

### Eval 10：重复 E2E blocker 循环

输入：E2E 已连续暴露多个确定性内部 seam blocker，当前修复尚未取得 lower-level 忠实证据。

期望：

- 默认暂停无目的的昂贵重跑；
- 为当前已确认 failure 建立最小忠实证据；
- 只有命中五类信号时，才检查当前业务动作中共享同一受损表示或权威事实的语义相邻 seam；
- 在内部证据恢复后，用有明确独有风险目标的 E2E 收口；
- 不把该默认动作描述成不可绕过的 admission gate。

### Eval 11：更早边界与总成本冲突

输入：可以新建一个更低层忠实 harness，但建设和维护成本高；仓库已有稳定的组装 runner，运行稍晚但能忠实保留同一反例且总成本明显更低。

期望：

- 先确认两个候选都忠实；
- 选择总证据成本更低的既有组装 runner；
- 不把“最早”解释成必须新建结构上最低的 harness；
- 只有总成本接近时才以反馈更早作为决胜因素。

### Eval 12：实现缺陷与合同歧义分流

输入一：现有 Acceptance Semantics 能唯一推出 consumer 必须拒绝不兼容输入，但实现错误接受。

输入二：现有合同没有决定两个版本冲突时应拒绝、降级还是采用新版本。

期望：

- 输入一按 implementation defect 修复并复用当前 D/S，不因措辞未逐字覆盖而机械升级 spec；
- 输入二识别为 contract ambiguity，停止受影响单元并路由 `req-align`；
- 测试、adapter 和 Working Branch owner 不临时选择共享语义；
- 能定位既有合同下的首个违约边界；合同无法裁决时交给 Acceptance Semantics owner。

### Eval 13：关键因果输入变化与 evidence freshness

输入一：Git revision 与环境名称未变，但当前 claim 依赖的外部协议版本或 schema 已改变。

输入二：同一证据之后只改变了与当前 claim 无关的显示配置。

期望：

- 输入一只将依赖该协议/schema 的证据判为 stale，并补跑受影响部分；
- 输入二继续复用已有证据，不因任意配置变化机械重跑；
- 不创建 freshness registry、全局因果输入清单或新 runtime state；
- completion audit 能说明变化为何与当前风险相关或无关。

### Eval 14：运行期诊断细化不自动升级 P

输入一：已批准的 Planned Verification 包含真实 provider 兼容风险；一次失败后，执行者增加控制变量和决定性 response checkpoint，以区分协议变化与 adapter 缺陷，但没有改变 claim、required evidence 或覆盖范围。

输入二：失败后决定取消原本 required 的真实 provider evidence，改用本地 mock 支持同一个 completion claim。

期望：

- 输入一由 `dev-with-track` 将诊断假设、控制变量、重跑理由和结果 append 到 ER，不升级 P revision；
- 输入二识别为验证策略和 required evidence 改变，路由 `impl-planning` 判断 P revision，且不能用 mock 冒充真实 provider；
- ER 与 `execution-findings.md` 不形成第二份 Planned Verification 合同；
- 运行期细化不能绕过新的 behavior 或 mutation authority 决策。

## 18. 实施顺序建议

### Phase 1：新增共享 reference

创建 `progressive-system-evidence.md`，吸收本设计第 5–16 节中的稳定方法论：

- 核心术语；
- 最早忠实边界四问；
- 证据阶梯；
- E2E 默认启发式与探索例外；
- checkpoint；
- 条件化失败学习；
- seam sweep 触发和范围；
- 事实分类、反事实检查与平台化判断；
- guardrails。

reference 应保持启发式表达，不复制当前 SKILL 的 artifact lifecycle 或状态操作。

### Phase 2：各 stage SKILL 局部落责

按第 14 节修改入口、planning、execution、subagent integration 和 completion audit。每个 SKILL 只写自身动作和停止条件，其余引用共享 reference。

重点审查：

- 是否把“默认”误写成 MUST gate；
- 是否把探索性 E2E 异常路径删掉；
- 是否把 seam sweep 扩张为所有 bug 的默认步骤；
- 是否把历史 failure 纳入当前 completion claim；
- 是否创建新的 artifact 或状态字段。

### Phase 3：增加 eval

优先增加第 17 节十四类场景，覆盖：

- 正确下沉；
- 正确保留真实 E2E；
- 正确允许探索运行；
- 正确拒绝偶发故障强造测试；
- 正确跳过 seam sweep；
- 正确限制 completion audit；
- 正确拒绝 fixture 特判和提前平台化。
- 正确处理更早反馈与总证据成本的冲突；
- 正确区分 implementation defect、contract ambiguity 和表达缺口。
- 正确证明 checkpoint authority/provenance，拒绝派生投影冒充权威状态；
- 正确保留可修订、可多因的失败分类；
- 正确按关键因果输入判断 evidence freshness，而不建立 registry 或机械重跑。
- 正确区分运行期诊断细化与需要升级 P 的验证策略变化。

### Phase 4：一致性验证

检查：

- `impl-package/SKILL.md` 是否仍只导航；
- stage SKILL 是否引用共享 reference 而不是复制整段正文；
- Planned Verification、ER、execution-findings 和 completion claim 的现有 owner 是否保持不变；
- 没有新增 runtime schema、projection、gate 或 approval；
- 低风险 eval 仍走轻量路径；
- 真实 E2E 没有被 mock/lower-level evidence 替代。

## 19. 方法论完成与停止条件

对于一个具体 attempt，本方法论不追求“所有风险都有所有层测试”。满足以下条件即可停止扩展验证设计：

1. 当前 completion claim 涉及的 material 系统假设可以被明确说出。
2. 每个已选择证据都位于保留关键因果机制的忠实边界；若存在多个忠实候选，已比较总证据成本，并仅在成本接近时优先更早反馈。
3. 昂贵验证的独有风险清楚，真实验收没有被 lower-level evidence 冒充。
4. 已知确定性内部前置缺口已获得足够证据，或有明确理由选择有界探索性真实运行；重复探索具有新的假设、delta 或决定性观察目标。
5. 与当前 claim 相关、已确认且 material 的失败已按条件化规则下沉，或诚实保留为 readiness、runbook、observability 或真实环境风险；若失败包含多个已确认原因，每个原因的证据与后续路由均已说明；复用证据所依赖的关键因果输入没有发生相关变化。
6. 对与当前 claim 相关、material、仍需定位且由当前系统可合理观测的失败，现有 checkpoint 足以指出最后成立和首个失效的业务假设，并能说明 checkpoint 的 authority 与 provenance。不可稳定复现的外部黑盒故障或当前系统无法进一步观测的失败，可以用外部原始证据、已知观察边界和 residual risk 收口；当更多 checkpoint 不能改变定位或决策时停止建设。
7. seam sweep 若被触发，已限制在当前业务动作中共享同一受损表示或权威事实的语义相邻边界并达到停止条件。
8. 没有为了测试引入 fixture 特判、错误通用化、额外状态源或提前平台。
9. 继续增加测试或流程不能显著降低当前 residual risk、反馈成本或诊断不确定性。

## 20. 最终设计结论

Impl-Package 不需要一个新的“系统测试阶段”，也不需要一个 E2E admission gate。它需要的是贯穿 planning、execution、integration 和 completion claim 的共同决策语言：

> 先说清正在证明哪个系统假设，排除不忠实边界后选择总证据成本最低的候选，成本接近时优先更早反馈；已知确定性内部前置缺证据时默认先建立便宜证据，但真实环境独有风险、探索性诊断和证据不足时允许带目的进行有界探索，重复运行必须产生信息增量；失败只有在可稳定复现、保留关键因果机制且具有更便宜稳定 oracle 时才下沉；seam sweep 只在明确的信息边界信号下触发，并限制在当前业务动作中共享同一受损表示或权威事实的语义相邻范围；现有合同能唯一裁决时按 implementation defect 修复，不能裁决时才路由 Acceptance Semantics owner；completion audit 只审计当前 claim 相关、已确认且 material 的 failure。

这一方法能够减少无效的真实 E2E 重跑，同时保留 E2E 对真实环境风险不可替代的权威地位。它通过触发信号、判断问题、推荐动作、反例和停止条件提供执行指导，但不把启发式固化为新的流程桎梏。
