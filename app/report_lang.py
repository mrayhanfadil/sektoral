"""Report language: the fixed words of a Company Update in Indonesian or English.

A report document is built once, in Indonesian, and stored; every language is
rendered from that same document (``app.render``), so a rebuild or re-render
needs no second pipeline run and both files carry the same figures.

``label`` turns the document's fixed text (exhibit titles, table headers, row
labels, short cells, section headings) into English: an exact term, a pattern
for templated labels ("Band P/E 12 bulan AMMN"), or, for text it does not
know, the same words with English figures, months and scale words. ``note``
does the same for methodology notes but leaves unknown sentences whole: prose
stays Indonesian until #33 and #34. Indonesian (the default) returns every
string unchanged.
"""
from __future__ import annotations

import functools
import re

from . import fmt, methodnote, valtables

LANGS = fmt.LANGS
DEFAULT = "id"


def check(lang: str) -> str:
    if lang not in LANGS:
        raise ValueError(f"unknown report language {lang!r} ({'|'.join(LANGS)})")
    return lang


def file_name(ticker, lang: str = DEFAULT, ext: str = "html") -> str:
    """``AMMN.html`` / ``AMMN.pdf`` in Indonesian, ``AMMN.en.html`` / ``AMMN.en.pdf`` in English."""
    t = str(ticker).upper()
    return f"{t}.{ext}" if lang == DEFAULT else f"{t}.{check(lang)}.{ext}"


# Exhibits with a stable id (app.exhibit_ids) take their English title from here.
TITLES = {"key_financials": "Key Financials",
          "method_chain": "Valuation Method Chain",
          "catalysts": "Catalysts, risks and monitoring indicators",
          **valtables.TITLES_EN}

