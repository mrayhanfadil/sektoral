# n8n — General Sectors API integration

> Source: <https://docs.sectors.app/recipes/non-programmatical-tools/04-n8n/01-n8n-sectors-api-guide>
> Author of original recipe: Andreas Christianto, Mar 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Use **n8n** as a visual orchestrator for the Sectors API. This file covers the **general integration** patterns — for the AI-screener chat workflow specifically, see [`n8n-ai-screener.md`](n8n-ai-screener.md).

Two reference workflows in this file:

1. **Workflow 1 — Single API call** (Manual Trigger → HTTP Request): the universal building block. Fetches a company report on demand.
2. **Workflow 2 — Scheduled top movers to Discord**: a complete automation that fires daily at 7 AM, transforms data, and posts to a channel.

## When to use n8n (vs. Sheets/Excel/MCP/scripts)

| Need | Tool |
|------|------|
| Daily/weekly scheduled report | **n8n** (or cron + script) |
| One-off ad-hoc fetches | n8n manual trigger, or just curl |
| Static dashboard | Looker Studio or Sheets |
| Conversational AI agent | MCP, or `n8n-ai-screener.md` |
| Browser-side / interactive | Streamlit (`sectorscan-part1.md`) |

n8n wins when you need **scheduling + branching + delivery to multiple sinks** without writing a script that owns its own cron + retry + auth.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents / assistants | medium | The AI screener variant is a Track 1 staple. The non-AI variant below is less so. |
| Track 2 — Automation workflows | **high** | n8n is the canonical low-code automation track. |
| Track 3 — Market intelligence / apps | medium | n8n is plumbing, not a user-facing artefact — pair it with a webhook that pushes to a chat/dashboard. |

## Cost estimate

n8n itself: free if self-hosted, ~€20/mo for n8n Cloud. The Sectors API: same ~5–10 credits per refresh of a small workflow. The Discord webhook receiver is free.

## Setup (one-time)

1. **n8n instance**: cloud at <https://n8n.io/cloud>, or self-host (Docker image `n8nio/n8n`).
2. **Sectors API key**: from <https://sectors.app/api>.
3. **Discord webhook** (only for Workflow 2): in Discord → channel → `Edit Channel` → `Integrations` → `Webhooks` → `Create Webhook` → copy URL.

## Workflow 1 — Single API call (the universal building block)

### Nodes

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Manual Trigger | `Trigger manually` | Execute on demand |
| 2 | HTTP Request | `http request` | Calls Sectors API |

### Configuration

**HTTP Request node:**

| Field | Value |
|-------|-------|
| Method | `GET` |
| URL | `https://api.sectors.app/v2/company/report/BBCA` |
| Authentication | `Generic Credential Type` → `Header Auth` |

For the Header Auth credential:

| Header Name | Header Value |
|-------------|--------------|
| `Authorization` | `<your raw Sectors API key>` (no `Bearer` prefix for REST) |

Click `Execute step` to verify. The OUTPUT panel will show the JSON response with overview, valuation, financials, dividend, etc. sections.

**Why `Header Auth` and not OAuth or generic API key?** n8n's `Header Auth` is the simplest model that matches Sectors' raw-key approach. OAuth adds ceremony you don't need. Save OAuth for cases where the upstream provider enforces it.

### Variations

Change the URL to any endpoint. Common shapes:

```text
# Daily price/volume for one ticker (90 days max)
https://api.sectors.app/v2/transaction/daily/{symbol}/?start=2026-08-01&end=2026-08-29

# Company report with specific sections only (saves credits)
https://api.sectors.app/v2/company/report/{symbol}/?sections=overview,valuation,dividend

# Screener with natural language
https://api.sectors.app/v2/companies/?q=top+5+banks+by+market+cap&limit=5

# Top movers today
https://api.sectors.app/v2/ranking/top-changes/?classifications=top_gainers,top_losers&periods=1d

# Subsector list (kebab-case slugs)
https://api.sectors.app/v2/subsectors/
```

---

## Workflow 2 — Scheduled top movers to Discord

### Nodes

