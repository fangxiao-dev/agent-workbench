---
name: discuss-ledger
description: Use when multiple parties need either independent Blind Opening ideas, live discuss-ledger convergence, or independent ideas followed by a converging discussion. Triggers on blind opening, 独立发散, brainstorm 多方方案, discuss, 组织审核, 多轮 loop review, 继续收敛, or discuss <target>.
user-invocable: true
---

# Discuss Ledger Router

Choose the requested mode before creating an artifact. Keep user-facing discussion and summaries in Chinese unless the target requires otherwise.

## Router settings

Mode and participants are separate choices. The default is normal `ledger` with `codex,claude`, preserving the former two-party behavior. Use `--mode blind` for independent discovery or `--mode combined` for Blind Opening followed by Ledger; use `--agents full` only when all three participants (`codex,claude,grok`) are wanted, or specify exactly two distinct participants such as `codex,grok`.

The full public contract is in [references/router.md](references/router.md).

```powershell
python <skill>\scripts\discuss_router.py --topic <target>
python <skill>\scripts\discuss_router.py --mode blind --agents codex,grok --topic <target>
python <skill>\scripts\discuss_router.py --mode combined --agents full --topic <target>
```

| User intent | Mode | Read first |
| --- | --- | --- |
| Independent ideas, brainstorming, or “do not let participants influence each other” | Blind Opening | [references/blind-opening.md](references/blind-opening.md) |
| Debate, respond to disagreements, converge, deadlock, or continue an existing ledger | Discuss Ledger | [references/ledger-discussion.md](references/ledger-discussion.md) |
| “First independently explore, then discuss/converge” | Blind Opening + Ledger | [references/blind-opening-plus-ledger.md](references/blind-opening-plus-ledger.md) |

Existing Discuss Ledger triggers default to normal Ledger for compatibility. If the requested mode remains materially ambiguous, ask one question; do not silently choose a mode.

Blind Opening is independent of Ledger and may end after its Markdown result. The combined mode hands consolidated initial points to the existing Ledger workflow; it does not alter the normal Ledger prompt, CLI, or state machine.

## Trigger boundary

An ordinary one-pass review or one-way subagent handoff is neither a Ledger discussion nor Blind Opening: return the finding through that workflow and do not create a ledger. Use this skill only when the user asks for independent multi-party exploration, a live responding discussion, or their explicit combination.
