# Evergreen Knowledge 与 Backfill

Implementation package 保存一次交付的 Decision、Spec、Plan、执行与 Gate；stable docs 保存当前仍成立的产品语言、架构和行为。两者不能互相替代。

## Durable Delta 流

1. 执行期发现先进入 `execution-findings.md` 或 Execution Record judgment。
2. terminal Gate 前分流：行为合同回 Decision/Spec；长期项目知识登记为 Durable Delta，并写入配置的 `_pending.md` 与 truth pointer/stub；没有增量时记录明确原因。
3. `backfill-stable-docs` 默认从 pending registry 消费；只有 terminal Gate 的 comparison commit 已进入 targetBranch、但没有 pending 登记时才做 gap-catching。
4. audit 只分类；owner 批准精确 item 后 apply；verify 独立检查。移动、删除、重命名或 package retirement 需要额外 destructive authorization。

Git commit ID 是 source/target reachability 与跨 session 比较的唯一版本锚点。Stable docs 不保存 package 文件内容身份，package 也不维护迁移或审计账本。
