# Institutional research grade baseline — 2026-09-26

## Run definition

- Report Date: `2026-09-26`; local Sectors and issuer data; deterministic `app.build`; no Research Agent/Tavily refresh; output folder `out/institutional-grade-baseline-2026-09-26/`.
- The cached market close is dated `2026-09-24` per the earlier read-only intake probe.
- The run produced HTML, report documents in the local SQLite store, and a finalized publication manifest for each ticker. It did not call paid agent/news services or create standalone Audit Trace HTML/PDF; this is a release-gate baseline, not a reviewable or distributable bundle.
- Machine-readable manifests are copied to `out/institutional-grade-baseline-2026-09-26/manifests/`; this is local ignored output, not a durable tracked archive.

## Results

| Ticker | Model Profile | Release Status | Method | Release blockers | Evidence rows / critical | Policy snapshot | Missing final artifacts |
|---|---|---|---|---:|---:|---|---|
| BBCA | financial_ddm | draft_non_distributable | DDM (dividen, Rp) | 5 | 11 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| BBRI | financial_ddm | draft_non_distributable | DDM (dividen, Rp) | 6 | 11 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| AMMN | finite_life_mining | draft_non_distributable | SOTP/LoM (belum lengkap) | 4 | 9 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| SSIA | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 6 | 2 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| INET | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 7 | 1 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| POWR | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 8 | 1 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| JPFA | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 8 | 2 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| GMFI | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 7 | 1 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |
| SIDO | going_concern_fcff | draft_non_distributable | DCF FCFF (belum lengkap) | 8 | 1 / 0 | 1.0.0 / documented_baseline_not_enforced / 045bc0783f58 | pdf, trace_html |

## Readout

- All nine source-pack tickers remain `draft_non_distributable`. No profile has a complete Production-Ready path; the financial profile still lacks its calculated earnings/capital/dividend bridge, going-concern reports use screening drivers, and AMMN lacks a reconciled physical-to-financial LoM/SOTP path.
- Evidence Register validation has zero critical violations across the nine inputs. Evidence validity does not prove that the forecast or selected valuation is complete.
- The versioned release policy is recorded in every manifest (`documented_baseline_not_enforced`). Numeric profile materiality cutoffs, a centralized tolerance rule, issuer reporting calendars, and staleness/withdrawal thresholds remain open policy work.
- `meta.model_profile` now matches the manifest profile for every report.
- The output folder lacks `pdf` and `trace_html` for every ticker, so no reviewer approval is possible from this baseline.

## Full named blockers

### BBCA (financial_ddm)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: financial driver-to-earnings/capital bridge is not calculated; historical revenue/margins and assumed payout remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- method chain: no sufficient valuation method (ddm: sourced operating and cash-flow forecast is incomplete; pbv_roe: sourced operating and cash-flow forecast is incomplete; pbv_roe_fy: forecast agent scenario has not passed validation; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation)

Harness:
- S2.S2.9: driver laba/modal/payout belum rekonsiliasi; screen bukan forecast produksi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: financial driver-to-earnings/capital bridge is not calculated; historical revenue/margins and assumed payout remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.method chain: no sufficient valuation method (ddm: sourced operating and cash-flow forecast is incomplete; pbv_roe: sourced operating and cash-flow forecast is incomplete; pbv_roe_fy: forecast agent scenario has not passed validation; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation)

### BBRI (financial_ddm)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: financial driver-to-earnings/capital bridge is not calculated; historical revenue/margins and assumed payout remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: equity
- method chain: no sufficient valuation method (ddm: sourced operating and cash-flow forecast is incomplete; pbv_roe: sourced operating and cash-flow forecast is incomplete; pbv_roe_fy: forecast agent scenario has not passed validation; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation)

Harness:
- S2.S2.9: driver laba/modal/payout belum rekonsiliasi; screen bukan forecast produksi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: financial driver-to-earnings/capital bridge is not calculated; historical revenue/margins and assumed payout remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: equity
- release.method chain: no sufficient valuation method (ddm: sourced operating and cash-flow forecast is incomplete; pbv_roe: sourced operating and cash-flow forecast is incomplete; pbv_roe_fy: forecast agent scenario has not passed validation; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation)

### AMMN (finite_life_mining)

Release Gate:
- operating bridge missing: forecast.operating_bridge
- mining forecast is not a verified physical-driver production forecast
- forecast gate failed: S2.9 physical-to-financial operating bridge is not reconciled
- method chain: no sufficient valuation method (sotp_lom: input LoM belum lengkap: discount_ust_10y, discount_fx, discount, cu_price_stale; rnav_lom: operating bridge missing: forecast.operating_bridge; ev_ebitda_fy: forecast agent scenario has not passed validation)

