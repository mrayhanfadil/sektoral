# Example 7: Mining — coal end-to-end

> Hackathon track fit: **Market Intel** / All
> Endpoints exercised: `GET /v2/mining/companies/`, `GET /v2/mining/companies/{slug}/`, `GET /v2/mining/sites/`, `GET /v2/mining/commodities/{name}/price/`, `GET /v2/mining/exports/`
> Credits per run: **5** (companies + 1 detail + sites + price + exports) — add another credit if you paginate the companies list

## What this demonstrates

- The **mining extension** of Sectors: separate from IDX/SGX/KLSE. Same auth header, same base URL, but `/v2/mining/...` prefix.
- Coal as the canonical use case — Indonesia is the world's largest thermal coal exporter, and the API has deep coverage (commodity prices, sites, exports, contracts, licenses).
- **Slug-based addressing**: mining endpoints use `slug` (e.g. `pt-adaro-andalan-indonesia-tbk`), not IDX symbol. Symbol can be `null` for non-listed mining entities.
- The **4-step vertical narrative**: discover operators → pick one → see its site footprint → read the macro context (price + exports). 5 credits total.

## Code

```python
"""
Mining sector end-to-end: coal in Indonesia.

Pipeline (5 credits total):
  1. List coal operators       (1 credit, paginated)
  2. Get a company's profile   (1 credit)
  3. List its mining sites     (1 credit, paginated by year/province)
  4. Coal price history        (1 credit)
  5. Coal export destinations   (1 credit)
"""
import os
import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}


def mining_companies(commodity_type: str | None = None,
                     company_type: str | None = None,
                     keyword: str | None = None,
                     has_financials: bool | None = None,
                     limit: int = 30, offset: int = 0) -> dict:
    """
    Search Indonesian mining companies.

    commodity_type enum: Aluminium, Coal, Copper, Gold, Nickel, Silver, Zinc and Lead
    company_type enum:   Consultant, Contractor, Holding, Manufacturer, Mine Owner, Trader

    Costs 1 credit per page (limit max 30).
    """
    params: dict = {"limit": limit, "offset": offset}
    if commodity_type:
        params["commodity_type"] = commodity_type
    if company_type:
        params["company_type"] = company_type
    if keyword:
        params["keyword"] = keyword
    if has_financials is not None:
        params["has_financials"] = "true" if has_financials else "false"
    r = requests.get(f"{BASE}/v2/mining/companies/", headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def mining_company_detail(slug: str) -> dict:
    """Full profile for one mining company (activities, licenses, contracts). 1 credit."""
    r = requests.get(f"{BASE}/v2/mining/companies/{slug}/", headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def mining_sites(commodity_type: str | None = None,
                 province: str | None = None,
                 company: str | None = None,
                 year: int | None = None,
                 min_production: float | None = None,
                 order_by: str = "-year",
                 limit: int = 30, offset: int = 0) -> dict:
    """
    List mining sites with advanced filters.

    commodity_type enum: Coal, Gold, Nickel, Copper  (NOTE: not the full set — Coal/Gold/Nickel/Copper only)
    province enum: 21 Indonesian provinces (Kalimantan Timur, Sumatera Selatan, etc.)
    order_by: production_volume, -production_volume, strip_ratio, -strip_ratio, year, -year

    Costs 1 credit per page (limit max 30).
    """
    params: dict = {"limit": limit, "offset": offset, "order_by": order_by}
    if commodity_type:
        params["commodity_type"] = commodity_type
    if province:
        params["province"] = province
    if company:
        params["company"] = company
    if year:
        params["year"] = year
    if min_production is not None:
        params["min_production"] = min_production
    r = requests.get(f"{BASE}/v2/mining/sites/", headers=HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()


def commodity_price(commodity_name: str,
                    start_year: int | None = None,
                    end_year: int | None = None) -> list[dict]:
    """
    Historical commodity price. Monthly granularity; bi-weekly for recent Coal.
    Max 3-year range (else 400). Costs 1 credit.

    commodity_name: get from /v2/mining/commodities/ — Gold, Coal, Copper, etc.
    """
    params: dict = {}
    if start_year:
        params["start_year"] = start_year
    if end_year:
        params["end_year"] = end_year
    r = requests.get(
        f"{BASE}/v2/mining/commodities/{commodity_name}/price/",
        headers=HEADERS, params=params, timeout=15,
    )
    r.raise_for_status()
    return r.json()


def commodity_exports(commodity_type: str, year: int, limit: int = 20) -> list[dict]:
    """
    Top export destinations for one commodity-year. Costs 1 credit.

    commodity_type enum: Coal, Copper, Gold  (NOTE: smaller set than commodity_name!)
    """
    r = requests.get(
        f"{BASE}/v2/mining/exports/",
        headers=HEADERS,
        params={"commodity_type": commodity_type, "year": year, "limit": limit},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# ---- Step 1: List coal mine owners (1 credit) ----
print("=== Step 1: Coal mine owners in Indonesia ===")
data = mining_companies(commodity_type="Coal", company_type="Mine Owner", limit=10)
print(f"  Total coal mine owners: {data['pagination']['total_count']}")
for row in data["results"][:5]:
    sym = row.get("symbol") or "(non-IDX)"
    print(f"    {row['slug']:<45} symbol={sym:<10} key_op={row.get('key_operation')}")
print()


# ---- Step 2: Detail for one (1 credit) ----
target_slug = "pt-adaro-indonesia"   # widely-known Indonesian coal operator
print(f"=== Step 2: Detail for {target_slug} ===")
detail = mining_company_detail(target_slug)
print(f"  Name: {detail.get('name')}")
print(f"  Listed: {detail.get('symbol') or 'No'}")
print(f"  Activities: {detail.get('activities')}")
print(f"  Commodities: {detail.get('commodity_type')}")
print(f"  Province: {detail.get('operation_province')}")
print(f"  License count: {len(detail.get('mining_license', []))}")
print(f"  Site count: {detail.get('mining_site_count')}")
print()


# ---- Step 3: Sites for that company, 2024, ranked by production (1 credit) ----
print(f"=== Step 3: Sites for {target_slug}, 2024, top by production ===")
sites = mining_sites(company=target_slug, year=2024, order_by="-production_volume", limit=5)
print(f"  Total sites (2024): {sites['pagination']['total_count']}")
for row in sites["results"][:5]:
    print(f"    {row['name']:<30} {row['province']:<20} "
          f"prod={row.get('production_volume')} {row.get('unit', '')}")
print()


# ---- Step 4: Coal price history (1 credit) ----
print("=== Step 4: Coal price, last 3 years (USD/ton) ===")
prices = commodity_price("coal", start_year=2023, end_year=2025)
print(f"  {len(prices)} monthly/bi-weekly points")
if prices:
    latest = prices[-1]
    earliest = prices[0]
    print(f"  Earliest ({earliest['date']}): USD {earliest['price_usd_per_ton']}/ton")
    print(f"  Latest   ({latest['date']}): USD {latest['price_usd_per_ton']}/ton")
print()


# ---- Step 5: Coal export destinations, 2024 (1 credit) ----
print("=== Step 5: Coal export destinations, 2024 ===")
exports = commodity_exports(commodity_type="Coal", year=2024, limit=10)
print(f"  Top {len(exports)} destinations:")
for row in exports[:5]:
    vol_bps = row.get("export_volume_bps")
    vol_esdm = row.get("export_volume_esdm")
    print(f"    {row['country']:<20} USD {row['export_usd']:>15,}  "
          f"BPS vol={vol_bps} {row.get('volume_unit', '')}  "
          f"ESDM vol={vol_esdm}")
print()


print("=== Total spent: 5 credits for the full coal vertical ===")
```

