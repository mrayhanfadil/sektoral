# IDX Screener & Helper Lists — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. IDX ticker = 4-letter code, optionally `.JK` (case-insensitive).

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/companies/` | SQL-like or NL screener for IDX-listed companies |
| `GET /v2/free-float/` | Free float % per company, filterable by one taxonomy level |
| `GET /v2/companies/list_companies_with_segments/` | Companies (with year list) that have revenue/cost segments |
| `GET /v2/companies/quarterly-financial-dates/` | Universe-wide latest quarterly report dates (freshness polling) |
| `GET /v2/company/get_quarterly_financial_dates/{symbol}/` | All quarterly report dates for one symbol |
| `GET /v2/subsectors/` | Sector/subsector kebab-slugs |
| `GET /v2/industries/` | Subsector/industry kebab-slugs |
| `GET /v2/subindustries/` | Industry/sub-industry kebab-slugs |

> Note on path naming: the docs index lists `…/api-references/v2/indonesia/screener/free-float.md`, but the actual REST path is `GET /v2/free-float/` (no `/screener/` prefix). Same for `/v2/companies/list_companies_with_segments/` (segments helper).

---

### `GET /v2/companies/`

- **Purpose:** Paginated screener for IDX-listed companies. Supports SQL-like structured queries (`where` + `order_by`) or natural language queries (`q`). `q` overrides `where`/`order_by`.

- **Query parameters**

| Name | Type | Default | Allowed values / format | Notes |
|---|---|---|---|---|
| `q` | string | — | natural language, e.g. `top 10 tech companies by revenue in 2023` | Mutually exclusive with structured params. Costs **3 credits** on success; **1 credit on 400 if the LLM translation already ran**; otherwise free. |
| `where` | string | — | SQL-like condition with `=`, `!=`, `>`, `>=`, `<`, `<=`, `like`, `in`, `and`/`or`. Bracket notation for year/quarter fields (`revenue[2024]`, `revenue_q[Q1-2024]`). Arithmetic allowed on both sides. | Free 400. Costs 1 credit on success. |
| `order_by` | string | — | Field name (asc) or `-field` (desc). Supports yearly bracket fields, e.g. `order_by=-revenue[2023]`. | Pairs with `where`. |
| `limit` | int | 50 | 1–200 | Page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |
| `include_query_values` | bool | false | `true`/`false` | When true, each `results[]` row carries a `query_values{}` block with the interpreted field values. |
| `sub_sector`, `industry`, `sub_industry`, `sector` | string | — | Kebab-case slugs from the helper endpoints | Optional filters. Best NL precision comes from filtering by these. |

- **Field categories in `where` / `order_by`**
  - Direct: `symbol`, `company_name`, `listing_board`, `industry`, `sub_industry`, `sector`, `sub_sector`, `market_cap`, `market_cap_rank`, `employee_num`, `employee_num_rank`, `listing_date`, `last_ex_dividend_date`, `last_close_price`, `daily_close_change`, `forward_pe`, `intrinsic_value`, `esg_score`, `yield_ttm`, `dividend_ttm`, `payout_ratio`, `cash_payout_ratio`, `yoy_quarter_earnings_growth`, `yoy_quarter_revenue_growth`.
  - Array (`in` only): `tags`, `indices`, `affiliates`.
  - JSON-object auto-extract: `pe_ttm`, `pb_mrq`, `ps_ttm`, `dar_mrq`, `der_mrq`, `roa_ttm`, `roe_ttm`, `total_assets_mrq`, `total_equity_mrq`, `total_revenue_mrq`, `earnings_mrq`, `total_liabilities_mrq`, `yearly_mcap_change`, `dividend_yield_avg_period`, `dividend_yield_avg`, `ytd_low_price`/`_date`, `ytd_high_price`/`_date`, `52_w_low_price`/`_date`, `52_w_high_price`/`_date`, `90_d_low_price`/`_date`, `90_d_high_price`/`_date`, `all_time_low_price`/`_date`, `all_time_high_price`/`_date`.
  - Yearly JSON (bracket `[YYYY]` required): `eps`, `eps_growth`, `total_dividend`, `total_yield`, `earnings`, `revenue`, `total_assets`, `total_equity`, `total_liabilities`, `ebit`, `ebitda`, `gross_profit`, `free_cash_flow`, `operating_cash_flow`, `cash_and_equivalents`, `cash_only`, `cash_inflow`, `cash_outflow`, `net_cash_flow`, `current_assets`, `current_liabilities`, `fixed_assets`, `inventories`, `retained_earnings`, `total_debt`, `interest_income`, `interest_expense`, `operating_pnl`, `tax`, `outstanding_shares`, `prepaid_assets`, `non_operating_income_or_loss`, `interest_expense_non_operating`, `capital_expenditure`, `realized_capital_goods_investment`, `cost_of_revenue`, `earnings_before_tax`, `financing_cash_flow`, `investing_cash_flow`, `end_cash_position`, `non_current_liabilities`, `provision`. Ratios: `pe`, `pb`, `ps`, `pcf`, `peg`, `enterprise_to_ebitda`, `enterprise_to_revenue`, `pb_peer_avg`, `pe_peer_avg`, `ps_peer_avg`, `debt_to_asset_ratio`, `debt_to_equity_ratio`, `cash_flow_to_debt_ratio`, `interest_coverage_ratio`, `current_ratio`, `operating_cash_flow_margin`, `fixed_asset_turnover`, `total_asset_turnover`, `roa`, `roe`, `net_profit_margin`, `gross_profit_margin`, `operating_profit_margin`, `efficiency_ratio`, `cost_to_income_ratio`. Banking-only: `allowance_for_loans`, `core_capital_tier1`, `credit_rwa`, `current_account`, `gross_loan`, `high_quality_liquid_asset`, `market_rwa`, `net_interest_income`, `net_loan`, `non_interest_bearing_liabilities`, `non_interest_income`, `non_loan_assets`, `non_loan_earning_assets`, `non_loan_non_earning_assets`, `operational_rwa`, `other_interest_bearing_liabilities`, `savings_account`, `supplementary_capital_tier2`, `time_deposit`, `total_cash_and_due_from_banks`, `total_deposit`, `total_risk_weighted_asset`, `special_mention_loan`, `non_performing_loan`, `restructured_loan_current`, `capital_adequacy_ratio`, `casa_ratio`, `leverage_ratio`, `loan_to_deposit_ratio`, `liquidity_coverage_ratio`, `net_interest_margin`. Insurance: `net_premium_income`, `premium_expense`, `premium_income`. Forecast: `forecast_eps_growth`, `forecast_revenue_growth`, `forecast_eps_estimate`, `forecast_revenue_estimate`.
  - Quarterly (`[Qi-YYYY]`): `revenue_q`, `earnings_q`, `net_loan_q`, `gross_profit_q`, `time_deposit_q`, `operating_pnl_q`, `total_deposit_q`.

- **Smart-FY handling:** Between January–April, "latest year" queries default to the **previous** audited year (e.g. early-2026 → 2024 data).

- **Sample request**

```bash
curl -G "https://api.sectors.app/v2/companies/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "where=sub_sector = 'banks' and market_cap IS NOT NULL" \
  --data-urlencode "order_by=-market_cap" \
  --data-urlencode "limit=10" \
  --data-urlencode "include_query_values=true"
