# 试运行读数说明

本页规定 bookkeeper 试运行要算哪几个数、怎么算、以及各自指向什么结论。**阈值在试运行开始前写定**，事后不调整——否则读数会退化为对既有倾向的事后合理化。

数据来源：`<package>/execution/<attempt>/bookkeeper-receipts.jsonl`，由 bookkeeper 每次回执追加一行，格式见 `skills/standing-bookkeeper/references/role.md` 更新循环第 6 步。

未来 session 消费这批数据只需读该文件与本设计目录，不需要聊天记录或 session id。

## 重要前提：跑的是 §19 之前的形态

`impl-package-standing-bookkeeper-skill-design-260814.md` 第 19 节的 bounded write unit（主 thread 填 `artifact / section / operation`、`NEEDS_SPLIT`、`unexpected paths` 回执）**尚未实施**。现役 skill 仍是更早的形态：

- 主 thread 给自然语言更新（结论 / 依据 / 依赖）；
- **bookkeeper 自己按 owning stage 规则定位写入位置**；
- 回执为「理解 / 写入 / 验证 / 阻塞」四行。

因此试运行不是在检验 §19.4，而是在产出**决定要不要实施 §19.4** 的数据。这与 [README 第 12 节](README.md#12-与-standing-bookkeeper-设计的关系)的判断方向一致：定位是路由问题，交给被委派的一侧更省；现役形态恰好已经是这样。

## 四个读数

| # | 读数 | 怎么算 | 指向什么 |
| --- | --- | --- | --- |
| R1 | **定位错误率** | 需要 correction event 的次数 ÷ 总回执数。回执 `paths` 与主 thread 复核后认定的目标不符即计入 | bookkeeper 自主定位是否可靠 |
| R2 | **握手频率与阻塞时长** | `dep=true` 的占比；每条从主 thread 发起到回执的时间差之和 | `依赖：是` 是不是无谓的同步点 |
| R3 | **越界写入次数** | `paths` 超出本次更新应触及范围的次数 | 现有边界够不够，是否需要 §19.5 的 `unexpected paths` 校验 |
| R4 | **落盘漏记率** | 见下 | 显式写行这条纪律在真实使用中守不守得住 |

### R4 的交叉校验

漏记率没有自述来源——bookkeeper 漏写一行时不会有人报告。用地面真相取下界：

```text
git log 中该 package 目录的改动次数（排除主 thread 自己的提交）
  对比
bookkeeper-receipts.jsonl 的行数
```

package 文件动了但 jsonl 没有对应行，即漏记。这与 thread-harness 的 `dispatches_since_progress` 是同一手法：证明不了每条记录为真，但能让"记了却没发生"和"发生了却没记"变成可见信号。

## 阈值与结论映射

| 读数 | 阈值 | 结论 |
| --- | --- | --- |
| R1 | **> 20%** | bookkeeper 自主定位不可靠，§19.4 把定位推回主 thread 有理由实施 |
| R1 | **< 10%** | 自主定位可靠，明确不实施 §19.4，[README §12](README.md#12-与-standing-bookkeeper-设计的关系) 的吸收判断成立 |
| R2 | `dep=true` **> 50%** 且事后判断多数不必等 | 握手确实是无谓同步点，按前沿写入 / 追溯写入划分替换 |
| R3 | **> 0** | 补 `unexpected paths` 校验；具体形态按实际越界样态定 |
| R4 | **> 30%** | 显式写行撑不住，处境表首版需重新考虑 [README §10.2](README.md#102-首版不改动-impl_package_statepy) 的"不改 state.py" |

R1 落在 10% 与 20% 之间时不下结论，继续跑或扩大样本。

## 样本量

回执数少于 20 条时任何结论都不成立，只能作为形态可用性的定性反馈。这一条同样在开跑前写定。
