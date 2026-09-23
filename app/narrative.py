"""TAHAP 4: NARASI & LAYOUT. Prosa templat deterministik dari angka model."""
import re

from . import cache as cache_mod
from . import ddm
from . import fmt
from . import methodnote
from . import rnav
from . import scrub
from . import valtables

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


def _draft_value(value):
    return "-" if value is None else fmt.miliar(value)


def _rnav_exhibit(lom, cash_idr, debt_idr, shares, discount_pct=0.0):
    """Convert LoM Rp-billion asset values to the raw-IDR table contract."""
    assets = [{"nama": stream["nama"], "nav": stream["nav_rpbn"] * 1e9,
               "kepemilikan": stream["kepemilikan"], "ukuran": stream["ukuran"]}
              for stream in lom["streams"]]
    return valtables.rnav_exhibits(
        assets, cash_idr, debt_idr, 0, shares, discount_pct)


def _build_draft(intake, fc, va, g1):
    """Build a clearly non-distributable evidence/status report.

    Do not expose the legacy DCF target or imply that the historical-CAGR
    mining screen is a production forecast. All reported facts come from the
    Sectors cache; local research documents and analyst estimate files are
    deliberately excluded.
    """
    t, name = intake["ticker"], intake["name"]
    release_result = va.get("release") or {}
    blockers = release_result.get("blockers") or [
        "production release gate has no validated result"
    ]
    profile = intake.get("model_profile") or "unsupported"
    A = intake.get("annuals") or []
    F = fc.get("rows") or []
    exhibits = []

    def add(title, columns, rows, source):
        exhibits.append({"n": len(exhibits) + 1, "judul": title, "tipe": "tabel",
                         "data": {"cols": columns, "rows": rows},
                         "catatan_sumber": source})
        return len(exhibits)

    hist = A[-3:]
    hist_rows = [
        ["Pendapatan (Rp miliar)"] + [_draft_value(a.get("revenue")) for a in hist],
        ["EBITDA (Rp miliar)"] + [_draft_value(a.get("ebitda")) for a in hist],
        ["Laba bersih (Rp miliar)"] + [_draft_value(a.get("earnings")) for a in hist],
    ]
    hist_no = add("Laporan historis di cache",
                  ["Metrik"] + [str(a.get("year", "-")) for a in hist], hist_rows,
                  "Sumber: Sectors cache, company/report; angka historis belum direkonsiliasi ke interim terbaru.")

    quarter = intake.get("latest_quarterly_actual")
    quarter_no = None
    if isinstance(quarter, dict):
        quarter_metrics = (
            ("Pendapatan (Rp miliar)", "revenue"),
            ("EBITDA (Rp miliar)", "ebitda"),
            ("Laba bersih (Rp miliar)", "earnings"),
            ("Capex (Rp miliar)", "capital_expenditure"),
            ("Arus kas operasi (Rp miliar)", "operating_cash_flow"),
            ("Arus kas bebas (Rp miliar)", "free_cash_flow"),
        )
        quarter_rows = [[label, _draft_value(quarter.get(key))]
                         for label, key in quarter_metrics]
        period_end = str(quarter.get("date") or "-")
        quarter_no = add(
            "Kinerja kuartalan yang tersedia di cache",
            ["Metrik", period_end], quarter_rows,
            f"Sumber: Sectors cache, financials/quarterly/{t}; tanggal adalah akhir periode. "
            "Cache tidak menyimpan tanggal publikasi/halaman untuk memvalidasi ketersediaan historis.")

    screening_no = None
    if F:
        screen_rows = [
            ["Pendapatan (Rp miliar)"] + [_draft_value(r.get("revenue")) for r in F],
            ["EBITDA (Rp miliar)"] + [_draft_value(r.get("ebitda")) for r in F],
            ["Laba bersih (Rp miliar)"] + [_draft_value(r.get("net")) for r in F],
            ["Capex (Rp miliar)"] + [_draft_value(r.get("capex")) for r in F],
        ]
        screening_no = add(
            "Screen historis (bukan forecast produksi)",
            ["Metrik"] + [str(r.get("label", "-")) for r in F], screen_rows,
            "Basis: CAGR pendapatan historis dan margin; capex proyek belum terjadwal. "
            "Hanya diagnostik internal, tidak digunakan untuk target harga.")

    news_no = None
    news_analysis = intake.get("news_analysis") or []
    news_rows, news_sources = [], []
    for item in news_analysis:
        if not isinstance(item, dict):
            continue
        news_rows.append([
            str(item.get("timestamp", ""))[:10] or "-",
            str(item.get("summary", "-")),
            str(item.get("connection", "-")),
            str(item.get("caveat", "-")),
        ])
        if item.get("source"):
            news_sources.append(str(item["source"]))
    if news_rows:
        news_no = add(
            "Konteks berita dari cache dan implikasi",
            ["Tanggal", "Narasi ulang", "Kaitan ke tesis", "Batasan"], news_rows,
            "Analisis agen atas berita ticker-spesifik di sectors_cache /news/. "
            "Berita adalah konteks media, bukan guidance; tidak mengubah forecast numerik "
            "tanpa dukungan data finansial/operasi cache. Referensi: " +
            "; ".join(news_sources))

    blocker_groups = {}
    for item in blockers:
        if item.startswith("latest interim actuals"):
            latest_date = ((intake.get("latest_quarterly_actual") or {}).get("date")
                           or "belum tersedia")
            blocker_groups["Validasi interim dari cache"] = (
                f"Baris kuartalan terakhir berakhir {latest_date}; cache belum memberi "
                "tanggal publikasi dan metadata kelengkapan untuk membuktikan data terbaru "
                f"per {intake.get('as_of') or intake.get('price_date')}.")
        elif item.startswith("operating bridge"):
            blocker_groups["Jembatan operasi ke keuangan"] = (
                "Belum ada rangkaian bukti yang menghubungkan produksi fisik ke penjualan, "
                "biaya, EBITDA, capex, modal kerja, utang dan FCFF.")
        elif item.startswith("mining forecast"):
            blocker_groups["Forecast fisik tambang"] = (
                "Forecast fisik-ke-keuangan belum dihitung dan direkonsiliasi; CAGR hanya screening.")
        elif item.startswith("SOTP"):
            blocker_groups["Valuasi SOTP/LoM"] = (
                "NAV per aset dan/atau jembatan ekuitas belum lengkap; target harga ditahan.")
        else:
            blocker_groups[item] = "Belum terpenuhi."
    blocker_no = add(
        "Kelengkapan sebelum rilis", ["Pemeriksaan", "Yang masih diperlukan"],
        [[label, detail] for label, detail in blocker_groups.items()],
        "Status ini memblokir distribusi laporan; detail validasi mesin tersimpan pada artefak JSON.")

    sotp = va.get("sotp") or {}
    sotp_gaps = sotp.get("gaps") or []
    sotp_labels = {
        "assets": "Daftar aset dan NAV",
        "cash_idr": "Kas",
        "debt_idr": "Utang",
        "minority_interest_idr": "Kepentingan nonpengendali",
        "corporate_overhead_idr": "Nilai kini overhead korporat",
        "shares": "Saham terdilusi",
        "discount_pct": "Diskon risiko",
    }
    sotp_reason_labels = {
        "required; provide at least one asset": "Tambahkan sedikitnya satu aset bernilai.",
        "required finite numeric value": "Nilai numerik wajib tersedia; tidak boleh diasumsikan nol.",
        "required finite numeric value in raw IDR": "NAV wajib numerik dalam IDR mentah.",
        "required non-empty text": "Isi nama/status/metode dan provenance sumber.",
        "required finite percentage from 0 to 100": "Persentase kepemilikan wajib bersumber dan antara 0-100.",
    }
    sotp_rows = []
    for gap in sotp_gaps:
        if not isinstance(gap, dict):
            continue
        path = str(gap.get("path", "SOTP"))
        top_field = path.split(".", 1)[0]
        label = sotp_labels.get(path, sotp_labels.get(top_field, path))
        reason = str(gap.get("reason", "-"))
        reason = sotp_reason_labels.get(reason, reason)
        if path.startswith("assets["):
            label = "Aset: " + path.split(".", 1)[-1].replace("_", " ")
        sotp_rows.append([label, reason])
    if not sotp_rows:
        sotp_rows = [["SOTP", "Valuasi belum lengkap"]]
    sotp_no = add(
        "Input SOTP yang belum lengkap",
        ["Input", "Kekurangan"], sotp_rows,
        "SOTP/LoM adalah metode utama untuk aset finite-life. Nilai tidak diisi nol; "
        "target harga ditahan sampai NAV aset dan jembatan ekuitas tervalidasi.")

    profile_basis = intake.get("model_profile_basis") or "basis profil tidak tersedia"
    price_date = intake.get("price_date")
    profile_text = (f"Model profile: {profile} ({profile_basis}). Fakta yang ditampilkan "
                    "dan angka historis hanya berasal dari sectors cache. Belum ada "
                    "forecast fisik-ke-keuangan yang lolos rekonsiliasi; nilai CAGR dan "
                    "RNAV annuitas tidak dipakai sebagai target.")
    release_text = ("Dokumen ini berstatus DRAFT NON-DISTRIBUTABLE. Target harga dan "
                    "rating ditahan karena data interim, forecast fisik, dan provenance "
                    "yang tersedia di cache belum lengkap; SOTP/LoM belum dapat direkonsiliasi. "
                    "Tidak ada target DCF substitusi.")
    sections = [
        {"halaman": 2, "judul": "Kinerja dan bukti yang tersedia",
         "layout": "stack",
         "paragraf": [profile_text],
         "exhibit": [exhibits[hist_no - 1]] +
                    ([exhibits[quarter_no - 1]] if quarter_no else [])},
        {"halaman": 3, "judul": "Valuasi dan kelengkapan model",
         "paragraf": [release_text],
         "exhibit": [exhibits[blocker_no - 1], exhibits[sotp_no - 1]]},
    ]
    next_page = 4
    if news_no:
        sections.append({"halaman": next_page, "judul": "Konteks berita dan kaitannya ke tesis",
                         "layout": "stack",
                         "paragraf": ["Ringkasan berikut diparafrase dari berita dalam cache. "
                                      "Kaitan ke operasi/laba dibedakan dari sentimen pasar; "
                                      "berita tidak menjadi asumsi angka tanpa bukti cache."],
                         "exhibit": [exhibits[news_no - 1]]})
        next_page += 1
    if screening_no:
        sections.append({"halaman": next_page, "judul": "Screen historis untuk diskusi internal",
                         "paragraf": ["Angka berikut adalah screening berbasis data historis, "
                                      "bukan estimasi produksi, guidance, atau target harga."],
                         "exhibit": [exhibits[screening_no - 1]]})

    price = intake["price"]
    market_cap = intake["market_cap"]
    return {
        "meta": {"ticker": t, "emiten": name, "tanggal": price_date,
                 "status": "draft_non_distributable",
                 "rating": "DRAFT NON-DISTRIBUTABLE", "tp": None,
                 "harga": price, "upside_persen": None},
        "cover": {
            "headline": "Target Harga Ditahan: SOTP dan Forecast Belum Lengkap",
            "bullets": [
                "Tidak ada rating atau target harga yang layak didistribusikan.",
                "Data sumber dibatasi pada sectors cache; sumber riset eksternal tidak dipakai.",
                "Berita yang lolos validasi diparafrase dan dihubungkan ke tesis dengan caveat.",
                "SOTP/LoM belum dapat direkonsiliasi dari input yang tersedia.",
            ],
            "paragraf": [
                {"judul": "Status riset", "isi": release_text},
                {"judul": "Basis model", "isi": profile_text},
            ],
            "data_pasar": {"harga": price, "tp": None,
                            "saham": intake["shares"], "market_cap": market_cap,
                            "adtv": "-", "free_float": "-"},
            "key_financials": hist_rows,
        },
        "bagian": sections,
        "tabel_asumsi": [],
        "log_gate": {"G1": g1.get("G1", {}), "G2": fc.get("g2", {}),
                     "G3": {}, "release": release_result},
        "method": "SOTP/LoM (belum lengkap)",
        "method_select": "auto", "holders": [],
        "catatan_metodologi": [
            "DRAFT NON-DISTRIBUTABLE: target harga dan rating ditahan.",
            "SOTP/LoM memerlukan NAV per aset, kepemilikan, net debt, minority interest, "
            "overhead korporat dan saham terdilusi dengan provenance.",
            "Validasi latest interim memakai metadata yang tersedia di cache; data di luar cache tidak dipakai.",
            "News context hanya memakai berita ticker-spesifik dari cache dan tidak langsung menjadi angka forecast.",
            "Forecast tambang harus dihitung dari driver fisik; proyeksi CAGR hanya screening.",
            "RNAV annuitas indikatif dari overlay cache bukan nilai wajar karena bukan SOTP asset-level.",
        ],
        "exhibits": exhibits,
    }


