# Handoff：处境表投递链 → DeepSeek harness 适配

日期：2026-08-19。上一段工作的交接材料，供讨论 DSH 适配的新 session 使用。

## 一、状态快照

- 仓库 `D:\CodeSpace\agent-workbench`，分支 `main`，工作区干净，**47 个提交未推送**。
- 已安装插件 `impl-package@agent-workbench` 的 `gitCommitSha` = `07a6cc5`。
- `07a6cc5` 之后又有三个 DSH 提交（`63a8c41`、`4e53faa`、`c95f1d5`），**尚未安装**。
- 全量测试在 `07a6cc5` 上是 `368 passed`（约 8 分钟）。DSH 三个提交之后未重跑。

## 二、刚落地的是什么：一条三段的投递链

这三段是同一件事，拆开任何一段另外两段都失效。

1. **投递通道**——`trail append` 写 `kind=dispatch` 时必须带一个 `situation.py render` 真发出过的 12 位 digest，凭据落在 `execution/<attempt>/situation-digest.json`，含 render 当时看到的 `state.json` sha256；state 变了则凭据过期。于是「渲染处境」从一个会被跳过的导航动作，变成了派活的前置条件。
2. **防误报的内容**——`git.accepted_seam_changed`：acceptance revision 到 HEAD 之间只有 `docs/` 或 `.md` 改动就不算 seam 变化。缺证据给 **U**。
3. **防漏报的内容**——`attempt.terminal_coverage_complete`：全部 Ticket 终态后，轨迹里必须有覆盖四条 Track 的 `terminal-final` dispatch 行，且这些行记录的 head 到当前 HEAD 之间只有文档改动。缺证据给 **false**。

第 2、3 条共用 `_diff_has_source_changes`，因为「什么算文档改动」必须是同一个定义；但两者默认值方向相反，这是刻意的，不是不一致。

配套：`review_phase`（`initial|finding-closure|terminal-final`）和 `review_track`（`Track A..D`）从各 session 自创的约定变成 `trail append` 校验的封闭词表；旧轨迹里的词表外取值读到时忽略、不报错。

## 三、贯穿这段工作的判断依据

- **载体原则**：不产出物、不产生调用、不派发任何东西的动作，跳过时不留缺口，长跑中必然被剪掉。实测：一次 9.5 小时 session 里 `trail append` 41 次（写入动作），`situation.py render` 2 次（导航动作）。
- **规则和它的执行位置错配**是反复出现的病根，本段之前已命中五次。
- **谁有资格声明**：一个检测器如果只能靠「被它判罚的那一方主动声明」触发，它等于不存在。本段修的两个 fact 都是这个形状。
- **误报比哑火更贵**：P0 层只要有一行长期误报，代价是主控学会忽略整个 P0 层。本段两轮返工都是误报，都是 fixture 抓出来的。

## 四、瘦身之后的开放问题（新 session 的第一件事）

`4e53faa` 把 19 个 SKILL 瘦成 14 个判断启发式文件（-73% 行）。结果：

- `skills/dev-with-track/SKILL.md` 从 93 行变为 **14 行**
- `situation.py render`、`trail append`、`situation-digest`、`host-tools-root` 这四个字符串**在任何 SKILL 文件中出现 0 次**
- 它们现在只存在于 `references/situation-inputs.md` 和脚本代码里

需要确认的是：**这些契约是否被 DSH 的 pre-step hook / typed tools 接住了。**

- 若接住了，这是升级不是退化——hook 会触发，散文不会，正好符合上面的载体原则。
- 若没接住，第一段（投递通道）的交付路径就断了：模型不知道要先 render 再 dispatch，`trail append` 只会在它尝试写 dispatch 时报错，而它可能根本不写。

`references/situation-inputs.md` 不是可靠的替代：实测 6 个 session 共 9 次读取，且逐 session 衰减到 0–1 次。

## 五、待收的读数（都有基线，装完新版后取）

| 读数 | 基线 | 判读 |
| --- | --- | --- |
| dispatch 的 `situation_digest` 覆盖率 | 2/15（grok，9.5h） | 回不到接近满覆盖 = 通道没生效 |
| `terminal-coverage-incomplete` 在非终审阶段出现 | 0 | **出现一次就是回退信号**，闸门又松了 |
| 直接读 `trail.jsonl` 次数 | 115（早期）→ 5（CLI 化之后） | 反弹 = 又在手算 seq |
| `kind=escape` 行 | 8/session（grok）、1/session（codex 早期） | 归零 = 反馈通道死了 |
| 阶段文档纪律 | 6 个 codex 作业里 3 个写了 | 同模型同指令不稳定，属未解决 |

## 六、已知未做的事

- **管不住「派的是不是声明的 leaf agent」**。TAW-05 那次自己捏了三个 `general-purpose` subagent 做终审，`do-review` 在 13 个 prompt 里出现 0 次。新的覆盖判定只看轨迹里有没有四条 Track 的 dispatch 行，写全了就能通过。堵这个要校验派发身份，等真实数据再做。
- **Q3 那 20 处记账漏项**（4 dispatch、3 worker-return、5 escape、7 evidenceIndex、1 ER judgment）没修。它是衰减型：fact 通道开场 7 分钟写了 6 条，之后 9 小时写 1 条。
- **`compaction_pressure.py` 只认 codex 和 grok 两个宿主**（`--host codex|grok|auto`）。DSH 若是第三个宿主，需要新的 reader；输出形状必须保持 `compactions/last_interval_min/shrinking/high/explanation`，下游 `dev-with-track` 的接线才不用改。grok 侧 `last_interval_min` 恒为 `null`（该宿主不提供 compaction 时间戳），这是诚实降级不是缺陷。

## 七、协作约束（沿用）

- 提交直接落 `main`，不要自作主张开分支。
- `D:\CodeSpace\kaispan-dev` 是正在跑的活包，**只读**。
- 有界任务派 codex：`gpt-5.6-luna` + `model_reasoning_effort=max`，允许它用 subagent，要求分阶段落盘（超时才有残值）。默认超时已提到 1800s；本段六个作业里四个撞满 2700s，派发时按任务体量给足。
- 派发前把设计冻死到比派发粒度更细，否则 N 个 worker 会发明 N 套。本段两轮返工都是冻结说明本身写错。
- `tests/fixtures/situations/*/expected.json` 是「哪一行会在什么处境下响」的对账清单，改动处境表或 fact 推导时必须逐个复核，不要整批 checkout 也不要整批保留。
