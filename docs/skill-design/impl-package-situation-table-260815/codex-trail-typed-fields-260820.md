# trail append 具名字段改造记录

## S1 盘点（2026-08-20）

本阶段只盘点现状，基线为 `main` 上游提交 `d1ec699`；工作树中已有的
`skills/call-grok/*`、`debug.log` 和 `plugin-marketplace/plugins/impl-package.zip`
等未提交改动不属于本任务。

### CLI 参数与校验路径

- 入口是
  `plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py` 的
  `trail` 命令组，转入
  `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py`。
- `command_groups.py:182-183` 的 `trail append` 当前只有一个无额外参数的
  `argparse` 子命令，帮助文本是“append a validated manual trail event from stdin”。
- `command_groups.py:237-238` 的 `_run()` 直接把 `sys.stdin.read()` 交给
  `engine.command_trail_append()`；stdin JSON 是当前唯一载荷入口。
- `engine.py:1167-1181` 先解析 stdin JSON，然后依次经过：
  - `_validate_trail_event()`：拒绝 `v/seq/ts/head`，校验四种 kind、subject、
    fact key/value、escape 字段、dispatch 基础字段和 review 字段；
  - `_validate_review_dispatch_fields()`（`engine.py:1108-1126`）：要求
    `review_phase` 与 `review_track` 成对出现，使用闭合词表，并要求
    `review_recheck` 为 boolean；
  - dispatch 的 12 位 hex 格式检查（`engine.py:1154-1161`）；
  - `_validate_dispatch_situation_digest()`（`engine.py:1088-1106`）：保留凭据
    文件存在、digest 匹配、`state.json` sha256 匹配三条闸门；之后才追加 trail。
- 读取旧轨迹的处境逻辑在 `situation.py`（例如 review track 读取处）；它对词表外
  的历史 `review_phase` / `review_track` 只忽略，不作为本次 CLI 输入校验收紧的目标。

### DSH `impl_trail_append` 引用点

`git grep -F impl_trail_append` 的全部当前引用如下：

- `plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/impl-tools.mjs:379`：
  唯一工具注册、自由 JSON `payload` schema，以及 stdin 调 CLI 的执行闭包；这是本次
  替换实现点。
- `plugin-marketplace/plugins/dsh-impl-package/README.md:93`：工具到 CLI 的表格；
  `README.md:103`：escape 轨迹说明。
- `plugin-marketplace/plugins/dsh-impl-package/baseline-skill-sizes.md:154`：9 个
  typed 工具的基线清单。
- `plugin-marketplace/plugins/dsh-impl-package/lib/index.mjs:156`：宿主注入公告中的
  工具清单。

没有其它 `impl_trail_append` 调用点；现有 `smoke-test.mjs` 只测试
`buildTicketArgv` 等纯函数，尚无 trail 工具构造测试。协议参考文档中的
`trail append` 说明是 CLI/JSON schema 说明，不是 DSH 工具名引用。

### `REVIEW_*_VALUES` 唯一来源

- `plugin-marketplace/plugins/impl-package/scripts/situation.py:42`：
  `REVIEW_PHASE_VALUES = ("initial", "finding-closure", "terminal-final")`。
- `situation.py:43`：
  `REVIEW_TRACK_VALUES = ("Track A", "Track B", "Track C", "Track D")`。
- `situation.py:44-45` 由这两个 tuple 派生 set；`situation.py:51-52` 由 tuple
  展开协议占位符。
- `engine.py:26-28` 直接从 `situation` 导入 tuple 和 set；没有第二份 Python
  合法值字面量。CLI choices 将从同一 `situation.REVIEW_*_VALUES` 读取。
- DSH 运行时不能直接 import Python 常量，因此 S3 将在 JS smoke test 中从
  `situation.py` 的定义解析合法值，并与四个工具 schema 的 enum 做 parity 断言。

## S1 结论

改造边界可以保持在 CLI 参数/合并入口、DSH typed schema/纯函数测试、相关 DSH
文档清单和阶段证据文档；不需要改 digest 校验、render 逻辑、`situations.yaml`、
`expected.json` 或既有处境尾注。

## S2 CLI flag（2026-08-20）

### 实现

- `command_groups.py` 的 `trail append` 现在公开：
  - `--situation-digest`：使用既有 `engine.TRAIL_DIGEST_RE` 做 argparse 类型校验；
  - `--review-phase`：`choices=situation.REVIEW_PHASE_VALUES`；
  - `--review-track`：`choices=situation.REVIEW_TRACK_VALUES`；
  - `--review-recheck`：boolean flag，缺省保持 `None`，只有显式出现才参与合并。
- `command_groups._run()` 将四个 parsed 值交给同一个
  `engine.command_trail_append()`；stdin JSON 仍是主载荷路径。
- `engine._merge_trail_named_fields()` 在既有事件校验前合并：
  - stdin 中没有该键时写入 flag 值；
  - 已有值与 flag 值严格同类型且相等时通过；
  - 值不同时抛出 `StateError`，不覆盖任一方向。
- `_validate_dispatch_situation_digest()`、`_validate_review_dispatch_fields()`
  以及缺 digest 时的拒绝路径没有修改；没有自动 render。

### 测试

新增 `tests/test_impl_package_state.py` 的真实 CLI seam 用例，覆盖四个 flag 合并、
非法 digest/phase/track、四种 stdin/flag 冲突、相同值通过和仅 stdin 的命名字段旧路径。

TDD 选择性回归（只选本文件中的新增相关用例）：

