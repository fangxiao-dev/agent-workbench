# Backfill Stable Docs Rubric

## Confirmed preferences

- Audit and the verifier are read-only. Apply records exact approved item IDs, including a uniquely resolved explicit batch approval of the unchanged report. The caller may repair this apply's mechanical errors within the same authorization and verify again.
- A direct “回刷” request or explicit Project Knowledge Manager invocation authorizes non-destructive apply for the candidates audited from that named source; `audit-only` remains read-only, and destructive changes or semantic conflicts still require a separate Owner decision.
- Gate and current package schema enable automatic discovery but are not prerequisites for manual audit of a user-specified completed source.
- Configuration and evidence use explicit repository-relative paths.
- Git commit IDs provide the only version boundary.
- Gate keeps the current readable verdict; Git keeps history.
- Scripts enumerate evidence but do not decide durable truth.

## T7 常见误判分流

- 同一规则只保留一个权威定义，其他位置使用带触发条件的指针。
- 仍会改变执行判断的独特提醒下沉到已有 runbook/reference；`SKILL.md` 只保留阶段动作和阶段级指针。
- 只有不影响执行、仅用于验证模型回归的案例才进入 `evals/`；当前 backfill 没有此类条目，不新增 evals。

## Superseded preferences

- Earlier format migration, binding and audit-only state are retired.
