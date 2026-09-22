# Stock Portfolio Optimization with Python + Sectors API

> Source: <https://docs.sectors.app/recipes/stock-investing-and-finance/01-portfolio-optimization>
> Author of original recipe: Rian Yan, Oct 2024
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Build a portfolio optimizer using Sectors data. Two approaches:

1. **Diversification strategy** — score and rank candidate stocks from a chosen index (LQ45, IDX30, IDXV30, etc.).
2. **Mean-Variance Optimization (MVO)** — Monte Carlo or SciPy minimisation over historical returns.

## When to use this approach

- You're pitching a **Track 3** (market intelligence app) with a portfolio layer.
- Audience is finance-adjacent — analysts, retail investors, robo-adjacent platforms.
- You want to demonstrate **quant finance intuition**, not just data fetching.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents | medium | Wrap the optimizer in an LLM "explain my portfolio" agent. |
| Track 2 — Automation | high | Schedule a daily rebalance recommendation. |
| Track 3 — Market intelligence / apps | **high** | Portfolio optimiser = canonical fintech app. |

## Cost estimate

- ~30 credits per optimization run (1 universe-feed + ~30 daily-feeds for 1y returns).
- Compute: trivial. Pandas + SciPy on a laptop in seconds.

## Pick your universe

Sectors has curated indices that match common investment strategies:

| Index | Focus | Use case |
|-------|-------|----------|
| FTSE | Global large-cap | Track broad market |
| IDX30 | Top 30 by mcap + liquidity | Blue-chip Indonesia |
| IDXBUMN20 | Top 20 SOEs | State-owned exposure |
| IDXESGL | ESG-compliant | Sustainable investing |
| IDXG30 | Growth stocks | Long-term capital appreciation |
| IDXHIDIV20 | High dividend yield | Income seekers |
| IDXQ30 | Quality stocks | Strong fundamentals |
| IDXV30 | Value stocks | Undervalued hunting |
| JII70 | Shariah-compliant | Islamic investors |
| KOMPAS100 | Most liquid 100 | Diversified liquid exposure |
| LQ45 | Top 45 by mcap + liquidity | Blue-chip stability |
| SMInfra18 | Infrastructure | Infra bull case |
| SRIKEHA18 / SRIKEHATI | Sustainability | ESG-focused |

Match your investment goal with the index's property:

| Persona | Goal | Recommended |
|---------|------|-------------|
| Risk-averse retiree | Liquidity + stability | IDX30, LQ45, KOMPAS100 |
| SOE enthusiast | Government-backed | IDXBUMN20 |
| Long-term value hunter | Undervalued | IDXV30 |
| Income seeker | Dividends | IDXHIDIV20 |
| ESG-conscious | Sustainability | IDXESGL, SRIKEHA18 |
| Aggressive growth | High-growth | IDXG30 |

For a hackathon pitch: pick **one persona** and tailor the story. Don't try to optimise across all 13 indices — too many branches, none deep.

## Approach 1 — Diversification strategy (the simpler one)

Score every stock in your chosen index on multiple metrics, then pick the top-K:

```python
import requests, pandas as pd

API_KEY = "<your_api_key>"
HEADERS = {"Authorization": API_KEY}

def fetch(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

# 1. Get the LQ45 universe
companies = fetch("https://api.sectors.app/v2/companies/?where=index_membership:lq45&limit=45")
df = pd.DataFrame(companies["results"])

# 2. For each company, fetch the financial-report section (revenue, earnings, growth)
def get_metrics(symbol):
    url = f"https://api.sectors.app/v2/company/report/{symbol}/?sections=financials"
    data = fetch(url)
    fin = data.get("financials", {})
    return {
        "revenue_growth_5y":  fin.get("revenue_growth_5y"),
        "earnings_growth_5y":  fin.get("earnings_growth_5y"),
        "roe":                 fin.get("roe"),
        "debt_to_equity":      fin.get("debt_to_equity"),
        "free_cash_flow_yield": fin.get("fcf_yield"),
    }

metrics = pd.DataFrame([get_metrics(s) for s in df["symbol"]])
df = pd.concat([df.reset_index(drop=True), metrics], axis=1)

# 3. Normalise + score
from sklearn.preprocessing import MinMaxScaler
score_cols = ["revenue_growth_5y", "earnings_growth_5y", "roe", "free_cash_flow_yield"]
inverse_cols = ["debt_to_equity"]

scaler = MinMaxScaler()
df_norm = df.copy()
df_norm[score_cols] = scaler.fit_transform(df[score_cols])
df_norm[inverse_cols] = 1 - scaler.fit_transform(df[inverse_cols])

df["score"] = df_norm[score_cols + inverse_cols].mean(axis=1)
df = df.sort_values("score", ascending=False)

print(df[["symbol", "company_name", "score"]].head(10))
```

