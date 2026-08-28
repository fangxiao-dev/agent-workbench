# DATEV导出材料与证据能力

本参考用于盘点一个Mandant的DATEV导出材料、准备Profile/Policy输入，或判断某份报表能证明什么。它描述常见DATEV Rechnungswesen导出物的字段能力和证据边界；实际列名、页数和报表组合会随DATEV版本、配置与导出选择变化。

它不是Mandant Policy。材料只能提供配置事实、历史使用证据或汇总校验；最终`Sachkonto`、`Kreditor`、`taxMode`和`BU/Steuerschlüssel`仍须由适用年度的受控Profile/Policy唯一决定。

## 证据分层

| 层级                    | 回答的问题                                                  | 典型材料                           |
| ----------------------- | ----------------------------------------------------------- | ---------------------------------- |
| Identity                | 这是哪个Berater/Mandant、年度、SKR、币种和法律主体？        | Mandantenstammdaten、导出header    |
| Master data             | 哪些Sachkonto/Kreditor存在，具有什么source behavior和状态？ | Kontenplan、Kreditorenstamm        |
| Transaction evidence    | 历史上何时以什么Konto/Gegenkonto、BU、税率和文本记过账？    | DTVF Buchungsstapel、Kontenblätter |
| Aggregate corroboration | 逐笔材料是否漏科目/月份，费用结构和VAT总额是否合理？        | SuSa、DATEV月度Auswertung报表包    |
| Document evidence       | 真实票据呈现了什么供应商、行项目、税率和税务提示？          | 发票、Gutschrift及其他原始凭证     |

前两层定义或约束Profile目录，第三层支持mapping调查，第四层只做覆盖和合理性校验，第五层支持票据事实与真实链路验收。任何单一层都不能独立替代完整Profile authority。

## 材料能力矩阵

### Mandantenstammdaten与导出header

常见可用字段：

- `Beraternummer`
- `Mandantennummer`
- Wirtschaftsjahr/期间
- 法律名称
- SKR/Kontenrahmen（必须有明确来源）
- 币种与账号长度（需要明确确认；不能因常见值而默认）

能力：建立Profile logical identity、材料期间和source lineage，并交叉检查不同导出是否属于同一账套。

边界：标题或账号段只能提供线索；SKR、币种、法律/税务主体等关键identity需由明确配置或owner确认。

### Kontenplan / Sachkontenstamm

常见可用字段：

- `Konto von` / `Konto bis`
- `Beschriftung`
- `Kontenzweck`
- `FE`
- `Funktion`
- `HFTyp`
- `Zusatzfunktion`
- source status

能力：

- 保留exact/range source identity；
- 判断账号是否属于Profile目录；
- 提供Profile search label/purpose；
- 提供Automatikkonto、fixed-rate或其他账户功能的source evidence；
- 支持active/inactive/excluded coverage检查。

边界：range不展开成虚构single rows，不填补gap。标准label、FE或Kontenfunktion仍须与适用年度reference和runtime policy共同使用，不能单独决定最终tax treatment或BU。

### Kreditorenstamm / Personenkontenstamm

常见可用字段：

- `Konto`
- account type（例如raw `K/I`）
- `Beschriftung`
- `Kurzbezeichnung`
- `Alternativer Suchname`
- source status与修改日期
- 地址、USt-IdNr.、银行字段等敏感附加列

能力：形成Profile-bound Kreditor catalog，支持名称召回、人工选择和服务器exact active revalidation。

边界：名称唯一不等于供应商identity已确认。Profile构建通常只需要账号、名称/简称、状态与source lineage；地址、联系方式、USt-IdNr.、IBAN等敏感字段按最小化原则处理，不进入仓库或普通日志。

### DTVF Buchungsstapel

常见可用字段：

- Konto、Gegenkonto
- BU-Schlüssel
- Belegdatum、Leistungsdatum、税务期间
- Umsatz、Soll/Haben、WKZ
- Buchungstext、Belegfelder
- Steuersatz
- EU/§13b相关字段
- KOST1/KOST2
- GU、Festschreibung、batch/GUID lineage

能力：提供批次视角的逐笔历史mapping evidence；可观察Sachkonto/Gegenkonto、BU、税率、期间和业务文本之间的组合，并识别付款、收入、期初、工资、现金调整或更正候选。

边界：出现频率不能单独晋级为Policy。更正、Generalumkehr和多腿事件需先重建；税率数字不能单独决定`domestic_vat`、§13b、EU acquisition或其他tax treatment。

### Kontenblätter / Kontenstapel

常见可用字段：

- Konto sheet/block identity
- Datum、Leistungsdatum
- BU、Gegenkonto
- Buchungstext、USt%
- Belegfelder
- Soll/Haben、WKZ
- KOST与batch identity

