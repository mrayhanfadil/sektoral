# SGX (Singapore Exchange) — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. SGX ticker = 3 characters (letters or digits), optionally `.si`.

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/sgx/companies/` | SQL-like or NL screener for SGX-listed companies |
| `GET /v2/sgx/company/report/{symbol}/` | Full SGX company report (4 selectable sections) |
| `GET /v2/sgx/sectors/` | Discovery — valid SGX sector slugs |
| `GET /v2/sgx/subsectors/` | Discovery — valid SGX subsector slugs |
| `GET /v2/sgx/tags/` | Discovery — valid SGX news tag slugs |
| `GET /v2/sgx/daily/{symbol}/` | Daily close + volume for one SGX symbol (≤90d) |
| `GET /v2/sgx/buybacks/` | SGX share buyback records |
| `GET /v2/sgx/short-sell/` | SGX short-sell activity |
| `GET /v2/sgx/companies/top/` | Top SGX by dividend_yield/revenue/earnings/market_cap/pe |
| `GET /v2/sgx/news/` | SGX news articles |
| `GET /v2/sgx/filings/` | SGX insider filings |

> All SGX paths are nested under `/v2/sgx/...` (NOT under `/v2/singapore/...` or `/v2/transaction/`).
> SGX is **annual-only** for fundamentals — no quarterly data exposed. Big-cap coverage only for many yearly cash-flow fields; bank-only fields cover DBS/OCBC/UOB.

---

### `GET /v2/sgx/companies/`

- **Purpose:** Paginated screener for SGX-listed companies. SQL-like (`where`+`order_by`) or NL (`q`).

- **Query parameters**

| Name | Type | Default | Allowed values / format | Notes |
|---|---|---|---|---|
| `q` | string | — | natural language, e.g. `top 5 SGX banks by market cap` | Costs **3 credits** on success; 1 credit on 400 if LLM translation already ran. |
| `where` | string | — | SQL-like condition (same operators as IDX). Bracket notation: `revenue[2024]`. | 1 credit on success. Free 400. |
| `order_by` | string | — | Field name (asc) or `-field` (desc). | — |
| `limit` | int | 50 | 1–200 | — |
| `offset` | int | 0 | ≥0 | — |
| `sub_sector` | string | — | kebab-case slug from `/v2/sgx/subsectors/` | — |
| `sector` | string | — | kebab-case slug from `/v2/sgx/sectors/` | NB: source has duplicate variants — see Gotchas. |
| `include_query_values` | bool | false | true/false | Echoes field values used in filter. |

- **Field categories**

- Direct: `symbol`, `company_name`, `sector`, `sub_sector`, `market_cap`, `volume`, `last_close_price`, `employee_num`, `pe`, `eps`, `beta`, `ps`, `pcf`, `pb`, `gross_margin`, `operating_margin`, `net_profit_margin`, `quick_ratio`, `current_ratio`, `debt_to_equity`, `one_year_eps_growth`, `one_year_sales_growth`, `forward_dividend`, `forward_dividend_yield`, `dividend_ttm`, `dividend_yield_5y_avg`, `dividend_growth_rate`, `payout_ratio`, `change_1d`, `change_7d`, `change_1m`, `change_ytd`, `change_1y`, `change_3y`.
- Array (`in` only): `tags`.
- JSON-object auto-extract: `ytd_low_price`/`_date`, `ytd_high_price`/`_date`, `52_w_low_price`/`_date`, `52_w_high_price`/`_date`, `90_d_low_price`/`_date`, `90_d_high_price`/`_date`, `all_time_low_price`/`_date`, `all_time_high_price`/`_date`.
- Yearly JSON (bracket `[YYYY]`): `revenue`, `earnings`, `total_dividend`, `total_yield`. Coverage-tagged: `operating_cash_flow`, `investing_cash_flow`, `financing_cash_flow`, `free_cash_flow`, `net_cash_flow`, `capital_expenditure`, `ebit`, `ebitda`, `gross_income`, `cost_of_revenue`, `operating_income`, `operating_expense`, `pretax_income`, `income_taxes`, `total_asset`, `total_equity`, `total_liabilities`, `working_capital`, `total_current_asset`, `total_non_current_asset` are **Big caps only** (~22 names). Bank-only: `net_interest_income`, `interest_income`, `interest_expense`, `net_fee_and_commission_income`, `net_trading_income`, `net_loan`, `gross_loan`, `total_deposit`, `core_capital_tier1`, `total_risk_weighted_asset`.

- **Sample request**

```bash
curl -G "https://api.sectors.app/v2/sgx/companies/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "where=sub_sector = 'Banks & Credit Services' and market_cap IS NOT NULL" \
  --data-urlencode "order_by=-market_cap" \
  --data-urlencode "limit=5"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/sgx/companies/",
    headers={"Authorization": "<api-key>"},
    params={
        "where": "sub_sector = 'Banks & Credit Services' and market_cap IS NOT NULL",
        "order_by": "-market_cap",
        "limit": 5,
    },
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [
    { "symbol": "D05", "company_name": "DBS Group Holdings Ltd", "query_values": { "sub_sector": "Banks & Credit Services", "market_cap": 194775527849 } }
  ],
  "pagination": { "total_count": 10, "showing": 1, "limit": 3, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 3, "previous_offset": null },
  "llm_translation": {
    "natural_query": "top 3 banks by market cap",
    "translated_params": { "where": "sub_sector = 'Banks & Credit Services' and market_cap IS NOT NULL", "order_by": "-market_cap", "limit": 3, "offset": null, "include_query_values": true },
    "message": null
  }
}
```

- **Gotchas**
  - **Annual only** — `revenue_q` style quarterly brackets return NON_TRANSLATABLE_QUERY if the LLM tries to translate a quarterly query.
  - **No person/entity ownership fields** — `executives`, `major_shareholders`, `affiliates` are IDX-only.
  - **No peer averages** — `pe_peer_avg`/`pb_peer_avg` not available for SGX.
  - **No `free_float`** — use `/v2/sgx/buybacks/` and `/v2/sgx/short-sell/` for capital-action data.
  - **Sector duplicate variants** (`Consumer Cyclical` / `Consumer Cyclicals`, `Financial Services` / `Financials`, `Real Estate` / `Properties & Real Estate` / `REIT`) — pending upstream cleanup. Use `OR` to capture all matches.
  - Coverage caveats: yearly fields marked `[Big caps only]` are populated for ~22 large-caps; `[Banks only]` only DBS/OCBC/UOB. The doc page marks these per field.

---

### `GET /v2/sgx/company/report/{symbol}/`

- **Purpose:** Full SGX company report organized into 4 selectable sections.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | SGX symbol, 3 chars (letters or digits), optionally `.si` (case-insensitive). E.g. `D05`, `U11`, `Z74`. |

- **Query parameters**

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `sections` | array of strings | `overview`, `valuation`, `financials`, `dividend` | Comma-separated. Defaults to all 4. |

- **Sections (what each contains)**

| Section | Content |
|---|---|
| `overview` | Market cap, volume, employee_num, sector, sub_sector, tags, last_close_price, change_{1d,7d,1m,1y,3y,ytd}, all-time price highs/lows |
| `valuation` | `pe`, `beta`, `ps`, `pcf`, `pb` (TTM ratios) |
| `financials` | `historical_financials[YYYY].{date, revenue, earnings, cash_flow_metrics, income_stmt_metrics, balance_sheet_metrics}`, `eps`, `gross_margin`, `operating_margin`, `net_profit_margin`, `one_year_eps_growth`, `one_year_sales_growth`, `quick_ratio`, `current_ratio`, `debt_to_equity` |
| `dividend` | `dividend_yield_5y_avg`, `dividend_growth_rate`, `payout_ratio`, `forward_dividend`, `forward_dividend_yield`, `dividend_ttm`, `historical_dividends[YYYY].{breakdown, total_yield, total_dividend}` |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/company/report/D05/?sections=overview,valuation,financials" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/sgx/company/report/D05/",
    headers={"Authorization": "<api-key>"},
    params={"sections": "overview,valuation,financials"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response (truncated)**

```json
{
  "symbol": "D05",
  "name": "DBS Group Holdings Ltd",
  "overview": {
    "market_cap": 194775527849, "volume": 4746800, "employee_num": 41000,
    "sector": "Financial Services", "sub_sector": "Banks & Credit Services",
    "tags": ["52-w-high", "90-d-high", "all-time-high", "dividend-increase-5y"],
    "last_close_price": 69.1,
    "change_1d": 0.0067, "change_7d": 0.0561, "change_1m": 0.1010,
    "change_1y": 0.2080, "change_3y": null, "change_ytd": 0.2080,
    "all_time_price": {
      "ytd_low":  { "2026-03-09": 52.81 },
      "ytd_high": { "2026-07-07": 68.64 },
      "all_time_low":  { "2009-03-09": 2.73 },
      "all_time_high": { "2026-07-07": 68.64 }
    }
  },
  "valuation": { "pe": 17.29, "beta": 1.20, "ps": 8.20, "pcf": 17.06, "pb": 2.71 },
  "financials": {
    "historical_financials": {
      "2025": {
        "date": "2025-12-31",
        "revenue": 22895000000, "earnings": 10934000000,
        "cash_flow_metrics": { "operating_cash_flow": 11024000000, "free_cash_flow": 10499000000 },
        "income_stmt_metrics": { "pretax_income": 12999000000, "operating_expense": 9309000000 },
        "balance_sheet_metrics": { "total_asset": 897488000000, "total_equity": 68916000000 }
      }
    },
    "eps": 3.82, "net_profit_margin": 0.48, "debt_to_equity": 1.09
  }
}
```

- **Gotchas**
  - **Costs 1 credit per section.** Defaults = 4 credits; pass `sections=` to save.
  - 404 "Given SGX symbol does not exist" → 1 credit.
  - Symbol accepts lowercase (`d05`), uppercase (`D05`), or with `.si` suffix (`d05.si`).

---

### `GET /v2/sgx/sectors/`

- **Purpose:** Discovery — flat array of SGX sector slugs.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/sectors/" -H "Authorization: <api-key>"
```

