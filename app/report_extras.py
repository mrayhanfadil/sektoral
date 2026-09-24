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
    # Design cover shows Rp and US$ side by side (Rpbn / US$mn) with dated FX.
    fx = (intake.get("fx_spot") or {}).get("rate")
    if isinstance(fx, (int, float)) and fx > 0:
        if data.get("market_cap"):
            data["market_cap_usd"] = fmt._id(data["market_cap"] / fx / 1e6, 1)
        if adtv:
            data["adtv_usd"] = fmt._id(adtv / fx / 1e6, 1)
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
        return peer_industry_page(intake)
    return _page("Industri dan harga komoditas", paragraphs, exhibits)


def _window_change(rows, key, start_day):
    """Change of ``key`` from the first row on/after ``start_day`` to the last row."""
    points = sorted((str(r.get("date"))[:10], _num(r.get(key))) for r in rows or []
                    if isinstance(r, dict) and r.get("date") and _num(r.get(key)))
    points = [p for p in points if p[0] >= start_day]
    return (points[-1][1] / points[0][1] - 1, points[0][0], points[-1][0]) if len(points) >= 2 else None


def price_vs_ihsg(ticker):
    """(issuer move, IHSG move) over the common window of the cached Sectors
    daily closes; each is (change, start, end) or None."""
    daily = (local_data.cache_get(ticker, f"/daily/{ticker}/") or {}).get("data") or []
    index = cache.first("/index-daily/ihsg/")
    index_rows = (index.get("data") if isinstance(index, dict) else index) or []
    # Common window: the later of the two series' first dates.
    firsts = [min((str(r.get("date"))[:10] for r in rows_ if isinstance(r, dict) and r.get("date")),
                  default=None) for rows_ in (daily, index_rows)]
    start = max(firsts) if all(firsts) else None
    if not start:
        return None, None
    return _window_change(daily, "close", start), _window_change(index_rows, "price", start)


def peer_industry_page(intake):
    """Struktur slide 2 for issuers without a cached Sectors sub-sector report:
    the sub-sector read from the issuer's Sectors peer table, the issuer's
    position in it, and market sentiment (price vs IHSG, foreign flow)."""
    ticker = intake["ticker"]
    peers = peer_tools.find_peers(ticker)
    rows = peers.get("rows") or []
    subject = next((r for r in rows if r["is_self"]), None)
    others = [r for r in rows if not r["is_self"]]
    if not subject or len(others) < 3:
        return None
    stats = _peer_stats(rows)
    caps = [(r["metrics"].get("market_cap"), r["metrics"].get("mcap_change_1y")) for r in others]
    weighted = [(cap, chg) for cap, chg in caps if cap and chg is not None]
    peer_change = (sum(cap * chg for cap, chg in weighted) / sum(cap for cap, _ in weighted)
                   if weighted else None)
    total_cap = sum(cap for cap, _ in caps if cap)
    own = subject["metrics"]
    mult = lambda v: "-" if v is None else fmt.mult(v)
    pct = lambda v: "-" if v is None else fmt.pct(v)
    table = [
        ["Kapitalisasi pasar (Rp triliun)", fmt._id(total_cap / 1e12, 1),
         fmt._id((own.get("market_cap") or 0) / 1e12, 1)],
        ["Perubahan kapitalisasi pasar 1 tahun", pct(peer_change), pct(own.get("mcap_change_1y"))],
        [f"P/E (median peer {_band_label(method_chain.PEER_PE_BAND)})", mult(stats["pe"][0]),
         mult(own.get("pe"))],
        [f"P/B (median peer {_band_label(method_chain.PEER_PB_BAND)})", mult(stats["pb"][0]),
         mult(own.get("pb"))],
        ["ROE (median)", pct(stats["roe"][0]), pct(own.get("roe"))],
        ["Margin laba bersih (median)", pct(stats["net_margin"][0]), pct(own.get("net_margin"))],
        ["Liabilitas/ekuitas (median)", mult(stats["leverage"][0]), mult(own.get("leverage"))]]
    group = peers.get("group") or intake.get("sub_sector") or "sub-sektor"
    exhibit = _exhibit(
        f"Kondisi sub-sektor {group}: peer dibanding {ticker}",
        ["Metrik", f"Peer ({len(others)} emiten, tanpa {ticker})", ticker], table,
        f"Sumber: {peers['source']} ({peers['basis']}), tahun buku "
        f"{subject.get('year') or own.get('year') or '-'}; "
        "perubahan kapitalisasi peer ditimbang kapitalisasi pasar; median P/E dan P/B memakai "
        "rentang yang sama dengan valuasi.")
    paragraphs = []
    if peer_change is not None and own.get("mcap_change_1y") is not None:
        gap = own["mcap_change_1y"] - peer_change
        verdict = ("mengungguli" if gap > 0.05 else "tertinggal dari" if gap < -0.05
                   else "sejalan dengan")
        paragraphs.append(
            f"Sub-sektor {group} berisi {len(others)} peer dengan kapitalisasi total "
            f"Rp{fmt._id(total_cap / 1e12, 1)} triliun; kapitalisasi pasar peer "
            f"{'naik' if peer_change >= 0 else 'turun'} {fmt.pct(abs(peer_change))} dalam setahun "
            f"(tertimbang kapitalisasi). {ticker} {verdict} peer: kapitalisasinya "
            f"{'naik' if own['mcap_change_1y'] >= 0 else 'turun'} "
            f"{fmt.pct(abs(own['mcap_change_1y']))}.")
    if own.get("roe") is not None and stats["roe"][0] is not None:
        paragraphs.append(
            f"ROE {ticker} {fmt.pct(own['roe'])} dibanding median peer {fmt.pct(stats['roe'][0])}, "
            f"dengan margin laba bersih {pct(own.get('net_margin'))} (median peer "
            f"{pct(stats['net_margin'][0])}); selisih ini menjelaskan posisi valuasinya terhadap "
            "peer, bukan tren industri yang terukur.")
    # Sentiment: price vs IHSG on common dates, and net foreign flow.
    own_move, ihsg_move = price_vs_ihsg(ticker)
    flows = (local_data.cache_get(ticker, f"/foreign-flow/{ticker}/") or {}).get("data") or []
    net_flow = sum(_num(r.get("net_foreign_inflow")) or 0 for r in flows if isinstance(r, dict))
    sentiment = []
    if own_move and ihsg_move:
        sentiment.append(
            f"Sejak {own_move[1]}, saham {ticker} {'naik' if own_move[0] >= 0 else 'turun'} "
            f"{fmt.pct(abs(own_move[0]))} sementara IHSG {'naik' if ihsg_move[0] >= 0 else 'turun'} "
            f"{fmt.pct(abs(ihsg_move[0]))}")
    if flows:
        sentiment.append(
            f"investor asing mencatat {'beli' if net_flow >= 0 else 'jual'} bersih "
            f"Rp{_rp_bn(abs(net_flow), 1)} miliar pada {str(flows[0].get('date'))[:10]} sampai "
            f"{str(flows[-1].get('date'))[:10]}")
    if sentiment:
        paragraphs.append("Sentimen pasar: " + "; ".join(sentiment) +
                          ". Angka ini konteks pasar, bukan dasar target harga.")
    return _page("Industri dan sentimen", paragraphs, [exhibit])


