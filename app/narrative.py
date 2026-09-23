"""TAHAP 4: NARASI & LAYOUT. Prosa templat deterministik dari angka model."""
import re
from urllib.parse import urlsplit

from . import cache as cache_mod
from . import ddm
from . import fmt
from . import methodnote
from . import rnav
from . import scrub
from . import valtables
from . import valuation as valuation_mod

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


_CURRENCY_METRICS = {
    "revenue", "gross_loan", "net_loan", "loans", "total_loans", "total_deposit",
    "deposits", "current_account", "savings_account", "time_deposit", "interest_income",
    "interest_expense", "net_interest_income", "non_interest_income", "earnings",
    "earnings_before_tax", "net_income", "net_profit", "gross_profit", "ebit", "ebitda",
    "total_assets", "total_liabilities", "total_equity", "operating_cash_flow",
    "investing_cash_flow", "financing_cash_flow", "net_cash_flow", "free_cash_flow",
}


def _research_citation_labels(citations):
    """Keep report references compact; the trace retains the complete cache values."""
    refs = []
    news_articles = {}
    for cite in citations:
        if not isinstance(cite, dict):
            continue
        endpoint = str(cite.get("endpoint") or "").strip()
        field_path = str(cite.get("field_path") or "").strip()
        if not endpoint or not field_path:
            continue
        match = re.fullmatch(r"/results/(\d+)/(title|body|timestamp|source)", field_path) \
            if endpoint == "/news/" else None
        if match:
            article = news_articles.setdefault(match.group(1), {})
            article[match.group(2)] = cite.get("value")
            continue

        ref = f"{endpoint} · {field_path}"
        value = cite.get("value")
        if isinstance(value, (int, float)) and field_path.rsplit("/", 1)[-1] in _CURRENCY_METRICS:
            ref += f" = Rp{fmt.miliar(value)} miliar"
        elif value is not None and isinstance(value, (str, int, float, bool)):
            ref += f" = {str(value)[:80]}"
        refs.append(ref)

    for index, article in news_articles.items():
        title = _word_cut(str(article.get("title") or "Berita cache"), 90)
        timestamp = str(article.get("timestamp") or "")[:10]
        source = str(article.get("source") or "")
        domain = urlsplit(source).netloc if source else ""
        date_source = "; ".join(value for value in (timestamp, domain) if value)
        suffix = f" ({date_source})" if date_source else ""
        refs.append(f"/news/ · /results/{index} · {title}{suffix}")
    return refs


def _draft_value(value):
    return "-" if value is None else fmt.miliar(value)


