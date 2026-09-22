# SectorScan Part 1 — Financial Data Visualization

> Source: <https://docs.sectors.app/recipes/build-python-app/sectorscan/01-sectorscan-part1>
> Author of original recipe: Aurellia Christie, May 2024
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Build the **SectorScan** Python app: a financial analytics tool that lets the user pick IDX sectors, then compares **market cap**, **valuation**, and **top companies** across the selection. Uses `streamlit` for the web UI and `altair` for the charts.

This file covers **Part 1** — data exploration in a notebook. Part 2 ([`sectorscan-part2.md`](sectorscan-part2.md)) wires it into a real Streamlit app.

## When to use this approach

- You want a **Python app** (not a spreadsheet, not a no-code tool) that the team can extend.
- Your audience is technical but small — analysts who can run `streamlit run` and have Python on their laptop.
- You're building a **Track 3** (market intelligence app) submission.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | low | Static visualisation, no LLM. |
| Track 2 — Automation | low | Manual user interaction only. |
| Track 3 — Market intelligence / apps | **highest** | Streamlit dashboard = canonical market-intel app. |

## Cost estimate

Part 1 is read-only on a handful of sectors and is cheap (~10–15 credits to fetch the sector universe once). Part 2 with `@st.cache_data` is even cheaper per session.

## Prerequisites

- Python 3.x
- `streamlit==1.35.0` (pin the version — newer releases have changed APIs)
- `pip install streamlit` will pull `pandas`, `requests`, `altair` automatically
- Sectors API key in `st.secrets` or `.env`

## The data

### Sector universe

```
GET https://api.sectors.app/v2/subsectors/
```

Returns a list of `[{sector, subsector}, ...]` pairs. The `subsector` field is the kebab-case slug you pass to the subsector-report endpoint.

```python
import requests

def fetch_data(url):
    headers = {"Authorization": "<your_api_key>"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    raise Exception(f"API request failed with status code {response.status_code}")

data    = fetch_data("https://api.sectors.app/v2/subsectors/")
sectors = sorted({item['subsector'] for item in data})
# ['banks', 'basic-materials', 'energy', 'financing-service', ...]
```

### Per-subsector market cap

```
GET https://api.sectors.app/v2/subsector/report/{subsector}/?sections=market_cap
```

Returns a `market_cap` block with:

```json
{
  "sector": "Financials",
  "sub_sector": "Banks",
  "market_cap": {
    "total_market_cap": 46765349582848.0,
    "avg_market_cap": 3117689972189.87,
    "quarterly_market_cap": {
      "prev_ttm_mcap":   {"2022.Q2": 39870000000000, ...},
      "current_ttm_mcap":{"2023.Q2": 53724000000000, ...},
      "current_ttm_mcap_pavg": {"2023.Q2": 293918156250000.0, ...}
    }
  }
}
```

The `current_ttm_mcap_pavg` field is **price-averaged market cap** — better for time-series comparison than raw `total_market_cap` because it adjusts for share price swings.

### Per-subsector valuation

```
GET https://api.sectors.app/v2/subsector/report/{subsector}/?sections=valuation
```

Returns aggregate P/E, P/B, dividend yield, etc. for the subsector.

### Top companies per subsector

```
GET https://api.sectors.app/v2/companies/?sub_sector={subsector}&order_by=-market_cap&limit=10
```

Use this to get the top 10 companies by market cap within a subsector. `sub_sector` is the kebab-case slug; `order_by` accepts `-field` for descending. Combine with `year=YYYY` for point-in-time ranking.

## Three charts (the app's core)

### Chart 1 — Market Cap by Sector

Bar chart, `total_market_cap` per sector in the user's selection. Trillions of IDR for readability.

```python
import altair as alt
import pandas as pd

df_mc = pd.DataFrame([
    {"subsector": s, "market_cap_trillions": total / 1e12}
    for s in selected_sectors
    for total in [fetch_data(f"https://api.sectors.app/v2/subsector/report/{s}/?sections=market_cap")["market_cap"]["total_market_cap"]]
])

chart_mc = alt.Chart(df_mc).mark_bar().encode(
    x=alt.X("subsector:N", sort="-y"),
    y=alt.Y("market_cap_trillions:Q", title="Market Cap (Trillion IDR)"),
    color=alt.Color("subsector:N", legend=None),
    tooltip=["subsector", alt.Tooltip("market_cap_trillions:Q", format=",.2f")],
).properties(title="Total Market Cap by Sector", width=700, height=400)
chart_mc
```

