---
name: datev-tax-accounting
description: Use whenever a task involves German DATEV accounting, SKR03/SKR04, Kontenplan, Sachkonto, Kreditor, BU/Steuerschlüssel, VAT treatment, Mandant accounting profiles, EXTF, Prüfprogramm, or the Finance invoice-to-DATEV chain. Route the question through the DATEV/tax wiki and the current Finance capability ledger; distinguish normative tax knowledge from tenant configuration and implemented runtime behavior; fail closed instead of guessing.
compatibility: Requires access to the KaiSpan Finance current-knowledge routes when assessing implementation status. Bundled public 2026 DATEV references are a baseline, not a substitute for a Mandant-specific approved policy.
---

# DATEV Tax and Accounting Knowledge

Use this skill as the navigation and reasoning protocol for the invoice-to-DATEV chain. The skill is not a free-form tax adviser and it is not the runtime accounting policy. It tells the agent which knowledge to load, how to classify evidence, and how to report an answer that a reviewer can audit.

## Load order

For KaiSpan work, read the current domain knowledge before any implementation package or historical note:

1. `docs/domains/finance-assistant/context/datev-accounting/README.md`
2. `docs/domains/finance-assistant/context/datev-accounting/terminology-and-rules.md`
3. `docs/domains/finance-assistant/context/datev-accounting/source-and-authority-policy.md`
4. `docs/domains/finance-assistant/module-knowledge/datev-accounting/prd.md`
5. `docs/domains/finance-assistant/module-knowledge/datev-accounting/spec.md`
6. `docs/domains/finance-assistant/module-knowledge/datev-accounting/capability-registry.yaml`

Read the relevant implementation package only to verify a cited decision, evidence anchor, or current transition. The package is a change record, not the long-term source of truth.

For general terminology or the public 2026 baseline, use the bundled references:

- `references/datev-glossary.md` for terms and field meanings.
- `references/source-policy.md` for authority classes, effective dates, and provenance.
- `references/sources/2026-official/` for the copied public SKR03/SKR04 and DATEV annual tables.
- `references/supported-knowledge-map.md` for the bridge from the public baseline to KaiSpan runtime capability.

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

Before evaluating a mapping or an export, identify the applicable values. If one is unknown, say so explicitly and use `review_required` or `fail_closed` as appropriate.

- jurisdiction and tax period;
- Wirtschaftsjahr and DATEV format/profile version;
- SKR03 or SKR04;
- Mandant/profile identity and account length;
- currency, document treatment, supplier and receiver identity evidence;
- the versioned Kontenplan, annual Steuerschlüssel table, Kontenfunktions table, and any approved custom override;
- the current Finance capability status and evidence pointer;
- whether the requested artifact is a controlled test-only output or a production action.

## Invoice-to-DATEV reasoning path

Use this order and preserve the boundaries:

1. **Source facts** — establish source hash, document/file/run identity, invoice treatment, dates, parties, totals, tax breakdown, and line-level facts.
2. **Canonical facts** — map Finance-visible OCR output or structured input into `CanonicalAccountingFactsV1` with evidence and deterministic hash. The existing `CanonicalEvaluation` envelope is the result contract; do not invent another envelope.
3. **Review** — record explicit human corrections and approval. Machine output is not a formal invoice fact until the review gate succeeds.
4. **Tax semantics** — classify the business/tax situation using the applicable jurisdiction, period, tax notices, rate, account function, and policy. A VAT percentage alone is not a tax key.
5. **Policy mapping** — resolve supplier identity to `Kreditor/Gegenkonto` and business/tax semantics to `Sachkonto`, using the profile-bound policy version and provenance.
6. **Resolver/grouping** — aggregate only source lines with the same final `Sachkonto` and tax mode; preserve every `sourceLineId`. Conflicting or multi-account results go to review.
7. **BookingCandidate** — determine amount, `Konto`, `Gegenkonto`, `Soll/Haben`, `BU/Steuerschlüssel`, date, and lineage from the validated policy and reviewed facts.
8. **EXTF** — serialize only a validated candidate through the existing serializer. A test-only EXTF is a technical artifact for controlled review, not a production DATEV write or proof of tax correctness.

## Fail-closed rules

Return a structured blocker or review state instead of inventing a value when any of the following occurs:

- unknown contract/profile/schema/map or unsupported version;
- missing or conflicting Mandant, source, file, or OCR-run identity;
- missing source field, unsupported page/evidence anchor, invalid hash, or broken lineage;
- supplier identity is only a fuzzy name, or a receiver is not uniquely bound;
- no unique approved mapping, same-priority mapping conflict, or account excluded by Kontenplan/Kontenfunktion;
- tax mode, BU/Steuerschlüssel, automatic-account behavior, or DATEV program-version constraint is unresolved;
- a blocking provider warning or a required OCR capability is absent;
- a candidate is stale because its fact, policy, batch, profile, or reference version changed;
- an action would write to production DATEV or mutate an external system without an explicit approved workflow.

Do not use a reserved, free, error-catching, or range account as an automatic fallback. Do not infer a final account from a standard SKR label alone. Do not treat a controlled fixture as real OCR provider validation.

## Provenance and privacy

Every normative or mapping statement should include its source class, version/effective scope, and an evidence path or hash where available. Keep raw customer files, VAT IDs, contact details, full invoice text, credentials, and Mandant-specific account rows outside the skill and repository unless the user has explicitly approved a controlled redacted fixture. A fixture path/hash is test-vector provenance; it is not part of stable runtime contract identity.

The stable runtime identity for a contract/profile is the registered tuple `family/profile/profileVersion/schemaVersion/mapId/mapFingerprint/version`. A legal replacement fixture may have a different path or raw-byte hash without changing that identity.

## Output contract

For a mapping or capability question, answer in this order:

1. **Scope** — jurisdiction, period, SKR, profile, and whether the result is test-only.
2. **Observed facts** — only facts supported by source/evidence; mark unavailable, ambiguous, or inferred states.
3. **Rule basis** — the relevant official/reference rule and its applicability.
4. **Mapping or capability result** — candidate values, implementation status, and lineage.
5. **Gate decision** — `verified-local`, `review_required`, `fail_closed`, `external-acceptance-pending`, or `blocked`.
6. **Evidence** — exact document/section, test, artifact, or hash pointer.
7. **Next action** — the smallest missing input or human decision; never silently guess.

For implementation reviews, explicitly distinguish `implemented`, `locally verified`, `externally accepted`, `production-ready`, and `closed`. The current Finance capability ledger is the authority for those labels.

## Maintenance

Update the public reference baseline only with a versioned source, hash, effective scope, and a note about what changed. Update KaiSpan current knowledge only after implementation evidence or owner-approved policy has been reviewed. Do not copy implementation-package history into current knowledge merely because it is recent. When a rule or runtime capability changes, update the relevant context page and capability registry together, then re-check inbound links and source hashes.
