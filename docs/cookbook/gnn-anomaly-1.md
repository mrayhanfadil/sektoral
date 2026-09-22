# GNN Anomaly Detection — Part 1: Setup, Data, and Model

> Source: <https://docs.sectors.app/recipes/gnn-anomaly-detection/01-gnn-part-1>
> Author of original recipe: Alya Dwinanda, June 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Build a **Graph Neural Network** that flags anomalous IDX stocks relative to their peers. By the end of Part 1 you have:

- A 180-day price/volume dataset fetched from Sectors.
- An 11-feature matrix per stock.
- A return-correlation graph.
- A Graph Variational Autoencoder (GVAE) ready to train.

Part 2 trains it. Part 3 validates against broker + foreign flow signals.

## When to use this approach

- You want to demonstrate **machine learning on financial graph data** — unusual for a hackathon, very strong Track 1 / Track 3 artefact.
- You're comfortable with PyTorch + PyTorch Geometric. CPU training is fine; GPU speeds it up.
- The story you tell is "stocks don't move in isolation — anomalies show up as peers don't behave like them".

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents / assistants | high | The GNN is the model. Pair with an LLM summariser for narrative output. |
| Track 2 — Automation workflows | medium | Schedule the notebook daily and post anomalies to Discord. |
| Track 3 — Market intelligence / apps | high | A "live anomaly radar" with explanations is a strong Track 3 deliverable. |

## Cost estimate

- Sectors API per training run: ~50 credits (1 universe-feed + 40 daily feeds).
- LLM (optional, Part 3): $0.01 per anomaly write-up.
- GPU vs CPU: model is tiny (~16K parameters, GVAE with 64-dim hidden, 32-dim latent) — CPU trains 200 epochs in ~3 minutes on a modern laptop. No GPU required.

## Prerequisites

```bash
pip install torch torch-geometric pandas numpy scikit-learn requests \
            matplotlib seaborn networkx
```

Set your API key:

```bash
export SECTORS_API_KEY="your_api_key_here"
```

## Why a GNN, not an autoencoder

Traditional anomaly detection treats each stock as an independent time series — isolation forests, z-scores, vanilla autoencoders. They miss a fundamental property of equity markets: stocks are correlated, and the most informative anomalies are stocks behaving unusually *relative to their correlated peers*.

A **Graph Variational Autoencoder** (GVAE) reframes the question: *"is this stock unusual compared to what its graph neighbors would predict?"*. A bank stock that diverges from every other bank stock is anomalous in the graph sense even if its standalone stats look fine.

Architecture:

```
Encoder:  GCN(input_dim → 64 hidden → 32 latent)  — 2 layers
Decoder:  inner-product reconstruction of features
Loss:     MSE(recon) + KL(q(z|x,A) || N(0,I))
Score:    per-node MSE → top 10% = anomaly
```

## Notebook structure

```
Cell 1 — Imports + hyperparameter config
Cell 2 — Fetch ticker universe + per-ticker daily data
Cell 3 — Feature engineering (11 features per stock)
Cell 4 — Return-correlation graph
Cell 5 — Model definition (GVAE)
```

Cells 6–8 (training, scoring, clustering) live in Part 2. Cells 9–11 (data quality, broker flow, foreign flow, combined risk score) live in Part 3.

## Cell 1 — Config

```python
import os, warnings, numpy as np, pandas as pd, networkx as nx
import matplotlib.pyplot as plt, seaborn as sns
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
import torch, torch.nn as nn, torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv, VGAE

warnings.filterwarnings("ignore")

SECTORS_API_KEY = os.environ.get("SECTORS_API_KEY", "YOUR_API_KEY_HERE")
BASE_URL        = "https://api.sectors.app/v2"
HEADERS         = {"Authorization": SECTORS_API_KEY}

START_DATE = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
END_DATE   = datetime.now().strftime("%Y-%m-%d")

# GNN hyperparameters
HIDDEN_DIM            = 64
LATENT_DIM            = 32
EPOCHS                = 200
LEARNING_RATE         = 0.005
CORRELATION_THRESHOLD = 0.6     # min return correlation to draw an edge
ANOMALY_PERCENTILE    = 90
N_CLUSTERS            = 4

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Device: {DEVICE}")
print(f"Analysis period: {START_DATE} to {END_DATE}")
```

