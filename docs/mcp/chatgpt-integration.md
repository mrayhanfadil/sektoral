# Connect Sectors to ChatGPT with OAuth

> Source: https://docs.sectors.app/recipes/sectors-for-ai-agents/03-sectors-in-chatgpt (verified 2026-08-29).
>
> For Claude (web/desktop) see [`claude-integration.md`](claude-integration.md).
> For Claude Code / Cursor / VS Code / JetBrains (API key auth) see
> [`setup.md`](setup.md).

Sectors can be connected to ChatGPT as a **custom MCP app**. Once added,
ChatGPT can call any of the 65+ Sectors tools — company reports, top movers,
quarterly financials, SGX coverage, and more — directly inside a chat.
Authentication uses OAuth with **Dynamic Client Registration**, so there's no
API key to copy and paste.

---

## Prerequisites

1. **A Sectors account on an Insider plan** — required to authorize the
   connector. Forever-Free and Standard plans do not include API access; sign
   up at https://sectors.app to enable.
2. **A ChatGPT plan that supports custom MCP apps in developer mode.** The
   exact tier list changes over time — see OpenAI's
   [Apps SDK / connectors documentation](https://platform.openai.com/docs/guides/apps-sdk)
   for the current requirements.

> Custom MCP apps in ChatGPT live behind a **Developer mode** toggle that
> OpenAI labels **Elevated Risk**. While developer mode is on, ChatGPT
> disables **Memory** and warns that unverified connectors could modify or
> erase data. Only enable it when you need to use Sectors (or other custom
> apps), and disconnect apps you no longer use.

---

## Setup

### 1. Open the Apps page

In the ChatGPT sidebar, click **Apps**.

### 2. Open Apps settings

On the Apps page, click the **gear icon** in the top right corner.

### 3. Open Advanced settings

In the settings dialog, make sure **Apps** is selected in the left sidebar,
then click **Advanced settings**.

### 4. Enable Developer mode

Toggle **Developer mode** on. ChatGPT shows an **ELEVATED RISK** warning and
notes that Memory will be disabled.

Read the warning before continuing. Leave **Enforce CSP in developer mode**
off unless you specifically need it.

### 5. Open the Create app dialog

Once developer mode is on, a **Create app** button appears at the top of the
page. Click it.

### 6. Fill in the Sectors app details

In the New App dialog, set:

- **Name**: `Sectors`
- **Description**: optional — e.g. *Indonesia, Singapore, and Malaysia market
  data via the Sectors API*
- **MCP Server URL**: `https://sectors-mcp.supertype.ai/mcp`
- **Authentication**: `OAuth`

Then check **I understand and want to continue** to acknowledge the custom-MCP
risk notice.

### 7. (Optional) Review Advanced OAuth settings

You can leave Advanced OAuth settings alone — the Sectors MCP server supports
**Dynamic Client Registration**, so ChatGPT discovers the auth, token,
registration, and resource URLs automatically.

If you do open the panel, you'll see DCR selected as the registration method,
and the discovered endpoints (auth URL, token URL, registration URL,
resource URL) filled in for you.

No edits are needed. Click **Create**.

### 8. Authorize Sectors

ChatGPT opens the Sectors authorization page. Sign in if needed, review the
requested permission (**Read access to Sectors API**), and click **Allow
Access**. Your existing subscription limits and credits apply to all requests
made through the app.

---

## Verify it works

Open a new chat and call the app explicitly so ChatGPT routes the request to
it:

> Using the Sectors app, give me an overview of Bank Central Asia (BBCA).

ChatGPT will ask for permission to run the `fetch-company-report` tool, then
return the company's sector, market cap, last close price, and index
memberships. Try a few more prompts from the
[main Sectors MCP guide usage examples][mcp-guide] to confirm other tools
work.

[mcp-guide]: https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide#usage-examples

---

## Managing access

- **Disable the app** — In the Apps settings dialog, find **Sectors** under
  your apps list and toggle it off (or remove it entirely).
- **Turn off developer mode** — Once you've added the apps you want, you can
  leave developer mode on, but disable it when you don't need custom MCP apps.
  Re-enabling later does not delete previously added apps.
- **Revoke from Sectors** — You can revoke the OAuth grant from your Sectors
  dashboard. After revoking, ChatGPT tool calls will fail with a 401 until you
  reconnect.

---

## Troubleshooting

**I don't see a Create app button.**

Developer mode isn't enabled, or your ChatGPT plan doesn't expose custom MCP
apps. Recheck **Advanced settings → Developer mode**, then confirm your plan
supports custom connectors against
[OpenAI's docs](https://platform.openai.com/docs/guides/apps-sdk).

**Dynamic Client Registration fails or endpoints don't auto-populate.**

This usually means the request to the MCP server was blocked (corporate
network, ad blocker) or the server was briefly unreachable. Close and reopen
the Create app dialog, then try again. If it still fails, check
https://status.supertype.ai — or fall back to entering endpoints manually
under Advanced OAuth settings.

**Authorization succeeds but tool calls return `401 Unauthorized`.**

The OAuth grant was likely revoked from your Sectors dashboard, or your
Insider subscription has lapsed. Remove and re-add the Sectors app to trigger
a fresh OAuth flow.

**ChatGPT isn't calling the Sectors app even though it's enabled.**

ChatGPT sometimes won't route to a custom app unless you mention it by name.
Prefix prompts with *"Using the Sectors app, ..."* or *"With Sectors, ..."*
until you confirm it's being picked up consistently.

**Memory disappeared after enabling developer mode.**

This is expected — ChatGPT disables Memory while developer mode is on. Turn
developer mode off (your apps stay added) to restore Memory.

---

## Comparison: Claude vs ChatGPT vs Streamable HTTP

| Setup                | Auth                | Best for                                  |
| -------------------- | ------------------- | ----------------------------------------- |
| Claude (web/desktop) | OAuth custom connector | One-click sign-in, no config files    |
| ChatGPT (web)        | OAuth custom app    | One-click sign-in, but requires Developer mode + ChatGPT plan support |
| Claude Code          | Bearer API key      | Terminal workflows, project-scoped         |
| Cursor / VS Code     | Bearer API key      | Editor-integrated agents                   |
| Generic HTTP client  | Bearer API key      | Custom SDKs, batch automation              |

For all auth-key setups, see [`setup.md`](setup.md).

---

## Next steps

- [Full tools reference and usage examples][mcp-guide] — what each of the
  65+ tools returns.
- [Sectors Agent Skills](https://docs.sectors.app/recipes/sectors-for-ai-agents/01-agent-skills-guide)
  — alternative skill-based integration if you prefer not to use developer mode.
- [`claude-integration.md`](claude-integration.md) — same OAuth flow for
  Claude (web/desktop).
- [`setup.md`](setup.md) — Claude Code / Cursor / VS Code / Windsurf /
  JetBrains setup with API key auth.
- [`../recipes/`](../recipes/) — agent patterns on top of the tools.
