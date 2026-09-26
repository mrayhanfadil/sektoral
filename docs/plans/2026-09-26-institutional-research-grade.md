# Institutional Research Grade Company Updates

**Status:** Execution in progress, 2026-09-26

**Scope:** The research run, Company Update, Audit Trace, analyst review, and distribution path for every supported Model Profile and covered ticker

**Outcome:** A reader can reproduce each material conclusion from dated evidence, challenge the forecast and valuation, see what could change the view, and identify who approved the exact artifact being distributed.

### Execution record

- **Completed in this worktree:** pre-agent Evidence Register validation and Release Gate blocking; deterministic verification of forecast readiness; artifact-hash-bound analyst approval; one publication predicate across report, trace, cover, API, history, and job artifact routes; content-hash-verified publication archives and retrieval links; source, publication, release-policy, and house-assumption manifest hashing; bank-driver uncertainty-range validation; authenticated reviewer identities and a bundle-bound 15-area challenge attestation; explicit informational/legal-review boundary; a versioned policy baseline documenting profile materiality bases, existing tolerances/freshness rules, owners, triggers, and unresolved thresholds; a canonical, manifest-bound registry of model-active discount-rate and terminal-growth house assumptions, with a Production-Ready blocker while its effective date, independent references, and terminal economics remain unapproved; a fresh nine-ticker Draft baseline at [`docs/baselines/2026-09-26-institutional-research-grade.md`](../baselines/2026-09-26-institutional-research-grade.md). Evidence Register failures block distribution; a report artifact alone never passes the gate.
- **Policy 1.2.0 (decided 2026-09-26 by the Sektoral Team):** quantitative materiality is >=5% of FY1 attributable earnings or value per share, plus >=50bp CAR for `financial_ddm` and >=5% attributable asset NAV for `finite_life_mining`; a period is due at its OJK POJK 14/2022 filing deadline (unknown semester assurance uses the 3-month audited deadline); a trigger labels a publication stale and opens a review, and withdrawal is due only for a measured material change without an approved replacement after 10 trading days. `app/release_policy.py` holds the rules and their boundary tests; `app/publication_monitor.py` applies them per published report (`python -m app.publication_monitor --folder <reports> [--candidate-folder <rebuild>] [--apply]`), the gallery shows a stale badge, and every withdrawal remains an authenticated publication event. Each build stores its materiality bases as `model_summary`.
- **Slice C1 (2026-09-26):** `app/period_basis.py` separates cumulative interim periods from standalone quarters and halves and refuses unlike growth; `app/corporate_actions.py` is a dated, sourced ledger with point-in-time share counts, split and rights-issue (TERP) per-share restatement, IAS 33/PSAK 56 weighted-average shares, treasury-stock and if-converted diluted EPS with anti-dilution, and financing effects counted with the dilution; `app/earnings_quality.py` records the reviewed normalization bridge and corporate-action share basis on every report and Audit Trace without changing Release Status. Fixtures cover a later restatement, cumulative interim data, a split, a reverse split, a rights issue, a placement, a buyback and a conversion across several Report Dates. **Production data (2026-09-26):** every covered issuer pack now carries `filing_sources`, a `share_ledger` and a `normalization_ledger` read from its 30 June 2026 statements and cited by PDF page. All nine share ledgers reconcile register to register through dated actions; the Report Date count (net of treasury shares) drives every per-share figure, which moves POWR (Rp1.330 to Rp1.350) and SIDO (Rp448 to Rp454) and leaves the other seven targets unchanged. Assessed 1H26 bridges give FY1 Core Earnings for the P/E and P/B-ROE methods (GMFI +63% from an FX loss, POWR +5%, SIDO -4.6%, JPFA -3.4%, SSIA -1.1%, banks and AMMN nil). Open review items: INET's normalization stays incomplete (a 5.4% other-operating line without a breakdown); INET's reported 1H26 weighted average (10.76 bn) does not reconcile to its January rights issue (derived 21.59 bn); SIDO's three outstanding counts differ by 0.3%; INET Series II exercises after 13 July 2026 and BBRI buyback cash after June are not in the ledgers; FY2025 and earlier are not normalized; the 22% tax rate and pro-rata minority effects are stated analyst assumptions.
- **Slice C2 (2026-09-26):** house policy 1.1.0 documents every model-active parameter (currency, tenor, nominal basis, policy/observation kind, review range, dated benchmark, rationale), including the review of the 3.5% rupiah and 3.0% US$ terminal growth (below IMF 2031 nominal GDP growth of about 7.8% and 4.0% and below the risk-free rate) and the 4% ERP (January 2026 implied premium 4.23%); rupiah models add no CRP because INDOGB embeds the sovereign spread. `app/terminal_economics.py` checks every selected scenario DCF and bank DDM per run ([ADR 0011](../adr/0011-terminal-economics-are-checked-per-run-and-labelled.md)); the per-share ledger rule is [ADR 0010](../adr/0010-per-share-figures-use-one-reviewed-share-ledger.md). Baseline results: BBCA, BBRI and JPFA consistent; GMFI grows 3% with zero net reinvestment, POWR implies a 103% return on new capital against a 13% explicit ROIC, SIDO 72% against 51%; each is labelled with its per-share effect; AMMN is finite-life and INET and SSIA use methods without a perpetuity. Open policy decisions: approval and effective date of the policy values, whether dated observations replace policy inputs, and whether a failing terminal is restated at the ceiling return or only labelled.
- **In progress:** reconciling the remaining open policy items (display tie-out formula, stale commodity fallback, INDOGB benchmark age, review-role authorization). House discount-rate and terminal-growth inputs are centralized and hash-bound, but have no approved effective date, independent profile references, or terminal reinvestment/return validation.
- **Migration note:** reports approved before the frozen-bundle model (for example `out/reports-20260926-rating`, approved by name through the CLI) have no publication manifest, stable Evidence Register row IDs, or authenticated 15-area attestation, so this branch treats them as review pending. They need a rebuild with this code and a fresh authenticated attestation before they can be published again.
- **Still required:** complete source-backed Production-Ready model paths and independent references for each profile; source-backed normalization and corporate-action ledgers for each covered issuer, and their use in the forecast and valuation; approved, effective-dated house assumptions and terminal-economics reconciliation; investor-focused driver/catalyst, business-quality and liquidity exhibits; authenticated author identity and author/reviewer separation when available; complete publication history with predecessor/successor and withdrawal events; prospective forecast monitoring; full PDF/trace baseline rebuild and complete supported-ticker verification.
- **Baseline boundary:** the current deterministic baseline has HTML and manifests but no agent Research Brief, standalone Audit Trace HTML, or PDF. It proves current calculation/release status only; it is not an approved bundle or full reproducibility sample.

