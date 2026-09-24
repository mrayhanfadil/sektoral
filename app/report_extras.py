"""Report sections built from local Sectors data after the narrative pass.

``narrative.build`` owns the issuer story and valuation. This module adds the
spec sections that come straight from the Sectors snapshot (industry and
commodity prices, peer comparison, ownership and market activity, financial
statements), a price/FX sensitivity for the assumption-led mining target,
market data for the cover, and then orders pages as the spec lays them out
and renumbers exhibits in reading order.
"""
from __future__ import annotations

import re
import statistics
from datetime import date, timedelta

from agents.analyst import signals as S
from agents.analyst import tools as peer_tools
from agents.estimator import tools as local_data

from . import cache, fmt, method_chain

TAX_RATE = 0.22  # Indonesian statutory corporate rate, used only for the sensitivity note
# "USD" rather than "US$": the report keeps "$" out of rupiah-only drafts (spec §5.3).
COMMODITY_UNITS = {"Copper": ("Tembaga", "USD/ton"), "Gold": ("Emas", "USD/oz"),
                   "Nickel": ("Nikel", "USD/ton"), "Coal": ("Batu bara", "USD/ton")}
# Page order from spec §5.4, matched on page title prefixes.
PAGE_ORDER = ("Tesis investasi", "Hasil terbaru", "Operasi", "Industri", "Kinerja keuangan", "Forecast", "Skenario FY26",
              "Skenario operasi", "Skenario laba", "Berita", "Sensitivitas", "Katalis",
              "Konteks historis", "Target harga", "Cross-check", "Skenario nilai",
              "Perbandingan peer", "Valuasi", "Data keuangan")


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _rp_bn(value, decimals=0):
    return "-" if value is None else fmt._id(value / 1e9, decimals)


def _signed_pct(value, cap=None):
    if value is None:
        return "-"
    if cap is not None and abs(value) > cap:
        return "n.m."
    return fmt.pct(value)


def _exhibit(title, columns, rows, source):
    return {"n": 0, "judul": title, "tipe": "tabel",
            "data": {"cols": columns, "rows": rows}, "catatan_sumber": source}


def _page(title, paragraphs, exhibits):
    return {"halaman": 0, "judul": title, "layout": "stack",
            "paragraf": [p for p in paragraphs if p], "exhibit": exhibits}


# ------------------------------------------------------------ method chain

_DECISION = {"selected": "Terpilih", "stop_extreme": "Terpilih, ekstrem (rantai berhenti)",
             "skipped": "Dilewati", "cross_check": "Silang cek", "not_needed": "Tidak dijalankan"}


def method_chain_exhibit(va):
    """Rantai metode §4.1a: urutan, keputusan, dan alasan tiap metode.

    Nilai per saham hanya tampil bila rilis lolos; draft menahan angka.
    Menampilkan usulan sistem vs override analis bila ada.
    """
    chain = (va or {}).get("method_chain") or {}
    trace = chain.get("trace") or []
    if not trace:
        return None
    released = ((va.get("release") or {}).get("status") or "").startswith("distributable")
    rows = []
    for t in trace:
        value = (f"Rp{fmt.rp(fmt.tick(t['per_share']))}"
                 if released and t.get("per_share") and t["decision"] in
                 ("selected", "cross_check")
                 else "ditahan" if (t.get("per_share") and not released
                                    and t["decision"] in ("selected", "cross_check", "stop_extreme"))
                 else "-")
        why = (method_chain.reader_reason(t["reasons"][0]) if t.get("reasons")
               else "; ".join(t.get("labels") or []) or "input lengkap")
        role_tag = ""
        if t["role"] == "primary":
            role_tag = " (utama)"
        elif t["role"] == "override":
            role_tag = " (override analis)"
        rows.append([f"{t['rank']}. {t['short']}" + role_tag,
                     _DECISION.get(t["decision"], t["decision"]), value, why])
    source = ("Source: Sektoral Estimates; urutan metode dikunci dari verdict Gates 0-5 "
              "sebelum nilai dihitung; metode berikutnya hanya dipakai bila metode "
              "sebelumnya tidak memadai, bukan karena hasilnya tidak disukai")
    override = chain.get("override")
    if override:
        proposed = (chain.get("proposed_order") or [None])[0]
        source += f"; Usulan sistem: {proposed}; dipilih analis: {override}."
    # Brand constant: Sectoral (keputusan branding fase ini).
    return _exhibit("Rantai metode valuasi",
                    ["Metode", "Keputusan", "Nilai/saham", "Alasan"], rows, source)


def attach_method_chain(doc, va):
    exhibit = method_chain_exhibit(va)
    if not exhibit:
        return
    page = next((p for prefix in ("Target harga", "Valuasi", "Skenario nilai")
                 for p in doc["bagian"] if str(p.get("judul", "")).startswith(prefix)), None)
    if page is None:
        doc["bagian"].append(_page(
            "Valuasi: rantai metode",
            ["Metode utama dan fallback dinilai berurutan; tabel mencatat metode yang "
             "dipakai dan alasan metode lain dilewati."], [exhibit]))
    else:
        page["exhibit"].append(exhibit)


# ------------------------------------------------------------ cover data

def _adtv_3m(ticker):
    rows = ((local_data.cache_get(ticker, f"/daily/{ticker}/") or {}).get("data") or [])
    values = [_num(r.get("close")) * _num(r.get("volume")) for r in rows[-60:]
              if isinstance(r, dict) and _num(r.get("close")) and _num(r.get("volume"))]
    return statistics.mean(values) if values else None


def _holders(intake):
    rows = []
    for holder in intake.get("major_holders") or []:
        pct = _num(holder.get("share_percentage"))
        if pct is None or not holder.get("name"):
            continue
        rows.append((str(holder["name"]), pct if pct > 1 else pct * 100))
    return rows