## Expected output shape

`/v2/mining/companies/` page:

```json
{
  "results": [
    {
      "slug": "pt-adaro-andalan-indonesia-tbk",
      "name": "PT Adaro Andalan Indonesia Tbk",
      "symbol": "AADI.JK",
      "company_type": "Holding",
      "key_operation": "Coal Trading",
      "commodity_type": ["Coal"]
    }
  ],
  "pagination": {"total_count": 366, "showing": 1, "limit": 30, "offset": 0, "has_next": true, ...}
}
```

`/v2/mining/companies/{slug}/` detail:

```json
{
  "name": "PT Adaro Andalan Indonesia Tbk",
  "slug": "pt-adaro-andalan-indonesia-tbk",
  "symbol": "AADI.JK",
  "company_type": "Holding",
  "operation_province": "Jakarta",
  "key_operation": "Coal Trading",
  "activities": ["Trading"],
  "commodity_type": ["Coal"],
  "mining_license": [
    {"license_type": "IUPK", "license_number": "11/1/IUP/PMA/2022",
     "wiup_code": "1300003032014132", "province": "Kalimantan Selatan",
     "city": "Kabupaten Tabalong", "license_effective_date": "2022-09-13",
     "license_expiry_date": "2032-10-01", "activity": "Operasi Produksi",
     "licensed_area_ha": 23942, "commodity_type": "Coal"}
  ],
  "mining_contract": [],
  "mining_site_count": 0
}
```

