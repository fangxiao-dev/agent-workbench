# 渐进式系统证据

本 reference 为 Impl-Package 的 planning、execution、integration 与 completion claim 提供共同的系统测试方法论。它是指导性判断，不创建 stage、gate 字段、case ID、证据矩阵或第二份行为合同。

## 何时读取

仅当当前 attempt 存在以下任一信号时读取：跨模块业务动作、`material seam`、昂贵的 browser/provider/native-tool 验证，或已发生需要定位的系统性 failure。单 owner、局部可逆且已有直接证据的改动继续走现有轻量路径。

稳定行为、interface、compatibility、authority、失败恢复与 Acceptance Semantics 仍由 Decision/Spec 拥有；plan 只选择证据，ER 只记录实际运行证据，completion skill 只审计 claim。执行者不得把新行为合同藏进本 reference、ER 或测试。

## 核心判断

### System assumption 与 material seam

系统假设是一个业务动作成立时多个组件、边界或环境共同依赖、且可被证伪的判断，例如信息保真、版本兼容、权威提交或真实环境执行合同。

`material seam` 是其失效可能让当前 Acceptance Semantics 在局部证据绿色时仍 false PASS 的信息、authority、兼容或副作用边界。DTO、adapter 或跨模块调用不因技术形态本身成为 material seam。

### 最早忠实边界与总证据成本

忠实边界保留当前风险的关键因果机制；它不是最低测试层、最小函数或最多 mock 的环境。缩小范围后，已知失败的最小反例或同类错误实现必须仍可到达，并由 oracle 稳定区分。替换实际 consumer、版本解释、转换、authority 切换或关键副作用顺序而使反例消失，则该边界不忠实。

选择边界时依次问：

1. 关键语义机制在较小范围内是否仍真实存在？
2. 必要输入、版本、状态、consumer 组合与顺序是否可受控建立？
3. oracle 能否直接区分正确和错误，而非只观察相邻信号？
4. 去掉真实 browser、provider、native tool、网络或部署环境后，是否丢失关键因果机制？

先用这四问和反例保留排除不忠实边界；再在忠实候选中比较总证据成本：能力建设、单次运行、长期维护、诊断成本、稳定性、复用概率与 false-confidence 风险。成本接近时优先更早反馈。真实环境独有风险仍由真实验证证明。

不要把 evidence ladder 当作逐层必跑的序列：局部语义、seam/contract、组装业务动作与真实 E2E 是对 claim 的风险分解。较早证据证明内部确定性合同，真实 E2E 证明环境独有剩余风险，二者可组合支持同一 claim。

## 昂贵验证与探索

对真实 E2E、provider、browser 或 native tool，在现有 Planned Verification 行中简短说明：正在证明的系统假设、独有剩余风险、必要 checkpoint/readiness，以及失败时如何初步区分内部 seam、真实环境、外部波动与观察缺口。

已知确定性内部前置缺证据时，默认先建立更便宜且忠实的证据，不反复消耗昂贵运行。这不是 E2E admission gate：当前风险依赖真实环境、需要探索诊断、边界尚未知，或真实运行能产生决定性 artifact 时，可以带明确目的进行有界探索。

每次探索运行写清：

- 待区分的候选假设；
- 能改变下一步判断的 checkpoint 或 artifact；
- 不同结果分别路由到内部修复、组装验证、环境处理或继续真实验证；
- 相对上次新增的假设、环境/修复 delta 或观测能力。

重复探索不需要新 gate，但必须有信息增量。没有新假设、delta 或决定性观察目标时停止无信息增益的重跑。mock 或 lower-level evidence 不得冒充真实 browser/provider/native-tool claim。

## 业务 checkpoint

checkpoint 应使当前 failure 能定位最后成立和首个失效的业务假设，而不是只输出函数名、payload 或最终错误码。按风险选择最少信息：业务对象/revision/correlation、语义输入与决定、语义输出、authority/owner、版本解释、以及副作用阶段。

可复用现有 test probe、结构化业务日志、只读 inspector、领域事件、审计记录或外部 artifact；不要为此建立全局 tracing 平台、第二状态源或强制 schema。

用于证明权威状态切换、提交成功或副作用确认的 checkpoint，必须直接观察 authority，或可机械追溯其 authority、revision 与 environment。UI、cache、日志副本或派生投影可用于定位，但不能单独证明权威状态已成立。更多 checkpoint 不能改变定位或决策时停止添加。

## Failure → evidence 学习闭环

