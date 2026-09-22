# Mining (Indonesia) — Commodities & Trade

> **Lane 1 — IDX + Mining ONLY.** Sectors Financial API v2 reference for
> Indonesian mining commodity price history, export destinations, global
> production data, sales destinations, and total national production.
> Source docs: `https://docs.sectors.app/api-references/v2/mining/commodities-trade/...`
> (verified 29 Aug 2026).

All endpoints live under `https://api.sectors.app/v2/mining/`. Auth is a raw API key in the `Authorization` header (no `Bearer ` prefix).

> **Mining commodity enum** (varies by endpoint): `Coal`, `Gold`, `Nickel`, `Copper`, `Bauxite`, `Silver`, `Cobalt`, `Tin`, `Iron`, `Sand, Stone, Gravel`, `Non-Metallic Mineral`. The exact enum differs per endpoint — see each section.
>
> **Currency**: USD (USD per ton for prices, USD millions for financials, USD for totals). Volume units per row (`Mt`, `Kg`, `ton`).

> **Important coverage note (from docs)**: "Most commodities only have data in the price table. Cross-table data (production, exports, reserves, sites) is limited to: **Coal**, **Gold**, **Nickel**, **Copper** — and partially Silver, Cobalt, Bauxite."

---

### `GET /v2/mining/commodities/` — List Commodities

