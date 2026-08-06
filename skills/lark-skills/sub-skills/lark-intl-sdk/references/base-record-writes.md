# Base Record Writes

Use `web/lib/lark/base-write.ts` for runtime Base create, update, delete, batch create, batch delete, and bitable attachment upload operations.

## Helper Index

| Operation | Helper |
|---|---|
| Create one record | `createBaseRecord` |
| Batch create records | `batchCreateBaseRecords` |
| Update one record | `updateBaseRecord` |
| Delete one record | `deleteBaseRecord` |
| Batch delete records | `batchDeleteBaseRecords` |
| Upload bitable attachment media | `uploadBitableAttachment` |

## Create

```ts
const recordId = await createBaseRecord({
  tableId: process.env.LARK_TABLE_ORDERS!,
  fields: {
    订单编号: orderNumber,
    客户邮箱: customer.email,
  },
  operation: 'orders.create',
  clientToken: orderNumber,
  retry: { maxAttempts: 2 },
})
```

Use `clientToken` for create operations that need idempotency. Retries for create are only enabled when a client token is supplied.

## Batch Create

```ts
const recordIds = await batchCreateBaseRecords({
  tableId: process.env.LARK_TABLE_ORDER_ITEMS!,
  operation: 'order-items.batch-create',
  records: items.map((item) => ({
    fields: {
      订单编号: item.orderNumber,
      数量: item.quantity,
    },
  })),
})
```

Batch create must return one valid `rec...` ID per requested record. Treat short responses as write failures.

## Update

```ts
await updateBaseRecord({
  tableId: process.env.LARK_TABLE_PRODUCTS!,
  recordId: productId,
  fields: { 锁定库存: nextLockedStock },
  operation: 'products.update-locked-stock',
  retry: { maxAttempts: 2 },
})
```

Validate the record ID before calling update. The shared helper does this; keep new code behind it.

## Delete

```ts
await deleteBaseRecord({
  tableId: process.env.LARK_TABLE_CUSTOMER_FAVORITES!,
  recordId: favoriteRecordId,
  operation: 'favorites.delete',
})
```

Use delete helpers only with concrete record IDs from trusted lookup paths.