# ------------------------------------------------------------ peer page

def _band_label(band):
    lo, hi = band
    return f"{lo:.0f}-{hi:.0f}x"


def _peer_stats(rows):
    """(median, average) per metric over peers other than the issuer. P/E and
    P/B use the valuation's peer bands, so the table, its narrative and the
    target price all read the same peer set."""
    bands = {"pe": method_chain.PEER_PE_BAND, "pb": method_chain.PEER_PB_BAND}
    out = {}
    for key in ("market_cap", "pe", "pb", "roe", "net_margin", "leverage"):
        vals = [r["metrics"].get(key) for r in rows if not r["is_self"]]
        vals = [v for v in vals if isinstance(v, (int, float)) and v == v]
        if key in bands:
            lo, hi = bands[key]
            vals = [v for v in vals if lo < v <= hi]
        out[key] = ((statistics.median(vals), sum(vals) / len(vals)) if vals
                    else (None, None))
    return out


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
    stats = _peer_stats(rows)
    for key, kind in (("market_cap", "rp"), ("pe", "x"), ("pb", "x"), ("roe", "pct"),
                      ("net_margin", "pct"), ("leverage", "x")):
        signal = ranked.get(f"peer.{key}") or {}
        median, avg = stats[key]
        median_row.append("-" if median is None else
                          fmt.pct(median) if kind == "pct" else
                          fmt.mult(median) if kind == "x" else _rp_bn(median))
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
        f"Median dan rata-rata P/E memakai peer dengan P/E {_band_label(method_chain.PEER_PE_BAND)} "
        f"dan P/B {_band_label(method_chain.PEER_PB_BAND)}, rentang yang sama dengan valuasi. "
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
    pe_median, pb_median = stats["pe"][0], stats["pb"][0]
    if pe_signal.get("value") is not None and pe_median:
        paragraphs.append(
            f"P/E {ticker} {fmt.mult(pe_signal['value'])} dibanding median peer "
            f"{fmt.mult(pe_median)}, sementara ROE berada di peringkat "
            f"{roe_signal.get('rank') or '-'} dari {roe_signal.get('n') or '-'}.")
    outliers = [r["symbol"] for r in rows
                if (r["metrics"].get("pe") or 0) > method_chain.PEER_PE_BAND[1]]
    negative = [r["symbol"] for r in rows if r["metrics"].get("pe") is None and not r["is_self"]]
    if outliers or negative:
        paragraphs.append(
            "Pencilan: " + ", ".join(
                ([f"P/E di atas {method_chain.PEER_PE_BAND[1]:.0f}x ({', '.join(outliers)})"]
                 if outliers else []) +
                ([f"laba negatif atau P/E tidak tersedia ({', '.join(negative)})"] if negative else []))
            + "; pencilan tidak masuk median dan rata-rata.")
    cross = []
    inputs = valuation_inputs or {}
    if inputs.get("eps_idr") and pe_median:
        implied = pe_median * inputs["eps_idr"]
        cross.append([f"P/E median peer x EPS {inputs['label']}", fmt.mult(pe_median),
                      f"Rp{fmt.rp(fmt.tick(implied))}"])
    if inputs.get("bvps_idr") and pb_median:
        implied = pb_median * inputs["bvps_idr"]
        cross.append([f"P/B median peer x BVPS {inputs.get('bvps_period', 'terakhir')}",
                      fmt.mult(pb_median), f"Rp{fmt.rp(fmt.tick(implied))}"])
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
        exhibits.extend(band_charts(intake))
    else:
        paragraphs.append("Band historis P/E dan P/BV belum dimodelkan: "
                          "cache membutuhkan harga harian + EPS/BVPS TTM yang sebanding; "
                          "cakupan saat ini tidak cukup.")
    return _page("Perbandingan peer", paragraphs, exhibits)


PUBLICATION_LAG_DAYS = 90  # annual results assumed public ~3 months after FY end


def _band_data(intake):
    """Own-history P/E and P/BV series over the cached daily window.

    Each close is divided by the annual EPS/BVPS already published on that
    date (FY end + PUBLICATION_LAG_DAYS). Returns None when the window is
    under 40 trading days or no base exists.
    """
    try:
        daily = (local_data.cache_get(intake["ticker"], f"/daily/{intake['ticker']}/") or {}).get("data") or []
    except Exception:
        daily = []
    shares = intake.get("shares") or 0
    annuals = [a for a in intake.get("annuals") or [] if isinstance(a.get("year"), int)]
    if len(daily) < 40 or len(annuals) < 2 or not shares:
        return None
    points = []
    for row in daily[-250:]:
        day = _day(row.get("date")) if isinstance(row, dict) else None
        close = _num(row.get("close")) if isinstance(row, dict) else None
        if day and close:
            points.append((day, close))
    if len(points) < 40:
        return None

    def base_on(day, key):
        known = [a for a in annuals
                 if date(a["year"], 12, 31) + timedelta(days=PUBLICATION_LAG_DAYS) <= day
                 and isinstance(a.get(key), (int, float))]
        return (known[-1][key] / shares, known[-1]["year"]) if known else (None, None)

    months = max(1, round((points[-1][0] - points[0][0]).days / 30.4))
    out = {"window": f"{months} bulan", "start": points[0][0], "end": points[-1][0],
           "multiples": {}}
    for label, key in (("P/E", "earnings"), ("P/BV", "equity")):
        series = []
        for day, close in points:
            base, year = base_on(day, key)
            if base and base > 0:
                series.append((day, close / base, base, year))
        if len(series) < 40:
            continue
        mults = sorted(m for _, m, _, _ in series)
        cur, base_now = series[-1][1], series[-1][2]
        out["multiples"][label] = {
            "series": [(d, m) for d, m, _, _ in series],
            "mean": sum(mults) / len(mults), "median": statistics.median(mults),
            "current": cur, "percentile": sum(1 for m in mults if m <= cur) / len(mults) * 100,
            "base_now": base_now, "base_year": series[-1][3],
            "constant_base": len({round(b, 6) for _, _, b, _ in series}) == 1}
    return out if out["multiples"] else None


