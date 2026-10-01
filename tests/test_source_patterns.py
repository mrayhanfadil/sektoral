"""English for model text quoted in prose (app.source_patterns).

Each example is a string its producer emits, built by calling the producer
where that is practical; the English must state the same figures, read as
English, and come from exactly one pattern.
"""
import pytest

from app import (bank_model, fmt, forecast_statements, investability, method_chain, prose_lang,
                 scenario_value, share_basis, source_patterns)


def english(text):
    with prose_lang.building("en"):
        return prose_lang.source(text)


def matching(text):
    return [p.pattern for p, _ in source_patterns.PATTERNS if p.fullmatch(text)]


def _bridge_examples():
    base = {"as_of": "2026-09-26", "shares": 1e9}
    annual = {"year": 2025, "total_debt": 5.0, "cash": 3.0, "shares": 1e9}
    fiscal = scenario_value.bridge({**base, "annuals": [annual],
                                    "dividend_events": [{"date": "2026-05-02", "dps": 150.0}]})
    interim = scenario_value.bridge({**base, "annuals": [annual], "official_evidence": {
        "balance_sheet": {"period_end": "2026-06-30", "cash": 4.0, "total_debt": 6.0,
                          "shares_outstanding": 1.2e9, "non_controlling_interest": 1.0}}})
    quarter = scenario_value.bridge({**base, "quarterly_actuals": [
        {"date": "2026-06-30", "total_debt": 5.0, "cash_only": 2.0, "total_equity": 10.0,
         "stockholders_equity": 9.0}]})
    usd = {"as_of": "2026-09-26", "fx_spot": {"rate": 16500.0},
           "dividend_events": [{"date": "2026-08-02", "dps": 150.0}],
           "official_evidence": {"reporting_currency": "USD", "balance_sheet": {
               "period_end": "2026-06-30", "cash": 4.0, "short_term_investments": 1.0,
               "total_debt": 6.0, "shares_outstanding": 1e9}}}
    native = scenario_value.bridge_native(usd)
    no_sti = dict(usd, official_evidence={**usd["official_evidence"], "balance_sheet": {
        **usd["official_evidence"]["balance_sheet"], "short_term_investments": None}})
    converted = scenario_value.bridge_native({
        **base, "annuals": [annual], "fx_spot": {"rate": 16500.0},
        "dividend_events": [{"date": "2026-05-02", "dps": 150.0}],
        "official_evidence": {"reporting_currency": "USD"}})
    ledger = share_basis.report_date_shares({"as_of": "2026-09-26", "share_basis": {
        "status": "assessed", "shares_on_report_date": 1e9, "basis": {"date": "2026-06-30"}}})
    return [
        (fiscal["cash_basis"], "cash and short-term investments, Sectors FY2025"),
        (fiscal["debt_basis"], "Sectors FY2025"),
        (fiscal["anchor_reason"],
         "fiscal year-end, so that seasonal working capital does not distort net debt"),
        (fiscal["distributions_basis"],
         "cash dividends of Rp150,00/share, ex-date 2026-05-02 (Sectors data), after the "
         "balance-sheet date of 2025-12-31"),
        (fiscal["shares_basis"], "Sectors data"),
        (interim["cash_basis"], "official interim balance sheet at 2026-06-30"),
        (interim["anchor_reason"],
         "latest interim balance sheet; the share count has changed materially since the fiscal "
         "year-end"),
        (interim["nci_basis"], "book value, official interim balance sheet at 2026-06-30"),
        (quarter["cash_basis"], "cash and short-term investments, Sectors quarter to 2026-06-30"),
        (quarter["debt_basis"], "Sectors quarter to 2026-06-30"),
        (quarter["anchor_reason"],
         "latest quarterly balance sheet; the share count has changed materially since the "
         "fiscal year-end"),
        (quarter["nci_basis"], "book value, Sectors 2026-06-30"),
        (native["cash_basis"],
         "cash and short-term investments, official interim balance sheet at 2026-06-30"),
        (scenario_value.bridge_native(no_sti)["cash_basis"],
         "cash, official interim balance sheet at 2026-06-30"),
        (native["debt_basis"], "interest-bearing debt, official interim balance sheet at 2026-06-30"),
        (native["anchor_reason"],
         "latest official balance sheet in US$, the model currency; the Sectors year-end balance "
         "sheet is only available in rupiah"),
        (native["distributions_basis"],
         "cash dividends of Rp150,00/share, ex-date 2026-08-02 (Sectors data), after the "
         "balance-sheet date of 2026-06-30; converted to US$ at the spot rate of Rp16.500/US$"),
        (converted["cash_basis"],
         "cash and short-term investments, Sectors FY2025; rupiah converted to US$ at the spot "
         "rate of Rp16.500/US$"),
        (ledger[1], "official share register at 2026-06-30, adjusted for corporate actions to "
                    "2026-09-26"),
        ("porsi induk 1H26 resmi", "official 1H26 parent share"),
        ("porsi induk FY2025 resmi, laporan tahunan resmi",
         "official FY2025 parent share, official annual report"),
        ("laporan tahunan resmi", "official annual report"),
        ("laba konsolidasi (porsi induk tidak dilaporkan terpisah)",
         "consolidated profit (parent share not reported separately)"),
        ("laba konsolidasi; porsi induk tidak dilaporkan terpisah",
         "consolidated profit; parent share not reported separately"),
        ("tidak dilaporkan terpisah; ekuitas induk = total ekuitas",
         "not reported separately; parent equity = total equity"),
    ]


