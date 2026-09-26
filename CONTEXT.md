# Sektoral

Sektoral turns a locally held snapshot of Sectors data on an IDX-listed issuer into a sourced Company Update for Indonesian equity analysts, and shows where the evidence stops.

## Language

### Outputs

**Company Update**:
The sourced research report on one issuer as of one Report Date, rendered as a web page and optionally a PDF.
_Avoid_: report card, research note

**Report Date**:
The date a Company Update is written for; evidence published after it is excluded, and a market price keeps its own date.
_Avoid_: run date, today

**Audit Trace**:
The record behind a Company Update: every data read, agent step, Method Gate and Stage Check verdict, blocker and assumption with its source.
_Avoid_: log, debug output

**Partial Result**:
A Company Update whose evidence could not support every section; the missing evidence is shown, never filled in.
_Avoid_: failed run, degraded report

**Report Gallery**:
The collection of finished Company Updates with their rating, target, method and status.

**Run Replay**:
A finished run played back step by step: each agent step, tool call, Method Gate verdict and Method Chain decision in the order it happened. A run stored before its steps were recorded is rebuilt from its Audit Trace, and its timing is labelled as estimated.
_Avoid_: recording, demo mode

### Evidence

**Sectors Snapshot**:
The local copy of Sectors data that is the only source of market data; it never expires and is refreshed only on purpose.
_Avoid_: Sectors API, live data, database

**Issuer Evidence**:
Dated metrics transcribed from an issuer's official release, used when the Sectors Snapshot omits them; it can be quoted but does not by itself approve a forecast or valuation.
_Avoid_: manual input, source pack

**Latest Interim Actuals**:
The issuer's most recent official period result (for example 1H26) published by the Report Date, treated as actual rather than context.
_Avoid_: latest quarter, recent results

**Period Basis**:
Whether a period figure is cumulative year to date (Q1, 1H, 9M, FY) or a standalone later quarter or second half derived from them; growth compares only the same length, basis and consolidated or parent scope.
_Avoid_: quarter (unqualified), YTD mixed with quarterly

**Earnings Normalization Ledger**:
Reviewed, dated bridge from reported to recurring attributable earnings: each one-off item with its tax and minority effect, restatements kept as new vintages; without it earnings are used as reported.
_Avoid_: adjusted earnings, core profit (unsourced)

**Corporate-Action Ledger**:
Dated, sourced splits, rights issues, placements, buybacks and conversions that set the share count and per-share history known at a Report Date; pending actions stay conditional scenarios.
_Avoid_: share changes, dilution (unqualified)

**Share Ledger**:
The issuer's dated official register counts (outstanding, net of treasury shares), the Corporate-Action Ledger between them, the reported weighted averages and potentially dilutive instruments; consecutive counts must reconcile through the actions. Its Report Date count is the one share count every per-share figure uses.
_Avoid_: share count (unsourced), issued shares as the denominator

**House Assumption Set**:
The versioned discount-rate and terminal-growth parameters every run uses, each with currency, tenor, basis, kind, review range, dated benchmark and rationale; issuer-specific deviations are not supported.
_Avoid_: defaults (unqualified), house view

**Terminal Economics**:
The per-run check that a perpetuity agrees with its own growth, reinvestment, returns on new capital (FCFF) or retention and ROE (bank), in the cash-flow currency.
_Avoid_: terminal sanity check

**Core Earnings**:
First-forecast-year parent earnings after the reviewed normalization bridge; P/E and P/B-ROE value them, while the income statement stays as reported.
_Avoid_: adjusted profit, recurring profit (undefined)

**Market Quote Override**:
A dated closing price newer than the one in the Sectors Snapshot.

**Web News**:
Dated headlines from Indonesian business media, used as narrative context only; no figure ever comes from it.
_Avoid_: news source, market data

**Signal**:
A deterministic fact computed from the Sectors Snapshot (a peer rank, a year-on-year move, a flow streak) with an id that agent conclusions must cite.
_Avoid_: metric, indicator, feature

**Provenance Status**:
Whether a datapoint is an actual, company guidance, or an analyst assumption; guidance is never labelled actual.

**Analyst Assumption**:
A judgement with a stated basis, source and uncertainty range, always labelled as such and never presented as issuer data.
_Avoid_: estimate, default

**Peer Group**:
The IDX-listed companies that share the issuer's business model, reviewed per issuer with a reason for each peer and each exclusion; foreign listings are never peers. When fewer than three such peers have data, the issuer's Sectors peer table stands in and the report says why.
_Avoid_: comps, sector, sub-sector

### Agents

**Planning Analyst Agent**:
The agent that writes a research question and hypotheses, chooses which tools to call after each result, and gives a verdict on each hypothesis.
_Avoid_: research agent, analyst bot

**Hypothesis Verdict**:
The Planning Analyst Agent's conclusion on one hypothesis: supported, not supported, or unanswered, citing Signals.

**Research Agent**:
The agent that reads only the Sectors Snapshot and writes a qualitative Research Brief; it produces no forecast or valuation.

**Research Brief**:
The Research Agent's evidence-linked summary, whose citations are checked against the rows actually read.

**Forecast Assumption Agent**:
The agent that turns dated issuer results and ticker news into bounded, source-matched Analyst Assumptions.

**Host Fallback**:
A labelled summary the system writes itself when an agent's output still fails validation after one repair.

**Run Memory**:
The per-ticker record of earlier runs that briefs the next plan and drives "since the last run".

### Forecast

