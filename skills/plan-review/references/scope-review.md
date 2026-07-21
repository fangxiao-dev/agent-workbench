# Scope Review

## 检查

- 先做 freshness gate：确认计划声明的目标路径与 contract 仍存在、尚未被实施或 supersede，并与当前 branch/HEAD 和 active/deprecated 状态相符；历史计划不能被默认为当前 implementation-ready。
- 从目标及必要 design/spec 中提取目标、验收条件、已接受约束、已定 contract 和明确非目标；计划改变或绕过它们时形成 conflict candidate，不能默认为工程自由度。
- 找出仓库中已经存在且可以复用的能力、contract、脚本、测试资产或发布路径；把结果归入 `What already exists`。
- 判断计划是否覆盖最小完整变更，而不是只实现 happy path 或留下无法验收的半套接线。
- 检查 TODO、前置依赖、迁移窗口、owner 边界和与既有 design/spec 的范围冲突；列出所有真实消费者、跨平台镜像和仍依赖旧布局或旧 contract 的入口。
- 当计划删除、重命名或替换 CLI、schema、文件布局、API 或持久化格式时，要求明确兼容、迁移、拒绝或归档策略，不能把手工修复留给实施者猜测。
- 把延期或明确不做的内容归入 `NOT in scope`，写出理由、当前影响及其不阻塞当前交付的依据；仅对 material 或可能长期滞留的延期按需说明 owner/destination 与重新进入条件。
- 对新技术或自建基础设施先检查平台内建能力、仓库现有实践和已知 footgun。只有结论依赖可能变化的外部事实时才查询权威来源。
- 仅当计划触及已知 regression、revert、incident 或已定迁移决定时，按需检查相关 history；发现静默推翻既有 contract 时形成 candidate，不执行无关的全量历史搜索。

## Distribution

当计划新增 binary、package、container、desktop/mobile app、plugin 或其他可分发 artifact 时，检查 build、publish、目标平台、安装/升级和 CI/CD。延期项必须显式进入 `NOT in scope`，不能静默遗漏。

## 输出

只输出能改变范围、验收或实施方式的 candidates，以及简短的 `What already exists` 和 `NOT in scope`。不要用固定文件数或 class 数量强迫拆分；根据 contract 数量、跨边界影响、不可逆性和验证成本判断。