```

```python
import requests
r = requests.get(
    "https://api.sectors.app/v2/companies/",
    headers={"Authorization": "<api-key>"},
    params={
        "where": "sub_sector = 'banks' and market_cap IS NOT NULL",
        "order_by": "-market_cap",
        "limit": 10,
        "include_query_values": "true",
    },
    timeout=30,
)
r.raise_for_status()
data = r.json()
```

- **Sample response (truncated)**

```json
{
  "results": [
    {
      "symbol": "BBCA.JK",
      "company_name": "PT Bank Central Asia Tbk.",
      "query_values": { "sub_sector": "Banks", "market_cap": 753611199412500 }
    }
  ],
  "pagination": {
    "total_count": 48, "showing": 1, "limit": 3, "offset": 0,
    "has_next": true, "has_previous": false,
    "next_offset": 3, "previous_offset": null
  },
  "llm_translation": {
    "natural_query": "top 3 banks by market cap",
    "translated_params": {
      "where": "sub_sector = 'Banks' and market_cap IS NOT NULL",
      "order_by": "-market_cap", "limit": 3, "offset": null,
      "include_query_values": true
    },
    "message": null
  }
}
```

- **Gotchas**
  - Field name `revenue_in_2024` → 400 `INVALID_WHERE_CLAUSE`; use bracket notation `revenue[2024]`.
  - `LIKE` on a numeric field → 400 `TYPE_MISMATCH`.
  - `LIMIT` must be 1–200; out-of-range → 400 `INVALID_LIMIT`.
  - Smart-FY only applies between Jan–Apr; rest of the year uses the most recent annual data.
  - Empty/unmatchable NL query → 400 `NON_TRANSLATABLE_QUERY` (billed 1 credit to recover LLM cost).
  - `where=free_float>0.5` is supported on this endpoint **or** use the dedicated `/v2/free-float/`.

---

### `GET /v2/free-float/`

- **Purpose:** Free float % per company, optionally filtered by one level of taxonomy. Results sorted by `free_float` descending.

- **Query parameters** (mutually exclusive — provide at most one filter)

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `sector` | string | kebab-case sector slug, e.g. `infrastructures`, `healthcare`, `transportation-logistic` | from `/v2/subsectors/` |
| `sub_sector` | string | e.g. `banks`, `basic-materials`, `food-beverage` | from `/v2/subsectors/` |
| `industry` | string | e.g. `oil-gas`, `electrical`, `chemicals` | from `/v2/industries/` |
| `sub_industry` | string | e.g. `coal-production`, `gold`, `healthcare-providers` | from `/v2/subindustries/` |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/free-float/?sub_sector=banks" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/free-float/",
    headers={"Authorization": "<api-key>"},
    params={"sub_sector": "banks"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "symbol": "PADI.JK", "company_name": "Minna Padi Investama Sekuritas Tbk", "free_float": 0.999 }
]
```

