# SDK Client

Use the project client factory:

```ts
import { getLarkClient } from '@/lib/lark/client'
```

`getLarkClient()` centralizes:

- `appId`: `LARK_APP_ID`
- `appSecret`: `LARK_APP_SECRET`
- `appType`: `lark.AppType.SelfBuild`
- `domain`: `lark.Domain.Lark`

Do not create ad hoc clients in feature modules. If a new SDK option is needed, update the factory and its tests so every integration uses the same configuration.

## Required Pattern

```ts
const client = getLarkClient()
const response = await client.bitable.appTableRecord.list({
  path: {
    app_token: process.env.LARK_BASE_APP_TOKEN,
    table_id: process.env.LARK_TABLE_PRODUCTS,
  },
  params: { page_size: 100 },
})
```

Keep secrets out of logs. When reporting SDK errors, use sanitized summaries rather than stringifying raw SDK objects.
