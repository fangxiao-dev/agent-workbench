---
name: lark-intl-shared
version: 1.0.0
description: "Lark CLI shared foundation (International): app config init, auth login, identity switching (--as user/bot), permission and scope management, Permission denied error handling, security rules. Triggers when: first-time setup (lark-cli config init), auth/login needed, insufficient permissions, switching user/bot identity, configuring scopes, or first use of lark-cli with Lark International."
---

# lark-cli Shared Rules (Lark International)

This skill guides you on how to use lark-cli to operate Lark resources, and what to watch out for.

## Config Initialization

On first use, run `lark-cli config init` to complete app configuration.

When helping a user initialize config, use a background process to run the command below, then read the output, extract the authorization link, and send it to the user:

```bash
# Start config (this command blocks until the user opens the link and completes the action, or it times out)
lark-cli config init --new
```

> **Lark International:** When prompted for domain, select **`larksuite.com`**.

## Authentication

### Identity Types

Two identity types, switched via `--as`:

| Identity | Flag | How to obtain | Use case |
|----------|------|---------------|----------|
| User identity | `--as user` | `lark-cli auth login` | Access user's own resources (calendar, Drive, etc.) |
| Bot identity | `--as bot` | Automatic — only needs appId + appSecret | App-level operations, access bot's own resources |

### Identity Selection Principles

The output `[identity: bot/user]` shows the current identity. Bot and user behave very differently — confirm the identity matches your goal:

- **Bot cannot see user resources**: Cannot access a user's calendar, Drive documents, mailbox, or other personal resources. For example, `--as bot` querying a schedule returns the bot's own (empty) calendar.
- **Bot cannot act on behalf of users**: Messages are sent in the app's name; documents created are owned by the bot.
- **Bot permissions**: Only need to enable scopes in the Lark Developer Console — no `auth login` required.
- **User permissions**: Enable scopes in the console **and** the user authorizes via `auth login` — both layers must be satisfied.

### Handling Insufficient Permissions

When you encounter a permission error, **take different actions depending on the current identity type**.

The error response contains key information:
- `permission_violations`: Lists missing scopes (choose 1 of N)
- `console_url`: Link to the permission config page in the Lark Developer Console
- `hint`: Suggested fix command

#### Bot identity (`--as bot`)

Provide the `console_url` from the error to the user and guide them to enable the scope in the console. **Never** run `auth login` for bot identity.

#### User identity (`--as user`)

```bash
lark-cli auth login --domain larksuite           # authorize by business domain
lark-cli auth login --scope "<missing_scope>"    # authorize by specific scope (recommended — minimal-privilege principle)
```

**Rule**: `auth login` must specify a scope (`--domain` or `--scope`). Multiple logins accumulate scopes (incremental authorization).

#### Agent-initiated auth (recommended)

When you as an AI agent need to help the user complete authentication, run the following command in background mode to start the authorization flow, then send the authorization link to the user:

```bash
# Start auth (blocks until user authorizes or times out)
lark-cli auth login --scope "calendar:calendar:readonly"
```

## Update Checks

After a lark-cli command runs, if a new version is detected, the JSON output will contain a `_notice.update` field (with `message`, `command`, etc.).

**When you see `_notice.update` in the output, after completing the user's current request, proactively offer to help update**:

1. Inform the user of the current version and the latest version number.
2. Offer to run the update (CLI and Skills should be updated together):
   ```bash
   npm update -g @larksuite/cli && npx skills add larksuite/cli -g -y
   ```
3. After the update, remind the user: **Exit and reopen the AI Agent** to load the latest skills.

**Rule**: Do not silently ignore update notifications. Even if the current task is unrelated to the update, inform the user after completing their request.

## Security Rules

- **Never output secrets** (appSecret, accessToken) in plaintext to the terminal.
- **Confirm user intent before write/delete operations**.
- Use `--dry-run` to preview dangerous requests.