def _driver_examples():
    official = lambda metrics: {"latest_official_actual": {"period": "1H26", "metrics": metrics}}
    annuals = lambda source: {"annuals": [
        {"year": y, "da": 5.0, "revenue": 100.0, "ebitda": 20.0, "da_source": source}
        for y in (2024, 2025)]}
    taxed = {"annuals": [{"year": y, "ebt": 100.0, "tax": 22.0} for y in (2023, 2024, 2025)]}
    nwc = lambda liabilities: {"annuals": [{"year": 2025, "current_assets": 50.0, "cash": 10.0,
                                            "current_liabilities": liabilities,
                                            "revenue": 100.0}]}
    da = scenario_value.da_intensity
    return [
        (da(official({"revenue": 100.0, "depreciation": 10.0}))[1], "official 1H26 depreciation"),
        (da(official({"revenue": 100.0, "ebitda": 30.0, "operating_profit": 20.0}))[1],
         "official 1H26 EBITDA less operating profit"),
        (da(annuals("official"))[1],
         "depreciation/revenue FY2024-FY2025, audited financial statements"),
        (da({"annuals": annuals("official")["annuals"][1:]})[1],
         "depreciation/revenue FY2025, audited financial statements"),
        (da(annuals(None))[1], "median D&A/revenue FY2024-FY2025, Sectors data"),
        (da({})[1], "D&A not available or implausible in Sectors data and official releases"),
        ("model operasional (penyusutan atas aset tetap neto awal)",
         "per the Operating Model (depreciation on opening net fixed assets)"),
        ("model operasional", "per the Operating Model"),
        (scenario_value.tax_rate(taxed)[1], "median effective rate FY2023-FY2025, Sectors data"),
        (scenario_value.tax_rate({})[1],
         "22% corporate income tax rate (historical effective rate not available)"),
        (f"PPh {fmt.pct(0.22)} dan PNBP {fmt.pct(0.1)} efektif 1H26 resmi, digabung",
         f"official 1H26 effective income tax {fmt.pct(0.22)} and PNBP {fmt.pct(0.1)}, combined"),
        (scenario_value.nwc_intensity({})[1],
         "working capital not available in Sectors data; ΔNWC taken as zero"),
        (scenario_value.nwc_intensity(nwc(44.0))[1],
         "FY2025 non-cash working capital negative (-4% of revenue); not counted as a source of "
         "cash"),
        (scenario_value.nwc_intensity(nwc(21.8))[1],
         "FY2025 non-cash working capital, Sectors data (18,2% of revenue)"),
        ("model operasional (hari piutang, persediaan, utang usaha)",
         "per the Operating Model (receivable, inventory and payable days)"),
        ("parameter kebijakan analis", "analyst policy parameter"),
        ("beban keuangan 1H26 resmi disetahunkan atas utang berbunga neraca resmi 2026-06-30",
         "official 1H26 finance costs annualised over interest-bearing debt on the official "
         "2026-06-30 balance sheet"),
        ("bunga efektif emiten (beban keuangan 1H26 resmi disetahunkan atas utang berbunga "
         "neraca resmi 2026-06-30)",
         "the issuer's effective interest rate (official 1H26 finance costs annualised over "
         "interest-bearing debt on the official 2026-06-30 balance sheet)"),
        ("UST 10Y + CRP, tingkat pasar pinjaman US$ berisiko Indonesia (parameter kebijakan "
         "analis)",
         "UST 10Y + CRP, the market rate for Indonesian-risk US$ borrowing (analyst policy "
         "parameter)"),
        ("UST 10Y + CRP, tingkat pasar pinjaman US$ berisiko Indonesia (parameter kebijakan "
         "analis); bunga efektif emiten 5,1% (beban keuangan 1H26 resmi disetahunkan atas utang "
         "berbunga neraca resmi 2026-06-30) di bawah tingkat pasar, tidak dipakai",
         "UST 10Y + CRP, the market rate for Indonesian-risk US$ borrowing (analyst policy "
         "parameter); the issuer's effective rate of 5,1% (official 1H26 finance costs annualised "
         "over interest-bearing debt on the official 2026-06-30 balance sheet) is below the "
         "market rate and is not used"),
    ]


