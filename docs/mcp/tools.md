# Sectors MCP — Tool Catalog

> Source: https://docs.sectors.app/recipes/sectors-for-ai-agents/00-sectors-mcp-guide#tools-reference (verified 2026-08-29).
>
> Companion setup guide: [`setup.md`](setup.md). Companion REST catalog (owned
> by Lane 1, cross-linked below): [`../rest/`](../rest/). All MCP tools listed
> here have an equivalent REST endpoint under `https://api.sectors.app/v2/`.

The Sectors MCP server exposes **65+ tools** covering IDX, SGX, KLSE, and
Indonesian mining data. Tools are organized by domain below. Each entry
follows this format:

```
### `<tool-name>`
- **Purpose:** <one line>
- **Parameters:** <list of named params with types and required/optional>
- **Returns:** <shape summary>
- **Equivalent REST:** <URL pattern>
- **Sample call:** <natural-language prompt → tool input JSON>
- **Sample response shape:** <truncated JSON>
```

---

## Quick-reference index

| Domain                                      | Tool count |
| ------------------------------------------- | ---------- |
| Company analysis                            | 5          |
| Market screening & rankings                 | 4          |
| Financial data                              | 3          |
| Market indices & daily data                 | 5          |
| Sector & industry classification            | 5          |
| News, filings & events                      | 4          |
| Broker data                                 | 6          |
| Singapore (SGX)                             | 11         |
| Malaysia (KLSE)                             | 4          |
| Mining (Indonesia)                          | 20         |
| **Total**                                   | **67**     |

---

## Company analysis

### `fetch-company-report`
- **Purpose:** Full company report with selectable sections.
- **Parameters:**
  - `symbol` (string, required) — bare ticker, e.g. `BBCA`
  - `sections` (string, optional) — comma-separated subset of: overview, valuation, future, peers, financials, dividend, management, ownership. Default = all.
- **Returns:** JSON object with `symbol`, `company_name`, and one key per requested section.
- **Equivalent REST:** `GET /v2/company/report/{symbol}/?sections=...` — see [`../rest/idx-company-report.md`](../rest/idx-company-report.md) (Lane 1).
- **Sample call:** "Give me an overview of Bank Central Asia (BBCA)" → `{"ticker": "BBCA", "sections": "overview"}`
- **Sample response shape:**
  ```json
  {
    "symbol": "BBCA.JK",
    "company_name": "PT Bank Central Asia Tbk.",
    "overview": {
      "sector": "Financials",
      "sub_sector": "Banks",
      "market_cap": 887857728862500,
      "market_cap_rank": 2,
      "employee_num": 27937,
      "listing_date": "2000-05-31",
      "last_close_price": 7275,
      "indices": ["LQ45", "IDX30", "KOMPAS100", "IDXHIDIV20"]
    }
  }
  ```

### `fetch-company-segments`
- **Purpose:** Revenue and cost segment breakdown for a financial year (Sankey-graph-ready).
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker, e.g. `TLKM`
  - `financial_year` (integer, required) — calendar year, e.g. `2023`
- **Returns:** JSON object with `symbol` and a `segments` array (revenue + cost split).
- **Equivalent REST:** `GET /v2/company/segments/{symbol}/{financial_year}/`
- **Sample call:** "Show me Telkom Indonesia's revenue segments in 2023" → `{"ticker": "TLKM", "financial_year": 2023}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "TLKM.JK",
    "financial_year": 2023,
    "segments": [
      {"name": "Mobile", "revenue": 45200000000000, "cost": 21500000000000},
      {"name": "Fixed Wireline", "revenue": 12700000000000, "cost": 9100000000000}
    ]
  }
  ```

### `fetch-listing-performance`
- **Purpose:** Price performance since listing date across 7d, 30d, 90d, 365d windows.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
- **Returns:** JSON object with `symbol`, `listing_date`, and percentage changes.
- **Equivalent REST:** `GET /v2/ipo/listing-performance/{symbol}/`
- **Sample call:** "What is the performance of GOTO since its IPO listing?" → `{"ticker": "GOTO"}`
- **Sample response shape:**
  ```json
  {
    "symbol": "GOTO.JK",
    "listing_date": "2022-04-11",
    "chg_7d": -0.0105,
    "chg_30d": -0.4188,
    "chg_90d": -0.1152,
    "chg_365d": -0.7408
  }
  ```

### `fetch-corporate-actions`
- **Purpose:** Splits, rights, warrants, bonus shares, AGM events, and dividend history.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
- **Returns:** JSON object with corporate action records grouped by type.
- **Equivalent REST:** `GET /v2/company/corporate-actions/{symbol}/`
- **Sample call:** "Show me BBCA's corporate actions history" → `{"ticker": "BBCA"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BBCA.JK",
    "actions": [
      {"date": "2024-03-25", "type": "dividend", "amount": 227.5},
      {"date": "2024-04-12", "type": "agm", "description": "RUPS Tahunan"}
    ]
  }
  ```

### `fetch-shareholders-composition`
- **Purpose:** Monthly shareholder breakdown by investor category (local and foreign).
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `year` (integer, required) — calendar year, e.g. `2024`
- **Returns:** JSON object with `symbol`, `year`, and a monthly composition array.
- **Equivalent REST:** `GET /v2/company/shareholders-composition/{symbol}/{year}/`
- **Sample call:** "Show BBCA local vs foreign ownership in 2024" → `{"ticker": "BBCA", "year": 2024}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BBCA.JK",
    "year": 2024,
    "composition": [
      {"month": "2024-01", "local_pct": 0.6523, "foreign_pct": 0.3477},
      {"month": "2024-02", "local_pct": 0.6491, "foreign_pct": 0.3509}
    ]
  }
  ```

