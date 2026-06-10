# Base Field Values

SDK payloads must use the value shape expected by the target Lark Base field type. Keep conversion close to the SDK write helper and assert the exact payload in tests.

## Common Write Shapes

| Field type | Payload shape |
|---|---|
| Text | `string` |
| Number | `number` |
| Checkbox / Boolean | `boolean` |
| Single select | option text as `string` |
| Link to records | `string[]` of record IDs |
| Attachment | `Array<{ file_token: string; name: string }>` |
| Datetime | millisecond timestamp as `number` |

## Datetime Fields

When writing datetime fields, send a millisecond timestamp. The project helper converts known datetime field names before calling the SDK.

Known runtime datetime fields include:

- `申请时间`
- `Bestelldatum`
- `订单确认时间`
- `订单驳回时间`
- `付款确认时间`
- `发货时间`
- `客户确认收货时间`
- `老客户付款期限`
- `库存更新时间`
- `预期库存更新时间`

If you add another writable datetime field, update `LARK_DATETIME_FIELDS` in `web/lib/lark/base-write.ts` and add a focused payload test.

## Linked Records

Use record IDs:

```ts
{
  关联客户: [customerId],
  关联商品: [productId],
}
```

Do not write display text into linked-record fields.

## Attachments

For attachment fields, first upload the file as bitable media, then write the returned token:

```ts
{
  Gewerbeschein: [{ file_token: fileToken, name: fileName }],
}
```

After writing an attachment that drives business state, read back the record and verify the active attachment list.