def _payout_examples():
    model = lambda historical, **extra: {"rows": [{"roe": 0.18, "label": "FY30F"}],
                                         "constraints": {"historical_payout": historical, **extra}}
    return [
        ("asumsi analis 25% (tanpa payout historis di data Sectors)",
         "analyst assumption of 25% (no historical payout in Sectors data)"),
        ("payout ratio historis di data Sectors", "historical payout ratio in Sectors data"),
        (f"DPS 12 bulan terakhir Rp{fmt._id(346.0, 1)} atas EPS FY2025 Rp{fmt._id(376.0, 1)} "
         "(data Sectors)",
         "last 12 months' DPS of Rp346,0 over FY2025 EPS of Rp376,0 (Sectors data)"),
        ("DPS historis 2020-2026 di data Sectors", "Historical DPS 2020-2026 in Sectors data"),
        ("tanpa DPS historis di data Sectors", "No historical DPS in Sectors data"),
        ("sumber tidak tercatat", "unrecorded sources"),
        (bank_model.terminal_payout(model(0.6), 0.05)[1],
         "historical payout (below the sustainable payout of 1 - g / ROE)"),
        (bank_model.terminal_payout(model(0.6, terminal_payout_cap=0.6), 0.05)[1],
         "sourced policy payout (below the sustainable payout of 1 - g / ROE)"),
        (bank_model.terminal_payout(model(0.9), 0.05)[1],
         "sustainable payout 1 - g / ROE of FY30F (5,0% / 18,0%), below the historical payout "
         "of 90,0%"),
    ]


