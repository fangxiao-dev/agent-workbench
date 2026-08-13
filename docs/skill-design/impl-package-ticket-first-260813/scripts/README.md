# 复现脚本

[evidence/measurements.md](../evidence/measurements.md) 里所有数字的来源。全部只读。

## 输入依赖

脚本里的 rollout 路径与任务包路径是**当时的绝对路径硬编码**，重跑前按需改：

- Codex rollout：`~/.codex/sessions/2026/08/{11,12,13}/rollout-*.jsonl`（5 个，见 `rollout_extract.py` 的 `DEFAULT_FILES`）
- DATEV 包：`kaispan-dev` → `docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import`
- AccountingScope 包：`kaispan-dev` → `docs/implementations/2026-08-10-accounting-scope-policy-ownership`

rollout 与任务包都不在本仓；本目录只保留脚本与结论，不复制原始数据（提取后的 `function_calls.jsonl` 约 13 MB、`records.jsonl` 约 23 MB）。

## 直接读 rollout 的脚本

无需预处理：

```bash
python session_summary.py    # 每 session 的 thread 类型、patch 数、压缩次数、累计 token
python context_profile.py    # 上下文占用峰值、>100k/150k/200k 占比、占用轨迹
python headroom.py           # 每请求增量分位数、段长、交接警告线落地占用表
```

## 需要先提取的脚本

`classify_calls.py` 与 `recovery_tax.py` 读的是提取后的 `function_calls.jsonl`：

```bash
python rollout_extract.py --out analysis_data
# 产出 analysis_data/{function_calls.jsonl,records.jsonl,schema_summary.json}

python classify_calls.py     # 工具调用分类：状态机 CLI / 文档读取 / 实现动作
python recovery_tax.py       # 每 session 到首次真实 dispatch 的调用数
```

两个脚本顶部的 `P` 常量指向 `function_calls.jsonl`，按实际输出位置修改。

## 直接读任务包的脚本

```bash
python er_split.py           # Execution Record 的 checkpoint / judgment token 拆分
```

包纸面规模（measurements §2）与 ER subject 分布（§7）是一次性命令，未单独成脚本：

```bash
# subject 分布
grep -o "^- Subject: .*" <package>/execution/<attempt>/execution-record.md | sort | uniq -c | sort -rn

# typed dependencies
awk '/^## Typed dependencies/{f=1;next}/^## /{f=0}f' <package>/tickets/*.md
```

## token 估算口径

统一为 CJK 字符 ×0.9 + 其余字符 ÷3.6，误差约 ±20%。用于纸面规模与 ER 拆分，不用于 rollout——rollout 的 token 数直接来自 `token_count` 事件，是真实计量。
