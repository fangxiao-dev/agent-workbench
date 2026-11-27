# PR #88 — Split contract permissions (dispatch / confirm)

We split the old `employee.profile.manage` permission so store managers can send contracts and verify signed copies without seeing the full employee profile.

## What changed
- New permissions: `employee.contract.dispatch`, `employee.contract.confirm`.
- Users WITH profile read keep using the existing documents endpoint and `ContractSection`.
- Users WITHOUT profile read get a minimal view: `GET /employees/:id/documents?contractMinimal=true` returns `ContractMinimalView` (no salary, no tax id), and the new `ContractTasksMinimal` component on the staff page lets them send, upload the signed copy, and confirm.
- Whitelist tests assert the minimal view never contains sensitive fields.

## Why separate
Changing the full documents endpoint would have touched many old regression tests, so the minimal path is isolated and easy to test.

Status: all tests green, ready to merge.