```text
python -m pytest tests/test_impl_package_state.py -q -k "named_flags or stdin_named_fields"
5 passed, 33 deselected, 1 warning
```

warning 仅为受限工作树无法写入 `.pytest_cache`，不影响测试结果；用户指定的整文件
回归留到 S4 执行。

## S2 结论

CLI 已从帮助可见性和输入合并两侧补上三个 review/digest 字段的具名入口，同时保持
stdin 兼容和原有 dispatch 闸门。进入 S3 拆除 DSH 的自由 `payload` 工具。

## S3 DSH 拆分（2026-08-20）

### 实现

- `impl-tools.mjs` 删除通用 `impl_trail_append` 注册，改为四个扁平 typed 工具：
  - `impl_trail_dispatch`：`subject`、`worker`、`outcome`、`returned`、必填
    `situationDigest`，以及 review 三字段；dispatch outcome enum 为 `RUNNING`；
  - `impl_trail_escape`：必填 `subject`、`deviation`、`reason`；
  - `impl_trail_fact`：必填 `subject`、`key`、`value`；value 保留任意 JSON 值；
  - `impl_trail_worker_return`：必填 `subject`、`outcome`。
- 四个工具分别调用同一个 `trail append` CLI。dispatch 的 `situationDigest`、
  `reviewPhase`、`reviewTrack` 和 true 的 `reviewRecheck` 优先走 S2 的具名 flag；
  `reviewRecheck=false` 保留为 stdin 的显式 boolean（CLI flag 本身是 true-only），
  不改变 Python 对 false/缺省的既有语义。
- `buildTrailDispatchInvocation`、`buildTrailEscapeInvocation`、
  `buildTrailFactInvocation`、`buildTrailWorkerReturnInvocation` 是可测纯构造函数，
  返回同一 CLI 的 `argv` 和 stdin JSON。
- README、baseline 和 `lib/index.mjs` 的工具清单已从 9/通用工具同步为 12/四个
  具名工具；没有保留 generic 工具的正向调用或文档入口。

### 测试与 parity

`plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs` 新增：四个纯构造
测试、generic 工具不存在断言，以及 schema enum parity 断言：

- 读取 `situation.py` 的 `REVIEW_PHASE_VALUES` / `REVIEW_TRACK_VALUES` tuple，
  与 dispatch schema 的 `reviewPhase` / `reviewTrack` enum 顺序和值逐项比较；
- 读取 `engine.py` dispatch validator 的 `outcome != "RUNNING"` 约束，与 dispatch
  schema 的 outcome enum 比较。

实际 smoke 结果：

```text
node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs
四个 trail constructor、generic removal、dispatch outcome parity、review phase parity、review track parity 均 ok
ALL PASS
```

## S3 结论

DSH 的唯一松散 trail 入口已被四个 typed 工具替换；合法 review/digest 值在 DSH
schema 与 Python 侧有 smoke parity 证据，进入 S4 指定验证。

## S4 指定验证（2026-08-20）

三项验证均在本工作树、同一 revision 执行，均 exit code `0`；没有执行全量
`pytest tests/`。

### 1. Python state 回归

命令：

```text
python -m pytest tests/test_impl_package_state.py -q
```

原始结果：

```text
......................................                                   [100%]
============================== warnings summary ===============================
C:\Users\Xiao\AppData\Local\Programs\Python\Python310\lib\site-packages\_pytest\cacheprovider.py:475
  C:\Users\Xiao\AppData\Local\Programs\Python\Python310\lib\site-packages\_pytest\cacheprovider.py:475: PytestCacheWarning: could not create cache path D:\CodeSpace\agent-workbench\.pytest_cache\v\cache\nodeids: [WinError 5] 拒绝访问。: 'D:\CodeSpace\agent-workbench\.pytest_cache\v\cache\nodeids'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
38 passed, 1 warning in 415.85s (0:06:55)
```

warning 是受限工作树无法写入 `.pytest_cache`，不影响测试通过。

### 2. DSH smoke

命令：

```text
node plugin-marketplace/plugins/dsh-impl-package/test/smoke-test.mjs
```

实际关键输出：

```text
== trail tools ==
  ok  dispatch constructor builds flat payload and named flags
  ok  escape constructor builds required payload
  ok  fact constructor preserves arbitrary JSON value
  ok  worker-return constructor builds required payload
  ok  four typed trail tools are registered
  ok  generic impl_trail_append is removed
  ok  dispatch outcome enum parity with Python validator
  ok  review phase enum parity with situation.py
  ok  review track enum parity with situation.py

ALL PASS
```

其余既有 resolution/render/protocol/commands/host-half/reviewer/orchestrator 检查也均为
`ok`。

### 3. `trail append --help`

命令：

```text
python plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py --package tests/fixtures/situations/p0-session-resumed trail append --help
```

完整原文：

```text
usage: impl_package_state.py --package <package> trail append
       [-h] [--situation-digest SITUATION_DIGEST]
       [--review-phase {initial,finding-closure,terminal-final}]
       [--review-track {Track A,Track B,Track C,Track D}] [--review-recheck]

options:
  -h, --help            show this help message and exit
  --situation-digest SITUATION_DIGEST
                        12-character hex digest previously emitted by
                        situation.py render
  --review-phase {initial,finding-closure,terminal-final}
  --review-track {Track A,Track B,Track C,Track D}
  --review-recheck
```

## S4 结论

指定 CLI 回归、DSH smoke/parity 和帮助发现性验证全部通过；S1–S4 阶段范围已完成。