def build(intake, fc, va, g1, method="auto"):
    method = (method or "auto").lower()
    if method not in ("auto", "dcf", "ddm", "rnav"):
        raise ValueError(f"method tak dikenal: {method} (auto|dcf|ddm|rnav)")
    if method == "ddm" and intake.get("payout") is None:
        raise ValueError("method ddm ditolak: tanpa payout di cache")
    if method == "rnav" and not intake.get("mineops"):
        raise ValueError("method rnav ditolak: tanpa overlay operasional di cache")
    if (va.get("release") or {}).get("status") != "distributable":
        return _build_draft(intake, fc, va, g1)
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

    mo = intake.get("mineops")
    p_mine = None
    if mo:
        cu, au = mo["comms"].get("Copper") or {}, mo["comms"].get("Gold") or {}
        cup, aup = mo.get("cu_price") or {}, mo.get("au_price") or {}
        mrows = [
            ["Produksi Cu", f"{fmt._id(cu.get('prod') or 0)} kton ({mo['year']})"],
            ["Produksi Au", f"{fmt._id(au.get('prod') or 0)} koz ({mo['year']})"],
            ["Kadar Cu / Au",
             f"{fmt._id(cu.get('cu_grade') or 0, 2)}% / {fmt._id(au.get('au_grade') or 0, 2)} g/t"],
            ["Cadangan terkandung",
             f"Cu {fmt._id(cu.get('cu_cont_mt') or 0)} kton; "
             f"Au {fmt._id(au.get('au_cont_koz') or 0)} koz"],
            ["Umur cadangan Cu",
             f"~{mo['reserve_life_cu_yr']:.0f} tahun ({mo['reserve_life_basis']})"]
            if mo.get("reserve_life_cu_yr") else ["Umur cadangan Cu", "-"],
            ["Harga Cu terakhir",
             f"USD {fmt._id(cup.get('last') or 0)}/ton ({cup.get('date') or '-'})"],
            ["Harga Au terakhir",
             f"USD {fmt._id(aup.get('last') or 0)}/ton ({aup.get('date') or '-'})"],
            ["Blok operasi", ", ".join(cu.get("blocks") or []) or "-"],
        ]
        E("Operasional tambang", "tabel",
          {"cols": ["Metrik", f"{mo['year']} / terakhir"],
           "rows": mrows},
          note="Source: Sectors mining data, Sektoral Estimates "
               "(umur cadangan)")
        cup_s = (f"USD {fmt._id(cup['last'])}/ton per {cup['date']} "
                 f"(rata-rata 12 bln USD {fmt._id(cup['avg12'])})" if cup else "-")
        aup_s = (f"USD {fmt._id(aup['last'])}/ton per {aup['date']} "
                 f"(rata-rata 12 bln USD {fmt._id(aup['avg12'])})" if aup else "-")
        p_mine = (f"Operasional {mo['year']}: produksi tembaga "
                  f"{fmt._id(cu.get('prod') or 0)} kton dan emas "
                  f"{fmt._id(au.get('prod') or 0)} koz dari "
                  f"{', '.join(cu.get('blocks') or ['-'])} pada kadar "
                  f"{fmt._id(cu.get('cu_grade') or 0, 2)}% Cu dan "
                  f"{fmt._id(au.get('au_grade') or 0, 2)} g/t Au. Cadangan "
                  f"terkandung {fmt._id(cu.get('cu_cont_mt') or 0)} kton Cu dan "
                  f"{fmt._id(au.get('au_cont_koz') or 0)} koz Au memberi umur "
                  f"cadangan sekitar {mo['reserve_life_cu_yr']:.0f} tahun pada "
                  f"laju produksi saat ini. Harga acuan: tembaga {cup_s}, emas "
                  f"{aup_s}. Data volume penjualan dan jadwal belanja modal "
                  f"smelter tidak ada di cache sehingga tidak dimodelkan.")

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
                                        for gg in (0.025, 0.035, 0.045)])
    E("Sensitivitas TP (WACC x g)", "tabel",
      {"cols": ["TP (Rp)", "g 2,5%", "g 3,5%", "g 4,5%"], "rows": sens_tp_rows})
    for _vex in [valtables.fcff_exhibit(intake, fc, va)]:
        E(_vex["judul"], _vex["tipe"], _vex["data"], _vex.get("catatan_sumber") or
          "Source: Company, Sektoral Estimates")
    _wacc = valtables.wacc_exhibit(intake, fc, va)
    E(_wacc["judul"], _wacc["tipe"], _wacc["data"], _wacc.get("catatan_sumber") or
      "Source: Company, Sektoral Estimates")
    _sens5 = valtables.sens_matrix_5x3(intake, fc, va)
    E(_sens5["judul"], _sens5["tipe"], _sens5["data"], _sens5.get("catatan_sumber") or
      "Source: Company, Sektoral Estimates")
    _is_bank = "bank" in ((intake.get("sub_sector") or "") + " " +
                          (intake.get("industry") or "")).lower()
    if _is_bank and intake.get("payout") is not None:
        for _vex in [valtables.ddm_exhibits(
                intake["payout"], (intake.get("roe_fwd") or 0.12),
                (intake["annuals"][-1].get("equity") or 0) / intake["shares"],
                va["wacc_inputs"]["re"])]:
            E(_vex["judul"], _vex["tipe"], _vex["data"], _vex.get("catatan_sumber") or
              "Source: Company, Sektoral Estimates")
    p_ddm = None
    if _is_bank:
        _re, _g = va["wacc_inputs"]["re"], va["wacc_inputs"]["g"]
        _nets = [r["net"] for r in F]
        _bvps = (A[-1].get("equity") or 0) / intake["shares"]
        _roae = _nets[0] / F[0]["equity"] if F[0]["equity"] else 0.12
        _roe_h = [(a.get("earnings") or 0) / a["equity"] for a in A[-3:]
                  if a.get("equity")]
        _vb = ddm.value_bank(_nets, None, intake.get("dps_hist") or [],
                             intake["shares"], _re, _g, _roae, _bvps)
        wi = va["wacc_inputs"]
        E("Komponen Cost of Equity", "tabel",
          {"cols": ["Komponen", "Nilai"],
           "rows": [["Jalur CAPM:", ""],
                     ["Risk-free rate (INDOGB 10Y)", fmt.pct(wi["rf"])],
                     ["Beta (Bloomberg)", fmt.mult(wi["beta"])],
                     ["Equity Risk Premium (Damodaran)", fmt.pct(wi["erp"])],
                     ["(=) Cost of Equity dipakai", fmt.pct(wi["re"])],
                     ["Jalur band (pola BBTN):", ""],
                     ["CoE mean 5 tahun", "n.a. (tanpa histori CoE di cache)"],
                     ["CoE SD 5 tahun", "n.a. (tanpa histori CoE di cache)"],
                     ["Offset dari mean", "n.a. — dipakai hasil CAPM"]]},
          note="Source: Company, Sektoral Estimates; Rf = INDOGB 10Y, "
               "ERP = Damodaran, Beta = Bloomberg")
        _cg_rows = []
        for _d in (-0.01, -0.005, 0.0, 0.005, 0.01):
            _cg_rows.append(
                [f"CoE {fmt.pct(_re + _d)}" + (" (base)" if _d == 0 else "")] +
                [fmt.rp(round(ddm.value_bank(
                    _nets, None, intake.get("dps_hist") or [],
                    intake["shares"], _re + _d, _gg, _roae,
                    _bvps)["tp_gordon"] / 10) * 10) +
                 (" *" if _d == 0 and _gg == _g else "")
                 for _gg in (_g - 0.01, _g, _g + 0.01)])
        E("Sensitivitas DDM (CoE x g)", "tabel",
          {"cols": ["CoE / g"] + [f"g {fmt.pct(_gg)}" for _gg in (_g - 0.01, _g, _g + 0.01)],
           "rows": _cg_rows},
          note="Source: Sektoral Estimates; sel = Nilai Wajar/saham Gordon; "
               "base (*) = CoE dan g terpakai")
        _cr_rows = []
        for _d in (-0.01, -0.005, 0.0, 0.005, 0.01):
            _cr_rows.append(
                [f"CoE {fmt.pct(_re + _d)}" + (" (base)" if _d == 0 else "")] +
                [fmt.rp(round(((_rr - _g) / (_re + _d - _g)) * _bvps / 10) * 10)
                 for _rr in (_roae - 0.04, _roae, _roae + 0.04)])
        E("Sensitivitas Inverse CoE (CoE x ROE)", "tabel",
          {"cols": ["CoE / ROE"] + [f"ROE {fmt.pct(_rr)}" for _rr in
                                    (_roae - 0.04, _roae, _roae + 0.04)],
           "rows": _cr_rows},
          note="Source: Sektoral Estimates; sel = P/BV wajar x BVPS; "
               "Fair P/BV = (ROE-g)/(CoE-g)")
        _roe_tr = ("naik" if _roe_h and _roae >= _roe_h[0] else "melandai")
        p_ddm = (f"Driver utama valuasi bank ini adalah lintasan ROE, bukan arus kas: "
                 f"ROAE historis {fmt.pct(_roe_h[0])} {_roe_tr} ke {fmt.pct(_roae)} "
                 f"forward bila laba {F[0]['label']} tercapai. DDM Gordon memberi "
                 f"Rp{fmt.rp(round(_vb['tp_gordon'] / 10) * 10)}/saham pada payout "
                 f"{fmt.pct(_vb['payout_used'])} ({intake.get('payout_basis')}); silang cek "
                 f"Inverse CoE Rp{fmt.rp(round(_vb['tp_inverse'] / 10) * 10)}/saham "
                 f"(P/BV wajar {fmt.mult(_vb['fair_pbv'], 2)}x). Payout {fmt.pct(_vb['payout_used'])} "
                 f"dinilai sustain sepanjang kebutuhan modal pertumbuhan kredit/aset "
                 f"tidak menuntut retensi di atas level historis; "
                 f"{intake.get('dps_basis')}.")
    E("Peer", "tabel",
      {"cols": ["Peer", "PER TTM", "PBV"],
       "rows": [[c["symbol"], fmt.mult(c["pe"] or 0), fmt.mult(c["pb"] or 0)]
                for c in intake["peers"][:8]] or [["Tanpa peer di cache", "-", "-"]]})
    br = fc.get("bridge")
    if br and br.get("gross_usd_bn"):
        E("Jembatan pendapatan tambang", "tabel",
          {"cols": ["Uraian", "Nilai"],
           "rows": [["Nilai logam bruto (produksi x harga 12 bln, USD miliar)",
                      f"{br['gross_usd_bn']:.2f}"],
                     [f"Pendapatan {F[0]['label']} (USD miliar, {rnav.FX_BASIS})",
                      f"{br['fy1_usd_bn']:.2f}"],
                     ["Payability tersirat (tercatat/bruto)", fmt.pct(br["payability"])],
                     ["Selisih vs bruto (ambang penjelasan 25%)", fmt.pct(br["gap_pct"])]]},
          note="Source: Sectors mining data, Sektoral Estimates; selisih = "
               "payability/TC-RC/royalti/mix, bukan error model")
    lom = va.get("lom")
    p_lom = None
    if lom:
        _rn = _rnav_exhibit(lom, fc["base"]["cash"], fc["base"]["debt"],
                            intake["shares"])
        E(_rn["judul"], _rn["tipe"], _rn["data"],
          (_rn.get("catatan_sumber") or "Source: Company, Sektoral Estimates") +
          "; diskon 0% (tanpa basis pembanding discount)")
        p_lom = (f"Silang cek umur tambang: NAV LoM Rp{fmt.rp(round(lom['rnav_ps']))}/saham "
                 f"(anuitas produksi flat sampai cadangan habis, tanpa terminal, diskon "
                 f"{fmt.pct(va['wacc'])}; {lom['margin_basis']}) vs TP DCF Rp{tp_s}. "
                 f"NAV LoM di atas TP karena horizon {(mo.get('reserve_life_cu_yr') or 0):.0f} tahun "
                 f"menangkap nilai cadangan yang dipotong terminal Gordon; TP dipakai "
                 f"dengan kesadaran keterbatasan itu. "
                 f"Diskon RNAV 0% adalah pure judgment assumption tanpa basis "
                 f"pembanding discount historis/sektor di cache.")
        _tn, _sh = lom["total_nav_rpbn"], intake["shares"]
        _cb, _db = fc["base"]["cash"] / 1e9, fc["base"]["debt"] / 1e9
        E("Discount Rate per Aset", "tabel",
          {"cols": ["Aset", "Tahap", "Discount rate", "Umur (thn)"],
           "rows": [[s["nama"].split(" (")[0], "produksi", fmt.pct(va["wacc"]),
                     f"{(s['life'] or 0):.0f}"] for s in lom["streams"]]},
          note="Source: Sektoral Estimates; satu tarif (WACC model) untuk "
               "semua aset tahap produksi — tidak ada diferensiasi "
               "matang-vs-development di cache")
        _dp_rows = []
        for _dd in (0.0, 0.10, 0.20, 0.30):
            _dp_rows.append(
                [f"Diskon {fmt.pct(_dd, 0)}"] +
                [fmt.rp(round((_tn * _pm + _cb - _db) * 1e9 / _sh * (1 - _dd) / 10) * 10)
                 for _pm in (0.8, 1.0, 1.2)])
        E("Sensitivitas RNAV (diskon x harga)", "tabel",
          {"cols": ["Diskon / harga"] + [f"Harga {p}" for p in
                                         ("-20%", "base", "+20%")],
           "rows": _dp_rows},
          note="Source: Sektoral Estimates; sel = TP/saham; NAV linear "
               "terhadap harga (anuitas flat)")
    E("Laba rugi", "tabel", _is(F, "laba"))
    E("Neraca", "tabel", _is(F, "neraca"))
    E("Arus kas", "tabel", _is(F, "kas"))

    # verify exhibit numbering sequential
    assert [e["n"] for e in exh] == list(range(1, len(exh) + 1))

    by_title = {e["judul"].split(". ", 1)[-1]: e for e in exh}
    get = by_title.get
    drv = (f"pertumbuhan pendapatan ke Rp{fmt.miliar(f3['revenue'])} miliar dan margin "
           f"EBITDA {fmt.pct(f3['margin'])} pada {f3['label']}")
    lim = ("proksi Gordon + exit multiple tanpa DCF umur tambang" if mo else
           "asumsi terminal growth dan exit multiple pada model generik")
    xtra = methodnote.extreme_tp_lines(va["upside"], va["tp"], intake["price"], drv, lim)
    bagian = [
        {"halaman": 2, "judul": "Industri dan makro: permintaan ke depan",
         "paragraf": [p_ind1, p_ind2, p_ind3] + ([p_mine] if p_mine else []),
         "exhibit": [e for e in
                     [get("Kinerja historis"),
                      get("Neraca dan arus kas historis"),
                      get("Operasional tambang")] if e is not None]},
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
                      f"exit Rp{fmt.rp(va['ps_exit'])} (WACC {fmt.pct(va['wacc'])})."] + xtra +
                      ([p_lom] if p_lom else []) + ([p_ddm] if p_ddm else []),
         "exhibit": [e for e in
                     [get("Ringkasan DCF"), get("Proyeksi FCFF"),
                      get("Sensitivitas TP (WACC x g)"),
                      get("Prakiraan FCFF, Nilai Terminal, dan Jembatan Nilai Wajar"),
                      get("Komponen WACC"),
                      get("Sensitivitas Nilai Wajar per Saham (Rp)"),
                      get("Prakiraan Dividen, Nilai Terminal, dan Inverse CoE"),
                      get("Komponen Cost of Equity"),
                      get("Sensitivitas DDM (CoE x g)"),
                      get("Sensitivitas Inverse CoE (CoE x ROE)"),
                      get("Jembatan pendapatan tambang"),
                      get("Rincian Aset dan Jembatan RNAV"),
                      get("Discount Rate per Aset"),
                      get("Sensitivitas RNAV (diskon x harga)"),
                      get("Peer")] if e is not None]},
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
    mnotes = methodnote.methodology_notes(intake, fc, va, intake.get("mineops"))
    method = (method or "auto").lower()
    if method not in ("auto", "dcf", "ddm", "rnav"):
        raise ValueError(f"method tak dikenal: {method} (auto|dcf|ddm|rnav)")
    if method == "ddm" and intake.get("payout") is None:
        raise ValueError("method ddm ditolak: tanpa payout di cache")
    if method == "rnav" and not intake.get("mineops"):
        raise ValueError("method rnav ditolak: tanpa overlay operasional di cache")
    method_label = {"auto": "DCF (FCFF, Rp)", "dcf": "DCF (FCFF, Rp)",
                    "ddm": "DDM (dividen, Rp)", "rnav": "RNAV LoM (Rp)"}[method]
    if method != "auto":
        mnotes = [f"metode valuasi dipilih analis: {method_label}."] + mnotes
    metodo = (["Angka bersumber dari snapshot cache Sectors (salinan lokal yang bisa "
               "kedaluwarsa; pembacaan tidak memakai kuota API). Tanpa angka karangan "
               "di luar asumsi berlabel pada tabel Asumsi."]
              + ([f"skala valuasi: {g32[1]} (ambang 20-300% dari market cap, "
                  "dicatat sebagai keterbatasan)"]
                 if isinstance(g32, tuple) and "gagal" in g32[0] else [])
              + [f"{k}: {v[1]} (dicatat sebagai keterbatasan)"
                 for k, v in va["g3"].items()
                 if isinstance(v, tuple) and "gagal" in v[0] and k != "G3.2_skala"]
              + mnotes[:2]
              + [methodnote.capex_impact_line(False, "volume penjualan dan jadwal smelter")]
              )[:6]
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
        "method": "DCF (FCFF, Rp)" if method == "auto" else method_label,
        "method_select": method,
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
    rows = []
    for nw in intake["news"] or []:
        title = scrub.clean_title(str(nw.get("title") or ""), 90)
        if not title:
            continue
        txt = f"{title} {nw.get('body') or ''}".lower()
        if any(k in txt for k in ["revenue", "growth", "expansion", "project"]):
            why = "terkait ekspansi dan pertumbuhan pendapatan"
        elif "dividend" in txt:
            why = "terkait kebijakan dividen"
        elif "contract" in txt:
            why = "terkait kontrak baru"
        elif any(k in txt for k in ["guidance", "target", "forecast"]):
            why = "terkait panduan kinerja"
        else:
            why = "konteks sentimen sektor"
        ts = str(nw.get("timestamp") or "")[:10] or "-"
        rows.append([title, ts, why, "Netral"])
        if len(rows) >= 5:
            break
    for c in (intake["corp_actions"] or [])[:2]:
        if not isinstance(c, dict):
            continue
        act = scrub.clean_title(str(c.get("action") or c.get("type") or ""), 90)
        if not act:
            continue
        ts = str(c.get("date") or "")[:10] or "-"
        rows.append([act, ts, "tercatat di keterbukaan emiten", "Netral"])
    rows = scrub.scrub_table_rows(rows)
    return rows or [scrub.catalyst_fallback()]


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
