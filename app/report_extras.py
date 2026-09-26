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

from . import (cache, commodity, fmt, forecast_statements, idx_history, landbank, method_chain,
               mineops, rate_benchmarks, scenario_value, share_basis)
from . import consensus, peer_groups
from . import lom as lom_mod

TAX_RATE = 0.22  # Indonesian statutory corporate rate, used only for the sensitivity note
# Spec §3.1: the forecast model and the valuation tables run five years
# (FY26F-FY30F); Key Financials, the statements and the Slide-3 charts show
# two actual and three forecast years of that same model
# (spec/Struktur-Template.md).
FORECAST_YEARS = 5
DISPLAY_FORECAST_YEARS = 3
# "USD" rather than "US$": the report keeps "$" out of rupiah-only drafts (spec §5.3).
COMMODITY_UNITS = {"Copper": ("Tembaga", "USD/ton"), "Gold": ("Emas", "USD/oz"),
                   "Nickel": ("Nikel", "USD/ton"), "Coal": ("Batu bara", "USD/ton")}
# Page order from spec §5.4, matched on page title prefixes.
PAGE_ORDER = ("Tesis investasi", "Hasil terbaru", "Operasi", "Industri", "Kinerja keuangan", "Forecast", "Skenario FY26",
              "Skenario operasi", "Skenario laba", "Berita", "Sensitivitas", "Katalis",
              "Konteks historis", "Target harga", "Cross-check", "Skenario nilai",
              "Perbandingan peer", "Valuasi", "Data keuangan", "Lampiran valuasi")


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


def _growth_pct(value, cap=5):
    """A growth rate: above the cap it reads '>500%' (the reader knows it is
    large); a fall past the negative cap is n.m."""
    if value is not None and value > cap:
        return f">{fmt._id(cap * 100, 0)}%"
    return _signed_pct(value, cap)


def _exhibit(title, columns, rows, source):
    return {"n": 0, "judul": title, "tipe": "tabel",
            "data": {"cols": columns, "rows": rows}, "catatan_sumber": source}


def _page(title, paragraphs, exhibits):
    return {"halaman": 0, "judul": title, "layout": "stack",
            "paragraf": [p for p in paragraphs if p], "exhibit": exhibits}


# ------------------------------------------------------------ method chain

_DECISION = {"selected": "Terpilih", "stop_extreme": "Terpilih, ekstrem (rantai berhenti)",
             "skipped": "Dilewati", "cross_check": "Silang cek", "not_needed": "Tidak dijalankan",
             "not_available": "Belum tersedia"}


METHOD_CHAIN_TITLE = "Rantai metode valuasi"


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
    for x in chain.get("cross_checks") or []:
        value = ("-" if not x.get("per_share") else
                 f"Rp{fmt.rp(fmt.tick(x['per_share']))}" if released else "ditahan")
        why = (method_chain.reader_reason(x["reasons"][0]) if x.get("reasons") else
               x.get("why") or "cross-check wajib framework")
        rows.append([f"x. {x['short']} (cross-check)",
                     _DECISION.get(x["decision"], x["decision"]), value, why])
    source = ("Source: Sektoral Estimates; urutan metode dikunci dari verdict Method Gates 0-5 "
              "sebelum nilai dihitung; metode berikutnya hanya dipakai bila metode "
              "sebelumnya tidak memadai, bukan karena hasilnya tidak disukai")
    override = chain.get("override")
    if override:
        proposed = (chain.get("proposed_order") or [None])[0]
        source += f"; Usulan sistem: {proposed}; dipilih analis: {override}."
    # Brand constant: Sectoral (keputusan branding fase ini).
    return _exhibit("Rantai metode valuasi",
                    ["Metode", "Keputusan", "Nilai/saham", "Alasan"], rows, source)


def holding_sotp_exhibit(va):
    """Framework Method Gate 2 cross-check: listed stakes at market, rest at book,
    holding discount as sensitivity. Per-share values are held on drafts."""
    chain = (va or {}).get("method_chain") or {}
    sotp = next((x for x in chain.get("cross_checks") or [] if x["key"] == "holding_sotp"),
                None) or next((t for t in chain.get("trace") or []
                               if t["key"] == "holding_sotp" and t["status"] == "sufficient"), None)
    if not sotp or sotp["status"] != "sufficient":
        return None
    released = ((va.get("release") or {}).get("status") or "").startswith("distributable")
    primary = chain.get("selected") == "holding_sotp"
    d = sotp["detail"]
    bn = lambda v: fmt._id(v / 1e9, 1)
    rows = []
    for c in d["components"]:
        rows.append([f"{c['name']} ({c['ticker']}), {c['segment']}: {fmt.pct(c['stake'])} x "
                     f"kapitalisasi Rp{bn(c['market_cap'])} miliar", "nilai pasar",
                     bn(c["market_value"])])
    rows.append([f"Ekuitas pemilik induk per {d.get('balance_period') or '-'}", "nilai buku",
                 bn(d["parent_equity"])])
    for c in d["components"]:
        rows.append([f"Dikurangi porsi {c['ticker']} atas ekuitas buku {c['ticker']} "
                     f"(FY{c.get('book_year') or '-'})", "nilai buku", f"({bn(c['book_share'])})"])
    land = d.get("landbank")
    rows.append(["Segmen lain (lahan industri, hotel, utilitas, sewa) pada nilai buku",
                 "nilai buku", bn(d["remainder_book"])])
    if land:
        li = land["inputs"]
        rows.append([f"Revaluasi landbank: RNAV Rp{bn(land['nav'])} miliar dikurangi nilai buku "
                     f"Rp{bn(li['carrying_idr'])} miliar, porsi {fmt.pct(li['stake'])}",
                     "RNAV", bn(d["landbank_uplift"])])
    rows.append(["Total nilai SOTP", "", bn(d["total"])])
    for item in d["discounts"]:
        rows.append([f"Nilai per saham, diskon holding {fmt.pct(item['discount'])}",
                     "sensitivitas" if item["discount"] else "basis",
                     f"Rp{fmt.rp(fmt.tick(item['per_share']))}" if released else "ditahan"])
    stake_sources = "; ".join(sorted({c["stake_source"] for c in d["components"]
                                      if c.get("stake_source")}))
    return _exhibit(
        ("SOTP holding: anak usaha tercatat pada nilai pasar" if primary else
         "Cross-check SOTP holding: anak usaha tercatat pada nilai pasar"),
        ["Komponen", "Basis", "Rp miliar"], rows,
        f"Source: Company, Sektoral Estimates; kepemilikan: {stake_sources}; kapitalisasi dan "
        f"ekuitas anak usaha: {', '.join(sorted({c['market_source'] for c in d['components']}))}; "
        "ekuitas induk: neraca interim emiten. "
        + ("Tanah untuk pengembangan dinilai dengan RNAV landbank (tabel terpisah) menggantikan "
           "nilai bukunya; hotel, utilitas dan sewa tetap pada nilai buku. "
           if d.get("landbank") else
           "Segmen tanpa harga pasar dinilai pada nilai buku (lahan industri tercatat pada "
           "biaya perolehan). ")
        + "Diskon holding 20-30% adalah asumsi analis untuk sensitivitas, bukan data. "
        + ("Metode utama (grup dengan lini usaha berbeda); target memakai diskon 0%."
           if primary else "Cross-check, bukan dasar target harga."))


def _rp_signed(value):
    """Per-share amount with the tables' convention: negatives in brackets."""
    amount = f"Rp{fmt.rp(abs(round(value)))}"
    return f"({amount})" if round(value) < 0 else amount


def landbank_exhibits(va):
    """RNAV of the landbank behind the holding SOTP: inputs and a pace x price grid."""
    chain = (va or {}).get("method_chain") or {}
    sotp = next((t for t in chain.get("trace") or []
                 if t["key"] == "holding_sotp" and t["status"] == "sufficient"), None)
    land = ((sotp or {}).get("detail") or {}).get("landbank")
    if not land:
        return []
    li, ev, lb = land["inputs"], land["inputs"]["evidence"], land["inputs"]["assumptions"]
    shares = sotp["detail"]["shares"]
    bn = lambda v: fmt._id(v / 1e9, 0)
    land_src = ev.get("land_for_development") or {}
    rows = [
        ["Tanah untuk pengembangan (bruto)", f"{fmt._id(li['gross_ha'], 0)} ha",
         f"audit {li['carrying_as_of']}, {land_src.get('page')}"],
        ["Nilai buku tanah", f"Rp{bn(li['carrying_idr'])} miliar",
         f"Rp{fmt._id(li['carrying_idr'] / (li['gross_ha'] * 10_000) / 1000, 0)} ribu/m2 bruto"],
        ["Porsi dapat dijual (asumsi analis)", fmt.pct(li["net_ratio"]),
         lb.get("net_saleable_basis") or "-"],
        ["Laju penjualan", f"{fmt._id(li['pace_ha'], 1)} ha/tahun",
         lb.get("pace_basis") or "-"],
        ["Harga jual awal", f"Rp{fmt._id(li['asp'] / 1000, 0)} ribu/m2",
         "marketing sales 1H26 (9,4 ha, Rp195,9 miliar)"],
        ["Pertumbuhan harga", fmt.pct(li["asp_growth"]), lb.get("growth_basis") or "-"],
        ["Margin kas", fmt.pct(li["cash_margin"]),
         f"laba kotor {fmt.pct(li['gross_margin'])} + biaya buku lahan "
         f"{fmt.pct(li['land_cost_share'])} - beban usaha {fmt.pct(li['opex_ratio'])} - PPh final "
         f"{fmt.pct(li['final_tax'])} (segmen properti {li['margin_periods']})"],
        ["Tingkat diskonto", fmt.pct(land["rate"]), lb.get("discount_basis") or "-"],
        ["RNAV landbank (100%)", f"Rp{bn(land['nav'])} miliar",
         f"terjual habis dalam {land['years']} tahun"],
        [f"Tambahan nilai porsi SSIA ({fmt.pct(li['stake'])})",
         f"Rp{bn(land['uplift_attributable'])} miliar",
         f"{_rp_signed(land['uplift_attributable'] / shares)} per saham"],
    ]
    appraisal = ev.get("appraisal") or {}
    if appraisal.get("fair_value_idr") and appraisal.get("area_m2"):
        rows.append(["Cross-check penilai independen",
                     f"Rp{fmt._id(appraisal['fair_value_idr'] / appraisal['area_m2'] / 1000, 0)} "
                     "ribu/m2 bruto",
                     f"{fmt._id(appraisal.get('area_ha'), 0)} ha, {appraisal.get('method')}, "
                     f"{appraisal.get('appraisal_date')} (tanah mentah, sebelum pengembangan)"])
    growths = sorted({g for (_, g) in land["grid"]})
    # The base pace joins the grid (same landbank.nav as the valuation) so the
    # base row and column can be marked and highlighted.
    grid = dict(land["grid"])
    base_pace, base_g = li["pace_ha"], round(li["asp_growth"], 4)
    for g in growths:
        grid.setdefault((base_pace, g), land["uplift_attributable"] if round(g, 4) == base_g
                        else (landbank.nav(li, land["rate"], base_pace, g)[0]
                              - li["carrying_idr"]) * li["stake"])
    grid_rows = [[(f"{fmt._id(p, 1)} ha/tahun (basis)" if p == base_pace else
                   f"{fmt._id(p, 0)} ha/tahun") + (" (target 2026)" if p == 135 else "")]
                 + [_rp_signed(grid[(p, g)] / shares) for g in growths]
                 for p in sorted({p for (p, _) in grid})]
    return [
        _exhibit("RNAV landbank Suryacipta: dasar perhitungan", ["Komponen", "Nilai", "Dasar"],
                 rows, f"Sumber: {land_src.get('source_title')}; "
                       f"{(ev.get('marketing_asp_idr_per_m2') or {}).get('source_title')}; "
                       "asumsi analis berlabel di data/analyst_scenarios. RNAV menggantikan nilai "
                       "buku tanah untuk pengembangan; hanya porsi SSIA atas selisihnya yang masuk SOTP."),
        _exhibit("Sensitivitas tambahan nilai landbank per saham: laju penjualan x pertumbuhan harga",
                 ["Laju penjualan"] + [f"Harga +{fmt.pct(g)}/tahun"
                                       + (" (basis)" if round(g, 4) == base_g else "")
                                       for g in growths], grid_rows,
                 "Sumber: estimasi Sektoral; tambahan nilai per saham di atas nilai buku, porsi SSIA. "
                 f"Basis: {fmt._id(li['pace_ha'], 1)} ha/tahun dan +{fmt.pct(li['asp_growth'])}/tahun."),
    ]


def attach_method_chain(doc, va):
    exhibit = method_chain_exhibit(va)
    if not exhibit:
        return
    sotp = holding_sotp_exhibit(va)
    page = next((p for prefix in ("Target harga", "Valuasi", "Skenario nilai")
                 for p in doc["bagian"] if str(p.get("judul", "")).startswith(prefix)), None)
    if page is None:
        doc["bagian"].append(_page(
            "Valuasi: rantai metode",
            ["Metode utama dan fallback dinilai berurutan; tabel mencatat metode yang "
             "dipakai dan alasan metode lain dilewati."], [exhibit] + ([sotp] if sotp else [])))
    else:
        page["exhibit"].append(exhibit)
        if sotp:
            page["exhibit"].append(sotp)
            page["exhibit"].extend(landbank_exhibits(va))


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


def _series_sourced(name, as_of=None):
    """Monthly Sectors points, or the dated Yahoo series when Sectors is stale
    at the Report Date (same rule as the LoM deck); (points, source note)."""
    points = [p for p in _sectors_series(name)
              if not as_of or p[0].isoformat() <= str(as_of)[:10]]
    label = f"Sectors, mining/commodities/{name}/price (data bulanan)"
    if as_of and points:
        age = (date.fromisoformat(str(as_of)[:10]) - points[-1][0]).days
        series = commodity.load(name) if age > mineops.DECK_MAX_AGE_DAYS else None
        yahoo = [(date.fromisoformat(r["date"]), r["price"]) for r in (series or {}).get("rows", [])
                 if r["date"] <= str(as_of)[:10]]
        if yahoo and yahoo[-1][0] > points[-1][0]:
            return yahoo, (f"{series['source']}; seri Sectors berhenti "
                           f"{points[-1][0].isoformat()} sehingga tidak dipakai")
    return points, label


def _series(name, as_of=None):
    return _series_sourced(name, as_of)[0]


def _sectors_series(name):
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
    return [n for n in dict.fromkeys(names) if _series(n, intake.get("as_of"))]


def industry_page(intake):
    exhibits, paragraphs = [], []
    if intake.get("model_profile") == "finite_life_mining":
        names = _commodities(intake)
        if names:
            sourced = {n: _series_sourced(n, intake.get("as_of")) for n in names}
            series = {n: sourced[n][0] for n in names}
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
                "Sumber: " + "; ".join(f"{COMMODITY_UNITS[n][0]}: {sourced[n][1]}" for n in names)
                + ". Harga emas dibaca sebagai USD/oz sesuai besaran datanya; titik data terakhir "
                "tiap seri dapat berbeda."))
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
                 _growth_pct(_num((growth.get(y) or {}).get("avg_annual_revenue_growth"))),
                 _growth_pct(_num((growth.get(y) or {}).get("avg_annual_earning_growth")))]
                for y in years]
        name = report.get("sub_sector") or intake.get("sub_sector")
        exhibits.append(_exhibit(
            f"Valuasi dan pertumbuhan sub-sektor {name}",
            ["Tahun", "P/E sub-sektor", "P/B sub-sektor", "Pertumbuhan pendapatan",
             "Pertumbuhan laba"], rows,
            f"Sumber: Sectors, subsector/report/{_slug(name)}; pertumbuhan adalah rata-rata "
            "tertimbang emiten di sub-sektor; di atas 500% ditulis >500% dan di bawah -500% "
            "ditulis n.m. karena basis rendah atau negatif."))
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


