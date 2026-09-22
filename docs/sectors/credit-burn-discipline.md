# Runbook: Sectors credit-burn discipline

**Trigger:** the Sectors credit burn has spiked (rate log shows repeated
`/v2/company/corporate-actions/AMMN/`, `/v2/financials/quarterly/AMMN/`,
`/v2/company/report/AMMN/`, `/v2/daily/AMMN/` Direct API hits within minutes).

**Do not** flip the key off or change the env. The right move is to make
the collector serve from the local freeze and gate any new live call
behind an explicit operator toggle.

## TL;DR

```bash
# Stop the bleed NOW - default-deny upstream until you say go again:
bash scripts/toggle_sectors_offline.sh lock && bash scripts/restart-api.sh

# Re-enable when a deliberate run needs fresh data:
bash scripts/toggle_sectors_offline.sh unlock && bash scripts/restart-api.sh
```

## How the freeze works (`agents/collector.py`)

The collector has a tiered resolution that no caller has to know about:

1. `data/output/cache_collector_{TICKER}.json`  - 4h TTL, written by the
   last successful `collect(ticker)`. Pure read; zero cost.
2. `output/cache/ticker_fill/company_report_{TICKER}_multisection.json`
   (legacy alias `output/cache/ammn_fill/`)  - the analyst freeze. Served
   REGARDLESS OF AGE since 19 Sep 2026: `FREEZE_TTL_DAYS` unset/0 = forever.
   `FREEZE_TTL_DAYS=N` restores an N-day recency gate (the historical value
   was a hardcoded 7 days, which silently dropped the foreign-flow chart from
   a freshly rendered AMMN PDF at 7.18 days old).
3. SQLite `sectors_cache`  - FOREVER LIVING. Rows are stamped with the
   `NEVER_EXPIRES_AT` sentinel (`server/credit_policy.cache_ttl_seconds`), so
   they are never a miss and `prune_expired()` can never delete them. Tune
   with `SECTORS_CACHE_TTL_DAYS=N` (or `tiers` for the old per-endpoint table).
4. Operator gates (`SECTORS_OFFLINE=1` / `SECTORS_CACHE_ONLY=1`)  - checked at
   the TRANSPORT layer (`server/sectors._get`, after the cache + window
   substitute lookups). They block the billable call only; a cache hit or a
   freeze read always wins. A cold endpoint raises `sectors_offline_mode`
   (collector) / `SectorsError(599)` (transport), and the ADK tools label it
   `{source: sectors_offline}`.
5. Sectors v2 upstream  - only when 1-4 all miss. Billed per the cache rules in
   `references/sectors-credit-leak-guards.md`; window substitution keeps the
   cache key stable across date drift.

### Why the gate is at the transport layer, not in `collect()`

Until 19 Sep 2026 `SECTORS_OFFLINE=1` was checked inside `collect()` BEFORE the
Sectors path was attempted, and `_get()` never looked at it. Two bugs fell out:
a warm `sectors_cache` looked empty to `collect()` (a full 11-row AMMN payload
sat on disk while `collect('AMMN')` raised), and every caller that bypassed
`collect()` (routers, ADK tools, backfill scripts) ignored the gate entirely.
The gate now lives where the credit is actually spent.

## Why the tier-1 cache alone isn't enough

`tier 1` is a 4h TTL written by the LAST `collect()`. If a tab clicks
"Run report" repeatedly and the cache is hit, the cache will be hit.
But the cache is keyed by `(endpoint, params)`  - the call site
`_try_sectors` re-computes `start = today - 90d` every call, so a fresh
window key on every render **bypasses the cache** (the original 2-credit
mystery from the ADK prod run).

The tier-2 freeze bypasses `_try_sectors` entirely  - it returns a
pre-shaped payload without invoking the Sectors adapter, so even if the
window key drifts the freeze short-circuits. For AMMN today the freeze
wins on every call (verified: `collect("AMMN")` returns 0.3ms with
`source: ammn_fill_freeze`, 0 Sectors calls).

## Locking the upstream

```bash
# Set SECTORS_OFFLINE=1 in the env file that docker-compose reads
bash scripts/toggle_sectors_offline.sh lock
# Bounce the api container (script handles the rebuild + recreate)
bash scripts/restart-api.sh
# Confirm: AMMN still serves the report (freeze), BBCA returns 422
curl -s localhost:8777/api/report/AMMN/html | grep "PBV" | head -1
curl -s -o /dev/null -w '%{http_code}\n' localhost:8777/api/report/BBCA/html
```

## Daily discipline

- The live page at `/api/report/AMMN/html` reads `data/assumptions/AMMN.json`
  + `data/drivers/AMMN.json` and never hits Sectors. That's the
  rendering hot-path; safe to refresh in a browser tab.
- The ADK run at `/api/agent/start` (POST) is what burns credits. Operators
  who click "Run Report" in the FE each trigger one full collector pass.
  When the freeze is present (AMMN), the pass costs 0 credits.
- Manual upstream pulls should use `scripts/sectors_harvest.py
  --execute` with the lake directory, NEVER call `server/sectors.*`
  inline.

## Verified workflow

```
$ bash scripts/toggle_sectors_offline.sh lock
$ bash scripts/restart-api.sh
$ .venv/bin/python -c "from agents.collector import collect; print(collect('AMMN', use_cache=False, force_refresh=True)['source'])"
ticker_fill_freeze              # 0 credits (freeze is never aged out)
$ .venv/bin/python -c "from agents.collector import collect; print(collect('BBCA', use_cache=False)['source'])"
sectors                         # 0 credits while sectors_cache holds the rows
$ .venv/bin/python -c "from agents.collector import collect; collect('NOPE', use_cache=False)"
RuntimeError: sectors_offline_mode: SECTORS_OFFLINE=1 set and no cache entry for NOPE
```

The last line is the ONLY failure mode of `lock`: cache cold *and* no freeze. Nothing
is charged in any of the three cases.
