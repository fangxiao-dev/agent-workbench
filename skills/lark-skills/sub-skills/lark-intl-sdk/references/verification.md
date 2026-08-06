# Verification

Use focused tests first, then project gates.

## Focused SDK Write Tests

Run targeted tests for changed Lark helpers:

```powershell
cd web
npm test -- lib/lark/base-write.test.ts
```

For domain source changes, include the source tests touched by the operation:

```powershell
cd web
npm test -- lib/lark/customers-source.test.ts lib/lark/orders-source.test.ts
```

## Runtime Boundary Guard

Production-facing runtime files must not shell out:

```powershell
cd web
npm test -- lib/lark/runtime-cli-guard.test.ts
```

For a manual scan:

```powershell
git grep -n -F -e "node:child_process" -e "lark-cli" -e "LARK_CLI_PATH" -- web/lib/lark web/app
```

No matches under `web/lib/lark` and `web/app` means runtime Lark code is not depending on a local executable.

## Full Verification

For broad Lark runtime write changes:

```powershell
cd web
npm test
npx tsc --noEmit
npm run build
npm run test:e2e
npm run test:e2e:lark-smoke
npm run check:lark-smoke
npm run check:prod-like
```

Use `E2E_PORT` or `E2E_LARK_APP_BASE_URL` when the default port is already occupied. Do not edit `.env.local` just to run tests.
