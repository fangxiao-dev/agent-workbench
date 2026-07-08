---
name: continuous-learning
description: Build pending skill proposals from sessions, require approval, then generate into workbench and install globally.
origin: ECC
---

# Continuous Learning Skill

Continuously learn from sessions with an approval gate:
- Stop hook writes pending proposals into this repository
- state and index are persisted as structured JSON for next-session awareness
- approved proposals generate real skills under `skills/` and trigger install
- rejected proposals are deleted directly from pending

## When to Activate

- Setting up session-to-skill continuous learning with approval
- Managing pending proposals before starting regular tasks
- Approving or rejecting generated proposals
- Verifying generated skills are installed through workbench install

## How It Works

1. Stop hook runs `evaluate-session.sh`
2. If session passes threshold, a pending proposal JSON is created in `skills/continuous-learning/pending/`
3. The hook updates:
   - `skills/continuous-learning/pending/state.json`
   - `skills/continuous-learning/pending/index.json`
4. At next task start, read state to decide whether to process pending first
5. Approval creates `skills/<new-skill>/SKILL.md` then runs install
6. Rejection deletes pending proposal and refreshes state

## Paths

- Proposals: `skills/continuous-learning/pending/proposal-*.json`
- State: `skills/continuous-learning/pending/state.json`
- Index: `skills/continuous-learning/pending/index.json`
- Generated skills: `skills/<skill-name>/SKILL.md`

## Configuration

Edit `config.json`:

```json
{
  "min_session_length": 10,
  "candidate_name_prefix": "learned",
  "pending_dir": "skills/continuous-learning/pending",
  "state_file": "skills/continuous-learning/pending/state.json",
  "index_file": "skills/continuous-learning/pending/index.json"
}
```

## Hook Setup

Add to your `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/skills/continuous-learning/evaluate-session.sh"
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "~/.claude/skills/continuous-learning/scripts/check-pending-before-task.sh"
      }]
    }]
  }
}
```

## Commands

- List pending proposals:

```bash
bash ~/.claude/skills/continuous-learning/scripts/list-pending-skills.sh
```

- Approve latest pending proposal and install globally:

```bash
bash ~/.claude/skills/continuous-learning/scripts/approve-pending-skill.sh
```

- Approve specific proposal:

```bash
bash ~/.claude/skills/continuous-learning/scripts/approve-pending-skill.sh <proposal-id-or-file> [custom-skill-name]
```

- Reject latest or specific pending proposal:

```bash
bash ~/.claude/skills/continuous-learning/scripts/reject-pending-skill.sh [proposal-id-or-file]
```

## Approval Rules

- Pending stage never writes final skills.
- Only approve action can generate `skills/<name>/SKILL.md`.
- Approval always triggers repository install flow.
- Reject deletes pending proposal and updates state/index.
