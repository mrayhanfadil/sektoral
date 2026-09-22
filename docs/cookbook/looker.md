# Looker Studio → Sectors API (two flavours)

> Sources:
> - Basic: <https://docs.sectors.app/recipes/non-programmatical-tools/03-looker/03-looker>
> - IDX market overview (BI workshop variant): <https://docs.sectors.app/recipes/non-programmatical-tools/03-looker/04-looker-bi-workshop>
>
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

Two recipes in one file:

1. **Looker recipe (basic)** — track the IDXV30 index constituents on a stock-by-stock basis (overview, daily, valuation, financials). Best when you want per-company drill-down.
2. **BI-workshop recipe** — broad IDX market KPIs (top movers, market cap, index history). Best when you want a "macro" dashboard.

Pick one. Don't mix — they pull different data shapes.

---

## Recipe 1 — IDXV30 constituents dashboard (basic)

> Source: Aurellia Christie, Oct 2024
> Live template: <https://lookerstudio.google.com/reporting/9afb6847-86b3-4e5b-8d1e-7b3a5b20edaa>
> Companion Sheet template: <https://docs.google.com/spreadsheets/d/16Q4-eVVficT2O3miLo3JNksGwBmc1oLVYxB-X5RS2Cg>

### Goal

Build a per-stock financial dashboard in Looker Studio, sourced from a Google Sheets workbook that's pre-loaded with Sectors API data via [`sheets.md`](sheets.md).

### When to use this approach

- You want polished, shareable dashboards with minimal code.
- Audience is non-developers who can read a Looker URL but can't run Python.
- You're building something for a thesis/competition that needs to look credible in screenshots.

### Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | low | Looker Studio is static visualisation, not an agent. |
| Track 2 — Automation | medium | Dashboard refreshes on the Sheets schedule. |
| Track 3 — Market intelligence / apps | **high** | Polished dashboard = strong visual artefact. |

### Cost estimate

Same as the Sheets recipe (~5–10 credits per refresh of the source workbook). Looker Studio itself is free.

### End-to-end walkthrough

1. **Pre-fetch the data** in Google Sheets using the API Connector (see [`sheets.md`](sheets.md)). Aurellia's template already includes 5 sheets:
   - `Index` — index constituent metadata
   - `Overview` — per-company stats (market cap, listing date, employees, ...)
   - `Daily Data` — daily price/volume/market cap history
   - `Valuation` — P/E, P/B, ROE, dividend yield per stock
   - `Financials` — revenue, earnings, growth

2. **Make your own copy** of both the Sheet template and the Looker Studio template (links above). File → Make a copy.

3. In Looker Studio, **Add data** → Google Sheets connector → pick your copy → select the `Index` worksheet. Repeat for each of the 4 other sheets. Authorise Looker once.

4. **Fix field types**. Looker Studio sometimes picks `Text` for columns that should be numeric (`Daily Close Change`, `Employee Num`, `Last Close Price`, `Market Cap`, `Market Cap Rank`). Go to `Resource` → `Manage added data sources` → `Edit` → change each field's type. Mark as **Number** for prices/market caps, **Percent** for change/ratios.

5. **Theme + layout**. Pick a theme (or extract from an image), then drag charts onto the canvas:
   - **Scorecards**: top-of-page for "Total Market Cap", "Daily Change %"
   - **Time series**: `Daily Data` → line chart of close price per ticker
   - **Bar chart**: `Valuation` → P/E vs P/B per ticker
   - **Heatmap**: `Valuation` → matrix of (ticker × metric)
   - **Filter controls**: ticker picker, date range, sector dropdown

6. **Add interactivity**:
   - A **button** that links to each ticker's Sectors URL (`https://sectors.app/idx/{symbol}`) — Configure → Interaction → Link → URL.
   - A **date-range control** that filters `Daily Data` globally.

7. **Share**: `Share` menu → email/embed/scheduled report. For the hackathon, an unlisted URL is fine.

### Known pitfalls

- **Field-type mismatches** wreck charts. A `Text` market cap field will plot alphabetically instead of numerically. Re-verify types before publishing.
- **Looker caching** is aggressive. After editing the source Sheet, refresh the Looker data source (`Resource` → `Manage added data sources` → ⋮ → `Refresh`). Scheduled refreshes also need a paid plan; for free, you're on demand.
- **Connector restrictions**: Looker Studio's built-in Google Sheets connector caps at ~50K rows per sheet. If your `Daily Data` grows past that, segment by year or switch to the BI-workshop recipe below.
- **API key exposure**: do **not** paste API keys into the Looker Studio itself. Keep them in Sheets' API Connector (which stores them out-of-band) or Apps Script Properties.
- **No drill-through beyond the data**: Looker Studio can filter, but it can't cross-correlate between fundamentally different schemas. If you need ML-style charts (volatility vs volume, anomaly flags), use the GNN recipe instead.

