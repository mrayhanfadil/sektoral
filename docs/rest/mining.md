# Indonesian Mining — REST API reference

> Source: https://docs.sectors.app/llms.txt (extracted 29 Aug 2026).
> All endpoints require `Authorization: <api-key>` (raw key, no `Bearer` prefix).
> Base URL: `https://api.sectors.app`. Mining uses **company slugs** (not IDX tickers) as the primary identifier — many companies are unlisted subsidiaries.

## Endpoints in this file

| Endpoint | Used for |
|---|---|
| `GET /v2/mining/companies/` | List mining companies (filter by commodity, company type, keyword) |
| `GET /v2/mining/companies/{slug}/` | Mining company detail (licenses, contracts, site count) |
| `GET /v2/mining/companies/financials/{slug}/` | Annual financials (USD millions) |
| `GET /v2/mining/companies/ownership/{slug}/` | Corporate ownership tree (parents + subsidiaries) |
| `GET /v2/mining/companies/performance/{slug}/` | Production volume, sales, strip ratio, resources/reserves |
| `GET /v2/mining/commodities/` | Discovery — commodities in the price database |
| `GET /v2/mining/commodities/{commodity_name}/price/` | Monthly price history (max 3-year range) |
| `GET /v2/mining/exports/` | Top export destinations by country for a commodity |
| `GET /v2/mining/global-commodity/` | Global production/reserves/trade per country |
| `GET /v2/mining/sales-destination/{slug}/` | Company sales by destination country |
| `GET /v2/mining/resources-reserves/` | Province × commodity × year coverage index |
| `GET /v2/mining/resources-reserves/{province}/` | Province resources & reserves detail |
| `GET /v2/mining/sites/` | List mining sites with advanced filters |
| `GET /v2/mining/sites/{slug}/` | Mining site detail with lat/long |
| `GET /v2/mining/total-production/` | National annual production for one commodity |
| `GET /v2/mining/licenses/` | Mining licenses (IUP/IUPK) from ESDM Minerba portal |
| `GET /v2/mining/license-auctions/` | License auctions list |
| `GET /v2/mining/license-auctions/{wiup_code}/` | License auction detail with phases + participants |
| `GET /v2/mining/contracts/` | Active mining contracts (mine owner ↔ contractor) |

> Mining endpoints are all under `/v2/mining/...` (no transaction/region subpath). Note: the **commodity universe is partial** — only Coal, Gold, Nickel, Copper have full cross-table coverage (production, exports, reserves, sites, prices). Silver/Cobalt/Bauxite are partial.

---

### `GET /v2/mining/companies/`

- **Purpose:** List mining companies. Filterable by commodity, company type, and a free-text keyword search.

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `keyword` | string | — | substring | Searches name, IDX symbol, slug, and key operations (case-insensitive). |
| `commodity_type` | string | — | `Aluminium`, `Coal`, `Copper`, `Gold`, `Nickel`, `Silver`, `Zinc and Lead` | Case-insensitive. |
| `company_type` | string | — | `Consultant`, `Contractor`, `Holding`, `Manufacturer`, `Mine Owner`, `Trader` | Case-insensitive. |
| `has_financials` | bool | false | true/false | Restrict to companies with financial data. |
| `limit` | int | 20 | 1–30 | Page size. |
| `offset` | int | 0 | ≥0 | Pagination offset. |

- **Cost:** 1 credit per page.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/companies/?commodity_type=Coal&company_type=Mine+Owner&limit=20" \
  -H "Authorization: <api-key>"
