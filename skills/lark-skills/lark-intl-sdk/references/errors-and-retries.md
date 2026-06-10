# Errors And Retries

Runtime SDK errors must be safe to log and useful for diagnosis.

## Sanitized Error Contract

Use `sanitizeLarkApiError` and the write helpers' operation labels. Error messages should preserve:

- operation name
- Lark or HTTP code
- sanitized message
- retryable classification

They must remove:

- app secrets
- access tokens
- bearer tokens
- obvious secret/token/password fields

## Nested Error Responses

SDK failures may carry useful Lark details inside nested response data. Prefer nested Lark `code` and `msg` over generic transport messages when available.

Expected shape to handle:

```ts
{
  code: 'ERR_BAD_RESPONSE',
  message: 'Request failed with status code 429',
  response: {
    status: 429,
    data: { code: 99991400, msg: 'rate limited' },
  },
}
```

## Retry Rules

- Retry only retryable codes such as 429, 5xx, `99991400`, and `99991663`.
- Create retries require a `clientToken`.
- Updates and deletes may retry when the caller explicitly passes retry options.
- Keep retry counts small in request/response runtime paths.

Add tests for any new retryable operation so future changes do not retry non-idempotent writes accidentally.
