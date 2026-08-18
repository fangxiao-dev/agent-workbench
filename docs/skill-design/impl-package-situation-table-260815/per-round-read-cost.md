# 主控每轮重复读成本调研

> 只读调研；唯一落盘文件。阶段 1、阶段 2、阶段 3 均已落盘；本任务 closed。

## 阶段 1：文件体量分布

### 样本与统计口径

样本是以下四个 checkout 在 2026-08-18 的工作树内容：

| 样本 | package 实例 | 老格式 | 新格式 |
| --- | ---: | ---: | ---: |
| `kaispan-dev` | 18 | 17 | 1 |
| `260809-finance-assistant-mvp` worktree | 20 | 17 | 3 |
| `260813-datev-pdf-ai-form-prefill-planning` worktree | 21 | 17 | 4 |
| `prj-supplyer-webapp` | 33 | 33 | 0 |
| **合计** | **92** | **84** | **8** |

这里按物理 checkout 中的 package 实例统计；同一相对路径在不同 checkout 中各算一个实例，不跨 checkout 去重。package 由 git 可见文件中的 `.impl-package/` 目录反推，目标文件直接读取工作树。新格式按存在 `.impl-package/state.json` 判定；8 个新包的 `formatVersion` 实测为 3.4 或 3.5。没有 `state.json` 的归入老格式。

统计对象是：package 根下的 `execution-findings.md`、`progress.md`，以及 package 根下 `execution/*/execution-record.md` 的全部 attempt 文件之和。某目标文件不存在时按 0 计入“全 package”分布；`execution-record.md` 的“有文件”表示至少有一个 attempt record。

行数使用文本的 `splitlines()` 计数。token 采用可复算的粗估：

```text
estimated_tokens = ceil(non-CJK characters / 4 + CJK characters / 1.5)
```

其中 CJK 取常用中日韩统一表意文字区间；其它字符（英文、数字、空格、标点、Markdown 符号）按 4 字符/token。系数是按常见 tokenizer 的英文约 4 字符/token、中文约 1--2 字符/token 取的工程估算，不等同于实际模型 tokenizer 计费。p90 使用 nearest-rank（排序后取第 `ceil(0.9*N)` 个值）。

### 全 package 分布

表中的行数和 token 均为 `median / p90 / max`；`有文件`是该格式中实际存在该目标文件的 package 数。

| 格式 | 文件 | package 数 | 有文件 | 行数（全 package） | token（全 package） |
| --- | --- | ---: | ---: | ---: | ---: |
| 老 | `execution-findings.md` | 84 | 17 | 0 / 41 / 128 | 0 / 810 / 2,458 |
| 老 | `progress.md` | 84 | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 老 | `execution/*/execution-record.md` 合计 | 84 | 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| 新 | `execution-findings.md` | 8 | 2 | 0 / 129 / 129 | 0 / 1,276 / 1,276 |
| 新 | `progress.md` | 8 | 8 | 33.5 / 37 / 37 | 335 / 525 / 525 |
| 新 | `execution/*/execution-record.md` 合计 | 8 | 8 | 664 / 1,026 / 1,026 | 14,904 / 20,048 / 20,048 |

只看非零样本时，老格式 `execution-findings.md` 为：17 个 package，行数中位数 / p90 / 最大值 `41 / 111 / 128`，token 为 `810 / 2,369 / 2,458`；新格式对应 2 个 package，行数 `89 / 129 / 129`，token `1,153 / 1,276 / 1,276`。新格式的 `progress.md` 和 execution records 全部有文件，因此非零分布与全 package 分布相同。

### 最大 package（按三份目标文件合计 token，物理实例排名）

