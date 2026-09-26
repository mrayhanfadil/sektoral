# Coverage completion: all nine tickers Production-Ready and published

**Date:** 2026-09-26  **Owner:** Sektoral Team (decisions, review), Claude (build)
**Follows:** [institutional research grade](2026-09-26-institutional-research-grade.md), slices A-H complete in code.

## Goal

Every covered ticker has a published Company Update that is Production-Ready (`distributable`), approved by an authenticated reviewer on its frozen bundle, with its forecast frozen in the forecast ledger. Where a ticker cannot reach that honestly, it is published as Assumption-Led with its named blockers, never promoted by relabelling.

## Baseline (2026-09-26)

Source: [coverage baseline](../baselines/2026-09-26-coverage.md), `python -m app.coverage --folder <run>`.

| Ticker | Profile | Status on a 26 Sep run | Missing for Production-Ready |
|---|---|---|---|
| POWR | going_concern_fcff | Production-Ready, Buy Rp1.490 | authenticated approval |
| BBRI | financial_ddm | Production-Ready, Buy Rp3.960 | authenticated approval |
| AMMN | finite_life_mining | Production-Ready, Sell Rp2.840 | authenticated approval |
| BBCA | financial_ddm | Assumption-Led, Hold Rp6.575 | bank driver file |
| JPFA | going_concern_fcff | Assumption-Led, Hold Rp2.320 | operating driver file |
| SIDO | going_concern_fcff | Assumption-Led, Buy Rp448 | operating driver file; decision D4 |
| GMFI | going_concern_fcff | Assumption-Led, Buy Rp81 | operating driver file |
| INET | going_concern_fcff | Assumption-Led, Sell Rp222 | operating driver file; decisions D5, D6 |
| SSIA | going_concern_fcff | Assumption-Led, Sell Rp1.370 | operating driver file; decision D7 |

Every ticker also has business-quality dimensions unanswered (all eight for the six Assumption-Led tickers; governance for all nine).

## Decisions (Sektoral Team)

| ID | Decision | Options | Needed by |
|---|---|---|---|
| D1 | Approve POWR and BBRI | approve / request edits / reject | Checkpoint 1 |
| D2 | BBRI guidance source | accept the Investing.com call transcript / supply BBRI's 1H26 presentation | Checkpoint 1 |
| D3 | AMMN without a working-capital schedule | approve with the stated limitation / hold Assumption-Led until working capital is modelled (task T3) | Checkpoint 1 |
| D4 | SIDO outstanding shares | note 1c total 29.520.300.000 (current) / movement arithmetic 29.435.200.000 / EPS note 29.430.685.529 / IDX register (supply) | Checkpoint 2 |
| D5 | INET weighted-average shares | ledger's dated derivation 21,98 bn (current) / ask the issuer | Checkpoint 3 |
| D6 | INET primary method | move to the operating-model DCF / keep the peer EV/EBITDA and stay Assumption-Led | Checkpoint 3 |
| D7 | SSIA primary method | build a production holding-SOTP path (listed stakes + operating model for the estate business) / move to an operating-model DCF / stay Assumption-Led | Checkpoint 3 |
| D8 | Governance dimension | name an acceptable dated source (e.g. an ASEAN CG Scorecard or OJK governance report) / keep unanswered | Checkpoint 4 |
| D9 | Open policy items | display tie-out formula; stale commodity fallback; INDOGB benchmark age; review-role authorization | Checkpoint 4 |
| D10 | Distribution | push `codex/insti-grade` and merge; which folder the server serves; Indonesian legal/compliance review | Checkpoint 1 (push), Checkpoint 5 (legal) |

## Tasks

- **T1 BBCA bank driver file** (`data/bank_drivers/BBCA.json`): 31 Dec / 30 Jun balances in the BBRI definitions, 1H26 lines, disclosed CAR requirement (risk-profile minimum plus buffers), cost of funds, payout policy, five labelled driver rows with BBCA's own guidance; reference DDM must agree.
- **T2 Operating driver files** (`data/operating_drivers/<T>.json`), in order JPFA, SIDO, GMFI: segment volumes and realized prices, per-unit and fixed costs, depreciation, committed and sustaining capex, working-capital days, debt, tax, payout, each actual cited by page and each forward driver labelled; first half equals the official actual; terminal and reference checks pass. A ticker whose filings do not disclose volumes records that gap and stays Assumption-Led.
- **T3 AMMN working capital** (if D3 = hold): receivables, inventories and payables in the LoM cash flows, with the reference updated.
- **T4 INET and SSIA** per D6 and D7.
- **T5 Business quality** (`data/business_quality/<T>.json`) for the six tickers without a file, and governance for all nine per D8.
- **T6 Catalyst thresholds:** tie each catalyst row to a model driver and its thesis-change threshold from the driver-to-value table.
- **T7 Publication:** after each checkpoint's approvals, the approved folder is served and each approval freezes the forecast.

## Checkpoints