```

```python
r = requests.get(
    "https://api.sectors.app/v2/mining/companies/",
    headers={"Authorization": "<api-key>"},
    params={"commodity_type": "Coal", "company_type": "Mine Owner", "limit": 20},
    timeout=30,
)
r.raise_for_status()
```

- **Sample response**

```json
{
  "results": [
    {
      "slug": "asia-pacific-nickel-pty-ltd",
      "name": "Asia Pacific Nickel Pty Ltd",
      "symbol": null,
      "company_type": "Holding",
      "key_operation": "Investment",
      "commodity_type": ["Nickel"]
    }
  ],
  "pagination": { "total_count": 366, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - **Total 366 companies** in the universe.
  - `symbol` is `null` for unlisted subsidiaries (most mining companies).
  - `slug` is the only stable cross-endpoint identifier — use it for `/{slug}/` detail calls.

---

### `GET /v2/mining/companies/{slug}/`

- **Purpose:** Single mining company profile — activities, commodity types, licenses, contracts, site count, address.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | URL-friendly company slug from `/v2/mining/companies/`. E.g. `pt-adaro-andalan-indonesia-tbk`. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/companies/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>"
```

- **Sample response (truncated)**

```json
{
  "name": "PT Adaro Andalan Indonesia Tbk",
  "slug": "pt-adaro-andalan-indonesia-tbk",
  "symbol": "AADI.JK",
  "company_type": "Holding",
  "operation_province": "Jakarta",
  "operation_district": "Jakarta Selatan",
  "key_operation": "Coal Trading",
  "activities": ["Trading"],
  "commodity_type": ["Coal"],
  "mining_license": [
    {
      "license_type": "IUPK", "license_number": "11/1/IUP/PMA/2022",
      "wiup_code": "1300003032014132", "province": "Kalimantan Selatan",
      "city": "Kabupaten Tabalong", "license_effective_date": "2022-09-13",
      "license_expiry_date": "2032-10-01", "activity": "Operasi Produksi",
      "licensed_area_ha": 23942, "cnc": "CNC", "generation": "GEN I",
      "location": "Kabupaten Tabalong, Kabupaten Balangan", "commodity_type": "Coal"
    }
  ],
  "mining_contract": [],
  "mining_site_count": 0
}
```

- **Gotchas**
  - `mining_site_count` is the count of sites owned by this company — fetch `/v2/mining/sites/?company=<slug>` for the actual site list.
  - 404 "Company not found. Please provide a valid company slug." → 1 credit.

---

### `GET /v2/mining/companies/financials/{slug}/`

- **Purpose:** Annual financials for one mining company (USD millions). Defaults to latest year.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Company slug. |

- **Query parameters**

| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| `year` | int | latest available | 1900–2026 | Single year. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/companies/financials/pt-adaro-andalan-indonesia-tbk/?year=2024" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "year": 2024,
  "available_years": [2023, 2024],
  "data": {
    "slug": "pt-adaro-andalan-indonesia-tbk",
    "symbol": "AADI.JK",
    "name": "PT Adaro Andalan Indonesia Tbk",
    "year": 2024,
    "assets_usd": 5993000000,
    "revenue_usd": 5320000000,
    "revenue_breakdown": {
      "coal_mining_and_trading": 5108610000,
      "logistics": 183680000,
      "others": 27290000
    },
    "cost_of_revenue_usd": 3853630000,
    "cost_of_revenue_breakdown": {
      "royalty": 1020160000,
      "freight_and_handling": 412090000,
      "logistic": 89240000
    },
    "net_profit_usd": 1327000000
  }
}
```

- **Gotchas**
  - **All monetary fields are in USD millions** — not IDR, not local.
  - Use `has_financials=true` filter on `/v2/mining/companies/` to avoid no-data slugs.
  - `available_years` is the year-list for that company — handy before drilling.

---

### `GET /v2/mining/companies/ownership/{slug}/`

- **Purpose:** Corporate ownership tree (parents + subsidiaries).

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Company slug. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/companies/ownership/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "slug": "pt-adaro-andalan-indonesia-tbk",
  "parents": [
    { "name": "PT Alamtri Resources Indonesia Tbk", "slug": "pt-alamtri-resources-indonesia-tbk", "symbol": "ADRO.JK", "percentage_ownership": 15.37 }
  ],
  "subsidiaries": [
    { "name": "PT Adaro Mining Technologies", "slug": "pt-adaro-mining-technologies", "symbol": null, "percentage_ownership": 100 }
  ]
}
```

- **Gotchas**
  - `percentage_ownership` for subsidiaries is always 100 (the parent fully owns them). For parents, it's a float — multiple parents may exist with <100% each.

---

### `GET /v2/mining/companies/performance/{slug}/`

- **Purpose:** Production volume, sales volume, strip ratio, resources/reserves for one company, one year, by commodity.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Company slug. |

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `commodity_type` | string | — | `Coal`, `Copper`, `Gold`, `Nickel`, `Silver` | Filter to one commodity. |
| `year` | int | latest | 1900–2026 | Single year. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/companies/performance/pt-adaro-andalan-indonesia-tbk/?commodity_type=Coal&year=2024" \
  -H "Authorization: <api-key>"
```

- **Sample response (truncated)**

```json
{
  "year": 2024,
  "available_years": [2019, 2020, 2021, 2022, 2023, 2024],
  "data": [
    {
      "year": 2024, "commodity_type": "Coal",
      "commodity_sub_type": "Sub-bituminous & Metallurgical Coal",
      "commodity_stats": {
        "unit": "Mt", "mining_operation_status": "production",
        "production_volume": 48.11, "sales_volume": 55.8,
        "overburden_removal_volume": 214.18, "strip_ratio": 4.51,
        "resources_reserves": {
          "probable_reserves_Mt": 356, "proven_reserves_Mt": 463,
          "total_reserves_Mt": 819,
          "inferred_resources_Mt": 640.6, "indicated_resources_Mt": 962,
          "measured_resources_Mt": 3176, "total_resources_Mt": 4374
        },
        "products": [
          {
            "product_name": "Envirocoal -North Tutupan",
            "calorific_value_kcal": { "max": 4843, "min": 4843 },
            "ash_content_adb": { "max": 2.1, "min": 2.1 },
            "total_sulphur_adb": { "max": 0.1, "min": 0.1 }
          }
        ]
      }
    }
  ]
}
```

- **Gotchas**
  - **`data[]` can be empty** if the company has no production data for the requested `commodity_type` / `year` combination.
  - Coal records carry calorific/ash/sulphur specs inside `products[]` — useful for quality-grading analysis.

---

### `GET /v2/mining/commodities/`

- **Purpose:** Discovery — list of commodities in the price database with coverage metadata.

- **Query parameters:** none.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/commodities/" -H "Authorization: <api-key>"
```

- **Sample response**

```json
[
  { "name": "Gold", "data_points": 703, "earliest_date": "1968-01-01", "latest_date": "2026-07-01" }
]
```

- **Gotchas**
  - Costs 1 credit.
  - Cross-table coverage is **limited**: Coal, Gold, Nickel, Copper (plus partial Silver/Cobalt/Bauxite) have production + exports + reserves + sites. Most commodities have price-only data.

---

### `GET /v2/mining/commodities/{commodity_name}/price/`

- **Purpose:** Historical price data for a commodity (USD/metric ton). Monthly, bi-weekly for recent Coal entries.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `commodity_name` | string | From `/v2/mining/commodities/`. Lowercase in URL is fine. |

- **Query parameters**

| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| `start_year` | int | current year − 2 | 1900–2026 | — |
| `end_year` | int | current year | 1900–2026 | Maximum 3-year range. Wider → 400. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/commodities/coal/price/?start_year=2022&end_year=2024" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
[
  { "name": "Coal", "date": "2024-01-01", "price_usd_per_ton": 125.85 }
]
```

- **Gotchas**
  - `commodity_name` in URL is **case-insensitive** (Coal, coal, COAL all work).
  - **3-year range limit is hard** — wider ranges return 400, no auto-clamp.
  - Bad commodity → 400 "Invalid commodity 'Golda'. Valid values: Coal, Copper, Gold."

---

### `GET /v2/mining/exports/`

- **Purpose:** Top destination countries for Indonesian commodity exports (one commodity, one year).

- **Query parameters**

| Name | Type | Required | Allowed | Notes |
|---|---|---|---|---|
| `commodity_type` | string | yes | `Coal`, `Copper`, `Gold` | — |
| `year` | int | yes | 1900–2026 | — |
| `limit` | int | no | 1–30 | Default 20. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/exports/?commodity_type=coal&year=2024&limit=10" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
[
  { "country": "China", "export_usd": 6553700000, "export_volume_bps": 93.1649, "export_volume_esdm": null, "volume_unit": "Mt" }
]
```

- **Gotchas**
  - `export_usd` is **base USD** (raw integer, not millions).
  - **Two volume sources** (`bps` from Badan Pusat Statistik, `esdm` from ESDM) — values may differ due to methodology. Either can be `null`.
  - Only Coal, Copper, Gold have export data — Nickel/Bauxite/Silver won't return rows even if requested.

---

### `GET /v2/mining/global-commodity/`

- **Purpose:** Global commodity data per country — production, reserves, trade.

- **Query parameters**

| Name | Type | Required | Allowed / format | Notes |
|---|---|---|---|---|
| `commodity_type` | string | yes (or `country`) | `Bauxite`, `Coal`, `Copper`, `Gold`, `Nickel` | — |
| `country` | string | yes (or `commodity_type`) | exact country name | At least one required. |
| `limit` | int | no | 1–30 | Default 20. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/global-commodity/?commodity_type=coal" \
  -H "Authorization: <api-key>"
```

- **Sample response (truncated)**

```json
[
  {
    "country": "Albania", "commodity_type": "Coal",
    "resources_reserves": null, "resources_reserves_share": null, "resources_reserves_unit": null,
    "export_import_usd": { "2023": { "export": null, "import": null } },
    "production_volume": null, "production_share": null, "production_volume_unit": null
  }
]
```

- **Gotchas**
  - Many fields return `null` for under-covered countries — don't try to compute totals.
  - `production_share` and `resources_reserves_share` are % of global (decimal).

---

### `GET /v2/mining/sales-destination/{slug}/`

- **Purpose:** Sales destination breakdown for one mining company (revenue & volume per country).

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Company slug. |

- **Query parameters**

| Name | Type | Default | Range | Notes |
|---|---|---|---|---|
| `year` | int | latest | 1900–2026 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/sales-destination/pt-adaro-andalan-indonesia-tbk/?year=2024" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "year": 2024,
  "data": {
    "China": {
      "revenue_usd": null, "percentage_of_total_revenue": null,
      "volume": null, "percentage_of_sales_volume": 16,
      "commodity_type": "Coal", "unit": "Mt"
    }
  }
}
```

- **Gotchas**
  - Compare to `/v2/mining/exports/` (national) — this is **per-company** (more granular).
  - Revenue fields often null while volume % is populated — API source separates BPS and company filings.

---

### `GET /v2/mining/resources-reserves/`

- **Purpose:** Discovery — which provinces × commodities × years have resources/reserves data. No query parameters.

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/resources-reserves/" -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "Aceh": {
    "Coal":   [2024, 2023, 2022, 2021, 2020, 2019],
    "Cobalt": [2024, 2023, 2022],
    "Copper": [2024, 2023, 2022, 2021, 2020],
    "Gold":   [2024, 2023, 2022, 2021, 2020],
    "Nickel": [2024, 2023, 2022, 2021],
    "Silver": [2024]
  }
}
```

