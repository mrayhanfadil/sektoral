# Gated Valuation Method Chain and Company-Update Template

**Status:** Implementation plan, 2026-09-24
**Branch:** `claude/fallback-valuation-dcf-000ba7` (built on `forward-looking-equity-research-2026-09-24`, `main` merged in `84cee9c`)
**Inputs:** Valuation Method Selection Framework (Gates 0-5, A. M. Armand, personal working document), BRIDS-style template "Ideation" (Slides 1-7), `spec/Instruksi-Report-v3.md` v3.6
**Core question:** For each issuer, which valuation method do the gates say is structurally correct, what does the engine fall back to when that method lacks evidence, and how does the report show the choice?

## Where the branch stands

| Commit | What it delivers |
|---|---|
| `d551a30` | Automatic method chain (`app/method_chain.py`): fixed order per `MODEL_PROFILE`, fall back only on missing inputs or structural failure, extreme result stops the chain, "Rantai metode valuasi" exhibit |
| `ddbab27` | Mining asset methods yield to the assumption-led EV/EBITDA route while the physical forecast is a screening proxy |
| `0727e2f` | Earnings-led last step for going concern and banks: FY PER median peer x EPS from a validated LLM earnings scenario (`distributable_assumption_led`) |
| `3a6918d` | Thesis points, sourced catalysts/risks, FY27F-FY30F path, Key Financials EPS/PER, brand and industry Tavily queries, "engine" false positive fixed |

Live result before the stop: JPFA published as Buy, TP Rp2.890 (+29,6%) on the LLM scenario; GMFI passed the engine gate and was blocked only by the "engine" false positive (fixed in `3a6918d`). The rerun of all eight tickers was stopped before JPFA finished and must be repeated after Phase 1.

**Gap this plan closes.** `model_profiles.evaluate()` already implements Gates 0-5, but the chain ignores its verdict and branches on three profiles only. Gate inputs are partly hardcoded (`nci_pct=0.0`, `has_steady_state_3y=True`, `life_cycle_stage="mature"`), so Gates 2-4 never fire for non-mining issuers. Gate 5 thresholds disagree across the gate code (+100%/-50%, TV 75%), the chain (|upside| > 50%), the harness (`G3.9_extreme`, |upside| > 50%) and the spec (§4.4 |50%|, G3.1 75%).

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Who selects the method | Automatic chain derived from the gate verdict; the analyst may override with a recorded reason |
| 2 | Extreme result (Gate 5) | Framework thresholds: upside > 100% or downside > 50% → Review Required; terminal value > 80% of EV → flagged, not blocking |
| 3 | Life-cycle and ramp-up classification | LLM classifies from sourced evidence; the analyst may correct it |
| 4 | Report language | Indonesian, with market-standard English financial terms (EBITDA, FCFF, PER, WACC) |
| 5 | Build order | Chain logic first (Phase 1), report template second (Phase 2) |

**Still open:** branding (Sectors.app logo, `sectors.app` footer and "Source: Company, Team Estimates" per the template, versus the current Sectoral / "Sektoral Estimates"). Phase 2 keeps a single brand constant so either answer is a one-line change.

**Fixed by the spec, not a choice:** forecast statement rows without sourced inputs show "belum dimodelkan" (§2 "jangan pernah mengarang angka"); they are never filled from screening ratios.

## Phase 1 — Gate-driven method chain

### 1.1 Real gate inputs

**Touch points:** `app/valuation.py` (`gate_inputs`), `app/intake.py`, `app/issuer_evidence.py`.

| Gate input | Source | Today |
|---|---|---|
| `filing_history_years`, `ebit_positive_count` | Sectors annuals | already computed |
| `d_de_ratio`, `net_debt_to_ebitda`, `icr` | Official balance sheet when present, else Sectors | Sectors only |
| `equity_positive` | Official `total_equity` / `equity_attributable` | uses market cap (always positive): wrong |
| `nci_pct` | Official `non_controlling_interest` / total equity | hardcoded 0 |
| `revenue_drivers` (commodity tags) | Profile + LLM classification (1.2) | profile only |
| `has_steady_state_3y`, `life_cycle_stage`, `segments_count` | LLM classification (1.2) or analyst override | hardcoded |

A missing input stays `None` and the gate records "tidak dapat dinilai" instead of defaulting to a passing value.

### 1.2 LLM stage classifier

**Touch points:** `agents/forecast_assumptions/run.py` (new `stage` subagent), `app/forecast.py` or a new `app/stage.py`.

