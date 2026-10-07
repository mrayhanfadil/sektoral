# Report audit and hackathon compliance, 25 Sep 2026

Scope: the nine published Company Updates in `out/reports/` (AMMN, BBCA, BBRI, GMFI, INET, JPFA, POWR, SIDO, SSIA), their Audit Traces and review records, and the repository against the [official rules](hackathon/rules.md) and the [AI Agents & Assistants track](../tracks/). This is the 25 Sep 2026 baseline audit: AMMN and JPFA PDFs were dated 25 Sep; the other seven were dated 24 Sep. The baseline observations are preserved below. **Section 7 records execution on 26 Sep, corrects findings disproved by the current engine, and supersedes stale status statements.** The source database and published report outputs were not modified; isolated rebuilds were written under `/tmp/sektoral-audit-20260926/`.

## 1. Verdict

The code and report pipeline are materially cleaner, but submission eligibility is **not yet verified**. The current checkout starts on 22 Sep 2026, inside the rules' build window, and no secret was found in the checked tree/history. The final available backend run has 871 passing tests, three skips, and two PDF-render failures; it excludes `test_record_demo.py` because this environment lacks FastAPI. The custom analyst agent is central to the workflow. Two items remain submission blockers:

1. **Repository visibility and pre-code onboarding need portal evidence.** The baseline GitHub check reported PRIVATE; the 26 Sep `gh repo view` attempt could not connect, so current visibility is unverified. The local team roster still shows onboarding as ⚪. Rules §03 requires every participant to complete onboarding before any project code is written; if the roster is accurate, this is an eligibility failure, not just a pending checklist item.
2. **The baseline reports conflicted with rules §12 ("must not provide financial advice").** The regenerated HTML now uses model-scenario language, suppresses action ratings, labels analyst assumptions, and includes an information/analysis disclaimer. The nine source PDFs remain unchanged and still need replacement and review before submission. See §7 and [`disclaimer-template.md`](hackathon/disclaimer-template.md).

The baseline arithmetic was generally reproducible, but it carried shared template defects and issuer-specific contradictions. The execution pass fixed or reclassified several of them; see §7 for the present disposition and unresolved model risks.

## 2. Hackathon compliance matrix

| Requirement (rules) | Status | Evidence |
|---|---|---|
| Repo created in build period, no previous-project code (§05) | Pass for observed history; provenance caveat | `sektoral` first commit `2160fdc` is 2026-09-22 23:02 WIB; first report-pipeline commit is also 22 Sep. The `docs/integration/` and `data/sectors_cache.db` imports are documentation/data snapshots dated 29 Aug (inside the build period). Confirm they contain no code/work from a separate prior project; date alone does not satisfy the no-previous-project-work rule. |
| Public repository, public for ≥90 days after 17 Oct (§08) | **Unverified blocker** | Baseline `gh repo view` reported PRIVATE; the 26 Sep check failed to connect to GitHub. The repository must be public at submission and stay public through 15 Jan 2027. |
| No API keys in repo (§08) | Pass | No key patterns in HEAD or history. The `eyJ…` hits are Rails blob IDs in amman.co.id URLs, not JWTs. `.env` was never tracked. |
| Sectors data is core, not decorative (§06) | Pass, with demo caveat | 314 cached Sectors responses cover all nine tickers and core report inputs. Rebuilt exhibit footers credit Sectors and Sectoral. The current demo is cache-backed; do not claim it makes a live upstream request. |
| Working end-to-end prototype (§06) | Pass for HTML workflow | Nine current HTML reports and traces rebuild from pinned stored runs; all pass template/rendered-HTML checks. New PDF workflow is unverified because the browser renderer cannot launch here. |
| AI/LLM custom agent at the core (track 01) | Pass | Planning analyst agent with its own tools, validators, run memory, forecast-assumption agents, method gates and run replay. This is not a wrapper around a stock client. |
| No automated trade execution (§06) | Pass | No broker or order code in `app/`, `agents/` or `web/`. The footer states it too. |
| Not financial advice; disclaimer (§12) | Pass for rebuilt HTML; PDF replacement required | Regenerated HTML uses `Skenario nilai`, model-value comparisons, explicit analyst-assumption labels, and an `INFORMASI DAN ANALISIS, BUKAN SARAN INVESTASI` disclosure. No BUY/HOLD/SELL action rating is rendered. The six assumption-led reports still publish model values; keep the demo framed as analysis, and replace the old PDFs before submission. |
| Every participant onboarded before code (§03) | **Unverified, potentially disqualifying** | [`team-roster.md`](hackathon/team-roster.md) currently shows ⚪ for onboarding, API key and credits. Check actual portal history; if onboarding occurred after code began or not at all, the rule's pre-code requirement is not met. |
| Teaser, judging video, one-sentence statement, social post, track, names (§08) | Not verified | The [checklist](hackathon/submission-checklist.md) remains unchecked; no portal or public-post evidence was inspected. |
| Honest labelling of drafts and gaps (checklist) | Pass in rebuilt HTML; review pending | Six reports are `distributable_assumption_led`; BBCA, BBRI and INET are visibly draft with model values withheld. All nine prior approvals are pending under the result-aware fingerprint. |
| Freeze (§05) | Not yet applicable | Deadline 8 Oct 2026 23:59 WIB. |