# Fixed Indonesian text of the report document and its English form, in
# concise sell-side English with the terms of CONTEXT.md.
TERMS = {
    # Section headings and cover paragraph headings.
    "Cadangan, jadwal proyek, dan biaya": "Reserves, project schedule and costs",
    "Capex historis dan asumsi analis FY26": "Historical capex and FY26 Analyst Assumptions",
    "Cross-check dan bukti lanjutan": "Cross-checks and further evidence",
    "Data keuangan": "Financial data",
    "Driver dan skenario nilai": "Drivers and value scenarios",
    "Elang: skala tambang dan infrastruktur pada tahap AMDAL":
        "Elang: mine and infrastructure scale at the AMDAL stage",
    "Forecast FY26F dari rilis terbaru": "FY26F forecast from the latest release",
    "Hasil terbaru dan jembatan laba": "Latest results and earnings bridge",
    "Industri dan harga komoditas": "Industry and commodity prices",
    "Industri dan sentimen": "Industry and sentiment",
    "Jadwal operasi dan status pengembangan tambang": "Operating schedule and mine development status",
    "Jembatan korporat untuk SOTP": "Corporate bridge for the SOTP",
    "Katalis, risiko, dan kepemilikan": "Catalysts, risks and ownership",
    "Kinerja keuangan dan profitabilitas": "Financial performance and profitability",
    "Kualitas bisnis dan investabilitas": "Business quality and investability",
    "Lampiran valuasi: tingkat diskonto, uji dan asumsi":
        "Valuation appendix: discount rates, tests and assumptions",
    "Operasi dan posisi keuangan": "Operations and financial position",
    "Perbandingan peer": "Peer comparison",
    "Royalti, bea keluar, dan netback": "Royalties, export duty and netback",
    "Skenario nilai": "Value scenarios",
    "Tesis investasi": "Investment thesis",
    "Valuasi dan kelengkapan bukti": "Valuation and evidence completeness",
    "Skenario FY26 dari rilis terbaru": "FY26 scenario from the latest release",
    "Cross-check nilai FY26 dari hasil terbaru": "FY26 value cross-check from latest results",
    "Asumsi skenario dan batasannya": "Scenario assumptions and their limits",
    "Driver operasi perlu diuji": "Operating drivers still to be tested",
    "Hasil terbaru memberi titik awal": "Latest results set the starting point",
    "Pandangan Kami: driver laba ke depan": "Our view: forward earnings drivers",
    # Exhibit titles.
    "Aktivitas investor asing": "Foreign investor activity",
    "Arus kas": "Cash flow",
    "Asumsi analis dalam SOTP/LoM": "Analyst Assumptions in the SOTP/LoM",
    "Asumsi eksplisit untuk skenario 2H26": "Explicit assumptions for the 2H26 scenario",
    "Asumsi proyeksi laporan keuangan": "Financial statement projection assumptions",
    "Biaya operasi historis per setengah tahun": "Historical operating costs by half-year",
    "Biaya unit historis dan pelunasan utang Q3": "Historical unit costs and Q3 debt repayment",
    "Bukti lanjutan untuk menguji target harga": "Further evidence to test the Target Price",
    "Cadangan dan sumber daya mineral": "Mineral reserves and resources",
    "Capex historis, aktual H1, dan skenario FY26": "Historical capex, H1 actual and FY26 scenario",
    "Cross-check nilai per saham dengan multiple peer": "Per-share value cross-check on peer multiples",
    "Dasar tiap tahun FY26F-FY30F: skenario interim dan jadwal LoM":
        "Basis of each year FY26F-FY30F: interim scenario and LoM schedule",
    "Driver material dan dampaknya ke nilai": "Material drivers and their effect on value",
    "FY26 dari hasil interim dan jadwal LoM": "FY26 from interim results and the LoM schedule",
    "Grup peer: alasan pemilihan": "Peer Group: selection rationale",
    "Harga komoditas utama emiten": "Issuer's key commodity prices",
    "Hasil interim resmi dan perubahan yoy": "Official interim results and yoy change",
    "Jadwal LoM per fase": "LoM schedule by phase",
    "Jembatan korporat SOTP yang terverifikasi, masih parsial":
        "Verified SOTP corporate bridge, still partial",
    "Jembatan pendapatan menurut layanan dan pelanggan": "Revenue bridge by service and customer",
    "Jembatan unit cash cost per pon Cu terjual": "Unit cash cost bridge per lb of Cu sold",
    "Kasus dasar, turun dan naik dari model yang sama": "Base, downside and upside cases from one model",
    "Katalis, risiko, dan indikator pemantauan": "Catalysts, risks and monitoring indicators",
    "Kerangka royalti dan bea keluar; netback belum dapat dihitung":
        "Royalty and export-duty framework; netback not yet computable",
    "Komponen Cost of Equity": "Cost of Equity components",
    "Komponen WACC": "WACC components",
    "Komponen WACC US$ untuk NAV aset tambang": "US$ WACC components for mine-asset NAV",
    "Konstruksi dalam pengerjaan: biaya tercatat dan rentang selesai":
        "Construction in progress: book cost and completion range",
    "Kinerja historis": "Historical performance",
    "Kualitas bisnis": "Business quality",
    "Laba rugi bank": "Bank income statement",
    "Laba rugi": "Income statement",
    "Likuiditas dan investabilitas": "Liquidity and investability",
    "Metrik operasi dan pemrosesan": "Operating and processing metrics",
    "Model driver bank FY26F: aktual 1H26 dan H2 model":
        "Bank driver model FY26F: 1H26 actual and modelled H2",
    "Neraca bank": "Bank balance sheet",
    "Neraca": "Balance sheet",
    "Nilai terminal dan jembatan EV ke ekuitas": "Terminal value and EV-to-equity bridge",
    "Nilai terminal dan nilai wajar per saham": "Terminal value and value per share",
    "Parameter tingkat diskonto: kebijakan vs pembanding": "Discount-rate parameters: policy vs benchmarks",
    "Pemegang saham utama": "Major shareholders",
    "Pemeriksaan sebelum rating dan target harga": "Checks before Rating and Target Price",
    "Posisi neraca interim": "Interim balance sheet",
    "Proyeksi FCFF dan nilai kini": "FCFF projection and present value",
    "Proyeksi dividen dan nilai kini": "Dividend projection and present value",
    "Rantai metode valuasi": "Valuation Method Chain",
    "Rasio utama": "Key ratios",
    "Rasio yang menjelaskan kualitas hasil": "Ratios that explain earnings quality",
    "Referensi regional": "Regional references",
    "konteks, bukan peer valuasi": "context, not valuation peers",
    "Rekonsiliasi target ke asumsi pasar dan konsensus":
        "Target reconciliation to market-implied assumptions and consensus",
    "Ringkasan keputusan": "Decision summary",
    "SOTP holding: anak usaha tercatat pada nilai pasar": "Holding SOTP: listed subsidiaries at market value",
    "SOTP/LoM: nilai aset ke ekuitas": "SOTP/LoM: asset value to equity",
    "Sensitivitas SOTP/LoM: tingkat diskonto x dek harga": "SOTP/LoM sensitivity: discount rate x price deck",
    "Sensitivitas nilai DCF: WACC x pertumbuhan terminal": "DCF value sensitivity: WACC x terminal growth",
    "Sensitivitas nilai DDM: CoE x pertumbuhan terminal": "DDM value sensitivity: CoE x terminal growth",
    "Sensitivitas tambahan nilai landbank per saham: laju penjualan x pertumbuhan harga":
        "Landbank value added per share: sales rate x price growth",
    "Silang cek: PER peer x EPS FY26F": "Cross-check: peer PER x FY26F EPS",
    "Skala dan lingkup Elang pada tahap pengumuman AMDAL": "Elang scale and scope at the AMDAL announcement",
    "Skenario FY26 berbasis hasil interim dan asumsi analis":
        "FY26 scenario from interim results and Analyst Assumptions",
    "Skenario laba FY26F: aktual 1H dan asumsi H2": "FY26F earnings scenario: 1H actual and H2 assumptions",
    "Target harga Sektoral dan konsensus analis": "Sektoral Target Price and analyst consensus",
    "Target harga: EV/EBITDA peer x EBITDA FY26F": "Target Price: peer EV/EBITDA x FY26F EBITDA",
    "Uji tambahan SOTP/LoM": "Additional SOTP/LoM tests",
    "Valuasi per tahun": "Valuation by year",
    "Nilai tercatat persediaan dan stockpiles": "Book value of inventories and stockpiles",
    "Penjualan H1 menurut produk dan pasar": "H1 sales by product and market",
    # Chart series and panel titles.
    "DER dan ROE": "DER and ROE",
    "EBITDA dan margin": "EBITDA and margin",
    "Ekuitas dan ROE": "Equity and ROE",
    "Laba bersih dan pertumbuhan EPS": "Net profit and EPS growth",
    "NIM dan biaya kredit": "NIM and cost of credit",
    "Pendapatan dan pertumbuhan": "Revenue and growth",
    "Produksi tembaga dan biaya unit C1": "Copper production and C1 unit cost",
    "Produksi tembaga": "Copper production",
    "pertumbuhan": "growth",
    "pertumbuhan EPS": "EPS growth",
    "biaya kredit": "cost of credit",
    "margin": "margin",
    # Column headers.
    "% selesai": "% complete",
    "rentang": "range",
    "1H aktual": "1H actual",
    "Akumulasi biaya": "Accumulated cost",
    "Alasan": "Rationale",
    "Ambang perubahan tesis": "Thesis-change threshold",
    "Angka / rencana yang diumumkan": "Announced figure / plan",
    "Arah": "Direction",
    "Aset": "Asset",
    "Asumsi": "Assumption",
    "Asumsi analis": "Analyst Assumption",
    "Asumsi dan sumbernya": "Assumption and source",
    "Basis": "Basis",
    "Basis dan batas bukti": "Basis and evidence limits",
    "Batas interpretasi": "Limits of interpretation",
    "Belanja modal": "Capex",
    "Biaya kredit": "Cost of credit",
    "Bukti terkini": "Latest evidence",
    "Bukti yang diperlukan": "Evidence required",
    "Bursa": "Exchange",
    "Cu konsentrat": "Cu concentrate",
    "Dampak ke model": "Model impact",
    "Dasar": "Base",
    "Dasar dan batasan": "Basis and limits",
    "Dek dasar": "Base deck",
    "Dimensi": "Dimension",
    "Driver dan jalur dampak": "Driver and transmission",
    "Driver model": "Model driver",
    "EV/EBITDA peer": "Peer EV/EBITDA",
    "Emas": "Gold",
    "Emas murni": "Refined gold",
    "Emiten": "Issuer",
    "Estimasi penyelesaian": "Estimated completion",
    "Fase": "Phase",
    "Guidance awal": "Initial guidance",
    "H2 asumsi": "H2 assumption",
    "H2 model": "Modelled H2",
    "H2 tersirat": "Implied H2",
    "Harga cadangan JORC": "JORC reserve price",
    "Implikasi yang diuji": "Implication tested",
    "Implisit mean / median": "Implied at mean / median",
    "Jadwal LoM": "LoM schedule",
    "Jawaban dari model": "Model answer",
    "Jenis produk / aktual": "Product / actual",
    "Kap. pasar": "Mkt cap",
    "Kap. Pasar": "Market cap",
    "Kasus": "Case",
    "Katalis / risiko": "Catalyst / risk",
    "Kategori": "Category",
    "Kategori aset": "Asset category",
    "Katoda": "Cathode",
    "Kebijakan": "Policy",
    "Kelipatan": "Multiple",
    "Kepemilikan": "Ownership",
    "Keputusan": "Decision",
    "Keterangan": "Note",
    "Kini": "Current",
    "persentil": "percentile",
    "Komponen": "Component",
    "US$/lb Cu terjual": "US$/lb Cu sold",
    "Kredit efektif": "Loan growth (effective)",
    "Kredit input": "Loan growth (input)",
    "Kredit tumbuh": "Loan growth",
    "Laba induk": "Parent net profit",
    "Laba induk FY1": "FY1 parent net profit",
    "Laju penjualan": "Sales rate",
    "Langkah": "Step",
    "kumulatif": "cumulative",
    "Liabilitas/ekuitas": "Liabilities/equity",
    "Margin bersih": "Net margin",
    "Metode": "Method",
    "Metrik": "Metric",
    "Nilai": "Value",
    "Nilai / status": "Value / status",
    "Nilai dasar": "Base value",
    "Nilai per saham": "Value per share",
    "Nilai/saham": "Value/share",
    "P/B sub-sektor": "Sub-sector P/B",
    "P/E sub-sektor": "Sub-sector P/E",
    "PER peer": "Peer PER",
    "Panduan": "Guidance",
    "Pembanding": "Benchmark",
    "Pemegang saham": "Shareholder",
    "Pemeriksaan": "Check",
    "Pendapatan": "Revenue",
    "Penilaian": "Assessment",
    "Periode": "Period",
    "Periode laba": "Earnings period",
    "Perkiraan atau status yang diumumkan": "Announced estimate or status",
    "Pertanyaan": "Question",
    "Pertumbuhan laba": "Earnings growth",
    "Pertumbuhan pendapatan": "Revenue growth",
    "Perubahan": "Change",
    "Perubahan driver": "Driver change",
    "Perusahaan": "Company",
    "Produk": "Product",
    "Rasio": "Ratio",
    "Rentang uji": "Test range",
    "Satuan / basis": "Unit / basis",
    "Skenario": "Scenario",
    "Sumber": "Source",
    "Sumber, tanggal": "Source, date",
    "Tahun": "Year",
    "Tahun buku 31 Des": "FY to 31 Dec",
    "Tarif atau jumlah": "Rate or amount",
    "Tema": "Theme",
    "Tembaga": "Copper",
    "Tercapai": "Achieved",
    "Terhadap harga": "Vs price",
    "Tingkat diskonto": "Discount rate",
    "Tingkat diskonto USD": "USD discount rate",
    "Tonggak / pekerjaan": "Milestone / work",
    "Tumbuh": "Growth",
    "Ukuran": "Measure",
    "Umpan": "Feed",
    "Uraian": "Item",
    "Waktu": "Timing",
    "Waktu dan bukti": "Timing and evidence",
    "Δ laba induk FY1 (Rp miliar) turun / naik": "Δ FY1 parent net profit (Rp bn) down / up",
    "Δ nilai per saham turun / naik": "Δ value per share down / up",
    # Income statement, balance sheet and cash flow.
    "Beban bunga": "Interest expense",
    "Beban operasional": "Operating expenses",
    "Beban pokok pendapatan": "Cost of revenue",
    "Beban usaha": "Operating expenses",
    "Depresiasi": "Depreciation",
    "Depresiasi dan amortisasi": "Depreciation and amortisation",
    "EBITDA": "EBITDA",
    "Laba bersih": "Net profit",
    "Laba bersih konsolidasi": "Consolidated net profit",
    "Laba kotor": "Gross profit",
    "Laba operasional": "Operating profit",
    "Laba pemilik induk": "Net profit to parent",
    "Laba sebelum pajak": "Profit before tax",
    "Laba sebelum provisi": "Pre-provision operating profit",
    "Laba usaha": "Operating profit",
    "Pajak penghasilan": "Income tax",
    "Pendapatan (beban) lain-lain": "Other income (expense)",
    "Pendapatan (beban) non-operasional": "Non-operating income (expense)",
    "Pendapatan bunga": "Interest income",
    "Pendapatan bunga bersih": "Net interest income",
    "Pendapatan non-bunga": "Non-interest income",
    "Pendapatan non-bunga / NII": "Non-interest income / NII",
    "Kepentingan non-pengendali": "Non-controlling interests",
    "Kepentingan nonpengendali": "Non-controlling interests",
    "Aset lancar lainnya": "Other current assets",
    "Aset tetap bersih": "Net fixed assets",
    "Aset tidak lancar lainnya": "Other non-current assets",
    "Kas": "Cash",
    "Kas dan setara kas": "Cash and equivalents",
    "Persediaan": "Inventories",
    "Piutang usaha": "Trade receivables",
    "Total aset": "Total assets",
    "Total aset lancar": "Total current assets",
    "Total aset produktif": "Total earning assets",
    "Total ekuitas": "Total equity",
    "Total liabilitas": "Total liabilities",
    "Total liabilitas dan ekuitas": "Total liabilities and equity",
    "Total liabilitas lancar": "Total current liabilities",
    "Liabilitas lancar lainnya": "Other current liabilities",
    "Liabilitas tidak lancar lainnya": "Other non-current liabilities",
    "Liabilitas berbunga lain": "Other interest-bearing liabilities",
    "Liabilitas tanpa bunga": "Non-interest-bearing liabilities",
    "Utang jangka panjang": "Long-term debt",
    "Utang jangka pendek": "Short-term debt",
    "Utang usaha": "Trade payables",
    "Utang finansial": "Financial debt",
    "Utang": "Debt",
    "Pinjaman berbunga": "Interest-bearing borrowings",
    "Uang muka pelanggan": "Customer advances",
    "Arus kas operasi": "Operating cash flow",
    "Arus kas investasi": "Investing cash flow",
    "Arus kas pendanaan": "Financing cash flow",
    "Jumlah arus kas operasi": "Net operating cash flow",
    "Jumlah arus kas investasi": "Net investing cash flow",
    "Jumlah arus kas pendanaan": "Net financing cash flow",
    "Arus kas bebas (operasi - capex, memo)": "Free cash flow (operating - capex, memo)",
    "Dividen dibayar": "Dividends paid",
    "Kas akhir": "Closing cash",
    "Kas awal": "Opening cash",
    "Saldo kas": "Cash balance",
    "Perubahan kas bersih": "Net change in cash",
    "Perubahan modal kerja": "Change in working capital",
    "Penarikan (pembayaran) utang": "Debt drawdown (repayment)",
    "Penerbitan (pembelian kembali) saham": "Share issuance (buyback)",
    "Pos investasi lainnya": "Other investing items",
    "Pos operasi lainnya": "Other operating items",
    "Pos pendanaan lainnya": "Other financing items",
    "Efek kurs dan selisih definisi kas (data sumber)": "FX effect and cash-definition difference (source data)",
    "Termasuk pinjaman penyeimbang kas (memo)": "Incl. cash-balancing borrowing (memo)",
    "Hasil interim resmi": "Official interim results",
    "Forecast operasi": "Operating forecast",
    "Forecast fisik": "Physical forecast",
    # Growth, margins and ratios.
    "Pertumbuhan": "Growth",
    "Profitabilitas": "Profitability",
    "Leverage": "Leverage",
    "Likuiditas, profitabilitas dan permodalan": "Liquidity, profitability and capital",
    "Efisiensi dan kualitas aset": "Efficiency and asset quality",
    "Dividen dan nilai buku": "Dividends and book value",
    "Margin EBITDA": "EBITDA margin",
    "Marjin EBITDA": "EBITDA margin",
    "Margin laba bersih": "Net profit margin",
    "Marjin laba bersih": "Net profit margin",
    "Marjin laba kotor": "Gross margin",
    "Marjin usaha": "Operating margin",
    "Pertumbuhan EBITDA": "EBITDA growth",
    "Pertumbuhan EPS": "EPS growth",
    "Pertumbuhan BVPS": "BVPS growth",
    "Pertumbuhan DPS": "DPS growth",
    "Pertumbuhan FCFF": "FCFF growth",
    "Pertumbuhan kredit": "Loan growth",
    "Pertumbuhan harga": "Price growth",
    "Pertumbuhan terminal g": "Terminal growth g",
    "Cakupan bunga (EBIT / beban bunga)": "Interest cover (EBIT / interest expense)",
    "Net gearing (utang bersih / ekuitas)": "Net gearing (net debt / equity)",
    "Tarif pajak efektif": "Effective tax rate",
    "Payout ratio": "Payout ratio",
    "Rasio pembayaran dividen": "Dividend payout ratio",
    "Dividend yield pada harga": "Dividend yield at price",
    "PER pada harga": "PER at price",
    "PER pada target": "PER at target",
    "PBV pada harga": "PBV at price",
    "PBV pada target": "PBV at target",
    "EV/EBITDA pada harga": "EV/EBITDA at price",
    "Belanja modal / pendapatan": "Capex / revenue",
    "Arus kas operasi / EBITDA": "Operating cash flow / EBITDA",
    # Bank.
    "Biaya dana": "Cost of funds",
    "Cadangan kerugian kredit": "Loan loss reserves",
    "Cakupan cadangan terhadap NPL": "NPL coverage",
    "Dana pihak ketiga": "Third-party funds",
    "Deposito": "Time deposits",
    "Giro": "Current accounts",
    "Tabungan": "Savings accounts",
    "Imbal hasil aset produktif": "Earning-asset yield",
    "Kredit bersih": "Net loans",
    "Kredit bruto": "Gross loans",
    "Kredit terhadap simpanan (LDR)": "Loan-to-deposit ratio (LDR)",
    "Marjin bunga bersih (NIM)": "Net interest margin (NIM)",
    "Obligasi pemerintah": "Government bonds",
    "Provisi": "Provisions",
    "Provisi dan cadangan": "Provisions and reserves",
    "Rasio CASA": "CASA ratio",
    "Rasio biaya / pendapatan": "Cost-to-income ratio",
    "Rasio biaya terhadap pendapatan": "Cost-to-income ratio",
    "Rasio kecukupan modal (CAR)": "Capital adequacy ratio (CAR)",
    "Rasio kredit bermasalah bruto (NPL)": "Gross NPL ratio",
    "Selisih bunga (spread)": "Interest spread",
    "Surat berharga": "Securities",
    "Aset non-produktif (kas, aset tetap, lain)": "Non-earning assets (cash, fixed assets, other)",
    "Pendapatan bunga (%)": "Interest income (%)",
    # Valuation.
    "Beta": "Beta",
    "Bobot ekuitas (nilai pasar)": "Equity weight (market value)",
    "Bobot utang (nilai pasar)": "Debt weight (market value)",
    "Cost of debt sebelum pajak": "Pre-tax cost of debt",
    "Cost of debt setelah pajak": "After-tax cost of debt",
    "Country risk premium Indonesia": "Indonesia country risk premium",
    "Equity risk premium": "Equity risk premium",
    "mature market": "mature market",
    "tanpa CRP terpisah": "no separate CRP",
    "kebijakan analis": "analyst policy",
    "parameter kebijakan analis": "analyst policy parameter",
    "Cost of Equity dipakai": "Cost of Equity applied",
    "Enterprise value": "Enterprise value",
    "Faktor diskonto terminal": "Terminal discount factor",
    "Faktor diskonto": "Discount factor",
    "Jumlah PV FCFF": "Sum of PV of FCFF",
    "Jumlah PV DPS eksplisit": "Sum of PV of explicit DPS",
    "Kenaikan modal kerja": "Increase in working capital",
    "Minoritas": "Minorities",
    "Nilai ekuitas": "Equity value",
    "Nilai ekuitas pemilik induk": "Equity value to parent",
    "Nilai terminal": "Terminal value",
    "tidak didiskonto": "undiscounted",
    "Nilai wajar per saham": "Value per share",
    "PV nilai terminal": "PV of terminal value",
    "PV overhead korporat": "PV of corporate overhead",
    "Porsi periode sesudah tanggal valuasi": "Share of period after valuation date",
    "Porsi terminal terhadap nilai": "Terminal share of value",
    "Saham beredar": "Shares outstanding",
    "Saham beredar sesudah treasuri": "Shares outstanding net of treasury",
    "Saham beredar yang digunakan model": "Shares outstanding used in the model",
    "Saham diterbitkan": "Shares issued",
    "Saham Treasury": "Treasury shares",
    "Target harga Sektoral": "Sektoral Target Price",
    "Target harga metode utama": "Primary Method Target Price",
    "Target Sektoral terhadap rata-rata konsensus": "Sektoral target vs consensus average",
    "Upside rata-rata konsensus terhadap harga": "Consensus average upside to price",
    "Rentang target konsensus": "Consensus target range",
    "Rekomendasi (beli / tahan / jual)": "Recommendations (buy / hold / sell)",
    "Sumber konsensus": "Consensus source",
    "Estimasi konsensus pendapatan, EBITDA, laba": "Consensus revenue, EBITDA and earnings estimates",
    "Konsensus analis": "Analyst consensus",
    "Keputusan rilis": "Release decision",
    "Rantai metode": "Method Chain",
    "Valuasi": "Valuation",
    "Jendela observasi": "Observation window",
    "Offset dari mean": "Offset from mean",
    "Kuartil atas": "Upper quartile",
    "Kuartil bawah": "Lower quartile",
    "Median peer (tanpa emiten)": "Peer median (excl. issuer)",
    "Rata-rata peer (tanpa emiten)": "Peer average (excl. issuer)",
    "Median referensi regional": "Regional reference median",
    "Waktu terima (tahun)": "Time to receipt (years)",
    "Titik data terakhir": "Latest data point",
    "Harga terakhir": "Last price",
    "Perubahan 12 bulan": "12M change",
    "Kapitalisasi pasar": "Market cap",
    "Perubahan kapitalisasi pasar 1 tahun": "1-year market cap change",
    "Driver H2": "H2 driver",
    "Ilustrasi posisi Rp10 miliar": "Illustrative Rp10bn position",
    "Ilustrasi posisi Rp50 miliar": "Illustrative Rp50bn position",
    "Ilustrasi posisi Rp100 miliar": "Illustrative Rp100bn position",
    "Nilai transaksi harian median / rata-rata": "Median / average daily value traded",
    "Sesi tanpa volume": "Sessions without volume",
    "Arus bersih asing, 20 sesi terakhir": "Net foreign flow, last 20 sessions",
    "Arus bersih asing, seluruh jendela data": "Net foreign flow, full data window",
    "Sesi berturut-turut dengan arah asing yang sama": "Consecutive sessions of same foreign direction",
    "Free float": "Free float",
    "Papan pencatatan": "Listing board",
    "Status perdagangan": "Trading status",
    "Public": "Public",
    "Masyarakat": "Public",
    # Business quality.
    "Alokasi modal manajemen": "Management capital allocation",
    "Daya penetapan harga": "Pricing power",
    "Eksposur pihak berelasi": "Related-party exposure",
    "Kepemilikan dan pengendalian": "Ownership and control",
    "Konsentrasi pelanggan dan pemasok": "Customer and supplier concentration",
    "Posisi kompetitif": "Competitive position",
    "Siklikalitas": "Cyclicality",
    "Tata kelola": "Governance",
    # Decision summary.
    "Ekspektasi model": "Model expectation",
    "Katalis berikutnya": "Next catalyst",
    "Status dan batas": "Status and limits",
    "Yang berubah": "What changed",
    "Yang disiratkan harga": "What the price implies",
    "Yang harus terjadi": "What must happen",
    "Yang membuktikan salah": "What would prove it wrong",
    # Mining.
    "Cadangan": "Reserves",
    "Sumber daya": "Resources",
    "Kadar emas (g/t)": "Gold grade (g/t)",
    "Kadar tembaga (%)": "Copper grade (%)",
    "Katoda tembaga": "Copper cathode",
    "Katoda tembaga terjual": "Copper cathode sold",
    "Konsentrat diproduksi": "Concentrate produced",
    "Konsentrat terjual": "Concentrate sold",
    "Emas dalam konsentrat": "Gold in concentrate",
    "Emas murni terjual": "Refined gold sold",
    "Tembaga dalam konsentrat": "Copper in concentrate",
    "Ekspor konsentrat": "Concentrate exports",
    "Biaya penambangan": "Mining cost",
    "Biaya pengolahan": "Processing cost",
    "Biaya smelting dan refining": "Smelting and refining cost",
    "Kredit produk sampingan": "By-product credit",
    "Unit cash cost dilaporkan": "Reported unit cash cost",
    "Margin kas": "Cash margin",
    "Royalti": "Royalty",
    "Harga emas": "Gold price",
    "Harga tembaga": "Copper price",
    "Rehandle stockpile": "Stockpile rehandling",
    "Jumlah NAV aset": "Sum of asset NAV",
    "Total nilai SOTP": "Total SOTP value",
    "Nilai buku tanah": "Land book value",
    "Diskon terhadap RNAV": "Discount to RNAV",
    # Short cell values.
    "dipakai": "used",
    "dikeluarkan": "excluded",
    "Positif": "Positive",
    "Negatif": "Negative",
    "Dua arah": "Two-way",
    "Naik": "Up",
    "Turun": "Down",
    "Terpilih": "Selected",
    "Terpilih, ekstrem (rantai berhenti)": "Selected, extreme (chain stops)",
    "Dilewati": "Skipped",
    "Silang cek": "Cross-check",
    "Tidak dijalankan": "Not run",
    "Belum tersedia": "Not yet available",
    "ditahan": "withheld",
    "belum dimodelkan": "not modelled",
    "tidak tersedia": "not available",
    "aktual resmi": "official actual",
    "asumsi analis": "Analyst Assumption",
    "Asumsi analis; bukan panduan emiten.": "Analyst Assumption; not issuer guidance.",
    "Asumsi analis; bukan guidance emiten": "Analyst Assumption; not issuer guidance",
    "asumsi analis / bersumber": "Analyst Assumption / sourced",
    "asumsi analis / panduan emiten": "Analyst Assumption / issuer guidance",
    "baris di atas": "row above",
    "1H aktual + H2 asumsi": "1H actual + H2 assumption",
    "sama dengan nilai kebijakan": "same as policy value",
    "Yahoo Finance (UST 10Y), tanggal laporan": "Yahoo Finance (UST 10Y), Report Date",
    "n.a. (tanpa histori CoE di data Sectors)": "n.a. (no CoE history in Sectors data)",
    "n.a.: dipakai hasil CAPM": "n.a.: CAPM result used",
    "peer PER valid kurang dari tiga": "fewer than three valid peer PERs",
    "peer P/BV valid kurang dari tiga": "fewer than three valid peer P/BVs",
    "forecast driver bersumber belum lengkap": "sourced driver forecast incomplete",
    "nilai buku": "book value",
    "driver dasar": "base driver",
    "Dilaporkan": "Reported",
    "sensitivitas": "sensitivity",
    "Rugi.": "Loss.",
    "tidak": "no",
    "ya": "yes",
    "Ya": "Yes",
    "Tidak": "No",
    "lolos": "pass",
    "gagal": "fail",
    "input lengkap": "inputs complete",
    "beli": "buy",
    "jual": "sell",
    "Pajak atas EBIT": "Tax on EBIT",
    "Bobot utang": "Debt weight",
    "Bobot ekuitas": "Equity weight",
    "Silang cek: EV exit": "Cross-check: exit EV",
    "silang cek": "cross-check",
    "CoE mean 5 tahun": "5-year mean CoE",
    "CoE SD 5 tahun": "5-year CoE SD",
    "Ekuitas per saham": "Equity per share",
    "Nilai Inverse CoE per saham": "Inverse CoE value per share",
    "Nilai terminal = DPS terminal / (CoE - g)": "Terminal value = terminal DPS / (CoE - g)",
    "provisi / rata-rata kredit": "provisions / average loans",
    "Pendapatan 2H": "2H revenue",
    "Belanja modal 2H": "2H capex",
    "Margin laba 2H": "2H profit margin",
    "Margin EBITDA 2H": "2H EBITDA margin",
    "Utang bersih dan capex": "Net debt and capex",
    "Volume dan kadar tambang": "Mine volume and grade",
    "Main (profil emiten data Sectors)": "Main (Sectors issuer profile)",
    "Porsi kepemilikan emiten atas aset": "Issuer's ownership of the asset",
    "judgment analis": "analyst judgement",
    # Parenthetical qualifiers.
    "utama": "primary",
    "emiten": "issuer",
    "basis": "base",
    "base": "base",
    "override analis": "analyst override",
    "tanpa emiten": "excl. issuer",
    "median": "median",
    "memo": "memo",
}
TERMS.update(valtables.LABELS_EN)

