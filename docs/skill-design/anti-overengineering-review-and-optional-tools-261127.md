# 设计期反过度设计拦截与节点可选工具机制

日期：2026-11-27  
设计依据：结合 KaiSpan 员工助手细化包（`2026-11-26-hr-refinement`，分支 `feat/2026-11-26-hr-refinement`）从设计到终审的实战复盘、优化登记（`fangxiao-dev/KaiSpan#628`），以及对 `impl-package`、`kickoff` 与第三方 `ponytail` 插件能力的对比调研。  
状态：方向已与 Owner 对齐，待实施。

---

## 1. 实战暴露的具体问题

### 1.1 现象：内核更收敛，外层明显发散
在既有员工助手模块上做权限细化与算钱链路收口，实际产出规模（不含自动生成的 `packages/contracts/*` 与文档）达到：
- API 生产代码：104 个文件，`+4,057 / -764`
- Web 生产代码：64 个文件，`+2,849 / -368`
- 新增 32 个非测试源文件，仅删除 1 个文件（`worktime-scope.ts`）

业务规则本身更严谨了，但外层长出了大量**平行视图、重复入口与分散约定**：
1. **单权限合同另造整套 `minimal` 世界**：后端新增 `contract-minimal-view.ts` / `contract-minimal.dto.ts` 与专用任务发现接口 `GET /v1/hr/contracts/tasks`，前端新写 448 行的 `hr-contract-tasks-minimal.tsx` 与 103 行的 `hr-contract-minimal-api.ts`，与完整合同视图双轨并存。
2. **单权限入职邀请另造最小名册**：前端新写 124 行的 `hr-invite-roster-minimal.tsx` 与独立接口，和原有员工名册平行维护。
3. **工资页重复实现工时账户与封账**：因为原有 `/hours` 入口绑死考勤权，在工资页又新写了 280 行的 `hr-payroll-worktime.tsx`（甚至前端循环逐店拉列表拼人名）与 158 行的 `hr-payroll-closing.tsx`。终审随即暴露出“工资页账户区漏接离职结清与冲回入口”的双轨同步缺陷。
4. **并发防线靠分散约定**：封账串行靠各写入口在 `Serializable` 事务内自觉 bump 组织行，终审一次揪出 3 处写入口漏锁。

### 1.2 根因定位：70% 来自设计阶段，30% 在实现与补丁阶段放大
- **不是业务权限拆得太细**：按职责拆分排班、邀请、档案、合同、考勤、工资在业务上直观合理；过度设计出在**实现方式上把“同一入口按能力裁剪”做成了“按单权限另造平行页面与 API”**。
- **现有设计流程是“单向加压”的，缺少反向拦截**：
  1. **`req-align`（`spec-gate.md` / `contract-surface-design.md`）**：只查“覆盖全不全、语义是否闭合、两个实施者会不会做出不同结果”。由于改既有接口要追踪全部下游消费者，而新开 `*-minimal` 接口白名单最好写，流程激励反而偏向另造平行接口。
  2. **`plan-review`（`scope-review.md` / `architecture-review.md`）**：把上游 `contract-design.md` 视为不可更改的既定合同，无权因过度设计退回简化；架构审阅只查失败场景、并发与规则边界，不查平行视图或重复组件。
  3. **`review-code`（`review-checklist.md` / `strict-maintainability.md`）**：已有很强的结构深挖基线，但默认藏在按需加载里，普通单票审阅很少触发；且到写完代码再翻上游合同成本已过高。
  4. **缺少跨包/模块级体检视角**：`impl-package` 全套面向单包 diff，连续几轮迭代累积的模块膨胀没有固定入口去盘点；即使安装了第三方体检工具（如 `/ponytail:ponytail-audit`），不放进流程节点作为可选项也会很快被遗忘。

---

## 2. 两个方向的解决方案