## 3. Anomalies that repeat across reports

These are template bugs: fixing the code fixes every report.

| # | Anomaly | Examples | Where |
|---|---|---|---|
| S1 | **Two different numbers labelled "FY26F–FY28F CAGR" in the same report.** Page 1 uses a 2-year CAGR from FY26F. The chart captions use a 3-year CAGR from 2025A but keep the FY26F–FY28F label. | SIDO revenue +5,5% (p1) vs −1,3% (chart); SSIA −2,5% vs +15,7%; BBRI 5,8% vs 11,2%; AMMN 1,4% vs 38,9%; BBCA 8,5% vs 7,4%. Seen in all nine. | `app/report_extras.py:2579`, `:2595`, `:2642-2644` |
| S2 | **The thesis tile counts FX translation as revenue growth for US$ reporters.** FY26F US$ revenue is converted at today's rate and compared with Sectors' FY2025 rupiah figure, which was converted at ~Rp16,736. | GMFI tile 28,8% vs 20,9% in Key Financials; POWR 14,1% vs 6,7%. Both gaps ≈ 17.837/16.736. | `app/narrative.py:3665-3669` |
| S3 | **Bank "Skenario nilai" section prints a second DDM whose payout does not match the basis it cites.** | BBCA: "payout 63,3% (DPS Rp381,0 atas EPS Rp468,4)", but 381/468.4 = 81,3%, and it gives Rp4.980 against a TP of Rp6.575. BBRI: "51,0% (Rp346/Rp376)", but that ratio is 92,0%, and it gives Rp3.270 against a TP of Rp4.570. Its inverse-CoE figure also differs from Exhibit 15/16. | `app/narrative.py:2576-2585` (`_vb` from `ddm.value_bank`) |
| S4 | **Headline templates ignore the forecast.** | "Laba FY26F Menopang Ruang Kenaikan Harga" on GMFI (FY26F profit −15,6%) and SIDO (−31,1%). BBRI is a Buy yet says "harga sudah memasukkan sebagian besar aliran dividen ini". | `app/narrative.py:3641-3643`, `:4368` |
| S5 | **Generic or internal text leaks into client pages.** | Bank reports ask for "FCFF yang direkonsiliasi", "capex, modal kerja". Every non-AMMN report says "forecast driver produksi … (S2.9)". Spec and gate IDs appear throughout: `§3.1`, `§4.4`, `§4.1a`, `§5.4`, "Method Gate 0/3". Also "Jalur band (pola BBTN)" in the BBCA/BBRI reports; citation tokens "(news:4)" and "(sectors_annuals)"; the artifact name "AMMN(2)" (AMMN Exh. 44); and "pertumbuhan didanai leverage yang meningkat" for debt-free SIDO. | `app/narrative.py:2539`, `app/report_extras.py:2736`, agent prose |
| S6 | **The header price differs from the chart's "Terakhir" price.** The header uses a Yahoo quote override; the chart uses a stale series. | BBCA 6.225 vs 6.300; BBRI 3.140 vs 3.190; INET 316 vs 328; POWR 955 vs 965; SIDO 350 vs 354; SSIA 1.750 vs 1.715. Sectors `/daily/` ends 2026-09-11 for BBCA, POWR and SSIA. | chart builder |
| S7 | **"Market cap change, 1 year" contradicts the price change for the same window.** | JPFA mcap +40,1% vs price +8,5%, and SSIA −25,3% vs −1,4%, with no share change. GMFI +220,9% vs −39,1% and INET +263,3% vs +42,6% are driven by share issuance but are still presented as outperformance. | §4 text of each report |
| S8 | **The same multiple, on the same day, has different values in one report.** | AMMN P/E 38,6x (peer table) vs 82,2x (band "kini"). INET P/BV 2,0x vs 7,3x, with negative band axes (−29,9x, −2,2x) and all three percentiles at p39. GMFI P/BV 2,7x vs 3,5x. SSIA P/E 16,2x beside ROE −1,1% and margin −2,0%. | band vs peer data |
| S9 | **Rupiah DCFs use the US$ benchmark template.** | JPFA and SIDO label INDOGB 6,5% as "UST 10Y, Yahoo Finance", benchmark g against US nominal GDP, and add a 2,46% CRP on top of INDOGB. That counts country risk twice and gives a benchmark CoE of 12,0% and 11,5%. The bank reports do this correctly (5,39% rupiah rf + 6,69% total ERP). | discount-rate exhibit |
| S10 | **One policy beta (1,10) for all nine issuers.** | Regression or Blume betas range from 0,25/0,49 (POWR) to 1,15/1,10 (AMMN). POWR's CoE is 12,1% against a 9,7% benchmark (−235 bp). | CAPM inputs |
| S11 | **Two exchange rates for the same source and date.** | AMMN and GMFI use Rp17.837/US$ and POWR Rp17.893/US$, all cited as "Yahoo Finance IDR=X, 2026-09-24". | FX snapshot |
| S12 | **The gallery mixes report dates.** | AMMN and JPFA are dated 25 Sep, the other seven 24 Sep. The consensus was fetched on 25 Sep, so only AMMN and JPFA show it; the rest say "tidak tersedia". JPFA reports 13 analysts but 14/0/0 recommendations. | batch `--as-of` |
| S13 | **Sectors is never credited.** | "Source: Company, Sectoral Estimates" appears under pure-Sectors tables: peers, ownership, foreign flow, sub-sector, commodity. | exhibit footer |
| S14 | **Stray glyphs in PDF footers.** | AMMN p3 "(   )", INET p6 "(   ) … See", POWR p5 "(   $)". | PDF render |
| S15 | **Methodology note contradicts page 1.** | GMFI, JPFA and SIDO: "Exit EV/EBITDA historis emiten tampil berdampingan" vs "kurang dari tiga titik, sehingga cross-check exit tidak dihitung". | methodology block |
| S16 | **Zero working capital in growing DCFs.** | GMFI and INET use 0,0% working-capital intensity because FY2025 non-cash WC was negative, while revenue grows 12–29% a year. | `forecast_statements` |
| S17 | **Mixed languages and product names.** | "Public", "Treasury Stock"; English sentences in AMMN Exh. 50/51. The UI says "Sectoral" (29 occurrences) while the reports and README say "Sectoral" (87), next to a data partner called "Sectors". | copy |