`/v2/mining/sites/` page:

```json
{
  "results": [
    {"name": "Tutupan Utara", "project_name": null, "year": 2024,
     "commodity_type": "Coal", "production_volume": null, "unit": "Mt",
     "strip_ratio": null, "province": "Kalimantan Selatan", "city": "Balangan",
     "company_slug": "pt-adaro-indonesia", "company_name": "PT Adaro Indonesia",
     "slug": "tutupan-utara"}
  ],
  "pagination": {...}
}
```

`/v2/mining/commodities/{name}/price/`:

```json
[{"name": "Coal", "date": "2024-01-01", "price_usd_per_ton": 125.85}]
```

`/v2/mining/exports/`:

```json
[
  {"country": "China", "export_usd": 6553700000,
   "export_volume_bps": 93.1649, "export_volume_esdm": null, "volume_unit": "Mt"}
]
```

## Pitfalls

- **Three different `commodity_type` enum sets** across endpoints:
  - `/v2/mining/companies/`: `Aluminium, Coal, Copper, Gold, Nickel, Silver, Zinc and Lead` (7)
  - `/v2/mining/sites/`: `Coal, Copper, Gold, Nickel` (4)
  - `/v2/mining/exports/`: `Coal, Copper, Gold` (3)
  - Different enums, different valid values — using a value from one set on another returns 400 (free).
- **Slug is the canonical address**, not symbol. Many mining entities have `symbol: null` (non-IDX-listed). Always address by `slug`.
- **Commodity name casing**: `/v2/mining/commodities/{name}/price/` is case-sensitive in some implementations — use lowercase (`coal`) when known safe, or fetch `/v2/mining/commodities/` (1 credit) to discover the canonical casing.
- **3-year max on price history** — going wider returns 400 (free).
- **`mining_company_detail` returns `mining_site_count: 0` for some companies** (Holding/Trading entities don't own sites directly). The `/v2/mining/sites/?company={slug}` call is the source of truth for "where does this company actually mine?".
- **`export_volume_bps` vs `export_volume_esdm`**: two government sources, values can differ (methodology). Always present both if your dashboard compares them.
- **`production_volume` can be `null`** for sites that haven't published production data — common for newly-licensed sites. Handle null gracefully.

## Variations

- **For Market Intel "Indonesia Mining Pulse"** — weekly cron:
  1. `commodity_price("coal", start_year=current-2, end_year=current)` → 1 credit (3-yr macro trend)
  2. `commodity_exports("Coal", year=last_complete_year)` → 1 credit (China/India/Japan destination split)
  3. `mining_sites(commodity_type="Coal", year=current_year, min_production=1000, order_by="-production_volume", limit=30)` → 1 credit (top 30 coal sites by volume)
  4. **Total**: 3 credits/week. Over 6 weeks: 18 credits. Very cheap.
- **For AI Agents**: wire each endpoint as a separate tool. Agent decides which to call based on user question. Always pass `commodity_type` enums from a single cached `/v2/mining/commodities/` call — agents shouldn't hardcode enum values.
- **For Automation anomaly detection** — compare this week's commodity price vs 30-day moving average. Alert when price drops >15% (could signal oversupply or policy change). Add `mining_licenses/?expiring_soon=true` (1 credit) for policy-tracking layer.
- **Beyond coal** — same pattern works for Nickel (Indonesia is #1 producer), Copper, Gold. Different `commodity_type` enum values per endpoint — re-check before reusing snippets.
- **Cross-reference with IDX screener** (example 01) — for IDX-listed mining companies like `AADI`, `PTBA`, `HRUM`, `BUMI`, `DOID`, `ADRO`, `BYAN`, `INCO`, `MDKA` — combine mining-side detail (licenses, sites) with IDX-side financials (example 02, sections=financials,valuation). Full picture in 3 credits per ticker.