| # | Node | Type | Purpose |
|---|------|------|---------|
| 1 | Schedule Trigger | `schedule trigger` | Fires daily at 07:00 |
| 2 | HTTP Request | `http request` | Calls `/v2/ranking/top-changes/` |
| 3 | Code | `code` | Transforms JSON to Discord message string |
| 4 | HTTP Request | `http request` | POSTs to Discord webhook |

### Node configuration

**Schedule Trigger**: cron expression for 07:00 daily, or use the visual time picker.

**HTTP Request #1 (Sectors API)**:

| Field | Value |
|-------|-------|
| Method | `GET` |
| URL | `https://api.sectors.app/v2/ranking/top-changes/` |
| Authentication | Header Auth → your Sectors credential |
| Query Parameters | `classifications` = `top_gainers,top_losers`, `periods` = `1d`, `n_stock` = `10` |

**Code node** (JavaScript, `Run Once for All Items`):

```javascript
const data = $input.all()[0].json;
const gainers = data.top_gainers['1d'];
const losers  = data.top_losers['1d'];

const formatChange = (change) => {
  const pct = (change * 100).toFixed(2);
  return pct.startsWith('-') ? pct : `+${pct}`;
};

const formatList = (stocks, emoji) =>
  stocks.map(s => `${emoji} ${s.symbol.replace('.JK', '')} — ${s.name} | Rp ${s.close.toLocaleString('id-ID')} | ${formatChange(s.change_pct)}%`).join('\n');

const today = new Date().toLocaleDateString('id-ID', { dateStyle: 'full' });

const message = [
  `📈 *Top Gainers — ${today}*`,
  formatList(gainers, '🟢'),
  '',
  `📉 *Top Losers — ${today}*`,
  formatList(losers, '🔴'),
  '',
  '_Source: sectors.app_',
].join('\n');

return [{ json: { content: message } }];
```

Three things worth noting:

- `formatChange` multiplies by 100 — the API returns raw decimals (e.g. `0.05`), this converts to `+5.00`.
- `.JK` is stripped so `BBCA.JK` becomes `BBCA` for cleaner display.
- `return [{ json: { ... } }]` — n8n requires every item wrapped in `{ json: ... }`.

**HTTP Request #2 (Discord)**:

| Field | Value |
|-------|-------|
| Method | `POST` |
| URL | your Discord webhook URL |
| Send Body | ON |
| Body Content Type | `JSON` |
| Specify Body | `Using Fields Below` |
| Body Parameters | name=`content`, value=`{{ $json.content }}` |

`{{ $json.content }}` references the Code node's output field.

### Test and publish

1. Click `Execute workflow`. All four nodes should turn green.
2. Check Discord — the message lands in the configured channel.
3. Click `Publish`, name it (e.g. `v1.0`), publish.

The workflow runs daily at 07:00 until you deactivate it.

## Known pitfalls

- **Discord webhook leakage**: anyone with the webhook URL can post to your channel. Treat it like a password — don't commit it to a public repo. In n8n, store it as a credential, not in the URL field literally.
- **`.JK` suffix in screener results**: `data.top_gainers['1d'][0].symbol` returns `BBCA.JK` — strip it before display or before passing into another endpoint that doesn't tolerate `.JK`.
- **Empty arrays**: if a day has no trading (holiday), `top_gainers['1d']` may be `[]`. Defensive code: `formatList(gainers ?? [], '🟢')`.
- **Ticker format mismatch**: when passing screener results into other endpoints via expression, strip `.JK`:
  ```text
  {{ $json.symbol.replace('.JK', '').replace('.jk', '') }}
  ```
- **Schedule timezone**: n8n uses the server's timezone unless overridden. Set `workflow timezone` in workflow settings to `Asia/Jakarta` so "7 AM" means 07:00 WIB, not UTC.
- **Auth value**: pasting `Bearer <key>` into the Header Auth value field will make every request return 401. The Sectors API REST expects the raw key without `Bearer`. Only MCP tools need the Bearer prefix.

## Cross-links

- AI screener variant: [`n8n-ai-screener.md`](n8n-ai-screener.md)
- Manual / non-n8n version: [`excel.md`](excel.md) or [`sheets.md`](sheets.md)
- Streamlit version: [`sectorscan-part1.md`](sectorscan-part1.md)
- REST endpoints referenced: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)