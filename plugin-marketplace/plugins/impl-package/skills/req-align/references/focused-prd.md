# Focused PRD: Business-Readable Product Definition

Read this reference when an earned `decision.md` needs a Focused PRD, when revising one, or when evaluating the Focused-need Decision Gate criterion. It does not apply to a passed lightweight correction that only points to an existing product definition, nor to the `contract impact=none` fast path.

## Definition and boundary

A Focused PRD explains why one concrete change is worth making, who benefits in which situation, how the user or business will perceive the change, what is and is not promised, and how the product result will be recognized. “Focused” means focused on this change; it does not mean short, abstract, or a summary of system capabilities.

It is not a field contract, state machine, error-code catalog, implementation design, test procedure, or task breakdown. Put normative behavior and cross-module data/API contracts in the Spec-stage artifact ensemble (`spec.md` plus an earned `contract-design.md`), and implementation choices in `plan.md`. Do not decide the layer by asking whether a field is mentioned; decide it by the question being answered.

## Six stable questions

Every earned Focused PRD answers these questions substantively. Use repository domain language and write enough detail to make the product promise understandable without code or architecture documents.

| Question | What the PRD must establish |
| --- | --- |
| Target beneficiary and situation | Who benefits, in what business event or use/calling context; for indirect systems, name the real beneficiary and caller context. |
| Current problem or opportunity, and reason to change | When relevant, how work happens now and its friction/risk/gap; otherwise the unmet opportunity, strategic window, or stage hypothesis. Explain why this change is worth making now. Name a triggering event only when it affects scope or product choice. |
| Expected result and value | What the user or business can reliably do, avoid, or understand after the change, and the resulting value. |
| Core product behavior or experience | How the change works from the user/business perspective: key steps and handoffs for a flow, or key rule and observable outcome when no flow exists. |
| Scope and boundary | What is promised and excluded, enough to prevent a reader from mistaking the commitment or responsibility boundary. |
| Success signal | A user- or business-observable outcome that indicates the product promise holds. Technical tests and implementation evidence belong to Spec/Plan. |

Qualitative signals are valid when a metric is not proportionate; do not invent a KPI merely to fill this section.

## Conditional product depth

Answer the following questions only when the requirement has the matching signal. Integrate the answer into the six stable questions; do not create blank headings, fixed matrices, or a new gate.

| Signal | Product question to answer |
| --- | --- |
| UI or human workflow | What does the user see, do, receive as feedback, and do next? |
| Multi-role collaboration | Who initiates, who confirms, where does handoff occur, and when does responsibility move? |
| Form or data review | What does the user provide, what does the system suggest, who confirms, and what returns for correction? |
| Automated recommendation or decision | What does the system propose or decide, may a user override it, and what user/business-visible safe result occurs when it cannot decide? If that material choice is unknown, record it as a Decision blocker rather than inventing a default. |
| Permission or data scope | Which kind of user may complete which business action in which scope? |
| Lifecycle change | How does a user/business process enter, leave, resume, or get reprocessed? |
| External-system handoff | Where does this product's responsibility end, and is downstream completion still managed here? |
| MVP, POC, or staged delivery | What does this stage validate, what does it deliberately not validate, and what condition reopens the next stage? |
| Migration or compatibility | How do existing users continue working, and how are existing data or behaviors treated? |

For example, a field authority matrix is appropriate only when a form, review, or editable-data signal makes it necessary. An MVP trade-off table is appropriate only for an MVP, POC, or staged-delivery signal. Persona narratives and UI prototypes are never automatic requirements.

## Business-readability rubric

The Focused-need Decision Gate passes only when the earned PRD satisfies all applicable checks:

- **Object is clear:** the affected beneficiary and situation are identifiable, not a generic “user.”
- **Confirmed promise is covered:** every material, confirmed product promise from the requirement inputs has a clear home in the PRD, decision, or declared boundary. It may be rephrased, but an explicit product surface, actor action, authority, or observable result cannot silently disappear into a more abstract description.
- **Rationale is grounded:** either the current friction, risk, or gap, or the unmet opportunity/strategic hypothesis, is described independently of the chosen solution. Do not invent a current workflow or trigger merely to fill the PRD.
- **Result is product-led:** user/business outcomes are named; “add an API/page/table/job” does not substitute for the result.
- **Experience is understandable:** a reader can understand key behavior without internal classes, schemas, artifacts, or test machinery.
- **Boundary is clear:** the stated scope prevents a mistaken promise or responsibility boundary.
- **Success is observable:** a user/business result can indicate success; implementation tests are evidence, not the definition of success.
- **Detail is proportionate:** only details that affect a product choice are expanded; field structures, state transitions, error contracts, and implementation steps stay in their owning layer.
- **Language is product-facing:** internal implementation vocabulary cannot replace user flow or business semantics.

## PRD / Spec / Plan routing

| Question | Owner |
| --- | --- |
| Why does the beneficiary need the change? | PRD |
| What can the user or business do, and what is the product default? | PRD |
| Who has final business control, including whether a system suggestion may be overridden? | PRD |
| Where does business responsibility end? | PRD |
| What are a field's type, length, nullability, storage, validation, or expiry rules? | Spec |
| What state machine, failure recovery, API, error, persistence, or integration contract applies? | Spec |
| How is the approved contract decomposed, implemented, and verified? | Plan |

“A tax adviser may override the current document's booking text without changing the global rule” is product control and belongs in the PRD. How that override is stored, validated, or expires belongs in the Spec.
