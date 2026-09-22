# Mining (Indonesia) — Companies

> **Lane 1 — IDX + Mining ONLY.** Sectors Financial API v2 reference for
> Indonesian mining companies (mine owners, contractors, holdings, traders).
> Source docs: `https://docs.sectors.app/api-references/v2/mining/companies/...`
> (verified 29 Aug 2026).

All endpoints live under `https://api.sectors.app/v2/mining/`. Auth is a raw API key in the `Authorization` header (no `Bearer ` prefix).

> **Mining slug convention**: URL-friendly identifier, e.g. `pt-adaro-andalan-indonesia-tbk`. Get slugs from [`/v2/mining/companies/`](#get-v2miningcompanies--list-mining-companies).
>
> **Mining commodity enum** (varies by endpoint): `Aluminium`, `Coal`, `Copper`, `Gold`, `Nickel`, `Silver`, `Zinc and Lead`. The full set is narrower than news/permits — see each endpoint for the exact enum.
>
> **All mining endpoints** use USD as the standard currency (USD millions for financials, USD per ton for prices). This differs from the IDX endpoints which use IDR.

---

### `GET /v2/mining/companies/` — List Mining Companies

- **Purpose:** Searches Indonesian mining companies by name, symbol, slug, or key operation. Filterable by commodity and company type.
- **Hackathon applicability:** **all tracks** — universe feed for mining universe screens.

#### Query parameters

| Name | Type | Default | Allowed / Notes |
|---|---|---|---|
| `keyword` | string | — | Case-insensitive search across company name, IDX symbol, slug, and key operations. |
| `commodity_type` | enum | — | `Aluminium`, `Coal`, `Copper`, `Gold`, `Nickel`, `Silver`, `Zinc and Lead`. |
| `company_type` | enum | — | `Consultant`, `Contractor`, `Holding`, `Manufacturer`, `Mine Owner`, `Trader`. |
| `has_financials` | boolean | false | If `true`, only return companies with financial data available. |
| `limit` | integer | 20 | 1–30, max 30. |
| `offset` | integer | 0 | Pagination. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/companies/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=Coal" \
  --data-urlencode "company_type=Holding" \
  --data-urlencode "limit=30"
```

#### Sample response

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
  "pagination": { "total_count": 366, "showing": 1, "limit": 2, "offset": 0,
    "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

#### Gotchas

- **Costs 1 credit** per call. ~366 total companies in the universe.
- `symbol` may be `null` — these include unlisted (private) mining companies too. Useful: combine with IDX universe for a "listed-miners-only" view.
- `key_operation` is free-text (e.g. `Investment`, `Coal Trading`, `Gold Mining`) — search it via `keyword=`.

---

### `GET /v2/mining/companies/{slug}/` — Mining Company Detail

- **Purpose:** Operational profile for one mining company: activities, commodity types, associated licenses, contracts, and site count.
- **Hackathon applicability:** **market-intel** (deep-dive profiles), **ai-agents** (company knowledge base).

#### Path parameters

| Name | Type | Notes |
|---|---|---|
| `slug` | string | E.g. `pt-adaro-andalan-indonesia-tbk`. Get from [`/v2/mining/companies/`](#get-v2miningcompanies--list-mining-companies). |

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/companies/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>"
```

#### Sample response

```json
{
  "name": "PT Adaro Andalan Indonesia Tbk",
  "slug": "pt-adaro-andalan-indonesia-tbk",
  "symbol": "AADI.JK",
  "company_type": "Holding",
  "operation_province": "Jakarta",
  "operation_district": "Jakarta Selatan",
  "key_operation": "Coal Trading",
  "representative_address": "Cyber 2 Tower Lantai 26, Jl. H.R. Rasuna Said Blok X-5, No.13, Jakarta 12950",
  "website": "www.adaroindonesia.com",
  "phone_number": "021-25533065",
  "email": "corsec@adaroindonesia.com",
  "activities": ["Trading"],
  "commodity_type": ["Coal"],
  "mining_license": [
    {
      "license_type": "IUPK",
      "license_number": "11/1/IUP/PMA/2022",
      "wiup_code": "1300003032014132",
      "province": "Kalimantan Selatan",
      "city": "Kabupaten Tabalong",
      "license_effective_date": "2022-09-13",
      "license_expiry_date": "2032-10-01",
      "activity": "Operasi Produksi",
      "licensed_area_ha": 23942,
      "cnc": "CNC",
      "generation": "GEN I",
      "location": "Kabupaten Tabalong, Kabupaten Balangan",
      "commodity_type": "Coal"
    }
  ],
  "mining_contract": [],
  "mining_site_count": 0
}
```

#### Gotchas

- **Costs 1 credit.**
- `mining_license` items mirror fields from [`/v2/mining/licenses/`](#get-v2mininglicenses--mining-licenses) — useful for "what licenses does company X hold?" without a separate call.
- `mining_contract` empty array is normal for holding/owner companies (they own, they don't contract).
- `mining_site_count` is 0 if the company is a holding/trader without operating sites — use [`/v2/mining/sites/`](./mining-sites-licenses.md#get-v2miningsites--mining-sites) to find actual mine sites.

---

### `GET /v2/mining/companies/financials/{slug}/` — Mining Company Financials

- **Purpose:** Annual financial records (assets, revenue, profit with breakdowns) for a mining company. All monetary values are in **USD millions**.
- **Hackathon applicability:** **market-intel** (financial dashboards), **ai-agents** (valuation work).

#### Path + query parameters

| Name | Type | Default | Notes |
|---|---|---|---|
| `slug` | path | required | Company slug. |
| `year` | integer | latest available | 1900–2026. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/companies/financials/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "year=2024"
```

#### Sample response (Adaro 2024)

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

#### Gotchas

- **Costs 1 credit.**
- **All values are USD (not IDR).** Note: values are stored as integers but represent USD millions per docs. So `assets_usd: 5993000000` = $5.993 billion.
- `available_years` shows what years have data — use it to plan range queries.
- `revenue_breakdown` and `cost_of_revenue_breakdown` schemas vary by commodity (coal has `coal_mining_and_trading`, `royalty`, etc.; nickel would have different keys).

---

### `GET /v2/mining/companies/ownership/{slug}/` — Mining Company Ownership

- **Purpose:** Corporate ownership tree — parent companies (who owns it) and subsidiaries (what it owns) with percentage stakes.
- **Hackathon applicability:** **market-intel** (group structure), **ai-agents** (conglomerate mapping).

#### Path parameters

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Company slug. |

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/companies/ownership/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>"
```

#### Sample response

```json
{
  "slug": "pt-adaro-andalan-indonesia-tbk",
  "parents": [
    { "name": "PT Alamtri Resources Indonesia Tbk", "slug": "pt-alamtri-resources-indonesia-tbk",
      "symbol": "ADRO.JK", "percentage_ownership": 15.37 }
  ],
  "subsidiaries": [
    { "name": "PT Adaro Mining Technologies", "slug": "pt-adaro-mining-technologies",
      "symbol": null, "percentage_ownership": 100 }
  ]
}
```

#### Gotchas

- **Costs 1 credit.**
- `percentage_ownership` is in percent (15.37 = 15.37%), not decimal.
- `symbol` may be `null` for private subsidiaries.
- Useful chain: `/v2/mining/companies/{slug}/` → ownership → recurse into each subsidiary's detail.

---

### `GET /v2/mining/companies/performance/{slug}/` — Mining Company Performance

- **Purpose:** Production volume, sales volume, strip ratio, and resources/reserves data for a mining company for a given year.
- **Hackathon applicability:** **market-intel** (operational KPIs), **ai-agents** ("what does this mine produce?").

#### Path + query parameters

| Name | Type | Default | Allowed / Notes |
|---|---|---|---|
| `slug` | path | required | Company slug. |
| `year` | integer | latest available | 1900–2026. |
| `commodity_type` | enum | — | `Coal`, `Copper`, `Gold`, `Nickel`, `Silver`. Case-insensitive. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/companies/performance/pt-adaro-andalan-indonesia-tbk/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "year=2024"
```

#### Sample response (Adaro 2024, coal)

```json
{
  "year": 2024,
  "available_years": [2019, 2020, 2021, 2022, 2023, 2024],
  "data": [
    {
      "year": 2024,
      "commodity_type": "Coal",
      "commodity_sub_type": "Sub-bituminous & Metallurgical Coal",
      "commodity_stats": {
        "unit": "Mt",
        "mining_operation_status": "production",
        "production_volume": 48.11,
        "sales_volume": 55.8,
        "overburden_removal_volume": 214.18,
        "strip_ratio": 4.51,
        "resources_reserves": {
          "measurement_year": 2024,
          "probable_reserves_Mt": 356, "proven_reserves_Mt": 463,
          "total_reserves_Mt": 819,
          "inferred_resources_Mt": 640.6, "indicated_resources_Mt": 962,
          "measured_resources_Mt": 3176, "total_resources_Mt": 4374
        },
        "products": [
          {
            "product_name": "Envirocoal -North Tutupan",
            "calorific_value_kcal": { "max": 4843, "min": 4843 },
            "total_moisture_pct": { "max": 27.1, "min": 27.1 },
            "ash_content_adb": { "max": 2.1, "min": 2.1 },
            "total_sulphur_adb": { "max": 0.1, "min": 0.1 },
            "volatile_matter_adb": { "max": 39.7, "min": 39.7 }
          }
        ]
      }
    }
  ]
}
```

#### Gotchas

- **Costs 1 credit.**
- `data` is an array — multi-commodity companies return one entry per commodity. Filter with `commodity_type=` query param to narrow.
- `strip_ratio` = overburden / coal. Higher = less efficient (more waste rock per ton of coal).
- For **coal** products: `calorific_value_kcal`, `total_moisture_pct`, `ash_content_arb/adb`, `total_sulphur_arb/adb`, `volatile_matter_adb`, `fixed_carbon_adb` are quality grades.
- Resources/reserves schema: `probable_reserves`, `proven_reserves`, `total_reserves` (production-ready) vs `inferred`, `indicated`, `measured`, `total_resources` (geological).

---

## Cross-references

- TOC anchor: [`sectors-api-and-mcp.md`](../sectors-api-and-mcp.md)
- Commodities + trade: [`mining-commodities-trade.md`](./mining-commodities-trade.md)
- Sites, resources, licenses, auctions: [`mining-sites-licenses.md`](./mining-sites-licenses.md)
- IDX endpoints: [`idx-*.md`](./)
