# Sectors MCP — Setup

Connect your AI client to the cloud-hosted Sectors MCP server and unlock 65+
tools covering IDX (Indonesia), SGX (Singapore), KLSE (Malaysia), and
Indonesian mining data. All setups target the same endpoint — only the auth
header, config file location, and one-time restart differ per client.

> Source: https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide (verified 2026-08-29).
> Companion REST catalog: [`../sectors-api-and-mcp.md`](../sectors-api-and-mcp.md).
> Tool-by-tool reference: [`tools.md`](tools.md).
>
> For Claude (web/desktop) and ChatGPT, see the OAuth custom-connector guides —
> [`claude-integration.md`](claude-integration.md) and
> [`chatgpt-integration.md`](chatgpt-integration.md). The instructions below
> cover every other Streamable-HTTP-capable client.

---

## TL;DR — the one endpoint

| Setting              | Value                                  |
| -------------------- | -------------------------------------- |
| Transport            | `http` (Streamable HTTP)               |
| URL                  | `https://sectors-mcp.supertype.ai/mcp` |
| Authorization header | `Bearer YOUR_SECTORS_API_KEY`          |

The MCP server is cloud-hosted on Cloudflare Workers. No local install, no
stdio subprocess. The same `Authorization: Bearer <key>` header is used by every
client; the key is generated from your Sectors Insider plan (or hackathon
onboarding) at https://sectors.app/api.

> **REST vs MCP**: REST uses raw key (`Authorization: <key>`, no `Bearer`).
> MCP uses `Authorization: Bearer <key>`. Same key value, different wrapper.
> Don't paste your REST key into MCP without the `Bearer` prefix — you'll get a
> 401 every time. See [`../sectors-api-and-mcp.md`](../sectors-api-and-mcp.md) §"Auth — concrete".

---

## Prerequisites