# The mining audit appendix (app.narrative's FY26 H2 reconstruction, moved out
# of the printed report by report_extras.slim_mining): the web trace page shows it.
# A label the report already translates keeps its English.
_AUDIT_APPENDIX = {
    # Column headings.
    "Batasan": "Limits", "Domestik": "Domestic", "Ekspor": "Export", "Selisih": "Difference",
    "Pos": "Item", "Produk/tahap": "Product/stage", "Produksi H1": "H1 production",
    "Penjualan H1": "H1 sales", "Produksi dikurangi penjualan": "Production less sales",
    "Q2 terjual": "Q2 sold", "Revenue / metrik": "Revenue / metric",
    "Revenue per unit, proxy": "Revenue per unit, proxy", "H1 terjual": "H1 sold",
    "H1 revenue": "H1 revenue", "Basis harga H2": "H2 price basis",
    "H2 produksi tersirat": "Implied H2 production", "H2 penjualan skenario": "Scenario H2 sales",
    "H2 terjual / output": "H2 sold / output", "Net realized price H1": "H1 net realized price",
    "H2 terjual skenario": "Scenario H2 sold", "H2 revenue": "H2 revenue",
    "Net realized H1 / nilai efektif": "H1 net realized / effective value",
    "Benchmark pasar terbaru": "Latest market benchmark",
    "Basis harga skenario H2": "Scenario H2 price basis",
    "Sisa H2 tersirat": "Implied H2 remainder",
    "Basis / batas interpretasi": "Basis / limits of interpretation",
    "Produksi Q2": "Q2 production", "Terjual Q2": "Q2 sold", "Q2 turunan": "Derived Q2",
    "Pengungkapan interim": "Interim disclosure", "Saldo keuangan": "Financial balance",
    "Fakta resmi": "Official facts", "Arus kas pendanaan H1 2026": "H1 2026 financing cash flow",
    "Basis / batas rekonsiliasi": "Basis / limits of reconciliation",
    "H1 terjual aktual": "H1 actual sold", "H2 output tersirat": "Implied H2 output",
    "H2 sales skenario": "Scenario H2 sales", "Volume × harga terealisasi H1":
        "Volume × H1 realized price", "Revenue hitungan": "Calculated revenue",
    "Revenue segmen dilaporkan": "Reported segment revenue",
    "FY26 balance vs H1": "FY26 balance vs H1", "½ kapasitas desain": "½ design capacity",
    "Utilisasi H2 tersirat": "Implied H2 utilisation", "Dampak pada forecast": "Effect on the forecast",
    "Klasifikasi dan batas data": "Classification and data limits",
    "Makna untuk forecast": "Meaning for the forecast",
    "H2 revenue pada basis harga H2": "H2 revenue on the H2 price basis",
    "H2 terjual untuk rekonsiliasi": "H2 sold for reconciliation",
    "US$ juta, kecuali per saham": "US$ mn, except per share",
    # Row labels.
    "Net sales": "Net sales", "Penjualan bersih": "Net sales", "Laba operasi": "Operating profit",
    "Beban keuangan": "Finance costs", "Beban pokok penjualan": "Cost of sales",
    "Lainnya": "Other", "Konsentrat": "Concentrate", "Pendapatan": "Revenue",
    "Laba bersih": "Net profit", "Arus kas operasi": "Operating cash flow",
    "Arus kas pendanaan": "Financing cash flow", "Depresiasi dan amortisasi":
        "Depreciation and amortisation", "Saham beredar": "Shares outstanding",
    "Nilai": "Value", "Nilai skenario (Rp/saham)": "Scenario value (Rp/share)",
    "Ekuitas induk setelah utang dan minoritas": "Parent equity after debt and minorities",
    "EBITDA FY26 skenario": "Scenario FY26 EBITDA", "Utang bersih 1H": "1H net debt",
    "Tembaga terkandung dalam konsentrat": "Copper contained in concentrate",
    "Emas terkandung dalam konsentrat": "Gold contained in concentrate",
    "Tembaga dalam konsentrat": "Copper in concentrate", "Emas dalam konsentrat": "Gold in concentrate",
    "Cu terkandung dalam konsentrat": "Cu contained in concentrate",
    "Au terkandung dalam konsentrat": "Au contained in concentrate",
    "Subtotal pada basis harga H2": "Subtotal on the H2 price basis",
    "Selisih yang belum dijelaskan": "Unexplained difference", "Gap belum dijelaskan":
        "Unexplained gap", "Selisih yang tidak dijembatani catatan": "Difference the notes do not bridge",
    "Skenario pendapatan H2": "H2 revenue scenario",
    "Tembaga, benchmark LME": "Copper, LME benchmark", "Emas, benchmark LBMA": "Gold, LBMA benchmark",
    "Konsentrat, nilai penjualan efektif": "Concentrate, effective sales value",
    "sisa guidance FY dikurangi aktual H1": "FY guidance remainder less H1 actual",
    "Output katoda tembaga": "Copper cathode output",
    "Rasio output katoda / Cu terkandung": "Cathode output / contained Cu ratio",
    "diagnostik antar-tahap; bukan recovery metalurgi":
        "inter-stage diagnostic; not metallurgical recovery",
    "Output emas murni": "Refined gold output",
    "Rasio output emas murni / Au terkandung": "Refined gold output / contained Au ratio",
    "H1 laporan keuangan dikurangi Q1": "H1 financial statements less Q1",
    "H1 laporan arus kas dikurangi Q1": "H1 cash flow statement less Q1",
    "H1 laporan posisi keuangan; kas 30 Jun": "H1 statement of financial position; cash at 30 Jun",
    "Arus kas bebas indikatif": "Indicative free cash flow",
    "OCF + arus kas investasi; turunan analis": "OCF + investing cash flow; analyst-derived",
    "Kenaikan kas sebelum kurs": "Cash increase before FX", "Dampak kurs": "FX effect",
    "Kas akhir Q2": "Q2 closing cash", "Kas untuk investasi/capex": "Cash for investment/capex",
    "Harga provisional saat penjualan": "Provisional price at sale",
    "Sebelum settlement final": "Before final settlement", "Periode final pricing":
        "Final pricing period", "Risiko harga": "Price risk", "Assay dan kuantitas": "Assay and quantity",
    "Piutang usaha total": "Total trade receivables", "Piutang usaha FVPL": "FVPL trade receivables",
    "Piutang usaha amortized cost": "Amortised-cost trade receivables",
    "Aset derivatif": "Derivative assets", "Liabilitas derivatif": "Derivative liabilities",
    "Mining, processing, dan operasi": "Mining, processing and operations",
    "Amortisasi stripping tertunda": "Deferred stripping amortisation",
    "Royalti pemerintah": "Government royalty", "Bea ekspor": "Export duty",
    "Beban karyawan": "Employee costs", "Angkut dan pemasaran": "Freight and marketing",
    "Kredit produk perak": "Silver by-product credit",
    "Kredit produk selenium": "Selenium by-product credit",
    "Kredit produk asam sulfat": "Sulphuric acid by-product credit",
    "Mutasi stockpile dan persediaan produk": "Stockpile and product inventory movement",
    "Total beban pokok penjualan": "Total cost of sales", "HPP dilaporkan": "Reported cost of sales",
    "Pergerakan stockpile/persediaan di HPP": "Stockpile/inventory movement in cost of sales",
    "Laba kotor dilaporkan": "Reported gross profit",
    "HPP setelah membalik pergerakan tersebut": "Cost of sales with that movement reversed",
    "Laba kotor diagnostik setelah dibalik": "Diagnostic gross profit after the reversal",
    "Persediaan bersih": "Net inventories", "Gabungan nilai tercatat": "Combined carrying value",
    "Kredit pergerakan persediaan di HPP H1": "Inventory movement credit in H1 cost of sales",
    "Penerimaan pinjaman bank jangka pendek": "Short-term bank loan proceeds",
    "Pembayaran pinjaman bank jangka pendek": "Short-term bank loan repayments",
    "Penerimaan pinjaman bank jangka panjang": "Long-term bank loan proceeds",
    "Pembayaran pokok pinjaman bank jangka panjang": "Long-term bank loan principal repayments",
    "Arus kas bersih pinjaman bank (hasil hitung)": "Net bank loan cash flow (calculated)",
    "Arus kas perubahan kas dibatasi": "Restricted cash change cash flow",
    "Arus kas bersih aktivitas pendanaan": "Net cash flow from financing activities",
    "Headline presentasi: utang dibayar YTD": "Presentation headline: debt repaid YTD",
    "Pelunasan utang yang dilaporkan untuk Q3 2026": "Debt repayment reported for Q3 2026",
    "Total produk": "Total products", "Revenue dihitung dari volume × realized price":
        "Revenue calculated from volume × realized price",
    # Short notes in the cells.
    "Arus kas masuk aktual H1.": "Actual H1 cash inflow.",
    "Arus kas keluar aktual H1.": "Actual H1 cash outflow.",
    "Arus kas yang dilaporkan di bagian pendanaan.": "Cash flow reported under financing.",
    "Jumlah penerimaan dan pembayaran short- plus long-term.":
        "Sum of short- plus long-term proceeds and repayments.",
    "Nilai laporan; sama dengan arus pinjaman bersih plus perubahan kas dibatasi.":
        "Reported value; equals net loan flow plus the restricted cash change.",
    "Dilaporkan telah dibayar; saldo utang/kas setelah pembayaran belum dilaporkan.":
        "Reported as paid; the debt/cash balance after payment is not yet reported.",
    "Belum disesuaikan dengan arus kas dan capex 2H.": "Not yet adjusted for 2H cash flow and capex.",
    "Dikurangkan dari enterprise value setelah utang bersih.":
        "Deducted from enterprise value after net debt.",
    "Sesudah saham treasuri; dilusi berikutnya belum dimodelkan.":
        "After treasury shares; later dilution not yet modelled.",
    "Hasil 1H aktual + asumsi 2H; bukan forecast LoM.":
        "1H actual results + 2H assumptions; not a LoM forecast.",
    "H1 revenue/unit dipertahankan datar untuk skenario; benchmark spot hanya pembanding.":
        "H1 revenue/unit held flat for the scenario; the spot benchmark is a comparison only.",
    "Tidak sebanding dengan benchmark Cu/Au tanpa kadar payable dan TC-RC":
        "Not comparable with the Cu/Au benchmark without payable grades and TC-RC",
    "H1 revenue/dmt dipakai sebagai proxy datar; belum merupakan netback produk.":
        "H1 revenue/dmt used as a flat proxy; not yet a product netback.",
    "Konsentrat dan katoda awalnya dicatat 100% pada harga provisional; pengakuan revenue tetap "
    "mensyaratkan delivery/title transfer.":
        "Concentrate and cathode are first recorded at 100% of the provisional price; revenue "
        "recognition still requires delivery/title transfer.",
    "Harga/kuantitas provisional bisa disesuaikan saat assay dan informasi jumlah metal baru "
    "diterima.":
        "Provisional price/quantity can be adjusted when assays and new metal quantity "
        "information are received.",
    "Harga di-mark-to-market memakai forward price untuk estimasi bulan settlement; embedded "
    "derivative masuk laba rugi.":
        "Prices are marked to market at the forward price for the estimated settlement month; "
        "the embedded derivative goes through profit or loss.",
    "Mengikuti periode yang ditetapkan kontrak; periode per shipment/customer tidak diungkap "
    "dalam catatan ini.":
        "Follows the period set by the contract; the period per shipment/customer is not "
        "disclosed in this note.",
    "Seluruh produk/customer; tidak dipilah shipment.": "All products/customers; not split by shipment.",
    "Kebijakan akuntansi mengaitkan kategori ini dengan sebagian piutang provisional Cu/Au.":
        "The accounting policy links this category to part of the provisional Cu/Au receivables.",
    "Tidak dirinci menurut produk/customer.": "Not itemised by product/customer.",
    "Note 18 merinci IRS/CCS/POS; bukan saldo provisional metal terpisah.":
        "Note 18 itemises IRS/CCS/POS; not a separate provisional metal balance.",
    "Selisih Q1 ke H1; kedua angka sumber dibulatkan ke US$ juta":
        "Q1 to H1 difference; both source figures rounded to US$ mn",
}
TERMS.update({k: v for k, v in _AUDIT_APPENDIX.items() if k not in TERMS})

