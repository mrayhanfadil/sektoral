# Sectors swap list - mechanical wiring once SECTORS_API_KEY lands

> Qualifying rule, verbatim (rules.md §06): "Projects must use **Sectors MCP
> or the Sectors REST API as a core data source**, not as a single decorative
> call. The product should **lose its core functionality if Sectors data is
> removed**." No all-Sectors mandate, no external ban - externals allowed as
> long as core verdicts are Sectors-grounded. We exceed it: every data path
> is Sectors-or-503, so the kill-Sectors test passes trivially. Other hard
> gates: all members onboarded (§03), repo public ≥90d post-winners, ZERO
> commits after freeze/submit (even bugfixes), strip API keys pre-submit,
> deadline 30 Sep 2026 23:59 WIB.

Client: `server/sectors.py` (raw-key auth, bare tickers, loud 503 when keyless).
23 helpers: 8 base (daily/universe/quarterly/report/actions/news/filings/flow)
+ 15 ranked (peers/future/valuation/ownership/management/broker-top/
suspensions/subsector/listing/screener/index-daily/idx-mcap/mining).
Tests: `tests/test_sectors_client.py` (keyless-loud over all 23).

## Pricing (discovered from docs, was unknown)
1 credit/section on reports; most endpoints 1; structured screener 1, NL ?q= 3
(NEVER ?q=); 404 bills 1 (validate tickers first); 400/401/429/5xx free;
empty-200 STILL bills (check quarterly-financial-dates before pulling).
Quintet Tier 1+2 probe budget ≈ <60 credits of the 1,000.
Cache rule: every new call goes behind the existing 4h `cached_endpoint` layer.
Credit rule: universe feeds > per-symbol loops, minimal `sections=`, quintet only.

## Call-site swaps (in wiring order - cheapest/highest-value first)

| # | File : line | Now (external) | Swap to | Notes |
|---|---|---|---|---|
| 1 | `server/routers/endpoints.py:172-235` `_infer_archetype` yfinance fallback | `yf.Ticker.info.sector` | `sectors.company_report(sym, "overview")` → sector field | Kills a runtime yfinance import in the hot path |
| 2 | `server/stockdata.py` whole module | IDX Postgres `stockdata:15437` + yfinance fallback | `sectors.universe_close(date)` for breadth, `sectors.daily(sym,…)` for depth | Docstring already says "Sectors P2 gated" - this IS P2 |
| 3 | `agents/adk/tools/web_tools.py` `web_search` | Tavily key | `sectors.news(symbols)` | **Done.** Tavily is gone from every runtime path: no code reads `TAVILY_API_KEY(S)`, the key is out of `.env` and `.env.example`, and `web_tools.py` is now a Sectors-gateway wrapper. The remaining mentions are this record and test docstrings that assert a third-party key has no effect. |
| 4 | `server/routers/mock_sectors.py` (758 lines) | yfinance/IDX harvester mimicking v2 schemas | Thin proxy to real v2 (`quarterly`, `news`, `filings`, `corporate_actions`) + cache | File keeps its routes/tests; only the fetch layer changes |
| 5 | `agents/collector.py` (27 ext refs) | yfinance statements | `sectors.quarterly(sym, 8)` (+ bank extras free) | Check bank field mapping: `net_interest_income`, `gross_loan`, `total_deposit` |
| 6 | `scripts/yfinance_fallback.py` | yfinance batch | `sectors.daily` / `universe_close` | Rename file to `sectors_backfill.py` when wired |
| 7 | `scripts/seed_assumptions.py`, `seed_synthetic.py` | hand-built/manual | `sectors.company_report(sym, "valuation,peers,financials,dividend")` | Assumptions files become Sectors-grounded, keep manual override |

## 503 wiring pattern (endpoints.py)

```python
from server.sectors import SectorsNotConfigured, SectorsError
try:
    data = sectors.daily(t, start, end)
except SectorsNotConfigured:
    raise HTTPException(503, "Sectors API key belum dipasang - data live belum tersedia")
except SectorsError as e:
    raise HTTPException(502, f"Sectors upstream {e.status}")
```

NEVER `except: fallback_to_yfinance()`. Explicit failure is the rule.

## New signals unlocked (had nothing before)

- `foreign_flow(sym,…)` - net foreign-broker inflow, 90d (feeds Thesis/Risk)
- `company_report` sections `future,management,ownership` - analyst-grade narrative
- `universe_close` - breadth scans (movers/screener) in 1 call

## Verification gate (needs key - do NOT run keyless)

