"""English for Indonesian text the model builds before the prose stage.

Forecast, valuation and intake write short basis and reason strings
(``payout_basis``, ``dps_basis``, method-chain reader reasons, …) once, in
Indonesian, before ``app.build`` runs the prose stage in two languages; a
template quotes them through ``prose_lang.source``. Each entry is a pattern
over the whole Indonesian string and its English template; the groups carry
figures and names through unchanged, so the English states the same figures.

A template is a ``str.format`` string, or a ``_Call`` whose function builds
the English from the groups: that is how a group holding Indonesian (a nested
basis, a Method Chain short name) gets its own English. A nested string
without English stays marked, so its field falls back to Indonesian whole.

The Indonesian side is written out here, not imported from its producer:
when a producer changes its wording the old English no longer matches and
the prose falls back instead of stating something the Indonesian does not.
"""
import re


class _Call:
    """A template whose English is built by `fn` from the match groups."""

    def __init__(self, fn):
        self.fn = fn

    def format(self, *groups):
        return self.fn(*groups)


def _source(text):
    """Nested Indonesian through the same lookup (dictionary, then patterns)."""
    from . import prose_lang
    return prose_lang.source(text)


# A document title the issuer published in English ("AMMAN FY 2025 Earnings
# Release", "... Consolidated Financial Statements ...") is quoted as it is; an
# Indonesian one goes through the same lookup as other text, so it still falls
# back when it has no English.
_ENGLISH_TITLE = re.compile(r"\b(Release|Report|Statements?|Presentation|Earnings|Financial|"
                            r"Annual|Interim|Consolidated|Update)\b")


def _title(text):
    return text if _ENGLISH_TITLE.search(text) else _source(text)


def _fixed(pairs):
    """Patterns for strings without variable parts."""
    return [(re.escape(id_text), en_text.replace("{", "{{").replace("}", "}}"))
            for id_text, en_text in pairs]


DATE = r"(\d{4}-\d{2}-\d{2})"
LABELS = r"(FY\d{2}F(?:, FY\d{2}F)*)"      # forecast year labels, "FY26F, FY27F"
PCT = r"(-?[\d.,]+%)"                      # fmt.pct: "22,0%"

# --- Method Chain short names (app.method_chain.SHORT), as report_lang names them.
SHORT_EN = {
    "SOTP/LoM": "SOTP/LoM", "RNAV LoM": "RNAV LoM", "EV/EBITDA FY": "EV/EBITDA FY",
    "EV/EBITDA peer": "EV/EBITDA peer", "EV/Sales peer": "Peer EV/Sales",
    "P/S peer": "Peer P/S", "P/BV relatif": "Relative P/BV", "Holding SOTP": "Holding SOTP",
    "Property NAV": "Property NAV", "DCF referensi": "Reference DCF", "DCF FCFF": "DCF FCFF",
    "PER relatif": "Relative PER", "DDM": "DDM", "P/BV-ROE": "P/BV-ROE",
    "P/BV-ROE FY skenario": "Scenario FY P/BV-ROE", "P/BV buku": "Book P/BV",
    "PER FY skenario": "Scenario FY PER",
}
_SHORT = "(" + "|".join(re.escape(s) for s in sorted(SHORT_EN, key=len, reverse=True)) + ")"

# --- Balance-sheet bridge (app.scenario_value.bridge / bridge_native / _distributions),
# report-date shares (app.share_basis.report_date_shares) and parent share
# (app.forecast, app.bank_model, app.forecast_statements).
_BRIDGE = [
    (r"kas dan investasi jangka pendek, Sectors FY(\d{4})",
     "cash and short-term investments, Sectors FY{0}"),
    (r"kas dan investasi jangka pendek, Sectors kuartal " + DATE,
     "cash and short-term investments, Sectors quarter to {0}"),
    (r"kas dan investasi jangka pendek, neraca interim resmi (\S+)",
     "cash and short-term investments, official interim balance sheet at {0}"),
    (r"kas, neraca interim resmi (\S+)", "cash, official interim balance sheet at {0}"),
    (r"neraca interim resmi (\S+)", "official interim balance sheet at {0}"),
    (r"Sectors FY(\d{4})", "Sectors FY{0}"),
    (r"Sectors kuartal " + DATE, "Sectors quarter to {0}"),
    (r"utang berbunga, neraca interim resmi (\S+)",
     "interest-bearing debt, official interim balance sheet at {0}"),
    (r"nilai buku, Sectors " + DATE, "book value, Sectors {0}"),
    (r"nilai buku, neraca interim resmi (\S+)",
     "book value, official interim balance sheet at {0}"),
    # app.forecast_statements: NCI opening from a US$ reporter's annual release.
    (r"nilai buku FY(\d{4}), (.+)",
     _Call(lambda year, title: f"book value FY{year}, {_title(title)}")),
    (r"rilis tahunan resmi", "official annual release"),
    (r"tidak dilaporkan terpisah; ekuitas induk = total ekuitas",
     "not reported separately; parent equity = total equity"),
    (r"dividen tunai Rp([\d.,]+)/saham, ex-date (\d{4}-\d{2}-\d{2}(?:, \d{4}-\d{2}-\d{2})*) "
     r"\(data Sectors\), sesudah tanggal neraca " + DATE,
     "cash dividends of Rp{0}/share, ex-date {1} (Sectors data), after the balance-sheet "
     "date of {2}"),
    # bridge_native: a US$ model converts the rupiah bridge, or its dividends, at the
    # dated spot rate (without a rate there is nothing to convert, so no suffix).
    (r"(.+); rupiah ke US\$ pada kurs spot Rp([\d.,]+)/US\$",
     _Call(lambda base, fx: f"{_source(base)}; rupiah converted to US$ at the spot rate of "
                            f"Rp{fx}/US$")),
    (r"(dividen tunai .+); ke US\$ pada kurs spot Rp([\d.,]+)/US\$",
     _Call(lambda base, fx: f"{_source(base)}; converted to US$ at the spot rate of "
                            f"Rp{fx}/US$")),
    (r"register saham resmi (\S+), disesuaikan aksi korporasi hingga (\S+)",
     "official share register at {0}, adjusted for corporate actions to {1}"),
    (r"porsi induk (\S+) resmi", "official {0} parent share"),
    (r"porsi induk FY(\d{4}) resmi, (.+)",
     _Call(lambda year, title: f"official FY{year} parent share, {_title(title)}")),
    (r"laporan tahunan resmi", "official annual report"),
    (r"laba konsolidasi \(porsi induk tidak dilaporkan terpisah\)",
     "consolidated profit (parent share not reported separately)"),
    (r"laba konsolidasi; porsi induk tidak dilaporkan terpisah",
     "consolidated profit; parent share not reported separately"),
] + _fixed([
    ("akhir tahun fiskal, agar modal kerja musiman tidak mendistorsi utang bersih",
     "fiscal year-end, so that seasonal working capital does not distort net debt"),
    ("neraca interim terbaru; jumlah saham berubah material sejak akhir tahun fiskal",
     "latest interim balance sheet; the share count has changed materially since the fiscal "
     "year-end"),
    ("neraca kuartal terbaru; jumlah saham berubah material sejak akhir tahun fiskal",
     "latest quarterly balance sheet; the share count has changed materially since the fiscal "
     "year-end"),
    ("neraca resmi terbaru dalam US$, mata uang model; neraca akhir tahun data Sectors hanya "
     "tersedia dalam rupiah",
     "latest official balance sheet in US$, the model currency; the Sectors year-end balance "
     "sheet is only available in rupiah"),
    ("data Sectors", "Sectors data"),
])

