# SKILL 降载减法审计（r3）

工作底稿统一取 `4e53faa^`；`impl-planning` 另合并同一提交前已删除的 `to-tickets/SKILL.md`。先将 HEAD 的路由、机制指针和后续修复移植到底稿，再只删除有宿主无关承接者的内容；未列入台账的内容均保留或仅做压缩。

HEAD 增量核对：`a0d0e7a` 只改组外 `do-review/SKILL.md`，本组四个来源无可移植 delta；本组适用的 `ef45e3b` 改动（`execution-boundaries` 路由）已移植到三个 req-align 文件和 impl-planning。

## 1. `req-align/SKILL.md`

删除台账：

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；本次仅压缩并移植 HEAD 改进） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 50 |
| 降载后（当前 HEAD） | 24 |
| 本次结果 | 48 |

本次移植：保留 Decision/Spec SUB-SKILL 路由链接、`execution-boundaries` owner、package/artifact ownership、fast path、主路径 7 步、package ID 不可改名、Gate 完成条件和业务化输出；补入 typed tools、语义 CLI 与 `situation.py`/`situations.yaml` 处境协议指针。

## 2. `req-align/sub-skills/decision/SUB-SKILL.md`

删除台账：

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；`4e53faa` 未删除本文件内容，本次仅压缩并移植 owner 路由） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 35 |
| 降载后（当前 HEAD） | 35 |
| 本次结果 | 34 |

本次移植：将 Decision artifact 写入/验证与返回 router 的 owner 从旧 `standing-bookkeeper` 改为 `/impl-package:execution-boundaries`，保留 requirement inputs、material promises、unknown triage、focused question、Decision Gate 全部闭合条件及 PASSED/BLOCKED 恢复入口。

## 3. `req-align/sub-skills/spec/SUB-SKILL.md`

删除台账：

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| （无；`4e53faa` 未删除本文件内容，本次仅压缩并移植 owner 路由） | — |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`4e53faa^`） | 52 |
| 降载后（当前 HEAD） | 52 |
| 本次结果 | 51 |

本次移植：将 Spec artifact 写入/验证与返回 router 的 owner 从旧 `standing-bookkeeper` 改为 `/impl-package:execution-boundaries`，保留完整设计范围、五项 Preflight、全部 coherence 触发条件与“禁止残留”列、唯一 authority/producer、disposition、六项写入规则、八章 Gate 完整性和留白导致的 BLOCKED 条件。

## 4. `impl-planning/SKILL.md`（合并原 `to-tickets/SKILL.md`）

删除台账：

| 删除的原文（引降载前） | 承接者（文件:行） |
| --- | --- |
| `impl-planning` 原文第 33–36 行的完整 `package init` / `package validate` Python 命令代码块（仅删除逐行展示，目标文件仍保留命令动作、插件根目录边界与 `package init → package validate` 顺序） | `plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py:39-66`（argparse 帮助、group choices、未知命令报错）；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py:122-132,236-242`（package 命令解析/dispatch）；`plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md:57-75`（当前语义命令入口） |

| 阶段 | 行数 |
| --- | ---: |
| 降载前（`impl-planning` 53 + `to-tickets` 21） | 74 |
| 降载后（当前 HEAD 的合并目标） | 30 |
| 本次结果 | 52 |

逐句核对结果：`to-tickets` 原文 21 行的 Ticket 条件、固定目录、纵向切片、字段、AC/evidence、section-level contract references、typed dependency、state/transition、早期反证与剩余完成证据、安全不变量、旧 Task `DONE`、`NEEDS-REVALIDATION`、运行时投影排除、`RETIRED`/disposition 及 legacy runtime 语义均已合并到“Ticket 拆分”段；没有把这些判断交给 `evals/` 或 DSH。