1. 保存原始事实：revision、worktree、environment、业务动作、最后成功/首个异常 checkpoint、决定性外部 artifact，以及可重复性。
2. 分类是可修订、可多因的工作假设：确定性内部 assumption、系统组装、真实环境独有、环境/外部偶发或观察缺口可以同时存在；新 evidence 出现后允许重新分类。
3. 只有满足全部条件时才下沉为更便宜的回归证据：可稳定复现或受控触发；保留关键因果机制；有更便宜稳定 oracle；不引入 production fixture 特判；与当前风险相关。
4. 不满足下沉条件时，保留为 readiness、runbook、observability、residual risk 或真实环境验证；不要强造代码测试。
5. 先区分 authority：现有 Acceptance Semantics 与 repository authority 能唯一推出正确行为时，按 implementation defect 修复；只有多个合理业务结果无法由现有合同裁决时，停止受影响单元并路由 `req-align`。
6. 定位首个违反既有合同的边界。producer 负责已承诺输出的语义/保真，consumer 负责按已声明合同解释、验证或拒绝，transport/platform 负责已承诺的传输/顺序/持久性/兼容。合同无法判断谁违约时，由 Acceptance Semantics owner 决定；worker、adapter 或测试不得临时发明共享语义。

### 有限 seam sweep

仅在版本兼容、序列化/映射、authority 切换、跨 consumer 解释分歧或静默信息丢失时触发。范围限于当前业务动作中直接读取、写入、转换同一受损表示，或依据同一 authority fact 作决定的语义相邻 producer/consumer；物理调用跳数不是边界，消息/事件连接只要参与当前 Acceptance Semantics 也可以相邻。不要全仓扫描、建立 consumer registry 或要求 worker 在派发前穷举 consumer。

当前 failure 已有稳定证据、语义相邻边界没有同类未覆盖风险、发现开始偏离当前动作，或继续需要新产品决策/公共平台时停止 sweep。

### 运行期诊断与 P revision

已批准风险、claim 与验证策略内的候选假设、控制变量、checkpoint、重跑理由与结果分流，只追加到 ER，由 `dev-with-track` 决定；它们不自动升级 P。只有 completion claim、验证策略、required evidence、覆盖范围或外部 mutation authority 改变时，才回 `impl-planning` 判断 P revision。ER 和 `execution-findings.md` 不形成第二份 Planned Verification 合同。

## Completion claim 的证据边界

completion audit 只审计当前 claim，不重新设计验证策略，也不追溯清偿无关历史 failure、旧 package 技术债或未触及风险。

复用 evidence 时，除 revision/worktree/environment 外，按当前 claim 检查关键因果输入是否变化，例如协议版本、feature flag、schema、部署配置、共享数据前置或认证策略。相关变化只使依赖它的 evidence stale；无关变化继续复用。不要创建 freshness registry 或因为任意配置变化机械全量重跑。

与当前 claim 相关、已确认且 material 的确定性内部 failure，应已有稳定回归证据，或有可信理由说明其不满足下沉条件。偶发环境问题可以以 readiness/runbook/observability/真实验证风险收口，不能为了 completion 伪造绿色代码测试。

## 抽象与停止护栏

用反事实检查区分事实：如果替换字段名、内部 ID、时间或样本为语义等价值，预期行为仍相同，它通常是 fixture 常量或实现细节，不能进入 production 特判或通用规则。领域事实和跨模块/版本/状态仍必须成立的系统不变量属于 Decision/Spec；可随重构改变的实现细节留在局部实现与测试。

优先复用已有 runner/probe/inspector；其次补窄 seam 能力；信息 ownership 不清时先修合同/边界；只有多个独立业务流反复共享同一稳定语义、且抽取能删除当前重复并降低复杂度时才平台化。

停止扩展证据，当：当前 claim 的 material system assumption 已明确；所选证据忠实且成本合理；真实环境独有风险仍有真实证据；当前 claim 相关 failure 已下沉或诚实保留；必要 checkpoint 能定位且 provenance 足够；继续增加证据不能明显降低残余风险、反馈成本或诊断不确定性。

## 明确禁止

- 不创建全层测试要求、固定矩阵、case ID、evidence graph、checkpoint/consumer/freshness registry、新 runtime state 或 gate。
- 不以 fixture、测试账号、provider 名称或样本常量改变 production 行为。
- 不让 lower-level evidence 替代真实 E2E 的独有风险。
- 不将任意 failure 强制下沉，不将任意内部 bug 强制 sweep，也不将探索运行变成固定次数或审批门。
- 不因本方法论使低风险局部改动新增 Plan revision、Ticket、DAG、review 或 owner checkpoint。