**Model Profile**:
The business archetype that decides which drivers, methods, Stage Checks and metrics apply: going concern, financial institution, or finite-life mining. A ticker never selects it.
_Avoid_: sector, company type

**Stage Classification**:
The sourced judgement of an issuer's life-cycle stage, steady-state history, commodity dependence and segment mix that feeds method selection; an analyst may override it.

**Screening Forecast**:
A forecast extrapolated from history (CAGR, three-year averages, capex equal to D&A, flat debt); useful as a diagnostic but never production evidence.
_Avoid_: base case, forecast (unqualified)

**Analyst Scenario**:
A full-year path built from the Latest Interim Actuals plus agent-chosen second-half and out-year assumptions; it can support an assumption-led target but is never a production forecast.
_Avoid_: forecast, LoM forecast, projection

**Bank Driver Scenario**:
An Analyst Scenario for a bank set as yearly drivers (loan growth, NIM, non-interest income to NII, cost-to-income, cost of credit, optionally deposit growth) from which the bank model derives NII, provisions, profit, the balance sheet, equity, dividends and a screening CAR; every other parameter holds at the bank's own history under a stated rule.
_Avoid_: bank forecast, NIM forecast, earnings scenario (for a bank that has one)

**Forecast Plan**:
A validated set of Analyst Assumptions tied to the exact evidence it was built on, reused while that evidence is unchanged.

**Physical Chain**:
For a finite-life miner, the chain from reserves through throughput, recovery, processing and realized price to revenue, costs and cash flow.
_Avoid_: operating model, bridge

### Valuation and release

**Method Gates**:
The six checks whose verdicts order the Method Chain: 0 business model, 1 data eligibility, 2 ownership structure, 3 cyclicality and operating stage, 4 life-cycle stage, 5 output sanity (the extreme-result threshold). Financial institutions are judged on Method Gates 0 and 5 only.
_Avoid_: Gates 0-5, gate (unqualified)

**Stage Checks**:
The reasonableness checks run at each stage of building a Company Update: S1 intake, S2 forecast, S3 valuation (for example S2.9 for a complete, sourced driver chain).
_Avoid_: G1/G2/G3, Gate 1/2/3, gate (unqualified)

**Method Chain**:
The ordered list of valuation methods for an issuer (primary, then fallbacks, then a last step), fixed from its Method Gate verdicts before any value is computed.
_Avoid_: method ranking, blended valuation

**Primary Method**:
The first method in the Method Chain, and the one the Model Profile considers correct for the business.

**Insufficient**:
A method's state when a required input is missing or a structural check fails; only this moves the Method Chain to the next method.
_Avoid_: rejected, failed, unreasonable

**Selected Method**:
The first sufficient method in the Method Chain, which alone sets the target price; other sufficient methods are only cross-checks and are never averaged in.

**Last Step**:
The final, assumption-led method in a Method Chain (for example FY EV/EBITDA for miners, FY PER for banks), with its own evidence requirements.

**Method Override**:
An analyst's recorded choice of method that replaces the system's proposal, shown in the Company Update alongside the system's proposal.

**Release Gate**:
The check that decides whether a Company Update may carry a target price and rating. The only term that uses the bare word "gate".
_Avoid_: approval, sign-off

**Release Status**:
The Release Gate's outcome: production-ready, distributable assumption-led, or draft non-distributable.

**Production-Ready**:
Released on a sourced, reconciled driver forecast and the Model Profile's Primary Method.

**Assumption-Led**:
Released on an Analyst Scenario or a Last Step, with every assumption labelled; the forecast is still not production-ready.
_Avoid_: production, provisional

**Draft**:
Not distributable; the target price and rating are withheld, and each blocker is named.
_Avoid_: preview, internal

**Blocker**:
A named, critical gap that forces a Draft; it is never turned into a caveat.
_Avoid_: warning, caveat

**Target Price**:
The per-share value from the Selected Method, shown only when the Release Gate passes.
_Avoid_: fair value, intrinsic value

**Rating**:
Buy, Hold or Sell from the upside to the Target Price, or Review Required when that upside is extreme.
_Avoid_: recommendation, call

**Review Required**:
The rating when upside exceeds +100% or downside is worse than -50%; it needs a sourced fundamental thesis and a stated model limitation.

### Publication

**Publication Bundle**:
The frozen Company Update, Audit Trace, manifest, rendered files, and analyst attestation identified by one publication ID.

**Publication State**:
Whether a Publication Bundle is built, analytically eligible, awaiting review, approved, published, superseded, or withdrawn; it is separate from Release Status.

**Archived Company Update**:
A previously approved Publication Bundle retained with its original identity after a newer bundle replaces it.

## Relationships

- A **Model Profile** and a **Stage Classification** feed the **Method Gates**, whose verdicts fix the **Method Chain**.
- **Stage Checks** failing on a critical input make every driver-based method **Insufficient**, so the chain can reach its **Last Step**.
- The **Method Chain** yields one **Selected Method**; the **Release Gate** then decides the **Release Status**.
- Only a **Production-Ready** or **Assumption-Led** **Release Status** allows a **Target Price** and **Rating**.
- A **Hypothesis Verdict** cites **Signals**; **Web News** may accompany it but cannot stand alone.
- An **Analyst Scenario** is anchored to **Latest Interim Actuals**; a **Screening Forecast** is not.
- A **Bank Driver Scenario** is an **Analyst Scenario**: the DDM values the parent profit and dividends the bank model derives from it, so it stays **Assumption-Led**.
- A **Run Replay** shows the same steps and **Method Gates** verdicts as the live run it replays; it never adds a step the **Audit Trace** does not hold.
