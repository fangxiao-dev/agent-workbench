# 四项改进的实施与验收结果

日期：2026-09-10。源码基线：`d25c584c1f623b8b399cee93d1dc1ad1ee8fc576`。

当前状态：四项授权交付均已完成并验收，本轮源码交付 closed；剩余实施项 0、待 Owner 决策项 0。历史诊断仍保留 4 个独立 open finding，未宣称它们已修复。源码已按 Owner 后续授权分主题提交：`32bb5d7`（批量登记）、`d874a20`（兼容性验收）、`ccfb7bf`（审查衔接）。没有运行真实 training、改版本、安装或发布。

## 交付内容

| 项目 | 实际结果 |
| --- | --- |
| Evidence 批量登记 | 现有 `evidence add` 接受单对象或非空数组，旧 `evidence-add` 别名兼容；数组按输入顺序返回 `records`、`added`、`duplicates`。全部合法后一次保存 state、一次刷新投影；非法批次不部分写入，完全重复批次不写入。 |
| 下游兼容性验收 | 在 req-align 原有 Spec 范围识别步骤中，区分修改范围与兼容性验收范围，沿实际受影响的既有消费者到可观察终态；增加正反行为样例，没有新增矩阵或 Ticket 流程。 |
| Delta review 衔接 | 保留每个代码 return 的及时独立审查；无额外 formal requirement 时一名 reviewer，有 requirement 时走 owning workflow，可核验的同增量 formal review 可复用。return 原因分流归 dev-with-track，terminal-final 启动条件唯一落在 do-review。 |
| 有界执行行为诊断 | 四类各取一代表完成证据与投影边界检查；没有复现历史长上下文中的实际工具选择，保留 OF-01..04 四个 open finding，未新增 hook。详见 [诊断结果](execution-behavior-diagnosis.md)。 |

状态写入继续使用现有原子文件替换。state 已保存而 projection 刷新失败时仍报错，通过 `package refresh-progress` 恢复，不将其描述为跨文件事务回滚。claim、revision、environment、timing 和 Gate 的既有验收含义不变。

## 验证证据

各组独立列示，不把 focused 子集、subtests 或诊断回归重复累加为一个总通过数。

| 检查 | 结果 |
| --- | --- |
| `python -m pytest tests/test_impl_package_state.py -q` | **67 passed，23 subtests**。其中批量 focused 子集为 5 passed、12 subtests，已包含在此组内。 |
| `python -m pytest tests/test_ticket_first_contract.py -q` | **16 passed**，保留既有单对象和旧 CLI 入口回归。 |
| req-align、Dispatcher、do-review 三轨、dev-with-track 词汇、SDD retirement 与 stage eval 直接合同 | 主控最终整合后运行，**35 passed**。撤回新增的逐字文案断言后 req-align 仍沿用原有 5 项合同检查，行为判断由下面的独立试用补足。 |
| 四个公开 Skill validator | Dispatcher、req-align、dev-with-track、do-review 均 **valid**。 |
| 独立五场景试用 | **5/5 判断符合预期**：受影响 training 兼容性、纯间距反例、无 formal requirement 的 INCOMPLETE 增量、单 finding closure、稳定安全候选 terminal coverage。 |
| 直接单条/批量对照 | 主控从同一已初始化 fixture 克隆两份，对 **19 条记录** 比较逐条返回与 batch `records`、evidenceIndex、四个 Ticket 完整状态，均相同；两边 Gate 都为 **pass**。 |
| 源码与快照一致性 | runtime 4 文件、Skill 7 文件，主控核对 **11/11 SHA-256 一致**；固定比较点保持基线 `d25c584`。 |

35 项直接合同的复跑命令：

```text
python -m pytest tests/test_req_align_contract.py tests/test_dispatcher_contract.py plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_three_track_contract.py tests/test_dev_with_track_situations_review_vocabulary.py tests/test_subagent_driven_development_contract.py tests/test_impl_package_step8_evals.py::test_stage_evals_are_valid_and_nonempty -q
```

作者在 5 条记录样例中量测到：

| 操作 | 逐条登记 | 批量登记 |
| --- | ---: | ---: |
| 完整状态校验调用 | 15 | 3 |
| state 写入 | 5 | 1 |
| projection 刷新 | 5 | 1 |
| 调用级处境尾注 | 5 | 1 |
| 本机一次样例耗时 | 5.08 秒 | 1.20 秒 |

次数下降对应本次实现目标；一次样例耗时不用于推算真实任务可节省的分钟数。单条和批量都仍需按记录检查字段与证据，批量没有省略验收保护。

## 独立审查与证据范围

- Skill：独立 luna-worker 检查固定 7 文件及直接引用，无 P0/P1/P2 actionable finding；五场景试用是规则判断验证，不是真实训练执行或历史行为复现。
- Runtime：独立 luna-worker 检查固定 4 文件，结论 **PASS，P1/P2 为 0**；另用最小临时仓库确认批次末项 timing 语义错误时返回失败、state 字节不变，未重复整套回归。
- 主控微调：移除逐字镜像文案的新增测试；补清 formal requirement 的派发分支；将 terminal-final 启动条件集中到 do-review。这些内容已包含在 Skill 固定快照和最终 35 项检查中。

本次临时审阅证据保存在 `C:/Users/Xiao/AppData/Local/Temp/execution-skills-260910-2n7qfuz8/`：`runtime-v1.json`、`skills-v1.json` 是路径指纹清单，`runtime-review-result.md`、`skill-review-result.md` 是两份独立审查报告，`check_equivalence.py` / `equivalence-result.json` 是主控单批对照脚本与结果。主控对照 fixture 临时目录已清理，源码快照与审阅材料保留供本次核查；本文件保存关键结论，不依赖临时目录长期存在。

## 独立未决项

历史诊断 OF-01..04 仍开放：已知候选未推进、关联候选进入上下文的过程、中断决定、收尾顺序判断的具体机制没有全部解释。已按每类一次条件恢复尝试停止，既不把未复现当作无问题，也不把当前投影测试通过当作历史问题修复。

这些问题不阻塞本次有界诊断交付；后续若要修复，需新的机制证据与明确的修改范围。
