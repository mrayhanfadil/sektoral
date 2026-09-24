# Forward-Looking Equity Research and Forecast Pipeline

**Status:** New implementation plan, 2026-09-24  
**Scope:** Eight-ticker research runs and every supported `MODEL_PROFILE`  
**Core question:** Given information known at the report's `as_of` date, what could change the issuer's future earnings, cash flow, and equity value?

## Outcome

Each company update must show a forecast for explicit future fiscal periods, the evidence and judgment behind each material change, a matching valuation, and a release status that reflects the strength of that forecast. Historical results establish the starting point and calibrate ranges. A historical growth extrapolation alone is a screening result, not a production forecast.

The standard research run must attempt both Sectors cached news and Tavily web news. Relevant articles must reach the forecast assumption process, not stop at the analyst trace. A missing or failed Tavily search is recorded explicitly. No article is invented to satisfy coverage, and a news event with no supported earnings channel receives zero model impact.

## Forecast-centered research contract

For every ticker, store one immutable run manifest: code revision, `as_of`, latest market close, cache snapshot IDs, official filings and publication dates, Tavily query and retrieval status, selected news URLs, assumption-plan hash, profile, release status, and blockers. This lets a new PDF be compared with an archived one without confusing changed data or methods with a gate regression.

Build a normalized evidence register before asking an agent for forecasts:

| Evidence kind | Use | Required fields |
|---|---|---|
| Official actual | Base-period level and reconciliation | Period end, publication date, value, unit, source and page/table |
| Company guidance or contract | Forward operating constraint | Effective years, scope, units, conditions, source and publication date |
| Sectors cached article | Candidate future event | Exact title, URL, publisher, publication date, text or verified excerpt |
| Tavily article | Discovery of future catalysts and changed expectations | Query, exact title, canonical URL, publisher, publication date, retrieved text/excerpt, fetched time |
| Analyst assumption | Quantified scenario judgment | Affected profile driver, fiscal year, base value, change, rationale, source IDs, uncertainty range |

All information used in a run must have been published by `as_of`. An announced future milestone is allowed if its announcement was already public; record the expected event date separately from the publication date. Deduplicate Sectors and Tavily results by canonical URL and event, and keep source disagreements visible. Tavily snippets are discovery leads; verify the underlying article or issuer disclosure before treating a claim as a material model fact. Official filings and guidance take precedence for issuer numbers. Media can motivate a bounded analyst assumption but does not become an issuer actual or guidance figure.

## Workstream 1 — Make Tavily a real research input

**Touch points:** `app/research.py`, `app/tavily.py`, `agents/analyst/tools.py`, `app/intake.py`, `agents/forecast_assumptions/run.py`.

1. In `app.research`, run a dated Tavily search for every ticker at the report `as_of`, independently of whether the optional analyst agent chooses `web_news`. Search the issuer name and ticker, plus profile-relevant future drivers: orders and capacity for operating companies; credit, rates and capital for financials; production, commissioning, commodity prices and permits for mining. Search for announced upcoming milestones as well as recent results. Cache raw retrieval metadata and record `searched`, `unavailable`, `failed`, or `no_relevant_results`.
2. Merge verified Tavily articles with Sectors `/news/` into a source register with stable IDs. Check issuer identity, dates, canonical URL, duplicated syndication, and whether the article is about an actual future driver. Fetch enough source text to check the claim; a title alone cannot support a numerical change.
3. Pass the merged register into the forecast assumption agent through a typed input. Remove the current split where Tavily is visible in `intel.web_news` but `forecast_agent(forecast_intake)` sees only `forecast_intake.news`. The trace should show search → selected source → assumption or explicit rejection.
4. If Tavily cannot be reached, keep the failure visible and use other verified evidence. Do not call a run fully researched when a material catalyst remains unexamined. Empty search results do not require a made-up news effect.

## Workstream 2 — Turn events into future assumptions

**Touch points:** `agents/forecast_assumptions/run.py`, `app/forecast.py`, `app/narrative.py`, `spec/Instruksi-Report-v3.md`.

For each material event, require this chain:

`published fact → expected timing and condition → profile driver → annual quantity/price/cost/capital assumption → earnings or cash flow → valuation sensitivity`

The event record includes `source_id`, verbatim claim location, event date or window, affected fiscal years, probability or conditions, selected driver, direction, numerical assumption and units, counterfactual base case, rationale for magnitude, downside/upside range, and whether it is issuer guidance or analyst judgment. An agent may propose the magnitude; deterministic validation checks source match, no look-ahead, unit/period compatibility, plausible bounds, and that the driver exists in the active profile. The engine calculates financial effects. The agent must not directly write target price, valuation, or production readiness.