def cover_market_data(doc, intake):
    data = doc["cover"].setdefault("data_pasar", {})
    # Price box: shares, mcap Rp/US$, ADTV 3m fixed, free float, major >5%.
    if intake.get("shares") and "saham" not in data:
        data["saham"] = intake["shares"]
    if intake.get("market_cap") and "market_cap" not in data:
        data["market_cap"] = intake["market_cap"]
    adtv = _adtv_3m(intake["ticker"])
    if adtv:
        data["adtv"] = fmt._id(adtv / 1e9, 1)
    holders = _holders(intake)
    public = next((pct for name, pct in holders if name.lower() in ("public", "publik", "masyarakat")), None)
    if public is not None:
        data["free_float"] = fmt._id(public, 1)
    # Major shareholders >5% (plan Slide 1).
    majors = [(n, p) for n, p in holders if p is not None and p > 5.0
              and n.lower() not in ("public", "publik", "masyarakat")]
    doc["holders"] = [[name, fmt._id(pct, 1) + "%"] for name, pct in majors[:5]]


# -------------------------------------------------------- industry page

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def _series(name):
    rows = []
    for _key, payload in cache.payloads(f"/mining/commodities/{name}/price/"):
        if isinstance(payload, list):
            rows = payload
    points = []
    for row in rows:
        price = _num((row or {}).get("price_usd_per_ton"))
        try:
            day = date.fromisoformat(str(row.get("date"))[:10])
        except (TypeError, ValueError):
            continue
        if price:
            points.append((day, price))
    return sorted(points)


def _year_average(points, year):
    values = [p for d, p in points if d.year == year]
    return statistics.mean(values) if values else None


def _change_12m(points):
    if len(points) < 2:
        return None
    last_day, last = points[-1]
    earlier = [p for d, p in points if (last_day - d).days >= 330]
    return last / earlier[-1] - 1 if earlier else None


def _commodities(intake):
    mineops = intake.get("mineops") or {}
    names = []
    for name, stats in (mineops.get("comms") or {}).items():
        if name in COMMODITY_UNITS:
            names.append(name)
        if (stats or {}).get("au_cont_koz"):
            names.append("Gold")
    return [n for n in dict.fromkeys(names) if _series(n)]


def industry_page(intake):
    exhibits, paragraphs = [], []
    if intake.get("model_profile") == "finite_life_mining":
        names = _commodities(intake)
        if names:
            series = {n: _series(n) for n in names}
            last_years = sorted({d.year for pts in series.values() for d, _ in pts})[-3:]
            rows = [["Titik data terakhir"] + [series[n][-1][0].isoformat() for n in names],
                    ["Harga terakhir"] + [fmt._id(series[n][-1][1], 0) for n in names]]
            for year in last_years:
                rows.append([f"Rata-rata {year}"] +
                            [fmt._id(_year_average(series[n], year), 0)
                             if _year_average(series[n], year) else "-" for n in names])
            rows.append(["Perubahan 12 bulan"] + [_signed_pct(_change_12m(series[n])) for n in names])
            cols = ["Metrik"] + [f"{COMMODITY_UNITS[n][0]} ({COMMODITY_UNITS[n][1]})" for n in names]
            exhibits.append(_exhibit(
                "Harga komoditas utama emiten", cols, rows,
                "Sumber: Sectors, mining/commodities/{nama}/price (data bulanan). Harga emas "
                "dibaca sebagai USD/oz sesuai besaran datanya; titik data terakhir tiap seri "
                "dapat berbeda."))
            for name in names:
                label, unit = COMMODITY_UNITS[name]
                day, price = series[name][-1]
                change = _change_12m(series[name])
                paragraphs.append(
                    f"Harga {label.lower()} USD {fmt._id(price, 0)}/{unit.split('/')[1]} pada "
                    f"{day.isoformat()}" + (f", {'naik' if change >= 0 else 'turun'} "
                                            f"{fmt.pct(abs(change))} dalam 12 bulan." if change is not None
                                            else "."))
            paragraphs.append(
                ("Kedua harga ini" if len(names) == 2 else "Harga ini") +
                " menjadi driver harga realisasi emiten; dampaknya ke EBITDA, "
                "laba bersih dan nilai per saham diuji pada tabel sensitivitas.")
    report = None
    for _key, payload in cache.payloads(f"/subsector/report/{_slug(intake.get('sub_sector'))}/"):
        report = payload if isinstance(payload, dict) else report
    if report:
        history = ((report.get("valuation") or {}).get("historical_valuation") or {})
        growth = ((report.get("growth") or {}).get("weighted_avg_growth_data") or {})
        years = sorted(y for y in history if y.isdigit())[-5:]
        rows = [[y, fmt.mult(_num(history[y].get("pe")) or 0) if _num(history[y].get("pe")) else "-",
                 fmt.mult(_num(history[y].get("pb")) or 0) if _num(history[y].get("pb")) else "-",
                 _signed_pct(_num((growth.get(y) or {}).get("avg_annual_revenue_growth")), cap=5),
                 _signed_pct(_num((growth.get(y) or {}).get("avg_annual_earning_growth")), cap=5)]
                for y in years]
        name = report.get("sub_sector") or intake.get("sub_sector")
        exhibits.append(_exhibit(
            f"Valuasi dan pertumbuhan sub-sektor {name}",
            ["Tahun", "P/E sub-sektor", "P/B sub-sektor", "Pertumbuhan pendapatan",
             "Pertumbuhan laba"], rows,
            f"Sumber: Sectors, subsector/report/{_slug(name)}; pertumbuhan adalah rata-rata "
            "tertimbang emiten di sub-sektor; n.m. bila di atas 500% karena basis rendah."))
        if years:
            last = history[years[-1]]
            forecasts = ((report.get("growth") or {}).get("growth_forecasts") or {})
            paragraphs.append(
                f"Sub-sektor {name} diperdagangkan pada P/E {fmt.mult(_num(last.get('pe')) or 0)} "
                f"dan P/B {fmt.mult(_num(last.get('pb')) or 0)} pada {years[-1]}.")
            for year, item in sorted(forecasts.items())[-1:]:
                eps, rev = _num(item.get("eps_growth")), _num(item.get("revenue_growth"))
                if eps is not None and rev is not None:
                    paragraphs.append(
                        f"Proyeksi Sectors untuk {year} memperkirakan EPS sub-sektor "
                        f"{'naik' if eps >= 0 else 'turun'} {fmt.pct(abs(eps))} dengan pendapatan "
                        f"{'naik' if rev >= 0 else 'turun'} {fmt.pct(abs(rev))}.")
    if not exhibits:
        return None
    return _page("Industri dan harga komoditas", paragraphs, exhibits)