- **Gotchas**
  - Filter parameters are mutually exclusive. Passing more than one → 400.
  - Free float is the `share_percentage` of the **Public** entry in the company's major-shareholders list (definition may differ from regulators).
  - Costs **1 credit per 100 companies returned, rounded up**.

---

### `GET /v2/companies/list_companies_with_segments/`

- **Purpose:** Lists every company that has revenue/cost segment data, with the available financial years. Use before `/v2/company/segments/{symbol}/{year}/`.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/companies/list_companies_with_segments/" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/companies/list_companies_with_segments/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
years_by_symbol = r.json()  # e.g. {"BBCA.JK": {"financial_year": [2022, 2023, 2024, 2025]}, ...}
```

- **Sample response (truncated)**

```json
{
  "BBCA.JK": { "financial_year": [2022, 2023, 2024, 2025] },
  "BBRI.JK": { "financial_year": [2022, 2023, 2024, 2025] },
  "BMRI.JK": { "financial_year": [2022, 2023, 2024, 2025] },
  "TLKM.JK": { "financial_year": [2022, 2023, 2024] }
}
```

- **Gotchas**
  - Dictionary keyed by **uppercase symbol with `.JK` suffix** (e.g. `BBCA.JK`).
  - Each value is `{financial_year: [int, ...]}`. Years are integers (no quotes).
  - Companies without segment data are **omitted** (not present with empty array).
  - Costs 1 credit.

---

### `GET /v2/companies/quarterly-financial-dates/`

- **Purpose:** Universe feed of the **latest** available quarterly report date per company. Built for freshness polling.

- **Query parameters**

| Name | Type | Default | Range / format | Notes |
|---|---|---|---|---|
| `since` | string (date) | — | `YYYY-MM-DD` | Return only companies whose latest quarter-end date is ≥ this date. Future date → empty result. |
| `year` | int | — | 1900–2026 | Restrict to quarters within the calendar year; returns each company's latest quarter inside it. |
| `limit` | int | 20 | 1–30 | Max page size. |
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
  "results": [
    { "symbol": "AADI.JK", "date": "2026-03-31", "quarter": "q1" }
  ],
  "pagination": {
    "total_count": 959, "showing": 1, "limit": 30, "offset": 0,
    "has_next": true, "has_previous": false,
    "next_offset": 30, "previous_offset": null
  }
}
```

