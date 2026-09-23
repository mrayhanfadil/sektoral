# Ticker-Agnostic Equity Report Modeling Framework

> Implement by profile and release gate. Keep issuer facts in sourced profiles. A successful render is separate from approval to distribute a rating or target price.

## Goal and scope

Build a complete forecast, valuation, report, and release path for every supported `MODEL_PROFILE`:

| Profile | Forecast | Primary valuation | Method-specific release evidence |
|---|---|---|---|
| `going_concern_fcff` | Operating and cash-flow drivers | FCFF DCF | Latest actuals, revenue and margin drivers, capex, working capital, debt/interest, FCFF and terminal assumptions |
| `financial_ddm` | Earnings, capital, and shareholder distributions | DDM or residual income/P/BV, selected by payout economics | Latest actuals, relevant earning-asset and profitability drivers, capital/book equity, payout or retained earnings, Cost of Equity |
| `finite_life_mining` | Physical-to-financial asset drivers | Finite-life LoM/SOTP | Latest actuals, asset/process production and sales bridge, costs, capex, economic life, ownership, corporate NAV bridge |

Historical-relative multiples are labeled cross-checks. They do not silently replace a missing primary model or get averaged mechanically into its target price.

AMMN is a mining pilot and regression fixture. Its projects, commodities, reporting periods, and numbers belong in its issuer profile and fixture. Shared code and instructions select behavior by profile, never by ticker.

**Definition of working across tickers:** each supported profile has at least one source-backed positive fixture that can reach `distributable` and one incomplete fixture that returns `draft_non_distributable` with exact blockers. All eight current tickers run through the same profile contracts. Their statuses follow available evidence; the plan does not assume every issuer is ready for release today.

## Architecture and decisions

Use a deterministic pipeline fed by the newest complete `sectors_cache` company report plus versioned issuer evidence and assumptions. Do not allow a newer overview-only cache response to displace a complete financial snapshot. Exceptional manual inputs are allowed when they are sourced, dated, labeled, and validated. The source register identifies the document and page or table.

| Decision | Rule |
|---|---|
| Profile routing | Bind forecast builder, valuation builder, release validator, and exhibits to `MODEL_PROFILE`. Unsupported or ambiguous profiles return an explicit blocker. |
| Source integrity | Every material input carries value, unit, period, source, publication date, page/table, and status: actual, company guidance, or analyst assumption. Analyst estimates are never presented as company guidance. |
| Latest actuals | Select the latest officially published period available by report date using the issuer fiscal calendar and release policy. Annual history is context, not a substitute for a required interim actual. |
| Forecast status | `production_ready` is calculated from source coverage and model reconciliation. No builder hardcodes it true or false for every issuer. A historical screen remains labeled as a screen. |
| Method controls | Run only checks applicable to the selected profile. FCFF and enterprise-value gates do not apply to financial DDM; physical mining and asset NAV gates do not apply to other profiles. |
| Missing values | Unknown means unavailable/null. Zero requires a sourced or explicitly justified zero assumption. No generic CAGR, flat debt, D&A-equals-capex, or zero project capex silently fills a material gap. |
| Divergent methods | If independent fair values differ by more than 30%, investigate inputs and assumptions. Select the defensible primary method and disclose the cross-check; do not average first. |
| Release | Critical data, unit, freshness, forecast, valuation, or sensitivity failures block a production rating/TP and identify the exact input path. Rendering alone is never a release gate. |