- **Gotchas**
  - Year lists are sorted **descending**.
  - Costs 1 credit.

---

### `GET /v2/mining/resources-reserves/{province}/`

- **Purpose:** Full resources/reserves detail for one province.

- **Path parameters**

| Name | Type | Allowed values | Notes |
|---|---|---|---|
| `province` | string | 32 Indonesian province names, exact match (case-insensitive): `Aceh`, `Banten`, `Bengkulu`, `Gorontalo`, `Jambi`, `Jawa Barat`, `Jawa Tengah`, `Jawa Timur`, `Kalimantan Barat`, `Kalimantan Selatan`, `Kalimantan Tengah`, `Kalimantan Timur`, `Kalimantan Utara`, `Kepulauan Bangka Belitung`, `Kepulauan Riau`, `Lampung`, `Maluku`, `Maluku Utara`, `Nusa Tenggara Barat`, `Nusa Tenggara Timur`, `Papua`, `Papua Barat`, `Papua Barat Daya`, `Papua Tengah`, `Riau`, `Sulawesi Barat`, `Sulawesi Selatan`, `Sulawesi Tengah`, `Sulawesi Tenggara`, `Sulawesi Utara`, `Sumatera Barat`, `Sumatera Selatan`, `Sumatera Utara`. | Bad name → 404. |