def _candidate_examples():
    first = lambda c: c["reasons"][0]
    peers = [{"ev_ebitda": 8.0, "ev_source_kind": "sectors"}]
    return [
        (method_chain.scale_reasons(10.0, 1.0, 1.0)[0],
         "scale: equity at 1000% of market cap (threshold 20-300%)"),
        (first(method_chain.candidate("ddm")), "value per share undefined or <= 0"),
        (first(method_chain.candidate("ddm", per_share=10.0, per_share_down=12.0)),
         "sensitivity downside not below the base"),
        (method_chain.relative_pe([{"pe": 10.0}] * 3, -1.0, 1.0, 1.0)["reasons"][0],
         "forward EPS <= 0; PER not meaningful"),
        (first(method_chain._peer_multiple_candidate("ps_peer", [1.0], 1.0, None, 1.0, 1.0)),
         "peer ps_peer not yet in the Sectors cache (1 < 3); not yet modelled"),
        (first(method_chain._peer_multiple_candidate("ps_peer", [1.0] * 3, -1.0, None, 1.0, 1.0)),
         "forecast denominator <= 0; multiple not meaningful"),
        (first(method_chain.ev_ebitda_peer(peers * 3, -1.0, 1.0, 1.0)),
         "forward EBITDA <= 0; EV/EBITDA not meaningful"),
        (first(method_chain.ev_sales_peer([{"ev_sales": 1.0}] * 3, -1.0, 1.0, 1.0)),
         "forward revenue <= 0; EV/Sales not meaningful"),
        (first(method_chain.pbv_relative([{"pb": 1.0}] * 3, -1.0, 1.0, 1.0)),
         "BVPS <= 0; P/BV not meaningful"),
        (first(method_chain.ps_peer([], 1.0, 1.0, 1.0)), "valid peer P/S 0 < 3; not yet modelled"),
        (first(method_chain.ps_peer([{"ps": 1.0}] * 3, -1.0, 1.0, 1.0)),
         "forward revenue or share count not yet available"),
        (method_chain.holding_sotp([{"ticker": "SSIA"}], -1.0, 1.0)["reasons"][0],
         "parent equity not yet available"),
        (method_chain.holding_sotp([{"ticker": "SSIA"}], -1.0, 1.0)["reasons"][1],
         "market/book value of SSIA not yet available"),
        ("metode belum dihitung", "method not yet calculated"),
        (scenario_value.ddm({}, {}, 0.1, 0.05)[1][0],
         "five-year earnings scenario (FY + four out-years) not yet validated"),
        ("payout historis tidak tersedia di data Sectors", "no historical payout in Sectors data"),
        ("jumlah saham atau tanggal neraca resmi tidak tersedia",
         "share count or official balance-sheet date not available"),
        ("laba pemilik induk skenario tidak lengkap", "scenario parent profit incomplete"),
        ("cost of equity tidak melebihi pertumbuhan jangka panjang",
         "cost of equity does not exceed long-term growth"),
        (scenario_value.discount_rates({"official_evidence": {"reporting_currency": "USD"}},
                                       0.07, 0.05)[1][0],
         "no dated UST 10Y yield on the Report Date; US$ cash flows are not discounted at a "
         "rupiah rate"),
        ("skenario belum memuat margin EBITDA dan capex untuk FY29F, FY30F",
         "the scenario does not yet carry EBITDA margin and capex for FY29F, FY30F"),
        ("jumlah saham, kurs atau tanggal neraca tidak tersedia",
         "share count, exchange rate or balance-sheet date not available"),
        ("kas atau utang untuk jembatan EV ke ekuitas tidak tersedia",
         "cash or debt for the EV-to-equity bridge not available"),
        (scenario_value.ev_ebitda_peer({}, {}, [])[1][0],
         "FY earnings scenario (official 1H actuals + H2 assumptions) not yet validated"),
        ("margin EBITDA FY skenario belum tersedia dari agen",
         "scenario FY EBITDA margin not yet available from the agent"),
        ("EBITDA FY skenario tidak positif; EV/EBITDA tidak bermakna",
         "scenario FY EBITDA not positive; EV/EBITDA not meaningful"),
        ("jumlah saham resmi, kurs atau tanggal neraca tidak tersedia",
         "official share count, exchange rate or balance-sheet date not available"),
        ("jembatan kas dan utang dari satu neraca belum tersedia",
         "cash and debt bridge from a single balance sheet not yet available"),
        ("overlay cadangan/produksi/harga tidak tersedia",
         "reserve/production/price overlay not available"),
        ("umur cadangan Katoda tembaga tidak terhitung",
         "reserve life of Copper cathode not calculated"),
        ("NAV Katoda tembaga tidak terhitung", "NAV of Copper cathode not calculated"),
        ("divergensi Gordon vs exit 42% > 30%", "Gordon vs exit divergence 42% > 30%"),
        ("grid sensitivitas DDM gagal", "DDM sensitivity grid failed"),
        ("hasil DDM/Inverse CoE tidak tersedia", "DDM/Inverse CoE result not available"),
        ("ROE forward tidak terhitung (ekuitas forecast kosong)",
         "forward ROE not calculated (forecast equity empty)"),
        ("BVPS <= 0 atau tidak tersedia", "BVPS <= 0 or not available"),
        ("input LoM belum lengkap: elang_capex, royalty",
         "LoM inputs incomplete: elang_capex, royalty"),
    ]


