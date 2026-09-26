"""Template harness (spec/Struktur-Template.md) on synthetic report documents.

Each profile has a compliant document that must pass every check (no false
positives); each check then fails on a one-line mutation of it. Nothing here
reads the app database.
"""
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.harness import template as T  # noqa: E402
from app.fmt import DEFAULT_SOURCE  # noqa: E402

YEARS = ["2024A", "2025A", "FY26F", "FY27F", "FY28F"]
FC5 = ["FY26F", "FY27F", "FY28F", "FY29F", "FY30F"]
SRC = DEFAULT_SOURCE


def idn(v, dec=0):
    s = f"{abs(v):,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"({s})" if v < 0 else s


def pct(v):
    return ("-" if v < 0 else "") + idn(abs(v), 1) + "%"


def mult(v):
    return idn(v, 1) + "x"


def ex(n, judul, cols=None, rows=None, note=SRC, tipe="tabel", **extra):
    data = {"cols": cols or [], "rows": rows or []}
    return {"n": n, "judul": judul, "tipe": tipe, "data": data, "catatan_sumber": note, **extra}


def combo(n, judul, label, bars, line, narasi="Narasi dua kalimat. Driver dijelaskan."):
    return {"n": n, "judul": judul, "tipe": "combo_panel", "narasi": narasi,
            "catatan_sumber": SRC,
            "data": {"cols": list(YEARS), "series": [{
                "label": label, "bars": list(bars), "line": list(line),
                "is_forecast": [False, False, True, True, True]}]}}


REV = [1000, 1100, 1210, 1331, 1464.1]
EBITDA = [200, 220, 242, 266.2, 292.8]
NP = [100, 110, 121, 133.1, 146.4]
NP_IS = [100, 110, 121, 133, 146]
CASH = [100, 150, 200, 260, 330]


def _kf(bank=False, cur="Rp miliar"):
    if bank:
        rows = [[f"Pendapatan ({cur})"] + [idn(v, 1) for v in REV],
                [f"Laba bersih ({cur})"] + [idn(v, 1) for v in NP],
                ["EPS (Rp)", "100", "110", "121", "133", "146"],
                ["Pertumbuhan EPS (%)"] + [pct(5.0)] + [pct(10.0)] * 4,
                ["BVPS (Rp)", "700", "760", "820", "890", "960"],
                ["ROE (%)"] + [pct(15.0)] * 5,
                ["DPS (Rp)", "50", "55", "60", "66", "73"],
                ["PER (x)"] + [mult(v) for v in (10.0, 9.1, 8.3, 7.5, 6.8)],
                ["PBV (x)"] + [mult(v) for v in (1.5, 1.4, 1.3, 1.2, 1.1)]]
    else:
        rows = [[f"Pendapatan ({cur})"] + [idn(v, 1) for v in REV],
                [f"EBITDA ({cur})"] + [idn(v, 1) for v in EBITDA],
                ["Pertumbuhan EBITDA (%)"] + [pct(5.0)] + [pct(10.0)] * 4,
                [f"Laba bersih ({cur})"] + [idn(v, 1) for v in NP],
                ["EPS (Rp)", "100", "110", "121", "133", "146"],
                ["Pertumbuhan EPS (%)"] + [pct(5.0)] + [pct(10.0)] * 4,
                ["PER (x)"] + [mult(v) for v in (10.0, 9.1, 8.3, 7.5, 6.8)],
                ["PBV (x)"] + [mult(v) for v in (1.5, 1.4, 1.3, 1.2, 1.1)],
                ["EV/EBITDA (x)"] + [mult(v) for v in (6.0, 5.5, 5.0, 4.5, 4.1)]]
    return ex(2, "Key Financials", ["Tahun buku 31 Des"] + YEARS, rows)


def _charts(profile, cur="Rp"):
    scale = 1e9 if cur == "Rp" else 1e6
    out = [combo(3, "Pendapatan dan pertumbuhan (2024A-FY28F)", f"Pendapatan ({cur}) & pertumbuhan",
                 [v * scale for v in REV], [5.0, 10.0, 10.0, 10.0, 10.0])]
    if profile != "financial_ddm":
        out.append(combo(4, "EBITDA dan margin (2024A-FY28F)", f"EBITDA ({cur}) & margin",
                         [v * scale for v in EBITDA], [20.0] * 5))
    out.append(combo(5, "Laba bersih dan pertumbuhan EPS (2024A-FY28F)",
                     f"Laba bersih ({cur}) & pertumbuhan EPS",
                     [v * scale for v in NP], [5.0, 10.0, 10.0, 10.0, 10.0]))
    fourth = {"going_concern_fcff": ("DER dan ROE (2024A-FY28F)", "DER (x) & ROE"),
              "financial_ddm": ("NIM dan biaya kredit (2024A-FY28F)", "NIM (%) & biaya kredit"),
              "finite_life_mining": ("Produksi dan biaya tunai (2024A-FY28F)", "Produksi (kt) & biaya tunai")}
    title, label = fourth[profile]
    out.append(combo(6, title, label, [0.5, 0.5, 0.4, 0.4, 0.3], [15.0, 15.5, 16.0, 16.5, 17.0]))
    return out


def _row(label, values, dec=0):
    return [label] + [idn(v, dec) for v in values]


def _is(bank=False, cur="Rp miliar"):
    if bank:
        rows = [_row("Pendapatan bunga", [900, 990, 1089, 1198, 1318]),
                _row("Beban bunga", [-300] * 5),
                _row("Pendapatan bunga bersih", [600, 690, 789, 898, 1018]),
                _row("Pendapatan non-bunga", [100] * 5),
                _row("Beban operasional", [-400, -440, -480, -520, -560]),
                _row("Laba sebelum provisi (PPOP)", [300, 350, 409, 478, 558]),
                _row("Provisi dan cadangan", [-165, -200, -243, -301, -363]),
                _row("Laba sebelum pajak", [135, 150, 166, 177, 195]),
                _row("Pajak", [-35, -40, -45, -44, -49]),
                _row("Laba bersih", NP_IS)]
        return ex(0, "Laba rugi bank", [cur] + YEARS, rows)
    rows = [_row("Pendapatan", [1000, 1100, 1210, 1331, 1464]),
            _row("Beban pokok pendapatan", [-600, -660, -726, -799, -878]),
            _row("Laba kotor", [400, 440, 484, 532, 586]),
            _row("Beban usaha", [-250, -275, -303, -333, -366]),
            _row("Laba usaha (EBIT)", [150, 165, 181, 199, 220]),
            _row("Pendapatan bunga", [5] * 5),
            _row("Beban bunga", [-20] * 5),
            _row("Pendapatan (beban) lain-lain", [0] * 5),
            _row("Laba sebelum pajak", [135, 150, 166, 184, 205]),
            _row("Pajak penghasilan", [-35, -40, -45, -51, -59]),
            _row("Kepentingan non-pengendali", [0] * 5),
            _row("Laba bersih", NP_IS)]
    return ex(0, "Laba rugi", [cur] + YEARS, rows)


def _bs(bank=False, cur="Rp miliar"):
    if bank:
        eq = [c + 350 for c in CASH]
        ta = [c + 750 for c in CASH]
        rows = [_row("Kredit bruto", [500] * 5), _row("Cadangan kerugian kredit", [-20] * 5),
                _row("Kredit bersih", [480] * 5), _row("Obligasi pemerintah", [100] * 5),
                _row("Surat berharga", [50] * 5), _row("Total aset produktif", [630] * 5),
                _row("Total aset", ta), _row("Dana pihak ketiga", [300] * 5),
                _row("Total liabilitas", [400] * 5), _row("Total ekuitas", eq),
                _row("Total liabilitas dan ekuitas", ta)]
        return ex(0, "Neraca bank", [cur] + YEARS, rows)
    tca = [c + 200 for c in CASH]
    ta = [c + 750 for c in CASH]
    rows = [_row("Kas dan setara kas", CASH), _row("Piutang usaha", [100] * 5),
            _row("Persediaan", [80] * 5), _row("Aset lancar lainnya", [20] * 5),
            _row("Total aset lancar", tca), _row("Aset tetap bersih", [500] * 5),
            _row("Aset tidak lancar lainnya", [50] * 5), _row("Total aset", ta),
            _row("Utang jangka pendek", [50] * 5), _row("Utang usaha", [60] * 5),
            _row("Liabilitas lancar lainnya", [40] * 5), _row("Total liabilitas lancar", [150] * 5),
            _row("Utang jangka panjang", [200] * 5), _row("Liabilitas tidak lancar lainnya", [50] * 5),
            _row("Total liabilitas", [400] * 5), _row("Total ekuitas", [c + 350 for c in CASH]),
            _row("Total liabilitas dan ekuitas", ta)]
    return ex(0, "Neraca", [cur] + YEARS, rows)