## 1. Product standard

A Company Update qualifies for distribution only when four independent conditions hold:

1. **Evidence:** material actuals, guidance, market inputs, and Analyst Assumptions have valid point-in-time provenance and no unresolved critical contradiction.
2. **Analysis:** the selected Model Profile's forecast, valuation, sensitivities, and Method Chain reconcile. The Release Gate assigns the honest Release Status. A Screening Forecast cannot become Production-Ready through source metadata alone.
3. **Review:** an identified analyst has challenged the material source claims, assumptions, scenario range, valuation, risks, and disclosures and approved the exact result and artifact versions.
4. **Distribution:** every public route serves only the approved artifact bundle. New inputs, code, assumptions, model output, or rendered bytes require a new review before the replacement is public.

These conditions are separate. The analytical Release Gate can return `distributable` or `distributable_assumption_led` before human review; that result is **eligible for review**, not yet published. `draft_non_distributable` remains an internal Draft. Review cannot turn a failed Release Gate into a passing one. An Assumption-Led Company Update retains its label and the Primary Method's unmet blockers in the Audit Trace, consistent with [ADR 0005](../adr/0005-assumption-led-is-a-separate-release-status.md).

**Production-Ready forecasts may contain Analyst Assumptions.** Qualification depends on supported judgment, complete profile-specific calculations, economic consistency, reconciliation, validation, and review. For each Assumption-Led result, name the structural or evidential gaps preventing production qualification. The presence of an Analyst Assumption alone is not a blocker. Carry this definition into `CONTEXT.md`, the report spec, and the applicable ADR when implementing the production paths; retain current status until the required calculations and checks exist.

The success measure is a defensible future view of earnings, cash flow, and value, with an inspectable reason for every material assumption. A polished PDF, long bibliography, or high count of passing statuses is not evidence of that outcome.

### Initial code baseline before implementation

- The pipeline already has Method Gates, Stage Checks, a Release Gate, source-linked issuer evidence, Sectors and Tavily news, sensitivity exhibits, a run manifest, and a Forecast Plan review record. Preserve these contracts and improve their enforcement.
- `app/forecast.py` currently leaves each profile's main forecast at `historical_screening_proxy`, with `production_ready=False` and a failed S2.9. This is truthful for the current screen. Production paths must become reachable only through calculated, reconciled profile-specific models.
- `app/build.py` constructs the normalized `evidence_register` after `forecast.build`; its violations are printed, and a register exception creates an error object while the build continues. Material evidence failure must affect release.
- `app/gallery.py` checks analyst review when showing a report as published. `app/server.py` serves existing report files and cover images by ticker without that publication check. The file routes must enforce the same decision.
- `app/assumption_review.py` ties review to the Forecast Plan and published result, but the fingerprint does not identify the rendered PDF/HTML bytes or a complete immutable source bundle. The current reviewer token authenticates access to the review endpoint; reviewer identity is still free text.
- The README's standard batch lists BBCA, BBRI, AMMN, SSIA, INET, POWR, JPFA, and GMFI. `data/issuer_evidence/` also contains SIDO. Phase 0 must establish the current supported ticker set from code and evidence, then use that set in whole-engine verification.
- `CONTEXT.md`, the report spec, ADR 0005, and code/UI use both informational **Model Value / Model Scenario Label** and **Target Price / Rating** language. Resolve the publication vocabulary and disclosure policy explicitly before changing user-facing claims; retain the three existing Release Status meanings.

Read-only intake/forecast probe for Report Date `2026-09-26` (cached closes dated `2026-09-24`; no agent research or artifact build). All nine source-pack tickers have 1H26 official actuals and the current generic forecast marks every profile `historical_screening_proxy`, `production_ready=False`:

