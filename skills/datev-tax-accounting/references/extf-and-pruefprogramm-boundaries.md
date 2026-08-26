# EXTF 与 Prüfprogramm 证据边界

## Prüfprogramm 能证明什么

- DATEV 将 Prüfprogramm 定位为对 CSV 的技术校验，重点包括格式版本、Header、字段长度、字符集、必填字段和表达式约束。
- `Headermeldungen: 0` / `Datensatzmeldungen: 0` 只表示该文件在所用 Prüfprogramm 版本下没有被检出的 Header/记录级技术错误。
- 该结果不证明 Sachkonto、Kreditor、Steuerschlüssel、税务期间、Vorsteuerabzug 或业务分类在专业上正确，也不证明 Mandant 已实际导入或记账。

## 传输、校验与会计正确性分层

| 证据 | 最多支持的结论 |
| --- | --- |
| Serializer/fixture test | 生成逻辑满足自身结构合同 |
| Prüfprogramm 0/0 | CSV 通过该工具覆盖的技术规则 |
| Buchungsdatenservice 接收 | 传输和基础 Header 校验成功；DATEV 明确说明这不等于完整 CSV 校验 |
| DATEV App 导入成功 | 文件可被目标应用处理 |
| 税务师/批准 Policy 核对 | Mandant-specific 会计与税务语义被确认 |

这些结论不能互相升级。尤其不能从“Prüfprogramm 0/0”推导 `export_ready` 的专业会计含义。

## 与 Buchungsstapel 期间有关的技术约束

- DATEV Header 是 CSV 第一行，并携带 WJ-Beginn、Sachkontenlänge、`Datum von` 与 `Datum bis`。
- DATEV 建议按 Buchungsperiode 分别生成 Buchungsstapel 文件；Header 期间正确不替代对每条凭证税务期间的专业判断。

## 来源

- [DATEV Developer Portal — Header](https://developer.datev.de/de/file-format/details/datev-format/format-description/header)
- [DATEV Developer Portal — Buchungsstapel](https://developer.datev.de/de/file-format/details/datev-format/format-description/booking-batch)
- [DATEV Developer Portal — accounting:extf-files interface requirements](https://developer.datev.de/de/product-detail/accounting-extf-files/2.0/documentation/interface-requirements-file)