def _cf(cur="Rp miliar"):
    blank = [""] * 5
    div = [-50, -30, -41, -43, -46]
    cfo = [n + 20 for n in NP_IS]
    rows = [["Blok Arus kas operasi"] + blank,
            _row("Laba bersih", NP_IS), _row("Depresiasi dan amortisasi", [30] * 5),
            _row("Perubahan modal kerja", [-10] * 5), _row("Pos operasi lainnya", [0] * 5),
            _row("Jumlah arus kas operasi", cfo),
            ["Blok Arus kas investasi"] + blank,
            _row("Belanja modal", [-50] * 5), _row("Pos investasi lainnya", [0] * 5),
            _row("Jumlah arus kas investasi", [-50] * 5),
            ["Blok Arus kas pendanaan"] + blank,
            _row("Penarikan (pembayaran) utang", [0] * 5), _row("Dividen dibayar", div),
            _row("Penerbitan (pembelian kembali) saham", [0] * 5),
            _row("Pos pendanaan lainnya", [0] * 5), _row("Jumlah arus kas pendanaan", div),
            _row("Perubahan kas bersih", [20, 50, 50, 60, 70]),
            _row("Kas awal", [80, 100, 150, 200, 260]), _row("Kas akhir", CASH),
            _row("Arus kas bebas (operasi - capex)", [c - 50 for c in cfo])]
    return ex(0, "Arus kas", [cur] + YEARS, rows)


def _ratio(bank=False):
    blank = [""] * 5
    if bank:
        labels = ["Imbal hasil aset produktif", "Biaya dana", "Selisih bunga (spread)",
                  "Marjin bunga bersih (NIM)", "Rasio biaya terhadap pendapatan", "Rasio NPL bruto",
                  "Cakupan cadangan NPL", "Biaya kredit (provisi / rata-rata kredit)",
                  "Kredit terhadap simpanan (LDR)", "Rasio CASA", "ROAE", "ROAA",
                  "Rasio kecukupan modal (CAR)"]
        rows = [["Blok Profitabilitas dan kualitas aset (%)"] + blank] + \
            [[lab] + [pct(5.0)] * 5 for lab in labels]
        return ex(0, "Rasio utama bank", ["Rasio"] + YEARS, rows)
    rows = [["Blok Pertumbuhan (%)"] + blank]
    rows += [[lab] + [pct(10.0)] * 5 for lab in ("Pendapatan", "EBITDA", "Laba usaha", "Laba bersih")]
    rows += [["Blok Profitabilitas (%)"] + blank]
    rows += [[lab] + [pct(20.0)] * 5 for lab in ("Marjin laba kotor", "Marjin EBITDA", "Marjin usaha",
                                                 "Marjin laba bersih", "ROAA", "ROAE")]
    rows += [["Blok Leverage (x)"] + blank,
             ["Net gearing (utang bersih / ekuitas)"] + [mult(0.3)] * 5,
             ["Cakupan bunga (EBIT / beban bunga)"] + [mult(7.5)] * 5]
    return ex(0, "Rasio utama", ["Rasio"] + YEARS, rows)


def _chain(label, value="Rp1.200"):
    return ex(0, "Rantai metode valuasi", ["Metode", "Keputusan", "Nilai/saham", "Alasan"],
              [[f"1. {label} (utama)", "Terpilih", value, "metode utama profile"],
               ["2. PER relatif", "Silang cek", "Rp1.100", "PER peer TTM"]])


def _sens(title, first, base_label, cols):
    rows = []
    for i, v in enumerate((9.9, 10.4, 10.9, 11.4, 11.9)):
        label = f"{first} {idn(v, 1)}%" + (" (basis)" if i == 2 else "")
        rows.append([label] + [f"Rp{idn(x)}" for x in (1500 - i * 150, 1600 - i * 200, 1800 - i * 300)])
    rows[2][2] = "Rp1.200"
    return ex(0, title, [base_label] + cols, rows)


