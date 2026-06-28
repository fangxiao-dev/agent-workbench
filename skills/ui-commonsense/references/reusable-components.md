# Reusable Components Commonsense

Use this reference before adding UI that looks like a reusable control, feedback pattern, or repeated admin interaction.

## Discovery Flow

1. Read `docs/top-level-knowledge/ui-component-inventory.md` first.
2. Search the codebase with concrete behavior keywords and likely component names.
3. Prefer an existing component when it covers about 80% of the interaction, accessibility, and visual-state needs.
4. If reusing would require domain-specific behavior, add a small wrapper instead of duplicating the primitive.
5. If you do not reuse an existing component, record the reason in the implementation summary.

## Keyword Map

- `success message`, `failure message`, `action result`, `inline result` -> `AdminInlineActionResult`
- `async submit`, `loading button`, `pending action` -> `Button` with `loading` and `loadingLabel`
- `table`, `admin list`, `sortable rows` -> `AdminDataTable`
- `status badge`, `state pill`, `review status` -> `AdminBadge` or a business wrapper around it
- `confirm destructive action`, `confirm dialog` -> `ConfirmActionDialog`
- `language switch`, `locale select` -> `LanguageSelect`

## Checks

- Does a component inventory entry already describe this behavior?
- Is the behavior generic enough to reuse directly?
- Would a thin business wrapper preserve reuse while keeping domain copy and rules local?
- Are success and failure states handled consistently with existing admin surfaces?
- Does the component already solve accessibility or timing details, such as focus, loading width, auto-dismiss, or persistent errors?

## Common Defects

- Rebuilding one-off success/failure messages when `AdminInlineActionResult` already encodes success auto-dismiss and persistent failures.
- Creating custom loading button states that shift layout or hide accessible pending copy.
- Copying table, badge, dialog, or combobox markup without checking the inventory.
- Extracting a component too early when the behavior is still domain-specific and only used once.
