# IDX Quarterly Financials & Daily Transactions — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. IDX ticker = 4-letter code, optionally `.JK`.

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/financials/quarterly/{symbol}/` | Quarterly income + balance sheet for one symbol |
| `GET /v2/company/get_quarterly_financial_dates/{symbol}/` | All available quarterly report dates for one symbol (helper) |
| `GET /v2/companies/quarterly-financial-dates/` | Universe-wide latest quarterly report dates (helper) |
| `GET /v2/close/` | Daily close for every IDX ticker on one trading day (universe feed) |
| `GET /v2/daily/{symbol}/` | Daily close + volume + market cap for one symbol |
| `GET /v2/idx-total/` | Historical total IDX market cap |
| `GET /v2/index-daily/{index_code}/` | Daily closing price for one IDX index |

> Path corrections vs the high-level `sectors-api-and-mcp.md` index:
> - `/v2/financials/quarterly/{symbol}/` is the actual quarterly-financials path (NOT `/v2/company/quarterly-financials/{symbol}/`).
> - `/v2/close/`, `/v2/daily/{symbol}/`, `/v2/idx-total/`, `/v2/index-daily/{index_code}/` are all top-level (NOT under `/v2/transaction/`).

---

### `GET /v2/financials/quarterly/{symbol}/`

- **Purpose:** Quarterly income + balance-sheet (and cash-flow where reported) for one IDX symbol. Banking/insurance companies get extra fields.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. E.g. `BMRI`, `BBCA`, `TLKM`. |

- **Query parameters**

| Name | Type | Default | Notes |
|---|---|---|---|
| `report_date` | string (date) | — | Specific `YYYY-MM-DD`. Get valid values from `/v2/company/get_quarterly_financial_dates/{symbol}/`. Bad format → 400 "Use a valid report_date format of YYYY-MM-DD". |
| `approx` | bool | `true` | If true, use approximate quarter matching when the exact date is not found. |
| `n_quarters` | int | — | ≥1. Number of most recent quarters to return. Defaults vary. |

- **Per-row fields** (most are nullable; some return `null` for non-financial companies)

| Group | Fields |
|---|---|
| Always | `symbol`, `date`, `revenue`, `earnings`, `total_assets`, `total_equity`, `total_liabilities`, `total_debt`, `stockholders_equity`, `operating_cash_flow`, `financing_cash_flow`, `investing_cash_flow`, `net_cash_flow`, `free_cash_flow`, `realized_capital_goods_investment`, `cash_only`, `cash_and_short_term_investments`, `ebit`, `ebitda`, `gross_profit`, `cost_of_revenue`, `interest_expense_non_operating`, `current_liabilities`, `non_interest_bearing_liabilities`, `non_loan_assets`, `non_operating_income_or_loss`, `non_interest_income`, `operating_expense`, `operating_pnl`, `premium_income`, `premium_expense`, `net_premium_income`, `provision`, `tax`, `earnings_before_tax`, `minorities`, `total_current_asset`, `total_non_current_assets`, `total_non_current_liabilities` |
| Banking/insurance only | `financials_sector_metrics.{interest_income, interest_expense, net_interest_income, gross_loan, allowance_for_loans, net_loan, current_account, savings_account, time_deposit, total_deposit, total_earning_assets, other_interest_bearing_liabilities, total_cash_and_due_from_banks}` |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/financials/quarterly/BBCA/?n_quarters=4" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/financials/quarterly/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"n_quarters": 4},
    timeout=30,
)
r.raise_for_status()
quarters = r.json()  # list, newest first
```

- **Sample response** (BBCA, financial sector, single quarter)

