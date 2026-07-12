# 双锚点与来源选择

## 双锚点

Stable Docs Backfill 跨越方法仓库和目标项目仓库时，必须记录两个不同角色的 commit：

- `Method Activation Ref`：`<repository-identity>@<full-commit>`，证明使用哪一版 backfill 方法。repository identity 是可移植标识，例如 `owner/agent-workbench`；本机 checkout 路径不进入项目历史。
- `Project Source Watermark`：目标项目内最后完成 source disposition 的 commit，是 Git range 的 exclusive lower bound。

每份 report 还固定一个目标项目 `Source HEAD`。Project Source Watermark 必须是 Source HEAD 的 ancestor；否则 fail closed。Apply 最多推进到 report 的 Source HEAD，不使用 apply 时更靠后的 checkout HEAD。

## Eligible Sources

稳态 source selection 是：

```text
packages active in (Project Source Watermark, Source HEAD]
UNION
unresolved carry-forward package IDs
```

`carry-forward` 是已经审计但尚未最终 disposition 的 package。推进 watermark 后仍必须保留这些 package ID；只有后续 report/apply 明确 applied、rejected、superseded 或 owner-approved no-delta 才能移除。

Bootstrap 不猜测历史下界。它读取 owner 明确批准的固定 source manifest，manifest 记录 Source HEAD、package inventory、排除/fixture 理由和 tree hash。

## Package Activity Ordering

需要确定“最近 N 个 package”时，以固定 Source HEAD 上每个 `docs/implementations/<package-id>/` 的最新 reachable Git commit 为 activity commit：

1. commit timestamp 降序；
2. timestamp 相同时 package ID 升序；
3. 不使用目录 mtime、当前 checkout dirty state 或 package 名日期猜测。

## Semantic And Supplemental Inputs

每个 package 的默认 semantic source set 只有：

1. `design.md`（存在时）；
2. `spec.md`（存在时）。

所有 tracked `findings.md` 都登记 path、Git identity/hash 和 package，但默认不读取内容。只有以下触发之一成立时才读取，并在 report item 记录 trigger/reason：

- design/spec 含可解析的本地 findings 链接；
- candidate 存在 evidence gap；
- authority sources 冲突，需要 findings 中的 current evidence 辅助裁决。

`gate.md` 只读取最新 verdict、Durable Deltas 摘要和 source pointer。`_pending.md` 与 commit range 只做覆盖对账。plan、patch plan、DAG、tickets、progress、Execution Record 和 command logs 默认不进入 semantic source set；只有明确 source pointer 无法解析时才定点读取，不扩展为 package 全过程审计。

## Collector Contract

[`../scripts/collect_sources.py`](../scripts/collect_sources.py) 负责机械 inventory，不负责 durable delta 判断：

- Python 3.10–3.12 standard library + Git CLI；
- `--method-root` 与 `--project-root` 是 invocation-local 参数；
- 默认 read-only，把 JSON 写到 stdout，diagnostics 写到 stderr；
- `--format markdown` 可输出人读 inventory；
- 只有显式 `--output` 才写文件，且目标必须位于 project root；
- repeated identical inputs 产生 deterministic payload，不含生成时间；
- 无效 method ref、非 ancestor watermark、未知 carry-forward、路径越界或不足的 fixture inventory 全部 fail closed。

示例：

```text
python skills/backfill-stable-docs/scripts/collect_sources.py \
  --mode bootstrap \
  --project-root <project-root> \
  --source-head <project-commit> \
  --project-watermark <ancestor-commit> \
  --method-root <agent-workbench-checkout> \
  --method-ref owner/agent-workbench@<method-commit> \
  --fixture-count 5
```

Collector 输出中的绝对 root 不持久化；manifest 只保存 repository identity、commits、package IDs、Git tree/blob identities 和相对路径。
