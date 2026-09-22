# GNN Anomaly Detection — Part 2: Training, Scoring, and Clustering

> Source: <https://docs.sectors.app/recipes/gnn-anomaly-detection/02-gnn-part-2>
> Author of original recipe: Alya Dwinanda, June 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Train the GVAE from [`gnn-anomaly-1.md`](gnn-anomaly-1.md), score every stock by its reconstruction error, cluster the embeddings, and produce a nine-panel diagnostic plot.

## When to use this approach

- You finished Part 1 and have `model`, `graph_data`, `feat_tensor`, `corr_matrix`, `nx_graph` in memory.
- You want a per-stock anomaly score, ranked top → bottom, ready for downstream validation.

## Cell 6 — Training loop

```python
def train_epoch(model, data, optimizer):
    model.train()
    optimizer.zero_grad()
    x_recon, mu, logstd, z = model(data.x, data.edge_index)
    total_loss, recon_loss = model.loss(data.x, x_recon, mu, logstd, data.edge_index)
    total_loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)   # critical — GCN gradient norms spike
    optimizer.step()
    return total_loss.item(), recon_loss.item()

loss_history = []
for epoch in range(1, EPOCHS + 1):
    total_loss, recon_loss = train_epoch(model, graph_data, optimizer)
    scheduler.step()
    loss_history.append({"epoch": epoch, "total": total_loss, "recon": recon_loss})
    if epoch % 20 == 0 or epoch == 1:
        print(f"  Epoch {epoch:4d}/{EPOCHS} | "
              f"Total: {total_loss:.4f} | Recon: {recon_loss:.4f} | "
              f"LR: {scheduler.get_last_lr()[0]:.5f}")

loss_df = pd.DataFrame(loss_history)
```

Expected loss trajectory (from the original run):

```
Epoch    1/200 | Total: 6.0272 | Recon: 1.0983 | LR: 0.00500
Epoch   20/200 | Total: 0.9167 | Recon: 0.5542 | LR: 0.00488
Epoch   60/200 | Total: 0.8946 | Recon: 0.4142 | LR: 0.00397
Epoch  100/200 | Total: 0.6771 | Recon: 0.3080 | LR: 0.00250
Epoch  200/200 | Total: 0.5897 | Recon: 0.3510 | LR: 0.00000
```

A healthy run:

- Total loss starts around 3.0 and drops fast in the first 25 epochs.
- Stabilises below 0.7 by epoch 150.
- Recon loss tracks below total loss because total includes KL and link terms.

What if it doesn't?

- **Loss oscillates without converging** → drop `LEARNING_RATE` from 0.005 to 0.001.
- **Loss collapses to near-zero in 10 epochs (posterior collapse)** → bump the KL weight from 0.5 to 1.0 in the loss function. This usually happens when the encoder learns to ignore inputs and just output the prior.

Gradient clipping at 1.0 is important — GCN layers produce large gradient norms when node degrees vary, which is normal in a correlation graph where hub stocks like BMRI connect to many nodes.

## Cell 7 — Anomaly scoring

```python
model.eval()
with torch.no_grad():
    x_recon, mu, logstd, z = model(graph_data.x, graph_data.edge_index)

recon_error    = F.mse_loss(x_recon, graph_data.x, reduction="none")
anomaly_scores = recon_error.mean(dim=1).cpu().numpy()   # one scalar per node
embeddings     = z.cpu().numpy()                          # (n_stocks, 32)

threshold  = np.percentile(anomaly_scores, ANOMALY_PERCENTILE)
is_anomaly = anomaly_scores > threshold

result_df = pd.DataFrame({
    "ticker":        active_tickers,
    "anomaly_score": anomaly_scores,
    "is_anomaly":    is_anomaly,
})

# Attach original features for interpretation
result_df = result_df.join(feat_df.reset_index(drop=True))

anomaly_tickers = result_df[result_df["is_anomaly"]]["ticker"].tolist()
normal_tickers  = result_df[~result_df["is_anomaly"]]["ticker"].tolist()
```

The `ANOMALY_PERCENTILE=90` threshold means roughly the top 10% are flagged. With 30 nodes that works out to ~3 anomalies per run. Tune:

- **Lower percentile (e.g. 85)** → more flags, more noise.
- **Higher percentile (e.g. 95)** → fewer flags, higher precision.

In the original run the flagged set was `['BBCA', 'PGAS', 'SMGR']`.

## Cell 8 — Clustering in embedding space

```python
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

# KMeans
kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
kmeans_labels = kmeans.fit_predict(embeddings)
result_df["kmeans_cluster"] = kmeans_labels

# DBSCAN for outlier detection
dbscan = DBSCAN(eps=0.5, min_samples=3)
dbscan_labels = dbscan.fit_predict(embeddings)
result_df["dbscan_cluster"] = dbscan_labels  # -1 = outlier

sil_score = silhouette_score(embeddings, kmeans_labels)
print(f"Silhouette score (KMeans): {sil_score:.3f}")
```

- **KMeans**: assign every stock to one of N clusters. Use to spot "which group does this anomalous stock belong to?"
- **DBSCAN**: points labelled `-1` are isolated outliers. In the original run, all 3 anomalies were DBSCAN outliers — meaning they became anomalous for different reasons (3 independent mechanisms, not a single shared cause).

## Cell 9 — Visualisation (9-panel grid)