# ------------------------------------------------------------ peer page

def peer_page(intake, valuation_inputs=None):
    ticker = intake["ticker"]
    peers = peer_tools.find_peers(ticker)
    rows = peers.get("rows") or []
    if len(rows) < 3 or not any(r["is_self"] for r in rows):
        return None
    ranked = {s["id"]: s for s in S.rank_peers(
        rows, ["market_cap", "pe", "pb", "roe", "net_margin", "leverage"], peers["source"])}
    m = lambda row, key, kind: ("-" if row["metrics"].get(key) is None else
                                _signed_pct(row["metrics"][key], cap=5) if kind == "pct" else
                                fmt.mult(row["metrics"][key]) if kind == "x" else
                                _rp_bn(row["metrics"][key]))
    table = []
    for row in sorted(rows, key=lambda r: r["metrics"].get("market_cap") or 0, reverse=True):
        label = row["symbol"] + (" (emiten)" if row["is_self"] else "")
        table.append([label, m(row, "market_cap", "rp"), m(row, "pe", "x"), m(row, "pb", "x"),
                      m(row, "roe", "pct"), m(row, "net_margin", "pct"), m(row, "leverage", "x")])
    median_row, avg_row, rank_row = (["Median peer (tanpa emiten)"],
                                     ["Rata-rata peer (tanpa emiten)"],
                                     [f"Peringkat {ticker}"])
    for key, kind in (("market_cap", "rp"), ("pe", "x"), ("pb", "x"), ("roe", "pct"),
                      ("net_margin", "pct"), ("leverage", "x")):
        signal = ranked.get(f"peer.{key}") or {}
        median = signal.get("median")
        median_row.append("-" if median is None else
                          fmt.pct(median) if kind == "pct" else
                          fmt.mult(median) if kind == "x" else _rp_bn(median))
        # Average: mean of valid metrics, excluding outliers >100x for PE.
        vals = [r["metrics"].get(key) for r in rows if not r["is_self"]]
        vals = [v for v in vals if isinstance(v, (int, float)) and v == v]
        if key == "pe":
            vals = [v for v in vals if 0 < v <= 100]
        avg = sum(vals) / len(vals) if vals else None
        avg_row.append("-" if avg is None else
                       fmt.pct(avg) if kind == "pct" else
                       fmt.mult(avg) if kind == "x" else _rp_bn(avg))
        rank_row.append(f"{signal['rank']}/{signal['n']}" if signal.get("rank") else "-")
    table += [median_row, avg_row, rank_row]
    exhibits = [_exhibit(
        f"Perbandingan peer {peers.get('group') or ''}".strip(),
        ["Emiten", "Kap. pasar (Rp miliar)", "P/E (x)", "P/B (x)", "ROE", "Margin bersih",
         "Liabilitas/ekuitas (x)"], table,
        f"Sumber: {peers['source']} ({peers['basis']}); per {intake.get('as_of') or intake.get('price_date') or '-'}; "
        "kriteria: model bisnis dan eksposur sebanding, kapitalisasi sebanding, outlier dijelaskan; "
        "P/E negatif tidak diperingkat; rasio di atas 500% ditulis n.m. karena basis pendapatan atau ekuitas sangat kecil. "
        "Rasio dihitung dari laba, ekuitas, pendapatan dan liabilitas tabel peer. "
        "Emiten yang dibahas disorot '(emiten)'.")]
    caps = [r["metrics"]["market_cap"] for r in rows if r["metrics"].get("market_cap")]
    caps = [r["metrics"]["market_cap"] for r in rows if r["metrics"].get("market_cap")]
    subject = next(r for r in rows if r["is_self"])
    paragraphs = [
        f"Grup peer berisi {len(rows)} emiten dengan kapitalisasi Rp{_rp_bn(min(caps))} "
        f"miliar sampai Rp{_rp_bn(max(caps))} miliar." if caps else "",
    ]
    pe_signal, roe_signal = ranked.get("peer.pe") or {}, ranked.get("peer.roe") or {}
    if pe_signal.get("value") is not None and pe_signal.get("median"):
        paragraphs.append(
            f"P/E {ticker} {fmt.mult(pe_signal['value'])} dibanding median peer "
            f"{fmt.mult(pe_signal['median'])}, sementara ROE berada di peringkat "
            f"{roe_signal.get('rank') or '-'} dari {roe_signal.get('n') or '-'}.")
    outliers = [r["symbol"] for r in rows if (r["metrics"].get("pe") or 0) > 100]
    negative = [r["symbol"] for r in rows if r["metrics"].get("pe") is None and not r["is_self"]]
    if outliers or negative:
        paragraphs.append(
            "Pencilan: " + ", ".join(
                ([f"P/E di atas 100x ({', '.join(outliers)})"] if outliers else []) +
                ([f"laba negatif atau P/E tidak tersedia ({', '.join(negative)})"] if negative else []))
            + "; median dipakai agar pencilan tidak mendominasi.")
    cross = []
    inputs = valuation_inputs or {}
    if inputs.get("eps_idr") and pe_signal.get("median"):
        implied = pe_signal["median"] * inputs["eps_idr"]
        cross.append([f"P/E median peer x EPS {inputs['label']}", fmt.mult(pe_signal["median"]),
                      f"Rp{fmt.rp(fmt.tick(implied))}"])
    pb_signal = ranked.get("peer.pb") or {}
    if inputs.get("bvps_idr") and pb_signal.get("median"):
        implied = pb_signal["median"] * inputs["bvps_idr"]
        cross.append([f"P/B median peer x BVPS {inputs.get('bvps_period', 'terakhir')}",
                      fmt.mult(pb_signal["median"]), f"Rp{fmt.rp(fmt.tick(implied))}"])
    if cross:
        if inputs.get("tp"):
            cross.append(["Target harga metode utama", inputs.get("method_label", "-"),
                          f"Rp{fmt.rp(inputs['tp'])}"])
        exhibits.append(_exhibit(
            "Cross-check nilai per saham dengan multiple peer",
            ["Basis", "Multiple", "Nilai per saham"], cross,
            "Sumber: tabel peer Sectors dan estimasi Sektoral. Cross-check tidak dirata-ratakan "
            "dengan metode utama; P/E dan P/B peer bukan EV/EBITDA dan berbeda struktur modal."))
        paragraphs.append(
            "Multiple peer di bawah ini hanya cross-check: tabel peer Sectors tidak memuat "
            "EBITDA dan utang bersih, sehingga EV/EBITDA peer belum dapat diverifikasi.")
    # 1-year own-history P/E and P/BV bands (mean, median, current, percentile).
    band = own_history_bands(intake)
    if band:
        exhibits.append(band)
    else:
        paragraphs.append("Band historis P/E dan P/BV 1 tahun belum dimodelkan: "
                          "cache membutuhkan harga harian + EPS/BVPS TTM yang sebanding; "
                          "cakupan saat ini tidak cukup.")
    return _page("Perbandingan peer", paragraphs, exhibits)


