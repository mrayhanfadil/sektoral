# IDX Per-Company Reports — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. IDX ticker = 4-letter code, optionally `.JK`.

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/company/report/{symbol}/` | Full company report (8 selectable sections) |
| `GET /v2/company/get-segments/{symbol}/` | Revenue/cost segments for one company/year (Sankey-ready) |
| `GET /v2/company/corporate-actions/{symbol}/` | Splits, rights, warrants, bonus, AGM, dividend history |
| `GET /v2/company/shareholders-composition/{symbol}/` | Local vs foreign monthly composition |
| `GET /v2/listing-performance/{symbol}/` | IPO listing performance since listing date |

> Path corrections vs the high-level `sectors-api-and-mcp.md` index:
> - `segments` lives at `/v2/company/get-segments/{symbol}/` (the doc page title says "Company Revenue Segments"). The `financial_year` is a **query** parameter, not a path segment.
> - `listing-performance` lives at `/v2/listing-performance/{symbol}/` (NOT under `/v2/ipo/`).

---

### `GET /v2/company/report/{symbol}/`

- **Purpose:** Full company report organized into 8 selectable sections. Pass `sections=` to fetch only the parts you need (saves credits).

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk` (case-insensitive). E.g. `BREN`, `BBCA`, `TLKM`. |

- **Query parameters**

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `sections` | array of strings | `overview`, `valuation`, `future`, `peers`, `financials`, `dividend`, `management`, `ownership` | Comma-separated. Defaults to all 8. Unknown value → 400 (free). |

- **Sections (what each contains)**

| Section | Content |
|---|---|
| `overview` | Listing board, industry, sector, market cap, price, ESG, tags, indices, affiliates, all-time high/low, YTD/52w/90d range |
| `valuation` | Last close, forward PE, intrinsic value, historical PB/PE/PS/PCF/PEG per year, peer-avg comparisons |
| `future` | Analyst consensus EPS / revenue forecasts, EPS/revenue growth forecasts, rating breakdown (strong_buy/buy/hold/sell/strong_sell) |
| `financials` | EPS, historical EPS, historical financials (revenue, earnings, total_assets, total_equity, total_liabilities, banking-specific fields), YoY growth |
| `dividend` | Historical/upcoming dividends, yield TTM, avg yield, payout ratio, last ex-dividend date |
| `management` | Key executives (`name`, `position`), executives' shareholdings (`share_amount`, `share_percentage`) |
| `ownership` | Major shareholders, top transactions, institutional transaction flow, whale investors, conglomerates group |
| `peers` | Peer companies in the same subsector with comparison fields (pe_ttm, pb_mrq, market_cap, total_assets, etc.) |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/company/report/BBCA/?sections=overview,valuation,financials" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/company/report/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"sections": "overview,valuation,financials"},
    timeout=30,
)
r.raise_for_status()
report = r.json()
```

- **Sample response (truncated, BBCA with `sections=overview,valuation`)**

```json
{
  "symbol": "BBCA.JK",
  "company_name": "PT Bank Central Asia Tbk.",
  "overview": {
    "listing_board": "Main",
    "industry": "Banks",
    "sub_industry": "Banks",
    "sector": "Financials",
    "sub_sector": "Banks",
    "market_cap": 753611199412500,
    "market_cap_rank": 1,
    "employee_num": 27937,
    "listing_date": "2000-05-31",
    "last_close_price": 6175,
    "latest_close_date": "2026-07-08",
    "daily_close_change": -0.0198412698412698,
    "esg_score": 21.44,
    "tags": ["dividend-yield-ttm-above-5-percent", "esg-under-25", "top-90d-transaction-value"],
    "indices": ["IDXESGL", "ECONOMIC30", "IDX30", "LQ45", "FTSE", "KOMPAS100", "IDXHIDIV20"],
    "affiliates": ["Djarum", "Hartono"]
  },
  "valuation": {
    "last_close_price": 6175,
    "forward_pe": 12.7984576757419,
    "intrinsic_value": 13694,
    "historical_valuation": [
      { "year": 2022, "pb": 4.7177, "pe": 25.6154, "ps": 11.9285, "pcf": 30.8908, "peg": 0.8643, "pb_peer_avg": 0.9759, "pe_peer_avg": 15.1293, "ps_peer_avg": 4.4186 }
    ]
  }
}
```

- **Gotchas**
  - **Costs 1 credit per requested section** — full report = 8 credits. Always pass `sections=` if you don't need everything.
  - `sections` accepts a comma-separated string (not repeated query keys). Both Python `params=` and curl `--data-urlencode sections=overview,valuation` work.
  - `symbol` accepts lowercase (`bbca.jk`), uppercase (`BBCA`), or bare 4-letter (`BBCA`).
  - 404 "Given stock symbol does not exist" → 1 credit (lookup ran).
  - Banking companies include extra fields (`net_interest_income`, `gross_loan`, `total_deposit`, etc.) inside `financials.historical_financials[]`. Insurance companies include `premium_income`, `net_premium_income`, `premium_expense`.

---

### `GET /v2/company/get-segments/{symbol}/`

- **Purpose:** Sankey-graph-ready revenue (and cost) segment breakdown for one company / one financial year.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. Not all companies have segment data — call `/v2/companies/list_companies_with_segments/` first. |

- **Query parameters**

| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| `financial_year` | int | latest available year | 1900–2026 | If omitted, defaults to the latest available year for the symbol. Bad year → 400 (free). |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/company/get-segments/BBCA/?financial_year=2025" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/company/get-segments/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"financial_year": 2025},
    timeout=30,
)
r.raise_for_status()
nodes = r.json()["revenue_breakdown"]
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "financial_year": 2025,
  "revenue_breakdown": [
    { "value": 67446394000000, "source": "Loans", "target": "Interest Income" }
  ]
}
```

