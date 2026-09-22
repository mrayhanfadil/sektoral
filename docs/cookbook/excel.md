# Excel Power Query → Sectors API

> Source: <https://docs.sectors.app/recipes/non-programmatical-tools/01-excel/01-excel>
> Author of original recipe: Vincentius C. Calvin (Jul 2024)
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Pull live IDX data into Excel using **Power Query** — no Python, no VBA. Refresh on demand and re-run with one click when new reports land.

## When to use this approach

- Audience is non-developers (analysts, IB interns, retail investors) who already live in Excel.
- You need a static, refreshable worksheet for a recurring watchlist (screener results, daily movers, fundamentals).
- You want to skip deploying a script or notebook — Excel becomes the artefact.

**Not for**: streaming tickers, programmatic control, multi-symbol fan-out. Use the cookbook's n8n or REST recipes for that.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents / assistants | low | Power Query doesn't talk to an LLM. Use Lane 2 (MCP) or `n8n-ai-screener.md` for agent-style workflows. |
| Track 2 — Automation workflows | medium | A scheduled Power Query refresh is possible via OneDrive/SharePoint, but n8n is more flexible. |
| Track 3 — Market intelligence / apps | high | A "live IDX screener workbook" is a legit submission if you dress it up with charts and a slide. |

## Cost estimate

Power Query doesn't carry its own credit cost — each refresh calls the API once per query. A typical workbook with 5–10 queries refreshes in ~5–10 credits. Set `Refresh All` to run hourly during the day and you'll burn ~80–100 credits for an 8-hour session. Cache aggressively by limiting the query list to the watchlist you actually watch.

## End-to-end walkthrough

### 1. Connect Excel to the Sectors API

`Data` tab → `Get Data` → `From Other Sources` → `From Web` → switch to **Advanced**.

Fill in:

| Field | Value |
|-------|-------|
| URL parts | `https://api.sectors.app/v2/transaction/daily/bbca` (start with this; we'll switch endpoints later) |
| HTTP request header parameter (left) | `Authorization` |
| HTTP request header parameter (right) | `<your raw Sectors API key>` (no `Bearer` prefix for REST) |

If Power Query throws a credentials error on the first try, this is a known Power Query quirk:

1. Click **Back**.
2. Change the URL to `https://api.sectors.app/health/` and click **OK** (this works because the `/health/` endpoint doesn't care about your key shape).
3. Open **View → Advanced Editor** and replace the URL in the `Web.Contents(...)` call with the real one (`/v2/transaction/daily/bbca`).
4. Click **Done**.

The Power Query Editor will then open with the JSON response.

### 2. Convert JSON → Table

In the Power Query Editor:

1. **Transform → To Table** (default settings: no delimiter).
2. The single column is now a `Record`. Click the expand arrow in the column header.
3. The response wraps arrays — e.g. daily data is `[{date, close, volume, market_cap}, ...]`. Click **Expand to New Rows** on the array column first, **then** expand the inner record to columns.
4. Optionally rename columns (`date`, `close`, `volume`, `market_cap`).

### 3. Add more queries (one per endpoint)

Repeat the dance for each endpoint you want:

| Use case | URL |
|---------|-----|
| Daily transaction for one symbol | `https://api.sectors.app/v2/transaction/daily/bbca` |
| Company report (full) | `https://api.sectors.app/v2/company/report/bbca` |
| Company report (sections only — saves credits) | `https://api.sectors.app/v2/company/report/bbca/?sections=overview,valuation,dividend` |
| Top movers (gainers + losers) | `https://api.sectors.app/v2/ranking/top-changes/?classifications=top_gainers,top_losers&periods=1d,7d` |
| Subsector list (kebab-case slugs) | `https://api.sectors.app/v2/subsectors/` |
| Most-traded stocks | `https://api.sectors.app/v2/ranking/most-traded/?start=2026-08-01&end=2026-08-29&n_stock=20` |

Use **different sheet destinations per query** — one sheet per endpoint is the canonical layout.

### 4. Refresh

- Manual: `Data` tab → `Refresh All`.
- Scheduled: publish the workbook to **OneDrive** or **SharePoint** and turn on "Refresh connections automatically". OneDrive/SharePoint refreshes hourly by default — sufficient for end-of-day market data.

## Known pitfalls

- **Header typo**: the `Authorization` header name is case-insensitive but the value must be the **raw key**, not `Bearer ...`. If you prefix it with `Bearer` you'll get HTTP 401 and the query will return a JSON error object instead of data — the Power Query editor will silently show the wrong-type column.
- **`/v1/*` URLs**: if a tutorial online shows `/v1/transaction/daily/bbca`, replace it with `/v2/transaction/daily/bbca`. v1 is dead.
- **Array expansion**: a common mistake is to expand the outer Record first. For daily data, the API returns an **array of records**, so you need two clicks: first **Expand to New Rows** (this unrolls the array into multiple rows), then **Expand the new columns** (this pulls out `date`, `close`, etc.).
- **Date types**: dates come as ISO strings. In Power Query, click the column header → `Transform` → `Data Type` → `Date`. Same for numerics (`Int64` for prices, `Decimal` for market caps).
- **`.JK` suffix**: you can pass either `bbca` or `bbca.jk`. Both work in REST. Power Query won't care.
- **Auto-refresh + OneDrive**: Power Query's "Refresh connections automatically" only runs on the **OneDrive/SharePoint schedule** (hourly by default). For more frequent refreshes you need a Power Automate flow or a dedicated VM.
- **No streaming**: Power Query refreshes pull the snapshot at refresh time. No WebSocket-equivalent in Excel.

## Build-quality checklist

Before you demo an Excel workbook as a hackathon artefact:

- [ ] One sheet per endpoint, named after what it shows (e.g. `Daily — BBCA`, `Top Gainers 1d`).
- [ ] Header row frozen (`View` → `Freeze Top Row`).
- [ ] Numeric columns formatted (currency for prices, thousands separator for volume).
- [ ] Date column formatted as a real Excel date (so charts and pivot tables work).
- [ ] `Refresh All` works without throwing errors.
- [ ] Sheet doesn't expose the API key in any visible cell (Power Query stores credentials out-of-band — verify by `File` → `Info` → `Workbook Settings` → confirm credentials are stored, not embedded).

## Cross-links

- Same data, but in Google Sheets: [`sheets.md`](sheets.md)
- Same data, but in Looker: [`looker.md`](looker.md)
- Real-time watchlist with scheduled refresh: [`n8n-api.md`](n8n-api.md)
- REST endpoints to use in Power Query: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)