## 4. Anomalies by report

### AMMN: Sell, TP Rp2.840 (−40,0%), SOTP/LoM
- **"PV overhead korporat (571)" is one year of cost, not a present value.** Its basis is "beban umum 1H26 x2". Discounted over a mine life to 2050 at 10,7%, it would be several times larger, so the TP is likely overstated. Section 16, Exh. 42 and Exh. 52 also say PV overhead and asset NAV are "belum tersedia", which contradicts Exh. 21.
- **Two different 2H26 models.** Key Financials and Exh. 16 use 2H revenue US$2.770m and EBITDA US$1.496m. The LoM in Exh. 22 uses US$2.620m and US$1.588m, labelled "panduan FY", with 102 kt of cathode against 81,2 kt implied by guidance (Exh. 7).
- Exh. 44: "FY2026 skenario AMMN(2) 390" vs FY26 capex of US$260m in Exh. 16 and 35. This also leaks an internal file name.
- "Laba bersih" is US$1.168,8m in Exh. 16 (consolidated) and US$1.128,0m in Key Financials (parent), under the same label.
- Exh. 24 steps don't add: 3.630→4.610 is shown as +990 (actual +980); 4.610→5.050 as +446 (+440).
- §8 says "P/E di atas 50x (MDKA, BRMS)", but MDKA is loss-making (Exh. 27).
- Adjusted C1 is (0,54) for FY2025 and (3,37) for 2024 in Exh. 15, while the reported half-year unit cash cost in Exh. 48 is 14,68 and 1,37 for 2025 and −0,40 and 0,43 for 2024.
- The gold price is dated 2026-09-01; copper is dated 2026-09-24.
- §3 gives 2026 sub-sector EPS +68,1% and revenue −11,9%, but Exh. 11 shows "-" for 2026.
- The target is 59% below a consensus of 8/0/0 Buy averaging Rp6.969. This is disclosed, but it will draw scrutiny.