- **Query parameters**

| Name | Type | Default | Allowed | Notes |
|---|---|---|---|---|
| `commodity_type` | string | — | `Coal`, `Gold`, `Silver`, `Copper`, `Nickel`, `Cobalt`, `Tin` | — |
| `year` | int | — | 1900–2026 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/resources-reserves/Kalimantan%20Selatan/" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "province": "Kalimantan Selatan",
  "data": {
    "2024": {
      "Coal": {
        "exploration_target_Mt": 7.83,
        "total_inventory_Mt": 1846.31,
        "inferred_resources_Mt": 3481.9, "indicated_resources_Mt": 3414.04,
        "measured_resources_Mt": 6635.73, "total_resources_Mt": 13531.67,
        "total_resources_verify_Mt": 12376.75,
        "total_reserves_Mt": 4066.94, "total_reserves_verify_Mt": 3644.19
      }
    }
  }
}
```

- **Gotchas**
  - URL-encode province names with spaces (`Kalimantan Selatan` → `Kalimantan%20Selatan`).
  - All values in **Mt** (megatonnes) unless `unit` says otherwise.
  - `_verify` fields are the audited values — use those for sourcing rather than the raw totals.

---

### `GET /v2/mining/sites/`

- **Purpose:** List mining sites with advanced filters (location, commodity, production, year).

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `province` | string | — | province enum | Exact match. |
| `commodity_type` | string | — | `Coal`, `Copper`, `Gold`, `Nickel` | Case-insensitive. |
| `company` | string | — | company slug | Filter to one owner's sites. |
| `year` | int | — | 1900–2026 | Reporting year. |
| `min_production` | float | — | ≥0 | Min production volume. |
| `order_by` | string | `-year` | `year`, `-year`, `production_volume`, `-production_volume`, `strip_ratio`, `-strip_ratio` | Prefix `-` for desc. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/sites/?commodity_type=Coal&province=Kalimantan%20Timur&min_production=10&order_by=-production_volume" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    { "name": "Tutupan Utara", "project_name": null, "year": 2024,
      "commodity_type": "Coal", "production_volume": null, "unit": "Mt",
      "strip_ratio": null, "province": "Kalimantan Selatan", "city": "Balangan",
      "company_slug": "pt-adaro-indonesia", "company_name": "PT Adaro Indonesia",
      "slug": "tutupan-utara" }
  ],
  "pagination": { "total_count": 156, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - 156 sites in the universe.
  - `production_volume` can be `null` for sites with no disclosed production — common.

---

### `GET /v2/mining/sites/{slug}/`

- **Purpose:** Single mining site detail with lat/long and resources/reserves.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Site slug from `/v2/mining/sites/`. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/sites/batubara-benhes-3/" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "name": "Batubara Benhes 3", "year": 2024, "commodity_type": "Coal",
  "production_volume": null, "unit": "Mt", "strip_ratio": null,
  "resources_reserves": {
    "measurement_year": 2022,
    "probable_reserves_Mt": 447.28, "proven_reserves_Mt": 475.12,
    "inferred_resources_Mt": 176.8, "indicated_resources_Mt": 672.8,
    "measured_resources_Mt": 482.5, "total_resources_Mt": 555
  },
  "location": {
    "province": "Kalimantan Timur", "city": "Kutai Timur",
    "latitude": 1.13465, "longitude": 116.753186
  },
  "company_slug": "pt-bumi-kaliman-sejahtera",
  "company_name": "PT Bumi Kaliman Sejahtera",
  "slug": "batubara-benhes-3"
}
```