| Ticker | Model Profile | Latest official actual | Published | Cached close | Evidence rows |
|---|---|---|---|---|---:|
| BBCA | `financial_ddm` | 1H26 | 2026-07-28 | 2026-09-24 | 11 |
| BBRI | `financial_ddm` | 1H26 | 2026-08-31 | 2026-09-24 | 11 |
| AMMN | `finite_life_mining` | 1H26 | 2026-09-21 | 2026-09-24 | 9 |
| SSIA | `going_concern_fcff` | 1H26 | 2026-08-04 | 2026-09-24 | 2 |
| INET | `going_concern_fcff` | 1H26 | 2026-09-11 | 2026-09-24 | 1 |
| POWR | `going_concern_fcff` | 1H26 | 2026-07-31 | 2026-09-24 | 1 |
| JPFA | `going_concern_fcff` | 1H26 | 2026-08-20 | 2026-09-24 | 2 |
| GMFI | `going_concern_fcff` | 1H26 | 2026-09-18 | 2026-09-24 | 1 |
| SIDO | `going_concern_fcff` | 1H26 | 2026-08-03 | 2026-09-24 | 1 |

The normalized registers produce zero look-ahead warnings and zero critical evidence blockers for all nine packs at this Report Date. AMMN's five documented units (`dmt`, `Mlbs`, `koz`, `kt`, `koz`) were added to its guidance rows after the first evidence check correctly blocked their missing unit fields.

This is an intake/forecast baseline only. Phase 0 still needs a full report/trace/manifest build to record current Method Chain, harness blockers, review state, and publicly served artifacts.

## 2. Decisions and architecture

| Area | Decision |
|---|---|
| Point in time | Every Report Date is an `as_of` cutoff on publication time. Preserve each market quote's own date. Record expected future event dates separately from when the event became public. |
| Market data | Keep the local Sectors Snapshot as the default market-data source. Keep dated Market Quote Overrides and other permitted gap fills separately labelled, following [ADR 0001](../adr/0001-sectors-snapshot-is-the-only-market-data-source.md) and [ADR 0002](../adr/0002-non-sectors-data-stays-labelled-and-outside-the-snapshot.md). |
| Agent role | Agents find, summarize, and propose bounded Analyst Assumptions. Deterministic code validates source, date, unit, period, driver, calculation, Method Chain, valuation, and Release Status. Agent prose does not introduce numeric market data, following [ADR 0004](../adr/0004-agent-prose-carries-no-numbers.md). |
| Forecast Plan | Pin to the exact eligible evidence, spec, and model version. New material evidence creates a new plan or an explicit review of the old one, following [ADR 0006](../adr/0006-forecast-plans-are-pinned-to-their-evidence.md). |
| Method choice | Fix the Method Chain from Method Gate verdicts before valuation. Move only on Insufficient evidence or structural failure; retain a sufficient extreme result for review, following [ADR 0003](../adr/0003-method-chain-moves-on-insufficiency-not-on-results.md). |
| Model Profile | Route forecast, valuation, sensitivity, Stage Checks, and report exhibits by `MODEL_PROFILE`. Issuer facts remain in dated source packs, not shared code or report instructions. |
| Storage | Store runtime records and reviews in SQLite; keep curated source packs in Git and HTML/PDF artifacts as files, following [ADR 0008](../adr/0008-runtime-data-in-sqlite.md). Archive each published bundle with content hashes and a stable publication ID. |
| Scope of approval | Human review approves one fingerprint containing evidence, plan, model outputs, Release Status, disclosures, and rendered artifacts. The public site serves that approved bundle or an explicitly labelled archived version. |

If the product will publish formal investment recommendations rather than informational model scenarios, record that decision in a new ADR and align `CONTEXT.md`, the report spec, UI language, rating definitions, investment horizon, conflict disclosures, and Indonesian distribution review. A generic disclaimer cannot supply those definitions. This plan keeps the present Release Status model while that product decision is resolved.

## 3. Phase 0 — Freeze a factual baseline and release policy

**Priority:** P0. **Touch points:** `CONTEXT.md`, `spec/Instruksi-Report-v3.md`, `app/model_profiles.py`, `app/outputs.py`, `app/gallery.py`, `docs/adr/`, batch harness.

1. Inventory supported tickers and their profiles, latest eligible issuer actuals, quote/FX dates, source coverage, Forecast Plan state, Sectors/Tavily search state, selected method, Stage Check failures, Release Status, review state, and current public artifact URLs. Save a dated matrix and run manifests before altering logic.
2. Rebuild one current representative per profile in a fresh output directory. Preserve report, trace, manifest, HTML, PDF, and the command/configuration used. Record whether the result is Draft, Assumption-Led, or analytically distributable; do not infer status from file existence.
3. Define a single publication state machine: `built -> analytically_eligible -> review_pending -> approved -> published -> superseded/withdrawn`. A Draft may be retained internally for review and debugging; only an analytically eligible and approved bundle can enter `published`.
4. Decide the public wording for Model Value, Model Scenario Label, Target Price, and Rating. Record the decision in an ADR if it changes or extends ADR 0005, then update `CONTEXT.md`, spec, API, report, and website together.
5. Define the release checklist and who can sign it: analyst, independent reviewer where available, and designated compliance/legal reviewer for any public recommendation policy. A local demonstration may use one reviewer role but must label the level of review accurately.
6. Establish the materiality, reconciliation, freshness, and update policy below. Assign an owner to each rule and record the policy version in every run manifest.

