# GNN Anomaly Detection — Part 3: Confirmation with Broker and Foreign Flow

> Source: <https://docs.sectors.app/recipes/gnn-anomaly-detection/03-gnn-part-3>
> Author of original recipe: Alya Dwinanda, June 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Validate the GNN anomaly scores from Part 2 against **two independent market signals**:

1. **Broker flow** — top accumulators/distributors for each stock (`/v2/brokers/broker-summary/top/{symbol}/`).
2. **Foreign flow** — daily net foreign inflow (`/v2/brokers/foreign-flow/{symbol}/?start=...&end=...`).

Combine into a single **adaptive risk score**.

## Why confirmation matters

A GNN reconstruction error is a *statistical* signal — it tells you the stock's behaviour was inconsistent with its graph context. It does not tell you whether that inconsistency reflects a real market event or a modelling artefact.

Broker flow and foreign flow are *transaction-grounded* signals. When three independent signals converge (high GNN score + broker distribution + foreign outflow), the evidence is much stronger than any single signal.

## Cell 11 — Data quality audit

Before fetching confirmation signals, audit `result_df`:

```python
numeric_feat_cols = [
    "mean_return", "volatility", "skewness", "kurtosis",
    "max_return_zscore", "n_extreme_days", "max_volume_zscore",
    "n_volume_spikes", "price_vs_sma20", "vol_regime_ratio", "sharpe_ratio",
]

# All-zero features = suspended stock with no data in window
zero_mask         = (result_df[numeric_feat_cols] == 0).all(axis=1)
zero_data_tickers = result_df[zero_mask]["ticker"].tolist()

# Duplicated anomaly scores = identical zero vectors
score_counts = result_df["anomaly_score"].value_counts()
duplicated   = score_counts[score_counts > 1]

# Drop zero-data stocks from downstream
result_df_clean        = result_df[~zero_mask].copy().reset_index(drop=True)
active_tickers_clean   = result_df_clean["ticker"].tolist()
anomaly_tickers_clean  = result_df_clean[result_df_clean["is_anomaly"]]["ticker"].tolist()

# Borderline = above p75 but not flagged anomaly
p75_clean  = result_df_clean["anomaly_score"].quantile(0.75)
borderline = result_df_clean[
    (result_df_clean["anomaly_score"] > p75_clean) &
    (~result_df_clean["is_anomaly"])
].sort_values("anomaly_score", ascending=False)

# Targets = anomalies + borderline (these get the most attention)
TARGET_TICKERS_BROKER = anomaly_tickers_clean + borderline["ticker"].tolist()
```

In the original run, `WIKA` and `WSKT` were all-zero (suspended during the analysis window). Both had identical anomaly scores because the model processed them as identical zero vectors. They were dropped before broker analysis.

Always run this audit before downstream — a suspended stock that stays in the graph can pull other nodes toward its zero embedding and distort clustering.

## Cell 12 — Broker flow analysis

```python
def fetch_broker_summary(symbol, start, end, n_brokers=20):
    """Top accumulators/distributors for one symbol."""
    url = f"{BASE_URL}/brokers/broker-summary/top/{symbol}/"
    params = {"start": start, "end": end, "n_brokers": n_brokers}
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        return None
    return resp.json()

broker_data = {}
for t in TARGET_TICKERS_BROKER:
    data = fetch_broker_summary(t, START_DATE, END_DATE)
    if data:
        accumulators = data.get("top_buyers", [])
        distributors = data.get("top_sellers", [])
        net_buy_value  = sum(b.get("net_value", 0) for b in accumulators)
        net_sell_value = sum(b.get("net_value", 0) for b in distributors)
        broker_data[t] = {
            "broker_net_total":  net_buy_value + net_sell_value,    # <0 = net distribution
            "broker_net_buy":    net_buy_value,
            "broker_net_sell":   net_sell_value,
            "n_accumulators":    len(accumulators),
            "n_distributors":    len(distributors),
            "top_buyer":         accumulators[0]["broker_code"] if accumulators else None,
            "top_seller":        distributors[0]["broker_code"] if distributors else None,
        }
```

Build a normalised **broker dominance score** per stock (cross-sectional):

```python
broker_df = pd.DataFrame(broker_data).T
broker_df["broker_score"] = (
    broker_df["broker_net_total"]
    .rank(pct=True)             # 0 = most distributed, 1 = most accumulated
)

# Join into the master result
result_df_clean["broker_net_total"] = result_df_clean["ticker"].map(
    broker_df["broker_net_total"]
)
result_df_clean["broker_score"]     = result_df_clean["ticker"].map(
    broker_df["broker_score"]
)
```

**Use `.map()`, not `.merge()`**, for signal injection — `.map()` is faster on Series index lookups and avoids accidental column-name collisions.

## Cell 13 — Foreign flow analysis