def price_vs_ihsg(ticker, start=None, as_of=None):
    """(issuer move, IHSG move) from ``start`` (or the first common date) to
    the last close; each is (change, start, end) or None. IDX closes when
    available, else the cached Sectors daily series."""
    own, index_idx = idx_history.load(ticker, as_of), idx_history.load("IHSG", as_of)
    if own and index_idx:
        daily = [{"date": d.isoformat(), "close": c} for d, c in own["points"]]
        index_rows = [{"date": d.isoformat(), "price": c} for d, c in index_idx["points"]]
    else:
        daily = (local_data.cache_get(ticker, f"/daily/{ticker}/") or {}).get("data") or []
        index = cache.first("/index-daily/ihsg/")
        index_rows = (index.get("data") if isinstance(index, dict) else index) or []
    # Common window: the later of the two series' first dates.
    firsts = [min((str(r.get("date"))[:10] for r in rows_ if isinstance(r, dict) and r.get("date")),
                  default=None) for rows_ in (daily, index_rows)]
    first_common = max(firsts) if all(firsts) else None
    if not first_common:
        return None, None
    start = max(first_common, str(start)[:10]) if start else first_common
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
    mult = lambda v: "-" if v is None else fmt.mult(v, cap=fmt.MULT_CAP)
    pct = lambda v: "-" if v is None else fmt.pct(v)
    median = lambda key, show: ("n.m." if stats["counts"].get(key, 0) < method_chain.MIN_PEERS
                                else show(stats[key][0]))
    table = [
        ["Kapitalisasi pasar (Rp triliun)", fmt._id(total_cap / 1e12, 1),
         fmt._id((own.get("market_cap") or 0) / 1e12, 1)],
        ["Perubahan kapitalisasi pasar 1 tahun", pct(peer_change), pct(own.get("mcap_change_1y"))],
        [f"P/E (median peer {_band_label(method_chain.PEER_PE_BAND)})", median("pe", mult),
         mult(own.get("pe"))],
        [f"P/B (median peer {_band_label(method_chain.PEER_PB_BAND)})", median("pb", mult),
         mult(own.get("pb"))],
        ["ROE (median)", median("roe", pct), pct(own.get("roe"))],
        ["Margin laba bersih (median)", median("net_margin", pct), pct(own.get("net_margin"))],
        ["Liabilitas/ekuitas (median)", median("leverage", mult), mult(own.get("leverage"))]]
    group = peers.get("group") or intake.get("sub_sector") or "sub-sektor"
    exhibit = _exhibit(
        (f"Kondisi grup peer {group}: peer dibanding {ticker}" if peers.get("curated") else
         f"Kondisi sub-sektor {group}: peer dibanding {ticker}"),
        ["Metrik", f"Peer ({len(others)} emiten, tanpa {ticker})", ticker], table,
        f"Sumber: {peers['source']} ({peers['basis']}), "
        + ("laporan terakhir tiap peer (12 bulan terakhir, atau tahun buku terakhir bila "
           "emiten melapor semesteran); perubahan kapitalisasi 1 tahun hanya untuk peer dari "
           "tabel Sectors, ditimbang kapitalisasi pasar; "
           if peers.get("curated") else
           f"tahun buku {subject.get('year') or own.get('year') or '-'}; "
           "perubahan kapitalisasi peer ditimbang kapitalisasi pasar; ")
        + "median P/E dan P/B memakai rentang yang sama dengan valuasi." + _thin_peer_note(stats)
        + (f" n.m. pada multiple {ticker}: di atas {fmt.MULT_CAP}x, basis laba atau ekuitas "
           "sangat kecil." if any(row[2] == "n.m." for row in table) else ""))
    paragraphs = []
    if peer_change is not None and own.get("mcap_change_1y") is not None:
        paragraphs.append(
            f"Sub-sektor {group} berisi {len(others)} peer dengan kapitalisasi total "
            f"Rp{fmt._id(total_cap / 1e12, 1)} triliun; kapitalisasi pasar peer "
            f"{'naik' if peer_change >= 0 else 'turun'} {fmt.pct(abs(peer_change))} dalam setahun "
            f"(tertimbang kapitalisasi). Kapitalisasi pasar {ticker} "
            f"{'naik' if own['mcap_change_1y'] >= 0 else 'turun'} "
            f"{fmt.pct(abs(own['mcap_change_1y']))}; perubahan ini juga dipengaruhi "
            "perubahan jumlah saham dan tidak mengukur imbal hasil harga saham.")
    if own.get("roe") is not None and stats["roe"][0] is not None:
        paragraphs.append(
            f"ROE {ticker} {fmt.pct(own['roe'])} dibanding median peer {fmt.pct(stats['roe'][0])}, "
            f"dengan margin laba bersih {pct(own.get('net_margin'))} (median peer "
            f"{pct(stats['net_margin'][0])}); selisih ini menjelaskan posisi valuasinya terhadap "
            "peer, bukan tren industri yang terukur.")
    # Sentiment: price vs IHSG over the past year (IDX), and net foreign flow.
    as_of = intake.get("as_of")
    year_ago = (date.fromisoformat(str(as_of)[:10]) - timedelta(days=365)).isoformat() if as_of else None
    own_move, ihsg_move = price_vs_ihsg(ticker, year_ago, as_of)
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
    bands = {"pe": method_chain.PEER_PE_BAND, "pb": method_chain.PEER_PB_BAND,
             "ev_ebitda": method_chain.PEER_EV_BAND}
    out = {"counts": {}}
    for key in ("market_cap", "pe", "pb", "ev_ebitda", "roe", "net_margin", "leverage"):
        vals = [r["metrics"].get(key) for r in rows if not r["is_self"]]
        vals = [v for v in vals if isinstance(v, (int, float)) and v == v]
        if key in bands:
            lo, hi = bands[key]
            vals = [v for v in vals if lo < v <= hi]
        elif key in ("roe", "net_margin"):
            # The table shows ratios beyond 500% as n.m.; one tiny base must
            # not drag the average to -2.306%.
            vals = [v for v in vals if abs(v) <= 5]
        # The method chain's minimum: fewer than three valid peers give no
        # median, so the peer pages never show a multiple the chain refused.
        out["counts"][key] = len(vals)
        out[key] = ((statistics.median(vals), sum(vals) / len(vals))
                    if len(vals) >= method_chain.MIN_PEERS else (None, None))
    return out


def _short_name(name):
    """'PT Bank Rakyat Indonesia (Persero) Tbk' -> 'Bank Rakyat Indonesia'."""
    text = re.sub(r"^PT\.?\s+", "", str(name or "").strip())
    text = re.sub(r"\s*\((Persero)\)", "", text)
    return re.sub(r",?\s+Tbk\.?$", "", text).strip()


def _thin_peer_note(stats, keys=("pe", "pb", "roe", "net_margin", "leverage")):
    """The n.m. reason for medians left out because fewer than three peers are valid."""
    names = {"market_cap": "kapitalisasi", "pe": "P/E", "pb": "P/B", "ev_ebitda": "EV/EBITDA",
             "roe": "ROE",
             "net_margin": "margin bersih", "leverage": "liabilitas/ekuitas"}
    thin = [f"{names[k]} {stats['counts'][k]} peer" for k in keys
            if stats["counts"].get(k, 0) < method_chain.MIN_PEERS]
    return (f" n.m.: kurang dari tiga peer valid ({', '.join(thin)}); minimum yang sama dengan "
            "rantai metode." if thin else "")


REGIONAL_TITLE = "Referensi regional (konteks, bukan peer valuasi)"


def regional_reference_exhibit(ticker):
    """Non-IDX listings of the curated pack (``regional_reference``), shown
    for context: they never enter the peer medians, the cross-checks or the
    method chain, which stay IDX-only."""
    try:
        rows, missing, basis = peer_groups.regional(ticker)
    except ValueError:
        return None
    if not rows:
        return None
    x = lambda v: fmt.mult(v, cap=fmt.MULT_CAP) if isinstance(v, (int, float)) and v > 0 else "n.m."
    table = []
    for row in rows:
        ev = (row.get("ev") or {}).get("ev_ebitda")
        table.append([f"{row['company_name']} ({row['symbol']})", row["market"],
                      _rp_bn(row["market_cap"]) if row.get("market_cap") else "-",
                      x(row.get("pe_ttm")), x(row.get("pb_mrq")), x(ev),
                      str(row.get("year") or "-")])

    def median(values):
        values = sorted(v for v in values if isinstance(v, (int, float)) and v > 0)
        if not values:
            return None
        mid = len(values) // 2
        return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
    table.append(["Median referensi regional", "", "",
                  x(median(r.get("pe_ttm") for r in rows)), x(median(r.get("pb_mrq") for r in rows)),
                  x(median((r.get("ev") or {}).get("ev_ebitda") for r in rows)), ""])
    fetched = sorted({str(r.get("source") or "").rsplit("diambil ", 1)[-1] for r in rows})
    return _exhibit(
        REGIONAL_TITLE,
        ["Perusahaan", "Bursa", "Kap. pasar (Rp miliar)", "P/E (x)", "P/B (x)", "EV/EBITDA (x)",
         "Periode laba"], table,
        f"Sumber: Yahoo Finance (laporan keuangan dan kapitalisasi pasar, diambil "
        f"{', '.join(fetched)}), dikonversi ke Rp; data/peer_groups/{ticker}.json. "
        + (basis or "Hanya konteks; tidak dipakai dalam valuasi.")
        + (f" Tanpa snapshot: {', '.join(missing)}." if missing else ""))


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
                                fmt.mult(row["metrics"][key], cap=fmt.MULT_CAP) if kind == "x" else
                                _rp_bn(row["metrics"][key]))
    # Template Exhibit 11: company name with its ticker, and (non-bank) EV/EBITDA,
    # the peer multiples the method chain reads (intake peers).
    bank = intake.get("model_profile") == "financial_ddm"
    ev_of = {str(p.get("symbol") or "").replace(".JK", ""): p.get("ev_ebitda")
             for p in intake.get("peers") or []}
    for row in rows:
        row["metrics"].setdefault("ev_ebitda", ev_of.get(row["symbol"]))
    table = []
    for row in sorted(rows, key=lambda r: r["metrics"].get("market_cap") or 0, reverse=True):
        label = f"{_short_name(row.get('name'))} ({row['symbol']})".lstrip() \
            if row.get("name") else row["symbol"]
        label += " (emiten)" if row["is_self"] else ""
        table.append([label, m(row, "market_cap", "rp"), m(row, "pe", "x"), m(row, "pb", "x")]
                     + ([] if bank else [m(row, "ev_ebitda", "x") if not row["is_self"] else "-"])
                     + [m(row, "roe", "pct"), m(row, "net_margin", "pct"), m(row, "leverage", "x")])
    median_row, avg_row, rank_row = (["Median peer (tanpa emiten)"],
                                     ["Rata-rata peer (tanpa emiten)"],
                                     [f"Peringkat {ticker}"])
    stats = _peer_stats(rows)
    for key, kind in (("market_cap", "rp"), ("pe", "x"), ("pb", "x")) + (
            () if bank else (("ev_ebitda", "x"),)) + (("roe", "pct"),
                                                      ("net_margin", "pct"), ("leverage", "x")):
        signal = ranked.get(f"peer.{key}") or {}
        median, avg = stats[key]
        if stats["counts"].get(key, 0) < method_chain.MIN_PEERS:
            median_row.append("n.m.")
            avg_row.append("n.m.")
            rank_row.append(f"{signal['rank']}/{signal['n']}" if signal.get("rank") else "-")
            continue
        median_row.append("-" if median is None else
                          fmt.pct(median) if kind == "pct" else
                          fmt.mult(median) if kind == "x" else _rp_bn(median))
        avg_row.append("-" if avg is None else
                       fmt.pct(avg) if kind == "pct" else
                       fmt.mult(avg) if kind == "x" else _rp_bn(avg))
        rank_row.append(f"{signal['rank']}/{signal['n']}" if signal.get("rank") else "-")
    table += [median_row, avg_row, rank_row]
    ev_cols = [] if bank else ["EV/EBITDA (x)"]
    curated = peers.get("curated")
    exhibits = [_exhibit(
        "Grup peer: alasan pemilihan",
        ["Emiten", "Bursa", "Status", "Alasan"],
        [[p.get("name") or p["symbol"], p.get("market") or "-", "dipakai", p["reason"]]
         for p in curated["peers"]]
        + [[x["symbol"], "BEI", "dikeluarkan", x["reason"]] for x in curated.get("excluded") or []],
        f"Sumber: data/peer_groups/{ticker}.json (kurasi Sektoral, {curated.get('as_of')}). "
        + curated["basis"])] if curated else []
    exhibits += [_exhibit(
        f"Perbandingan peer {peers.get('group') or ''}".strip(),
        ["Emiten", "Kap. pasar (Rp miliar)", "P/E (x)", "P/B (x)"] + ev_cols
        + ["ROE", "Margin bersih", "Liabilitas/ekuitas (x)"], table,
        f"Sumber: {peers['source']} ({peers['basis']}); per {intake.get('as_of') or intake.get('price_date') or '-'}; "
        "kriteria: model bisnis dan eksposur sebanding, kapitalisasi sebanding, outlier dijelaskan; "
        "P/E negatif tidak diperingkat; rasio di atas 500% ditulis n.m. karena basis pendapatan atau ekuitas sangat kecil. "
        f"Median dan rata-rata P/E memakai peer dengan P/E {_band_label(method_chain.PEER_PE_BAND)} "
        f"dan P/B {_band_label(method_chain.PEER_PB_BAND)}, rentang yang sama dengan valuasi. "
        "Rasio dihitung dari laba, ekuitas, pendapatan dan liabilitas tabel peer. "
        + ("" if bank else
           f"EV/EBITDA peer = kapitalisasi pasar + utang - kas atas EBITDA terakhir dari laporan "
           f"peer ({method_chain.peer_ev_sources(intake.get('peers'))}), rentang valid "
           f"{_band_label(method_chain.PEER_EV_BAND)} seperti rantai metode; EV/EBITDA emiten ada "
           "di Key Financials. ")
        + "Emiten yang dibahas disorot '(emiten)'."
        + _thin_peer_note(stats, ("market_cap", "pe", "pb") + (() if bank else ("ev_ebitda",))
                          + ("roe", "net_margin", "leverage")))]
    regional = regional_reference_exhibit(ticker)
    if regional:
        exhibits.append(regional)
    caps = [r["metrics"]["market_cap"] for r in rows if r["metrics"].get("market_cap")]
    subject = next(r for r in rows if r["is_self"])
    paragraphs = [
        f"Grup peer berisi {len(rows)} emiten dengan kapitalisasi Rp{_rp_bn(min(caps))} "
        f"miliar sampai Rp{_rp_bn(max(caps))} miliar." if caps else "",
    ]
    pe_signal, roe_signal = ranked.get("peer.pe") or {}, ranked.get("peer.roe") or {}
    pe_median, pb_median = stats["pe"][0], stats["pb"][0]
    own_pe = subject["metrics"].get("pe")
    if own_pe is not None and not pe_median and 0 < own_pe <= fmt.MULT_CAP:
        valid = [(r["symbol"], r["metrics"]["pe"]) for r in rows if not r["is_self"]
                 and isinstance(r["metrics"].get("pe"), (int, float))
                 and method_chain.PEER_PE_BAND[0] < r["metrics"]["pe"] <= method_chain.PEER_PE_BAND[1]]
        paragraphs.append(
            f"Median dan rata-rata P/E peer tidak dihitung karena peer valid kurang dari tiga; "
            f"P/E {ticker} {fmt.mult(own_pe)} dibanding "
            + (", ".join(f"{sym} {fmt.mult(v)}" for sym, v in valid) if valid else "tanpa peer valid")
            + ", sehingga posisi relatifnya hanya indikatif.")
    if pe_signal.get("value") is not None and pe_median:
        paragraphs.append(
            (f"P/E {ticker} di atas {fmt.MULT_CAP}x (laba terlalu kecil untuk bermakna) dibanding median peer "
             if pe_signal["value"] > fmt.MULT_CAP else
             f"P/E {ticker} {fmt.mult(pe_signal['value'])} dibanding median peer ") +
            f"{fmt.mult(pe_median)}, sementara ROE berada di peringkat "
            f"{roe_signal.get('rank') or '-'} dari {roe_signal.get('n') or '-'}.")
    outliers = [r["symbol"] for r in rows
                if (r["metrics"].get("pe") or 0) > method_chain.PEER_PE_BAND[1]]
    negative = [r["symbol"] for r in rows if r["metrics"].get("pe") is None and not r["is_self"]]
    # A peer with assets (ROA) but no book-based ratio has zero or negative equity.
    no_book = [r["symbol"] for r in rows if not r["is_self"] and (
        (isinstance(r["metrics"].get("pb"), (int, float)) and r["metrics"]["pb"] <= 0) or
        (r["metrics"].get("roa") is not None and all(
            r["metrics"].get(k) is None for k in ("pb", "roe", "leverage"))))]
    if outliers or negative or no_book:
        paragraphs.append(
            "Pencilan: " + ", ".join(
                ([f"P/E di atas {method_chain.PEER_PE_BAND[1]:.0f}x ({', '.join(outliers)})"]
                 if outliers else []) +
                ([f"laba negatif atau P/E tidak tersedia ({', '.join(negative)})"] if negative else []) +
                ([f"ekuitas negatif atau tidak dilaporkan ({', '.join(no_book)})"]
                 if no_book else []))
            + "; pencilan tidak masuk median dan rata-rata.")
    cross = []
    inputs = valuation_inputs or {}
    thin = {key: stats["counts"].get(key, 0) < method_chain.MIN_PEERS for key in ("pe", "pb")}
    if inputs.get("eps_idr") and (pe_median or thin["pe"]):
        cross.append([f"P/E median peer x EPS {inputs['label']}", "n.m.", "n.m."] if thin["pe"]
                     else [f"P/E median peer x EPS {inputs['label']}", fmt.mult(pe_median),
                           f"Rp{fmt.rp(fmt.tick(pe_median * inputs['eps_idr']))}"])
    if inputs.get("bvps_idr") and (pb_median or thin["pb"]):
        basis = f"P/B median peer x BVPS {inputs.get('bvps_period', 'terakhir')}"
        cross.append([basis, "n.m.", "n.m."] if thin["pb"] else
                     [basis, fmt.mult(pb_median), f"Rp{fmt.rp(fmt.tick(pb_median * inputs['bvps_idr']))}"])
    if cross:
        if inputs.get("tp"):
            cross.append(["Target harga metode utama", inputs.get("method_label", "-"),
                          f"Rp{fmt.rp(inputs['tp'])}"])
        exhibits.append(_exhibit(
            "Cross-check nilai per saham dengan multiple peer",
            ["Basis", "Multiple", "Nilai per saham"], cross,
            f"Sumber: {peers['source']} dan estimasi Sektoral. Cross-check tidak dirata-ratakan "
            "dengan metode utama; P/E dan P/B peer bukan EV/EBITDA dan berbeda struktur modal."
            + _thin_peer_note(stats, ("pe", "pb"))))
        peer_ev = [p for p in intake.get("peers") or []
                   if isinstance(p.get("ev_ebitda"), (int, float))]
        paragraphs.append(
            "Multiple peer di bawah ini hanya cross-check: EV/EBITDA peer dibangun dari "
            f"laporan tiap peer ({method_chain.peer_ev_sources(intake.get('peers'))}) dan "
            f"tersedia untuk {len(peer_ev)} peer; ia dipakai di rantai metode, bukan di tabel "
            "ini." if peer_ev else
            "Multiple peer di bawah ini hanya cross-check: EBITDA dan utang bersih peer belum "
            "tersedia dari laporan peer (Sectors atau snapshot Yahoo Finance), sehingga "
            "EV/EBITDA peer belum dapat diverifikasi.")
    # 1-year own-history P/E and P/BV bands (mean, median, current, percentile).
    band = own_history_bands(intake)
    if band:
        exhibits.append(band)
        exhibits.extend(band_charts(intake))
        swaps = [(sub, orig, why) for sub, orig, why in band_selection(_band_data(intake))
                 if orig]
        paragraphs.append(
            "Band historis P/E dan P/BV adalah cross-check mean-reversion atas sejarah emiten "
            "sendiri, bukan target harga: harga implisitnya menganggap driver fundamental "
            "(EPS dan BVPS terakhir) konstan dan hanya multiple yang kembali ke mean atau median."
            + "".join(f" Grafik band memakai {sub} sebagai pengganti {orig} karena {why}; "
                      f"harga implisit {sub} = multiple x basis per saham terakhir dikurangi "
                      "utang bersih per saham." for sub, orig, why in swaps))
    else:
        paragraphs.append("Band historis P/E dan P/BV belum dimodelkan: "
                          "cache membutuhkan harga harian + EPS/BVPS TTM yang sebanding; "
                          "cakupan saat ini tidak cukup.")
    return _page("Perbandingan peer", _merge_paragraphs(paragraphs), exhibits)