def _valuation(profile, cur="Rp miliar"):
    if profile == "going_concern_fcff":
        fcff = ex(0, "Proyeksi FCFF dan nilai kini (FY26F-FY30F)", [cur] + FC5, [
            _row("Pendapatan", [1210, 1331, 1464, 1610, 1771], 1),
            _row("EBITDA", [242, 266, 293, 322, 354], 1),
            _row("(-) D&A", [30] * 5, 1), _row("EBIT", [212, 236, 263, 292, 324], 1),
            _row("(-) Pajak atas EBIT (22,0%)", [47, 52, 58, 64, 71], 1),
            _row("NOPAT", [165, 184, 205, 228, 253], 1), _row("(+) D&A", [30] * 5, 1),
            _row("(-) Capex", [90, 104, 119, 136, 155], 1),
            _row("(-) Kenaikan modal kerja", [10] * 5, 1),
            _row("FCFF", [95, 100, 106, 112, 118], 1),
            ["Pertumbuhan FCFF", pct(4.0), pct(5.3), pct(6.0), pct(5.7), pct(5.4)],
            ["Faktor diskonto (WACC 10,9%)", "0,949", "0,856", "0,772", "0,696", "0,628"],
            _row("PV FCFF", [90, 86, 82, 78, 74], 1)])
        term = ex(0, "Nilai terminal dan jembatan EV ke ekuitas", [cur, "Gordon g 3,5% (basis)"], [
            ["FCFF terminal = FCFF FY30F x (1 + g)", "122,1"], ["Pertumbuhan terminal g", "3,5%"],
            ["Nilai terminal (tidak didiskonto)", "1.650,0"], ["Faktor diskonto terminal", "0,628"],
            ["PV nilai terminal", "1.036,2"], ["Jumlah PV FCFF", "410,0"],
            ["Enterprise value", "1.446,2"], ["(+) Kas", "150,0"], ["(-) Utang", "(250,0)"],
            ["(-) Minoritas", "(0,0)"], ["Nilai ekuitas pemilik induk", "1.200,0"],
            ["Nilai wajar per saham (Rp)", "1.200"]])
        wacc = ex(0, "Komponen WACC", ["Parameter", "Nilai"], [
            ["Risk-free (INDOGB 10Y)", "6,5%"], ["Beta (Bloomberg)", "1,10"],
            ["Equity risk premium (Damodaran)", "4,0%"], ["Cost of equity (CAPM)", "10,9%"],
            ["Cost of debt sebelum pajak", "9,0%"], ["Tarif pajak efektif", "22,0%"],
            ["Cost of debt setelah pajak", "7,0%"], ["Bobot utang (nilai pasar)", "0,0%"],
            ["Bobot ekuitas (nilai pasar)", "100,0%"], ["WACC", "10,9%"]])
        sens = _sens("Sensitivitas nilai DCF: WACC x pertumbuhan terminal", "WACC", "WACC",
                     ["g 2,5%", "g 3,5%", "g 4,5%"])
        return "DCF FCFF skenario FY26F-FY30F + terminal Gordon", "fcff_dcf", \
            [fcff, term, wacc, sens, _chain("DCF FCFF")]
    if profile == "financial_ddm":
        div = ex(0, "Proyeksi dividen dan nilai kini (DDM, FY26F-FY30F)", ["Rp"] + FC5, [
            ["Laba pemilik induk (Rp miliar)"] + [idn(v, 1) for v in (121, 133, 146, 161, 177)],
            ["Payout ratio"] + [pct(50.0)] * 5,
            ["DPS (Rp)", "60", "66", "73", "80", "88"],
            ["Pertumbuhan DPS", pct(9.1), pct(10.0), pct(10.6), pct(9.6), pct(10.0)],
            ["Faktor diskonto (CoE 10,9%)", "0,925", "0,834", "0,752", "0,678", "0,612"],
            ["PV DPS (Rp)", "55", "55", "55", "54", "54"]])
        term = ex(0, "Nilai terminal dan nilai wajar per saham (DDM)", ["Komponen", "Nilai"], [
            ["Jumlah PV DPS eksplisit (Rp)", "273"], ["DPS terminal = DPS FY30F x (1 + g) (Rp)", "91"],
            ["Pertumbuhan terminal g", "3,5%"], ["Nilai terminal (Rp)", "1.232"],
            ["PV nilai terminal (Rp)", "927"], ["Nilai wajar per saham (Rp)", "1.200"]])
        coe = ex(0, "Komponen Cost of Equity", ["Komponen", "Nilai"], [
            ["Risk-free rate (INDOGB 10Y)", "6,5%"], ["Beta (Bloomberg)", "1,1x"],
            ["Equity Risk Premium (Damodaran)", "4,0%"], ["(=) Cost of Equity dipakai", "10,9%"]])
        sens = _sens("Sensitivitas nilai DDM: CoE x pertumbuhan terminal", "CoE", "Cost of equity",
                     ["g 2,5%", "g 3,5%", "g 4,5%"])
        return "DDM dividen skenario FY26F-FY30F + terminal Gordon (CoE)", "ddm", \
            [div, term, coe, sens, _chain("DDM")]
    sotp = ex(0, "SOTP/LoM: nilai aset ke ekuitas", ["Komponen", "Kepemilikan", "Rp miliar", "Basis"], [
        ["NAV Tambang A", "100,0%", "900,0", "LoM DCF 10,9%"],
        ["NAV Proyek B", "60,0%", "300,0", "LoM DCF 12,0%"],
        ["Jumlah NAV aset", "", "1.200,0", ""], ["(-) PV overhead korporat", "", "(50,0)", ""],
        ["(+) Kas", "", "150,0", "neraca"], ["(-) Utang", "", "(100,0)", "neraca"],
        ["Total RNAV", "", "1.200,0", ""], ["Diskon RNAV", "", "0,0%", "asumsi"],
        ["Nilai per saham (Rp)", "", "Rp1.200", "1,0 miliar saham"]])
    lom = ex(0, "Jadwal LoM (FY26F-FY30F)", [cur] + FC5, [
        _row("Produksi (kt)", [100, 105, 110, 110, 110]), _row("Pendapatan", [1210, 1331, 1464, 1464, 1464]),
        _row("EBITDA", [242, 266, 293, 293, 293]), _row("Capex", [90, 90, 90, 90, 90]),
        _row("FCFF", [120, 140, 160, 160, 160])])
    rates = ex(0, "Tingkat diskonto per aset", ["Aset", "Tingkat diskonto", "Dasar"], [
        ["Tambang A", "10,9%", "operasi matang"], ["Proyek B", "12,0%", "tahap pengembangan"]])
    assumptions = ex(0, "Asumsi analis dalam SOTP/LoM", ["Asumsi", "Nilai", "Dasar"], [
        ["Risk-free (INDOGB 10Y)", "6,5%", "data pasar"], ["Beta (Bloomberg)", "1,1", "peer"],
        ["ERP (Damodaran)", "4,0%", "kebijakan analis"], ["Tingkat diskonto", "10,9%", "CAPM"]])
    sens = _sens("Sensitivitas SOTP/LoM: tingkat diskonto x dek harga", "Diskonto", "Tingkat diskonto",
                 ["Dek -20%", "Dek dasar", "Dek +20%"])
    return "SOTP/LoM: Tambang A + Proyek B tanpa terminal perpetual", "sotp_lom", \
        [sotp, lom, rates, assumptions, sens, _chain("SOTP/LoM")]


def _peers(bank=False):
    sel = ex(0, "Grup peer: alasan pemilihan", ["Emiten", "Bursa", "Status", "Alasan"], [
        ["Alfa Tbk", "IDX", "dipakai", "model bisnis sama"],
        ["Beta Tbk", "IDX", "dipakai", "model bisnis sama"],
        ["Gamma Tbk", "IDX", "dipakai", "model bisnis sama"]])
    cols = ["Emiten", "Kap. pasar (Rp miliar)", "P/E (x)", "P/B (x)"] + ([] if bank else ["EV/EBITDA (x)"]) + ["ROE"]

    def r(name, cap, pe, pb, ev, roe):
        return [name, cap, pe, pb] + ([] if bank else [ev]) + [roe]
    comp = ex(0, "Perbandingan peer Uji", cols, [
        r("Alfa Tbk (AAAA)", "5.000", "12,0x", "1,5x", "7,0x", "12,0%"),
        r("Beta Tbk (BBBB)", "4.000", "10,0x", "1,3x", "6,0x", "13,0%"),
        r("Gamma Tbk (CCCC)", "3.000", "8,0x", "1,1x", "5,0x", "14,0%"),
        r("Uji Coba Tbk (TEST) (emiten)", "1.000", "9,1x", "1,4x", "5,5x", "15,0%"),
        r("Median peer (tanpa emiten)", "4.000", "10,0x", "1,3x", "6,0x", "13,0%"),
        r("Rata-rata peer (tanpa emiten)", "4.000", "10,0x", "1,3x", "6,0x", "13,0%")],
        note="Source: grup peer kurasi; per 2026-09-24; kriteria: model bisnis dan kapitalisasi sebanding.")
    band_table = ex(0, "Band historis 12 bulan P/E dan P/BV (bukan target harga)",
                    ["Multiple", "Mean", "Median", "Kini (persentil)", "Implisit mean / median"], [
                        ["P/E", "10,0x", "9,8x", "9,1x (p30)", "Rp1.100 / Rp1.080"],
                        ["P/BV", "1,5x", "1,5x", "1,4x (p40)", "Rp1.070 / Rp1.070"]])
    dates = [f"{2025 + (m + 8) // 12}-{(m + 8) % 12 + 1:02d}-24" for m in range(13)]
    dates[-1] = "2026-09-23"

    def band(label, values):
        mean = sum(values) / len(values)
        return {"n": 0, "judul": f"Band {label} 12 bulan TEST", "tipe": "band_chart", "catatan_sumber": SRC,
                "data": {"label": label, "dates": dates, "values": values, "mean": mean,
                         "median": sorted(values)[6], "current": values[-1], "percentile": 30.0}}
    pe = band("P/E", [10.0 + (i % 3) * 0.2 for i in range(13)])
    pb = band("P/BV", [1.5 + (i % 3) * 0.02 for i in range(13)])
    paras = ["TEST diperdagangkan pada P/E FY26F 8,3x, diskon terhadap median peer 10,0x.",
             "Harga implisit band adalah cross-check, bukan target harga, dengan driver fundamental tetap."]
    return paras, [sel, comp, band_table, pe, pb]


COVER_PARA3 = ("Nilai model Rp1.200 dihitung dengan {family}, dengan asumsi {param} sebesar 10,9%. "
               "Nilai model ini mengimplikasikan EBITDA CAGR FY26-28F sebesar 10,0%, didukung kapasitas baru. "
               "Pada nilai model tersebut, saham diperdagangkan pada PER 26F sebesar 9,9x, dibandingkan rata-rata historis 10,0x. "
               "Risiko utama: harga bahan baku.")


