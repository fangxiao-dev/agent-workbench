# Requirement Inputs: Zero-Shot Capture and Follow-Up Evolution

Read this reference before Focused PRD work for every contract-impacting Decision. It determines what inputs the Decision must reconcile; it does not create a new artifact, Gate, fixed table, or owner-facing section.

## Requirement inputs are broader than documents

Confirmed requirement input can be a user's oral/chat instruction, a meeting conclusion, a screenshot annotation, a linked document, an existing package artifact, or a repository fact. Classify each statement before drafting:

- **Confirmed product promise:** an explicitly requested user/business capability, authority, boundary, product surface, or observable result. It must have a clear home in the Decision/PRD or be explicitly resolved as changed, excluded, or blocked.
- **Constraint:** a confirmed limit on scope, authority, delivery, compatibility, or responsibility. It belongs in the relevant Decision/Spec boundary.
- **Implementation candidate:** a possible mechanism, not yet a product promise. Do not promote it without evidence or an owner decision.
- **Unknown:** missing information whose answer may affect a contract. Classify it under the existing blocking-uncertainty discipline.

Do not infer a product promise from a vague possibility. Conversely, do not recast an explicit promise as a generic capability and thereby discard its product meaning. “Provide a shared editing UI” is a product surface and user capability; permission checks that protect its mutations are a different, Spec-level concern.

## Initial Decision: zero-shot capture

For an initial package, derive the minimum product promise set from the confirmed conversation and discovered inputs before choosing a solution. For each material promise, identify enough of the following to preserve its meaning:

- the actor or beneficiary;
- the product surface or business action;
- the relevant condition, authority, or boundary;
- the observable result or value.

This is working analysis, not a mandatory table. Map the result into the six Focused PRD questions, Decision rationale, or declared scope boundary. If an explicit promise conflicts with another confirmed input or cannot be located in the intended scope, record the conflict or blocking question; do not silently broaden, narrow, or omit it.

## Follow-Up Decision: evolve the current contract

For a follow-up, first read the current `decision.md` and `spec.md` revisions that own the package. They are the complete current baseline of still-valid commitments. The incoming conversation, document, or screenshot is a delta by default, even when it does not repeat earlier oral requirements.

Reconcile the delta as one of: carry forward, add, modify, explicitly remove, or blocker. Absence from the new request means carry forward. Only an owner-stated replacement, modification, or removal may alter a current promise. If “replace the requirement” could mean either a full replacement or a scoped change, ask one focused question before dropping existing commitments.

Current artifacts, not every historical revision, are the normal follow-up input. Consult history only when the current baseline is ambiguous or a material conflict must be resolved.

## Reconciliation checks

Before passing the Decision Gate, check that:

- every material confirmed promise from an initial input has a current home;
- every current promise affected by a follow-up delta is carried forward, modified, explicitly removed, or blocked;
- an omitted statement was not treated as an implicit removal;
- product surfaces and actor actions were not weakened into generic system capabilities;
- changed decision direction follows the existing Decision Gate rules, while behavior-only changes follow the existing Spec Gate rules.

Keep only the resulting current requirement and decision in the formal artifacts. Do not paste working notes or an input-by-input ledger into the Focused PRD.
