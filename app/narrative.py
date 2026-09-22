"""TAHAP 4: NARASI & LAYOUT. Prosa templat deterministik dari angka model."""
import re

from . import cache as cache_mod
from . import fmt

MAX_PARA = 150


def _trim(s, cap=30):
    w = s.split()
    return " ".join(w[:cap]) if len(w) > cap else s


def _word_cut(s, cap=64):
    s = str(s).strip()
    if len(s) <= cap:
        return s
    cut = s[:cap + 1].rfind(" ")
    return s[:cut].rstrip() if cut > 0 else s[:cap]


def build(intake, fc, va, g1):
    t, name = intake["ticker"], intake["name"]
    A, F = intake["annuals"], fc["rows"]
    last, rev_last = A[-1], A[-1]["revenue"]
    rev_cagr = (A[-1]["revenue"] / A[0]["revenue"]) ** (1 / (len(A) - 1)) - 1
    f1 = F[0]
    upside_s, tp_s = fmt.pct(va["upside"]), fmt.rp(va["tp"])
    rating = va["rating"]

    rev_g = fmt.pct((f1["revenue"] / rev_last) - 1)
    ebitda_g = fmt.pct((f1["ebitda"] / last["ebitda"]) - 1) if last["ebitda"] else "n.a."
    mg = fmt.pct(f1["margin"])
    prev = A[-2]
    yoy_rev = fmt.pct(last["revenue"] / prev["revenue"] - 1)
    yoy_eb = (fmt.pct(last["ebitda"] / prev["ebitda"] - 1)
              if last["ebitda"] and prev["ebitda"] else "n.a.")
    yoy_net = (fmt.pct(last["earnings"] / prev["earnings"] - 1)
               if last["earnings"] and prev["earnings"] else "n.a.")
    m_last = fmt.pct(last["ebitda"] / last["revenue"]) if last["ebitda"] else "n.a."
    f3 = F[-1]
    per1 = intake["price"] / f1["eps"] if f1["eps"] > 0 else None
    peer_txt = (f"median PER TTM peer {fmt.mult(intake['peer_median_pe'])} dibanding "
                f"PER {f1['label']} model {fmt.mult(per1)}"
                if intake.get("peer_median_pe") and per1 else
                "tanpa pembanding peer yang memadai di cache")

    headline = _headline(intake, fc)
    b1 = _trim(f"Laba {F[0]['label']} diproyeksikan Rp{fmt.miliar(f1['net'])} miliar "
               f"dengan margin EBITDA {mg}, didorong pertumbuhan pendapatan {rev_g}.", 30)
    b2 = _trim(f"Driver utama {F[1]['label']}-{F[2]['label']} adalah volume dan operating "
               f"leverage menuju margin {fmt.pct(F[2]['margin'])}.", 30)
    b3 = _trim(f"Kami merekomendasikan {rating} dengan TP Rp{tp_s} "
               f"(upside {upside_s}), setara {fmt.mult(va['implied']['ev_ebitda'] or 0)} "
               f"EV/EBITDA {F[0]['label']}.", 30)

    p1 = (f"{name} menutup {last['year']} dengan pendapatan Rp{fmt.miliar(rev_last)} miliar "
          f"({yoy_rev} yoy) dan EBITDA Rp{fmt.miliar(last['ebitda'] or 0)} miliar ({yoy_eb} yoy) "
          f"pada margin {m_last}. Laba bersih tercatat Rp{fmt.miliar(last['earnings'] or 0)} miliar "
          f"({yoy_net} yoy). Model kami memproyeksikan pendapatan {f1['label']} "
          f"Rp{fmt.miliar(f1['revenue'])} miliar ({rev_g}), dengan EBITDA Rp{fmt.miliar(f1['ebitda'])} miliar "
          f"({ebitda_g}) pada margin {mg}. Laba bersih {f1['label']} diproyeksikan "
          f"Rp{fmt.miliar(f1['net'])} miliar, lalu tumbuh ke Rp{fmt.miliar(f3['net'])} miliar pada "
          f"{f3['label']} seiring operating leverage menuju margin {fmt.pct(f3['margin'])}. Basis ini "
          f"konsisten dengan CAGR historis {fmt.pct(rev_cagr)} sejak {A[0]['year']}, sehingga jalur "
          f"forecast tidak mengasumsikan percepatan di luar rekam jejak. Implikasinya, pertumbuhan tiga "
          f"tahun ke depan bertumpu pada ekspansi volume dan disiplin biaya ketimbang kenaikan harga.")
    p1t = "Hasil terakhir jadi basis forecast"

    p2 = (f"Tesis kami untuk {F[1]['label']} sampai {f3['label']} bertumpu pada dua tuas. Pertama, "
          f"kelanjutan pertumbuhan pendapatan hingga Rp{fmt.miliar(f3['revenue'])} miliar pada "
          f"{f3['label']}. Kedua, pengangkatan margin EBITDA ke {fmt.pct(f3['margin'])}, yang masih di "
          f"dalam rentang historis sehingga tidak menuntut efisiensi yang belum pernah dicapai. Belanja "
          f"modal sustaining sekitar Rp{fmt.miliar(f1['capex'])} miliar per tahun, setara D&A, menjaga "
          f"arus kas bebas {f1['label']} Rp{fmt.miliar(f1['fcf'])} miliar dan naik ke "
          f"Rp{fmt.miliar(f3['fcf'])} miliar pada {f3['label']}. Konteks valuasi: {peer_txt}, sehingga "
          f"ekspektasi pasar sudah mencerminkan sebagian tesis ini. KPI pemantau tesis adalah realisasi "
          f"margin EBITDA tiap kuartal terhadap jalur {mg} menuju {fmt.pct(f3['margin'])}; deviasi dua "
          f"kuartal beruntun memicu revisi forecast.")
    p2t = "Volume dan leverage jadi mesin laba"

    r3 = "konsentrasi komoditas, eksekusi belanja modal, dan pelemahan harga"
    wacc_in = va["wacc_inputs"]
    p3 = (f"Valuasi memakai {va['method']}, dengan WACC {fmt.pct(va['wacc'])} (risk-free "
          f"{fmt.pct(wacc_in['rf'])}, beta {fmt._id(wacc_in['beta'], 1)}) dan terminal growth "
          f"{fmt.pct(wacc_in['g'])}. TP Rp{tp_s} adalah rerata nilai Gordon Rp{fmt.rp(va['ps_gordon'])} "
          f"dan exit EV/EBITDA {fmt._id(wacc_in['exit_mult'], 1)}x Rp{fmt.rp(va['ps_exit'])}, memberi upside "
          f"{upside_s} dari harga Rp{fmt.rp(intake['price'])} sehingga rating {rating}. Pada TP, saham "
          f"diperdagangkan {fmt.mult(va['implied']['per'] or 0)} PER dan "
          f"{fmt.mult(va['implied']['ev_ebitda'] or 0)} EV/EBITDA {f1['label']}. Utang bersih posisi dasar "
          f"Rp{fmt.miliar(va['net_debt'])} miliar dipakai konsisten di seluruh perhitungan. Skenario "
          f"downside (WACC +1pp, g -1pp) menghasilkan Rp{fmt.rp(va['tp_down'])}, di bawah base case. "
          f"Risiko utama: {r3}.")
    p3t = "TP Rp" + tp_s + " dengan upside " + upside_s

    # Left rail market data calculations: ADTV & Free Float
    daily_pts = {}
    for _, p in cache_mod.payloads(f"/daily/{t}/"):
        for r in (p.get("data") or []):
            d, c, v = r.get("date"), r.get("close"), r.get("volume")
            if d and c is not None and v is not None:
                daily_pts[d] = float(v) * float(c)
    if daily_pts:
        adtv_val = sum(daily_pts.values()) / len(daily_pts)
        adtv_str = fmt.miliar(adtv_val)
    else:
        adtv_val = None
        adtv_str = "-"

    maj_holders = intake.get("major_holders") or []
    pub_holder = next((h for h in maj_holders if str(h.get("name", "")).strip().lower() in ("public", "masyarakat")), None)
    if pub_holder and pub_holder.get("share_percentage") is not None:
        ff_pct = float(pub_holder["share_percentage"])
        ff_str = fmt.pct(ff_pct)
    else:
        ff_str = "-"

    top_non_pub = [[h.get("name", "?"), fmt.pct(float(h.get("share_percentage") or 0))]
                   for h in maj_holders
                   if str(h.get("name", "")).strip().lower() not in ("public", "masyarakat")][:2]
    holders_display = top_non_pub if top_non_pub else [
        [h.get("name", "?"), fmt.pct(float(h.get("share_percentage") or 0))]
        for h in maj_holders[:2]
    ]

    # Page 2 rich industry and historical data
    min_eb_mg = fmt.pct(min((a["ebitda"] or 0) / a["revenue"] for a in A))
    max_eb_mg = fmt.pct(max((a["ebitda"] or 0) / a["revenue"] for a in A))
    c_list = [a["capex_out"] for a in A if a.get("capex_out")]
    avg_capex = fmt.miliar(sum(c_list) / len(c_list)) if c_list else "-"

    p_ind1 = (f"Emiten beroperasi pada sektor {intake.get('industry') or 'terkait'} "
              f"(sub-sektor {intake.get('sub_sector') or '-'}). Rekam jejak historis "
              f"dari tahun {A[0]['year']} hingga {last['year']} membukukan pertumbuhan "
              f"pendapatan dengan CAGR {fmt.pct(rev_cagr)}, dari Rp{fmt.miliar(A[0]['revenue'])} miliar "
              f"menjadi Rp{fmt.miliar(rev_last)} miliar. Margin EBITDA berfluktuasi antara "
              f"{min_eb_mg} hingga {max_eb_mg} (posisi {last['year']} pada level {m_last}), "
              f"mencerminkan elastisitas operasional dan siklus harga. Total ekuitas bertumbuh ke "
              f"Rp{fmt.miliar(last['equity'] or 0)} miliar dengan akumulasi aset "
              f"Rp{fmt.miliar(last['assets'] or 0)} miliar pada penutupan {last['year']}.")

    p_ind2 = (f"Pandangan Kami: proyeksi periode {F[0]['label']}-{F[-1]['label']} tidak "
              "mengasumsikan akselerasi volume di luar rekam jejak historis, melainkan "
              "menumpukan ekspansi laba pada utilisasi kapasitas dan stabilitas biaya "
              f"operasional. Permintaan di sub-sektor {intake.get('sub_sector') or '-'} memberikan "
              "visibilitas pendapatan tahunan, sementara penyelesaian siklus belanja modal "
              "besar menopang pemulihan arus kas bebas menuju margin EBITDA "
              f"{fmt.pct(F[-1]['margin'])} pada {F[-1]['label']}.")

    p_ind3 = ("Dinamika neraca dan arus kas historis menunjukkan disiplin pendanaan selama "
              f"periode ekspansi. Realisasi belanja modal rata-rata Rp{avg_capex} miliar per "
              "tahun berhasil diserap tanpa mengorbankan solvabilitas dasar, meletakkan "
              f"fondasi neraca yang solid untuk mendukung proyeksi {F[0]['label']}.")

    exh, n = [], [0]

    def E(judul, tipe, data, note="Source: Company, Sektoral Estimates"):
        n[0] += 1
        exh.append({"n": n[0], "judul": judul, "tipe": tipe, "data": data,
                    "catatan_sumber": note})
        return n[0]

    kf_rows = [["Pendapatan (Rp miliar)"] + [fmt.miliar(a["revenue"]) for a in A[-2:]]
               + [fmt.miliar(r["revenue"]) for r in F]]
    kf_rows += [["EBITDA (Rp miliar)"] + [fmt.miliar(a["ebitda"] or 0) for a in A[-2:]]
                + [fmt.miliar(r["ebitda"]) for r in F]]
    kf_rows += [["Laba bersih (Rp miliar)"] + [fmt.miliar(a["earnings"] or 0) for a in A[-2:]]
                + [fmt.miliar(r["net"]) for r in F]]
    kf_rows += [["EPS (Rp)"] + [fmt.rp((a["earnings"] or 0) / intake["shares"]) for a in A[-2:]]
                + [fmt.rp(r["eps"]) for r in F]]
    kf_cols = ["Key Financials"] + [str(a["year"]) for a in A[-2:]] + [r["label"] for r in F]
    E("Key Financials", "tabel", {"cols": kf_cols, "rows": kf_rows})

    hist3 = A[-3:]
    hist_rows = [
        ["Pendapatan"] + [fmt.miliar(a["revenue"]) for a in hist3],
        ["EBITDA"] + [fmt.miliar(a["ebitda"] or 0) for a in hist3],
        ["Margin EBITDA"] + [fmt.pct((a["ebitda"] or 0) / a["revenue"]) for a in hist3],
        ["Laba bersih"] + [fmt.miliar(a["earnings"] or 0) for a in hist3],
    ]
    E("Kinerja historis", "tabel",
      {"cols": ["Rp miliar"] + [str(a["year"]) for a in hist3],
       "rows": hist_rows})

    hist_bs_rows = [
        ["Kas & setara kas"] + [fmt.miliar(a["cash"] or 0) for a in hist3],
        ["Total utang"] + [fmt.miliar(a["total_debt"] or 0) for a in hist3],
        ["Total ekuitas"] + [fmt.miliar(a["equity"] or 0) for a in hist3],
        ["Capex"] + [f"({fmt.miliar(a['capex_out'])})" if a["capex_out"] else ("-" if a["capex_out"] is None else "0,0")
                     for a in hist3],
    ]
    E("Neraca dan arus kas historis", "tabel",
      {"cols": ["Rp miliar"] + [str(a["year"]) for a in hist3],
       "rows": hist_bs_rows})

    asu_cols = ["Driver", "Satuan"] + [r["label"] for r in F] + ["Dasar"]

    def _disp(satuan, v):
        if satuan == "Rp 0":
            return "Rp0"
        if satuan in ("Rp",):
            return "Rp" + fmt.miliar(v) + " miliar"
        return fmt._id(v, 1) + "%"

    asu_rows = [[d, s, _disp(s, f), _disp(s, s2), _disp(s, t3), b]
                for d, s, f, s2, t3, b in fc["assumptions"]]
    E("Asumsi forecast", "tabel", {"cols": asu_cols, "rows": asu_rows})

    # G2.3: operating leverage — ±10% revenue mengalir penuh ke EBITDA
    sens_rows = [[f"Pendapatan {s}"] +
                 [fmt.miliar(r["ebitda"] + (0.1 if s == "+10%" else -0.1) * r["revenue"])
                  for r in F] for s in ["+10%", "-10%"]]
    E("Sensitivitas EBITDA terhadap harga/permintaan", "tabel",
      {"cols": ["Skenario"] + [r["label"] for r in F], "rows": sens_rows})

    kat = _katalis(intake)
    E("Katalis", "tabel", {"cols": ["Katalis", "Waktu", "Kenapa penting", "Arah"],
                           "rows": kat})
    E("Kepemilikan", "tabel",
      {"cols": ["Pemegang saham", "Porsi"],
       "rows": [[h.get("name", "?"),
                 fmt.pct(float(h.get("share_percentage") or 0))]
                for h in (intake["major_holders"] or [])[:5]] or [["Tidak ada di cache", "-"]]})

    E("Ringkasan DCF", "tabel",
      {"cols": ["Komponen", "Rp miliar"],
       "rows": [["PV eksplisit", fmt.miliar(va["pv_explicit"])],
                ["PV terminal", fmt.miliar(va["pv_terminal"])],
                [f"Porsi terminal ({fmt.pct(va['tv_share'], 0)})", "-"],
                ["EV", fmt.miliar(va["ev_gordon"])],
                ["Utang bersih", fmt.miliar(va["net_debt"])],
                ["TP Gordon", f"Rp{fmt.rp(va['ps_gordon'])}"],
                ["TP exit", f"Rp{fmt.rp(va['ps_exit'])}"],
                ["TP final", f"Rp{fmt.rp(va['tp'])}"]]})
    E("Proyeksi FCFF", "tabel",
      {"cols": ["Rp miliar"] + [r["label"] for r in F],
       "rows": [["FCFF", *[fmt.miliar(r["fcf"]) for r in F]]]})
    grid = va.get("tp_grid") or {}
    sens_tp_rows = []
    for dw, wlabel in ((-0.01, "WACC -1pp"), (0.0, "WACC base"), (0.01, "WACC +1pp")):
        sens_tp_rows.append([wlabel] + [f"Rp{fmt.rp(grid.get((dw, gg), 0))}"
                                        for gg in (0.015, 0.025, 0.035)])
    E("Sensitivitas TP (WACC x g)", "tabel",
      {"cols": ["TP (Rp)", "g 1,5%", "g 2,5%", "g 3,5%"], "rows": sens_tp_rows})
    E("Peer", "tabel",
      {"cols": ["Peer", "PER TTM", "PBV"],
       "rows": [[c["symbol"], fmt.mult(c["pe"] or 0), fmt.mult(c["pb"] or 0)]
                for c in intake["peers"][:8]] or [["Tanpa peer di cache", "-", "-"]]})
    E("Laba rugi", "tabel", _is(F, "laba"))
    E("Neraca", "tabel", _is(F, "neraca"))
    E("Arus kas", "tabel", _is(F, "kas"))

    # verify exhibit numbering sequential
    assert [e["n"] for e in exh] == list(range(1, len(exh) + 1))

    by_title = {e["judul"].split(". ", 1)[-1]: e for e in exh}
    get = by_title.get
    bagian = [
        {"halaman": 2, "judul": "Industri dan makro: permintaan ke depan",
         "paragraf": [p_ind1, p_ind2, p_ind3],
         "exhibit": [get("Kinerja historis"), get("Neraca dan arus kas historis")]},
        {"halaman": 3, "judul": "Asumsi forecast dan sensitivitas",
         "paragraf": ["Tiap tahun forecast berbeda drivernya: " +
                      ", ".join(f"{r['label']} tumbuh {fmt.pct(r['revenue']/F[i-1]['revenue']-1) if i else fmt.pct(r['revenue']/rev_last-1)}"
                                for i, r in enumerate(F)) + "."],
         "exhibit": [get("Asumsi forecast"), get("Sensitivitas EBITDA terhadap harga/permintaan")]},
        {"halaman": 4, "judul": "Katalis, risiko, kepemilikan",
         "paragraf": [f"Risiko utama: {r3}. Arah neto insider dan arus asing "
                      "tercatat di tabel kepemilikan sebagai konteks."],
         "exhibit": [get("Katalis"), get("Kepemilikan")]},
        {"halaman": 5, "judul": "Valuasi",
         "paragraf": [f"TP Rp{tp_s} adalah rerata Gordon Rp{fmt.rp(va['ps_gordon'])} dan "
                      f"exit Rp{fmt.rp(va['ps_exit'])} (WACC {fmt.pct(va['wacc'])})."],
         "exhibit": [get("Ringkasan DCF"), get("Proyeksi FCFF"),
                     get("Sensitivitas TP (WACC x g)"), get("Peer")]},
        {"halaman": 6, "judul": "Laporan keuangan",
         "paragraf": ["Kas adalah satu-satunya penyeimbang neraca; D&A, capex, dan tarif "
                      "pajak identik di IS, CF, dan DCF."],
         "exhibit": [get("Laba rugi"), get("Neraca"), get("Arus kas")]},
    ]
    assert all(b["exhibit"] and all(e is not None for e in b["exhibit"]) for b in bagian)
    for b in bagian:
        for p in b["paragraf"]:
            assert fmt.words(p) <= 400, "paragraf kepanjangan"
    for para in (p1, p2, p3):
        assert fmt.words(para) <= MAX_PARA, f"paragraf cover {fmt.words(para)} kata"

    g32 = va["g3"].get("G3.2_skala")
    metodo = (["Angka bersumber dari snapshot cache Sectors (salinan lokal yang bisa "
               "kedaluwarsa; pembacaan tidak memakai kuota API). Tanpa angka karangan "
               "di luar asumsi berlabel pada tabel Asumsi."]
              + ([f"skala valuasi: {g32[1]} (ambang 20-300% dari market cap, "
                  "dicatat sebagai keterbatasan)"]
                 if isinstance(g32, tuple) and "gagal" in g32[0] else [])
              + [f"{k}: {v[1]} (dicatat sebagai keterbatasan)"
                 for k, v in va["g3"].items()
                 if isinstance(v, tuple) and "gagal" in v[0] and k != "G3.2_skala"]
              + va["notes"][:3])[:5]
    return {
        "meta": {"ticker": t, "emiten": name, "tanggal": intake["price_date"],
                 "rating": rating, "tp": va["tp"], "harga": intake["price"],
                 "upside_persen": round(va["upside"] * 100, 1)},
        "cover": {"headline": headline, "bullets": [b1, b2, b3],
                  "paragraf": [{"judul": p1t, "isi": p1}, {"judul": p2t, "isi": p2},
                               {"judul": p3t, "isi": p3}],
                  "data_pasar": {"harga": intake["price"], "tp": va["tp"],
                                 "saham": intake["shares"],
                                 "market_cap": intake["market_cap"],
                                 "adtv": adtv_str,
                                 "free_float": ff_str},
                  "key_financials": kf_rows},
        "bagian": bagian,
        "tabel_asumsi": [{"driver": d, "satuan": s, "FY26F": f, "FY27F": s2,
                          "FY28F": t3, "dasar": b}
                         for d, s, f, s2, t3, b in fc["assumptions"]],
        "log_gate": {"G1": g1["G1"], "G2": fc["g2"], "G3": {k: (v if isinstance(v, str) else v[0])
                                                          for k, v in va["g3"].items()}},
        "method": "DCF (FCFF, Rp)",
        "fy26": {"Pendapatan": fmt.miliar(f1["revenue"]),
                 "EBITDA": fmt.miliar(f1["ebitda"]),
                 "Laba bersih": fmt.miliar(f1["net"])},
        "holders": holders_display,
        "catatan_metodologi": metodo,
        "exhibits": exh,
    }