1. `set -a && source .env && set +a` (never echo key)
2. One cheap probe: `company_report("BBCA","dividend")` → 200 + shape assert
3. Quintet sweep × 5 tickers, count calls, confirm < 40 total (budget check)
4. `pytest tests/ -q` full green, then FE rebuild + Pages deploy

## Audit verdict - 3-lane gap-fix (2026-09-08, Lane C append - do not rewrite above)

- Lane A (cache): READY + poisoning-risk - 4h `cached_endpoint` layer wired, but stale/error entries must never be cached (404 bills 1 credit; empty-200 also bills). Cache only 200s with shape assert.
- Lane B (agents): CONDITIONALLY READY - `agents/adk/tools/web_tools.py` is Sectors-or-honest-`source` (`sectors` | `sectors_missing_key` | `sectors_error`); Critic accepts claims only on `source == "sectors"`. Live probe (`agents/adk/tests/test_sectors_live_probe.py`) still needs a keyed run before wiring claims.
- Lane C (data): GAPS - harvest plan exists (`scripts/sectors_harvest.py --dry-run` = 97 credits) but lake is unpopulated keyless; synthetic `seed_synthetic.py` (seed-42) remains the offline fallback and must stay disclosed as synthetic.

Corrected filenames (audit fix - prior doc drafts cited files that do not exist): real files are `scripts/report_fixtures.py` (61KB), `server/routers/mock_sectors.py`, `scripts/seed_synthetic.py` (seed=42, 49-ticker UNIVERSE). `scripts/sectors_api.py` and `export_demo_data.py` DO NOT EXIST - do not reference them.

97-credit harvest math (`scripts/sectors_harvest.py --dry-run`): per-ticker ~17 (report 5 sections + daily + dates/quarterly + segments + shareholders + news + filings + actions + flow + brokertop + suspensions + listing) × 5 quintet (RATU/CDIA/MTEL/BBCA/ADRO) = 85, shared ~12 (universe + idx-mcap + jci + 4 subsectors×2 + screener) → 85 + 12 = 97. Daily refresh ≈ 11. Budget 1,000 - full harvest <10%.

Roster-lock warning: do NOT claim API credits before the roster is final - claim = roster lock. Registration deadline 22 Sep 2026 23:59 WIB (see team-roster.md banner).

## LOUD-policy fix batch (2026-09-08, orchestrator append - do not rewrite above)

Sweep D1+D2+D3 found silent invented numbers in prod paths; user approved loud
policy (keyless errors until SECTORS_API_KEY lands). Fixed in 3 lanes + orchestrator:

- F1 endpoints.py: ARCHETYPE_DEFAULTS no longer merged; missing fcf/shares/price
  -> 422 naming fields; helpers return []/{} + sectors_missing_key; bands drop
  synthetic_prices; outlook/universe -> 503 keyless; news source honest; stubs flagged.
- F2 pdf.py + typst_renderer.py: fabricated archetype dicts + gate inputs +
  BBCA/ADRO exhibits -> 422/ValueError/empty-skeleton; fixture "Sectors (^JKSE)"
  strings -> "yfinance/IDX (Sectors pending)".
- F3 (orchestrator-completed, lane produced nothing): common.py yfinance label
  wash fixed; SOTP pillar + strategy Top Picks tables carry static-demo notes
  (peer/sensitivity rows in single.typ de-baked to dashes in the E-batch below).
- Templates none-safe: theme.typ nstr() + rating-box renders "- data Sectors
  pending"; single/sotp/infra numeric spots + market rows guarded; RATU-branched
  market defaults -> "-". Narrative RATU fallbacks have honest else-branches (left).
  Mirrored to templates/ copies (single enforced by sync test; sotp/infra/strategy
  fallback copies patched for crash spots only - still stale vs server, P2).
- Tests: tests/_loud_test_inputs.py per-ticker declared scenarios (RATU full-pass
  DCF, CDIA thin+ramping Relative, MTEL NCI-band SOTP x-check, BBCA bank DDM,
  ADRO mining NAV); endpoint/loud/dynamic/forecast expectations updated to loud codes.

Verify: 275 passed, 3 skipped. Residual NEEDS-KEY: assumptions re-seed, harvest
--execute (97), live probe keyed run, gate_inputs from real Sectors fundamentals.

## E-batch adversarial removal (2026-09-08, 6-lane cross-check: 3 Hermes + 3 AGY flash)