### Chart 2 — Valuation Comparison

Line chart over time, one line per sector, showing price-averaged market cap as a proxy for "how the sector has grown".

For per-stock valuation, fetch `company/report/{symbol}/?sections=valuation` and plot `pe_ratio`, `pb_ratio`, `dividend_yield`.

### Chart 3 — Top Companies

Bar chart of top 10 stocks by revenue / profit / market cap in the selected subsector.

```python
df_top = pd.DataFrame([
    {"symbol": c["symbol"], "revenue_trillions": c["revenue"][year] / 1e12}
    for c in fetch_data(f"https://api.sectors.app/v2/companies/?sub_sector={s}&order_by=-revenue[{year}]&limit=10")
])

chart_top = alt.Chart(df_top).mark_bar().encode(
    x=alt.X("revenue_trillions:Q", title=f"Revenue {year} (Trillion IDR)"),
    y=alt.Y("symbol:N", sort="-x"),
    tooltip=["symbol", alt.Tooltip("revenue_trillions:Q", format=",.2f")],
).properties(title=f"Top 10 Companies by Revenue in {s}", width=700, height=400)
chart_top
```

## Wiring it into a notebook (Colab / Jupyter)

```python
# Cell 1 — imports + setup
import requests, pandas as pd, altair as alt
API_KEY = "<your_api_key>"
HEADERS = {"Authorization": API_KEY}

def fetch(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

# Cell 2 — sector universe
sectors = sorted({s["subsector"] for s in fetch("https://api.sectors.app/v2/subsectors/")})

# Cell 3 — selected sectors
selected = ["banks", "basic-materials", "energy", "consumer-non-cyclicals"]

# Cell 4 — market cap
mc = {s: fetch(f"https://api.sectors.app/v2/subsector/report/{s}/?sections=market_cap") for s in selected}
df_mc = pd.DataFrame([{"subsector": s, "total_tcap": v["market_cap"]["total_market_cap"]/1e12} for s, v in mc.items()])

# Cell 5 — chart
alt.Chart(df_mc).mark_bar().encode(
    x=alt.X("subsector:N", sort="-y"),
    y="total_tcap:Q",
    color="subsector:N",
).properties(width=700, height=400)
```

That's the entire data layer. Part 2 ([`sectorscan-part2.md`](sectorscan-part2.md)) wires these charts into a Streamlit UI with sector multi-select.

## Known pitfalls

- **`total_market_cap` vs `current_ttm_mcap_pavg`**: raw total cap moves with price (so a sector crash looks like a "shrink"). Use `current_ttm_mcap_pavg` for trend charts. Use `total_market_cap` for snapshot comparisons.
- **Banks vs insurance financial shape**: `subsector/report/{sub_sector}/?sections=financials` returns different fields for banks (`net_interest_income`, `gross_loan`, `total_deposit`) vs other sectors. When comparing, filter to common fields (revenue, earnings, total_assets) unless you specifically want banking metrics.
- **`sub_sector` vs `subsector`**: the endpoint path uses `sub_sector` (with underscore). The JSON keys also use `sub_sector`. The kebab-case slug value comes from the `subsectors/` endpoint's `subsector` field. Don't mix them up — `sub_sector: banks` is correct, `subsector: banks` is correct, but `sub-sector: banks` is wrong.
- **Year field in `revenue[YYYY]`**: bracket notation is supported in `where` and `order_by`. Use the fiscal year, not the calendar year — companies report on different schedules.
- **Top-N consistency**: `order_by=-revenue[2023]` ranks by 2023 reported revenue. If you mix years across sectors you'll get inconsistent comparisons.

## Cross-links

- Streamlit UI: [`sectorscan-part2.md`](sectorscan-part2.md)
- Equivalent Streamlit app pattern with `st.cache_data`: [`sectorscan-part2.md`](sectorscan-part2.md#caching--error-handling)
- REST endpoint catalog: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)
- Other visualisation: [`r-animations.md`](r-animations.md)