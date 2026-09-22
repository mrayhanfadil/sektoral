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
