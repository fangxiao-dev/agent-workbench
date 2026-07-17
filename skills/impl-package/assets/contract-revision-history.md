# Impl-Package Contract 修订摘要

本文件是升级参考，不是运行时状态，也不是逐包迁移日志。正常使用 Impl-Package 或 backfill 时不要读取；只有 contract preflight 判定任务包低于当前版本时，agent 才读取相关条目，并结合当前模板、schema 和任务包实际内容自行完成改造。

## 3.0 基线

- 现行 v3 体系的统一基线；历史上不同 JSON 曾使用独立整数 `schemaVersion`，这些编号不再作为升级依据。
- runtime state、revision binding、gate content binding、中文唯一 projection 和 backfill 四类识别已存在，但部分实现仍保留旧 schema/legacy heading 兼容分支。

## 3.1

- 所有活动契约改用统一字符串 `contractVersion: "3.1"`；版本检测以 package 当前内容现场推导，不落盘 published/migration 状态。
- 旧 runtime/revision schema、`migrate`、`migrationRequired` 和 `legacy-heading` fallback 不再是可消费输入；旧包须先直接整理成 3.1，再运行 stage 或 backfill。
- backfill 纳入 Impl-Package 目录与路由，先执行可写 contract preflight，校验通过后才执行只读 audit/apply/verify。
- 新任务包从创建起只生成 current projection；机器重复字段、旧 revision header 和兼容摘要不迁入新包。
