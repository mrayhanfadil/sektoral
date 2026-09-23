# Sectors-Hackathon Adoption Plan

> Source: `https://github.com/mrayhanfadil/sectors-hackathon` (`plan.md`, `docs/valuation-framework.md`, `agents/valuation/gates.py`, `templates/DATA_CONTRACT.md`, `docs/sectors-swap.md`, `credit-calculator.md`) into `sektoral` (`app/`, `spec/Instruksi-Report-v3.md`, `docs/integration/`).
> Constraint: cache-only pipeline stays. Facts from `data/sectors_cache.db` only. No yfinance/IDX Postgres/Tavily/Google-news/X-sentiment runtime. No React/ADK stack. Track stays T01.

## Goal

Port 4 high-value ideas, adapt — don't copy — code:

1. Method routing with thin-data + sanity gates.
2. Single report contract + pre-render validator.
3. Exhibit provenance / house-format hardening.
4. Credit/cache discipline wording + selective KPI/bands.

## Do not adopt

* `server/` FastAPI, `src/fe/` React+Vite, `agents/adk/` — duplicates `app/web.py`, `app/cache.py`, `docs/integration/`.
* yfinance fallback, `data/sectors.db seed=42`, Tavily/web_search news, social sentiment runtime — violates `app/build.py:1` + `README.md` cache-only rule.
* `merge-plan.md` reference-branch process — already covered by `docs/rest/`, `docs/mcp/`, `docs/cookbook/`.

## Phase 0 — Baseline (1 task, no behavior change)

### Task 0.1: Freeze current gates as regression oracle
* Files: read-only `app/valuation.py`, `app/model_profiles.py`, `app/release.py`, `app/build.py`, `tests/test_model_profiles.py`, `tests/test_release.py`, `tests/test_pipeline.py`.
* Steps: `python3 -m pytest tests/ -q`; `python3 -m app.build AMMN --out out baseline`; save `out/AMMN.json` hash + G1/G2/G3 log.
* Gate:全 green before Phase 1.

## Phase 1 — Method routing upgrade (P0)

Adapts remote Gates 0-5 (`agents/valuation/gates.py:55`, `:81`, `:144`, `:168`, `:209`, `:234`) to local `SUPPORTED_PROFILES` in `app/model_profiles.py:9`.

### Task 1.1: Extend profile registry with gate inputs
* Modify: `app/model_profiles.py` — add `evaluate()` returning `(primary, secondary, thin_data, rating_override, reasons)`.
* Inputs (all from `intake`/`forecast`, never ticker): `filing_history_years`, `ebit_positive_count`, `d_de_ratio`, `net_debt_to_ebitda`, `icr`, `equity>0`, `nci_pct`, `revenue_drivers[]`, `has_steady_state_3y`, `life_cycle_stage`.
* Mapping:
  * Gate0 → existing `finite_life_mining` / `financial_ddm` / `going_concern_fcff`; add `holding_dissimilar → SOTP primary` only when segments>1 in cache.
  * Gate1a `<4y` → keep DCF shortened horizon + `thin_data=True` (remote Delta 1), surface `⚠ Thin Data` banner via `release.py`. Do NOT switch to pure Relative.
  * Gate1b EBIT<2/3y → Relative only; Gate1c leverage breach → DCF + mandatory Relative cross-check; Gate1d negative equity → EV multiples only.
  * Gate2 NCI 15-40% → DCF + SOTP cross-check; >40% → SOTP primary.
  * Gate3 commodity-driven → NAV/reserve primary (maps to existing `finite_life_mining`); ramping <3y → forward Relative.
  * Gate4 `decline` → P/BV/NAV primary; `pre_revenue/high_growth_pre_profit` → EV/Sales primary.
* Test: `tests/test_method_gates.py` — RATU full-pass DCF, CDIA thin+ramping Relative, MTEL NCI-band SOTP x-check, BBCA bank DDM, ADRO mining NAV, unknown → `unsupported`.

