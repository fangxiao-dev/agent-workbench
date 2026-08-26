# 账户功能与 Steuerschlüssel 决策边界

适用范围：德国 Regelbesteuerung、Wirtschaftsjahr 2026、SKR03/SKR04。本文只说明公开年度规则的组合边界；Mandant 的最终可用科目和税键仍以其已批准 Profile/Policy 为准。

## 决策顺序

1. 先确定税务情形，再看税率。`7 %` 或 `19 %` 本身不能排除 § 13b、innergemeinschaftlicher Erwerb、Steuerbefreiung 或其他专用情形。
2. 再读取目标 Sachkonto 的 Kontenfunktion。2026 Kontenfunktions-Tabelle 将 Zusatzfunktion `V` / Hauptfunktion `AV` 定义为自动计算 Vorsteuer；`AV 30 001, AV 30 190` 对应德国 19%，`AV 30 002, AV 30 070` 对应德国 7%。这是账户行为，不是普通税键建议。
3. 与税务情形兼容的 `AV` 账户默认让账户功能计算 Vorsteuer。DATEV 将 Berichtigungsschlüssel `4` 单独定义为“Aufhebung der Automatik”；因此不能仅因票面税率为 7%/19%，再把同一自动账户改写成普通 Steuerschlüssel `8`/`9`。
4. 只有目标账户不承担相应 Steuerautomatik、且情形已确认为普通国内可抵扣 Vorsteuer 时，才按 2026 Steuerschlüssel-Tabelle 使用 `8 = Vorsteuer 7 %` 或 `9 = Vorsteuer 19 %`。
5. § 13b、EU、steuerfrei、nicht steuerbar、Aufteilung 或 Berichtigung 使用各自的专用 Steuerschlüssel/功能组合；不得把 `8`/`9` 当作所有含税采购的兜底。

## 2026 可核对锚点

| 公开年度语义 | 官方资料位置 |
| --- | --- |
| `8` = Vorsteuer 7%，示例标准科目 SKR03 3300 / SKR04 5300 | `Steuerschlüssel-Tabelle 2026...xlsx`, `Tabelle1!A9:L9` |
| `9` = Vorsteuer 19%，示例标准科目 SKR03 3400 / SKR04 5400 | 同文件，`Tabelle1!A10:L10` |
| `V` / `AV` = automatische Vorsteuer | `Kontenfunktions-Tabelle 2026...xlsx`, `Legende!A5:C7` |
| `AV 30 001/190` = DE 19%；`AV 30 002/070` = DE 7% | 同文件，`DE Regelbesteuerung SKR03_SKR04!A168:N169` |
| `AV 30 900` = DE 0% Photovoltaik | 同文件，`DE Regelbesteuerung SKR03_SKR04!A170:N170`；这是专用情形，不能泛化成所有 0% |

## 来源

- 本 Skill 内复制的 DATEV 2026 官方年度表及其 SHA-256：[`sources/2026-official/README.md`](sources/2026-official/README.md)。
- DATEV 对 Kontenfunktionen、Steuerschlüssel 和 Berichtigungsschlüssel 的公开说明：[Erläuterungen zu den Kontenfunktionen](https://www.datev.de/content/dam/markenassets/themen-und-produktgruppen/zielgruppen/zielgruppenuebergreifend/shop-assets/rechnungswesen/kontenrahmen/10136_HGB_SKR_04_McDonalds_2026.pdf)。
