# Root Cause Tracing

Use this technique when an error appears deep in a call chain, an invalid value reaches a distant consumer, or the visible failure point is unlikely to be the origin.

## Principle

Trace backward from the observed failure until you find the first transition that made valid state invalid. Fix that source transition; guards at later layers are supplementary protection, not a substitute for the root fix.

## Procedure

1. Record the exact symptom and the operation that directly produced it.
2. Inspect the inputs at that operation, including relevant environment and configuration.
3. Identify the immediate caller and where each suspicious input came from.
4. Repeat one level upward until you find where the value was first created, transformed incorrectly, or accepted without the required invariant.
5. State the candidate root cause as a falsifiable claim and test it with the smallest possible probe.
6. Apply the fix at the earliest responsible boundary, then rerun both the minimal reproduction and the original feedback loop.

## Instrumentation

When static tracing is insufficient, instrument immediately before the failing operation:

```typescript
console.error('[DEBUG-root-trace]', {
  input,
  environment: process.env.NODE_ENV,
  stack: new Error().stack,
});
```

Capture the value, execution context and stack. Give temporary logs a unique prefix so cleanup can find every insertion after the diagnosis.

## Stop conditions

- Do not stop at the first function that throws if its inputs were already invalid.
- Do not add validation at every layer by default; add a guard only where that layer owns an invariant or the operation is dangerous.
- If the chain crosses an unobservable boundary, first add boundary evidence rather than guessing what crossed it.

The tracing result should name the original invalid transition, the evidence that confirms it, and why fixing there prevents the reported symptom.