```json
[
  {
    "symbol": "BBCA.JK",
    "date": "2026-03-31",
    "revenue": 28434118000000,
    "earnings": 14695475000000,
    "total_assets": 1640830566000000,
    "total_equity": 259358793000000,
    "operating_pnl": 18077072000000,
    "operating_cash_flow": 47920728000000,
    "free_cash_flow": 47485515000000,
    "financials_sector_metrics": {
      "interest_income": 24592248000000,
      "interest_expense": 3483815000000,
      "net_interest_income": 21108433000000,
      "gross_loan": 970701203000000,
      "allowance_for_loans": 30526805000000,
      "net_loan": 940174398000000,
      "current_account": 447811289000000,
      "savings_account": 634224104000000,
      "time_deposit": 194373518000000,
      "total_deposit": 1276408911000000,
      "total_cash_and_due_from_banks": 90242485000000
    }
  }
]
```

- **Gotchas**
  - **Costs 1 credit per quarter returned.** Calling `n_quarters=4` costs 4 credits.
  - `approx=true` is the default — useful when you pass a fuzzy date and want the closest quarter. Set `approx=false` if you need an exact match.
  - All money fields in **IDR** (integer).
  - Banking/insurance companies always include `financials_sector_metrics`; non-financial companies leave it as `null` (or omit it).
  - 404 "Invalid stock symbol and/or data for the specified report_date does not exist" → 1 credit.

---

### `GET /v2/company/get_quarterly_financial_dates/{symbol}/`

- **Purpose:** Helper — list every available quarterly report date for one symbol, grouped by financial year. Use as input for `report_date=` above.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. E.g. `ASII`, `BBCA`. |

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/company/get_quarterly_financial_dates/BBCA/" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/company/get_quarterly_financial_dates/BBCA/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{ "2026": [["2026-03-31", "q1"]] }
```

- **Gotchas**
  - Dictionary keys are **string years** (`"2026"`, not `2026`).
  - Values are `[report_date, quarter_label]` tuples; `quarter_label` ∈ `q1`..`q4`.
  - 404 → 1 credit.
  - For universe freshness, prefer `/v2/companies/quarterly-financial-dates/?since=` instead — see next.

---

### `GET /v2/companies/quarterly-financial-dates/`

- **Purpose:** Universe feed — latest available quarterly report date for every IDX company in one paginated feed. Built for incremental polling via `since=`.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `since` | string (date) | — | `YYYY-MM-DD` | Return only companies whose latest quarter-end ≥ this date. Future date → empty result. |
| `year` | int | — | 1900–2026 | Restrict to a calendar year; returns each company's latest quarter inside it. |
| `limit` | int | 20 | 1–30 | Page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/companies/quarterly-financial-dates/?since=2025-09-30&limit=30" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/companies/quarterly-financial-dates/",
    headers={"Authorization": "<api-key>"},
    params={"since": "2025-09-30", "limit": 30},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [{ "symbol": "AADI.JK", "date": "2026-03-31", "quarter": "q1" }],
  "pagination": {
    "total_count": 959, "showing": 1, "limit": 30, "offset": 0,
    "has_next": true, "has_previous": false,
    "next_offset": 30, "previous_offset": null
  }
}
```

- **Gotchas**
  - Sorted by symbol. Companies with no quarterly data omitted. ~950 rows in the universe.
  - `since` invalid → 400 "Use a valid date format of YYYY-MM-DD".
  - `year` invalid → 400 "Please provide a valid year".
  - 1 credit per page. Full sweep at `limit=30` ≈ 32 pages ≈ 32 credits. Use `since` to poll incrementally and stay near 1 credit per run.

---

### `GET /v2/close/`

