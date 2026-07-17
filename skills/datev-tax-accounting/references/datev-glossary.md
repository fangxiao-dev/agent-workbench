# DATEV / 税务基础名词表

本表是面向 agent 的短版术语导航，不替代税务师对具体 Mandant、凭证或年度的判断。

| 术语 | 含义 | 在链路中的位置 |
| --- | --- | --- |
| `SKR03` / `SKR04` | DATEV 两套常用标准科目框架；同一业务在两套框架中的账号可能不同 | 选择年度 reference catalog，不等于企业实际 Kontenplan |
| `Kontenrahmen` | 标准科目框架 | 标准参考层 |
| `Kontenplan` | 某个 Mandant 实际启用、改名或定制后的科目集合 | profile-specific policy 输入 |
| `Sachkonto` | 总账科目，用于费用、收入、资产、负债或税务等 | 业务语义和税务情形映射的目标 |
| `Personenkonto` | 具体客户或供应商的明细账户 | Kreditor/Debitor 主数据层 |
| `Kreditor` / `Kreditorenkonto` | 供应商及其应付往来账户 | 供应商稳定身份映射的目标 |
| `Konto` / `Gegenkonto` | 一条分录的主账户和对方账户 | EXTF booking row 两侧；方向作用于 `Konto` |
| `Soll` / `Haben` | 借方 / 贷方 | 由后续会计规则确定，Canonical facts 不直接输出 |
| `Steuerschlüssel` | 描述税务处理的 DATEV 控制码 | 税务规则和 EXTF BU 字段的参考 |
| `BU-Schlüssel` | Buchungsstapel 中的记账税码表示，通常需四位序列化 | 由 policy/tax mode 决定；不是税率的同义词 |
| `Automatikkonto` | 账户功能会触发自动税务处理的科目 | 不能无条件再填普通 BU |
| `Vorsteuer` | 满足条件时可抵扣的进项税 | 票据税务语义，不是额外手工费用行 |
| `UStVA` | Umsatzsteuer-Voranmeldung，增值税预申报 | 税务键影响申报归属的领域 |
| `OPOS` / `Offene Posten` | 未清项 | 正确的 Kreditor 采购分录可形成应付未清项 |
| `Beraternummer` | DATEV 顾问/事务所编号 | EXTF Header 技术输入，需 profile 绑定 |
| `Mandantennummer` | DATEV 客户账套编号 | EXTF Header 技术输入，需 profile 绑定 |
| `Wirtschaftsjahr` | 经济年度 | 影响 Header 和年度税务资料适用范围 |
| `EXTF` | 外部应用生成的 DATEV-Format 标识 | KaiSpan test-only serializer 输出目标 |
| `DTVF` | DATEV 原生导出格式标识 | 可能作为受控输入或 golden reference；不是 KaiSpan 目标输出 |
| `Buchungsstapel` | DATEV 记账批次 | EXTF 的数据对象 |
| `Festschreibung` | 批次是否已锁定 | 测试/草稿输出保持未锁定 |
| `Canonical facts` | 带 evidence、source hash 和确定性 hash 的票据事实 | OCR/结构化输入到 Review 的共同 contract |
| `Reviewed facts` | 人工检查和修订后的不可变事实快照 | 正式会计规则的安全上游 |
| `BookingCandidate` | 准备映射成 DATEV 行的结构化会计候选 | resolver/grouping 到 EXTF serializer 的 seam |
| `test-only` | 仅用于受控测试环境的 policy/EXTF 状态 | 不表示 production-ready 或税务正确 |

## 关键区别

- 税率不是 BU/Steuerschlüssel 的充分条件。
- 标准 SKR 账号名称不是 Mandant 已启用科目的证明。
- Canonical facts 不包含最终 `Sachkonto`、`Kreditor`、`BU` 或 `Soll/Haben`。
- `technical_export_ready` 只表示格式和前置校验通过，不表示会计正确或 DATEV 已成功导入。
