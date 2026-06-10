# Bitable Attachments

Use `uploadBitableAttachment` for runtime attachment uploads.

## Upload Then Write

```ts
const fileToken = await uploadBitableAttachment({
  fileName,
  file: fs.createReadStream(absoluteFilePath),
  size,
  operation: 'customers.upload-gewerbeschein',
})

await updateBaseRecord({
  tableId: process.env.LARK_TABLE_CUSTOMERS!,
  recordId,
  fields: {
    Gewerbeschein: [{ file_token: fileToken, name: fileName }],
  },
  operation: 'customers.update-gewerbeschein',
  retry: { maxAttempts: 2 },
})
```

The upload call uses:

```ts
{
  data: {
    file_name: fileName,
    parent_type: 'bitable_file',
    parent_node: LARK_BASE_APP_TOKEN,
    size,
    file,
  },
}
```

## Readback Verification

For registration documents and similar business-critical attachments, read the record after update and verify exactly one active attachment with the expected name. This catches stale or failed file token writes.

## Test Fixtures

Browser smoke tests should create attachment preconditions through the same application path the user uses. Avoid injecting attachment state through an unrelated helper when the test is meant to verify runtime registration or upload behavior.