PUBLICATION_LAG_DAYS = 90  # annual results assumed public ~3 months after FY end


def own_history_bands(intake):
    """1y own-history P/E and P/BV bands; None bila cache tidak cukup.

    Each close is divided by the annual EPS/BVPS that was already published
    on that date (FY end + PUBLICATION_LAG_DAYS), so the multiple moves with
    both price and fundamentals. When one base covers the whole window the
    series is only a rescaled price band: the row says so instead of showing
    a reversion "implied price" that would equal the average close.
    """
    try:
        daily = (local_data.cache_get(intake["ticker"], f"/daily/{intake['ticker']}/") or {}).get("data") or []
    except Exception:
        daily = []
    shares = intake.get("shares") or 0
    annuals = [a for a in intake.get("annuals") or [] if isinstance(a.get("year"), int)]
    if len(daily) < 60 or len(annuals) < 2 or not shares:
        return None
    points = []
    for row in daily[-250:]:
        day = _day(row.get("date")) if isinstance(row, dict) else None
        close = _num(row.get("close")) if isinstance(row, dict) else None
        if day and close:
            points.append((day, close))
    if len(points) < 60:
        return None

    def base_on(day, key):
        known = [a for a in annuals
                 if date(a["year"], 12, 31) + timedelta(days=PUBLICATION_LAG_DAYS) <= day
                 and isinstance(a.get(key), (int, float))]
        return known[-1][key] / shares if known else None

    rows = []
    for label, key in (("P/E", "earnings"), ("P/BV", "equity")):
        series = [(close / base, base) for day, close in points
                  for base in [base_on(day, key)] if base and base > 0]
        if len(series) < 60:
            rows.append([label, "belum dimodelkan", "belum dimodelkan",
                         "belum dimodelkan", "basis fundamental historis tidak cukup"])
            continue
        mults = sorted(m for m, _ in series)
        mean, med = sum(mults) / len(mults), statistics.median(mults)
        cur, base_now = series[-1]
        pct = sum(1 for m in mults if m <= cur) / len(mults) * 100
        if len({round(b, 6) for _, b in series}) == 1:
            implied = ("belum dimodelkan: basis tetap sepanjang jendela, "
                       "band hanya rentang harga")
        else:
            implied = (f"mean Rp{fmt.rp(fmt.tick(mean * base_now))}; "
                       f"median Rp{fmt.rp(fmt.tick(med * base_now))}")
        rows.append([label, f"{mean:.1f}x", f"{med:.1f}x", f"{cur:.1f}x (p{pct:.0f})", implied])
    return _exhibit(
        "Band historis 1 tahun P/E dan P/BV (bukan target harga)",
        ["Multiple", "Mean", "Median", "Kini (persentil)", "Implikasi mean/median"],
        rows,
        f"Source: Sectors daily {intake['ticker']} dan laba/ekuitas tahunan yang sudah "
        f"terbit pada tiap tanggal (akhir tahun buku + {PUBLICATION_LAG_DAYS} hari), saham "
        f"kini sebagai basis pro forma; per {intake.get('as_of') or '-'}; mean/median "
        "reversion hanya konteks, bukan target harga.")


# ------------------------------------------ ownership and market activity

def ownership_exhibits(intake):
    exhibits, paragraphs = [], []
    holders = _holders(intake)
    if holders:
        exhibits.append(_exhibit(
            "Pemegang saham utama", ["Pemegang saham", "Kepemilikan (%)"],
            [[name, fmt._id(pct, 1)] for name, pct in holders[:6]],
            "Sumber: Sectors, company/report, ownership.major_shareholders; komposisi dapat "
            "berbeda dari tanggal laporan interim."))
        top = holders[0]
        paragraphs.append(f"Pemegang saham terbesar adalah {top[0]} dengan {fmt._id(top[1], 1)}% saham.")
    flow_rows = (local_data.cache_get(intake["ticker"], f"/foreign-flow/{intake['ticker']}/") or {}).get("data") or []
    flows = S.flow_signals(intake["ticker"], flow_rows)
    if flows:
        exhibits.append(_exhibit(
            "Aktivitas investor asing", ["Metrik", "Nilai", "Periode"],
            [[s["label"], s["display"], s.get("period") or "-"] for s in flows],
            f"Sumber: Sectors, foreign-flow/{intake['ticker']}; konteks pasar, bukan driver laba."))
        net = next(s for s in flows if s["id"] == "flow.net_20d")
        window = next(s for s in flows if s["id"] == "flow.net_window")
        paragraphs.append(
            f"Investor asing mencatat arus bersih {net['display']} dalam 20 sesi terakhir, "
            f"dibanding {window['display']} sepanjang jendela data.")
    return exhibits, paragraphs


# ------------------------------------------------------------ financials

