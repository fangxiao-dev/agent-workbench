# 方法锚点、项目水位线与来源选择

## 两类锚点

Stable Docs Backfill 必须记录两个不同角色的锚点：

- `Method Activation Ref`：从当前 Plugin `.codex-plugin/plugin.json` 读取的 `plugin name + version`，证明使用哪一版 backfill 方法。本机 Plugin/cache 路径不进入项目历史。
- `Project Source Watermark`：目标项目内最后完成 source disposition 的 commit，是目标项目 Git range 的 exclusive lower bound。

每份 audit 还固定一个目标项目 `Source HEAD`。Project Source Watermark 必须是 Source HEAD 的 ancestor，否则 fail closed。Apply 最多推进到 audit 的 Source HEAD，不使用 apply 时更靠后的 checkout HEAD。Plugin version 不参与目标项目 Git range，Project Source Watermark 也不能充当方法版本。

旧 state 中的 repository-commit Method Activation Ref 只作为 migration provenance 保留。首次 Plugin apply 将当前方法锚点写成 Plugin identity/version；迁移动作本身不得推进项目水位线。

## 配置选择

项目路径差异只由配置声明。用户显式传入 `--config` 时使用该文件；否则读取目标项目根目录 `.stable-docs-backfill.json`。显式配置可位于目标项目外，所有配置内相对路径仍以项目根为基准。缺少配置或配置非法时 fail closed，不从仓库名或历史目录猜测。

## Eligible Sources

稳态 source selection 是：

```text
packages active in (Project Source Watermark, Source HEAD]
UNION
unresolved carry-forward package IDs
```

Implementation Package 根路径来自配置的 `implementationsPath`。`carry-forward` 是已经审计但尚未最终 disposition 的 package。推进 watermark 后仍必须保留这些 package ID；只有后续 audit/apply 明确 applied、rejected、superseded 或 owner-approved no-delta 才能移除。

Collector 必须从完整 Git range 枚举发生过 activity 的 package path。若某个 package 在 Source HEAD 已被删除或改名，必须输出到 `removed_packages` / `eligible_removed_packages`，交给 audit 明确做 tombstone、supersession 或 removal disposition；不得因为它已不在 HEAD inventory 中而静默漏掉。

Bootstrap 不猜测历史下界。它读取 owner 明确批准的固定 source manifest，manifest 记录 Source HEAD、package inventory、排除/fixture 理由和 tree hash。

## Package Activity Ordering

需要确定“最近 N 个 package”时，以固定 Source HEAD 上每个 configured Implementation Package 的最新 reachable Git commit 为 activity commit：

1. commit timestamp 降序；
2. timestamp 相同时 package ID 升序；
3. 不使用目录 mtime、当前 checkout dirty state 或 package 名日期猜测。

## Semantic And Supplemental Inputs

每个 package 的默认 semantic source set 只有 `design.md` 与 `spec.md`（存在时）。所有 tracked `findings.md` 都登记 path、Git identity/hash 和 package，但默认不读取内容。只有 design/spec 含可解析的本地 findings 链接、candidate 存在 evidence gap，或 authority sources 冲突时才读取，并在 audit item 记录 trigger/reason。

`gate.md` 只读取最新 verdict、Durable Deltas 摘要和 source pointer。`pendingPath` 与 commit range 只做覆盖对账。plan、patch plan、DAG、tickets、progress、Execution Record 和 command logs 默认不进入 semantic source set；只有明确 source pointer 无法解析时才定点读取，不扩展为 package 全过程审计。

## Collector Contract

[`../scripts/collect_sources.py`](../scripts/collect_sources.py) 负责机械 inventory，不负责 durable delta 判断：

- Python 3.10–3.12 standard library + Git CLI；
- `--project-root` 是 invocation-local 参数，`--config` 可显式指向外部 profile；
- Plugin identity/version 只从 collector 所属 Plugin manifest 读取；
- 默认 read-only，把 JSON 写到 stdout，diagnostics 写到 stderr；
- `--format markdown` 可输出人读 inventory；
- 只有显式 `--output` 才写文件，且目标必须位于 project root；
- repeated identical inputs 产生 deterministic payload，不含生成时间或本机绝对路径；
- 非 ancestor watermark、未知 carry-forward、路径越界、非法配置或不足的 fixture inventory 全部 fail closed。

示例：

```text
python scripts/collect_sources.py \
  --mode steady-state \
  --project-root <project-root> \
  --config <optional-external-profile> \
  --source-head <project-commit> \
  --project-watermark <ancestor-commit>
```

Collector 输出中的绝对 root 和外部 config path 不持久化；inventory 只保存 Plugin identity/version、项目 repository identity、commits、配置 digest、package IDs、Git tree/blob identities 和项目相对路径。