The original recipe uses `/v2/companies/?order_by=-market_cap&limit=40` to pick the universe. v2 endpoints we'll use throughout:

| Purpose | Endpoint |
|---------|----------|
| Universe (top N IDX stocks by market cap) | `/v2/companies/?order_by=-market_cap&limit=40` |
| Daily price/volume per ticker | `/v2/transaction/daily/{symbol}/?start=YYYY-MM-DD&end=YYYY-MM-DD` |
| Quarterly financials (Part 3) | `/v2/company/quarterly-financials/{symbol}/?n_quarters=4` |

Note: the original recipe's URLs reference `daily/{ticker}/` and `companies/top/`. Both have been renamed in v2 — `daily/` lives under `transaction/daily/`, and `companies/top/` is now a filter on `/v2/companies/?order_by=-market_cap`. Check [`../rest/idx-screener.md`](../rest/idx-screener.md) for the full catalog.

## Cell 2 — Fetch data

```python
def fetch_top_companies(n=50):
    url    = f"{BASE_URL}/companies/"
    params = {"order_by": "-market_cap", "limit": n}
    resp   = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        raise ValueError(f"API error {resp.status_code}: {resp.text}")
    return resp.json()

def fetch_daily_data(ticker, start, end):
    url    = f"{BASE_URL}/transaction/daily/{ticker}/"
    params = {"start": start, "end": end}
    resp   = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code != 200:
        return pd.DataFrame()
    data = resp.json()
    if not data:
        return pd.DataFrame()
    df           = pd.DataFrame(data)
    df["date"]   = pd.to_datetime(df["date"])
    df["ticker"] = ticker
    return df.set_index("date").sort_index()

companies = fetch_top_companies(n=40)
tickers   = [c["symbol"] for c in companies]

all_daily = pd.concat([fetch_daily_data(t, START_DATE, END_DATE) for t in tickers], ignore_index=False)
```

The empty-DataFrame fallback means a single failed ticker doesn't break the loop. Check the response codes in a separate pass if you want visibility.

## Cell 3 — Feature engineering

11 features per stock, all rolling/aggregated from the 180-day window:

| Feature | Definition |
|---------|-----------|
| `mean_return` | Average daily return |
| `volatility` | Std of daily returns |
| `skewness` | Return distribution skew |
| `kurtosis` | Return distribution kurtosis |
| `max_return_zscore` | Largest |return z-score| |
| `n_extreme_days` | Days where |z-score| > 2 |
| `max_volume_zscore` | Largest volume z-score |
| `n_volume_spikes` | Days where volume z-score > 2 |
| `price_vs_sma20` | (Close / SMA20) − 1 |
| `vol_regime_ratio` | Recent 30d vol / 180d vol |
| `sharpe_ratio` | mean_return / volatility × √252 |

```python
def compute_features(price_df: pd.DataFrame, volume_df: pd.DataFrame, ticker: str) -> dict:
    rets = price_df.pct_change().dropna()
    feats = {
        "mean_return":       rets.mean(),
        "volatility":        rets.std(),
        "skewness":          rets.skew(),
        "kurtosis":          rets.kurt(),
        "max_return_zscore": rets.abs().max() / rets.std(),
        "n_extreme_days":    (rets.abs() > 2 * rets.std()).sum(),
        "max_volume_zscore": (volume_df / volume_df.rolling(20).mean()).max(),
        "n_volume_spikes":   (volume_df > 2 * volume_df.rolling(20).mean()).sum(),
        "price_vs_sma20":    price_df.iloc[-1] / price_df.rolling(20).mean().iloc[-1] - 1,
        "vol_regime_ratio":  rets[-30:].std() / rets.std(),
        "sharpe_ratio":      rets.mean() / rets.std() * np.sqrt(252),
    }
    return feats
```

Standardize across the universe:

```python
from sklearn.preprocessing import StandardScaler
feat_df = pd.DataFrame([compute_features(...) for ...])
scaler  = StandardScaler()
feat_tensor = torch.tensor(scaler.fit_transform(feat_df.values), dtype=torch.float)
```

## Cell 4 — Correlation graph