def make_doc(profile="going_concern_fcff", status="distributable_assumption_led"):
    bank = profile == "financial_ddm"
    method, key, val_exhibits = _valuation(profile)
    family = {"fcff_dcf": "DCF FCFF", "ddm": "DDM", "sotp_lom": "SOTP/LoM"}[key]
    param = {"fcff_dcf": "WACC", "ddm": "CoE", "sotp_lom": "tingkat diskonto"}[key]
    price = ex(0, "TEST relatif terhadap IHSG", tipe="price_chart")
    price["data"] = {"ticker": "TEST", "as_of": "2026-09-24"}
    kf = _kf(bank)
    charts = _charts(profile)
    peer_paras, peer_exhibits = _peers(bank)
    fin = [_is(bank), _bs(bank), _cf(), _ratio(bank)]
    pages = [
        {"halaman": 2, "judul": "Kinerja keuangan", "paragraf": ["Kinerja per grafik."], "exhibit": charts},
        {"halaman": 3, "judul": f"Nilai model berbasis {family}", "paragraf": ["Valuasi."],
         "exhibit": val_exhibits},
        {"halaman": 4, "judul": "Perbandingan peer", "paragraf": peer_paras, "exhibit": peer_exhibits},
        {"halaman": 5, "judul": "Data keuangan", "paragraf": ["Laporan keuangan."], "exhibit": fin},
    ]
    exhibits = [price, kf] + [e for p in pages for e in p["exhibit"]]
    for n, e in enumerate(exhibits, 1):
        e["n"] = n
    return {
        "meta": {"ticker": "TEST", "emiten": "PT Uji Coba Tbk", "tanggal": "2026-09-24",
                 "harga": 1000.0, "status": status, "model_profile": profile,
                 "rating": "Di atas harga pasar", "tp": 1200, "upside_persen": 20.0,
                 "rating_status": "Skenario nilai indikatif"},
        "cover": {
            "headline": "Kapasitas Baru Mendorong Laba Tumbuh Konsisten",
            "bullets": ["Pendapatan 1H26 naik 12% yoy ke Rp600 miliar.",
                        "Kapasitas baru menambah volume mulai 2H26.",
                        f"Nilai model per saham Rp1.200 (+20,0%) dari {family}."],
            "paragraf": [{"judul": "Hasil 1H26 melampaui run-rate", "isi": "Pendapatan 1H26 naik 12%."},
                         {"judul": "Kapasitas baru menopang volume", "isi": "Volume naik 8%."},
                         {"judul": f"Nilai model berbasis {family}",
                          "isi": COVER_PARA3.format(family=family, param=param)}],
            "data_pasar": {"harga": 1000.0, "saham": 1e9, "market_cap": 1e12, "market_cap_usd": "60,0",
                           "adtv": "5,0", "adtv_usd": "0,3", "free_float": "40,0"},
            "key_financials": kf["data"]["rows"]},
        "holders": [["PT Induk", "60,0%"]],
        "method": method,
        "bagian": pages,
        "exhibits": exhibits,
        "harness": {"log_gate": {"release": {"method_key": key}}},
    }


def results(doc, **kw):
    return {c["check"]: c for c in T.check_template(doc, **kw)["checks"]}


def failed(doc, **kw):
    return {k: c for k, c in results(doc, **kw).items() if c["status"] == T.FAIL}


def find(doc, title):
    return next(e for e in doc["exhibits"] if e["judul"].startswith(title))


def row(e, label):
    return next(r for r in e["data"]["rows"] if r[0].startswith(label))


# ------------------------------------------------------------ compliant docs

@pytest.mark.parametrize("profile", ["going_concern_fcff", "financial_ddm", "finite_life_mining"])
def test_compliant_doc_passes_every_check(profile):
    res = results(make_doc(profile))
    assert not [f"{k}: {c['message']}" for k, c in res.items() if c["status"] == T.FAIL]
    assert set(res) == set(T.CHECKS), "every registered check reports"


def test_registry_severities_are_blocker_or_warning():
    assert {sev for sev, _o, _r in T.CHECKS.values()} == {T.BLOCKER, T.WARNING}
    assert all(owner in ("present", "layout", "model", "peers") for _s, owner, _r in T.CHECKS.values())


def test_blocker_status_and_list():
    doc = make_doc()
    row(find(doc, "Key Financials"), "PBV")[4] = "NA"
    out = T.check_template(doc)
    assert out["status"] == "gagal"
    assert any(b.startswith("TF.forecast_cells:") for b in out["blockers"])


# ------------------------------------------------------------ parsing

def test_parse_num_indonesian_formats():
    assert T.num("3.520,0") == 3520.0
    assert T.num("(139,1)") == -139.1
    assert T.num("-31,1%") == -31.1
    assert T.num("12,4x") == 12.4
    assert T.num("Rp5.925") == 5925
    assert T.num("(Rp234)") == -234
    assert T.num("tidak ada") is None
    assert T.parse_num("1.005,7")[1] == 1


def test_parse_period_and_cells():
    assert T.parse_period("2024A") == (2024, "A")
    assert T.parse_period("FY26F") == (2026, "F")
    assert T.parse_period("2025") == (2025, None)
    assert T.parse_period("1H26") is None
    assert T.classify_cell("NA") == "blank" and T.classify_cell("-") == "blank"
    assert T.classify_cell("belum dimodelkan") == "nm"
    assert T.classify_cell("n.m.") == "nm" and T.classify_cell("1.234,5") == "num"
    assert T.classify_cell("H2/H1 1,40x; margin 25,0%") == "text"


# ------------------------------------------------------------ T1

def test_generic_exhibit_title_warns():
    doc = make_doc()
    find(doc, "Komponen WACC")["judul"] = "Tabel"
    assert failed(doc)["T1.exhibit_label"]["severity"] == T.WARNING


def test_numbering_out_of_reading_order_blocks():
    doc = make_doc()
    a, b = find(doc, "Laba rugi"), find(doc, "Neraca")
    a["n"], b["n"] = b["n"], a["n"]
    assert failed(doc)["T1.numbering"]["blocker"]


def test_unplaced_exhibit_blocks_numbering():
    doc = make_doc()
    extra = ex(len(doc["exhibits"]) + 1, "Tabel yang tidak ditempatkan", ["A", "B"], [["x", "1"]])
    doc["exhibits"].append(extra)
    assert "tidak ditempatkan" in failed(doc)["T1.numbering"]["message"]


def test_title_range_must_match_columns():
    doc = make_doc()
    find(doc, "DER dan ROE")["judul"] = "DER dan ROE (2021-2025)"
    assert failed(doc)["T1.title_period_range"]["blocker"]


# ------------------------------------------------------------ TF

@pytest.mark.parametrize("cell", ["NA", "-", "", "n.a.", "tidak tersedia"])
def test_bare_forecast_cell_blocks(cell):
    doc = make_doc()
    row(find(doc, "Neraca"), "Piutang usaha")[4] = cell
    assert failed(doc)["TF.forecast_cells"]["blocker"]


def test_nm_forecast_cell_needs_reason_in_note():
    doc = make_doc()
    bs = find(doc, "Neraca")
    row(bs, "Piutang usaha")[3:] = ["n.m."] * 3
    assert "TF.forecast_cells" not in failed(doc)
    assert failed(doc)["TF.nm_reason"]["blocker"]
    bs["catatan_sumber"] += "; piutang usaha n.m.: tidak dilaporkan terpisah."
    assert "TF.nm_reason" not in failed(doc)


def test_belum_dimodelkan_out_years_need_the_reason_in_the_note():
    doc = make_doc()
    kf = find(doc, "Key Financials")
    for r in kf["data"]["rows"]:
        r[4:] = ["belum dimodelkan"] * 2
    f = failed(doc)
    assert "TF.forecast_cells" not in f and f["TF.nm_reason"]["blocker"]
    kf["catatan_sumber"] += "; FY27F-FY28F belum dimodelkan: skenario tahun lanjut belum tervalidasi."
    f = failed(doc)
    assert "TF.forecast_cells" not in f and "TF.nm_reason" not in f
    kf["data"]["cols"] = kf["data"]["cols"][:4]  # dropping the columns stays a blocker
    kf["data"]["rows"] = [r[:4] for r in kf["data"]["rows"]]
    assert failed(doc)["T2.key_financials_cols"]["blocker"]