def _method_examples():
    source = lambda *kinds: method_chain.peer_ev_sources(
        [{"ev_ebitda": 8.0, "ev_source_kind": k} for k in kinds])
    return [
        ("PER FY skenario (fallback dari DCF FCFF; belum lengkap)",
         "Scenario FY PER (fallback from DCF FCFF; incomplete)"),
        (source("sectors", "yahoo"), "Sectors data and Yahoo Finance"),
        (source("sectors", None), "Sectors data and unrecorded sources"),
        (source("yahoo", None), "Yahoo Finance and unrecorded sources"),
        (source("sectors", "yahoo", None), "Sectors data and Yahoo Finance and unrecorded sources"),
        (source("yahoo"), "Yahoo Finance"),
        (source(), "no peers"),
        (method_chain.peer_multiple_source({"peer_basis": "grup peer kurasi Sektoral"}),
         "curated Peer Group (Sectors peer table and Yahoo Finance snapshots)"),
    ]


_MOVED_TEXT = (f"jumlah saham berubah {fmt.pct(0.2)} sejak akhir FY2025 (aksi korporasi); neraca "
               "akhir tahun tidak lagi mewakili dan skenario tidak memuat arus dana aksi korporasi")
_MOVED_EN = (f"the share count changed {fmt.pct(0.2)} since the end of FY2025 (corporate "
             "actions); the year-end balance sheet is no longer representative and the scenario "
             "does not carry the corporate-action funding flows")
_DA_REASON = ("D&A tidak tersedia atau tidak wajar di data Sectors dan rilis resmi (aturan yang "
              "sama dengan DCF skenario); tanpa penyusutan bersumber, EBIT, aset tetap, kas dan "
              "arus kas operasi tidak dihitung agar tidak mengarang angka.")
_DA_REASON_EN = ("D&A not available or implausible in Sectors data and official releases (the "
                 "same rule as the scenario DCF); without sourced depreciation, EBIT, fixed "
                 "assets, cash and operating cash flow are not calculated rather than invented.")
_NO_PAYOUT = ("Payout tidak tersedia di data Sectors maupun asumsi forecast, sehingga dividen "
              "dan ekuitas tidak dapat diproyeksikan.")
_NO_PAYOUT_EN = ("Payout is available neither in Sectors data nor in the forecast assumptions, "
                 "so dividends and equity cannot be projected.")