def financials_page(intake):
    report = cache.company_report(intake["ticker"]) or {}
    history = sorted((r for r in ((report.get("financials") or {}).get("historical_financials") or [])
                      if isinstance(r, dict) and r.get("year")), key=lambda r: r["year"])[-5:]
    if len(history) < 2:
        return None
    years = [str(r["year"]) for r in history]

    def line(label, key):
        return [label] + [_rp_bn(_num(r.get(key))) for r in history]

    def derived(label, fn):
        values = []
        for r in history:
            try:
                values.append(_rp_bn(fn(r)))
            except TypeError:
                values.append("-")
        return [label] + values

    income = [line("Pendapatan", "revenue"), line("Laba kotor", "gross_profit"),
              line("EBITDA", "ebitda"), line("EBIT", "ebit"), line("Pajak", "tax"),
              line("Laba bersih", "earnings")]
    balance = [line("Kas", "cash_only"), line("Aset lancar", "current_assets"),
               line("Aset tetap", "fixed_assets"), line("Total aset", "total_assets"),
               line("Total utang berbunga", "total_debt"), line("Utang bersih", "net_debt"),
               line("Total liabilitas", "total_liabilities"), line("Total ekuitas", "total_equity")]
    cash_flow = [line("Arus kas operasi", "operating_cash_flow"),
                 line("Belanja modal", "capital_expenditure"),
                 line("Arus kas bebas", "free_cash_flow"), line("Arus kas bersih", "net_cash_flow")]
    cash_flow = [row for row in cash_flow if any(cell != "-" for cell in row[1:])]
    ratios = {str(r.get("year")): r for r in ((report.get("financials") or {}).get("historical_financial_ratio") or [])
              if isinstance(r, dict)}
    ratio_rows = []
    for label, group, key in (("ROE", "profitability", "roe"), ("ROA", "profitability", "roa"),
                              ("Margin laba kotor", "profitability", "gross_profit_margin"),
                              ("Margin laba bersih", "profitability", "net_profit_margin"),
                              ("Utang/ekuitas (x)", "leverage", "debt_to_equity_ratio"),
                              ("Rasio lancar (x)", "liquidity", "current_ratio")):
        cells = []
        for year in years:
            value = _num(((ratios.get(year) or {}).get(group) or {}).get(key))
            cells.append("-" if value is None else fmt.mult(value) if "(x)" in label else fmt.pct(value))
        if any(cell != "-" for cell in cells):
            ratio_rows.append([label] + cells)
    note = ("Sumber: Sectors, company/report, financials.historical_financials; nilai dalam "
            "Rp miliar sesuai konversi Sectors, sehingga dapat berbeda dari laporan emiten "
            "dalam mata uang pelaporan.")
    exhibits = [_exhibit("Laba rugi historis", ["Rp miliar"] + years, income, note),
                _exhibit("Neraca historis", ["Rp miliar"] + years, balance, note)]
    if cash_flow:
        exhibits.append(_exhibit("Arus kas historis", ["Rp miliar"] + years, cash_flow, note))
    if ratio_rows:
        exhibits.append(_exhibit("Rasio keuangan utama", ["Rasio"] + years, ratio_rows,
                                 "Sumber: Sectors, company/report, financials.historical_financial_ratio."))
    return _page("Data keuangan", [
        f"Ringkasan laporan keuangan {years[0]} sampai {years[-1]} dari data Sectors; angka "
        "negatif ditampilkan dalam kurung."], exhibits)


# ---------------------------------------------------------- sensitivity

def sensitivity_page(inputs):
    """Price and FX shocks recomputed through EBITDA, net profit and the target."""
    if not inputs or not inputs.get("h2_revenue") or not inputs.get("ebitda_usd"):
        return None
    shocks, fx_shocks = (-0.10, 0.0, 0.10), (-0.05, 0.0, 0.05)
    base_ebitda, base_profit = inputs["ebitda_usd"], inputs.get("net_profit_usd")

    def target(ebitda, fx_shift):
        equity = ebitda * inputs["multiple"] - inputs["net_debt_usd"] - inputs["minority_usd"]
        return fmt.tick(equity / inputs["shares"] * inputs["fx_rate"] * (1 + fx_shift))

    earnings_rows, grid = [], []
    for shock in shocks:
        delta = inputs["h2_revenue"] * shock
        ebitda = base_ebitda + delta
        profit = (base_profit + delta * (1 - TAX_RATE)) if base_profit is not None else None
        label = "Base" if shock == 0 else f"Harga {'+' if shock > 0 else ''}{fmt.pct(shock)}"
        earnings_rows.append([label, fmt._id(ebitda / 1e6, 1),
                              "-" if profit is None else fmt._id(profit / 1e6, 1)])
        grid.append([label] + [f"Rp{fmt.rp(target(ebitda, fx))}" for fx in fx_shocks])
    label = inputs["label"]
    exhibits = [
        _exhibit(f"Sensitivitas EBITDA dan laba {label} terhadap harga komoditas",
                 ["Skenario harga 2H", f"EBITDA {label} (US$ juta)", f"Laba bersih {label} (US$ juta)"],
                 earnings_rows,
                 "Sumber: estimasi Sektoral. Guncangan harga diterapkan pada pendapatan 2H; biaya "
                 f"dianggap tetap dan pajak {fmt.pct(TAX_RATE)} (tarif statutori) dipakai untuk laba bersih."),
        _exhibit(f"Sensitivitas target harga: harga komoditas x kurs USD/IDR",
                 ["Harga 2H \\ USD/IDR"] + [("Base" if fx == 0 else f"{'+' if fx > 0 else ''}{fmt.pct(fx)}")
                                            for fx in fx_shocks], grid,
                 f"Sumber: estimasi Sektoral; multiple {fmt.mult(inputs['multiple'])} EV/EBITDA, "
                 f"utang bersih dan minoritas neraca {inputs.get('balance_period')}, kurs dasar "
                 f"{fmt._id(inputs['fx_rate'], 0)}. Biaya dalam rupiah tidak dimodelkan terpisah."),
    ]
    low, high = grid[0][1], grid[-1][-1]
    return _page("Sensitivitas harga komoditas dan kurs", [
        f"Guncangan harga komoditas 10% pada semester kedua mengubah EBITDA {label} sekitar "
        f"US${fmt._id(inputs['h2_revenue'] * 0.10 / 1e6, 0)} juta.",
        f"Rentang target pada tabel adalah {low} sampai {high}; skenario turun selalu "
        "menghasilkan nilai lebih rendah dari base case."], exhibits)