# Method Chain short names (app.method_chain.SHORT) and report method lines.
TERMS.update({
    "EV/Sales peer": "Peer EV/Sales", "P/S peer": "Peer P/S", "P/BV relatif": "Relative P/BV",
    "DCF referensi": "Reference DCF", "PER relatif": "Relative PER",
    "P/BV-ROE FY skenario": "Scenario FY P/BV-ROE", "P/BV buku": "Book P/BV",
    "PER FY skenario": "Scenario FY PER",
    "Holding SOTP per anak usaha/aset": "Holding SOTP by subsidiary/asset",
})

# Templated labels: every group is itself translated with label().
_PATTERNS = [(re.compile(p), t) for p, t in (
    (r"Band (P/E|P/BV|EV/EBITDA|EV/Sales) 12 bulan (\S+)", "12M {0} band, {1}"),
    (r"Band historis 12 bulan (.+) \(bukan target harga\)", "12M historical {0} bands (not a Target Price)"),
    (r"(.+) dan (P/BV|EV/EBITDA|EV/Sales)", "{0} and {1}"),
    (r"(\S+) relatif terhadap IHSG", "{0} relative to the JCI"),
    (r"Target harga berbasis (.+)", "Target Price based on {0}"),
    (r"Kondisi grup peer (.+): peer dibanding (\S+)", "Peer Group conditions, {0}: peers vs {1}"),
    (r"Kondisi sub-sektor (.+): peer dibanding (\S+)", "Sub-sector conditions, {0}: peers vs {1}"),
    (r"Perbandingan peer (.+)", "Peer comparison: {0}"),
    (r"Valuasi dan pertumbuhan sub-sektor (.+)", "{0} sub-sector valuation and growth"),
    (r"Komposisi pendapatan (\S+)", "Revenue mix, {0}"),
    (r"Panduan produksi (\S+) dari manajemen", "Management production guidance, {0}"),
    (r"Realisasi (\S+) terhadap panduan (\S+)", "{0} delivery against {1} guidance"),
    (r"Rasio (\S+) dari jadwal LoM", "{0} ratios from the LoM schedule"),
    (r"RNAV landbank (.+): dasar perhitungan", "{0} landbank RNAV: calculation basis"),
    (r"Skenario laba (FY\S+)", "Earnings scenario {0}"),
    (r"Jadwal LoM (FY\S+)", "LoM schedule {0}"),
    (r"Peer \((\d+) emiten, tanpa (\S+)\)", "Peers ({0} issuers, excl. {1})"),
    (r"Peringkat (\S+)", "{0} rank"),
    (r"Segmen: (.+)", "Segment: {0}"),
    (r"Tersedia: (.+)", "Available: {0}"),
    (r"(\S+) aktual", "{0} actual"),
    (r"(\S+) produksi", "{0} production"),
    (r"(\S+) skenario", "{0} scenario"),
    (r"(\S+) tahunan", "{0} full year"),
    (r"(\S+) tersirat", "Implied {0}"),
    (r"Realisasi (\S+)", "{0} delivered"),
    (r"Guidance kini (\S+)", "Current {0} guidance"),
    (r"Dek (.+)", "Deck {0}"),
    (r"Harga (.+)/tahun", "Price {0}/yr"),
    (r"(.+) ha/tahun", "{0} ha/yr"),
    (r"Diskonto (.+)", "Discount rate {0}"),
    (r"tarif efektif (.+)", "effective rate {0}"),
    (r"Akumulasi biaya (.+)", "Accumulated cost {0}"),
    (r"FCFF terminal = FCFF (\S+) dengan capex >= D&A, x \(1 \+ g\)",
     "Terminal FCFF = {0} FCFF with capex >= D&A, x (1 + g)"),
    (r"Diskon RNAV (.+)", "RNAV discount {0}"),
    (r"Rata-rata (\d{4})", "{0} average"),
    (r"Rata-rata target konsensus", "Consensus target average"),
    (r"(\d+) analis", "{0} analysts"),
    (r"(\d+) analis, (\S+)", "{0} analysts, {1}"),
    (r"(\d+) sesi (beli|jual) bersih", "{0} net-{1} sessions"),
    (r"(\d+) bulan s\.d\. (\S+)", "{0}M to {1}"),
    (r"regresi Sektoral, harga IDX s\.d\. (\S+)", "Sektoral regression, IDX prices to {0}"),
    (r"dasar nilai (.+)\.", "value basis: {0}."),
    (r"Probabilitas pengembangan Elang(.*)", "Elang development probability{0}"),
    (r"Ke target (.+)", "To target {0}"),
    (r"Margin laba bersih (FY\S+)", "Net margin {0}"),
    (r"Pertumbuhan pendapatan (FY\S+) vs (\d{4})", "Revenue growth {0} vs {1}"),
    (r"Pendapatan skenario (FY\S+) vs (\d{4}) \(mata uang pelaporan\)",
     "Scenario revenue {0} vs {1} (reporting currency)"),
    (r"Faktor diskonto \((.+)\)", "Discount factor ({0})"),
    (r"Nilai per saham, diskon holding (.+)", "Value per share, {0} holding discount"),
    (r"CoE tersirat harga (\S+) \((\S+)\)", "CoE implied by price {0} ({1})"),
    # Report method lines (doc["method"]).
    (r"DCF FCFF model operasional (\S+) \+ terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
     "FCFF DCF on the Operating Model {0} + Gordon terminal; historical exit EV/EBITDA as cross-check"),
    (r"DCF FCFF skenario (\S+) \+ terminal Gordon; exit EV/EBITDA historis sebagai cross-check",
     "FCFF DCF on scenario {0} + Gordon terminal; historical exit EV/EBITDA as cross-check"),
    (r"DDM dividen skenario (\S+) \+ terminal Gordon \(CoE, bukan WACC\)",
     "DDM on scenario dividends {0} + Gordon terminal (CoE, not WACC)"),
    (r"(\S+) EV/EBITDA median peer x EBITDA skenario analis",
     "{0} peer median EV/EBITDA x Analyst Scenario EBITDA"),
    (r"SOTP/LoM: (.+) \(probabilitas (\S+)\) sampai (\d{4}), tanpa terminal perpetual",
     "SOTP/LoM: {0} ({1} probability) to {2}, no perpetual terminal value"),
    # Cover rating status.
    (r"Dalam peninjauan \(rating terakhir (\S+)\)", "Under review (last rating {0})"),
    # Mining audit appendix cells.
    (r"Kurs (\S+); harga saham Sectors (\S+) lebih lama\.",
     "FX rate {0}; the Sectors share price of {1} is older."),
    (r"Penurunan (\S+) dinilai tidak signifikan terhadap laba per (.+); tidak ada sensitivitas "
     r"dolar yang diberikan\.",
     "A {0} fall is judged not significant to profit as at {1}; no dollar sensitivity is given."),
)]
TERMS.update({"Inisiasi": "Initiation", "Dipertahankan": "Maintained", "Dalam peninjauan": "Under review",
              "Skenario informasional": "Informational scenario", "Analisis": "Analysis"})

