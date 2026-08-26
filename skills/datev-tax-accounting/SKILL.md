---
name: datev-tax-accounting
description: Use whenever a task involves German DATEV accounting, SKR03/SKR04, Kontenplan, Sachkonto, Kreditor, BU/Steuerschlüssel, VAT treatment, Mandant accounting profiles, EXTF, Prüfprogramm, or the Finance invoice-to-DATEV chain. Route the question through the DATEV/tax wiki and the current Finance capability ledger; distinguish normative tax knowledge from tenant configuration and implemented runtime behavior; fail closed instead of guessing.
compatibility: Requires access to the KaiSpan Finance current-knowledge routes when assessing implementation status. Bundled public 2026 DATEV references are a baseline, not a substitute for a Mandant-specific approved policy.
---

# DATEV Tax and Accounting Knowledge

## 定位

本 Skill 是面向德国税务师与 DATEV 工作域的客观专业知识库及查询协议。它的知识上限来自版本化的官方/专业来源、适用法域与年度，以及经批准的 Mandant Profile/Policy；用于回答规则是什么、需要哪些事实、适用边界在哪里，并形成可审计的专业推理，而不是描述某个软件当前已经实现了什么。

KaiSpan 的 Spec、capability registry、代码和测试只在问题明确询问“当前系统能力或行为”时作为实施证据读取。它们不能反向定义、缩减或改写 DATEV/税务知识；当客观专业规则超出当前实现时，分别报告专业结论与实现缺口。

本 Skill 不提供无边界的税务法律意见，也不替代 Mandant 的 runtime accounting policy。具体 Mandant 的最终 `Sachkonto`、`Kreditor`、`BU/Steuerschlüssel` 或导出结论仍须由适用且经批准的 Profile/Policy 唯一确定。

## KaiSpan routing (conditional)

For KaiSpan work, start with `docs/domains/finance-assistant/context/datev-accounting/README.md`, then read only the owner document needed by the question:

- workflow, field authority, EXTF registry, correction, draft/export semantics, or audit/UI wording: read the DATEV module PRD and Spec plus `context/datev-accounting/workflow-and-field-authority.md`;
- Category/Taxonomy, Kreditor, 0%, KOST, or Sachkonto recommendation: read `terminology-and-rules.md` plus `business-classification-and-tax-boundaries.md`;
- current implementation, verification, external acceptance, readiness, or closure claim: read `module-knowledge/datev-accounting/capability-registry.yaml` first, then its cited evidence only if needed;
- executable mapping for one Mandant: read the approved runtime profile/policy and applicable annual/source material; the domain wiki never supplies a final tenant value;
- implementation-package history: use it only to trace a cited decision, evidence anchor, or transition. It never establishes current behavior.

Do not load a full implementation package, capability ledger, or every DATEV context page for a narrow terminology question.

For general terminology or the public 2026 baseline, use the bundled references:

- `references/datev-glossary.md` for terms and field meanings.
- `references/source-policy.md` for authority classes, effective dates, and provenance.
- `references/account-function-and-tax-key-boundaries.md` for Automatikkonto, Kontenfunktion, BU/Steuerschlüssel, or automatic-versus-explicit tax behavior.
- `references/tax-treatment-and-period-gates.md` for 0%, § 13b, EU acquisition, exemption, or cross-period/cross-year questions.
- `references/extf-and-pruefprogramm-boundaries.md` for EXTF validation, Prüfprogramm, import, or evidence-scope questions.
- `references/sources/2026-official/` for the copied public SKR03/SKR04 and DATEV annual tables.
- `references/supported-knowledge-map.md` for the boundary between public references and KaiSpan owner documents; it is not a capability ledger.

## Knowledge layers

Keep the following layers separate in every answer:

| Layer | Answers | Can it directly choose a final booking value? |
| --- | --- | --- |
| Normative DATEV/tax knowledge | What a term, field, tax mode, or standard annual table means | No |
| Mandant/profile configuration | What this Mandant/year/SKR actually enables, including Kreditor and custom account functions | Only through an approved, versioned policy |
| Finance implementation capability | What KaiSpan currently supports and what evidence proves it | No; it describes capability and limits |
| Runtime policy/resolver | Which unique mapping may become a BookingCandidate | Yes, only when all identity, policy, tax, and evidence gates pass |