def _merge_paragraphs(paragraphs):
    """One paragraph for the issuer's position in its group (composition,
    multiple vs median, outliers) and one for the method notes (cross-check,
    bands), instead of a string of one-sentence paragraphs."""
    texts = [p.strip() for p in paragraphs if p and p.strip()]
    notes = ("Multiple peer", "Band historis")
    position = [t for t in texts if not t.startswith(notes)]
    method = [t for t in texts if t.startswith(notes)]
    return [" ".join(group) for group in (position, method) if group]


PUBLICATION_LAG_DAYS = 90  # annual results assumed public ~3 months after FY end


def _band_data(intake):
    """Own-history P/E and P/BV series over the cached daily window.

    Each close is divided by the annual EPS/BVPS already published on that
    date (FY end + PUBLICATION_LAG_DAYS). Returns None when the window is
    under 40 trading days or no base exists.
    """
    shares = intake.get("shares") or 0
    annuals = [a for a in intake.get("annuals") or [] if isinstance(a.get("year"), int)]
    if len(annuals) < 2 or not shares:
        return None
    # Struktur slide 5: a 1-year band. IDX closes cover it; the Sectors cache
    # (about three months) is the fallback.
    idx = idx_history.load(intake["ticker"], intake.get("as_of"))
    if idx:
        end = idx["points"][-1][0]
        points = [(d, c) for d, c in idx["points"] if (end - d).days <= 365]
        source = "harga harian IDX (ringkasan perdagangan)"
    else:
        try:
            daily = (local_data.cache_get(intake["ticker"], f"/daily/{intake['ticker']}/") or {}).get("data") or []
        except Exception:
            daily = []
        points = []
        for row in daily[-250:]:
            day = _day(row.get("date")) if isinstance(row, dict) else None
            close = _num(row.get("close")) if isinstance(row, dict) else None
            if day and close:
                points.append((day, close))
        source = f"Sectors daily {intake['ticker']}"
    if len(points) < 40:
        return None

    def base_on(day, key):
        known = [a for a in annuals
                 if date(a["year"], 12, 31) + timedelta(days=PUBLICATION_LAG_DAYS) <= day
                 and isinstance(a.get(key), (int, float))]
        return (known[-1][key] / shares, known[-1]["year"]) if known else (None, None)

    def net_debt_on(day):
        """Net debt per share of the annual already published on ``day``."""
        known = [a for a in annuals
                 if date(a["year"], 12, 31) + timedelta(days=PUBLICATION_LAG_DAYS) <= day]
        if not known or not all(isinstance(known[-1].get(k), (int, float))
                                for k in ("total_debt", "cash")):
            return None
        return (known[-1]["total_debt"] - known[-1]["cash"]) / shares

    months = max(1, round((points[-1][0] - points[0][0]).days / 30.4))
    out = {"window": f"{months} bulan", "start": points[0][0], "end": points[-1][0],
           "source": source, "multiples": {}}
    # P/E and P/BV are the template's bands; EV/EBITDA and EV/Sales are the
    # substitutes a report shows when one of them is not meaningful
    # (``band_selection``). EV = close x current shares + debt - cash of the
    # annual already published on that day.
    for label, key, ev in (("P/E", "earnings", False), ("P/BV", "equity", False),
                           ("EV/EBITDA", "ebitda", True), ("EV/Sales", "revenue", True)):
        series = []
        for day, close in points:
            base, year = base_on(day, key)
            debt = net_debt_on(day) if ev else 0.0
            if base and base > 0 and debt is not None and (close + debt) > 0:
                series.append((day, (close + debt) / base, base, year, debt))
        if len(series) < 40:
            continue
        mults = sorted(m for _, m, _, _, _ in series)
        cur, base_now = series[-1][1], series[-1][2]
        out["multiples"][label] = {
            "series": [(d, m) for d, m, _, _, _ in series],
            "mean": sum(mults) / len(mults), "median": statistics.median(mults),
            "current": cur, "percentile": sum(1 for m in mults if m <= cur) / len(mults) * 100,
            "base_now": base_now, "base_year": series[-1][3], "net_debt_now": series[-1][4],
            "constant_base": len({round(b, 6) for _, _, b, _, _ in series}) == 1}
    return out if any(k in out["multiples"] for k in BAND_MULTIPLES) else None


BAND_MULTIPLES = ("P/E", "P/BV")            # the template's own-history bands
BAND_SUBSTITUTES = ("EV/EBITDA", "EV/Sales")  # in this order when one is not meaningful
_BAND_BASE = {"P/E": "EPS", "P/BV": "BVPS", "EV/EBITDA": "EBITDA per saham",
              "EV/Sales": "pendapatan per saham"}


def _band_problem(data, label):
    """Why a multiple's band is not meaningful, or None when it is: it must
    cover about a year, end on the last close (a positive base today) and
    stay within the multiple cap."""
    m = data["multiples"].get(label)
    base = _BAND_BASE[label].split(" ")[0]
    if not m:
        return f"basis {base} tidak positif sepanjang jendela"
    first, last = m["series"][0][0], m["series"][-1][0]
    if last < data["end"]:
        after = last + timedelta(days=1)
        return (f"{base} FY{_published_year_on(data, label, after)} tidak positif sejak "
                f"{after.isoformat()}, sehingga {label} kini tidak bermakna")
    if (last - first).days < 330:
        months = max(1, round((last - first).days / 30.4))
        return (f"basis {base} tidak positif sebelum {first.isoformat()}, sehingga band {label} "
                f"hanya {months} bulan" if first > data["start"] else
                f"data harga harian hanya {months} bulan")
    if max(m["mean"], m["median"]) > fmt.MULT_CAP:
        return (f"{label} di atas {fmt.MULT_CAP}x (basis {base} sangat kecil), "
                "sehingga band-nya tidak bermakna")
    return None


def _published_year_on(data, label, day):
    """The fiscal year whose annual is published on ``day`` (FY end + lag)."""
    year = day.year - 1
    return year if date(year, 12, 31) + timedelta(days=PUBLICATION_LAG_DAYS) <= day else year - 1


def band_selection(data):
    """[(label, replaces, why)] for the two band charts: P/E and P/BV, each
    replaced by the first meaningful substitute (EV/EBITDA, else EV/Sales)
    when its own band is not meaningful. ``replaces``/``why`` are None for a
    template multiple shown as is."""
    out, used = [], set()
    for label in BAND_MULTIPLES:
        why = _band_problem(data, label)
        if why is None:
            out.append((label, None, None))
            continue
        sub = next((s for s in BAND_SUBSTITUTES if s not in used
                    and _band_problem(data, s) is None), None)
        if sub:
            used.add(sub)
            out.append((sub, label, why))
        elif label in data["multiples"]:
            out.append((label, None, None))  # nothing better: the short band as is
    return out


def _implied(m, label):
    """Implied price per share at a multiple (EV multiples less net debt)."""
    debt = m.get("net_debt_now") or 0.0 if label.startswith("EV/") else 0.0
    return lambda multiple: multiple * m["base_now"] - debt


def own_history_bands(intake):
    """Struktur slide 5 lower half: own-history band table (mean, median,
    current percentile, implied price at mean and median reversion). A
    substitute band (EV/EBITDA or EV/Sales, ``band_selection``) adds its row
    and the note states why it replaces P/E or P/BV."""
    data = _band_data(intake)
    if not data:
        return None
    swaps = [(sub, orig, why) for sub, orig, why in band_selection(data) if orig]
    rows = []
    for label in BAND_MULTIPLES + tuple(sub for sub, _, _ in swaps):
        m = data["multiples"].get(label)
        if not m:
            rows.append([label, "NA", "NA", "NA", "basis fundamental historis tidak cukup"])
            continue
        # A base that is no longer positive (the latest annual is a loss or
        # negative equity) leaves no current multiple and no implied price.
        stale = m["series"][-1][0] < data["end"]
        meaningless = stale or max(m["mean"], m["median"]) > fmt.MULT_CAP
        price = _implied(m, label)
        implied = ("n.m." if meaningless else
                   f"Rp{fmt.rp(fmt.tick(price(m['mean'])))} / "
                   f"Rp{fmt.rp(fmt.tick(price(m['median'])))}")
        rows.append([label, fmt.mult(m["mean"], cap=fmt.MULT_CAP), fmt.mult(m["median"], cap=fmt.MULT_CAP),
                     "n.m." if stale else
                     f"{fmt.mult(m['current'], cap=fmt.MULT_CAP)} (p{m['percentile']:.0f})", implied])
    stale = [label for label in BAND_MULTIPLES if label in data["multiples"]
             and data["multiples"][label]["series"][-1][0] < data["end"]]
    constant = [label for label, m in data["multiples"].items()
                if m["constant_base"] and label in [r[0] for r in rows] and label not in stale]
    replaced = {orig for _, orig, _ in swaps}

    def row_note(label):
        """What a template row reads when its band is not meaningful."""
        m = data["multiples"][label]
        if label in stale:
            return (f"mean dan median {label} atas periode basis positif; kolom kini dan harga "
                    "implisit ditulis n.m. (tanpa basis positif saat ini)")
        if (m["series"][-1][0] - m["series"][0][0]).days < 330:
            return f"baris {label} memakai jendela yang lebih pendek itu"
        return ""
    shown = [row[0] for row in rows]
    return _exhibit(
        f"Band historis {data['window']} {', '.join(shown[:-1])} dan {shown[-1]} "
        "(bukan target harga)",
        ["Multiple", "Mean", "Median", "Kini (persentil)", "Implisit mean / median"],
        rows,
        f"Source: {data['source']} {data['start'].isoformat()} sampai "
        f"{data['end'].isoformat()} dan laba/ekuitas tahunan Sectors yang "
        f"sudah terbit pada tiap tanggal (akhir tahun buku + {PUBLICATION_LAG_DAYS} hari), saham "
        "kini sebagai basis pro forma. Harga implisit = multiple mean/median x EPS/BVPS terakhir "
        "dengan driver tetap; cross-check reversion, bukan target harga. Multiple di atas "
        f"{fmt.MULT_CAP}x ditulis n.m. karena basis laba atau ekuitas sangat kecil."
        + (f" Basis {', '.join(constant)} tidak berubah sepanjang jendela, sehingga harga "
           "implisitnya sama dengan rata-rata/median harga penutupan." if constant else "")
        + "".join(f" {label}: {row_note(label)} karena {_band_problem(data, label)}."
                  for label in stale if label not in replaced)
        + "".join(f" {sub} menggantikan band {orig} karena {why}"
                  + (f"; {row_note(orig)}" if orig in data["multiples"] and row_note(orig) else "")
                  + "." for sub, orig, why in swaps)
        + (" EV = kapitalisasi pasar (saham kini) + utang - kas dari laporan tahunan yang sudah "
           "terbit; harga implisit EV = multiple x basis per saham - utang bersih per saham "
           "terakhir; kepentingan non-pengendali tidak dikurangkan." if swaps else ""))


def band_charts(intake):
    """Struktur Exhibits 12-13: P/E and P/BV lines with mean (dashed),
    median (dotted) and the current level marked. A band that is not
    meaningful is replaced by EV/EBITDA or EV/Sales (``band_selection``),
    and the chart note states why."""
    data = _band_data(intake)
    if not data:
        return []
    charts = []
    for label, replaces, reason in band_selection(data):
        m = data["multiples"][label]
        # A series shorter than the price window (a negative EPS/BVPS base or a
        # short price history) states its own window in the title.
        first, last = m["series"][0][0], m["series"][-1][0]
        months = max(1, round((last - first).days / 30.4))
        short = (last - first).days < 330
        window = f"{months} bulan" if short else data["window"]
        base = _BAND_BASE[label]
        why = ("" if not short else
               f" Jendela {first.isoformat()} sampai {last.isoformat()} ({months} bulan): "
               + (f"basis {base} tidak positif sebelum {first.isoformat()}."
                  if first > data["start"] else
                  f"basis {base} tidak positif sejak {(last + timedelta(days=1)).isoformat()}."
                  if last < data["end"] else
                  "data harga harian lokal hanya mencakup periode ini."))
        swap = (f" {label} menggantikan band {replaces} karena {reason}; EV = kapitalisasi pasar "
                "(saham kini) + utang - kas dari laporan tahunan yang sudah terbit."
                if replaces else "")
        charts.append({
            "n": 0, "judul": f"Band {label} {window} {intake['ticker']}", "tipe": "band_chart",
            "data": {"label": label, "dates": [d.isoformat() for d, _ in m["series"]],
                     "values": [round(v, 4) for _, v in m["series"]], "mean": m["mean"],
                     "median": m["median"], "current": m["current"],
                     "percentile": m["percentile"]},
            "catatan_sumber": (
                f"Source: {data['source']}; basis "
                f"{base} FY{m['base_year']}; garis putus-putus = "
                f"mean {fmt.mult(m['mean'])}, titik-titik = median {fmt.mult(m['median'])}; "
                f"kini {fmt.mult(m['current'])} di persentil {m['percentile']:.0f}." + why + swap)})
    return charts


# ------------------------------------------ ownership and market activity

def ownership_exhibits(intake):
    exhibits, paragraphs = [], []
    holders = _holders(intake)
    if holders:
        exhibits.append(_exhibit(
            "Pemegang saham utama", ["Pemegang saham", "Kepemilikan (%)"],
            [[name, fmt._id(pct, 1)] for name, pct in holders[:6]],
            (f"Sumber: {intake['major_holders_source']} (Sectors tidak memuat pemegang saham "
             "emiten ini); komposisi dapat berbeda dari tanggal laporan interim."
             if intake.get("major_holders_source") else
             "Sumber: Sectors, company/report, ownership.major_shareholders; komposisi dapat "
             "berbeda dari tanggal laporan interim.")))
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

_RECLASSIFIED = ("laporan resmi mereklasifikasi pendapatan tahun ini; angka Sectors untuk pos "
                 "ini masih sebelum reklasifikasi")


def _official_overlay(row, official, annual):
    """An actual Sectors year with the official figures Key Financials shows.

    Revenue and EBITDA follow the official annual release; EBIT and D&A follow
    the audited figures intake carries (``da_source == "official"``) instead of
    a Sectors value intake rejected. A cost line Sectors reports before a
    revenue reclassification is dropped (n.m. with the reason); operating
    expense is re-derived as gross profit less the official EBIT.
    """
    out, reasons = dict(row), {}
    official, annual = official or {}, annual or {}
    revenue = _num(official.get("revenue"))
    if revenue is not None and _num(row.get("revenue")) and abs(revenue / row["revenue"] - 1) > 0.001:
        out["revenue"] = revenue
        for key in ("cost_of_revenue", "gross_profit", "operating_expense"):
            out[key] = None
            reasons[key] = _RECLASSIFIED
    if annual.get("da_source") == "official" and _num(annual.get("ebit")) is not None:
        out["operating_pnl"] = out["ebit"] = annual["ebit"]
        if _num(annual.get("ebitda")):
            out["ebitda"] = annual["ebitda"]
        if _num(out.get("gross_profit")) is not None:
            out["operating_expense"] = out["gross_profit"] - annual["ebit"]
            out["_opex_derived"] = True
    if _num(official.get("ebitda")) is not None:
        out["ebitda"] = official["ebitda"]
    out["_nm"] = reasons
    return out


def statement_rows(intake, fc, va=None):
    """The five-year statement model behind every forecast table and chart."""
    return forecast_statements.forecast_rows(intake, fc, va)


# Reasons for cells the statements cannot fill (spec §3.1: n.m. with a reason, never NA).
_NO_FORECAST = "skenario forecast belum tervalidasi, sehingga kolom forecast belum dimodelkan"
_NOT_MODELED = "pos ini tidak dihasilkan model forecast"
_NOT_MEANINGFUL = "tidak bermakna karena basis pembanding nol, negatif, atau tidak tersedia"
_BEYOND_MODEL = "tahun ini di luar horizon skenario tervalidasi"
_SECTORS_GAP = "tidak dilaporkan di data Sectors untuk tahun ini"
# Cash-flow reconciling lines: shown only when an actual year's Sectors figures
# do not reconcile, so the table adds up and the reader sees the source gap.
# The harness (T7.cash_flow_actual_reconciliation) accepts them on actual
# columns only; forecast cells must read 0 or n.m.
CASH_GAP_LINE = "Efek kurs dan selisih definisi kas (data sumber)"
FLOW_GAP_LINE = "Selisih komponen arus kas (data sumber)"
_OFFICIAL_USD_GAP = ("rilis tahunan resmi US$ hanya memuat pendapatan, EBITDA, laba dan ekuitas; "
                     "data Sectors untuk pos ini hanya tersedia dalam rupiah hasil konversi")
# Lines Sectors never reports for an actual year, with the reason the note gives.
_SECTORS_ABSENT = {
    "trade_receivables": "Sectors tidak memisahkan piutang usaha; nilainya termasuk aset lancar lainnya",
    "trade_payables": "Sectors tidak memisahkan utang usaha; nilainya termasuk liabilitas lancar lainnya",
    "interest_income": "Sectors tidak memisahkan pendapatan bunga emiten non-bank; nilainya "
                       "termasuk pendapatan (beban) lain-lain",
    "change_in_working_capital": "Sectors hanya memuat total arus kas operasi; perubahan modal "
                                 "kerja termasuk pos operasi lainnya",
    "debt_raised": "Sectors hanya memuat total arus kas pendanaan tanpa rincian",
    "dividends_paid": "Sectors hanya memuat total arus kas pendanaan tanpa rincian",
    "equity_raised": "Sectors hanya memuat total arus kas pendanaan tanpa rincian",
    "other_financing_cash_flow": "Sectors hanya memuat total arus kas pendanaan tanpa rincian",
    "government_bonds": "Sectors tidak memisahkan obligasi pemerintah dan surat berharga",
    "securities": "Sectors tidak memisahkan obligasi pemerintah dan surat berharga",
    "npl": "Sectors tidak memuat kredit bermasalah (NPL)",
    "payout": "Sectors tidak memuat dividen tahunan pada laporan keuangan historis",
    "revolver": "pinjaman penyeimbang kas adalah pos model forecast; utang aktual seluruhnya di "
                "utang jangka pendek dan jangka panjang",
    "revolver_flow": "pinjaman penyeimbang kas adalah pos model forecast; utang aktual seluruhnya "
                     "di penarikan (pembayaran) utang",
}
# Memo lines under short-term debt and debt raised: the part the model draws
# to keep cash at its minimum (``forecast_statements`` revolver). The harness
# (T6.balancing_debt_share) reads the balance-sheet memo line.
REVOLVER_LINE = "Termasuk pinjaman penyeimbang kas (memo)"