核心原则：**能力内建（零第三方硬依赖）+ 编排可见（把可选工具挂到节点菜单）**。

| 方向 | 落点仓库 / 模块 | 核心目标 | 对第三方插件的立场 |
| --- | --- | --- | --- |
| **方向一：设计期与审阅期的内建“反过度设计拦截”** | `plugin-marketplace/plugins/impl-package/` | 在合同冻结前拦住平行视图与冗余抽象，在计划期赋予上游退回权，在代码审阅期把“减法/近拷贝合并”提到常规必查 | **零依赖**。只吸收 `ponytail` 里最锋利的 `lean` 判据（近拷贝合并、单实现抽象、删除优于新增、显式减法清单），直接内化为自有规则 |
| **方向二：在 `kickoff` 编排层与下游节点引入“可选工具菜单（`optional_tools`）”** | `skills/kickoff/`（及下游审阅提示） | 在各阶段声明“可选工具 + 触发时机 + 无插件回退做法”，由 CLI 自动展示但不卡门禁，让好用的体检工具融入节奏、不被遗忘 | **弱消费、可随时替换**。如 `discover` 节点将 `/ponytail:ponytail-audit` 列为既有模块迭代的可选项，插件不存在时自动回退为同等维度的只读子代理巡检 |

---

## 3. 两个方向的具体落地清单

### 3.1 方向一：`impl-package` 内建反过度设计拦截（方法层）

#### A. `req-align` Spec Gate（合同冻结前，第一道拦截）
- **目标文件**：`plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md`（必要时同步 `sub-skills/spec/SUB-SKILL.md`）
- **具体改动**：将现有 Spec Gate 的独立覆盖核对升级为双向核对——既查“漏了什么”，也强制做 4 项**简约性与复用拦截**：
  1. **平行视图拦截**：凡因权限/角色拆分，为同一业务实体或流程新造第二套列表接口、DTO 或独立页面（如 `*-minimal`），默认质疑并要求给出“为什么无法在原有入口做服务端字段投影 + 能力位裁剪”的硬理由；说不清则 `BLOCKED`。
  2. **多入口归属拦截**：同一业务操作出现在 2 个以上入口时，冻结前必须明确单一查询源与共享组件归属，避免下游各自拼凑。
  3. **新增面比例审查**：对照业务承诺列出新增 API、独立 DTO、新表清单，标出仅为“绕开旧代码/方便写测试”而新增的 surface 并逐项挑战必要性。
  4. **分散约定拦截**：并发锁、幂等、权限校验若依赖“所有未来写入口自觉调用某 helper”，要求评估能否收口到统一写通道或显式守卫。
- **输出要求**：在 Spec Gate 独立审阅输出中增加简短的**减法清单**（可合并/可取消的新增 surface；无则写“无”）。

#### B. `plan-review`（拆票前，第二道拦截 + 上游退回权）
- **目标文件**：
  - `plugin-marketplace/plugins/impl-package/skills/plan-review/references/scope-review.md`
  - `plugin-marketplace/plugins/impl-package/skills/plan-review/references/architecture-review.md`
- **具体改动**：
  1. **授予上游简化退回权**：在 `scope-review.md` 明确——当拆票发现上游 `contract-design.md` 会逼出明显双轨页面、重复接口或高同步维护面时，不必机械顺着合同拆票，可直接提出 `contract-simplification candidate`，走 `kickoff` 的 `--touched-upstream` 退回 `req-align` 简化。
  2. **共享组件显式声明**：在 `architecture-review.md` 增加检查——既有页面已有的交互面板（如账户、封账、合同核验）需要在新入口出现时，Plan 必须写明抽取复用哪个共享组件，禁止静默复制一套平行页面。
  3. **分散约定风险审查**：对依赖多处写入口自觉遵守的并发/一致性约定，在架构审阅中标出漏锁风险并要求评估收口。

