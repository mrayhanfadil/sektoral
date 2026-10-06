# Template harness: rule reconciliation

Every rule in `spec/Struktur-Template.md` mapped to the check that enforces it
(`app/harness/template.py` = doc checks on the report JSON,
`app/harness/render_check.py` = checks on the rendered HTML and PDF text), its
severity, and where the template and `spec/Instruksi-Report-v3.md` disagree.

Severity. **blocker** = the failure misleads a reader or breaks a tie-out; it
joins `run_all`'s blocker list as `T.<id>` and forces `draft_non_distributable`
(fail closed; one switch, `app.harness.template.ENABLED`, on unless
`SEKTORAL_TEMPLATE_HARNESS=0`, or `run_all(..., template_checks=False)`).
**warning** = presentation rule that does not change meaning; reported, never
blocks. A check that does not apply (profile, draft, exhibit absent for a reason
another check already names) reports `tidak_berlaku`.

Owner = who fixes a real finding: **present** (`report_extras`, `narrative`),
**layout** (`render`, `fmt`), **model** (`forecast_statements`, `valuation`),
**peers** (`data/peer_groups`, `peer_groups`).

## Decisions that settle template-vs-spec conflicts

| # | Topic | Template says | Spec says | Harness enforces |
|---|---|---|---|---|
| D1 | Horizon | KF/IS/BS/CF/ratio/charts: 2024A-2028F; FCFF block 1 "5 years" | Model 5 forecast years; display 2A+3F | Display tables and Slide-3 charts: exactly 2A+3F, consecutive. Valuation tables (FCFF, dividend, LoM): 5 consecutive forecast years from last actual + 1. Every forecast cell filled; `n.m.` only with the reason in the exhibit note; bare `NA`, `n.a.`, blank, `-`, null = blocker |
| D2 | Source line | "Source: Company, Team Estimates", no exception | `Source: Company, [Nama Rumah] Estimates`, detail to appendix | Rendered line under every exhibit is exactly `Source: Sectors (market and financial data), issuer disclosures; Sectoral analysis and estimates.`; detail lives in the end-of-report source appendix (warning if the appendix is missing) and in `catatan_sumber` (doc) |
| D3 | Language | English labels ("Revenue", "Net Profit", "Buy", "(Maintained)") | Bahasa Indonesia, English financial terms | Labels matched by concept with Indonesian and English aliases; never requires English. Rating words Buy/Hold/Sell; status Inisiasi/Dipertahankan/Naik/Turun (or English) |
| D4 | Peers | Sector/sub-sector, market-cap range | Comparable business model | IDX (BEI) listings only (blocker); Median + Average rows, issuer row marked/highlighted, criteria and as-of date (warning) |
| D5 | EPS consensus (Exhibit 1) | "Ga perlu" | forecast vs guidance/consensus when comparable | Not checked |
| D6 | Method choice | "dipilih manual oleh analis" | Method Gates 0-5 + chain, analyst override | Method taken from the release `method_key` (or the method-chain `Terpilih` row); the matching option's exhibits are mandatory. Methods outside options A/B/C (EV/EBITDA peer, PER FY, P/BV) need chain + TP calculation + sensitivity |
| D7 | Numbering | Exhibit 1 = EPS consensus, 2 = relative chart, 3 = Key Financials | Global sequential numbering | Global 1..N in reading order; no fixed numbers (Exhibit 1 is dropped per D5) |
| D8 | Bank variants | Bank IS/BS/ratio per BBTN; charts 1-3 generic | EV/EBITDA and net gearing not required for banks | `financial_ddm`: bank line sets; EBITDA chart and EV/EBITDA column optional |
| D9 | Mining | E&P needs separate treatment; RNAV option C | LoM/SOTP without perpetual terminal | `finite_life_mining`: option C exhibits; chart 4 = volume and unit cost (warning); FCFF perpetual rows not required |
| D10 | Decimals of Rp bn | no decimals for Rp bn, EPS one decimal | 0 or 1 decimal for Rp bn/US$ mn | Rp bn/US$ mn: 0 or 1 decimal accepted. Multiples and % one decimal (warning). EPS decimals not checked |
| D11 | Header/footer brand | Logo Sectors.app; footer left "sectors.app" | Styling is the renderer's | Logo image in the header and "sectors.app" in the footer are warnings; the lead decides the brand text |
| D12 | Currency | (GMFI example: USD reporter uses UST) | Model in reporting currency; no USD cash flows at a rupiah rate | KF, statements and Slide-3 charts in one currency (blocker); values are tied out only within one currency; USD reporter's discount rate UST-based, rupiah model without extra CRP (blocker) |
| D13 | Unfilled forecast | every cell 2024A-2028F | §4.5: "belum dimodelkan" with a reason | Columns always present. A cell reading `n.m.` or "belum dimodelkan" (out-years that failed validation) is compliant only with the reason in the exhibit note (`TF.nm_reason`); bare NA, n.a., "-", "tidak tersedia", blank = `TF.forecast_cells`. A chart forecast category without a value is compliant only when its caption/note says why |
| D14 | Chart 4 without forecasts | charts 2024A-2028F | driver chart only where the profile models it | Charts 1-3 (revenue, EBITDA, net profit): missing forecast year = blocker. Chart 4 that shows actuals only, says so in its title/narrative and gives the reason: warning `TF.chart_forecast_nm` (lead to confirm; otherwise it is a `TF.display_horizon` blocker) |
| D15 | Peer-derived values | peer table median/average | chain moves on insufficiency (min 3 valid peers) | A value or median derived from peers must agree with the method chain and rest on >= 3 valid multiples (P/E 0-50x, P/B 0-10x, EV/EBITDA 0-50x) |
| D16 | PDF header | header on every slide | - | PDF pages 2+ draw the header as an image until app/pdf.py adds a text layer, so `T1.header.pdf` is a warning |