def _revolver_note(modeled, money):
    """Why the model draws short-term debt: the years operating cash flow
    falls short of capex and dividends, and how large the balance gets
    against equity."""
    balance = [(f.get("label"), _num(f.get("revolver"))) for f in modeled
               if _num(f.get("revolver"))]
    short = []
    for f in modeled:
        cfo, capex, paid = (_num(f.get(k)) for k in ("operating_cash_flow", "capital_expenditure",
                                                      "dividends_paid"))
        if None not in (cfo, capex) and (_num(f.get("revolver_flow")) or 0.0) > 0.5:
            short.append(f"{f.get('label')} arus kas operasi {money(cfo)} terhadap belanja modal "
                         f"{money(abs(capex))}" + (f" dan dividen {money(abs(paid))}" if paid else ""))
    last = modeled[-1] if modeled else {}
    share = (_num(last.get("revolver")) / _num(last.get("total_equity"))
             if _num(last.get("revolver")) and _num(last.get("total_equity")) else None)
    return (" Baris 'Termasuk pinjaman penyeimbang kas' adalah bagian utang jangka pendek forecast "
            "yang ditarik model agar kas tidak turun di bawah kas minimum (asumsi screening, tanpa "
            "fasilitas atau jadwal pelunasan dari emiten): "
            + "; ".join(f"{label} {money(v)}" for label, v in balance) + "."
            + (" Penarikan terjadi karena " + "; ".join(short) + "." if short else "")
            + (f" Saldonya {fmt.pct(share)} dari total ekuitas {last.get('label')}; pembiayaan "
               "sebenarnya (utang bank, obligasi atau penundaan capex) belum dimodelkan."
               if share is not None else ""))