### Task 1.2: Wire Gate5 sanity into valuation + release
* Modify: `app/valuation.py:83` (`G3.1_terminal`, `G3.2_skala`) + `app/release.py:279` (`assess_release`).
* Rules: `upside>100%` or `<-50%` → `rating_override="Review Required"` (remote Delta 2, cf. spec §4.4 `|upside|>50%` thesis rule — keep both, stricter one wins for release). `tv_share>75-80%` → warning, no override. Implied exit EV/EBITDA outside peer/history range → flag for Relative cross-check.
* Test: extend `tests/test_model_profiles.py` + `tests/test_release.py`; verify `valuation.build()` output carries `gate_verdict` dict.

## Phase 2 — Report contract validator (P0)

Adapts remote `templates/DATA_CONTRACT.md` validation rules to local `narrative.build()` → `render.render()` shape (`spec/Instruksi-Report-v3.md §7`).

### Task 2.1: Add `app/report_contract.py` + hook in `app/build.py:24`
* Create: `app/report_contract.py` — `validate(doc)` checks:
  1. `blended weights sum==100` (when present; local default Gordon+exit 50/50 — assert, don't silently average if divergence>30% per spec §4.4).
  2. Every exhibit has non-empty `source` (internal provenance) + global sequential `Exhibit N`, no hand numbering.
  3. `segments share_pct sum==100±0.5` when >1, else hide pie.
  4. `upside == round((tp-price)/price*100,1)` recompute; abort on mismatch.
  5. `news[]` has url+date; gauge/score in range if present.
  6. `esg found=false → hide box` (no fabricated scores).
* Modify: `app/build.py:24` — call validator after `narrative.build()`, fail closed (raise, don't render partial as complete).
* Test: `tests/test_report_contract.py` — 6 rules, each with 1 fail fixture.

## Phase 3 — Exhibit provenance + credit discipline (P1)

### Task 3.1: House-format hardening
* Modify: `app/render.py`, `app/narrative.py` — renderer owns figure counter; visible line always `Source: Company, Sektoral Estimates`; `title` never generic (`Chart`/`Table` reject); port `templates/helpers.py` number guards (`n.m.` for `pe<=0` or `>200`, cf. absorpsi plan A4).
* Test: extend `tests/test_pipeline.py` + `tests/test_pdf_copy_text.py` — grep PDF text for `kurasi skor`, `tanpa tanggal`, `$`-for-Rp, raw `9.141`.

### Task 3.2: Credit-policy doc sync
* Modify: `docs/integration/credit_policy.py`, `docs/integration/sectors_client.py` — encode remote `credit-calculator.md`: 1cr/section, never NL `?q=` (3cr), validate ticker first (404 bills), check `quarterly-financial-dates` before `quarterly`, prefer universe feed, minimal `sections=`.
* No runtime behavior change (cache-forever stays); docs + `scripts/` dry-run budget assert `<100cr` quintet harvest.
* Test: `tests/test_sectors.py` — assert `sections=` minimal + keyless-loud 503 path.

## Phase 4 — Selective depth: KPI / bands / adversarial (P2, gated)

Only if Phases 1-2 green + cache fields exist.

### Task 4.1: KPI-per-subsector + bands (behind profile flag)
* Modify: `app/narrative.py`, `app/render.py` — infra hero table (`tenancy=tenant/tower`, fiber km) + blended 60/40 table + PBV/EV 3Y bands (`AVG±STD`). Hide entire block when cache lacks fields; never synthesize.
* Test: `tests/test_mining_report_content.py`-style new `tests/test_kpi_bands.py`.

### Task 4.2: Critic extension (citation → assumption checks)
* Modify: `agents/research/validate.py` — add WACC/beta/g/peer-date checks mirroring remote `agents/critic.py`: numbers in prose == tables, `source+date` per claim, reject `agree-without-evidence`.
* Test: `tests/test_research_agent.py` — 2 adversarial fixtures (wrong WACC, invented peer).

## Verification (each phase)

1. `python3 -m pytest tests/ -q` — all pass, new test files included.
2. `python3 -m app.build AMMN --out out --pdf` — G1/G2/G3 OK or explicit `draft_non_distributable` with blockers.
3. `pdftotext` asserts: `kurasi skor`=0, `tanpa tanggal`=0, internal strings=0.
4. `git add` only `app/*` + `tests/*` + `docs/integration/*` + this plan; preserve unrelated worktree changes.