# Risk categories, printed in lower case after a risk title.
TERMS.update({"komoditas": "commodity", "modal": "capital", "operasi": "operations",
              "pendanaan": "funding", "proyek": "project", "regulasi": "regulation",
              "tata kelola": "governance", "pasar": "market", "valuasi": "valuation"})

# Headings and exhibit titles of the prose pages (#33).
TERMS.update({
    "Persediaan, penjualan, dan batas rekonsiliasi": "Inventory, sales and reconciliation limits",
    "Produksi dan penjualan aktual H1 menurut tahap": "1H actual production and sales by stage",
    "Uji antar-tahap produksi H2": "2H production inter-stage test",
    "Rekonstruksi aktual Q2 2026": "Q2 2026 actuals reconstruction",
    "Saldo settlement provisional dan klasifikasi derivatif": "Provisional settlement balances and derivative classification",
    "Komposisi biaya aktual dan keterbatasan run-rate": "Actual cost composition and run-rate limits",
    "Persediaan, gross profit, dan batas rekonsiliasi": "Inventory, gross profit and reconciliation limits",
    "Baris kuartalan dalam data lokal": "Quarterly rows in local data",
    "Delta produksi dan penjualan produk H1": "1H product production and sales delta",
    "Uji antar-tahap logam H2: konsentrat ke produk refinery": "2H metal inter-stage test: concentrate to refinery products",
    "Rekonstruksi Q2 2026 (H1 dikurangi Q1)": "Q2 2026 reconstruction (1H less Q1)",
    "Rekonstruksi laba rugi dan arus kas Q2 2026": "Q2 2026 income statement and cash flow reconstruction",
    "Ketentuan provisional pricing dan settlement": "Provisional pricing and settlement terms",
    "Piutang provisional FVPL dan derivatif swap": "Provisional FVPL receivables and swap derivatives",
    "Rekonsiliasi komponen beban pokok penjualan Q2": "Q2 cost of goods sold reconciliation",
    "Dampak pergerakan persediaan pada laba kotor (diagnostik)": "Inventory movement effect on gross profit (diagnostic)",
    "Nilai tercatat persediaan bukan tonase konsentrat": "Inventory carrying value, not concentrate tonnage",
    "Batas bukti kontrak, beban bunga, dan capex": "Evidence limits: contracts, interest expense and capex",
    "Arus kas pinjaman dan pelunasan utang": "Borrowing cash flows and debt repayment",
    "Uji monetisasi produksi terhadap revenue H2": "Production monetisation test against 2H revenue",
    "Uji realized price terhadap revenue aktual H1": "Realized price test against 1H actual revenue",
    "Uji kapasitas terhadap sisa panduan produksi": "Capacity test against remaining production guidance",
    "Konteks historis dan kepemilikan": "Historical context and ownership",
    "Skenario operasi ilustratif": "Illustrative operating scenario",
    "Berita dan keputusan asumsi": "News and assumption decisions",
    "Valuasi ilustratif dan keterbatasannya": "Illustrative valuation and its limits",
    "Valuasi menunggu rekonsiliasi": "Valuation awaits reconciliation",
    "Kontrak cathode, utang, dan kewajiban kas yang diungkapkan": "Disclosed cathode contracts, debt and cash obligations",
    "Rekonsiliasi arus pinjaman dan pembayaran utang H1 2026": "1H 2026 borrowing and debt repayment reconciliation",
    "Uji revenue H2 dari volume produk dan realized price": "2H revenue test from product volumes and realized prices",
    "Rekonsiliasi realized price dengan revenue produk H1": "Realized price reconciliation with 1H product revenue",
    "Kapasitas fasilitas versus panduan produksi FY26": "Facility capacity versus FY26 production guidance",
    "Cross-check EV/EBITDA FY26 berbasis skenario interim": "FY26 EV/EBITDA cross-check on the interim scenario",
    "Input cross-check FY26 dan batasannya": "FY26 cross-check inputs and their limits",
    "Riwayat keuangan dalam data Sectors": "Financial history in Sectors data",
    "Neraca historis dalam data Sectors": "Historical balance sheet in Sectors data",
    "Screen proyeksi historis, bukan forecast produksi": "Historical projection screen, not a production forecast",
    "Asumsi yang membuat screen belum layak rilis": "Assumptions that keep the screen from release",
    "Berita sebagai asumsi skenario": "News as scenario assumptions",
    "Perbandingan nilai model lama, bukan target harga": "Prior model value comparison, not a Target Price",
    "Sensitivitas Gordon ilustratif (Rp/saham)": "Illustrative Gordon sensitivity (Rp/share)",
    "Sensitivitas DDM (CoE x g)": "DDM sensitivity (CoE x g)",
    "Sensitivitas Inverse CoE (CoE x ROE)": "Inverse CoE sensitivity (CoE x ROE)",
    "Valuasi dan batasan model": "Valuation and model limits",
    "Jembatan revenue H2 menurut produk": "2H revenue bridge by product",
    "Output dan penjualan H2": "2H output and sales",
    "Net realized price dan volume logam": "Net realized price and metal volumes",
    "Harga komoditas dan asumsi realisasi": "Commodity prices and realization assumptions",
    "Estimasi FY26 dan pembanding": "FY26 estimates and comparison",
    "Valuasi: hasil ekstrem ditahan": "Valuation: extreme result withheld",
    "Jembatan penjualan produk dan revenue H2 2026": "2H 2026 product sales and revenue bridge",
    "Q2 2026: angka turunan dari H1 dikurangi Q1": "Q2 2026: figures derived as 1H less Q1",
    "Output tersirat dan asumsi penjualan H2": "Implied output and 2H sales assumptions",
    "Volume penjualan dan net realized price per logam": "Sales volume and net realized price by metal",
    "Benchmark komoditas dan asumsi nilai realisasi": "Commodity benchmarks and realization assumptions",
    "Estimasi FY26 Sektoral dibanding BRIDS": "Sektoral FY26 estimates versus BRIDS",
    "Valuasi: rantai metode": "Valuation: Method Chain",
    "Sensitivitas harga komoditas dan kurs": "Commodity price and FX sensitivity",
    "Target harga ditahan": "Target Price withheld",
    "Status target harga": "Target Price status",
    "Target harga: P/B peer x nilai buku terlapor": "Target Price: peer P/B x reported book value",
    "Ringkasan riset berbantuan AI": "AI-assisted research summary",
    "Kinerja dan bukti yang tersedia": "Performance and available evidence",
    "Valuasi dan kelengkapan model": "Valuation and model completeness",
    "Konteks berita dan kaitannya ke tesis": "News context and its link to the thesis",
    "Screen historis untuk diskusi internal": "Historical screen for internal discussion",
    "Status riset": "Research status",
    "Basis model": "Model basis",
    "Laporan historis di data Sectors": "Historical statements in Sectors data",
    "Kinerja kuartalan yang tersedia di data Sectors": "Quarterly performance available in Sectors data",
    "Screen historis (bukan forecast produksi)": "Historical screen (not a production forecast)",
    "Konteks berita dari Sectors dan implikasi": "News context from Sectors and implications",
    "Kelengkapan sebelum rilis": "Completeness before release",
    "Input SOTP yang belum lengkap": "Incomplete SOTP inputs",
    "Hasil terakhir jadi basis forecast": "Latest results anchor the forecast",
    "Volume dan leverage jadi mesin laba": "Volume and leverage drive earnings",
    "Skenario nilai indikatif": "Indicative value scenario",
    "Industri dan makro: permintaan ke depan": "Industry and macro: demand ahead",
    "Asumsi forecast dan sensitivitas": "Forecast assumptions and sensitivity",
    "Katalis, risiko, kepemilikan": "Catalysts, risks, ownership",
    "Laporan keuangan": "Financial statements",
    "Neraca dan arus kas historis": "Historical balance sheet and cash flow",
    "Operasional tambang": "Mine operations",
    "Asumsi forecast": "Forecast assumptions",
    "Sensitivitas EBITDA terhadap harga/permintaan": "EBITDA sensitivity to price/demand",
    "Katalis": "Catalysts",
    "Ringkasan skenario DCF": "DCF scenario summary",
    "Proyeksi FCFF": "FCFF projection",
    "Sensitivitas nilai skenario (WACC x g)": "Scenario value sensitivity (WACC x g)",
    "Jembatan pendapatan tambang": "Mining revenue bridge",
    "Discount Rate per Aset": "Discount rate by asset",
    "Sensitivitas RNAV (diskon x harga)": "RNAV sensitivity (discount x price)",
})
# Checked before the general patterns above, which they narrow.
_PATTERNS[:0] = [(re.compile(p), t) for p, t in (
    (r"Target harga: PER peer x EPS (.+)", "Target Price: peer PER x EPS {0}"),
    (r"Target harga: P/BV wajar dari ROE (.+) \(sensitivitas CoE x g\)", "Target Price: fair P/BV from ROE {0} (CoE x g sensitivity)"),
    (r"Target harga (FY\d+F?) EV/EBITDA", "{0} EV/EBITDA Target Price"),
    (r"Target harga dan sensitivitas (FY\d+F?) EV/EBITDA", "Target Price and {0} EV/EBITDA sensitivity"),
    (r"Input target harga (FY\d+F?) dan batasannya", "{0} Target Price inputs and their limits"),
    (r"Target harga berbasis hasil (FY\d+F?)", "Target Price based on {0} results"),
    (r"Asumsi skenario laba (FY\d+F?)-(FY\d+F?)", "Earnings scenario assumptions, {0}-{1}"),
    (r"(.+) \(lanjutan\)", "{0} (continued)"),
    # Audit appendix cells with figures (app.narrative's H1 debt-flow reconciliation).
    (r"Angka rinci laporan keuangan; (US\$\S+m) adalah pelunasan dipercepat yang termasuk di sini\.",
     "Detailed financial statement figure; it includes the {0} accelerated repayment."),
    (r"Dibanding pembayaran pokok jangka panjang rinci (US\$\S+m), selisih nominal (US\$\S+m) "
     r"belum direkonsiliasi; basis keduanya belum terbukti sama\.",
     "Against detailed long-term principal repayments of {0}, a nominal difference of {1} is "
     "not yet reconciled; the two are not shown to share a basis."),
)]