def test_chart_forecast_point_missing_blocks_unless_explained():
    doc = make_doc()
    chart = find(doc, "EBITDA dan margin")
    chart["data"]["series"][0]["bars"][4] = None
    assert failed(doc)["TF.forecast_cells"]["blocker"]
    chart["catatan_sumber"] += "; FY28F n.m. karena basis negatif."
    assert "TF.forecast_cells" not in failed(doc)


def test_descriptive_row_in_scenario_table_is_not_a_blank_cell():
    doc = make_doc()
    scen = ex(0, "Skenario laba FY26F: aktual 1H dan asumsi H2", ["Rp miliar", "1H aktual", "H2 asumsi", "FY26F"],
              [["Pendapatan", "600,0", "610,0", "1.210,0"], ["Asumsi", "-", "H2/H1 1,02x; margin 10,0%", "-"]])
    doc["bagian"][1]["exhibit"].append(scen)
    doc["exhibits"] = T.reading_order(doc)
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    assert "TF.forecast_cells" not in failed(doc)


def test_actual_blank_cell_warns():
    doc = make_doc()
    row(find(doc, "Key Financials"), "EBITDA (")[1] = "-"
    f = failed(doc)
    assert f["TF.actual_cells"]["severity"] == T.WARNING and "TF.forecast_cells" not in f


def test_statement_horizon_three_actual_two_forecast_blocks():
    doc = make_doc()
    find(doc, "Laba rugi")["data"]["cols"] = ["Rp miliar", "2023A", "2024A", "2025A", "FY26F", "FY27F"]
    assert failed(doc)["TF.display_horizon"]["blocker"]


def test_chart_missing_forecast_year_blocks_and_extra_history_warns():
    doc = make_doc()
    chart = find(doc, "Pendapatan dan pertumbuhan")
    chart["data"]["cols"] = chart["data"]["cols"][:4]
    assert failed(doc)["TF.display_horizon"]["blocker"]
    doc = make_doc()
    chart = find(doc, "Pendapatan dan pertumbuhan")
    chart["data"]["cols"].insert(0, "2023A")
    s = chart["data"]["series"][0]
    s["bars"].insert(0, 900e9), s["line"].insert(0, 4.0), s["is_forecast"].insert(0, False)
    chart["judul"] = "Pendapatan dan pertumbuhan (2023A-FY28F)"
    f = failed(doc)
    assert f["TF.chart_history"]["severity"] == T.WARNING and "TF.display_horizon" not in f


def test_actual_only_fourth_chart_with_reason_is_a_warning():
    doc = make_doc("financial_ddm")
    chart = find(doc, "NIM dan biaya kredit")
    chart["judul"] = "NIM dan biaya kredit (2024A-2025A, aktual)"
    chart["narasi"] = "Skenario tidak memodelkan neraca kredit, sehingga grafik ini hanya aktual."
    chart["data"]["cols"] = ["2024A", "2025A"]
    s = chart["data"]["series"][0]
    s["bars"], s["line"], s["is_forecast"] = s["bars"][:2], s["line"][:2], [False, False]
    f = failed(doc)
    assert "TF.display_horizon" not in f and f["TF.chart_forecast_nm"]["severity"] == T.WARNING
    chart["narasi"] = "NIM stabil."
    chart["judul"] = "NIM dan biaya kredit (2024A-2025A)"
    assert failed(doc)["TF.display_horizon"]["blocker"]


def test_valuation_table_needs_five_forecast_years():
    doc = make_doc()
    fcff = find(doc, "Proyeksi FCFF")
    fcff["data"]["cols"] = fcff["data"]["cols"][:5]
    fcff["data"]["rows"] = [r[:5] for r in fcff["data"]["rows"]]
    fcff["judul"] = "Proyeksi FCFF dan nilai kini (FY26F-FY29F)"
    assert failed(doc)["TF.valuation_horizon"]["blocker"]


def test_mining_lom_table_from_second_forecast_year_blocks():
    doc = make_doc("finite_life_mining")
    lom = find(doc, "Jadwal LoM")
    lom["data"]["cols"] = ["Rp miliar", "FY27F", "FY28F", "FY29F", "FY30F"]
    lom["data"]["rows"] = [r[:1] + r[2:] for r in lom["data"]["rows"]]
    lom["judul"] = "Jadwal LoM (FY27F-FY30F)"
    assert failed(doc)["TF.valuation_horizon"]["blocker"]


def test_period_label_without_suffix_warns():
    doc = make_doc()
    find(doc, "Key Financials")["data"]["cols"][1] = "2024"
    assert failed(doc)["TF.period_labels"]["severity"] == T.WARNING


# ------------------------------------------------------------ T2

def test_rating_block_and_status():
    doc = make_doc()
    doc["meta"]["rating"] = "Strong Buy"
    assert failed(doc)["T2.cover_rating_block"]["blocker"]
    doc = make_doc()
    doc["meta"]["rating_status"] = "Bagus"
    assert failed(doc)["T2.rating_status"]["severity"] == T.WARNING


def test_draft_skips_published_only_checks():
    doc = make_doc(status="draft_non_distributable")
    for k in ("rating", "tp", "upside_persen", "rating_status"):
        doc["meta"].pop(k)
    res = results(doc)
    for cid in ("T2.cover_rating_block", "T2.price_box", "T2.cover_tp_method",
                "T4.valuation_option_exhibits", "T2.valuation_paragraph",
                "T4.ddm_blocks", "T4.ddm_rows"):
        assert res[cid]["status"] == T.NA, cid
    assert not [k for k, c in res.items() if c["status"] == T.FAIL]


def test_draft_ddm_skips_published_valuation_completeness():
    doc = make_doc("financial_ddm", status="draft_non_distributable")
    for key in ("rating", "tp", "upside_persen", "rating_status"):
        doc["meta"].pop(key)
    res = results(doc)
    assert res["T4.ddm_blocks"]["status"] == T.NA
    assert res["T4.ddm_rows"]["status"] == T.NA
    assert not [k for k, c in res.items() if c["status"] == T.FAIL]


def test_upside_must_equal_tp_over_price():
    doc = make_doc()
    doc["meta"]["upside_persen"] = 25.0
    assert failed(doc)["T2.price_box"]["blocker"]


def test_stats_block_and_relative_chart_warn():
    doc = make_doc()
    del doc["cover"]["data_pasar"]["market_cap_usd"]
    doc["holders"] = []
    assert "kap. pasar US$" in failed(doc)["T2.stats_block"]["message"]
    doc = make_doc()
    doc["exhibits"] = doc["exhibits"][1:]
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    assert failed(doc)["T2.relative_chart"]["severity"] == T.WARNING


def test_thesis_bullets_paragraphs_warn():
    doc = make_doc()
    doc["cover"]["headline"] = "Company Update"
    doc["cover"]["bullets"].append("Bullet keempat.")
    doc["cover"]["paragraf"] = doc["cover"]["paragraf"][1:]
    f = failed(doc)
    assert {"T2.thesis_subtitle", "T2.cover_bullets", "T2.cover_paragraphs"} <= set(f)
    assert all(f[k]["severity"] == T.WARNING for k in ("T2.thesis_subtitle", "T2.cover_bullets"))


def test_valuation_paragraph_elements():
    doc = make_doc()
    p = doc["cover"]["paragraf"][2]
    p["isi"] = p["isi"].replace("CAGR FY26-28F", "CAGR FY25-FY28F").replace("Pada nilai model tersebut", "Pada harga kini")
    msg = failed(doc)["T2.valuation_paragraph"]["message"]
    assert "CAGR FY26-28F" in msg and "multiple dihitung pada nilai model" in msg


def test_cover_tp_and_method_must_match_valuation_page():
    doc = make_doc()
    doc["cover"]["bullets"][2] = "Nilai model Rp1.300 (+30,0%) dari DCF FCFF."
    assert failed(doc)["T2.cover_tp_method"]["blocker"]
    doc = make_doc()
    doc["method"] = "DDM dividen skenario"
    assert failed(doc)["T2.cover_tp_method"]["blocker"]
    doc = make_doc()
    row(find(doc, "Rantai metode"), "1. DCF")[2] = "Rp1.500"
    assert failed(doc)["T2.cover_tp_method"]["blocker"]
    doc = make_doc()
    row(find(doc, "Nilai terminal"), "Nilai wajar per saham")[1] = "1.350"
    assert failed(doc)["T2.cover_tp_method"]["blocker"]