def financials_page(intake, fc=None, va=None, statements=None):
    """Struktur Slides 6-7: income statement, balance sheet, cash flow and key
    ratios for two actual years and the first three forecast years.

    Actual columns come from Sectors historical_financials (Rp miliar). A US$
    reporter whose official annual release covers both actual years is shown
    in US$ juta like its Key Financials and charts: actual lines from that
    release, forecast lines from the model divided back by the same rate the
    model used (spec §2: the model is in the reporting currency).
    Forecast columns come from ``forecast_statements.forecast_rows``, whose
    rows carry the same keys, so one line function reads both and the
    forecast ties out with Key Financials, the Slide-3 charts and the
    valuation. A cell that cannot be derived shows n.m. and the table note
    gives the reason (the model's own for forecast lines). Banks switch to
    the bank layout (NII, PPOP, provisions; loans, earning assets, deposits;
    yield, cost of funds, NIM, LDR, CAR).
    """
    report = cache.company_report(intake["ticker"]) or {}
    fin = report.get("financials") or {}
    every = sorted((r for r in fin.get("historical_financials") or []
                    if isinstance(r, dict) and r.get("year")), key=lambda r: r["year"])
    if len(every) < 2:
        return None
    actual = every[-2:]
    if statements is None:
        statements = statement_rows(intake, fc, va)
    modeled = [dict(r) for r in (statements.get("rows") or [])[:DISPLAY_FORECAST_YEARS]]
    model_notes = statements.get("notes") or {}
    evidence = intake.get("official_evidence") or {}
    official = {int(r["year"]): r for r in evidence.get("annual_actuals") or [] if r.get("year")}
    fx = _num((intake.get("fx_spot") or {}).get("rate"))
    usd = bool(evidence.get("reporting_currency") == "USD" and fx and fx > 0
               and all(int(a["year"]) in official for a in actual))
    if not usd:
        actual = [_official_overlay(row, official.get(int(row["year"])),
                                    next((a for a in intake.get("annuals") or []
                                          if a.get("year") == int(row["year"])), None))
                  for row in actual]
        every = every[:-2] + actual
    if usd:
        def official_row(year):
            row = official[year]
            parent = row.get("net_profit_attributable")
            return {"year": year, "revenue": row.get("revenue"), "ebitda": row.get("ebitda"),
                    "earnings": parent if parent is not None else row.get("net_profit"),
                    "net_cons": row.get("net_profit"), "total_equity": row.get("equity"),
                    "stockholders_equity": row.get("equity_attributable")}
        every = [official_row(y) for y in sorted(official)]
        actual = [r for r in every if r["year"] in {int(a["year"]) for a in actual}]
        # Per-share values stay in rupiah; ratios have no currency.
        keep = {"year", "label", "eps", "dps", "bvps", "payout", "roe", "interest_coverage"}
        modeled = [{k: (v / fx if k not in keep and isinstance(v, (int, float)) else v)
                    for k, v in r.items()} for r in modeled]
    drawn = any(abs(_num(f.get("revolver")) or 0.0) > 0.5 for f in modeled)
    start = int(modeled[-1]["year"]) if modeled else int(actual[-1]["year"])
    forecast = modeled + [{"year": start + i}
                          for i in range(1, DISPLAY_FORECAST_YEARS - len(modeled) + 1)]
    labels = ([f"{r['year']}A" for r in actual] +
              [r.get("label") or f"FY{int(r['year']) % 100:02d}F" for r in forecast])
    fc_span = f"{labels[len(actual)]}-{labels[-1]}"
    bank = intake.get("model_profile") == "financial_ddm"
    ratios = {int(r["year"]): r for r in fin.get("historical_financial_ratio") or []
              if isinstance(r, dict) and r.get("year")}
    by_year = {int(r["year"]): r for r in every}
    by_year.update({int(r["year"]): r for r in forecast})
    # Every row that is not a forecast column is a Sectors row (actual years
    # and the year before them, which growth and averages read).
    is_actual = lambda r: not any(r is f for f in forecast)
    misses = []

    def get(row, key, zero_is_missing=False):
        value = _num(row.get(key))
        if value is None or (zero_is_missing and value == 0):
            misses.append(key)
            return None
        return value

    def before(row):
        return by_year.get(int(row["year"]) - 1) or {}

    def why(row, missed):
        """The reason a cell reads n.m.: the model's own note for a missing
        forecast key, the Sectors gap for an actual one, else a base effect."""
        absent = [k for k in dict.fromkeys(missed) if _num(row.get(k)) is None]
        overridden = row.get("_nm") or {}
        if is_actual(row) and any(k in overridden for k in absent):
            return next(overridden[k] for k in absent if k in overridden)
        if is_actual(row) and usd:
            return (_OFFICIAL_USD_GAP if absent and row.get("year") in official else
                    "tahun sebelumnya tidak ada di rilis tahunan resmi US$" if absent
                    else _NOT_MEANINGFUL)
        if is_actual(row):
            return next((_SECTORS_ABSENT[k] for k in absent if k in _SECTORS_ABSENT),
                        _SECTORS_GAP if absent else _NOT_MEANINGFUL)
        if not modeled:
            return _NO_FORECAST
        if not any(row is m for m in modeled):
            return _BEYOND_MODEL
        return next((str(model_notes[k]).rstrip(".") for k in absent if model_notes.get(k)),
                    _NOT_MODELED if absent else _NOT_MEANINGFUL)

    def table(specs):
        """Rows for (label, fn, format) specs; a bare label is a section row.
        Returns the rows and, per column kind, {reason: [line labels]}."""
        rows, gaps = [], {"aktual": {}, "forecast": {}}
        for spec in specs:
            if isinstance(spec, str):
                rows.append([spec] + [""] * len(labels))
                continue
            label, fn, show = spec
            cells = [label]
            for row in actual + forecast:
                misses.clear()
                try:
                    value = fn(row)
                except (TypeError, ZeroDivisionError):
                    value = None
                if value is not None:
                    cells.append(show(value))
                    continue
                cells.append("n.m.")
                kind = "aktual" if is_actual(row) else "forecast"
                names = gaps[kind].setdefault(why(row, misses), [])
                if label not in names:
                    names.append(label)
            rows.append(cells)
        return rows, gaps

    def gap_note(gaps):
        parts = []
        for kind, where in (("aktual", "kolom aktual"), ("forecast", f"kolom {fc_span}")):
            if kind == "forecast" and not modeled:
                continue  # the forecast sentence already gives the one reason
            for reason, names in gaps[kind].items():
                parts.append(f"{', '.join(names)} ({where}): {reason}")
        return (" n.m. pada " + "; ".join(parts) + ".") if parts else ""

    def minus(*values):
        return None if any(v is None for v in values) else values[0] - sum(values[1:])

    def neg(value):
        return None if value is None else -abs(value)

    def cash(r):
        return get(r, "cash_and_equivalents") or get(r, "cash_only")

    def net_cons(r):
        value = _num(r.get("net_cons"))
        return value if value is not None else minus(get(r, "earnings_before_tax"), get(r, "tax"))

    def avg(r, key):
        now, prev = get(r, key), _num(before(r).get(key))
        return (now + prev) / 2 if now is not None and prev is not None else now

    def growth(key, zero_is_missing=False):
        def fn(r):
            now = get(r, key, zero_is_missing)
            prev = _num(before(r).get(key))
            return now / prev - 1 if now is not None and prev and prev > 0 else None
        return fn

    def forecast_only(key, fn=None):
        """A line the model may give that Sectors never reports."""
        def read(r):
            if is_actual(r):
                misses.append(key)
                return None
            value = get(r, key)
            return fn(value) if fn and value is not None else value
        return read

    money = (lambda v: fmt._id(v / 1e6, 1)) if usd else _rp_bn
    pct = fmt.pct
    roaa = lambda r: get(r, "earnings") / avg(r, "total_assets")
    roae = lambda r: get(r, "earnings") / avg(r, "total_equity")
    if bank:
        def sectors_ratio(group, key, drivers):
            """Actual years: Sectors' ratio; forecast years: the model's own value."""
            def fn(r):
                if is_actual(r):
                    return _num(((ratios.get(int(r["year"])) or {}).get(group) or {}).get(key))
                for driver in drivers[1:]:
                    get(r, driver)  # records the model keys the ratio would need
                return get(r, drivers[0])
            return fn

        def model_or(key, actual_fn):
            """A ratio the bank model states for forecast years (its own averages:
            the interim year's include the 30 June balances); actual years compute it."""
            def fn(r):
                if not is_actual(r) and _num(r.get(key)) is not None:
                    return _num(r[key])
                return actual_fn(r)
            return fn

        earning = lambda r: get(r, "non_loan_earning_assets")
        avg_earning = lambda r: avg(r, "non_loan_earning_assets")
        funding = lambda r: minus(get(r, "total_deposit"), -(get(r, "other_interest_bearing_liabilities") or 0))
        yield_ea = model_or("yield_on_earning_assets",
                            lambda r: get(r, "interest_income") / avg_earning(r))

        def _cost_of_funds(r):
            prev = before(r)
            now_f = funding(r)
            prev_f = (None if _num(prev.get("total_deposit")) is None else
                      _num(prev.get("total_deposit")) + (_num(prev.get("other_interest_bearing_liabilities")) or 0))
            base = (now_f + prev_f) / 2 if now_f is not None and prev_f is not None else now_f
            return get(r, "interest_expense") / base
        cost_of_funds = model_or("cost_of_funds", _cost_of_funds)
        # NIM on average earning assets in every column, the bank model's driver
        # (Sectors' own ratio divides by the year-end balance).
        nim = model_or("net_interest_margin",
                       lambda r: get(r, "net_interest_income") / avg_earning(r))
        coc = model_or("cost_of_credit", lambda r: get(r, "provision") / avg(r, "gross_loan"))

        def bvps(r):
            if is_actual(r):
                return get(r, "total_equity") / get(r, "outstanding_shares")
            return get(r, "bvps")

        def bvps_growth(r):
            now = bvps(r)
            prev = bvps(before(r))
            return now / prev - 1 if now is not None and prev and prev > 0 else None

        income_rows, income_gaps = table([
            ("Pendapatan bunga", lambda r: get(r, "interest_income"), money),
            ("Beban bunga", lambda r: neg(get(r, "interest_expense")), money),
            ("Pendapatan bunga bersih", lambda r: get(r, "net_interest_income"), money),
            ("Pendapatan non-bunga", lambda r: get(r, "non_interest_income"), money),
            ("Beban operasional", lambda r: neg(get(r, "operating_expense")), money),
            ("Laba sebelum provisi (PPOP)",
             lambda r: get(r, "operating_pnl") + get(r, "provision"), money),
            ("Provisi dan cadangan", lambda r: neg(get(r, "provision")), money),
            ("Laba operasional", lambda r: get(r, "operating_pnl"), money),
            ("Pendapatan (beban) non-operasional",
             lambda r: get(r, "non_operating_income_or_loss"), money),
            ("Laba sebelum pajak", lambda r: get(r, "earnings_before_tax"), money),
            ("Pajak penghasilan", lambda r: neg(get(r, "tax")), money),
            ("Laba bersih konsolidasi", net_cons, money),
            ("Kepentingan non-pengendali", lambda r: neg(minus(net_cons(r), get(r, "earnings"))), money),
            ("Laba bersih", lambda r: get(r, "earnings"), money)])
        balance_rows, balance_gaps = table([
            ("Kredit bruto", lambda r: get(r, "gross_loan"), money),
            ("Cadangan kerugian kredit", lambda r: neg(get(r, "allowance_for_loans")), money),
            ("Kredit bersih", lambda r: get(r, "net_loan"), money),
            ("Obligasi pemerintah", lambda r: get(r, "government_bonds"), money),
            ("Surat berharga", lambda r: get(r, "securities"), money),
            ("Total aset produktif", earning, money),
            ("Aset non-produktif (kas, aset tetap, lain)",
             lambda r: minus(get(r, "total_assets"), earning(r),
                             -abs(get(r, "allowance_for_loans") or 0)), money),
            ("Total aset", lambda r: get(r, "total_assets"), money),
            ("Giro", lambda r: get(r, "current_account"), money),
            ("Tabungan", lambda r: get(r, "savings_account"), money),
            ("Deposito", lambda r: get(r, "time_deposit"), money),
            ("Dana pihak ketiga", lambda r: get(r, "total_deposit"), money),
            ("Liabilitas berbunga lain",
             lambda r: get(r, "other_interest_bearing_liabilities"), money),
            ("Liabilitas tanpa bunga", lambda r: get(r, "non_interest_bearing_liabilities"), money),
            ("Total liabilitas", lambda r: get(r, "total_liabilities"), money),
            ("Total ekuitas", lambda r: get(r, "total_equity"), money),
            ("Total liabilitas dan ekuitas",
             lambda r: get(r, "total_liabilities") + get(r, "total_equity"), money)])
        ratio_rows, ratio_gaps = table([
            "Blok Pendapatan bunga (%)",
            ("Imbal hasil aset produktif", yield_ea, pct),
            ("Biaya dana", cost_of_funds, pct),
            ("Selisih bunga (spread)", lambda r: yield_ea(r) - cost_of_funds(r), pct),
            ("Marjin bunga bersih (NIM)", nim, pct),
            "Blok Efisiensi dan kualitas aset (%)",
            # Computed from the statement: Sectors' cost_to_income field uses another base.
            ("Rasio biaya terhadap pendapatan",
             lambda r: get(r, "operating_expense") / (get(r, "net_interest_income") +
                                                       get(r, "non_interest_income")), pct),
            ("Rasio kredit bermasalah bruto (NPL)", lambda r: get(r, "npl"), pct),
            ("Cakupan cadangan terhadap NPL", lambda r: get(r, "allowance_for_loans") / get(r, "npl"),
             pct),
            ("Biaya kredit (provisi / rata-rata kredit)", coc, pct),
            "Blok Likuiditas, profitabilitas dan permodalan (%)",
            ("Kredit terhadap simpanan (LDR)",
             sectors_ratio("liquidity", "loan_to_deposit_ratio", ("loan_to_deposit_ratio",)), pct),
            ("Rasio CASA",
             sectors_ratio("liquidity", "casa_ratio", ("casa_ratio",)), pct),
            ("ROAE", roae, pct),
            ("ROAA", roaa, pct),
            ("Rasio kecukupan modal (CAR)",
             sectors_ratio("capital", "capital_adequacy_ratio", ("capital_adequacy_ratio",)), pct),
            "Blok Dividen dan nilai buku (%)",
            ("Rasio pembayaran dividen", forecast_only("payout"), pct),
            ("Pertumbuhan BVPS", bvps_growth, pct)])
    else:
        margin = lambda key, zero=False: (lambda r: get(r, key, zero) / get(r, "revenue"))

        def coverage(value):
            return f">{fmt.MULT_CAP}x" if value > fmt.MULT_CAP else fmt.mult(value)

        income_rows, income_gaps = table([
            ("Pendapatan", lambda r: get(r, "revenue"), money),
            ("Beban pokok pendapatan", lambda r: neg(get(r, "cost_of_revenue")), money),
            ("Laba kotor", lambda r: get(r, "gross_profit"), money),
            ("Beban usaha", lambda r: neg(get(r, "operating_expense")), money),
            ("Laba usaha (EBIT)", lambda r: get(r, "operating_pnl"), money),
            ("Pendapatan bunga", forecast_only("interest_income"), money),
            ("Beban bunga", lambda r: neg(get(r, "interest_expense_non_operating")), money),
            # The remainder between EBIT and pre-tax profit after interest, so the
            # statement adds up whichever source gave EBIT (for actual years it
            # also holds interest income, which Sectors does not split out).
            ("Pendapatan (beban) lain-lain",
             lambda r: (_num(r["other_non_operating"])
                        if not is_actual(r) and _num(r.get("other_non_operating")) is not None
                        else minus(get(r, "earnings_before_tax"), get(r, "operating_pnl"),
                                   neg(get(r, "interest_expense_non_operating")),
                                   0 if is_actual(r) else (_num(r.get("interest_income")) or 0))),
             money),
            ("Laba sebelum pajak", lambda r: get(r, "earnings_before_tax"), money),
            ("Pajak penghasilan", lambda r: neg(get(r, "tax")), money),
            ("Kepentingan non-pengendali",
             lambda r: neg(minus(net_cons(r), get(r, "earnings"))), money),
            ("Laba bersih", lambda r: get(r, "earnings"), money)])
        balance_rows, balance_gaps = table([
            ("Kas dan setara kas", cash, money),
            ("Piutang usaha", forecast_only("trade_receivables"), money),
            ("Persediaan", lambda r: get(r, "inventories"), money),
            ("Aset lancar lainnya",
             lambda r: minus(get(r, "current_assets"), cash(r), _num(r.get("inventories")) or 0,
                             _num(r.get("trade_receivables")) or 0), money),
            ("Total aset lancar", lambda r: get(r, "current_assets"), money),
            ("Aset tetap bersih", lambda r: get(r, "fixed_assets"), money),
            ("Aset tidak lancar lainnya",
             lambda r: minus(get(r, "total_assets"), get(r, "current_assets"),
                             get(r, "fixed_assets")), money),
            ("Total aset", lambda r: get(r, "total_assets"), money),
            ("Utang jangka pendek", lambda r: get(r, "short_term_debt"), money)]
            + ([(REVOLVER_LINE, forecast_only("revolver"), money)] if drawn else [])
            + [("Utang usaha", forecast_only("trade_payables"), money),
            ("Liabilitas lancar lainnya",
             lambda r: minus(get(r, "current_liabilities"), _num(r.get("short_term_debt")) or 0,
                             _num(r.get("trade_payables")) or 0), money),
            ("Total liabilitas lancar", lambda r: get(r, "current_liabilities"), money),
            ("Utang jangka panjang", lambda r: get(r, "long_term_debt"), money),
            ("Liabilitas tidak lancar lainnya",
             lambda r: minus(get(r, "non_current_liabilities"),
                             _num(r.get("long_term_debt")) or 0), money),
            ("Total liabilitas", lambda r: get(r, "total_liabilities"), money),
            ("Total ekuitas", lambda r: get(r, "total_equity"), money),
            ("Total liabilitas dan ekuitas",
             lambda r: get(r, "total_liabilities") + get(r, "total_equity"), money)])
        ratio_rows, ratio_gaps = table([
            "Blok Pertumbuhan (%)",
            ("Pendapatan", growth("revenue"), pct),
            ("EBITDA", growth("ebitda", True), pct),
            ("Laba usaha", growth("operating_pnl"), pct),
            ("Laba bersih", growth("earnings"), pct),
            "Blok Profitabilitas (%)",
            ("Marjin laba kotor", margin("gross_profit"), pct),
            ("Marjin EBITDA", margin("ebitda", True), pct),
            ("Marjin usaha", margin("operating_pnl"), pct),
            ("Marjin laba bersih", margin("earnings"), pct),
            ("ROAA", roaa, pct),
            ("ROAE", roae, pct),
            "Blok Leverage (x)",
            ("Net gearing (utang bersih / ekuitas)",
             lambda r: get(r, "net_debt") / get(r, "total_equity"), fmt.mult),
            ("Cakupan bunga (EBIT / beban bunga)",
             lambda r: get(r, "operating_pnl") / get(r, "interest_expense_non_operating"), coverage)])

    def depreciation(r):
        if is_actual(r):
            return minus(get(r, "ebitda", zero_is_missing=True), get(r, "ebit"))
        return get(r, "depreciation")

    def other_operating(r):
        """CFO less net profit, D&A and working capital; for actual years it
        also holds working capital, which Sectors does not split out."""
        if not is_actual(r) and _num(r.get("other_operating_cash_flow")) is not None:
            return _num(r["other_operating_cash_flow"])
        wc = 0 if is_actual(r) else get(r, "change_in_working_capital")
        return minus(get(r, "operating_cash_flow"), get(r, "earnings"), depreciation(r), wc)

    def other_investing(r):
        if not is_actual(r) and _num(r.get("other_investing_cash_flow")) is not None:
            return _num(r["other_investing_cash_flow"])
        return minus(get(r, "investing_cash_flow"), neg(get(r, "capital_expenditure")))

    def other_financing(r):
        if is_actual(r):
            misses.append("other_financing_cash_flow")
            return None
        if _num(r.get("other_financing_cash_flow")) is not None:
            return _num(r["other_financing_cash_flow"])
        return minus(get(r, "financing_cash_flow"), get(r, "debt_raised"),
                     neg(get(r, "dividends_paid")), get(r, "equity_raised"))

    def begin_cash(r):
        if not is_actual(r) and not any(r is m for m in modeled):
            misses.append("cash_begin")  # no forecast for this year: nothing opens it
            return None
        if not is_actual(r) and _num(r.get("cash_begin")) is not None:
            return _num(r["cash_begin"])  # the model's own opening balance
        return cash(before(r))

    # Tie-outs: begin cash + net change = end cash; assets = liabilities + equity.
    # An actual year whose Sectors figures do not reconcile gets an explicit,
    # labelled reconciling line (the source gap, never a forecast plug).
    cash_gaps_text, balance_breaks = [], []
    fx_gap_years, flow_gap_years = [], []
    for r, label in zip(actual + forecast, labels):
        if not is_actual(r) and not any(r is m for m in modeled):
            continue
        begin, change, end = _num(begin_cash(r)), _num(r.get("net_cash_flow")), _num(cash(r))
        misses.clear()
        if is_actual(r) and None not in (begin, change, end) and end and \
                abs(begin + change - end) / abs(end) > 0.001:
            fx_gap_years.append(label)
            cash_gaps_text.append(f"{label}: kas akhir selisih {money(end - begin - change)} "
                                  "dari kas awal + perubahan kas")
        flows = [_num(r.get(k)) for k in ("operating_cash_flow", "investing_cash_flow",
                                          "financing_cash_flow")]
        if is_actual(r) and None not in flows and change is not None and \
                abs(sum(flows) - change) > 0.01 * max(abs(change), abs(sum(flows)), 1):
            flow_gap_years.append(label)
            cash_gaps_text.append(f"{label}: arus kas operasi + investasi + pendanaan "
                                  f"{money(sum(flows))} vs perubahan kas {money(change)}")
        if not is_actual(r):
            assets, liab, equity = (_num(r.get(k)) for k in
                                    ("total_assets", "total_liabilities", "total_equity"))
            if None not in (assets, liab, equity) and assets and \
                    abs(assets - liab - equity) / abs(assets) > 0.001:
                balance_breaks.append(f"{label} selisih {money(assets - liab - equity)}")

    def _settled(value, scale):
        """A forecast residual of floating-point size is the model's exact zero."""
        return 0.0 if value is not None and abs(value) <= 1e-6 * max(abs(scale or 0), 1) else value

    def flow_gap(r):
        """Sectors' net change less CFO + CFI + CFF (actual years); the model's
        own residual, zero by construction, in forecast years."""
        value = minus(get(r, "net_cash_flow"), get(r, "operating_cash_flow"),
                      get(r, "investing_cash_flow"), get(r, "financing_cash_flow"))
        return value if is_actual(r) else _settled(value, _num(r.get("net_cash_flow")))

    def cash_gap(r):
        """End cash less begin cash and net change: FX effects and the gap
        between the balance-sheet and cash-flow cash definitions (actual years)."""
        value = minus(cash(r), begin_cash(r), get(r, "net_cash_flow"))
        return value if is_actual(r) else _settled(value, cash(r))

    cash_rows, cash_gaps = table([
        "Blok Arus kas operasi",
        ("Laba bersih", lambda r: get(r, "earnings"), money),
        ("Depresiasi dan amortisasi", depreciation, money),
        ("Perubahan modal kerja", forecast_only("change_in_working_capital"), money),
        ("Pos operasi lainnya", other_operating, money),
        ("Jumlah arus kas operasi", lambda r: get(r, "operating_cash_flow"), money),
        "Blok Arus kas investasi",
        ("Belanja modal", lambda r: neg(get(r, "capital_expenditure")), money),
        ("Pos investasi lainnya", other_investing, money),
        ("Jumlah arus kas investasi", lambda r: get(r, "investing_cash_flow"), money),
        "Blok Arus kas pendanaan",
        ("Penarikan (pembayaran) utang", forecast_only("debt_raised"), money)]
        + ([(REVOLVER_LINE, forecast_only("revolver_flow"), money)] if drawn else [])
        + [("Dividen dibayar", forecast_only("dividends_paid", neg), money),
        ("Penerbitan (pembelian kembali) saham", forecast_only("equity_raised"), money),
        ("Pos pendanaan lainnya", other_financing, money),
        ("Jumlah arus kas pendanaan", lambda r: get(r, "financing_cash_flow"), money),
        "Blok Saldo kas"]
        + ([(FLOW_GAP_LINE, flow_gap, money)] if flow_gap_years else [])
        + [("Perubahan kas bersih", lambda r: get(r, "net_cash_flow"), money),
           ("Kas awal", begin_cash, money)]
        + ([(CASH_GAP_LINE, cash_gap, money)] if fx_gap_years else [])
        + [("Kas akhir", cash, money),
           ("Arus kas bebas (operasi - capex, memo)",
            lambda r: minus(get(r, "operating_cash_flow"), abs(get(r, "capital_expenditure"))),
            money)])
    if bank:
        # A bank has no capex or working-capital line; keep what either side reports.
        keep = [row for row in cash_rows
                if row[0].startswith("Blok ") or row[0].startswith("Jumlah ")
                or row[0] in ("Laba bersih", "Perubahan kas bersih", "Kas awal", "Kas akhir")
                or any(cell not in ("n.m.", "") for cell in row[1:])]
        dropped = {row[0] for row in cash_rows} - {row[0] for row in keep}
        cash_rows = keep
        for kind in cash_gaps.values():
            for reason in list(kind):
                kind[reason] = [n for n in kind[reason] if n not in dropped]
                if not kind[reason]:
                    del kind[reason]

    usd_reporter = evidence.get("reporting_currency") == "USD"
    spot = intake.get("fx_spot") or {}
    basis = statements.get("basis") or "skenario analis"
    fc_sentence = (
        f" Kolom {fc_span}: {basis}, dari model laporan keuangan lima tahun yang memakai skenario "
        "yang sama dengan Key Financials dan valuasi."
        + (f" Forecast US$ = nilai rupiah model dibagi kurs Rp{fmt.rp(fx)}/US$ "
           f"({spot.get('date', '-')}), kurs yang sama dengan model." if usd else
           f" Forecast berpelaporan USD dikonversi pada kurs Rp{fmt.rp(spot.get('rate'))}/USD "
           f"({spot.get('date', '-')}), sedangkan aktual memakai konversi Sectors, sehingga "
           f"pertumbuhan {labels[len(actual)]} terhadap {labels[len(actual) - 1]} memuat efek kurs."
           if usd_reporter and spot.get("rate") else "")
        if modeled else f" Kolom {fc_span} ditulis n.m.: {_NO_FORECAST}.")
    source = (f"Sumber aktual: {evidence.get('annual_source_title') or 'rilis tahunan resmi emiten'}"
              " (US$ juta, mata uang pelaporan)" if usd else
              "Sumber: Sectors, company/report (historical_financials), dalam Rp miliar sesuai "
              "konversi Sectors")
    note = source + "; angka negatif dalam kurung." + fc_sentence
    bank_model = bank and statements.get("mode") == forecast_statements.MODE_BANK_DRIVER
    balance_note = note + gap_note(balance_gaps) + (
        " Neraca forecast tidak seimbang: " + "; ".join(balance_breaks) + "."
        if balance_breaks else
        " Total aset = total liabilitas dan ekuitas di setiap kolom forecast; kas mengikuti "
        "arus kas, bukan angka penyeimbang." if modeled and not bank else
        " Total aset = total liabilitas dan ekuitas di setiap kolom forecast; aset "
        "non-produktif (kas, aset tetap, aset lain) = total aset - aset produktif + cadangan "
        "dan pada kolom forecast dijaga pada porsi historisnya terhadap total aset; aset "
        "produktif selain kredit (penempatan, surat berharga) adalah pos penyeimbang model "
        "driver bank."
        if modeled and bank_model else "")
    gap_lines = [line for line, years in ((FLOW_GAP_LINE, flow_gap_years),
                                          (CASH_GAP_LINE, fx_gap_years)) if years]
    cf_note = note + gap_note(cash_gaps) + (
        " Selisih data sumber pada kolom aktual: " + "; ".join(cash_gaps_text)
        + ". Angka aktual adalah data Sectors apa adanya: kas di neraca dan kas di laporan arus "
        "kas memakai definisi berbeda (misalnya penempatan jangka pendek atau giro di bank "
        "sentral), ditambah efek kurs dan reklasifikasi. Baris "
        + " dan ".join(f"'{line}'" for line in gap_lines)
        + " menampilkan selisih itu secara eksplisit"
        + (" (" + CASH_GAP_LINE.split(" (")[0].lower() + " = kas akhir - kas awal - perubahan kas"
           if fx_gap_years else " (")
        + ("; " if fx_gap_years and flow_gap_years else "")
        + ("selisih komponen = perubahan kas - arus kas operasi, investasi dan pendanaan"
           if flow_gap_years else "")
        + ") sehingga kolom aktual terekonsiliasi; baris ini bukan angka penyeimbang model"
        + (" dan pada kolom forecast bernilai 0 karena kas proyeksi terekonsiliasi tanpa pos "
           "penyeimbang." if modeled and not bank else ".")
        if cash_gaps_text else
        " Kas awal + perubahan kas = kas akhir, dan kas akhir sama dengan kas di neraca.")
    if not bank:
        cf_note += ((" Pos operasi lainnya pada kolom aktual memuat perubahan modal kerja dan "
                     "pos non-kas lain;" if not usd else "")
                    + " arus kas bebas adalah memo, bukan FCFF.")
    derived = [f"{r['year']}A" for r in actual if r.get("_opex_derived")]
    bundled = [f.get("label") for f in modeled if _num(f.get("other_non_operating")) is not None
               and _num(f.get("interest_expense_non_operating")) is None]
    interest_note = (f" Pendapatan (beban) lain-lain {', '.join(bundled)} termasuk beban bunga "
                     "bersih, karena skenario tidak memisahkan bunga (laba sebelum pajak dikurangi "
                     "laba usaha)." if bundled else "")
    revolver_note = _revolver_note(modeled, money) if drawn else ""
    official_note = ((" Pendapatan, EBITDA, laba usaha dan D&A aktual mengikuti laporan resmi "
                      "yang sama dengan Key Financials; beban usaha " + ", ".join(derived)
                      + " = laba kotor Sectors dikurangi laba usaha resmi (termasuk pendapatan dan "
                      "beban operasi lain); pendapatan (beban) lain-lain = laba sebelum pajak "
                      "dikurangi laba usaha dan beban bunga.") if derived else
                     " Pendapatan (beban) lain-lain = laba sebelum pajak dikurangi laba usaha dan "
                     "beban bunga." if not bank else "")
    cols = ["US$ juta" if usd else "Rp miliar"] + labels
    exhibits = [
        _exhibit("Laba rugi" + (" bank" if bank else ""), cols, income_rows,
                 note + gap_note(income_gaps) + official_note + interest_note),
        _exhibit("Neraca" + (" bank" if bank else ""), cols, balance_rows,
                 balance_note + revolver_note),
        _exhibit("Arus kas", cols, cash_rows, cf_note),
        _exhibit("Rasio utama", ["Rasio"] + labels, ratio_rows,
                 (source + "; rasio dari angka US$" if usd else
                  "Sumber: Sectors, company/report (historical_financials dan "
                  "historical_financial_ratio)")
                 + "; ROAA/ROAE memakai rata-rata saldo awal dan akhir "
                 "tahun; satu desimal, angka negatif dalam kurung."
                 + (" NIM, imbal hasil aset produktif dan biaya kredit memakai rata-rata saldo "
                    "awal dan akhir tahun (rasio NIM Sectors memakai saldo akhir); kolom forecast "
                    "pertama memakai rata-rata tiga saldo termasuk 30 Juni, sama dengan model "
                    "driver bank; LDR = kredit bersih / DPK, CAR kolom forecast adalah proksi "
                    "screening." if bank else "") + fc_sentence
                 + gap_note(ratio_gaps))]
    assumptions = [str(a) for a in statements.get("assumptions") or [] if str(a).strip()]
    if modeled and assumptions:
        exhibits.append(_exhibit(
            "Asumsi proyeksi laporan keuangan", ["Asumsi dan sumbernya"],
            [[a] for a in assumptions],
            "Sumber: model laporan keuangan Sektoral; asumsi analis atau screening yang "
            "dilabeli, dari sumber yang sama dengan valuasi."))
    tie = ("laba bersih, dividen dan ekuitas" if bank else
           "pendapatan, EBITDA dan laba bersih")
    actual_source = "rilis tahunan resmi dalam US$" if usd else "data Sectors"
    paragraph = (
        f"Laporan keuangan {labels[0]}-{labels[-1]}: dua tahun aktual dari {actual_source} dan tiga "
        f"tahun pertama model forecast lima tahun ({basis}). {tie[0].upper() + tie[1:]} forecast "
        "sama dengan Key Financials, grafik kinerja dan exhibit valuasi untuk tahun yang sama; "
        "pos yang tidak dapat diturunkan ditulis n.m. dengan alasannya di catatan tabel."
        if modeled else
        f"Laporan keuangan {labels[0]}-{labels[-1]}: dua tahun aktual dari {actual_source}; kolom "
        f"{fc_span} ditulis n.m. karena {_NO_FORECAST}.")
    return _page("Data keuangan", [paragraph], exhibits)


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
        points = _series(name, intake.get("as_of"))
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


# The bank screening DDM (historical payout on a CAGR screen), not a target.
SCREENING_GRIDS = ("Sensitivitas DDM (CoE x g)", "Sensitivitas Inverse CoE (CoE x ROE)")
_SCREENING_TEXT = "DDM Gordon memberi Rp"


