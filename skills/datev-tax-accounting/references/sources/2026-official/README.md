# 2026 DATEV 官方公开资料

这些文件来自受控 `Kontierung` 目录中的非个人公开资料，作为 2026 年标准参考基线。文件哈希用于确认版本；它们不代表任何 Mandant 的实际启用科目、Kreditor 或自定义税务配置。

| 文件 | 用途 | SHA-256 |
| --- | --- | --- |
| `11174 SKR03 BilrUg.pdf` | 2026 SKR03 标准科目框架（DATEV Dok.-Nr. 11174） | `FA93F12A1A520DDDC81FD0CEC5179A116C885CDEA4A867DE1BD457B57CE8CBBF` |
| `11175 SKR04 BilrUg.pdf` | 2026 SKR04 标准科目框架（DATEV Dok.-Nr. 11175） | `50AE33016C8CF717FC0615DBEEA727AF612ED9D0BDADD7BD44DE752F76266518` |
| `Steuerschlüssel-Tabelle 2026 im SKR03 und SKR04.xlsx` | 年度 Steuerschlüssel、税率/税务处理和相关提示 | `C81EA8EFCC95D9231C81FC1FE902A3B42AFF05F84B718B535BCCB46BFD5BD45A` |
| `Kontenfunktions-Tabelle 2026 im SKR03 und SKR04.xlsx` | 年度账户功能、允许的税务行为和说明 | `7C83891EA753062E1D89AF2D190B9A93E59332D80C8B5CDE1FDDF038AD32AB8C` |

## 使用边界

技术 EXTF 字段规则以 DATEV Developer Portal 的在线格式规范为准；年度 SKR/Steuerschlüssel/Kontenfunktion 资料只负责标准会计参考。Mandant-specific Kontenplan、Kreditor、KOST、程序版本、Beraternummer 和自定义 Steuerautomatik 必须另行绑定并验证。

年度资料变化后，必须重新计算 source hash、更新适用范围并重跑相关回归；不能仅因为年份相近就复用上一年度的税务规则。