```python
fig, axes = plt.subplots(3, 3, figsize=(20, 18))

# Panel 1: training loss curves
axes[0, 0].plot(loss_df["epoch"], loss_df["total"], label="Total")
axes[0, 0].plot(loss_df["epoch"], loss_df["recon"], label="Recon")
axes[0, 0].set_title("Training Loss")
axes[0, 0].legend()

# Panel 2: anomaly score distribution with threshold line
axes[0, 1].hist(anomaly_scores, bins=20)
axes[0, 1].axvline(threshold, color="red", linestyle="--", label=f"p{ANOMALY_PERCENTILE}")
axes[0, 1].set_title("Anomaly Score Distribution")
axes[0, 1].legend()

# Panel 3: PCA(2D) embedding, coloured by cluster
pca = PCA(n_components=2).fit_transform(embeddings)
axes[0, 2].scatter(pca[:, 0], pca[:, 1], c=kmeans_labels, cmap="tab10")
axes[0, 2].set_title("PCA Embedding (KMeans)")

# Panel 4: top-10 anomaly bars
top10 = result_df.nlargest(10, "anomaly_score")
axes[1, 0].barh(top10["ticker"], top10["anomaly_score"])
axes[1, 0].set_title("Top 10 Anomaly Scores")

# Panel 5: correlation matrix heatmap
sns.heatmap(corr_matrix, ax=axes[1, 1], cmap="RdBu_r", center=0)
axes[1, 1].set_title("Return Correlation")

# Panel 6: feature importance for top anomaly (z-score vs population)
top = result_df.loc[result_df["anomaly_score"].idxmax()]
zscores = (feat_df.sub(feat_df.mean()).div(feat_df.std())).loc[top["ticker"]]
axes[1, 2].barh(zscores.index, zscores.values)
axes[1, 2].set_title(f"Feature Z-Scores for {top['ticker']}")

# Panel 7: DBSCAN clustering on PCA
axes[2, 0].scatter(pca[:, 0], pca[:, 1], c=dbscan_labels, cmap="tab10")
axes[2, 0].set_title("DBSCAN Clusters (-1 = outlier)")

# Panel 8: correlation graph with node size = anomaly score
pos = nx.spring_layout(nx_graph, seed=42)
node_sizes = 200 + 1500 * (anomaly_scores / anomaly_scores.max())
nx.draw_networkx(nx_graph, pos=pos, node_size=node_sizes, node_color=anomaly_scores,
                 cmap="Reds", ax=axes[2, 1], with_labels=True, font_size=8)
axes[2, 1].set_title("Correlation Graph (size = anomaly score)")

# Panel 9: anomaly score vs volatility
axes[2, 2].scatter(feat_df["volatility"], anomaly_scores)
axes[2, 2].set_xlabel("Volatility")
axes[2, 2].set_ylabel("Anomaly Score")
axes[2, 2].set_title("Anomaly vs Volatility")

plt.tight_layout()
plt.savefig("gnn_anomaly_diagnostic.png", dpi=150)
```

How to read each panel:

| Panel | What to look for |
|-------|------------------|
| 1 (loss) | Smooth decline, no oscillation |
| 2 (distribution) | Right-skewed, threshold in the gap between two clusters |
| 3 (PCA + KMeans) | Anomalies isolated from the main cluster |
| 4 (top-10 bars) | Sanity check — any obvious "weird" stock at the top? |
| 5 (corr heatmap) | Sector blocks should be visible (banks cluster, telcos cluster) |
| 6 (feature z-scores) | Tells you *why* the top anomaly is anomalous |
| 7 (DBSCAN) | Points labelled `-1` are isolated outliers — independent anomalies |
| 8 (graph) | Large central node = hub stock that's also anomalous (most interesting case) |
| 9 (vol vs score) | Tests whether the model just picked high-vol stocks (it shouldn't) |

## What we have after Part 2

| Output | Meaning |
|--------|---------|
| `anomaly_scores` | One scalar per node, ranking of unusualness |
| `embeddings` | 32-dim latent vector per node |
| `kmeans_labels` | Cluster assignment (0–3) |
| `dbscan_labels` | Cluster or `-1` (outlier) |
| `result_df` | Combined table — anomaly score + clusters + features |

Continue to [`gnn-anomaly-3.md`](gnn-anomaly-3.md) to validate these scores against broker flow and foreign flow.

## Known pitfalls

- **Posterior collapse**: encoder outputs the prior regardless of input. Symptom: embeddings cluster near origin, anomaly scores are near-identical. Fix: increase KL weight to 1.0, or reduce hidden dimension.
- **All-zero anomaly scores**: a node with NaN features produces a zero reconstruction error. Audit for this *before* scoring (see Part 3, Cell 11).
- **Undirected vs directed edges**: if your `edge_index` is one-directional, only one-half of each correlation pair passes messages. Add reverse edges:
  ```python
  edge_index = torch.cat([edge_index, edge_index.flip(0)], dim=1)
  ```
- **Cluster count `N_CLUSTERS=4`**: heuristic. Try 3 or 5 if the silhouette score is low.
- **DBSCAN `eps=0.5` is dataset-dependent**: scale `eps` based on the median pairwise distance in `embeddings`. Default works for LQ45; tune for IDX30 or different universes.
- **GPU vs CPU determinism**: PyTorch Geometric's sparse scatter operations are deterministic on CPU but can produce tiny differences on GPU across runs. For reproducibility, set `torch.manual_seed(42)` before training.

## Cross-links

- Setup + data + model: [`gnn-anomaly-1.md`](gnn-anomaly-1.md)
- Validate with broker + foreign flow: [`gnn-anomaly-3.md`](gnn-anomaly-3.md)
- Simpler visualisation (no ML): [`sectorscan-part1.md`](sectorscan-part1.md)
- Streamlit wrapper for results: [`sectorscan-part2.md`](sectorscan-part2.md)