Never promote a glossary definition, model suggestion, BWA observation, or standard SKR account into a final `Sachkonto`, `Kreditor`, `BU`, `Steuerschlüssel`, or `export_ready` decision by itself.

## Required context

Before evaluating a mapping or an export, identify the applicable values required by the runtime policy and product Spec. If one is unknown, say so explicitly and use the applicable review/fail-closed outcome rather than guessing.

- jurisdiction and tax period;
- Wirtschaftsjahr and DATEV format/profile version;
- SKR03 or SKR04;
- Mandant/profile identity and account length;
- currency, document treatment, supplier and receiver identity evidence;
- the versioned Kontenplan, annual Steuerschlüssel table, Kontenfunktions table, and any approved custom override;
- current capability status and evidence pointer, when the question makes an implementation or readiness claim;
- artifact type and product boundary, when the question concerns generation or external action.

## Invoice-to-DATEV reasoning path

Use this order and preserve the boundaries:

1. **Observed and reviewed facts** — establish evidence-bound business facts. The actual facts contract and review checkpoint belong to the product Spec.
2. **Business and tax semantics** — classify the business situation using applicable jurisdiction, period, tax notices, rate, account function, and policy. A VAT percentage alone is not a tax key; an AI category suggestion is not a final account decision.
3. **Profile-bound mapping** — resolve supplier identity to `Kreditor/Gegenkonto` and business/tax semantics to `Sachkonto` only through the approved Mandant policy.
4. **Resolver/grouping** — create a candidate only when final account and tax semantics are compatible; preserve the relevant source lineage. Conflicts or non-unique results go to review.
5. **Serialization and external boundary** — serialize a validated candidate through the product's serializer. Artifact type, checkpoint gates, UI wording, technical validation, and any DATEV-facing action must be read from the Spec and capability registry, not inferred from this reasoning path.

## Fail-closed rules

Return the review or fail-closed outcome defined by the applicable Spec and runtime policy; do not invent a value when:

- public knowledge, an AI suggestion, or an input without one unique approved Mandant policy would determine a tenant booking;
- required input, identity, evidence, policy/version, or tax-treatment gates are not met; or
- an action would write to DATEV or another external system outside an explicitly approved workflow.

Do not use a reserved, free, error-catching, or range account as an automatic fallback. Do not infer a final account from a standard SKR label alone. Do not treat a controlled fixture as real OCR provider validation.

## Provenance and privacy

Every normative or mapping statement should identify its source class, version/effective scope, and an evidence pointer when the task requires an execution or audit decision. Keep raw customer files, VAT IDs, contact details, full invoice text, credentials, and Mandant-specific account rows outside the skill and repository unless the user has explicitly approved a controlled redacted fixture. A fixture path/hash is test-vector provenance; it is not part of stable runtime contract identity.

Internal identity/hash/version data can be necessary evidence without being default user-facing content. UI visibility follows the product Spec; do not turn raw hashes into ordinary business copy.

Read the applicable contract or Spec for the registered runtime identity. A legal replacement fixture can have a different path or raw-byte hash without changing the relevant registered identity.

## Output contract

For a mapping or capability question, answer in this order:

1. **Scope** — jurisdiction, period, SKR, profile, and the artifact type/boundary defined by the applicable product Spec and runtime policy.
2. **Observed facts** — only facts supported by source/evidence; mark unavailable, ambiguous, or inferred states.
3. **Rule basis** — the relevant official/reference rule and its applicability.
4. **Mapping or capability result** — candidate values, implementation status, and lineage.
5. **Gate decision** — use the status vocabulary and evidence scope defined by the applicable Spec or capability registry; do not invent a capability label in the skill.
6. **Evidence** — exact document/section, test, artifact, or hash pointer.
7. **Next action** — the smallest missing input or human decision; never silently guess.

For implementation reviews, read the current Finance capability registry before asserting any status. The registry, not this skill, is the authority for capability labels and evidence scope.

## Maintenance

Update the public reference baseline only with a versioned source, hash, effective scope, and a note about what changed. Update KaiSpan current knowledge only after implementation evidence or owner-approved policy has been reviewed. Do not copy implementation-package history into current knowledge merely because it is recent. Update the capability registry only when a capability claim or evidence scope changes; a conceptual domain-document change alone does not change runtime status.