### BBCA: Hold, TP Rp6.575 (+5,6%), DDM
- S1 and S3 (63,3% vs 81,3%; Rp5.600 at 2,44x vs Rp5.725 at 2,38x).
- **The terminal payout goes back to 81,3%** after the capital cap cut the FY29F and FY30F payouts to 75,5% and 72,7%. Terminal DPS is Rp587 vs Rp507 in FY30F (+16% at g 3,5%), and the terminal is 73,7% of value.
- Exh. 17 shows uncapped loan growth (9/9/11/11/10%), while the LDR cap binds from FY27F (8,2/9,0/9,0/8,0%).
- The FY27F rationale mentions "pelemahan 1H26 (annualized 2,44%)", while the same page says loans grew 8% YoY.
- The 2024A cash flow needs a "selisih definisi kas" plug of Rp46.071bn, larger than year-end cash.
- The TP was Rp6.625 when approved and is Rp6.575 as published (P1).

### BBRI: Buy, TP Rp4.570 (+45,5%), DDM
- **Page 1, the thesis and Exh. 18 all say "pertumbuhan kredit FY2026 10,0%".** The capital cap cut it to 4,2% ("dibatasi dari 10,0% ke 4,2%"), and the balance sheet shows 1.517.080 → 1.580.420 (+4,2%). The resulting LDR is 89,3%, while the narrative says "mendekati 94%".
- **The headline and methodology say "payout 92,0%",** but the DDM uses 41,7/42,0/48,6/64,5/62,5% and a 79,4% terminal payout. Terminal DPS is Rp444 vs Rp338 in FY30F (+31%), and the terminal is 80,3% of value. FY26F DPS is Rp176, −49% vs the trailing Rp346.
- **The +22,7% FY26F revenue growth is a data artefact.** 2025A non-interest income is Rp29.508bn (2024A: 54.358), with a +Rp26.117bn non-operating line in the same year. That looks like a reclassification in the Sectors data, and it also produces the 49,1% CIR in 2025A.
- The interim balance sheet (Exh. 5) shows "-" for cash and equity, yet the model uses 1H26 total assets of Rp2.352,0tn.
- FY26F CAR is 21,0%, below the model's own floor of 21,1%.
- **The TP was Rp5.325 when approved and is Rp4.570 as published** (P1).

### GMFI: Buy, TP Rp103 (+83,9%), DCF US$
- S2 (tile 28,8% vs 20,9%) and S4 (profit −15,6% under a "Menopang" headline).
- PER 2024A of 3,0x implies a share price of about Rp10, inconsistent with Exh. 1 (about Rp70 two years ago).
- Working capital is 0,0 in every forecast year. Capex is 1,8% of revenue, below D&A at 2,6%, while the text describes expansion capex.
- Only two valid peers (CASS, HELI). The airlines GIAA and CMPP are listed as "dipakai" but never qualify. [CONTEXT.md](../CONTEXT.md) says the Sectors peer table should stand in when fewer than three peers have data; here it was excluded (toll roads, ports). That is defensible, but it is not what the glossary promises.
- "median tarif efektif FY2025-FY2025" covers a single year. The mcap +220,9% (issuance) is presented as "mengungguli peer".