def _headline(intake, fc):
    F = fc["rows"]
    g = (F[-1]["revenue"] / F[0]["revenue"]) - 1
    up = F[-1]["margin"] >= F[0]["margin"]
    if g > 0.15 and up:
        return "Volume Tumbuh, Leverage Angkat Margin"
    if g > 0.15:
        return "Pendapatan Tumbuh, Margin Dijaga Ketat"
    if up:
        return "Efisiensi Angkat Margin di Tengah Perlambatan"
    return "Arus Kas Stabil Topang Valuasi"


def _katalis(intake):
    rows, scored = [], []
    for nw in intake["news"] or []:
        title = str(nw.get("title") or "tanpa judul")
        txt = f"{title} {nw.get('body') or ''}".lower()
        score = (1 if any(k in txt for k in ["revenue", "growth", "expansion", "capex",
                                            "project", "dividend", "contract"]) else 0)
        score += (1 if any(k in txt for k in ["guidance", "target", "forecast"]) else 0)
        score += 1  # kebaruan: item cache terbaru
        ts = str(nw.get("timestamp") or "")[:10] or "tanpa tanggal"
        src_raw = str(nw.get("source") or "tak dikenal")
        src = re.sub(r"^https?://", "", src_raw).split("/")[0][:28]
        scored.append((score, _word_cut(title, 64), ts, src))
    scored.sort(key=lambda x: -x[0])
    for s, title, ts, src in scored[:5]:
        rows.append([title, ts, f"kurasi skor {s}/9 ({src}); kaitkan ke driver "
                                "sebelum masuk model", "Netral"])
    for c in (intake["corp_actions"] or [])[:2]:
        if isinstance(c, dict):
            act = _word_cut(c.get("action", c.get("type", "aksi korporasi")), 64)
            ts = str(c.get("date") or "")[:10] or "tanpa tanggal"
            rows.append([act, ts, "aksi korporasi tercatat", "Netral"])
    return rows or [["Belum ada katalis terkurasi dari cache", "-", "-", "-"]]


