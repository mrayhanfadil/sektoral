# Benchmark IDX Banking Stocks with Python + Sectors API

> Source: <https://docs.sectors.app/recipes/stock-investing-and-finance/02-benchmarking-idx-banking-stocks-sectors-api>
> Author of original recipe: Alya Dwinanda, June 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Build a **repeatable, automated benchmarking workflow** for IDX bank stocks:

- Pull live quarterly financial data via the Sectors API v2.
- Compute four sector-relative metrics: **ROE, ROA, NIM, CIR**.
- Produce a comparison table + bar / bubble / heatmap charts.
- Re-run quarterly with one command.

## When to use this approach

- Your pitch focuses on **banking-sector analysis** (a Track 3 staple).
- You need a deterministic, refreshable artefact (vs. a one-off snapshot).
- You're benchmarking for an equity research report or a thesis.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | medium | Wrap the table in an LLM "explain BBCA vs BMRI" agent. |
| Track 2 — Automation | high | Schedule quarterly refresh, post to Slack. |
| Track 3 — Market intelligence / apps | **highest** | Polished benchmark dashboard = strong Track 3 deliverable. |

## Cost estimate

- 7 banks × 1 quarterly financials call = ~7 credits per run.
- ~1 credit for any universe-feed checks.
- Compute: seconds in pandas + matplotlib.

## Prerequisites

- Python 3.9+
- `pip install requests pandas matplotlib numpy`
- Insider-plan Sectors API key.

## The 7-bank universe

The recipe picks the Big Four state banks + one Sharia bank + two mid-caps:

```python
BANKS = [
    {"symbol": "BBCA", "name": "Bank Central Asia"},
    {"symbol": "BBRI", "name": "Bank Rakyat Indonesia"},
    {"symbol": "BMRI", "name": "Bank Mandiri"},
    {"symbol": "BBNI", "name": "Bank Negara Indonesia"},
    {"symbol": "BRIS", "name": "Bank Syariah Indonesia"},
    {"symbol": "BNGA", "name": "Bank CIMB Niaga"},
    {"symbol": "MEGA", "name": "Bank Mega"},
]
```

Tweak freely: swap `BNGA`/`MEGA` for `ARTO`/`BBSI` (digital-native) if your pitch emphasises digital banking.

## Fetch quarterly financials

```python
import requests

API_KEY = "<your_sectors_api_key>"
HEADERS = {"Authorization": API_KEY}

def get_quarterly(symbol, n=4):
    """
    Fetch the last n quarters of financial data for one IDX bank.
    Uses /v2/company/quarterly-financials/{symbol}/?n_quarters={n}.
    Returns a list of quarterly dicts, most recent first.
    """
    url = f"https://api.sectors.app/v2/company/quarterly-financials/{symbol}/"
    r = requests.get(url, headers=HEADERS, params={"n_quarters": n})
    r.raise_for_status()
    return r.json()
```

## Compute TTM and banking-specific metrics

```python
import pandas as pd

def compute_metrics(quarters, company_name):
    """
    TTM metrics = sum of last 4 quarters (income statement items).
    Balance sheet metrics = latest quarter only (point-in-time).
    """
    latest = quarters[0]

    def safe_sum(key):
        return sum(q.get(key) or 0 for q in quarters)

    def sector_sum(key):
        return sum((q.get("financials_sector_metrics") or {}).get(key) or 0 for q in quarters)

    ttm_revenue  = safe_sum("revenue")
    ttm_earnings = safe_sum("earnings")
    ttm_nii      = sector_sum("net_interest_income")
    ttm_opex     = safe_sum("operating_expense")
    assets       = latest.get("total_assets") or 0
    equity       = latest.get("total_equity") or 0

    return {
        "Ticker":       latest["symbol"].replace(".JK", ""),
        "Company":      company_name,
        "As of":        latest["date"],
        "Revenue (T)":  ttm_revenue / 1e12,
        "Earnings (T)": ttm_earnings / 1e12,
        "Total Assets (T)": assets / 1e12,
        "Total Equity (T)": equity / 1e12,
        "ROE %":        100 * ttm_earnings / equity if equity else None,
        "ROA %":        100 * ttm_earnings / assets if assets else None,
        "NIM %":        100 * ttm_nii / assets if assets else None,    # approximation
        "CIR %":        100 * ttm_opex / ttm_revenue if ttm_revenue else None,
    }

rows = []
for b in BANKS:
    try:
        quarters = get_quarterly(b["symbol"], n=4)
        rows.append(compute_metrics(quarters, b["name"]))
    except Exception as e:
        print(f"Failed: {b['symbol']}: {e}")

df = pd.DataFrame(rows)
print(df.round(2).to_string(index=False))
```

The `financials_sector_metrics.net_interest_income` field is bank-specific. For non-bank sectors it doesn't exist — `sector_sum` returns 0. The recipe relies on the Sectors API to populate the bank-specific fields for financial-sector companies.

## Composite score

Rank banks on each axis, then average ranks into a single composite score:

```python
def composite_score(df):
    df = df.copy()
    df["ROE_rank"]  = df["ROE %"].rank(ascending=True)
    df["ROA_rank"]  = df["ROA %"].rank(ascending=True)
    df["NIM_rank"]  = df["NIM %"].rank(ascending=True)
    df["CIR_rank"]  = df["CIR %"].rank(ascending=False)    # lower CIR = better
    n = len(df)
    df["Score"] = ((df["ROE_rank"] + df["ROA_rank"] + df["NIM_rank"] + df["CIR_rank"]) / (4 * n) * 100).round(1)
    return df.sort_values("Score", ascending=False)

print(composite_score(df)[["Ticker", "Company", "ROE %", "ROA %", "NIM %", "CIR %", "Score"]].to_string(index=False))
```

Score range: 0 (worst on all axes) to 100 (best on all axes). Equal weighting across four axes — easy to defend in a slide.

## Three publication-ready charts

### Bar chart — 4 metrics side by side

```python
import matplotlib.pyplot as plt
import numpy as np

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
metrics = [("ROE %", axes[0, 0], "Return on Equity"),
           ("ROA %", axes[0, 1], "Return on Assets"),
           ("NIM %", axes[1, 0], "Net Interest Margin"),
           ("CIR %", axes[1, 1], "Cost-to-Income Ratio")]
for col, ax, title in metrics:
    sorted_df = df.sort_values(col)
    ax.barh(sorted_df["Ticker"], sorted_df[col], color="steelblue")
    ax.set_title(title)
    ax.set_xlabel(col)
plt.tight_layout()
plt.savefig("bank_metrics_bars.png", dpi=150)
```

### Bubble chart — NIM vs ROE, sized by total assets

```python
fig, ax = plt.subplots(figsize=(10, 7))
scatter = ax.scatter(df["NIM %"], df["ROE %"], s=df["Total Assets (T)"] * 100,
                     alpha=0.6, c=df["CIR %"], cmap="RdYlGn_r")
for _, row in df.iterrows():
    ax.annotate(row["Ticker"], (row["NIM %"], row["ROE %"]), fontsize=10)
ax.set_xlabel("Net Interest Margin (%)")
ax.set_ylabel("Return on Equity (%)")
ax.set_title("IDX Banks — NIM vs ROE (bubble size = total assets, colour = CIR)")
plt.colorbar(scatter, label="CIR % (green = efficient)")
plt.savefig("bank_bubble.png", dpi=150)
```

### Heatmap — bank × metric

```python
import seaborn as sns

heatmap_df = df.set_index("Ticker")[["ROE %", "ROA %", "NIM %", "CIR %"]]
# Z-score per column for cross-bank comparison
heatmap_z = (heatmap_df - heatmap_df.mean()) / heatmap_df.std()

fig, ax = plt.subplots(figsize=(8, 6))
sns.heatmap(heatmap_z, annot=True, fmt=".2f", cmap="RdYlGn", center=0, ax=ax)
ax.set_title("IDX Banks — Metric Z-Scores (green = above average)")
plt.tight_layout()
plt.savefig("bank_heatmap.png", dpi=150)
```

## Automation

- **Schedule quarterly refresh** — cron job on the day after each bank's earnings release. Archive each output CSV with a datestamp to build a historical benchmarking database.
- **Extend to regional BPD banks** — swap in `BJBR` (Bank Jabar Banten), `BJTM` (Bank Jatim), `BDKR` (Bank DKI) for regional-development-bank analysis.
- **MCP variant** — the same workflow is achievable conversationally via the Sectors MCP server. See `references/mcp/setup.md` (Lane 2).

## Known pitfalls

- **TTM aggregation pitfall**: `sum(revenue)` over 4 quarters is the TTM. But **balance-sheet items** (total_assets, total_equity) are point-in-time — use only the **latest** quarter, not the sum.
- **`financials_sector_metrics`** is bank-specific. If `get_quarterly(symbol)` for a non-bank doesn't include this field, `sector_sum` returns 0, and NIM shows as 0. Filter to banks.
- **NIM approximation**: the recipe divides TTM net interest income by latest total assets. The textbook definition divides NII by **average** total assets (mean of 4 quarter-ends). Close enough for hackathon purposes; flag in your slide deck.
- **CIR (Cost-to-Income Ratio)**: definition varies. This recipe uses operating expenses / revenue. Some banks use operating expenses / net interest income + non-interest income. Cross-check before publishing.
- **`total_assets` may be null** for some bank reports. Always wrap in `or 0` or guard with `if total_assets else None`.
- **Quarterly timing**: banks report at different times. TTM comparisons only make sense if all 7 banks reported within ~2 weeks of each other. If `As of` dates vary wildly, your chart will mislead.
- **Endpoint changes**: `/v2/company/quarterly-financials/{symbol}/?n_quarters=4` — confirm against the live docs before shipping. The recipe works as of Aug 2026.

## Cross-links

- Portfolio optimiser (different angle on the same data): [`portfolio-optimization.md`](portfolio-optimization.md)
- REST endpoint catalog: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)
- Visualisation in R: [`r-animations.md`](r-animations.md)
- Streamlit dashboard wrapping the table: [`sectorscan-part2.md`](sectorscan-part2.md)