## Check table

| Template rule | Check id | Sev. | Reads | Owner |
|---|---|---|---|---|
| **General** Exhibit label above every object, descriptive | `T1.exhibit_label` | warning | doc `exhibits[].judul` (not empty, not a generic word such as "Chart"/"Tabel") | present |
| | `T1.exhibit_label_rendered` | warning | HTML: every exhibit block carries an `Exhibit N.` caption | layout |
| Source line under every object | `T1.source_line` | blocker | HTML `p.src` / `.info-src` per exhibit block; PDF lines starting `Source:` | layout |
| n.m. only with its reason, printed where the cell is | `T1.nm_note_rendered` | blocker | HTML: every exhibit table with an `n.m.` cell has a `p.nm-note` (the n.m. part of its note) under the source line; `>500%` replaces n.m. for growth above 500% | layout |
| Detail provenance at the back (D2) | `T1.source_appendix` | warning | HTML: appendix heading ("Lampiran sumber"/"Source appendix") after the last exhibit, every exhibit number listed | layout |
| Sequential numbering, global counter | `T1.numbering` | blocker | doc: `n` = 1..N in reading order (price chart, Key Financials, then `bagian` order), every placed exhibit in `exhibits` | present |
| | `T1.numbering_rendered` | blocker | HTML `Exhibit N.` captions in order = 1..N (an appendix run is not counted) | layout |
| Title describes its period (e.g. "(2024A-2028F)") | `T1.title_period_range` | blocker | title range `(A-B)` vs first/last period column (or period row labels) | present |
| Header: "Equity Research – Company Update", "Day, DD Month YYYY", logo, divider | `T1.header` | warning | HTML report header + `@top-*` margin boxes; PDF each page; date = `meta.tanggal`, weekday correct, Indonesian or English names | layout |
| Footer: "sectors.app" left, disclosure + page number right | `T1.footer` | warning | HTML `@bottom-*` content; PDF each page | layout |
| **Forecast completeness (D1)** | `TF.forecast_cells` | blocker | every table with forecast columns and every Slide-3 chart: forecast cells numeric or `n.m.` | model / present |
| `n.m.` needs its reason | `TF.nm_reason` | blocker | exhibit with an `n.m.` cell: note (`catatan_sumber`/`catatan`) explains `n.m.` | present |
| Actual cells | `TF.actual_cells` | warning | actual cells of display tables: bare `NA`/blank/`-`/null | present |
| Annotation rows | (rule inside `TF.forecast_cells`) | - | a row of words without figures in a non-statement table (e.g. "Asumsi") is not a data row | - |
| Display horizon 2A+3F | `TF.display_horizon` | blocker | IS, BS, CF, ratio columns; Slide-3 chart columns (missing forecast year = blocker; extra history = see `TF.chart_history`) | present |
| | `TF.chart_history` | warning | Slide-3 charts show periods older than the 2 actual years | present |
| | `TF.chart_forecast_nm` | warning | chart 4 actual-only with a written reason (D14) | present |
| Valuation tables 5 forecast years | `TF.valuation_horizon` | blocker | FCFF block 1 / dividend block 1 / LoM annual exhibit: FY(last actual+1)F..+5 consecutive, as columns or row labels | model |
| Period label style `2024A`, `FY26F` | `TF.period_labels` | warning | display tables: actual labels end in `A`, forecast in `F` | present |
| **Slide 1** Rating block Buy/Hold/Sell + status | `T2.cover_rating_block` | blocker (published) | `meta.rating` in Buy/Hold/Sell; status wording checked in `T2.rating_status` | present |
| | `T2.rating_status` | warning | `meta.rating_status`: Inisiasi/Dipertahankan/Naik dari/Turun dari (or English); draft: "Dalam peninjauan" | present |
| Price box: Last Price, TP, Upside = TP/Price-1 with sign | `T2.price_box` | blocker (published) | `meta.harga`, `meta.tp`, `meta.upside_persen` recomputed (0.05pp) | present |
| | `T2.price_box_rendered` | warning | HTML: price, TP, upside rows; upside has `+`/`-` and one decimal | layout |
| Secondary stats (shares, mcap Rp/US$, ADTV Rp/US$ with window, free float, major holders) | `T2.stats_block` | warning | `cover.data_pasar`, `holders` | present |
| Exhibit "[TICKER] relative to JCI" 1-2y, dual axis, month ticks | `T2.relative_chart` | warning | doc: `price_chart` exhibit exists and is first | present |
| | `T2.relative_chart_rendered` | warning | HTML: caption names IHSG/JCI, window 12-24 months, `Mmm-YY` ticks | layout |
| Analyst block "Equity Analyst" | `T2.analyst_block` | warning | HTML cover text | layout |
| Company name + "(TICKER IJ)" | `T2.company_header` | warning | HTML `h1` / cover text | layout |
| Thesis subtitle, not generic | `T2.thesis_subtitle` | warning | `cover.headline`: <= 10 words, <= 1 number, not the company name | present |
| 3 bullets, one sentence each; bullet 3 rating + TP | `T2.cover_bullets` | warning | `cover.bullets` | present |
| 3 paragraphs with bold subheadings | `T2.cover_paragraphs` | warning | `cover.paragraf[].judul/isi` | present |
| Valuation paragraph: method + key parameter %, CAGR FY26-28F, multiple at TP vs history/peers | `T2.valuation_paragraph` | warning (published) | valuation paragraph text | present |
| TP and method identical on cover and valuation page (spec §4.4) | `T2.cover_tp_method` | blocker (published) | every "target/TP Rp X" on cover = `meta.tp`; `doc.method` and TP sentences name the selected family; method-chain `Terpilih` row value and primary valuation per-share value = TP (one IDX tick) | present / model |
| Key Financials rows (profile set) | `T2.key_financials_rows` | blocker | KF row labels (non-bank: revenue, EBITDA, EBITDA growth, net profit, EPS, EPS growth, PER, PBV, EV/EBITDA; bank: revenue, net profit, EPS, EPS growth, BVPS, ROE, DPS, PER, PBV) | present |
| | `T2.key_financials_order` | warning | same rows in template order | present |
| Key Financials columns 2A+3F | `T2.key_financials_cols` | blocker | KF `cols` | present |
| Multiples and % one decimal | `TN.one_decimal` | warning | KF `(x)`/`(%)` rows, ratio table, peer multiples | present |
| Negatives in brackets | `TN.negatives_brackets` | warning | HTML numeric table cells | layout |
| **Slide 3** Revenue, EBITDA, net profit combo charts (bar + line, actual vs forecast) | `T3.combo_charts` | blocker | `combo_panel`/`combo_chart` exhibits (bank: EBITDA chart optional) | present |
| | `T3.chart_style` | warning | each chart has bars + line; `is_forecast` matches `F` columns; narrative present | present |
| Chart 4 by sector | `T3.chart4_by_profile` | warning | fourth chart label: DER/ROE; bank NIM/CoC or NPL; mining volume/unit cost | present |
| Slide 3 ties to Key Financials | `T3.tieout_key_financials` | blocker | chart bars vs KF values, chart lines vs KF growth/margin, same period (0.1% + display rounding) | present |
| One currency across KF, statements, charts (D12) | `T3.currency_consistency` | blocker | units in KF row labels, statement `cols[0]`, chart labels | present / model |
| **Slide 4** Active option's mandatory exhibits | `T4.valuation_option_exhibits` | blocker (published) | option A: FCFF + WACC + sensitivity; B: dividend + CoE + sensitivity; C: asset/RNAV-SOTP bridge + sensitivity; other chain methods: TP table + sensitivity; all: method chain | present |
| FCFF three blocks | `T4.fcff_blocks` | blocker | explicit (FCFF, discount factor, PV FCFF), terminal (TV, PV TV), bridge (EV, net debt, equity, fair value/share) | present |
| | `T4.fcff_rows` | warning | all template rows (revenue, EBIT, tax on EBIT, NOPAT, D&A, capex, NWC, FCFF growth, terminal FCFF, g, terminal DF, sum PV, minority) | present |
| WACC components, WACC last | `T4.wacc_components` | blocker | rows Rf, beta, ERP, CoE, WACC | present |
| | `T4.wacc_rows` | warning | CoD pre/after tax, tax rate, weights; WACC is the bottom row | present |
| Sensitivity grid, base highlighted | `T4.sensitivity_grid_base_highlight` | blocker | base row `(basis)` x base column = fair value/TP (one tick) | model |
| | `T4.sensitivity_grid_shape` | warning | 5 discount-rate steps, >= 3 columns | model |
| | `T4.sensitivity_highlight_rendered` | warning | HTML: base cell/row styled differently | layout |
| DDM blocks (CoE, not WACC) | `T4.ddm_blocks` | blocker | block 1 (DPS, discount factor, PV DPS), block 2 (terminal DPS/TV, PV TV, fair value/share); WACC in a DDM exhibit = fail | present |
| | `T4.ddm_rows` | warning | net profit, payout, DPS growth, g | present |
| CoE components | `T4.coe_components` | blocker | Rf, beta, ERP, CoE rows | present |
| RNAV bridge | `T4.rnav_bridge` | blocker | asset NAV rows + bridge (cash, debt, equity/RNAV, per share) | present |
| | `T4.rnav_rows` | warning | ownership %, sum of NAV, corporate overhead, discount to RNAV | present |
| Discount rate per asset | `T4.discount_rate_per_asset` | warning | option C: exhibit or per-asset rate column | present |
| Rf/beta/ERP sources | `T4.rf_beta_erp_sources` | warning | CoE/WACC rows + note: INDOGB/UST, Bloomberg/policy, Damodaran/policy | present |
| Rf currency (spec §2, §4.2) | `T4.discount_rate_currency` | blocker | USD reporter: Rf UST; rupiah: INDOGB without extra CRP | model |
| Terminal g cap | `T4.terminal_growth_cap` | blocker | terminal g <= Rf | model |
| FCF memo vs FCFF ballpark | `T4.fcf_vs_fcff` | warning | CF memo FCF vs FCFF same year within 2x | model |
| **Slide 5** Peer table: Median, Average, issuer row, criteria, as-of | `T5.peer_table_median_average_highlight_asof_criteria` | warning | peer comparison exhibit rows, cols, note | present / peers |
| | `T5.peer_highlight_rendered` | warning | HTML: issuer row and Median/Average rows styled | layout |
| IDX only (D4) | `T5.peers_idx_only` | blocker | peer selection exhibit (exchange column of used peers) and peer comparison rows (4-letter IDX codes, not listed elsewhere with a foreign exchange) | peers |
| Peer values agree with the chain (D15) | `T5.peer_crosscheck_consistency` | blocker | medians/averages in the peer table and every peer-derived per-share row vs method-chain rows and valid multiples | present |
| P/E and P/BV bands with mean, median, current marker | `T5.hist_bands_mean_median_marker` | warning | `band_chart` data (P/E, P/BV, mean/median/current/percentile, window >= 11 months, mean within band). Where P/E or P/BV is not meaningful (base not positive for part of the year or today, or above 100x) an EV/EBITDA or EV/Sales band stands in, only when its note states '<X> menggantikan band <P/E/P/BV> karena ...' | present |
| | `T5.band_lines_rendered` | warning | HTML band SVG: mean and median lines in two dash styles besides the grid, plus a marker | layout |
| Implied price mean and median, >= 2 multiples | `T5.implied_price_mean_median_two_multiples` | warning | band table rows: >= 2 multiples with implied prices at mean and median; a substitute multiple's row counts only when the table note states the substitution | present |
| Disclaimer: cross-check, not the TP, constant drivers | `T5.disclaimer` | warning | visible text of the band page (paragraphs, titles, narasi) | present |
| Peer narrative vs median/average | `T5.peer_narrative` | warning | peer page paragraphs | present |
| **Slide 6** Income statement lines | `T6.income_statement_lines` | blocker | IS row labels (non-bank / bank set) | present / model |
| | `T6.income_statement_order` | warning | template order | present |
| Balance sheet lines, TA = TL&E | `T6.balance_sheet_lines_and_balance` | blocker | BS row labels; total assets vs total liabilities and equity per column (0.1%) | model |
| | `T6.balance_sheet_subtotals` | warning | subtotal arithmetic | model |
| **Slide 7** Cash flow sections and reconciliation | `T7.cash_flow_sections_and_tieout` | blocker | section rows, lines; forecast: begin + change = end, CFO+CFI+CFF = change (0.1%) | model |
| | `T7.cash_flow_actual_reconciliation` | warning | same arithmetic on actual columns (1%); a source gap (FX, cash definitions) counts only through an explicit line labelled `(data sumber)`: 'Efek kurs dan selisih definisi kas' between begin and end cash, 'Selisih komponen arus kas' between CFO+CFI+CFF and the net change. Such a line on a forecast column must read 0 or n.m., else it is a plug and fails `T7.cash_flow_sections_and_tieout` | present |
| Key ratio sections and format | `T7.key_ratio_sections_format` | blocker | ratio lines (non-bank growth/profitability/leverage; bank set) | present / model |
| | `T7.key_ratio_format` | warning | section header rows, one decimal | present |
| Tie-outs: IS = KF = CF start; CF end cash = BS cash; begin(t) = end(t-1) | `T7.tieouts` | blocker | same columns, 0.1% + display rounding; bank BS without cash line: n/a | model |
| **Rendered output** Report renders | `R.render_error` | blocker | `app.render.render(doc)` raises | layout |
| PDF text (standalone `--render`) | `T1.source_line.pdf`, `T1.numbering_rendered.pdf` | blocker | pypdf text of `<folder>/<T>.pdf` | layout |
| | `T1.header.pdf`, `T1.footer.pdf` | warning | every page: header + date, "sectors.app", disclosure, page number (D16) | layout |

## Not machine-checked (left to the LLM judge / reviewer)

Narrative quality: paragraph content of slide 2 (industry, catalysts, sentiment),
"claim, number, implication", chart narratives explaining drivers, sensitivity
narrative naming the most sensitive parameter, discount-to-RNAV justification,
the own-history methodology text, visual styling (navy header shading, colours,
2x2 grid, section divider between peer and own-history parts). The Gordon vs
exit gap disclosure is S3/§4.4 (`S3.8_divergence`).