Each checkpoint ends with: the full test suite passing, `git diff --check` clean, a fresh dated rebuild of every ticker (`app.rebuild --as-of`), a coverage run written to `docs/baselines/`, a revision comparison against the previous checkpoint, and this plan's status table updated.

### Checkpoint 1: first three published
- **Needs:** D1, D2, D3, D10 (push).
- **Work:** T3 only if D3 = hold; rebuild POWR, BBRI, AMMN dated on or after 2026-09-26 with PDFs; reviewer attestation on each frozen bundle; server serves the approved folder.
- **Done when:** the three are `approved` in `assumption_review.status`, each has a frozen `forecast_ledger` record keyed by its publication, the public routes serve exactly those bundles, and the other six remain labelled Assumption-Led.

### Checkpoint 2: BBCA and JPFA Production-Ready
- **Needs:** none (D4 is only needed for SIDO).
- **Work:** T1 (BBCA), T2 (JPFA), T5 for both.
- **Done when:** both reach `distributable` on a fresh run with the reference agreeing within 0,5% and terminal economics consistent (or not applicable), the coverage table lists no next action for them, and both are approved and frozen.

### Checkpoint 3: SIDO, GMFI, INET, SSIA resolved
- **Needs:** D4, D5, D6, D7.
- **Work:** T2 (SIDO, GMFI), T4 (INET, SSIA), T5 for all four.
- **Done when:** each ticker is either `distributable` and approved, or Assumption-Led with a coverage next action that names a specific missing disclosure (not a missing file or unchosen method).

### Checkpoint 4: quality and policy completeness
- **Needs:** D8, D9.
- **Work:** governance dimension per D8; T6; the four policy items implemented or documented as decided.
- **Done when:** no business-quality dimension is unanswered without a stated reason, every catalyst row names a driver and threshold, and the release-policy snapshot lists no unresolved item.

### Checkpoint 5: first monitoring cycle
- **Needs:** D10 (legal/compliance review under way).
- **Work:** at the 9M26 filings (OJK deadline 2026-10-31), run `app.publication_monitor` on the served folder; track each frozen forecast; rebuild candidates where results are new; record revision bridges.
- **Done when:** every published report shows current or stale with its triggers, each 9M26 result has a tracking record, each material change has a review task with a recorded disposition, and the legal/compliance review outcome is recorded before any claim of regulated research status.

## Status

| Checkpoint | State | Date | Notes |
|---|---|---|---|
| 1 | done under ADR 0014 (2df9b40) |  2026-09-26 | Accepted by the Sektoral Team: POWR forward assumptions (industrial volume +5,0/+4,5/+4,0/+3,5% FY27-FY30, flat US$ tariff and fuel cost per MWh, 25% tax); D2 resolved: BBRI 2026 guidance from the Investing.com call transcript, FY27-FY30 analyst drivers and the guided 70%/60% payout (TP Rp4.570 to Rp3.960) accepted. D3 resolved by modelling (T3 done, 4bf36d4): AMMN working capital from the 30 Jun 2026 statements (receivable, product-inventory and operating-payable days, supplies released at mine end, customer advance settled in product 2026-2027) and Elang probability 65% (approvals 0,80 x FID 0,80) replacing the flat 50%; per share Rp2.839 to Rp2.843 (working capital -75, advance -89, Elang +168), Sell Rp2.840 unchanged. POWR, BBRI and AMMN still need authenticated attestations on their frozen bundles. Publication changed to two tiers (release policy 1.3.0): the nine cp4 reports publish automatically, labelled not analyst-reviewed, with forecasts frozen; an authenticated approval (D1 accepted in chat, attestation form now pre-filled) only adds the analyst badge. Branch pushed (D10) |
| 2 | ready to start | | |
| 3 | waiting on D5-D7 | 2026-09-26 | D4 accepted: SIDO shares = note 1c total 29.520.300.000. D5 recommendation: keep the ledger's 21,98 bn (FY26 EPS Rp3,06; INET's own 16,62 bn gives Rp4,04; TP Rp222 Sell unchanged either way), awaiting confirmation |
| 4 | D8, D9 decided; T5, T6 open | 2026-09-26 | D8: governance kept unanswered with that stated reason. D9 decided and implemented as release policy 1.3.0 (1657665): tie-out formulas recorded per check; a deck still stale after fallback blocks mining production use; INDOGB benchmark at most 7 days, ERP/CRP/growth 400 days; role table (analyst views, reviewer and compliance approve and withdraw). The snapshot lists no unresolved item. Fresh dated rebuild of all nine under policy 1.3.0 (out/reports-20260926-cp4, PDFs): POWR, BBRI, AMMN Production-Ready, six Assumption-Led, ratings and TPs unchanged; [coverage](../baselines/2026-09-26-checkpoint-4-coverage.md), [revision](../baselines/2026-09-26-checkpoint-4-revision.md) |
| 5 | scheduled for the 9M26 filings | | |