- **Gotchas**
  - Response only includes `revenue_breakdown` items as `{value, source, target}` tuples — ready to feed directly into a Sankey diagram (e.g. Plotly `go.Sankey(link=..., node=...)`).
  - Costs 1 credit.
  - 404 "Invalid stock symbol and/or data for the specified financial year does not exist" → 1 credit.
  - The `financial_year` is a query parameter; passing it as a path segment (`/v2/company/segments/BBCA/2025/`) returns 404 — that's the **wrong path**.
  - Use the helper list (`/v2/companies/list_companies_with_segments/`) to know which `(symbol, year)` pairs return data before calling.

---

### `GET /v2/company/corporate-actions/{symbol}/`

- **Purpose:** Full corporate-action history for one company: stock splits, rights, warrants, bonus, AGM events, dividends paid, upcoming dividends.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. E.g. `BBCA`, `BMRI`. |

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/company/corporate-actions/BBCA/" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/company/corporate-actions/BBCA/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "corporate_actions": {
    "agm": [
      {
        "agm_date": "2025-03-12",
        "agm_time": "09:30:00",
        "agm_place": "Menara Bca, Grand Indonesia, Jl. M. H. Thamrin No. 1, Jakarta 10310",
        "agm_result": null
      }
    ],
    "bonus": null,
    "warrant": null,
    "dividend": [
      {
        "ex_date": "2025-12-03",
        "payment_date": "2025-12-22",
        "dividend_yield": 0.00641717,
        "dividend_amount": 55
      }
    ],
    "right_issue": null,
    "stock_split": [
      { "date": "2021-10-13", "split_ratio": 5 }
    ],
    "upcoming_dividend": null
  }
}
```

- **Gotchas**
  - All 7 action keys are **always present** (`agm`, `bonus`, `warrant`, `dividend`, `upcoming_dividend`, `right_issue`, `stock_split`). Empty types are `null`.
  - `split_ratio` is a multiplier (e.g. `5` = 5-for-1 split).
  - Costs 1 credit. 404 "No data found for symbol 'XYZA'" → 1 credit.

---

### `GET /v2/company/shareholders-composition/{symbol}/`

- **Purpose:** Monthly shareholder-composition snapshots for one symbol in a single calendar year. Categorized by investor type × local/foreign.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. E.g. `BBCA`, `BMRI`. |

- **Query parameters**

| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| `year` | int | current year | 1900–2026 | Calendar year of snapshots. Data available **from 2021 onwards** — earlier years return an empty `data` array. Future years are rejected. |

- **Investor categories returned** (per row, both `_l` = local and `_f` = foreign): `insurance`, `corporate`, `pension_fund`, `financial_institutions`, `individual`, `mutual_fund`, `securities_companies`, `foundation`, `other`, plus `total_l` and `total_f`. Aggregate fields: `shares_number`, `numbers_of_shareholders`, `change_in_shareholders`.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/company/shareholders-composition/BBCA/?year=2025" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/company/shareholders-composition/BBCA/",
    headers={"Authorization": "<api-key>"},
    params={"year": 2025},
    timeout=30,
)
r.raise_for_status()
rows = r.json()["data"]  # one per month
```