- **Purpose:** Daily close for **every** IDX ticker on a single trading day, in one paginated feed. Universe feed — cheaper than per-symbol loops.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `date` | string (date) | most recent trading day | `YYYY-MM-DD` | Bad format → 400. Future date → 400 "Date cannot be in the future". |
| `limit` | int | 20 | 1–30 | Max page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/close/?date=2025-05-02&limit=30" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/close/",
    headers={"Authorization": "<api-key>"},
    params={"date": "2025-05-02", "limit": 30},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [{ "symbol": "AADI.JK", "date": "2025-05-02", "close": 7150 }],
  "pagination": {
    "total_count": 942, "showing": 1, "limit": 30, "offset": 0,
    "has_next": true, "has_previous": false,
    "next_offset": 30, "previous_offset": null
  }
}
```

- **Gotchas**
  - **Only `close` is returned** — no volume or market cap here. For those, use `/v2/daily/{symbol}/` per ticker.
  - Tickers with no recorded close for the day are **omitted** (not returned with `null`).
  - 1 credit per page. Full ~950-ticker pull at `limit=30` ≈ 32 credits. For 1-day freshness this is the cheapest universe source.

---

### `GET /v2/daily/{symbol}/`

- **Purpose:** Daily close, volume, and market cap for one IDX symbol over a date range of up to 90 days.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. E.g. `BBCA`, `GOTO`, `TLKM`. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | 30 days before `end` | `YYYY-MM-DD` | Wider ranges clamped to the most recent 90 days. |
| `end` | string (date) | today | `YYYY-MM-DD` | Future date → 400 "Date cannot be in the future". |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/daily/BBCA/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/daily/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "symbol": "BBCA.JK", "date": "2025-05-02", "close": 8975, "volume": 92219000, "market_cap": 1095329638012500 }
]
```

- **Gotchas**
  - Costs 1 credit (regardless of `n_quarters`-like date span).
  - Max window = 90 days; silently clamps wider ranges to the most recent 90 ending at `end`.
  - **404 only when the symbol itself is unknown** ("Given stock symbol 'ZZZZ' does not exist"). A valid symbol with no rows in the window returns `200` with `[]`.
  - For >90-day history on a single symbol, paginate `start`/`end` in 90-day chunks.

---

### `GET /v2/idx-total/`

- **Purpose:** Historical total IDX market capitalization over a date range of up to 90 days.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | 30 days before `end` | `YYYY-MM-DD`, **earliest `2021-01-01`** | Earlier → 400 "Starting date must not be earlier than January 1, 2021." Wider ranges clamped to most recent 90. |
| `end` | string (date) | today | `YYYY-MM-DD` | Future date → 400. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/idx-total/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/idx-total/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "date": "2026-06-09", "idx_total_market_cap": 10095511071726246 }
]
```

- **Gotchas**
  - Market cap is in **IDR** (integer).
  - Costs 1 credit.
  - Earliest valid `start` = `2021-01-01`.

---

### `GET /v2/index-daily/{index_code}/`

- **Purpose:** Daily closing price for one IDX index over a date range of up to 90 days.

- **Path parameters**

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `index_code` | string | `ftse`, `idx30`, `idxbumn20`, `idxesgl`, `idxg30`, `idxhidiv20`, `idxq30`, `idxv30`, `ihsg`, `jii70`, `kompas100`, `lq45`, `sminfra18`, `srikehati`, `sti`, `economic30`, `idxvesta28` | All lowercase in the URL. Bad code → 400 "Please provide a valid index code". |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | 30 days before `end` | `YYYY-MM-DD`, **earliest `2019-01-02`** | Wider ranges clamped to most recent 90. |
| `end` | string (date) | today | `YYYY-MM-DD` | Future date → 400. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/index-daily/lq45/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/index-daily/lq45/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "index_code": "LQ45", "date": "2025-05-05", "price": 767.32 }
]
```

- **Gotchas**
  - `index_code` is case-sensitive in the URL — use lowercase (`lq45` not `LQ45`). Response echoes the **uppercase** form.
  - `price` is a `double` (most IDX indices use float values).
  - Costs 1 credit.
  - Earliest `start` = `2019-01-02`.

---

## Cross-reference

- For per-symbol fundamentals over time, pair `/v2/financials/quarterly/{symbol}/` with `/v2/daily/{symbol}/` (price) and `/v2/brokers/foreign-flow/{symbol}/` (foreign flow).
- The two **universe feeds** (`/v2/close/`, `/v2/companies/quarterly-financial-dates/`) are the cheapest way to poll breadth. Use them as your cron triggers.
- Daily endpoints share the 90-day clamp pattern — paginate by 90-day chunks for longer histories.
- See `idx-screener.md` for the screening-side helpers, `idx-company.md` for full company reports, `idx-rankings-brokers-news.md` for rankings + broker flow.