Harness:
- S2.S2.9: forecast fisik-ke-keuangan belum dihitung; CAGR hanya screening
- T.TF.display_horizon: grafik Exhibit 12: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 13: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 14: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 15: tanpa tahun [2026, 2027, 2028]
- T.TF.valuation_horizon: tanpa exhibit LoM tahunan FY(aktual+1)F..+5 (jadwal per fase tidak cukup)
- T.T3.currency_consistency: USD: Key Financials; IDR: laba rugi, neraca, arus kas, grafik Exhibit 12, grafik Exhibit 13, grafik Exhibit 14
- T.T4.rnav_bridge: tanpa: NAV per aset, RNAV/ekuitas, per saham
- release.operating bridge missing: forecast.operating_bridge
- release.mining forecast is not a verified physical-driver production forecast
- release.forecast gate failed: S2.9 physical-to-financial operating bridge is not reconciled
- release.method chain: no sufficient valuation method (sotp_lom: input LoM belum lengkap: discount_ust_10y, discount_fx, discount, cu_price_stale; rnav_lom: operating bridge missing: forecast.operating_bridge; ev_ebitda_fy: forecast agent scenario has not passed validation)

### SSIA (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: capex
- method chain: no sufficient valuation method (fcff_dcf: skala: ekuitas 18% dari market cap (ambang 20-300%); relative_pe: skala: ekuitas 9% dari market cap (ambang 20-300%); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 11: tanpa tahun [2026, 2027, 2028]
- T.T4.fcff_blocks: blok tidak lengkap: eksplisit (fcff, discount_factor, pv_fcff); terminal (terminal_value, pv_tv); bridge (ev, equity_value, fv); bridge (utang bersih)
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: capex
- release.method chain: no sufficient valuation method (fcff_dcf: skala: ekuitas 18% dari market cap (ambang 20-300%); relative_pe: skala: ekuitas 9% dari market cap (ambang 20-300%); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

### INET (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: ebitda
- method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: skala: ekuitas 5% dari market cap (ambang 20-300%); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)
- cross-check relatif/SOTP wajib belum tersedia padahal peer ada

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: ebitda
- release.method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: skala: ekuitas 5% dari market cap (ambang 20-300%); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

### POWR (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: ebitda
- driver forecast missing required series: capex
- method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: peer PER valid 2 < 3 (band 0-50x); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)
- cross-check relatif/SOTP wajib belum tersedia padahal peer ada

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]
- T.T3.currency_consistency: USD: Key Financials; IDR: laba rugi, neraca, arus kas, grafik Exhibit 7, grafik Exhibit 8, grafik Exhibit 9
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: ebitda
- release.driver forecast missing required series: capex
- release.method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: peer PER valid 2 < 3 (band 0-50x); pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

### JPFA (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: ebitda
- driver forecast missing required series: capex
- method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)
- cross-check relatif/SOTP wajib belum tersedia padahal peer ada

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: ebitda
- release.driver forecast missing required series: capex
- release.method chain: no sufficient valuation method (fcff_dcf: sourced operating and cash-flow forecast is incomplete; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

### GMFI (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: capex
- method chain: no sufficient valuation method (fcff_dcf: divergensi Gordon vs exit 51% > 30%; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)
- cross-check relatif/SOTP wajib belum tersedia padahal peer ada

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]
- T.T3.currency_consistency: USD: Key Financials; IDR: laba rugi, neraca, arus kas, grafik Exhibit 8, grafik Exhibit 9, grafik Exhibit 10
- T.T4.fcff_blocks: blok tidak lengkap: eksplisit (fcff, discount_factor, pv_fcff); terminal (terminal_value, pv_tv); bridge (ev, equity_value, fv); bridge (utang bersih)
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: capex
- release.method chain: no sufficient valuation method (fcff_dcf: divergensi Gordon vs exit 51% > 30%; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

### SIDO (going_concern_fcff)

Release Gate:
- sourced operating and cash-flow forecast is incomplete
- forecast is not verified as production-ready
- forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- forecast gate failed: S2.9 driver forecast is not reconciled
- driver forecast missing required series: ebitda
- driver forecast missing required series: capex
- method chain: no sufficient valuation method (fcff_dcf: divergensi Gordon vs exit 45% > 30%; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)
- cross-check relatif/SOTP wajib belum tersedia padahal peer ada

Harness:
- S2.S2.9: CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi
- T.TF.display_horizon: grafik Exhibit 7: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 8: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 9: tanpa tahun [2026, 2027, 2028]; grafik Exhibit 10: tanpa tahun [2026, 2027, 2028]
- release.sourced operating and cash-flow forecast is incomplete
- release.forecast is not verified as production-ready
- release.forecast: operating driver-to-FCFF bridge is not calculated; historical CAGR, capex=D&A, flat debt and balancing cash remain screening inputs
- release.forecast gate failed: S2.9 driver forecast is not reconciled
- release.driver forecast missing required series: ebitda
- release.driver forecast missing required series: capex
- release.method chain: no sufficient valuation method (fcff_dcf: divergensi Gordon vs exit 45% > 30%; relative_pe: sourced operating and cash-flow forecast is incomplete; pe_fy_scenario: forecast agent scenario has not passed validation; pbv_book: forecast agent scenario has not passed validation)