Forecast the remaining current year from latest actuals and dated guidance, then at least three explicit forward fiscal years where the method requires them. Distinguish a one-time timing shift from a sustained run-rate change. Reconcile known interim results with annual projections. Use a base case and specific upside/downside shocks to the same drivers; do not apply one generic percentage to every ticker. Explain changes in forecast versus the previous run and versus company guidance or comparable consensus when available.

Examples of allowed transmissions: a contracted capacity ramp changes volume from its expected commissioning year; feed costs change unit margin; a rate path changes funding cost and credit losses for a bank; mine recovery and product mix change payable sales. An article about share-price movement or broad sentiment has no earnings effect unless a supported causal channel is documented. Material conflicting evidence becomes a stated scenario range or blocker, rather than a silent average.

## Workstream 3 — Calculate by business profile

**Touch points:** `app/forecast.py`, `app/valuation.py`, `app/release.py`, profile modules and issuer evidence files.

| Profile | Forward model | Primary value link | Evidence that blocks production if absent |
|---|---|---|---|
| `going_concern_fcff` | Volume/price/mix or contracts → revenue → costs, capex, working capital, debt/interest → FCFF | Explicit FCFF DCF and enterprise-to-equity bridge | Material operating, investment, or funding driver with no supported value/range |
| `financial_ddm` | Earning assets, yields, funding, credit losses, costs, capital, payout → earnings/dividends/book equity | DDM or supported residual-income equity value | Capital, payout, or earnings bridge missing; FCFF checks are inapplicable |
| `finite_life_mining` | Asset output, recovery, payable sales, price, costs, project/sustaining capex, mine life → annual cash flows | Finite-life LoM/SOTP; separately labeled assumption-led alternative only when its own evidence passes | Physical-to-financial bridge, economic life, ownership, or corporate NAV bridge missing |

Forecast and release routing come from `MODEL_PROFILE`, never from a ticker name. Remove the unconditional `historical_screening_proxy`/failed G2.9 result for a complete production model. Keep it as a clearly labeled fallback for incomplete data. Split the release checks so a bank is never held for FCFF inputs. Readiness is computed from source coverage, forecast reconciliation, method-specific valuation and sensitivity; rendering a PDF cannot change it.

## Workstream 4 — Show the investment view

The report should lead with the future investment question: base-case earnings and value, what must happen, the next dated catalysts, and what evidence would change the view. Put annual assumptions and their source IDs beside the forecast table. For each meaningful news-driven revision, show the before/after driver and the resulting earnings or target-price sensitivity. Separate published fact from analyst estimate in wording and tables. Keep detailed AI research audit in HTML/trace; the PDF carries concise sourced claims, forecasts, risks and valuation.

Archived PDFs remain available but receive an archive label and run-manifest comparison. The old AMMN target must never appear as if it were produced by the new method.

## Delivery sequence and review points

1. **Baseline:** inventory the eight tickers' latest official actuals, current forward assumptions, Sectors/Tavily news coverage, and exact blockers. Save a dated manifest for each existing run.
2. **News vertical slice:** make `app.research` call Tavily, merge and verify news, pass it to the forecast agent, and show one event-to-driver-to-year trace for a representative ticker. Review a zero-impact article too.
3. **Forecast vertical slices:** complete FCFF, financial DDM and finite-life mining in turn. For each, review one fully evidenced forward model and one incomplete case with exact blockers before expanding issuer coverage.
4. **Release and report:** connect each profile's primary valuation, sensitivity, source table, catalyst text and applicable gates. Fix the current DDM/FCFF gate overlap and permanent screening flags as part of this step.
5. **Eight-ticker run:** populate issuer-specific evidence and scenarios, rerun all eight into a new dated output folder, inspect trace and PDF figures, and publish a matrix of `status`, target method, source coverage, Tavily status, forecast years, and remaining blockers.

**Acceptance:** Tavily is attempted on every standard research run; selected Tavily or Sectors news can demonstrably change a future model driver with source and calculation trace; irrelevant news changes nothing; all published forecast years reconcile to valuation; complete fixtures for all three profiles can pass their own gates; the eight tickers have truthful release statuses. A ticker with missing critical evidence stays draft with a precise input request. The objective is a defensible future view, not eight green status labels.
