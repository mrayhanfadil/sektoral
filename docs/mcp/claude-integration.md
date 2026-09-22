# Connect Sectors to Claude with OAuth

> Source: https://docs.sectors.app/recipes/sectors-for-ai-agents/02-sectors-in-claude (verified 2026-08-29).
>
> For Claude Code, Cursor, VS Code, JetBrains, or any Streamable HTTP client
> (auth header `Authorization: Bearer <key>`), use [`setup.md`](setup.md)
> instead.

Connect Sectors to **claude.ai (web)** or **Claude Desktop** as a custom
connector. Once connected, Claude can pull live IDX, SGX, and KLSE data into
any conversation. No API key to paste into a config file, no JSON to edit,
and access is revocable from your Sectors dashboard at any time.

| Setup style                  | Best for                        | Auth                   | Endpoint                                |
| ---------------------------- | ------------------------------- | ---------------------- | --------------------------------------- |
| **OAuth custom connector** (this guide) | claude.ai, Claude Desktop | Browser sign-in        | `https://sectors-mcp.supertype.ai/mcp`  |
| API key + Streamable HTTP    | Claude Code, Cursor, VS Code    | `Bearer YOUR_API_KEY`  | `https://sectors-mcp.supertype.ai/mcp`  |

---

## Prerequisites

1. **A Sectors account on an Insider plan.** Forever-Free and Standard plans
   do not include API access. Sign up at https://sectors.app to enable API key
   generation and connect custom MCP apps.
2. **Claude on web or desktop** — sign in at https://claude.ai or install the
   Claude Desktop app from https://claude.ai/download. The Connectors UI
   shown below is available on both surfaces.

---

## Setup on claude.ai (Web)

Open the Claude sidebar and follow the steps below. Each screenshot from the
source docs is annotated inline.

### 1. Open Customize

In the Claude sidebar, click **Customize**.

### 2. Open Connectors

In the Customize panel, click **Connectors**.

### 3. Add a custom connector

Click the **+** button at the top of the Connectors list and choose
**Add custom connector**.

### 4. Enter the Sectors connector details

In the dialog, set:

- **Name**: `Sectors`
- **URL**: `https://sectors-mcp.supertype.ai/mcp`

Leave the advanced settings at their defaults and click **Add**.

### 5. Authorize access

Claude opens the Sectors authorization page in a new window. Review the
requested permission (**Read access to Sectors API**) and click **Allow Access**.

Sign in to your Sectors account if you aren't already. Your existing
subscription limits and credits apply to all requests made through the
connector.

### 6. Confirm the connection

Back in Connectors, **Sectors Mcp** now appears under **Web** with all 65+
tools listed. From here you can toggle tool permissions individually
(**Always allow** / **Ask** / **Never**) using the icons on the right of each
tool row.

For the full tool catalog with parameters and response shapes, see
[`tools.md`](tools.md).

---

## Setup on Claude Desktop

Claude Desktop uses the same Connectors UI as the web app. Open the Desktop
app, click your profile → **Customize** → **Connectors**, then follow steps
3–6 above. The connector you add is synced to your Claude account, so a
connector added on the web will also appear in Desktop and vice versa.

> Make sure you're on a recent version of Claude Desktop. If **Connectors**
> doesn't appear under **Customize**, update the app from
> https://claude.ai/download and restart it.

---

## Verify it works

Open a new chat and try:

> Give me an overview of Bank Central Asia (BBCA) using the Sectors connector.

Claude will request permission to call `fetch-company-report` (unless you've
already set it to **Always allow**), then return the company's sector, market
cap, last close price, and index memberships.

If the tool call succeeds, you're done. For more example prompts and the
full tools reference, see the [main Sectors MCP guide][mcp-guide].

[mcp-guide]: https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide#usage-examples

---

## Managing access

- **Tool permissions** — In **Customize → Connectors → Sectors Mcp**, expand
  the tools list and set each tool to **Always allow**, **Ask**, or **Never**.
  This is per-tool and per-user.
- **Disconnect** — Click **Disconnect** at the top of the connector panel to
  remove it from Claude.
- **Revoke from Sectors** — You can also revoke the OAuth grant from your
  Sectors dashboard. After revoking, Claude tool calls will start failing
  with a 401 until you reconnect.

---

## Troubleshooting

**The connector doesn't show up after I add it.**

Refresh the Connectors page, or close and reopen Claude. If you added it on
Desktop and don't see it on the web (or vice versa), give it a few seconds —
sync isn't always instant.

**Authorization loops back to the login screen.**

This usually means you're signed into the wrong Sectors account, or your
session has expired. Open https://sectors.app in the same browser, confirm
you're signed in, then retry the connector authorization.

**Tools return `401 Unauthorized` after authorizing.**

The OAuth grant may have been revoked from your Sectors dashboard, or your
Insider subscription has lapsed. Reconnect the connector — Claude will
redirect you to authorize again.

**A tool returns an empty array.**

Same causes as the API key flow: wrong subsector slug, ticker not found, or
a date range with no trading days. See
[setup.md → Data & coverage](setup.md#data--coverage) for the full list.

---

## Next steps

- [Full tools reference and usage examples][mcp-guide] — all 65+ tools, what
  they return, key parameters.
- [Sectors Agent Skills](https://docs.sectors.app/recipes/sectors-for-ai-agents/01-agent-skills-guide)
  — alternative integration that ships as a Claude Skill instead of an MCP
  connector.
- [`setup.md`](setup.md) — Claude Code / Cursor / VS Code / Windsurf /
  JetBrains setup with API key auth.
- [`chatgpt-integration.md`](chatgpt-integration.md) — same OAuth flow for
  ChatGPT with Developer mode.
- [`../recipes/`](../recipes/) — agent patterns on top of the tools.