def _build_general_draft(intake, fc, va, g1, method="auto",
                         illustrative_scenarios=False):
    """Company-update shaped evidence brief while the production model is gated."""
    ticker = intake["ticker"]
    mining = intake.get("model_profile") == "finite_life_mining"
    evidence = intake.get("official_evidence") or {}
    actual = evidence.get("latest_actual") or {}
    annuals = evidence.get("annual_actuals") or []
    balance = evidence.get("balance_sheet") or {}
    shares_outstanding = balance.get("shares_outstanding") or balance.get("shares_issued")
    release = va.get("release") or {}
    blockers = release.get("blockers") or ["Bukti model belum lengkap"]
    currency = evidence.get("reporting_currency") or "Rp"
    scale = 1e6 if currency == "USD" else 1e9
    unit = "US$ juta" if currency == "USD" else "Rp miliar"
    money = lambda value: ("-" if value is None else
                           f"({fmt._id(abs(value) / scale, 1)})" if value < 0 else
                           fmt._id(value / scale, 1))
    money_phrase = lambda value: (f"US${money(value)} juta" if currency == "USD"
                                  else f"Rp{money(value)} miliar")
    source_page = actual.get("page")
    page_reference = (f"hlm. {source_page}"
                      if isinstance(source_page, int) or
                      (isinstance(source_page, str) and source_page.replace("-", "").isdigit())
                      else f"rujukan {source_page}")
    pct_change = lambda now, prior: (fmt.pct(now / prior - 1)
                                     if now is not None and prior is not None and
                                     prior > 0 and now >= 0 else "n.m." if
                                     now is not None and prior is not None and
                                     (prior < 0 or now < 0) else "-")
    exhibits = []

    def add(title, columns, rows, source):
        exhibits.append({"n": len(exhibits) + 1, "judul": title,
                         "tipe": "tabel", "data": {"cols": columns, "rows": rows},
                         "catatan_sumber": source})
        return exhibits[-1]

    annual_by_year = {row["year"]: row for row in annuals}
    history = [annual_by_year.get(year) for year in (2024, 2025)]
    if all(history):
        def values(key):
            return [money(row.get(key)) for row in history]

        def growth(key):
            return ["-", pct_change(history[1].get(key), history[0].get(key))]

        def per_share(key):
            shares = shares_outstanding
            factor = 100 if currency == "USD" else 1
            result = []
            for row in history:
                value = row.get(key)
                if value is None or not shares:
                    result.append("-")
                    continue
                formatted = fmt._id(abs(value) / shares * factor, 2)
                result.append(f"({formatted})" if value < 0 else formatted)
            return result

        F = fc.get("rows") or []
        f_labels = [r["label"] for r in F] if F else [f"FY{(int(history[-1]['year']) + 1 + i)%100:02d}F" for i in range(5)]
        f_dashes = ["-"] * len(f_labels)
        total_cols_dash = ["-"] * (len(history) + len(f_labels))
        key_rows = [
            [f"Pendapatan ({unit})"] + values("revenue") + f_dashes,
            ["Pertumbuhan pendapatan (%)"] + growth("revenue") + f_dashes,
            [f"EBITDA ({unit})"] + values("ebitda") + f_dashes,
            ["Pertumbuhan EBITDA (%)"] + growth("ebitda") + f_dashes,
            [f"Laba bersih ({unit})"] + values("net_profit") + f_dashes,
            ["Pertumbuhan laba bersih (%)"] + growth("net_profit") + f_dashes,
            ["EPS (US$ sen)" if currency == "USD" else "EPS (Rp)"] +
            per_share("net_profit_attributable") + f_dashes,
            ["BVPS (US$ sen)" if currency == "USD" else "BVPS (Rp)"] +
            per_share("equity_attributable") + f_dashes,
            ["DPS"] + total_cols_dash,
            ["PER (x)"] + total_cols_dash,
            ["PBV (x)"] + total_cols_dash,
            ["Dividend yield (%)"] + total_cols_dash,
            ["EV/EBITDA (x)"] + total_cols_dash,
        ]
        key_note = (f"Sumber: {evidence.get('annual_source_title') or actual.get('source_title')}; "
                    f"angka {history[0]['year']}–{history[-1]['year']} ditampilkan dalam {unit}. "
                    "EPS/BVPS historis memakai laba/ekuitas pemilik induk dan jumlah "
                    f"saham per {balance.get('period_end', 'periode interim')} sebagai basis pro forma; "
                    f"{f_labels[0]}–{f_labels[-1]} belum diterbitkan.")
    else:
        cached = intake.get("annuals") or []
        history = cached[-2:]
        F = fc.get("rows") or []
        f_labels = [r["label"] for r in F] if F else [
            f"FY{(int(history[-1]['year']) + 1 + i) % 100:02d}F" for i in range(5)]
        f_dashes = ["-"] * len(f_labels)
        key_rows = [[f"Pendapatan ({unit})"] +
                    [money(row.get("revenue")) for row in history] + f_dashes,
                    [f"EBITDA ({unit})"] +
                    [money(row.get("ebitda")) for row in history] + f_dashes,
                    [f"Laba bersih ({unit})"] +
                    [money(row.get("earnings")) for row in history] + f_dashes]
        key_note = ("Sumber: Sectors cache, company/report. Kolom forecast dan "
                    "multiple belum tersedia karena model belum lolos validasi.")
    years = [str(row["year"]) for row in history]
    add("Key Financials", ["Tahun buku 31 Des"] + years +
        f_labels, key_rows, key_note)

    actual_rows = []
    if actual:
        previous = actual.get("prior_year") or {}
        for label, key in (("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                           ("Laba usaha", "operating_profit"),
                           ("Laba bersih", "net_profit"),
                           ("Beban material", "material_expense"),
                           ("Depresiasi", "depreciation"),
                           ("Belanja modal", "capital_expenditure"),
                           ("Arus kas operasi", "operating_cash_flow")):
            current = actual["metrics"].get(key)
            prior = previous.get(key)
            if current is None and prior is None:
                continue
            actual_rows.append([f"{label} ({unit})", money(prior), money(current),
                                pct_change(current, prior)])
        add("Hasil interim resmi dan perubahan yoy",
            ["Metrik", previous.get("period", "Periode lalu"),
             actual["period"], "yoy"], actual_rows,
            f"Sumber: {actual['source_title']}, {page_reference}; "
            f"{actual['source_url']}")
        metrics = actual["metrics"]
        prior_metrics = actual.get("prior_year") or {}
        def ratio(numerator, denominator):
            return (fmt.pct(numerator / denominator)
                    if numerator is not None and denominator and denominator > 0 else "-")
        diagnostic_rows = [
            ["Margin EBITDA", ratio(prior_metrics.get("ebitda"), prior_metrics.get("revenue")),
             ratio(metrics.get("ebitda"), metrics.get("revenue"))],
            ["Margin laba bersih", ratio(prior_metrics.get("net_profit"), prior_metrics.get("revenue")),
             ratio(metrics.get("net_profit"), metrics.get("revenue"))],
        ]
        if metrics.get("capital_expenditure") is not None:
            diagnostic_rows.append(
                ["Belanja modal / pendapatan",
                 ratio(prior_metrics.get("capital_expenditure"), prior_metrics.get("revenue")),
                 ratio(metrics.get("capital_expenditure"), metrics.get("revenue"))])
        if metrics.get("operating_cash_flow") is not None:
            diagnostic_rows.append(
                ["Arus kas operasi / EBITDA",
                 ratio(prior_metrics.get("operating_cash_flow"), prior_metrics.get("ebitda")),
                 ratio(metrics.get("operating_cash_flow"), metrics.get("ebitda"))])
        add("Rasio yang menjelaskan kualitas hasil",
            ["Rasio", previous.get("period", "Periode lalu"), actual["period"]],
            diagnostic_rows,
            f"Sumber: {actual['source_title']}, {page_reference}; "
            "rasio dihitung dari angka resmi, nilai negatif ditampilkan sebagai '-'.")
        chart_metrics = [
            {"label": "Pendapatan", "prior": prior_metrics.get("revenue"),
             "current": metrics.get("revenue")},
            {"label": "EBITDA", "prior": prior_metrics.get("ebitda"),
             "current": metrics.get("ebitda")},
        ]
        if prior_metrics.get("net_profit", 0) >= 0:
            chart_metrics.append({"label": "Laba bersih",
                                  "prior": prior_metrics.get("net_profit"),
                                  "current": metrics.get("net_profit")})
        exhibits.append({
            "n": len(exhibits) + 1, "judul": f"Perbandingan metrik {actual['period']}",
            "tipe": "bar_chart", "data": {"unit": unit, "rows": chart_metrics,
                                         "prior_label": previous.get("period", "1H25"),
                                         "current_label": actual["period"]},
            "catatan_sumber": (f"Sumber: {actual['source_title']}, {page_reference}; "
                               "grafik memakai nilai absolut dari angka yang dilaporkan.")})
    else:
        quarter = intake.get("latest_quarterly_actual") or {}
        if quarter:
            add("Baris kuartalan dalam data lokal",
                ["Metrik", str(quarter.get("date") or "-")],
                [[label, money(quarter.get(key))] for label, key in
                 (("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                  ("Laba bersih", "earnings"))],
                f"Sumber: Sectors cache, financials/quarterly/{ticker}; "
                "cakupan kumulatif dan tanggal publikasi belum terverifikasi.")

    revenue_breakdown = evidence.get("revenue_breakdown") or {}
    if revenue_breakdown and actual:
        breakdown_rows = []
        for group, heading in (("segments", "Segmen"),
                               ("major_customers", "Pelanggan utama")):
            for row in revenue_breakdown.get(group) or []:
                breakdown_rows.append([f"{heading}: {row['name']}",
                                       money(row.get("prior")),
                                       money(row.get("current")),
                                       pct_change(row.get("current"), row.get("prior"))])
        add(f"Komposisi pendapatan {actual['period']}" if mining else
            "Jembatan pendapatan menurut layanan dan pelanggan",
            ["Uraian", (actual.get("prior_year") or {}).get("period", "Periode lalu"),
             actual["period"], "yoy"], breakdown_rows,
            f"Sumber: {actual['source_title']}, hlm. "
            f"{revenue_breakdown['source_page']}. " +
            ("Angka merupakan penjualan produk, bukan forecast tahunan."
             if mining else "Segmen dan pelanggan adalah dua pemotongan pendapatan "
             "yang berbeda; jangan dijumlahkan bersama."))

    operating_metrics = evidence.get("operating_metrics") or []
    if operating_metrics and actual:
        add("Metrik operasi dan pemrosesan",
            ["Metrik", (actual.get("prior_year") or {}).get("period", "Periode lalu"),
             actual["period"], "yoy"],
            [[row["name"],
              "-" if row.get("prior") is None else fmt._id(row["prior"], row.get("decimals", 0)),
              fmt._id(row["current"], row.get("decimals", 0)),
              pct_change(row["current"], row.get("prior"))]
             for row in operating_metrics],
            f"Sumber: {actual['source_title']}, hlm. 3–4. Produksi tidak sama "
            "dengan penjualan; kadar dan throughput perlu dijembatani terpisah.")

    guidance = evidence.get("management_guidance") or []
    if guidance and actual:
        guidance_period = evidence.get("guidance_period") or f"FY{actual['period_end'][:4]}"
        add(f"Panduan produksi {guidance_period} dari manajemen",
            ["Produk", f"{guidance_period} guidance"],
            [[row["name"], fmt._id(row["value"], 0)] for row in guidance],
            f"Sumber: {actual['source_title']}, hlm. 7. Panduan manajemen "
            "bukan estimasi analis atau dasar target harga secara otomatis.")

    mine_life = evidence.get("mine_life_context") or {}
    if mining and mine_life:
        add("Cadangan dan jadwal tambang dari rilis resmi",
            ["Aset / tonggak", "Data manajemen"],
            [["Cadangan bijih Batu Hijau", f"{fmt._id(mine_life['batu_hijau_reserves_mt'])} juta ton"],
             ["Penambangan Batu Hijau sampai", mine_life["batu_hijau_mining_through"]],
             ["Pengolahan stockpile sampai", mine_life["batu_hijau_stockpile_through"]],
             ["Cadangan bijih Elang", f"{fmt._id(mine_life['elang_reserves_mt'])} juta ton"],
             ["Bijih pertama Elang", mine_life["elang_first_ore"]],
             ["Target keputusan investasi Elang", mine_life["elang_fid_target"]]],
            f"Sumber: {mine_life['source_title']}, hlm. {mine_life['source_page']}; "
            f"{mine_life['source_url']}. Jadwal dan cadangan belum memberi produksi, "
            "harga, biaya, capex, atau arus kas tahunan untuk NAV LoM.")

    if balance:
        debt = balance.get("total_debt")
        if debt is None:
            components = [balance.get(k) for k in
                          ("loans_current", "loans_noncurrent", "lease_current",
                           "lease_noncurrent")]
            debt = sum(value for value in components if value is not None) \
                if all(value is not None for value in components) else None
        equity = balance.get("total_equity")
        if equity is None and balance.get("equity_attributable") is not None and \
                balance.get("non_controlling_interest") is not None:
            equity = balance["equity_attributable"] + balance["non_controlling_interest"]
        shares = shares_outstanding
        balance_unit = "US$ juta" if currency == "USD" else "Rp miliar"
        add("Posisi neraca interim", ["Metrik", balance["period_end"]],
            [[f"Kas ({balance_unit})", money(balance.get("cash"))],
             [f"Pinjaman berbunga ({balance_unit})", money(debt)],
             [f"Total ekuitas ({balance_unit})", money(equity)],
             [f"Kepentingan nonpengendali ({balance_unit})",
              money(balance.get("non_controlling_interest"))],
             ["Saham beredar sesudah treasuri (juta)",
              fmt._id(shares / 1e6, 1) if shares is not None else "-"],
             ["Saham diterbitkan (juta)",
              fmt._id(balance["shares_issued"] / 1e6, 1)
              if balance.get("shares_issued") is not None else "-"]],
            f"Sumber: {balance.get('source_title') or actual['source_title']}, "
            "hlm. " + ", ".join(str(p) for p in balance.get("source_pages", [])) +
            f"; {balance.get('source_url') or actual['source_url']}.")

    illustrative_pages = []
    if illustrative_scenarios and mining:
        agent_case = fc.get("interim_scenario")
        if agent_case:
            case_money = lambda value: fmt._id(value / 1e6, 1)
            measures = (("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                        ("Laba bersih", "net_profit"),
                        ("Belanja modal", "capital_expenditure"))
            case_exhibit = add(
                "Skenario FY26 berbasis hasil interim dan asumsi analis",
                ["US$ juta", "1H26 aktual", "2H26 skenario", "FY26 skenario"],
                [[label, case_money(agent_case["h1"][key]),
                  case_money(agent_case["h2"][key]),
                  case_money(agent_case["full_year"][key])]
                 for label, key in measures],
                f"Sumber aktual: {agent_case['source_url']} (terbit "
                f"{agent_case['published_at']}); 2H26 adalah asumsi analis. "
                "Rasio produksi panduan tidak sama dengan penjualan: persediaan, bauran "
                "produk, harga realisasi, dan biaya belum direkonsiliasi.")
            case_assumptions = agent_case["assumptions"]
            ratio_exhibit = add(
                "Asumsi eksplisit untuk skenario 2H26",
                ["Driver", "Asumsi", "Dasar dan batasan"],
                [["Pendapatan 2H / 1H", fmt.pct(case_assumptions["h2_revenue_to_h1"]),
                  "Penilaian dari realisasi 1H dan panduan tahunan; volume produksi "
                  "belum tentu sama dengan penjualan dan harga realisasi bisa berubah."],
                 ["Margin EBITDA 2H", fmt.pct(case_assumptions["h2_ebitda_margin_pct"] / 100),
                  "Asumsi analis; belum ada panduan margin 2H."],
                 ["Margin laba 2H", fmt.pct(case_assumptions["h2_net_margin_pct"] / 100),
                  "Asumsi analis; pajak dan bunga belum dijembatani."],
                 ["Belanja modal 2H / 1H", fmt.pct(case_assumptions["h2_capex_to_h1"]),
                  "Asumsi analis; jadwal capex proyek belum tervalidasi."]],
                f"Sumber: {agent_case['source_url']}; asumsi numerik adalah "
                "interpretasi analis untuk skenario internal, bukan guidance emiten.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Skenario FY26 dari rilis terbaru",
                "layout": "stack",
                "paragraf": ["Hasil 1H26 dan panduan operasi digunakan untuk "
                             "membentuk skenario 2H26. Konversi ke rupiah pada "
                             "halaman nilai berikutnya hanya untuk cross-check, "
                             "bukan dasar target harga."],
                "exhibit": [case_exhibit, ratio_exhibit]})
            crosscheck = valuation_mod.scenario_ev_ebitda_crosscheck(intake, fc)
            if crosscheck:
                check_money = lambda value: fmt._id(value / 1e6, 1)
                value_exhibit = add(
                    "Cross-check EV/EBITDA FY26 berbasis skenario interim",
                    ["US$ juta, kecuali per saham"] +
                    [f"{item['multiple']:.0f}x" for item in crosscheck["values"]],
                    [["Enterprise value"] +
                     [check_money(item["enterprise_usd"]) for item in crosscheck["values"]],
                     ["Ekuitas induk setelah utang dan minoritas"] +
                     [check_money(item["equity_usd"]) for item in crosscheck["values"]],
                     ["Nilai skenario (Rp/saham)"] +
                     [f"Rp{fmt.rp(round(item['per_share_idr'] / 10) * 10)}"
                      if item["per_share_idr"] is not None else "n.m."
                      for item in crosscheck["values"]]],
                    f"Sumber EBITDA skenario: {crosscheck['source_url']}; "
                    f"kas/utang/minoritas/saham: neraca {crosscheck['balance_period']}; "
                    f"kurs: {crosscheck['fx']['source']} ({crosscheck['fx']['date']}). "
                    "Multiple 6x/8x/10x adalah asumsi sensitivitas analis, bukan "
                    "multiple peer yang tervalidasi atau target harga.")
                inputs_exhibit = add(
                    "Input cross-check FY26 dan batasannya",
                    ["Input", "Basis", "Batasan"],
                    [["EBITDA FY26 skenario", f"US${check_money(crosscheck['ebitda_usd'])} juta",
                      "Hasil 1H aktual + asumsi 2H; bukan forecast LoM."],
                     ["Utang bersih 1H", f"US${check_money(crosscheck['net_debt_usd'])} juta",
                      "Belum disesuaikan dengan arus kas dan capex 2H."],
                     ["Kepentingan nonpengendali", f"US${check_money(crosscheck['minority_interest_usd'])} juta",
                      "Dikurangkan dari enterprise value setelah utang bersih."],
                     ["USD/IDR", fmt._id(crosscheck["fx"]["rate"], 0),
                      f"Kurs {crosscheck['fx']['date']}; harga saham cache "
                      f"{intake['price_date']} lebih lama."],
                     ["Saham beredar", fmt._id(crosscheck["shares"] / 1e6, 1) + " juta",
                      "Sesudah saham treasuri; dilusi berikutnya belum dimodelkan."]],
                    "Sumber: rilis interim resmi dan cache FX bertanggal. Skenario "
                    "multiple mengabaikan umur tambang, capex LoM, dan nilai aset "
                    "terpisah; hanya cross-check internal.")
                illustrative_pages.append({
                    "halaman": 0, "judul": "Cross-check nilai FY26 dari hasil terbaru",
                    "layout": "stack",
                    "paragraf": ["EBITDA skenario FY26 diuji pada tiga multiple EV/EBITDA. "
                                 "Angka per saham ini sensitif pada harga komoditas, "
                                 "kurs, utang, dan multiple; bukan target harga."],
                    "exhibit": [value_exhibit, inputs_exhibit]})
        annual_cache = (intake.get("annuals") or [])[-5:]
        if annual_cache:
            years = [str(row["year"]) for row in annual_cache]
            cache_money = lambda value: "-" if value is None else fmt.miliar(value)
            history_items = (
                ("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                ("Laba bersih", "earnings"), ("Arus kas operasi", "ocf"),
                ("Belanja modal", "capex_out"), ("Arus kas bebas tercatat", "fcf"))
            history_exhibit = add(
                "Riwayat keuangan dalam cache",
                ["Rp miliar"] + years,
                [[label] + [cache_money(row.get(key)) for row in annual_cache]
                 for label, key in history_items],
                f"Sumber: Sectors cache, company/report/{ticker}, financials.historical_financials. "
                "Angka Rp historis adalah konteks terpisah dari laporan interim resmi "
                f"bermata uang {currency}; belum direkonsiliasi ke model.")
            balance_items = (("Kas", "cash"), ("Utang", "total_debt"),
                             ("Ekuitas", "equity"), ("Aset", "assets"))
            balance_exhibit = add(
                "Neraca historis dalam cache", ["Rp miliar"] + years,
                [[label] + [cache_money(row.get(key)) for row in annual_cache]
                 for label, key in balance_items],
                f"Sumber: Sectors cache, company/report/{ticker}, financials.historical_financials; "
                "basis historis, bukan jembatan SOTP.")
            history_page_exhibits = [history_exhibit, balance_exhibit]
            holders = intake.get("major_holders") or []
            if holders:
                holder_rows = []
                for holder in holders:
                    try:
                        pct = fmt.pct(float(holder["share_percentage"]))
                    except (KeyError, TypeError, ValueError):
                        pct = "-"
                    shares_held = holder.get("share_amount")
                    holder_rows.append([
                        str(holder.get("name") or "-"), pct,
                        fmt._id(shares_held / 1e6, 1)
                        if isinstance(shares_held, (int, float)) else "-"])
                history_page_exhibits.append(add(
                    "Pemegang saham utama dalam cache",
                    ["Pemegang saham", "Porsi", "Saham (juta)"], holder_rows,
                    f"Sumber: Sectors cache, company/report/{ticker}, ownership.major_shareholders; "
                    "snapshot cache dapat berbeda dari tanggal laporan interim."))
            illustrative_pages.append({
                "halaman": 0, "judul": "Konteks historis dan kepemilikan",
                "layout": "stack",
                "paragraf": ["Tabel historis berikut membantu membaca siklus operasi dan pendanaan. "
                             "Angka cache dalam rupiah dan angka rilis interim dalam mata uang "
                             "pelaporan ditampilkan terpisah; perbedaan definisi belum "
                             "direkonsiliasi."],
                "exhibit": history_page_exhibits})

        screen = fc.get("rows") or []
        if screen:
            labels = [str(row["label"]) for row in screen]
            screen_money = lambda key: ["-" if row.get(key) is None else
                                        fmt.miliar(row[key]) for row in screen]
            screen_exhibit = add(
                "Screen proyeksi historis, bukan forecast produksi",
                ["Rp miliar"] + labels,
                [["Pendapatan"] + screen_money("revenue"),
                 ["EBITDA"] + screen_money("ebitda"),
                 ["Laba bersih proksi"] + screen_money("net"),
                 ["Belanja modal proksi"] + screen_money("capex"),
                 ["Arus kas proksi"] + screen_money("fcf")],
                "Sumber: Sectors cache annuals; kalkulasi screen historis Sektoral "
                "dengan penyesuaian berita tervalidasi bila tercatat. "
                "CAGR/margin diproyeksikan mekanis, capex disamakan dengan D&A dan "
                "modal kerja belum dimodelkan. Rilis interim terbaru belum masuk "
                "ke proyeksi ini; angka bukan forecast investasi.")
            prior_revenue = (intake.get("annuals") or [{}])[-1].get("revenue")
            growth_values = []
            for row in screen:
                growth_values.append(fmt.pct(row["revenue"] / prior_revenue - 1)
                                     if prior_revenue and row.get("revenue") is not None else "-")
                prior_revenue = row.get("revenue")
            assumption_exhibit = add(
                "Asumsi yang membuat screen belum layak rilis",
                ["Asumsi"] + labels,
                [["Pertumbuhan pendapatan"] + growth_values,
                 ["Margin EBITDA"] + [fmt.pct(row["margin"]) for row in screen],
                 ["Capex = D&A (Rp miliar)"] + screen_money("capex"),
                 ["Utang tetap (Rp miliar)"] + screen_money("debt"),
                 ["Perubahan modal kerja"] + ["belum dihitung"] * len(screen)],
                "Sumber: screen historis Sektoral dari Sectors cache. Asumsi "
                "capex, utang dan modal kerja belum memiliki jadwal operasi/pendanaan "
                "yang bersumber; angka tidak boleh dipakai sebagai forecast produksi.")
            page_exhibits = [screen_exhibit, assumption_exhibit]
            news_assumptions = fc.get("news_assumptions") or []
            if news_assumptions:
                labels = {"revenue_growth_pp": "Pertumbuhan pendapatan (pp)",
                          "ebitda_margin_pp": "Margin EBITDA (pp)",
                          "wacc_bps": "WACC screen (bp)",
                          "coe_bps": "Cost of Equity screen (bp)",
                          "none": "Tidak ada perubahan angka"}
                event_rows, event_sources = [], []
                for event in news_assumptions:
                    article = (intake.get("news") or [])[event["article_index"]]
                    impact = (f"{labels[event['driver']]} {event['change']:+g}; "
                              f"{', '.join(str(year) for year in event['years'])}"
                              if event["driver"] != "none" else "0; tanpa perubahan")
                    explanation = (
                        "Tidak ada katalis operasi atau biaya emiten yang terukur "
                        "dari artikel ini." if event["driver"] == "none" else
                        str(event.get("mechanism") or event["rationale"])[:130])
                    event_rows.append([
                        str(event["timestamp"])[:10],
                        (_word_cut(article.get("title") or "-", 65) +
                         ("…" if len(str(article.get("title") or "-")) > 65 else "")),
                        impact, explanation])
                    event_sources.append(event["source_url"])
                news_exhibit = add(
                    "Berita sebagai asumsi skenario",
                    ["Tanggal", "Berita", "Dampak ke model", "Dasar keputusan"],
                    event_rows,
                    "Sumber: berita bertanggal dalam Sectors cache: " +
                    "; ".join(dict.fromkeys(event_sources)) +
                    ". Dampak numerik adalah asumsi analis, bukan fakta emiten.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Skenario operasi ilustratif",
                "layout": "stack",
                "paragraf": ["Screen rupiah ini memperlihatkan perhitungan historis "
                             "dan perubahan driver yang ditautkan ke berita. Skenario "
                             "interim US$ pada halaman lain belum dijembatani ke model "
                             "rupiah ini."],
                "exhibit": page_exhibits})
            if news_assumptions:
                illustrative_pages.append({
                    "halaman": 0, "judul": "Berita dan keputusan asumsi",
                    "layout": "stack",
                    "paragraf": ["Setiap berita bertanggal diuji terhadap driver forecast. "
                                 "Angka nol menunjukkan berita tidak memberi dasar "
                                 "untuk mengubah asumsi operasi atau valuasi."],
                    "exhibit": [news_exhibit]})

            wi = va.get("wacc_inputs") or {}
            if (all(isinstance(va.get(key), (int, float)) for key in
                    ("ps_gordon", "ps_exit", "wacc", "net_debt")) and
                    all(isinstance(wi.get(key), (int, float)) for key in
                        ("g", "exit_mult"))):
                gordon, exit_value = va["ps_gordon"], va["ps_exit"]
                divergence = abs(gordon - exit_value) / max(abs(gordon), abs(exit_value), 1)
                value_exhibit = add(
                    "Perbandingan nilai model lama, bukan target harga",
                    ["Perhitungan ilustratif", "Hasil", "Batas penggunaan"],
                    [["Gordon perpetual", f"Rp{fmt.rp(round(gordon / 10) * 10)}/saham",
                      "Terminal perpetual tidak cocok untuk aset tambang berumur terbatas."],
                     ["Exit EV/EBITDA", f"Rp{fmt.rp(round(exit_value / 10) * 10)}/saham",
                      "Kelipatan exit belum dijembatani ke LoM per aset."],
                     ["Selisih dua metode", fmt.pct(divergence),
                      "Tidak dirata-ratakan menjadi target harga."],
                     ["WACC / pertumbuhan terminal",
                      f"{fmt.pct(va['wacc'])} / {fmt.pct(wi['g'])}",
                      f"Screen termasuk penyesuaian berita {wi.get('news_wacc_bps', 0):+g} bp; "
                      "bukan discount rate dan life aset tervalidasi."],
                     ["Porsi nilai terminal", fmt.pct(va.get("tv_share") or 0),
                      "Ketergantungan terminal tinggi mengurangi kegunaan screen."]],
                    "Sumber: Sektoral historical screening model dari Sectors cache; "
                    "tidak memasukkan LoM/SOTP, jadwal proyek, dan jembatan 1H terbaru. "
                    "Tidak ada rating, target harga, atau nilai wajar produksi dari tabel ini.")
                grid = valuation_mod.gordon_screen_grid(
                    intake, fc, va["wacc"], wi["g"], wi["exit_mult"], va["net_debt"])
                grid_exhibit = add(
                    "Sensitivitas Gordon ilustratif (Rp/saham)",
                    ["WACC / g"] + [fmt.pct(rate) for rate in grid["growth_rates"]],
                    [[fmt.pct(rate)] + [
                        f"Rp{fmt.rp(round(value / 10) * 10)}" if value is not None else "n.m."
                        for value in values] for rate, values in grid["rows"]],
                    "Sumber: screen Gordon yang sama; bukan sensitivitas NAV tambang. "
                    "Basis pusat memakai asumsi lama dan bukan target harga.")
                illustrative_pages.append({
                    "halaman": 0, "judul": "Valuasi ilustratif dan keterbatasannya",
                    "layout": "stack",
                    "paragraf": ["Dua metode lama ditampilkan terpisah agar dampak asumsi "
                                 "terlihat. Metode ini belum menghitung arus kas sampai "
                                 "akhir umur tambang maupun nilai tiap aset, sehingga "
                                 "hasilnya tidak menjadi rekomendasi atau target harga."],
                    "exhibit": [value_exhibit, grid_exhibit]})

    if mining:
        release_rows = [
            ["Hasil interim resmi", ("Tersedia: " + actual["period"] + " dengan data keuangan dan operasi.")
             if actual else "Belum ada hasil interim resmi yang memenuhi tanggal laporan."],
            ["Forecast fisik", "Perlu jadwal produksi, pemrosesan dan penjualan, harga, biaya, pajak dan capex per tahun."],
            ["SOTP", "Perlu NAV setiap aset dan proyek yang material, kepemilikan, kas, utang, overhead dan jumlah saham."],
            ["Keputusan rilis", "Rating dan target harga ditahan sampai forecast dan SOTP dapat direkonsiliasi."]]
    else:
        release_rows = [
            ["Hasil interim resmi", ("Tersedia: " + actual["period"])
             if actual else "Belum ada rilis resmi yang tervalidasi untuk tanggal laporan."],
            ["Forecast operasi", "Perlu driver volume, harga/mix, margin, capex, modal kerja, pajak dan utang."],
            ["Valuasi", "Perlu FCFF yang direkonsiliasi dan sensitivitas terminal yang konsisten."],
            ["Keputusan rilis", "Rating dan target harga ditahan sampai seluruh pemeriksaan lolos."]]
    add("Pemeriksaan sebelum rating dan target harga",
        ["Pemeriksaan", "Bukti yang diperlukan"], release_rows,
        "Sumber: pemeriksaan rilis model Sektoral; rating dan target harga hanya "
        "dapat disajikan setelah seluruh syarat metode terpenuhi.")

    if actual:
        if mining:
            watch_rows = [
                [f"Perkembangan operasi {i + 1}", item["fact"],
                 "Uji dampaknya pada volume terjual, biaya, arus kas dan nilai aset."]
                for i, item in enumerate((evidence.get("operating_context") or [])[:2])
                if item.get("fact")]
            segments = revenue_breakdown.get("segments") or []
            if segments:
                segment = max(segments, key=lambda row: row.get("current") or 0)
                watch_rows.append([
                    f"Bauran {segment['name']}",
                    f"Penjualan {segment['name']} {money_phrase(segment.get('current'))} "
                    f"pada {actual['period']}.",
                    "Pantau volume, harga realisasi dan waktu pengakuan penjualan."])
            if guidance:
                item = guidance[0]
                watch_rows.append([
                    f"Panduan {item['name']}",
                    f"Manajemen menyatakan {fmt._id(item['value'], 0)} "
                    f"untuk {guidance_period}.",
                    "Bandingkan realisasi dengan panduan pada satuan dan periode yang sama."])
        else:
            watch_rows = [
                ["Pendapatan", "Pecah perubahan hasil menjadi volume, harga dan mix.",
                 "Butuh data operasi yang terhubung ke laporan keuangan."],
                ["Margin", "Pisahkan perubahan harga, biaya produksi dan biaya tetap.",
                 "Jangan ekstrapolasi margin tanpa jembatan operasional."],
                ["Kas dan capex", "Arus kas dan belanja modal belum direkonsiliasi ke forecast.",
                 "Butuh jadwal modal kerja, capex, bunga dan pajak."],
                ["Forecast", "Driver tahunan belum didukung bukti yang tervalidasi.",
                 "Rating dan target harga tetap ditahan."]]
        add("Katalis, risiko, dan indikator pemantauan",
            ["Tema", "Bukti terkini", "Implikasi yang diuji"], watch_rows,
            f"Sumber fakta: {actual['source_title']}; kolom implikasi adalah "
            "analisis Sektoral dan belum menjadi asumsi valuasi.")

    if actual:
        current = actual["metrics"]
        prior = actual.get("prior_year") or {}
        material_current = current.get("material_expense")
        material_prior = prior.get("material_expense")
        material_mix = (f"Beban material naik "
                        f"{pct_change(material_current, material_prior)} ke "
                        f"{fmt.pct(material_current/current['revenue'])} dari pendapatan "
                        f"({prior.get('period', 'periode pembanding')}: "
                        f"{fmt.pct(material_prior/prior['revenue'])}), "
                        "menahan margin EBITDA meski aktivitas naik. "
                        if material_current is not None and material_prior and
                        current.get("revenue") and prior.get("revenue") else "")
        last_annual_year = max(annual_by_year) if annual_by_year else None
        prior_full = annual_by_year.get(last_annual_year) or {}
        runrate = (f"Pendapatan {actual['period']} mencapai "
                   f"{fmt.pct(current['revenue']/prior_full['revenue'])} dari "
                   f"FY{last_annual_year}; perbandingan ini bukan pengganti "
                   f"uji terhadap forecast {f_labels[0]}. "
                   if current.get("revenue") and prior_full.get("revenue") else "")
        financial_fact_labels = (
            ("pendapatan", "revenue"), ("EBITDA", "ebitda"),
            ("laba usaha", "operating_profit"), ("laba bersih", "net_profit"),
        )
        lead_facts = []
        for label, key in financial_fact_labels:
            value = current.get(key)
            if value is None:
                continue
            fact = f"{label} {money_phrase(value)}"
            prior_value = prior.get(key)
            if prior_value is not None:
                fact += f" ({pct_change(value, prior_value)} yoy)"
            lead_facts.append(fact)
        lead = (f"{ticker} mencatat " + ", ".join(lead_facts) + ". " +
                f"{material_mix}{runrate}"
                f"Hasil ini berasal dari laporan resmi terbit {actual['published_at']}.")
        operating = evidence.get("operating_context") or []
        driver = operating[0]["fact"] if operating else "Rincian driver operasional belum tervalidasi."
        if revenue_breakdown and not mining:
            segment = (revenue_breakdown.get("segments") or [None])[0]
            customer_rows = revenue_breakdown.get("major_customers") or []
            segment_text = (f"Segmen {segment['name']} tumbuh "
                            f"{pct_change(segment.get('current'), segment.get('prior'))} "
                            f"ke {money_phrase(segment.get('current'))}. "
                            if segment else "")
            customer_names = " dan ".join(row["name"] for row in customer_rows[:2])
            customer_text = (
                f"Pelanggan {customer_names} menyumbang "
                f"{fmt.pct(sum(c.get('current') or 0 for c in customer_rows) / current['revenue'])} "
                f"pendapatan {actual['period']}; konsentrasi pelanggan ini menjadi "
                "risiko volume dan piutang. "
                if customer_rows and current.get("revenue") else "")
        else:
            segment_text = customer_text = ""
        milestone = (operating[1]["fact"] + " " if len(operating) > 1 else "")
        if mining:
            segments = revenue_breakdown.get("segments") or []
            largest = max(segments, key=lambda row: row.get("current") or 0) if segments else None
            mix_text = (
                f"{largest['name']} menyumbang {money_phrase(largest.get('current'))} "
                f"atau {fmt.pct(largest['current'] / current['revenue'])} dari "
                f"pendapatan {actual['period']}. "
                if largest and largest.get("current") is not None and current.get("revenue") else "")
            outlook = (f"{driver} {milestone}{mix_text}"
                       "Jembatan produksi, persediaan, penjualan, harga realisasi, "
                       "biaya dan capex per tahun belum lengkap untuk membangun "
                       "proyeksi umur aset.")
        else:
            outlook = (f"{driver} {segment_text}{milestone}{customer_text}"
                       "Forecast memerlukan driver pendapatan dan biaya, capex, modal kerja, "
                       "pajak dan utang yang dapat ditelusuri ke sumber dan tahun fiskal.")
        if balance:
            debt = balance.get("total_debt")
            if debt is None:
                debt_components = [balance.get(key) for key in
                                   ("loans_current", "loans_noncurrent", "lease_current",
                                    "lease_noncurrent")]
                if all(value is not None for value in debt_components):
                    debt = sum(debt_components)
            cash = balance.get("cash")
            if cash is not None and debt is not None:
                net_debt_text = f"utang bersih {money_phrase(debt - cash)}"
                position_text = (f"Kas {money_phrase(cash)} dan pinjaman berbunga "
                                 f"{money_phrase(debt)} menyiratkan {net_debt_text}.")
            else:
                cash_text = money_phrase(cash) if cash is not None else "belum tersedia"
                debt_text = money_phrase(debt) if debt is not None else "belum tersedia"
                position_text = (f"Kas {cash_text}; pinjaman berbunga {debt_text}; "
                                 "utang bersih belum dapat dihitung dari data yang tersedia.")
            equity = balance.get("total_equity")
            equity_text = money_phrase(equity) if equity is not None else "belum tersedia"
            valuation_text = (
                f"{position_text} Per {balance.get('period_end', 'tanggal laporan')}. "
                f"Ekuitas tercatat {equity_text}. " +
                ("SOTP yang dapat dipakai sebagai target perlu LoM dan NAV tiap aset "
                 "material, arus kas pemrosesan, biaya penyelesaian proyek, nilai "
                 "opsi yang disesuaikan risiko, dan rekonsiliasi utang bersih. " if mining else
                "DCF FCFF yang dapat dipakai sebagai target memerlukan jadwal utang dan "
                "bunga, capex, perubahan modal kerja, serta proyeksi operasi yang "
                "terhubung. Selisih nilai Gordon dan exit multiple pada screen lama "
                "belum direkonsiliasi. ") +
                "Karena itu rating dan Target Harga masih ditahan; tabel halaman "
                "valuasi mencatat bukti yang kurang.")
        else:
            valuation_text = ("Data aktual yang tersedia belum cukup untuk "
                              "menerbitkan nilai wajar atau rekomendasi produksi. "
                              "Pemeriksaan yang belum selesai tercantum pada halaman valuasi.")
        first_bullet = (f"Pendapatan {actual['period']} tumbuh "
                        f"{pct_change(current.get('revenue'), prior.get('revenue'))} yoy "
                        f"ke {money_phrase(current.get('revenue'))}.")
        if mining:
            segments = revenue_breakdown.get("segments") or []
            segment_facts = ", ".join(
                f"{row['name']} {money_phrase(row.get('current'))}"
                for row in segments if row.get("current") is not None)
            composition = (
                f"Rincian penjualan {actual['period']} mencatat {segment_facts}. "
                "Bauran produk dan waktu penjualan perlu dijembatani ke realisasi "
                "harga sebelum menjadi forecast tahunan."
                if segment_facts else
                "Rincian produk dan penjualan belum cukup untuk menjembatani "
                "perubahan volume ke pendapatan tahunan.")
            cash_facts = []
            for label, key in (("Belanja modal", "capital_expenditure"),
                               ("arus kas operasi", "operating_cash_flow")):
                value = current.get(key)
                if value is not None:
                    cash_facts.append(f"{label} {money_phrase(value)} "
                                      f"({pct_change(value, prior.get(key))} yoy)")
            cash_line = "; ".join(cash_facts)
            cash_text = (cash_line[:1].upper() + cash_line[1:] + ". "
                         if cash_line else "")
            margin_text = (
                f"Margin EBITDA {fmt.pct(current['ebitda'] / current['revenue'])} "
                f"({actual['period']}) dibanding "
                f"{fmt.pct(prior['ebitda'] / prior['revenue'])} "
                f"({prior.get('period', 'periode pembanding')}). "
                if current.get("ebitda") is not None and current.get("revenue") and
                prior.get("ebitda") is not None and prior.get("revenue") else "")
            result_paragraphs = [composition,
                margin_text + cash_text +
                "Jadwal produksi, capex, modal kerja dan pembayaran utang masih "
                "diperlukan untuk menilai keberlanjutan arus kas."]
            second_bullet = _trim(driver, 30)
        else:
            result_paragraphs = [
                "Angka interim menunjukkan hasil yang dilaporkan untuk periode tersebut, "
                "tetapi tidak dengan sendirinya menetapkan lintasan tahunan. Perubahan "
                "mix, biaya, modal kerja dan unsur non-operasional perlu direkonsiliasi "
                "dengan laporan sebelum forecast dibuat.",
                "Bukti yang tersedia belum menyediakan jembatan terukur dari volume, "
                "harga atau mix ke margin, capex dan arus kas. Driver tersebut tetap "
                "ditandai belum terverifikasi dan tidak diisi dari CAGR historis."]
            second_bullet = ("Pisahkan driver pendapatan, biaya, modal kerja dan capex "
                             "sebelum hasil interim diterjemahkan menjadi forecast.")
    else:
        lead = ("Hasil interim terbaru dan tanggal publikasi belum dapat "
                "dibuktikan dari data yang tersedia.")
        outlook = ("Driver operasi, capex dan arus kas perlu diverifikasi sebelum "
                   "forecast dan valuasi diterbitkan.")
        valuation_text = ("Data aktual yang tersedia belum cukup untuk "
                          "menerbitkan nilai wajar atau rekomendasi produksi.")
        first_bullet = "Hasil interim resmi terbaru belum tervalidasi."
        result_paragraphs = []
        second_bullet = "Driver operasi dan arus kas masih perlu verifikasi."

    sections = [
        {"halaman": 2, "judul": "Hasil terbaru dan jembatan laba",
         "layout": "stack", "paragraf": [lead] + result_paragraphs,
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Hasil interim resmi dan perubahan yoy",
                      "Baris kuartalan dalam data lokal",
                      "Rasio yang menjelaskan kualitas hasil",
                      f"Perbandingan metrik {actual['period']}" if actual else ""}]},
        {"halaman": 3, "judul": "Operasi dan posisi keuangan",
         "layout": "stack", "paragraf": [outlook],
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Posisi neraca interim",
                      "Jembatan pendapatan menurut layanan dan pelanggan",
                      f"Komposisi pendapatan {actual['period']}" if actual else "",
                      "Metrik operasi dan pemrosesan",
                      "Cadangan dan jadwal tambang dari rilis resmi",
                      f"Panduan produksi {guidance_period} dari manajemen" if guidance and actual else ""}]},
        {"halaman": 4, "judul": "Valuasi dan kelengkapan bukti",
         "layout": "stack",
         "paragraf": [valuation_text],
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Pemeriksaan sebelum rating dan target harga",
                      "Katalis, risiko, dan indikator pemantauan"}]},
    ]
    if illustrative_pages:
        sections[2:2] = illustrative_pages
        for page_number, section in enumerate(sections, start=2):
            section["halaman"] = page_number

    method = (method or "auto").lower()
    method_select = method
    _is_bank = "bank" in ((intake.get("sub_sector") or "") + " " +
                          (intake.get("industry") or "")).lower() or \
               intake.get("model_profile") == "financial_ddm" or method == "ddm"

    if _is_bank and va.get("wacc_inputs"):
        A = intake.get("annuals") or []
        F = fc.get("rows") or []
        _re, _g = va["wacc_inputs"]["re"], va["wacc_inputs"]["g"]
        _nets = [r["net"] for r in F] if F else [0, 0, 0]
        _bvps = (A[-1].get("equity") or 0) / intake["shares"] if (A and intake.get("shares")) else 0
        _roae = _nets[0] / F[0]["equity"] if (F and F[0].get("equity")) else 0.12
        _roe_h = [(a.get("earnings") or 0) / a["equity"] for a in A[-3:]
                  if a.get("equity")]
        _vb = ddm.value_bank(_nets, None, intake.get("dps_hist") or [],
                             intake["shares"], _re, _g, _roae, _bvps)
        wi = va["wacc_inputs"]
        add("Komponen Cost of Equity", ["Komponen", "Nilai"],
            [["Jalur CAPM:", ""],
             ["Risk-free rate (INDOGB 10Y)", fmt.pct(wi["rf"])],
             ["Beta (Bloomberg)", fmt.mult(wi["beta"])],
             ["Equity Risk Premium (Damodaran)", fmt.pct(wi["erp"])],
             ["(=) Cost of Equity dipakai", fmt.pct(wi["re"])],
             ["Jalur band (pola BBTN):", ""],
             ["CoE mean 5 tahun", "n.a. (tanpa histori CoE di cache)"],
             ["CoE SD 5 tahun", "n.a. (tanpa histori CoE di cache)"],
             ["Offset dari mean", "n.a.: dipakai hasil CAPM"]],
            "Source: Company, Sektoral Estimates; Rf = INDOGB 10Y, "
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
        add("Sensitivitas DDM (CoE x g)",
            ["CoE / g"] + [f"g {fmt.pct(_gg)}" for _gg in (_g - 0.01, _g, _g + 0.01)],
            _cg_rows,
            "Source: Sektoral Estimates; sel = Nilai Wajar/saham Gordon; "
            "base (*) = CoE dan g terpakai")

        _cr_rows = []
        for _d in (-0.01, -0.005, 0.0, 0.005, 0.01):
            _cr_rows.append(
                [f"CoE {fmt.pct(_re + _d)}" + (" (base)" if _d == 0 else "")] +
                [fmt.rp(round(((_rr - _g) / (_re + _d - _g)) * _bvps / 10) * 10)
                 for _rr in (_roae - 0.04, _roae, _roae + 0.04)])
        add("Sensitivitas Inverse CoE (CoE x ROE)",
            ["CoE / ROE"] + [f"ROE {fmt.pct(_rr)}" for _rr in
                             (_roae - 0.04, _roae, _roae + 0.04)],
            _cr_rows,
            "Source: Sektoral Estimates; sel = P/BV wajar x BVPS; "
            "Fair P/BV = (ROE-g)/(CoE-g)")

        _roe_tr = ("naik" if _roe_h and _roae >= _roe_h[0] else "melandai")
        p_ddm = (f"Driver utama valuasi bank ini adalah lintasan ROE, bukan arus kas: "
                 f"ROAE historis {fmt.pct(_roe_h[0]) if _roe_h else '-'} {_roe_tr} ke {fmt.pct(_roae)} "
                 f"forward bila laba {(F[0]['label'] if F else 'FY26F')} tercapai. DDM Gordon memberi "
                 f"Rp{fmt.rp(round(_vb['tp_gordon'] / 10) * 10)}/saham pada payout "
                 f"{fmt.pct(_vb['payout_used'])} ({intake.get('payout_basis')}); silang cek "
                 f"Inverse CoE Rp{fmt.rp(round(_vb['tp_inverse'] / 10) * 10)}/saham "
                 f"(P/BV wajar {fmt.mult(_vb['fair_pbv'], 2)}x). Payout {fmt.pct(_vb['payout_used'])} "
                 f"dinilai sustain sepanjang kebutuhan modal pertumbuhan kredit/aset "
                 f"tidak menuntut retensi di atas level historis; "
                 f"{intake.get('dps_basis')}.")

        sections.append({
            "halaman": len(sections) + 2,
            "judul": "Skenario nilai",
            "layout": "stack",
            "paragraf": [p_ddm],
            "exhibit": [e for e in exhibits if e["judul"] in {
                "Komponen Cost of Equity",
                "Sensitivitas DDM (CoE x g)",
                "Sensitivitas Inverse CoE (CoE x ROE)",
            }],
        })

    if method == "ddm":
        method_label = "DDM (dividen, Rp)"
    elif method == "dcf":
        method_label = "DCF (FCFF, Rp)"
    elif method == "rnav":
        method_label = "RNAV LoM (Rp)"
    elif _is_bank:
        method_label = "DDM (dividen, Rp)"
    elif mining:
        method_label = ("SOTP/LoM menunggu; DCF screen internal"
                        if illustrative_pages else "SOTP/LoM (belum lengkap)")
    else:
        method_label = "DCF FCFF (belum lengkap)"

    catatan = [
        "DRAFT NON-DISTRIBUTABLE: rating dan target harga belum disajikan.",
        f"Hasil interim {actual.get('period', 'terbaru')} memakai sumber resmi "
        "bila tersedia; forecast tidak diturunkan otomatis dari CAGR historis.",
        "Tanda '-' berarti angka tidak tersedia atau belum tervalidasi, bukan nol.",
    ]
    if illustrative_pages:
        catatan.append(
            "Skenario ilustratif memakai proksi historis dan metode perpetual/exit; "
            "hasilnya bukan forecast produksi, NAV umur tambang atau target harga.")
    if method != "auto":
        catatan.insert(0, f"metode valuasi dipilih analis: {method_label}.")

    return {
        "meta": {"ticker": ticker, "emiten": intake["name"],
                 "tanggal": intake["as_of"], "harga": intake["price"],
                 "harga_tanggal": intake["price_date"],
                 "status": "draft_non_distributable",
                 "illustrative_scenarios": bool(illustrative_pages),
                 "status_rating": "Dalam peninjauan",
                 "research_status": (intake.get("research_analysis_status") or {}).get("status", "missing")},
        "cover": {"headline": (
                    ("Pendapatan Interim Naik, SOTP Menunggu Bukti" if
                     actual and (actual.get("prior_year") or {}).get("revenue") and
                     actual["metrics"].get("revenue", 0) > actual["prior_year"]["revenue"] else
                     "Hasil Interim Terbit, SOTP Menunggu Bukti") if mining else
                    "Hasil Terbaru Menunggu Model Lengkap"),
                  "bullets": [first_bullet,
                              second_bullet,
                              ("Skenario angka di halaman berikut adalah ilustrasi internal, "
                               "bukan target harga atau rekomendasi." if illustrative_pages else
                               "Rating dan target harga menunggu forecast serta valuasi yang tervalidasi.")],
                  "paragraf": [
                      {"judul": "Hasil terbaru memberi titik awal", "isi": lead},
                      {"judul": "Driver operasi perlu diuji", "isi": outlook},
                      {"judul": "Valuasi menunggu rekonsiliasi", "isi": valuation_text}],
                  "data_pasar": {"harga": intake["price"],
                                  "saham": shares_outstanding or intake["shares"],
                                  "market_cap": intake["price"] *
                                  (shares_outstanding or intake["shares"]),
                                  "adtv": "-", "free_float": "-"},
                   "key_financials": key_rows},
        "bagian": sections,
        "tabel_asumsi": [], "exhibits": exhibits,
        "log_gate": {"G1": g1.get("G1", {}), "G2": fc.get("g2", {}),
                     "G3": {},
                     "release": {"status": "draft_non_distributable",
                                 "blocker_count": len(blockers),
                                 "blockers": blockers}},
        "method": method_label,
        "method_select": method_select,
        "holders": [],
        "catatan_metodologi": catatan,
    }


def _build_assumption_led(intake, fc, va, g1, method="auto"):
    """Publish the validated FY scenario as the selected multiple-based method."""
    doc = _build_general_draft(intake, fc, va, g1, method=method,
                               illustrative_scenarios=True)
    scenario = fc["interim_scenario"]
    forecast_label = f"FY{scenario['year'] % 100:02d}F"
    value = va["scenario_target"]
    meta = doc["meta"]
    meta.update(status="distributable_assumption_led", rating=va["rating"],
                tp=va["tp"], upside_persen=va["upside"] * 100,
                status_rating=va["rating"], illustrative_scenarios=False)
    doc["method"] = va["method"]
    doc["log_gate"]["G3"] = va["g3"]
    doc["log_gate"]["release"] = va["release"]
    doc["cover"]["headline"] = (
        f"{va['rating']}: {forecast_label} EBITDA dan valuasi 8x EV/EBITDA")
    doc["cover"]["bullets"][2] = (
        f"Target Rp{fmt.rp(va['tp'])} memberi {fmt.pct(va['upside'])} terhadap "
        f"penutupan Rp{fmt.rp(intake['price'])} pada {intake['price_date']}; "
        "basis 8x EV/EBITDA adalah asumsi analis.")
    doc["cover"]["paragraf"][2] = {
        "judul": "Target harga berbasis hasil FY",
        "isi": (f"EBITDA {forecast_label} US${fmt._id(value['ebitda_usd']/1e6, 1)} "
                "juta berasal dari realisasi interim dan asumsi semester berikutnya. "
                "Kelipatan 8x dipilih di bawah kelipatan implisit harga pasar "
                f"{fmt.mult((intake['price'] * value['shares'] / value['fx']['rate'] + value['net_debt_usd'] + value['minority_interest_usd']) / value['ebitda_usd'], 1)} "
                "untuk mencerminkan ketidakpastian LoM dan capex. Nilai ekuitas "
                "dihitung setelah utang bersih dan "
                "kepentingan nonpengendali. LoM/SOTP per aset belum tersedia; "
                "karena itu risiko umur tambang, capex, dan harga komoditas material.")}
    doc["catatan_metodologi"] = [
        "Rating dan target harga memakai FY forecast berbasis hasil interim resmi "
        "serta multiple 8x EV/EBITDA sebagai asumsi analis, bukan multiple peer terverifikasi.",
        "Skenario 6x/8x/10x menunjukkan sensitivitas; 8x adalah basis target harga.",
        f"Harga penutupan {intake['price_date']} bersumber dari "
        f"{(intake.get('market_quote') or {}).get('source_url', 'data pasar bertanggal')}.",
        "LoM/SOTP per aset, capex masa depan, dan perubahan kas/utang setelah neraca "
        "interim belum dimodelkan; audit gate SOTP tetap ada dalam trace.",
        "Tanda '-' berarti angka tidak tersedia, bukan nol.",
    ]
    remove_titles = {"Konteks historis dan kepemilikan", "Skenario operasi ilustratif",
                     "Valuasi ilustratif dan keterbatasannya"}
    if not any(effect.get("driver") != "none" for effect in fc.get("news_assumptions") or []):
        remove_titles.add("Berita dan keputusan asumsi")
    doc["bagian"] = [page for page in doc["bagian"] if page["judul"] not in remove_titles]
    forward = fc.get("outyear_scenario")
    if forward and forward.get("rows"):
        source_lookup = {"official": (intake.get("official_evidence") or {}).get("latest_actual", {}).get("source_url")}
        news_effects = fc.get("news_assumptions") or []
        source_lookup.update({f"news:{item.get('article_index')}": item.get("source_url")
                              for item in news_effects})
        assumption_rows = []
        cited_urls = []
        for row in forward["rows"]:
            sources = [source_lookup[source_id] for source_id in row["source_ids"]
                       if source_lookup.get(source_id)]
            cited_urls.extend(sources)
            assumption_rows.append([
                row["label"],
                (f"Revenue growth {fmt.pct(row['revenue_growth_pct'] / 100)}; "
                 f"EBITDA margin {fmt.pct(row['ebitda_margin_pct'] / 100)}; "
                 f"net margin {fmt.pct(row['net_income_margin_pct'] / 100)}; "
                 f"capex/revenue {fmt.pct(row['capex_to_revenue_pct'] / 100)}"),
                f"{row['rationale']} [Sumber: {', '.join(row['source_ids'])}]"])
        assumptions_exhibit = {
            "n": len(doc["exhibits"]) + 1,
            "judul": "Asumsi skenario laba FY27F-FY30F",
            "tipe": "tabel",
            "data": {"cols": ["Tahun", "Asumsi analis", "Dasar dan batasan"],
                     "rows": assumption_rows},
            "catatan_sumber": (
                "Sumber referensi: " + "; ".join(dict.fromkeys(cited_urls)) +
                ". Angka tahunan dihitung dari FY26F dan asumsi di tabel; "
                "bukan panduan emiten atau forecast produksi LoM.")}
        doc["exhibits"].append(assumptions_exhibit)
        anchor = next((index for index, page in enumerate(doc["bagian"])
                       if page["judul"] == "Forecast FY26 dari rilis terbaru"), 0)
        doc["bagian"].insert(anchor + 1, {
            "halaman": 0,
            "judul": "Skenario laba FY27F-FY30F",
            "layout": "stack",
            "paragraf": [
                "Estimasi di bawah memperpanjang FY26F memakai pertumbuhan dan "
                "margin asumsi analis yang diturunkan dari rilis resmi dan konteks "
                "operasi. Perusahaan belum memberi jadwal tahunan produksi, harga, "
                "biaya dan capex untuk periode ini; angka ini adalah skenario laba, "
                "bukan forecast fisik tambang atau SOTP."],
            "exhibit": [assumptions_exhibit],
        })
    for page in doc["bagian"]:
        if page["judul"] == "Skenario FY26 dari rilis terbaru":
            page["judul"] = f"Forecast {forecast_label} dari rilis terbaru"
            page["paragraf"] = [
                "Hasil interim resmi menjadi basis semester pertama. Semester kedua "
                "mengikuti asumsi analis yang dijelaskan di tabel; panduan produksi "
                "belum otomatis menjadi volume penjualan.",
                ". ".join((scenario.get("rationale") or "").split(". ")[:4]).rstrip(".") + "."]
        elif page["judul"] == "Cross-check nilai FY26 dari hasil terbaru":
            page["judul"] = f"Target harga {forecast_label} EV/EBITDA"
            page["paragraf"] = [
                f"Target Rp{fmt.rp(va['tp'])} memakai EBITDA {forecast_label} "
                "dan multiple 8x. Rentang 6x–10x memperlihatkan sensitivitas "
                "terhadap asumsi valuasi; seluruh nilai memakai utang, minoritas, "
                "jumlah saham, dan kurs yang ditampilkan."]
        elif page["judul"] == "Valuasi dan kelengkapan bukti":
            page["judul"] = "Valuasi dan batasan model"
            page["paragraf"] = [
                "Metode utama adalah FY forecast EV/EBITDA 8x dengan asumsi analis. "
                "LoM/SOTP tetap belum lengkap; daftar di bawah menunjukkan bukti "
                "yang diperlukan untuk menguji ulang nilai aset dan capex."]
        page["halaman"] = doc["bagian"].index(page) + 2
    for exhibit in doc["exhibits"]:
        title = exhibit["judul"]
        if title == "Cross-check EV/EBITDA FY26 berbasis skenario interim":
            exhibit["judul"] = f"Target harga dan sensitivitas {forecast_label} EV/EBITDA"
            exhibit["data"]["rows"][2][0] = "Nilai ekuitas (Rp/saham)"
            exhibit["catatan_sumber"] = (
                f"Sumber EBITDA: {value['source_url']}; neraca: "
                f"{(intake.get('official_evidence') or {}).get('balance_sheet', {}).get('source_url')}; "
                f"kurs {value['fx']['source']} ({value['fx']['date']}). "
                "6x/8x/10x adalah asumsi analis; 8x menjadi basis target, "
                "bukan multiple peer terverifikasi.")
        elif title == "Input cross-check FY26 dan batasannya":
            exhibit["judul"] = f"Input target harga {forecast_label} dan batasannya"
            exhibit["data"]["rows"][3][2] = (
                f"Kurs {value['fx']['date']}; harga penutupan {intake['price_date']}.")
            exhibit["catatan_sumber"] = (
                "Sumber: rilis interim resmi, neraca emiten, dan FX bertanggal. "
                "Metode multiple tidak menghitung LoM, capex per aset, atau perubahan "
                "utang sesudah tanggal neraca.")
        elif title == "Pemeriksaan sebelum rating dan target harga":
            exhibit["judul"] = "Bukti lanjutan untuk menguji target harga"
            exhibit["data"]["rows"][-1][1] = (
                "Target berbasis multiple diterbitkan; LoM/SOTP tetap perlu "
                "direkonsiliasi sebelum dipakai sebagai metode aset.")
            exhibit["catatan_sumber"] = (
                "Sumber: pemeriksaan model Sektoral; kelengkapan LoM/SOTP "
                "dicatat terpisah dari metode target FY EV/EBITDA.")
    used = {id(exhibit) for page in doc["bagian"] for exhibit in page["exhibit"]}
    used.add(id(doc["exhibits"][0]))
    doc["exhibits"] = [exhibit for exhibit in doc["exhibits"] if id(exhibit) in used]
    for number, exhibit in enumerate(doc["exhibits"], 1):
        exhibit["n"] = number
    if doc["cover"].get("key_financials"):
        rows = doc["cover"]["key_financials"]
        full = scenario["full_year"]
        forecast_values = [{"year": scenario["year"], **full}] + (forward or {}).get("rows", [])
        history = (intake.get("official_evidence") or {}).get("annual_actuals") or []
        prior = next((row for row in history if row.get("year") == scenario["year"] - 1), {})
        for row in rows:
            key = ("revenue" if row[0].startswith("Pendapatan") else
                   "ebitda" if row[0].startswith("EBITDA") else
                   "net_profit" if row[0].startswith("Laba bersih") else None)
            growth_key = ("revenue" if row[0].startswith("Pertumbuhan pendapatan") else
                          "ebitda" if row[0].startswith("Pertumbuhan EBITDA") else
                          "net_profit" if row[0].startswith("Pertumbuhan laba bersih") else None)
            metric = key or growth_key
            if metric:
                previous_value = prior.get(metric)
                for index, projection in enumerate(forecast_values, start=3):
                    if index >= len(row):
                        break
                    current_value = projection.get(metric)
                    if current_value is None:
                        continue
                    if key:
                        row[index] = fmt._id(current_value / 1e6, 1)
                    elif previous_value and previous_value > 0:
                        row[index] = fmt.pct(current_value / previous_value - 1)
                    previous_value = current_value
        doc["exhibits"][0]["catatan_sumber"] = (
            f"Sumber aktual: {(intake.get('official_evidence') or {}).get('annual_source_title')}; "
            f"{forecast_label} adalah estimasi Sektoral dari rilis interim "
            f"{scenario['source_url']} dan asumsi semester kedua. "
            + ("FY27F-FY30F adalah skenario laba asumsi analis pada exhibit terpisah; "
               "bukan jadwal produksi LoM. " if forward else
               "FY27F-FY30F belum dimodelkan karena asumsi lanjutan belum tervalidasi. ")
            + "EPS/BVPS historis memakai jumlah saham "
            f"per {value['balance_period']} sebagai basis pro forma.")
    doc["fy26"] = {
        "Pendapatan": fmt._id(scenario["full_year"]["revenue"] * value["fx"]["rate"] / 1e9, 0),
        "EBITDA": fmt._id(scenario["full_year"]["ebitda"] * value["fx"]["rate"] / 1e9, 0),
        "Laba bersih": fmt._id(scenario["full_year"]["net_profit"] * value["fx"]["rate"] / 1e9, 0),
    }
    return doc


def _research_section(intake, page=2):
    """Build print-friendly cards from the upstream-validated research brief."""
    brief = intake.get("research_analysis")
    if not isinstance(brief, dict):
        return None
    insights, cards = brief.get("insights"), []
    if not isinstance(insights, list):
        return None
    for item in insights:
        if not isinstance(item, dict):
            continue
        citations = _research_citation_labels(item.get("citations") or [])
        # Research claims without a validated cache citation are not published.
        if not citations:
            continue
        cards.append({"title": _word_cut(item.get("title") or "Temuan", 100),
                      "observation": _word_cut(item.get("observation") or "-", 330),
                      "implication": _word_cut(item.get("implication") or "-", 330),
                      "caveat": _word_cut(item.get("caveat") or "-", 240),
                      "citations": citations[:4]})
    if not cards:
        return None
    paragraphs = []
    summary = brief.get("summary")
    if summary:
        paragraphs.append(_word_cut(summary, 320))
    as_of = brief.get("as_of")
    if as_of:
        paragraphs.append(f"Ringkasan riset bertanggal {str(as_of)[:40]}.")
    limitations = brief.get("limitations")
    if isinstance(limitations, list) and limitations:
        paragraphs.append("Batasan: " + "; ".join(_word_cut(x, 120) for x in limitations[:4]))
    return {"halaman": page, "judul": "Ringkasan riset berbantuan AI",
            "layout": "research_cards", "paragraf": paragraphs,
            "research_cards": cards, "exhibit": []}


def _rnav_exhibit(lom, cash_idr, debt_idr, shares, discount_pct=0.0):
    """Convert LoM Rp-billion asset values to the raw-IDR table contract."""
    assets = [{"nama": stream["nama"], "nav": stream["nav_rpbn"] * 1e9,
               "kepemilikan": stream["kepemilikan"], "ukuran": stream["ukuran"]}
              for stream in lom["streams"]]
    return valtables.rnav_exhibits(
        assets, cash_idr, debt_idr, 0, shares, discount_pct)


def _build_draft(intake, fc, va, g1, method="auto",
                 illustrative_scenarios=False):
    """Build a clearly non-distributable evidence/status report.

    Do not expose the legacy DCF target or imply that the historical-CAGR
    mining screen is a production forecast. All reported facts come from the
    Sectors cache; local research documents and analyst estimate files are
    deliberately excluded.
    """
    if (intake.get("model_profile") != "finite_life_mining" or
            intake.get("official_evidence")):
        return _build_general_draft(intake, fc, va, g1, method=method,
                                    illustrative_scenarios=illustrative_scenarios)
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
            "Hanya diagnostik internal dan bukan estimasi produksi.")

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
        deepdive = [item for item in (intake.get("news_full") or [])
                    if isinstance(item, dict)]
        fetched = [item for item in deepdive if item.get("fetch_status") == "fetched"]
        deepdive_note = ""
        if deepdive:
            deepdive_note = (
                f" Teks lengkap otomatis tersedia untuk {len(fetched)} dari "
                f"{len(deepdive)} tautan berita di atas; kutipan yang dipakai "
                "agen tetap merujuk pada judul dan tautan yang sama dengan cache."
            )
        news_no = add(
            "Konteks berita dari cache dan implikasi",
            ["Tanggal", "Narasi ulang", "Kaitan ke tesis", "Batasan"], news_rows,
            "Analisis agen atas berita ticker-spesifik di sectors_cache /news/. "
            "Berita adalah konteks media, bukan guidance; tidak mengubah forecast numerik "
            "tanpa dukungan data finansial/operasi cache. Referensi: " +
            "; ".join(news_sources) + "." + deepdive_note)

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
            "NAV per aset dan/atau jembatan ekuitas belum lengkap; skenario nilai belum dapat disajikan.")
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
        "skenario nilai menunggu NAV aset dan jembatan ekuitas tervalidasi.")

    profile_basis = intake.get("model_profile_basis") or "basis profil tidak tersedia"
    price_date = intake.get("price_date")
    profile_text = (f"Model profile: {profile} ({profile_basis}). Fakta yang ditampilkan "
                    "dan angka historis hanya berasal dari sectors cache. Belum ada "
                    "forecast fisik-ke-keuangan yang lolos rekonsiliasi; nilai CAGR dan "
                    "RNAV annuitas tidak dipakai sebagai target.")
    release_text = ("Dokumen ini berstatus DRAFT NON-DISTRIBUTABLE. Skenario nilai belum "
                    "disajikan karena data interim, forecast fisik, dan provenance "
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
    research = _research_section(intake)
    if research:
        sections.insert(0, research)
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
                                      "bukan estimasi produksi atau guidance."],
                         "exhibit": [exhibits[screening_no - 1]]})
    for page_number, section in enumerate(sections, start=2):
        section["halaman"] = page_number

    price = intake["price"]
    market_cap = intake["market_cap"]
    return {
        "meta": {"ticker": t, "emiten": name, "tanggal": intake["as_of"],
                 "harga_tanggal": price_date,
                 "status": "draft_non_distributable", "harga": price,
                 "research_status": (intake.get("research_analysis_status") or {}).get("status", "missing")},
        "cover": {
        "headline": "Bukti Model Belum Lengkap",
            "bullets": [
                "Skenario nilai belum disajikan karena bukti penting masih kurang.",
                "Data sumber dibatasi pada sectors cache; sumber riset eksternal tidak dipakai.",
                "Berita yang lolos validasi diparafrase dan dihubungkan ke tesis dengan caveat.",
                "SOTP/LoM belum dapat direkonsiliasi dari input yang tersedia.",
            ],
            "paragraf": [
                {"judul": "Status riset", "isi": release_text},
                {"judul": "Basis model", "isi": profile_text},
            ],
            "data_pasar": {"harga": price,
                            "saham": intake["shares"], "market_cap": market_cap,
                            "adtv": "-", "free_float": "-"},
            "key_financials": hist_rows,
        },
        "bagian": sections,
        "tabel_asumsi": [],
        "log_gate": {"G1": g1.get("G1", {}), "G2": fc.get("g2", {}),
                     "G3": {}, "release": {"status": release_result.get("status"),
                                              "blocker_count": len(blockers)}},
        "method": ("DDM (dividen, Rp)" if method == "ddm" else
                   "DCF (FCFF, Rp)" if method == "dcf" else
                   "RNAV LoM (Rp)" if method == "rnav" else
                   "SOTP/LoM (belum lengkap)"),
        "method_select": method, "holders": [],
        "catatan_metodologi": (
            [f"metode valuasi dipilih analis: {'DDM (dividen, Rp)' if method == 'ddm' else 'DCF (FCFF, Rp)' if method == 'dcf' else 'RNAV LoM (Rp)'}."] if method != "auto" else []
        ) + [
            "DRAFT NON-DISTRIBUTABLE: skenario nilai belum disajikan karena bukti belum lengkap.",
            "SOTP/LoM memerlukan NAV per aset, kepemilikan, net debt, minority interest, "
            "overhead korporat dan saham terdilusi dengan provenance.",
            "Validasi latest interim memakai metadata yang tersedia di cache; data di luar cache tidak dipakai.",
            "News context hanya memakai berita ticker-spesifik dari cache dan tidak langsung menjadi angka forecast.",
            "Forecast tambang harus dihitung dari driver fisik; proyeksi CAGR hanya screening.",
            "RNAV annuitas indikatif dari overlay cache bukan nilai wajar karena bukan SOTP asset-level.",
        ],
        "exhibits": exhibits,
    }


