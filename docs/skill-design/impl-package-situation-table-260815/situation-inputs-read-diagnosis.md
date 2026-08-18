# `situation-inputs.md` 运行时读取诊断

## 结论摘要

按上一轮 `per-round-read-cost.md` 的口径，六个 session 中有 9 个把
`situation-inputs.md` 作为读取或搜索对象的命令级动作。它们不是 9 次同质化全文读取：
`01a00deb` 的 7 次集中发生在 0.4.0 的首次真实运行、首次写 trail、首次处理 worker/finding
返回和修正 malformed fact 的过程中；后五个 session 的序列是 `0、1、1、0、0`。因此，
“首次接触这套体系 + 首轮边运行边补齐轨迹合同”确实是主要原因，且在本样本中自然衰减；
没有证据表明每轮都会持续重读这份 reference。

但 7 次不能全部归因于 onboarding：其中 4 次是首个 session 内针对 event/fact、finding
定级和 P2/P3 row 的即时查表。真正应该在 `dev-with-track/SKILL.md` 里出现的只有一段很小的
runtime quick contract：当前活动 trail、subject scope、几类事件的最低字段、`situation_digest`、
escape 和 canonical fact 的硬边界。按现有长段落风格，净增加约 8--12 行即可；不应把
`when` key 全表、P0--P5 row 映射、finding parser 细节或 fixture 示例搬进去。若把本轮所有
查到的内容原样搬运，约会增加 250--300 行并重复 `trail-schema.md`，结论是不该这样做。

## 统计口径与路径说明

- 复用了 `scripts/rollout_pulse.py` 的 `resolve()` 和 `read_rollout()` 定位/读取六个 JSONL，
  再只检查 `response_item` 中实际发出的工具调用。
- 计数对象是命令明确把目标文件作为 `Get-Content` 或 `Select-String` 对象的动作；不计
  prompt/assistant 文本提及、`Test-Path`、目录枚举和 `git status`。同一工具调用内的两个或
  多个独立 `Get-Content` 分别计数。
- session 里实际命中的不是当前工作树相对路径，而是插件缓存中的 0.4.0 副本：
  `C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.4.0\...`。
  当前工作树对应文件是 `plugin-marketplace/plugins/impl-package/references/situation-inputs.md`。
  因此下面的“全文/局部”描述的是 session 当时的缓存文件读取动作；缓存 0.4.0 与当前
  reference 的行号和内容已有演进，段落名称使用当前 reference 对照。
- `01a0101a` 的目标路径写成了
  `...\impl-package\0.4.0\skills\dev-with-track\references\situation-inputs.md`，该路径
  不存在，只返回 `PathNotFound`。按上一轮“命令级读取动作”口径计入 1 次，但它没有产生
  目标文件内容，也没有形成全文 token 成本。

## 九次读取逐次复原

### 1. `01a00deb / e105` — 2026-08-17 04:23:03，全文成功

主控正在按用户要求切换到目标 worktree，执行 impl-package 0.4.0 的首次真实运行 preflight，
并准备首次创建 `execution/initial/trail.jsonl`。同一个批量工具调用还读取了 trail schema、
runtime protocol，并从 plan 中核对授权/写集边界。

它要找的不是一个孤立的 `when` key，而是整套输入合同的基线：

- situation renderer 从哪些 package artifact 取输入、subject 如何分域、`unknown/false/HF`
  如何区分；
- trail 的 event/fact 形状，以及首次写 dispatch、result、worker-return、fact 时必须保留的
  字段；
- finding/review/authorization 相关的运行时约束，避免首次写 trail 时落下不可回放的事件。

这是 7 次中的“首次接触/宽读”部分。目标文件读取成功；同批次的 worktree-relative
`trail-schema.md` 路径失败，但不影响这一次目标文件读取。

### 2. `01a00deb / e366` 的第一个局部读 — 2026-08-17 04:36:05