def test_key_financials_rows_order_and_columns():
    doc = make_doc()
    kf = find(doc, "Key Financials")
    kf["data"]["rows"] = [r for r in kf["data"]["rows"] if not r[0].startswith("PBV")]
    assert "pbv" in failed(doc)["T2.key_financials_rows"]["message"]
    doc = make_doc()
    rows = find(doc, "Key Financials")["data"]["rows"]
    rows[0], rows[1] = rows[1], rows[0]
    assert failed(doc)["T2.key_financials_order"]["severity"] == T.WARNING
    doc = make_doc()
    kf = find(doc, "Key Financials")
    kf["data"]["cols"] = ["Tahun buku 31 Des", "2023A", "2024A", "2025A", "FY26F", "FY27F"]
    assert failed(doc)["T2.key_financials_cols"]["blocker"]


def test_bank_key_financials_row_set():
    doc = make_doc("financial_ddm")
    kf = find(doc, "Key Financials")
    kf["data"]["rows"] = [r for r in kf["data"]["rows"] if not r[0].startswith("DPS")]
    assert "dps" in failed(doc)["T2.key_financials_rows"]["message"]


def test_multiples_need_one_decimal():
    doc = make_doc()
    row(find(doc, "Key Financials"), "PER")[3] = "8x"
    assert failed(doc)["TN.one_decimal"]["severity"] == T.WARNING


# ------------------------------------------------------------ T3

def test_missing_slide3_chart_blocks_but_bank_needs_no_ebitda_chart():
    doc = make_doc()
    doc["bagian"][0]["exhibit"] = [e for e in doc["bagian"][0]["exhibit"] if not e["judul"].startswith("EBITDA")]
    doc["exhibits"] = T.reading_order(doc)
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    assert failed(doc)["T3.combo_charts"]["blocker"]
    assert "T3.combo_charts" not in failed(make_doc("financial_ddm"))


def test_chart_style_and_fourth_chart_warn():
    doc = make_doc()
    find(doc, "DER dan ROE")["narasi"] = ""
    find(doc, "DER dan ROE")["data"]["series"][0]["label"] = "Capex (Rp) & intensitas"
    f = failed(doc)
    assert f["T3.chart_style"]["severity"] == T.WARNING
    assert f["T3.chart4_by_profile"]["severity"] == T.WARNING


def test_chart_values_tie_out_to_key_financials():
    doc = make_doc()
    find(doc, "Laba bersih dan pertumbuhan")["data"]["series"][0]["bars"][3] = 140e9
    assert failed(doc)["T3.tieout_key_financials"]["blocker"]
    doc = make_doc()
    find(doc, "EBITDA dan margin")["data"]["series"][0]["line"][2] = 22.0
    assert failed(doc)["T3.tieout_key_financials"]["blocker"]


def test_key_financials_and_statements_in_different_currencies_block():
    doc = make_doc()
    kf = find(doc, "Key Financials")
    for r in kf["data"]["rows"]:
        r[0] = r[0].replace("Rp miliar", "US$ juta")
    f = failed(doc)
    assert f["T3.currency_consistency"]["blocker"]
    assert "T3.tieout_key_financials" not in f  # compared within one currency only


# ------------------------------------------------------------ T4

def test_missing_option_exhibit_blocks():
    doc = make_doc()
    doc["bagian"][1]["exhibit"] = [e for e in doc["bagian"][1]["exhibit"] if e["judul"] != "Komponen WACC"]
    doc["exhibits"] = T.reading_order(doc)
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    f = failed(doc)
    assert "WACC Components" in f["T4.valuation_option_exhibits"]["message"]
    assert f["T4.wacc_components"]["blocker"]


def test_fcff_blocks_and_rows():
    doc = make_doc()
    term = find(doc, "Nilai terminal")
    term["data"]["rows"] = [r for r in term["data"]["rows"] if r[0] != "Enterprise value"]
    assert "bridge" in failed(doc)["T4.fcff_blocks"]["message"]
    doc = make_doc()
    fcff = find(doc, "Proyeksi FCFF")
    fcff["data"]["rows"] = [r for r in fcff["data"]["rows"] if r[0] != "NOPAT"]
    f = failed(doc)
    assert "nopat" in f["T4.fcff_rows"]["message"] and "T4.fcff_blocks" not in f


def test_wacc_components_and_rows():
    doc = make_doc()
    w = find(doc, "Komponen WACC")
    w["data"]["rows"] = [r for r in w["data"]["rows"] if not r[0].startswith("Beta")]
    assert "beta" in failed(doc)["T4.wacc_components"]["message"]
    doc = make_doc()
    find(doc, "Komponen WACC")["data"]["rows"].append(["WACC tersirat harga kini", "13,0%"])
    assert failed(doc)["T4.wacc_rows"]["severity"] == T.WARNING


def test_sensitivity_base_cell_must_equal_fair_value():
    doc = make_doc()
    find(doc, "Sensitivitas nilai DCF")["data"]["rows"][2][2] = "Rp1.500"
    assert failed(doc)["T4.sensitivity_grid_base_highlight"]["blocker"]
    doc = make_doc()
    s = find(doc, "Sensitivitas nilai DCF")
    s["data"]["rows"] = s["data"]["rows"][1:4]
    assert failed(doc)["T4.sensitivity_grid_shape"]["severity"] == T.WARNING


def test_ddm_uses_cost_of_equity_and_complete_blocks():
    doc = make_doc("financial_ddm")
    row(find(doc, "Proyeksi dividen"), "Faktor diskonto")[0] = "Faktor diskonto (WACC 10,9%)"
    assert "WACC" in failed(doc)["T4.ddm_blocks"]["message"]
    doc = make_doc("financial_ddm")
    div = find(doc, "Proyeksi dividen")
    div["data"]["rows"] = [r for r in div["data"]["rows"] if r[0] != "Payout ratio"]
    assert "payout" in failed(doc)["T4.ddm_rows"]["message"]
    doc = make_doc("financial_ddm")
    coe = find(doc, "Komponen Cost of Equity")
    coe["data"]["rows"] = [r for r in coe["data"]["rows"] if not r[0].startswith("Equity Risk")]
    assert failed(doc)["T4.coe_components"]["blocker"]


def test_rnav_bridge_rows_and_asset_rates():
    doc = make_doc("finite_life_mining")
    sotp = find(doc, "SOTP/LoM")
    sotp["data"]["rows"] = [r for r in sotp["data"]["rows"] if not r[0].startswith("Nilai per saham")]
    assert "per saham" in failed(doc)["T4.rnav_bridge"]["message"]
    doc = make_doc("finite_life_mining")
    sotp = find(doc, "SOTP/LoM")
    sotp["data"]["cols"][1] = "Ukuran"
    sotp["data"]["rows"] = [r for r in sotp["data"]["rows"] if not r[0].startswith("Diskon")]
    assert failed(doc)["T4.rnav_rows"]["severity"] == T.WARNING
    doc = make_doc("finite_life_mining")
    doc["bagian"][1]["exhibit"] = [e for e in doc["bagian"][1]["exhibit"] if e["judul"] != "Tingkat diskonto per aset"]
    for r in find(doc, "SOTP/LoM")["data"]["rows"]:
        r[3] = "nilai buku"
    doc["exhibits"] = T.reading_order(doc)
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    assert failed(doc)["T4.discount_rate_per_asset"]["severity"] == T.WARNING