- **Sample response**

```json
["consumer-non-cyclicals"]
```

- **Gotchas**
  - Costs 1 credit.
  - Returned as a flat array of slugs (not key-value pairs).
  - Same duplicate-variant gotcha as the screener — fetch the full list and treat labels carefully.

---

### `GET /v2/sgx/subsectors/`

- **Purpose:** Discovery — sector/subsector kebab-slug pairs.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/subsectors/" -H "Authorization: <api-key>"
```

- **Sample response**

```json
[{ "sector": "reit", "subsector": "reit-industrial" }]
```

- **Gotchas**
  - Costs 1 credit.

---

### `GET /v2/sgx/tags/`

- **Purpose:** Discovery — full list of distinct SGX news tag slugs.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/tags/" -H "Authorization: <api-key>"
```

- **Sample response (truncated — full list is ~63 slugs)**

```json
{
  "tags": [
    "analyst-ratings", "annual-report", "artificial-intelligence",
    "asset-management", "asset-purchase", "award", "bearish", "bonus",
    "bullish", "business-expansion", "capital-funding", "central-bank",
    "commodities", "credit", "cryptocurrency", "currency-fx", "cyber-security",
    "debt-issuance", "delisting", "digital-payments", "digital-transformation",
    "diversification", "dividend-announcement", "domestic-investor", "esg",
    "executive-changes", "export", "financial-metrics", "foreign-investment",
    "global-economy", "global-index", "government-policy", "inflation",
    "insider-trading", "institutional-investor", "interest-rate", "ipo",
    "joint-venture", "market-sentiment", "mergers-acquisitions", "ministry",
    "mou", "neutral", "oversubscribed", "ownership", "partnerships-agreements",
    "pilot-project", "politics-regulation", "portfolio", "private-placement",
    "product-launch", "production-operations", "rd", "risk-compliance",
    "shareholders-general-meeting", "stock-buyback", "stock-split",
    "subsidiaries", "subsidies-incentives", "suspension", "tariff-vat",
    "trading-halt", "undervalued", "violation"
  ]
}
```