# ------------------------------------------------------ catalysts (mining)

def mining_catalysts(doc, intake):
    evidence = intake.get("official_evidence") or {}
    actual = evidence.get("latest_actual") or {}
    if intake.get("model_profile") != "finite_life_mining" or not actual:
        return
    operating = evidence.get("operating_context") or []
    life = evidence.get("mine_life_context") or {}
    balance = evidence.get("balance_sheet") or {}
    published = actual.get("published_at") or "-"
    period = actual.get("period") or "periode terakhir"
    rows = []
    if operating:
        rows.append(["Volume dan kadar tambang", f"{operating[0]['fact']} (rilis {published})",
                     "Volume konsentrat dan kadar menentukan pendapatan serta EBITDA tahun berjalan.",
                     "Positif; turun bila kadar kembali melemah"])
    if len(operating) > 1:
        rows.append(["Ramp-up pemrosesan", f"{operating[1]['fact']} (rilis {published})",
                     "Utilisasi smelter dan PMR menaikkan porsi produk olahan dan margin.",
                     "Positif bila utilisasi naik; negatif bila terjadi gangguan"])
    attainment = guidance_attainment(evidence)
    if attainment:
        low = min(r[3] for r in attainment)
        high = max(r[3] for r in attainment)
        rows.append([f"Pencapaian panduan {_guidance_period(evidence)}",
                     f"Realisasi {period} {fmt.pct(low)} sampai {fmt.pct(high)} dari panduan volume.",
                     "Volume semester kedua menentukan EBITDA forecast dan target harga.",
                     "Negatif bila semester kedua di bawah laju yang disiratkan panduan"])
    for name in _commodities(intake):
        points = _series(name)
        change = _change_12m(points)
        if change is None:
            continue
        rows.append([f"Harga {COMMODITY_UNITS[name][0].lower()}",
                     f"{'Naik' if change >= 0 else 'Turun'} {fmt.pct(abs(change))} dalam 12 bulan "
                     f"(data s.d. {points[-1][0].isoformat()}).",
                     "Harga realisasi langsung mengalir ke pendapatan; lihat tabel sensitivitas.",
                     "Dua arah"])
    debt, cash = balance.get("total_debt"), balance.get("cash")
    if debt is not None and cash is not None:
        rows.append(["Utang bersih dan capex",
                     f"Utang bersih US${fmt._id((debt - cash) / 1e6, 0)} juta per "
                     f"{balance.get('period_end', '-')}.",
                     "Beban bunga dan capex memengaruhi laba bersih dan nilai ekuitas.",
                     "Negatif bila capex pengembangan dipercepat"])
    if life.get("elang_fid_target") or life.get("elang_first_ore"):
        rows.append(["Pengembangan Elang",
                     f"Target keputusan investasi {life.get('elang_fid_target', '-')}; "
                     f"bijih pertama {life.get('elang_first_ore', '-')}.",
                     "Capex pengembangan menekan arus kas bebas; nilai aset baru masuk setelah LoM tersedia.",
                     "Dua arah"])
    for exhibit in doc["exhibits"]:
        if exhibit["judul"] == "Katalis, risiko, dan indikator pemantauan" and rows:
            exhibit["data"] = {"cols": ["Katalis / risiko", "Waktu dan bukti",
                                        "Driver dan jalur dampak", "Arah"], "rows": rows}
            exhibit["catatan_sumber"] = (
                f"Sumber fakta: {actual.get('source_title')} (terbit {published}); Sectors untuk "
                "harga komoditas. Kolom driver dan arah adalah analisis Sektoral.")


def _guidance_period(evidence):
    actual = evidence.get("latest_actual") or {}
    return evidence.get("guidance_period") or (
        f"FY{str(actual['period_end'])[:4]}" if actual.get("period_end") else "FY")


def guidance_attainment(evidence):
    """1H actual as a share of full-year guidance, matched on product and unit."""
    guidance = evidence.get("management_guidance") or []
    metrics = {row["name"]: row for row in evidence.get("operating_metrics") or []
               if isinstance(row, dict) and row.get("name")}
    scale = {("koz", "oz"): 1e3, ("kt", "ton"): 1e3, ("mlbs", "mlbs"): 1, ("koz", "koz"): 1}
    rows = []
    for item in guidance:
        match = re.match(r"(.+?)\s*\(([^)]+)\)", item.get("name") or "")
        if not match or not _num(item.get("value")):
            continue
        base, unit = match.group(1).strip().lower(), match.group(2).strip().lower()
        for name, metric in metrics.items():
            m = re.match(r"(.+?)\s*\(([^)]+)\)", name)
            if not m or _num(metric.get("current")) is None:
                continue
            if m.group(1).strip().lower() == base and (unit, m.group(2).strip().lower()) in scale:
                actual = metric["current"] / scale[(unit, m.group(2).strip().lower())]
                rows.append((item["name"], actual, item["value"], actual / item["value"]))
    return rows


def guidance_exhibit(evidence, house_ratio=None):
    rows = guidance_attainment(evidence)
    if not rows:
        return None
    actual = evidence.get("latest_actual") or {}
    period = actual.get("period") or "1H"
    table = [[name, fmt._id(real, 1), fmt._id(guide, 0), fmt.pct(share),
              fmt.mult((guide - real) / real) if real else "-"]
             for name, real, guide, share in rows]
    note = ("Sumber: rilis resmi emiten (realisasi dan panduan). Kolom terakhir adalah volume "
            "semester kedua yang disiratkan panduan dibagi realisasi semester pertama.")
    if house_ratio:
        note += (f" Asumsi pendapatan 2H/1H rumah {fmt.mult(house_ratio)} dibandingkan dengan "
                 "rasio volume ini pada basis semester yang sama.")
    return _exhibit(f"Realisasi {period} terhadap panduan {_guidance_period(evidence)}",
                    ["Produk", f"Realisasi {period}", "Panduan", "Tercapai", "Implied 2H/1H"],
                    table, note)


