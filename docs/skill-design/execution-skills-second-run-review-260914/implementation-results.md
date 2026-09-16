# 推荐项的实施与验收结果

日期：2026-09-14。按 [recommendations.md §6](recommendations.md) 的 Owner 决定实施：R1（含处境注入与 handoff 联动）、R2、R3 模板、R4 两侧、R5、R6、R7；review 档位与 terminal 重登记语义未动；call-grok 未动。未提交、未安装、未发布，版本仍 `0.4.2`。

## 改了什么

| 项 | 文件 | 内容 |
| --- | --- | --- |
| R1a 执行原则块 | [`skills/dispatcher/SKILL.md`](../../../skills/dispatcher/SKILL.md) | `## 执行循环` 之前新增 `## 执行原则` 四行（角色≠载体 / 载体可有 worktree / 先 foundation 再 fan-out / ready≠执行 dependency），每行指向展开段落 |
| R1b 入口指向 | [`dev-with-track/SKILL.md`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md) 第 3 步、[`impl-package/SKILL.md`](../../../plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md) 路由表、[`handoff-to-new-session/SKILL.md`](../../../skills/handoff-to-new-session/SKILL.md) 与 [continuation 模板](../../../skills/handoff-to-new-session/references/handoff-prompt-template.md) | 形成第一份 brief 前先读四行；continuation card 点名四条 |
| R1c 启动读取减量 | `dev-with-track/SKILL.md` 首段 | 开工只读执行原则；composition-contract / current-state / progressive-system-evidence 改按需 |
| R1d 抽象词加具体句 | `dispatcher/SKILL.md` 并行与复用段 | 「写集不重叠、验证 oracle 互不改变的 lane 可以同时跑」；「`implementation` 边只挡绑定未稳定语义的实现」 |
| R1 处境注入 | [`scripts/situation.py`](../../../plugin-marketplace/plugins/impl-package/scripts/situation.py) | render 结果新增 `hints`（JSON 与人读输出都有）：in_flight 且 runnable 非空 → 「在途 worker 不阻塞独立候选」；`attempt.readiness.all-edges-held` 命中或 withheld 含 implementation-dependency blocker → 「implementation 边只挡实现，只读调研 / child-local 可先做」。`situations.yaml` 的 `all-edges-held` action effect 同步改写 |
| R2 terminal 路由 | `dev-with-track/SKILL.md` terminal 段、`situations.yaml` `terminal-coverage-incomplete` effect、[`do-review/SKILL.md`](../../../plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md) §5 | terminal FAIL 后走 fix + finding-closure，不再起 terminal-final；只在最终 HEAD 再起一次；报告写明复用的 PASS HEAD |
| R3 evidence 模板 | `situations.yaml:223`、[`runtime-protocol.md`](../../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md) | bash `printf` 与 PowerShell `Set-Content` + `Get-Content -Raw` 两种可抄形态；多条一律数组 |
| R4 依赖粒度 | [`impl-planning/SKILL.md`](../../../plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md) 第 6 步、[Ticket 模板](../../../plugin-marketplace/plugins/impl-package/skills/to-tickets/assets/templates/ticket.md)、[`common-misjudgments.md`](../../../plugin-marketplace/plugins/impl-package/skills/impl-planning/references/common-misjudgments.md)、`dispatcher/SKILL.md` 并行与复用段 | 默认 `acceptance`，只有没有上游产物就无法实现且无法 child-local 验证才写 `implementation` 并写出产物；主控核实后可把 package 自写的 `implementation` 边降为 `acceptance` 并记 judgment，升级与 Owner 明示的边归 Owner |
| R5 汇报与轻路径 | [`talk-to-boss/SKILL.md`](../../../skills/talk-to-boss/SKILL.md) 完成条件、`handoff-to-new-session/SKILL.md` 使用前确认 | 仓库状态汇报首段带 worktree / 分支 / HEAD，内部词同句翻译；说明文档请求不走 anchor/continuation |
| R6 旧 profile | [`scripts/codex_setup.py`](../../../scripts/codex_setup.py) | `audit` 把内容等于已管理 profile（去掉 marker 与 name 行）的旧文件报为 `INSTALL-MISMATCH · superseded by <new>`；本机 `backend.toml` / `frontend.toml` 已被报出，删除仍由 Owner 手动 |
| R7 context 卫生 | `dispatcher/SKILL.md` 第 3 步 | 长测试、长驻进程轮询、稳定文档回刷、批量登记核对默认包给 worker |
| evals | `dev-with-track/evals/evals.json` #10、`impl-planning/evals/evals.json` #9 | terminal FAIL → closure 场景；上游只挡验收 → `acceptance` 场景 |

## 验证

| 检查 | 结果 |
| --- | --- |
| 7 个被改 Skill 的 validator（dispatcher、handoff-to-new-session、talk-to-boss、dev-with-track、impl-planning、do-review、impl-package） | 全部 valid |
| `situation.py check` | PASS，51 implemented when keys |
| `tests/test_dispatcher_contract.py`（新增执行原则断言）+ `tests/test_handoff_to_new_session_contract.py`（新增 continuation 指向断言）+ req-align、do-review 三轨、dev-with-track 词汇、stage evals、codex_setup（新增旧 profile 用例）、impl-package agents/plugin、ticket-first | 100 passed |
| `tests/test_impl_package_state.py` + `tests/test_situation_render.py`（新增 hints 用例） | 167 passed，25 subtests |
| 本机 `python scripts/codex_setup.py audit` | 报出 `backend.toml`、`frontend.toml` 两个旧 profile |

## 未做

- review 各轨默认档位、terminal 重登记 runtime 语义、call-grok：按 Owner 决定不动。
- 旧 profile 文件的删除：audit 只报告，不删。
- `~/.codex/AGENTS.md` 的「引用即读本体」一句：用户全局文件，仓库不管。
- 行为层面的验证（Owner 不贴四行时主控是否读原则块、并行度与 profile 是否正确、hints 是否改变动作）只能等下一批 rollout。
