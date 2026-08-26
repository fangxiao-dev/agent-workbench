# Tax treatment 与期间证据门槛

本文不建立完整税法百科，只记录最容易被票面税率或日期误导的判断门槛。

## 税率不能唯一决定 treatment

- 普通国内 Vorsteuer 不只要求票面出现 7%/19%。§ 15 Abs. 1 Nr. 1 UStG 要求该税为其他企业向本企业提供的、法律上应付的税，并持有符合 §§ 14、14a 的 Rechnung。金额能对上不能替代这些身份、用途和发票证据。
- `0 %` 不是一个唯一 tax treatment。它可能来自明确的零税率规则，也可能是 steuerfrei、nicht steuerbar、§ 13b、innergemeinschaftlicher Erwerb、Einfuhr 或证据缺失。至少要识别交易方向、供需双方所在地/身份、货物或服务地点、USt-IdNr.、发票税务措辞及法条依据；缺少唯一依据时保持未决。
- § 13b UStG 由 Leistungsempfänger 承担税债，innergemeinschaftlicher Erwerb 由 § 1a UStG 定义；两者都有专用 DATEV Steuerschlüssel，不能复用普通国内 Vorsteuer `8`/`9`。
- Steuerbefreiung 与 Vorsteuerabzug 不是同义关系。§ 15 Abs. 2 原则上排除用于 steuerfreie Umsätze 的 Vorsteuer，Abs. 3 又规定例外；看到“steuerfrei”不能直接推导“无 Vorsteuerabzug”或反之。

## 日期不能只看 Rechnungsdatum

- Sollversteuerung 下，§ 13 Abs. 1 Nr. 1a UStG 通常以 Leistung ausgeführt 所在的 Voranmeldungszeitraum 为税款发生期间；提前收款对已收部分另有规则。
- Istversteuerung 下，§ 13 Abs. 1 Nr. 1b 以 Entgelt vereinnahmt 所在期间为准。
- innergemeinschaftlicher Erwerb 按 § 13 Abs. 1 Nr. 6 以 Rechnung Ausstellung、最迟以下一个月期末为发生时点。
- 因此 Rechnungsdatum、Leistungsdatum/-zeitraum、Zahlungsdatum 和 Buchungsperiode 承担不同作用。跨月或跨年时必须先确定适用税务期间，再选择对应 Wirtschaftsjahr 的 Steuerschlüssel/Kontenfunktion 资料；不能仅因发票创建于某年就静默套用该年规则。

## 来源

- [§ 13 UStG — Entstehung der Steuer](https://www.gesetze-im-internet.de/ustg_1980/__13.html)
- [§ 15 UStG — Vorsteuerabzug](https://www.gesetze-im-internet.de/ustg_1980/__15.html)
- [§ 1a UStG — Innergemeinschaftlicher Erwerb](https://www.gesetze-im-internet.de/ustg_1980/__1a.html)
- [§ 13b UStG — Leistungsempfänger als Steuerschuldner](https://www.gesetze-im-internet.de/ustg_1980/__13b.html)
- [§ 4 UStG — Steuerbefreiungen](https://www.gesetze-im-internet.de/ustg_1980/__4.html)
- DATEV 年度 Steuerschlüssel 与 Kontenfunktion 资料：[`sources/2026-official/README.md`](sources/2026-official/README.md)