### 3.1 Materiality, numerical tolerances, and update rules

Extend the existing shared threshold configuration with a versioned policy per Model Profile and check. Each rule declares its input path, units, absolute and relative tolerance, materiality basis, severity, applicable methods, freshness window, update trigger, and review owner. Define materiality using the affected earnings, cash flow, capital requirement, or Model Value and qualitative risks such as going concern, governance, and financing. A small numerical difference does not excuse an invalid source, wrong period, or missing critical driver.

Compare model identities using unrounded values in consistent base units; test display rounding separately. Use explicit absolute tolerances near zero and meaningful relative tolerances elsewhere. Reconcile the policy with existing spec thresholds, including the 0.1% report tie-out rule; approve and document any change before implementation. A failing calculation must not cause the tolerance to widen automatically. Distinguish a critical Blocker, an item requiring analyst review, and an immaterial display difference with a recorded reason.

Set freshness rules by input type and issuer release calendar. New official results, restatements, material corporate actions, guidance changes, financing events, and breached thesis thresholds create a review task with an owner and due time. Define when an older published view may remain available with a stale label and when it must be withdrawn. A fresh quote cannot make stale financial evidence current.

**Exit criteria:** The baseline is reproducible; the supported ticker matrix is explicit; vocabulary, publication states, and measurable control rules are documented. Boundary tests cover values just inside and outside tolerances, near-zero denominators, and expired data. No current Draft or unreviewed artifact is mistaken for published research.

## 4. Phase 1 — Enforce evidence and publication controls

**Priority:** P0, before further public distribution. **Touch points:** `app/evidence.py`, `app/research.py`, `app/build.py`, `app/release.py`, `app/harness/`, `app/gallery.py`, `app/server.py`, `app/jobs.py`, `app/outputs.py`, `app/run_manifest.py`.

### 4.1 Validate evidence before an agent uses it

Build the normalized Evidence Register before Forecast Assumption Agent input. Give every material row a stable ID, kind, status (`actual`, `company_guidance`, `analyst_assumption`, or context), period, unit/currency, publication date, retrieved date where relevant, source URL or approved file reference, and page/table or exact claim location. Store the original and normalized values and any conversion rule.

Use source precedence for issuer facts: official filing/release, then eligible Sectors data, then separately labelled secondary context. Sectors and Tavily articles can support an Analyst Assumption only when the underlying article text supports the claim; a numerical effect from Tavily-only evidence requires the exact supporting quote. Track accepted, rejected, duplicate, unavailable, and contradictory items. An article about price action with no supported earnings channel has zero model impact.

Validate dates strictly. A malformed date, source published after Report Date, unresolvable material source, contradictory official actual, or missing unit/period on a material number is a named blocker. Nonmaterial context failures can be omitted with a recorded reason. `evidence_register.error` and critical `violations` must feed the Release Gate and publication decision; they must never be represented as an empty, passing register.

### 4.2 Create one publication predicate

Centralize `publishable(bundle)` over analytical status, evidence errors, review fingerprint, artifact hashes, and withdrawal/supersession state. Use it in the Report Gallery, report/trace API, direct HTML/PDF/cover routes, and any history or job link that exposes a distributable artifact. Separate authenticated internal preview URLs from public URLs. Generate or copy public files into an approved namespace only after the predicate passes; perform an atomic switch from the prior approved bundle.

When a new run or rebuild creates different inputs, values, text, PDF, or HTML, keep the previous approved version as an archive and mark the new version review pending. The same known ticker URL must not reveal an unapproved replacement. Missing output metadata or review record fails closed. Record publication and withdrawal events with actor, time, reason, and bundle ID.

### 4.3 Freeze the bundle

Expand the source run manifest to identify the exact code revision or source-tree hash, dirty-tree state or build image, spec hash, model/agent version, source-pack hashes, cache payload hashes, official documents and dates, retrieved news metadata, normalized Evidence Register hash, Forecast Plan hash, overrides, quote/FX inputs, selected method, Release Status, and blockers. After rendering, finalize a detached publication manifest with the HTML/PDF/trace content hashes and stable publication ID; keep the source manifest embedded in the report and the finalized sidecar in the runtime store and Audit Trace. This avoids a self-referential hash inside the PDF. The reviewer record binds to the same publication ID and artifacts. A missing source or publication manifest blocks distribution.

Keep third-party full text only where storage and distribution rights allow. Always retain enough metadata and a verifiable excerpt/location to audit the claim; the public PDF cites the source without republishing an article.

### 4.4 Earnings quality, restatements, and corporate actions

**Priority:** P1 before each production model is accepted. **Touch points:** `app/intake.py`, `app/issuer_evidence.py`, `app/evidence.py`, `app/forecast_statements.py`, market quote/share inputs, issuer evidence packs.