- **Gotchas**
  - **`location.latitude` / `longitude` are real WGS84** — ready for map overlay (Leaflet, Mapbox, etc.).
  - `resources_reserves.measurement_year` may lag the site `year` (different sources, different refresh cycles).

---

### `GET /v2/mining/total-production/`

- **Purpose:** National annual production for one commodity across all years + YoY change.

- **Query parameters**

| Name | Type | Required | Allowed | Notes |
|---|---|---|---|---|
| `commodity_type` | string | yes | `Coal`, `Copper`, `Gold`, `Nickel` | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/total-production/?commodity_type=coal" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
[
  { "year": 2024, "production_volume": 836.1, "prev_year_volume": 775.2, "unit": "Mt", "yoy_change_percent": 7.86 }
]
```

- **Gotchas**
  - Results sorted by year **descending**.
  - `yoy_change_percent` is decimal (7.86 = +7.86%).

---

### `GET /v2/mining/licenses/`

- **Purpose:** Mining licenses (IUP/IUPK/IPR/KK/PKP2B/SIPB) from ESDM Minerba portal.

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `province` | string | — | province enum (33 values incl. multi-province strings like `Kalimantan Tengah, Kalimantan Timur`) | Exact match. |
| `commodity_type` | string | — | `Bauxite`, `Clay`, `Coal`, `Copper`, `Gold`, `Granite`, `Iron`, `Limestone`, `Nickel`, `Non-Metallic Mineral`, `Others`, `Sand`, `Sand, Stone, Gravel`, `Tin` | Case-insensitive. |
| `company` | string | — | company slug | Filter to one owner. |
| `license_type` | string | — | `IPR`, `IUP`, `IUPK`, `KK`, `PKP2B`, `SIPB` | Case-insensitive. |
| `activity` | string | — | `Eksplorasi`, `Operasi Produksi` | Case-insensitive. |
| `cnc` | bool | — | true/false | Filter to Clear & Clean status. |
| `expiring_soon` | bool | — | true/false | Filter to licenses expiring within 365 days. |
| `order_by` | string | `license_expiry_date` | field or `-field` for desc | Allowed: `license_effective_date`, `license_expiry_date`, `licensed_area_ha`, `commodity_type`. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/licenses/?commodity_type=Coal&license_type=IUP&expiring_soon=true&limit=20" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    {
      "wiup_code": "2232785402019006",
      "license_number": "540/59/29.1.07.0/DPMPTSP/2020", "license_type": "IUP",
      "province": "Jawa Barat", "city": "Kota Tasikmalaya",
      "license_effective_date": "2020-10-14", "license_expiry_date": "2025-10-14",
      "activity": "Operasi Produksi", "licensed_area_ha": 9.2,
      "location": "Kota Tasikmalaya", "commodity_type": "Sand, Stone, Gravel",
      "company_name": "CV Anak Sejati", "cnc": "CNC", "generation": null,
      "company_slug": null
    }
  ],
  "pagination": { "total_count": 4151, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - **4,151 licenses** in the universe.
  - `company_slug` is `null` for unlisted holders (small/license holders without company entities in the mining companies table).
  - Default sort is **soonest expiring first** — useful for "license expiry watch" agents.

---

### `GET /v2/mining/license-auctions/`

- **Purpose:** Mining license auctions scraped from ESDM Minerba.

- **Query parameters**

| Name | Type | Default | Allowed / format | Notes |
|---|---|---|---|---|
| `province` | string | — | 8-province enum | Case-insensitive. |
| `commodity_type` | string | — | `Coal`, `Copper`, `Gold`, `Nickel` | Case-insensitive. |
| `area_type` | string | — | `WIUP`, `WIUPK` | Case-insensitive. |
| `status` | string | — | any auction status string | e.g. `Lelang Selesai`. |
| `participant` | string | — | partial company name | Find auctions where this company participated. |
| `qualified` | bool | — | true/false | Pair with `participant`; only return auctions where the participant passed. |
| `min_participants` | int | — | ≥0 | Filter to auctions with N+ participants. |
| `order_by` | string | `-winner_date` | field or `-field` for desc | Allowed: `commodity_type`, `winner_date`, `licensed_area_ha`, `participant_count`. |
| `limit` | int | 20 | 1–30 | — |
| `offset` | int | 0 | ≥0 | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/license-auctions/?commodity_type=Nickel&limit=10" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "results": [
    {
      "commodity_type": "Nickel", "city": "Luwu Timur", "province": "Sulawesi Selatan",
      "company_name": "Aneka Tambang", "winner_date": "2024-06-20",
      "licensed_area_ha": 4252, "license_number": "56.K/MB.01/MEM.B/2023",
      "area_type": "WIUPK", "kdi": "14409850000", "wiup_code": "1473242122023001",
      "auction_status": "Lelang Selesai", "participant_count": 3,
      "winner": true, "company_slug": "pt-aneka-tambang-tbk"
    }
  ],
  "pagination": { "total_count": 14, "showing": 1, "limit": 2, "offset": 0, "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

- **Gotchas**
  - **Only 14 auctions** in the universe — small but high-signal dataset.
  - `kdi` is the auction's "KDI value" (rupiah bid metric) — kept as string even though it looks numeric.
  - List endpoint omits `phases` and `participants` — fetch detail endpoint for those.

---

### `GET /v2/mining/license-auctions/{wiup_code}/`

- **Purpose:** Single auction record with phases timeline and participant qualification list.

- **Path parameters**

| Name | Type | Notes |
|---|---|---|
| `wiup_code` | string | WIUP code from `/v2/mining/license-auctions/`. |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/license-auctions/1752072062023002/" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
{
  "commodity_type": "Gold", "city": "Sumbawa Barat", "province": "Nusa Tenggara Barat",
  "company_name": "Tambang Sukses Sakti", "winner_date": "2024-01-03",
  "licensed_area_ha": 4813, "license_number": "271.K/MB.01/MEM.B/2023-U",
  "area_type": "WIUP", "kdi": "7225880000", "wiup_code": "1752072062023002",
  "auction_status": "Lelang Selesai", "participant_count": 2, "winner": true,
  "created_at": "2024-01-16", "last_modified": "2024-01-17",
  "phases": [
    { "order": 1, "description": "Pengumuman Pelaksanaan Lelang", "start_date": "2023-11-14", "end_date": null }
  ],
  "participants": [
    { "NIB": "1240001442836", "company_name": "Tambang Sukses Sakti", "email": "saktitambangsukses@gmail.com", "qualification_result": "Lolos" }
  ],
  "company_slug": null
}
```