# --- DCF drivers (app.scenario_value.da_intensity / tax_rate / nwc_intensity, the
# Operating Model's own basis, the LoM tax basis in app.forecast_statements) and
# the cost of debt (app.scenario_value.effective_cost_of_debt / usd_cost_of_debt).
_DRIVERS = [
    (r"penyusutan (\S+) resmi", "official {0} depreciation"),
    (r"EBITDA dikurangi laba usaha (\S+) resmi", "official {0} EBITDA less operating profit"),
    (r"penyusutan/pendapatan FY(\d{4}) laporan keuangan audit",
     "depreciation/revenue FY{0}, audited financial statements"),
    (r"penyusutan/pendapatan FY(\d{4})-FY(\d{4}) laporan keuangan audit",
     "depreciation/revenue FY{0}-FY{1}, audited financial statements"),
    (r"median D&A/pendapatan FY(\d{4})-FY(\d{4}) data Sectors",
     "median D&A/revenue FY{0}-FY{1}, Sectors data"),
    (r"median tarif efektif FY(\d{4})-FY(\d{4}) data Sectors",
     "median effective rate FY{0}-FY{1}, Sectors data"),
    (r"PPh " + PCT + r" dan PNBP " + PCT + r" efektif (\S+) resmi, digabung",
     "official {2} effective income tax {0} and PNBP {1}, combined"),
    (r"modal kerja non-kas FY(\d{4}) negatif \((-?\d+)% pendapatan\); tidak dihitung sebagai "
     r"sumber kas",
     "FY{0} non-cash working capital negative ({1}% of revenue); not counted as a source of cash"),
    (r"modal kerja non-kas FY(\d{4}) data Sectors \((-?[\d.,]+)% pendapatan\)",
     "FY{0} non-cash working capital, Sectors data ({1}% of revenue)"),
    (r"beban keuangan (\S+) resmi disetahunkan atas utang berbunga neraca resmi (\S+)",
     "official {0} finance costs annualised over interest-bearing debt on the official {1} "
     "balance sheet"),
    (r"bunga efektif emiten \((.+)\)",
     _Call(lambda basis: f"the issuer's effective interest rate ({_source(basis)})")),
    (r"UST 10Y \+ CRP, tingkat pasar pinjaman US\$ berisiko Indonesia \(parameter kebijakan "
     r"analis\); bunga efektif emiten " + PCT + r" \((.+)\) di bawah tingkat pasar, tidak dipakai",
     _Call(lambda rate, basis: "UST 10Y + CRP, the market rate for Indonesian-risk US$ "
                               f"borrowing (analyst policy parameter); the issuer's effective "
                               f"rate of {rate} ({_source(basis)}) is below the market rate and "
                               "is not used")),
] + _fixed([
    ("D&A tidak tersedia atau tidak wajar di data Sectors dan rilis resmi",
     "D&A not available or implausible in Sectors data and official releases"),
    ("model operasional (penyusutan atas aset tetap neto awal)",
     "per the Operating Model (depreciation on opening net fixed assets)"),
    ("model operasional", "per the Operating Model"),
    ("tarif PPh badan 22% (tarif efektif historis tidak tersedia)",
     "22% corporate income tax rate (historical effective rate not available)"),
    ("modal kerja tidak tersedia di data Sectors; ΔNWC dianggap nol",
     "working capital not available in Sectors data; ΔNWC taken as zero"),
    ("model operasional (hari piutang, persediaan, utang usaha)",
     "per the Operating Model (receivable, inventory and payable days)"),
    ("parameter kebijakan analis", "analyst policy parameter"),
    ("UST 10Y + CRP, tingkat pasar pinjaman US$ berisiko Indonesia (parameter kebijakan analis)",
     "UST 10Y + CRP, the market rate for Indonesian-risk US$ borrowing (analyst policy "
     "parameter)"),
])