Preserve reported statements and build an explicit bridge to recurring earnings attributable to owners of the parent. Each adjustment records the reported line, amount, sign, tax and minority effects, fiscal period, source, rationale, and whether it affects future earnings or cash flow. Examine exceptional gains, impairments, FX effects, capitalization policies, related-party transactions, and persistent differences between profit and operating cash flow. Recurring restructuring or operating costs cannot be excluded merely because an issuer calls them exceptional. Show reported and adjusted figures together and use the same earnings definition in forecasts, peer multiples, and consensus comparisons.

Version original and restated filings by publication date, period, and accounting scope. For a historical Report Date, use the version then available. A later restatement triggers a new analysis while preserving the prior published bundle. Record a legitimate restatement as a superseding version; unresolved differences between equally applicable official sources remain a conflict. Distinguish standalone quarters from cumulative interim periods and parent accounts from consolidated accounts before calculating growth or normalizing earnings.

Maintain a dated corporate-action ledger for rights issues, warrants, convertibles, splits, buybacks, treasury shares, and other material dilution. Record announcement, ex-date, effective date, terms, conditions, proceeds, and share/debt effects. Use weighted-average basic or diluted shares for the corresponding EPS definition and the appropriate valuation-date or scenario share count for per-share Model Value. Model proceeds, debt conversion, dividends, and dilution together to avoid counting an action's benefit without its financing cost. Keep price, shares, per-share history, and return series on a consistent adjustment basis. Pending actions remain conditional scenarios until the relevant conditions are satisfied.

**Exit criteria:** A future-dated material row, register error, missing manifest, stale review, or direct URL to an unapproved PDF cannot yield a published report. An approved archived artifact remains retrievable with its original identity. Rebuilding unchanged inputs yields the same numerical result and explains any byte-level rendering difference. Before production acceptance, reported-to-adjusted earnings reconcile and fixtures cover a later restatement, cumulative interim data, a split, and a dilutive financing action without contaminating earlier Report Dates.

## 5. Phase 2 — Make Production-Ready mathematically reachable

**Priority:** P1. **Touch points:** `app/forecast.py`, `app/forecast_statements.py`, profile modules, `app/valuation.py`, `app/release.py`, `app/harness/`, `app/model_profiles.py`, issuer evidence packs.

Define a shared forecast output contract with annual rows, fiscal periods, units/currency, driver series, source IDs, assumption ranges, accounting bridge, profile-specific Stage Checks, `forecast_basis`, `production_ready`, and exact `production_blockers`. Each driver value identifies whether it is an actual, company guidance, or Analyst Assumption. Compute `production_ready` from coverage and reconciliations; do not set it with an issuer switch or metadata flag.

For the latest interim year, reconcile reported actuals plus the explicitly forecast remaining period to the full-year row. For every forecast year, make statement identities and financing flows balance without cash or debt plugs. Map every material event through:

`published claim -> timing/condition -> profile driver and fiscal year -> earnings/cash flow -> value/sensitivity`.

Calculate the counterfactual without the event and record the incremental earnings, cash flow, and per-share value. Treat an uncertain event as a bounded Analyst Assumption with a downside and upside range. Preserve a zero-impact result where there is no supported numerical channel.

### 5.1 `going_concern_fcff`

Build issuer-appropriate volume, price, mix, utilization, backlog, or contract drivers into revenue. Calculate operating costs, tax, D&A, committed and sustaining capex, operating working capital, debt/rate/interest, and FCFF. Reconcile `FCFF = NOPAT + D&A - capex - change in operating working capital`; reconcile the income, balance, and cash-flow statements. Value the same FCFF through the Primary Method's currency-consistent DCF and enterprise-to-equity bridge. Show terminal-value share and a base sensitivity cell equal to the published Model Value. Missing material project capex, funding, or working-capital evidence remains a blocker.

### 5.2 `financial_ddm`

Calculate earning assets, yields, funding cost, fees, credit loss, operating costs, tax, earnings, capital, retained earnings, book equity, sustainable payout and dividends. Reconcile the balance sheet and capital constraints across years. Use equity Cost of Equity and the applicable DDM or supported equity method; reconcile DPS, share count, and equity value. Bank checks use earnings, funding, capital, and payout; they do not inherit FCFF, capex, NWC, EV, or WACC requirements. A bank driver scenario that holds material funding/capital ratios at history remains Assumption-Led until its production bridge is evidenced.

### 5.3 `finite_life_mining`

Model each asset and process through reserve/economic life, throughput, grade or quality, recovery, payable product, sales mix, realized price/netback, unit costs, royalties, taxes, sustaining and project capex, working capital, and debt. Separate source assets and downstream processes; remove internal transfers and double counting. Value supported finite-life cash flows in LoM/SOTP, then reconcile attributable asset NAV, development risk, corporate items, minorities, debt, and diluted shares to equity value. An unknown asset NAV or capex is unavailable, never zero. Keep an eligible Assumption-Led last step explicitly separate from a Production-Ready LoM/SOTP result.

### 5.4 Cross-profile checks

Select the Model Profile from verified business facts. One complete and one incomplete fixture per profile must exercise forecast, valuation, Stage Checks, Release Gate, and report. A complete fixture can reach Production-Ready; an incomplete fixture names its missing driver or reconciliation. If two sufficient methods diverge materially, show the drivers of that difference and retain the Method Chain's selected method. Validate the base, downside, and upside from the same inputs; the downside value must be lower. Preserve existing Assumption-Led publication when its own evidence checks pass, without relabelling it Production-Ready.