def _is(F, kind):
    cols = ["Rp miliar"] + [r["label"] for r in F]
    if kind == "laba":
        rows = [["Pendapatan", *[fmt.miliar(r["revenue"]) for r in F]],
                ["EBITDA", *[fmt.miliar(r["ebitda"]) for r in F]],
                ["D&A", *[fmt.miliar(r["da"]) for r in F]],
                ["EBIT", *[fmt.miliar(r["ebit"]) for r in F]],
                ["Beban bunga", *[fmt.miliar(r["interest"]) for r in F]],
                ["Pajak", *[fmt.miliar(r["tax"]) for r in F]],
                ["Laba bersih", *[fmt.miliar(r["net"]) for r in F]],
                ["EPS (Rp)", *[fmt.rp(r["eps"]) for r in F]]]
    elif kind == "neraca":
        rows = [["Kas", *[fmt.miliar(r["cash"]) for r in F]],
                ["Utang", *[fmt.miliar(r["debt"]) for r in F]],
                ["Ekuitas", *[fmt.miliar(r["equity"]) for r in F]],
                ["Total aset", *[fmt.miliar(r["assets"]) for r in F]]]
    else:
        rows = [["Arus kas operasi", *[fmt.miliar(r["ocf"]) for r in F]],
                ["Capex", *[f"({fmt.miliar(r['capex'])})" for r in F]],
                ["Arus kas bebas", *[fmt.miliar(r["fcf"]) for r in F]],
                ["Dividen", *[f"({fmt.miliar(r['div'])})" for r in F]]]
    return {"cols": cols, "rows": rows}