---

## Market screening & rankings

### `fetch-companies-by-subsector`
- **Purpose:** Filter and sort IDX companies — structured query (`where`/`order_by`) or natural language (`q`).
- **Parameters:**
  - `q` (string, optional) — natural-language query, e.g. `"top 5 banks by market cap"`
  - `where` (string, optional) — SQL-like filter, e.g. `"sub_sector = 'banks' and market_cap > 100000000000"`
  - `order_by` (string, optional) — field name with optional `-` prefix for desc, e.g. `"-market_cap"`
  - `limit` (integer, optional) — 1–200, default 50
- **Returns:** JSON object with `results[]`, `pagination{}`, and `llm_translation{}` (if `q` was used).
- **Equivalent REST:** `GET /v2/companies/?...` — see [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1).
- **Sample call:** "Top 5 banking stocks in Indonesia by market cap" → `{"where": "sub_sector = 'banks'", "order_by": "-market_cap", "limit": 5}`
- **Sample response shape:**
  ```json
  {
    "results": [
      {"symbol": "BBCA.JK", "company_name": "PT Bank Central Asia Tbk.",              "market_cap": 887857728862500},
      {"symbol": "BBRI.JK", "company_name": "PT Bank Rakyat Indonesia (Persero) Tbk", "market_cap": 574666266378210}
    ],
    "pagination": {"page": 1, "per_page": 5, "total": 47}
  }
  ```

### `fetch-companies-top-changes`
- **Purpose:** Top gainers and losers across 1d/7d/14d/30d/365d periods.
- **Parameters:**
  - `classifications` (string, required) — comma-separated from `top_gainers`, `top_losers`
  - `periods` (string, required) — comma-separated from `1d`, `7d`, `14d`, `30d`, `365d`
  - `sub_sector` (string, optional) — kebab-case subsector slug
  - `n_stock` (integer, optional) — top N per period, default 10
- **Returns:** JSON object keyed by `(classification, period)` → list of companies.
- **Equivalent REST:** `GET /v2/ranking/top-changes/?classifications=...&periods=...`
- **Sample call:** "Show me the top 5 gainers over the last 7 days" → `{"classifications": "top_gainers", "periods": "7d", "n_stock": 5}`
- **Sample response shape:** (truncated)
  ```json
  {
    "top_gainers": {
      "7d": [
        {"symbol": "XXXX.JK", "company_name": "...", "chg_pct": 0.184},
        {"symbol": "YYYY.JK", "company_name": "...", "chg_pct": 0.121}
      ]
    }
  }
  ```

### `fetch-most-traded-stocks`
- **Purpose:** Most traded IDX stocks by transaction volume over a date range.
- **Parameters:**
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 90 days from `start`
  - `n_stock` (integer, required) — top N per day, e.g. `20`
  - `sub_sector` (string, optional) — kebab-case subsector slug
- **Returns:** JSON object keyed by date → list of `{symbol, company_name, volume, price}`.
- **Equivalent REST:** `GET /v2/ranking/most-traded/?start=...&end=...&n_stock=...`
- **Sample call:** "Top 10 most traded stocks over the last 7 days" → `{"start": "2024-07-24", "end": "2024-07-31", "n_stock": 10}`
- **Sample response shape:** (truncated)
  ```json
  {
    "2024-07-24": [
      {"symbol": "GOTO.JK", "company_name": "PT GoTo Gojek Tokopedia Tbk", "volume": 2660984600, "price": 54},
      {"symbol": "BSBK.JK", "company_name": "PT Wulandari Bangun Laksana Tbk", "volume": 1833364900, "price": 83}
    ]
  }
  ```

### `fetch-close`
- **Purpose:** Closing price for **every** IDX ticker on a single trading day (universe feed).
- **Parameters:**
  - `date` (string, required) — `YYYY-MM-DD` trading day
- **Returns:** JSON object with `date` and a `results[]` array of every ticker (paginated).
- **Equivalent REST:** `GET /v2/transaction/close/{date}/`
- **Sample call:** "Give me every IDX ticker's closing price on 2024-07-31" → `{"date": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "date": "2024-07-31",
    "results": [
      {"symbol": "BBCA.JK", "close": 7275, "volume": 12345678},
      {"symbol": "BBRI.JK", "close": 4860, "volume": 87654321}
    ],
    "pagination": {"page": 1, "per_page": 200, "total": 928}
  }
  ```

> **Why use this?** A universe feed (one paginated call) is cheaper than 900
> separate per-symbol calls. For cron jobs that need breadth, prefer
> `fetch-close` over iterating `fetch-company-report`. Same for
> `fetch-companies-quarterly-financial-dates` (financial data).

---

## Financial data

### `fetch-quarterly-financials`
- **Purpose:** Quarterly income statement and balance sheet for an IDX ticker.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `n_quarters` (integer, optional) — default 4
  - `report_date` (string, optional) — `YYYY-Qn` (e.g. `2024-Q1`). If omitted, returns latest N.