| 格式 | checkout / package | 合计 token | 合计行数 | findings | progress | execution records | record 文件数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 新 | `260813-datev-pdf-ai-form-prefill-planning` / `docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import` | 20,381 | 1,055 | 0 | 333 | 20,048 | 2 |
| 新 | `260809-finance-assistant-mvp` / `docs/domains/finance-assistant/implementations/2026-08-10-mobile-photo-capture-ocr` | 16,619 | 964 | 0 | 364 | 16,255 | 2 |
| 新 | `kaispan-dev` / `docs/implementations/2026-08-10-accounting-scope-policy-ownership` | 15,239 | 701 | 0 | 335 | 14,904 | 2 |
| 新 | `260809-finance-assistant-mvp` / `docs/implementations/2026-08-10-accounting-scope-policy-ownership` | 15,239 | 701 | 0 | 335 | 14,904 | 2 |
| 新 | `260813-datev-pdf-ai-form-prefill-planning` / `docs/implementations/2026-08-10-accounting-scope-policy-ownership` | 15,239 | 701 | 0 | 335 | 14,904 | 2 |
| 新 | `260813-datev-pdf-ai-form-prefill-planning` / `docs/domains/finance-assistant/implementations/2026-08-15-datev-tax-advisor-import-workbench` | 15,014 | 735 | 1,276 | 525 | 13,213 | 1 |
| 新 | `260813-datev-pdf-ai-form-prefill-planning` / `docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe` | 9,942 | 568 | 1,030 | 276 | 8,636 | 1 |
| 老 | `prj-supplyer-webapp` / `docs/implementations/inventory-manufacture-issues-153-158` | 2,458 | 128 | 2,458 | 0 | 0 | 0 |
| 老 | `prj-supplyer-webapp` / `docs/implementations/release-external-readiness-audit` | 2,369 | 108 | 2,369 | 0 | 0 | 0 |
| 老 | `prj-supplyer-webapp` / `docs/implementations/order-snapshot-reuse` | 2,140 | 111 | 2,140 | 0 | 0 | 0 |

阶段 1 到此为止；阶段 2 将从指定六个 rollout 中统计真实读取动作的次数。

## 阶段 2：真实读取频次

### 识别方法

先复用 `scripts/rollout_pulse.py` 的 `resolve()` 和 `read_rollout()` 定位并逐行解析六个 rollout；没有另写一套 rollout JSONL 解析器。再在其解析出的 `response_item` 中检查实际执行的 `custom_tool_call`（本批相关调用均为 `name=exec`）及其 shell 命令参数。

计数对象是实际把目标文件作为读取/搜索对象的动作：`Get-Content`、`Select-String -Path/-LiteralPath`、`git grep`、输出内容的 `git diff`，以及等价的 `cat`/`sed`/专用读文件工具。一个 pipeline 对同一目标只计一次；同一 JS/tool call 内两个独立 `Get-Content` 分别计数。按 basename 计数，所以不同 attempt 目录下的 `execution-record.md`、`trail.jsonl` 都会计入；`trail.jsonl.lock` 不计入。

排除：prompt/assistant 文本中的文件名、patch/evidence 字符串、`Test-Path`、`Get-Item`、`Get-ChildItem`、`git status`、`git diff --check`，以及 helper 内部隐含读取。`Select-String -Pattern 'trail.jsonl'` 如果实际读取的是别的脚本，也不算 `trail.jsonl`。

因此这里量的是 rollout 中“主控明确发出的文件读取动作”，不是文件名出现次数，也不是 helper 可能在内部做的 I/O。可能漏计的主要是：专用工具把读取封装在不可见的 helper 内、命令通过变量或脚本间接打开目标文件但 rollout 没有展开其内部实现、以及非上述已识别命令形态的读取。`01a011d0` 在前一位 worker 扫描超时后由主 session 用相同入口做了 bounded fallback；其余五个使用 worker 的正式结果。

### 六个 session 的读取次数

| session | 日期 | `execution-findings.md` | `progress.md` | `execution-record.md` | `trail.jsonl` | `situations.yaml` | `situation-inputs.md` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `01a00deb` | 08-17 | 1 | 6 | 2 | 10 | 1 | 7 |
| `01a00e82` | 08-17 | 0 | 1 | 2 | 1 | 0 | 0 |
| `01a00f08` | 08-17 | 0 | 5 | 9 | 6 | 0 | 1 |
| `01a0101a` | 08-17 | 0 | 3 | 10 | 9 | 0 | 1 |
| `01a010e6` | 08-17 | 0 | 3 | 4 | 12 | 0 | 0 |
| `01a011d0` | 08-18 | 0 | 5 | 6 | 77 | 0 | 0 |
| **六 session 合计** |  | **1** | **23** | **33** | **115** | **1** | **9** |

