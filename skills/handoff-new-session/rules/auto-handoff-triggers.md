# Auto Handoff Triggers

Use this rule for long-running workflows that need durable continuation across sessions.

## Required Triggers

Enter the durable handoff flow when either condition is true:

1. **A major quality gate has passed**
   - Examples: integration gate, adapter readiness gate, final backend gate, frontend gate, cutover gate.
   - Finish the checkpoint first: record verification results, commit related changes when appropriate, capture fresh git state, then write or refresh the handoff.
2. **Context auto-compaction happened**
   - If the conversation has been compacted or only a summary remains, do not rely on the summary alone.
   - Recover facts from the actual workspace first: `git status --short --branch`, `git log -1 --oneline`, and the relevant plan / handoff / progress files.
   - Then write or refresh the durable handoff before continuing or creating a new session.

## Gate Boundary

A major quality gate is a handoff-worthy phase boundary. It is not every unit test, typo fix, or small local iteration.

When unsure, prefer writing a handoff, but never invent verification, commits, external updates, or task status that did not actually happen.
