# Sectors Quickstart

> Minimum-viable first request in every stack we plan to use.
> Everything below assumes you already have a Sectors API key (generate it at <https://sectors.app/api> after onboarding; see [`sectors-api-and-mcp.md`](sectors-api-and-mcp.md) for the 1,000-credit grant context).

## Pick your stack

| If you're building...                                | Use...            | Read first                                          |
| --------------------------------------------------- | ----------------- | --------------------------------------------------- |
| A scheduled cron / CI script / batch pipeline        | REST              | `references/rest/idx-screener.md` (Lane 1)          |
| An AI agent inside Claude Code / Cursor / VS Code    | MCP               | `references/mcp/setup.md` (Lane 2)                  |
| A no-code dashboard for non-developers               | Looker / Excel / Sheets | `references/cookbook/looker.md` (this lane)     |
| A workflow automation (alerts, scheduled jobs, chat) | n8n               | `references/cookbook/n8n-api.md` (this lane)        |
| A Python data app (Streamlit, Jupyter)               | REST + Streamlit  | `references/cookbook/sectorscan-part1.md` (this lane) |
| An R analytics / content workflow                    | REST + `httr`     | `references/cookbook/r-animations.md` (this lane)   |
| A notebook that scores stocks by peer behaviour     | REST + PyTorch Geometric | `references/cookbook/gnn-anomaly-1.md` (this lane) |
| A portfolio optimizer / benchmarker                  | REST + SciPy / pandas | `references/cookbook/portfolio-optimization.md` |
| Indonesian mining commodity / site / license data    | REST              | `references/rest/mining.md` (Lane 1, when merged) — FYI tag below |

> **FYI — SGX / KLSE coverage:** the Sectors API covers Singapore (SGX, e.g. `D05`) and Malaysia (KLSE, e.g. `1155`) too, but the **hackathon rules §06 restrict submissions to Indonesian data only**. Treat SGX/KLSE endpoints as out-of-scope; everything in this cookbook assumes IDX tickers (`BBCA`, `BMRI`, ...) and Indonesian mining (commodities, sites, license auctions). If you want SGX/KLSE recipes, see the upstream docs at <https://docs.sectors.app/recipes/> — don't lift them into a submission.

All paths are **relative to this `references/` folder**. Cookbooks live one level deeper in `cookbook/`.

---

## First request — Python + REST (the universal baseline)

```python
import requests

API_KEY = "<your_sectors_api_key>"          # raw key, NO "Bearer " prefix
url     = "https://api.sectors.app/v2/subsectors/"

r = requests.get(url, headers={"Authorization": API_KEY})
r.raise_for_status()
data = r.json()                              # list of {sector, subsector}
```

That endpoint is cheap (one credit) and tells you the kebab-case subsector slugs (`banks`, `software-it-services`, ...) that every other endpoint expects.

For a per-symbol report:

```python
r = requests.get(
    "https://api.sectors.app/v2/company/report/BBCA",
    headers={"Authorization": API_KEY},
    params={"sections": "overview,valuation"},   # only what you need → saves credits
)
```

---

## First request — Claude Code + MCP

```bash
claude mcp add -t http sectors https://sectors-mcp.supertype.ai/mcp \
  -H "Authorization: Bearer <your_sectors_api_key>"
```

Restart Claude Code. You can now ask things like:

> "Use Sectors to list the top 5 banks by market cap and fetch their dividend sections."

The MCP server exposes ~65 tools (`fetch-company-report`, `fetch-companies-by-subsector`, `fetch-most-traded-stocks`, ...) — see [`sectors-api-and-mcp.md`](sectors-api-and-mcp.md#mcp-tool-catalog-if-we-go-mcp-instead-of-rest) for the full cheat sheet.

---

## First request — Node + REST (n8n / JS pipelines)

```javascript
const r = await fetch("https://api.sectors.app/v2/subsectors/", {
  headers: { Authorization: process.env.SECTORS_API_KEY },  // raw key, NO "Bearer "
});
if (!r.ok) throw new Error(`HTTP ${r.status}`);
const data = await r.json();
```

In n8n specifically, configure the HTTP Request node as:
- **Authentication** → *Generic Credential Type* → *Header Auth*
- **Header Name**: `Authorization`
- **Header Value**: `<your raw API key>` (n8n sends it verbatim — do not prepend "Bearer" for REST)

---

## First request — R

```r
library(httr)
library(jsonlite)

api_key <- "your_sectors_api_key"
url     <- "https://api.sectors.app/v2/subsectors/"
response <- GET(url, add_headers(Authorization = api_key))    # raw key

data <- fromJSON(content(response, "text"), flatten = TRUE)
```

---

## Common traps (TL;DR)

These trip every new Sectors builder at least once. Save yourself the credits:

1. **v1 is dead.** Always use `https://api.sectors.app/v2/...`. `/v1/*` returns HTTP 410 Gone since 2026-05-11. Migration was just s/v1/v2/, except three endpoints (`/companies/`, `/companies/top/`, `/companies/most-traded/` are now `/companies/`, `/companies/?order_by=...`, `/companies/?order_by=-yoy_quarter_revenue_growth`).
2. **Auth: REST = raw key. MCP = Bearer.** Both use the same Sectors API key, but:
   - REST: `Authorization: <raw_key>`
   - MCP (Claude Code / Cursor / VS Code / Windsurf): `Authorization: Bearer <raw_key>`
3. **Tickers: drop the `.JK` suffix.**
   - IDX REST tolerates both `BBCA` and `BBCA.JK` (case-insensitive).
   - IDX MCP **requires bare** `BBCA`, `TLKM`, `BMRI`. Passing `BBCA.JK` to `fetch-company-report` returns nothing.
   - **FYI only — SGX / KLSE are out of scope for this hackathon.** SGX uses 3-char codes (`D05`, `U11`, `Z74`); KLSE uses 4-digit numeric (`1155`, `4197`). Don't use these in submissions.
4. **Subsectors are kebab-case slugs**, not CamelCase. Use `/v2/subsectors/` (REST) or `get-subsectors` (MCP) to get the exact list. Common hits: `banks`, `software-it-services`, `consumer-non-cyclicals`, `energy`, `basic-materials`, `mining`.
5. **`sections=` saves credits.** `/v2/company/report/{symbol}/` accepts a comma-separated subset of `overview,valuation,future,peers,financials,dividend,management,ownership`. Default returns everything — choose only what you use.
6. **Universe feeds beat per-symbol loops.** `GET /v2/transaction/close/{date}/` returns every IDX ticker on one date in a paginated feed. `GET /v2/companies/quarterly-financial-dates/` gives you latest-report-dates across the universe. Cheaper than looping N tickers.
7. **`where` syntax supports bracket notation** for time-series fields: `revenue[2024] / total_assets[2024] > 0.5`. Operators: `=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`, `and`/`or`. `limit` 1–200, default 50.
8. **News needs `extension`**: `idx` (default) or `mining`. Without it, `/v2/news/news/` errors out.
9. **No rate-limit headers** in the public docs. Be polite — cache aggressively, prefer universe endpoints, and back off on 429s.
10. **No WebSocket / streaming.** Everything is request/response. If you need intraday data, scrape IDX directly (out of Sectors' scope).
11. **1,000 credits = 42-day window** (Aug 19 – Sep 30 2026). Plan usage: per-symbol report with all sections is ~5–10 credits; universe close feed is ~1; natural-language screener is ~2–3. With 1,000 you get ~100–200 well-scoped calls or ~50 unscoped reports.
12. **The 1,000-credit grant is one-time, gated on team onboarding at sectors.app.** If onboarding isn't done yet, you can read docs but every request 401s.

---

## Where to go next

| Want to ...                                          | File                                              |
| ---------------------------------------------------- | ------------------------------------------------- |
| See the full REST endpoint catalog                   | `references/rest/idx-screener.md` (Lane 1)        |
| See the full MCP tool catalog                        | `references/mcp/setup.md` (Lane 2)                |
| Use it inside a spreadsheet                          | `references/cookbook/excel.md`                    |
| Use it inside Google Sheets                          | `references/cookbook/sheets.md`                   |
| Build a Looker / Google Sheets dashboard             | `references/cookbook/looker.md`                   |
| Wire it into n8n                                     | `references/cookbook/n8n-api.md`                  |
| Build an AI screener in n8n                          | `references/cookbook/n8n-ai-screener.md`          |
| Build a Streamlit app (SectorScan)                   | `references/cookbook/sectorscan-part1.md` + `part2` |
| Detect stock anomalies with a GNN                    | `references/cookbook/gnn-anomaly-1.md` + `2` + `3` |
| Make animated charts in R                            | `references/cookbook/r-animations.md`             |
| Secure the API key properly                          | `references/cookbook/api-security.md`             |
| Build a portfolio optimizer                          | `references/cookbook/portfolio-optimization.md`   |
| Benchmark IDX bank stocks                            | `references/cookbook/benchmark-banking.md`        |
| Compare against other recipes (multi-agent, NLQ)     | `references/recipes/` (Lane 2)                    |

---

## Provenance

> Sources (verified 29 Aug 2026):
> - <https://docs.sectors.app/recipes/quick-start-in-python/00-your-first-request>
> - <https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide>
> - <https://docs.sectors.app/get-started/v2/migration-guide>
> - <https://docs.sectors.app/llms.txt>
> - <https://sectors.app/pricing>