### INET: Sell, TP Rp222 (−29,7%), peer EV/EBITDA
- **Equity adds all Rp4.336,9bn of June cash.** The model itself says that cash still holds unspent raise proceeds, and it spends them on FY26–28F capex of Rp855/830/683bn. The Rp280,4bn SGI payment on 15 Sep 2026, after the balance-sheet date, is not deducted either.
- Agent prose says "H2/H1 1,05 (di luar ambang deviasi 0,8-1,25)", but 1,05 is inside that range.
- The band exhibit uses a stale basis (see S8), so its implied Rp585 and Rp830 are not meaningful.
- The "median 5 peer 12,8x" silently drops SUPR (52,2x), which is not listed as an outlier.
- FY30F profit is Rp325,0bn on page 1 and Rp330,2bn in Exh. 16.

### JPFA: Hold, TP Rp2.320 (+6,4%), DCF
- **The agent's stated assumptions do not match the model.** The prose says the H2 net margin is held at 7,5% (page 1, §2, §3), but Exh. 14 uses 4,0%. It gives EBITDA margins of 12,5/13,0/13,2/13,0/12,8% for FY26–30F; the model uses 10,5/11,0/10,5/10,0/9,5%. It gives net margins of 8,0/7,9/7,7%; the model uses 5,6/5,2/4,8%. As a result, FY26F profit falls 5% even though 1H26 profit rose 97%. Implied 2H26 parent profit is about Rp1,12tn vs about Rp2,64tn in 2H25 (−58%), with no explanation. The headline says "Laba FY26F Sejalan".
- The valuation is dated 2025-12-31 on FY2025 cash and debt, with no roll-forward to the report date (about 0,7 years at a 9,6% WACC, roughly +7%).
- S9 benchmark mislabels. Consensus shows 13 analysts but 14 recommendations.
- The P/BV reason is self-contradictory: "aset tetap kurang dari separuh total aset; P/BV bukan metode untuk emiten aset berat".

### POWR: Buy, TP Rp1.330 (+39,3%), DCF US$
- S2 (tile 14,1% vs 6,7%), S10 and S11.
- The EV bridge adds cash of US$298,2m, labelled "neraca interim resmi", while Exh. 5 shows interim cash of US$124,0m. The difference, about Rp193 per share or 15% of the TP, is short-term investments; it should be labelled as such.
- The FY25 EBITDA margin is cited as 32,2% ("sectors_annuals") and "32% historis", while the report's own figure is 30,2%.
- The agent says EBITDA margin is compressed "karena depresiasi aset baru", but depreciation sits below EBITDA.
- PER 2025A is n.m. because "data harga … tidak mencakup tahun ini", but 2024A has a value.

### SIDO: Buy, TP Rp448 (+28,0%), DCF
- S1 with opposite signs (+5,5% vs −1,3%), and S4 (profit −31,1%).
- **The share count ignores 1,9% treasury stock.** "Saham beredar sesudah treasuri" equals shares issued (30.000m), so value per share is understated by about 1,9%.
- The valuation is dated 2025-12-31 on FY2025 cash (Rp462,6bn) although the June interim (Rp475,6bn) is shown. There is no roll-forward.
- S9 benchmark mislabels.

### SSIA: Sell, TP Rp1.370 (−21,7%), holding SOTP
- **Non-controlling interest is 0 in FY26–28F.** It was Rp214bn in 2024A and Rp118bn in 2025A, NCI equity is Rp2.698bn, and the NRCA stake is 63,9%. Parent profit and EPS are overstated.
- Page 1 says "Dengan diskon holding 30,0% nilainya Rp960", but the TP uses a 0% discount (Exh. 20).
- Page 1 cites a "rata-rata band P/E historis 32,9x", while Exh. 26 says the P/E band is not meaningful.
- The risk text says 1H26 capex was "baru Rp330miliar", while the cited source is headlined "SSIA realisasikan capex Rp1,1 triliun".
- "Pemegang saham terbesar adalah Public dengan 51,5% saham."
- The BYD plant opening on 3 Sep 2026 is sourced to an article dated 2026-09-02.
- The cross-checks (DCF Rp580, PER Rp740) are far below the Rp1.370 target, and the cash-balancing debt of Rp3,0tn carries no interest. Both are disclosed.

## 5. Process and repository anomalies