能力：提供以单个Sachkonto为中心的逐笔时间线，适合核对某科目的实际Gegenkonto、BU、税率、周期和更正历史。

边界：它通常比汇总报表更细，但未必更全；导出可能只覆盖选中的Konto或截止日期。用SuSa和DTVF检查其科目/期间覆盖，不把文件名cutoff当成唯一事实。

### SuSa（Summen- und Saldenliste）

常见可用信息：

- 科目期初余额
- 月度/累计借贷发生额
- 期末余额
- 期间和实际使用科目范围

能力：检查逐笔导出是否漏科目或漏月份，确认费用科目是否真实使用，并做账户级总额reconciliation。

边界：SuSa没有足够的单笔供应商、Gegenkonto、BU和票据关联，不能独立生成Category→Sachkonto规则。

### DATEV月度Auswertung报表包

`Auswertung.pdf`通常是一个组合包，不应笼统等同于BWA。一个月度包可能包含：

| 组成                                    | 提供的信息                                            | Profile/Policy加成                   |
| --------------------------------------- | ----------------------------------------------------- | ------------------------------------ |
| Betriebswirtschaftlicher Kurzbericht    | 经营指标、收入/成本概览和文字说明                     | 理解经营结构和异常变化               |
| Kurzfristige Erfolgsrechnung（KER/BWA） | 当月和年累计的收入、Wareneinsatz、费用和结果分类      | 确定主要费用族与调查优先级           |
| Vorjahresvergleich                      | 当前期与上年同期差异                                  | 识别季节性和显著变化                 |
| Wertenachweis zur KER                   | BWA分类背后的具体Sachkonto和金额                      | 将经营类别与实际科目族交叉核对       |
| Wertenachweis zum Vorjahresvergleich    | 当前/上年具体科目差异                                 | 发现新增、停用或异常波动科目         |
| Jahresübersicht                         | 各类别的月度序列和累计                                | 检查月份覆盖、趋势和source cutoff    |
| Umsatzsteuer-Voranmeldung               | 月度VAT申报汇总                                       | 确认申报期间和总体税务结构           |
| UStVA-Verprobung                        | VAT税基、税额、科目交通额和Vorsteuer/Umsatzsteuer核对 | 发现总体税率、税额或科目方向明显失真 |

能力：把经营结构、科目组成、月份趋势和VAT汇总放在同一月度材料包中，用于交叉验证逐笔mapping调查。

边界：不同月份的页数和组成可能变化，应按页标题分类。BWA、Jahresübersicht、UStVA和Verprobung均为汇总视角，不能反推某张发票的最终Sachkonto、BU或tax treatment。

### 真实票据与特殊税务样本

常见可用事实：供应商原文、票据方向/类型、日期、行项目、金额、VAT rate、税务notice和证据位置。

能力：验证OCR→Review→Profile mapping→Formal→EXTF的真实入口，并为0%、§13b、EU acquisition、Gutschrift等逐类treatment调查提供票据事实。

边界：票据自身不定义Mandant Kontenplan或历史mapping；相同税率可以对应不同tax treatment，必须与Profile和税务证据共同判断。

## 最低材料包

准备一个普通支出MVP Profile/Policy，至少需要：

1. 一份可确认Berater/Mandant、年度、SKR、币种、账号长度和法律主体的identity材料；
2. 目标年度Kontenplan/Sachkontenstamm；
3. 目标年度Kreditorenstamm；
4. 至少一种逐笔历史来源：DTVF Buchungsstapel或Kontenblätter；
5. 适用年度/SKR的批准reference release或等价权威来源。

材料少于该集合时，收窄可发布规则：缺少可靠Sachkonto mapping时使用`manual_required`，缺少唯一tax treatment时保持review/blocker。材料缺口不由频次、标准SKR label或模型建议补猜。

## 推荐增强材料

有条件时同时取得：

- DTVF与Kontenblätter两种逐笔视角；
- 连续月份的SuSa；
- 月度Auswertung完整包，尤其Wertenachweis和UStVA-Verprobung；
- 更长且cutoff明确的历史期间；
- 代表性普通7%/19%支出票据；
- 希望支持的0%、§13b、EU、Gutschrift等特殊样本及对应历史入账。

这些材料提升覆盖、冲突发现和真实验收能力，但不会把观察证据自动升级为最终Policy。

## 提炼与隐私

将原始材料留在受控位置，只把以下内容带入builder或调查产物：

- material class、report ID、期间和source cutoff；
- exact/range或Kreditor record identity；
- 必要的source behavior字段；
- 脱敏且可追溯的mapping evidence；
- conflicts、exclusions和批准状态。

完整账簿、供应商联系方式、银行字段、税号、发票正文和明文booking text不进入Skill、仓库或普通日志。对外汇报材料能力时列字段类别和证据作用，不复制Mandant-specific rows。
