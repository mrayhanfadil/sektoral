# Mining (Indonesia) — Sites, Resources, Licenses, Auctions

> **Lane 1 — IDX + Mining ONLY.** Sectors Financial API v2 reference for
> Indonesian mining sites, resources & reserves, mining contracts, license
> auctions, and active licenses. Source docs:
> `https://docs.sectors.app/api-references/v2/mining/...` (verified 29 Aug 2026).

All endpoints live under `https://api.sectors.app/v2/mining/`. Auth is a raw API key in the `Authorization` header (no `Bearer ` prefix).

> **Mining commodity enum** (varies per endpoint): `Coal`, `Gold`, `Nickel`, `Copper`, `Silver`, `Cobalt`, `Tin`, `Bauxite`, `Iron`, `Sand, Stone, Gravel`, `Non-Metallic Mineral`, `Limestone`, `Clay`, `Granite`. See each endpoint for the exact list.
>
> **Province enums** are spelled exactly: e.g. `Kalimantan Timur`, `Sulawesi Selatan`, `Papua Barat Daya`. Case-insensitive per docs.
>
> **Site slugs** are URL-friendly identifiers — e.g. `tutupan-utara`, `batubara-benhes-3`. Get from [`/v2/mining/sites/`](#get-v2miningsites--mining-sites).

---

### `GET /v2/mining/sites/` — Mining Sites

- **Purpose:** Lists mining sites with filtering by location, commodity, production volume, plus sorting.
- **Available commodity_type**: `Coal`, `Gold`, `Nickel`, `Copper`.
- **Hackathon applicability:** **market-intel** (production heatmaps), **ai-agents** (site-level queries).

#### Query parameters

| Name | Type | Default | Allowed / Notes |
|---|---|---|---|
| `commodity_type` | enum | — | `Coal`, `Copper`, `Gold`, `Nickel`. Case-insensitive. |
| `province` | enum | — | Exact name. E.g. `Kalimantan Timur`, `Sulawesi Selatan`. |
| `company` | string | — | Filter by company slug. E.g. `pt-maruwai-coal`. |
| `year` | integer | — | 1900–2026. |
| `min_production` | double | — | Filter for sites with `production_volume ≥ this value`. |
| `order_by` | enum | `-year` | `production_volume`, `strip_ratio`, `year` (prefix `-` for desc). |
| `limit` | integer | 20 | 1–30, max 30. |
| `offset` | integer | 0 | Pagination. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/sites/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=Coal" \
  --data-urlencode "province=Kalimantan%20Timur" \
  --data-urlencode "min_production=1000" \
  --data-urlencode "order_by=-production_volume"
```

#### Sample response

```json
{
  "results": [
    { "name": "Tutupan Utara", "project_name": null, "year": 2024,
      "commodity_type": "Coal", "production_volume": null, "unit": "Mt",
      "strip_ratio": null, "province": "Kalimantan Selatan", "city": "Balangan",
      "company_slug": "pt-adaro-indonesia", "company_name": "PT Adaro Indonesia",
      "slug": "tutupan-utara" }
  ],
  "pagination": { "total_count": 156, "showing": 1, "limit": 2, "offset": 0,
    "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

#### Gotchas

- **Costs 1 credit** per page.
- `production_volume` and `strip_ratio` can be `null` for sites without recent production data.
- **Province enum is limited** (~22 entries). If the province you want isn't listed, the response will 400 — try the detail endpoint for the company instead.

---

### `GET /v2/mining/sites/{slug}/` — Mining Site Detail

- **Purpose:** Full detail for one mining site: parsed resources/reserves, location (latitude/longitude), parent company.

#### Path parameters

| Name | Type | Notes |
|---|---|---|
| `slug` | string | Site slug. Get from [`/v2/mining/sites/`](#get-v2miningsites--mining-sites). E.g. `batubara-benhes-3`. |

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/sites/batubara-benhes-3/" \
  -H "Authorization: <api-key>"
```

#### Sample response

```json
{
  "name": "Batubara Benhes 3",
  "project_name": null, "year": 2024, "commodity_type": "Coal",
  "production_volume": null, "unit": "Mt",
  "overburden_removal_volume": null, "strip_ratio": null,
  "resources_reserves": {
    "measurement_year": 2022,
    "probable_reserves_Mt": 447.28, "proven_reserves_Mt": 475.12,
    "total_reserves_Mt": null,
    "inferred_resources_Mt": 176.8, "indicated_resources_Mt": 672.8,
    "measured_resources_Mt": 482.5, "total_resources_Mt": 555,
    "calorific_value_kcal": null
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

#### Gotchas

- **Costs 1 credit.**
- **`location` includes lat/long** — useful for geo-visualisations (Leaflet, Mapbox, etc.).
- `resources_reserves.calorific_value_kcal` is `null` for non-coal sites.

---

### `GET /v2/mining/resources-reserves/` — Resources & Reserves Index

- **Purpose:** Discovery index showing which (province, year, commodity) tuples have resources/reserves data. Use before [`/v2/mining/resources-reserves/{province}/`](#get-v2miningresources-reservesprovince--resources--reserves-detail).
- **Hackathon applicability:** **market-intel** (national reserves inventory), **ai-agents** (avoid 404s on province detail calls).

#### Query parameters

**None.** This is a fixed catalog endpoint.

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/resources-reserves/" \
  -H "Authorization: <api-key>"
```

#### Sample response

```json
{
  "Aceh": {
    "Coal": [2024, 2023, 2022, 2021, 2020, 2019],
    "Cobalt": [2024, 2023, 2022],
    "Copper": [2024, 2023, 2022, 2021, 2020],
    "Gold": [2024, 2023, 2022, 2021, 2020],
    "Nickel": [2024, 2023, 2022, 2021],
    "Silver": [2024]
  }
}
```

#### Gotchas

- **Costs 1 credit.** Cache.
- Province → commodity → `[years]` triple-nested dictionary. Use to plan province-detail calls.
- **33 Indonesian provinces** in the enum (including newer Papua Tengah, Papua Barat Daya, Papua Selatan — see detail endpoint for full list).

---

### `GET /v2/mining/resources-reserves/{province}/` — Resources & Reserves Detail

- **Purpose:** Resources and reserves data for a single province, nested by year then by commodity. Each commodity entry contains the full breakdown: `exploration_target`, `total_inventory`, `resources`, `reserves`, `unit`.
- **Available commodity_type**: `Coal`, `Gold`, `Silver`, `Copper`, `Nickel`, `Cobalt`, `Tin`.
- **Hackathon applicability:** **market-intel** (province-level reserves inventory), **ai-agents** (geological baselines).

#### Path + query parameters

| Name | Type | Notes |
|---|---|---|
| `province` | path | required. Exact province name. Case-insensitive. 33 entries — full list in OpenAPI spec for this endpoint. |
| `commodity_type` | enum | Optional. Restrict to one commodity. |
| `year` | integer | Optional. Restrict to one year. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/resources-reserves/Kalimantan%20Selatan/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=Coal" \
  --data-urlencode "year=2024"
```

#### Sample response

```json
{
  "province": "Kalimantan Selatan",
  "data": {
    "2024": {
      "Coal": {
        "exploration_target_Mt": 7.83,
        "total_inventory_Mt": 1846.31,
        "inferred_resources_Mt": 3481.9,
        "indicated_resources_Mt": 3414.04,
        "measured_resources_Mt": 6635.73,
        "total_resources_Mt": 13531.67,
        "total_resources_verify_Mt": 12376.75,
        "total_reserves_Mt": 4066.94,
        "total_reserves_verify_Mt": 3644.19
      }
    }
  }
}
```

#### Gotchas

- **Costs 1 credit.**
- Province names with spaces — URL-encode them (`Kalimantan%20Timur`).
- Schema is `Mt` (megatons) for coal. Other commodities may use `Kg` or similar.
- `*_verify_Mt` fields are Sectors' verification-corrected totals — use these over the raw `*_Mt` fields for reporting.

---

### `GET /v2/mining/contracts/` — Mining Contracts

- **Purpose:** Active mining contracts linking mine owners to their service contractors. Optionally filter by owner or contractor.
- **Hackathon applicability:** **market-intel** (contractor dependency), **ai-agents** (supply-chain mapping).

#### Query parameters

| Name | Type | Allowed / Notes |
|---|---|---|
| `mine_owner` | string | Filter by mine owner company slug. |
| `contractor` | string | Filter by contractor company slug. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/contracts/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "mine_owner=pt-maruwai-coal"
```

#### Sample response

```json
[
  { "mine_owner_slug": "pt-maruwai-coal", "mine_owner_name": "PT Maruwai Coal",
    "contractor_slug": "pt-indonesia-bulk-terminal",
    "contractor_name": "PT Indonesia Bulk Terminal",
    "contract_period_end": "2024-12-31" }
]
```

#### Gotchas

- **Costs 1 credit.**
- One contract per row (not per service). A single mine owner with multiple contractors returns multiple rows.
- `contract_period_end` may be `null` for indefinite contracts.

---

### `GET /v2/mining/license-auctions/` — Mining License Auctions

- **Purpose:** Mining license auctions scraped from the ESDM Minerba portal. Phases and participants are omitted from list results — use the detail endpoint for the full auction record.
- **Available commodity_type**: `Nickel`, `Coal`, `Gold`, `Copper`.
- **Hackathon applicability:** **market-intel** (auction pipeline), **ai-agents** ("who's bidding on what?").

#### Query parameters

| Name | Type | Default | Allowed / Notes |
|---|---|---|---|
| `commodity_type` | enum | — | `Coal`, `Copper`, `Gold`, `Nickel`. |
| `province` | enum | — | `Bengkulu`, `Gorontalo`, `Kalimantan Tengah`, `Maluku Utara`, `Nusa Tenggara Barat`, `Sulawesi Selatan`, `Sulawesi Utara`, `Sumatera Selatan`. |
| `area_type` | enum | — | `WIUP`, `WIUPK`. |
| `status` | string | — | E.g. `Lelang Selesai`. Case-insensitive. |
| `participant` | string | — | Partial company-name match. |
| `qualified` | boolean | — | When `true`, only return auctions where the `participant` passed qualification. **Requires `participant`.** |
| `min_participants` | integer | — | Min participant count. |
| `order_by` | enum | `-winner_date` | `commodity_type`, `licensed_area_ha`, `participant_count`, `winner_date` (prefix `-` for desc). |
| `limit` | integer | 20 | 1–30, max 30. |
| `offset` | integer | 0 | Pagination. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/license-auctions/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=Nickel" \
  --data-urlencode "qualified=true" \
  --data-urlencode "participant=Aneka%20Tambang"
```

#### Sample response

```json
{
  "results": [
    { "commodity_type": "Nickel", "city": "Luwu Timur", "province": "Sulawesi Selatan",
      "company_name": "Aneka Tambang", "winner_date": "2024-06-20",
      "licensed_area_ha": 4252, "license_number": "56.K/MB.01/MEM.B/2023",
      "area_type": "WIUPK", "kdi": "14409850000", "wiup_code": "1473242122023001",
      "auction_status": "Lelang Selesai", "participant_count": 3,
      "winner": true, "company_slug": "pt-aneka-tambang-tbk" }
  ],
  "pagination": { "total_count": 14, "showing": 1, "limit": 2, "offset": 0,
    "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

#### Gotchas

- **Costs 1 credit.**
- `kdi` = "Komitmen Dana Investasi" (Investment Commitment) — the bidder's committed investment in IDR.
- `wiup_code` is the WIUP (Wilayah Izin Usaha Pertambangan) mining permit area code. Use it for [`/v2/mining/license-auctions/{wiup_code}/`](#get-v2mininglicense-auctionswiup_code--mining-license-auction-detail).
- `auction_status` is free-text Bahasa Indonesia (`Lelang Selesai` = auction finished).

---

### `GET /v2/mining/license-auctions/{wiup_code}/` — Mining License Auction Detail

- **Purpose:** Full auction record including phases timeline and participant qualification list.

#### Path parameters

| Name | Type | Notes |
|---|---|---|
| `wiup_code` | string | The WIUP identifier from [`/v2/mining/license-auctions/`](#get-v2mininglicense-auctions--mining-license-auctions). |

#### Sample request

```bash
curl "https://api.sectors.app/v2/mining/license-auctions/1752072062023002/" \
  -H "Authorization: <api-key>"
```

#### Sample response

```json
{
  "commodity_type": "Gold", "city": "Sumbawa Barat", "province": "Nusa Tenggara Barat",
  "company_name": "Tambang Sukses Sakti", "winner_date": "2024-01-03",
  "licensed_area_ha": 4813, "license_number": "271.K/MB.01/MEM.B/2023-U",
  "area_type": "WIUP", "kdi": "7225880000", "wiup_code": "1752072062023002",
  "auction_status": "Lelang Selesai", "participant_count": 2,
  "winner": true, "created_at": "2024-01-16", "last_modified": "2024-01-17",
  "phases": [
    { "order": 1, "description": "Pengumuman Pelaksanaan Lelang",
      "start_date": "2023-11-14", "end_date": null }
  ],
  "participants": [
    { "NIB": "1240001442836", "company_name": "Tambang Sukses Sakti",
      "email": "saktitambangsukses@gmail.com", "qualification_result": "Lolos" }
  ],
  "company_slug": null
}
```

#### Gotchas

- **Costs 1 credit.**
- `phases` array is the auction timeline — `description` is free-text Bahasa Indonesia.
- `participants[].NIB` = Nomor Induk Berusaha (Indonesian Business Registration Number).
- `qualification_result` = `Lolos` (passed) / `Tidak Lolos` (failed).

---

### `GET /v2/mining/licenses/` — Mining Licenses

- **Purpose:** Active mining licenses (IUP/IUPK) from the ESDM Minerba portal, filterable by status, commodity, location, and expiry.
- **Hackathon applicability:** **market-intel** (license-expiry dashboard), **ai-agents** ("which licenses expire in 6 months?").

#### Query parameters

| Name | Type | Default | Allowed / Notes |
|---|---|---|---|
| `commodity_type` | enum | — | `Bauxite`, `Clay`, `Coal`, `Copper`, `Gold`, `Granite`, `Iron`, `Limestone`, `Nickel`, `Non-Metallic Mineral`, `Others`, `Sand`, `Sand, Stone, Gravel`, `Tin`. |
| `province` | enum | — | 36 entries (see full list in OpenAPI spec). |
| `company` | string | — | Filter by company slug. |
| `license_type` | enum | — | `IPR`, `IUP`, `IUPK`, `KK`, `PKP2B`, `SIPB`. |
| `activity` | enum | — | `Eksplorasi`, `Operasi Produksi`. |
| `cnc` | boolean | — | Filter by Clear & Clean status. |
| `expiring_soon` | boolean | — | `true` = licenses expiring within next 365 days. |
| `order_by` | enum | `license_expiry_date` | `commodity_type`, `license_effective_date`, `license_expiry_date`, `licensed_area_ha` (prefix `-` for desc). |
| `limit` | integer | 20 | 1–30, max 30. |
| `offset` | integer | 0 | Pagination. |

#### Sample request

```bash
curl -G "https://api.sectors.app/v2/mining/licenses/" \
  -H "Authorization: <api-key>" \
  --data-urlencode "commodity_type=Coal" \
  --data-urlencode "expiring_soon=true" \
  --data-urlencode "license_type=IUP" \
  --data-urlencode "order_by=license_expiry_date"
```

#### Sample response

```json
{
  "results": [
    { "wiup_code": "2232785402019006",
      "license_number": "540/59/29.1.07.0/DPMPTSP/2020",
      "license_type": "IUP",
      "province": "Jawa Barat", "city": "Kota Tasikmalaya",
      "license_effective_date": "2020-10-14", "license_expiry_date": "2025-10-14",
      "activity": "Operasi Produksi", "licensed_area_ha": 9.2,
      "location": "Kota Tasikmalaya", "commodity_type": "Sand, Stone, Gravel",
      "company_name": "CV Anak Sejati", "cnc": "CNC", "generation": null,
      "company_slug": null }
  ],
  "pagination": { "total_count": 4151, "showing": 1, "limit": 2, "offset": 0,
    "has_next": true, "has_previous": false, "next_offset": 2, "previous_offset": null }
}
```

#### License-type glossary (Indonesia mining permits)

| Code | Full name | Translation |
|---|---|---|
| `IUP` | Izin Usaha Pertambangan | Mining Business Permit — general operating license. |
| `IUPK` | Izin Usaha Pertambangan Khusus | Special Mining Business Permit — for foreign investment or state-owned. |
| `IPR` | Izin Pertambangan Rakyat | People's Mining Permit — small-scale / artisanal. |
| `KK` | Kuasa Kontrak | Contract of Work — legacy PMA license. |
| `PKP2B` | Perjanjian Karya Pengusahaan Pertambangan Batubara | Coal Cooperation Agreement — legacy coal-specific. |
| `SIPB` | Surat Izin Penambangan Batuan | Rock Mining Permit — non-metal/quarry. |

#### Gotchas

- **Costs 1 credit** per page. ~4,151 total licenses — full sweep is ~139 pages.
- `cnc` = "Clear & Clean" status — `null` means not yet verified; `CNC` means cleared; `non-CNC` means has issues.
- `generation` field: legacy generational classification (e.g. `GEN I`).
- `expiring_soon=true` covers the next 365 days — combine with `order_by=license_expiry_date` to surface the soonest-expiring first.

---

## Cross-references

- TOC anchor: [`sectors-api-and-mcp.md`](../sectors-api-and-mcp.md)
- Mining companies: [`mining-companies.md`](./mining-companies.md)
- Commodities + trade: [`mining-commodities-trade.md`](./mining-commodities-trade.md)
- IDX endpoints: [`idx-*.md`](./)