def drop_screening_values(doc):
    """Remove screening fair values a reader could take for the target.

    A draft withholds its target (unless it was built as an illustrative
    internal draft), so it must not print its candidate valuation elsewhere.
    When a scenario DDM sets the value, a second screening DDM grid with another
    base value only contradicts it. Runs after the harness has fixed the
    release status, then renumbers exhibits.
    """
    meta = doc.get("meta") or {}
    draft = meta.get("status") == "draft_non_distributable" and not meta.get("illustrative_scenarios")
    scenario_ddm = str(doc.get("method") or "").startswith("DDM dividen skenario")
    if not (draft or scenario_ddm):
        return

    if draft:
        withheld = "Target harga dan sensitivitas valuasi ditahan sampai tinjauan analis selesai."
        cover = doc.get("cover") or {}
        for index, bullet in enumerate(cover.get("bullets") or []):
            if isinstance(bullet, str) and re.search(
                    r"(?:menetapkan target|target(?:\s+harga)?\s+Rp|nilai model Rp)",
                    bullet, flags=re.I):
                cover["bullets"][index] = withheld
        for paragraph in cover.get("paragraf") or []:
            if not isinstance(paragraph, dict):
                continue
            text = " ".join(str(paragraph.get(key) or "") for key in ("judul", "isi"))
            if re.search(r"(?:menetapkan target|target(?:\s+harga)?\s+Rp|nilai model Rp)",
                         text, flags=re.I):
                paragraph["judul"], paragraph["isi"] = "Status target harga", withheld

        valuation_titles = ("target harga", "nilai model berbasis", "valuasi dan kelengkapan",
                            "cross-check dan bukti lanjutan", "skenario nilai")
        input_exhibits = {
            "kelengkapan sebelum rilis",
            "pemeriksaan sebelum rating dan target harga",
            "bukti lanjutan untuk menguji target harga",
            "input sotp yang belum lengkap",
            "komponen cost of equity",
            "proyeksi dividen",
        }
        for page in doc.get("bagian") or []:
            title = str(page.get("judul") or "").strip().lower()
            if any(title.startswith(prefix) for prefix in valuation_titles):
                if title.startswith(("target harga", "nilai model berbasis", "skenario nilai")):
                    page["judul"] = "Target harga ditahan"
                page["paragraf"] = [withheld]
                page["exhibit"] = [exhibit for exhibit in page.get("exhibit") or []
                                   if (str(exhibit.get("judul") or "").lower()
                                       in input_exhibits or
                                       str(exhibit.get("judul") or "").lower().startswith(
                                           "proyeksi dividen"))]

        # A method-chain table may sit outside the valuation page. Keep the
        # gate evidence, but never leave its selected per-share value or an
        # engine-side "issued" statement visible in a final draft.
        exhibits = list(doc.get("exhibits") or []) + [
            exhibit for page in doc.get("bagian") or []
            for exhibit in page.get("exhibit") or []]
        for exhibit in exhibits:
            if not str(exhibit.get("judul") or "").lower().startswith("rantai metode"):
                continue
            data = exhibit.get("data") or {}
            cols = data.get("cols") or []
            value_columns = [i for i, col in enumerate(cols)
                             if re.search(r"(?:nilai|harga|target).*(?:saham|share)|"
                                          r"(?:saham|share).*(?:nilai|harga|target)",
                                          str(col), re.I)]
            for row in data.get("rows") or []:
                if not isinstance(row, list) or not row:
                    continue
                label = str(row[0]).strip().lower()
                if label.startswith("keputusan rilis") and len(row) > 1:
                    row[1] = "Rating dan target harga ditahan sampai seluruh pemeriksaan selesai."
                if re.search(r"nilai (?:wajar|model) per saham|nilai per saham|target harga", label):
                    for index in range(1, len(row)):
                        row[index] = "Ditahan"
                for index in value_columns:
                    if index < len(row):
                        row[index] = "Ditahan"

        for key in ("rating", "tp", "upside_persen", "tp_sebelumnya"):
            meta.pop(key, None)

    keep = lambda e: e.get("judul") not in SCREENING_GRIDS
    doc["exhibits"] = [e for e in doc["exhibits"] if keep(e)]
    for page in doc.get("bagian") or []:
        if page.get("exhibit"):
            page["exhibit"] = [e for e in page["exhibit"] if keep(e)]
        if draft and page.get("paragraf"):
            page["paragraf"] = [p for p in page["paragraf"] if _SCREENING_TEXT not in p]
    renumber(doc)


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


def trim_key_financials(doc, actual_years=2, forecast_years=DISPLAY_FORECAST_YEARS):
    """Spec §5.4 and the template: two actual and three forecast periods on the
    cover; the model's later years stay in the valuation exhibits."""
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


def _year_end_close(ticker, year, as_of=None):
    """Last IDX close in December of ``year`` (a historical multiple needs the
    price of its own period, spec §5.4), with its date."""
    history = idx_history.load(ticker, as_of) or {}
    closes = [(day, close) for day, close in history.get("points") or []
              if day.year == year and day.month == 12]
    return closes[-1] if closes else None


def shape_key_financials(doc, intake, fc=None, va=None, statements=None):
    """Struktur Exhibit 3: Key Financials rows and 2A+3F columns per template.

    Non-bank: Pendapatan, EBITDA, Pertumbuhan EBITDA, Laba bersih, EPS,
    Pertumbuhan EPS, PER, PBV, EV/EBITDA. Bank: Pendapatan, Laba bersih, EPS,
    Pertumbuhan EPS, BVPS, ROE, DPS, PER, PBV (no EBITDA, spec §5.4). Values the
    narrative already wrote (revenue, EBITDA, profit, EPS, forward PER and
    EV/EBITDA) stay; per-share forecasts come from the statement model,
    forward multiples use the current price, actual multiples the year-end
    close of that year. A cell that cannot be derived reads n.m. and the note
    says why.
    """
    kf = next((e for e in doc["exhibits"] if e.get("judul") == "Key Financials"), None)
    if not kf:
        return
    if statements is None:
        statements = statement_rows(intake, fc, va)
    cols, rows = kf["data"]["cols"], kf["data"]["rows"]
    periods = [str(c) if str(c).endswith(("A", "F")) else f"{c}A" for c in cols[1:]]
    n = len(periods)
    actual = [not p.endswith("F") for p in periods]
    bank = intake.get("model_profile") == "financial_ddm"
    model = {r.get("label"): r for r in statements.get("rows") or []}
    modeled = bool(model)
    report = cache.company_report(intake["ticker"]) or {}
    sectors = {int(r["year"]): r for r in (report.get("financials") or {}).get("historical_financials") or []
               if isinstance(r, dict) and r.get("year")}
    price, price_date = _num(intake.get("price")), intake.get("price_date") or "-"
    reasons = {}

    def find(*prefixes):
        return next((r for r in rows if str(r[0]).startswith(prefixes)), None)

    def year_of(i):
        return int(periods[i][:4]) if actual[i] else None

    def sectors_row(i):
        return sectors.get(year_of(i)) or {} if actual[i] else {}

    def model_row(i):
        return {} if actual[i] else (model.get(periods[i]) or {})

    def why_forecast(key):
        if not modeled:
            return ("skenario forecast belum tervalidasi, sehingga kolom forecast belum "
                    "dimodelkan")
        note = (statements.get("notes") or {}).get(key)
        return str(note).rstrip(".") if note else "pos ini tidak dihasilkan model forecast"

    def build(label, existing, compute, keep_actual=True, keep_forecast=True):
        """One row: keep what the narrative wrote, compute the rest, else n.m."""
        old = list(existing[1:]) if existing else []
        cells = [label]
        for i in range(n):
            cur = old[i] if i < len(old) else None
            keep = keep_actual if actual[i] else keep_forecast
            if keep and cur not in (None, "", "NA", "-", "n.a.", "n.m."):
                cells.append(cur)
                continue
            value, reason = compute(i)
            if keep and cur == "n.m.":
                if value is not None and not reason:
                    # The narrative wrote n.m. by its own rule (a growth rate
                    # across zero; above 500% prints '>500%'); name that rule.
                    reason = ("perubahan dari/ke angka negatif tidak bermakna "
                              "sebagai pertumbuhan")
                value = None  # the narrative's n.m. stands; compute only gives its reason
            if value is None:
                cells.append("n.m.")
                kind = "kolom aktual" if actual[i] else "kolom forecast"
                reasons.setdefault((reason, kind), [])
                if label not in reasons[(reason, kind)]:
                    reasons[(reason, kind)].append(label)
            else:
                cells.append(value)
        return cells

    def year_end(i):
        """Market value of equity at the close of an actual year."""
        row = sectors_row(i)
        close = _year_end_close(intake["ticker"], year_of(i), intake.get("as_of"))
        shares = _num(row.get("outstanding_shares"))
        if not close or not shares:
            return None, ("multiple historis memerlukan harga akhir tahun dan jumlah saham tahun "
                          "itu; data harga IDX lokal tidak mencakup tahun ini")
        return close[1] * shares, None

    def multiple(value):
        if value > fmt.MULT_CAP:
            return None, (f"multiple di atas {fmt.MULT_CAP}x tidak bermakna karena basis laba, "
                          "ekuitas atau EBITDA sangat kecil")
        return fmt.mult(value, 1), None

    def per(i):
        if actual[i]:
            mcap, reason = year_end(i)
            earnings = _num(sectors_row(i).get("earnings"))
            if mcap is None:
                return None, reason
            if not earnings or earnings <= 0:
                return None, "laba bersih tahun itu tidak positif"
            return multiple(mcap / earnings)
        eps = _num(model_row(i).get("eps"))
        if eps is None:
            return None, why_forecast("eps")
        return multiple(price / eps) if eps > 0 and price else (
            None, "EPS forecast tidak positif")

    def pbv(i):
        if actual[i]:
            mcap, reason = year_end(i)
            equity = _num(sectors_row(i).get("total_equity"))
            if mcap is None:
                return None, reason
            return multiple(mcap / equity) if equity and equity > 0 else (
                None, "ekuitas tahun itu tidak positif")
        bvps = _num(model_row(i).get("bvps"))
        if bvps is None:
            return None, why_forecast("bvps")
        return multiple(price / bvps) if bvps > 0 and price else (
            None, "BVPS forecast tidak positif")

    # The valuation's dated cash, debt and minority bridge.
    link = scenario_value.bridge(intake) if not bank else {}
    computed_ev = []

    def ev_ebitda(i):
        if actual[i]:
            mcap, reason = year_end(i)
            row = sectors_row(i)
            # The EBITDA the table shows for that year (official where it exists);
            # a US$ reporter's rupiah EBITDA is Sectors' conversion of it.
            ebitda = (_num(row.get("ebitda")) or None) if usd and official_basis \
                else actual_value(year_of(i), "ebitda")
            net_debt = _num(row.get("net_debt"))
            if mcap is None:
                return None, reason
            if not ebitda or ebitda <= 0 or net_debt is None:
                return None, "EBITDA atau utang bersih tahun itu tidak tersedia di data Sectors"
            return multiple((mcap + net_debt) / ebitda)
        ebitda = _num(model_row(i).get("ebitda"))
        if ebitda is None:
            return None, why_forecast("ebitda")
        parts = [_num(link.get(k)) for k in ("shares", "cash", "debt")]
        if None in parts or not price or ebitda <= 0:
            return None, "jembatan EV (kas, utang, saham) valuasi tidak lengkap"
        shares, cash_now, debt = parts
        ev = (price * shares + debt - (cash_now - (_num(link.get("distributions")) or 0))
              + (_num(link.get("nci")) or 0))
        computed_ev.append(periods[i])
        return multiple(ev / ebitda)

    evidence = intake.get("official_evidence") or {}
    official = {int(r["year"]): r for r in evidence.get("annual_actuals") or [] if r.get("year")}
    # The narrative writes actual columns from the official annual release
    # when it covers both actual years, else from Sectors; growth follows it.
    official_basis = all(year_of(i) in official for i in range(n) if actual[i])
    parent_key = ("net_profit_attributable" if official_basis and all(
        official[year_of(i)].get("net_profit_attributable") is not None
        for i in range(n) if actual[i]) else "net_profit")

    usd = evidence.get("reporting_currency") == "USD"
    fx = _num((intake.get("fx_spot") or {}).get("rate")) or 1.0

    def actual_value(year, key):
        if official_basis:
            row = official.get(year) or {}
            return _num(row.get({"ebitda": "ebitda", "earnings": parent_key}[key]))
        # Intake's annuals carry the audited overrides (EBIT, D&A, EBITDA) the
        # narrative writes into Key Financials; raw Sectors otherwise.
        annual = next((a for a in intake.get("annuals") or [] if a.get("year") == year), None)
        value = _num((annual or sectors.get(year) or {}).get(key))
        return value or None if key == "ebitda" else value

    prior_from_sectors = []

    def growth_of(key, model_key):
        def value(i):
            if i < 0:
                if not actual[0]:
                    return None
                prior = year_of(0) - 1
                before = actual_value(prior, key)
                # The audited rows start at the first actual year: the year before
                # comes from Sectors' parent profit (same basis, rupiah reporters).
                if before is None and key == "earnings" and official_basis and not usd:
                    before = _num((sectors.get(prior) or {}).get("earnings"))
                    if before is not None and prior not in prior_from_sectors:
                        prior_from_sectors.append(prior)
                return before
            if actual[i]:
                return actual_value(year_of(i), key)
            value = _num(model_row(i).get(model_key))
            # Official US$ actuals: bring the rupiah model back to US$ first.
            return value / fx if value is not None and official_basis and usd else value

        def compute(i):
            now, before = value(i), value(i - 1)
            if now is None:
                return None, (why_forecast(model_key) if not actual[i] else
                              "tidak tersedia pada data aktual tabel ini")
            if not before or before <= 0 or now < 0:
                return None, "basis tahun sebelumnya nol, negatif, atau tidak tersedia"
            return fmt.pct(now / before - 1), None
        return compute

    eps_growth = find("Pertumbuhan EPS")
    if eps_growth is None and find("Pertumbuhan laba bersih"):
        # EPS uses one pro forma share count in every column, so its growth
        # is the growth of the profit it divides.
        eps_growth = ["Pertumbuhan EPS (%)"] + list(find("Pertumbuhan laba bersih")[1:])
    eps_growth_row = build("Pertumbuhan EPS (%)", eps_growth, growth_of("earnings", "earnings"))
    per_row = build("PER (x)", find("PER"), per, keep_actual=False)
    pbv_row = build("PBV (x)", find("PBV"), pbv, keep_actual=False)
    shares_pf = next((r["earnings"] / r["eps"] for r in model.values()
                      if _num(r.get("earnings")) and _num(r.get("eps"))), None) or \
        share_basis.report_date_shares(intake)[0]

    def eps(i):
        """EPS for a table whose narrative did not write one (Sectors basis, Rp)."""
        if actual[i]:
            earnings = _num(sectors_row(i).get("earnings"))
            if earnings is None or not shares_pf:
                return None, "laba atau jumlah saham tidak tersedia"
            return fmt.rp(round(earnings / shares_pf)), None
        value = _num(model_row(i).get("eps"))
        return (fmt.rp(round(value)), None) if value is not None else (None, why_forecast("eps"))

    base = [find("Pendapatan ("), None if bank else find("EBITDA ("), find("Laba bersih ("),
            find("EPS (") or build("EPS (Rp)", None, eps)]
    if bank:
        shares = shares_pf

        def bvps(i):
            if actual[i]:
                equity = _num(sectors_row(i).get("total_equity"))
                if equity is None or not shares:
                    return None, "ekuitas atau jumlah saham tidak tersedia"
                return fmt.rp(round(equity / shares)), None
            value = _num(model_row(i).get("bvps"))
            return (fmt.rp(round(value)), None) if value is not None else (None, why_forecast("bvps"))

        def roe(i):
            if actual[i]:
                row, prior = sectors_row(i), sectors.get(year_of(i) - 1) or {}
                equity = [_num(r.get("total_equity")) for r in (row, prior)]
                earnings = _num(row.get("earnings"))
                if earnings is None or None in equity:
                    return None, "laba atau ekuitas tahun itu tidak tersedia di data Sectors"
                return fmt.pct(earnings / (sum(equity) / 2)), None
            # Same basis as the actual columns and the ratio table: average equity.
            prior = model_row(i - 1) if not actual[i - 1] else sectors_row(i - 1)
            earnings = _num(model_row(i).get("earnings"))
            equity = [_num(model_row(i).get("total_equity")), _num(prior.get("total_equity"))]
            if earnings is None or None in equity:
                return None, why_forecast("roe")
            return fmt.pct(earnings / (sum(equity) / 2)), None

        def dps(i):
            if actual[i]:
                return None, ("data Sectors mencatat dividen per tanggal ex-date, bukan per "
                              "tahun buku")
            value = _num(model_row(i).get("dps"))
            return (fmt.rp(round(value)), None) if value is not None else (None, why_forecast("dps"))

        shaped = [r for r in base if r] + [
            eps_growth_row,
            build("BVPS (Rp)", find("BVPS"), bvps, keep_actual=False),
            build("ROE (%)", find("ROE"), roe),
            build("DPS (Rp)", None, dps),
            per_row, pbv_row]
    else:
        ebitda_growth = build("Pertumbuhan EBITDA (%)", find("Pertumbuhan EBITDA"),
                              growth_of("ebitda", "ebitda"))
        shaped = [r for r in base[:2] if r] + [ebitda_growth] + [r for r in base[2:] if r] + [
            eps_growth_row, per_row, pbv_row,
            build("EV/EBITDA (x)", find("EV/EBITDA"), ev_ebitda, keep_actual=False)]
    # Every template cell is filled: a value or n.m. (never NA, "-" or blank).
    for row in shaped:
        for i in range(1, len(row)):
            if row[i] in (None, "", "NA", "-", "n.a."):
                row[i] = "n.m."
                key = ("tidak dilaporkan pada sumber data aktual tabel ini" if actual[i - 1] else
                       "tidak dihasilkan skenario untuk tahun ini",
                       "kolom aktual" if actual[i - 1] else "kolom forecast")
                reasons.setdefault(key, [])
                if row[0] not in reasons[key]:
                    reasons[key].append(row[0])
    kf["data"]["cols"] = [cols[0]] + periods
    kf["data"]["rows"] = shaped
    doc["cover"]["key_financials"] = shaped

    note = kf.get("catatan_sumber") or ""
    note = re.sub(r"\s*DPS/yield dan PBV forecast tidak dihitung tanpa asumsi dividen dan ekuitas\.",
                  "", note)
    note = note.replace("NA: belum dimodelkan", "n.m.: belum dimodelkan")
    if not any(str(r[0]).startswith("BVPS") for r in shaped):
        note = note.replace("EPS/BVPS historis", "EPS historis").replace(
            "laba/ekuitas pemilik induk", "laba pemilik induk")
    close_dates = sorted({str(c[0]) for i in range(n) if actual[i]
                          for c in [_year_end_close(intake["ticker"], year_of(i), intake.get("as_of"))]
                          if c})
    note += (" Pertumbuhan EPS sama dengan pertumbuhan laba yang dibagi karena EPS memakai satu "
             "jumlah saham pro forma di semua kolom.")
    if prior_from_sectors and eps_growth_row[1] != "n.m.":
        note += (f" Pertumbuhan EPS {periods[0]} dihitung terhadap laba bersih pemilik induk "
                 + ", ".join(f"FY{y}" for y in prior_from_sectors)
                 + " dari data Sectors, karena laporan resmi yang dipakai tabel ini tidak memuat "
                 "tahun itu.")
    if close_dates:
        note += (" Multiple aktual memakai harga penutupan akhir tahun (IDX, "
                 + ", ".join(close_dates) + ") dengan jumlah saham, laba, ekuitas"
                 + ("" if bank else ", EBITDA dan utang bersih") + " tahun itu dari data Sectors.")
    if modeled:
        note += (f" PER dan PBV forecast memakai harga {price_date} atas EPS dan BVPS model "
                 "laporan keuangan (laba dan ekuitas pemilik induk, jumlah saham valuasi)")
        note += ("; ROE forecast = laba induk / rata-rata ekuitas; DPS = payout x EPS, sama "
                 "dengan exhibit DDM." if bank else
                 f"; EV/EBITDA {', '.join(computed_ev)} = EV kini (harga {price_date}, kas, "
                 f"utang dan minoritas {link.get('cash_basis') or 'neraca valuasi'}) atas "
                 "EBITDA forecast." if computed_ev else ".")
    if reasons:
        note += " n.m. pada " + "; ".join(
            f"{', '.join(names)} ({kind}): {reason}" for (reason, kind), names in reasons.items()) + "."
    kf["catatan_sumber"] = note


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
        return [{"year": r.get("year"), "label": r.get("label"), "revenue": r.get("revenue"),
                 "ebitda": r.get("ebitda"), "net": r.get("net"),
                 "net_attr": r.get("net_attr", r.get("net")),
                 "margin": r.get("margin")} for r in (fc.get("rows") or [])[:FORECAST_YEARS]]
    anchor = fc.get("earnings_scenario") or fc.get("interim_scenario")
    if not anchor:
        return []
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    fx = (intake.get("fx_spot") or {}).get("rate") if usd else 1.0
    if not (isinstance(fx, (int, float)) and fx > 0):
        return []
    idr = lambda v: v * fx if isinstance(v, (int, float)) else None
    full = anchor.get("full_year") or {}
    # The mining interim anchor records consolidated profit only; the parent's
    # share is the last official year's ratio, the basis of Key Financials EPS,
    # so every exhibit shows the same parent profit.
    split = forecast_statements.parent_share(intake, anchor)
    share = split[0] if split else 1.0
    parent = full.get("net_profit_attributable")
    rows = [{"year": anchor["year"], "label": f"FY{anchor['year'] % 100:02d}F",
             "revenue": idr(full.get("revenue")),
             "ebitda": idr(full.get("ebitda")), "net": idr(full.get("net_profit")),
             "net_attr": idr(parent if parent is not None else
                             (full["net_profit"] * share if full.get("net_profit") is not None
                              else None))}]
    for r in ((fc.get("outyear_scenario") or {}).get("rows") or []):
        attr = r.get("net_profit_attributable")
        if split and r.get("net_profit") is not None:
            attr = r["net_profit"] * share
        rows.append({"year": r.get("year"), "label": r.get("label"),
                     "revenue": idr(r.get("revenue")),
                     "ebitda": idr(r.get("ebitda")), "net": idr(r.get("net_profit")),
                     "net_attr": idr(attr)})
    for r in rows:
        r["margin"] = (r["ebitda"] / r["revenue"]
                       if r.get("ebitda") is not None and r.get("revenue") else None)
    return rows[:FORECAST_YEARS]