- **Gotchas**
  - Costs 1 credit. Cache once.
  - Response wraps tags inside a `tags` key (unlike `/v2/sgx/sectors/` which is a bare array).

---

### `GET /v2/sgx/daily/{symbol}/`

- **Purpose:** Daily close + volume for one SGX symbol over a date range of up to 90 days.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | SGX symbol, 3 chars. E.g. `D05`, `U11`. |

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `start` | string (date) | 30 days before `end` | `YYYY-MM-DD` | Wider ranges clamped to most recent 90. |
| `end` | string (date) | today | `YYYY-MM-DD` | Future → 400. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/daily/D05/?start=2025-05-01&end=2025-05-14" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/sgx/daily/D05/",
    headers={"Authorization": "<api-key>"},
    params={"start": "2025-05-01", "end": "2025-05-14"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "symbol": "D05", "date": "2025-05-02", "close": 42.70, "volume": 4354400 }
]
```

- **Gotchas**
  - No `market_cap` here (unlike IDX `/v2/daily/{symbol}/`).
  - `close` is a `double` (SGX prices are fractional), `volume` is integer.
  - 404 "Given SGX symbol 'XYZ' does not exist" → 1 credit.

---

### `GET /v2/sgx/buybacks/`

- **Purpose:** SGX share buyback records (purchase date, type, price range, value, mandate).

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `symbol` | string | — | SGX 3-char | Filter to one ticker. |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `purchase_date`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/buybacks/?symbol=U11&limit=20" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    {
      "symbol": "U11",
      "purchase_date": "2026-07-08",
      "type": "On Market",
      "price_per_share": { "lowest": 41.71, "highest": 42.44 },
      "total_value": 633841.58,
      "total_shares_purchased": 15100,
      "treasury_shares_after_purchase": 13376400,
      "mandate": {
        "mandate_start": "2026-04-17", "mandate_end": "2027-04-17",
        "mandate_total": 82676174, "mandate_remaining": 79645474,
        "cumulative_purchased": 3030700
      }
    }
  ],
  "pagination": { "total_count": 2884, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - Costs 1 credit.
  - `mandate_remaining` is a great real-time "how much dry powder is left?" signal.
  - 2,884 historical buyback records in the universe.

---

### `GET /v2/sgx/short-sell/`

- **Purpose:** SGX short-sell records (counterparty, date, volume, value).

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `symbol` | string | — | SGX 3-char | — |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `date`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/short-sell/?symbol=D05&start=2026-07-01" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    { "name": "aem sgd", "symbol": "AWX", "date": "2026-07-08", "volume": 758800, "value": 7150370 }
  ],
  "pagination": { "total_count": 16665, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - `name` is the **counterparty / short seller** — not the listed company.
  - 16,665 historical short-sell records in the universe.
  - Costs 1 credit.

---

### `GET /v2/sgx/companies/top/`

- **Purpose:** Top SGX companies ranked by 1+ classifications (dividend_yield/revenue/earnings/market_cap/pe).

- **Query parameters**

| Name | Type | Default | Allowed / range | Notes |
|---|---|---|---|---|
| `classifications` | array | all 5 | `dividend_yield`, `revenue`, `earnings`, `market_cap`, `pe` | Comma-separated. Bad value → 400. |
| `n_stock` | int | 5 | 1–10 | Per-classification list length. |
| `sector` | string | all | kebab-case slug | Filter to one sector. |
| `min_mcap_million` | int | 1000 | ≥0 | Min market cap in million SGD (1M SGD = 1,000,000 SGD). |

- **Cost:** 1 credit per classification. Defaults (5) = 5 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/companies/top/?classifications=dividend_yield,market_cap&n_stock=10" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "dividend_yield": [
    { "symbol": "T14", "forward_dividend_yield": 0.2528, "company_name": "Tianjin Pharmaceutical Da Ren Tang Group Corp Ltd" }
  ],
  "revenue": [
    { "symbol": "F34", "revenue": 90420797802, "company_name": "Wilmar International Ltd" }
  ],
  "earnings": [
    { "symbol": "D05", "earnings": 10934000000, "company_name": "DBS Group Holdings Ltd" }
  ],
  "market_cap": [
    { "symbol": "M12", "market_cap": 735208084260, "company_name": "Maruwa Co Ltd" }
  ],
  "pe": [
    { "symbol": "B61", "pe": 0.0954, "company_name": "Bukit Sembawang Estates Ltd" }
  ]
}
```