# --- Payout and dividends (app.intake payout_basis / dps_basis,
# app.bank_model.terminal_payout, app.forecast_statements' default).
_PAYOUT = [
    (r"DPS 12 bulan terakhir Rp([\d.,]+) atas EPS FY(\d{4}) Rp([\d.,]+) \(data Sectors\)",
     "last 12 months' DPS of Rp{0} over FY{1} EPS of Rp{2} (Sectors data)"),
    (r"DPS historis (\w+)-(\w+) di data Sectors", "Historical DPS {0}-{1} in Sectors data"),
    (r"payout berkelanjutan 1 - g / ROE (\S+) \(" + PCT + " / " + PCT + r"\), di bawah payout "
     r"historis " + PCT,
     "sustainable payout 1 - g / ROE of {0} ({1} / {2}), below the historical payout of {3}"),
] + _fixed([
    ("asumsi analis 25% (tanpa payout historis di data Sectors)",
     "analyst assumption of 25% (no historical payout in Sectors data)"),
    ("payout ratio historis di data Sectors", "historical payout ratio in Sectors data"),
    ("sumber tidak tercatat", "unrecorded sources"),
    ("tanpa DPS historis di data Sectors", "No historical DPS in Sectors data"),
    ("payout kebijakan bersumber (di bawah payout berkelanjutan 1 - g / ROE)",
     "sourced policy payout (below the sustainable payout of 1 - g / ROE)"),
    ("payout historis (di bawah payout berkelanjutan 1 - g / ROE)",
     "historical payout (below the sustainable payout of 1 - g / ROE)"),
])

# --- Method Chain: reader reasons (app.method_chain.reader_reason), the raw
# candidate reasons it passes through (app.method_chain, app.scenario_value,
# app.valuation), short names, the cover's fallback label (narrative
# _chain_cover_label) and peer EV sources (peer_ev_sources / peer_multiple_source).
_READER = _fixed([
    ("Elang belum dapat dinilai: capex dan jadwal produksi studi kelayakan belum diungkapkan "
     "emiten",
     "Elang cannot be valued yet: the issuer has not disclosed the feasibility-study capex and "
     "production schedule"),
    ("NAV per aset dan jembatan ekuitas SOTP belum lengkap",
     "per-asset NAV and SOTP equity bridge incomplete"),
    ("skenario forecast analis belum tervalidasi", "analyst forecast scenario not yet validated"),
    ("hasil interim resmi belum tervalidasi", "official interim results not yet validated"),
    ("skenario interim bersumber belum tersedia", "sourced interim scenario not yet available"),
    ("skenario interim belum cocok dengan rilis resmi",
     "interim scenario does not yet match the official release"),
    ("harga penutupan bersumber sesudah rilis belum tersedia",
     "sourced post-release closing price not yet available"),
    ("kurs USD/IDR bersumber belum tersedia", "sourced USD/IDR rate not yet available"),
    ("jembatan kas, utang, minoritas dan saham belum lengkap",
     "cash, debt, minority and share bridge incomplete"),
    ("sensitivitas multiple 6x/8x/10x belum lengkap", "6x/8x/10x multiple sensitivity incomplete"),
    ("sensitivitas multiple tidak monoton", "multiple sensitivity not monotonic"),
    ("metode multiple hanya untuk profil tambang", "multiple method for the mining profile only"),
    ("hasil DDM belum tersedia", "DDM result not yet available"),
    ("forecast fisik tambang masih screening", "physical mining forecast still at screening"),
    ("jembatan operasi fisik ke keuangan belum ada", "no physical-to-financial operating bridge yet"),
    ("forecast driver belum lolos rekonsiliasi", "driver forecast has not passed reconciliation"),
    ("forecast driver bersumber belum lengkap", "sourced driver forecast incomplete"),
    ("forecast masih screening", "forecast still at screening"),
    ("seri driver forecast belum bersumber", "forecast driver series not yet sourced"),
    ("skenario laba FY belum tervalidasi", "FY earnings scenario not yet validated"),
    ("peer PER valid kurang dari tiga", "fewer than three valid peer PERs"),
    ("peer EV/EBITDA valid kurang dari tiga", "fewer than three valid peer EV/EBITDA multiples"),
    ("peer EV/EBITDA belum tersedia di cache", "peer EV/EBITDA not yet in the cache"),
    ("EBITDA FY skenario belum tersedia atau tidak positif",
     "scenario FY EBITDA not available or not positive"),
    ("peer EV/Sales belum tersedia di cache", "peer EV/Sales not yet in the cache"),
    ("peer P/BV valid kurang dari tiga", "fewer than three valid peer P/BVs"),
    ("SOTP holding belum tersedia", "holding SOTP not yet available"),
    ("NAV properti belum tersedia", "property NAV not yet available"),
    ("SOTP holding memerlukan evidence pack per anak usaha",
     "holding SOTP needs an evidence pack per subsidiary"),
    ("NAV properti memerlukan evidence pack per aset", "property NAV needs an evidence pack per asset"),
    ("jumlah saham resmi belum tersedia", "official share count not yet available"),
    ("skenario empat tahun lanjutan belum tervalidasi", "four-out-year scenario not yet validated"),
    ("payout historis bersumber belum tersedia", "sourced historical payout not yet available"),
    ("riwayat dividen kurang dari tiga tahun", "dividend history shorter than three years"),
    ("CoE tidak melebihi pertumbuhan jangka panjang", "CoE does not exceed long-term growth"),
    ("dividen lima tahun eksplisit belum lengkap", "five explicit years of dividends incomplete"),
    ("arus kas lima tahun eksplisit belum lengkap", "five explicit years of cash flow incomplete"),
    ("WACC tidak melebihi pertumbuhan jangka panjang", "WACC does not exceed long-term growth"),
    ("FCFF terminal tidak positif", "terminal FCFF not positive"),
    ("jembatan EV ke ekuitas belum lengkap", "EV-to-equity bridge incomplete"),
    ("nilai ekuitas tidak positif", "equity value not positive"),
    ("aset tetap kurang dari separuh total aset; P/BV bukan metode untuk emiten aset berat",
     "fixed assets below half of total assets; P/BV is not the method, as the issuer is not "
     "asset-heavy"),
    ("belum dimodelkan", "not yet modelled"),
    ("tidak dapat dinilai", "cannot be valued"),
])