def combo_charts_page(intake, fc=None, va=None, statements=None):
    """Struktur Slide 3: four combo charts over 2024A-FY28F, each with its own
    narrative, tying out with Key Financials for the same periods.

    Non-bank: revenue and growth, EBITDA and margin, net profit and EPS
    growth, DER and ROE. Bank: revenue and growth, net profit and EPS growth,
    equity and ROE (EBITDA means nothing for a bank), and NIM with cost of
    credit, which the scenario does not drive, so that chart shows actual
    years only. Actual bars solid, forecast lighter; forecast points come
    from the same five-year model as the statements (first three years).
    """
    sectors_history = intake.get("annuals") or []
    if len(sectors_history) < 2:
        return None
    sectors_annuals = sectors_history[-2:]
    frows = chart_forecast_rows(intake, fc)[:DISPLAY_FORECAST_YEARS]
    # A scenario shorter than the display horizon still shows all three
    # forecast years; the missing ones read n.m. (outside the scenario).
    padded = []
    if frows and frows[-1].get("year"):
        for year in range(int(frows[-1]["year"]) + 1,
                          int(frows[-1]["year"]) + 1 + DISPLAY_FORECAST_YEARS - len(frows)):
            padded.append(f"FY{year % 100:02d}F")
            frows = frows + [{"year": year, "label": padded[-1]}]
    if statements is None:
        statements = statement_rows(intake, fc, va)
    model = {r.get("label"): r for r in statements.get("rows") or []}
    num = lambda v: v if isinstance(v, (int, float)) else None
    earnings = lambda a: a.get("earnings") if a.get("earnings") is not None else a.get("net_profit")
    # Key Financials writes its actual years from the official annual release
    # when that covers both years (in the reporting currency), else from
    # Sectors; revenue, EBITDA and profit here use the same numbers, so
    # Slide 3 ties out with Exhibit 3.
    evidence = intake.get("official_evidence") or {}
    official = {int(r["year"]): r for r in evidence.get("annual_actuals") or [] if r.get("year")}
    official_basis = all(int(a["year"]) in official for a in sectors_annuals)
    usd = official_basis and evidence.get("reporting_currency") == "USD"
    fx = num((intake.get("fx_spot") or {}).get("rate"))
    if usd and not fx:
        official_basis = usd = False
    if official_basis:
        parent = ("net_profit_attributable" if all(
            official[int(a["year"])].get("net_profit_attributable") is not None
            for a in sectors_annuals) else "net_profit")
        history = [{"year": y, "revenue": official[y].get("revenue"),
                    "ebitda": official[y].get("ebitda"), "earnings": official[y].get(parent),
                    "net_profit": official[y].get("net_profit")} for y in sorted(official)]
    else:
        history = sectors_history
    annuals = history[-2:]
    to_ccy = (lambda v: v / fx if num(v) is not None else None) if usd else (lambda v: v)
    unit = "US$" if usd else "Rp"
    labels = [f"{a.get('year')}A" for a in annuals] + [r.get("label", "") for r in frows]
    n_act = len(annuals)
    span = f"{labels[0]}-{labels[-1]}"
    is_fc = [False] * n_act + [True] * len(frows)
    bank = intake.get("model_profile") == "financial_ddm"

    def yoy(values, base):
        """Growth in % for each point, the first one against ``base``."""
        out = []
        for prev, cur in zip([base] + values[:-1], values):
            out.append((cur / prev - 1) * 100 if num(cur) is not None and num(prev) and prev > 0
                       else None)
        return out

    def cagr(values):
        vals = [v for v in values if num(v) is not None]
        return ((vals[-1] / vals[0]) ** (1 / (len(vals) - 1)) - 1
                if len(vals) >= 2 and vals[0] > 0 and vals[-1] > 0 else None)

    base = history[-3] if len(history) >= 3 else {}
    if not base and official_basis and not usd:
        # Official rows start at the first actual year: EPS growth of that year
        # reads Sectors' parent profit of the year before, as Key Financials does.
        prior = next((a for a in sectors_history
                      if a.get("year") == int(annuals[0]["year"]) - 1), None)
        base = {"earnings": earnings(prior)} if prior else {}
    rev_bars = [a.get("revenue") for a in annuals] + [to_ccy(r.get("revenue")) for r in frows]
    rev_g = yoy(rev_bars, base.get("revenue"))
    # An unreported EBITDA arrives as 0 from Sectors; it is a gap, not a zero bar.
    ebitda_bars = [a.get("ebitda") or None for a in annuals] + [to_ccy(r.get("ebitda")) for r in frows]
    ebitda_m = [e / r * 100 if num(e) is not None and r else None
                for e, r in zip(ebitda_bars, rev_bars)]
    net_bars = [earnings(a) for a in annuals] + [to_ccy(r.get("net_attr")) for r in frows]
    # EPS uses one share count across the periods (Key Financials basis), so
    # EPS growth is the growth of the parent profit it divides.
    eps_g = yoy(net_bars, earnings(base) if base else None)

    def fc_ratio(key_num, key_den, scale=1.0):
        out = []
        for r in frows:
            row = model.get(r.get("label")) or {}
            top, bottom = num(row.get(key_num)), num(row.get(key_den))
            out.append(top / bottom * scale if top is not None and bottom else None)
        return out

    panels = []
    revenue_title = f"Pendapatan dan pertumbuhan ({span})"
    hist_rev = [a.get("revenue") for a in history[-5:]]
    hist_cagr = cagr(hist_rev)
    fc_rev = rev_bars[n_act:]
    # The accompanying label starts at the first forecast year.  Starting the
    # calculation at the last actual adds an extra year to the denominator and
    # makes the displayed FY26F-FY28F CAGR describe FY25A-FY28F instead.
    fc_cagr = cagr(rev_bars[n_act:]) if any(num(v) for v in fc_rev) else None
    years = f"{history[-5:][0].get('year')}-{history[-1].get('year')}"
    move = lambda g: f"{'naik' if g >= 0 else 'turun'} {fmt.pct(abs(g) / 100)}"
    last_g = rev_g[n_act - 1]
    if hist_cagr is not None and len([v for v in hist_rev if num(v) is not None]) > 2:
        text = f"Pendapatan tumbuh CAGR {fmt.pct(hist_cagr)} pada {years}"
        if last_g is not None:
            text += f" dan {move(last_g)} pada {labels[n_act - 1]}"
    elif last_g is not None:
        text = f"Pendapatan {move(last_g)} pada {labels[n_act - 1]}"
    else:
        text = "Pendapatan historis belum cukup untuk CAGR"
    if fc_cagr is not None:
        pace = ("lebih lambat dari" if fc_cagr < hist_cagr - 0.05 else
                "lebih cepat dari" if fc_cagr > hist_cagr + 0.05 else "sejalan dengan") \
            if hist_cagr is not None else "dibanding"
        text += (f"; skenario {labels[n_act]}-{labels[-1]} memberi CAGR {fmt.pct(fc_cagr)}, "
                 f"{pace} laju historis")
    panels.append((revenue_title, {"label": f"Pendapatan ({unit}) & pertumbuhan", "bars": rev_bars,
                                   "line": rev_g, "is_forecast": is_fc}, labels, text + "."))

    if not bank:
        hist_m = [a["ebitda"] / a["revenue"] for a in history[-5:]
                  if num(a.get("ebitda")) and a.get("revenue")]
        fc_m = [m for m in ebitda_m[n_act:] if m is not None]
        if hist_m:
            text = (f"Margin EBITDA {labels[n_act - 1]} "
                    f"{fmt.pct(ebitda_m[n_act - 1] / 100) if ebitda_m[n_act - 1] is not None else 'n.m.'}"
                    f" dibanding rata-rata {len(hist_m)} tahun {fmt.pct(sum(hist_m) / len(hist_m))}")
            text += (f"; skenario membawa margin ke {fmt.pct(fc_m[-1] / 100)} pada {labels[-1]}, "
                     + ("di atas" if fc_m[-1] / 100 > sum(hist_m) / len(hist_m) + 0.02 else
                        "di bawah" if fc_m[-1] / 100 < sum(hist_m) / len(hist_m) - 0.02 else
                        "sejalan dengan") + " rata-rata historis."
                     if fc_m else "; skenario belum memodelkan EBITDA, sehingga margin historis "
                     "menjadi acuan.")
        else:
            text = ("EBITDA tidak dilaporkan pada data Sectors untuk periode ini; margin "
                    "EBITDA tidak ditampilkan.")
        has_ebitda = any(num(v) is not None for v in ebitda_bars)
        panels.append((f"EBITDA dan margin ({span})",
                       {"label": f"EBITDA ({unit}) & margin" if has_ebitda else "EBITDA belum dimodelkan",
                        "bars": ebitda_bars, "line": ebitda_m, "is_forecast": is_fc},
                       labels, text))

    last_rev_g, last_net_g = rev_g[n_act - 1], eps_g[n_act - 1]
    if last_rev_g is not None and last_net_g is not None:
        gap = last_net_g - last_rev_g
        text = (f"Laba bersih {labels[n_act - 1]} {'naik' if last_net_g >= 0 else 'turun'} "
                f"{fmt.pct(abs(last_net_g) / 100)} dibanding pendapatan "
                f"{'naik' if last_rev_g >= 0 else 'turun'} {fmt.pct(abs(last_rev_g) / 100)}")
        if abs(gap) > 5:
            now, before = sectors_annuals[-1], sectors_annuals[-2]
            items = []
            for key, name in (("interest", "beban bunga"), ("tax", "pajak")):
                a_now, a_before = _num(now.get(key)), _num(before.get(key))
                if a_now is not None and a_before:
                    items.append(f"{name} {'naik' if a_now >= a_before else 'turun'} "
                                 f"{fmt.pct(abs(a_now / a_before - 1))}")
            text += ("; selisihnya berasal dari pos di bawah laba usaha (" + ", ".join(items) + ")"
                     if items else "; selisihnya berasal dari pos di bawah laba usaha")
        text += "."
    else:
        text = "Pertumbuhan laba bersih belum dapat dibandingkan dengan pendapatan."
    net_cagr = cagr(net_bars[n_act:]) if any(num(v) for v in net_bars[n_act:]) else None
    if net_cagr is not None and fc_cagr is not None:
        text += (f" Pada {labels[n_act]}-{labels[-1]} laba bersih tumbuh CAGR {fmt.pct(net_cagr)} "
                 f"dibanding pendapatan {fmt.pct(fc_cagr)}.")
    panels.append((f"Laba bersih dan pertumbuhan EPS ({span})",
                   {"label": f"Laba bersih ({unit}) & pertumbuhan EPS", "bars": net_bars,
                    "line": eps_g, "is_forecast": is_fc}, labels, text))

    mining_panel = None if bank else _mining_ops_panel(intake, va, labels, n_act, frows, is_fc)
    base_sectors = sectors_history[-3] if len(sectors_history) >= 3 else {}
    equity = [num(a.get("equity")) for a in sectors_annuals] + [
        num((model.get(r.get("label")) or {}).get("total_equity")) for r in frows]
    # ROE on average equity, the ROAE of the ratio table and Key Financials.
    profit = [num(earnings(a)) for a in sectors_annuals] + [
        num((model.get(r.get("label")) or {}).get("earnings")) for r in frows]
    roe = []
    for i, (now, gain) in enumerate(zip(equity, profit)):
        prev = equity[i - 1] if i else num(base_sectors.get("equity"))
        mean = (now + prev) / 2 if now is not None and prev is not None else None
        roe.append(gain / mean * 100 if gain is not None and mean and mean > 0 else None)
    if bank:
        text = (f"Ekuitas {labels[n_act - 1]} Rp{fmt._id(equity[n_act - 1] / 1e12, 1)} triliun "
                f"dengan ROE {fmt.pct(roe[n_act - 1] / 100)}"
                if equity[n_act - 1] and roe[n_act - 1] is not None else "Ekuitas aktual belum lengkap")
        payout = next((num(r.get("payout")) for r in statements.get("rows") or []
                       if num(r.get("payout")) is not None), None)
        if equity[-1] and roe[-1] is not None:
            text += (f"; skenario membawa ekuitas ke Rp{fmt._id(equity[-1] / 1e12, 1)} triliun dan "
                     f"ROE {fmt.pct(roe[-1] / 100)} pada {labels[-1]}"
                     + (f", dengan payout {fmt.pct(payout)} dari laba" if payout is not None else ""))
        panels.append((f"Ekuitas dan ROE ({span})",
                       {"label": "Ekuitas (Rp) & ROE", "bars": equity, "line": roe,
                        "is_forecast": is_fc}, labels, text + "."))
        # NIM and cost of credit on average balances (the ratio table's and the
        # bank model's definition). Actual years from Sectors; forecast years
        # from the bank driver model, else n.m. with the scenario's reason.
        report = cache.company_report(intake["ticker"]) or {}
        fin = report.get("financials") or {}
        hist = {int(r["year"]): r for r in fin.get("historical_financials") or []
                if isinstance(r, dict) and r.get("year")}
        nim, coc = [], []
        average = lambda now, before, key: (
            (_num(now.get(key)) + _num(before.get(key))) / 2
            if _num(now.get(key)) is not None and _num(before.get(key)) is not None
            else _num(now.get(key)))
        for a in sectors_annuals:
            year = int(a["year"])
            now, before = hist.get(year) or {}, hist.get(year - 1) or {}
            assets = average(now, before, "non_loan_earning_assets")
            income = _num(now.get("net_interest_income"))
            nim.append(income / assets * 100 if income is not None and assets else None)
            loans = average(now, before, "gross_loan")
            provision = _num(now.get("provision"))
            coc.append(abs(provision) / loans * 100 if provision is not None and loans else None)
        for r in frows:
            row = model.get(r.get("label")) or {}
            nim.append(num(row.get("net_interest_margin")) * 100
                       if num(row.get("net_interest_margin")) is not None else None)
            coc.append(num(row.get("cost_of_credit")) * 100
                       if num(row.get("cost_of_credit")) is not None else None)
        has_fc = any(v is not None for v in nim[n_act:] + coc[n_act:])
        text = (f"NIM {labels[n_act - 1]} {fmt.pct(nim[n_act - 1] / 100)}"
                + (f" dengan biaya kredit {fmt.pct(coc[n_act - 1] / 100)}"
                   if coc[n_act - 1] is not None else "")
                + "; keduanya driver utama laba bank, bukan leverage"
                if nim[n_act - 1] is not None else
                "NIM belum tersedia di data Sectors untuk periode ini")
        if has_fc and nim[-1] is not None and coc[-1] is not None:
            text += (f". Model driver bank membawa NIM ke {fmt.pct(nim[-1] / 100)} dan biaya "
                     f"kredit ke {fmt.pct(coc[-1] / 100)} pada {labels[-1]}")
        text += "."
        cols = labels if frows else labels[:n_act]
        nim, coc = nim[:len(cols)], coc[:len(cols)]
        panels.append((f"NIM dan biaya kredit ({cols[0]}-{cols[-1]}"
                       + (")" if frows else ", aktual)"),
                       {"label": "NIM (%) & biaya kredit", "bars": nim, "line": coc,
                        "is_forecast": is_fc[:len(cols)], "bar_unit": "%"},
                       cols, text))
    elif mining_panel:
        # Finite-life miner: production volume (bars) vs unit cost (line),
        # Struktur-Template's mining/E&P fourth chart.
        panels.append(mining_panel)
    else:
        # A negative equity makes DER meaningless; leave the bar out.
        der = [a["liab"] / a["equity"] if num(a.get("liab")) is not None and num(a.get("equity"))
               and a["equity"] > 0 else None for a in sectors_annuals] + [
            v if v is not None and v >= 0 else None
            for v in fc_ratio("total_liabilities", "total_equity")]
        has_fc = any(v is not None for v in der[n_act:] + roe[n_act:])
        cols = labels if has_fc else labels[:n_act]
        parts = []
        if der[n_act - 1] is not None and roe[n_act - 1] is not None:
            parts.append(f"Liabilitas terhadap ekuitas {labels[n_act - 1]} "
                         f"{fmt.mult(der[n_act - 1])} dengan ROE "
                         f"{fmt.pct(roe[n_act - 1] / 100)}: " +
                         ("pertumbuhan didanai leverage yang meningkat"
                          if der[n_act - 2] and der[n_act - 1] > der[n_act - 2] * 1.1
                          else "rasio tidak naik material"))
        elif any(num(a.get("equity")) is not None and a["equity"] <= 0 for a in sectors_annuals):
            parts.append("Ekuitas aktual sempat negatif, sehingga DER dan ROE aktual tidak "
                         "bermakna")
        if has_fc and der[-1] is not None and roe[-1] is not None:
            parts.append(f"skenario membawa DER ke {fmt.mult(der[-1])} dan ROE ke "
                         f"{fmt.pct(roe[-1] / 100)} pada {labels[-1]}")
        elif has_fc and roe[-1] is not None:
            parts.append(f"skenario membawa ROE ke {fmt.pct(roe[-1] / 100)} pada {labels[-1]}")
        text = ("; ".join(parts) + ".") if parts else \
            "Data leverage/ROE belum lengkap untuk periode ini."
        text = text[0].upper() + text[1:]
        panels.append((f"DER dan ROE ({cols[0]}-{cols[-1]})",
                       {"label": "DER (x) & ROE", "bars": der[:len(cols)], "line": roe[:len(cols)],
                        "is_forecast": is_fc[:len(cols)]}, cols, text))

    notes = statements.get("notes") or {}
    reasons = {"Produksi tembaga": (_MINING_VOLUME_GAP, _MINING_C1_GAP),
               "Pendapatan": (notes.get("revenue"), "basis tahun sebelumnya nol atau negatif"),
               "EBITDA": (notes.get("ebitda"), "pendapatan atau EBITDA tidak tersedia"),
               "Laba bersih": (notes.get("earnings"), "laba tahun sebelumnya nol atau negatif"),
               "DER": (notes.get("total_liabilities"), "ekuitas rata-rata tidak positif"),
               "Ekuitas": (notes.get("total_equity"), "ekuitas rata-rata tidak positif"),
               "NIM": (notes.get("net_interest_margin") or "skenario bank tidak memodelkan NIM",
                       notes.get("cost_of_credit") or "skenario bank tidak memodelkan biaya kredit")}

    def explain(panel, cols, text):
        """Name forecast points left empty (n.m.) and why, next to the chart."""
        name = panel["label"].split(" (")[0].split(" &")[0]
        bar_reason, line_reason = reasons.get(name, (None, "tidak bermakna"))
        flags = panel.get("is_forecast") or []
        out = []
        for part, reason in (("bars", bar_reason or "tidak dimodelkan skenario"),
                             ("line", line_reason)):
            gone = [c for i, c in enumerate(cols) if i < len(flags) and flags[i]
                    and c not in padded and (i >= len(panel[part]) or panel[part][i] is None)]
            if gone:
                what = ("batang" if part == "bars" else "garis")
                out.append(f"{what} {', '.join(gone)} n.m.: {str(reason).rstrip('.')}")
        if padded and any(c in padded for c in cols):
            out.append(f"{', '.join(padded)} n.m.: tahun di luar horizon skenario tervalidasi")
        return text + (" " + "; ".join(out)[0].upper() + "; ".join(out)[1:] + "." if out else "")

    panels = [(title, panel, cols, explain(panel, cols, text))
              for title, panel, cols, text in panels]
    source = (f"Source: Company, Sektoral Estimates; periode {span}; aktual solid, forecast "
              "lebih terang; "
              + (f"pendapatan, EBITDA dan laba dalam US$ seperti Key Financials (forecast rupiah "
                 f"dibagi kurs Rp{fmt.rp(fx)}/US$); " if usd else "")
              + "forecast dari model yang sama dengan Key Financials dan tabel keuangan"
              + (" (DER = total liabilitas / ekuitas; ROE = laba bersih / rata-rata ekuitas)."
                 if not mining_panel else "; volume tambang dari rilis operasi emiten dan jadwal "
                 "LoM valuasi."))
    exhibits = [{"n": 0, "judul": title, "tipe": "combo_panel",
                 "data": {"cols": cols, "series": [panel]}, "narasi": note,
                 "catatan_sumber": source + (panel.pop("source_note", None) or "")}
                for title, panel, cols, note in panels]
    return _page("Kinerja keuangan dan profitabilitas",
                 [f"Empat grafik berikut memakai periode {span} yang sama dengan Key Financials; "
                  "forecast hanya tampil bila skenario tervalidasi."], exhibits)