The Release Gate must validate the calculated model rows and reconciliations itself, or verify a calculation record whose contents it can recompute. It must not accept caller-supplied `production_ready=True`, an allowed `forecast_basis` string, or source metadata as proof of a completed model. Add a negative test that supplies plausible source metadata and the readiness flag with hand-constructed, unreconciled forecast rows and confirms the Release Gate blocks it.

### 5.5 Economic consistency of house assumptions

Maintain a dated house assumption set for FX, risk-free rates, risk premiums, commodity paths, inflation where used, and other shared macro drivers. Each parameter records currency, tenor/horizon, nominal or real basis, source or Analyst Assumption rationale, effective date, range, and version. Runs on the same Report Date use the applicable version; issuer-specific deviations require a recorded reason. Keep spot observations, forward curves, and analyst forecasts distinct and align cash-flow currency and inflation treatment with the discount rate.

Review the spec's existing 3.5% terminal growth and 4% Equity Risk Premium defaults for applicability to each currency, date, and business. Document any retained default and change the spec and shared configuration together if the policy changes. A numeric default without a defensible rationale cannot establish production readiness.

For going concerns, reconcile sustainable terminal growth with reinvestment and return on invested capital; justify the transition from explicit forecast years to steady-state economics. For banks, reconcile growth and payout with sustainable ROE, retained earnings, funding, and capital requirements. Check the corresponding economic identities under their stated assumptions rather than applying one universal formula across profiles. Finite-life mining retains its supported economic-life treatment. Joint scenarios must use a coherent combination of prices, volumes, FX, costs, capex, and financing, with correlations or conditional relationships explained and each material risk counted once.

### 5.6 Independent financial model validation

Before accepting a production path, independently calculate a representative model using a reviewer workbook or a separate reference calculation that does not call the production valuation functions. Compare operating or financial drivers, statements, cash flows, discount factors, terminal or asset values, equity bridge, and per-share output. Retain the input bundle, reference calculations, differences, tolerances, and reviewer disposition as acceptance evidence.

Test stressed revenue/margins, negative earnings, low cash, financing shortfalls, dilution, capital constraints, and relevant asset-life/commissioning changes. Check expected directional relationships only where economics imply them; investigate an unexpected result instead of forcing monotonicity. Each supported profile needs a real source-backed case plus boundary fixtures. A materially changed formula or assumption policy requires revalidation of affected reference cases.

**Exit criteria:** Each profile has a source-backed, calculated positive path and a truthful negative path. All published annual forecast figures, sensitivities, and per-share values reconcile to the selected valuation and an independent reference within documented tolerances. House assumptions and terminal economics are consistent. Complete forecasts with supported Analyst Assumptions can qualify; unresolved structural gaps retain the appropriate Assumption-Led or Draft status. Shared code contains no ticker-specific business assumptions.

## 6. Phase 3 — Make the Company Update useful for an investment decision

**Priority:** P1 after the matching model slice. **Touch points:** `app/narrative.py`, `app/render.py`, `app/report_extras.py`, `app/consensus.py`, `app/rating_history.py`, `spec/Instruksi-Report-v3.md`, web report and trace views.

The first page should answer six questions in plain Bahasa Indonesia: what changed since the last Company Update, what the model expects in the next explicit periods, what must occur for the base case, what the current market price appears to imply, what could prove the view wrong, and what the next observable catalyst is. Give the Report Date, quote date, model status, selected method, value horizon, and the most material limitation beside the conclusion.

For each material driver, put actual/guidance/assumption status, source ID, forecast years, base value, range, and effect on earnings or cash flow next to the forecast exhibit. Show a dated, conditional catalyst with the observable metric, expected timing, affected year/driver, and a predeclared thesis-change threshold. Risks should be tied to model variables and quantified sensitivities rather than generic industry statements. Show company guidance and independent consensus only when period, unit, scope, and definition align; otherwise explain the mismatch. A reverse-implied valuation may show what growth, margin, payout, or commodity path the quoted price would require, with its method limitations visible.

Present a compact base/downside/upside table calculated from the same model, including the changed drivers and their source or Analyst Assumption basis. Do not invent event probabilities. Keep cross-check methods separate from the selected Method Chain value. Make unavailable figures `n.m.` with a reason. Preserve AI research detail in HTML/Audit Trace and keep the final PDF focused on sourced conclusions, forecasts, exhibits, risks, methodology, and disclosures.

### 6.1 Business quality and investability

Add an issuer-specific assessment of competitive position, customer and supplier concentration, pricing power, cyclicality, management capital allocation, ownership/control, related-party exposure, and governance. Tie conclusions to dated evidence and explain their effect on volumes, margins, reinvestment, financing, scenarios, or the uncertainty range. Unsupported competitive-advantage claims stay unanswered. Material business risks already modelled in cash flows must not receive an unexplained second discount in valuation.

Show dated free float, trading turnover/liquidity over a stated observation window, and applicable trading restrictions or suspension status. Explain why these may constrain the use of the research by an institutional investor. Any illustrative position-liquidity calculation must state the assumed position size and participation rate; it cannot imply that an order can be executed at the quoted price. Missing market information remains unavailable. Keep business quality, liquidity constraints, and Model Value distinguishable in the report.

