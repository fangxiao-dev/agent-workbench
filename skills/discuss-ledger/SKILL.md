---
name: discuss-ledger
description: Use when multiple parties need either independent Blind Opening ideas, live discuss-ledger convergence, or independent ideas followed by a converging discussion. Triggers on blind opening, 独立发散, brainstorm 多方方案, discuss, 组织审核, 多轮 loop review, 继续收敛, or discuss <target>.
user-invocable: true
---

# Discuss Ledger Router

Choose the requested mode before creating an artifact. Keep user-facing discussion and summaries in Chinese unless the target requires otherwise.

## Router settings

Mode and participants are separate choices. `discuss_router.py` only selects the workflow and participants and forwards the rest; it defines no model identity, role, prompt or permission.

| Setting | Default | Accepted values | Effect |
| --- | --- | --- | --- |
| `--mode` | `ledger` | `ledger`, `blind`, `combined` | Normal discussion, independent discovery, or Blind Opening followed by normal Ledger. |
| `--agents` | `codex,claude` | `full`, or exactly two distinct names from `codex`, `claude`, `grok` | `full` expands to `codex,claude,grok`. One participant or a literal three-name list is rejected. |
| `--max-rounds` | `5` | integer | Full participant cycles for `ledger` / `combined`. |
| `--timeout-s` | `300` | integer | Per-agent, per-call timeout. |
| `--<agent>-model` / `--<agent>-effort` | see below | `<agent>` is `codex`, `claude` or `grok` | Per-run model and reasoning-effort override for that participant; unset keeps the default. |

Defaults: Claude runs the `sonnet` alias at `high`; Codex runs its configured default model at `high`; Grok runs call-grok's default model at `low`. Override only when the user asks, e.g. `--codex-model gpt-6-astra --codex-effort low`; the router forwards overrides to every mode. Do not pin model versions on your own.

Dispatch: `ledger` → `discuss_orchestrator.py`; `blind` → `blind_opening.py` (writes only the independent-opening artifacts); `combined` → `blind_opening_then_ledger.py` (hands consolidated points to the unchanged Ledger workflow).

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
| Multi-round loop over any mode (“loop 审查”, “盲审 loop”) | Loop over that mode | [references/loop-mode.md](references/loop-mode.md) |

Every run follows [references/convergence.md](references/convergence.md): the goal and boundary come first, and value and convergence are judged against them.

Existing Discuss Ledger triggers default to normal Ledger for compatibility. If the requested mode remains materially ambiguous, ask one question; do not silently choose a mode.

Blind Opening is independent of Ledger and may end after its Markdown result. The combined mode does not alter the normal Ledger prompt, CLI, or state machine.

## Trigger boundary

An ordinary one-pass review or one-way subagent handoff is neither a Ledger discussion nor Blind Opening: return the finding through that workflow and do not create a ledger. Use this skill only when the user asks for independent multi-party exploration, a live responding discussion, or their explicit combination.