- **P1. The approval gate does not cover what is published.** One reviewer wrote eight approvals at 2026-09-25 10:15:11 UTC, all within the same second, and JPFA's at 10:23. None has a note or an edit. About two dozen commits were merged between 17:10 and 20:58 WIB, and the reports were rebuilt at 21:00. The approval fingerprint covers only the agent plan (`app/assumption_review.py:127-136`), so all nine still read `approved` even where the output changed:

  | Ticker | TP when approved | TP published |
  |---|---|---|
  | BBCA | Rp6.625 | Rp6.575 |
  | BBRI | Rp5.325 | Rp4.570 (−14%) |
  | POWR | Rp1.325 | Rp1.330 |

  The published PDFs carry no reviewer or approval marker.
- **P2.** The repository is private (see §2).
- **P3.** `.env.example` lists variables from another stack (`ADK_PROVIDER`, `SPARK13_MAX_TOKENS`, `OPENCODE_GO_API_KEY`, `~/.config/sectors-be/env`, "/agent routes") that the app does not read. It is not a violation, but judges may ask about it.
- **P4.** One commit (`0cc9af0`) is authored with a work e-mail address (`…@seryucargo.com`), which becomes public when the repo does.
- **P5.** `team-roster.md` and `onboarding-blocker.md` are stale (see §2).
- **P6.** The Sectors snapshot was fetched 12–23 Sep. Header prices come from dated Yahoo overrides in `data/market_quotes/`, which ADR 0002 allows, but the video narration and README should say so plainly.

## 6. Fix order before the 8 Oct freeze

1. Make the repository public. Decide whether to rewrite the work e-mail author on `0cc9af0` first.
2. Settle §12. Either reframe the rating and TP as a labelled model scenario ("nilai model di atas/di bawah harga"), or keep them but replace the PDF disclosure with the boilerplate from `disclaimer-template.md`. Either way, drop "rekomendasi", credit Sectors, and add a README Disclaimer section.
3. Fix the template bugs S1, S2, S3 and S4. They touch every report and are each small.
4. Fix JPFA (prose vs model: either stop clamping silently or regenerate the prose from the clamped numbers), BBRI (narrate the capped loan growth and the real payouts), SSIA (NCI), INET (cash net of committed capex and the SGI payment), AMMN (PV the overhead or relabel it) and SIDO (treasury shares).
5. Rebuild all nine with one `--as-of` date. Then re-review them individually, and extend the approval fingerprint to cover rating and TP so an engine change resets the review.
6. Remove leaked internal IDs from client pages (S5), fix the footer glyphs (S14), and pick one product name (S17).
7. Update the roster and onboarding status and work through the submission checklist.

## 7. Execution record, 26 Sep 2026

### Rebuild and release status

- Rebuilt AMMN, BBCA, BBRI, GMFI, INET, JPFA, POWR, SIDO and SSIA from their stored traces into `/tmp/sektoral-audit-20260926/rebuilt-2026-09-25/`, with a common report cutoff of 25 Sep 2026 and the run-manifest market snapshots pinned. No research agent, paid LLM, or new upstream fetch was used.
- The original `data/sectoral.db`, `out/reports/` records and the nine source PDFs were not changed. Rebuilt HTML and traces are audit artifacts under `/tmp`.
- Six rebuilt reports remain `distributable_assumption_led` (AMMN, GMFI, JPFA, POWR, SIDO, SSIA). BBCA, BBRI and INET are `draft_non_distributable`; their old approval fingerprints no longer match. All nine reviews are pending under the new result-aware fingerprint. No report was re-approved automatically.
- A gap remained after the first redaction change: drafts had lost the cover value but still showed the candidate price and sensitivity page. The shared finalizer now removes draft valuation pages and replaces them with a pending-review notice. Regression tests cover this case; the rebuilt BBCA, BBRI and INET HTML contain no candidate model price.
- All nine reports have a 25 Sep 2026 cutoff and 24 Sep close; an HTML check confirmed the chart's final close equals each cover quote. The template and rendered-HTML harness reports zero blockers across all nine and one warning: SSIA's cash-balancing debt exceeds 25% of equity in FY26F-FY28F because capex/dividends are not funded in the forecast bridge.
- The six non-draft HTML reports show neutral `Skenario nilai`/`Nilai model` labels, no BUY/HOLD/SELL rating, and an information-and-analysis disclosure. Forecasts are labeled analyst assumptions. The shared narrative no longer claims that the market has or has not priced a scenario.
- PDF generation could not be completed: Playwright's browser process closes at launch (`TargetClosedError`; direct Chromium attempts also exited with `SIGTRAP` during crashpad initialization). The original PDFs are the only PDFs and still contain the baseline copy. No PDF text or visual review of regenerated artifacts is claimed.
- Backend tests: **871 passed, 3 skipped, 2 failed**, with both failures limited to PDF rendering. `tests/test_record_demo.py` was excluded from collection because FastAPI is absent in the environment. Frontend: `npm test` passed 15/15 and `npm run build` passed. `python3 -m compileall -q app` and `git diff --check` passed.
- A first rerun attempt used the misspelled database environment variable and consequently read the default database, where the isolated staged trace keys were absent. It made no report or database changes. Correcting the variable to `SECTORAL_DB` restored the isolated rebuild. This was an execution-environment issue, not missing source traces.