# ------------------------------------------------------------- finalize

def _rank(title):
    for index, prefix in enumerate(PAGE_ORDER):
        if title.startswith(prefix):
            return index
    return len(PAGE_ORDER)


def renumber(doc):
    """Exhibit 1 stays the cover table; the rest follow page order."""
    cover = next((e for e in doc["exhibits"] if e.get("judul") == "Key Financials"),
                 doc["exhibits"][0] if doc["exhibits"] else None)
    ordered = [cover] if cover else []
    for page in doc["bagian"]:
        for exhibit in page.get("exhibit") or []:
            if all(exhibit is not seen for seen in ordered):
                ordered.append(exhibit)
    for number, exhibit in enumerate(ordered, 1):
        exhibit["n"] = number
    doc["exhibits"] = ordered


def trim_key_financials(doc, actual_years=2, forecast_years=3):
    """Spec §5.4: two actual and three forecast periods on the cover."""
    cover = next((e for e in doc["exhibits"] if e.get("judul") == "Key Financials"), None)
    if not cover:
        return
    cols = cover["data"]["cols"]
    actual = [i for i, c in enumerate(cols[1:], 1) if not str(c).endswith("F")][-actual_years:]
    forecast = [i for i, c in enumerate(cols[1:], 1) if str(c).endswith("F")][:forecast_years]
    keep = [0] + actual + forecast
    cover["data"]["cols"] = [cols[i] for i in keep]
    cover["data"]["rows"] = [[row[i] if i < len(row) else "-" for i in keep]
                             for row in cover["data"]["rows"]]
    doc["cover"]["key_financials"] = cover["data"]["rows"]


# ------------------------------------------------------------ combo charts (Slide 3)

def chart_forecast_rows(intake, fc):
    """Forecast points a chart may show, in IDR, never the CAGR screen.

    Validated scenario rows (going concern/bank earnings scenario, mining
    interim scenario, and their outyear path) or a production forecast.
    Anything else stays off the chart, matching "belum dimodelkan" in Key
    Financials.
    """
    fc = fc or {}
    if fc.get("production_ready") is True:
        return [{"label": r.get("label"), "revenue": r.get("revenue"),
                 "ebitda": r.get("ebitda"), "net": r.get("net"),
                 "margin": r.get("margin")} for r in (fc.get("rows") or [])[:3]]
    anchor = fc.get("earnings_scenario") or fc.get("interim_scenario")
    if not anchor:
        return []
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    if not (isinstance(fx, (int, float)) and fx > 0):
        return []
    idr = lambda v: v * fx if isinstance(v, (int, float)) else None
    full = anchor.get("full_year") or {}
    rows = [{"label": f"FY{anchor['year'] % 100:02d}F", "revenue": idr(full.get("revenue")),
             "ebitda": idr(full.get("ebitda")), "net": idr(full.get("net_profit"))}]
    for r in ((fc.get("outyear_scenario") or {}).get("rows") or []):
        rows.append({"label": r.get("label"), "revenue": idr(r.get("revenue")),
                     "ebitda": idr(r.get("ebitda")), "net": idr(r.get("net_profit"))})
    for r in rows:
        r["margin"] = (r["ebitda"] / r["revenue"]
                       if r.get("ebitda") is not None and r.get("revenue") else None)
    return rows[:3]


def combo_charts_page(intake, fc=None):
    """2x2 combo: Revenue+growth, EBITDA+margin, Net Profit+EPS growth, DER vs ROE.

    Actual bars solid, forecast lighter; EBITDA only when modeled; each with
    2-3 sentences; tie-out with Key Financials (same period labels).
    Bank: NIM+CoC note when financial_ddm (data Sectors tidak membawa NIM rinci).
    """
    annuals = (intake.get("annuals") or [])[-5:]
    if len(annuals) < 2:
        return None
    frows = chart_forecast_rows(intake, fc)
    labels = [str(a.get("year")) for a in annuals] + [r.get("label", "") for r in frows[:3]]
    rev_bars = [a.get("revenue") for a in annuals] + [r.get("revenue") for r in frows[:3]]
    rev_g = [None] + [(cur / prev - 1) * 100
                      if isinstance(cur, (int, float)) and isinstance(prev, (int, float)) and prev
                      else None for prev, cur in zip(rev_bars, rev_bars[1:])]
    ebitda_bars = [a.get("ebitda") for a in annuals] + [r.get("ebitda") for r in frows[:3]]
    has_ebitda = any(isinstance(v, (int, float)) for v in ebitda_bars)
    ebitda_m = []
    for a in annuals:
        rev, eb = a.get("revenue") or 0, a.get("ebitda")
        ebitda_m.append(eb / rev * 100 if rev and isinstance(eb, (int, float)) else None)
    ebitda_m += [((r.get("margin") or 0) * 100) if r.get("margin") is not None else None
                 for r in frows[:3]]
    net_bars = [(a.get("earnings") if a.get("earnings") is not None else a.get("net_profit"))
                for a in annuals] + [r.get("net") for r in frows[:3]]
    is_fc = [False] * len(annuals) + [True] * min(3, len(frows))
    net_g = [None] + [(cur / prev - 1) * 100
                      if isinstance(cur, (int, float)) and isinstance(prev, (int, float)) and prev > 0
                      else None for prev, cur in zip(net_bars, net_bars[1:])]
    series = [
        {"label": "Pendapatan (Rp) & pertumbuhan", "bars": rev_bars, "line": rev_g,
         "is_forecast": is_fc},
        {"label": "Laba bersih (Rp) & pertumbuhan", "bars": net_bars, "line": net_g,
         "is_forecast": is_fc},
    ]
    if has_ebitda:
        series.insert(1, {"label": "EBITDA (Rp) & margin", "bars": ebitda_bars,
                          "line": ebitda_m, "is_forecast": is_fc})
    else:
        series.insert(1, {"label": "EBITDA belum dimodelkan", "bars": [None] * len(labels),
                          "line": [None] * len(labels), "is_forecast": is_fc})
    # DER vs ROE placeholder: leverage from annuals liab/equity; ROE from earnings/equity.
    der = []
    roe = []
    for a in annuals:
        liab, eq = a.get("liab") or 0, a.get("equity") or 0
        earn = a.get("earnings") or 0
        der.append(liab / eq if eq else None)
        roe.append(earn / eq * 100 if eq else None)
    der += [None] * min(3, len(frows))
    roe += [None] * min(3, len(frows))
    series.append({"label": "DER (x) & ROE", "bars": der,
                   "line": roe, "is_forecast": is_fc})
    exhibit = {"n": 0, "judul": "Kinerja keuangan: pendapatan, profitabilitas, leverage",
               "tipe": "combo_chart",
               "data": {"cols": labels, "series": series},
               "catatan_sumber": f"Source: Company, Sektoral Estimates; periode {labels[0]}-{labels[-1]}; "
                                 "actual solid, forecast lighter; EBITDA hanya bila dimodelkan; "
                                 "tie-out dengan Key Financials periode sama."}
    paras = ["Pendapatan dan laba actual menjadi basis; forecast hanya bila driver bersumber.",
             "Margin dan leverage dibaca bersama capex dan modal kerja di catatan metodologi."]
    if (intake.get("model_profile") == "financial_ddm"):
        paras.append("Bank: NIM dan cost-of-credit dibaca dari driver laba/ekuitas; "
                     "rincian NIM historis tidak dibawa cache Sectors.")
    return _page("Kinerja keuangan dan profitabilitas", paras, [exhibit])