Output, validated deterministically:

```json
{"life_cycle_stage": "pre_revenue | high_growth_pre_profit | mature | decline",
 "has_steady_state_3y": true,
 "commodity_price_driven": false,
 "dissimilar_segments": 1,
 "rationale": "Bahasa Indonesia, 40-600 karakter",
 "source_ids": ["official", "news:0"]}
```

Validation: enum values only; every non-default classification (anything other than `mature`, `true`, `false`, `1`) must cite `official` or a dated article; the rationale must be consistent with Sectors history (e.g. `decline` requires falling revenue in the latest annuals or a cited restructuring). An analyst file `data/method_overrides/<TICKER>.json` (`field`, `value`, `reason`, `analyst`, `date`) wins over the LLM and is shown in the report. Without a validated classification the gates use the conservative defaults and label them as unverified.

### 1.3 Chain order from the verdict

**Touch points:** `app/method_chain.py`, `app/model_profiles.py`.

Replace the three static `CHAINS` with `chain_for(verdict, profile)`:

| Gate outcome | Chain (primary → fallbacks → last step) |
|---|---|
| Financial institution | DDM → P/BV vs ROE → PER relatif → PER FY skenario |
| REIT / property investment | Property NAV → P/BV relatif → PER FY skenario |
| Holding, NCI > 40% or dissimilar segments | Holding SOTP → consolidated DCF (reference) → PER FY skenario |
| Finite reserves / commodity price-driven | SOTP/LoM → RNAV LoM → EV/EBITDA FY |
| History < 4 years or ramping asset | Forward EV/EBITDA peer → PER FY skenario |
| Chronic operating losses (EBIT > 0 in < 2 of 3 years) | EV/Sales peer → P/S peer |
| Negative equity | EV/EBITDA peer → EV/Sales peer (no PER, no P/BV) |
| Decline / turnaround | P/BV relatif (or NAV if asset base substantial) → DCF (reference) |
| Passes all gates | DCF FCFF → PER relatif → PER FY skenario |

Rules kept from the current chain: order is fixed before values are computed; fall back only on missing inputs or structural failure; screening-forecast methods yield while profile data gates fail; the extreme rule stops the chain.

### 1.4 Methods to add

**Touch points:** `app/valuation.py`, `app/method_chain.py`, `app/release.py`.

1. **First task: check peer data.** Confirm whether the Sectors cache carries peer EV/EBITDA, EV/Sales and P/BV (today only `pe` is used). The methods below depend on it.
2. EV/EBITDA peer (forward and FY), EV/Sales and P/S peer, P/BV relatif for non-banks: median of at least three valid peers, lower/upper quartile as sensitivity, the same band filter idea as PER.
3. Holding SOTP and property NAV: only from a sourced per-subsidiary or per-asset evidence pack (same provenance rules as the mining SOTP bridge). Without one they appear in the chain as "belum tersedia" and are skipped.

### 1.5 Mandatory cross-checks

Framework: relative valuation is never fully optional. When DCF is primary, when Gate 1c flags extreme leverage, or when NCI is 15-40%, the chain must carry a sufficient relative or SOTP cross-check. If peer data exists and the cross-check is missing, that is a release blocker; if no peer data exists, it is a labeled limitation in the methodology notes.

### 1.6 One Gate 5 rule

**Touch points:** `app/method_chain.py` (`EXTREME_UPSIDE`), `app/model_profiles.py` (`_eval_gate5`), `app/harness/g3.py` (`G3.9_extreme`, G3.1), `app/valuation.py` (mining SOTP and DDM extreme checks), `spec/Instruksi-Report-v3.md` (§4.4, §4.6).

- Review Required when upside > 100% or downside < -50%. The chain stops at that method and the report stays draft until a sourced fundamental thesis exists.
- Terminal value > 80% of EV: flag with implied exit EV/EBITDA check; not a blocker.
- Implied exit EV/EBITDA outside the peer or own-history range: flag and require the EV/EBITDA cross-check.
- One constant module used by all four places; tests assert they agree.

### 1.7 Analyst override

`--method <key>` on `app.build` and `app.research`, plus the override file from 1.2 with `method`, `reason`, `analyst`, `date`. The chain records `route: "override"`, keeps the system's proposed order in the trace, and still applies every data gate. The report shows both: "Usulan sistem: X; dipilih analis: Y (alasan)".

### 1.8 Spec