_CANDIDATE = [
    (r"skala: ekuitas (-?\d+)% dari market cap \(ambang (\d+)-(\d+)%\)",
     "scale: equity at {0}% of market cap (threshold {1}-{2}%)"),
    (r"peer ([a-z_]+) belum tersedia di cache Sectors \((\d+) < (\d+)\); belum dimodelkan",
     "peer {0} not yet in the Sectors cache ({1} < {2}); not yet modelled"),
    (r"peer P/S valid (\d+) < (\d+); belum dimodelkan", "valid peer P/S {0} < {1}; not yet modelled"),
    (r"nilai pasar/buku (\S+) belum tersedia", "market/book value of {0} not yet available"),
    (r"skenario belum memuat margin EBITDA dan capex untuk " + LABELS,
     "the scenario does not yet carry EBITDA margin and capex for {0}"),
    (r"umur cadangan (.+) tidak terhitung",
     _Call(lambda name: f"reserve life of {_source(name)} not calculated")),
    (r"NAV (.+) tidak terhitung", _Call(lambda name: f"NAV of {_source(name)} not calculated")),
    (r"divergensi Gordon vs exit (\d+)% > 30%", "Gordon vs exit divergence {0}% > 30%"),
    (r"input LoM belum lengkap: ([a-z0-9_]+(?:, [a-z0-9_]+)*)", "LoM inputs incomplete: {0}"),
] + _fixed([
    ("nilai per saham tidak terdefinisi atau <= 0", "value per share undefined or <= 0"),
    ("downside sensitivitas tidak lebih rendah dari base", "sensitivity downside not below the base"),
    ("EPS forward <= 0; PER tidak bermakna", "forward EPS <= 0; PER not meaningful"),
    ("denominator forecast <= 0; multiple tidak bermakna",
     "forecast denominator <= 0; multiple not meaningful"),
    ("EBITDA forward <= 0; EV/EBITDA tidak bermakna", "forward EBITDA <= 0; EV/EBITDA not meaningful"),
    ("revenue forward <= 0; EV/Sales tidak bermakna", "forward revenue <= 0; EV/Sales not meaningful"),
    ("BVPS <= 0; P/BV tidak bermakna", "BVPS <= 0; P/BV not meaningful"),
    ("pendapatan forward atau jumlah saham belum tersedia",
     "forward revenue or share count not yet available"),
    ("ekuitas pemilik induk belum tersedia", "parent equity not yet available"),
    ("metode belum dihitung", "method not yet calculated"),
    ("skenario laba lima tahun (FY + empat tahun lanjutan) belum tervalidasi",
     "five-year earnings scenario (FY + four out-years) not yet validated"),
    ("payout historis tidak tersedia di data Sectors", "no historical payout in Sectors data"),
    ("jumlah saham atau tanggal neraca resmi tidak tersedia",
     "share count or official balance-sheet date not available"),
    ("laba pemilik induk skenario tidak lengkap", "scenario parent profit incomplete"),
    ("cost of equity tidak melebihi pertumbuhan jangka panjang",
     "cost of equity does not exceed long-term growth"),
    ("imbal hasil UST 10Y bertanggal tidak tersedia pada tanggal laporan; arus kas US$ tidak "
     "didiskonto dengan tingkat rupiah",
     "no dated UST 10Y yield on the Report Date; US$ cash flows are not discounted at a rupiah "
     "rate"),
    ("jumlah saham, kurs atau tanggal neraca tidak tersedia",
     "share count, exchange rate or balance-sheet date not available"),
    ("kas atau utang untuk jembatan EV ke ekuitas tidak tersedia",
     "cash or debt for the EV-to-equity bridge not available"),
    ("skenario laba FY (aktual 1H resmi + asumsi H2) belum tervalidasi",
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
    ("grid sensitivitas DDM gagal", "DDM sensitivity grid failed"),
    ("hasil DDM/Inverse CoE tidak tersedia", "DDM/Inverse CoE result not available"),
    ("ROE forward tidak terhitung (ekuitas forecast kosong)",
     "forward ROE not calculated (forecast equity empty)"),
    ("BVPS <= 0 atau tidak tersedia", "BVPS <= 0 or not available"),
])

_PEER_SOURCES = ("data Sectors", "Yahoo Finance", "sumber tidak tercatat")
_PEER_SOURCES_EN = dict(zip(_PEER_SOURCES, ("Sectors data", "Yahoo Finance", "unrecorded sources")))

_METHOD = [
    (_SHORT + r" \(fallback dari " + _SHORT + r"; belum lengkap\)",
     _Call(lambda sel, first: f"{SHORT_EN[sel]} (fallback from {SHORT_EN[first]}; incomplete)")),
] + _fixed([(name, en) for name, en in SHORT_EN.items() if name != en]) + _fixed([
    # peer_ev_sources: the kinds present, in order, joined by " dan "; single
    # "data Sectors" and "sumber tidak tercatat" are shared with the bases above.
    *[(" dan ".join(parts), " and ".join(_PEER_SOURCES_EN[p] for p in parts))
      for parts in (_PEER_SOURCES[:2], _PEER_SOURCES[::2], _PEER_SOURCES[1:], _PEER_SOURCES)],
    ("Yahoo Finance", "Yahoo Finance"),
    ("tanpa peer", "no peers"),
    ("grup peer kurasi (tabel peer Sectors dan snapshot Yahoo Finance)",
     "curated Peer Group (Sectors peer table and Yahoo Finance snapshots)"),
])

# --- Valuation method labels (va["method"]): the scenario primaries of
# app.valuation and the fixed app.method_chain.LABELS, quoted as "the Target
# Price uses {method}".
_YEARS = r"FY(\d{2})F-FY(\d{2})F"
_LABEL = [
    (r"DDM dividen skenario " + _YEARS + r" \+ terminal Gordon \(CoE, bukan WACC\)",
     "scenario dividend DDM FY{0}F-FY{1}F + Gordon terminal (CoE, not WACC)"),
    (r"DCF FCFF skenario " + _YEARS + r" \+ terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
     "scenario FCFF DCF FY{0}F-FY{1}F + Gordon terminal; historical exit EV/EBITDA as a cross-check"),
    (r"DCF FCFF model operasional " + _YEARS
     + r" \+ terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
     "Operating Model FCFF DCF FY{0}F-FY{1}F + Gordon terminal; historical exit EV/EBITDA as a cross-check"),
    (r"FY(\d{2})F EV/EBITDA median peer x EBITDA skenario analis",
     "FY{0}F median peer EV/EBITDA x Analyst Scenario EBITDA"),
] + _fixed([
    # Already English in app.method_chain.LABELS.
    ("SOTP/LoM (asset-based, no perpetual terminal)", "SOTP/LoM (asset-based, no perpetual terminal)"),
    ("EV/EBITDA peer forward x EBITDA", "EV/EBITDA peer forward x EBITDA"),
    ("EV/Sales peer x Revenue", "EV/Sales peer x Revenue"),
    ("RNAV LoM anuitas (tanpa terminal perpetual)", "annuity RNAV LoM (no perpetual terminal)"),
    ("FY26F EV/EBITDA 8x (asumsi analis)", "FY26F EV/EBITDA 8x (analyst assumption)"),
    ("P/S peer x Sales per share", "peer P/S x sales per share"),
    ("P/BV relatif peer x BVPS", "peer-relative P/BV x BVPS"),
    ("Holding SOTP per anak usaha/aset", "holding SOTP by subsidiary/asset"),
    ("Property NAV per aset", "property NAV by asset"),
    ("DCF konsolidasi (referensi)", "consolidated DCF (reference)"),
    ("DCF FCFF eksplisit + terminal Gordon, dibobot sama dengan exit EV/EBITDA",
     "explicit FCFF DCF + Gordon terminal, weighted equally with exit EV/EBITDA"),
    ("Relatif PER peer (median) x EPS forward", "peer-relative PER (median) x forward EPS"),
    ("DDM dividen eksplisit + terminal Gordon (CoE, bukan WACC)",
     "explicit dividend DDM + Gordon terminal (CoE, not WACC)"),
    ("P/BV wajar vs ROE (Inverse CoE)", "fair P/BV vs ROE (Inverse CoE)"),
    ("P/BV wajar dari ROE skenario laba FY", "fair P/BV from the FY earnings scenario ROE"),
    ("P/BV peer x nilai buku terlapor (aset berat)", "peer P/BV x reported book value (asset-heavy)"),
    ("FY26F PER median peer x EPS skenario analis", "FY26F median peer PER x Analyst Scenario EPS"),
])

# --- Statement notes (app.forecast_statements notes; app.bank_model._notes): why a
# line is not modelled, quoted next to the charts.
_MOVED = (r"jumlah saham berubah " + PCT + r" sejak akhir FY(\d{4}) \(aksi korporasi\); neraca "
          r"akhir tahun tidak lagi mewakili dan skenario tidak memuat arus dana aksi korporasi")
_MOVED_EN = ("the share count changed {0} since the end of FY{1} (corporate actions); the "
             "year-end balance sheet is no longer representative and the scenario does not carry "
             "the corporate-action funding flows")
_NOTE_PARTS = [
    (r"Mekanika model: " + _MOVED + r", sehingga neraca dan arus kas tidak diproyeksikan\.",
     "Model mechanics: " + _MOVED_EN + ", so the balance sheet and cash flow are not "
     "projected."),
    (r"Neraca aktual FY(\d{4}) tidak tersedia di data Sectors, sehingga neraca dan arus kas "
     r"tidak dapat di-roll-forward\.",
     "The FY{0} actual balance sheet is not available in Sectors data, so the balance sheet "
     "and cash flow cannot be rolled forward."),
    (r"Neraca FY(\d{4}) data Sectors tidak lengkap \(aset atau liabilitas lancar, aset tetap "
     r"atau kas\), sehingga neraca dan arus kas tidak di-roll-forward\.",
     "The FY{0} Sectors balance sheet is incomplete (current assets or liabilities, fixed "
     "assets or cash), so the balance sheet and cash flow are not rolled forward."),
] + _fixed([
    ("D&A tidak tersedia atau tidak wajar di data Sectors dan rilis resmi (aturan yang sama "
     "dengan DCF skenario); tanpa penyusutan bersumber, EBIT, aset tetap, kas dan arus kas "
     "operasi tidak dihitung agar tidak mengarang angka.",
     "D&A not available or implausible in Sectors data and official releases (the same rule as "
     "the scenario DCF); without sourced depreciation, EBIT, fixed assets, cash and operating "
     "cash flow are not calculated rather than invented."),
    ("Skenario tidak memuat margin EBITDA untuk setiap tahun forecast.",
     "The scenario does not carry an EBITDA margin for every forecast year."),
    ("Skenario tidak memuat intensitas capex untuk setiap tahun forecast.",
     "The scenario does not carry a capex intensity for every forecast year."),
    ("Payout tidak tersedia di data Sectors maupun asumsi forecast, sehingga dividen dan "
     "ekuitas tidak dapat diproyeksikan.",
     "Payout is available neither in Sectors data nor in the forecast assumptions, so "
     "dividends and equity cannot be projected."),
])
_NOTE_PART_RES = [re.compile(p) for p, _ in _NOTE_PARTS]


def _joined(text):
    """English of the statements note that joins several reasons with spaces
    (``forecast_statements._reasons`` when the balance sheet is not rolled)."""
    out, pos = [], 0
    while pos < len(text):
        for part in _NOTE_PART_RES:
            found = part.match(text, pos)
            if found and (found.end() == len(text) or text[found.end()] == " "):
                out.append(_source(found.group(0)))
                pos = found.end() + 1
                break
        else:
            from . import prose_lang
            return f"{prose_lang._UNTRANSLATED}{text}{prose_lang._UNTRANSLATED}"
    return " ".join(out)


_NOTE_PART = "(?:" + "|".join(p for p, _ in _NOTE_PARTS) + ")"

_NOTES = _NOTE_PARTS + [
    ("(" + _NOTE_PART + "(?: " + _NOTE_PART + ")+)", _Call(lambda text, *_: _joined(text))),
    (r"Mekanika model: " + _MOVED + r", dan neraca interim resmi \(ekuitas\) atau laba H2 "
     r"skenario tidak tersedia; ekuitas tidak diproyeksikan\.",
     "Model mechanics: " + _MOVED_EN + ", and the official interim balance sheet (equity) or "
     "scenario H2 profit is not available; equity is not projected."),
    (r"Neraca aktual FY(\d{4}) tidak tersedia di data Sectors; ekuitas tidak dapat "
     r"di-roll-forward\.",
     "The FY{0} actual balance sheet is not available in Sectors data; equity cannot be rolled "
     "forward."),
    (r"Persediaan tidak dilaporkan di data Sectors FY(\d{4}); termasuk dalam aset lancar lain\.",
     "Inventories are not reported in FY{0} Sectors data; they are included in other current "
     "assets."),
    (r"Skenario laba tidak memisahkan beban bunga dari pos non-operasional lain; totalnya pun "
     r"tidak dihitung\. (.+)",
     _Call(lambda why: "The earnings scenario does not separate interest expense from other "
                       f"non-operating items; their total is not calculated either. "
                       f"{_source(why)}")),
    (r"Payout historis tidak tersedia: asumsi analis (\d+)% \(?tanpa payout historis di data "
     r"Sectors\)?\. DPS dan payout forecast memerlukan payout atau panduan dividen yang "
     r"didukung\.",
     "No historical payout: an analyst assumption of {0}% with no historical payout in Sectors "
     "data. Forecast DPS and payout need a supported payout or dividend guidance."),
    # A line missing in some years: the years, then the reason.
    (LABELS + r": ([A-Z].+)", _Call(lambda years, why: f"{years}: {_source(why)}")),
    (LABELS + r": tidak dapat dihitung\.", "{0}: cannot be calculated."),
    (LABELS + r": ekuitas rata-rata tidak positif; ROE tidak bermakna\.",
     "{0}: average equity is not positive; ROE is not meaningful."),
    (LABELS + r": beban bunga nol\.", "{0}: zero interest expense."),
    (LABELS + r": dividen tahun berjalan sudah tercermin di ekuitas neraca interim (\S+); arus "
     r"kas dividen setahun penuh tidak dimodelkan\.",
     "{0}: the current year's dividend is already reflected in equity on the {1} interim "
     "balance sheet; a full-year dividend cash flow is not modelled."),
] + _fixed([
    ("Tidak dimodelkan pada skenario ini.", "Not modelled in this scenario."),
    ("Skenario tidak memuat pendapatan dan laba untuk tahun forecast pertama; tahun forecast "
     "tidak diproyeksikan.",
     "The scenario does not carry revenue and profit for the first forecast year; forecast "
     "years are not projected."),
    ("Belum ada skenario analis tervalidasi atau forecast produksi; tahun forecast tidak "
     "diproyeksikan (forecast screening historis tidak dipakai di laporan).",
     "There is no validated Analyst Scenario or production forecast yet; forecast years are not "
     "projected (the historical screening forecast is not used in the report)."),
    ("Kurs USD/IDR bertanggal tidak tersedia; skenario dalam US$ tidak dapat dikonversi ke "
     "Rupiah.",
     "No dated USD/IDR rate is available; the US$ scenario cannot be converted to Rupiah."),
    ("Neraca dan arus kas tidak diproyeksikan.", "The balance sheet and cash flow are not projected."),
    ("Jumlah saham tidak tersedia di neraca resmi maupun data Sectors.",
     "The share count is available neither on the official balance sheet nor in Sectors data."),
    ("Jumlah saham tidak tersedia.", "The share count is not available."),
    # R_GROSS, R_INTEREST, R_INTEREST_INCOME, R_TRADE, R_COVERAGE
    ("Skenario analis menetapkan margin EBITDA, bukan margin laba kotor; memecah EBITDA menjadi "
     "beban pokok pendapatan dan beban usaha memerlukan asumsi margin kotor yang tidak dipakai "
     "valuasi dan tidak bersumber, sehingga tidak dimodelkan.",
     "The Analyst Scenario sets an EBITDA margin, not a gross margin; splitting EBITDA into cost "
     "of revenue and operating expenses would need a gross-margin assumption that the valuation "
     "does not use and that is not sourced, so it is not modelled."),
    ("Skenario laba tidak memisahkan beban bunga dari pos non-operasional lain; totalnya, yaitu "
     "laba sebelum pajak dikurangi EBIT yang implisit dari margin laba bersih skenario, tersaji "
     "sebagai pendapatan (beban) lain-lain bersih termasuk bunga.",
     "The earnings scenario does not separate interest expense from other non-operating items; "
     "their total, pre-tax profit less the EBIT implied by the scenario net margin, is shown as "
     "net other income (expense) including interest."),
    ("Data Sectors tidak memuat pendapatan bunga emiten non-keuangan; pendapatan bunga termasuk "
     "dalam pos non-operasional bersih.",
     "Sectors data do not carry interest income for non-financial issuers; interest income is "
     "included in net non-operating items."),
    ("Data Sectors tidak memisahkan piutang usaha dan utang usaha emiten non-keuangan; keduanya "
     "termasuk dalam aset lancar lain dan liabilitas lancar lain, yang bergerak dengan modal "
     "kerja.",
     "Sectors data do not separate trade receivables and trade payables for non-financial "
     "issuers; both are included in other current assets and other current liabilities, which "
     "move with working capital."),
    ("Beban bunga tidak dipisahkan dalam skenario, sehingga cakupan bunga (EBIT dibagi beban "
     "bunga) tidak dapat dihitung.",
     "Interest expense is not separated in the scenario, so interest coverage (EBIT divided by "
     "interest expense) cannot be calculated."),
    # _BANK_REASONS
    ("Skenario laba bank tidak memodelkan aset produktif, imbal hasil dan biaya dana, sehingga "
     "pendapatan bunga, beban bunga dan pendapatan bunga bersih tidak diproyeksikan.",
     "The bank earnings scenario does not model earning assets, yields and cost of funds, so "
     "interest income, interest expense and net interest income are not projected."),
    ("Skenario laba bank menetapkan pendapatan dan margin laba bersih tanpa memecahnya menjadi "
     "pendapatan non-bunga, beban operasional, provisi dan PPOP.",
     "The bank earnings scenario sets revenue and net margin without splitting them into "
     "non-interest income, operating expenses, provisions and PPOP."),
    ("Skenario laba bank menetapkan margin laba bersih; laba sebelum pajak dan pajak tidak "
     "diturunkan agar tidak menambah asumsi yang tidak dipakai DDM.",
     "The bank earnings scenario sets the net margin; pre-tax profit and tax are not derived, "
     "so as not to add assumptions the DDM does not use."),
    ("Skenario laba bank tidak memodelkan penyaluran kredit, cadangan kerugian dan kredit "
     "bermasalah; kredit bruto, cadangan, kredit bersih dan NPL tidak diproyeksikan.",
     "The bank earnings scenario does not model lending, loss allowances and non-performing "
     "loans; gross loans, allowances, net loans and NPLs are not projected."),
    ("Skenario laba bank tidak memodelkan obligasi pemerintah, surat berharga dan aset "
     "produktif lain; total aset produktif dan total aset tidak diproyeksikan.",
     "The bank earnings scenario does not model government bonds, securities and other earning "
     "assets; total earning assets and total assets are not projected."),
    ("Skenario laba bank tidak memodelkan simpanan nasabah (giro, tabungan, deposito), pinjaman "
     "dan liabilitas lain; neraca pendanaan bank tidak diproyeksikan.",
     "The bank earnings scenario does not model customer deposits (current, savings and time "
     "deposits), borrowings and other liabilities; the bank's funding balance sheet is not "
     "projected."),
    ("Arus kas dan kas bank tidak diproyeksikan; DDM menilai dividen, bukan arus kas bebas.",
     "The bank's cash flow and cash are not projected; the DDM values dividends, not free cash "
     "flow."),
    ("EBITDA, EBIT dan D&A tidak bermakna untuk bank; skenario laba bank tidak memecah beban "
     "operasional menurut jenisnya.",
     "EBITDA, EBIT and D&A are not meaningful for a bank; the bank earnings scenario does not "
     "split operating expenses by type."),
    ("Capex, modal kerja dan FCFF tidak dipakai untuk institusi keuangan.",
     "Capex, working capital and FCFF are not used for a financial institution."),
    ("Pos laporan keuangan emiten non-keuangan; tidak berlaku untuk bank.",
     "A non-financial issuer's statement line; not applicable to a bank."),
    ("Skenario laba bank tidak memodelkan aset produktif dan dana berbiaya, sehingga imbal hasil "
     "aset produktif, biaya dana dan NIM tidak diproyeksikan.",
     "The bank earnings scenario does not model earning assets and interest-bearing funds, so "
     "the earning-asset yield, cost of funds and NIM are not projected."),
    ("Skenario laba bank tidak memodelkan beban operasional, provisi dan kredit bermasalah, "
     "sehingga rasio biaya, biaya kredit dan cakupan cadangan tidak diproyeksikan.",
     "The bank earnings scenario does not model operating expenses, provisions and "
     "non-performing loans, so the cost ratio, cost of credit and allowance coverage are not "
     "projected."),
    ("Skenario laba bank tidak memodelkan kredit, simpanan nasabah, aset tertimbang menurut "
     "risiko dan total aset, sehingga LDR, rasio CASA, CAR dan ROAA tidak diproyeksikan.",
     "The bank earnings scenario does not model loans, customer deposits, risk-weighted assets "
     "and total assets, so LDR, the CASA ratio, CAR and ROAA are not projected."),
    # _BANK_MODEL_REASONS
    ("Model driver bank memakai biaya kredit sebagai driver kualitas aset; data Sectors tidak "
     "memuat kredit bermasalah, sehingga NPL dan cakupan cadangan terhadap NPL tidak "
     "diproyeksikan.",
     "The bank driver model uses the cost of credit as the asset-quality driver; Sectors data "
     "do not carry non-performing loans, so NPLs and allowance coverage of NPLs are not "
     "projected."),
    ("Model driver bank memproyeksikan aset produktif selain kredit sebagai satu pos "
     "penyeimbang pendanaan tanpa memecahnya menjadi obligasi pemerintah, surat berharga dan "
     "penempatan.",
     "The bank driver model projects earning assets other than loans as one funding balancing "
     "item, without splitting it into government bonds, securities and placements."),
    ("Pendapatan non-bunga model mencakup seluruh pendapatan di antara NII dan laba sebelum "
     "pajak (fee, premi bersih dan pos non-operasional), sehingga pos non-operasional tidak "
     "dipisahkan.",
     "The model's non-interest income covers all income between NII and pre-tax profit (fees, "
     "net premiums and non-operating items), so non-operating items are not separated."),
    ("Arus kas bank tidak diproyeksikan: DDM menilai dividen, dan kas termasuk aset "
     "non-produktif yang model driver bank jaga pada porsi historisnya terhadap total aset.",
     "The bank's cash flow is not projected: the DDM values dividends, and cash is among the "
     "non-earning assets the bank driver model holds at their historical share of total "
     "assets."),
    ("Pendanaan bank dimodelkan sebagai DPK, liabilitas berbunga lain dan liabilitas tanpa "
     "bunga; utang korporasi tidak dipisahkan.",
     "Bank funding is modelled as third-party deposits, other interest-bearing liabilities and "
     "non-interest-bearing liabilities; corporate debt is not separated."),
    ("EBITDA, EBIT dan D&A tidak bermakna untuk bank; model driver bank menurunkan beban "
     "operasional dari rasio biaya terhadap pendapatan tanpa memecahnya menurut jenis.",
     "EBITDA, EBIT and D&A are not meaningful for a bank; the bank driver model derives "
     "operating expenses from the cost-to-income ratio without splitting them by type."),
    # app.bank_model._notes
    ("Data Sectors tidak memuat beban bunga dan DPK dua tahun terakhir, sehingga biaya dana "
     "tidak dapat dihitung; model memproyeksikan NII langsung dari NIM tanpa memecah pendapatan "
     "dan beban bunga.",
     "Sectors data do not carry interest expense and third-party deposits for the last two "
     "years, so the cost of funds cannot be calculated; the model projects NII directly from "
     "NIM without splitting interest income and expense."),
    ("Data Sectors FY dasar tidak memisahkan giro dan tabungan, sehingga komposisi DPK dan rasio "
     "CASA tidak diproyeksikan.",
     "Base-year FY Sectors data do not separate current and savings accounts, so the deposit mix "
     "and CASA ratio are not projected."),
    ("Data Sectors FY dasar tidak memuat modal regulasi atau ATMR, sehingga CAR tidak dapat "
     "diproyeksikan.",
     "Base-year FY Sectors data do not carry regulatory capital or risk-weighted assets, so CAR "
     "cannot be projected."),
])

# --- The LoM schedule's yearly basis (app.lom outyear rows), quoted in the
# scenario basis table.
def _lom_kinds(kinds):
    return kinds.replace("konsentrat", "concentrate")


_LOM = [
    (r"Jadwal LoM: umpan ([\d.,]+) Mt \(([^()]*)\), katoda ([\d.,]+) kt, emas murni ([\d.,]+) koz; "
     r"dek Cu US\$([\d.,]+)/t dan Au US\$([\d.,]+)/oz(?: \(dek 2026 dieskalasi (.+)\))?; EBITDA "
     r"sesudah beban umum korporat; bunga 2x beban keuangan 1H26; pajak dan PNBP pada tarif "
     r"efektif 1H26\.",
     _Call(lambda feed, kinds, cathode, gold, cu, au, esc:
           f"LoM schedule: feed {feed} Mt ({_lom_kinds(kinds)}), cathode {cathode} kt, refined "
           f"gold {gold} koz; Cu deck US${cu}/t and Au US${au}/oz"
           + (f" (2026 deck escalated by {_source(esc)})" if esc else "")
           + "; EBITDA after corporate overheads; interest at 2x 1H26 finance costs; tax and "
           "PNBP at 1H26 effective rates.")),
    (r"inflasi AS jangka panjang ([\d.,]+%) per tahun \((.+)\)",
     "long-term US inflation of {0} a year ({1})"),
]

# --- Model drivers' base values and test units (app.driver_value), quoted with
# their figures as written in the decision summary and catalyst thresholds; a
# DCF bridge's parent share (app.scenario_value); the bank model's funding
# warning (app.bank_model.checks).
_DRIVER_UNITS = [
    (r"([\d.,]+) ha/tahun", "{0} ha/yr"),
    (r"±([\d.,]+) ha/tahun", "±{0} ha/yr"),
    (r"±([\d.,]+) pp per tahun", "±{0} pp per year"),
    (r"±([\d.,]+)% level harga", "±{0}% price level"),
    (r"±([\d.,]+)% level biaya, diteruskan ke tarif", "±{0}% cost level, passed through to tariffs"),
    (r"porsi induk ([\d.,]+)% dari laba 1H resmi", "parent share of {0}% of official 1H profit"),
    (r"(LDR|porsi kredit dalam aset produktif) di atas rekor tertinggi historis data Sectors "
     r"\(" + PCT + r"\): (.+); kredit tumbuh lebih cepat dari pendanaan skenario",
     _Call(lambda name, record, years:
           f"{'LDR' if name == 'LDR' else 'loan share of earning assets'} above its historical "
           f"Sectors record ({record}): {years}; loans grow faster than scenario funding")),
    (r"CAR di bawah target jangka menengah manajemen \(" + PCT + r"\), di atas batas regulator: "
     r"(.+)",
     "CAR below management's medium-term target ({0}), above the regulatory floor: {1}"),
] + _fixed([
    ("tidak dilaporkan terpisah; dianggap tidak material",
     "not reported separately; taken as immaterial"),
])

# --- Liquidity and business quality (app.investability), quoted in the
# investability exhibits.
_INVESTABILITY = [
    (r"kurang dari 20 sesi harga dan volume sampai " + DATE + r" di data Sectors",
     "fewer than 20 sessions of price and volume to {0} in Sectors data"),
    (r"data Sectors harian (\S+) \(harga penutupan x volume\)",
     "Sectors daily data, {0} (closing price x volume)"),
] + _fixed([
    ("porsi publik tidak tersedia di data kepemilikan",
     "the public share is not in the ownership data"),
    ("data kepemilikan Sectors", "Sectors ownership data"),
    ("profil emiten data Sectors", "Sectors issuer profile"),
    ("status suspensi dan notasi khusus tidak ada di data; tidak diasumsikan normal",
     "suspension status and special notations are not in the data; normal trading is not "
     "assumed"),
    ("tidak dijawab: Sectoral Team belum menetapkan sumber penilaian tata kelola bertanggal yang "
     "dapat diterima (keputusan D8, 2026-09-26)",
     "unanswered: the Sectoral Team has not yet set an acceptable dated source for governance "
     "assessments (decision D8, 2026-09-26)"),
    ("tidak dijawab: belum ditelaah; berkas kualitas bisnis tidak memuat bukti bertanggal untuk "
     "dimensi ini",
     "unanswered: not yet reviewed; the business-quality file holds no dated evidence for this "
     "dimension"),
])

PATTERNS = [(re.compile(p), t) for p, t in (
    _BRIDGE + _DRIVERS + _PAYOUT + _READER + _CANDIDATE + _METHOD + _LABEL + _NOTES
    + _INVESTABILITY + _LOM + _DRIVER_UNITS
)]
