# Object-Owned Operations Commonsense

Use this reference before designing operational/admin navigation, object detail pages, editable rows, workflow tabs, or action panels.

The goal is to decide ownership before layout. Many visual defects come from mixing domain objects, object properties, object actions, workflows, reports, and settings at the same navigation level. CSS can hide that problem, but it cannot make the interface feel coherent.

## Core Principle

Operational UI usually starts with a domain object:

> A user opens or finds an object, reads its current state, edits its properties, and performs actions on it.

Design the interface around that sentence before choosing tabs, tables, cards, drawers, or forms.

## Ownership Types

- Object: the durable thing users manage, compare, search, or open.
- Property: editable or readable state owned by an object.
- Action: a command that changes one object or a selected set of objects.
- Workflow: a multi-step process that may create or transform several objects.
- Report: a read-oriented view that summarizes many objects or events.
- Settings group: configuration that changes future behavior rather than one current object.

These types can coexist, but they should not be mixed carelessly as sibling navigation items.

## Navigation Rules

- Same-level navigation should use the same abstraction type.
- Do not place a broad management label next to the concrete object it manages.
- Do not promote an object action into a sibling tab unless it is truly a cross-object workflow.
- If a tab name is a generic noun such as "Management", "Operations", "Overview", or "Configuration", ask what object, workflow, report, or settings group it actually contains.
- Prefer concrete object or workflow names over broad category names.

## Object And Action Rules

- Properties belong on the object surface that owns them.
- Row-level actions stay visually attached to the row or object they affect.
- Detail-level actions stay in the object's detail surface or action area.
- Bulk actions must make the selected object set obvious.
- If users must scan across a wide page to infer which object a button affects, the action ownership is unclear.
- A separate action panel is appropriate only when it remains visibly scoped to the object or selected rows it will change.

## Quantity And Unit Ownership

- Quantity, unit, and conversion evidence are one semantic group.
- If a unit changes how a quantity is interpreted, the unit selector belongs next to that quantity input.
- If an object has multiple unit systems, label which system each field uses.
- Do not put units only in object subtitles, metadata text, or unrelated columns while quantities appear elsewhere.

## Repeated Operational Data

- Use rows or tables when users compare many objects by the same attributes.
- Use a detail panel, drawer, or inline expansion for object-specific editing.
- Do not make repeated objects into large independent cards unless each item needs its own local hierarchy.
- Avoid repeating helper text, long labels, or explanatory copy inside every repeated row.

## Design Sentence Check

Before implementing controls, write one sentence:

```text
User opens/finds [object], sees [state], edits [properties], and performs [actions].
```

If the sentence is hard to write, do not start layout yet. Clarify the object model and action ownership first.

## Smells

- Two sibling tabs appear to manage the same concept.
- One tab is a domain object and another is a generic management/operations label for that same domain.
- A property appears in a separate primary navigation item instead of on its owning object.
- A row action is separated from the row by unrelated fields or large blank space.
- A repeated list uses card-like blocks even though users need column comparison.
- Quantities and units are separated so the user must mentally join them.
- Helper text repeats for every row in a dense operational form.
- Normal user-facing UI exposes technical keys instead of meaningful object names, states, quantities, or evidence.

## Better Patterns

- Object list with row actions:
  - Object identity
  - Current state
  - Key editable properties
  - Row action area

- Object list plus detail drawer:
  - The list supports search, compare, and select.
  - The drawer edits properties and runs actions for the selected object.

- Workflow tab:
  - Use this only when the task spans multiple objects or has distinct stages.
  - Keep the workflow name concrete and task-oriented.

- Report tab:
  - Use this for read-only summaries, exceptions, and audit views.
  - Do not hide primary object editing inside a report.

## Checks

- What is the primary object?
- Which visible fields are properties of that object?
- Which controls are actions on that object?
- Which flows deserve separate navigation because they span multiple objects or stages?
- Are sibling tabs the same abstraction level?
- Can every action be visually traced to the object or selected set it changes?
- Are quantities displayed and edited with their units?
- Would a new user know where the source of truth for the object lives?