_LEAD = re.compile(r"(\(\+\) |\(-\) |\(=\) |\(/\) |\(-/\+\) |\(\+/-\) |\(x\) |(?:\d+|x)\. )")
_TAIL = re.compile(r"(.+?) \(([^()]*)\)")
_CURRENCY_SCALE = re.compile(r"(Rp|US\$|USD)\s(triliun|miliar|juta)\b")
_FIGURE_SCALE = re.compile(r"(\d)\s?(triliun|miliar|juta)\b")
_SCALE = {"triliun": "tn", "miliar": "bn", "juta": "mn"}
# Month abbreviations that differ between the languages (Des-25, 30 Des 2025).
_MONTH = re.compile(r"\b(Mei|Agu|Okt|Des)\b(?=[- ]?\d)")
_MONTHS = {"Mei": "May", "Agu": "Aug", "Okt": "Oct", "Des": "Dec"}


def plain(text: str) -> str:
    """Words kept; figures, currency scales and months in English."""
    out = fmt.localize(text, "en")
    out = _CURRENCY_SCALE.sub(lambda m: f"{m[1]} {_SCALE[m[2]]}", out)
    out = _FIGURE_SCALE.sub(lambda m: f"{m[1]}{_SCALE[m[2]]}", out)
    return _MONTH.sub(lambda m: _MONTHS[m[1]], out)