### Findings corrected or reclassified

| Baseline finding | Execution result |
|---|---|
| S1 forecast CAGR used mismatched periods | The chart now uses the forecast range named in its label. |
| S2 USD-reporting revenue growth mixed USD forecast with IDR actual | Growth compares amounts in the same currency. |
| S3 bank page showed a second DDM with a different payout/value | The narrative and exhibits use the selected DDM detail; payout ratios are shown by forecast year and for terminal value. |
| S4 headline could say profit was supported while model profit fell | The headline follows the modeled profit direction. BBRI shows input and effective credit growth separately, including binding constraints. |
| S4 BBRI's cover inferred that the share price had priced dividend flows | Removed the causal market-reading statement. The rebuilt copy reports the scenario DPS/price ratio as an explicitly indicative calculation. |
| S5 internal IDs, agent rationale, and bank FCFF checklist leaked to client copy | Shared prose is sanitized after enrichment; bank-specific gaps and calculated constraints replace conflicting agent text. Rebuilt HTML has no legacy “Kami menetapkan target” phrasing. |
| S7 market-cap issuance was called peer outperformance | The narrative describes market-cap change and its share-count context without claiming outperformance. |
| S9 Rupiah DCFs used the U.S. benchmark/extra CRP | Current IDR discount-rate code uses INDOGB and no separate CRP; JPFA and SIDO exhibits show the IDR policy inputs. The baseline labels are stale. US$ mine models retain UST + CRP. |
| S13 Sectors was not credited | Shared exhibit footers now credit Sectors market/financial data, issuer disclosures, and Sectoral analysis/estimates. All rebuilt HTML passed the source-line check. |
| S15 methodology note claimed an unavailable exit multiple was shown | The note claims an exit EV/EBITDA cross-check only when the data exists. |
| S16 zero working-capital intensity could read as a proven zero requirement | The report now says a negative or missing historical basis does not establish that future working-capital needs are zero. The 0.0% scenario assumption itself remains a model limitation. |
| S17 mixed brand/product copy | Shared web labels use “Sectoral”; the source partner remains “Sectors”. |
| S6 cover quote differed from chart's final close | Current rebuilt HTML uses the same dated close in both places for all nine; price date is shown as 24 Sep 2026. The old-PDF status remains unverified. |
| AMMN “PV overhead” was accused of representing one undiscounted year | The valuation sums annualized 1H26 general expense across each LoM year and discounts each year. The basis note now says so. The separate data-completeness wording still needs a page-by-page PDF review. |
| SSIA projected non-controlling interest was called zero | Current forecast rolls forward the 30 Jun 2026 interim NCI balance and projected minority earnings. The baseline zero-NCI claim is stale. |
| Published approval remained valid after the result changed (P1) | The fingerprint now covers plan, release state, model label and per-share value; old approvals become pending. Draft candidate values are withheld from the report body as well as the cover. |
| Consensus exhibit exposed action ratings | The shared exhibit now compares the Sectoral model value with sourced consensus values without printing Buy/Hold/Sell recommendation counts. |
| `.env.example`, source credit, disclaimer and roster issues | Obsolete environment variables were removed; public copy calls the output information/analysis and a model scenario; the roster now uses the current registration deadline and repository name. Participant identity and onboarding remain unverified. |

The baseline claim that BBCA's terminal payout “goes back” to its FY2025 historical payout is not a confirmed defect: the terminal policy computes sustainable payout as `1 - g / terminal-year ROE`, capped at historical payout. It is now disclosed separately from the yearly payouts. Because BBCA's final explicit-year payout is reduced by the capital constraint while its terminal payout rises, an analyst should still review whether that steady-state transition is appropriate.