**Exit criteria:** A reviewer can point from each headline claim and catalyst to an Evidence Register row, then to the forecast-year change and valuation effect. The report explains why its view differs from available guidance/consensus, what observed result would cause a revision, and the material business-quality and investability limits. HTML, PDF text, trace, and cover values agree.

## 7. Phase 4 — Add substantive analyst challenge and disclosures

**Priority:** P1 for public distribution; P2 for richer workflow. **Touch points:** `app/assumption_review.py`, `app/server.py`, `app/gallery.py`, `app/outputs.py`, report metadata/disclosure rendering, review UI.

Replace the approval of only a plan/result pair with a checklist and attestation tied to the frozen bundle. The reviewer must inspect: latest official actual and period; material source claims and conflicting evidence; the three largest value-sensitive assumptions; interim and statement reconciliations; Model Profile and Method Chain; base/downside/upside consistency; catalyst and thesis-change tests; independent consensus comparison where available; and limitations/conflicts. Record reviewed source IDs, objections, required edits, disposition, reviewer identity, time, and the final bundle fingerprint. Any edit rebuilds the Company Update and returns it to review pending.

Include earnings-normalization adjustments, restatement and corporate-action treatment, house assumptions and terminal economics, independent validation results, business quality, and liquidity limitations in that review. Record any materiality or tolerance override with its justification and policy version; an override cannot bypass a critical evidence or reconciliation failure.

Use authenticated reviewer identity rather than relying on a shared token plus self-entered name for attribution. Support a separate author and reviewer when the team has both roles. Permit explicit rejection and withdrawal. Maintain the prior approval history without changing its meaning after a new run. Add a concise disclosure record: author/reviewer role, source and methodology, applicable economic or ownership conflicts, any relevant issuer relationship, scope/limitations, and the policy governing rating or model-scenario language. If a required declaration is unknown, keep it unknown and block the publication mode that requires it. Obtain Indonesian legal/compliance review before claiming that a public output satisfies regulated research requirements.

**Exit criteria:** The public artifact displays the correct Release Status and disclosure; the Audit Trace identifies who approved exactly that version and what they challenged. A change to material content invalidates approval. A Draft or rejected bundle has no public distribution URL.

## 8. Phase 5 — Monitor the view after publication

**Priority:** P2. **Touch points:** run history, `app/rating_history.py`, `app/consensus.py`, `app/run_manifest.py`, agent memory, review UI, batch output.

On every new official result or material event, compare the new evidence with the prior published assumptions before running a replacement Forecast Plan. Record actual versus forecast by fiscal period and material driver, absolute and percentage errors with their units, catalyst met/missed/delayed state, changes in guidance and consensus, market input changes, and the decomposition of any Model Value change into actuals, assumptions, valuation parameters, share count, and FX. Distinguish forecast error from a change in source definition or accounting scope.

Publish a version history that links each Company Update to its predecessor, stated reason for revision, supersession date, and archive. Track process measures by Model Profile: source completeness, proportion of material assumptions reviewed, reconciliation failures, Draft/Assumption-Led/Production-Ready mix, time since latest eligible official result, forecast error, and unresolved material conflicts. Use these measures to improve the assumption process; do not rank analysts by target-price hit rate alone.

Evaluate forecasting prospectively by freezing estimates before the next official result. Compare errors and scenario coverage by fiscal horizon and Model Profile against simple, declared baselines and comparable point-in-time consensus when available. Historical walk-forward evaluation must use source vintages and corporate-action information available at each cutoff. Report sample size, exclusions, revised actuals, and limitations; guard against survivorship and look-ahead bias. Retrospective agent evaluation must disclose that model training knowledge can contain later events even when supplied documents respect `as_of`; prospective frozen runs provide stronger evidence against that contamination.

**Exit criteria:** Given any two published versions, a reader can see which facts, assumptions, methods, or prices changed and how those changes moved earnings, cash flow, and value. A missed catalyst or material forecast error produces an explicit review task and an explained update or documented decision to retain the view. Forecast evaluation retains the original published estimates, comparable actuals, baseline, horizon, and sample limitations.

## 9. Delivery slices and verification

Implement in small, reviewable slices with a fresh baseline after each shared-engine change:

| Slice | Required deliverable | Acceptance evidence |
|---|---|---|
| A. Baseline and policy | Supported ticker/profile matrix, publication state machine, vocabulary and materiality policy | Reproducible archived sample per profile; ADR/`CONTEXT.md`/spec consistent; tolerance and freshness boundary checks |
| B. Public artifact control | One publication predicate and approved artifact namespace | Direct PDF, HTML, cover, API, and gallery tests deny Draft, unreviewed, stale, withdrawn, and superseded versions |
| C. Point-in-time evidence | Pre-agent Evidence Register and release blockers | Future, malformed, contradictory, unavailable, and valid source cases; exact source-to-assumption trace |
| C1. Financial normalization | Reported/adjusted earnings bridge, filing vintages, corporate-action ledger | Recurring-profit, restatement, period, split, dilution, and proceeds reconciliation fixtures |
| C2. House assumptions | Dated macro set, issuer deviations, terminal economic checks | Currency/horizon consistency; documented defaults; growth, reinvestment, payout, and capital agree |
| D. FCFF slice | One calculated operating-to-FCFF path | Positive and negative fixtures; statements, FCFF, DCF, sensitivity, report and independent reference agree |
| E. Financial slice | One calculated earnings-to-dividend/capital path | Positive and negative fixtures; no FCFF-only requirement; DDM/equity bridge and independent reference agree |
| F. Mining slice | One calculated physical-to-LoM/SOTP path | Positive and negative fixtures; asset/process and NAV bridges and independent reference agree |
| G. Investment view and review | Driver-linked thesis, business quality, investability, scenarios, disclosures, frozen approval | Source-to-driver-to-value checks; liquidity limitations; invalidation of review on material change |
| H. Coverage and monitoring | Fresh batch, revision dashboard, prospective evaluation | All supported tickers assessed with truthful status and precise blockers; reproducible version comparisons; forecast errors against declared baselines |