- **Returns:** JSON object with `symbol`, `report_date`, and quarterly figures. **Financial-sector companies** (banks, insurance) include extra fields: `net_interest_income`, `gross_loan`, `total_deposit`, etc.
- **Equivalent REST:** `GET /v2/company/quarterly-financials/{symbol}/?n_quarters=4[&report_date=YYYY-Qn]`
- **Sample call:** "Get BBCA's last 4 quarters of financial statements" → `{"ticker": "BBCA", "n_quarters": 4}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BBCA.JK",
    "report_date": "2024-Q1",
    "financials": [
      {"quarter": "2024-Q1", "revenue": 24500000000000, "net_profit": 5800000000000, "eps": 235},
      {"quarter": "2023-Q4", "revenue": 23800000000000, "net_profit": 5600000000000, "eps": 228}
    ]
  }
  ```

### `fetch-quarterly-financial-dates`
- **Purpose:** Available quarterly report dates for a single company (call first before `fetch-quarterly-financials` with a specific `report_date`).
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
- **Returns:** JSON object with `symbol` and an array of `report_date` strings grouped by year.
- **Equivalent REST:** `GET /v2/company/quarterly-financial-dates/{symbol}/`
- **Sample call:** "What quarters are available for BMRI?" → `{"ticker": "BMRI"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BMRI.JK",
    "dates": {
      "2024": ["2024-Q1", "2024-Q2", "2024-Q3"],
      "2023": ["2023-Q1", "2023-Q2", "2023-Q3", "2023-Q4"]
    }
  }
  ```

### `fetch-companies-quarterly-financial-dates`
- **Purpose:** Latest quarterly report date for every IDX company, in one paginated feed (universe freshness polling).
- **Parameters:**
  - `since` (string, optional) — `YYYY-MM-DD` filter; only include companies filed after this date
  - `year` (integer, optional) — calendar year filter
- **Returns:** JSON object with `results[]` of `{symbol, latest_report_date}`.
- **Equivalent REST:** `GET /v2/companies/quarterly-financial-dates/?since=YYYY-MM-DD`
- **Sample call:** "Which companies filed Q3 2024 results in the last week?" → `{"since": "2024-10-15"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"symbol": "BBCA.JK", "latest_report_date": "2024-Q3"},
      {"symbol": "BBRI.JK", "latest_report_date": "2024-Q3"}
    ],
    "pagination": {"page": 1, "per_page": 50, "total": 142}
  }
  ```

---

## Market indices & daily data

### `fetch-index-daily`
- **Purpose:** Daily closing price for a market index over a date range.
- **Parameters:**
  - `index_code` (string, required) — one of: `ftse`, `idx30`, `idxbumn20`, `idxesgl`, `idxg30`, `idxhidiv20`, `idxq30`, `idxv30`, `jii70`, `kompas100`, `lq45`, `sminfra18`, `srikehati`, `economic30`, `idxvesta28`
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`
- **Returns:** JSON object with `index_code` and a daily series array.
- **Equivalent REST:** `GET /v2/transaction/index-daily/{index_code}/?start=...&end=...`
- **Sample call:** "Show me LQ45 daily close for the last 30 days" → `{"index_code": "lq45", "start": "2024-07-01", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "index_code": "lq45",
    "data": [
      {"date": "2024-07-01", "close": 728.45},
      {"date": "2024-07-02", "close": 731.20}
    ]
  }
  ```

### `fetch-idx-market-cap`
- **Purpose:** Historical total IDX market capitalization over a date range.
- **Parameters:**
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`
- **Returns:** JSON object with daily total IDX market cap in IDR.
- **Equivalent REST:** `GET /v2/transaction/idx-total/?start=...&end=...`
- **Sample call:** "Total IDX market cap for the last 7 days" → `{"start": "2024-07-24", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "data": [
      {"date": "2024-07-24", "total_market_cap": 12500000000000000},
      {"date": "2024-07-25", "total_market_cap": 12480000000000000}
    ]
  }
  ```

### `fetch-daily-transaction`
- **Purpose:** Daily close price, volume, and market cap for one symbol over a date range.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 90 days
- **Returns:** JSON object with `symbol` and a daily array.
- **Equivalent REST:** `GET /v2/transaction/daily/{symbol}/?start=...&end=...`
- **Sample call:** "BBCA daily close for the last 30 days" → `{"symbol": "BBCA", "start": "2024-07-01", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BBCA.JK",
    "data": [
      {"date": "2024-07-01", "close": 7275, "volume": 12345678, "market_cap": 887857728862500}
    ]
  }
  ```

### `fetch-foreign-flow`
- **Purpose:** Net daily foreign-broker inflow/outflow for a symbol.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 90 days
- **Returns:** JSON object with `symbol` and a daily array of `net_foreign_inflow` in IDR. Positive = net buy, negative = net sell.
- **Equivalent REST:** `GET /v2/brokers/foreign-flow/{symbol}/?start=...&end=...`
- **Sample call:** "Foreign flow on BBCA over the last 30 days" → `{"symbol": "BBCA", "start": "2024-07-01", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "symbol": "BBCA.JK",
    "data": [
      {"date": "2024-07-01", "net_foreign_inflow": 125000000000},
      {"date": "2024-07-02", "net_foreign_inflow": -45000000000}
    ]
  }
  ```

### `fetch-free-float`
- **Purpose:** Free float percentage for IDX companies, filterable by sector taxonomy.
- **Parameters:**
  - `sector` (string, optional) — kebab-case sector slug
  - `sub_sector` (string, optional) — kebab-case subsector slug
  - `industry` (string, optional) — kebab-case industry slug