Methodology references supplied earlier: [FCFF DCF](https://github.com/abidamassi/dcf-valuation-tool), [DDM](https://github.com/abidamassi/ddm_tool), and [historical-relative multiples](https://github.com/abidamassi/relativepeers). These are references, not runtime dependencies or permission to bypass source controls.

### Dated pilot evidence, separate from the rules

- The earlier AMMN cache snapshot had quarterly financials through 1Q26 and lacked the then-required 1H26 row. Recheck the latest official release against each report date.
- Mining overlays lacked a complete physical-to-sales, capex, and asset-separated LoM chain. `data/drivers/AMMN.json` contains published analyst estimates; preserve their analyst status and provenance.
- The current forecast builder emits `historical_screening_proxy`, `production_ready: false`, and a failed G2.9 for every profile. The release validator also applies the same driver-forecast check to FCFF and financial DDM. Both structural paths must be replaced.
- The current eight-ticker batch at `out/e2e-2026-09-23/` is a diagnostic baseline. Its draft results are not positive fixtures and should not be converted to distributable by changing labels.

## Phase 0 — Versioned inputs and profile registry

### 0.1 Source register and issuer contract

**Files:** `data/assumptions/{TICKER}.json`, `data/sources/{TICKER}/README.md`, `app/intake.py`, `app/issuer_evidence.py`.

Define one versioned issuer contract. Common fields are issuer identity, reporting currency, fiscal calendar, as-of date, latest official actual, annual history, market price/shares, source references, and `MODEL_PROFILE`. Each used datapoint has `value`, `unit`, `period`, `source_title`, `source_url_or_file`, `published_at`, `page_or_table`, and `status`. Analyst assumptions additionally have a rationale and sensitivity range. Preserve source documents only when permitted.

Profile extensions are declared rather than imposed on every issuer:

- `operating_drivers[]`: relevant volume, price, mix, utilization, margin, cost, capex, working-capital, debt, and tax drivers for FCFF.
- `financial_drivers[]`: relevant earning assets, funding costs, fees, credit losses, capital, ROE, payout, dividends, and book equity for financial institutions. A bank-specific metric is not mandatory for every financial business.
- `assets[]`, `processes[]`, `products[]`/`commodities[]`: ownership, stage, physical output, capacity, yields, realized prices, costs, capex, economic life, and source links for mining where applicable. Names are values, not schema keys.
- `model_policy`: required/optional fields, source precedence, freshness thresholds, forecast horizon, valuation method, and release checks for the selected profile.

The profile determines completeness. A field required by mining does not block a bank or a general going concern.

### 0.2 Registry and applicability

**Files:** `app/model_profiles.py`, `app/forecast.py`, `app/valuation.py`, `app/release.py`.

Register a forecast builder, primary valuation method, release validator, sensitivity axes, and report exhibits for each supported profile. Configuration or verified business metadata chooses the profile. Unknown metadata fails with `unsupported_model_profile`. Historical-relative multiples remain cross-checks. Keep issuer-specific branches out of shared code.

## Phase 1 — Actuals and model controls

### 1.1 Latest published period

**Files:** `app/intake.py`, `app/issuer_evidence.py`.

Parse annual, interim, and quarterly periods with period end, publication date, scope, and cumulative-versus-standalone semantics. Select the latest eligible official actual by report date and the issuer's fiscal calendar/release policy. Sum quarters only when all components and definitions support the calculation. A required but missing latest actual returns `latest_interim_missing`; it cannot be disguised as the latest result.

### 1.2 Controls by profile

**Files:** `app/model_controls.py`, `app/build.py`.

Apply common price/share/FX scale, period, freshness, source, and accounting checks. Add only method-relevant controls:

- FCFF: operating revenue-to-cash-flow bridge, capex, calculated NWC, debt/rate/interest schedule, FCFF identity, enterprise-to-equity bridge, terminal assumptions.
- Financial DDM/residual income: earnings and book-equity roll-forward, capital and payout coverage, dividend-per-share/share-count consistency, Cost of Equity, and equity-value bridge.
- Mining: physical quantities, price/unit conversions, no double counting of intermediate and refined products, asset life/ownership, NAV bridge, and LoM cash-flow identity.

A failed material check stops production TP with its input path. Missing values remain null; they never become zero in the forecast or valuation.

## Phase 2 — Profile-specific production forecasts

### 2.1 Shared forecast output contract

**Files:** `app/forecast.py` and profile forecast modules.

Replace the universal screening-only return. Each builder returns its rows, assumptions, source links, applicable G2 checks, `forecast_basis`, `production_ready`, and blockers. Valid production bases are profile-specific, for example `driver_forecast` for FCFF, `financial_driver_forecast` for financials, and `physical_driver_forecast` for mining. Compute readiness from coverage, source validity, and reconciliation. A historical proxy can still render an informational draft, with no production TP.

G2.9 means the selected profile's driver-to-earnings/value chain reconciles. It is not a permanently failed constant. Other G2 checks also declare applicability; EBITDA margin and FCFF checks do not run against financial DDM merely because they exist in the shared report format.

### 2.2 Non-financial going concern: FCFF

**Files:** `app/fcff_forecast.py`, `app/forecast.py`.

Forecast revenue from material business drivers such as volume, price, mix, utilization, backlog, or contract economics as the issuer profile supports. Link costs and margins to those drivers. Calculate taxes, D&A, committed and sustaining capex, operating working capital excluding cash/debt, and debt/interest from schedules or sourced assumptions. Reconcile `FCFF = NOPAT + D&A - capex - ΔNWC` and the financial statements. Historical CAGR and flat ratios are cross-checks; they do not certify a production forecast. If material project spend or funding is unknown, return a specific blocker.

### 2.3 Financial institution: DDM or residual income

**Files:** `app/financial_forecast.py`, `app/ddm.py`, `app/forecast.py`.

Forecast the earnings and capital drivers relevant to the configured financial archetype. For a bank this can include earning assets, yields, funding costs, fee income, credit losses, operating costs, tax, capital, payout, dividends, and book-equity roll-forward. Select DDM when distributions represent sustainable shareholder cash flows; otherwise use a supported residual-income/P/BV-versus-ROE method. Use Cost of Equity and equity value. Do not require a generic capex/NWC/FCFF bridge, WACC, or EV for this profile. Incomplete dividend/capital evidence returns a named blocker rather than a fabricated path.

### 2.4 Finite-life mining: physical-to-financial

**Files:** `app/mining_forecast.py`, `app/forecast.py`.

Implement the applicable chain:

`asset access/development → throughput × grade/quality → contained output → recovery/yield → payable/saleable product → processing capacity/utilization → product sales mix → realized price/netback → revenue → unit costs/royalties → EBITDA → tax, capex, NWC, debt, FCFF`.

Forecast source assets and downstream processes separately, removing internal transfers and double counting. Declare conversion units, source/currency/date and annual basis for every material price deck. Include committed project and sustaining spend separately; unknown capex does not default to zero. Development assets begin contributing operating cash flows only when supported by their stage and schedule. Use calculated NWC and a debt/rate/repayment schedule. Connect FX, price, regulation, and milestones to the years and cash flows they change. A missing profile-critical physical driver keeps the forecast incomplete.

## Phase 3 — Primary valuation and sensitivity by profile

### 3.1 FCFF DCF

**Files:** `app/valuation.py` or `app/fcff_valuation.py`.

Discount sourced FCFF using a currency-consistent WACC. Support a defensible terminal growth or exit assumption for a going concern; show PV of explicit cash flows, PV terminal, EV, latest net debt, minority/non-operating items, equity value, and per-share TP. Reconcile the base sensitivity cell to the published TP. Flag excessive terminal dependence and unexplained equity-value extremes.

### 3.2 Financial DDM/residual income

**Files:** `app/ddm.py`, `app/valuation.py`.

Value sustainable dividends or residual earnings using Cost of Equity and book equity. Reconcile forecast net profit, retained earnings, payout, DPS, share count, capital needs, and terminal assumptions. Present an appropriate CoE/ROE/payout sensitivity and a named historical P/BV cross-check when comparable. Do not run FCFF or EV/WACC release checks.

### 3.3 Mining LoM/SOTP

**Files:** `app/mining_valuation.py` or `app/sotp.py`, `app/rnav.py`, `app/valuation.py`.

Value producing assets through supported reserve/economic life without an unsupported perpetual terminal. Count downstream incremental cash flows once, development projects separately with stage-appropriate risk and capex, and corporate/non-operating items in the bridge. Reconcile:

`RNAV/share = (attributable asset/process NAV + non-operating assets - net debt - minorities ± corporate items) / diluted shares`.

Unknown asset NAV remains unavailable, not zero. Missing life, separation, ownership, or corporate bridge evidence yields incomplete SOTP and no production TP. EV/EBITDA is an independent sanity check.

### 3.4 Cross-checks and scenarios

If independent methods diverge by more than 30%, trace the gap through horizon, drivers, capex, discount rates, terminal assumptions, and risk adjustments. Correct errors or select the method that best matches the profile, with the other method disclosed as a cross-check. Recalculate material upside and downside scenarios from the same base as TP. The downside TP must be lower. Compare house estimates with company guidance and independent consensus only on aligned period, unit, and definition. Missing comparisons remain unavailable.

## Phase 4 — Profile-aware report content

**Files:** `app/narrative.py`, `app/render.py`.

The cover, key financials, exhibits, catalysts, risks, and valuation page follow the active profile. Remove fixed fiscal-year keys and issuer assumptions from generated report fields; use the selected issuer's actual fiscal-year labels. Non-financial reports show relevant revenue, EBITDA, capex, FCFF, debt, and DCF drivers. Financial reports show relevant earnings, ROE, book equity, capital, payout/dividends, and CoE drivers. Mining reports show physical output, price/netback, capex, LoM/SOTP, and asset bridge. Unavailable metrics display `n.m.` with a reason; they are not zero or fixed empty slots.

Every catalyst identifies a dated/conditioned observable event, the model driver and year affected, expected earnings/value direction, and source/status. Risks and scenarios are selected from issuer evidence and the active model. News without a material earnings/value path is excluded. The renderer accommodates different asset and exhibit counts without issuer-specific page assumptions. The AI-assisted research summary stays available in HTML/trace for audit and is excluded from the final PDF.

## Phase 5 — Release gate and acceptance

### 5.1 Profile-specific release decision

**Files:** `app/release.py`, `app/build.py`, `app/report_contract.py`.

Split the current combined FCFF/DDM release branch. Common checks cover verified actuals, date/source/unit validity, share/price basis, method selection, and critical model consistency. Apply additional checks only for the active profile:

- FCFF: sourced operating forecast, capex/NWC/debt/interest reconciliation, FCFF DCF, and applicable G3 checks.
- Financial DDM/residual income: sourced earnings/capital/payout forecast, equity valuation reconciliation, and applicable G3 checks.
- Mining: official interim actuals, physical operating bridge, production-ready LoM forecast, complete SOTP, and applicable G3 checks.

The release result contains `status` and a list of precise `blockers`. `production_ready` and G2.9 must be derived from the actual model, never flipped solely to clear a report. Research validation status remains visible in trace; invalid/insufficient research is not promoted into report insight. If a required source is absent, return an honest draft.

### 5.2 Acceptance matrix and batch review

**Files:** focused profile tests, `tests/test_pipeline.py`, `tests/test_release.py`, and eight-ticker artifacts.

- At least one complete positive fixture and one missing-source/failed-reconciliation fixture per supported profile; an unknown profile fails explicitly.
- No shared code or instruction contains issuer-specific business facts or ticker comparisons. Two mining fixtures with different asset/process/product configurations exercise the same engine.
- Latest actual selection respects fiscal calendar, publication date, and complete cache snapshots.
- FCFF, DDM/residual income, and mining each use their own forecast, valuation, release, and report path. A financial fixture cannot be held for missing FCFF/capex/NWC evidence.
- Missing inputs cannot become zero, historical CAGR production forecasts, flat debt/interest plugs, or a published TP.
- Unit, currency, source, sensitivity base, downside direction, value bridge, and report figures reconcile for each applicable profile.
- Rebuild all eight current tickers. Record status, blocker count, and source gaps per ticker; resolve available evidence and formula defects. A genuine missing critical input remains a draft with a specific blocker.
- Review HTML, trace, PDF text, arithmetic, and page layout. The final PDF excludes the AI research-summary section. Preserve unrelated worktree changes.

## Implementation order

1. Define the shared source/profile contract, registry, and status schema.
2. Preserve and verify complete cache selection; implement latest-actual selection and profile-applicable controls.
3. Replace unconditional screening flags and split FCFF from DDM release validation.
4. Build and prove a positive and negative production path for FCFF, financial DDM/residual income, and mining.
5. Connect the corresponding valuations, sensitivities, and profile-aware report exhibits.
6. Populate the eight issuer profiles from verified sources; rebuild and review the batch with exact remaining blockers.

**Release rule:** an issuer output remains `draft_non_distributable` until the active profile's required source evidence and model controls pass. The framework must make a valid production report reachable for every supported profile without promoting unsupported forecasts or target prices.