- **Gotchas**
  - `phases[].end_date` is `null` for ongoing phases.
  - `qualification_result` includes `Lolos` (passed) or `Tidak Lolos` (failed).

---

### `GET /v2/mining/contracts/`

- **Purpose:** Active mining contracts linking mine owners to service contractors.

- **Query parameters**

| Name | Type | Allowed / format | Notes |
|---|---|---|---|
| `contractor` | string | contractor company slug | — |
| `mine_owner` | string | mine-owner company slug | — |

- **Sample request**

```bash
curl "https://api.sectors.app/v2/mining/contracts/?mine_owner=pt-maruwai-coal" \
  -H "Authorization: <api-key>"
```

- **Sample response**

```json
[
  { "mine_owner_slug": "pt-maruwai-coal", "mine_owner_name": "PT Maruwai Coal",
    "contractor_slug": "pt-indonesia-bulk-terminal", "contractor_name": "PT Indonesia Bulk Terminal",
    "contract_period_end": "2024-12-31" }
]
```

- **Gotchas**
  - Bare `GET /v2/mining/contracts/` returns the full universe.
  - `contract_period_end` is the latest known end date — may be `null` for evergreen contracts.

---

## Cross-reference

- Mining uses **slug identifiers, not tickers** — call `/v2/mining/companies/` first to discover slugs, then chain detail calls.
- The cross-table story is **commodity × table coverage**: only Coal/Gold/Nickel/Copper have full production + exports + reserves + sites; everything else is price-only.
- For an end-to-end "Indonesian critical-minerals intelligence" app: start with `/v2/mining/total-production/` (national volume), drill to `/v2/mining/exports/` (where it goes), then `/v2/mining/sites/` + `/v2/mining/companies/performance/` (who's producing), then `/v2/mining/companies/ownership/` (who owns them) and `/v2/mining/licenses/` + `/v2/mining/contracts/` (legal structure).
- License auctions are a **leading indicator** for production changes — Aneka Tambang winning a Nickel auction in 2024 explains their 2025+ production profile.
- See `idx-*.md` for IDX, `sgx.md` for SGX, `klse.md` for KLSE.