def enrich(doc, intake, valuation_inputs=None, va=None, fc=None):
    cover_market_data(doc, intake)
    trim_key_financials(doc)
    mining_catalysts(doc, intake)
    evidence = intake.get("official_evidence") or {}
    pages = doc["bagian"]
    titles = {page["judul"] for page in pages}
    exhibit_titles = {e["judul"] for e in doc["exhibits"]}

    guidance = guidance_exhibit(evidence, (valuation_inputs or {}).get("house_h2_ratio"))
    if guidance:
        for page in pages:
            anchor = next((i for i, e in enumerate(page["exhibit"])
                           if e["judul"].startswith("Panduan produksi")), None)
            if anchor is not None:
                page["exhibit"].insert(anchor + 1, guidance)
                break

    new_pages = [industry_page(intake), combo_charts_page(intake, fc),
                 sensitivity_page(valuation_inputs),
                 peer_page(intake, valuation_inputs)]
    catalyst = next((e for p in pages for e in p["exhibit"]
                     if e["judul"] == "Katalis, risiko, dan indikator pemantauan"), None)
    owner_exhibits, owner_paragraphs = ownership_exhibits(intake)
    if catalyst or owner_exhibits:
        for page in pages:
            page["exhibit"] = [e for e in page["exhibit"] if e is not catalyst]
        new_pages.append(_page(
            "Katalis, risiko, dan kepemilikan",
            ["Katalis dan risiko dipilih menurut dampaknya ke volume, harga realisasi, biaya dan "
             "neraca; kepemilikan dan arus asing ditampilkan sebagai konteks pasar."] + owner_paragraphs,
            ([catalyst] if catalyst else []) + owner_exhibits))
    if not ({"Riwayat keuangan dalam data Sectors", "Laba rugi historis"} & exhibit_titles):
        new_pages.append(financials_page(intake))
    for page in new_pages:
        if page and page["judul"] not in titles:
            pages.append(page)
    if va:
        attach_method_chain(doc, va)
    doc["bagian"] = [p for p in sorted(pages, key=lambda p: _rank(p["judul"]))
                     if p["exhibit"] or p["paragraf"] or p.get("cards")]
    for index, page in enumerate(doc["bagian"]):
        page["halaman"] = index + 2
    renumber(doc)
    return doc


def valuation_inputs(intake, fc, va):
    """Numbers the extras need from the selected valuation, when one exists."""
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    target = va.get("scenario_target") or {}
    scenario = fc.get("interim_scenario") or {}
    fx_rate = ((intake.get("fx_spot") or {}).get("rate") or
               (target.get("fx") or {}).get("rate"))
    shares = balance.get("shares_outstanding") or balance.get("shares_issued") or intake.get("shares")
    inputs = {"label": f"FY{scenario['year'] % 100:02d}F" if scenario.get("year") else "FY",
              "tp": va.get("tp") if va.get("rating") else None,
              "method_label": va.get("method") or "-",
              "balance_period": balance.get("period_end")}
    usd = evidence.get("reporting_currency") == "USD"
    if usd and fx_rate and shares and balance.get("total_equity") is not None:
        equity_parent = balance["total_equity"] - (balance.get("non_controlling_interest") or 0)
        inputs["bvps_idr"] = equity_parent / shares * fx_rate
        inputs["bvps_period"] = balance.get("period_end")
    full = scenario.get("full_year") or {}
    annuals = evidence.get("annual_actuals") or []
    prior = next((row for row in annuals if row.get("year") == (scenario.get("year") or 0) - 1), {})
    if usd and fx_rate and shares and full.get("net_profit") and prior.get("net_profit"):
        share = (prior.get("net_profit_attributable") or prior["net_profit"]) / prior["net_profit"]
        inputs["eps_idr"] = full["net_profit"] * share / shares * fx_rate
    if va.get("rating") and target.get("ebitda_usd") and fx_rate:
        inputs.update({
            "ebitda_usd": target["ebitda_usd"], "net_profit_usd": full.get("net_profit"),
            "h2_revenue": (scenario.get("h2") or {}).get("revenue"),
            "multiple": 8.0, "net_debt_usd": target["net_debt_usd"],
            "minority_usd": target.get("minority_interest_usd") or 0,
            "shares": target["shares"], "fx_rate": target["fx"]["rate"]})
    ratio = (scenario.get("assumptions") or {}).get("h2_revenue_to_h1")
    if ratio:
        inputs["house_h2_ratio"] = ratio
    return inputs