1. **A Sectors API key** from an Insider plan or hackathon onboarding
   (https://sectors.app). Forever-Free and Standard plans do NOT include API
   access; upgrade or claim hackathon credits before continuing.
2. **An MCP-compatible client**. As of 2026-08-29 this includes:
   - [Claude Code](https://claude.com/claude-code) (terminal)
   - [Claude (web/desktop)](https://claude.ai) — see [`claude-integration.md`](claude-integration.md) for the OAuth path
   - [Cursor](https://cursor.com)
   - [VS Code](https://code.visualstudio.com) with GitHub Copilot Chat
   - [Windsurf](https://windsurf.com)
   - [JetBrains IDEs](https://www.jetbrains.com/) (IntelliJ, PyCharm, etc.)
   - Any other client that speaks Streamable HTTP (custom SDK, Postman MCP, etc.)

---

## Claude Code

One command, no config file. Run in any terminal where you want the MCP server
available — it stores the config in your user-level Claude Code settings, so the
server persists across projects on the same machine.

```bash
claude mcp add -t http sectors https://sectors-mcp.supertype.ai/mcp \
  -H "Authorization: Bearer YOUR_API_KEY_HERE"
```

Replace `YOUR_API_KEY_HERE` with your Sectors API key. Verify the registration:

```bash
claude mcp list
```

You should see `sectors: https://sectors-mcp.supertype.ai/mcp (HTTP)` in the
output. Restart any open Claude Code sessions — most clients only load MCP
servers at startup.

> **Pitfall**: the `Bearer` prefix is required. If you accidentally omit it
> (or copy from the REST example which uses no prefix), every tool call returns
> `401 Unauthorized`. Re-run the command above with the correct header value.

---

## Cursor

Edit (or create) `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "sectors": {
      "url": "https://sectors-mcp.supertype.ai/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}
```

Restart Cursor completely. The Sectors tools become available in **Agent mode**
(regular chat mode does not surface MCP tools). Click the tools icon in the
composer pane to confirm 65+ tools are listed.

> **Pitfall**: edits to `mcp.json` only take effect on full restart, not on
> reload-window. Quit Cursor entirely (Cmd+Q / Alt+F4) and reopen.

---

## VS Code (Copilot Chat)

VS Code supports per-workspace MCP config. Create `.vscode/mcp.json` in your
project root:

```json
{
  "servers": {
    "sectors": {
      "type": "http",
      "url": "https://sectors-mcp.supertype.ai/mcp",
      "headers": {
        "Authorization": "Bearer ${input:sectors-api-key}"
      }
    }
  },
  "inputs": [
    {
      "type": "promptString",
      "id": "sectors-api-key",
      "description": "Your Sectors Financial API key",
      "password": true
    }
  ]
}
```

VS Code will securely prompt you for the key the first time the server starts
in each session. The key is held in memory only — it won't persist across
restarts (by design). Reopen VS Code and confirm via
**View → Command Palette → "MCP: List Servers"** — `sectors` should show
"Running" with 65+ tools.

> **Pitfall**: this config is workspace-scoped, not global. Copy `.vscode/mcp.json`
> into every project where you want Sectors data, or use the
> "MCP: Add Server" command for a user-level install.

---

## Windsurf

Windsurf reads the same `~/.cursor/mcp.json` format (it's a Cursor-family
client). Use the Cursor config above verbatim. Restart Windsurf and verify in
the Cascade panel's tool list.

---

## JetBrains IDEs (IntelliJ, PyCharm, GoLand, WebStorm, etc.)

JetBrains added MCP support to its AI Assistant in 2025. Open **Settings →
Tools → AI Assistant → MCP Servers** (exact path varies by IDE version) and add
a new server:

- **Name**: `sectors`
- **URL**: `https://sectors-mcp.supertype.ai/mcp`
- **Headers**: `Authorization: Bearer YOUR_API_KEY_HERE`

The IDE validates the URL, prompts you to allow each tool on first use, and
lists them in the AI Assistant chat panel.

> **Pitfall**: not every JetBrains IDE version has MCP. If the MCP Servers
> settings panel is missing, update to the latest stable build (2025.2+).

---

## Generic Streamable HTTP client

If you're writing your own client (Python, Node, Go, anything that speaks HTTP),
the connection is just a JSON-RPC-style Streamable HTTP request. The minimum
viable config:

| Setting              | Value                                  |
| -------------------- | -------------------------------------- |
| Transport            | `http` (Streamable HTTP, MCP spec)     |
| URL                  | `https://sectors-mcp.supertype.ai/mcp` |
| Authorization header | `Bearer YOUR_API_KEY_HERE`             |
| Content-Type         | `application/json`                     |
| Method               | `POST` (handshake + tool calls)        |

The official MCP SDKs (`@modelcontextprotocol/sdk` for Node, `mcp` for Python,
`mcp` for Go) all accept the same triplet: transport type, URL, headers. There
is no separate "register" or "login" step — the first POST negotiates the
session and the same Bearer header authenticates every subsequent tool call.

Reference snippets:

```python
# Python (using the official mcp package)
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

headers = {"Authorization": f"Bearer {SECTORS_API_KEY}"}

async with streamablehttp_client(
    "https://sectors-mcp.supertype.ai/mcp", headers=headers
) as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        # tools.tools -> list of 65+ Tool objects
```

```typescript
// TypeScript (using @modelcontextprotocol/sdk)
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";

const client = new Client(
  { name: "sectors-client", version: "1.0.0" },
  { capabilities: {} }
);

const transport = new StreamableHTTPClientTransport(
  new URL("https://sectors-mcp.supertype.ai/mcp"),
  { requestInit: { headers: { Authorization: `Bearer ${process.env.SECTORS_API_KEY}` } } }
);

await client.connect(transport);
const { tools } = await client.listTools();
// tools -> array of 65+ tool descriptors
```

---

## Troubleshooting & FAQ

### Setup

**The server doesn't appear in my MCP client after setup.**
Restart your client completely after editing the config — most clients only
load MCP servers on startup. For Claude Code, run `claude mcp list` in the
terminal to confirm the server is registered.

**VS Code keeps prompting me for the API key on every session.**
This is expected. The VS Code config uses `${input:sectors-api-key}` which
prompts once per session and stores the value in memory. It won't persist
across restarts by design.

**Windsurf shows no tools in the Cascade panel.**
Verify `~/.cursor/mcp.json` is valid JSON (no trailing comma, quotes around all
strings). Quit Windsurf entirely and reopen — Cascade reads MCP at startup.

---

### Authentication

**I'm getting a `401 Unauthorized` error on every tool call.**

Check all three:

1. The key is correct and belongs to an active Insider plan (or hackathon
   onboarding). Test it against REST first:
   ```bash
   curl -H "Authorization: YOUR_RAW_KEY" https://api.sectors.app/v2/subsectors/
   ```
   A 200 response means the key is good; a 401 means it's wrong or the plan
   has lapsed.
2. The header value is `Bearer YOUR_API_KEY_HERE` — the `Bearer ` prefix is
   required for MCP. The REST API does NOT use Bearer; the MCP server DOES.
3. There are no extra spaces or line breaks in the key value. Trim whitespace
   before pasting.

**My API key works on the Sectors website but not in the MCP server.**

The MCP server uses the same key as the Sectors Financial API. Copy the key
from https://sectors.app/api, not from a cached or expired token. The
"Forgot key?" flow on the site resets the value — the old value stops working
immediately.

**Do I need separate keys for REST and MCP?**

No. One Sectors API key works for both. The only difference is the header
format (`Authorization: <key>` for REST, `Authorization: Bearer <key>` for MCP).

---

### Data & coverage

**Which markets does the Sectors MCP server cover?**

Three Southeast Asian exchanges:

- **IDX** — Indonesia Stock Exchange (primary coverage, 40+ tools across
  equities, brokers, filings, mining)
- **SGX** — Singapore Exchange (full company reports, rankings, dividends)
- **KLSE** — Bursa Malaysia (basic company report and sector data)

Plus a full **Indonesian mining** dataset (commodity prices, sites, licenses,
auctions).

**What ticker format should I use?**

All IDX tools accept the bare ticker **without** the `.JK` suffix (e.g.
`BBCA`, `TLKM`). Do not include `.JK` — the API handles the formatting
internally. SGX tickers use the SGX code directly (`D05`, `O39`). KLSE tickers
are 4-digit numeric (`1155`, `4197`, `5225`).

> The REST API tolerates `.JK`/`.si`/`.KL` suffixes; the MCP server expects
> bare tickers. See [`../sectors-api-and-mcp.md`](../sectors-api-and-mcp.md)
> §"Ticker conventions" for the full table.

**A tool returned an empty array or no results.**

Most common causes:

- **Wrong subsector slug** — subsector names are in kebab-case
  (`banks`, `software-it-services`). Use `get-subsectors` to get the exact
  list of valid slugs.
- **Ticker not found** — double-check the symbol. If the company exists on the
  exchange, the bare ticker should resolve.
- **Date range with no trading days** — for daily-transaction tools, ensure
  the range includes at least one trading day. Weekends and IDX holidays return
  empty results.

**How fresh is the data?**

> "Market prices and daily transaction data are updated at end-of-day.
> Quarterly financials are updated as companies file their reports. Dividend
> data is updated when announcements are made."
>
> — Source: https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide (verified 2026-08-29).

For automation that depends on EOD data, schedule cron at 08:00 WIB (after
IDX close + buffer). Real-time intraday tick data is out of scope — there is no
streaming/WebSocket API.

---

## Next steps

- **Tool catalog** — [`tools.md`](tools.md) lists all 65+ tools with
  parameters, return shapes, and equivalent REST endpoints.
- **Claude (web/desktop)** — [`claude-integration.md`](claude-integration.md)
  shows the OAuth custom-connector path with one-click sign-in.
- **ChatGPT** — [`chatgpt-integration.md`](chatgpt-integration.md) walks through
  Developer mode and the custom MCP app flow.
- **Agent recipes** — [`../recipes/`](../recipes/) covers generative AI
  patterns: tool-use RAG, multi-agent workflows, structured output, ReAct
  agents, conversational memory, and the FinArena-style Human-Agent
  Collaboration framework.
- **REST catalog** — [`../sectors-api-and-mcp.md`](../sectors-api-and-mcp.md)
  for cron-friendly REST endpoints.