- **Sample response**

```json
{
  "symbol": "BBCA.JK",
  "year": 2026,
  "data": [
    {
      "date": "2026-06-30",
      "shares_number": 123275050000,
      "insurance_l": 2347930190,
      "corporate_l": 676811585,
      "pension_fund_l": 326033400,
      "financial_institutions_l": 437363600,
      "individual_l": 11100401696,
      "mutual_fund_l": 1218211444,
      "securities_companies_l": 109436679,
      "foundation_l": 73544460,
      "other_l": 14203600,
      "total_l": 16303936654,
      "insurance_f": 551962796,
      "corporate_f": 1223361552,
      "pension_fund_f": 5139363015,
      "financial_institutions_f": 2811510529,
      "individual_f": 326180480,
      "mutual_fund_f": 19268413209,
      "securities_companies_f": 558727363,
      "foundation_f": 298788705,
      "other_f": 5971446817,
      "total_f": 36149754466,
      "numbers_of_shareholders": 797115,
      "change_in_shareholders": 29745
    }
  ]
}
```

- **Gotchas**
  - All count fields are integers in **shares**, not IDR.
  - "Available from 2021 onwards" — earlier years return 200 with `data: []`.
  - Future years → 400.
  - Costs 1 credit. 404 "Symbol 'XYZA.JK' not found in shareholders composition data" → 1 credit.

---

### `GET /v2/listing-performance/{symbol}/`

- **Purpose:** Price change percentages since listing date across 7/30/90/365-day windows, plus IPO book-building details.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | IDX symbol, 4 letters, optionally `.jk`. Listing data only exists for tickers listed **after May 2005**. |

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/listing-performance/BREN/" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/listing-performance/BREN/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "symbol": "BREN.JK",
  "company_name": "PT Barito Renewables Energy Tbk.",
  "chg_7d": 2.52564,
  "chg_30d": 4.64103,
  "chg_90d": 8.26282,
  "chg_365d": 7.58974,
  "listing_date": null,
  "shares_offered": 4015000000,
  "percent_total_shares": 0.03,
  "book_building_start_date": "2023-09-18",
  "book_building_end_date": "2023-09-25",
  "book_building_lower_bound": 670,
  "book_building_upper_bound": 780,
  "offering_start_date": "2023-10-03",
  "offering_end_date": "2023-10-05",
  "offering_price": 780,
  "distribution_date": "2023-10-06",
  "prospectus_url": "https://e-ipo.co.id/en/pipeline/get-prospectus-file?id=266&type=",
  "additional_info_url": "https://e-ipo.co.id/en/pipeline/get-additional-info?id=266"
}
```

- **Gotchas**
  - **All price-change fields and IPO metadata fields are returned as `null` when missing** (not absent). The schema marks every key as required.
  - `chg_*` are **multipliers** (decimals): `2.52564` ≈ +252.564% from listing at day 7.
  - Path is `/v2/listing-performance/{symbol}/` — NOT `/v2/ipo/listing-performance/...`.
  - Listing data only available for tickers listed **after May 2005**.
  - Costs 1 credit. 404 "Given stock symbol does not exist for this data" → 1 credit.

---

## Cross-reference

- The `sections=` parameter on `/v2/company/report/{symbol}/` is the biggest credit-saver on this surface — prefer 2–3 sections per agent turn over the full 8-section report.
- `shareholders-composition` is the cleanest source for local-vs-foreign ownership trend over time; pair with `/v2/brokers/foreign-flow/{symbol}/` for daily foreign-flow.
- `corporate-actions.upcoming_dividend` is the place to watch for not-yet-paid dividend announcements (vs `dividend` = historical).
- See `idx-screener.md` for universe feeds that drive these per-symbol endpoints.