def _statement_examples():
    reasons = forecast_statements._reasons(
        bank=False, full=False, moved_text=_MOVED_TEXT, da_reason=_DA_REASON, has_ebitda=False,
        has_capex=False, base=None, first_year=2026, payout=None, bs_complete=False,
        income_ok=False, equity_reason=_NO_PAYOUT, shares=1.0, payout_sourced=False,
        payout_basis="asumsi analis", inventories_known=True)
    rolled = forecast_statements._reasons(
        bank=False, full=False, moved_text=None, da_reason=None, has_ebitda=True,
        has_capex=True, base={"year": 2025}, first_year=2026, payout=0.25, bs_complete=False,
        income_ok=True, equity_reason=None, shares=None, payout_sourced=False,
        payout_basis="asumsi analis 25% (tanpa payout historis di data Sectors)",
        inventories_known=True)
    full = forecast_statements._reasons(
        bank=False, full=True, moved_text=None, da_reason=None, has_ebitda=True, has_capex=True,
        base={"year": 2025}, first_year=2026, payout=0.25, bs_complete=True, income_ok=True,
        equity_reason=None, shares=1.0, payout_sourced=True, payout_basis="-",
        inventories_known=False)
    rows = [{"year": 2026, "label": "FY26F", "revenue": None, "ebitda": None, "roe": None,
             "interest_coverage": None, "dividends_paid": None},
            {"year": 2027, "label": "FY27F", "revenue": 1.0, "ebitda": 1.0, "roe": 0.1,
             "interest_coverage": 2.0, "dividends_paid": 1.0}]
    notes = forecast_statements._notes(
        rows, ("capex",), {"ebitda": "Skenario tidak memuat margin EBITDA untuk setiap tahun "
                                     "forecast."},
        {"interim": True, "when": "2026-06-30"})
    bank = bank_model._notes({"cost_of_funds": None, "ca_share": None, "sa_share": 1.0,
                              "capital_to_equity": None, "rwa_per_loan": 0.0}, None)
    return [
        (reasons["total_assets"],
         "Model mechanics: " + _MOVED_EN + ", so the balance sheet and cash flow are not "
         "projected. " + _DA_REASON_EN + " The scenario does not carry an EBITDA margin for every "
         "forecast year. The scenario does not carry a capex intensity for every forecast year. "
         "The FY2025 actual balance sheet is not available in Sectors data, so the balance sheet "
         "and cash flow cannot be rolled forward. " + _NO_PAYOUT_EN),
        (f"Mekanika model: {_MOVED_TEXT}, sehingga neraca dan arus kas tidak diproyeksikan.",
         "Model mechanics: " + _MOVED_EN + ", so the balance sheet and cash flow are not "
         "projected."),
        (reasons["depreciation"], _DA_REASON_EN),
        (reasons["ebitda"], "The scenario does not carry an EBITDA margin for every forecast year."),
        (reasons["capital_expenditure"],
         "The scenario does not carry a capex intensity for every forecast year."),
        (reasons["total_equity"], _NO_PAYOUT_EN),
        (reasons["interest_expense_non_operating"],
         "The earnings scenario does not separate interest expense from other non-operating "
         "items; their total is not calculated either. " + _DA_REASON_EN),
        (rolled["total_assets"],
         "The FY2025 Sectors balance sheet is incomplete (current assets or liabilities, fixed "
         "assets or cash), so the balance sheet and cash flow are not rolled forward."),
        (rolled["eps"],
         "The share count is available neither on the official balance sheet nor in Sectors "
         "data."),
        (rolled["dps"],
         "No historical payout: an analyst assumption of 25% with no historical payout in "
         "Sectors data. Forecast DPS and payout need a supported payout or dividend guidance."),
        (full["inventories"],
         "Inventories are not reported in FY2025 Sectors data; they are included in other "
         "current assets."),
        (f"Mekanika model: {_MOVED_TEXT}, dan neraca interim resmi (ekuitas) atau laba H2 "
         "skenario tidak tersedia; ekuitas tidak diproyeksikan.",
         "Model mechanics: " + _MOVED_EN + ", and the official interim balance sheet (equity) or "
         "scenario H2 profit is not available; equity is not projected."),
        ("Neraca aktual FY2025 tidak tersedia di data Sectors; ekuitas tidak dapat "
         "di-roll-forward.",
         "The FY2025 actual balance sheet is not available in Sectors data; equity cannot be "
         "rolled forward."),
        ("Neraca aktual FY2025 tidak tersedia di data Sectors, sehingga neraca dan arus kas "
         "tidak dapat di-roll-forward.",
         "The FY2025 actual balance sheet is not available in Sectors data, so the balance sheet "
         "and cash flow cannot be rolled forward."),
        ("Neraca dan arus kas tidak diproyeksikan.",
         "The balance sheet and cash flow are not projected."),
        (notes["capex"], "Not modelled in this scenario."),
        (notes["revenue"], "FY26F: cannot be calculated."),
        (notes["ebitda"],
         "FY26F: The scenario does not carry an EBITDA margin for every forecast year."),
        (notes["roe"], "FY26F: average equity is not positive; ROE is not meaningful."),
        (notes["interest_coverage"], "FY26F: zero interest expense."),
        (notes["dividends_paid"],
         "FY26F: the current year's dividend is already reflected in equity on the 2026-06-30 "
         "interim balance sheet; a full-year dividend cash flow is not modelled."),
        (forecast_statements.forecast_rows({}, {})["notes"]["revenue"],
         "There is no validated Analyst Scenario or production forecast yet; forecast years are "
         "not projected (the historical screening forecast is not used in the report)."),
        (forecast_statements.forecast_rows({"official_evidence": {"reporting_currency": "USD"}},
                                           {"earnings_scenario": {"year": 2026}})
         ["notes"]["revenue"],
         "No dated USD/IDR rate is available; the US$ scenario cannot be converted to Rupiah."),
        ("Skenario tidak memuat pendapatan dan laba untuk tahun forecast pertama; tahun "
         "forecast tidak diproyeksikan.",
         "The scenario does not carry revenue and profit for the first forecast year; forecast "
         "years are not projected."),
        (bank["interest_income"],
         "Sectors data do not carry interest expense and third-party deposits for the last two "
         "years, so the cost of funds cannot be calculated; the model projects NII directly from "
         "NIM without splitting interest income and expense."),
        (bank["casa_ratio"],
         "Base-year FY Sectors data do not separate current and savings accounts, so the deposit "
         "mix and CASA ratio are not projected."),
        (bank["capital_adequacy_ratio"],
         "Base-year FY Sectors data do not carry regulatory capital or risk-weighted assets, so "
         "CAR cannot be projected."),
        (bank["eps"], "The share count is not available."),
    ]