- **Gotchas**
  - Each classification produces a different ranking schema — `dividend_yield` returns `forward_dividend_yield`, `market_cap` returns `market_cap`, etc.
  - Default `min_mcap_million=1000` = 1B SGD floor. Set `=0` to include small-caps.

---

### `GET /v2/sgx/news/`

- **Purpose:** Paginated SGX news articles.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `sector` | string | — | case-insensitive sector name | — |
| `sub_sector` | string | — | case-insensitive sub-sector name | — |
| `symbols` | string | — | comma-sep, e.g. `D05,U11` | — |
| `tags` | string | — | comma-sep tag slugs from `/v2/sgx/tags/` | — |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `timestamp`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/news/?sector=financial-services&limit=20" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    {
      "title": "Three SGX underdog stocks raise dividends amid soft profit trends",
      "body": "The article discusses three Singapore Exchange-listed companies that increased their total dividend payouts ...",
      "source": "https://thesmartinvestor.com.sg/hunting-for-cash-these-sgx-underdog-stocks-just-paid-out-big/",
      "timestamp": "2026-07-09T11:30:00",
      "sector": "financial-services",
      "sub_sector": ["financial-data-shell-companies", "hardware-electronics", "restaurants-food-retail"],
      "tags": ["Dividend Announcement", "Financial Metrics", "Stock Buyback", "Bullish"],
      "symbols": ["TCU", "BN2", "5ML"],
      "dimension": { "future": 0, "dividend": 0, "ownership": 0, "technical": 0, "valuation": 0, "financials": 1, "management": 0, "sustainability": 0 }
    }
  ],
  "pagination": { "total_count": 243, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - Costs 1 credit per page. SGX universe is smaller (~243 articles) than IDX.
  - `dimension` is a structured score object — useful for filtering "financials-focused" news.
  - `tags` here are mixed-case ("Dividend Announcement" with capital D) — pass them verbatim when filtering.

---

### `GET /v2/sgx/filings/`

- **Purpose:** SGX insider trading filings (buy/sell/award/transfer/others).

- **Query parameters**

| Name | Type | Default | Allowed | Notes |
|---|---|---|---|---|
| `symbol` | string | — | SGX 3-char | — |
| `transaction_type` | string | — | `award`, `buy`, `others`, `sell`, `transfer` | Case-insensitive. |
| `holder_type` | string | — | `insider`, `institution` | Case-insensitive. |
| `start` | string (date) | — | `YYYY-MM-DD` | Optional lower bound on `timestamp`. |
| `end` | string (date) | — | `YYYY-MM-DD` | Optional upper bound. Future → 400. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/sgx/filings/?symbol=D05&transaction_type=buy&limit=20" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    {
      "symbol": "S59", "timestamp": "2026-07-06", "transaction_type": "award",
      "holder_name": "Chin Yau Seng", "holder_type": "insider",
      "holding_before": 172700, "holding_after": 495193, "amount_transaction": 322493,
      "transaction_value": null, "price_per_share": null,
      "share_percentage_before": 0.00015, "share_percentage_after": 0.00044,
      "share_percentage_transaction": 0.00029
    }
  ],
  "pagination": { "total_count": 541, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - `transaction_type=award` covers share grants (RSU/ESPP) which are non-cash — `transaction_value` and `price_per_share` will be `null`.
  - `share_percentage_transaction` is the headline metric — easy to compare across small/large companies.
  - Costs 1 credit per page.

---

## Cross-reference

- SGX coverage is **annual-only** for fundamentals — no quarterly bracket fields like IDX.
- SGX data is **smaller and simpler** than IDX. The screener lacks `free_float`, peer averages, executives, and major-shareholders queries — that's a data limitation, not a query bug.
- For SGX capital-action signals: `buybacks` (insider sentiment from the company) + `short-sell` (bearish positioning from the market) cover the same territory as IDX broker-flow analysis.
- See `klse.md` (Malaysia), `mining.md` (Indonesian mining), and `idx-*.md` (IDX) for the other regions.