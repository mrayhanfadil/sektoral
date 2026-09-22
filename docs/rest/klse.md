# KLSE (Bursa Malaysia) — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. KLSE ticker = **4-digit numeric** code (`1155`, `4197`, `5225`).

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/klse/sectors/` | Discovery — valid KLSE sector slugs |
| `GET /v2/klse/companies/` | All KLSE companies in one sector (symbol + company_name) |
| `GET /v2/klse/companies/top/` | Top KLSE by dividend_yield/revenue/earnings/market_cap/pe |
| `GET /v2/klse/company/report/{symbol}/` | Full KLSE company report (4 selectable sections) |

> KLSE coverage is the **thinnest** of the three stock exchanges in Sectors (IDX → SGX → KLSE). There is **no daily price endpoint, no filings endpoint, no news endpoint, no broker endpoint, and no quarterly financials endpoint** — only discovery + top rankings + company reports.

---

### `GET /v2/klse/sectors/`

- **Purpose:** Discovery — flat array of valid KLSE sector slugs.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/klse/sectors/" -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/klse/sectors/",
    headers={"Authorization": "<api-key>"}, timeout=30,
)
r.raise_for_status()
sectors = r.json()  # ["consumer-non-cyclicals", ...]
```

- **Sample response**

```json
["consumer-non-cyclicals"]
```

- **Gotchas**
  - Costs 1 credit.
  - Cache once — the list is small and rarely changes.
  - Returns a bare array (not wrapped in `{}`).

---

### `GET /v2/klse/companies/`

- **Purpose:** All KLSE-listed companies in one sector, as `{symbol, company_name}` pairs.

- **Query parameters**

| Name | Type | Required | Allowed / format | Notes |
|---|---|---|---|---|
| `sector` | string | yes | kebab-case slug from `/v2/klse/sectors/`, e.g. `financials`, `healthcare`, `consumer-cyclicals` | Bad value → 400 "The requested sector does not exist." |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/klse/companies/?sector=financials" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/klse/companies/",
    headers={"Authorization": "<api-key>"},
    params={"sector": "financials"},
    timeout=30,
)
r.raise_for_status()
symbols = [c["symbol"] for c in r.json()]
```

- **Sample response**

```json
[
  { "symbol": "0053", "company_name": "OSK Ventures International Berhad" }
]
```

- **Gotchas**
  - Costs 1 credit.
  - **`sector` is REQUIRED** — bare `GET /v2/klse/companies/` returns 400.
  - This is the cheapest way to enumerate KLSE tickers; there's no NL or `where=` screener like IDX/SGX have.

---

### `GET /v2/klse/companies/top/`

- **Purpose:** Top KLSE companies ranked by 1+ classifications (dividend_yield/revenue/earnings/market_cap/pe).

- **Query parameters**

| Name | Type | Default | Allowed / range | Notes |
|---|---|---|---|---|
| `classifications` | array | all 5 | `dividend_yield`, `revenue`, `earnings`, `market_cap`, `pe` | Comma-separated. Bad value → 400. |
| `n_stock` | int | 5 | 1–10 | Per-classification list length. |
| `sector` | string | all | kebab-case slug | Filter to one sector. |
| `min_mcap_million` | int | 1000 | ≥0 | Min market cap in **million MYR**. |

- **Cost:** 1 credit per classification. Defaults (5) = 5 credits.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/klse/companies/top/?classifications=dividend_yield,market_cap&n_stock=10" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/klse/companies/top/",
    headers={"Authorization": "<api-key>"},
    params={"classifications": "dividend_yield,market_cap", "n_stock": 10},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response (truncated — dividend_yield and pe can be empty if no companies meet the floor)**

```json
{
  "dividend_yield": [],
  "revenue": [
    { "symbol": "4197", "revenue": 70515000000, "company_name": "Sime Darby Berhad" }
  ],
  "earnings": [
    { "symbol": "5099", "earnings": 12372463000, "company_name": "Capital A Berhad" }
  ],
  "market_cap": [
    { "symbol": "1155", "market_cap": 132322770944, "company_name": "Malayan Banking Berhad" }
  ],
  "pe": []
}
```

- **Gotchas**
  - Default `min_mcap_million=1000` = 1B MYR floor. Set `=0` to include small-caps. (Note: with the default floor, `dividend_yield` and `pe` may come back empty for some calls.)
  - All money fields are in **MYR**.
  - Numeric revenue/earnings are `double` (no integer IDR/SGD guarantee).
  - Empty classifications return as empty arrays, not 404.

---

### `GET /v2/klse/company/report/{symbol}/`

- **Purpose:** Full KLSE company report organized into 4 selectable sections.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `symbol` | string | **4-digit numeric** code. E.g. `1155`, `4197`, `5225`. |

- **Query parameters**

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `sections` | array of strings | `overview`, `valuation`, `financials`, `dividend` | Comma-separated. Defaults to all 4. |

- **Sections (what each contains)**

| Section | Content |
|---|---|
| `overview` | `market_cap`, `volume`, `employee_num`, `sector`, `sub_sector`, `change_{1d,7d,1m,1y,3y,ytd}` |
| `valuation` | `pe`, `beta`, `ps`, `pcf`, `pb` |
| `financials` | `historical_revenue[YYYY]` + `historical_earnings[YYYY]` + `TTM` line, `eps`, `gross_margin`, `operating_margin`, `net_profit_margin`, `quick_ratio`, `current_ratio`, `debt_to_equity` |
| `dividend` | `dividend_yield_5y_avg`, `dividend_growth_rate`, `payout_ratio`, `forward_dividend`, `forward_dividend_yield`, `dividend_ttm` |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/klse/company/report/1155/?sections=overview,valuation" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/klse/company/report/1155/",
    headers={"Authorization": "<api-key>"},
    params={"sections": "overview,valuation"},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response (truncated, Maybank 1155)**

```json
{
  "symbol": "1155",
  "name": "Malayan Banking Berhad",
  "overview": {
    "market_cap": 132322770944,
    "volume": 0,
    "employee_num": null,
    "sector": "Financials", "sub_sector": "Banks",
    "change_1d": -0.00183, "change_7d": 0.0130,
    "change_1m": 0.0206, "change_1y": 0.1916,
    "change_3y": 0.5093, "change_ytd": 0.0761
  },
  "valuation": { "pe": 12.72, "beta": 0.121, "ps": 4.64, "pcf": 35.71, "pb": 1.46 }
}
```

- **Gotchas**
  - **Costs 1 credit per section.** Defaults = 4 credits.
  - All money fields in **MYR**.
  - 404 "Given KLSE symbol does not exist" → 1 credit.
  - `historical_revenue`/`historical_earnings` include a `TTM` (trailing twelve months) entry — useful for "as of last quarter" comparisons.

---

## Cross-reference

- KLSE has **no daily price, no filings, no news, no broker, no quarterly financials** endpoints. If your use case needs those for Malaysia, look at the underlying Bursa Malaysia site or a paid Bursa API.
- The four endpoints you do get are sufficient for a "KLSE top-performers dashboard" — combine `/v2/klse/sectors/` → `/v2/klse/companies/?sector=...` → `/v2/klse/company/report/{symbol}/` for a full drill-down.
- Default market-cap floor (1B MYR) is **higher** than IDX's 5T IDR floor relative to typical exchange size — for KLSE small/mid-cap coverage, set `min_mcap_million=0` explicitly.
- See `idx-*.md` for IDX (full coverage), `sgx.md` for SGX (annual-only fundamentals), and `mining.md` for Indonesian mining.