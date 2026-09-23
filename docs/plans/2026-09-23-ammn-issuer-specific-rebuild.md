# Ticker-Agnostic Valuation Framework - AMMN Mining Pilot

> **For Hermes:** implement sequentially by gates; no report release until every P0 gate passes. Preserve unrelated worktree changes and verify every derived value against sourced inputs.

**Goal:** Route issuers to a suitable valuation/forecast profile without ticker-specific branches. Implement the mining finite-life profile with AMMN as the first pilot, while preserving distinct DCF, DDM/residual-income, and historical-relative methods for issuers whose business economics fit them.

**Architecture:** Keep the deterministic, cache-only pipeline. Dispatch by configured business/model profile, never by ticker. Share intake, provenance, period, unit, and release controls; route the forecast and valuation to `finite_life_mining` (LoM/SOTP), `going_concern_fcff` (DCF), or `financial_ddm` (DDM/residual income) as appropriate. Historical-relative multiples are a separate cross-check, not a primary method selected by ticker or an automatic blend. Define versioned issuer input contracts, with facts/estimates stored in ticker-keyed profiles. Load interim statements using each issuer's fiscal calendar; fail closed when profile-required inputs, units, freshness, or reconciliations are invalid. Keep shared code and report instructions free of issuer names, projects, dates, and figures.