Bump to v3.7: §4.1 references the gate table; §4.1a replaces the three-profile table with the gate-outcome table; §4.4 and §4.6 carry the Gate 5 rule; add the stage classifier and override rules. The spec hash changes the forecast-plan fingerprint, so the next run re-queries the LLM (expected cost).

### Phase 1 acceptance

- Unit tests per gate outcome: verdict → chain order; each hardcoded input replaced; missing input stays unassessed.
- Stage classifier validator tests (enum, citation requirement, override precedence).
- Gate 5 constant shared by chain, gates, harness and spec text; tests for +100%, -50%, TV 80%.
- Existing suite green (the pre-existing logo-path failure in `tests/test_sectoral_branding.py` excluded).

## Phase 2 — Report template (Ideation Slides 1-7, Indonesian labels)

**Touch points:** `app/narrative.py`, `app/report_extras.py`, `app/render.py`, `app/valtables.py`, `app/harness/narrative_tool.py`.

| Slide | Deliverable | Data constraint |
|---|---|---|
| All | Global exhibit counter (exists), source line on every exhibit, header "Equity Research – Company Update" + "Hari, DD Bulan YYYY", brand constant, footer with page number | Branding open |
| 1 Cover | Rating + status (Inisiasi / Dipertahankan / Naik dari X / Turun dari X) from a new rating history store `data/rating_history/`; price box; No. of Shares, Mkt Cap Rp/US$, ADTV (fixed 3-month window), Free Float, major shareholders > 5%; price vs IHSG (exists); Key Financials 2A+3F with Revenue, EBITDA, EBITDA growth, Net Profit, EPS, EPS growth, PER, PBV, EV/EBITDA; three paragraphs (Kinerja keuangan with running-rate check, Berita dan katalis with quantified impact and price-in check vs IHSG, Valuasi in the four-sentence structure) | EPS consensus table dropped per template; rows without inputs show "-" with reason |
| 2 | Industri, katalis emiten, sentimen pasar (foreign flow, stock vs IHSG, media tone); no valuation talk | Sector growth only when sourced |
| 3 | 2x2 combo charts: Revenue + growth, EBITDA + margin, Net Profit + EPS growth, DER vs ROE (bank: NIM + CoC); actual bars solid, forecast bars lighter; each with 2-3 sentences; tie-out with Key Financials | New combo chart renderer in `app/render.py`; EBITDA charts only when EBITDA is modeled |
| 4 | Active option only (DCF / DDM / RNAV / multiple), per spec §4.5; plus the method chain exhibit showing system proposal and any override | Exists; align labels |
| 5 | Peer table with Median and Average rows, covered issuer highlighted, selection criteria and as-of date; 1-year own-history P/E and P/BV bands (mean, median, current marker, percentile) with implied prices from mean/median reversion and the "bukan target harga" disclaimer | Needs daily price + TTM EPS/BVPS series; check cache coverage first |
| 6-7 | Income statement, balance sheet, cash flow (2A+3F), key ratios (Growth, Profitability, Leverage; bank set NIM, CoF, NPL, LDR, CASA, CAR, DuPont); tie-out checks as harness blockers (net profit, ending cash, balance check) | Forecast rows without sourced inputs show "belum dimodelkan"; bank rows only where evidence exists |

### Phase 2 acceptance

- Harness checks: every exhibit has a source line; Key Financials, Slide 3 charts and statements tie out for the same period; forecast rows without inputs are "belum dimodelkan", never numbers.
- Rendered PDFs reviewed for JPFA (going concern), BBRI (bank), AMMN (mining).

## Phase 3 — Rerun and review

1. Rerun JPFA, GMFI, INET, BBRI, SSIA, POWR, AMMN, BBCA with `app.research --pdf --refresh-assumptions` (requires `.env` and `data/fx_usdidr.json` in the worktree; both are gitignored).
2. Per ticker, record: gate verdict, chain order, selected method, route (primary / fallback / override), release status and blockers, TP, and the LLM classification with sources.
3. Review PDFs against the template; open issues become follow-up tasks.
4. Push the branch and open a PR to `forward-looking-equity-research-2026-09-24` (or `main` once that branch merges).

## Out of scope

- EPS consensus table (template marks it as not needed).
- E&P/PSC-specific DCF modification (spec §4.5 note; separate discussion).
- Fixing the pre-existing logo-path test.
- Research analyst agent failures seen in the live run (recommendation wording, synthesis timeout); tracked separately.