@functools.lru_cache(maxsize=16384)
def _en(text: str) -> str:
    hit = TERMS.get(text)
    if hit is not None:
        return hit
    stripped = text.strip()
    if stripped != text:
        return text.replace(stripped, _en(stripped)) if stripped else text
    for pattern, template in _PATTERNS:
        found = pattern.fullmatch(text)
        if found:
            return template.format(*(_en(g) if g else "" for g in found.groups()))
    lead = _LEAD.match(text)
    if lead:
        return lead.group(1) + _en(text[lead.end():])
    if text.startswith("Blok ") and len(text) > 5:  # a table's section row
        return _en(text[5:])
    tail = _TAIL.fullmatch(text)
    if tail:
        return f"{_en(tail.group(1))} ({_en(tail.group(2))})"
    for sep in (" & ", " / "):
        if sep in text:
            return sep.join(_en(part) for part in text.split(sep))
    return plain(text)


def label(text, lang: str = DEFAULT):
    """A fixed label of the report document in `lang`.

    Only Indonesian source text goes in: English text read as Indonesian
    would have its figures rewritten again."""
    if lang == DEFAULT or not isinstance(text, str) or not text:
        return text
    return _en(text)


def known(text) -> str | None:
    """The English of a label the tables know (a term, or a pattern whose
    groups are labels too), or None; ``label`` would keep unknown words."""
    if not isinstance(text, str) or not text:
        return None
    hit = TERMS.get(text)
    if hit is not None:
        return hit
    for pattern, template in _PATTERNS:
        found = pattern.fullmatch(text)
        if found:
            return template.format(*(_en(g) if g else "" for g in found.groups()))
    return None