主控刚收到 I-02 reuse worker 的调查结果，正在决定如何把 Ticket 选择、escape、worker return
和 finding 结果写入首次 trail。命令是 `-Skip 110 -First 80`，返回了 ticket/evidence/finding/
trail 相关的 key 表，并接到 event/fact schema 的开头。

它要找的是 `when`/fact 的推导口径：每个事实从 state、Ticket、evidence 还是 trail 来，
缺失时是 U/F 还是硬失败，应该使用哪个 canonical key，以及 fact 应落在哪个 subject scope。
这是“为当前 trail 事实选正确 key”的查表，不是泛读。

### 3. `01a00deb / e366` 的第二个局部读 — 同一工具调用

同一主控阶段读取 `-Skip 450 -First 35`，命中当前 reference 的 `§4.3 trail.jsonl：按统一
event schema 写入` 一段。

目标是确认轨迹事件的最低形状：`decision`、`dispatch`、`result`、`worker-return`、`fact`
各需要哪些字段，direct evidence 的 tuple 放在哪里，哪些旧 kind 只是兼容输入。它属于
“轨迹事件形状”，不是 when-key 推导。

### 4. `01a00deb / e366` 的第三个局部读 — 同一工具调用

同一工具调用再读取 `-Skip 785 -First 45`，返回了 finding 形状说明和“已知失效 key”的规范
形状，尤其是 `ticket.record.evidence-unfiled`、`attempt.readiness.worker-still-running`
以及 `worker-return`/direct-evidence、open dispatch 的例子。

主控是在判断 worker 返回的证据 envelope 是否能被 renderer 消费、以及当前 fixture/结果属于
真实输入形状问题还是 priority/语义问题。它找的是“已知失败形状和归因边界”，不是完整
fact key 清单。

### 5. `01a00deb / e790` — 2026-08-17 05:14:26，匹配搜索

B-01 相关调查/返回处理后，主控开始定义 finding 的 severity/disposition，并在写入 finding
结果前用 `Select-String` 同时搜索 SKILL 和 reference 中的
`P0|P1|P2|P3|severity|finding`。

它要找的是 finding 文档和 situation row 的交界规则：open finding 的合法 Grade
（`P1/P2/P3/editorial`）、Track、source recheck、triage/closure marker，以及 P0--P5
优先级如何影响当前可见处境。输出只返回匹配行，但 `Select-String` 会扫描目标文件全文。
这是“finding 定级/分流和 priority”查表，不是普通 trail event 形状。

### 6. `01a00deb / e2807` 的第一个局部读 — 2026-08-17 06:54:39

主控此前已经直接检查 `situation.py`，发现要修正 3 条 malformed fact；在交接、checkpoint 和
修复轨迹前，再读取 `-Skip 170 -First 25`。

它要确认的是 typed fact 的写法和作用域：`kind=fact` 的 `subject/key/value/ts`、同 key 的
最新值规则、canonical key 的封闭集合，以及 fact 写错 subject 不会跨 scope 生效。这里是
“fact key/轨迹输入合同”的局部复核。

### 7. `01a00deb / e2807` 的第二个局部读 — 同一工具调用

同一工具调用读取 `-Skip 910 -First 18`，命中 P2/P3 的 row 映射，包括 worker envelope
invalid、连续 incomplete、worker blocked、evidence gap、reviewer return 和
source-recheck 等行。

主控要的是把刚修正的 fact/结果放入正确的处境 row，并确认 scope、outcome、worker mode
的组合条件；这是具体的 `when` 组合查表。到这里，首个 session 的 7 次已经包含了首次
接触之外的实际纠错成本。

### 8. `01a00f08 / e140` — 2026-08-17 09:29:17，全文成功

这是新的独立 local session，正在继续 B-01 tax-web browser evidence；在固定 viewport、
local-auth 和 review contract 后，主控准备派发 B-01 worker。它批量全文读取 0.4.0 缓存的
`situation-inputs.md`，并尝试读取 trail schema。