- **Returns:** JSON object with a `results[]` array sorted by `free_float` descending.
- **Equivalent REST:** `GET /v2/screener/free-float/` (also `/v2/companies/?where=free_float>0.5`)
- **Sample call:** "Which financial stocks have free float above 50%?" → `{"sub_sector": "banks", ...}` or use the screener with `where=free_float>0.5`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"symbol": "BBCA.JK", "company_name": "PT Bank Central Asia Tbk.", "free_float": 0.4954}
    ]
  }
  ```

---

## Sector & industry classification

### `get-subsectors`
- **Purpose:** All sector/subsector pairs as kebab-case slugs (discovery).
- **Parameters:** none.
- **Returns:** JSON array of `{sector, subsector}` pairs.
- **Equivalent REST:** `GET /v2/subsectors/`
- **Sample call:** "What subsectors are available?" → `{}`
- **Sample response shape:** (truncated)
  ```json
  [
    {"sector": "Financials", "subsector": "banks"},
    {"sector": "Financials", "subsector": "insurance"},
    {"sector": "Technology", "subsector": "software-it-services"}
  ]
  ```

### `fetch-industries`
- **Purpose:** All subsector/industry pairs (finer taxonomy).
- **Parameters:** none.
- **Returns:** JSON array of `{subsector, industry}` pairs.
- **Equivalent REST:** `GET /v2/industries/`
- **Sample call:** "What industries are under each subsector?" → `{}`
- **Sample response shape:** (truncated)
  ```json
  [
    {"subsector": "banks", "industry": "banks"},
    {"subsector": "software-it-services", "industry": "software-it-services"}
  ]
  ```

### `fetch-subindustries`
- **Purpose:** All industry/sub-industry pairs (deepest taxonomy).
- **Parameters:** none.
- **Returns:** JSON array of `{industry, sub_industry}` pairs.
- **Equivalent REST:** `GET /v2/subindustries/`
- **Sample call:** "What sub-industries exist?" → `{}`
- **Sample response shape:** (truncated)
  ```json
  [{"industry": "banks", "sub_industry": "banks"}]
  ```

### `fetch-subsector-report`
- **Purpose:** Aggregated metrics and company list for a subsector (with selectable sections).
- **Parameters:**
  - `sub_sector` (string, required) — kebab-case subsector slug, e.g. `banks`
  - `sections` (string, optional) — comma-separated subset of: overview, financials, valuation, future, peers, dividend
- **Returns:** JSON object with aggregated metrics + companies array.
- **Equivalent REST:** `GET /v2/subsector/report/{sub_sector}/?sections=...`
- **Sample call:** "Give me a financial overview of the banks subsector" → `{"sub_sector": "banks", "sections": "overview,financials"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "sub_sector": "banks",
    "overview": {"total_companies": 47, "total_market_cap": 2200000000000000},
    "financials": {"aggregate_revenue_2023": 450000000000000}
  }
  ```

### `fetch-companies-with-segments`
- **Purpose:** All companies that have revenue and cost segment data available, plus their available financial years.
- **Parameters:** none.
- **Returns:** JSON object mapping `symbol → [years]`.
- **Equivalent REST:** `GET /v2/companies/segments-list/`
- **Sample call:** "Which companies have segment breakdowns available?" → `{}`
- **Sample response shape:** (truncated)
  ```json
  {"TLKM.JK": [2021, 2022, 2023], "UNVR.JK": [2020, 2021, 2022, 2023]}
  ```

---

## News, filings & events

### `fetch-news`
- **Purpose:** IDX and mining news articles, filterable by sector, symbol, tag, or keyword.
- **Parameters:**
  - `extension` (string, required) — `idx` or `mining` (each extension has its own valid filters)
  - `sector` (string, optional) — kebab-case sector slug
  - `sub_sector` (string, optional) — kebab-case subsector slug
  - `symbols` (string, optional) — comma-separated tickers
  - `keyword` (string, optional) — full-text search
  - `tags` (string, optional) — comma-separated tag slugs (use `fetch-tags` to get the valid list)
  - `start` (string, optional) — `YYYY-MM-DD`
  - `end` (string, optional) — `YYYY-MM-DD`
- **Returns:** JSON object with paginated `results[]` of news articles.
- **Equivalent REST:** `GET /v2/news/news/?extension=idx[&filters...]`
- **Sample call:** "Latest BBCA news" → `{"extension": "idx", "symbols": "BBCA"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"date": "2024-07-30", "title": "BBCA posts 12% net profit growth", "url": "https://...", "tags": ["earnings", "banks"]}
    ],
    "pagination": {"page": 1, "per_page": 50, "total": 14}
  }
  ```

### `fetch-filings`
- **Purpose:** IDX insider trading buy/sell filings.
- **Parameters:**
  - `symbol` (string, optional) — bare IDX ticker
  - `transaction_type` (string, optional) — `buy` or `sell`
  - `holder_type` (string, optional) — e.g. `director`, `commissioner`, `major_shareholder`
  - `sector` (string, optional) — kebab-case sector slug
  - `start` (string, optional) — `YYYY-MM-DD`
  - `end` (string, optional) — `YYYY-MM-DD`
- **Returns:** JSON object with paginated insider filings.
- **Equivalent REST:** `GET /v2/news/filings/?symbol=...&transaction_type=...`
- **Sample call:** "BBCA insider buy filings over the last 30 days" → `{"symbol": "BBCA", "transaction_type": "buy", "start": "2024-07-01"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"date": "2024-07-22", "insider": "X", "type": "buy", "shares": 100000, "price": 7200}
    ]
  }
  ```

### `fetch-suspensions`
- **Purpose:** Historical IDX stock suspensions with dates, official reasons, and PDF links.
- **Parameters:**
  - `symbol` (string, optional) — bare IDX ticker
  - `start` (string, optional) — `YYYY-MM-DD`
  - `end` (string, optional) — `YYYY-MM-DD`
- **Returns:** JSON object with paginated suspension records.
- **Equivalent REST:** `GET /v2/news/suspensions/?symbol=...`
- **Sample call:** "Suspension history for YYYY" → `{"symbol": "YYYY"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"date": "2024-06-15", "symbol": "YYYY.JK", "reason": "Material information pending disclosure", "pdf_url": "https://..."}
    ]
  }
  ```

### `fetch-tags`
- **Purpose:** All valid tag slugs for use in news and filings filters.
- **Parameters:** none.
- **Returns:** Sorted alphabetical JSON array of tag slugs.
- **Equivalent REST:** `GET /v2/tags/`
- **Sample call:** "What news tags are available?" → `{}`
- **Sample response shape:** (truncated)
  ```json
  ["acquisition", "bankruptcy", "dividend", "earnings", "ipo", "rights-issue", "split", "suspension"]
  ```

---

## Broker data

### `fetch-brokers`
- **Purpose:** IDX broker registry with origin (foreign/domestic) and cohort classifications.
- **Parameters:**
  - `origin` (string, optional) — `foreign` or `domestic`
  - `cohort` (string, optional) — `retail`, `mixed`, `institutional`, `unknown`
- **Returns:** JSON array of broker records.
- **Equivalent REST:** `GET /v2/brokers/registry/?origin=...&cohort=...`
- **Sample call:** "List all foreign institutional brokers" → `{"origin": "foreign", "cohort": "institutional"}`
- **Sample response shape:** (truncated)
  ```json
  [
    {"broker_code": "KGI", "name": "KGI Sekuritas Indonesia", "origin": "foreign", "cohort": "institutional"}
  ]
  ```

### `fetch-top-brokers`
- **Purpose:** Brokers ranked by gross trade value (default) or absolute net flow for a single date.
- **Parameters:**
  - `date` (string, required) — `YYYY-MM-DD`
  - `metric` (string, required) — `gross_value` or `n_abs_net_flow`
  - `n_brokers` (integer, optional) — top N, default 20
  - `origin` (string, optional) — `foreign` or `domestic`
  - `cohort` (string, optional) — `retail`, `mixed`, `institutional`, `unknown`
- **Returns:** JSON object with a ranked `results[]` array.
- **Equivalent REST:** `GET /v2/brokers/top/?date=...&metric=...&n_brokers=...`
- **Sample call:** "Top 10 brokers by gross value on 2024-07-31" → `{"date": "2024-07-31", "metric": "gross_value", "n_brokers": 10}`
- **Sample response shape:** (truncated)
  ```json
  {
    "results": [
      {"broker_code": "KGI", "gross_value": 1250000000000, "rank": 1}
    ]
  }
  ```

### `fetch-broker-summary`
- **Purpose:** Per-broker daily trading rows for a single stock.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `broker_code` (string, required) — e.g. `KGI`
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 14 days
- **Returns:** JSON object with daily activity for that broker on that stock.
- **Equivalent REST:** `GET /v2/brokers/broker-summary/{broker_code}/{symbol}/?start=...&end=...`
- **Sample call:** "KGI activity on BBCA over the last 7 days" → `{"symbol": "BBCA", "broker_code": "KGI", "start": "2024-07-24", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "data": [
      {"date": "2024-07-24", "buy_value": 500000000, "sell_value": 350000000, "net": 150000000, "buy_lots": 5000, "sell_lots": 3500, "avg_buy_price": 7200}
    ]
  }
  ```

### `fetch-broker-summary-top`
- **Purpose:** Top accumulating and distributing brokers for a single stock.
- **Parameters:**
  - `symbol` (string, required) — bare IDX ticker
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 14 days
  - `n_brokers` (integer, optional) — top N, default 20
- **Returns:** JSON object with `top_buyers[]` and `top_sellers[]`.
- **Equivalent REST:** `GET /v2/brokers/broker-summary/top/{symbol}/?start=...&end=...&n_brokers=...`
- **Sample call:** "Who are the top accumulators on BBCA in the last week?" → `{"symbol": "BBCA", "start": "2024-07-24", "end": "2024-07-31", "n_brokers": 10}`
- **Sample response shape:** (truncated)
  ```json
  {
    "top_buyers": [{"broker_code": "KGI", "net": 500000000}, ...],
    "top_sellers": [{"broker_code": "YP", "net": -350000000}, ...]
  }
  ```

### `fetch-broker-activity`
- **Purpose:** All stocks traded by a single broker over a date range.
- **Parameters:**
  - `broker_code` (string, required) — e.g. `KGI`
  - `symbol` (string, optional) — filter to one stock
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 14 days
- **Returns:** JSON object with grouped-by-date activity listing every stock touched.
- **Equivalent REST:** `GET /v2/brokers/broker-activity/{broker_code}/?start=...&end=...[&symbol=...]`
- **Sample call:** "What did KGI trade over the last 7 days?" → `{"broker_code": "KGI", "start": "2024-07-24", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "data": [
      {"date": "2024-07-24", "stocks": [{"symbol": "BBCA.JK", "buy_value": 500000000, "sell_value": 350000000, "net": 150000000}, ...]}
    ]
  }
  ```

### `fetch-broker-activity-top`
- **Purpose:** Top accumulations and distributions by a single broker.
- **Parameters:**
  - `broker_code` (string, required) — e.g. `KGI`
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 14 days
- **Returns:** JSON object with `top_accumulations[]` and `top_distributions[]`.
- **Equivalent REST:** `GET /v2/brokers/broker-activity/top/{broker_code}/?start=...&end=...`
- **Sample call:** "What are KGI's biggest positions in the last week?" → `{"broker_code": "KGI", "start": "2024-07-24", "end": "2024-07-31"}`
- **Sample response shape:** (truncated)
  ```json
  {
    "top_accumulations": [{"symbol": "BBCA.JK", "net": 1500000000}, ...],
    "top_distributions": [{"symbol": "TLKM.JK", "net": -800000000}, ...]
  }
  ```

---

## Singapore (SGX)

All SGX tools follow the same shape as their IDX counterparts but use **3-char
SGX symbols** (e.g. `D05`, `U11`, `Z74`) without the `.si` suffix.

### `fetch-sgx-sectors`
- **Purpose:** All SGX sector slugs (discovery).
- **Parameters:** none.
- **Returns:** JSON array of sector slugs.
- **Equivalent REST:** `GET /v2/sgx/sectors/`

### `fetch-sgx-subsectors`
- **Purpose:** All SGX sector/subsector pairs.
- **Parameters:** none.
- **Returns:** JSON array of `{sector, subsector}` pairs.
- **Equivalent REST:** `GET /v2/sgx/subsectors/`

### `fetch-sgx-company-report`
- **Purpose:** SGX company report — overview, valuation, financials, dividend.
- **Parameters:**
  - `symbol` (string, required) — SGX code, e.g. `D05`
  - `sections` (string, optional) — comma-separated subset of: overview, valuation, financials, dividend
- **Returns:** JSON object with `symbol` and one key per requested section.
- **Equivalent REST:** `GET /v2/sgx/report/{symbol}/?sections=...`

### `fetch-sgx-companies-by-sector`
- **Purpose:** SGX companies in a given sector.
- **Parameters:**
  - `sector` (string, required) — SGX sector slug
- **Returns:** JSON array of `{symbol, company_name}` pairs.
- **Equivalent REST:** `GET /v2/sgx/companies-by-sector/?sector=...`

### `fetch-sgx-top-companies`
- **Purpose:** Top SGX companies by dividend yield, revenue, earnings, market cap, or PE.
- **Parameters:**
  - `classifications` (string, required) — comma-separated from: `dividend_yield`, `revenue`, `earnings`, `market_cap`, `pe`
  - `sector` (string, optional) — filter to one SGX sector
- **Returns:** JSON object with ranked `results[]` per classification.
- **Equivalent REST:** `GET /v2/sgx/ranking/top-companies/?classifications=...`

### `fetch-sgx-daily-transaction`
- **Purpose:** Daily close price and volume for an SGX stock.
- **Parameters:**
  - `symbol` (string, required) — SGX code
  - `start` (string, required) — `YYYY-MM-DD`
  - `end` (string, required) — `YYYY-MM-DD`, max 90 days
- **Returns:** JSON object with `symbol` and a daily series.
- **Equivalent REST:** `GET /v2/sgx/transaction/daily/{symbol}/?start=...&end=...`

### `fetch-sgx-filings`
- **Purpose:** SGX insider trading buy/sell filings.
- **Parameters:**
  - `symbol` (string, optional)
  - `transaction_type` (string, optional) — `buy` or `sell`
  - `holder_type` (string, optional)
  - `start` (string, optional)
  - `end` (string, optional)
- **Returns:** JSON object with paginated filings.
- **Equivalent REST:** `GET /v2/sgx/news/sgx-filings/?symbol=...`

### `fetch-sgx-news`
- **Purpose:** SGX news articles, filterable by sector, symbol, tag.
- **Parameters:**
  - `sector` (string, optional)
  - `symbols` (string, optional) — comma-separated SGX codes
  - `tags` (string, optional) — comma-separated tag slugs (use `fetch-sgx-tags`)
  - `start` (string, optional)
  - `end` (string, optional)
- **Returns:** JSON object with paginated news articles.
- **Equivalent REST:** `GET /v2/sgx/news/sgx-news/?...`

### `fetch-sgx-buybacks`
- **Purpose:** SGX share buyback records (purchase date, type, price range, total value, treasury shares, mandate details).
- **Parameters:**
  - `symbol` (string, optional)
  - `start` (string, optional)
  - `end` (string, optional)
- **Returns:** JSON object with paginated buyback records.
- **Equivalent REST:** `GET /v2/sgx/transaction/share-buybacks/?symbol=...`

### `fetch-sgx-short-sell`
- **Purpose:** SGX short sell data.
- **Parameters:**
  - `symbol` (string, optional)
  - `start` (string, optional)
  - `end` (string, optional)
- **Returns:** JSON object with paginated short-sell records.
- **Equivalent REST:** `GET /v2/sgx/transaction/short-sell/?symbol=...`

### `fetch-sgx-tags`
- **Purpose:** All valid tag slugs for SGX news filters.
- **Parameters:** none.
- **Returns:** Sorted alphabetical JSON array of tag slugs.
- **Equivalent REST:** `GET /v2/sgx/tags/`

---

## Malaysia (KLSE)

KLSE tickers are **4-digit numeric** (e.g. `1155`, `4197`, `5225`). All KLSE
tools follow the same shape as IDX/SGX equivalents.

### `fetch-klse-sectors`
- **Purpose:** All KLSE sector slugs (discovery).
- **Parameters:** none.
- **Returns:** JSON array of sector slugs.
- **Equivalent REST:** `GET /v2/klse/sectors/`

### `fetch-klse-company-report`
- **Purpose:** KLSE company report — overview, valuation, financials, dividend.
- **Parameters:**
  - `symbol` (string, required) — 4-digit numeric KLSE code
  - `sections` (string, optional) — comma-separated subset of: overview, valuation, financials, dividend
- **Returns:** JSON object with `symbol` and one key per requested section.
- **Equivalent REST:** `GET /v2/klse/report/{symbol}/`

### `fetch-klse-companies-by-sector`
- **Purpose:** KLSE companies in a given sector.
- **Parameters:**
  - `sector` (string, required) — KLSE sector slug
- **Returns:** JSON array of `{symbol, company_name}` pairs.
- **Equivalent REST:** `GET /v2/klse/companies/?sector=...`

### `fetch-klse-top-companies`
- **Purpose:** Top KLSE companies by dividend yield, revenue, earnings, market cap, or PE.
- **Parameters:**
  - `classifications` (string, required) — comma-separated from: `dividend_yield`, `revenue`, `earnings`, `market_cap`, `pe`
  - `sector` (string, optional) — filter to one KLSE sector
- **Returns:** JSON object with ranked `results[]` per classification.
- **Equivalent REST:** `GET /v2/klse/top-companies/?classifications=...`

---

## Mining (Indonesia)

The mining dataset covers Indonesian coal, nickel, gold, copper, bauxite and
other commodities, with companies, sites, licenses, auctions, and global price
data. All monetary values in financial endpoints are **USD millions**.

### `fetch-mining-commodities`
- **Purpose:** Available commodities with price database coverage metadata.
- **Parameters:** none.
- **Returns:** JSON array of commodity metadata (name, slug, coverage).
- **Equivalent REST:** `GET /v2/mining/commodities/`

### `fetch-mining-commodity-price`
- **Purpose:** Historical commodity price by year range (monthly, up to 3 years).
- **Parameters:**
  - `commodity_name` (string, required) — e.g. `coal`, `nickel`
  - `start_year` (integer, required)
  - `end_year` (integer, required)
- **Returns:** JSON object with monthly price series.
- **Equivalent REST:** `GET /v2/mining/commodities/price/{commodity}/?start_year=...&end_year=...`

### `fetch-mining-global-commodity`
- **Purpose:** Global production, reserves, and trade data by commodity and country.
- **Parameters:**
  - `commodity_type` (string, optional)
  - `country` (string, optional) — at least one must be provided
- **Returns:** JSON object with global production/reserves/trade aggregates.
- **Equivalent REST:** `GET /v2/mining/commodities/{commodity}/global/?country=...`

### `fetch-mining-companies`
- **Purpose:** Search mining companies by name, symbol, commodity, or company type.
- **Parameters:**
  - `keyword` (string, optional)
  - `commodity_type` (string, optional)
  - `company_type` (string, optional)
- **Returns:** JSON array of mining company records.
- **Equivalent REST:** `GET /v2/mining/companies/?keyword=...&commodity_type=...`

### `fetch-mining-company-detail`
- **Purpose:** Operational details for a single mining company (activities, licenses, contracts, site count).
- **Parameters:**
  - `slug` (string, required) — mining company slug
- **Returns:** JSON object with full operational profile.
- **Equivalent REST:** `GET /v2/mining/companies/{slug}/`

### `fetch-mining-company-financials`
- **Purpose:** Annual financial records (assets, revenue, profit) in **USD millions**.
- **Parameters:**
  - `slug` (string, required)
  - `year` (integer, optional) — defaults to latest available
- **Returns:** JSON object with annual figures.
- **Equivalent REST:** `GET /v2/mining/companies/{slug}/financials/?year=...`

### `fetch-mining-company-ownership`
- **Purpose:** Corporate ownership tree (parent companies and subsidiaries with percentage stakes).
- **Parameters:**
  - `slug` (string, required)
- **Returns:** JSON object with `parents[]` and `subsidiaries[]` arrays.
- **Equivalent REST:** `GET /v2/mining/companies/{slug}/ownership/`

### `fetch-mining-company-performance`
- **Purpose:** Production volume, sales volume, strip ratio, and resources/reserves for a given year.
- **Parameters:**
  - `slug` (string, required)
  - `commodity_type` (string, optional)
  - `year` (integer, optional) — defaults to latest
- **Returns:** JSON object with performance figures.
- **Equivalent REST:** `GET /v2/mining/companies/{slug}/performance/?commodity_type=...&year=...`

### `fetch-mining-sites`
- **Purpose:** Mining sites with filters for location, commodity, and production volume.
- **Parameters:**
  - `commodity_type` (string, optional)
  - `province` (string, optional)
  - `year` (integer, optional)
  - `min_production` (number, optional)
- **Returns:** JSON array of mining site records.
- **Equivalent REST:** `GET /v2/mining/sites/?commodity_type=...&province=...&year=...`

### `fetch-mining-site-detail`
- **Purpose:** Full details for a single mining site including coordinates.
- **Parameters:**
  - `slug` (string, required) — mining site slug
- **Returns:** JSON object with site profile, parsed resources/reserves, lat/long.
- **Equivalent REST:** `GET /v2/mining/sites/{slug}/`

### `fetch-mining-total-production`
- **Purpose:** National total production for a commodity across all years (with YoY % change).
- **Parameters:**
  - `commodity_type` (string, required)
- **Returns:** JSON array ordered by year descending.
- **Equivalent REST:** `GET /v2/mining/sites-production/commodity-production/?commodity_type=...`

### `fetch-mining-exports`
- **Purpose:** Top export destinations by country for a commodity and year.
- **Parameters:**
  - `commodity_type` (string, required)
  - `year` (integer, required)
- **Returns:** JSON array of `{country, value}` ranked by export value.
- **Equivalent REST:** `GET /v2/mining/commodities/{commodity}/exports/?year=...`

### `fetch-mining-sales-destination`
- **Purpose:** Revenue and volume by destination country for a mining company.
- **Parameters:**
  - `slug` (string, required)
  - `year` (integer, optional) — defaults to latest
- **Returns:** JSON object with destination breakdown.
- **Equivalent REST:** `GET /v2/mining/commodities/{commodity}/sales-destination/?slug=...&year=...`

### `fetch-mining-contracts`
- **Purpose:** Active mining contracts linking mine owners to their service contractors.
- **Parameters:**
  - `mine_owner` (string, optional)
  - `contractor` (string, optional)
- **Returns:** JSON array of contract records.
- **Equivalent REST:** `GET /v2/mining/contracts/?mine_owner=...&contractor=...`

### `fetch-mining-licenses`
- **Purpose:** Mining licenses (IUP/IUPK) with filters for status, commodity, location, and expiry.
- **Parameters:**
  - `commodity_type` (string, optional)
  - `province` (string, optional)
  - `license_type` (string, optional)
  - `expiring_soon` (boolean, optional)
- **Returns:** JSON array of license records.
- **Equivalent REST:** `GET /v2/mining/licenses/?commodity_type=...&province=...`

### `fetch-mining-license-auctions`
- **Purpose:** Mining license auctions scraped from the ESDM Minerba portal.
- **Parameters:**
  - `commodity_type` (string, optional)
  - `province` (string, optional)
  - `status` (string, optional) — `open` or `closed`
- **Returns:** JSON array of auction records (list view, no phases/participants — use detail tool).
- **Equivalent REST:** `GET /v2/mining/license-auctions/?status=open`

### `fetch-mining-license-auction-detail`
- **Purpose:** Full auction record including parsed phases timeline and participant qualification list.
- **Parameters:**
  - `wiup_code` (string, required) — WIUP code from the auction list
- **Returns:** JSON object with full auction record.
- **Equivalent REST:** `GET /v2/mining/license-auctions/{wiup_code}/`

### `fetch-mining-resources-reserves`
- **Purpose:** Discovery index of available resources/reserves data by province and commodity.
- **Parameters:** none.
- **Returns:** JSON array of available `(province, year, commodity)` combinations.
- **Equivalent REST:** `GET /v2/mining/sites-production/commodity-resources-reserves/`

### `fetch-mining-resources-reserves-detail`
- **Purpose:** Resources and reserves data for a province, nested by year then by commodity.
- **Parameters:**
  - `province` (string, required)
  - `commodity_type` (string, required)
  - `year` (integer, required)
- **Returns:** JSON object with `exploration_target`, `total_inventory`, `resources`, `reserves`, `unit`.
- **Equivalent REST:** `GET /v2/mining/sites-production/commodity-resources-reserves-detail/?province=...&commodity_type=...&year=...`

---

## Coverage summary by exchange

| Exchange | Tools  | Notes                                                        |
| -------- | -----  | ------------------------------------------------------------ |
| IDX      | 40+    | Primary coverage: equities, brokers, filings, mining         |
| SGX      | 11     | Full company reports, rankings, dividends, buybacks, shorts   |
| KLSE     | 4      | Basic company report and sector data                         |
| Mining   | 20     | Indonesia-focused: commodities, sites, licenses, auctions     |
| **Total**| **75** | 67 unique tools listed + cross-domain overlap                |

> The MCP guide advertises "65+ tools" — this catalog lists 67 unique tools
> plus cross-domain overlap. The exact count may grow as new endpoints are
> added. Re-fetch `https://docs.sectors.app/llms.txt` if you need the
> authoritative live count.