对照结果不是“都接近 0”：`trail.jsonl` 合计 115 次，主要集中在 `01a011d0` 的 77 次；`situation-inputs.md` 合计 9 次，出现在 `01a00deb`（7 次）、`01a00f08`（1 次）、`01a0101a`（1 次）。`situations.yaml` 仅在 `01a00deb` 出现 1 次。也就是说，设计意图在这批真实运行中没有完全落实。

### 频次证据指针

以下 `eN` 是扫描中成功解析记录的 0-based event index，用来复核“次数”不是从文本提及推导出来的：

- `01a00deb`：findings `e1091`；progress `e28,e164,e1161,e2682,e2715,e2849`；trail 主要在 `e147,e352,e1067,e2702,e2723,e2728,e2816,e2838`；situation-inputs 读取分布在 `e105,e366,e790,e2807` 等；`situations.yaml` 为 `e2795`。
- `01a00e82`：progress `e75`；execution records `e79,e1724`；trail `e111`。
- `01a00f08`：progress `e55,e2068,e2642,e3072,e3275`；execution records 9 次分布在 `e55,e1773,e2085,e3072,e3327,e3331,e3340,e3359` 等；trail 主要在 `e148,e400,e1196,e2028,e2041`；situation-inputs 为 `e140`。
- `01a0101a`：progress `e77,e1632,e1962`；execution records 10 次集中在 `e77,e81,e85,e89,e94,e112,e116,e136,e1661,e1962,e1966`；trail 为 `e154,e258,e673,e1048,e1053,e1057,e1511,e1531,e1605`；situation-inputs 为 `e154`。
- `01a010e6`：progress `e125,e372,e3254`；execution records `e125,e129,e3259,e3353`；trail `e134,e580,e701,e751,e823,e953,e1115,e1314,e1403,e1665,e3259,e3314`。
- `01a011d0`：progress `e66,e75,e79,e4340,e4349`；execution records `e266,e1842,e3202,e5136,e6492,e7437`；trail 的读取动作从 `e167` 延续到 `e7311`，包含同一 event 内的两个独立 tail 读取；未发现目标 findings、situations 或 situation-inputs 的直接读取。

阶段 2 到此为止；阶段 3 将把上述次数与阶段 1 的体量估算相乘，并给出是否值得改造的数字判断。

## 阶段 3：每 session 成本估算与结论

### 计算输入与边界

六个 session 的目标路径显示：`progress.md` 与 `execution-record.md` 都在 `2026-08-15-datev-tax-advisor-import-workbench`；`01a00deb` 的 1 次 findings 读取实际来自同一 worktree 下的 `2026-08-12-datev-pdf-ai-form-prefill-probe`，不是 08-15 包的 findings。因此使用的体量是：

| 实际使用的文件 | 行数 | 估算 token |
| --- | ---: | ---: |
| 08-15 包 `execution-findings.md` | 129 | 1,276 |
| 08-15 包 `progress.md` | 34 | 525 |
| 08-15 包 `execution/initial/execution-record.md` | 572 | 13,213 |
| 08-12 包 `execution-findings.md`（仅 `01a00deb`） | 49 | 1,030 |

估算公式是“阶段 1 的文件 token 估算 × 阶段 2 的读取次数”。这是**全量等价 token**，不是每次命令实际返回给模型的精确 token：rollout 中有 `-Tail`、`-First`、`Select-String`、`git grep` 等局部读取，因而下表对真实上下文消耗偏保守；但它正是“文件体量 × 频次”的可比上界。

### 每 session 成本（按文件贡献从大到小排列）