Complete C1 and C2 for the applicable inputs before accepting D, E, or F as Production-Ready. Independent validation is part of each model slice's exit criteria. Business quality and investability are required for each corresponding Company Update; expand their comparative coverage as the issuer set grows. Prospective evaluation begins with the first frozen forecast and accumulates evidence as results are published.

For each slice, run focused unit/integration tests and `git diff --check`. For shared forecast, valuation, release, or renderer changes, run the full test suite and rebuild **every supported ticker** into a fresh dated output folder. Inspect each report's `meta.status`, Release Gate and harness blockers, Evidence Register, manifest, method, forecast years, and review state. For final PDFs, check text extraction and representative pages for every profile; compare displayed figures to the stored model and Audit Trace. Preserve unrelated worktree changes and do not overwrite an approved artifact during verification.

### Final acceptance matrix

The product reaches this plan's research standard when all of the following are demonstrated:

- Every supported Model Profile has a complete source-backed fixture that can pass its own Production-Ready path and an incomplete fixture that remains Draft or correctly Assumption-Led with named limitations.
- Supported Analyst Assumptions can be part of a Production-Ready forecast; each remaining Assumption-Led classification identifies the missing structural or evidential requirements.
- Reported and normalized earnings reconcile with tax and minority effects. Original and restated actuals remain available by publication date. Corporate actions reconcile price/share bases, proceeds, debt effects, EPS, and Model Value without hindsight or double counting.
- Dated house assumptions are consistent across comparable runs. Terminal growth has an explicit reinvestment/return basis where applicable, and bank growth/payout respects funding and capital requirements.
- Each production profile agrees with an independently calculated reference within versioned tolerances and passes relevant stress cases. Quantitative materiality, rounding, freshness, and update rules are explicit and tested.
- The same dated input bundle reproduces model numbers; a changed source, spec, assumption, code, or rendered artifact is visible in the manifest and invalidates the applicable approval.
- Material evidence published after Report Date, unresolved source conflict, missing source/unit/period, register failure, and failed numerical reconciliation cannot enter a published Company Update.
- Every public route checks the same publication state. Direct URLs cannot bypass review, and archived versions remain identifiable as archives.
- All material forecast changes trace from source or labelled Analyst Assumption through profile driver and fiscal year to earnings/cash flow and selected valuation sensitivity. Irrelevant news has zero model effect.
- Selected value, cross-checks, downside/upside scenarios, cover, exhibits, PDF, HTML, and Audit Trace use consistent numbers and status. A PDF's existence never changes Release Status.
- The current supported ticker batch receives fresh evidence and a report-by-report matrix of status, method, forecast basis, source coverage, news retrieval, review state, and remaining blockers. Missing evidence remains a precise Draft or Assumption-Led limitation.
- Each published report has a reviewer-attested frozen bundle, visible methodology and material limitations, a recorded publication event, and a predecessor/successor relationship when revised.
- Material conclusions on business quality, governance, ownership, and liquidity have dated evidence and a stated implication. Prospective forecast evaluation preserves original estimates and reports errors and scenario coverage against declared baselines with sample limitations.

## 10. External professional benchmarks

Use these as quality benchmarks, not a claim of CFA certification or Indonesian regulatory approval:

- [CFA Institute Standard V(A): Diligence and Reasonable Basis](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-v-a): research conclusions need a reasonable, diligent analytical basis, including when models are used.
- [CFA Institute Standard V(B): Communication](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-v-b): explain process and material risks; distinguish facts from opinions and forecasts.
- [CFA Institute Standard V(C): Record Retention](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-v-c): retain records supporting investment analysis and communications.
- [CFA Institute Standard VI(A): Disclosure of Conflicts](https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-vi-a): identify and disclose material conflicts that could affect objectivity.
- [CFA Institute: Evaluating Quality of Financial Reports](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/evaluating-quality-financial-reports): assess accounting policies, recurring earnings, cash conversion, and management incentives when evaluating reported results.
- [CFA Institute Research Foundation: Investment Model Validation](https://rpc.cfainstitute.org/research/foundation/2024/investment-model-validation): validate models with explicit attention to assumptions, uncertainty, and the robustness of their results.

The first concrete milestone is **Slices A–C**: a documented publication policy, one enforced public artifact path, and a point-in-time Evidence Register whose critical failures block distribution. Model work follows on this trustworthy base, one profile at a time.