def _label_examples():
    # Valuation method labels (va["method"]) as app.valuation builds them.
    return [
        ("DDM dividen skenario FY26F-FY30F + terminal Gordon (CoE, bukan WACC)",
         "scenario dividend DDM FY26F-FY30F + Gordon terminal (CoE, not WACC)"),
        ("DCF FCFF skenario FY26F-FY30F + terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
         "scenario FCFF DCF FY26F-FY30F + Gordon terminal; historical exit EV/EBITDA as a cross-check"),
        ("DCF FCFF model operasional FY26F-FY30F + terminal Gordon; exit EV/EBITDA historis sebagai "
         "cross-check",
         "Operating Model FCFF DCF FY26F-FY30F + Gordon terminal; historical exit EV/EBITDA as a "
         "cross-check"),
        ("FY26F EV/EBITDA median peer x EBITDA skenario analis",
         "FY26F median peer EV/EBITDA x Analyst Scenario EBITDA"),
        *[(label, label) for label in ("SOTP/LoM (asset-based, no perpetual terminal)",
                                       "EV/EBITDA peer forward x EBITDA", "EV/Sales peer x Revenue")],
    ]


def _investability_examples():
    """app.investability's reasons and sources, quoted in the investability exhibits (#41)."""
    quality = investability.business_quality("XXXX", "2026-09-26", root="/nonexistent")
    reasons = {item["dimension"]: item["reason"] for item in quality}
    assessed = investability.assess({"ticker": "XXXX", "as_of": "2026-09-26"})
    return [
        (investability.liquidity("XXXX", "2026-09-26")["reason"],
         "fewer than 20 sessions of price and volume to 2026-09-26 in Sectors data"),
        ("data Sectors harian BBRI (harga penutupan x volume)",
         "Sectors daily data, BBRI (closing price x volume)"),
        (investability.free_float({})["reason"], "the public share is not in the ownership data"),
        ("data kepemilikan Sectors", "Sectors ownership data"),
        ("profil emiten data Sectors", "Sectors issuer profile"),
        (assessed["trading_status"]["reason"],
         "suspension status and special notations are not in the data; normal trading is not "
         "assumed"),
        (reasons["governance"],
         "unanswered: the Sektoral Team has not yet set an acceptable dated source for governance "
         "assessments (decision D8, 2026-09-26)"),
        (reasons["pricing_power"],
         "unanswered: not yet reviewed; the business-quality file holds no dated evidence for "
         "this dimension"),
    ]


def _lom_examples():
    """The LoM schedule's yearly basis (app.lom), its escalation basis and a US$
    reporter's NCI basis (app.forecast_statements)."""
    escalated = ("Jadwal LoM: umpan 68 Mt (Batu Hijau pit), katoda 205 kt, emas murni 515 koz; "
                 "dek Cu US$13.580/t dan Au US$4.653/oz (dek 2026 dieskalasi inflasi AS jangka "
                 "panjang 2,2% per tahun (IMF WEO Apr 2026)); EBITDA sesudah beban umum korporat; "
                 "bunga 2x beban keuangan 1H26; pajak dan PNBP pada tarif efektif 1H26.")
    return [
        (escalated,
         "LoM schedule: feed 68 Mt (Batu Hijau pit), cathode 205 kt, refined gold 515 koz; Cu "
         "deck US$13.580/t and Au US$4.653/oz (2026 deck escalated by long-term US inflation of "
         "2,2% a year (IMF WEO Apr 2026)); EBITDA after corporate overheads; interest at 2x 1H26 "
         "finance costs; tax and PNBP at 1H26 effective rates."),
        ("inflasi AS jangka panjang 2,2% per tahun (IMF WEO Apr 2026)",
         "long-term US inflation of 2,2% a year (IMF WEO Apr 2026)"),
        ("nilai buku FY2025, rilis tahunan resmi", "book value FY2025, official annual release"),
        # A title the issuer published in English is quoted as it is.
        ("nilai buku FY2025, AMMAN FY 2025 Earnings Release",
         "book value FY2025, AMMAN FY 2025 Earnings Release"),
        ("rilis tahunan resmi", "official annual release"),
    ]