def test_discount_rate_sources_currency_and_growth_cap():
    doc = make_doc()
    w = find(doc, "Komponen WACC")
    for r in w["data"]["rows"]:
        r[0] = r[0].replace(" (Bloomberg)", "").replace(" (Damodaran)", "")
    w["catatan_sumber"] = SRC
    assert failed(doc)["T4.rf_beta_erp_sources"]["severity"] == T.WARNING
    doc = make_doc()
    assert "T4.discount_rate_currency" not in failed(doc)
    assert failed(doc, currency="USD")["T4.discount_rate_currency"]["blocker"]
    doc = make_doc()
    find(doc, "Komponen WACC")["data"]["rows"].insert(3, ["Country risk premium", "2,0%"])
    assert failed(doc)["T4.discount_rate_currency"]["blocker"]
    doc = make_doc()
    find(doc, "Nilai terminal")["data"]["cols"][1] = "Gordon g 7,0% (basis)"
    row(find(doc, "Nilai terminal"), "Pertumbuhan terminal")[1] = "7,0%"
    assert failed(doc)["T4.terminal_growth_cap"]["blocker"]


def test_fcf_far_from_fcff_warns():
    doc = make_doc()
    row(find(doc, "Proyeksi FCFF"), "FCFF")[1:4] = ["950,0", "1.000,0", "1.060,0"]
    assert failed(doc)["T4.fcf_vs_fcff"]["severity"] == T.WARNING


# ------------------------------------------------------------ T5

def test_peer_table_median_average_issuer_asof():
    doc = make_doc()
    comp = find(doc, "Perbandingan peer")
    comp["data"]["rows"] = [r for r in comp["data"]["rows"] if not r[0].startswith("Median")]
    comp["catatan_sumber"] = SRC
    msg = failed(doc)["T5.peer_table_median_average_highlight_asof_criteria"]["message"]
    assert "Median" in msg and "kriteria" in msg and "as of" in msg


def test_non_idx_peers_block():
    doc = make_doc()
    row(find(doc, "Grup peer"), "Beta")[1] = "NYSE"
    assert failed(doc)["T5.peers_idx_only"]["blocker"]
    doc = make_doc()
    row(find(doc, "Perbandingan peer"), "Gamma")[0] = "FCX"
    assert "FCX" in failed(doc)["T5.peers_idx_only"]["message"]


def test_peer_values_follow_the_method_chain():
    doc = make_doc()
    chain = find(doc, "Rantai metode")
    chain["data"]["rows"].append(["3. P/BV buku", "Tidak dijalankan", "-", "peer P/B valid kurang dari tiga"])
    xcheck = ex(0, "Cross-check nilai per saham dengan multiple peer", ["Basis", "Multiple", "Nilai per saham"],
                [["P/B median peer x BVPS 2026-06-30", "1,3x", "Rp990"]])
    doc["bagian"][2]["exhibit"].insert(2, xcheck)
    doc["exhibits"] = T.reading_order(doc)
    for n, e in enumerate(doc["exhibits"], 1):
        e["n"] = n
    assert "tidak menjalankan P/B" in failed(doc)["T5.peer_crosscheck_consistency"]["message"]


def test_peer_median_needs_three_valid_multiples():
    doc = make_doc()
    row(find(doc, "Perbandingan peer"), "Alfa")[2] = "73,2x"
    row(find(doc, "Perbandingan peer"), "Beta")[2] = "n.m."
    find(doc, "Perbandingan peer")["catatan_sumber"] += " n.m. = rugi."
    assert failed(doc)["T5.peer_crosscheck_consistency"]["blocker"]


def test_band_implied_disclaimer_and_narrative_warn():
    doc = make_doc()
    band = next(e for e in doc["exhibits"] if e["tipe"] == "band_chart")
    band["data"]["dates"] = band["data"]["dates"][-4:]
    band["data"]["values"] = band["data"]["values"][-4:]
    tbl = find(doc, "Band historis")
    tbl["data"]["rows"] = tbl["data"]["rows"][:1]
    doc["bagian"][2]["paragraf"] = ["Peer dibandingkan."]
    tbl["judul"] = "Band historis 12 bulan P/E dan P/BV"
    f = failed(doc)
    for cid in ("T5.hist_bands_mean_median_marker", "T5.implied_price_mean_median_two_multiples",
                "T5.disclaimer", "T5.peer_narrative"):
        assert f[cid]["severity"] == T.WARNING, cid


# ------------------------------------------------------------ T6/T7

def test_income_statement_lines_and_order():
    doc = make_doc()
    lr = find(doc, "Laba rugi")
    lr["data"]["rows"] = [r for r in lr["data"]["rows"] if r[0] != "Laba kotor"]
    assert "gross_profit" in failed(doc)["T6.income_statement_lines"]["message"]
    doc = make_doc()
    rows = find(doc, "Laba rugi")["data"]["rows"]
    rows[0], rows[2] = rows[2], rows[0]
    assert failed(doc)["T6.income_statement_order"]["severity"] == T.WARNING


def test_balance_sheet_must_balance_and_subtotals_add_up():
    doc = make_doc()
    row(find(doc, "Neraca"), "Total liabilitas dan ekuitas")[4] = "1.100"
    assert "tidak seimbang" in failed(doc)["T6.balance_sheet_lines_and_balance"]["message"]
    doc = make_doc()
    row(find(doc, "Neraca"), "Total aset lancar")[2] = "999"
    assert failed(doc)["T6.balance_sheet_subtotals"]["severity"] == T.WARNING


def test_balancing_debt_above_a_quarter_of_equity_is_a_warning():
    doc = make_doc()
    assert results(doc)["T6.balancing_debt_share"]["status"] == T.PASS
    bs = find(doc, "Neraca")
    at = next(i for i, r in enumerate(bs["data"]["rows"]) if r[0] == "Utang jangka pendek")
    # Equity FY26F-FY28F = 550, 610, 680; the memo line is part of short-term debt.
    bs["data"]["rows"].insert(at + 1, ["Termasuk pinjaman penyeimbang kas (memo)", "n.m.",
                                       "n.m.", "40", "100", "150"])
    assert results(doc)["T6.balancing_debt_share"]["status"] == T.PASS
    bs["data"]["rows"][at + 1][5] = "400"
    f = failed(doc)["T6.balancing_debt_share"]
    assert f["severity"] == T.WARNING and "2028F 59%" in f["message"]
    assert "T6.balance_sheet_subtotals" not in failed(doc)


def test_bank_balance_sheet_lines():
    doc = make_doc("financial_ddm")
    bs = find(doc, "Neraca bank")
    bs["data"]["rows"] = [r for r in bs["data"]["rows"] if r[0] != "Obligasi pemerintah"]
    assert "govt_bonds" in failed(doc)["T6.balance_sheet_lines_and_balance"]["message"]


def test_cash_flow_forecast_reconciliation_blocks_actual_warns():
    doc = make_doc()
    row(find(doc, "Arus kas"), "Kas akhir")[4] = "999"
    row(find(doc, "Neraca"), "Kas dan setara kas")[4] = "999"
    f = failed(doc)
    assert "rekonsiliasi proyeksi" in f["T7.cash_flow_sections_and_tieout"]["message"]
    doc = make_doc()
    row(find(doc, "Arus kas"), "Perubahan kas bersih")[1] = "30"
    assert failed(doc)["T7.cash_flow_actual_reconciliation"]["severity"] == T.WARNING


def _with_source_gap_lines(doc, cash_gap, flow_gap=None):
    """Insert the explicit source-data reconciling lines into the cash flow."""
    rows = find(doc, "Arus kas")["data"]["rows"]
    at = rows.index(row(find(doc, "Arus kas"), "Kas akhir"))
    rows.insert(at, _row("Efek kurs dan selisih definisi kas (data sumber)", cash_gap))
    if flow_gap:
        at = rows.index(row(find(doc, "Arus kas"), "Perubahan kas bersih"))
        rows.insert(at, _row("Selisih komponen arus kas (data sumber)", flow_gap))
    return doc