它想重新确认的是 dispatch/return/review 所需的轨迹合同，以及 renderer 输入与当前处境的
关系；从实际上下文看，这是新 session 无历史继承时的重新对齐，不是某一个具体 when key
缺失。目标全文读取成功，但同批次另一个 worktree-relative trail-schema 路径失败，外层输出
还被工具上限截断。

### 9. `01a0101a / e154` — 2026-08-17 14:28:03，全文尝试失败

这是新的独立 B-02 session。主控已经把 B-02 映射到 AC-05，准备按串行 worker/review 合同派发，
同时检查当前 trail 尾部、HEAD 和工作树状态。批量命令意图全文读取 situation contract、
trail schema，再核对现有 trail。

但它把目标写成了不存在的
`...\skills\dev-with-track\references\situation-inputs.md`，所以没有拿到文件内容；同批次
trail schema 路径也失败，随后只能继续做路径定位。它是一次“想做全文合同复核”的失败尝试，
不能算 25K token 的全文消费。

## 全文、局部与失败比例

### 按命令返回形态

| 分类 | 次数 | 具体动作 | 实际内容情况 |
| --- | ---: | --- | --- |
| 显式全文读取尝试 | 3 | `e105`、`e140`、`e154` 的 `Get-Content -Raw` | 2 次成功；`e154` 失败且无目标内容 |
| 局部/匹配结果 | 6 | `e366` 的 3 个 range、`e790` 的 1 个 `Select-String`、`e2807` 的 2 个 range | 6 次均有目标内容返回 |
| 合计命令级动作 | **9** |  | **8 次有内容，1 次路径失败** |

所以如果“全文”指主控收到的完整文件内容，比例是：成功全文 `2/8`，局部/匹配 `6/8`；
若按上一轮的 9 个命令级动作计，则是全文尝试 `3/9`、局部/匹配 `6/9`，并必须单列
1 次失败尝试。若“读取全文”指磁盘扫描，`e790` 的 `Select-String` 也会扫描整文件，
但它只把匹配行返回给主控，不能与 `Get-Content -Raw` 的全文上下文成本等同。

## 是否只是第一个 session 的一次性成本

| session | 任务阶段 | `situation-inputs.md` 动作数 | 解释 |
| --- | --- | ---: | --- |
| `01a00deb` | 0.4.0 首次真实运行、TAW-01 revalidation、首次 trail/finding 处理 | **7** | 首次合同对齐 + 当前 trail/finding/fact 纠错 |
| `01a00e82` | 独立 anchor session | **0** | 没有读取目标 |
| `01a00f08` | B-01 browser evidence | **1** | 新独立 session 的 dispatch/review 合同复核 |
| `01a0101a` | B-02 browser evidence | **1** | 新独立 session 的全文复核尝试，但路径失败 |
| `01a010e6` | TAW-01 C-01 | **0** | 没有读取目标 |
| `01a011d0` | 后续 TAW-02 独立 session | **0** | 没有读取目标 |

首个 session 占 `7/9 = 77.8%`；其后的五个 session 合计 2 次，序列为 `0、1、1、0、0`。
这支持“首次接触成本会衰减”的判断，尤其是后两个 session 已经是 0；但两个 1 次也说明：
每个不继承历史的独立 session 在进入 B-01/B-02 这类轨迹派发边界时，仍可能做一次合同复核。
因此更准确的结论是：首轮集中成本自然衰减，不是永久的每轮开销；不能把它绝对化为未来必然
永远为 0。

## 哪些内容应在 SKILL，哪些应留在 reference

当前 `dev-with-track/SKILL.md` 的“处境投递与轨迹”段已经给了事件类型、`subject`、fact 和
`situation_digest` 的压缩版，但没有把 runtime 最低形状和硬边界集中成可直接执行的 quick
contract。这是本轮局部 schema 查阅能说明的唯一稳定缺口。

### 应进入 SKILL 的最小运行时片段

来源是 `situation-inputs.md`：

- `§1.1 输入文件和 subject` 中的 scope 规则（当前活动 `trail.jsonl`、`attempt`、
  `ticket:<id>`、`finding:<id>`）；