### Open report and process items

- **S8, S10 and S11:** Historical/peer multiple comparability, the common policy beta of 1.10, and differing FX snapshots remain analyst-input/data-provenance questions; no evidence in this execution justifies silently changing them.
- **S12:** All rebuilds now share a report cutoff. Each close and consensus snapshot still has its own source date and may be unavailable for some issuers.
- **S14:** Footer glyph defects cannot be cleared until fresh PDFs can be generated and checked with `pdftotext -layout` and rendered pages.
- **JPFA:** Forecast prose now reflects the model's margins. Continue reviewing the H2 margin assumptions and whether its cash/debt bridge rolls forward from the interim balance sheet.
- **BBCA/BBRI:** Review the constrained yearly payout path and BBCA's transition to terminal payout. BBRI's FY26 CAR is 21.0% against the model's 21.1% floor; its 2025A non-interest-income data may contain a reclassification artifact, and interim cash/equity fields are incomplete despite their use in the bank model.
- **AMMN:** Continue reconciling the different H2/LoM volume and EBITDA assumptions, parent versus consolidated net-profit labels, the capex basis, production/cash-cost cross-checks, and the consensus gap. The overhead present-value calculation was corrected, but the full report still needs analyst review.
- **GMFI:** The model uses 119,666,152,876 shares while KSEI reports 124,835,258,434 total shares (4.14% difference). This may reflect a definition/treasury-share difference; evidence reviewed does not establish the cause. Reconcile the denominator and the 0.0% working-capital-intensity scenario before relying on per-share value. Sources: [KSEI GMFI register](https://web.ksei.co.id/services/registered-securities/shares/lc/GMFI?setLocale=en-US), [GMF 1H26 financial statements](https://gmf-aeroasia.co.id/laporan/keuangan).
- **INET:** Reconcile the 30 Jun cash balance with the 15 Sep SGI payment and the use of unspent capital proceeds before treating all cash as available to equity holders. Reconfirm the post-raise share denominator used by the per-share bridge.
- **JPFA:** The prose now matches the model's H2 margin, but the value remains anchored to 31 Dec 2025 cash/debt. Review a roll-forward to the latest interim balance sheet or retain that valuation date with a clear rationale.
- **POWR:** Reconcile interim cash with the larger cash amount used in the EV bridge; short-term investments may be included but need an accurate label.
- **SIDO:** The model uses 29,719,584,139 shares while KSEI lists 30,000,000,000 total shares (0.94% difference). Treasury shares could explain this, but current issuer evidence was not reconciled. The report labels the modeled denominator and distinguishes it from total shares. Source: [KSEI SIDO register](https://web.ksei.co.id/services/registered-securities/shares/lc/SIDO).
- **SSIA:** The current harness warns that balancing debt is above 25% of equity in FY26F-FY28F, as forecast capex/dividends are not funded. The NCI roll-forward is corrected; the holding discount, land sales pace and valuation bridge remain analyst assumptions.
- **Hackathon submission:** The GitHub visibility query failed due to network access, so current visibility is unverified. The roster's onboarding marker is ⚪; because onboarding must precede code, verify portal evidence immediately. Public-repo retention through 15 Jan 2027, the teaser and judging video, problem statement, track/team names, and tagged public social post also require portal or human evidence. No external status was changed. Recheck the [official rules](https://hackathon.sectors.app/rules).
- **P4/P6:** Review the work email on commit `0cc9af0` before making history public. Keep the video narration aligned with the dated Sectors snapshots and any Yahoo market-price overrides.
- **PDF release:** The source PDFs have not been replaced. After a working PDF renderer is available, rebuild all nine, verify every `pdftotext -layout` output and representative rendered pages, inspect traces/review states separately, and only then treat the copy/layout findings as closed.

Final validation: `python3 -m compileall -q app`; `git diff --check`; 871 backend passes, 3 skips, two PDF-render failures, with `tests/test_record_demo.py` excluded because FastAPI is unavailable; 15 frontend tests passed; frontend production build passed; nine regenerated HTML reports passed the rendered harness with zero blockers and one SSIA warning. PDF replacement and visual QA remain outstanding.