Tweak the score columns and weights to match your persona. A conservative retiree weighs `roe` and `debt_to_equity` heavily; an aggressive growth hunter weighs `revenue_growth_5y` and `earnings_growth_5y`.

## Approach 2 — Mean-Variance Optimisation (Markowitz)

Fetch 1 year of daily closes, compute returns, then run MVO.

```python
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib.pyplot as plt

tickers = df["symbol"].head(10).tolist()  # top 10 by score
prices  = pd.DataFrame()

for t in tickers:
    data = fetch(f"https://api.sectors.app/v2/transaction/daily/{t}/?start=2025-08-01&end=2026-08-29")
    prices[t] = pd.DataFrame(data).set_index("date")["close"]

returns = prices.pct_change().dropna()
mean_returns = returns.mean() * 252          # annualised
cov_matrix   = returns.cov()  * 252          # annualised

# Monte Carlo — random portfolio weights, plot efficient frontier
def random_portfolio(n_portfolios=10000):
    results = np.zeros((3, n_portfolios))
    weights_list = []
    for i in range(n_portfolios):
        w = np.random.random(len(tickers))
        w /= w.sum()
        weights_list.append(w)
        p_return = np.dot(w, mean_returns)
        p_std    = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
        results[0, i] = p_return
        results[1, i] = p_std
        results[2, i] = p_return / p_std      # Sharpe ratio (assume rf = 0)
    return results, weights_list

results, weights_list = random_portfolio()
plt.figure(figsize=(10, 6))
plt.scatter(results[1], results[0], c=results[2], cmap="viridis", alpha=0.5)
plt.xlabel("Volatility (annualised)")
plt.ylabel("Expected Return (annualised)")
plt.title("Efficient Frontier — Monte Carlo")
plt.colorbar(label="Sharpe ratio")
plt.savefig("efficient_frontier.png", dpi=150)

# SciPy deterministic — find max-Sharpe portfolio
def neg_sharpe(w):
    p_return = np.dot(w, mean_returns)
    p_std    = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
    return -p_return / p_std

bounds = [(0, 1)] * len(tickers)
constraints = [{"type": "eq", "fun": lambda w: w.sum() - 1}]

best = minimize(neg_sharpe, x0=np.ones(len(tickers)) / len(tickers),
                bounds=bounds, constraints=constraints, method="SLSQP")
optimal_weights = best.x
print(pd.Series(optimal_weights, index=tickers).round(3))
```

## Limitations of both approaches

- **MVO assumes normal return distribution**. Black-swan events (March 2020, 2022 bear market) are not normal.
- **Monte Carlo** is computationally cheap but converges slowly; results depend on the random seed.
- **SciPy SLSQP** is deterministic but sensitive to initial guess — try multiple `x0` and pick the best Sharpe.
- **Historical covariance** may not predict future correlation. Diversification benefits shift during crises.
- **Transaction costs + liquidity** not modelled. For IDX retail-sized positions this matters.

For a hackathon pitch, document these caveats in your slide deck. The judges will respect quantitative honesty more than over-claimed certainty.

## Real-world extensions

- **Dynamic risk modelling** — GARCH for volatility, rolling-window covariance.
- **Transaction cost modelling** — IDX charges 0.15% buy + 0.15% sell (retail). Add to objective.
- **Liquidity constraints** — limit single-position weight to X% of ADV.
- **Tail risk** — use CVaR (Conditional Value-at-Risk) instead of variance. Lower bound for losses in the worst 5% of scenarios.
- **Black-Litterman** — blend market-implied returns with your views.

## Known pitfalls

- **Currency mismatches**: Sectors prices are in IDR. Don't compare to USD-denominated benchmarks without conversion.
- **Survivorship bias**: your universe may exclude delisted stocks. 5-year backtests are biased upward.
- **Look-ahead bias**: when you backtest, ensure every data point in your training set was available at the time. Don't use 2024 fundamentals to optimise a 2020 portfolio.
- **Equal-weighted vs market-cap-weighted**: the IDX30 is market-cap-weighted. If you rebalance to equal weights annually, you're taking a small-cap bet.
- **Annualising returns**: `mean_daily * 252` is the standard approximation. `mean_daily * 365` overstates by ~45%.
- **Covariance annualisation**: `cov_daily * 252` is standard. Some quants use `* sqrt(252)` for std but `* 252` for variance — make sure you know which.
- **Sharpe ratio with `rf=0`** is the simplest version. For real portfolios, subtract risk-free rate (e.g. SUN 10Y ~7% as of late 2025).

## Cross-links

- Banking benchmark (related quant work): [`benchmark-banking.md`](benchmark-banking.md)
- Anomaly detection alternative: [`gnn-anomaly-1.md`](gnn-anomaly-1.md)
- REST endpoints: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)