def own_history_bands(intake):
    """Struktur slide 5 lower half: own-history band table (mean, median,
    current percentile, implied price at mean and median reversion)."""
    data = _band_data(intake)
    if not data:
        return None
    rows = []
    for label in ("P/E", "P/BV"):
        m = data["multiples"].get(label)
        if not m:
            rows.append([label, "NA", "NA", "NA", "basis fundamental historis tidak cukup"])
            continue
        implied = (f"Rp{fmt.rp(fmt.tick(m['mean'] * m['base_now']))} / "
                   f"Rp{fmt.rp(fmt.tick(m['median'] * m['base_now']))}")
        rows.append([label, fmt.mult(m["mean"]), fmt.mult(m["median"]),
                     f"{fmt.mult(m['current'])} (p{m['percentile']:.0f})", implied])
    constant = [label for label, m in data["multiples"].items() if m["constant_base"]]
    return _exhibit(
        f"Band historis {data['window']} P/E dan P/BV (bukan target harga)",
        ["Multiple", "Mean", "Median", "Kini (persentil)", "Implisit mean / median"],
        rows,
        f"Source: Sectors daily {intake['ticker']} {data['start'].isoformat()} sampai "
        f"{data['end'].isoformat()} (cakupan data harian lokal) dan laba/ekuitas tahunan yang "
        f"sudah terbit pada tiap tanggal (akhir tahun buku + {PUBLICATION_LAG_DAYS} hari), saham "
        "kini sebagai basis pro forma. Harga implisit = multiple mean/median x EPS/BVPS terakhir "
        "dengan driver tetap; cross-check reversion, bukan target harga."
        + (f" Basis {', '.join(constant)} tidak berubah sepanjang jendela, sehingga harga "
           "implisitnya sama dengan rata-rata/median harga penutupan." if constant else ""))


def band_charts(intake):
    """Struktur Exhibits 12-13: P/E and P/BV lines with mean (dashed),
    median (dotted) and the current level marked."""
    data = _band_data(intake)
    if not data:
        return []
    charts = []
    for label in ("P/E", "P/BV"):
        m = data["multiples"].get(label)
        if not m:
            continue
        charts.append({
            "n": 0, "judul": f"Band {label} {data['window']} {intake['ticker']}", "tipe": "band_chart",
            "data": {"label": label, "dates": [d.isoformat() for d, _ in m["series"]],
                     "values": [round(v, 4) for _, v in m["series"]], "mean": m["mean"],
                     "median": m["median"], "current": m["current"],
                     "percentile": m["percentile"]},
            "catatan_sumber": (
                f"Source: Sectors daily {intake['ticker']}, Sektoral Estimates; basis "
                f"{'EPS' if label == 'P/E' else 'BVPS'} FY{m['base_year']}; garis putus-putus = "
                f"mean {fmt.mult(m['mean'])}, titik-titik = median {fmt.mult(m['median'])}; "
                f"kini {fmt.mult(m['current'])} di persentil {m['percentile']:.0f}.")})
    return charts


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
        def flow(signal):
            value = signal.get("value")
            if not isinstance(value, (int, float)):
                return f"arus bersih {signal['display']}"
            return (f"{'beli' if value >= 0 else 'jual'} bersih "
                    f"{signal['display'].replace('Rp-', 'Rp').replace('-', '', 1) if value < 0 else signal['display']}")
        paragraphs.append(
            f"Investor asing mencatat {flow(net)} dalam 20 sesi terakhir, dibanding "
            f"{flow(window)} sepanjang jendela data.")
    return exhibits, paragraphs


# ------------------------------------------------------------ financials

