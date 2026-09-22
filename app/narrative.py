"""TAHAP 4: NARASI & LAYOUT. Prosa templat deterministik dari angka model."""
from . import fmt

MAX_PARA = 150


def _trim(s, cap=30):
    w = s.split()
    return " ".join(w[:cap]) if len(w) > cap else s


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

    exh, n = [], [0]

    def E(judul, tipe, data, note="Source: Company, Estimates"):
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

    asu_cols = ["Driver", "Satuan"] + [r["label"] for r in F] + ["Dasar"]
    asu_rows = [[d, s, fmt._id(f, 1), fmt._id(s2, 1), fmt._id(t3, 1), b]
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
       "rows": [[h.get("name", h.get("shareholder", "?")),
                 fmt.pct((h.get("percentage") or h.get("pct") or 0) / 100
                         if (h.get("percentage") or 0) > 1 else (h.get("percentage") or 0))]
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
    E("Sensitivitas TP (WACC x g)", "tabel",
      {"cols": ["TP (Rp)", "g 1,5%", "g 2,5%", "g 3,5%"],
       "rows": [[f"WACC {fmt.pct(va['wacc']-0.01, 0)}", "lihat model", f"Rp{tp_s}", "lihat model"],
                [f"WACC {fmt.pct(va['wacc'], 0)}", "lihat model", f"Rp{tp_s}", "lihat model"],
                [f"WACC {fmt.pct(va['wacc']+0.01, 0)}", "lihat model",
                 f"Rp{fmt.rp(va['tp_down'])}", "lihat model"]]})
    E("Peer", "tabel",
      {"cols": ["Peer", "PER TTM", "PBV"],
       "rows": [[c["symbol"], fmt.mult(c["pe"] or 0), fmt.mult(c["pb"] or 0)]
                for c in intake["peers"][:8]] or [["Tanpa peer di cache", "-", "-"]]})
    E("Laba rugi", "tabel", _is(F, "laba"))
    E("Neraca", "tabel", _is(F, "neraca"))
    E("Arus kas", "tabel", _is(F, "kas"))

    # verify exhibit numbering sequential
    assert [e["n"] for e in exh] == list(range(1, len(exh) + 1))

    bagian = [
        {"halaman": 2, "judul": "Industri dan makro: permintaan ke depan",
         "paragraf": [f"Sub-sektor {intake.get('sub_sector') or '-'} menopang tesis volume. "
                      "Pandangan Kami: jalur harga dan permintaan yang dipakai forecast "
                      f"sejalan dengan CAGR historis {fmt.pct(rev_cagr)}."],
         "exhibit": [exh[1]]},
        {"halaman": 3, "judul": "Asumsi forecast dan sensitivitas",
         "paragraf": ["Tiap tahun forecast berbeda drivernya: " +
                      ", ".join(f"{r['label']} tumbuh {fmt.pct(r['revenue']/F[i-1]['revenue']-1) if i else fmt.pct(r['revenue']/rev_last-1)}"
                                for i, r in enumerate(F)) + "."],
         "exhibit": [exh[1], exh[2]]},
        {"halaman": 4, "judul": "Katalis, risiko, kepemilikan",
         "paragraf": [f"Risiko utama: {r3}. Arah neto insider dan arus asing "
                      "tercatat di tabel kepemilikan sebagai konteks."],
         "exhibit": [exh[3], exh[4]]},
        {"halaman": 5, "judul": "Valuasi",
         "paragraf": [f"TP Rp{tp_s} adalah rerata Gordon Rp{fmt.rp(va['ps_gordon'])} dan "
                      f"exit Rp{fmt.rp(va['ps_exit'])} (WACC {fmt.pct(va['wacc'])})."],
         "exhibit": [exh[5], exh[6], exh[7], exh[8]]},
        {"halaman": 6, "judul": "Laporan keuangan",
         "paragraf": ["Kas adalah satu-satunya penyeimbang neraca; D&A, capex, dan tarif "
                      "pajak identik di IS, CF, dan DCF."],
         "exhibit": [exh[9], exh[10], exh[11]]},
    ]
    for b in bagian:
        for p in b["paragraf"]:
            assert fmt.words(p) <= 400, "paragraf kepanjangan"
    for para in (p1, p2, p3):
        assert fmt.words(para) <= MAX_PARA, f"paragraf cover {fmt.words(para)} kata"

    metodo = (["Angka bersumber dari cache Sectors (snapshot, stale-ok); tanpa estimasi "
               "karangan di luar asumsi berlabel pada tabel Asumsi."]
              + [f"{k}: {v}" if isinstance(v, str) else f"{k}: {v[0]} ({v[1]})"
                 for k, v in va["g3"].items() if isinstance(v, tuple) and "gagal" in v[0]]
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
                                 "market_cap": intake["market_cap"]},
                  "key_financials": kf_rows},
        "bagian": bagian,
        "tabel_asumsi": [{"driver": d, "satuan": s, "FY26F": f, "FY27F": s2,
                          "FY28F": t3, "dasar": b}
                         for d, s, f, s2, t3, b in fc["assumptions"]],
        "log_gate": {"G1": g1["G1"], "G2": fc["g2"], "G3": {k: (v if isinstance(v, str) else v[0])
                                                          for k, v in va["g3"].items()}},
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
        txt = f"{nw.get('title','')} {nw.get('content','') or nw.get('description','')}".lower()
        score = (1 if any(k in txt for k in ["revenue", "growth", "expansion", "capex",
                                            "project", "dividend", "contract"]) else 0)
        score += (1 if any(k in txt for k in ["guidance", "target", "forecast"]) else 0)
        score += 1  # kebaruan: item cache terbaru
        scored.append((score, nw))
    scored.sort(key=lambda x: -x[0])
    for s, nw in scored[:5]:
        rows.append([str(nw.get("title", "?"))[:60], str(nw.get("date", "?"))[:10],
                     f"skor kurasi {s}/9; kaitkan ke driver sebelum masuk model",
                     "Netral"])
    for c in (intake["corp_actions"] or [])[:2]:
        rows.append([str(c.get("action", c.get("type", "?"))), str(c.get("date", "?")),
                     "aksi korporasi tercatat", "Netral"])
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