---

## Cross-references to Lane 1's REST catalog

The full REST endpoint catalog lives in `references/rest/` (owned by Lane 1
under `references/rest-catalog-2026-08-29`). Below are the cross-links MCP
users will hit most often:

- Companies screener → [`../rest/idx-screener.md`](../rest/idx-screener.md)
- Company report → [`../rest/idx-company-report.md`](../rest/idx-company-report.md)
- Quarterly financials → [`../rest/idx-quarterly-financials.md`](../rest/idx-quarterly-financials.md)
- Daily close (universe feed) → [`../rest/idx-daily-close.md`](../rest/idx-daily-close.md)
- Foreign flow → [`../rest/idx-foreign-flow.md`](../rest/idx-foreign-flow.md)
- Top movers → [`../rest/idx-top-changes.md`](../rest/idx-top-changes.md)
- Subsector report → [`../rest/idx-subsector-report.md`](../rest/idx-subsector-report.md)
- News (IDX) → [`../rest/idx-news.md`](../rest/idx-news.md)
- Filings → [`../rest/idx-filings.md`](../rest/idx-filings.md)
- Brokers → [`../rest/idx-brokers.md`](../rest/idx-brokers.md)
- SGX report → [`../rest/sgx-company-report.md`](../rest/sgx-company-report.md)
- KLSE report → [`../rest/klse-company-report.md`](../rest/klse-company-report.md)
- Mining commodities → [`../rest/mining-commodities.md`](../rest/mining-commodities.md)

If a `../rest/<file>.md` is missing, it means Lane 1 has not yet committed
that endpoint to `references/rest/`. Treat it as a TODO — the MCP tool still
works, the REST page just isn't mirrored yet. The MCP guide remains the
source of truth for tool semantics.