| session | `execution-record.md` | `progress.md` | `execution-findings.md` | 三份合计 token |
| --- | ---: | ---: | ---: | ---: |
| `01a00deb` | 2 × 13,213 = **26,426** | 6 × 525 = **3,150** | 1 × 1,030 = **1,030** | **30,606** |
| `01a00e82` | 2 × 13,213 = **26,426** | 1 × 525 = **525** | 0 | **26,951** |
| `01a00f08` | 9 × 13,213 = **118,917** | 5 × 525 = **2,625** | 0 | **121,542** |
| `01a0101a` | 10 × 13,213 = **132,130** | 3 × 525 = **1,575** | 0 | **133,705** |
| `01a010e6` | 4 × 13,213 = **52,852** | 3 × 525 = **1,575** | 0 | **54,427** |
| `01a011d0` | 6 × 13,213 = **79,278** | 5 × 525 = **2,625** | 0 | **81,903** |
| **六 session 合计** | **436,029** | **12,075** | **1,030** | **449,134** |

按六 session 合计排序：`execution-record.md` 436,029 token（97.08%），`progress.md` 12,075（2.69%），`execution-findings.md` 1,030（0.23%）。

### 三份文件是否值得改造

| 文件 | 判断 | 数字依据 |
| --- | --- | --- |
| `execution-record.md` | **值得** | 33 次读取 × 13,213 token = 436,029，占三份文件估算总量 97.08%；单个 session 最高 132,130 token；样本新包 record 的 p90 为 20,048 token。它是当前可量化的主成本来源。 |
| `progress.md` | **当前不值得优先做全量摘要改造** | 23 次读取 × 525 = 12,075，占 2.69%；六个 session 平均约 2,013 token。即使完全消除，绝对量也远小于 execution records。 |
| `execution-findings.md` | **按本批真实频次不值得单独改造** | 只有 1 次读取，成本 1,030 token，占 0.23%；样本老包有文件样本的 p90 也只有 2,369 token。背景里的“19 条未关闭 finding”说明它可能在别的工作集成为风险，但这六个 rollout 的证据不支持把它列为当前优先项。 |

### findings 摘要不能只保留计数

如果后续因为 findings 频次上升而需要摘要，只有“开放 finding 数量”不足以让主控决定下一步修哪条。每条仍需保留以下可行动字段：

1. 稳定的 finding ID、严重级别/优先级、当前状态（open、blocked、needs-revalidation 或 resolved）。
2. 一句话描述被破坏的 invariant/失败现象，以及影响范围（哪个 package、attempt、Ticket 或共享 seam）。
3. 当前根因判断与下一动作；包括 owner/worker、前置依赖和阻塞原因。否则主控只能知道“有 19 条”，不能挑出先修哪一条。
4. 最小但可回查的证据锚点：命令或测试、文件:行号/ER 或 trail event、以及最后验证的 revision/head。这样摘要不会把已失效证据当成当前事实。
5. 稳定排序键（至少按严重级别、阻塞依赖、更新时间），让摘要每轮变化可解释。

### 是否有比摘要更划算的做法

有，数字上是**少读 execution record**比压缩 `progress.md` 或低频 findings 更划算。作为敏感性场景：如果 execution record 从当前 33 次降到每个 session 只读 1 次，仍保留其它两份文件的现有读取，则 execution-record 成本会从 436,029 降到 `6 × 13,213 = 79,278`，三份文件总量减少 **356,751 token（79.43%）**。这不是实施方案，只说明“减少不必要读取”对当前数据的收益上限明显高于处理 progress/findings。

另外，阶段 2 的两个对照本身是独立发现：`trail.jsonl` 实际读了 115 次，`situation-inputs.md` 读了 9 次，`situations.yaml` 读了 1 次；它们没有纳入上述 449,134 token，因为阶段 1 没有测这几类文件的体量。它们的次数已经足以说明“按设计运行时不该打开”在这批 rollout 中并未完全成立。

## 最终结论

本轮只读调研全部完成：阶段 1 覆盖 92 个 package 实例，阶段 2 覆盖 6 个指定 session，阶段 3 完成 449,134 token 的全量等价估算。数字支持优先关注 `execution-record.md` 的读取行为；不支持为了交付而对 `progress.md` 或 `execution-findings.md` 做当前优先级的摘要改造。没有修改任何样本仓库、package、插件或脚本，也没有 commit。