- `§3.1 trail event schema、fact 通道和 validation result` 中事件/typed fact 的最低字段和
  当前文件取最新 fact 的规则；
- `§4.3 trail.jsonl：按统一 event schema 写入` 中 `dispatch`、`result`/`worker-return`、
  `escape`、`fact` 的最小形状。

不需要原文搬运；把它们去重成一段约 8--12 行的 quick contract，内容应只保留：

1. 当前活动 trail 路径和 subject scope；
2. `dispatch` 的 `outcome=RUNNING`、`returned=false`、`worker` 与本次 renderer 的
   12 位 `situation_digest`；
3. `result`/`worker-return` 的 `subject/outcome/of` 及 direct-evidence tuple 的位置；
4. `escape` 必须有 `subject/deviation/reason`；
5. `fact` 必须有 `subject/key/value/ts`，只能使用 canonical key，未知 key 是硬失败，
   同 subject/key 按 `ts/seq/文件顺序`取最新；
6. 明确“具体 when-key、priority、finding 解析仍查 reference”。

这段内容可以覆盖 e366 的 event-schema 局部读和 e2807 的 fact-schema 局部读，也会降低
e105/e140/e154 这类新 session 宽读的动机；它不能消除需要精确推导条件的查表。

### 不应搬入 SKILL 的内容

| 观察到的查阅内容 | 当前 reference 段落 | 不搬的理由与规模 |
| --- | --- | --- |
| 68 个 when key 的来源、取值、U/F/HF 和消费者 | `§2.1`/`§2.2`（约 84 行，68 个 key） | 这是 renderer 合同和维护处境表时的推导口径；随 situation table 演进，不是每轮执行必读。 |
| P0--P5 优先级和具体 row 映射 | `§3.2`、`§9.2`--`§9.4`（约 55--60 行的相关片段） | e2807/e790 需要的是精确组合条件；压缩到 SKILL 会丢掉 U、scope 和抢占边界，完整搬运会变成第二份 table。 |
| finding ID、Status、Track、Grade、source-recheck、triage、closure 解析 | `§4.4`（约 48 行）及 `§9.3`/`§9.4` | 这是 finding parser 的维护合同；`dev-with-track` 只需要知道分流由 situation table 投递，不应复制 parser 细节。 |
| `evidence-unfiled`、`worker-still-running` 等已知失效 key 的规范例子 | `§7`（约 44 行） | 是 fixture/回归和维护材料，不能作为普通 runtime 操作规则。 |

如果把上述实际查阅内容连同 schema、例子和 row 表原样复制，规模约 250--300 行，当前
SKILL 约 93 行，会重复独立的 `trail-schema.md` 和 reference；这不符合“只把运行时真正需要
知道的最小合同放进 skill”的边界。

### 最终 placement 判断

不建议为消除这 9 个命令级动作而整体搬运 `situation-inputs.md`。本轮证据支持的最小归属是：
在现有“处境投递与轨迹”段旁增加约 8--12 行 runtime quick contract；when-key 推导、fact
key 全表、finding/P0--P5 语义和示例继续留在 reference。结合首个 session 的 77.8% 集中、
后续自然降到 0/1，以及其中一次为错误路径失败，9 次本身不构成大规模 SKILL 改写的理由。

## 复核来源

- `docs/skill-design/impl-package-situation-table-260815/per-round-read-cost.md`：上一轮统计口径、9 次计数及 event index 指针。
- `scripts/rollout_pulse.py`：session `resolve()` / `read_rollout()`。
- `C:\Users\Xiao\.codex\sessions` 下的六个指定 rollout：`01a00deb`、`01a00e82`、`01a00f08`、`01a0101a`、`01a010e6`、`01a011d0`。
- 当前工作树的 `plugin-marketplace/plugins/impl-package/references/situation-inputs.md`、
  `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md` 和
  `docs/skill-design/impl-package-situation-table-260815/trail-schema.md`：用于段落对照和规模估算。