---

## Recipe 2 — IDX Market Overview dashboard (BI-workshop variant)

> Source: Gerald Bryan, Dec 2024

### Goal

Macro dashboard for the whole IDX: market cap history, index history, top movers, sector leaders. Different shape from Recipe 1 — eight independent feeds, one chart each.

### When to use this approach

- You want a "cockpit" view that summarises the entire market, not a single sector.
- Demo audience is a committee that needs the big picture (BI workshop, regulator pitch).

### Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | low | Static dashboard. |
| Track 2 — Automation | medium | Refresh-on-schedule only. |
| Track 3 — Market intelligence / apps | **high** | Strong "show me you understand the market" artefact. |

### End-to-end walkthrough

Eight feeds to set up in Sheets via API Connector:

| Feed | URL |
|------|-----|
| Historical IDX Market Cap (30 days) | `https://api.sectors.app/v2/transaction/idx-total/?start=2026-08-01&end=2026-08-29` |
| Historical LQ45 daily close | `https://api.sectors.app/v2/transaction/index-daily/lq45/?start=2026-08-01&end=2026-08-29` |
| Historical IDX30 daily close | `https://api.sectors.app/v2/transaction/index-daily/idx30/?start=2026-08-01&end=2026-08-29` |
| Historical JII70 daily close | `https://api.sectors.app/v2/transaction/index-daily/jii70/?start=2026-08-01&end=2026-08-29` |
| Top 10 by market cap (current) | `https://api.sectors.app/v2/companies/?order_by=-market_cap&limit=10` |
| Top 10 by revenue (2024) | `https://api.sectors.app/v2/companies/?order_by=-revenue[2024]&limit=10` |
| Top 10 by earnings (2024) | `https://api.sectors.app/v2/companies/?order_by=-earnings[2024]&limit=10` |
| Top 10 30-day gainers | `https://api.sectors.app/v2/ranking/top-changes/?classifications=top_gainers&n_stock=10&periods=30d` |
| Top 10 30-day losers | `https://api.sectors.app/v2/ranking/top-changes/?classifications=top_losers&n_stock=10&periods=30d` |

Each lands in its own sheet tab. Connect each to Looker Studio via Google Sheets connector (same as Recipe 1). Then:

- **Time-series line chart** for `idx-total` and each index.
- **Bar charts** for each top-10 list (sorted descending).
- **Combined scorecard** at the top: total IDX market cap, LQ45 current value, count of gainers vs losers.

### Direct Looker Studio connection (advanced)

The `Windsor.ai` Looker connector (Partner Connectors) supports JSON, but **cannot** send an `Authorization` header. So you can't call the Sectors API directly from Looker Studio without going through Sheets or a proxy.

If you want to skip Sheets, the practical alternative is to wrap the Sectors API in a public endpoint that takes the key as a query param — but **do not** do that for production. API keys in URLs get logged everywhere.

### Known pitfalls

- **30-day window is hardcoded** in the URLs above. For a live dashboard, recompute `start` and `end` dynamically — easiest is Sheets' `TODAY()-30` formula in the API Connector URL, or a daily Apps Script that rewrites the connector config.
- **Bracket notation in `where`/`order_by`**: `revenue[2024]` is supported in the v2 screener. Note the year is the most-recently-reported fiscal year, not necessarily the calendar year.
- **`n_stock=10`**: tune higher (up to ~50) if your screen real estate allows.
- **Cross-sheet blends**: Looker Studio blends require a join key (e.g. `symbol`). Without it, each chart stays in its own data island. Use scorecards/blended data only when you really need a joined view.

## Build-quality checklist (both recipes)

- [ ] Every chart has a title, axis labels, and units (IDR trillion, %).
- [ ] Numeric fields all typed correctly (`Number`, `Percent`).
- [ ] Source Sheets documented in a README tab (`data source`, `last refreshed`, `refresh cadence`).
- [ ] Date-range control covers at least 30 days by default.
- [ ] Looker Studio link works for reviewers who don't have edit access.

## Cross-links

- Source Sheets: [`sheets.md`](sheets.md)
- Excel alternative: [`excel.md`](excel.md)
- Programmatic equivalent: [`n8n-api.md`](n8n-api.md)
- REST endpoints to use: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)