AGY lanes caught holes Hermes lanes missed. Removed, verified:
- pdf.py fallback payload: vs_jci synthetic series labeled "Sectors", peers
  [t,10,6] labeled "Sectors", financial rows 1000/1100, segments/KPI/risk/
  catalyst invented blocks, placeholder-trend forecast expansion -> all
  honest-empty + sectors_missing_key notes. we/wd/g added to required keys.
- outlook: always 503 (JPM-9100 fixture block deleted, OutlookResponse model
  deleted); /api/tickers: always 503 (stockdata pool retired as source);
  /api/dcf: 422 without file-backed rf/beta/erp/cod + file-as-overrides.
- ratios ebitda*2 invention -> None + note. last_price or-1000 -> direct
  (422-guaranteed). agent.py default prompt: STOP keyless, never synthetic.
- Collector neutered: _synthetic raises, _peers_for empty, supplements dropped,
  no-source -> RuntimeError. Orphans deleted: data/sectors.db (git rm),
  .cache/yfinance/, cache_collector_*.json. yfinance dep removed from
  server/requirements.txt. adversarial.py calibration fallbacks -> raise.
- Templates: relval/peer/caption sources -> Sectors (pending); RATU peer rows
  de-baked; market-cap math + upside comparisons none-guarded; SOTP pillar +
  strategy tables carry static-demo notes. Mirrored to templates/ copies.
- FE: SEED_CHALLENGES emptied; blended 740 fallback + GGM 4200/0.197/0.04/0.1176
  defaults -> "-"; RiskFactors ticker text + segmentsSource ternary removed;
  SentimentChart/StatCards invention -> nulls + honest-empty states; SummaryCard
  BUY/4/3 defaults -> PENDING/counts/empty; api.ts price||0/rating HOLD removed.
- Fixture interception removed from prod loaders (pdf route + typst renderer);
  tests declare demo payloads explicitly via load_demo_fixture().

Residual NEEDS-KEY (cannot fabricate, cannot do keyless): assumptions re-seed
from sectors.company_report, harvest --execute (97), live probe keyed run,
Sectors-native outlook + screener wiring, gate_inputs from real fundamentals.
Orphaned-but-kept: seed_synthetic.py/seed_assumptions.py (demo generators,
zero prod importers). PURGED Sep 2026 with explicit approval:
scripts/report_fixtures.py + scripts/fixtures/*.json deleted,
pdf._load_fixture removed, typst default-data-path fallbacks now require
explicit data_path, render scripts require explicit report_data.json.
Render tests use inline TEST scaffolding or skip honestly keyless.

## H3 template-mirror + docs consistency pins (2026-09-08, tests/test_template_docs_consistency.py - 9 passed)
- Mirror server/report/typst -> templates/typst/archetypes holds ONLY for
  report_single (modulo ../common/ imports); sotp/infra/strategy diverge -
  templates copies still carry baked Peer Median / Rata-rata / Median rows.
- Pinned de-baked: single peer dashes + Sectors (pending); infra peers fully
  data-driven; sotp 4x ilustratif-statis notes. Verified: no `jci_target` in
  endpoints.py (outlook 503), no OutlookResponse in models.py.
- Residual: strategy tables (9100 target, Top Picks) have source labels but no
  ilustratif note; templates sotp/infra/strategy re-mirror still pending.

## T-revamp Bloomberg-terminal FE (2026-09-08, 3x AGY 3.7-flash-high fallback - 3.8 stalled on 90s probe, answered late 2652B)
T1 report routes + components/report (15 files), T2 agent.tsx + components/agent (10 + new RunCommandPalette), T3 shell/hub/mock/css (4). tsc 0 + build OK per lane, verified independently.
Orchestrator anti-overclaim fixes: FEED LIVE -> FEED·SNAPSHOT, OJK-compliance footer -> DISCLAIMER RISET (Sectors API pending), hub 5/5 TERHUBUNG LIVE -> PANTAU 5 EMITEN·SNAPSHOT, REAL-TIME deck -> SNAPSHOT deck, via-Sectors-API source -> snapshot-IDX, 100%-live-audited edu claim -> BE-bound/PENDING, 11 AGENTS hardcoded -> {KNOWN_AGENTS.length} (16, single source with rail). Agent latency/STREAMING/QUEUED verified real-gated. DcfFriend untouched by lanes (dark: variants present, no clash). Render-verified via headless dump-dom (vision service 500): offline honest states, zero overclaim strings. vision_analyze down - visual aesthetic (density, alignment) NOT yet human-verified.
Residual: FE has no test runner (NO-RUNNER) - null-state regressions unpinned; DcfFriend light-mode classes predate console theme.