**Method references supplied by the user:**
- [DCF valuation tool](https://github.com/abidamassi/dcf-valuation-tool): FCFF/WACC workflow for non-financial going concerns; use as a method/reference profile, subject to this pipeline's sourced-input and release gates.
- [DDM tool](https://github.com/abidamassi/ddm_tool): dividend-based equity valuation with Cost of Equity and residual-income/P/BV cross-checks; use only when dividend history and payout economics support it.
- [Relative historical tool](https://github.com/abidamassi/relativepeers): issuer-versus-own-history multiples and sector scorecard; classify as a historical-multiple cross-check, not peer valuation and not a substitute for finite-life asset NAV.

These repositories are methodology references, not runtime dependencies or permission to bypass the cache-only/source-provenance controls. Reimplement or adapt only the required model logic into the existing pipeline after reviewing its assumptions and gates.

**Tech Stack:** Python stdlib, SQLite cache, JSON inputs, pytest, existing HTML/PDF renderer.

---

## Decision Log

| # | Decision | Why | Alternatives rejected | Risk / mitigation |
|---|---|---|---|---|
| D1 | Mining forecasts use a physical-to-financial chain, not historical revenue CAGR as the primary driver | Access, throughput, grade, recovery/payability, processing and product mix determine issuer economics | CAGR with mining prose added afterward | Granular operational data may be incomplete; expose sourced manual inputs and uncertainty ranges |
| D2 | Exceptional manual inputs are allowed only with source, publication date, period, unit, definition, owner/asset, and explicit actual/guidance/analyst status | Sectors cache does not carry every material project/operating datapoint | Inventing a default, silently borrowing peer data, or unlabeled spreadsheet overrides | Source documents must be archived or linked; stale/unsourced critical values block production |
| D3 | Latest-results gate is independent of the forecast horizon and parameterized by issuer fiscal calendar/reporting policy | Latest actual must reflect what was officially published by the report date | Reuse whichever annual or quarterly row happens to appear last in cache | AMMN is the first dated regression fixture; add fixtures with different fiscal calendars and release gaps |
| D4 | Mining valuation follows supported finite-life asset economics, with methodology selected from the issuer's asset profile | Producing assets, processing assets, development projects and corporate items have distinct risk and cash-flow profiles | Apply one perpetual terminal or one aggregate multiple to every mining issuer | Reconcile asset boundaries and ownership; missing life-of-mine or asset-separation data blocks a definitive production TP |
| D5 | No averaging of methods when fair values diverge >30%; explain/reconcile first | Existing rule already requires investigation | Convenient arithmetic mean | If unresolved, select the defensible primary method and disclose cross-check only |
| D6 | Model-control failures are release blockers, not footnotes | RNAV contradiction, NWC plug, debt/interest mismatch, unit errors and stale inputs invalidate outputs | Preserve output with caveats | Fail closed can delay the report; report the exact missing evidence instead |
| D7 | Catalyst inclusion requires a company-specific earnings/valuation transmission path | Daily stock/commodity moves and index flows do not establish issuer catalysts | Fill page with news irrespective of earnings relevance | Real milestones with uncertain dates are shown as windows and marked unconfirmed |
| D8 | Shared procedures and model engine are ticker-agnostic; issuer facts, model profile and disclosed assumptions are input data | Reuse comes from stable contracts and profile dispatch, while evidence varies by issuer | Hardcode issuer names, projects, dates, or figures into shared prompt/code | Add schema, method-routing, cross-issuer fixture and genericity tests |

---

## Pilot Evidence / Blockers (AMMN fixture; verified locally before implementation)

- `data/sectors_cache.db` had AMMN quarterly financial rows through `2026-03-31` (1Q26) when this plan was drafted and no 1H26 row. Verify the official latest release relative to each report date and store its provenance. This is pilot evidence, not a shared reporting-period rule.
- Cache mining overlays currently provide annual production/reserve snapshots and commodity prices, but not the complete Phase 8-to-sales schedule, payable-metal bridge, smelter/PMR ramp, product sales mix, capex schedule or asset-separated LoM cash flows.
- Existing `data/drivers/AMMN.json` is uncommitted user work containing published KB Valbury estimates. Preserve it. Do not overwrite or silently treat analyst estimates as company guidance. The new operational input schema must coexist with and cite/label this evidence.
- Worktree already contains user changes in `agents/estimator/prompt.py`, `agents/estimator/run.py`, `tests/test_estimator.py`, and new `data/drivers/AMMN.json`. Keep them untouched; no broad `git add`.
- Current code confirms the known structural defects: `app/forecast.py` projects CAGR revenue, sustaining capex = D&A and project capex = 0; `app/valuation.py` blends 3-year Gordon and exit multiple; `app/rnav.py` builds crude metal annuities; `app/intake.py` labels annual base as latest while ignoring interim period for the base.

---

## Phase 0 - Evidence pack and input contract (do first)

### Task 0.1: Assemble issuer source register and verify reporting period

**Files:**
- Create: `data/assumptions/{TICKER}-operating.json` (issuer instance of the versioned, provenance-indexed input contract; do not invent missing values)
- Create: `data/sources/{TICKER}/README.md` (issuer source register and document hashes/URLs/date; store source documents only if license permits)
- Modify later: `app/intake.py`
- Test: `tests/test_operating_inputs.py`

For the AMMN pilot, record latest official interim statements and presentation, mine access/production/grade/recovery/payable metrics, processing ramp, product sales, capex commitments, reserve/resource/LoM and development-project milestones. Apply the same contract to each issuer using only relevant assets and metrics. Each datapoint records `value`, `unit`, `period`, `source_title`, `source_url_or_file`, `published_at`, `page_or_table`, `status` (`actual|company_guidance|analyst_assumption`), and optional `asset_id`/`process_id`. Preserve unsupported values as unavailable/null.

**Gate:** no production forecast or target price may claim an input is sourced until that input has provenance. Define completeness from the selected model profile's critical-input requirements; unrelated optional fields do not block. Never label analyst estimates as company guidance. AMMN's existing analyst evidence remains analyst evidence.

### Task 0.2: Define and validate the operating input schema

The versioned issuer profile should have extensible sections for:
- `issuer` / `model_profile`: ticker, reporting currency, fiscal calendar, business archetype, schema version, and configured freshness/release policies.
- `reporting_periods`: official interim periods and annual actuals, with period end, publication date, scope, and audited/reviewed status.
- `assets[]`: stable asset IDs, ownership, stage, reserve/resource basis, operating schedule, unit costs, capex, useful/economic life, and source links. Asset names are data, never schema keys.
- `processes[]`: optional processing, transport, or downstream facilities linked to source/sink assets; capacities, ramp, yields, products, transfer pricing, and incremental economics.
- `products[]` / `commodities[]`: optional product quantities, units, price basis, realization deductions, sales mix, and scenario deck.
- `market`: relevant price decks, FX, royalties/taxes/regulation, source/as-of dates, and scenario ranges.
- `corporate`: latest net debt, corporate costs, minority interests/ownership, and non-operating items.

Do not require a field merely because it exists for the AMMN pilot. Model-profile rules declare required and optional fields, supported valuation methods, and applicable unit/freshness checks.

The model registry must explicitly route supported archetypes: finite-life mining to physical-driver forecast + LoM/SOTP; non-financial going concerns to FCFF DCF; financial/dividend issuers to DDM and/or residual income/P/BV when payout and capital economics support them. Historical-relative multiples are optional cross-checks for any profile with valid history. Unsupported/ambiguous profiles fail with an explicit `unsupported_model_profile`, never a guessed method or ticker-name branch.

### Task 0.3: Define model-profile registry and routing

**Files:**
- Create: `app/model_profiles.py`
- Modify: `app/forecast.py`
- Modify: `app/valuation.py`
- Test: `tests/test_model_profiles.py`

Create an explicit profile registry separating issuer identity from business archetype and valuation method. Route mining, general going-concern, and financial/dividend fixtures to the appropriate engine. Preserve relative historical multiple outputs as named cross-checks only; no automatic averaging with primary fair value. Profile selection must be supplied by configuration or derived from verified business metadata, never from hardcoded ticker comparisons.

**Gate:** test at least one issuer fixture per supported profile and an unknown profile. Financial issuers must not enter enterprise-value DCF; finite-life assets must not receive perpetual going-concern terminals; historical-relative value must not silently become the primary TP.

Schema validation must reject missing provenance for used material inputs, incompatible units, stale critical inputs under the selected profile, duplicate/overlapping assets, invalid ownership/attribution, and company guidance presented as actual. `null` means unavailable; zero is a real sourced or explicitly justified assumption, never a missing-data fallback.

---

## Phase 1 - Latest actuals and data controls (P0)

### Task 1.1: Parse quarterly/interim financials by actual period

**Files:**
- Modify: `app/intake.py`
- Test: `tests/test_intake_periods.py`
- Test: `tests/test_pipeline.py`

Add a typed period parser for quarterly, interim, and annual rows. Derive cumulative periods from component quarters only when all required quarters are present and source semantics support summation; otherwise use the official cumulative report. Select the latest released actual based on publication date, period end, scope, and the issuer fiscal calendar, not row order or stale annual history. Keep annual history for comparisons and full-year forecast. Make freshness thresholds configurable by period type and reporting policy; never hardcode a fiscal year or period label.

**Fail-closed behavior:** when the configured policy requires a newer interim actual and neither cache nor a verified source contains it, stop production output with a clear `latest_interim_missing` error; do not label a stale annual/quarterly result as latest.

**Tests:** shuffled rows; reporting-policy freshness boundaries; cumulative interim supersedes stale annual/quarterly rows; no double counting when official cumulative totals are used; different fiscal calendars; preserve existing non-mining behavior.

### Task 1.2: Add metric and unit validation before narrative/render

**Files:**
- Create: `app/model_controls.py`
- Modify: `app/build.py`
- Test: `tests/test_model_controls.py`

Add profile-aware hard checks for: NAV bridge arithmetic and share conversion; declared quantity/price units and conversion factors; date freshness for material market inputs; price basis/as-of disclosure; debt, interest rate and interest expense reconciliation; NWC as calculated operating working capital, not a balancing plug; FCFF components and consistency across forecast/valuation; physical-to-revenue bridges where applicable; and no duplicate asset/reserve attribution. A failed critical check prevents production PDF/TP generation and reports the exact check and input path. Add Cu/Au unit fixtures from AMMN without making those units mandatory for other profiles.

### Task 1.3: Replace zero NAV substitution with missing-value semantics

**Files:**
- Modify: `app/rnav.py`
- Modify: `app/valuation.py`
- Test: `tests/test_rnav.py`
- Test: `tests/test_model_controls.py`

Unknown asset NAV must be `None`/unavailable, not numeric zero. Never sum unavailable NAV as zero while presenting a complete RNAV/share. Reconcile asset NAV rows to SOTP bridge and sensitivity base exactly; if any required asset NAV is missing, suppress the RNAV TP and label the report not production-ready.

---

## Phase 2 - Mining operating forecast (P0/P1)

### Task 2.1: Build operating forecast module from physical drivers

**Files:**
- Create: `app/mining_forecast.py`
- Modify: `app/forecast.py` (dispatch by configured model profile; retain compatible existing paths for other profiles)
- Test: `tests/test_mining_forecast.py`

Implement the linked annual forecast:

`asset access/development -> throughput x grade/quality -> contained product -> recovery/yield -> payable/saleable product -> optional processing stages -> product sales mix -> realized price/netback -> revenue -> unit costs/royalties -> EBITDA -> tax, capex, NWC and FCFF`.

Build a commodity/product bridge for each relevant stream, using source-supported conversion factors and attributable ownership. Forecast asset output and processing capacity separately; do not count an intermediate and its refined output twice. Price decks declare annual basis (company/consensus/forward curve/analyst), source date, source currency and unit. Apply FX exactly once when converting to reporting currency. Include sourced committed project spend and separately labeled sustaining estimates; do not default unknown capex to zero. Development assets remain separate from operating production until the profile's operating-status criteria are met. AMMN-specific commodities, facilities and project stages belong only in its issuer profile.

For each year, derive revenue from quantities and realized price, and EBITDA from asset/process economics. Historical CAGR is a cross-check only when a material driver model applies. Every analyst assumption carries rationale and sensitivity range. If a profile-critical driver is unavailable, mark the forecast incomplete and block production TP rather than silently reverting to CAGR.

### Task 2.2: Replace NWC, debt and interest plugs with mechanics

**Files:**
- Modify: `app/mining_forecast.py`
- Modify: `app/forecast.py` only as needed for shared helpers
- Test: `tests/test_mining_forecast.py`

NWC = operating current assets less operating current liabilities, excluding cash/debt; calculate delta year-over-year using historical and forecast drivers (or explicit sourced days/ratios where balances lack detail). Interest = beginning/average debt by tranche x explicit rate, plus fees/FX where sourced; debt evolves through drawdowns and scheduled repayment. No relationship between net income and FCFF may be assumed or engineered. Include a bridge exhibit and identity tests proving `FCFF = NOPAT + D&A - capex - ΔNWC` and that FCFF is not mechanically equal to net income.

### Task 2.3: Connect macro and regulatory drivers to economics

**Files:**
- Modify: `app/mining_forecast.py`
- Modify: `app/narrative.py`
- Test: `tests/test_mining_forecast.py`

Map relevant commodity/product prices, FX, demand, royalties/tax/regulation and processing deductions to revenue, net realized price, EBITDA, tax and FCFF. Include source/as-of dates and profile-configured freshness checks. Do not promote daily spot movements into annual forecasts; use the declared price deck and scenario framework.

---

## Phase 3 - LoM/SOTP valuation and sensitivity (P0/P1)

### Task 3.1: Replace mining Gordon/exit average with finite-life asset SOTP

**Files:**
- Modify: `app/valuation.py`
- Modify or replace: `app/rnav.py`
- Create if separation is cleaner: `app/mining_valuation.py`
- Test: `tests/test_rnav.py`
- Test: `tests/test_mining_valuation.py`

Value supported components separately according to the selected mining profile:
1. Producing assets: annual production and cost profiles through supported reserve/economic life, with no unsupported perpetual terminal value.
2. Processing/downstream assets: incremental cash flows only; remove transfer/intercompany duplication with source assets and respect remaining economic life.
3. Development assets: separate risk-adjusted NAV with stage-appropriate probability, capex and timing. Do not include operating production before profile criteria are met.
4. Corporate bridge: latest net debt, minority interests/ownership, corporate overhead PV and other non-operating assets/liabilities.

`RNAV/share = (sum of attributable asset/process NAVs + non-operating assets - net debt - minorities +/- corporate items) / diluted shares`.

EV/EBITDA may appear only as an independent sanity check and cannot be assigned an arbitrary TP weight. If life-of-mine or asset separation data required by the profile is missing, do not substitute a short Gordon value as a production TP; return an explicit incomplete-valuation status and enumerate missing inputs. Reconcile sum-of-assets, bridge, per-share value and sensitivity base to zero tolerance.

### Task 3.2: Explain and gate valuation divergence

**Files:**
- Modify: `app/valuation.py`
- Modify: `app/narrative.py`
- Test: `tests/test_mining_valuation.py`

If independent valuation methods differ by >30%, identify the source (mine life, price deck, margin, WACC, capex, risk haircut, terminal assumptions); correct data/formula or select the method best matched to the asset. Never average first. Label cross-check valuation separately from primary TP.

### Task 3.3: Expand sensitivity and consensus/guidance comparisons

**Files:**
- Modify: `app/mining_valuation.py` / `app/mining_forecast.py`
- Modify: `app/narrative.py`
- Test: `tests/test_mining_forecast.py`
- Test: `tests/test_mining_valuation.py`

Sensitivity must recompute EBITDA and net profit for the material profile-specific price/demand drivers and FX, plus combined downside/upside cases; include discount-rate and relevant asset-risk/valuation haircut sensitivities. Show house forecasts against company guidance and independently sourced consensus/peer estimates when available, with aligned period/unit/definitions. Missing comparison sources are unavailable, not fabricated. AMMN's Cu/Au +/-10% and FX +/-5% cases are pilot fixtures, not universal required axes.

---

## Phase 4 - Report content and page density

### Task 4.1: Rewrite mining industry/model bridge and catalyst/risks pages

**Files:**
- Modify: `app/narrative.py`
- Test: `tests/test_mining_report_content.py`

Replace generic sector prose and noisy catalyst rows with issuer-specific, sourced milestones selected from the active profile: access/development, production/quality, utilization/ramp, results/guidance, project de-risking, regulation, and price-deck deviations where relevant. Every catalyst row must provide expected date/window, observable event/condition, model driver, EBITDA/FCFF/valuation transmission, direction, and source/status. If date or impact is unknown, say so; exclude daily moves, passive flows and index rebalancing without material issuer earnings transmission.

Risk analysis should select material operating, product-quality, processing, commodity/FX, capex, debt/refinancing/interest, regulation, governance and development-option risks from issuer evidence and calculated sensitivities. Do not print risks irrelevant to the issuer.

### Task 4.2: Complete cover key financials and improve useful density

**Files:**
- Modify: `app/narrative.py`
- Modify: `app/render.py`
- Test: `tests/test_mining_report_content.py`
- Visual QA: rendered pilot report pages and profile-driven exhibits; verify layout does not assume a fixed issuer or asset count

Add revenue/EBITDA/net profit and growth, EPS and growth, BVPS, DPS, PER, PBV, dividend yield, EV/EBITDA and net gearing where derivable; unavailable metrics must be `n.m.`/`-` with reason, not zero. Use available report space for profile-relevant operating/price/production/FCFF/valuation bridges and scenario charts, not issuer-specific fixed page assumptions. Preserve the house visual shell and page-count restraint.

---

## Phase 5 - Release gate and verification

### Task 5.1: End-to-end acceptance tests

**Files:**
- Modify: `tests/test_pipeline.py`
- Create: `tests/test_production_gates.py`

The tests must prove:
- latest official interim actual is selected according to issuer fiscal calendar and release policy; AMMN's 1H26 case is one regression fixture.
- profile routing sends finite-life mining to LoM/SOTP, non-financial going concerns to FCFF DCF, and dividend-eligible financial issuers to DDM/residual income as configured; unknown profiles fail closed.
- two mining issuer profiles with different asset/process/product configurations pass without ticker-specific branches; existing non-mining profiles retain their existing model dispatch.
- Every critical manual input has verifiable provenance and correct period/unit.
- Driver chain is complete and reconciles to reported/sourced revenue within defined, disclosed bridge tolerances.
- Production/capacity and concentrate/refined output are not double-counted.
- Missing data cannot become zero, generic CAGR, flat debt/interest, or a published TP.
- profile-declared commodity/price/quantity units catch deliberate swaps; stale market inputs fail configured freshness gates.
- FCFF, debt, interest, NWC, NAV/share, SOTP and sensitivities reconcile; sensitivity base equals TP and downside is lower.
- No unsupported Gordon/perpetual terminal value is used for finite-life primary valuation; going-concern profiles retain their applicable methods.
- Historical-relative multiples are labeled as own-history cross-checks, filtered for invalid denominators/structural breaks, and never automatically averaged into the primary TP.
- Catalysts each map to a dated/conditioned earnings driver; noise is excluded.
- Shared system instruction and shared model code contain no issuer-specific names, dates, projects, or figures; issuer-specific information is loaded from profiles.
- PDF text scan finds no internal strings; all pages have no clipping/overlap and useful page density.

### Task 5.2: Build and independently review

Run in order after source inputs are populated:
1. `python3 -m pytest tests/test_operating_inputs.py tests/test_intake_periods.py tests/test_model_controls.py tests/test_mining_forecast.py tests/test_mining_valuation.py tests/test_mining_report_content.py tests/test_production_gates.py -q`
2. `python3 -m pytest tests/ -q`
3. Build each fixture via its configured profile (including AMMN pilot) and require either a production-ready report with all P0 gates passed or refusal with exact missing evidence. A successful process exit alone is not acceptance.
4. Validate rendered PDF text, units, fiscal period, exhibit arithmetic, latest-result recency, applicable terminal-value policy, NAV/TP consistency and source notes for each profile.
5. Inspect pilot report screenshots and layout behavior for profiles with different asset counts; use an independent visual reviewer if available.
6. Confirm existing unrelated dirty files remain unchanged and stage only explicitly intended framework/profile files.

## Implementation order and release status

1. Shared profile schema, source register and verified latest actuals for the pilot issuer.
2. Period/unit/model-control gates and remove invalid RNAV publication.
3. Driver-based forecast and real cash-flow mechanics.
4. LoM/SOTP valuation and sensitivities.
5. Catalysts, risks, key financials and layout density.
6. Full test suite, PDF arithmetic/text/visual QA.

**Release rule:** an issuer output is a non-distributable research draft until that profile's required latest actuals, asset/operating inputs and P0 checks pass. The AMMN pilot specifically requires verified latest interim results and supported asset-level life-of-mine, processing, development-project and corporate bridge inputs. No fabricated values, silent fallbacks, or production TP from an incomplete profile.