#### C. `review-code`（实现审阅期，常规必查提权）
- **目标文件**：`plugin-marketplace/plugins/impl-package/skills/review-code/references/review-checklist.md`
- **具体改动**：
  1. 不引入第三方 `ponytail-review`，保留现有更强的 `strict-maintainability.md`；
  2. 在常规 `Standards and maintainability` 基线中，把**近拷贝/平行视图合并**、**单实现薄抽象**与**可删减代码/文件清单**提成常规必查信号，不再等手动启用深挖才看；
  3. 明确区分：为了跨包/模块级瘦身才采用可选体检工具（见方向二），单包 diff 审阅仍以 `review-code` 为唯一规范。

---

### 3.2 方向二：`kickoff` 编排层增加节点可选工具与减法原则（流程层）

#### A. `pipeline.json` 结构增量与原则补强
- **目标文件**：
  - `skills/kickoff/pipeline.json`
  - `skills/kickoff/scripts/engine.py`（读取并打印 `optional_tools`，不改状态机门禁）
  - `skills/kickoff/SKILL.md` & `skills/kickoff/tests/test_kickoff.py`
- **交互形态（轻量非阻塞）**：在 `stages[]` 增加可选数组 `optional_tools: [{ "name", "when", "fallback" }]`，在 `kickoff.py status` 和 `advance` 切换节点时自动打印“本阶段可选工具（不卡门禁）”。不新增复杂 CLI 开关，不因第三方插件缺失而报错。
- **各节点具体挂载**：
  1. **`init`**：原则补充——复述确认时，若本次是对既有大模块的二次细化或重构，顺带向 Owner 亮出后续节点可用的体检/瘦身选项（1 行带过，防止遗忘）。
  2. **`discover`**：
     - 原则补充：既有大模块二次迭代时，先摸底模块内是否已存在平行视图或重复入口，决定“借机合并”还是“继续叠加”。
     - `optional_tools`：挂载 `/ponytail:ponytail-audit <目标模块目录>`（`when`：既有模块经历多轮迭代或准备做重构/瘦身包前；全新模块跳过；`fallback`：无该插件时，派一只读子代理按“跨入口重复逻辑 / 单实现抽象 / 死代码 / 可合并文件”四维扫描）。
  3. **`spec`**：
     - 原则补充：新增硬原则——不为单权限/单角色另造平行视图或平行发现接口，默认在原入口做服务端字段投影与能力位裁剪，除非给出不可复用的硬理由。
     - `optional_tools`：标明 Spec Gate 的内建简约性反查（零外部依赖）。
  4. **`plan`**：
     - 原则补充：拆票时若发现上游合同导致双轨页面或重复组件，优先走 `--touched-upstream` 退回简化；多入口共享能力须声明复用的共享组件。

#### B. 范围边界（不塞进 `kickoff` 的项）
- `/ponytail:ponytail-review`（针对代码 diff 的瘦身审阅）与 `/ponytail:ponytail-debt`（扫 `shortcut: <limit>, <when to upgrade>` 临时妥协账本）属于**实施与收口期**工具，不塞进只管到 `ready` 的 `kickoff`；后续在实施编排（如 `dev-with-track` / `do-review` 或收口检查）按同样“可选工具 + 无插件回退”方式按需挂载即可。

---

## 4. 下一步实施与验证建议

1. **分两小步改动**：
   - 先改 `impl-package` 的 4 份参考文档（`spec-gate.md`、`scope-review.md`、`architecture-review.md`、`review-checklist.md`）；
   - 再改 `kickoff` 的 `pipeline.json`、`engine.py`、`SKILL.md` 与 `tests/test_kickoff.py`，跑通单测与 `diagram --sync-md --check`。
2. **首轮实战检验**：以 `fangxiao-dev/KaiSpan#628`（员工助手权限双轨视图收敛）作为第一个试跑对象，在 `discover` 节点实测一次可选模块体检 + `spec` 简约性拦截的效果。