```python
def fetch_foreign_flow(symbol, start, end):
    """Daily net foreign inflow (IDR) for one symbol."""
    url = f"{BASE_URL}/brokers/foreign-flow/{symbol}/"
    params = {"start": start, "end": end}
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        return None
    return resp.json()

foreign_data = {}
for t in TARGET_TICKERS_BROKER:
    data = fetch_foreign_flow(t, START_DATE, END_DATE)
    if data:
        # Sum daily net_foreign_inflow over the window
        total_inflow = sum(d.get("net_foreign_inflow", 0) for d in data)
        foreign_data[t] = {
            "foreign_net_total": total_inflow,         # <0 = net selling
            "foreign_n_days":    len(data),
        }

foreign_df = pd.DataFrame(foreign_data).T
foreign_df["foreign_score"] = foreign_df["foreign_net_total"].rank(pct=True)
```

## Cell 14 — Combined risk score

The three signals live on different scales. Use rank-percentile so each contributes equally:

```python
result_df_clean["gnn_score"]      = result_df_clean["anomaly_score"].rank(pct=True)
result_df_clean["foreign_score"]  = result_df_clean["ticker"].map(foreign_df["foreign_score"])
result_df_clean["broker_score"]   = result_df_clean["ticker"].map(broker_df["broker_score"])

# Adaptive weights — give more weight to broker + foreign for high-GNN-score stocks
def adaptive_weight(gnn_pct):
    # When GNN score is high, broker/foreign confirmation matters more
    # When GNN score is low, the signal is noise — dampen everything
    return min(1.0, gnn_pct * 2)

result_df_clean["risk_score"] = result_df_clean.apply(
    lambda r: adaptive_weight(r["gnn_score"]) * (
        0.4 * r["gnn_score"]
        + 0.3 * (1 - r["broker_score"])    # low broker_score = distribution → risk ↑ when inverted
        + 0.3 * (1 - r["foreign_score"])
    ),
    axis=1,
)

result_df_clean.sort_values("risk_score", ascending=False)[[
    "ticker", "anomaly_score", "gnn_score", "broker_net_total",
    "foreign_net_total", "risk_score"
]].head(10)
```

The combined score is dimensionless, rank-normalised 0–1. The "adaptive weight" means a stock with a low GNN score gets a dampened risk score even if broker/foreign look bad — preventing false positives.

## Cell 15 — Render the final risk dashboard

Plot a 2D scatter: GNN score (x) vs broker-net (y), sized by combined risk score, coloured by foreign net flow. Anomalies (high GNN) in the bottom-left quadrant (distribution + foreign selling) are the most actionable.

```python
fig, ax = plt.subplots(figsize=(12, 8))
scatter = ax.scatter(
    result_df_clean["gnn_score"],
    result_df_clean["broker_score"],
    s=200 + 1000 * result_df_clean["risk_score"],
    c=result_df_clean["foreign_score"],
    cmap="RdYlGn",
    alpha=0.7,
)
for _, row in result_df_clean.iterrows():
    ax.annotate(row["ticker"], (row["gnn_score"], row["broker_score"]), fontsize=8)
ax.axhline(0.5, color="grey", linestyle="--")
ax.axvline(0.5, color="grey", linestyle="--")
ax.set_xlabel("GNN Anomaly Score (percentile)")
ax.set_ylabel("Broker Net Score (1 = accumulation)")
ax.set_title("Combined Risk Dashboard")
plt.colorbar(scatter, label="Foreign Flow Score (green = inflow)")
plt.savefig("risk_dashboard.png", dpi=150)
```

## Summary across the three parts

| Part | Output |
|------|--------|
| 1 | `feat_tensor`, `graph_data`, `model` (untrained) |
| 2 | `anomaly_scores`, `embeddings`, `kmeans_labels`, `dbscan_labels` |
| 3 | `risk_score` (combined), broker/foreign confirmation, data-quality audit |

The key insight: **no single signal is sufficient**. A high GNN score with no broker or foreign confirmation may reflect a real but internally-driven event. A high GNN score with broker distribution + foreign outflow is a convergence of evidence worth investigating.

## Known pitfalls

- **Empty broker/foreign responses**: stocks listed recently or suspended for part of the window return no data. Filter those out before computing scores.
- **HTTP 400 on broker endpoint**: `START_DATE`/`END_DATE` should be within the supported range. `/v2/brokers/broker-summary/top/{symbol}/` accepts up to ~14 days per call; longer windows need paginated calls.
- **Identical anomaly scores** = always means zero-feature nodes. Audit before broker/foreign analysis.
- **`.map()` not `.merge()`** for signal injection: avoids accidental column collisions and is faster.
- **Foreign flow endpoint**: `/v2/brokers/foreign-flow/{symbol}/?start=...&end=...` returns up to 90 days. If you want 180 days, you have to paginate.
- **Date alignment**: Sectors API returns daily timestamps. Make sure your `START_DATE`/`END_DATE` cover the same window as Part 1. A mismatch silently produces misleading scores.

## Cross-links

- Setup + model: [`gnn-anomaly-1.md`](gnn-anomaly-1.md)
- Train + score + cluster: [`gnn-anomaly-2.md`](gnn-anomaly-2.md)
- Streamlit wrapper to display results: [`sectorscan-part2.md`](sectorscan-part2.md)
- Broker endpoints reference: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)