_MINING_C1_GAP = ("jadwal LoM valuasi hanya memuat sebagian tahun ini (2H), sehingga biaya "
                  "tunai setahun penuh per pon tidak dihitung")
_MINING_VOLUME_GAP = "jadwal LoM atau panduan emiten untuk tahun ini tidak tersedia"


def _mining_ops_panel(intake, va, labels, n_act, frows, is_fc):
    """Mining chart 4 (title, series, cols, narrative) or None: copper in
    concentrate (Mlbs, bars) against Adjusted C1 (US$/lb, line). Actual years
    from the issuer's annual operations (``annual_operations.rows``); forecast
    volumes from the valued LoM schedule (a part year adds the reported 1H),
    else FY guidance for its year. The line is Adjusted C1 for actual years
    and the LoM's own cash cost after the gold credit (``lom.unit_cost``) for
    full forecast years, labelled as a different definition."""
    if intake.get("model_profile") != "finite_life_mining":
        return None
    evidence = intake.get("official_evidence") or {}
    ops = evidence.get("annual_operations") or {}
    by_year = {int(r["year"]): r for r in ops.get("rows") or []
               if isinstance(r, dict) and r.get("year")}
    years = [int(str(label)[:4]) for label in labels[:n_act]]
    if not years or not all(isinstance((by_year.get(y) or {}).get("copper_mlb"), (int, float))
                            for y in years):
        return None
    volume = [float(by_year[y]["copper_mlb"]) for y in years]
    c1 = [by_year[y].get("c1_cost_usd_lb") if isinstance(by_year[y].get("c1_cost_usd_lb"),
                                                          (int, float)) else None
          for y in years]
    gold = [by_year[y].get("gold_koz") for y in years]
    detail = forecast_statements._trace_detail(va, ("sotp_lom",), ("lom",)) or {}
    lom = detail.get("lom") or {}
    inp = lom.get("inputs") or {}
    schedule_t, part_year = {}, set()
    for row in (lom.get("base") or {}).get("rows") or []:
        schedule_t[row["year"]] = schedule_t.get(row["year"], 0.0) + (row.get("cu_rec_t") or 0.0)
        if (row.get("share") or 1.0) < 1.0:
            part_year.add(row["year"])
    guidance = {str(g.get("period")): g for g in evidence.get("management_guidance") or []
                if isinstance(g, dict) and g.get("name") == "Tembaga dalam konsentrat (Mlbs)"}
    model_cost = {int(k): v for k, v in (lom.get("unit_cost") or {}).items()}
    fc_cost = [model_cost.get(int(r["year"])) if r.get("year") else None for r in frows]
    fc_volume, basis = [], []
    for r in frows:
        year = int(r["year"]) if r.get("year") else None
        tonnes = schedule_t.get(year)
        if tonnes is not None and year in part_year:
            h1 = _num(inp.get("h1_cu_t"))
            tonnes = tonnes + h1 if h1 is not None else None
        if tonnes is not None:
            fc_volume.append(tonnes * lom_mod.LB_PER_T / 1e6)
            basis.append((r.get("label"), "1H aktual + 2H jadwal LoM" if year in part_year
                          else "jadwal LoM valuasi"))
        elif _num((guidance.get(f"FY{year}") or {}).get("value")) is not None:
            fc_volume.append(float(guidance[f"FY{year}"]["value"]))
            basis.append((r.get("label"), f"panduan emiten FY{year}"))
        else:
            fc_volume.append(None)
    last = labels[n_act - 1]
    text = (f"Tembaga dalam konsentrat {last} {fmt._id(volume[-1], 0)} juta pon "
            f"({'turun' if volume[-1] < volume[0] else 'naik'} "
            f"{fmt.pct(abs(volume[-1] / volume[0] - 1))} dari {labels[0]})")
    if all(isinstance(g, (int, float)) for g in gold):
        text += f", emas {fmt._id(gold[-1], 0)} ribu oz dari {fmt._id(gold[0], 0)} ribu oz"
    if c1[-1] is not None:
        text += (f"; Adjusted C1 {'(' + fmt._id(-c1[-1], 2) + ')' if c1[-1] < 0 else fmt._id(c1[-1], 2)}"
                 " US$/lb"
                 + (" (negatif: kredit emas dan perak melebihi biaya tunai)"
                    if c1[-1] < 0 else ""))
    known = [f"{label} {fmt._id(v, 0)} ({how})" for (label, how), v in
             zip(basis, [v for v in fc_volume if v is not None])]
    if known:
        text += ". Volume forecast (juta pon): " + ", ".join(known)
    costed = [(r.get("label"), v) for r, v in zip(frows, fc_cost) if v is not None]
    if costed:
        text += (". Biaya tunai model setelah kredit emas (US$/lb): "
                 + ", ".join(f"{label} {'(' + fmt._id(-v, 2) + ')' if v < 0 else fmt._id(v, 2)}"
                             for label, v in costed))
    text += "."
    sources = "; ".join(dict.fromkeys(
        f"{by_year[y].get('source_title')}, hlm. {by_year[y].get('page')}" for y in years
        if by_year[y].get("source_title")))
    note = ((f" Volume dan C1 aktual: {sources}." if sources else "")
            + " Tembaga = kandungan logam dalam konsentrat yang diproduksi; Adjusted C1 per pon "
            "tembaga terjual, negatif (dalam kurung) bila kredit emas dan perak melebihi biaya "
            "tunai."
            + (" Garis forecast adalah biaya tunai jadwal LoM valuasi per pon tembaga diproduksi: "
               "biaya tambang, olah dan smelter dikurangi pendapatan emas pada dek dasar, tanpa "
               "royalti, bea keluar, G&A korporat dan kredit perak; definisinya bukan Adjusted C1 "
               "emiten, sehingga dibaca sebagai arah, bukan angka yang sebanding."
               if any(v is not None for v in fc_cost) else ""))
    cols = labels
    return (f"Produksi tembaga dan biaya unit C1 ({cols[0]}-{cols[-1]})",
            {"label": "Produksi tembaga (juta pon) & Adjusted C1",
             "bars": volume + fc_volume, "line": c1 + fc_cost,
             "is_forecast": is_fc[:len(cols)], "line_unit": "US$/lb", "source_note": note},
            cols, text)


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
            change = _change_12m(_series(name, intake.get("as_of")))
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
    # One five-year statement model feeds Key Financials, the charts and the
    # statements, so the same year reads the same number everywhere.
    statements = statement_rows(intake, fc, va)
    trim_key_financials(doc)
    shape_key_financials(doc, intake, fc, va, statements)
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

    new_pages = [industry_page(intake), combo_charts_page(intake, fc, va, statements),
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
        new_pages.append(financials_page(intake, fc, va, statements))
    for page in new_pages:
        if page and page["judul"] not in titles:
            pages.append(page)
    if va:
        attach_method_chain(doc, va)
        attach_rate_benchmarks(pages, intake, va)
        # A draft withholds its target, so the consensus table must not print it.
        meta = doc.get("meta") or {}
        released = meta.get("tp") if meta.get("rating") else None
        attach_consensus(pages, intake, va, released_value=released)
    doc["bagian"] = [p for p in sorted(pages, key=lambda p: _rank(p["judul"]))
                     if p["exhibit"] or p["paragraf"] or p.get("cards") or p.get("risks")]
    slim_mining(doc, intake)
    for index, page in enumerate(doc["bagian"]):
        page["halaman"] = index + 2
    renumber(doc)
    return doc


RATE_EXHIBITS = ("Komponen WACC", "Komponen Cost of Equity")


def attach_consensus(pages, intake, va, *, released_value=None):
    """House target vs the dated analyst consensus (app.consensus), just
    before the method chain on the target page."""
    for page in pages:
        exhibits = page.get("exhibit") or []
        at = next((i for i, e in enumerate(exhibits)
                   if e.get("judul") == METHOD_CHAIN_TITLE), None)
        if at is None:
            continue
        if not any(e.get("judul") == consensus.TITLE for e in exhibits):
            exhibits.insert(at, consensus.exhibit(
                intake.get("ticker"), intake.get("as_of"), _num(released_value),
                (va or {}).get("rating"), _num(intake.get("price"))))
        return


def attach_rate_benchmarks(pages, intake, va):
    """The policy-vs-benchmark table (app.rate_benchmarks) right after the
    first WACC or Cost of Equity exhibit; nothing when the report has none."""
    for page in pages:
        exhibits = page.get("exhibit") or []
        at = next((i for i, e in enumerate(exhibits)
                   if str(e.get("judul") or "").startswith(RATE_EXHIBITS)), None)
        if at is None:
            continue
        if any(e.get("judul") == rate_benchmarks.TITLE for e in exhibits):
            return
        table = rate_benchmarks.exhibit(intake.get("ticker"), intake.get("as_of"), va)
        if table:
            exhibits.insert(at + 1, table)
        return


# A mining report argues its target in the main body and keeps a short
# valuation appendix. The FY26 H2 reconstruction (Q2 rebuild, revenue and
# monetisation tests, provisional settlement, inventory and debt-flow
# diagnostics) and a cross-check on an assumed multiple barely move a
# life-of-mine target: they leave the PDF and stay in the report document's
# audit appendix (``lampiran_audit``), which the web trace page shows.
MINING_AUDIT_ONLY = (
    "Persediaan, penjualan, dan batas rekonsiliasi", "Produksi dan penjualan aktual H1",
    "Rekonstruksi aktual Q2", "Jembatan revenue H2", "Output dan penjualan H2",
    "Net realized price", "Harga komoditas dan asumsi realisasi", "Estimasi FY26 dan pembanding",
    "Uji antar-tahap", "Saldo settlement provisional", "Komposisi biaya aktual",
    "Persediaan, gross profit", "Batas bukti kontrak", "Arus kas pinjaman", "Uji monetisasi",
    "Uji realized price", "Uji kapasitas", "Cross-check")
# Side exhibits of the target page that move to the valuation appendix page.
MINING_TARGET_SIDE = ("Komponen WACC", rate_benchmarks.TITLE, "Uji tambahan SOTP/LoM",
                      "Asumsi analis dalam SOTP/LoM", "Bukti lanjutan")
VALUATION_APPENDIX = "Lampiran valuasi: tingkat diskonto, uji dan asumsi"


def slim_mining(doc, intake):
    """Mining reports only: audit-only sections to ``lampiran_audit``, the
    target page's side exhibits to one valuation appendix page."""
    if intake.get("model_profile") != "finite_life_mining":
        return
    kept, audit = [], list(doc.get("lampiran_audit") or [])
    for page in doc.get("bagian") or []:
        (audit if str(page.get("judul") or "").startswith(MINING_AUDIT_ONLY) else kept).append(page)
    target = next((p for p in kept if str(p.get("judul") or "").startswith("Target harga")), None)
    if target:
        side = [e for e in target["exhibit"] if str(e.get("judul") or "").startswith(MINING_TARGET_SIDE)]
        if side:
            target["exhibit"] = [e for e in target["exhibit"] if e not in side]
            at = next((i for i, p in enumerate(kept) if str(p.get("judul") or "").startswith("Data keuangan")),
                      len(kept) - 1)
            kept.insert(at + 1, _page(
                VALUATION_APPENDIX,
                ["Komponen tingkat diskonto dan pembandingnya, uji tambahan dan daftar asumsi analis "
                 "di balik target SOTP/LoM. Lampiran berikutnya memuat royalti, capex, cadangan, "
                 "Elang, jadwal tambang dan jembatan korporat."], side))
    appendix = next((p for p in kept if p.get("judul") == VALUATION_APPENDIX), None)
    if audit and appendix:
        appendix["paragraf"].append(
            f"Rekonstruksi H2 FY26 dan uji rekonsiliasinya ({len(audit)} bagian: Q2 2026, jembatan "
            "revenue dan harga realisasi, settlement provisional, persediaan dan arus pinjaman) "
            "tidak dicetak karena hampir tidak menggerakkan target umur tambang; semuanya tersimpan "
            "di jejak audit laporan.")
    for index, page in enumerate(kept):
        page["halaman"] = index + 2
    doc["bagian"] = kept
    seen = set()
    for page in audit:  # two builders can title a section the same way
        if page["judul"] in seen:
            page["judul"] = f"{page['judul']} (lanjutan)"
        seen.add(page["judul"])
    doc["lampiran_audit"] = audit


def valuation_inputs(intake, fc, va):
    """Numbers the extras need from the selected valuation, when one exists."""
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    target = va.get("scenario_target") or {}
    scenario = fc.get("interim_scenario") or {}
    fx_rate = ((intake.get("fx_spot") or {}).get("rate") or
               (target.get("fx") or {}).get("rate"))
    shares = share_basis.report_date_shares(intake)[0]
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
    # The multiple-based sensitivity page only describes an EV/EBITDA target.
    if (va.get("rating") and target.get("ebitda_usd") and fx_rate and
            (va.get("method_chain") or {}).get("selected") != "sotp_lom"):
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