def _driver_unit_examples():
    """Driver bases and test units (app.driver_value), a DCF bridge's parent share
    (app.scenario_value) and the bank model's funding warning (app.bank_model)."""
    return [
        ("50,3 ha/tahun", "50,3 ha/yr"),
        ("±25 ha/tahun", "±25 ha/yr"),
        ("±1 pp per tahun", "±1 pp per year"),
        ("±2% level harga", "±2% price level"),
        ("±2% level biaya, diteruskan ke tarif", "±2% cost level, passed through to tariffs"),
        ("porsi induk 92,2% dari laba 1H resmi", "parent share of 92,2% of official 1H profit"),
        ("tidak dilaporkan terpisah; dianggap tidak material",
         "not reported separately; taken as immaterial"),
        ("LDR di atas rekor tertinggi historis data Sectors (97,8%): FY26F 98,4%, FY27F 98,4%; "
         "kredit tumbuh lebih cepat dari pendanaan skenario",
         "LDR above its historical Sectors record (97,8%): FY26F 98,4%, FY27F 98,4%; loans grow "
         "faster than scenario funding"),
        ("CAR di bawah target jangka menengah manajemen (20,0%), di atas batas regulator: FY27F "
         "19,6%, FY28F 19,7%",
         "CAR below management's medium-term target (20,0%), above the regulatory floor: FY27F "
         "19,6%, FY28F 19,7%"),
    ]


EXAMPLES = (_bridge_examples() + _driver_examples() + _payout_examples()
            + _candidate_examples() + _method_examples() + _label_examples()
            + _statement_examples() + _investability_examples() + _lom_examples()
            + _driver_unit_examples())

# Fixed texts read straight from their producers: each must have English.
PRODUCED = sorted(
    {text for _, text in method_chain._READER_REASONS}
    | {label for label in method_chain.LABELS.values()
       if label not in {e[0] for e in _label_examples()}}
    | {name for name in method_chain.SHORT.values()
       if source_patterns.SHORT_EN[name] != name}
    | set(forecast_statements._BANK_REASONS.values())
    | set(forecast_statements._BANK_MODEL_REASONS.values())
    | {forecast_statements.R_GROSS, forecast_statements.R_INTEREST,
       forecast_statements.R_INTEREST_INCOME, forecast_statements.R_TRADE,
       forecast_statements.R_COVERAGE})


@pytest.mark.parametrize("id_text,en_text", EXAMPLES)
def test_examples_get_their_english(id_text, en_text):
    assert english(id_text) == en_text


@pytest.mark.parametrize("id_text", [e[0] for e in EXAMPLES] + PRODUCED)
def test_english_states_the_same_figures_in_english(id_text):
    en = english(id_text)
    assert prose_lang._UNTRANSLATED not in en
    assert prose_lang.figures(id_text) == prose_lang.figures(en)
    assert not prose_lang.mixed(en)


@pytest.mark.parametrize("id_text", [e[0] for e in EXAMPLES] + PRODUCED)
def test_one_pattern_per_text(id_text):
    assert len(matching(id_text)) == 1, matching(id_text)


def test_every_pattern_has_an_example():
    texts = [e[0] for e in EXAMPLES] + PRODUCED
    unused = [p.pattern for p, _ in source_patterns.PATTERNS
              if not any(p.fullmatch(text) for text in texts)]
    assert unused == []


def test_short_names_cover_the_method_chain():
    assert set(method_chain.SHORT.values()) <= set(source_patterns.SHORT_EN)


def test_nested_text_without_english_keeps_the_field_indonesian():
    # A group that is itself untranslated stays marked, so the field falls back.
    assert prose_lang._UNTRANSLATED in english("FY26F: Alasan tanpa terjemahan.")
    assert prose_lang._UNTRANSLATED in english("porsi induk FY2025 resmi, Laporan Tahunan XYZ")


def test_indonesian_builds_are_unchanged():
    for id_text, _ in EXAMPLES:
        assert prose_lang.source(id_text) == id_text
