# Condition-Based Waiting

Use this technique when async tests or feedback loops rely on arbitrary delays, fail under load, or pass and fail depending on machine speed.

## Principle

Wait for the observable condition that makes the next assertion valid, not for a guessed amount of time.

```typescript
// Timing guess
await new Promise(resolve => setTimeout(resolve, 100));

// Observable condition
await waitFor(() => machine.state === 'ready', 'machine to become ready');
```

## Procedure

1. Identify the state, event, count, file or output the test actually needs.
2. Poll or subscribe to that condition using fresh state on every check.
3. Set a bounded timeout with an error that names the missing condition.
4. Choose a polling interval that is responsive without creating unnecessary load.
5. After replacement, run the loop repeatedly or under load to confirm the flake rate changed.

Typical conditions include:

- an event with a specific type or payload;
- a state machine reaching its ready state;
- a queue or collection reaching an expected count;
- a file or external artifact becoming available;
- multiple observable predicates becoming true together.

Read `condition-based-waiting-example.ts` when a reusable TypeScript polling helper or event-specific wrapper is useful.

## When elapsed time is the behavior

An explicit delay is appropriate when the requirement itself concerns debounce, throttle, retry intervals or another clock-based behavior. First synchronize on the event that starts the interval, then wait using a documented duration derived from the contract. Do not use an arbitrary sleep to compensate for an unknown race.

## Common failures

- Polling cached state instead of invoking a getter each time.
- Omitting the timeout and allowing a loop to hang indefinitely.
- Using a timeout message that does not identify the awaited condition.
- Replacing one guessed delay with another longer guessed delay.
