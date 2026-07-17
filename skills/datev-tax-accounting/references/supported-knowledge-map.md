# 公开规则与当前 Finance 能力对照

## 当前已知链路

```text
Finance-visible OCR / structured source
  -> CanonicalAccountingFactsV1 + evidence + hash
  -> Reviewed facts
  -> versioned policy mapping
  -> resolver / grouping
  -> BookingCandidate
  -> test-only EXTF + manifest + Prüfprogramm evidence
```

## 能力状态语义

| 状态 | 解释 |
| --- | --- |
| `implemented` | 代码和接口已存在，但不自动代表验证通过 |
| `verified-local` | 当前固定 worktree/commit 的 focused tests 和静态验证已通过 |
| `external-acceptance-pending` | 需要税务师、Test Mandant 或真实 provider/consumer 才能验收 |
| `review_required` | 输入或规则不足以安全自动推进 |
| `blocked` | 明确依赖未满足，不能继续该路径 |
| `closed` | 仅当该能力自己的 acceptance gate 全部满足；不能由局部测试代替 |

## 当前证据边界

截至 2026-07-17，最近的 Finance DATEV implementation package 在独立 feature worktree 中记录了：Canonical contract、既有 `CanonicalEvaluation` envelope、Finance OCR-output adapter、package-owned controlled vector，以及 adapter→review→policy mapping→resolver/grouping→BookingCandidate→test-only EXTF conformance。T7/T8 的本地验证已记录为 DONE；税务师 Test Mandant 导入与 expected-field 核对仍是 `0/2`，因此 package 仍为 Active/blocked。

该 evidence 证明的是受控 contract 和后半段链路行为，不是 OCR provider 自动识别、复杂真实票据识别、production DATEV 写入或真实税务正确性。合并到主线后，应把 capability registry 的 evidence pointer 更新到合并后的 commit。

## 当前知识入口

- `docs/domains/finance-assistant/context/datev-accounting/`：DATEV/税务全景、规则边界和来源政策。
- `docs/domains/finance-assistant/module-knowledge/datev-accounting/`：Finance 当前模块意图、行为和能力账本。
- `docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules/`：当前 implementation evidence 和 gate。
- `docs/domains/finance-assistant/implementations/2026-07-16-canonical-accounting-facts-adapter/`：Canonical/OCR adapter 规格输入。
- `docs/domains/finance-assistant/implementations/2026-07-14-datev-kontierung-poc/`：DATEV/EXTF POC 的历史设计与公开年度资料索引。
