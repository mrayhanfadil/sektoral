# Sectors API Cookbook v2 — Worked Examples

> Source of truth: live docs at https://docs.sectors.app (verified 29 Aug 2026).
> Cross-reference: `../sectors-api-and-mcp.md` (high-level overview).

This cookbook is a set of **copy-pasteable Python recipes** for the Sectors Financial API v2. Every example assumes IDX tickers in bare form (`BBCA`, not `BBCA.JK`). Each recipe is self-contained, runnable after you drop in an API key, and grounded in the live OpenAPI contract — not hand-waved.

## Who this is for

Hackathon builders who need to ship IDX / mining / broker data workflows on a **1,000-credit hackathon budget**. The recipes are tuned for that constraint: each one shows its credit cost, and the patterns (paged universe feeds, section selection, freshness polling) are exactly the moves that stretch a 1,000-credit quota across a 6-week build.

## Setup

```bash
pip install requests
export SECTORS_API_KEY="sk_live_xxx..."   # raw key, NO "Bearer " prefix
```

The recipes expect either `SECTORS_API_KEY` in the environment or a `sectors_key.txt` next to the script. Auth header is **raw key**, no `Bearer` prefix — this is the single biggest "why doesn't this work?" gotcha.

```python
# standard header for every request
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}
BASE = "https://api.sectors.app"
```

## Recipes (in order of usefulness)

| # | Recipe | What it does | Track fit | ~Credits |
|---|--------|--------------|-----------|----------|
| 01 | [Screener with `where` + bracket notation](01-screener.md) | Filter + sort IDX companies by SQL-like conditions, bracket-year fields, and arithmetic | All | 1 per call (3 with `q=`) |
| 02 | [Company deep-dive with section selection](02-company-deep-dive.md) | Pull only the sections you need from `/v2/company/report/{symbol}/` | AI Agents / Market Intel | 1 per section (8 default) |
| 03 | [Quarterly freshness polling](03-quarterly-freshness.md) | Incremental "which IDX companies reported a new quarter since X?" feed | Automation / Market Intel | ~32 full sweep / `~1` per `since=` poll |
| 04 | [Universe feed (full-IDX daily close + market cap)](04-universe-feed.md) | Paginated every-ticker pull for one date + IDX total market cap | Market Intel / Automation | ~33 (close 32 + idx-total 1) |
| 05 | [Top movers + most-traded](05-rankings-movers.md) | Top gainers/losers per period + most-traded-by-volume | Market Intel / Automation | 1–10 depending on selections (default top-changes = 10) |
| 06 | [Broker & foreign-flow analysis](06-broker-foreign-flow.md) | Top broker rankings + per-symbol net foreign inflow | AI Agents / Market Intel | 2 + 2 + 1 |
| 07 | [Mining: coal end-to-end](07-mining-coal.md) | Find coal operators, pull commodity prices, list top sites, top export destinations | Market Intel / All | 6 |
| 08 | [Production error handling + retry](08-error-handling.md) | Single robust wrapper that all 7 above plug into | All | n/a — wrapper, not a call |

## Credit math cheatsheet

From the live docs (https://docs.sectors.app → "Billing & Credits"):

| Response | Consumes credits? |
|---|---|
| `2xx` success | **Yes** — endpoint's stated cost |
| `404` (resource not found) | **Yes — 1 credit** (the lookup ran, just returned nothing) |
| `400` bad request | **No**, *except* `?q=` natural-language screener after the LLM ran (then 1 credit) |
| `401 / 403` auth | **No** |
| `429` rate-limit | **No** |
| `5xx` server error | **No** |

Practical translation for the hackathon budget:

- A **structured** screener (`where` + `order_by`) = **1 credit**.
- A **natural-language** screener (`?q=...`) = **3 credits** (LLM cost is passed through).
- **Company report**: 1 credit per section requested — `sections=overview,valuation` = 2 credits, NOT the default 8.
- **Quarterly financials**: 1 credit per quarter returned. `n_quarters=4` = 4 credits.
- **Universe feeds** (`/v2/close/`, `/v2/companies/quarterly-financial-dates/`): 1 credit per page, max 30 results per page. Full IDX universe (~950 tickers) = ~32 pages = ~32 credits per full sweep. Use `since=` on the quarterly-dates endpoint to poll incrementally for ~1 credit per poll.
- **Top-changes**: 1 credit per `classification × period` combo. Default (2 classifications × 5 periods) = **10 credits**. Always trim: `classifications=top_gainers&periods=1d,7d` = 2 credits.
- **Most-traded**, **broker top**, **broker summary top**: **2 credits each** flat.
- All other endpoints: **1 credit** flat.

## Conventions used in every recipe

- **Ticker format**: bare `BBCA`, `BMRI`, `TLKM`, `GOTO` — never `BBCA.JK`. (The API tolerates `.JK` in REST, but the bare form is what MCP tools demand and the form we use everywhere else.)
- **Date format**: `YYYY-MM-DD` always. Future dates return 400 (free, not billed).
- **IDR amounts**: integer IDR, not float. `market_cap`, `revenue`, etc. are whole rupiah.
- **Pagination**: every list endpoint returns `{results: [...], pagination: {total_count, showing, limit, offset, has_next, next_offset}}`. `next_offset` is `null` when `has_next` is `false`.
- **204-credit minimum cost call you can make**: a structured screener with `limit=1` = 1 credit. Use this in dev loops.

## How to read each recipe

Every file follows the same shape:

1. Header with track fit, endpoints exercised, credit cost.
2. **What this demonstrates** — the 2-3 things the snippet teaches.
3. **Code** — a single self-contained Python snippet. Drop in your key and run.
4. **Expected output shape** — verbatim from the live docs' response examples.
5. **Pitfalls** — the things that wasted credits during testing.
6. **Variations** — how to adapt for the three tracks.

All snippets have been AST-parsed to confirm they're syntactically valid Python (no live API calls were made — we have no key). Endpoint URLs, parameter names, and response shapes are pulled directly from the v2 OpenAPI specs at `https://docs.sectors.app/api-references/v2/...`.