- **Gotchas**
  - Sorted by symbol. Companies with no quarterly data are omitted (~950 rows in the universe).
  - `since` must be `YYYY-MM-DD` else 400 "Use a valid date format of YYYY-MM-DD".
  - `year` must be a valid year else 400 "Please provide a valid year".
  - **Cost:** 1 credit per page. Full sweep at `limit=30` ≈ 32 pages ≈ 32 credits. Use `since` for repeat runs to stay near 1 credit.

---

### `GET /v2/company/get_quarterly_financial_dates/{symbol}/`

- **Purpose:** All available quarterly report dates for one symbol, grouped by year.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk` (case-insensitive). E.g. `ASII`, `BBCA`, `BMRI`. |

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
{
  "2026": [["2026-03-31", "q1"]]
}
```

- **Gotchas**
  - Output keys are **string years** (`"2026"` not `2026`).
  - Values are `[report_date, quarter_label]` tuples; quarter is `q1`..`q4`.
  - 404 "Invalid stock symbol or data does not exist" → billed 1 credit (lookup ran).
  - Use the returned `report_date` strings as inputs to `report_date=` on the Quarterly Financials endpoint.
  - Prefer `/v2/companies/quarterly-financial-dates/?since=...` over per-symbol calls when polling the whole universe.

---

### `GET /v2/subsectors/`

- **Purpose:** Discovery for `sector`/`sub_sector` parameters across the screener, sector report, and free float endpoints.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/subsectors/" -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/subsectors/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
sectors = r.json()  # [{"sector": "...", "subsector": "..."}]
```

- **Sample response**

```json
[
  { "sector": "transportation-logistic", "subsector": "transportation" }
]
```

- **Gotchas**
  - Both `sector` and `subsector` are kebab-case slugs. Don't guess — call this first.
  - Costs 1 credit.

---

### `GET /v2/industries/`

- **Purpose:** Discovery for the `industry` parameter (subsector → industry pairs).

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/industries/" -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/industries/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "subsector": "investment-service", "industry": "investment-services" }
]
```

- **Gotchas**
  - Costs 1 credit.

---

### `GET /v2/subindustries/`

- **Purpose:** Discovery for the `sub_industry` parameter (industry → sub-industry pairs).

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/subindustries/" -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/subindustries/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
[
  { "industry": "metals-minerals", "sub_industry": "diversified-metals-minerals" }
]
```

- **Gotchas**
  - Costs 1 credit.

---

## Cross-reference

- The Companies Screener is the **workhorse endpoint** for almost every IDX agent workflow. Universe feeds (`/v2/companies/quarterly-financial-dates/`, `/v2/transaction/close/{date}/`) are cheaper than per-symbol loops.
- For deeper per-company data, see `idx-company.md` and `idx-financials-transactions.md`.
- For universe-wide sector reports, see the Subsector Report under detailed reports (lane 2 territory).