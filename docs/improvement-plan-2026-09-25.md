# Improvement plan (after PR #11)

State on 25 Sep 2026, `main` at `f2bac4f`: 9 company updates published as `distributable_assumption_led`. The template harness passes them with 0 blockers and 0 warnings. 845 Python and 15 web tests pass. The Command Deck UI runs live and replays.

The goal of this plan is to move the reports from "AI-assisted drafts with an audit trail" toward institutional grade, then polish the demo.

Each item has an acceptance check. Effort is rough: S is under half a day, M is 1–2 days, L is 3 or more days.

---

## Phase 1: fix what a professional would challenge first

### 1.1 BBRI capital path (M)
**Problem:** the bank driver model pays out 92% of profit while loans grow about 10% a year. Equity barely moves, so by FY28 the CAR proxy falls below its historical low and LDR passes 100%.

**Do:**
- Add a capital constraint in `app/bank_model.py`: a minimum CAR (the issuer's historical low, or a stated policy value) and a maximum LDR.
- When a year would breach either limit, lower the payout for that year, or cap loan growth. State which one applies.
- Show the constrained payout in the DDM (`app/scenario_value.py`) and in the dividend exhibit.

**Accept when:**
- CAR ≥ the floor and LDR ≤ the cap in every forecast year, for BBCA and BBRI.
- DPS in the DDM equals payout × parent profit on the constrained path.
- There are tests for a breach and for the adjustment.

### 1.2 SSIA capex and the balancing short-term debt (S–M)
**Problem:** FY26F capex of Rp2,2 trillion is funded entirely by a model-drawn short-term debt line. That debt reaches Rp3,2 trillion by FY30 and is never repaid.

**Do:**
- Check the agent's capex intensity against SSIA's guidance (FY25 and 1H26 presentations).
- If guidance is lower, re-run the forecast agent for SSIA only: `python -m app.rebuild --refresh-assumptions SSIA`.
- Show the balancing debt as its own line in the balance sheet and cash flow, not only in a note.
- Add a harness warning when that debt exceeds a set share of equity.

**Accept when:**
- The capex path cites a dated source.
- The balancing debt is visible and explained in the report.

### 1.3 AMMN contrarian call (M)
**Problem:** Sell Rp2.830 against a published analyst average of about Rp6.800. The gap comes mainly from:
- the expired export permit (feed capped at smelter capacity);
- Elang at 50% probability;
- the licence horizon to 2050.

**Do:**
- Write a one-page reconciliation exhibit: our value → the consensus value, step by step (permit, Elang, horizon, price deck, WACC).
- Test each driver in the sensitivity section.

**Accept when:** a reader can see which assumption explains each part of the gap.

---

## Phase 2: source the policy parameters

### 2.1 Discount-rate inputs (M)
**Problem:** ERP 4%, CRP 2,5%, beta 1,1 and terminal growth (3,5% Rp, 3,0% US$) are labelled as analyst policy values with no market source.

**Do:**
- Add a dated source or benchmark for each value, with no inventing:
  - ERP: a published survey or implied-ERP series;
  - CRP: the Indonesian sovereign CDS or bond spread over UST;
  - beta: a regression on IDX prices (IHSG vs stock, 2–5 years of weekly data) using `data/idx_history`;
  - terminal growth: long-run nominal GDP (IMF WEO, dated).
- Keep the policy value if it differs, and show the benchmark next to it.

**Accept when:** the WACC and CoE exhibits show each input with its source and date, or an explicit "policy vs benchmark" row.

### 2.2 Consensus comparison (M)
**Do:**
- Add a "house vs consensus" row set (revenue, EBITDA, net profit FY26F–FY27F) where consensus data is available from a source you can cite.
- The template marks the EPS consensus table as optional, but reviewers expect it.

**Accept when:** each report either shows consensus with its date and source, or states it is unavailable.

---

## Phase 3: benchmark and data gaps

### 3.1 Benchmark against real broker reports (M per ticker)
- AMMN is done (`spec/20260629-AMMN.pdf`).
- Pick 2–3 more with published reports, such as GMFI (the Kompas Saham PDF in the main checkout's `spec/`), BBCA and SIDO.
- Compare method, key assumptions, forecast and TP.
- Record each gap and whether it is a data error, a methodology difference or an assumption difference, in a follow-up to `docs/e2e-self-review-2026-09-25.md`.

**Accept when:** every gap above 20% of TP is explained or fixed.

### 3.2 Data still missing (S each)
- **POWR:** add the official US$ FY2024–FY2025 annual figures to `data/issuer_evidence/POWR.json`. Its statements then switch to US$ like AMMN and GMFI, and match its US$ DCF.
- **INET:** save the two IDX filings locally for the record. The URLs are in the INET evidence pack and in the PR #11 notes.
- **BBCA free float:** read the monthly shareholder registry (IDX, 9 Sep 2026), confirm the position date, and adjust for affiliates of PT Dwimuria Investama Andalan if the data allows.
- **GMFI peers:** only CASS and HELI have valid multiples. Consider regional MRO peers in a clearly separate "regional reference" table. That table must not feed the method chain, because peers used for valuation stay IDX-only by rule.
- **AMMN unit cost forecast:** C1 is n.m. for forecast years. Add a mine-plan cost per lb if the LoM can support it.

### 3.3 Analyst-agent output quality (S–M)
- Clean the validator messages at the source (`agents/analyst/run.py`), not only in the UI.
- Reject topic or index pages in the news register (the BBRI register contains a Bisnis.com topic page).
- AMMN's hypotheses all ended "belum terjawab": check why the synthesis couldn't decide them.

---

## Phase 4: analyst review step (L)
The biggest step toward institutional grade: a human approves the agent's assumptions before a report publishes.

**Do:**
- After the forecast agent runs, add an "assumptions review" state for the job.
- In the web app, show the plan (drivers, sources, rationale) with approve and edit controls. Edits are recorded with the analyst's name and reason, in the same way as `data/method_overrides/`.
- Publish only after approval. The audit trace records what was changed, and by whom.

**Accept when:** a report cannot move from draft to published without a recorded approval.

---

## Phase 5: demo and UI polish (S each)
- **Fresh runs:** re-run all 9 live once, to get fresh forecast plans and replays with real timing. Review every target price that moves, starting with BBRI and SSIA. Compare the result against the current published set before replacing it.
- **Mobile deck bar:** "Cara" is too short. Use an icon-only F3 with an accessible label, or a clearer word.
- **Hypothesis panel:** replace the amber wash over the whole block with a per-row hold light.
- **Landing:** its five sections share one layout. Give at least one of them the Deck's console grammar.
- **Trace page:** show the bank driver rows (loans, NIM, cost of credit), which the API already returns.
- **Web bundle:** code-split the Deck and the landing to clear the chunk-size warning.

---

## Housekeeping (S)
- Delete old output folders in the session worktree:
  - `out/reports-final`
  - `out/rebuild-*`
  - `out/evidence-check*`
  - `out/harness-check`
  - `out/bank-drivers`
  - `out/live-demo`

  The published set is copied to the main checkout's `out/reports`.
- Remove the database backups once you're satisfied:
  - `data/sectoral.db-bak-20260925-cleanup` (in the worktree);
  - `data/sectoral.db-bak-20260925-pr11` (in the main checkout).
- Delete the merged branch `claude/ui-revamp` and its worktree.
- Decide what to do with the untracked `spec/Kompas Saham - GMFI.pdf` in the main checkout.

## Suggested order
1. Before showing anyone beyond friends: 1.1, 1.2 and 3.2 (POWR).
2. For credibility: 2.1, then 3.1 on two tickers.
3. For institutional grade: Phase 4.
4. Before the demo video: Phase 5 (live re-runs first).