def financials_page(intake, fc=None):
    """Struktur slides 6-7: income statement, balance sheet, cash flow and key
    ratios for the last two actual years and three forecast years.

    Actuals come from Sectors (Rp miliar); forecast columns reuse the
    validated rows behind Key Financials and the combo chart, so all three
    tie out. A line the model does not forecast shows NA. Banks switch to a
    bank layout (NII, PPOP, provisions; loans, deposits; NIM, LDR, CAR).
    """
    report = cache.company_report(intake["ticker"]) or {}
    fin = report.get("financials") or {}
    every = sorted((r for r in fin.get("historical_financials") or []
                    if isinstance(r, dict) and r.get("year")), key=lambda r: r["year"])
    if len(every) < 2:
        return None
    actual = every[-2:]
    prior = {r["year"]: r for r in every}
    forecast = [dict(r) for r in chart_forecast_rows(intake, fc)[:3]]
    labels = [f"{r['year']}A" for r in actual] + [
        r.get("label") or "-" for r in forecast]
    labels += [f"FY{(int(actual[-1]['year']) + i) % 100:02d}F"
               for i in range(len(forecast) + 1, 4)]
    n_fc = 3
    forecast += [{} for _ in range(n_fc - len(forecast))]
    bank = intake.get("model_profile") == "financial_ddm"
    ratios = {int(r["year"]): r for r in fin.get("historical_financial_ratio") or []
              if isinstance(r, dict) and r.get("year")}

    def get(row, key, zero_is_missing=False):
        value = _num(row.get(key))
        return None if value is None or (zero_is_missing and value == 0) else value

    def money(value):
        return "NA" if value is None else _rp_bn(value)

    def line(label, fn, fc_fn=None):
        cells = [money(fn(r)) for r in actual]
        cells += [money(fc_fn(f)) if fc_fn and f else "NA" for f in forecast]
        return [label] + cells

    def minus(*values):
        return None if any(v is None for v in values) else values[0] - sum(values[1:])

    def neg(value):
        return None if value is None else -abs(value)

    net_cons = lambda r: minus(get(r, "earnings_before_tax"), get(r, "tax"))
    if bank:
        income = [
            line("Pendapatan bunga", lambda r: get(r, "interest_income")),
            line("Beban bunga", lambda r: neg(get(r, "interest_expense"))),
            line("Pendapatan bunga bersih", lambda r: get(r, "net_interest_income")),
            line("Pendapatan non-bunga", lambda r: get(r, "non_interest_income")),
            line("Beban operasional", lambda r: neg(get(r, "operating_expense"))),
            line("Laba sebelum provisi (PPOP)",
                 lambda r: None if get(r, "operating_pnl") is None or get(r, "provision") is None
                 else get(r, "operating_pnl") + get(r, "provision")),
            line("Provisi dan cadangan", lambda r: neg(get(r, "provision"))),
            line("Laba operasional", lambda r: get(r, "operating_pnl")),
            line("Pendapatan (beban) non-operasional", lambda r: get(r, "non_operating_income_or_loss")),
            line("Laba sebelum pajak", lambda r: get(r, "earnings_before_tax")),
            line("Pajak", lambda r: neg(get(r, "tax"))),
            line("Laba bersih", net_cons, lambda f: f.get("net")),
            line("Laba bersih pemilik induk", lambda r: get(r, "earnings"),
                 lambda f: f.get("net_attr"))]
        balance = [
            line("Kredit bruto", lambda r: get(r, "gross_loan")),
            line("Cadangan kerugian kredit", lambda r: neg(get(r, "allowance_for_loans"))),
            line("Kredit bersih", lambda r: get(r, "net_loan")),
            line("Aset produktif non-kredit", lambda r: get(r, "non_loan_earning_assets")),
            line("Total aset", lambda r: get(r, "total_assets")),
            line("Giro", lambda r: get(r, "current_account")),
            line("Tabungan", lambda r: get(r, "savings_account")),
            line("Deposito", lambda r: get(r, "time_deposit")),
            line("Dana pihak ketiga", lambda r: get(r, "total_deposit")),
            line("Total liabilitas", lambda r: get(r, "total_liabilities")),
            line("Total ekuitas", lambda r: get(r, "total_equity")),
            line("Total liabilitas dan ekuitas",
                 lambda r: None if get(r, "total_liabilities") is None or get(r, "total_equity") is None
                 else get(r, "total_liabilities") + get(r, "total_equity"))]
    else:
        income = [
            line("Pendapatan", lambda r: get(r, "revenue"), lambda f: f.get("revenue")),
            line("Beban pokok pendapatan", lambda r: neg(get(r, "cost_of_revenue"))),
            line("Laba kotor", lambda r: get(r, "gross_profit")),
            line("Beban usaha", lambda r: neg(get(r, "operating_expense"))),
            line("Laba usaha (EBIT)", lambda r: get(r, "operating_pnl")),
            line("EBITDA", lambda r: get(r, "ebitda", zero_is_missing=True), lambda f: f.get("ebitda")),
            line("Beban bunga", lambda r: neg(get(r, "interest_expense_non_operating"))),
            line("Pendapatan (beban) non-operasional lain",
                 lambda r: minus(get(r, "non_operating_income_or_loss"),
                                 neg(get(r, "interest_expense_non_operating")))),
            line("Laba sebelum pajak", lambda r: get(r, "earnings_before_tax")),
            line("Pajak", lambda r: neg(get(r, "tax"))),
            line("Kepentingan non-pengendali",
                 lambda r: neg(minus(net_cons(r), get(r, "earnings")))),
            line("Laba bersih", lambda r: get(r, "earnings"), lambda f: f.get("net_attr"))]
        balance = [
            line("Kas dan setara kas", lambda r: get(r, "cash_and_equivalents") or get(r, "cash_only")),
            line("Persediaan", lambda r: get(r, "inventories")),
            line("Aset lancar lainnya",
                 lambda r: minus(get(r, "current_assets"),
                                 get(r, "cash_and_equivalents") or get(r, "cash_only"),
                                 get(r, "inventories") or 0)),
            line("Total aset lancar", lambda r: get(r, "current_assets")),
            line("Aset tetap bersih", lambda r: get(r, "fixed_assets")),
            line("Aset tidak lancar lainnya",
                 lambda r: minus(get(r, "total_assets"), get(r, "current_assets"),
                                 get(r, "fixed_assets"))),
            line("Total aset", lambda r: get(r, "total_assets")),
            line("Utang jangka pendek", lambda r: get(r, "short_term_debt")),
            line("Liabilitas lancar lainnya",
                 lambda r: minus(get(r, "current_liabilities"), get(r, "short_term_debt") or 0)),
            line("Total liabilitas lancar", lambda r: get(r, "current_liabilities")),
            line("Utang jangka panjang", lambda r: get(r, "long_term_debt")),
            line("Liabilitas tidak lancar lainnya",
                 lambda r: minus(get(r, "non_current_liabilities"), get(r, "long_term_debt") or 0)),
            line("Total liabilitas", lambda r: get(r, "total_liabilities")),
            line("Total ekuitas", lambda r: get(r, "total_equity")),
            line("Total liabilitas dan ekuitas",
                 lambda r: None if get(r, "total_liabilities") is None or get(r, "total_equity") is None
                 else get(r, "total_liabilities") + get(r, "total_equity"))]

    def begin_cash(r):
        before = prior.get(r["year"] - 1) or {}
        return get(before, "cash_and_equivalents") or get(before, "cash_only")

    cash_flow = [
        line("Arus kas operasi", lambda r: get(r, "operating_cash_flow")),
        line("Belanja modal", lambda r: neg(get(r, "capital_expenditure"))),
        line("Arus kas investasi", lambda r: get(r, "investing_cash_flow")),
        line("Arus kas pendanaan", lambda r: get(r, "financing_cash_flow")),
        line("Perubahan kas bersih", lambda r: get(r, "net_cash_flow")),
        line("Kas awal", begin_cash),
        line("Kas akhir", lambda r: get(r, "cash_and_equivalents") or get(r, "cash_only")),
        line("Arus kas bebas (operasi - capex)",
             lambda r: None if get(r, "capital_expenditure") is None
             else minus(get(r, "operating_cash_flow"), abs(get(r, "capital_expenditure"))))]
    cash_flow = [row for row in cash_flow if any(cell not in ("NA",) for cell in row[1:3])]
    # Tie-out: kas awal + perubahan kas = kas akhir (selisih biasanya efek kurs).
    gaps = []
    for r in actual:
        begin, change = begin_cash(r), get(r, "net_cash_flow")
        end = get(r, "cash_and_equivalents") or get(r, "cash_only")
        if None not in (begin, change, end) and end and abs(begin + change - end) / abs(end) > 0.001:
            gaps.append(f"{r['year']} selisih Rp{_rp_bn(begin + change - end)} miliar")

    # Key ratios: growth needs the year before the first column.
    series = actual + []
    def growth(key, zero_is_missing=False):
        cells = []
        for r in actual:
            now, before = get(r, key, zero_is_missing), get(prior.get(r["year"] - 1) or {}, key, zero_is_missing)
            cells.append(fmt.pct(now / before - 1) if now is not None and before and before > 0 else "NA")
        return cells

    def fc_growth(key, base_key):
        cells, before = [], get(actual[-1], base_key)
        for f in forecast:
            now = f.get(key)
            cells.append(fmt.pct(now / before - 1) if now is not None and before and before > 0
                         else "NA")
            before = now
        return cells

    def ratio(fn):
        cells = []
        for r in actual:
            try:
                value = fn(r)
            except (TypeError, ZeroDivisionError):
                value = None
            cells.append("NA" if value is None else fmt.pct(value))
        return cells

    def avg(r, key):
        before = get(prior.get(r["year"] - 1) or {}, key)
        now = get(r, key)
        return (now + before) / 2 if now is not None and before is not None else now

    roaa = lambda r: get(r, "earnings") / avg(r, "total_assets")
    roae = lambda r: get(r, "earnings") / avg(r, "total_equity")
    na3 = ["NA"] * n_fc
    fc_margin = ["NA" if not f.get("revenue") or f.get("net_attr") is None
                 else fmt.pct(f["net_attr"] / f["revenue"]) for f in forecast]
    if bank:
        sector = lambda group, key: (lambda r: _num(((ratios.get(r["year"]) or {}).get(group) or {}).get(key)))
        coc = lambda r: get(r, "provision") / avg(r, "gross_loan")
        ratio_rows = [
            ["Blok Pertumbuhan (%)"] + [""] * (2 + n_fc),
            ["Pendapatan bunga bersih"] + growth("net_interest_income") + na3,
            ["Laba bersih pemilik induk"] + growth("earnings") + fc_growth("net_attr", "earnings"),
            ["Blok Profitabilitas dan kualitas aset (%)"] + [""] * (2 + n_fc),
            ["Marjin bunga bersih (NIM)"] + ratio(sector("profitability", "net_interest_margin")) + na3,
            # Computed from the statement: Sectors' cost_to_income field uses another base.
            ["Rasio biaya terhadap pendapatan"] + ratio(
                lambda r: get(r, "operating_expense") / (get(r, "net_interest_income") +
                                                          get(r, "non_interest_income"))) + na3,
            ["Biaya kredit (provisi / rata-rata kredit)"] + ratio(coc) + na3,
            ["ROAA"] + ratio(roaa) + na3,
            ["ROAE"] + ratio(roae) + na3,
            ["Blok Likuiditas dan permodalan (%)"] + [""] * (2 + n_fc),
            ["Kredit terhadap simpanan (LDR)"] + ratio(sector("liquidity", "loan_to_deposit_ratio")) + na3,
            ["Rasio CASA"] + ratio(sector("liquidity", "casa_ratio")) + na3,
            ["Rasio kecukupan modal (CAR)"] + ratio(sector("capital", "capital_adequacy_ratio")) + na3]
    else:
        margin = lambda key, zero=False: (lambda r: get(r, key, zero) / get(r, "revenue"))
        coverage = []
        for r in actual:
            ebit, interest = get(r, "operating_pnl"), get(r, "interest_expense_non_operating")
            coverage.append(fmt.mult(ebit / interest) if ebit is not None and interest else "NA")
        gearing = []
        for r in actual:
            net_debt, equity = get(r, "net_debt"), get(r, "total_equity")
            gearing.append(fmt.mult(net_debt / equity) if net_debt is not None and equity else "NA")
        ratio_rows = [
            ["Blok Pertumbuhan (%)"] + [""] * (2 + n_fc),
            ["Pendapatan"] + growth("revenue") + fc_growth("revenue", "revenue"),
            ["EBITDA"] + growth("ebitda", True) + na3,
            ["Laba usaha"] + growth("operating_pnl") + na3,
            ["Laba bersih"] + growth("earnings") + fc_growth("net_attr", "earnings"),
            ["Blok Profitabilitas (%)"] + [""] * (2 + n_fc),
            ["Marjin laba kotor"] + ratio(margin("gross_profit")) + na3,
            ["Marjin EBITDA"] + ratio(margin("ebitda", True)) + na3,
            ["Marjin usaha"] + ratio(margin("operating_pnl")) + na3,
            ["Marjin laba bersih"] + ratio(margin("earnings")) + fc_margin,
            ["ROAA"] + ratio(roaa) + na3,
            ["ROAE"] + ratio(roae) + na3,
            ["Blok Leverage (x)"] + [""] * (2 + n_fc),
            ["Net gearing (utang bersih / ekuitas)"] + gearing + na3,
            ["Cakupan bunga (EBIT / beban bunga)"] + coverage + na3]

    has_fc = any(forecast)
    fc_note = (f" Kolom {labels[2]}-{labels[-1]} memakai skenario yang sama dengan Key Financials; "
               "baris yang tidak dimodelkan ditulis NA." if has_fc else
               f" Kolom {labels[2]}-{labels[-1]} belum dimodelkan (NA) karena forecast belum tervalidasi.")
    note = ("Sumber: Sectors, company/report (historical_financials), dalam Rp miliar sesuai "
            "konversi Sectors; angka negatif dalam kurung." + fc_note)
    cf_note = note + (" Kas awal + perubahan kas tidak sama dengan kas akhir: " + "; ".join(gaps)
                      + " (efek kurs atau reklasifikasi kas)." if gaps else
                      " Kas awal + perubahan kas = kas akhir (tie-out neraca).")
    cols = ["Rp miliar"] + labels
    exhibits = [_exhibit("Laba rugi" + (" bank" if bank else ""), cols, income, note),
                _exhibit("Neraca" + (" bank" if bank else ""), cols, balance, note)]
    if cash_flow:
        exhibits.append(_exhibit("Arus kas", cols, cash_flow, cf_note))
    exhibits.append(_exhibit("Rasio utama", ["Rasio"] + labels, ratio_rows,
                             "Sumber: Sectors, company/report (historical_financials dan "
                             "historical_financial_ratio); ROAA/ROAE memakai rata-rata saldo awal "
                             "dan akhir tahun." + fc_note))
    return _page("Data keuangan", [
        f"Laporan keuangan {labels[0]}-{labels[-1]}: dua tahun aktual dari data Sectors dan tiga "
        "tahun forecast dari skenario yang juga dipakai di Key Financials, sehingga laba bersih "
        "di halaman ini, di Key Financials dan di grafik kinerja sama untuk periode yang sama."],
        exhibits)


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
    """Cover exhibits first (price vs IHSG, then Key Financials); the rest
    follow page order."""
    chart = next((e for e in doc["exhibits"] if e.get("tipe") == "price_chart"), None)
    others = [e for e in doc["exhibits"] if e is not chart]
    cover = next((e for e in others if e.get("judul") == "Key Financials"),
                 others[0] if others else None)
    ordered = [e for e in (chart, cover) if e is not None]
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
                 "net_attr": r.get("net_attr", r.get("net")),
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
             "ebitda": idr(full.get("ebitda")), "net": idr(full.get("net_profit")),
             "net_attr": idr(full.get("net_profit_attributable"))}]
    for r in ((fc.get("outyear_scenario") or {}).get("rows") or []):
        rows.append({"label": r.get("label"), "revenue": idr(r.get("revenue")),
                     "ebitda": idr(r.get("ebitda")), "net": idr(r.get("net_profit")),
                     "net_attr": idr(r.get("net_profit_attributable"))})
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
    # An unreported EBITDA arrives as 0 from Sectors; it is a gap, not a zero bar.
    ebitda_bars = [a.get("ebitda") or None for a in annuals] + [r.get("ebitda") for r in frows[:3]]
    has_ebitda = any(isinstance(v, (int, float)) for v in ebitda_bars)
    ebitda_m = []
    for a in annuals:
        rev, eb = a.get("revenue") or 0, a.get("ebitda") or None
        ebitda_m.append(eb / rev * 100 if rev and isinstance(eb, (int, float)) else None)
    ebitda_m += [((r.get("margin") or 0) * 100) if r.get("margin") is not None else None
                 for r in frows[:3]]
    net_bars = [(a.get("earnings") if a.get("earnings") is not None else a.get("net_profit"))
                for a in annuals] + [r.get("net_attr") for r in frows[:3]]
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
    bank = intake.get("model_profile") == "financial_ddm"
    n_act = len(annuals)
    if bank:
        # Bank switch (struktur Exhibit 7): NIM bars and cost of credit line.
        report = cache.company_report(intake["ticker"]) or {}
        fin = report.get("financials") or {}
        ratio_by_year = {int(r["year"]): r for r in fin.get("historical_financial_ratio") or []
                         if isinstance(r, dict) and r.get("year")}
        hist = {int(r["year"]): r for r in fin.get("historical_financials") or []
                if isinstance(r, dict) and r.get("year")}
        nim, coc = [], []
        for a in annuals:
            year = int(a["year"])
            value = _num(((ratio_by_year.get(year) or {}).get("profitability") or {})
                         .get("net_interest_margin"))
            nim.append(value * 100 if value is not None else None)
            now, before = hist.get(year) or {}, hist.get(year - 1) or {}
            loans = [_num(r.get("gross_loan")) for r in (now, before) if _num(r.get("gross_loan"))]
            provision = _num(now.get("provision"))
            coc.append(provision / (sum(loans) / len(loans)) * 100
                       if provision is not None and loans else None)
        fourth = {"label": "NIM (%) & biaya kredit", "bars": nim + [None] * min(3, len(frows)),
                  "line": coc + [None] * min(3, len(frows)), "is_forecast": is_fc,
                  "bar_unit": "%"}
    else:
        der, roe = [], []
        for a in annuals:
            liab, eq = a.get("liab") or 0, a.get("equity") or 0
            earn = a.get("earnings") or 0
            der.append(liab / eq if eq else None)
            roe.append(earn / eq * 100 if eq else None)
        fourth = {"label": "DER (x) & ROE", "bars": der + [None] * min(3, len(frows)),
                  "line": roe + [None] * min(3, len(frows)), "is_forecast": is_fc}
    series.append(fourth)

    def cagr(values):
        vals = [v for v in values if isinstance(v, (int, float))]
        return ((vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
                if len(vals) >= 2 and vals[0] > 0 and vals[-1] > 0 else None)

    actual_rev, fc_rev = rev_bars[:n_act], rev_bars[n_act:]
    notes = []
    hist_cagr = cagr(actual_rev)
    fc_cagr = cagr(actual_rev[-1:] + fc_rev) if fc_rev and any(v for v in fc_rev) else None
    text = (f"Pendapatan tumbuh CAGR {fmt.pct(hist_cagr)} pada {labels[0]}-{labels[n_act - 1]}"
            if hist_cagr is not None else "Pendapatan historis belum cukup untuk CAGR")
    if fc_cagr is not None:
        pace = ("lebih lambat dari" if fc_cagr < hist_cagr - 0.05 else
                "lebih cepat dari" if fc_cagr > hist_cagr + 0.05 else "sejalan dengan") \
            if hist_cagr is not None else "dibanding"
        text += (f"; skenario {labels[n_act]}-{labels[-1]} memberi CAGR {fmt.pct(fc_cagr)}, "
                 f"{pace} laju historis")
    notes.append(text + ".")
    margins = [m for m in ebitda_m[:n_act] if m is not None]
    if margins:
        notes.append(
            f"Margin EBITDA {labels[n_act - 1]} {fmt.pct(margins[-1] / 100)} dibanding rata-rata "
            f"{len(margins)} tahun {fmt.pct(sum(margins) / len(margins) / 100)}"
            + ("; skenario belum memodelkan EBITDA, sehingga margin historis menjadi acuan."
               if not any(ebitda_bars[n_act:]) else "."))
    else:
        notes.append("EBITDA tidak dilaporkan pada data Sectors untuk periode ini; margin "
                     "EBITDA tidak ditampilkan.")
    last_rev_g = rev_g[n_act - 1] if n_act >= 2 else None
    last_net_g = net_g[n_act - 1] if n_act >= 2 else None
    if last_rev_g is not None and last_net_g is not None:
        gap = last_net_g - last_rev_g
        text = (f"Laba bersih {labels[n_act - 1]} {'naik' if last_net_g >= 0 else 'turun'} "
                f"{fmt.pct(abs(last_net_g) / 100)} dibanding pendapatan "
                f"{'naik' if last_rev_g >= 0 else 'turun'} {fmt.pct(abs(last_rev_g) / 100)}")
        if abs(gap) > 5:
            now, before = annuals[n_act - 1], annuals[n_act - 2]
            items = []
            for key, name in (("interest", "beban bunga"), ("tax", "pajak")):
                a_now, a_before = _num(now.get(key)), _num(before.get(key))
                if a_now is not None and a_before:
                    items.append(f"{name} {'naik' if a_now >= a_before else 'turun'} "
                                 f"{fmt.pct(abs(a_now / a_before - 1))}")
            text += ("; selisihnya berasal dari pos di bawah laba usaha (" + ", ".join(items) + ")"
                     if items else "; selisihnya berasal dari pos di bawah laba usaha")
        notes.append(text + ".")
    else:
        notes.append("Pertumbuhan laba bersih belum dapat dibandingkan dengan pendapatan.")
    bars4, line4 = fourth["bars"][:n_act], fourth["line"][:n_act]
    if bank and bars4[-1] is not None:
        notes.append(f"NIM {labels[n_act - 1]} {fmt.pct(bars4[-1] / 100)}"
                     + (f" dengan biaya kredit {fmt.pct(line4[-1] / 100)}" if line4[-1] is not None
                        else "") + "; keduanya driver utama laba bank, bukan leverage.")
    elif not bank and bars4[-1] is not None and line4[-1] is not None:
        notes.append(f"DER {labels[n_act - 1]} {fmt.mult(bars4[-1])} dengan ROE "
                     f"{fmt.pct(line4[-1] / 100)}: " +
                     ("pertumbuhan didanai leverage yang meningkat."
                      if len(bars4) >= 2 and bars4[-2] and bars4[-1] > bars4[-2] * 1.1
                      else "leverage tidak naik material."))
    else:
        notes.append("Data leverage/ROE belum lengkap untuk periode ini.")

    titles = [f"Pendapatan dan pertumbuhan ({labels[0]}-{labels[-1]})",
              f"EBITDA dan margin ({labels[0]}-{labels[-1]})",
              f"Laba bersih dan pertumbuhan ({labels[0]}-{labels[-1]})",
              (f"NIM dan biaya kredit ({labels[0]}-{labels[n_act - 1]})" if bank else
               f"DER dan ROE ({labels[0]}-{labels[n_act - 1]})")]
    source = (f"Source: Company, Sektoral Estimates; periode {labels[0]}-{labels[-1]}; aktual "
              "solid, proyeksi lebih terang; tie-out dengan Key Financials periode sama.")
    exhibits = [{"n": 0, "judul": title, "tipe": "combo_panel",
                 "data": {"cols": labels, "series": [panel]}, "narasi": note,
                 "catatan_sumber": source}
                for title, panel, note in zip(titles, series[:4], notes)]
    return _page("Kinerja keuangan dan profitabilitas",
                 ["Empat grafik berikut memakai periode yang sama dengan Key Financials; "
                  "proyeksi hanya tampil bila skenario tervalidasi."], exhibits)


def price_chart_exhibit(intake):
    """Cover Exhibit 1: the issuer against IHSG (drawn by render at print time)."""
    return {"n": 0, "judul": f"{intake['ticker']} relatif terhadap IHSG",
            "tipe": "price_chart", "data": {"ticker": intake["ticker"],
                                            "as_of": intake.get("as_of")},
            "catatan_sumber": "Source: Sectors, Sektoral Estimates"}


def fallback_risks(intake):
    """Spec §5.4 risks computed from filed data when no validated agent list
    exists: leverage, control, free float, margin trend, commodity and mine
    life. Each carries the number that sizes it; none is generic filler."""
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    usd = evidence.get("reporting_currency") == "USD"
    source = (evidence.get("latest_actual") or {}).get("source_title") or "laporan keuangan emiten"
    money = (lambda v: f"US${fmt._id(v / 1e6, 1)} juta") if usd else (
        lambda v: f"Rp{fmt._id(v / 1e9, 1)} miliar")
    risks = []
    annual = sorted((row for row in evidence.get("annual_actuals") or [] if row.get("year")),
                    key=lambda row: row["year"])
    debt, cash = balance.get("total_debt"), balance.get("cash")
    sectors = sorted((r for r in intake.get("annuals") or [] if r.get("year")),
                     key=lambda r: r["year"])
    # Sectors annuals are in rupiah; only a rupiah reporter can mix them with the balance sheet.
    ebitda_rows = [r for r in annual if r.get("ebitda")] or (
        [] if usd else [r for r in sectors if r.get("ebitda")])
    as_of = balance.get("period_end", "neraca terakhir")
    if (debt is None or cash is None) and not usd and sectors and \
            intake.get("model_profile") != "financial_ddm":
        debt, cash = sectors[-1].get("total_debt"), sectors[-1].get("cash")
        as_of = f"akhir {sectors[-1]['year']}"
    last = ebitda_rows[-1] if ebitda_rows else None
    leverage = ((debt - cash) / last["ebitda"] if debt is not None and cash is not None
                and last and last["ebitda"] > 0 else None)
    # Net debt under 2x EBITDA is not a material funding risk.
    if debt is not None and cash is not None and debt > cash and (leverage is None or leverage >= 2):
        cover = f", setara {fmt.mult(leverage, 1)} EBITDA {last['year']}" if leverage else ""
        risks.append({"kategori": "Pendanaan", "judul": "Utang bersih serta biaya bunga",
                      "isi": f"Utang bersih {money(debt - cash)} per {as_of}{cover}. "
                             "Kenaikan bunga, refinancing, atau EBITDA yang lebih rendah "
                             "langsung menekan laba bersih dan nilai ekuitas.",
                      "sumber": source})
    holders = [(name, pct) for name, pct in _holders(intake) if pct is not None]
    public = next((pct for name, pct in holders
                   if name.lower() in ("public", "publik", "masyarakat")), None)
    control = max((h for h in holders if h[0].lower() not in ("public", "publik", "masyarakat")),
                  key=lambda h: h[1], default=None)
    top3 = sorted((h for h in holders if h[0].lower() not in ("public", "publik", "masyarakat")),
                  key=lambda h: -h[1])[:3]
    if control and control[1] <= 50 and sum(pct for _, pct in top3) > 50:
        risks.append({"kategori": "Tata kelola", "judul": "Kepemilikan terkonsentrasi",
                      "isi": f"Tiga pemegang saham terbesar memegang "
                             f"{fmt._id(sum(pct for _, pct in top3), 1)}% saham. Kebijakan dividen "
                             "dan aksi korporasi ditentukan oleh sedikit pihak, dan penjualan "
                             "blok saham dapat menekan harga.",
                      "sumber": "data kepemilikan Sectors"})
    if control and control[1] > 50:
        risks.append({"kategori": "Tata kelola", "judul": "Kendali pemegang saham mayoritas",
                      "isi": f"{control[0]} memegang {fmt._id(control[1], 1)}% saham. Transaksi "
                             "pihak berelasi, kebijakan dividen, dan aksi korporasi mengikuti "
                             "kepentingan pengendali, sehingga minoritas menanggung risikonya.",
                      "sumber": "data kepemilikan Sectors"})
    if public is not None and public < 7.5:
        risks.append({"kategori": "Regulasi", "judul": "Free float di bawah batas minimum",
                      "isi": f"Free float {fmt._id(public, 1)}% di bawah batas 7,5% bursa. "
                             "Pemenuhannya lewat penerbitan saham baru atau penjualan pengendali "
                             "dapat mendilusi atau menekan harga saham.",
                      "sumber": "data kepemilikan Sectors"})
    # Filed annuals when extracted, otherwise the Sectors annual history.
    history = [(row["year"], row.get("revenue"), row.get("net_profit")) for row in annual] or [
        (row["year"], row.get("revenue"), row.get("earnings")) for row in sectors]
    margins = [(year, profit / revenue) for year, revenue, profit in history[-2:]
               if revenue and profit is not None]
    # A decline of at least 1pp is material; a small drift is not a risk.
    if len(margins) == 2 and margins[1][1] <= margins[0][1] - 0.01:
        (y0, m0), (y1, m1) = margins
        risks.append({"kategori": "Operasi",
                      "judul": ("Laba bersih berbalik rugi" if m1 < 0
                                else "Margin laba bersih menyempit"),
                      "isi": (f"Margin laba bersih {fmt.pct(m0)} pada {y0} berbalik menjadi rugi "
                              f"bersih {fmt.pct(-m1)} dari pendapatan pada {y1}. "
                              if m1 < 0 else
                              f"Margin laba bersih turun dari {fmt.pct(m0)} pada {y0} ke "
                              f"{fmt.pct(m1)} pada {y1}. ")
                             + "Bila tekanan biaya berlanjut, pertumbuhan pendapatan tidak "
                               "sepenuhnya menjadi laba.",
                      "sumber": source})
    if intake.get("model_profile") == "financial_ddm":
        loans, deposits = balance.get("loans"), balance.get("deposits")
        if loans and deposits:
            risks.append({"kategori": "Pendanaan", "judul": "Likuiditas serta biaya dana",
                          "isi": f"Rasio kredit terhadap simpanan {fmt.pct(loans / deposits)} "
                                 f"per {balance.get('period_end', 'neraca terakhir')}. Pertumbuhan "
                                 "kredit bergantung pada kenaikan simpanan; persaingan dana "
                                 "menaikkan biaya dana dan menekan margin bunga bersih.",
                          "sumber": source})
        last = next((row for row in reversed(intake.get("annuals") or [])
                     if row.get("equity") and row.get("assets")), None)
        if last:
            risks.append({"kategori": "Modal", "judul": "Ruang modal untuk pertumbuhan kredit",
                          "isi": f"Ekuitas setara {fmt.pct(last['equity'] / last['assets'])} dari "
                                 f"aset pada {last.get('year', 'tahun terakhir')}. Kenaikan kredit "
                                 "bermasalah atau pembayaran dividen yang besar menggerus modal "
                                 "yang menopang pertumbuhan kredit.",
                          "sumber": "data keuangan Sectors"})
    if intake.get("model_profile") == "finite_life_mining":
        for name in reversed(_commodities(intake)):
            change = _change_12m(_series(name))
            label = COMMODITY_UNITS.get(name, (name,))[0].lower()
            if change is not None:
                risks.insert(0, {"kategori": "Komoditas", "judul": f"Harga {label}",
                              "isi": f"Harga {label} {'naik' if change >= 0 else 'turun'} "
                                     f"{fmt.pct(abs(change))} dalam 12 bulan. Harga realisasi "
                                     "mengalir langsung ke pendapatan dan EBITDA, sehingga "
                                     "koreksi harga menurunkan laba dan nilai aset.",
                              "sumber": "harga komoditas Sectors"})
        life = evidence.get("mine_life_context") or {}
        if life.get("elang_fid_target") or life.get("elang_first_ore"):
            risks.insert(sum(r["kategori"] == "Komoditas" for r in risks), {"kategori": "Proyek", "judul": "Umur tambang serta capex pengembangan",
                          "isi": f"Target keputusan investasi {life.get('elang_fid_target', '-')} "
                                 f"dan bijih pertama {life.get('elang_first_ore', '-')}. "
                                 "Penundaan atau kenaikan capex menekan arus kas bebas sebelum "
                                 "cadangan baru menggantikan tambang yang menua.",
                          "sumber": source})
    return risks[:5]


def attach_risks(doc, intake, page):
    """Place 'Risiko utama' on the catalyst page and name the risks on the
    cover's valuation paragraph (spec §5.4: cover paragraph 3 is valuasi/risiko)."""
    risks = (doc.get("risks") or fallback_risks(intake))[:5]
    doc["risks"] = risks
    if not risks:
        return
    page["risks"] = risks
    page["risks_after"] = 1 if any(e["judul"] == "Katalis, risiko, dan indikator pemantauan"
                                   for e in page["exhibit"]) else 0
    paragraphs = (doc.get("cover") or {}).get("paragraf") or []
    if paragraphs and isinstance(paragraphs[-1], dict):
        names = [r["judul"][:1].lower() + r["judul"][1:] for r in risks[:3]]
        joined = (" dan ".join(names) if len(names) <= 2
                  else ", ".join(names[:-1]) + ", dan " + names[-1])
        paragraphs[-1]["isi"] = paragraphs[-1]["isi"].rstrip() + f" Risiko utama: {joined}."


def enrich(doc, intake, valuation_inputs=None, va=None, fc=None):
    if not any(e.get("tipe") == "price_chart" for e in doc["exhibits"]):
        doc["exhibits"].insert(0, price_chart_exhibit(intake))
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
    risk_page = _page(
        "Katalis, risiko, dan kepemilikan",
        ["Katalis dan risiko dipilih menurut dampaknya ke volume, harga realisasi, biaya dan "
         "neraca; kepemilikan dan arus asing ditampilkan sebagai konteks pasar."] + owner_paragraphs,
        ([catalyst] if catalyst else []) + owner_exhibits)
    for page in pages:
        page["exhibit"] = [e for e in page["exhibit"] if e is not catalyst]
    attach_risks(doc, intake, risk_page)
    if catalyst or owner_exhibits or risk_page.get("risks"):
        new_pages.append(risk_page)
    if not ({"Riwayat keuangan dalam data Sectors", "Laba rugi", "Laba rugi bank"} & exhibit_titles):
        new_pages.append(financials_page(intake, fc))
    for page in new_pages:
        if page and page["judul"] not in titles:
            pages.append(page)
    if va:
        attach_method_chain(doc, va)
    doc["bagian"] = [p for p in sorted(pages, key=lambda p: _rank(p["judul"]))
                     if p["exhibit"] or p["paragraf"] or p.get("cards") or p.get("risks")]
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
