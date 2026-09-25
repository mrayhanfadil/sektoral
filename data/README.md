# sectors_cache — snapshot DB (read-only, 0 credits)

Export of ONLY the `sectors_cache` table from
`sectors-hackathon:data/agent_runs.db` (sidestream tables `agent_runs`,
`agent_events`, `memory_facts` NOT copied).

- File: `data/sectors_cache.db` (~1.1 MB, 162 rows, ~0.97 MB payload)
- Schema: `data/schema.sql` — `(cache_key PK, endpoint, fetched_at, expires_at, payload_json)`
- Coverage: AMMN 38 + quintet/others (ADRO/ACES/AUTO/BBCA/CDIA/MTEL/PGEO/POWR/RATU/SSIA/SSMS/VKTR ×5, mining names ×2), endpoints: filings, index-daily/ihsg, company/report, daily, foreign-flow, broker-summary, news, financials/quarterly, corporate-actions, subsector/report, subsectors
- Expiry: NEVER — semua 162 baris dilayani apa adanya, berapapun umurnya.
  `expires_at` hanya info umur. Refresh hanya eksplisit via
  `python3 -m app.topup <paket> <target> --live` (butuh SECTORS_API_KEY,
  tercatat di `data/credit_log.jsonl`). Tanpa itu, upstream tidak tersentuh.

## App database (`data/sectoral.db`, gitignored)

Everything the app writes at run time lives in one SQLite file: agent memory,
forecast plans, fetched news and article text, Yahoo peer and USD/IDR
snapshots, and the report, trace and manifest of every run (see `app/store.py`,
`app/outputs.py`). The hand-curated packs in this folder (`issuer_evidence/`,
`idx_history/`, `market_quotes/`, `analyst_scenarios/`, `method_overrides/`,
`rating_history/`) stay reviewed JSON in git. Import JSON caches written by older
versions with `python -m app.store_import`.

## Peer fundamentals from Yahoo Finance (`yahoo_fundamentals` in the app database)

Peer EV/EBITDA needs each peer's debt, cash and EBITDA (the last four quarters
when Yahoo has them, else the last fiscal year). When a peer's own
`/company/report/<peer>/` is not in the cache, the model reads a dated Yahoo
Finance snapshot instead (`python3 -m app.peer_fundamentals --peers-of INET`).
Those rows stay labelled Yahoo Finance in every exhibit and note; they are
never written into `sectors_cache.db` and never called Sectors data.

## Refreshing dated market data

`python -m app.refresh --as-of <date> <tickers>` refreshes, in one run, the
USD/IDR close, the copper and gold series, the tickers' closing-price packs and
their peer snapshots (curated group, else the Sectors peer table). Each section
below describes one of those inputs; the single-step commands still work.

## Curated peer groups (`peer_groups/`)

The Sectors peer table is the issuer's sub-sector, not its business model
(GMFI's "Airport Operators" holds toll roads and BREN). A reviewed pack per
issuer names the comparable peers and the excluded ones, each with a reason.
Peers in the issuer's Sectors table keep that row; others (including foreign
listings) come from a dated Yahoo snapshot fetched with
`python -m app.peer_fundamentals --group <T>`, valued in their own reporting
currency. With fewer than three peers that have data, the report falls back
to the Sectors table and says so.

## Commodity prices from Yahoo Finance (`commodity_prices` in the app database)

The mine valuation prices metal at the average of the last 12 calendar months.
The Sectors series stays the source while its last point is within 45 days of
the Report Date; when it is older (the copper series in this snapshot ends on
15 Feb 2026) the dated Yahoo series (COMEX `HG=F`, `GC=F`) is used and labelled.
With neither fresh, SOTP/LoM is not adequate. Refresh explicitly:
`python -m app.commodity`.

## Closing prices (`market_quotes/`)

Each pack keeps the last ten Yahoo daily closes; a run takes the latest close on
or before its Report Date. Write them for review with
`python -m app.market_quote --as-of 2026-09-24 AMMN BBRI ...`.

## Use

```bash
python3 scripts/cache_read.py --list-endpoints
python3 scripts/cache_read.py --endpoint "/company/report/AMMN/" --limit 3
python3 scripts/cache_read.py --get "sc:/daily/AMMN/:8f3ab29c5f66170662c85eb787d037ea"
```

Reads are local SQLite only — no `SECTORS_API_KEY`, no network, no credits.
`--get` prints `age_days` alongside the payload (never "expired").

## Refresh (explicit only — costs nothing to read, costs credits to refresh)

1. In `sectors-hackathon`, run cache-first collect for the ticker(s).
2. Re-export just the table:
   `python3 -c "...copy sectors_cache into data/sectors_cache.db..."`
   (see git history of this folder for the exact one-liner).
3. Commit the new `.db` + updated counts below.

## Snapshot provenance

- Source rev: `sectors-hackathon@614aca7` (22 Sep 2026)
- Exported: 162 rows. Update this count + rev on every refresh.