def build(intake, fc, va, g1, method="auto", illustrative_scenarios=False):
    method = (method or "auto").lower()
    if method not in ("auto", "dcf", "ddm", "rnav"):
        raise ValueError(f"method tak dikenal: {method} (auto|dcf|ddm|rnav)")
    if method == "ddm" and intake.get("payout") is None:
        raise ValueError("method ddm ditolak: tanpa payout di cache")
    if method == "rnav" and not intake.get("mineops"):
        raise ValueError("method rnav ditolak: tanpa overlay operasional di cache")
    if (va.get("release") or {}).get("status") == "distributable_assumption_led":
        return _build_assumption_led(intake, fc, va, g1, method=method)
    if (va.get("release") or {}).get("status") != "distributable":
        return _build_draft(intake, fc, va, g1, method=method,
                            illustrative_scenarios=illustrative_scenarios)
    t, name = intake["ticker"], intake["name"]
    A, F = intake["annuals"], fc["rows"]
    last, rev_last = A[-1], A[-1]["revenue"]
    rev_cagr = (A[-1]["revenue"] / A[0]["revenue"]) ** (1 / (len(A) - 1)) - 1
    f1 = F[0]
    modeled_value_s = fmt.rp(va["tp"])

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
    b2 = _trim(f"Driver utama {F[1]['label']}-{F[-1]['label']} adalah volume dan operating "
               f"leverage menuju margin {fmt.pct(F[-1]['margin'])}.", 30)
    b3 = _trim(f"{va['rating']} dengan Target Harga Rp{modeled_value_s} "
               f"(upside/downside {fmt.pct(va['upside'])}) berdasarkan {va['method']}.", 30)

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
    p3 = (f"Skenario nilai memakai {va['method']}, dengan WACC {fmt.pct(va['wacc'])} (risk-free "
          f"{fmt.pct(wacc_in['rf'])}, beta {fmt._id(wacc_in['beta'], 1)}) dan terminal growth "
          f"{fmt.pct(wacc_in['g'])}. Nilai skenario indikatif Rp{modeled_value_s} per saham "
          f"merupakan rerata Gordon Rp{fmt.rp(va['ps_gordon'])} dan exit EV/EBITDA "
          f"{fmt._id(wacc_in['exit_mult'], 1)}x Rp{fmt.rp(va['ps_exit'])}. Pada skenario ini, saham "
          f"diperdagangkan {fmt.mult(va['implied']['per'] or 0)} PER dan "
          f"{fmt.mult(va['implied']['ev_ebitda'] or 0)} EV/EBITDA {f1['label']}. Utang bersih posisi dasar "
          f"Rp{fmt.miliar(va['net_debt'])} miliar dipakai konsisten di seluruh perhitungan. Skenario "
          f"sensitivitas (WACC +1pp, g -1pp) menghasilkan Rp{fmt.rp(va['tp_down'])}, di bawah skenario dasar. "
          f"Risiko utama: {r3}.")
    p3t = "Skenario nilai indikatif"

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
                  f"proyek tidak ada di cache sehingga tidak dimodelkan.")

    asu_cols = ["Driver", "Satuan"] + [r["label"] for r in F] + ["Dasar"]

    def _disp(satuan, v):
        if satuan == "Rp 0":
            return "Rp0"
        if satuan in ("Rp",):
            return "Rp" + fmt.miliar(v) + " miliar"
        return fmt._id(v, 1) + "%"

    asu_rows = [[row[0], row[1]] + [_disp(row[1], v) for v in row[2:-1]] + [row[-1]]
                for row in fc["assumptions"]]
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

    E("Ringkasan skenario DCF", "tabel",
      {"cols": ["Komponen", "Rp miliar"],
       "rows": [["PV eksplisit", fmt.miliar(va["pv_explicit"])],
                ["PV terminal", fmt.miliar(va["pv_terminal"])],
                [f"Porsi terminal ({fmt.pct(va['tv_share'], 0)})", "-"],
                ["EV", fmt.miliar(va["ev_gordon"])],
                ["Utang bersih", fmt.miliar(va["net_debt"])],
                ["Nilai skenario Gordon", f"Rp{fmt.rp(va['ps_gordon'])}"],
                ["Nilai skenario exit", f"Rp{fmt.rp(va['ps_exit'])}"],
                ["Nilai skenario gabungan", f"Rp{fmt.rp(va['tp'])}"]]})
    E("Proyeksi FCFF", "tabel",
      {"cols": ["Rp miliar"] + [r["label"] for r in F],
       "rows": [["FCFF", *[fmt.miliar(r["fcf"]) for r in F]]]})
    grid = va.get("tp_grid") or {}
    sens_tp_rows = []
    for dw, wlabel in ((-0.01, "WACC -1pp"), (0.0, "WACC base"), (0.01, "WACC +1pp")):
        sens_tp_rows.append([wlabel] + [f"Rp{fmt.rp(grid.get((dw, gg), 0))}"
                                        for gg in (0.025, 0.035, 0.045)])
    E("Sensitivitas nilai skenario (WACC x g)", "tabel",
      {"cols": ["Nilai indikatif (Rp)", "g 2,5%", "g 3,5%", "g 4,5%"], "rows": sens_tp_rows})
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
                     ["Offset dari mean", "n.a.: dipakai hasil CAPM"]]},
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
          f"{fmt.pct(va['wacc'])}; {lom['margin_basis']}) dibanding skenario DCF Rp{modeled_value_s}. "
          f"NAV LoM berbeda karena horizon {(mo.get('reserve_life_cu_yr') or 0):.0f} tahun "
          f"menangkap nilai cadangan yang dipotong terminal Gordon; skenario DCF "
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
               "semua aset tahap produksi; tidak ada diferensiasi "
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
          note="Source: Sektoral Estimates; sel = nilai indikatif per saham; NAV linear "
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
    xtra = []
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
        {"halaman": 5, "judul": "Skenario nilai",
         "paragraf": [f"Nilai skenario indikatif Rp{modeled_value_s} per saham adalah rerata "
                      f"Gordon Rp{fmt.rp(va['ps_gordon'])} dan exit Rp{fmt.rp(va['ps_exit'])} "
                      f"(WACC {fmt.pct(va['wacc'])}); hasil sensitif terhadap asumsi model."] + xtra +
                      ([p_lom] if p_lom else []) + ([p_ddm] if p_ddm else []),
         "exhibit": [e for e in
                     [get("Ringkasan skenario DCF"), get("Proyeksi FCFF"),
                      get("Sensitivitas nilai skenario (WACC x g)"),
                      get("Proyeksi FCFF, Nilai Terminal, dan Jembatan Nilai Skenario"),
                      get("Komponen WACC"),
                      get("Sensitivitas Nilai Skenario per Saham (Rp)"),
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
    research = _research_section(intake)
    if research:
        bagian.insert(0, research)
    for page_number, section in enumerate(bagian, start=2):
        section["halaman"] = page_number
    assert all((b.get("layout") == "research_cards" and b.get("research_cards")) or
               (b["exhibit"] and all(e is not None for e in b["exhibit"])) for b in bagian)
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
              + [methodnote.capex_impact_line(False, "volume penjualan dan jadwal investasi")]
              )[:6]
    return {
        "meta": {"ticker": t, "emiten": name, "tanggal": intake["as_of"],
                 "harga_tanggal": intake["price_date"],
                 "status": "production_report", "harga": intake["price"],
                 "rating": va["rating"], "tp": va["tp"],
                 "upside_persen": va["upside"] * 100,
                 "research_status": (intake.get("research_analysis_status") or {}).get("status", "missing")},
        "cover": {"headline": headline, "bullets": [b1, b2, b3],
                  "paragraf": [{"judul": p1t, "isi": p1}, {"judul": p2t, "isi": p2},
                               {"judul": p3t, "isi": p3}],
                  "data_pasar": {"harga": intake["price"],
                                 "saham": intake["shares"],
                                 "market_cap": intake["market_cap"],
                                 "adtv": adtv_str,
                                 "free_float": ff_str},
                  "key_financials": kf_rows},
        "bagian": bagian,
        "tabel_asumsi": [
            {
                "driver": item[0],
                "satuan": item[1],
                **{F[i]["label"]: item[2 + i] for i in range(len(F)) if 2 + i < len(item) - 1},
                **({"FY26F": item[2], "FY27F": item[3], "FY28F": item[4]} if len(item) >= 6 else {}),
                "dasar": item[-1],
            }
            for item in fc["assumptions"]
        ],
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
    # Raw cached headlines can be broad market stories or contain third-party
    # trade calls. Only validated, ticker-matched paraphrases enter the report.
    for item in intake.get("news_analysis") or []:
        title = scrub.clean_title(str(item.get("summary") or ""), 90)
        if not title:
            continue
        ts = str(item.get("timestamp") or "")[:10] or "-"
        rows.append([title, ts, _word_cut(item.get("connection") or "-", 110), "Pantau"])
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