def title(exhibit: dict, lang: str = DEFAULT) -> str:
    """An exhibit's title in `lang`: by its stable id when it has one."""
    judul = exhibit.get("judul") or ""
    if lang == DEFAULT:
        return judul
    return TITLES.get(exhibit.get("exhibit_id")) or label(str(judul), lang)


# Fixed methodology-note sentences; the others are prose and stay Indonesian.
NOTES = {
    "Tanda '-' berarti angka tidak tersedia, bukan nol.":
        "A '-' means the figure is not available, not zero.",
    "Skenario bukan forecast driver terekonsiliasi (S2.9); statusnya berbasis asumsi.":
        "The scenario is not a reconciled driver forecast (S2.9); its status is Assumption-Led.",
    "Skenario bukan forecast driver yang sudah direkonsiliasi; statusnya berbasis asumsi.":
        "The scenario is not a reconciled driver forecast; its status is Assumption-Led.",
    "Cross-check Exit EV/EBITDA tidak dihitung karena titik historis yang sebanding belum cukup.":
        "The exit EV/EBITDA cross-check is not computed: too few comparable historical points.",
    "Exit EV/EBITDA historis emiten tampil berdampingan sebagai cross-check; selisih dengan Gordon "
    "diungkapkan, tidak dirata-rata (§4.4).":
        "The issuer's historical exit EV/EBITDA is shown alongside as a cross-check; the gap to "
        "Gordon is disclosed, not averaged (§4.4).",
    "Exit EV/EBITDA historis emiten tampil sebagai cross-check; selisih dengan Gordon diungkapkan, "
    "tidak dirata-rata.":
        "The issuer's historical exit EV/EBITDA is shown as a cross-check; the gap to Gordon is "
        "disclosed, not averaged.",
    "DCF konsolidasi atas skenario analis menjadi referensi di rantai metode; PER FY skenario "
    "menjadi langkah terakhir.":
        "A consolidated DCF on the Analyst Scenario is the reference in the Method Chain; scenario "
        "FY PER is the Last Step.",
    "P/BV-ROE FY dan PER FY skenario menjadi cross-check di rantai metode, tidak dirata-rata "
    "dengan target.":
        "Scenario FY P/BV-ROE and FY PER are cross-checks in the Method Chain, not averaged into "
        "the target.",
    "PER FY skenario menjadi langkah berikutnya di rantai metode, tidak dirata-rata dengan target. "
    "DCF menunggu tiga tahun kondisi stabil.":
        "Scenario FY PER is the next step in the Method Chain, not averaged into the target. DCF "
        "waits for three years of steady state.",
    "Model operasional direkonsiliasi (FCFF, neraca dan likuiditas setiap tahun) dan dihitung "
    "ulang secara independen; driver ke depan yang berupa asumsi analis diberi label.":
        "The Operating Model is reconciled (FCFF, balance sheet and liquidity each year) and "
        "recomputed independently; forward drivers that are Analyst Assumptions are labelled.",
    "Rating dan target harga memakai SOTP/LoM, metode utama tambang: NAV per aset dari rantai "
    "fisik (cadangan, umpan, recovery, smelter, harga, biaya, royalti, pajak, capex) tanpa nilai "
    "terminal perpetual.":
        "Rating and Target Price use SOTP/LoM, the Primary Method for miners: NAV per asset from "
        "the Physical Chain (reserves, feed, recovery, smelter, price, costs, royalty, tax, capex) "
        "with no perpetual terminal value.",
}
_NOTE_PATTERNS = [(re.compile(p), t) for p, t in (
    (r"Rating dan target harga memakai DCF FCFF, metode utama going concern, atas skenario analis "
     r"(\S+): pendapatan, margin EBITDA dan capex dari agen, terminal Gordon\.",
     "Rating and Target Price use FCFF DCF, the going-concern Primary Method, on the Analyst "
     "Scenario {0}: revenue, EBITDA margin and capex from the agent, Gordon terminal."),
    (r"Rating dan target harga memakai SOTP holding, metode utama untuk grup dengan lini usaha "
     r"berbeda( \(Method Gate 0 framework\))?: anak usaha tercatat pada kapitalisasi pasar dikali "
     r"kepemilikan, sisa ekuitas pemilik induk pada nilai buku\.",
     "Rating and Target Price use a holding SOTP, the Primary Method for groups with distinct "
     "businesses: listed subsidiaries at market cap times ownership, the remaining parent equity "
     "at book value."),
    (r"EV/EBITDA (\S+) (\S+) menjadi cross-check di rantai metode, tidak dirata-rata\.",
     "{0} EV/EBITDA of {1} is a cross-check in the Method Chain, not averaged."),
)]


def note(text, lang: str = DEFAULT):
    """A methodology note in `lang`: a known sentence in English, prose unchanged."""
    if lang == DEFAULT or not isinstance(text, str):
        return text
    own = methodnote.localize_note(text, lang)
    if own != text:
        return own
    if text in NOTES:
        return NOTES[text]
    for pattern, template in _NOTE_PATTERNS:
        found = pattern.fullmatch(text)
        if found:
            return template.format(*(fmt.localize(g or "", lang) for g in found.groups()))
    return text
