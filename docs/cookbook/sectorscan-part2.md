# SectorScan Part 2 — Building a Financial Intelligence App with Streamlit

> Source: <https://docs.sectors.app/recipes/build-python-app/sectorscan/02-sectorscan-part2>
> Author of original recipe: Aurellia Christie, May 2024
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Take the Part 1 ([`sectorscan-part1.md`](sectorscan-part1.md)) notebook and turn it into a **deployable Streamlit app** — multi-select sectors, three tabs (Market Cap / Valuation / Top Companies), published to Streamlit Cloud for free.

## When to use this approach

- You have a working Python notebook (Part 1) and want to ship it as a real web app.
- Your audience can't or won't run Python locally.
- You want free hosting (Streamlit Cloud free tier).

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | low | No LLM. |
| Track 2 — Automation | medium | Auto-refresh on schedule. |
| Track 3 — Market intelligence / apps | **highest** | Live web app = canonical Track 3 deliverable. |

## Cost estimate

Streamlit Cloud: free for public apps. Sectors API: same ~5–10 credits per session because of `@st.cache_data`. Hosting cost: $0.

## Setup

```bash
pip install streamlit==1.35.0
# creates sectorscan/sectorscan.py
mkdir sectorscan && cd sectorscan
touch sectorscan.py
mkdir .streamlit && touch .streamlit/secrets.toml
```

In `.streamlit/secrets.toml`:

```toml
SECTORS_KEY = "your_sectors_api_key"
```

`.streamlit/secrets.toml` must be in `.gitignore`. The full source of `sectorscan.py` lives at <https://github.com/AurelliaChristie/sectorscan>.

## The skeleton

```python
import streamlit as st
import pandas as pd
import requests
import altair as alt

st.set_page_config(page_title="SectorScan", layout="wide")
st.title("SectorScan")
st.write("Compare IDX sectors on market cap, valuation, and top companies.")
```

Run it:

```bash
streamlit run sectorscan.py
# → opens http://localhost:8501
```

`Ctrl+C` to stop.

## Caching + error handling

```python
@st.cache_data(ttl=3600)  # cache for 1 hour
def fetch_data(url: str):
    headers = {"Authorization": st.secrets["SECTORS_KEY"]}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    st.error("Error: Something went wrong. Please reload the app.")
    return None
```

- `@st.cache_data` prevents hitting Sectors on every page rerun (Streamlit reruns the entire script on every widget change).
- `st.error` surfaces API failures without crashing the app. For a hackathon demo this is enough; for production add retry-with-backoff.
- `ttl=3600` refreshes the cache every hour. For intraday use cases, drop to `ttl=600`.

## Sector multi-select

```python
sectors_raw = fetch_data("https://api.sectors.app/v2/subsectors/")
sectors     = sorted({item["subsector"] for item in sectors_raw})

selected = st.multiselect(
    "Pick sectors to compare",
    options=sectors,
    default=["banks", "consumer-non-cyclicals"],
)
```

`multiselect` returns a Python list. Pass it to the chart-building functions from Part 1.

## Three tabs

```python
tab1, tab2, tab3 = st.tabs(["Market Cap", "Valuation", "Top Companies"])

with tab1:
    if selected:
        rows = []
        for s in selected:
            data = fetch_data(f"https://api.sectors.app/v2/subsector/report/{s}/?sections=market_cap")
            if data:
                rows.append({"subsector": s, "total_tcap": data["market_cap"]["total_market_cap"] / 1e12})
        df = pd.DataFrame(rows)
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X("subsector:N", sort="-y"),
            y=alt.Y("total_tcap:Q", title="Market Cap (Trillion IDR)"),
            color="subsector:N",
        )
        st.altair_chart(chart, use_container_width=True)

with tab2:
    # similar pattern — fetch /v2/subsector/report/{s}/?sections=valuation
    ...

with tab3:
    # similar — fetch /v2/companies/?sub_sector={s}&order_by=-market_cap&limit=10
    ...
```

Streamlit reruns the whole script on every widget change. `@st.cache_data` keeps API calls cheap.

## Known pitfalls

- **Secrets in git**: never commit `.streamlit/secrets.toml`. Add it to `.gitignore` on day one.
- **`st.secrets` only works in Streamlit**: when testing locally outside Streamlit (e.g. plain `python sectorscan.py`), `st.secrets["SECTORS_KEY"]` raises `FileNotFoundError`. Use `os.getenv("SECTORS_KEY")` as fallback, or always launch via `streamlit run`.
- **Streamlit version drift**: `streamlit==1.35.0` is the version in the original recipe. Some APIs (`st.cache_data`, `st.set_page_config`) have changed across releases. Pin your version in `requirements.txt`.
- **`st.altair_chart` chart size**: pass `use_container_width=True` for responsive layout. Without it the chart is a fixed pixel width and looks terrible on wide screens.
- **Streamlit Cloud deploy**: secrets are set in the Streamlit Cloud dashboard, not in a committed file. Settings → Secrets → paste `SECTORS_KEY="..."` in TOML.
- **Free tier limits**: Streamlit Cloud free apps sleep after 7 days of inactivity. For a demo, that's fine. For a persistent portfolio tracker, switch to a paid tier or self-host.
- **Cache key collision**: `@st.cache_data` uses the function's arguments as the cache key. If your URL string changes per request (e.g. timestamp), the cache misses every time. Use stable URL patterns — `?start=YYYY-MM-DD&end=YYYY-MM-DD` is fine because the dates repeat daily.

## Deploy to Streamlit Cloud (free)

1. Push the `sectorscan/` folder to a GitHub repo.
2. Go to <https://share.streamlit.io>, sign in with GitHub.
3. Click **New app** → pick the repo + branch + `sectorscan.py`.
4. **Advanced settings → Secrets** → paste your TOML secrets.
5. **Deploy!** — your app is live at `https://<your-username>-sectorscan.streamlit.app/`.

The first deploy takes 2–5 minutes. Subsequent deploys are faster (just rebuilds the Docker image).

## Build-quality checklist

- [ ] App loads within 5 seconds on a cold cache.
- [ ] Empty-state: when no sectors are selected, charts don't error — show a hint instead.
- [ ] API failures show a friendly `st.error` banner, not a stack trace.
- [ ] Mobile responsive (Streamlit default is OK; check on a phone).
- [ ] README tab in the app explaining what data sources are used (`st.markdown` block).

## Going beyond

Things to extend for a stronger Track 3 submission:

- Add a **time-series view**: instead of only the latest market cap, fetch 12 quarters and let the user scrub through.
- Add **screener integration**: let the user type "top 10 banks by ROE" and render an interactive table.
- Add **broker-summary** tab: top buyers/sellers per stock from `/v2/brokers/broker-summary/top/{symbol}/`.
- Add **foreign flow** tab: 30-day net foreign inflow for selected stocks.
- Add **Streamlit auth** (paid plan only) if you want a private portfolio tracker.

## Cross-links

- Data exploration notebook: [`sectorscan-part1.md`](sectorscan-part1.md)
- REST endpoints: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)
- Anomaly detection alternative (different shape): [`gnn-anomaly-1.md`](gnn-anomaly-1.md)
- Animated charts in R: [`r-animations.md`](r-animations.md)