def test_cash_flow_actual_gap_reconciles_through_an_explicit_source_line():
    # 2024A: Sectors end cash 130 = begin 80 + change 20 + a 30 FX/definition gap.
    doc = make_doc()
    row(find(doc, "Arus kas"), "Kas akhir")[1] = "130"
    row(find(doc, "Arus kas"), "Kas awal")[2] = "130"
    row(find(doc, "Neraca"), "Kas dan setara kas")[1] = "130"
    assert "T7.cash_flow_actual_reconciliation" in failed(doc)
    _with_source_gap_lines(doc, [30, -30, 0, 0, 0])   # 2025A opens at the 130 again
    res = results(doc)
    check = res["T7.cash_flow_actual_reconciliation"]
    assert check["status"] != T.FAIL and "2024A" in check["message"], check
    assert res["T7.cash_flow_sections_and_tieout"]["status"] != T.FAIL


def test_cash_flow_component_gap_line_bridges_cfo_cfi_cff_to_net_change():
    doc = make_doc()
    row(find(doc, "Arus kas"), "Perubahan kas bersih")[2] = "0"   # source reports 0
    row(find(doc, "Arus kas"), "Kas awal")[2] = "100"
    _with_source_gap_lines(doc, [0, 50, 0, 0, 0], flow_gap=[0, -50, 0, 0, 0])
    assert "T7.cash_flow_actual_reconciliation" not in failed(doc)


def test_cash_flow_source_gap_line_never_plugs_a_forecast_year():
    doc = _with_source_gap_lines(make_doc(), [0, 0, 5, 0, 0])
    row(find(doc, "Arus kas"), "Kas akhir")[3] = "205"
    msg = failed(doc)["T7.cash_flow_sections_and_tieout"]["message"]
    assert "terisi pada 2026F" in msg


def test_cash_flow_gap_line_needs_the_source_data_label():
    doc = make_doc()
    row(find(doc, "Arus kas"), "Kas akhir")[1] = "130"
    row(find(doc, "Arus kas"), "Kas awal")[2] = "130"
    row(find(doc, "Neraca"), "Kas dan setara kas")[1] = "130"
    rows = find(doc, "Arus kas")["data"]["rows"]
    rows.insert(rows.index(row(find(doc, "Arus kas"), "Kas akhir")),
                _row("Penyesuaian kas", [30, 0, 0, 0, 0]))
    assert "T7.cash_flow_actual_reconciliation" in failed(doc)


def _swap_band(doc, reason_stated=True):
    """Replace the P/BV band with an EV/EBITDA band (as for a negative book)."""
    chart = next(e for e in doc["exhibits"] if e["tipe"] == "band_chart" and e["data"]["label"] == "P/BV")
    chart["data"]["label"] = "EV/EBITDA"
    chart["judul"] = "Band EV/EBITDA 12 bulan TEST"
    table = find(doc, "Band historis")
    table["data"]["rows"][1] = ["P/BV", "3,6x", "3,5x", "3,5x (p52)", "Rp57 / Rp56"]
    table["data"]["rows"].append(["EV/EBITDA", "8,0x", "7,9x", "7,5x (p40)", "Rp1.050 / Rp1.030"])
    table["judul"] = "Band historis 12 bulan P/E, P/BV dan EV/EBITDA (bukan target harga)"
    if reason_stated:
        why = (" EV/EBITDA menggantikan band P/BV karena basis BVPS tidak positif sebelum "
               "2026-03-31, sehingga band P/BV hanya 6 bulan.")
        chart["catatan_sumber"] += why
        table["catatan_sumber"] += why
    return doc


def test_band_substitute_counts_only_with_a_stated_reason():
    res = results(_swap_band(make_doc()))
    bands = res["T5.hist_bands_mean_median_marker"]
    assert bands["status"] != T.FAIL and "EV/EBITDA menggantikan P/BV" in bands["message"]
    assert res["T5.implied_price_mean_median_two_multiples"]["status"] != T.FAIL
    f = failed(_swap_band(make_doc(), reason_stated=False))
    assert "P/BV" in f["T5.hist_bands_mean_median_marker"]["message"]


def test_band_substitute_still_needs_two_multiples_with_implied_prices():
    doc = _swap_band(make_doc())
    rows = find(doc, "Band historis")["data"]["rows"]
    rows[0][4] = "n.m."
    rows[1][4] = "n.m."
    assert "T5.implied_price_mean_median_two_multiples" in failed(doc)
    doc = _swap_band(make_doc())
    find(doc, "Band historis")["catatan_sumber"] = SRC   # substitution not stated in the table
    find(doc, "Band historis")["data"]["rows"][0][4] = "n.m."
    msg = failed(doc)["T5.implied_price_mean_median_two_multiples"]["message"]
    assert "pengganti tanpa alasan" in msg


def test_key_ratio_lines_and_format():
    doc = make_doc()
    ratio = find(doc, "Rasio utama")
    ratio["data"]["rows"] = [r for r in ratio["data"]["rows"] if r[0] != "ROAE"]
    assert failed(doc)["T7.key_ratio_sections_format"]["blocker"]
    doc = make_doc()
    row(find(doc, "Rasio utama"), "ROAA")[2] = "20%"
    assert failed(doc)["T7.key_ratio_format"]["severity"] == T.WARNING


def test_statement_tieouts():
    doc = make_doc()
    row(find(doc, "Arus kas"), "Kas akhir")[3] = "205"
    row(find(doc, "Arus kas"), "Kas awal")[4] = "205"
    row(find(doc, "Arus kas"), "Perubahan kas bersih")[3] = "55"
    row(find(doc, "Arus kas"), "Perubahan kas bersih")[4] = "55"
    row(find(doc, "Arus kas"), "Jumlah arus kas pendanaan")[3] = "(36)"
    row(find(doc, "Arus kas"), "Jumlah arus kas pendanaan")[4] = "(48)"
    assert "kas akhir AK vs kas neraca" in failed(doc)["T7.tieouts"]["message"]
    doc = make_doc()
    row(find(doc, "Laba rugi"), "Laba bersih")[4] = "140"
    assert "laba bersih LR vs KF" in failed(doc)["T7.tieouts"]["message"]


# ------------------------------------------------------------ run_all

def _run_all(doc, monkeypatch, **kw):
    from test_harness_gates import _intake_fcff
    from app import render
    from app.harness import runner
    monkeypatch.setattr(render, "render", lambda d: "<html><body></body></html>")
    intake, fc = _intake_fcff()
    va = {"tp": 1200.0, "tp_down": 1000.0, "s3": {}, "method_chain": {"selected": "fcff_dcf"}}
    return runner.run_all(intake, fc, va, doc, **kw)


def test_run_all_adds_template_blockers_and_fails_closed(monkeypatch):
    doc = make_doc()
    row(find(doc, "Neraca"), "Piutang usaha")[4] = "NA"
    out = _run_all(doc, monkeypatch)
    assert out["status"] == "draft_non_distributable"
    assert any(b.startswith("T.TF.forecast_cells:") for b in out["blockers"])
    # The empty rendering fails the rendered-report checks too.
    assert any(b.startswith("T.T1.source_line:") for b in out["blockers"])
    assert out["log_gate"]["template"]["TF.forecast_cells"] == "gagal"


def test_run_all_template_switch(monkeypatch):
    doc = make_doc()
    row(find(doc, "Neraca"), "Piutang usaha")[4] = "NA"
    out = _run_all(doc, monkeypatch, template_checks=False)
    assert not any(b.startswith("T.") for b in out["blockers"])
    from app.harness import template
    monkeypatch.setattr(template, "ENABLED", False)
    out = _run_all(doc, monkeypatch)
    assert not any(b.startswith("T.") for b in out["blockers"])


def test_run_all_render_failure_is_a_blocker(monkeypatch):
    from test_harness_gates import _intake_fcff
    from app import render
    from app.harness import runner

    def boom(_doc):
        raise KeyError("cover")
    monkeypatch.setattr(render, "render", boom)
    intake, fc = _intake_fcff()
    out = runner.run_all(intake, fc, {"s3": {}}, make_doc())
    assert any(b.startswith("T.R.render_error:") for b in out["blockers"])


def test_doc_is_not_mutated():
    doc = make_doc()
    before = copy.deepcopy(doc)
    T.check_template(doc)
    assert doc == before
