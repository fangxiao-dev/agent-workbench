# DATEV / 税务知识来源政策

## 来源等级

| 等级 | 来源 | 可支持的结论 | 不能单独支持 |
| --- | --- | --- | --- |
| `official-format` | DATEV Developer Portal、官方格式资料、官方 Prüfprogramm 说明 | EXTF 结构、字段顺序、编码、格式版本、工具行为 | 某个 Mandant 的最终会计归属 |
| `official-annual` | DATEV 年度 SKR、Steuerschlüssel、Kontenfunktion 资料 | 标准年度科目、税务键和账户功能参考 | Mandant 自定义启用范围、Kreditor 或 override |
| `mandant-controlled` | 受控 Kontenplan、Kreditor、Mandant 设置、Berater 提供的导出 | 该 profile 的实际配置事实 | 其他 Mandant 或其他年度 |
| `berater-approved-policy` | 明确批准的版本化 mapping/policy | 允许 runtime 选择的最终映射和导出范围 | 未绑定 profile/年度/来源 hash 的泛化规则 |
| `implementation-evidence` | 代码、共置测试、manifest、review、gate | KaiSpan 已实现和已验证到的能力 | 税法正确性或真实 DATEV 导入成功 |
| `controlled-fixture` | 脱敏、版本化、hash-bound 的测试向量 | contract、lineage、grouping 和 test-only 输出的回归行为 | 真实 OCR provider 能力、生产会计正确性 |

冲突时按适用范围优先，而不是按文件新旧盲选：官方格式规则约束物理输出，年度官方资料约束标准参考，Mandant-controlled 配置约束该客户实际设置，berater-approved policy 才允许自动最终 mapping，implementation evidence 只说明产品行为。

## 适用范围元数据

一条规则至少登记 `jurisdiction`、`effectiveFrom/effectiveTo`、`wirtschaftsjahr`、`skr`、`profile`、`authorityClass`、`sourceVersion` 和 `sourceSha256`。特殊 Steuerschlüssel 还要登记所需 DATEV 程序版本；无法确认时进入 `review_required`。

## 复制与隐私

可以复制公开、非个人的 SKR03/SKR04 定义和年度官方表。不要复制 Mandant-specific Kontenplan、Kreditor、BWA、DTVF、发票正文、VAT-ID、联系方式、凭据或其他敏感身份信息。受控 fixture 只保留脱敏字段、source hash、evidence anchor 和必要的 lineage。

## 运行时安全边界

Wiki 或 Skill 文本不会直接驱动会计入账。runtime 只能消费带版本、适用 profile、来源 hash 和批准状态的 policy/registry。未知版本、无唯一 mapping、身份冲突、税务情形不完整或证据链断裂都必须 `fail_closed` 或 `review_required`。