- **Purpose:** Lists all commodities available in the price database with coverage metadata. Discovery endpoint for [`/v2/mining/commodities/{commodity_name}/price/`](#get-v2miningcommoditiescommodity_nameprice--commodity-price-history).
- **Hackathon applicability:** **all tracks** — use as discovery before commodity calls.

#### Query parameters

None.

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/commodities/" -H "Authorization: <api-key>"
```

#### Sample response

```json
[
  { "name": "Gold", "data_points": 703, "earliest_date": "1968-01-01", "latest_date": "2026-07-01" }
]
```

#### Gotchas

- **Costs 1 credit.** Cache.
- `data_points` is the number of monthly price observations available — useful for "is there enough data to backtest?" checks.

---

### `GET /v2/mining/commodities/{commodity_name}/price/` — Commodity Price History

- **Purpose:** Historical price data for one commodity by year range. Data is monthly (bi-weekly for recent Coal entries). **Maximum range: 3 years.**
- **Hackathon applicability:** **market-intel** (commodity dashboards), **automation** (commodity price alerts).

#### Path + query parameters

| Name | Type | Default | Notes |
|---|---|---|---|
| `commodity_name` | path | required | E.g. `Gold`, `Coal`. Get valid values from [`/v2/mining/commodities/`](#get-v2miningcommodities--list-commodities). |
| `start_year` | integer | current year − 2 | 1900–2026. |
| `end_year` | integer | current year | 1900–2026. Inclusive. **Max 3-year range.** |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/commodities/coal/price/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "start_year=2022" \
  --data-urlencode "end_year=2024"
```

#### Sample response

```json
[
  { "name": "Coal", "date": "2024-01-01", "price_usd_per_ton": 125.85 }
]
```

#### Errors

- `400 Invalid commodity 'Golda'. Valid values: Coal, Copper, Gold.` (or whichever commodities are available at the time).
- `400` for date range > 3 years.
- `404 No price data for this commodity in the specified range.`

#### Gotchas

- **Costs 1 credit** per call.
- Prices are **USD per metric ton** (`price_usd_per_ton`) — uniform unit across commodities per docs.
- Coal has bi-weekly updates for recent data; other commodities are monthly.
- Commodity names are case-sensitive on path. Use `coal`, `gold`, `copper`, `nickel` (per OpenAPI examples) — capitalised names also work per the API.

---

### `GET /v2/mining/exports/` — Top Export Destinations

- **Purpose:** Ranks countries by total export value for a given year and commodity, showing top destinations for Indonesian commodity exports.
- **Available commodity_type**: `Coal`, `Copper`, `Gold`.
- **Hackathon applicability:** **market-intel** (trade-flow dashboards), **ai-agents** (demand-side analysis).

#### Query parameters

| Name | Type | Notes |
|---|---|---|
| `commodity_type` | enum | **Required.** `Coal`, `Copper`, `Gold`. |
| `year` | integer | **Required.** 1900–2026. |
| `limit` | integer | 1–30, max 30. Default 20. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/exports/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=coal" \
  --data-urlencode "year=2024" \
  --data-urlencode "limit=30"
```

#### Sample response

```json
[
  { "country": "China", "export_usd": 6553700000,
    "export_volume_bps": 93.1649, "export_volume_esdm": null, "volume_unit": "Mt" }
]
```

#### Field glossary

| Field | Meaning |
|---|---|
| `export_usd` | Total export value in USD. |
| `export_volume_bps` | Volume per **BPS** (Badan Pusat Statistik / Statistics Indonesia). |
| `export_volume_esdm` | Volume per **ESDM** (Kementerian Energi dan Sumber Daya Mineral / Ministry of Energy & Mineral Resources). Often `null`. |
| `volume_unit` | Per-row unit. Typically `Mt` for coal. |

#### Gotchas

- **Costs 1 credit.**
- **Two volume sources** may differ — pick BPS as the default (Statistics Indonesia is the canonical authority).
- Only 3 commodities available (Coal/Copper/Gold). For Nickel/Bauxite, no export data via this endpoint.

---

### `GET /v2/mining/global-commodity/` — Global Commodity Data

- **Purpose:** Global commodity data: production, reserves, and trade information. At least one of `commodity_type` or `country` is required.
- **Available commodity_type**: `Coal`, `Gold`, `Nickel`, `Copper`, `Bauxite`.
- **Hackathon applicability:** **market-intel** (global benchmarking), **ai-agents** ("how does Indonesia rank?").

#### Query parameters

| Name | Type | Notes |
|---|---|---|
| `commodity_type` | enum | `Bauxite`, `Coal`, `Copper`, `Gold`, `Nickel`. Required if `country` not provided. |
| `country` | string | Exact match (e.g. `Australia`). Required if `commodity_type` not provided. |
| `limit` | integer | 1–30, max 30. Default 20. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/global-commodity/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=coal"
```

#### Sample response

```json
[
  { "country": "Albania", "commodity_type": "Coal",
    "resources_reserves": null, "resources_reserves_share": null,
    "resources_reserves_unit": null,
    "export_import_usd": { "2023": { "export": null, "import": null } },
    "production_volume": null, "production_share": null,
    "production_volume_unit": null }
]
```

#### Gotchas

- **Costs 1 credit.**
- Many fields can be `null` — countries don't always have all data filled in.
- Use `country=Indonesia` to see how Indonesia compares for a specific commodity.
- Output is year-keyed nested dicts (`production_volume: {year: value}`, `production_share: {year: percent}`).

---

### `GET /v2/mining/sales-destination/{slug}/` — Company Sales Destinations

- **Purpose:** Sales destination breakdown for a specific mining company by its slug — revenue and volume distribution by country for a specific year.
- **Hackathon applicability:** **market-intel** (per-company export exposure), **ai-agents** (customer concentration analysis).

#### Path + query parameters

| Name | Type | Default | Notes |
|---|---|---|---|
| `slug` | path | required | Company slug. E.g. `pt-adaro-andalan-indonesia-tbk`. |
| `year` | integer | latest available | 1900–2026. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/sales-destination/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "year=2024"
```

#### Sample response

```json
{
  "year": 2024,
  "data": {
    "China": {
      "revenue_usd": null,
      "percentage_of_total_revenue": null,
      "volume": null,
      "percentage_of_sales_volume": 16,
      "commodity_type": "Coal",
      "unit": "Mt"
    }
  }
}
```

#### Gotchas

- **Costs 1 credit.**
- `data` is keyed by country name (string → object).
- `revenue_usd` and `volume` are often `null` — only `percentage_*` is reliably populated. Use this for concentration % rather than absolute numbers.
- Complements the country-level [`/v2/mining/exports/`](#get-v2miningexports--top-export-destinations) view.

---

### `GET /v2/mining/total-production/` — Total Commodity Production

- **Purpose:** Total national production for a commodity across all years, with year-over-year percentage change. Results ordered by year descending.
- **Available commodity_type**: `Coal`, `Nickel`, `Gold`, `Copper`.
- **Hackathon applicability:** **market-intel** (national output trends), **automation** (supply-side alerts).

#### Query parameters

| Name | Type | Notes |
|---|---|---|
| `commodity_type` | enum | **Required.** `Coal`, `Copper`, `Gold`, `Nickel`. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/total-production/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=coal"
```

#### Sample response

```json
[
  { "year": 2024, "production_volume": 836.1,
    "prev_year_volume": 775.2, "unit": "Mt", "yoy_change_percent": 7.86 }
]
```

#### Field glossary

| Field | Meaning |
|---|---|
| `production_volume` | National total for the year. |
| `prev_year_volume` | Same for previous year (or `null` if first observation). |
| `unit` | Per-row. `Mt` for coal, `Kg` for gold/copper usually. |
| `yoy_change_percent` | Year-over-year change (%). E.g. `7.86` = +7.86%. |

#### Gotchas

- **Costs 1 credit** per call.
- Sorted by `year` descending (most recent first).
- Useful for trend analysis — pair with [`/v2/mining/commodities/{name}/price/`](#get-v2miningcommoditiescommodity_nameprice--commodity-price-history) for revenue estimation.

---

## Cross-references

- TOC anchor: [`sectors-api-and-mcp.md`](../sectors-api-and-mcp.md)
- Mining companies: [`mining-companies.md`](./mining-companies.md)
- Sites, resources, licenses, auctions: [`mining-sites-licenses.md`](./mining-sites-licenses.md)
- IDX endpoints: [`idx-*.md`](./)