```python
# Pivot to wide: rows=date, cols=ticker, values=close
price_wide = all_daily.reset_index().pivot(index="date", columns="ticker", values="close")
rets_wide  = price_wide.pct_change().dropna()

corr_matrix = rets_wide.corr()

# Edges: pairs where |correlation| >= CORRELATION_THRESHOLD
edges = []
for i, t1 in enumerate(tickers):
    for j, t2 in enumerate(tickers):
        if j <= i: continue
        c = corr_matrix.loc[t1, t2]
        if abs(c) >= CORRELATION_THRESHOLD:
            edges.append((i, j))

edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
```

Why `CORRELATION_THRESHOLD = 0.6` works for LQ45:

- Below 0.5 → graph too dense, GNN can't detect local anomalies.
- Above 0.75 → graph too sparse, hub stocks (e.g. BMRI) connect to many nodes while smaller stocks become isolated.

## Cell 5 — Model definition (VGAE)

```python
from torch_geometric.nn import GCNConv, VGAE

class AnomalyGNN(torch.nn.Module):
    def __init__(self, in_dim, hidden_dim, latent_dim):
        super().__init__()
        self.encoder = VGAE(
            encoder=GCNEncoder(in_dim, hidden_dim, latent_dim),
            decoder=None,  # use inner-product default
        )

    def forward(self, x, edge_index):
        return self.encoder(x, edge_index)

class GCNEncoder(torch.nn.Module):
    def __init__(self, in_dim, hidden_dim, latent_dim):
        super().__init__()
        self.conv1 = GCNConv(in_dim, hidden_dim)
        self.conv_mu     = GCNConv(hidden_dim, latent_dim)
        self.conv_logstd = GCNConv(hidden_dim, latent_dim)

    def forward(self, x, edge_index):
        h = F.relu(self.conv1(x, edge_index))
        return self.conv_mu(h, edge_index), self.conv_logstd(h, edge_index)

in_dim = feat_tensor.shape[1]
model  = AnomalyGNN(in_dim, HIDDEN_DIM, LATENT_DIM).to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-5)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

print(f"Model parameters: {sum(p.numel() for p in model.parameters()):,}")
```

`weight_decay=1e-5` is mild L2 — helps when N stocks is small relative to parameter count.

## State after Part 1

| Variable | Contents |
|----------|----------|
| `price_df` | Wide DataFrame of daily close prices |
| `volume_df` | Wide DataFrame of daily volume |
| `feat_df` | 11-feature matrix, one row per stock |
| `feat_tensor` | Standardised features as PyTorch tensor |
| `graph_data` | PyG `Data` with node features + edges |
| `nx_graph` | NetworkX graph for visualisation |
| `corr_matrix` | Full return correlation matrix |
| `model` | Untrained `AnomalyGNN` instance |
| `optimizer` | Adam optimiser |
| `scheduler` | Cosine annealing LR scheduler |

Continue to [`gnn-anomaly-2.md`](gnn-anomaly-2.md) to train the model.

## Known pitfalls

- **Empty DataFrames** for suspended stocks: when `/v2/transaction/daily/{ticker}/` returns nothing (stock suspended, no data in window), the per-ticker DataFrame is empty. The correlation matrix will be all-NaN for that ticker. Drop NaN rows before computing correlation.
- **Sparse 180-day window for new listings**: a stock listed 30 days ago has only 30 returns — not enough for stable kurtosis. Either extend the window to 252 days or filter by listing date.
- **Index heterogeneity**: LQ45 constituents change quarterly. The 40-stock universe you fetch today may not match what you'd have fetched 3 months ago. Pin a snapshot date for reproducibility.
- **Edge direction**: PyG `edge_index` is shape `[2, num_edges]`. The original recipe uses an undirected graph — you must add edges in both directions (or use `T.ToUndirected()`). Otherwise message passing only flows one way.
- **CPU training speed**: 200 epochs on 40 nodes with 11 features trains in ~3 minutes on a modern CPU. Don't bother with GPU unless you're scaling to 1000+ nodes.

## Cross-links

- Train + score + cluster: [`gnn-anomaly-2.md`](gnn-anomaly-2.md)
- Validate with broker/foreign flow: [`gnn-anomaly-3.md`](gnn-anomaly-3.md)
- Sector-level visualisation (no ML): [`sectorscan-part1.md`](sectorscan-part1.md)