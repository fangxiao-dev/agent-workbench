# Escape 形状与交接轮换调用

状态：阶段 1 已完成并验证；阶段 2、阶段 3 和最终验证尚未完成。本轮直接在 `main`
工作树修改，不 commit。

## 范围判断

- 不新增 fact key、gate 或常驻进程。
- `situation_digest` 仍是兼容可选字段；本轮只把它提升为 dispatch 的常规字段措辞。
- 轮换只挂到显式交接 checkpoint，不改变普通 checkpoint。
- `state.json` 是权威；trail 是记录。trail 写入或轮换失败只警告，不回滚 state、不改变
  checkpoint 命令成功语义。

## 阶段 1：`kind=escape`

### 字段定义（原文）

```json
{"v":1,"seq":13,"ts":"2026-08-15T12:03:00Z","subject":"attempt","kind":"escape","deviation":"attempt.record.unmatched -> manual recovery","reason":"当前处境表没有覆盖该恢复窗口","of":"dispatch-01"}
```

正式形状是：

- `kind`: 固定为 `escape`；
- `subject`: 事实/事件作用域，使用 `attempt`、`ticket:<id>` 或 `finding:<id>`；
- `deviation`: 偏离的 renderer 建议或未覆盖的处境，非空字符串；
- `reason`: 选择 escape 的理由，非空字符串；
- `of`: 可选，关联的 dispatch/decision 标识。

`escape` 是事件，不是 `kind=fact`，因此不消耗封闭 fact key，也不因缺少新字段让
renderer 失败。`situation.py` 保留并读取该事件行。

### 老形状兼容

既有 `kind=decision` + `chosen: "escape: ..."` 继续按旧 decision 事件读取；没有把旧行
迁移或改写成新 kind。`dispatch_audit.py` 继续识别该 `chosen` 前缀，并保留旧行的理由
审计路径；新 `kind=escape` 可用 `reason` 和可选 `of` 关联同一审计。

### 已落盘文件与验证

- `plugin-marketplace/plugins/impl-package/scripts/situation.py`：把 `escape` 从 fact
  兼容分支中明确分流为事件行。
- `docs/skill-design/impl-package-situation-table-260815/trail-schema.md`：加入事件表和
  示例。
- `plugin-marketplace/plugins/impl-package/references/situation-inputs.md`：加入两处
  event schema 表的形状说明。
- `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md`：把强制记录句
  补为 `kind=escape`、`subject`、`deviation`、`reason`。
- `tests/test_situation_render.py`：覆盖新事件和老 decision escape 形状的读取。

阶段定向验证：

```text
python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py -q
66 passed, 1 warning in 37.68s

python -m py_compile plugin-marketplace/plugins/impl-package/scripts/situation.py plugin-marketplace/plugins/impl-package/scripts/dispatch_audit.py
exit 0
```

warning 是既有 `.pytest_cache` 无法写入的 Windows 权限 warning。

## 阶段 2：`situation_digest` 常规字段

### SKILL 原文

```text
`dispatch` 行的常规字段包括 `subject`、`worker` 和本次派发所依据的 renderer 12 位 `situation_digest`，老轨迹和手写轨迹仍可缺失，缺失由只读审计报告，不阻断渲染。
```

这只改变写入指引和 schema 说明，不改变 parser、audit、render 的必填校验；缺少
`situation_digest` 仍是 `dispatch_audit.py` 的 `no-digest` 信号，render 仍可读取老轨迹和
手写轨迹。

阶段验证：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py check
check: PASS
- stage: dev-with-track
- situations: 59
- implemented when keys: 68
- priority groups: 6
```

## 阶段 3：显式交接轮换

### 判断结论

- 标志名：`--handoff`。它只表示当前 `recovery checkpoint` 是交接边界；普通 checkpoint
  （包括 BLOCKED、retry 和普通恢复）不轮换。
- 带标志的 checkpoint 仍先按原路径写入 `state.json` 和既有 `kind=checkpoint` 记录；随后
  活动 `trail.jsonl` 原样移动为下一个 `trail.NNN.jsonl`，创建新的活动文件，并写入一条
  `kind=handoff`、相同 `subject`、`checkpoint:true` 和当前 checkpoint payload 的记录。
- `kind=handoff` 由 CLI 机械写入，不再依赖模型自觉；新文件的 checkpoint marker 也避免
  交接后把 handoff 自身误判成 checkpoint 之后的动作。
- 轮换失败或 handoff 记录失败只写 stderr warning；state 不回滚，checkpoint 命令不失败，
  stdout JSON 仍只有 `subject`、`checkpoint`、`idempotent`，没有改变既有 `--expect` 语义。
- 归档中的最大 `seq` 参与下一序号计算，保持 attempt 内单调序；归档命名仍是严格的
  `trail.NNN.jsonl`。

### `attempt.record.trail-rotation-due`

保留这条处境行。它仍表达 Ticket 边界上的机械轮换需求，但动作口径改为显式调用
`recovery checkpoint --handoff`；它不再只是“建议手工按 schema 移文件”。普通 checkpoint
不触发它的动作，pressure-driven `attempt.record.handoff-due` 仍独立存在。

### 已落盘文件与定向验证

- `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py`：
  recovery checkpoint 接受 `--handoff`。
- `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py`：实现归档、
  新活动 trail、全局 seq 续接、handoff 行和 best-effort warning。
- `tests/test_impl_package_state.py`：覆盖不带标志不轮换、带标志轮换并写 handoff、轮换失败
  checkpoint 仍成功；没有改现有 fixture 的 expected 值。
- 相关 schema、SKILL、situation action 和 CLI reference 已同步。

```text
python -m pytest tests/test_impl_package_state.py -q -k 'handoff_checkpoint or handoff_rotation'
2 passed, 16 deselected, 1 warning in 5.33s

python -m pytest tests/test_situation_render.py tests/test_dispatch_audit.py -q
66 passed, 1 warning in 43.36s
```

完整 `tests/test_impl_package_state.py` 尚待最终验证；此前 180 秒窗口只跑出 5 个点后超时，
该次不计为通过，最终会使用足够的运行窗口完整跑完。

## 尚未落盘

1. 运行用户指定的 check、两组 pytest 和真实 package 的只读 audit/render。

## 工作树边界

`skills/call-grok/SKILL.md` 在本任务开始前已有未提交改动；该文件属于另一项作业，本轮不
修改、不纳入本报告的实现 diff。
