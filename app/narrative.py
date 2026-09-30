"""TAHAP 4: NARASI & LAYOUT. Prosa templat deterministik dari angka model."""
import re
import json
import copy
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from . import cache as cache_mod
from . import consensus
from . import ddm
from . import fmt
from . import share_basis
from . import method_chain
from . import exhibit_ids
from . import methodnote
from . import rnav
from .prose_lang import t as _t
from . import prose_lang
from . import scrub
from . import valtables
from . import scenario_value
from . import valuation as valuation_mod

MAX_PARA = 150


def _market_rail(intake):
    """Build dated ADTV and public-ownership context from available local data."""
    ticker = str(intake.get("ticker") or "").upper()
    price_date = str(intake.get("price_date") or intake.get("as_of") or "")[:10]
    points = {}
    for _, payload in cache_mod.payloads(f"/daily/{ticker}/"):
        for row in (payload.get("data") or []):
            day = str(row.get("date") or "")[:10]
            if (day and (not price_date or day <= price_date) and
                    row.get("close") is not None and row.get("volume") is not None):
                points[day] = float(row["close"]) * float(row["volume"])
    # A sourced daily sidecar can be newer than the API cache. Overlay it by
    # date so the report uses the latest observation available at its cutoff.
    source = "sectors_cache"
    sidecar = Path(__file__).resolve().parent.parent / "data" / "market_history" / f"{ticker}.json"
    try:
        with sidecar.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        payload = None
    if isinstance(payload, dict):
        for row in (payload.get("observations") or []):
            day = str(row.get("date") or "")[:10]
            if (day and (not price_date or day <= price_date) and
                    row.get("close") is not None and row.get("volume") is not None):
                points[day] = float(row["close"]) * float(row["volume"])
                source = str(payload.get("source_title") or "sourced market history sidecar")
    adtv, adtv_end, adtv_count = None, None, 0
    if points:
        adtv_end = max(points)
        start = (date.fromisoformat(adtv_end) - timedelta(days=90)).isoformat()
        vals = [value for day, value in points.items() if start <= day <= adtv_end]
        if vals:
            adtv, adtv_count = sum(vals) / len(vals), len(vals)
    holders = intake.get("major_holders") or []
    public = next((h for h in holders
                   if str(h.get("name") or "").strip().lower() in ("public", "masyarakat")), None)
    public_ownership = None
    if public and public.get("share_percentage") is not None:
        try:
            public_ownership = float(public["share_percentage"])
            if public_ownership > 1:
                public_ownership /= 100
        except (TypeError, ValueError):
            pass
    return {"adtv": adtv, "adtv_end": adtv_end, "adtv_count": adtv_count,
            "adtv_source": source if adtv is not None else None,
            "public_ownership": public_ownership}


def _product_key(name):
    text = str(name or "").lower()
    if "konsentrat" in text or "concentrate" in text:
        return "concentrate"
    if "katoda" in text and "tembaga" in text:
        return "cathode_copper"
    if "emas murni" in text:
        return "refined_gold"
    if "emas" in text:
        return "gold"
    if "tembaga" in text or "copper" in text:
        return "copper"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _mining_sales_bridge(intake, scenario):
    """Return an explicit, assumption-led product sales/revenue reconciliation."""
    evidence = intake.get("official_evidence") or {}
    actual = evidence.get("latest_actual") or {}
    q2 = (evidence.get("quarterly_actuals") or {}).get("q2_2026_derived") or {}
    sales = evidence.get("sales_production_bridge") or []
    revenues = (evidence.get("revenue_breakdown") or {}).get("segments") or []
    guidance = evidence.get("management_guidance") or []
    analyst = intake.get("analyst_scenario") or {}
    top_down_projection = analyst.get("top_down_projection") or {}
    if not scenario and top_down_projection.get("h2_revenue_usd") is not None:
        scenario = {"h2": {"revenue": top_down_projection["h2_revenue_usd"]}}
    sales_assumptions = {row.get("product_key"): row for row in
                         (analyst.get("product_sales") or [])}
    q2_by_key = {row.get("product_key"): row for row in
                 (q2.get("sales_production_bridge") or [])}
    market_refs = {row.get("product_key"): row for row in
                   (analyst.get("market_references") or [])}
    if not actual or not sales or not revenues or not scenario:
        return None

    by_key = {_product_key(row.get("name")): row for row in revenues}
    details = []
    for product in sales:
        key = _product_key(product.get("product"))
        revenue_row = by_key.get(key)
        if not revenue_row:
            continue
        h1_sold = product.get("sales")
        h1_production = product.get("production")
        h1_revenue = revenue_row.get("current")
        if not all(isinstance(x, (int, float)) and x > 0 for x in
                   (h1_sold, h1_production, h1_revenue)):
            continue
        unit_value = h1_revenue / h1_sold
        h2_price_basis = "H1 net realized price; carried forward as analyst assumption"
        price_components = []
        metal_prices = product.get("net_realized_prices") or {}
        metal_sales = product.get("metal_sales") or {}
        if key == "concentrate" and metal_prices and metal_sales:
            cu_sold_lbs = float(metal_sales.get("copper_mlbs") or 0) * 1e6
            au_sold_oz = float(metal_sales.get("gold_oz") or 0)
            cu_price = float(metal_prices.get("copper_usd_per_lb") or 0)
            au_price = float(metal_prices.get("gold_usd_per_oz") or 0)
            modeled_revenue = cu_sold_lbs * cu_price + au_sold_oz * au_price
            if all(value > 0 for value in (cu_sold_lbs, au_sold_oz, cu_price, au_price)):
                unit_value = modeled_revenue / h1_sold
                price_components = [
                    {"product": "Tembaga dalam konsentrat", "h1_sold": cu_sold_lbs,
                     "unit": "lb", "h1_price": cu_price},
                    {"product": "Emas dalam konsentrat", "h1_sold": au_sold_oz,
                     "unit": "oz", "h1_price": au_price},
                ]
        elif isinstance(product.get("net_realized_price"), dict):
            unit_value = float(product["net_realized_price"].get("value") or unit_value)
            q2_price = (q2_by_key.get(key) or {}).get("implied_net_realized_price")
            if isinstance(q2_price, dict) and isinstance(q2_price.get("value"), (int, float)):
                unit_value = float(q2_price["value"])
                h2_price_basis = "Q2 implied net realized price; analyst carry-forward assumption"
        h2_sales = None
        basis = ""
        h2_production = None
        def guidance_unit_matches(candidate):
            name = str(candidate.get("name") or "").lower()
            unit = str(product.get("unit") or "").lower()
            return ((unit == "ton" and "(kt)" in name) or
                    (unit == "oz" and "(koz)" in name) or
                    (unit == "dmt" and "(dmt)" in name) or
                    (unit not in ("ton", "oz", "dmt") and
                     _product_key(candidate.get("name")) == key))
        guide = next((g for g in guidance
                      if _product_key(g.get("name")) == key and
                      guidance_unit_matches(g)), None)
        if guide:
            guide_value = float(guide["value"])
            guide_name = str(guide.get("name") or "").lower()
            if "kt" in guide_name:
                guide_value *= 1000
            elif "koz" in guide_name:
                guide_value *= 1000
            h2_production = max(0.0, guide_value - h1_production)
            basis = "sisa guidance produksi FY; volume penjualan diproyeksikan terpisah"
        if key in sales_assumptions:
            assumption = sales_assumptions[key]
            factor = assumption.get("h2_sales_to_h1")
            if isinstance(factor, (int, float)) and factor >= 0:
                h2_sales = h1_sold * factor
                basis = str(assumption.get("basis") or "asumsi analis")
        elif h2_production is not None:
            q2_product = q2_by_key.get(key) or {}
            q2_production, q2_sold = q2_product.get("production"), q2_product.get("sales")
            sellthrough = (q2_sold / q2_production
                           if isinstance(q2_sold, (int, float)) and q2_production else
                           h1_sold / h1_production)
            h2_sales = h2_production * sellthrough
            basis = ("sisa guidance produksi FY × rasio penjualan/produksi Q2; Q2 diturunkan dari H1−Q1 (asumsi analis)"
                     if q2_product else
                     "sisa guidance produksi FY × rasio penjualan/produksi H1 (asumsi analis)")
        if h2_sales is None:
            continue
        for component in price_components:
            component["h2_sold"] = component["h1_sold"] * h2_sales / h1_sold
            component["h2_revenue"] = component["h2_sold"] * component["h1_price"]
        details.append({"key": key, "label": product["product"],
                        "unit": product.get("unit") or "unit",
                        "h1_sold": h1_sold, "h1_production": h1_production,
                        "h1_revenue": h1_revenue, "unit_value": unit_value,
                        "h2_production": h2_production, "h2_sales": h2_sales,
                        "h2_revenue": (sum(c["h2_revenue"] for c in price_components)
                                       if price_components else h2_sales * unit_value),
                        "price_components": price_components, "basis": basis,
                        "h2_price_basis": h2_price_basis,
                        "net_realized_price": product.get("net_realized_price"),
                        "market_ref": market_refs.get(
                            "copper" if key == "cathode_copper" else
                            "gold" if key == "refined_gold" else key)})
    if not details:
        return None
    product_order = {_product_key(row.get("name")): index
                     for index, row in enumerate(revenues)}
    details.sort(key=lambda row: product_order.get(row["key"], 1e9))
    h2_topdown = (scenario.get("h2") or {}).get("revenue")
    base_sum = sum(row["h2_revenue"] for row in details)
    residual = h2_topdown - base_sum if isinstance(h2_topdown, (int, float)) else None
    gold = next((row for row in details if row["key"] == "refined_gold"), None)
    gold_required = (gold["h2_sales"] + residual / gold["unit_value"]
                     if gold and residual is not None else None)
    return {"rows": details, "h2_topdown": h2_topdown, "base_sum": base_sum,
            "residual": residual, "gold_required": gold_required,
            "gold_required_sellthrough": (
                gold_required / gold["h2_production"]
                if gold and gold_required is not None and gold["h2_production"] else None)}


def _volume_text(value, unit):
    if value is None:
        return "-"
    if unit == "ton":
        return f"{fmt._id(value / 1000, 1)} kt"
    if unit == "oz":
        return f"{fmt._id(value / 1000, 1)} koz"
    if unit == "dmt":
        return f"{fmt._id(value / 1000, 1)} kdmt"
    return f"{fmt._id(value, 1)} {unit}"


def _market_price_unit(unit):
    text = str(unit or "").lower()
    if "tonne" in text or text.endswith("/ton"):
        return "ton"
    if text.endswith("/oz"):
        return "oz"
    return str(unit or "unit")


def _replace_interest_causality(text, net_margin_pct):
    safe = _t(f"Net margin H2 {fmt.pct(net_margin_pct / 100)} adalah asumsi analis; "
              "pajak dan jadwal bunga belum dijembatani.",
              f"H2 net margin of {fmt.pct(net_margin_pct / 100)} is an analyst assumption; "
              "tax and the interest schedule are not yet bridged.")
    sentences = re.split(r"(?<=[.!?])\s+", str(text or ""))
    out = []
    replaced = False
    for sentence in sentences:
        lower = sentence.lower()
        if ("net margin" in lower and _t("bunga", "interest") in lower and
                ("flat" in lower or _t("karena", "because") in lower)):
            out.append(safe)
            replaced = True
        else:
            out.append(sentence)
    return " ".join(out), replaced


def _trim(s, cap=30):
    w = s.split()
    return " ".join(w[:cap]) if len(w) > cap else s


def _bullet(s, cap=30):
    """One complete sentence of at most ``cap`` words (spec §5.2 bullets).

    Takes the first sentence; if it is still too long, ends at the last
    clause break (comma/semicolon) inside the limit instead of mid-phrase.
    """
    first = re.split(r"(?<=[.!?])\s+", s.strip(), maxsplit=1)[0].rstrip(" .")
    words = first.split()
    if len(words) <= cap:
        return first + "."
    head = " ".join(words[:cap])
    cut = max(head.rfind(","), head.rfind(";"))
    if cut >= len(head) // 2:
        head = head[:cut]
    return head.rstrip(" ,;") + "."


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
        title = _word_cut(str(article.get("title") or "Berita Sectors"), 90)
        timestamp = str(article.get("timestamp") or "")[:10]
        source = str(article.get("source") or "")
        domain = urlsplit(source).netloc if source else ""
        date_source = "; ".join(value for value in (timestamp, domain) if value)
        suffix = f" ({date_source})" if date_source else ""
        refs.append(f"/news/ · /results/{index} · {title}{suffix}")
    return refs


def _draft_value(value):
    return "-" if value is None else fmt.miliar(value)


def _method_chain_text(va):
    """Satu kalimat rantai metode (§4.1a) untuk tabel pemeriksaan draft."""
    chain = va.get("method_chain") or {}
    trace = chain.get("trace") or []
    if not trace:
        return None
    parts = [f"{t['short']} dilewati ({method_chain.reader_reason(t['reasons'][0])})"
             for t in trace if t["decision"] == "skipped"]
    sel = next((t for t in trace if t["decision"] in ("selected", "stop_extreme")), None)
    if sel:
        parts.append(f"dasar nilai {sel['short']}" +
                     (" tetapi hasilnya ekstrem sehingga rantai berhenti"
                      if sel["decision"] == "stop_extreme" else ""))
    else:
        parts.append("belum ada metode yang memadai")
    return "; ".join(parts) + "."


def _chain_cover_label(va, default):
    """Label cover draft: metode fallback terpilih bila metode utama dilewati."""
    chain = va.get("method_chain") or {}
    if chain.get("route") != "fallback":
        return default
    trace = {t["key"]: t for t in chain["trace"]}
    return (f"{trace[chain['selected']]['short']} (fallback dari "
            f"{chain['trace'][0]['short']}; belum lengkap)")


def _method_label(method):
    """Reader label for an analyst-selected method key (legacy or chain key)."""
    legacy = {"ddm": "DDM (dividen, Rp)", "dcf": "DCF (FCFF, Rp)", "rnav": "RNAV LoM (Rp)"}
    return legacy.get(method) or method_chain.LABELS.get(method) or method


def _NM_CHANGE_NOTE(rows):
    """The reason for n.m. in a yoy column: a change across zero. A change
    above 500% prints as '>500%' and needs no note."""
    if not any("n.m." in [str(c) for c in row[1:]] for row in rows):
        return ""
    return (" n.m. pada kolom yoy: perubahan dari/ke angka negatif tidak bermakna "
            "sebagai persentase.")


def _build_general_draft(intake, fc, va, s1, method="auto",
                         illustrative_scenarios=False):
    """Company-update shaped evidence brief while the production model is gated."""
    ticker = intake["ticker"]
    mining = intake.get("model_profile") == "finite_life_mining"
    evidence = intake.get("official_evidence") or {}
    market_rail = _market_rail(intake)
    actual = evidence.get("latest_actual") or {}
    annuals = evidence.get("annual_actuals") or []
    balance = evidence.get("balance_sheet") or {}
    # The report's valuation denominator: the reviewed share ledger, else the
    # official outstanding count (issued shares can include treasury stock).
    shares_outstanding, shares_basis_text = share_basis.report_date_shares(intake)
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
    pct_change = lambda now, prior: (">500%" if now is not None and prior is not None and
                                     prior > 0 and now >= 0 and now / prior - 1 > 5 else
                                     fmt.pct(now / prior - 1)
                                     if now is not None and prior is not None and
                                     prior > 0 and now >= 0 else "n.m." if
                                     now is not None and prior is not None and
                                     (prior < 0 or now < 0) else "-")
    exhibits = []
    inventory_sales_section = None
    physical_sales_section = None
    royalty_section = None
    capex_section = None

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
        # Spec §2: forecast tanpa input bersumber tampil belum dimodelkan (NA), bukan angka
        # screening. "NA" fits the narrow Figma cover columns; the note spells it out.
        f_dashes = ["NA"] * len(f_labels)
        total_cols_dash = ["-"] * (len(history) + len(f_labels))
        # Net profit is the parent's share, the EPS basis, so Key Financials ties
        # out with the income statement and the combo chart.
        attributable_key = ("net_profit_attributable" if all(
            row.get("net_profit_attributable") is not None for row in history) else "net_profit")
        key_rows = [
            [f"Pendapatan ({unit})"] + values("revenue") + f_dashes,
            ["Pertumbuhan pendapatan (%)"] + growth("revenue") + f_dashes,
            [f"EBITDA ({unit})"] + values("ebitda") + f_dashes,
            ["Pertumbuhan EBITDA (%)"] + growth("ebitda") + f_dashes,
            [f"Laba bersih ({unit})"] + values(attributable_key) + f_dashes,
            ["Pertumbuhan laba bersih (%)"] + growth(attributable_key) + f_dashes,
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
        annual_title = (evidence.get("annual_source_title")
                        or (evidence.get("annual_actuals_source") or {}).get("title")
                        or actual.get("source_title"))
        key_note = (f"Sumber: {annual_title}; "
                    f"angka {history[0]['year']}-{history[-1]['year']} ditampilkan dalam {unit}. "
                    "EPS/BVPS historis memakai laba/ekuitas pemilik induk dan jumlah "
                    f"saham per {balance.get('period_end', 'periode interim')}"
                    + (f" ({_shares_source(evidence)})" if _shares_source(evidence) else "")
                    + " sebagai basis pro forma; "
                    f"{f_labels[0]}-{f_labels[-1]} belum diterbitkan (NA: belum dimodelkan).")
    else:
        cached = intake.get("annuals") or []
        history = cached[-2:]
        F = fc.get("rows") or []
        f_labels = [r["label"] for r in F] if F else [
            f"FY{(int(history[-1]['year']) + 1 + i) % 100:02d}F" for i in range(5)]
        f_dashes = ["NA"] * len(f_labels)
        # Sectors history is in rupiah whatever the issuer reports in, so this
        # table is in Rp miliar; USD scenario columns are converted when filled.
        rp_money = lambda value: ("-" if value is None else
                                  f"({fmt._id(abs(value) / 1e9, 1)})" if value < 0 else
                                  fmt._id(value / 1e9, 1))
        key_rows = [["Pendapatan (Rp miliar)"] +
                    [rp_money(row.get("revenue")) for row in history] + f_dashes,
                    # Sectors reports an unfiled EBITDA as 0; show it as missing.
                    ["EBITDA (Rp miliar)"] +
                    [rp_money(row.get("ebitda") or None) for row in history] + f_dashes,
                    ["Laba bersih (Rp miliar)"] +
                    [rp_money(row.get("earnings")) for row in history] + f_dashes]
        key_note = ("Sumber: Sectors, company/report. Kolom forecast dan "
                    "multiple belum tersedia karena model belum lolos validasi "
                    "(NA: belum dimodelkan).")
    years = [str(row["year"]) for row in history]
    exhibit_ids.tag(add("Key Financials", ["Tahun buku 31 Des"] + years +
                        f_labels, key_rows, key_note), exhibit_ids.KEY_FINANCIALS)

    actual_rows = []
    if actual:
        previous = actual.get("prior_year") or {}
        # EBITDA means nothing for a bank (spec §5.4): no EBITDA line or ratio.
        bank = intake.get("model_profile") == "financial_ddm"
        for label, key in (("Pendapatan", "revenue"),) + ((("EBITDA", "ebitda"),) if not bank else ()) + (
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
            f"{actual['source_url']}" + _NM_CHANGE_NOTE(actual_rows))
        metrics = actual["metrics"]
        prior_metrics = actual.get("prior_year") or {}
        gaps = {}

        def ratio(label, numerator, denominator, period):
            """A ratio of official figures; n.m. with the missing input named."""
            if numerator is not None and denominator and denominator > 0:
                return fmt.pct(numerator / denominator)
            gaps.setdefault(label, []).append(period)
            return "n.m."

        def pair(label, top, bottom):
            prior_period = previous.get("period", "periode lalu")
            return [label, ratio(label, prior_metrics.get(top), prior_metrics.get(bottom), prior_period),
                    ratio(label, metrics.get(top), metrics.get(bottom), actual["period"])]

        diagnostic_rows = ([] if bank else [pair("Margin EBITDA", "ebitda", "revenue")]) + [
            pair("Margin laba bersih", "net_profit", "revenue")]
        if metrics.get("capital_expenditure") is not None:
            diagnostic_rows.append(pair("Belanja modal / pendapatan", "capital_expenditure", "revenue"))
        if metrics.get("operating_cash_flow") is not None and not bank:
            diagnostic_rows.append(pair("Arus kas operasi / EBITDA", "operating_cash_flow", "ebitda"))
        add("Rasio yang menjelaskan kualitas hasil",
            ["Rasio", previous.get("period", "Periode lalu"), actual["period"]],
            diagnostic_rows,
            f"Sumber: {actual['source_title']}, {page_reference}; "
            "rasio dihitung dari angka resmi; nilai negatif ditampilkan dalam kurung."
            + ("" if not gaps else " n.m.: " + "; ".join(
                f"{label} {', '.join(periods)} (rilis resmi tidak memuat "
                f"{'EBITDA' if 'EBITDA' in label else 'salah satu angka'} periode itu)"
                for label, periods in gaps.items()) + "."))
    else:
        quarter = intake.get("latest_quarterly_actual") or {}
        if quarter:
            add("Baris kuartalan dalam data lokal",
                ["Metrik", str(quarter.get("date") or "-")],
                [[label, money(quarter.get(key))] for label, key in
                 (("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                  ("Laba bersih", "earnings"))],
                f"Sumber: Sectors, financials/quarterly/{ticker}; "
                "cakupan kumulatif dan tanggal publikasi belum terverifikasi.")

    revenue_breakdown = evidence.get("revenue_breakdown") or {}
    if revenue_breakdown and actual:
        items = [(f"{heading}: {row['name']}", row)
                 for group, heading in (("segments", "Segmen"),
                                        ("major_customers", "Pelanggan utama"))
                 for row in revenue_breakdown.get(group) or []]
        # A release that splits only the current period gets a one-period table,
        # not a column of blanks for the prior period and yoy.
        with_prior = any(row.get("prior") is not None for _, row in items)
        prior_period = (actual.get("prior_year") or {}).get("period", "Periode lalu")
        breakdown_rows = [
            [label, money(row.get("prior")) if row.get("prior") is not None else "n.m.",
             money(row.get("current")),
             pct_change(row.get("current"), row.get("prior"))
             if row.get("prior") is not None else "n.m."] if with_prior else
            [label, money(row.get("current"))]
            for label, row in items]
        add(f"Komposisi pendapatan {actual['period']}" if mining else
            "Jembatan pendapatan menurut layanan dan pelanggan",
            (["Uraian", prior_period, actual["period"], "yoy"] if with_prior
             else ["Uraian", actual["period"]]), breakdown_rows,
            f"Sumber: {actual['source_title']}, hlm. "
            f"{revenue_breakdown['source_page']}. " +
             ("Angka merupakan penjualan produk, bukan forecast tahunan."
             if mining else "Segmen dan pelanggan adalah dua pemotongan pendapatan "
             "yang berbeda; jangan dijumlahkan bersama.")
            + (f" Rilis tidak merinci {prior_period} untuk sebagian baris, sehingga "
               "angka periode lalu dan yoy baris itu n.m." if with_prior and any(
                   row.get("prior") is None for _, row in items) else "")
            + ("" if with_prior else f" Rilis tidak merinci komposisi {prior_period}."))

    inventory_sales = evidence.get("inventory_and_sales_detail") or {}
    if mining and inventory_sales:
        inventory_rows = [
            [row["name"], fmt._id(row["dec_2025"] / 1000, 1),
             fmt._id(row["jun_2026"] / 1000, 1)]
            for row in inventory_sales.get("inventory_and_stockpile_carrying_amounts") or []
        ]
        add("Nilai tercatat persediaan dan stockpiles",
            ["Pos (US$m)", "31 Des 2025", "30 Jun 2026"], inventory_rows,
            f"Sumber: {inventory_sales['source_title']}, hlm. "
            f"{inventory_sales['inventory_source_page']}; {inventory_sales['source_url']}. "
            "Ini nilai tercatat berbasis biaya, bukan jumlah fisik konsentrat siap jual. "
            "Laporan tidak memuat roll-forward tonase persediaan konsentrat, umpan smelter, "
            "atau produk yang menunggu penjualan. Manajemen menyatakan stockpiles dapat dipakai/dijual "
            "dan nilai realisasi netonya melebihi nilai tercatat.")

        sales_market_rows = [
            [row["product"], fmt._id(row["domestic"] / 1000, 1),
             fmt._id(row["export"] / 1000, 1), fmt._id(row["total"] / 1000, 1)]
            for row in inventory_sales.get("net_sales_by_product_and_market") or []
        ]
        add("Penjualan H1 menurut produk dan pasar",
            ["Produk (US$m)", "Domestik", "Ekspor", "Total"], sales_market_rows,
            f"Sumber: {inventory_sales['source_title']}, hlm. "
            f"{inventory_sales['sales_source_page']}; {inventory_sales['source_url']}. "
            "Angka laporan keuangan dalam US$ ribu. Penjualan historis menurut pasar tidak "
            "menetapkan volume, harga, atau kanal penjualan H2; volume dan harga forward kontrak "
            "tetap belum diungkap.")
        inventory_sales_section = {
            "halaman": 0,
            "judul": "Persediaan, penjualan, dan batas rekonsiliasi",
            "layout": "stack",
            "paragraf": [
                _t("Penjualan H1 dapat ditautkan ke produk dan pasar, dan laporan memberi nilai tercatat persediaan konsentrat serta WIP smelter. Namun, nilai tersebut memakai basis biaya dan tidak menyediakan tonase fisik atau kandungan logam per tahap. Karena itu, selisih 227.228 dmt antara produksi dan penjualan konsentrat H1 belum dapat dijelaskan sebagai umpan smelter, perubahan stockpile konsentrat, atau produk yang menunggu penjualan.",
                   "H1 sales can be traced to product and market, and the report gives the carrying value of concentrate inventory and smelter WIP. Those values are on a cost basis, however, and give no physical tonnage or metal content by stage. The 227.228 dmt gap between H1 concentrate production and sales therefore cannot yet be explained as smelter feed, a change in the concentrate stockpile, or product awaiting sale.")
            ],
            "exhibit": [
                next(e for e in exhibits if e["judul"] == "Nilai tercatat persediaan dan stockpiles"),
                next(e for e in exhibits if e["judul"] == "Penjualan H1 menurut produk dan pasar"),
            ],
        }
        physical_rows = []
        for row in evidence.get("sales_production_bridge") or []:
            product = str(row.get("product") or "")
            if product == "Konsentrat":
                physical_rows.append([
                    "Konsentrat",
                    f"{fmt._id(row['production'], 0)} dmt",
                    f"{fmt._id(row['sales'], 0)} dmt",
                    f"{fmt._id(row['production'] - row['sales'], 0)} dmt",
                ])
                metal_production = row.get("metal_production") or {}
                metal_sales = row.get("metal_sales") or {}
                for key, label, unit in (
                        ("copper_mlbs", "Tembaga terkandung dalam konsentrat", "Mlb"),
                        ("gold_oz", "Emas terkandung dalam konsentrat", "oz")):
                    produced, sold = metal_production.get(key), metal_sales.get(key)
                    if isinstance(produced, (int, float)) and isinstance(sold, (int, float)):
                        physical_rows.append([
                            label, f"{fmt._id(produced, 0)} {unit}",
                            f"{fmt._id(sold, 0)} {unit}",
                            f"{fmt._id(produced - sold, 0)} {unit}",
                        ])
            elif product in ("Katoda tembaga", "Emas murni"):
                produced, sold = row.get("production"), row.get("sales")
                if isinstance(produced, (int, float)) and isinstance(sold, (int, float)):
                    unit = str(row.get("unit") or "unit")
                    physical_rows.append([
                        product, f"{fmt._id(produced, 0)} {unit}",
                        f"{fmt._id(sold, 0)} {unit}",
                        f"{fmt._id(produced - sold, 0)} {unit}",
                    ])
        if physical_rows:
            physical_exhibit = add(
                "Delta produksi dan penjualan produk H1",
                ["Produk/tahap", "Produksi H1", "Penjualan H1", "Produksi dikurangi penjualan"],
                physical_rows,
                f"Sumber: {actual['source_title']}, hlm. 3; {actual['source_url']}. "
                "Delta adalah selisih arus produksi dan penjualan yang dilaporkan, bukan perubahan persediaan. "
                "Konsentrat, kandungan logam konsentrat, katoda, dan emas murni berada pada tahap berbeda; "
                "angka tidak boleh dijumlahkan lintas tahap atau diperlakukan sebagai payable metal/inventory.")
            physical_sales_section = {
                "halaman": 0,
                "judul": "Produksi dan penjualan aktual H1 menurut tahap",
                "layout": "stack",
                "paragraf": [
                    _t("Laporan memberi volume produksi dan penjualan pada beberapa tahap rantai produk. Selisih antarangka menunjukkan pekerjaan rekonsiliasi yang dibutuhkan, tetapi tidak mengungkap sendiri tonase yang masuk smelter, recovery, payable metal, stok awal/akhir, atau waktu pengapalan dan pengakuan pendapatan.",
                       "The report gives production and sales volumes at several stages of the product chain. The gaps between them show the reconciliation work required, but do not by themselves reveal the tonnage fed to the smelter, recovery, payable metal, opening/closing stock, or the timing of shipment and revenue recognition.")
                ],
                "exhibit": [physical_exhibit],
            }

    royalty = evidence.get("royalty_and_export_duty") or {}
    if mining and royalty:
        rates = royalty.get("rates_pct_of_reference_price") or {}
        def rate_range(rows):
            values = []
            for row in rows:
                if row.get("below") is not None:
                    band = f"<{fmt._id(row['below'], 0)}"
                elif row.get("from_inclusive") is not None and row.get("to_exclusive") is not None:
                    band = (f"{fmt._id(row['from_inclusive'], 0)}–"
                            f"<{fmt._id(row['to_exclusive'], 0)}")
                elif row.get("from_inclusive") is not None:
                    band = f"≥{fmt._id(row['from_inclusive'], 0)}"
                else:
                    band = "-"
                values.append(f"{band}: {fmt.pct(row['rate_pct'] / 100)}")
            return "; ".join(values)
        royalty_rows = [
            ["HMA resmi H1 2026: tembaga (12 periode, US$/dmt)",
             "11.790,32–13.648,27; seluruh periode masuk tier tertinggi"],
            ["HMA resmi H1 2026: emas (12 periode, US$/oz)",
             "4.302,37–5.135,76; seluruh periode masuk tier tertinggi"],
            ["Tier terpilih: konsentrat Cu / katoda Cu",
             "10% / 7% dari harga referensi"],
            ["Tier terpilih: Au ikutan konsentrat / emas murni",
             "16% / 16% dari harga referensi"],
            ["Tembaga dalam konsentrat (HMA US$/t)",
             rate_range(rates.get("copper_in_concentrate_by_hma_usd_per_tonne") or [])],
            ["Emas ikutan dalam konsentrat (HMA US$/oz)",
             rate_range(rates.get("gold_byproduct_in_copper_concentrate_by_hma_usd_per_oz") or [])],
            ["Katoda tembaga (HMA US$/t)",
             rate_range(rates.get("copper_cathode_by_hma_usd_per_tonne") or [])],
            ["Emas murni, logam primer (HMA US$/oz)",
             rate_range(rates.get("primary_refined_gold_by_hma_usd_per_oz") or [])],
            ["Bea keluar ekspor konsentrat pada periode yang ditegaskan AMMAN",
             f"{fmt.pct(royalty.get('concentrate_export_duty_pct') / 100)}"],
            ["Beban PNBP H1 2026 (US$m)",
             fmt._id(royalty.get("h1_2026_pnbp_expense_usd_thousand") / 1000, 1)],
            ["Kas dibayar: royalti, pajak dan PNBP H1 2026 (US$m)",
             fmt._id(royalty.get("h1_2026_cash_paid_royalties_taxes_pnbp_usd_thousand") / 1000, 1)],
            ["Formula HPM konsentrat tembaga", "Cu/Au/Ag payable × (HMA − TC/RC); Kepmen 144/2026"],
            ["Input kontrak yang belum diungkap untuk netback", "assay/payable, TC/RC, penalti, HMA per shipment, timing volume"],
        ]
        royalty_exhibit = add(
            "Kerangka royalti dan bea keluar; netback belum dapat dihitung",
            ["Jenis produk / aktual", "Tarif atau jumlah"], royalty_rows,
            f"Tarif: {royalty.get('statutory_source_title')}, hlm. "
            f"{', '.join(str(p) for p in royalty.get('regulation_source_pages') or [])}; "
            f"{royalty.get('statutory_source_url')}. PNBP, duty, dan arus kas: "
            f"{royalty.get('company_confirmation_source_title')}, hlm. "
            f"{', '.join(str(p) for p in royalty.get('company_confirmation_source_pages') or [])}; "
            f"{royalty.get('company_confirmation_source_url')}. Tarif royalti bertingkat menggunakan HMA, "
            f"sementara formula HPM konsentrat berubah melalui {((royalty.get('hpm_concentrate_methodology') or {}).get('source_title'))}, "
            f"{((royalty.get('hpm_concentrate_methodology') or {}).get('source_url'))}. Formula itu memerlukan assay Cu/Au/Ag, "
            "payable metal, TC/RC dan periode shipment; HPM legal bukan harga realisasi kontrak AMMN. "
            "Seri HMA resmi dua-mingguan H1 2026 berasal dari 12 lampiran keputusan ESDM (lampiran halaman 5; nomor dan URL per keputusan disimpan di evidence JSON). "
            "Semua 12 periode memilih tier tertinggi; ini menetapkan bracket hukum, bukan tarif efektif per shipment atau netback AMMN. "
            "Net realized H1 hanya dijelaskan net treatment/refining dan MTM. Rilis tidak "
            "mengungkap basis HMA/HPM per shipment, volume dan dasar royalti aktual per produk, atau apakah royalty/export duty sudah tercermin "
            "dalam harga realisasi. Baris arus kas menggabungkan royalti, pajak dan PNBP. Jangan kurangi "
            "tarif legal sekali lagi dari net realized atau forecast sebelum tie-out tersedia.")
        royalty_section = {
            "halaman": 0,
            "judul": "Royalti, bea keluar, dan netback",
            "layout": "stack",
            "paragraf": [
                _t("HMA resmi untuk seluruh 12 periode H1 telah dipetakan dan menentukan tier maksimum PP 19/2025. Namun, HMA bukan harga shipment AMMN: assay/payable, HPM, TC/RC, volume dan dasar royalti per produk serta tie-out terhadap net realized dan kas belum diungkap. Karena itu netback H1/H2 belum tervalidasi dan tarif legal tidak dikurangkan ulang dari realized price.",
                   "Official HMA for all 12 H1 periods has been mapped and sets the top tier of PP 19/2025. HMA is not AMMN's shipment price, however: assay/payable, HPM, TC/RC, volume and royalty base by product, and the tie-out to net realized price and cash are undisclosed. H1/H2 netback is therefore not validated, and statutory rates are not deducted again from the realized price.")
            ],
            "exhibit": [royalty_exhibit],
        }

    capex_reference = evidence.get("historical_capex_reference") or {}
    analyst_projection = (intake.get("analyst_scenario") or {}).get(
        "top_down_projection") or {}
    if mining and capex_reference:
        capex_rows = [
            ["FY2024 aktual emiten", fmt._id(capex_reference["fy2024"], 1), "Dilaporkan"],
            ["FY2025 aktual emiten", fmt._id(capex_reference["fy2025"], 1), "Dilaporkan"],
            ["FY2025: sustaining tambang Phase 8", fmt._id((capex_reference.get("fy2025_by_use_usd_million") or {}).get("phase_8_mining_sustaining"), 1), "Dilaporkan; sudah di atas skenario FY26 total"],
            ["FY2025: smelter tembaga dan PMR", fmt._id((capex_reference.get("fy2025_by_use_usd_million") or {}).get("copper_smelter_and_precious_metal_refinery"), 1), "US$m menurut penggunaan"],
            ["FY2025: ekspansi pabrik pengolahan", fmt._id((capex_reference.get("fy2025_by_use_usd_million") or {}).get("processing_plant_expansion"), 1), "US$m menurut penggunaan"],
            ["FY2025: PLTGU dan fasilitas LNG", fmt._id((capex_reference.get("fy2025_by_use_usd_million") or {}).get("combined_cycle_power_plant_lng_facilities"), 1), "US$m menurut penggunaan"],
            ["1H2025 aktual", fmt._id(capex_reference["h1_2025"], 1), "Pembanding dalam H1 release"],
            ["1H2026 aktual", fmt._id(capex_reference["h1_2026"], 1), "Laporan interim; capex kas + additions"],
        ]
        if analyst_projection.get("fy2026_capex_usd") is not None:
            scenario_capex = analyst_projection["fy2026_capex_usd"] / 1e6
            h2_capex = scenario_capex - capex_reference["h1_2026"]
            capex_rows.extend([
                ["FY2026 skenario analis", fmt._id(scenario_capex, 1), "Asumsi analis; bukan guidance emiten"],
                ["H2 tersirat dari skenario", fmt._id(h2_capex, 1), "FY26 skenario dikurangi H1 aktual"],
            ])
        capex_exhibit = add(
            "Capex historis, aktual H1, dan skenario FY26",
            ["Periode / basis (US$m)", "Belanja modal", "Status"], capex_rows,
            f"FY24/FY25: {capex_reference['source_title']}, hlm. "
            f"{capex_reference['source_page']}; {capex_reference['source_url']}. "
            f"Rincian penggunaan FY25: {(capex_reference.get('fy2025_by_use_usd_million') or {}).get('source_title')}, "
            f"hlm. {(capex_reference.get('fy2025_by_use_usd_million') or {}).get('source_page')}; "
            f"{(capex_reference.get('fy2025_by_use_usd_million') or {}).get('source_url')}. Annual Report membulatkan "
            "total FY25 menjadi US$1.373bn sementara kategori penggunaan yang ditampilkan berjumlah US$1.372bn. "
            f"H1 aktual: {actual['source_title']}, hlm. {actual.get('page')}; "
            f"rekonsiliasi detail: {capex_reference['h1_2026_exact_source_title']}, hlm. "
            f"{', '.join(str(p) for p in capex_reference['h1_2026_exact_source_pages'])}; "
            f"{capex_reference['h1_2026_exact_source_url']}. Tidak ditemukan budget FY26, "
            "jadwal capex per proyek, atau pembayaran kontrak tersisa dalam sumber resmi yang ditelaah. "
            "Actual FY24/FY25 bukan run-rate forward; skenario FY26 tidak menjadi forecast tervalidasi.")
        cip = capex_reference.get("construction_in_progress") or {}
        cip_exhibit = None
        if cip:
            cip_rows = []
            for item in cip.get("current") or []:
                prior = next((row for row in cip.get("prior_by_asset_class") or []
                              if row.get("asset_class") == item.get("asset_class")), {})
                completion = item.get("completion_pct_range") or []
                prior_completion = prior.get("completion_pct_range") or []
                cip_rows.append([
                    item.get("asset_class", "-"),
                    fmt._id(item.get("accumulated_cost"), 1),
                    (f"{fmt._id(completion[0], 1)}–{fmt._id(completion[1], 1)}%"
                     if len(completion) == 2 else "-"),
                    item.get("estimated_completion", "-"),
                    fmt._id(prior.get("accumulated_cost"), 1),
                    (f"{fmt._id(prior_completion[0], 1)}–{fmt._id(prior_completion[1], 1)}%"
                     if len(prior_completion) == 2 else "-"),
                ])
            cip_rows.append([
                "TOTAL konsolidasi",
                fmt._id(cip.get("current_total"), 1), "-", "-",
                fmt._id(cip.get("prior_total"), 1), "-",
            ])
            cip_exhibit = add(
                "Konstruksi dalam pengerjaan: biaya tercatat dan rentang selesai",
                ["Kategori aset", "Akumulasi biaya Jun-26 (US$m)",
                 "% selesai (rentang)", "Estimasi penyelesaian", "Akumulasi biaya Des-25 (US$m)",
                 "% selesai (rentang)"],
                cip_rows,
                f"Sumber: {cip.get('source_title')}, hlm. {cip.get('source_page')}; "
                f"{cip.get('source_url')}. Akumulasi CIP adalah nilai tercatat sampai tanggal laporan, "
                "bukan estimasi biaya tersisa, kewajiban kontrak, atau arus kas capex mendatang. "
                "Saldo konsolidasi tidak dialokasikan per proyek; rentang persentase/jadwal mencakup aset berbeda "
                "dan tidak menunjukkan tanggal penyelesaian per proyek. Perubahan saldo CIP tidak sama dengan capex kas "
                "atau additions karena juga dapat mencakup kapitalisasi, transfer ke aset operasi, dan reklasifikasi.")
        capex_section = {
            "halaman": 0,
            "judul": "Capex historis dan asumsi analis FY26",
            "layout": "stack",
            "paragraf": [
                _t("Skenario capex FY26 US$390 juta menyisakan sekitar US$260 juta untuk H2 setelah aktual H1. Total FY26 skenario itu US$84 juta lebih rendah daripada US$474 juta capex sustaining Phase 8 yang dilaporkan untuk FY25, dan tidak mencakup pembanding proyek-proyek FY25 secara sebanding. Laporan interim menunjukkan CIP konsolidasi US$3.082 juta dengan estimasi selesai yang membentang hingga Q4 2027; angka tersebut adalah biaya terakumulasi, bukan biaya tersisa atau budget FY26. Karena nilai CIP tidak dirinci per proyek dan tidak ada jadwal pembayaran, asumsi capex H2 belum tervalidasi. Belum ada rekonsiliasi capex, modal kerja, bunga, pajak, dan pembayaran utang menjadi FCFF H2.",
                   "The FY26 capex scenario of US$390 juta leaves about US$260 juta for H2 after H1 actuals. That FY26 scenario total is US$84 juta below the US$474 juta of Phase 8 sustaining capex reported for FY25, and it offers no like-for-like comparison with the FY25 projects. The interim report shows consolidated CIP of US$3.082 juta, with estimated completion stretching to Q4 2027; that figure is accumulated cost, not remaining cost or an FY26 budget. As CIP is not broken down by project and there is no payment schedule, the H2 capex assumption is not validated. Capex, working capital, interest, tax and debt repayment are not yet reconciled into H2 FCFF.")
            ],
            "exhibit": [capex_exhibit] + ([cip_exhibit] if cip_exhibit else []),
        }

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
            f"Sumber: {actual['source_title']}, hlm. 3-4. Produksi tidak sama "
            "dengan penjualan; kadar dan throughput perlu dijembatani terpisah."
            + _NM_CHANGE_NOTE([[row["name"], pct_change(row["current"], row.get("prior"))]
                               for row in operating_metrics]))

    guidance = evidence.get("management_guidance") or []
    if guidance and actual:
        guidance_period = evidence.get("guidance_period") or f"FY{actual['period_end'][:4]}"
        operating_by_name = {
            re.sub(r"\s*\([^)]*\)", "", str(row.get("name") or "")).strip().lower(): row
            for row in operating_metrics
        }
        product_production_by_key = {
            _product_key(row.get("product")): row
            for row in (evidence.get("sales_production_bridge") or [])
            if isinstance(row.get("production"), (int, float))
        }
        guidance_rows = []
        has_prior_guidance = any(
            isinstance(row.get("previous_value"), (int, float))
            for row in guidance)
        for row in guidance:
            label = str(row.get("name") or "")
            unit_name = label.lower()
            base = re.sub(r"\s*\([^)]*\)", "", label).strip().lower()
            operating = operating_by_name.get(base)
            product_actual = product_production_by_key.get(_product_key(base))
            if product_actual and not (
                    str(product_actual.get("unit") or "").lower() == "dmt" and
                    "(dmt)" in unit_name):
                product_actual = None
            fy_value = float(row["value"])
            h1_value = (operating.get("current") if operating else
                        product_actual.get("production") if product_actual else None)
            implied_h2 = None
            display_unit = ""
            if "(kt)" in unit_name:
                fy_value *= 1000
                display_unit = "kt"
                h1_value = h1_value / 1000 if h1_value is not None else None
                fy_value /= 1000
            elif "(koz)" in unit_name:
                fy_value *= 1000
                display_unit = "koz"
                h1_value = h1_value / 1000 if h1_value is not None else None
                fy_value /= 1000
            elif "(mlbs)" in unit_name:
                display_unit = "Mlbs"
            else:
                display_unit = str(row.get("unit") or "")
            if h1_value is not None:
                implied_h2 = fy_value - h1_value
            guidance_row = [
                label,
                "-" if h1_value is None else fmt._id(h1_value, 1),
            ]
            if has_prior_guidance:
                guidance_row.append(
                    fmt._id(row["previous_value"], 1)
                    if isinstance(row.get("previous_value"), (int, float)) else "-")
            guidance_row.extend([
                fmt._id(fy_value, 1),
                "-" if implied_h2 is None else fmt._id(implied_h2, 1),
            ])
            guidance_rows.append(guidance_row)
        guidance_note = (
            f"Sumber: {actual['source_title']}, hlm. 3 dan 7. Panduan manajemen "
            "bukan estimasi analis atau dasar target harga secara otomatis. H2 tersirat "
            "adalah guidance FY dikurangi output H1, bukan guidance penjualan. "
            "AMMAN menyebut utilisasi smelter dapat menggeser timing persediaan dan penjualan konsentrat "
            "(FY 2025 Earnings Presentation, hlm. 19). Izin ekspor yang dikutip dalam laporan keuangan "
            "interim berlaku sampai 30 April 2026 (H1 2026 Financial Statements, hlm. 123); "
            "berita 6 Mei mengutip pejabat NTB bahwa AMNT mengajukan tambahan waktu, tetapi juru bicara AMMAN "
            "pada 7 Mei menyatakan belum mengajukan; pada 6 Juni Kepala ESDM NTB menyebut AMNT belum berencana "
            "mengajukan. Status resmi setelah Juni tetap belum terverifikasi, jadi sisa guidance adalah output, "
            "bukan penjualan yang dijamin.")
        if has_prior_guidance:
            revised = next(row for row in guidance
                           if isinstance(row.get("previous_value"), (int, float)))
            guidance_note += (
                f" Panduan FY26 {revised['name']} direvisi dari "
                f"{fmt._id(revised['previous_value'], 0)} menjadi "
                f"{fmt._id(revised['value'], 0)} (+{fmt._id(revised.get('revision_change_pct'), 1)}%). "
                f"{str(revised.get('revision_reason') or '').rstrip('. ')}. "
                f"Panduan awal: {revised.get('previous_guidance_source_title')}, hlm. "
                f"{revised.get('previous_guidance_source_page')}; revisi: "
                f"{revised.get('revision_source_title')}, hlm. {revised.get('revision_source_page')}.")
        add(f"Panduan produksi {guidance_period} dari manajemen",
            (["Produk", f"{actual['period']} produksi", "Guidance awal",
              "Guidance kini FY26", "H2 tersirat"]
             if has_prior_guidance else
             ["Produk", f"{actual['period']} produksi", f"{guidance_period} guidance",
              "H2 tersirat"]),
            guidance_rows,
            guidance_note + " Dokumen: https://www.amman.co.id/rails/active_storage/blobs/proxy/"
            "eyJfcmFpbHMiOnsiZGF0YSI6NDk3OCwicHVyIjoiYmxvYl9pZCJ9fQ%3D%3D--50df1975317d5d37d39e6c868f5b05f51f29bb1d/"
            "FY%202025%20EARNINGS%20PRESENTATION.pdf?disposition=inline; "
            "https://www.amman.co.id/rails/active_storage/blobs/proxy/"
            "eyJfcmFpbHMiOnsiZGF0YSI6Njc4NSwicHVyIjoiYmxvYl9pZCJ9fQ%3D%3D--2724448c92eb5bf87ae5b6b608b4f67980755d3b/"
            "H1%202026%20FINANCIAL%20STATEMENTS.pdf?disposition=inline.")

    cost_actuals = evidence.get("cost_actuals") or {}
    if mining and cost_actuals:
        cost_rows = [
            ["Biaya penambangan", fmt._id(cost_actuals["prior_unit_mining_cost_usd_per_tonne"], 2),
             fmt._id(cost_actuals["unit_mining_cost_usd_per_tonne"], 2),
             fmt._id(cost_actuals.get("fy2025_unit_mining_cost_usd_per_tonne"), 2),
             "US$/ton; FY25 kolom tahunan"],
            ["Biaya pengolahan", fmt._id(cost_actuals["prior_unit_processing_cost_usd_per_tonne"], 2),
             fmt._id(cost_actuals["unit_processing_cost_usd_per_tonne"], 2), "-",
             "US$/ton bijih"],
            ["Biaya smelting dan refining", fmt._id(cost_actuals["prior_smelting_refining_cost_usd_per_cathode_tonne"], 0),
             fmt._id(cost_actuals["smelting_refining_cost_usd_per_cathode_tonne"], 0), "-",
             "US$/ton katoda"],
        ]
        debt_outlook = evidence.get("debt_outlook") or {}
        actual_q3_repayment = debt_outlook.get("actual_q3_debt_repayment_usd")
        planned_q3_repayment = debt_outlook.get("planned_q3_debt_repayment_usd")
        if actual_q3_repayment:
            cost_rows.append(["Pelunasan utang Q3 (dilaporkan aktual)", "-",
                              fmt._id(actual_q3_repayment / 1e6, 0),
                              "-", "US$ juta; presentasi manajemen, 21 Sep 2026"])
        elif planned_q3_repayment:
            cost_rows.append(["Rencana pelunasan utang Q3", "-",
                              fmt._id(planned_q3_repayment / 1e6, 0),
                              "-", "US$ juta; outlook, belum aktual"])
        add("Biaya unit historis dan pelunasan utang Q3",
            ["Metrik", "1H25", "1H26 / Q3 actual", "FY25 tahunan", "Satuan / basis"], cost_rows,
            f"Sumber: {cost_actuals['source_title']}, hlm. {cost_actuals['source_page']}; "
            f"{cost_actuals['source_url']}. FY25 unit mining cost: "
            f"{cost_actuals.get('fy2025_cost_context_source_title')}, hlm. "
            f"{cost_actuals.get('fy2025_cost_context_source_page')}; "
            f"{cost_actuals.get('fy2025_cost_context_source_url')}. Basis/periode FY25 dan H1 tidak dinormalisasi; angka historis tidak menjadi jadwal biaya FY26. "
            + (f"Pembayaran Q3 yang disebut aktual: {debt_outlook.get('actual_source_title')}, hlm. "
               f"{debt_outlook.get('actual_source_page')}; {debt_outlook.get('actual_source_url')}. "
               "Saldo utang/kas pascapembayaran belum tersedia; jumlah ini tidak dimasukkan sebagai saldo baru atau proyeksi bunga."
               if actual_q3_repayment else
               "Rencana pembayaran utang bukan bukti pembayaran terealisasi atau jadwal bunga."))
        cost_history = cost_actuals.get("operating_cost_history") or {}
        trend = cost_history.get("unit_cost_trend") or []
        cash_costs = cost_history.get("cash_cost_per_copper_lb_sold") or []
        if trend:
            periods = [row.get("period", "-") for row in trend]
            unit_rows = []
            for key, label, decimals in (
                    ("unit_mining_cost_usd_per_tonne_mined", "Penambangan (US$/t material mined)", 2),
                    ("unit_processing_cost_usd_per_tonne_milled", "Pengolahan (US$/t throughput)", 2),
                    ("unit_smelt_refine_cost_usd_per_tonne_cathode", "Smelting/refining (US$/t katoda)", 0)):
                unit_rows.append([label] + [
                    "-" if row.get(key) is None else fmt._id(row[key], decimals)
                    for row in trend])
            add("Biaya operasi historis per setengah tahun",
                ["Metrik", *periods], unit_rows,
                f"Sumber: {cost_history.get('source_title')}, hlm. {cost_history.get('source_page')}; "
                f"{cost_history.get('source_url')}. Basis berbeda: biaya mining per ton material mined, "
                "processing per ton throughput, smelting/refining per ton katoda. Series ini menunjukkan "
                "historis biaya dan ramp-up, bukan FY26 forecast; grafik menyajikan angka fisik yang dibulatkan.")
        if cash_costs:
            periods = [row.get("period", "-") for row in cash_costs]
            cash_rows = []
            for key, label in (
                    ("operating_costs_ex_adjustments", "Biaya operasi, sebelum adjustment"),
                    ("byproduct_credits", "Kredit produk sampingan"),
                    ("smelt_refine_treatment_costs", "Biaya treatment smelting/refining"),
                    ("royalties", "Royalti"),
                    ("unit_cash_cost", "Unit cash cost dilaporkan")):
                cash_rows.append([label] + [fmt._id(row[key], 2) for row in cash_costs])
            add("Jembatan unit cash cost per pon Cu terjual",
                ["Komponen (US$/lb Cu terjual)", *periods], cash_rows,
                f"Sumber: {cost_history.get('source_title')}, hlm. {cost_history.get('source_page')}; "
                f"{cost_history.get('source_url')}. Kredit by-product mencakup emas, perak, asam sulfat dan selenium; "
                "treatment cost mencakup smelter dan PMR. Angka biaya sangat sensitif terhadap campuran dan volume produk, "
                "kadar, recovery, harga kredit by-product dan royalti. H1 2025 hingga H1 2026 bukan satu run-rate; "
                "unit cash cost ini adalah historical cross-check, bukan asumsi biaya H2 atau forecast C1/FCF per aset. "
                "Jumlah komponen dapat berbeda dari subtotal dilaporkan karena pembulatan.")

    mine_life = evidence.get("mine_life_context") or {}
    amdal_scope_exhibit = None
    if mining and mine_life:
        rows = []
        for name, category, mt_key, cu_grade_key, au_grade_key, cu_key, au_key in (
                ("Stockpile Batu Hijau", "Stockpile", "stockpile_mt",
                 "stockpile_grade_cu_pct", "stockpile_grade_au_gpt",
                 "stockpile_contained_cu_blb", "stockpile_contained_au_moz"),
                ("Batu Hijau", "Cadangan", "batu_hijau_reserves_mt",
                 "batu_hijau_grade_cu_pct", "batu_hijau_grade_au_gpt",
                 "batu_hijau_contained_cu_blb", "batu_hijau_contained_au_moz"),
                ("Batu Hijau", "Sumber daya", "batu_hijau_resources_mt",
                 "batu_hijau_resource_grade_cu_pct", "batu_hijau_resource_grade_au_gpt",
                 "batu_hijau_resource_contained_cu_blb", "batu_hijau_resource_contained_au_moz"),
                ("Elang", "Cadangan", "elang_reserves_mt",
                 "elang_grade_cu_pct", "elang_grade_au_gpt",
                 "elang_contained_cu_blb", "elang_contained_au_moz"),
                ("Elang", "Sumber daya", "elang_resources_mt",
                 "elang_resource_grade_cu_pct", "elang_resource_grade_au_gpt",
                 "elang_resource_contained_cu_blb", "elang_resource_contained_au_moz")):
            mt = mine_life.get(mt_key)
            cu_grade = mine_life.get(cu_grade_key)
            au_grade = mine_life.get(au_grade_key)
            cu_contained = mine_life.get(cu_key)
            au_contained = mine_life.get(au_key)
            if all(value is not None for value in
                   (mt, cu_grade, au_grade, cu_contained, au_contained)):
                rows.append([name, category, fmt._id(mt, 0),
                             fmt._id(cu_grade, 2), fmt._id(au_grade, 2),
                             fmt._id(cu_contained, 2), fmt._id(au_contained, 2)])
        add("Cadangan dan sumber daya mineral",
            ["Aset", "Kategori", "Mt", "Cu %", "Au g/t", "Cu Blb", "Au Moz"],
            rows,
            f"Sumber: {mine_life['source_title']}, hlm. {mine_life['source_page']}; "
            f"{mine_life['source_url']}. As of {mine_life.get('resource_source_date') or mine_life.get('reserves_as_of')}; "
            f"competent person: {mine_life.get('competent_person')}. Sumber daya "
            "mencakup cadangan dan tidak boleh dijumlahkan dengannya. Angka ini "
            "belum menjadi jadwal produksi, biaya, capex, atau arus kas tahunan NAV LoM.")
        development = mine_life.get("development_status") or {}
        milestone_rows = [
            ["Penambangan Batu Hijau sampai", mine_life["batu_hijau_mining_through"]],
            ["Pengolahan stockpile sampai", mine_life["batu_hijau_stockpile_through"]],
            ["Bijih pertama Elang", mine_life["elang_first_ore"]],
            ["Target keputusan investasi Elang", mine_life["elang_fid_target"]],
        ]
        status_labels = (
            ("mine_planning_status", "Penyusunan rencana tambang"),
            ("overland_conveyor_corridor_permitting", "Perizinan koridor OLC"),
            ("early_engineering_contractor_selection", "Pemilihan kontraktor early engineering"),
            ("feasibility_study_status", "Feasibility study Elang"),
            ("optimization_study_status", "Optimasi teknis Elang"),
        )
        for key, label in status_labels:
            if development.get(key):
                milestone_rows.append([label, development[key]])
        if development.get("infrastructure_scope"):
            milestone_rows.append(["Lingkup infrastruktur Elang", development["infrastructure_scope"]])
        annual_report = development.get("annual_report_context") or {}
        if annual_report.get("elang_operations_through"):
            milestone_rows.append([
                "Elang: horizon operasi yang diperkirakan",
                annual_report["elang_operations_through"]])
        if annual_report.get("detailed_engineering_and_optimization"):
            milestone_rows.append([
                "Engineering rinci dan optimasi (Annual Report 2025)",
                annual_report["detailed_engineering_and_optimization"]])
        consultation = development.get("2026_public_consultation_context") or {}
        if consultation:
            capex_range = consultation.get("reported_initial_investment_idr_trillion_range") or []
            if len(capex_range) == 2:
                capex_indication = (
                    f"Rp{fmt._id(capex_range[0], 0)}–{fmt._id(capex_range[1], 0)} triliun; "
                    "informasi awal yang disampaikan Bupati sebagai informasi dari AMNT")
                milestone_rows.append(["Indikasi investasi awal Elang (bukan anggaran tervalidasi)", capex_indication])
            if consultation.get("reported_construction_target"):
                milestone_rows.append([
                    "Target konstruksi yang disampaikan pada konsultasi publik",
                    consultation["reported_construction_target"]])
        if consultation.get("reported_project_status"):
            milestone_rows.append([
                "Konteks konsultasi publik AMDAL (22 Sep 2026)",
                consultation["reported_project_status"]])
        amdal_notice = development.get("2026_amdal_scoping_notice") or {}
        if amdal_notice:
            comparison = amdal_notice.get("context_comparators") or {}
            planned_facilities = amdal_notice.get("planned_support_facilities") or []
            conveyor_notice = next((item for item in planned_facilities
                                    if "conveyor" in item.lower()), "-")
            amdal_rows = [
                ["Rencana kapasitas penambangan bijih Elang",
                 f"~{fmt._id(amdal_notice.get('ore_mining_capacity_million_tonnes_per_year_approx'), 0)} Mt/tahun",
                 "Skala rencana pada pengumuman penyusunan AMDAL; bukan output tahunan atau guidance produksi."],
                ["Kapasitas tahunan pabrik pengolahan",
                 f"{fmt._id(comparison.get('annual_processing_ore_capacity_million_tonnes'), 0)} Mt/tahun",
                 "Angka nameplate ekspansi pabrik pada presentasi H1; definisinya berbeda dari kapasitas penambangan Elang."],
                ["Rentang desain ekspansi pabrik (Annual Report 2025)",
                 f"{fmt._id((annual_report.get('planned_processing_capacity_million_tonnes_per_year_range') or [85, 90])[0], 0)}–{fmt._id((annual_report.get('planned_processing_capacity_million_tonnes_per_year_range') or [85, 90])[1], 0)} Mt/tahun; first ore to mills {annual_report.get('expanded_plant_first_ore_to_mills_target', 'ditargetkan 2026')}",
                 "Rentang yang diungkap lebih awal; presentasi H1 2026 kemudian menyebut kapasitas pabrik 85 Mt/tahun. Tidak digunakan sebagai skenario throughput tambahan."],
                ["Overland conveyor Elang",
                 "54 km (presentasi Mar-26) / " + conveyor_notice.replace("overland ore conveyor ", ""),
                 "Panjang/rute belum direkonsiliasi; perbedaan berdampak pada lingkup dan estimasi capex."],
                ["Fasilitas pendukung yang direncanakan",
                 "; ".join(item for item in planned_facilities if "conveyor" not in item.lower()),
                 "Ruang lingkup awal AMDAL; tidak berisi biaya, jadwal konstruksi terinci, atau komitmen kontrak."],
            ]
            amdal_scope_exhibit = add(
                "Skala dan lingkup Elang pada tahap pengumuman AMDAL",
                ["Komponen", "Angka / rencana yang diumumkan", "Batas interpretasi"],
                amdal_rows,
                f"Pengumuman penyusunan AMDAL oleh PT AMNT, {amdal_notice.get('published_date')}; "
                f"dokumen: {amdal_notice.get('document_url')}; salinan diumumkan di "
                f"{amdal_notice.get('dissemination_page_url')}. Kapasitas olah 85 Mt/tahun: "
                f"{comparison.get('source_title')}, hlm. {comparison.get('source_page')}; "
                f"{comparison.get('source_url')}. Rentang desain pabrik dan target first ore: "
                f"{annual_report.get('source_title')}, hlm. 103; {annual_report.get('source_url')}. "
                f"Lingkup OLC sebelumnya: "
                f"{development.get('infrastructure_scope_source_title')}, hlm. "
                f"{development.get('infrastructure_scope_source_page')}; "
                f"{development.get('infrastructure_scope_source_url')}. Notice AMDAL meminta "
                f"masukan masyarakat selama {amdal_notice.get('public_input_period_working_days')} hari kerja; "
                "ini dokumen scoping untuk penyusunan AMDAL, bukan AMDAL disetujui atau desain final. "
                "Kapasitas 90 Mt/tahun adalah skala penambangan bijih, sedangkan 85 Mt/tahun merujuk kapasitas pengolahan; "
                "keduanya tidak disamakan menjadi asumsi throughput. Perbedaan OLC 54/60 km belum dimodelkan sebagai capex.")
        status_source = ""
        if development.get("source_url"):
            status_source = (
                f" Status pengembangan: {development.get('source_title')}, "
                f"hlm. {development.get('source_page')}; {development['source_url']}."
            )
        if development.get("feasibility_source_url"):
            status_source += (
                f" Status studi/optimasi FY2025: {development.get('feasibility_source_title')}, "
                f"hlm. {development.get('feasibility_source_page')}; "
                f"{development['feasibility_source_url']}."
            )
        if development.get("infrastructure_scope_source_url"):
            status_source += (
                f" Lingkup infrastruktur: {development.get('infrastructure_scope_source_title')}, "
                f"hlm. {development.get('infrastructure_scope_source_page')}; "
                f"{development['infrastructure_scope_source_url']}."
            )
        if annual_report.get("source_url"):
            status_source += (
                f" Horizon Elang dan status studi lanjutan: {annual_report.get('source_title')}, "
                f"hlm. {', '.join(str(page) for page in annual_report.get('source_pages') or [])}; "
                f"{annual_report['source_url']}."
            )
        if consultation.get("source_url"):
            status_source += (
                f" Informasi konsultasi publik 22 September 2026: {consultation.get('source_title')} "
                f"({consultation.get('source_attribution')}); {consultation['source_url']}. "
                "Rentang investasi bersifat indikatif, disampaikan Bupati dengan atribusi informasi dari AMNT; "
                "bukan capex budget atau phasing dan tidak digunakan sebagai input NAV LoM."
            )
        add("Jadwal operasi dan status pengembangan tambang",
            ["Tonggak / pekerjaan", "Perkiraan atau status yang diumumkan"],
            milestone_rows,
            f"Sumber tonggak: {mine_life['source_title']}, hlm. {mine_life['source_page']}; "
            f"{mine_life['source_url']}.{status_source} Tonggak proyek dan status "
            "pekerjaan bukan jadwal tahunan produksi, biaya, capex, atau arus kas "
            "untuk NAV LoM; rencana tambang masih dalam penyusunan.")

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
            ["Saham beredar yang digunakan model (juta)",
              fmt._id(shares / 1e6, 1) if shares is not None else "-"],
             ["Saham diterbitkan (juta)",
              fmt._id(balance["shares_issued"] / 1e6, 1)
              if balance.get("shares_issued") is not None else "-"]],
            f"Sumber: {balance.get('source_title') or actual['source_title']}, "
            "hlm. " + ", ".join(str(p) for p in balance.get("source_pages", [])) +
            f"; {balance.get('source_url') or actual['source_url']}; saham beredar "
            f"dari {shares_basis_text or 'data Sectors'}.")

    illustrative_pages = []
    if illustrative_scenarios and mining:
        top_down_projection = (intake.get("analyst_scenario") or {}).get(
            "top_down_projection") or {}
        product_bridge = _mining_sales_bridge(
            intake, fc.get("interim_scenario") or {})
        # Compare remaining FY26 contained-metal guidance with refined
        # product output guidance. These stage-to-stage ratios are diagnostics,
        # not recovery rates: feed timing and inventory movements are absent.
        guidance = evidence.get("management_guidance") or []
        guide_by_name = {str(row.get("name") or "").lower(): row
                         for row in guidance}
        actual_sales = evidence.get("sales_production_bridge") or []
        actual_by_key = {_product_key(row.get("product")): row
                         for row in actual_sales}

        def guide_value(fragment):
            item = next((row for name, row in guide_by_name.items()
                         if fragment in name), None)
            value = item.get("value") if item else None
            return value if isinstance(value, (int, float)) else None

        contained_cu_guide = guide_value("tembaga dalam konsentrat")
        contained_au_guide = guide_value("emas dalam konsentrat")
        cathode_guide_kt = guide_value("katoda tembaga")
        refined_au_guide_koz = guide_value("emas murni")
        concentrate_actual = actual_by_key.get("concentrate") or {}
        cathode_actual = actual_by_key.get("cathode_copper") or {}
        gold_actual = actual_by_key.get("refined_gold") or {}
        cu_h1_mlb = (concentrate_actual.get("metal_production") or {}).get("copper_mlbs")
        au_h1_oz = (concentrate_actual.get("metal_production") or {}).get("gold_oz")
        cathode_h1_t = cathode_actual.get("production")
        refined_au_h1_oz = gold_actual.get("production")
        interstage_rows = []
        if all(isinstance(value, (int, float)) for value in
               (contained_cu_guide, cu_h1_mlb, cathode_guide_kt, cathode_h1_t)):
            cu_h2_mlb = contained_cu_guide - cu_h1_mlb
            cathode_h2_kt = cathode_guide_kt - cathode_h1_t / 1000
            cathode_h2_mlb = cathode_h2_kt * 2.20462262
            interstage_rows.extend([
                ["Cu terkandung dalam konsentrat", f"{fmt._id(cu_h2_mlb, 1)} Mlb", "sisa guidance FY dikurangi aktual H1"],
                ["Output katoda tembaga", f"{fmt._id(cathode_h2_kt, 1)} kt / {fmt._id(cathode_h2_mlb, 1)} Mlb Cu", "sisa guidance FY dikurangi aktual H1"],
                ["Rasio output katoda / Cu terkandung", fmt.pct(cathode_h2_mlb / cu_h2_mlb) if cu_h2_mlb else "-", "diagnostik antar-tahap; bukan recovery metalurgi"],
            ])
        if all(isinstance(value, (int, float)) for value in
               (contained_au_guide, au_h1_oz, refined_au_guide_koz, refined_au_h1_oz)):
            au_h2_koz = (contained_au_guide * 1000 - au_h1_oz) / 1000
            refined_au_h2_koz = refined_au_guide_koz - refined_au_h1_oz / 1000
            interstage_rows.extend([
                ["Au terkandung dalam konsentrat", f"{fmt._id(au_h2_koz, 1)} koz", "sisa guidance FY dikurangi aktual H1"],
                ["Output emas murni", f"{fmt._id(refined_au_h2_koz, 1)} koz", "sisa guidance FY dikurangi aktual H1"],
                ["Rasio output emas murni / Au terkandung", fmt.pct(refined_au_h2_koz / au_h2_koz) if au_h2_koz else "-", "diagnostik antar-tahap; bukan recovery metalurgi"],
            ])
        if interstage_rows:
            interstage_exhibit = add(
                "Uji antar-tahap logam H2: konsentrat ke produk refinery",
                ["Metrik", "Sisa H2 tersirat", "Basis / batas interpretasi"],
                interstage_rows,
                f"Aktual H1 dan panduan FY26: {actual.get('source_title')}, hlm. 3 dan 7. "
                "H2 dihitung sebagai panduan FY dikurangi produksi H1; angka Mlb katoda "
                "dikonversi dari ton metrik. Cu/Au dalam konsentrat dan output katoda/emas "
                "murni adalah tahap berbeda, dapat memiliki timing serta persediaan antar-tahap, "
                "dan tidak mengungkap feed, recovery, assay, atau roll-forward material. Rasio "
                "bukan recovery metalurgi dan tidak memvalidasi penjualan maupun revenue H2.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Uji antar-tahap produksi H2",
                "layout": "stack",
                "paragraf": [
                    _t("Panduan FY26 menyiratkan output H2 katoda dan emas murni yang besar relatif terhadap sisa logam terkandung dalam panduan konsentrat. Rasio ini hanya penanda besarnya aliran material yang perlu dijelaskan: produk H2 dapat memakai umpan dan persediaan lintas periode, sedangkan produksi konsentrat dapat dijual eksternal atau masuk ke smelter. Tanpa rekonsiliasi feed, stockpile, recovery, dan jadwal penjualan, diagnostik ini tidak dapat dipakai sebagai recovery ataupun jembatan revenue tervalidasi.",
                       "FY26 guidance implies large H2 cathode and refined gold output relative to the contained metal left in concentrate guidance. The ratio only flags how much material flow needs explaining: H2 products can draw on feed and inventory across periods, while concentrate output can be sold externally or go to the smelter. Without a reconciliation of feed, stockpiles, recovery and the sales schedule, this diagnostic cannot serve as a recovery rate or a validated revenue bridge.")],
                "exhibit": [interstage_exhibit]})
        q2_data = ((evidence.get("quarterly_actuals") or {}).get(
            "q2_2026_derived") or {})
        if q2_data and product_bridge:
            q2_financials = q2_data.get("financials_usd_mn") or {}
            q2_product_rows = []
            for item in q2_data.get("sales_production_bridge") or []:
                key = item.get("product_key")
                if key not in ("concentrate", "cathode_copper", "refined_gold"):
                    continue
                label = {"concentrate": "Konsentrat", "cathode_copper": "Katoda tembaga",
                         "refined_gold": "Emas murni"}[key]
                rev = item.get("segment_revenue_usd_mn")
                q2_product_rows.append([
                    label, _volume_text(item.get("production"), item.get("unit")),
                    _volume_text(item.get("sales"), item.get("unit")),
                    money(rev * 1e6) if rev is not None else "-",
                    (f"US$ {fmt._id(item['revenue_per_sold_unit_proxy'], 0)}/{item['unit']}"
                     if item.get("revenue_per_sold_unit_proxy") is not None else "-"),
                    ((f"US$ {fmt._id(item['implied_net_realized_price']['value'], 0)}/"
                      f"{item['implied_net_realized_price']['unit'].replace('USD/', '')}")
                     if item.get("implied_net_realized_price") else "-")])
            for label, key in (("Net sales", "net_sales"), ("EBITDA", "ebitda"),
                               ("Laba bersih", "net_income"), ("Capex", "capex")):
                q2_product_rows.append([label, "-", "-",
                                        fmt._id(q2_financials.get(key), 0), "US$ juta", "-"])
            q2_exhibit = add(
                "Rekonstruksi Q2 2026 (H1 dikurangi Q1)",
                ["Produk / metrik", "Produksi Q2", "Terjual Q2",
                 "Revenue / metrik", "Revenue per unit, proxy", "Implied net price"], q2_product_rows,
                "Q2 diturunkan dari H1 resmi dikurangi Q1 resmi; volume dan metrik finansial adalah angka turunan. "
                "Revenue produk dibulatkan di kedua rilis; revenue/unit konsentrat adalah proxy segmen, bukan realized price/netback. "
                "Sumber Q1: AMMAN Q1 2026 Performance Release, hlm. 3-5. "
                "Sumber H1: AMMAN H1 2026 Earnings Release, hlm. 3-4.")
            q2_is = q2_data.get("income_statement_usd_thousand") or {}
            q2_cf = q2_data.get("cash_flow_usd_thousand") or {}
            q2_fin_rows = []
            for label, key in (("Penjualan bersih", "net_sales"),
                               ("Beban pokok penjualan", "cost_applicable_to_sales"),
                               ("Laba operasi", "operating_profit"),
                               ("Beban keuangan", "finance_costs"),
                               ("Pajak penghasilan", "income_tax"),
                               ("Laba bersih", "net_income")):
                q2_fin_rows.append([label, fmt._id(q2_is[key] / 1000, 1),
                                    "H1 laporan keuangan dikurangi Q1"])
            for label, key, basis in (
                    ("Arus kas operasi", "operating_cash_flow", "H1 laporan arus kas dikurangi Q1"),
                    ("Kas untuk investasi/capex", "investing_cash_used", "H1 laporan arus kas dikurangi Q1"),
                    ("Arus kas bebas indikatif", "free_cash_flow_derived", "OCF + arus kas investasi; turunan analis"),
                    ("Arus kas pendanaan", "financing_cash_flow", "H1 laporan arus kas dikurangi Q1"),
                    ("Kenaikan kas sebelum kurs", "net_increase_in_cash", "H1 laporan arus kas dikurangi Q1"),
                    ("Dampak kurs", "fx_effect", "H1 laporan arus kas dikurangi Q1"),
                    ("Kas akhir Q2", "closing_cash", "H1 laporan posisi keuangan; kas 30 Jun")):
                q2_fin_rows.append([label, fmt._id(q2_cf[key] / 1000, 1), basis])
            q2_fin_rows.insert(1, [
                "EBITDA", fmt._id(q2_data["financials_usd_mn"]["ebitda"], 0),
                "Selisih Q1 ke H1; kedua angka sumber dibulatkan ke US$ juta"])
            q2_fin_exhibit = add(
                "Rekonstruksi laba rugi dan arus kas Q2 2026",
                ["Metrik", "Q2 (US$ juta)", "Basis"], q2_fin_rows,
                "Turunan H1 dikurangi Q1 dari laporan interim resmi; angka laporan keuangan dasar dalam US$ ribu. "
                "EBITDA serta revenue per produk memakai angka rilis yang dibulatkan. FCF indikatif = arus kas operasi + arus kas investasi; "
                "bukan metrik FCF yang dinyatakan emiten. Sumber: Q1 2026 Performance Release, lampiran laporan keuangan; "
                "H1 2026 Earnings Release, lampiran laporan keuangan.")
            pricing = evidence.get("provisional_pricing_evidence") or {}
            pricing_exhibit = None
            if pricing:
                pricing_rows = [
                    ["Harga provisional saat penjualan", "Konsentrat dan katoda awalnya dicatat 100% pada harga provisional; pengakuan revenue tetap mensyaratkan delivery/title transfer."],
                    ["Sebelum settlement final", "Harga di-mark-to-market memakai forward price untuk estimasi bulan settlement; embedded derivative masuk laba rugi."],
                    ["Assay dan kuantitas", "Harga/kuantitas provisional bisa disesuaikan saat assay dan informasi jumlah metal baru diterima."],
                    ["Periode final pricing", "Mengikuti periode yang ditetapkan kontrak; periode per shipment/customer tidak diungkap dalam catatan ini."],
                    ["Risiko harga", "Penurunan 2% dinilai tidak signifikan terhadap laba per 30 Jun; tidak ada sensitivitas dolar yang diberikan."],
                ]
                pricing_exhibit = add(
                    "Ketentuan provisional pricing dan settlement",
                    ["Pengungkapan interim", "Dampak pada forecast"], pricing_rows,
                    f"Sumber: {pricing.get('source_title')}, Catatan 2.s hlm. 40 dan Catatan 30.a.ii hlm. 113; "
                    f"{pricing.get('source_url')}. Harga Q2 implied pada exhibit sebelumnya adalah estimasi historis turunan, "
                    "bukan final price atau netback shipment H2.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Rekonstruksi aktual Q2 2026",
                "layout": "stack",
                "paragraf": [
                    _t("Ini angka aktual turunan dari dua rilis, bukan angka Q2 yang dilaporkan terpisah. Perusahaan melaporkan volume dan realized price H1; harga Q2 sendiri tidak diberikan terpisah. Konsentrat dan katoda juga memakai provisional pricing sampai settlement final, sehingga implied price Q2 hanya kalibrasi historis, bukan harga final H2. Revenue/unit hanya proxy untuk menguji konsistensi mix dan sales.",
                       "These are actuals derived from two releases, not separately reported Q2 figures. The company reports H1 volumes and realized prices; Q2 prices are not given separately. Concentrate and cathode are also provisionally priced until final settlement, so the implied Q2 price is only a historical calibration, not the final H2 price. Revenue per unit is only a proxy for testing the consistency of mix and sales.")],
                "exhibit": [q2_exhibit, q2_fin_exhibit] +
                           ([pricing_exhibit] if pricing_exhibit else [])})

            pricing_balances = ((evidence.get("provisional_pricing_evidence") or {}).get(
                "receivables_and_derivatives") or {})
            if pricing_balances:
                receivables = pricing_balances.get("trade_receivables") or {}
                derivs = pricing_balances.get("derivative_balances") or {}
                jun = receivables.get("2026-06-30") or {}
                dec = receivables.get("2025-12-31") or {}
                jun_deriv = derivs.get("2026-06-30") or {}
                dec_deriv = derivs.get("2025-12-31") or {}
                pricing_balance_rows = [
                    ["Piutang usaha total", fmt._id(jun.get("total", 0) / 1000, 1),
                     fmt._id(dec.get("total", 0) / 1000, 1), "Seluruh produk/customer; tidak dipilah shipment."],
                    ["Piutang usaha FVPL", fmt._id(jun.get("fair_value_through_profit_or_loss", 0) / 1000, 1),
                     fmt._id(dec.get("fair_value_through_profit_or_loss", 0) / 1000, 1),
                     "Kebijakan akuntansi mengaitkan kategori ini dengan sebagian piutang provisional Cu/Au."],
                    ["Piutang usaha amortized cost", fmt._id(jun.get("amortized_cost", 0) / 1000, 1),
                     fmt._id(dec.get("amortized_cost", 0) / 1000, 1), "Tidak dirinci menurut produk/customer."],
                    ["Aset derivatif", fmt._id(jun_deriv.get("assets", 0) / 1000, 1),
                     fmt._id(dec_deriv.get("assets", 0) / 1000, 1),
                     "Note 18 merinci IRS/CCS/POS; bukan saldo provisional metal terpisah."],
                    ["Liabilitas derivatif", fmt._id(jun_deriv.get("liabilities", 0) / 1000, 1),
                     fmt._id(dec_deriv.get("liabilities", 0) / 1000, 1),
                     "Note 18 merinci IRS/CCS/POS; bukan saldo provisional metal terpisah."],
                ]
                pricing_balance_exhibit = add(
                    "Piutang provisional FVPL dan derivatif swap",
                    ["Saldo keuangan (US$m)", "30 Jun 2026", "31 Des 2025", "Klasifikasi dan batas data"],
                    pricing_balance_rows,
                    f"Sumber: {pricing_balances.get('source_title')}, {pricing_balances.get('classification_source_note')}; "
                    f"{pricing_balances.get('derivative_source_note')}; {pricing_balances.get('source_url')}. "
                    "Piutang FVPL adalah bagian dari piutang usaha, sedangkan aset/liabilitas derivatif merupakan pos berbeda.")
                illustrative_pages.append({
                    "halaman": 0,
                    "judul": "Saldo settlement provisional dan klasifikasi derivatif",
                    "layout": "stack",
                    "paragraf": [
                        _t("Kebijakan akuntansi menyebut aset FVPL mencakup sebagian piutang dari penjualan tembaga/emas provisional. Nilai tercatat kategori itu turun dari US$540,5 juta pada akhir 2025 menjadi US$23,3 juta per Juni 2026, tetapi laporan tidak memecahnya per produk, customer, shipment, atau tanggal final pricing. Penurunan saldo tidak sama dengan volume settlement atau realized price H1. Pos derivative asset/liability yang terpisah dirinci sebagai IRS, CCS, dan POS; jangan menghitungnya sebagai eksposur harga komoditas provisional.",
                           "The accounting policy says FVPL assets include part of the receivables from provisionally priced copper/gold sales. The carrying value of that category fell from US$540,5 juta at end-2025 to US$23,3 juta at June 2026, but the report does not split it by product, customer, shipment or final pricing date. The fall in the balance is not the same as settlement volume or the H1 realized price. The separate derivative asset/liability lines are itemised as IRS, CCS and POS; they are not provisional commodity price exposure.")
                    ],
                    "exhibit": [pricing_balance_exhibit]})

            cogs = q2_data.get("cost_of_sales_components") or {}
            cogs_components = cogs.get("components") or {}
            if cogs_components:
                q1_costs = cogs_components.get("reported_q1") or {}
                q2_costs = cogs_components.get("derived_q2") or {}
                h1_costs = cogs_components.get("reported_h1") or {}
                cost_labels = [
                    ("mining_processing_operating", "Mining, processing, dan operasi"),
                    ("deferred_stripping_movement", "Amortisasi stripping tertunda"),
                    ("depreciation_amortization", "Depresiasi dan amortisasi"),
                    ("government_royalty", "Royalti pemerintah"),
                    ("export_duty", "Bea ekspor"),
                    ("employee_costs", "Beban karyawan"),
                    ("freight_marketing", "Angkut dan pemasaran"),
                    ("silver_byproduct_credit", "Kredit produk perak"),
                    ("selenium_byproduct_credit", "Kredit produk selenium"),
                    ("sulfuric_acid_byproduct_credit", "Kredit produk asam sulfat"),
                    ("stockpiles_product_inventory_movement", "Mutasi stockpile dan persediaan produk"),
                    ("other", "Lainnya"),
                    ("total_costs_applicable_to_sales", "Total beban pokok penjualan"),
                ]
                cogs_rows = [[label,
                              fmt._id(q1_costs[key] / 1000, 1),
                              fmt._id(q2_costs[key] / 1000, 1),
                              fmt._id(h1_costs[key] / 1000, 1)]
                             for key, label in cost_labels]
                cogs_exhibit = add(
                    "Rekonsiliasi komponen beban pokok penjualan Q2",
                    ["Komponen (US$m)", "Q1 aktual", "Q2 turunan", "H1 aktual"],
                    cogs_rows,
                    "Q1 dari laporan interim AMMAN, Catatan 25 hlm. 105 dan Catatan 11 hlm. 72; H1 dari laporan keuangan interim AMMAN, Catatan 25 hlm. 108 dan Catatan 11 hlm. 73. "
                    "Q2 dihitung sebagai H1 dikurangi Q1; bukan angka triwulanan yang dilaporkan terpisah. "
                    "Sumber Q1 (arsip salinan filing emiten): https://www.indopremier.com/xdir/news/LAPORAN%20KEUANGAN/2026/q1/AMMN_Q1_2026.pdf. "
                    f"Sumber H1: {cogs.get('source_url_h1')}. Nilai dalam US$ juta; angka sumber dalam US$ ribu.")
                illustrative_pages.append({
                    "halaman": 0,
                    "judul": "Komposisi biaya aktual dan keterbatasan run-rate",
                    "layout": "stack",
                    "paragraf": [
                        _t("Catatan biaya menunjukkan HPP Q2 US$622,7 juta tersusun dari US$436,9 juta mining/processing/operasi, US$286,0 juta amortisasi stripping tertunda, dan US$168,6 juta royalti, lalu sebagian diimbangi mutasi stockpile/persediaan negatif US$435,9 juta serta kredit produk sampingan. Catatan 11 melaporkan nihil tambahan kapitalisasi stripping pada Q1 dan H1; jumlah US$286,0 juta adalah amortisasi aset stripping, bukan belanja kas Q2. Jadi HPP akuntansi tidak sama dengan biaya kas unit yang bisa langsung diekstrapolasi. Data ini merekonsiliasi aktual Q2; belum menentukan biaya H2 karena jadwal ore, grade, penjualan, inventory, dan basis kewajiban fiskal per shipment belum tersedia.",
                           "The cost notes show Q2 COGS of US$622,7 juta made up of US$436,9 juta mining/processing/operations, US$286,0 juta amortisation of deferred stripping and US$168,6 juta royalties, partly offset by a negative stockpile/inventory movement of US$435,9 juta and by-product credits. Note 11 reports no additions to capitalised stripping in Q1 and H1; the US$286,0 juta is amortisation of the stripping asset, not Q2 cash spending. Accounting COGS is therefore not a unit cash cost that can be extrapolated directly. These data reconcile Q2 actuals; they do not yet set H2 costs, because the schedule of ore, grade, sales and inventory, and the fiscal-obligation base per shipment, are not available.")
                    ],
                    "exhibit": [cogs_exhibit]})

                gp_diag = q2_data.get("inventory_movement_gross_profit_diagnostic") or {}
                inv_diag = q2_data.get("inventory_carrying_value_vs_cogs_movement") or {}
                gp_periods = gp_diag.get("periods") or {}
                if gp_periods and inv_diag:
                    gp_rows = []
                    for label, key in [
                            ("Penjualan bersih", "net_sales_usd_thousand"),
                            ("HPP dilaporkan", "reported_costs_applicable_to_sales_usd_thousand"),
                            ("Pergerakan stockpile/persediaan di HPP", "stockpiles_product_inventory_movement_in_cogs_usd_thousand"),
                            ("Laba kotor dilaporkan", "gross_profit_excluding_that_movement_usd_thousand"),
                            ("HPP setelah membalik pergerakan tersebut", "cogs_excluding_that_movement_usd_thousand"),
                            ("Laba kotor diagnostik setelah dibalik", "gross_profit_excluding_that_movement_usd_thousand")]:
                        # Compute reported gross profit directly for the first appearance;
                        # the diagnostic gross profit is shown after reversing the movement credit.
                        row = [label]
                        for period in ("q1_reported", "q2_derived", "h1_reported"):
                            values = gp_periods[period]
                            if label == "Laba kotor dilaporkan":
                                amount = (values["net_sales_usd_thousand"] -
                                          values["reported_costs_applicable_to_sales_usd_thousand"])
                            else:
                                amount = values[key]
                            row.append(fmt._id(amount / 1000, 1))
                        gp_rows.append(row)
                    gp_exhibit = add(
                        "Dampak pergerakan persediaan pada laba kotor (diagnostik)",
                        ["Metrik (US$m)", "Q1 aktual", "Q2 turunan", "H1 aktual"],
                        gp_rows,
                        "Perhitungan analitis dari laporan keuangan Q1 dan H1, bukan metrik yang dilaporkan emiten. "
                        "Q2 = H1 dikurangi Q1. Baris diagnostik hanya membalik satu baris pergerakan stockpile/persediaan pada HPP; "
                        "bukan gross profit adjusted, cash cost, EBITDA, atau FCFF. Sumber Q1: AMMAN Interim Financial Statements, "
                        "laporan laba rugi dan Catatan 25, hlm. 4 dan 105; sumber H1: AMMAN Interim Financial Statements, "
                        "laporan laba rugi dan Catatan 25, hlm. 4-5 dan 108.")
                    carrying_rows = {
                        row.get("name"): row for row in
                        ((evidence.get("inventory_and_sales_detail") or {}).get(
                            "inventory_and_stockpile_carrying_amounts") or [])}
                    inv_rows = []
                    for key, label in (("Total inventory, net", "Persediaan bersih"),
                                       ("Stockpiles, total", "Stockpiles")):
                        item = carrying_rows.get(key) or {}
                        opening = item.get("dec_2025")
                        closing = item.get("jun_2026")
                        if opening is not None and closing is not None:
                            inv_rows.append([
                                label, fmt._id(opening / 1000, 1),
                                fmt._id(closing / 1000, 1),
                                fmt._id((closing - opening) / 1000, 1)])
                    inv_rows.extend([
                        ["Gabungan nilai tercatat", fmt._id(inv_diag["opening_inventory_and_stockpile_carrying_value"] / 1000, 1),
                         fmt._id(inv_diag["closing_inventory_and_stockpile_carrying_value"] / 1000, 1),
                         fmt._id(inv_diag["increase_in_carrying_value"] / 1000, 1)],
                        ["Kredit pergerakan persediaan di HPP H1", "-", "-",
                         fmt._id(inv_diag["h1_cogs_stockpiles_product_inventory_movement"] / 1000, 1)],
                        ["Selisih yang tidak dijembatani catatan", "-", "-",
                         fmt._id(inv_diag["difference_not_reconciled_by_public_note"] / 1000, 1)],
                    ])
                    inv_exhibit = add(
                        "Nilai tercatat persediaan bukan tonase konsentrat",
                        ["Komponen (US$m)", "Des-25", "Jun-26", "Perubahan"],
                        inv_rows,
                        "Sumber: AMMAN H1 2026 Interim Financial Statements, Catatan 7 hlm. 61 dan Catatan 25 hlm. 108. "
                        "Selisih nilai tercatat gabungan dengan kredit HPP tidak direkonsiliasi langsung dalam catatan; "
                        "keduanya tidak boleh dikonversi menjadi tonase konsentrat atau volume penjualan.")
                    illustrative_pages.append({
                        "halaman": 0,
                        "judul": "Persediaan, gross profit, dan batas rekonsiliasi",
                        "layout": "stack",
                        "paragraf": [
                            _t("Baris pergerakan stockpile/persediaan mengurangi HPP yang dilaporkan sebesar US$974,7 juta pada H1. Jika baris itu dibalik secara mekanis, laba kotor H1 menjadi negatif US$10,6 juta; angka ini hanya diagnostik, bukan ukuran laba atau arus kas alternatif. Nilai tercatat gabungan persediaan dan stockpiles naik US$1.024,6 juta, berbeda US$49,9 juta dari kredit HPP. Catatan tidak menyediakan roll-forward fisik yang menghubungkan produksi, transfer ke smelter, penjualan, dan saldo akhir. Karena itu nilai inventory tidak memvalidasi penjualan konsentrat H2.",
                               "The stockpile/inventory movement line reduced reported COGS by US$974,7 juta in H1. Reversing that line mechanically would turn H1 gross profit into a loss of US$10,6 juta; this is only a diagnostic, not an alternative measure of profit or cash flow. The combined carrying value of inventory and stockpiles rose US$1.024,6 juta, US$49,9 juta different from the COGS credit. The notes give no physical roll-forward linking production, transfers to the smelter, sales and closing balances. Inventory values therefore do not validate H2 concentrate sales.")
                        ],
                        "exhibit": [gp_exhibit, inv_exhibit]})

            debt_evidence = evidence.get("debt_and_contract_evidence") or {}
            offtake = evidence.get("customer_delivery_commitment") or {}
            if debt_evidence and offtake:
                debt = debt_evidence.get("debt_usd_thousand") or {}
                costs = debt_evidence.get("h1_finance_costs_usd_thousand") or {}
                h1_debt_cash = debt_evidence.get("h1_bank_debt_cash_flows_usd_thousand") or {}
                liquidity = debt_evidence.get(
                    "contractual_undiscounted_long_term_loan_cashflows_usd_thousand") or {}
                advances = offtake.get("prepayment_advance_usd_thousand") or {}
                debt_contract_rows = [
                    ["Pelunasan utang yang dilaporkan untuk Q3 2026",
                     fmt._id((evidence.get("debt_outlook") or {}).get(
                         "actual_q3_debt_repayment_usd", 0) / 1e6, 0),
                     "Dilaporkan telah dibayar; saldo utang/kas setelah pembayaran belum dilaporkan."],
                    ["Glencore cathode prepayment balance, Jun-26",
                     fmt._id(advances.get("balance_2026_06_30") / 1000, 1),
                     "Monthly deduction against cathode deliveries; delivery quantity and price formula not public."],
                    ["Long-term loans, net of unamortized fees",
                     fmt._id(debt.get("long_term_loans_net") / 1000, 1),
                     f"Current maturity US${fmt._id(debt.get('long_term_current_maturities')/1000, 1)}m; noncurrent net US${fmt._id(debt.get('long_term_noncurrent_net')/1000, 1)}m."],
                    ["Undiscounted long-term loan cash flows <1y",
                     fmt._id(liquidity.get("less_than_1_year") / 1000, 1),
                     "Principal plus interest; not a principal-only maturity or free-cash-flow forecast."],
                    ["H1 interest expense (long-term debt)",
                     fmt._id(costs.get("long_term_interest_expense") / 1000, 1),
                     f"H1 total consolidated P&L finance cost US${fmt._id(costs.get('total_consolidated_pnl_finance_cost')/1000, 1)}m; cash finance costs US${fmt._id(costs.get('cash_finance_costs_paid')/1000, 1)}m."],
                    ["Accrued capex payable, Jun-26",
                     fmt._id(debt_evidence.get("accrued_capital_expenditure_usd_thousand") / 1000, 1),
                     "Accrued balance only; not remaining project budget or payment schedule."],
                ]
                debt_contract_exhibit = add(
                    "Kontrak cathode, utang, dan kewajiban kas yang diungkapkan",
                    ["Fakta resmi (US$m)", "Nilai", "Makna untuk forecast"],
                    debt_contract_rows,
                    f"Sumber: {debt_evidence.get('source_title')}, catatan laporan keuangan 15, 17, 21 dan 30; "
                    f"{debt_evidence.get('source_url')}. Pelunasan Q3 US$350m dilaporkan aktual oleh manajemen pada "
                    f"{(evidence.get('debt_outlook') or {}).get('actual_source_title')}, hlm. "
                    f"{(evidence.get('debt_outlook') or {}).get('actual_source_page')}; "
                    f"{(evidence.get('debt_outlook') or {}).get('actual_source_url')}. Angka itu memperbarui outlook H1, "
                    "tetapi belum ada neraca pascapembayaran untuk menghitung kas/utang baru atau bunga forward."
                )
                illustrative_pages.append({
                    "halaman": 0,
                    "judul": "Batas bukti kontrak, beban bunga, dan capex",
                    "layout": "stack",
                    "paragraf": [
                        _t("Ada bukti offtake cathode sampai akhir 2027 dan customer prepayment, tetapi volume pengiriman dan formula harga tidak diungkap. Beban bunga serta pembayaran pinjaman Q2 kini dapat direkonsiliasi sebagai actual; keduanya belum menjadi jadwal H2. Capex akrual dan capex kas H1/Q2 juga tidak menggantikan anggaran sisa proyek.",
                           "There is evidence of a cathode offtake to the end of 2027 and a customer prepayment, but delivery volumes and the price formula are not disclosed. Interest expense and Q2 loan repayments can now be reconciled as actuals; neither is yet an H2 schedule. Accrued capex and H1/Q2 cash capex do not replace the remaining project budget either.")
                    ],
                    "exhibit": [debt_contract_exhibit]})
                if h1_debt_cash:
                    hc = h1_debt_cash
                    h1_debt_rows = [
                        ["Penerimaan pinjaman bank jangka pendek", fmt._id(hc["short_term_bank_loan_proceeds"] / 1000, 1), "Arus kas masuk aktual H1."],
                        ["Pembayaran pinjaman bank jangka pendek", fmt._id(hc["short_term_bank_loan_repayments"] / 1000, 1), "Arus kas keluar aktual H1."],
                        ["Penerimaan pinjaman bank jangka panjang", fmt._id(hc["long_term_bank_loan_proceeds"] / 1000, 1), "Arus kas masuk aktual H1."],
                        ["Pembayaran pokok pinjaman bank jangka panjang", fmt._id(hc["long_term_bank_loan_principal_repayments"] / 1000, 1), "Angka rinci laporan keuangan; US$340,0m adalah pelunasan dipercepat yang termasuk di sini."],
                        ["Arus kas bersih pinjaman bank (hasil hitung)", fmt._id(hc["net_cash_flow_from_bank_borrowing_calculated"] / 1000, 1), "Jumlah penerimaan dan pembayaran short- plus long-term."],
                        ["Arus kas perubahan kas dibatasi", fmt._id(hc["restricted_cash_change_cash_flow"] / 1000, 1), "Arus kas yang dilaporkan di bagian pendanaan."],
                        ["Arus kas bersih aktivitas pendanaan", fmt._id(hc["net_cash_used_in_financing_activities_reported"] / 1000, 1), "Nilai laporan; sama dengan arus pinjaman bersih plus perubahan kas dibatasi."],
                        ["Headline presentasi: utang dibayar YTD", fmt._id(hc["management_presentation_repayment_headline_usd_thousand"] / 1000, 1), f"Dibanding pembayaran pokok jangka panjang rinci US${fmt._id(abs(hc['long_term_bank_loan_principal_repayments']) / 1000, 3)}m, selisih nominal US${fmt._id(hc['difference_presentation_headline_vs_exact_long_term_repayments'] / 1000, 3)}m belum direkonsiliasi; basis keduanya belum terbukti sama."],
                    ]
                    h1_debt_flow_exhibit = add(
                        "Rekonsiliasi arus pinjaman dan pembayaran utang H1 2026",
                        ["Arus kas pendanaan H1 2026 (US$m)", "Nilai", "Basis / batas rekonsiliasi"],
                        h1_debt_rows,
                        f"Sumber utama: {hc.get('source_title')}, laporan arus kas cetak hlm. "
                        f"{(hc.get('source_pages') or {}).get('cash_flow_statement')} dan rincian pembayaran pokok Note 17 hlm. "
                        f"{(hc.get('source_pages') or {}).get('long_term_principal_detail')}; {hc.get('source_url')}. "
                        "Presentasi manajemen H1 hlm. 16 menyebut US$588m utang dibayar YTD; laporan keuangan merinci US$580,866m pembayaran pokok jangka panjang. "
                        "Selisih nominal headline tidak dijelaskan dalam sumber yang ditelaah dan basis headline belum terbukti sama; angka presisi laporan keuangan tetap dipakai untuk arus kas. "
                        "Pembayaran US$350m Q3 yang dilaporkan kemudian tidak termasuk dalam periode H1 dan belum memiliki saldo kas/utang pascapembayaran."
                    )
                    illustrative_pages.append({
                        "halaman": 0,
                        "judul": "Arus kas pinjaman dan pelunasan utang",
                        "layout": "stack",
                        "paragraf": [
                            _t("Rekonsiliasi H1 menunjukkan arus kas bank bersih keluar US$520,0m, bukan pembayaran pokok bruto. "
                               "Setelah arus kas perubahan kas dibatasi US$57,5m, total kas bersih aktivitas pendanaan adalah US$462,4m keluar. "
                               "Headline pelunasan US$588m pada presentasi H1 berbeda secara nominal US$7,134m dari pembayaran pokok jangka panjang rinci; sumber tidak mengonfirmasi bahwa basis keduanya sama atau memberi bridge selisih.",
                               "The H1 reconciliation shows a net bank-borrowing cash outflow of US$520,0m, not gross principal repayments. "
                               "After the US$57,5m restricted-cash cash flow, net cash used in financing activities totals US$462,4m. "
                               "The US$588m repayment headline in the H1 presentation differs in nominal terms by US$7,134m from the detailed long-term principal repayments; the source neither confirms that the two share a basis nor bridges the gap.")
                        ],
                        "exhibit": [h1_debt_flow_exhibit],
                    })

            product_rows = []
            for row in product_bridge["rows"]:
                if row.get("price_components"):
                    price_text = "; ".join(
                        f"{('Cu' if 'Tembaga' in component['product'] else 'Au')} "
                        f"US${fmt._id(component['h1_price'], 2)}/{component['unit']}"
                        for component in row["price_components"])
                elif row.get("net_realized_price"):
                    price = row["net_realized_price"]
                    price_unit = str(price.get("unit", row["unit"])).replace("USD/", "")
                    if price_unit == "tonne":
                        price_unit = "t"
                    if row.get("h2_price_basis", "").startswith("Q2 implied"):
                        price_text = (f"Q2 impl. US${fmt._id(row['unit_value'], 0)}/"
                                      f"{price_unit}")
                    else:
                        price_text = (f"H1 US${fmt._id(price['value'], 0)}/"
                                      f"{price_unit}")
                else:
                    price_text = (f"US${fmt._id(row['unit_value'], 2)}/"
                                  f"unit revenue proxy")
                product_rows.append([
                    row["label"], _volume_text(row["h1_sold"], row["unit"]),
                    price_text,
                    _volume_text(row["h2_production"], row["unit"]),
                    _volume_text(row["h2_sales"], row["unit"]),
                    fmt._id(row["h2_revenue"] / 1e6, 1)])
            product_rows.extend([
                ["Subtotal product bridge", "-", "-", "-", "-",
                 fmt._id(product_bridge["base_sum"] / 1e6, 1)],
                ["Top-down H2 analyst scenario", "-", "-", "-", "-",
                 fmt._id(product_bridge["h2_topdown"] / 1e6, 1)],
                ["Gap belum dijelaskan", "-", "-", "-", "-",
                 fmt._id(product_bridge["residual"] / 1e6, 1)]])
            product_exhibit = add(
                "Uji revenue H2 dari volume produk dan realized price",
                ["Produk", "H1 terjual aktual", "Basis harga H2", "H2 output tersirat", "H2 sales skenario", "H2 revenue (US$m)"],
                product_rows,
                "H1 sales dan realized prices: AMMAN H1 2026 Earnings Presentation, hlm. 22; FY output guidance: "
                "AMMAN H1 2026 Earnings Release, hlm. 7. H2 sales memakai sell-through Q2 turunan untuk produk olahan; "
                "cabang sensitivitas konservatif mengecualikan penjualan konsentrat karena volume ekspor H2 belum dapat diverifikasi. "
                "Q2 implied net realized price untuk katoda dan emas diturunkan dari rata-rata tertimbang harga Q1 dan H1 yang dilaporkan; angka sumber dibulatkan, sehingga ini estimasi, bukan harga Q2 yang dilaporkan terpisah. Harga Q1 dan H1 sama-sama net of mark-to-market adjustment. Ini bukan fakta aktual, forecast emiten, atau bukti penjualan konsentrat total nol. "
                "DetikBali (6 Mei 2026) mengutip pejabat NTB mengatakan AMNT mengajukan tambahan waktu enam bulan; "
                "DetikBali (7 Mei 2026) mengutip VP Corporate Communications AMMAN bahwa perpanjangan belum diajukan; "
                "kedua laporan itu bertentangan. IDN Times (6 Juni 2026) mengutip Kepala ESDM NTB yang menyampaikan hasil koordinasi AMNT belum berencana mengajukan. "
                "Laporan media itu terbatas pada tanggal masing-masing, bukan konfirmasi status izin setelah Juni. "
                "Rujukan: https://www.detik.com/bali/bisnis/d-8477778/amnt-ajukan-perpanjangan-ekspor-konsentrat-ke-esdm; "
                "https://www.detik.com/bali/bisnis/d-8479474/amnt-sebut-belum-ajukan-perpanjangan-izin-ekspor-konsentrat; "
                "https://ntb.idntimes.com/news/ntb/amnt-dipastikan-tak-ajukan-perpanjangan-relaksasi-ekspor-konsentrat-00-ldn3d-b7qt8x. "
                "Paparan Publik AMMAN 2026, hlm. 16, menyatakan konsentrat hanya dapat dijual dengan izin sementara sampai 30 April 2026; laporan interim H1 mengonfirmasi izin tersebut berakhir, bukan status izin berikutnya. "
                "PP 24/2026 tentang ekspor SDA strategis mencakup batubara, kelapa sawit, dan ferroalloy pada tahap awal, bukan konsentrat tembaga; peraturan tersebut tidak membuktikan ada atau tidaknya izin AMNT. "
                "AMMAN juga menyatakan stabilitas utilisasi smelter dapat memengaruhi timing persediaan dan penjualan konsentrat: "
                "FY 2025 Earnings Presentation, hlm. 19. "
                f"Top-down H2 revenue US${fmt._id(product_bridge['h2_topdown']/1e6, 1)} juta berasal dari "
                f"{top_down_projection.get('source_title', 'skenario analis yang dimasukkan')}; angka ini adalah hurdle skenario, "
                "bukan panduan emiten atau forecast tervalidasi. "
                "Harga Q2 implied untuk katoda/emas dan net realized price H1 untuk konsentrat dipakai sebagai proxy H2, bukan forecast harga emiten. H2 adalah periode enam bulan Jul-Dec yang "
                "dihitung dari H1 aktual. Presentasi H1 menyebut first ore mill baru pada pertengahan Agustus, laju smelter Juni 93%, "
                "rate Juli-Agustus membaik/stabil, dan rekor kinerja baru pada Juli-Agustus; tetapi tidak memberi tonase umpan atau "
                "produksi bulanan Jul-Aug, sehingga update operasional ini belum memvalidasi penjualan maupun revenue H2. Volume periode itu masih belum dapat "
                "diisolasi sebagai actual kuantitatif dalam jembatan ini. Sumber: AMMAN H1 2026 Earnings Presentation, hlm. 10, 12, 18; "
                "https://www.amman.co.id/rails/active_storage/blobs/proxy/eyJfcmFpbHMiOnsiZGF0YSI6Njc4NiwicHVyIjoiYmxvYl9pZCJ9fQ%3D%3D--b709bb5b1cfcd4e10d811aac0d9407656a084723/H1%202026%20EARNINGS%20PRESENTATION.pdf?disposition=inline. "
                "Rilis H1/Q1 resmi membulatkan revenue segmen.")
            q2_concentrate = next((row for row in
                                   q2_data.get("sales_production_bridge") or []
                                   if row.get("product_key") == "concentrate"), {})
            concentrate_scenario = next((row for row in
                                         ((intake.get("analyst_scenario") or {}).get("product_sales") or [])
                                         if row.get("product_key") == "concentrate"), {})
            contingent_text = ""
            if q2_concentrate.get("revenue_per_sold_unit_proxy") and \
                    concentrate_scenario.get("conditional_case_h2_sales_to_h1"):
                h1_conc = next((row for row in product_bridge["rows"]
                                if row["key"] == "concentrate"), None)
                if h1_conc:
                    contingent_volume = (h1_conc["h1_sold"] *
                                         concentrate_scenario["conditional_case_h2_sales_to_h1"])
                    contingent_value = contingent_volume * q2_concentrate["revenue_per_sold_unit_proxy"]
                    contingent_text = _t(
                        f" Jika ada izin/kanal dan kontrak yang berlaku, {_volume_text(contingent_volume, 'dmt')} penjualan konsentrat (volume H1) "
                        f"pada proxy revenue Q2 sekitar US${fmt._id(contingent_value/1e6, 1)} juta akan menutup hampir "
                        "seluruh gap. Ini sensitivitas, bukan asumsi base atau bukti penjualan.",
                        f" With a valid permit/channel and contract, {_volume_text(contingent_volume, 'dmt')} of concentrate sales (the H1 volume) "
                        f"at the Q2 revenue proxy, about US${fmt._id(contingent_value/1e6, 1)} juta, would close almost "
                        "all of the gap. This is a sensitivity, not a base assumption or evidence of sales.")
            delivery_commitment = ((intake.get("official_evidence") or {}).get(
                "customer_delivery_commitment") or {})
            commitment_text = ""
            if delivery_commitment:
                advance = delivery_commitment.get("prepayment_advance_usd_thousand") or {}
                opening_advance = advance.get("balance_2025_12_31")
                received_advance = advance.get("received_2026_04")
                closing_advance = advance.get("balance_2026_06_30")
                commitment_text = _t(
                    " Kontrak Glencore mendukung keberadaan kanal penjualan katoda dengan komitmen "
                    f"pengiriman sampai {delivery_commitment.get('delivery_commitment_until')}; uang muka "
                    "dipotong proporsional dari pengiriman bulanan, dan kegagalan memenuhi komitmen "
                    "mewajibkan pembayaran kembali uang muka terkait beserta bunga. ",
                    " The Glencore contract supports the existence of a cathode sales channel, with delivery "
                    f"commitments until {delivery_commitment.get('delivery_commitment_until')}; the advance "
                    "is deducted pro rata from monthly deliveries, and failing to meet the commitment "
                    "requires repaying the related advance with interest. "
                )
                if all(value is not None for value in
                       (opening_advance, received_advance, closing_advance)):
                    commitment_text += _t(
                        f"Penerimaan uang muka April adalah US${fmt._id(received_advance/1000, 1)} juta; "
                        f"saldo naik bersih dari US${fmt._id(opening_advance/1000, 1)} juta pada akhir 2025 "
                        f"menjadi US${fmt._id(closing_advance/1000, 1)} juta pada akhir Juni. ",
                        f"The April advance received was US${fmt._id(received_advance/1000, 1)} juta; "
                        f"the balance rose net from US${fmt._id(opening_advance/1000, 1)} juta at end-2025 "
                        f"to US${fmt._id(closing_advance/1000, 1)} juta at end-June. "
                    )
                commitment_text += _t(
                    "Catatan tidak mengungkap volume tersisa per kuartal, formula harga, atau rekonsiliasi "
                    "penerimaan dan potongan atas pengiriman. Kontrak ini tidak memvalidasi volume katoda H2 "
                    "atau harga pada bridge. Sumber: "
                    f"{delivery_commitment.get('source_title')}, hlm. {delivery_commitment.get('source_page')}; "
                    f"{delivery_commitment.get('source_url')}.",
                    "The notes do not disclose the remaining volume per quarter, the price formula, or a "
                    "reconciliation of receipts and deductions against deliveries. The contract does not validate "
                    "H2 cathode volumes or the prices in the bridge. Source: "
                    f"{delivery_commitment.get('source_title')}, p. {delivery_commitment.get('source_page')}; "
                    f"{delivery_commitment.get('source_url')}."
                )
            export_report = (((intake.get("official_evidence") or {}).get(
                "strategic_export_governance_2026") or {}).get(
                    "reported_export_realization") or {})
            export_text = ""
            if export_report:
                export_text = _t(
                    f" Data terpisah yang Bloomberg Technoz atribusikan kepada pejabat Kemendag menyebut "
                    f"ekspor sementara {fmt._id(export_report.get('volume', 0)/1000, 0)} ribu "
                    f"{export_report.get('unit')} sampai menjelang izin berakhir pada April 2026; "
                    "verifikasi bersama Bea Cukai saat itu masih berlangsung. Angka WMT ini tidak dapat "
                    "direkonsiliasi langsung dengan rekomendasi kuota 480 ribu DMT AMMAN karena konversi "
                    "kadar air tidak tersedia, tidak sama dengan revenue sales, dan tidak membuktikan izin H2. "
                    f"Sumber laporan bertanggal {export_report.get('published_date')}: "
                    f"{export_report.get('source_url')}.",
                    f" Separate data that Bloomberg Technoz attributes to Trade Ministry officials put "
                    f"temporary exports at {fmt._id(export_report.get('volume', 0)/1000, 0)} thousand "
                    f"{export_report.get('unit')} up to shortly before the permit expired in April 2026; "
                    "joint verification with Customs was still under way at the time. This WMT figure cannot "
                    "be reconciled directly with AMMAN's recommended quota of 480 thousand DMT because the "
                    "moisture conversion is not available; it is not sales revenue and does not prove an H2 permit. "
                    f"Source report dated {export_report.get('published_date')}: "
                    f"{export_report.get('source_url')}."
                )
            illustrative_pages.append({
                "halaman": 0, "judul": "Uji monetisasi produksi terhadap revenue H2",
                "layout": "stack",
                "paragraf": [_t(
                    f"Product bridge pada asumsi penjualan dasar menghasilkan US${fmt._id(product_bridge['base_sum']/1e6, 1)} juta, dibanding top-down US${fmt._id(product_bridge['h2_topdown']/1e6, 1)} juta. "
                    f"Gap US${fmt._id(product_bridge['residual']/1e6, 1)} juta masih belum dijelaskan.{contingent_text}{commitment_text}{export_text} "
                    "Karena belum ada konfirmasi volume H2, realized price forward, atau jadwal stockpile/umpan smelter, kedua angka tetap skenario internal dan release gate tetap draft.",
                    f"On base sales assumptions the product bridge yields US${fmt._id(product_bridge['base_sum']/1e6, 1)} juta, against a top-down US${fmt._id(product_bridge['h2_topdown']/1e6, 1)} juta. "
                    f"A gap of US${fmt._id(product_bridge['residual']/1e6, 1)} juta remains unexplained.{contingent_text}{commitment_text}{export_text} "
                    "With no confirmation yet of H2 volumes, forward realized prices, or the stockpile/smelter-feed schedule, both figures remain internal scenarios and the release gate stays at draft.")],
                "exhibit": [product_exhibit]})

            h1_price_rows = []
            reconstructed_total = 0.0
            reported_total = 0.0
            for row in product_bridge["rows"]:
                if row.get("price_components"):
                    price_basis = "; ".join(
                        f"{fmt._id(component['h1_sold'] / 1e6, 1)} Mlb Cu × "
                        f"US${fmt._id(component['h1_price'], 2)}/lb" if component["unit"] == "lb" else
                        f"{fmt._id(component['h1_sold'] / 1000, 1)} koz Au × "
                        f"US${fmt._id(component['h1_price'], 0)}/oz"
                        for component in row["price_components"])
                else:
                    realized = row.get("net_realized_price") or {}
                    price_unit = str(realized.get("unit", row["unit"])).replace("USD/", "")
                    if price_unit == "tonne":
                        price_unit = "t"
                    price_basis = (f"{_volume_text(row['h1_sold'], row['unit'])} × "
                                   f"US${fmt._id(row['unit_value'], 0)}/{price_unit}")
                reconstructed = row["unit_value"] * row["h1_sold"]
                reconstructed_total += reconstructed
                reported_total += row["h1_revenue"]
                h1_price_rows.append([
                    row["label"], price_basis,
                    fmt._id(reconstructed / 1e6, 1),
                    fmt._id(row["h1_revenue"] / 1e6, 0),
                    fmt._id((reconstructed - row["h1_revenue"]) / 1e6, 1),
                ])
            h1_price_rows.append([
                "Total produk", "Revenue dihitung dari volume × realized price",
                fmt._id(reconstructed_total / 1e6, 1),
                fmt._id(reported_total / 1e6, 0),
                fmt._id((reconstructed_total - reported_total) / 1e6, 1),
            ])
            h1_price_exhibit = add(
                "Rekonsiliasi realized price dengan revenue produk H1",
                ["Produk", "Volume × harga terealisasi H1", "Revenue hitungan (US$m)",
                 "Revenue segmen dilaporkan (US$m)", "Selisih (US$m)"],
                h1_price_rows,
                "Harga realisasi dan volume penjualan: AMMAN H1 2026 Earnings Presentation, hlm. 22; "
                "revenue segmen: AMMAN H1 2026 Earnings Release, hlm. 3-4. Harga/volume "
                "yang dipublikasikan dibulatkan sehingga tie-out tidak presisi; selisih tidak "
                "dianggap penyesuaian harga yang bisa diekstrapolasi ke H2. Untuk konsentrat, "
                "Cu dan Au dihitung terpisah memakai net realized metal price yang dilaporkan.")
            illustrative_pages.append({
                "halaman": 0,
                "judul": "Uji realized price terhadap revenue aktual H1",
                "layout": "stack",
                "paragraf": [_t(
                    "Volume kali harga realisasi memberi cross-check revenue tiap produk. "
                    "Selisih kecil terhadap revenue segmen berasal dari presisi publikasi "
                    "yang dibulatkan dan tidak dipakai untuk menambah atau mengurangi "
                    "asumsi H2.",
                    "Volume times realized price gives a revenue cross-check for each product. "
                    "The small gaps to segment revenue come from rounded published figures "
                    "and are not used to raise or lower the H2 assumptions.")],
                "exhibit": [h1_price_exhibit]})

            capacity = evidence.get("processing_capacity") or {}
            capacity_products = capacity.get("products") or {}
            actual_by_key = {
                _product_key(row.get("product")): row for row in
                (evidence.get("sales_production_bridge") or [])}
            guidance_map = {
                "cathode_copper": ("Katoda tembaga (kt)", 1000),
                "refined_gold": ("Emas murni (koz)", 1000),
            }
            capacity_rows = []
            for key, (guide_name, unit_multiplier) in guidance_map.items():
                cap_product = capacity_products.get(key) or {}
                actual_product = actual_by_key.get(key) or {}
                guide = next((item for item in guidance
                              if item.get("name") == guide_name and
                              item.get("value") is not None), None)
                actual_output = actual_product.get("production")
                annual_capacity = cap_product.get("annual_design_capacity")
                if not all(isinstance(value, (int, float)) for value in
                           (guide.get("value") if guide else None,
                            actual_output, annual_capacity,
                            cap_product.get("fy2025_production"))):
                    continue
                guide_output = guide["value"] * unit_multiplier
                h2_balance = guide_output - actual_output
                half_capacity = annual_capacity / 2
                needed_utilization = h2_balance / half_capacity if half_capacity else None
                unit = actual_product.get("unit") or cap_product.get("unit")
                capacity_rows.append([
                    cap_product.get("name") or key,
                    _volume_text(cap_product["fy2025_production"], unit) +
                    f" / {fmt._id(cap_product.get('fy2025_output_rate_pct'), 0)}%",
                    _volume_text(actual_output, unit),
                    _volume_text(guide_output, unit),
                    _volume_text(h2_balance, unit),
                    _volume_text(half_capacity, unit),
                    fmt.pct(needed_utilization) if needed_utilization is not None else "-",
                ])
            if capacity_rows:
                capacity_exhibit = add(
                    "Kapasitas fasilitas versus panduan produksi FY26",
                    ["Produk", "FY25 produksi / output rate", "H1 aktual", "FY26 guidance", "FY26 balance vs H1", "½ kapasitas desain", "Utilisasi H2 tersirat"],
                    capacity_rows,
                    f"Nameplate dan output rate FY2025: {capacity.get('source_title')}, "
                    f"hlm. {', '.join(str(page) for page in capacity.get('source_pages') or [])}; "
                    f"{capacity.get('source_url')}. H1 actual dan FY26 guidance: "
                    "AMMAN H1 2026 Earnings Release, hlm. 3 dan 7. Balance FY guidance "
                    "dikurangi output H1 dan utilisasi H2 dihitung analis dengan membagi "
                    "nameplate tahunan menjadi dua semester. Presentasi H1 melaporkan mill baru first ore pada pertengahan Agustus, "
                    "smelter rate Juni 93%, rate Juli-Agustus membaik/stabil, dan catatan rekor kinerja baru Juli-Agustus; "
                    "tetapi tidak memberi output bulanan Jul-Aug. "
                    "Karena itu pembagian kapasitas desain menjadi dua semester bukan jadwal aktual H2. " +
                    str(capacity.get("capacity_caveat") or ""))
                illustrative_pages.append({
                    "halaman": 0,
                    "judul": "Uji kapasitas terhadap sisa panduan produksi",
                    "layout": "stack",
                    "paragraf": [_t(
                        "Panduan logam olahan FY26 menyiratkan produksi untuk seluruh periode H2 yang lebih tinggi "
                        "daripada output H1, tetapi masih di bawah setengah kapasitas desain "
                        "tahunan. Ini mendukung kemungkinan fisik ramp-up; angka tersebut "
                        "tetap panduan produksi, bukan volume penjualan atau forecast revenue.",
                        "FY26 refined-metal guidance implies production across H2 above H1 output, "
                        "but still below half of annual design capacity. This supports the physical "
                        "feasibility of the ramp-up; the figures remain production guidance, not "
                        "sales volumes or a revenue forecast.")],
                    "exhibit": [capacity_exhibit]})

        agent_case = fc.get("interim_scenario")
        if agent_case:
            case_money = lambda value: fmt._id(value / 1e6, 1)
            measures = (("Pendapatan", "revenue"), ("EBITDA", "ebitda"),
                        ("Laba bersih", "net_profit"),
                        ("Belanja modal", "capital_expenditure"))
            lom_basis = agent_case.get("basis") == "lom_schedule"
            case_exhibit = add(
                ("FY26 dari hasil interim dan jadwal LoM" if lom_basis else
                 "Skenario FY26 berbasis hasil interim dan asumsi analis"),
                ["US$ juta", "1H26 aktual", "2H26 LoM" if lom_basis else "2H26 skenario",
                 "FY26F" if lom_basis else "FY26 skenario"],
                [[label, case_money(agent_case["h1"][key]),
                  case_money(agent_case["h2"][key]),
                  case_money(agent_case["full_year"][key])]
                 for label, key in measures],
                (f"Sumber aktual: {agent_case['source_url']} (terbit "
                 f"{agent_case['published_at']}); 2H26 dari jadwal LoM yang dinilai: katoda dan "
                 "emas murni sesuai panduan FY2026 emiten, dek harga, biaya unit, royalti, beban "
                 "umum, pajak dan PNBP 1H26. Penjualan persediaan 1H tidak dimodelkan terpisah."
                 if lom_basis else
                 f"Sumber aktual: {agent_case['source_url']} (terbit "
                 f"{agent_case['published_at']}); 2H26 adalah asumsi analis. "
                 "Rasio produksi panduan tidak sama dengan penjualan: persediaan, bauran "
                 "produk, harga realisasi, dan biaya belum direkonsiliasi. Per 24 Sep, "
                 "2H mencakup Jul-Dec; produksi/penjualan Jul-Aug belum tersedia sebagai "
                 "actual publik setelah H1 cutoff."))
            case_assumptions = agent_case["assumptions"]
            if lom_basis:
                # The ratios shown are the LoM's own 2H against the 1H actual.
                h1, h2 = agent_case["h1"], agent_case["h2"]
                case_assumptions = {
                    "h2_revenue_to_h1": h2["revenue"] / h1["revenue"] if h1["revenue"] else 0.0,
                    "h2_ebitda_margin_pct": h2["ebitda"] / h2["revenue"] * 100 if h2["revenue"] else 0.0,
                    "h2_net_margin_pct": h2["net_profit"] / h2["revenue"] * 100 if h2["revenue"] else 0.0,
                    "h2_capex_to_h1": (h2["capital_expenditure"] / h1["capital_expenditure"]
                                       if h1["capital_expenditure"] else 0.0)}
            lom_note = "Hasil jadwal LoM, bukan asumsi terpisah."
            ratio_exhibit = add(
                ("Rasio 2H26 dari jadwal LoM" if lom_basis else
                 "Asumsi eksplisit untuk skenario 2H26"),
                ["Driver", "Rasio" if lom_basis else "Asumsi", "Dasar dan batasan"],
                [["Pendapatan 2H / 1H", fmt.pct(case_assumptions["h2_revenue_to_h1"]),
                  lom_note if lom_basis else
                  "Penilaian dari realisasi 1H dan panduan tahunan; volume produksi "
                  "belum tentu sama dengan penjualan dan harga realisasi bisa berubah."],
                 ["Margin EBITDA 2H", fmt.pct(case_assumptions["h2_ebitda_margin_pct"] / 100),
                  lom_note if lom_basis else "Asumsi analis; belum ada panduan margin 2H."],
                 ["Margin laba 2H", fmt.pct(case_assumptions["h2_net_margin_pct"] / 100),
                  lom_note if lom_basis else "Asumsi analis; pajak dan bunga belum dijembatani."],
                 ["Belanja modal 2H / 1H", fmt.pct(case_assumptions["h2_capex_to_h1"]),
                  "Asumsi analis dari rencana belanja modal 2H26; sama dengan jadwal LoM."
                  if lom_basis else "Asumsi analis; jadwal capex proyek belum tervalidasi."]],
                f"Sumber: {agent_case['source_url']}; asumsi numerik adalah "
                "interpretasi analis untuk skenario internal, bukan guidance emiten.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Skenario FY26 dari rilis terbaru",
                "layout": "stack",
                "paragraf": [_t("Hasil 1H26 dan panduan operasi digunakan untuk "
                                "membentuk skenario 2H26. Konversi ke rupiah pada "
                                "halaman nilai berikutnya hanya untuk cross-check, "
                                "bukan dasar target harga.",
                                "1H26 results and operating guidance are used to "
                                "build the 2H26 scenario. The rupiah conversion on "
                                "the following value page is only a cross-check, "
                                "not the basis for a Target Price.")],
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
                     [f"Rp{fmt.rp(fmt.tick(item['per_share_idr']))}"
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
                      f"Kurs {crosscheck['fx']['date']}; harga saham Sectors "
                      f"{intake['price_date']} lebih lama."],
                     ["Saham beredar", fmt._id(crosscheck["shares"] / 1e6, 1) + " juta",
                      "Sesudah saham treasuri; dilusi berikutnya belum dimodelkan."]],
                    "Sumber: rilis interim resmi dan kurs FX bertanggal. Skenario "
                    "multiple mengabaikan umur tambang, capex LoM, dan nilai aset "
                    "terpisah; hanya cross-check internal.")
                illustrative_pages.append({
                    "halaman": 0, "judul": "Cross-check nilai FY26 dari hasil terbaru",
                    "layout": "stack",
                    "paragraf": [_t("EBITDA skenario FY26 diuji pada tiga multiple EV/EBITDA. "
                                    "Angka per saham ini sensitif pada harga komoditas, "
                                    "kurs, utang, dan multiple; bukan target harga.",
                                    "FY26 scenario EBITDA is tested at three EV/EBITDA multiples. "
                                    "These per-share figures are sensitive to commodity prices, "
                                    "the exchange rate, debt and the multiple; they are not a Target Price.")],
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
                "Riwayat keuangan dalam data Sectors",
                ["Rp miliar"] + years,
                [[label] + [cache_money(row.get(key)) for row in annual_cache]
                 for label, key in history_items],
                f"Sumber: Sectors, company/report/{ticker}, financials.historical_financials. "
                "Angka Rp historis adalah konteks terpisah dari laporan interim resmi "
                f"bermata uang {currency}; belum direkonsiliasi ke model.")
            balance_items = (("Kas", "cash"), ("Utang", "total_debt"),
                             ("Ekuitas", "equity"), ("Aset", "assets"))
            balance_exhibit = add(
                "Neraca historis dalam data Sectors", ["Rp miliar"] + years,
                [[label] + [cache_money(row.get(key)) for row in annual_cache]
                 for label, key in balance_items],
                f"Sumber: Sectors, company/report/{ticker}, financials.historical_financials; "
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
                holder_source = intake.get("major_holders_source")
                history_page_exhibits.append(add(
                    "Pemegang saham utama" + ("" if holder_source else " dalam data Sectors"),
                    ["Pemegang saham", "Porsi", "Saham (juta)"], holder_rows,
                    f"Sumber: {holder_source} (Sectors tidak memuat pemegang saham emiten ini); "
                    "komposisi dapat berbeda dari tanggal laporan interim." if holder_source else
                    f"Sumber: Sectors, company/report/{ticker}, ownership.major_shareholders; "
                    "snapshot Sectors dapat berbeda dari tanggal laporan interim."))
            illustrative_pages.append({
                "halaman": 0, "judul": "Konteks historis dan kepemilikan",
                "layout": "stack",
                "paragraf": [_t("Tabel historis berikut membantu membaca siklus operasi dan pendanaan. "
                                "Angka Sectors dalam rupiah dan angka rilis interim dalam mata uang "
                                "pelaporan ditampilkan terpisah; perbedaan definisi belum "
                                "direkonsiliasi.",
                                "The historical tables below help read the operating and funding cycle. "
                                "Sectors figures in rupiah and interim-release figures in the reporting "
                                "currency are shown separately; differences in definition are not yet "
                                "reconciled.")],
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
                "Sumber: Sectors, data tahunan; kalkulasi screen historis Sektoral "
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
                "Sumber: screen historis Sektoral dari data Sectors. Asumsi "
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
                    "Sumber: berita bertanggal dari Sectors dan/atau Tavily: " +
                    "; ".join(dict.fromkeys(event_sources)) +
                    ". Dampak numerik adalah asumsi analis, bukan fakta emiten.")
            illustrative_pages.append({
                "halaman": 0, "judul": "Skenario operasi ilustratif",
                "layout": "stack",
                "paragraf": [_t("Screen rupiah ini memperlihatkan perhitungan historis "
                                "dan perubahan driver yang ditautkan ke berita. Skenario "
                                "interim US$ pada halaman lain belum dijembatani ke model "
                                "rupiah ini.",
                                "This rupiah screen shows the historical calculation "
                                "and the driver changes linked to news. The US$ interim "
                                "scenario on another page is not yet bridged to this "
                                "rupiah model.")],
                "exhibit": page_exhibits})
            if news_assumptions:
                illustrative_pages.append({
                    "halaman": 0, "judul": "Berita dan keputusan asumsi",
                    "layout": "stack",
                    "paragraf": [_t("Setiap berita bertanggal diuji terhadap driver forecast. "
                                    "Angka nol menunjukkan berita tidak memberi dasar "
                                    "untuk mengubah asumsi operasi atau valuasi.",
                                    "Each dated news item is tested against the forecast drivers. "
                                    "A zero means the news gives no basis for changing "
                                    "operating or valuation assumptions.")],
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
                    [["Gordon perpetual", f"Rp{fmt.rp(fmt.tick(gordon))}/saham",
                      "Terminal perpetual tidak cocok untuk aset tambang berumur terbatas."],
                     ["Exit EV/EBITDA", f"Rp{fmt.rp(fmt.tick(exit_value))}/saham",
                      "Kelipatan exit belum dijembatani ke LoM per aset."],
                     ["Selisih dua metode", fmt.pct(divergence),
                      "Tidak dirata-ratakan menjadi target harga."],
                     ["WACC / pertumbuhan terminal",
                      f"{fmt.pct(va['wacc'])} / {fmt.pct(wi['g'])}",
                      f"Screen termasuk penyesuaian berita {wi.get('news_wacc_bps', 0):+g} bp; "
                      "bukan discount rate dan life aset tervalidasi."],
                     ["Porsi nilai terminal", fmt.pct(va.get("tv_share") or 0),
                      "Ketergantungan terminal tinggi mengurangi kegunaan screen."]],
                    "Sumber: Sektoral historical screening model dari data Sectors; "
                    "tidak memasukkan LoM/SOTP, jadwal proyek, dan jembatan 1H terbaru. "
                    "Tidak ada rating, target harga, atau nilai wajar produksi dari tabel ini.")
                grid = valuation_mod.gordon_screen_grid(
                    intake, fc, va["wacc"], wi["g"], wi["exit_mult"], va["net_debt"])
                grid_exhibit = add(
                    "Sensitivitas Gordon ilustratif (Rp/saham)",
                    ["WACC / g"] + [fmt.pct(rate) for rate in grid["growth_rates"]],
                    [[fmt.pct(rate)] + [
                        f"Rp{fmt.rp(fmt.tick(value))}" if value is not None else "n.m."
                        for value in values] for rate, values in grid["rows"]],
                    "Sumber: screen Gordon yang sama; bukan sensitivitas NAV tambang. "
                    "Basis pusat memakai asumsi lama dan bukan target harga.")
                illustrative_pages.append({
                    "halaman": 0, "judul": "Valuasi ilustratif dan keterbatasannya",
                    "layout": "stack",
                    "paragraf": [_t("Dua metode lama ditampilkan terpisah agar dampak asumsi "
                                    "terlihat. Metode ini belum menghitung arus kas sampai "
                                    "akhir umur tambang maupun nilai tiap aset, sehingga "
                                    "hasilnya tidak menjadi rekomendasi atau target harga.",
                                    "The two legacy methods are shown separately so the effect of the "
                                    "assumptions is visible. They do not yet compute cash flows to the "
                                    "end of mine life or the value of each asset, so the results are "
                                    "not a rating or a Target Price.")],
                    "exhibit": [value_exhibit, grid_exhibit]})

    if mining:
        bridge_exhibit = None
        release_rows = [
            ["Hasil interim resmi", ("Tersedia: " + actual["period"] + " dengan data keuangan dan operasi.")
             if actual else "Belum ada hasil interim resmi yang memenuhi tanggal laporan."],
            ["Forecast fisik", "Perlu jadwal produksi, pemrosesan dan penjualan, harga, biaya, pajak dan capex per tahun."],
            ["SOTP", "Kas, utang finansial, NCI dan saham sudah bersumber; NAV aset LoM, overhead PV, serta rekonsiliasi uang muka pelanggan ke delivery/arus kas belum tersedia."],
            ["Keputusan rilis", "Rating dan target harga ditahan sampai forecast dan SOTP dapat direkonsiliasi."]]
        chain_text = _method_chain_text(va)
        if chain_text:
            release_rows.insert(-1, ["Rantai metode", chain_text])
        sotp = va.get("sotp") or {}
        bridge = intake.get("sotp_bridge") or {}
        if sotp and bridge:
            cash_value = sotp.get("cash_idr")
            debt_value = sotp.get("debt_idr")
            minority_value = sotp.get("minority_interest_idr")
            shares_value = sotp.get("shares")
            cash_ev = bridge.get("cash_idr") or {}
            fx_text = (f"{_lom_fx_source(intake)} Rp{fmt.rp(cash_ev.get('fx_rate'))}/USD"
                       if cash_ev.get("fx_rate") else "kurs bertanggal")
            bridge_rows = [
                ["Kas dan setara kas", f"Rp{fmt._id(cash_value / 1e12, 2)} triliun" if cash_value is not None else "-",
                 f"Financial Statements 30 Jun 2026, hlm. 1; diterjemahkan pada {fx_text}."],
                ["Utang finansial", f"Rp{fmt._id(debt_value / 1e12, 2)} triliun" if debt_value is not None else "-",
                 f"Pinjaman bank neto + lease/pembiayaan; hlm. 2, 89, 98; diterjemahkan pada {fx_text}."],
                ["Kepentingan nonpengendali", f"Rp{fmt._id(minority_value / 1e12, 2)} triliun" if minority_value is not None else "-",
                 f"Financial Statements 30 Jun 2026, hlm. 3; diterjemahkan pada {fx_text}."],
                ["Saham beredar", f"{fmt._id(shares_value / 1e6, 1)} juta" if shares_value is not None else "-",
                 "Financial Statements 30 Jun 2026, hlm. 101; sesudah saham treasuri."],
                ["PV overhead korporat", "Belum tersedia",
                 "Tidak ada proyeksi overhead dan dasar kapitalisasi yang bersumber."],
                ["Uang muka pelanggan", f"US${fmt._id((bridge.get('customer_advance_excluded_usd_thousand') or 0) / 1000, 1)} juta",
                 "Tidak dimasukkan ke utang finansial; volume delivery, harga, dan alokasi arus kas kontrak belum dipetakan."],
            ]
            bridge_exhibit = add("Jembatan korporat SOTP yang terverifikasi, masih parsial",
                ["Komponen", "Nilai / status", "Basis dan batas bukti"], bridge_rows,
                "Sumber: AMMAN H1 2026 Financial Statements. Saldo keuangan per 30 Jun 2026 "
                f"diterjemahkan ke IDR memakai kurs laporan ({fx_text}); ini hanya mengisi "
                "jembatan korporat, bukan NAV aset atau target harga.")
    else:
        financial_ddm = intake.get("model_profile") == "financial_ddm"
        release_rows = [
            ["Hasil interim resmi", ("Tersedia: " + actual["period"])
             if actual else "Belum ada rilis resmi yang tervalidasi untuk tanggal laporan."],
            ["Forecast operasi", ("Perlu proyeksi laba, kredit, NIM, kualitas aset, biaya kredit, dan modal "
                                  "yang direkonsiliasi." if financial_ddm else
                                  "Perlu driver volume, harga/mix, margin, capex, modal kerja, pajak dan utang.")],
            ["Valuasi", ("Perlu DDM yang direkonsiliasi dengan payout, kebutuhan modal, dan sensitivitas CoE/g."
                         if financial_ddm else
                         "Perlu FCFF yang direkonsiliasi dan sensitivitas terminal yang konsisten.")],
            ["Keputusan rilis", "Rating dan target harga ditahan sampai seluruh pemeriksaan lolos."]]
        chain_text = _method_chain_text(va)
        if chain_text:
            release_rows.insert(-1, ["Rantai metode", chain_text])
    add("Pemeriksaan sebelum rating dan target harga",
        ["Pemeriksaan", "Bukti yang diperlukan"], release_rows,
        "Sumber: pemeriksaan rilis model Sektoral; rating dan target harga hanya "
        "dapat disajikan setelah seluruh syarat metode terpenuhi.")

    if actual:
        if mining:
            watch_rows = [
                [item.get("label") or f"Perkembangan operasi {i + 1}", item["fact"],
                 "Uji dampaknya pada volume terjual, biaya, arus kas dan nilai aset."]
                for i, item in enumerate((evidence.get("operating_context") or [])[:2])
                if item.get("fact")]
            segments = revenue_breakdown.get("segments") or []
            if segments:
                segment = max(segments, key=lambda row: row.get("current") or 0)
                segment_name = re.sub(r"^penjualan\s+", "", segment["name"], flags=re.IGNORECASE)
                watch_rows.append([
                    f"Penjualan {segment_name} H1",
                    f"Penjualan {segment_name} {money_phrase(segment.get('current'))} "
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
        operating_sources = evidence.get("operating_context") or []
        operating_source = next((item for item in operating_sources
                                if item.get("label") == "Ramp-up fasilitas hilir"), {})
        watch_source_note = f"Sumber fakta: {actual['source_title']}; "
        if operating_source.get("source_url"):
            watch_source_note += (
                f"ramp-up fasilitas: {operating_source.get('source_title')}, "
                f"hlm. {', '.join(str(page) for page in operating_source.get('source_pages') or [])}; "
                f"{operating_source['source_url']}. "
            )
        watch_source_note += "Kolom implikasi adalah analisis Sektoral dan belum menjadi asumsi valuasi."
        exhibit_ids.tag(add("Katalis, risiko, dan indikator pemantauan",
                            ["Tema", "Bukti terkini", "Implikasi yang diuji"], watch_rows,
                            watch_source_note), exhibit_ids.CATALYSTS)

    if actual:
        current = actual["metrics"]
        prior = actual.get("prior_year") or {}
        material_current = current.get("material_expense")
        material_prior = prior.get("material_expense")
        material_mix = (_t(f"Beban material naik "
                           f"{pct_change(material_current, material_prior)} ke "
                           f"{fmt.pct(material_current/current['revenue'])} dari pendapatan "
                           f"({prior.get('period', 'periode pembanding')}: "
                           f"{fmt.pct(material_prior/prior['revenue'])}), "
                           "menahan margin EBITDA meski aktivitas naik. ",
                           f"Material costs rose "
                           f"{pct_change(material_current, material_prior)} to "
                           f"{fmt.pct(material_current/current['revenue'])} of revenue "
                           f"({prior.get('period', 'the comparison period')}: "
                           f"{fmt.pct(material_prior/prior['revenue'])}), "
                           "holding back EBITDA margin despite higher activity. ")
                        if material_current is not None and material_prior and
                        current.get("revenue") and prior.get("revenue") else "")
        last_annual_year = max(annual_by_year) if annual_by_year else None
        prior_full = annual_by_year.get(last_annual_year) or {}
        runrate = (_t(f"Pendapatan {actual['period']} mencapai "
                      f"{fmt.pct(current['revenue']/prior_full['revenue'])} dari "
                      f"FY{last_annual_year}; perbandingan ini bukan pengganti "
                      f"uji terhadap forecast {f_labels[0]}. ",
                      f"{actual['period']} revenue reached "
                      f"{fmt.pct(current['revenue']/prior_full['revenue'])} of "
                      f"FY{last_annual_year}; the comparison is no substitute for "
                      f"a test against the {f_labels[0]} forecast. ")
                   if current.get("revenue") and prior_full.get("revenue") else "")
        financial_fact_labels = (
            (_t("pendapatan", "revenue"), "revenue"), ("EBITDA", "ebitda"),
            (_t("laba usaha", "operating profit"), "operating_profit"),
            (_t("laba bersih", "net profit"), "net_profit"),
        )
        lead_facts = []
        for label, key in financial_fact_labels:
            value = current.get(key)
            if value is None:
                continue
            lead_facts.append(
                _change_sentence(label, value, prior.get(key), actual["period"],
                                 prior.get("period", _t("periode pembanding", "the comparison period")),
                                 money_phrase))
        lead = (_t(f"{ticker} menerbitkan hasil {actual['period']} pada {actual['published_at']}. ",
                   f"{ticker} published {actual['period']} results on {actual['published_at']}. ") +
                " ".join(lead_facts[:3]) + " " + f"{material_mix}{runrate}").strip()
        operating = evidence.get("operating_context") or []
        driver = (prose_lang.source(operating[0]["fact"]) if operating else
                  _t("Rincian driver operasional belum tervalidasi.",
                     "Operating driver detail is not yet validated."))
        if revenue_breakdown and not mining:
            segment = (revenue_breakdown.get("segments") or [None])[0]
            customer_rows = revenue_breakdown.get("major_customers") or []
            segment_text = (_t(f"Segmen {segment['name']} tumbuh "
                               f"{pct_change(segment.get('current'), segment.get('prior'))} "
                               f"ke {money_phrase(segment.get('current'))}. ",
                               f"The {prose_lang.source(segment['name'])} segment grew "
                               f"{pct_change(segment.get('current'), segment.get('prior'))} "
                               f"to {money_phrase(segment.get('current'))}. ")
                            if segment else "")
            customer_names = _t(" dan ", " and ").join(row["name"] for row in customer_rows[:2])
            customer_text = (_t(
                f"Pelanggan {customer_names} menyumbang "
                f"{fmt.pct(sum(c.get('current') or 0 for c in customer_rows) / current['revenue'])} "
                f"pendapatan {actual['period']}; konsentrasi pelanggan ini menjadi "
                "risiko volume dan piutang. ",
                f"Customers {customer_names} contributed "
                f"{fmt.pct(sum(c.get('current') or 0 for c in customer_rows) / current['revenue'])} "
                f"of {actual['period']} revenue; this customer concentration is a "
                "volume and receivables risk. ")
                if customer_rows and current.get("revenue") else "")
        else:
            segment_text = customer_text = ""
        milestone = (prose_lang.source(operating[1]["fact"]) + " " if len(operating) > 1 else "")
        if mining:
            segments = revenue_breakdown.get("segments") or []
            largest = max(segments, key=lambda row: row.get("current") or 0) if segments else None
            mix_text = (_t(
                f"{largest['name']} menyumbang {money_phrase(largest.get('current'))} "
                f"atau {fmt.pct(largest['current'] / current['revenue'])} dari "
                f"pendapatan {actual['period']}. ",
                f"{prose_lang.source(largest['name'])} contributed {money_phrase(largest.get('current'))} "
                f"or {fmt.pct(largest['current'] / current['revenue'])} of "
                f"{actual['period']} revenue. ")
                if largest and largest.get("current") is not None and current.get("revenue") else "")
            lom_published = ((va.get("method_chain") or {}).get("selected") == "sotp_lom"
                             and str((va.get("release") or {}).get("status") or "")
                             .startswith("distributable"))
            outlook = (f"{driver} {milestone}{mix_text}"
                       + (_t("Proyeksi umur aset di halaman valuasi dibangun dari cadangan, "
                             "kapasitas pabrik dan smelter, biaya unit, royalti dan pajak resmi; "
                             "yang tidak diungkapkan emiten (capex Elang, laju sesudah izin ekspor "
                             "berakhir) adalah asumsi analis berlabel.",
                             "The asset-life projection on the valuation page is built from reserves, "
                             "plant and smelter capacity, unit costs, and official royalties and taxes; "
                             "what the issuer does not disclose (Elang capex, the rate after the export "
                             "permit expired) is a labelled Analyst Assumption.")
                          if lom_published else
                          _t("Jembatan produksi, persediaan, penjualan, harga realisasi, "
                             "biaya dan capex per tahun belum lengkap untuk membangun "
                             "proyeksi umur aset.",
                             "The annual bridge of production, inventory, sales, realized prices, "
                             "costs and capex is not yet complete enough to build an "
                             "asset-life projection.")))
        else:
            outlook = (f"{driver} {segment_text}{milestone}{customer_text}" +
                       _t("Forecast memerlukan driver pendapatan dan biaya, capex, modal kerja, "
                          "pajak dan utang yang dapat ditelusuri ke sumber dan tahun fiskal.",
                          "A forecast needs revenue and cost drivers, capex, working capital, "
                          "tax and debt that can be traced to a source and a fiscal year."))
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
                net_debt_text = _t(f"utang bersih {money_phrase(debt - cash)}",
                                   f"net debt of {money_phrase(debt - cash)}")
                debt_label = (_t("utang finansial (pinjaman bank dan lease/pembiayaan)",
                                 "financial debt (bank loans and leases/financing)")
                              if balance.get("debt_scope") else
                              _t("pinjaman berbunga", "interest-bearing borrowings"))
                position_text = _t(f"Kas {money_phrase(cash)} dan {debt_label} "
                                   f"{money_phrase(debt)} menyiratkan {net_debt_text}.",
                                   f"Cash of {money_phrase(cash)} and {debt_label} of "
                                   f"{money_phrase(debt)} imply {net_debt_text}.")
            else:
                cash_text = (money_phrase(cash) if cash is not None else
                             _t("belum tersedia", "not yet available"))
                debt_text = (money_phrase(debt) if debt is not None else
                             _t("belum tersedia", "not yet available"))
                position_text = _t(f"Kas {cash_text}; pinjaman berbunga {debt_text}; "
                                   "utang bersih belum dapat dihitung dari data yang tersedia.",
                                   f"Cash {cash_text}; interest-bearing borrowings {debt_text}; "
                                   "net debt cannot yet be computed from the available data.")
            equity = balance.get("total_equity")
            equity_text = (money_phrase(equity) if equity is not None else
                           _t("belum tersedia", "not yet available"))
            valuation_text = (
                _t(f"{position_text} Per {balance.get('period_end', 'tanggal laporan')}. "
                   f"Ekuitas tercatat {equity_text}. ",
                   f"{position_text} As of {balance.get('period_end', 'the report date')}. "
                   f"Book equity {equity_text}. ") +
                (_t("SOTP yang dapat dipakai sebagai target masih memerlukan NAV LoM "
                    "tiap aset material, jadwal arus kas dan capex per aset, serta PV "
                    "overhead korporat. Uang muka pelanggan Glencore US$388,4 juta "
                    "dicatat terpisah dari utang finansial dan belum direkonsiliasi "
                    "ke volume delivery/arus kas. ",
                    "A SOTP usable for a target still needs a LoM NAV for each material "
                    "asset, cash-flow and capex schedules per asset, and the PV of corporate "
                    "overhead. The US$388,4 juta Glencore customer advance is recorded "
                    "separately from financial debt and is not yet reconciled to delivery "
                    "volumes/cash flows. ") if mining else
                 _t("DCF FCFF yang dapat dipakai sebagai target memerlukan jadwal utang dan "
                    "bunga, capex, perubahan modal kerja, serta proyeksi operasi yang "
                    "terhubung. Selisih nilai Gordon dan exit multiple pada screen lama "
                    "belum direkonsiliasi. ",
                    "An FCFF DCF usable for a target needs debt and interest schedules, "
                    "capex, working-capital changes and a linked operating projection. "
                    "The gap between the Gordon and exit-multiple values in the legacy "
                    "screen is not yet reconciled. ")) +
                _t("Karena itu rating dan Target Harga masih ditahan; tabel halaman "
                   "valuasi mencatat bukti yang kurang.",
                   "The rating and Target Price are therefore held; the table on the "
                   "valuation page lists the missing evidence."))
        else:
            valuation_text = _t("Data aktual yang tersedia belum cukup untuk "
                                "menerbitkan nilai wajar atau rekomendasi produksi. "
                                "Pemeriksaan yang belum selesai tercantum pada halaman valuasi.",
                                "The available actuals are not yet enough to publish a "
                                "production fair value or rating. "
                                "The outstanding checks are listed on the valuation page.")
        first_bullet = _change_sentence(_t("pendapatan", "revenue"), current.get("revenue"),
                                        prior.get("revenue"), actual["period"],
                                        prior.get("period", _t("periode pembanding",
                                                               "the comparison period")),
                                        money_phrase)
        if mining:
            segments = revenue_breakdown.get("segments") or []
            segment_facts = ", ".join(
                f"{prose_lang.source(row['name'])} {money_phrase(row.get('current'))}"
                for row in segments if row.get("current") is not None)
            composition = (
                _t(f"Rincian penjualan {actual['period']} mencatat {segment_facts}. "
                   "Bauran produk dan waktu penjualan perlu dijembatani ke realisasi "
                   "harga sebelum menjadi forecast tahunan.",
                   f"The {actual['period']} sales breakdown records {segment_facts}. "
                   "Product mix and sales timing need to be bridged to realized "
                   "prices before they become an annual forecast.")
                if segment_facts else
                _t("Rincian produk dan penjualan belum cukup untuk menjembatani "
                   "perubahan volume ke pendapatan tahunan.",
                   "The product and sales breakdown is not yet enough to bridge "
                   "volume changes to annual revenue."))
            cash_facts = []
            for label, key in ((_t("Belanja modal", "Capex"), "capital_expenditure"),
                               (_t("arus kas operasi", "operating cash flow"), "operating_cash_flow")):
                value = current.get(key)
                if value is not None:
                    cash_facts.append(f"{label} {money_phrase(value)} "
                                      f"({pct_change(value, prior.get(key))} yoy)")
            cash_line = "; ".join(cash_facts)
            cash_text = (cash_line[:1].upper() + cash_line[1:] + ". "
                         if cash_line else "")
            margin_text = (
                _t(f"Margin EBITDA {fmt.pct(current['ebitda'] / current['revenue'])} "
                   f"({actual['period']}) dibanding "
                   f"{fmt.pct(prior['ebitda'] / prior['revenue'])} "
                   f"({prior.get('period', 'periode pembanding')}). ",
                   f"EBITDA margin {fmt.pct(current['ebitda'] / current['revenue'])} "
                   f"({actual['period']}) versus "
                   f"{fmt.pct(prior['ebitda'] / prior['revenue'])} "
                   f"({prior.get('period', 'the comparison period')}). ")
                if current.get("ebitda") is not None and current.get("revenue") and
                prior.get("ebitda") is not None and prior.get("revenue") else "")
            result_paragraphs = [composition,
                margin_text + cash_text +
                _t("Jadwal produksi, capex, modal kerja dan pembayaran utang masih "
                   "diperlukan untuk menilai keberlanjutan arus kas.",
                   "Production, capex, working-capital and debt-repayment schedules are "
                   "still needed to judge whether cash flow is sustainable.")]
            second_bullet = _trim(driver, 30)
        else:
            result_paragraphs = [
                _t("Angka interim menunjukkan hasil yang dilaporkan untuk periode tersebut, "
                   "tetapi tidak dengan sendirinya menetapkan lintasan tahunan. Perubahan "
                   "mix, biaya, modal kerja dan unsur non-operasional perlu direkonsiliasi "
                   "dengan laporan sebelum forecast dibuat.",
                   "The interim figures show the reported results for the period, "
                   "but do not by themselves set the annual trajectory. Changes in "
                   "mix, costs, working capital and non-operating items need to be reconciled "
                   "with prior reports before a forecast is made."),
                _t("Bukti yang tersedia belum menyediakan jembatan terukur dari volume, "
                   "harga atau mix ke margin, capex dan arus kas. Driver tersebut tetap "
                   "ditandai belum terverifikasi dan tidak diisi dari CAGR historis.",
                   "The available evidence does not yet provide a measurable bridge from volume, "
                   "price or mix to margins, capex and cash flow. Those drivers stay "
                   "flagged as unverified and are not filled from historical CAGR.")]
            second_bullet = _t("Pisahkan driver pendapatan, biaya, modal kerja dan capex "
                               "sebelum hasil interim diterjemahkan menjadi forecast.",
                               "Separate the revenue, cost, working-capital and capex drivers "
                               "before interim results are turned into a forecast.")
    else:
        lead = _t("Hasil interim terbaru dan tanggal publikasi belum dapat "
                  "dibuktikan dari data yang tersedia.",
                  "The latest interim results and their publication date cannot yet "
                  "be verified from the available data.")
        outlook = _t("Driver operasi, capex dan arus kas perlu diverifikasi sebelum "
                     "forecast dan valuasi diterbitkan.",
                     "Operating drivers, capex and cash flow need verifying before "
                     "a forecast and valuation are published.")
        valuation_text = _t("Data aktual yang tersedia belum cukup untuk "
                            "menerbitkan nilai wajar atau rekomendasi produksi.",
                            "The available actuals are not yet enough to publish a "
                            "production fair value or rating.")
        first_bullet = _t("Hasil interim resmi terbaru belum tervalidasi.",
                          "The latest official interim results are not yet validated.")
        result_paragraphs = []
        second_bullet = _t("Driver operasi dan arus kas masih perlu verifikasi.",
                           "Operating drivers and cash flow still need verification.")

    sections = [
        {"halaman": 2, "judul": "Hasil terbaru dan jembatan laba",
         "layout": "stack", "paragraf": [lead] + result_paragraphs,
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Hasil interim resmi dan perubahan yoy",
                      "Baris kuartalan dalam data lokal",
                      "Rasio yang menjelaskan kualitas hasil"}]},
        {"halaman": 3, "judul": "Operasi dan posisi keuangan",
         "layout": "stack", "paragraf": [outlook],
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Posisi neraca interim",
                      "Jembatan pendapatan menurut layanan dan pelanggan",
                      f"Komposisi pendapatan {actual['period']}" if actual else "",
                      "Metrik operasi dan pemrosesan",
                      f"Panduan produksi {guidance_period} dari manajemen" if guidance and actual else ""}]},
        {"halaman": 4, "judul": "Valuasi dan kelengkapan bukti",
         "layout": "stack",
         "paragraf": [valuation_text],
         "exhibit": [e for e in exhibits if e["judul"] in
                     {"Pemeriksaan sebelum rating dan target harga",
                      "Katalis, risiko, dan indikator pemantauan"}]},
    ]
    if mining:
        sections.insert(2, {
            "halaman": 4, "judul": "Cadangan, jadwal proyek, dan biaya",
            "layout": "stack",
            "paragraf": [_t(
                "Rilis terbaru memberi basis reserve/resource dan tonggak umur tambang, "
                "serta beberapa biaya unit aktual. Seri resmi cash cost berubah dari "
                "US$14,68/lb pada H1 2025 menjadi negatif US$0,58/lb pada H1 2026, "
                "bersamaan dengan perubahan besar pada kredit by-product; angka H1 2026 "
                "bukan run-rate biaya ke depan. Presentasi H1 menyebut rencana "
                "tambang masih disusun, sementara perizinan koridor OLC dan pemilihan "
                "kontraktor early engineering masih berjalan. Presentasi FY2025 "
                "menyatakan feasibility study Elang selesai, dengan optimasi teknis "
                "masih berlangsung. Annual Report 2025 menyebut operasi Elang "
                "berlanjut setidaknya sampai 2050. Pengumuman scoping AMDAL September "
                "menambahkan skala rencana penambangan bijih sekitar 90 Mt/tahun dan "
                "lingkup infrastruktur awal, tetapi belum memberi jadwal produksi tahunan. "
                "Panjang OLC 54 km versus 60 km belum direkonsiliasi. Data publik tersebut belum "
                "memuat jadwal produksi tahunan, biaya per aset, capex Elang, atau "
                "FCFF untuk NAV LoM.",
                "The latest release gives a reserve/resource basis and mine-life milestones, "
                "plus some actual unit costs. The official cash-cost series moved from "
                "US$14,68/lb in H1 2025 to negative US$0,58/lb in H1 2026, "
                "alongside a large change in by-product credits; the H1 2026 figure "
                "is not a forward cost run-rate. The H1 presentation says the mine "
                "plan is still being prepared, while OLC corridor permitting and the selection "
                "of an early-engineering contractor are under way. The FY2025 presentation "
                "states that the Elang feasibility study is complete, with technical optimisation "
                "still in progress. The 2025 Annual Report says Elang operations "
                "continue until at least 2050. The September AMDAL scoping announcement "
                "adds a planned ore-mining scale of about 90 Mt/year and the "
                "initial infrastructure scope, but no annual production schedule yet. "
                "The OLC length of 54 km versus 60 km is not yet reconciled. The public data do not yet "
                "contain an annual production schedule, per-asset costs, Elang capex, or "
                "FCFF for a LoM NAV.")],
            "exhibit": [e for e in exhibits if e["judul"] in {
                "Cadangan dan sumber daya mineral",
                "Biaya unit historis dan pelunasan utang Q3",
                "Biaya operasi historis per setengah tahun",
                "Jembatan unit cash cost per pon Cu terjual"}]})
        schedule_exhibit = next((e for e in exhibits if e["judul"] ==
                                 "Jadwal operasi dan status pengembangan tambang"), None)
        if amdal_scope_exhibit:
            sections.insert(3, {
                "halaman": 6, "judul": "Elang: skala tambang dan infrastruktur pada tahap AMDAL",
                "layout": "stack",
                "paragraf": [
                    _t("Pengumuman ini memberi batas skala awal untuk menguji konsistensi rancangan, bukan untuk membentuk lintasan throughput atau capex. Perbedaan panjang conveyor dan tidak adanya jadwal tambang membuat FCFF Elang belum dapat dihitung dari angka ini.",
                       "The announcement gives an initial scale boundary for testing the design's consistency, not for building a throughput or capex trajectory. The difference in conveyor length and the absence of a mine schedule mean Elang FCFF cannot yet be computed from these figures.")],
                "exhibit": [amdal_scope_exhibit]})
        if schedule_exhibit:
            sections.insert(4, {
                "halaman": 5, "judul": "Jadwal operasi dan status pengembangan tambang",
                "layout": "stack",
                "paragraf": [_t(
                    "Jadwal ini merangkum tonggak publik, bukan jadwal produksi atau "
                    "arus kas tahunan yang tervalidasi. Elang masih memerlukan studi, "
                    "optimasi teknis, perizinan, dan keputusan investasi; angka "
                    "investasi indikatif belum dimasukkan ke valuasi.",
                    "This schedule summarises public milestones, not a validated annual "
                    "production or cash-flow schedule. Elang still needs studies, "
                    "technical optimisation, permits and an investment decision; the "
                    "indicative investment figure is not yet included in the valuation.")],
                "exhibit": [schedule_exhibit]})
        if bridge_exhibit:
            sections.insert(5, {
                "halaman": 5, "judul": "Jembatan korporat untuk SOTP",
                "layout": "stack",
                "paragraf": [_t(
                    "Kas, utang finansial, kepentingan nonpengendali dan saham beredar "
                    "kini memiliki input bersumber. Jembatan ini masih parsial: PV "
                    "overhead dan NAV aset belum tersedia; uang muka Glencore perlu "
                "dipetakan ke kewajiban delivery sebelum net debt final.",
                    "Cash, financial debt, non-controlling interests and shares outstanding "
                    "now have sourced inputs. The bridge is still partial: the PV of "
                    "overhead and the asset NAVs are not yet available; the Glencore advance "
                    "needs mapping to delivery obligations before net debt is final.")],
                "exhibit": [bridge_exhibit]})
        if inventory_sales_section:
            sections.insert(2, inventory_sales_section)
        if physical_sales_section:
            sections.insert(2, physical_sales_section)
        if royalty_section:
            sections.insert(2, royalty_section)
        if capex_section:
            sections.insert(2, capex_section)
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
        _vb = _selected_ddm_detail(va)
        wi = va["wacc_inputs"]
        add("Komponen Cost of Equity", ["Komponen", "Nilai"],
            [["Jalur CAPM:", ""],
             ["Risk-free rate IDR (house policy)", fmt.pct(wi["rf"])],
             ["Beta (kebijakan analis)", fmt.mult(wi["beta"])],
             ["Equity Risk Premium (kebijakan analis)", fmt.pct(wi["erp"])],
             ["(=) Cost of Equity dipakai", fmt.pct(wi["re"])],
             ["Jalur band (pola rentang CoE):", ""],
             ["CoE mean 5 tahun", "n.a. (tanpa histori CoE di data Sectors)"],
             ["CoE SD 5 tahun", "n.a. (tanpa histori CoE di data Sectors)"],
             ["Offset dari mean", "n.a.: dipakai hasil CAPM"]],
            "Source: Company, Sektoral Estimates; Rf, beta dan ERP mengikuti parameter house policy, "
            "bukan data Bloomberg/Damodaran. Yield INDOGB bertanggal ditampilkan terpisah.")

        _cg_rows = []
        for _d in (-0.01, -0.005, 0.0, 0.005, 0.01):
            _cg_rows.append(
                [f"CoE {fmt.pct(_re + _d)}" + (" (base)" if _d == 0 else "")] +
                [fmt.rp(fmt.tick(ddm.value_bank(
                    _nets, None, intake.get("dps_hist") or [],
                    intake["shares"], _re + _d, _gg, _roae,
                    _bvps)["tp_gordon"])) +
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
                [fmt.rp(fmt.tick(((_rr - _g) / (_re + _d - _g)) * _bvps))
                 for _rr in (_roae - 0.04, _roae, _roae + 0.04)])
        add("Sensitivitas Inverse CoE (CoE x ROE)",
            ["CoE / ROE"] + [f"ROE {fmt.pct(_rr)}" for _rr in
                             (_roae - 0.04, _roae, _roae + 0.04)],
            _cr_rows,
            "Source: Sektoral Estimates; sel = P/BV wajar x BVPS; "
            "Fair P/BV = (ROE-g)/(CoE-g)")

        _roe_tr = (_t("naik", "rises") if _roe_h and _roae >= _roe_h[0] else
                   _t("melandai", "eases"))
        ddm_summary = _bank_ddm_summary(_vb)
        ddm_paragraphs = []
        if ddm_summary:
            ddm_paragraphs.append(_t(
                f"Driver utama valuasi bank ini adalah lintasan ROE, bukan arus kas: "
                f"ROAE historis {fmt.pct(_roe_h[0]) if _roe_h else '-'} {_roe_tr} ke {fmt.pct(_roae)} "
                f"forward bila laba {(F[0]['label'] if F else 'FY26F')} tercapai. "
                f"{ddm_summary} {intake.get('dps_basis')}.",
                f"The main driver of this bank's valuation is the ROE trajectory, not cash flow: "
                f"historical ROAE of {fmt.pct(_roe_h[0]) if _roe_h else '-'} {_roe_tr} to {fmt.pct(_roae)} "
                f"forward if {(F[0]['label'] if F else 'FY26F')} earnings are delivered. "
                f"{ddm_summary} {prose_lang.source(intake.get('dps_basis'))}."))
        sections.append({
            "halaman": len(sections) + 2,
            "judul": "Skenario nilai",
            "layout": "stack",
            "paragraf": ddm_paragraphs,
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
        method_label = _chain_cover_label(va, "DDM (dividen, Rp)")
    elif mining:
        method_label = ("SOTP/LoM menunggu; DCF screen internal"
                        if illustrative_pages else
                        _chain_cover_label(va, "SOTP/LoM (belum lengkap)"))
    else:
        method_label = _chain_cover_label(va, "DCF FCFF (belum lengkap)")

    catatan = [
        _t("DRAFT NON-DISTRIBUTABLE: rating dan target harga belum disajikan.",
           "DRAFT NON-DISTRIBUTABLE: no rating or Target Price is presented yet."),
        _t(f"Hasil interim {actual.get('period', 'terbaru')} memakai sumber resmi "
           "bila tersedia; forecast tidak diturunkan otomatis dari CAGR historis.",
           f"{actual.get('period', 'Latest')} interim results use official sources "
           "where available; the forecast is not derived automatically from historical CAGR."),
        _t("Tanda '-' berarti angka tidak tersedia atau belum tervalidasi, bukan nol.",
           "A dash (-) means the figure is not available or not yet validated, not zero."),
    ]
    if market_rail.get("adtv") is not None:
        catatan.append(_t(
            f"ADTV adalah rata-rata nilai transaksi 90 hari berdasarkan {market_rail['adtv_count']} "
            f"observasi dari {market_rail.get('adtv_source') or 'cache'} sampai {market_rail['adtv_end']}.",
            f"ADTV is the 90-day average traded value, based on {market_rail['adtv_count']} "
            f"observations from {market_rail.get('adtv_source') or 'cache'} to {market_rail['adtv_end']}."))
    if market_rail.get("public_ownership") is not None:
        catatan.append(_t("Porsi pemegang 'Public' adalah kategori kepemilikan dari snapshot cache, bukan angka free float terverifikasi.",
                          "The 'Public' holder share is an ownership category from the cached snapshot, not a verified free-float figure."))
    if illustrative_pages:
        catatan.append(_t(
            "Skenario ilustratif memakai proksi historis dan metode perpetual/exit; "
            "hasilnya bukan forecast produksi, NAV umur tambang atau target harga.",
            "Illustrative scenarios use historical proxies and perpetual/exit methods; "
            "the results are not a production forecast, a mine-life NAV or a Target Price."))
    if method != "auto":
        method_label_en = {"DDM (dividen, Rp)": "DDM (dividends, Rp)",
                           "DCF (FCFF, Rp)": "DCF (FCFF, Rp)",
                           "RNAV LoM (Rp)": "RNAV LoM (Rp)",
                           "SOTP/LoM menunggu; DCF screen internal":
                               "SOTP/LoM pending; internal DCF screen",
                           "SOTP/LoM (belum lengkap)": "SOTP/LoM (incomplete)",
                           "DCF FCFF (belum lengkap)": "FCFF DCF (incomplete)"}.get(method_label)
        catatan.insert(0, _t(f"metode valuasi dipilih analis: {method_label}.",
                             f"Valuation method selected by the analyst: "
                             f"{method_label_en or prose_lang.source(method_label)}."))

    return {
        "meta": {"ticker": ticker, "emiten": intake["name"],
                 "tanggal": intake["as_of"], "harga": intake["price"],
                 "harga_tanggal": intake["price_date"],
                 "status": "draft_non_distributable",
                 "illustrative_scenarios": bool(illustrative_pages),
                 "status_rating": "Dalam peninjauan",
                 "research_status": (intake.get("research_analysis_status") or {}).get("status", "missing")},
        "cover": {"headline": (
                    (_t("Pendapatan Interim Naik, SOTP Menunggu Bukti",
                        "Interim Revenue Up, SOTP Awaits Evidence") if
                     actual and (actual.get("prior_year") or {}).get("revenue") and
                     actual["metrics"].get("revenue", 0) > actual["prior_year"]["revenue"] else
                     _t("Hasil Interim Terbit, SOTP Menunggu Bukti",
                        "Interim Results Out, SOTP Awaits Evidence")) if mining else
                    _t("Hasil Terbaru Menunggu Model Lengkap",
                       "Latest Results Await a Complete Model")),
                  "bullets": [first_bullet,
                              second_bullet,
                              (_t("Skenario angka di halaman berikut adalah ilustrasi internal, "
                                  "bukan target harga atau rekomendasi.",
                                  "The scenario figures on the following pages are internal illustrations, "
                                  "not a Target Price or a rating.") if illustrative_pages else
                               _t("Rating dan target harga menunggu forecast serta valuasi yang tervalidasi.",
                                  "The rating and Target Price await a validated forecast and valuation."))],
                  "paragraf": [
                      {"judul": "Hasil terbaru memberi titik awal", "isi": lead},
                      {"judul": "Driver operasi perlu diuji", "isi": outlook},
                      {"judul": "Valuasi menunggu rekonsiliasi", "isi": valuation_text}],
                  "data_pasar": {"harga": intake["price"],
                                  "saham": shares_outstanding or intake["shares"],
                                  "market_cap": intake["price"] *
                                  (shares_outstanding or intake["shares"]),
                                  "adtv": (f"{fmt.miliar(market_rail['adtv'])}"
                                           + (f" (s.d. {market_rail['adtv_end']})"
                                              if market_rail.get("adtv_end") else ""))
                                  if market_rail.get("adtv") is not None else "-",
                                  "public_ownership": (fmt.pct(market_rail["public_ownership"])
                                                       if market_rail.get("public_ownership") is not None else "-")},
                   "key_financials": key_rows},
        "bagian": sections,
        "tabel_asumsi": [], "exhibits": exhibits,
        "log_gate": {"S1": s1.get("S1", {}), "S2": fc.get("s2", {}),
                     "S3": {},
                     "release": {"status": "draft_non_distributable",
                                 "blocker_count": len(blockers),
                                 "blockers": blockers}},
        "method": method_label,
        "method_select": method_select,
        "holders": [],
        "catatan_metodologi": catatan,
    }


def _lom_exhibits(intake, va, detail):
    """SOTP/LoM page: asset NAVs to equity, LoM schedule by phase, sensitivity,
    and every input with its source or analyst label."""
    lom_res = detail["lom"]
    inp, base, fx = lom_res["inputs"], lom_res["base"], lom_res["fx"]
    sotp = detail["sotp"]
    b = lom_res["bridge_idr"]
    usd = lambda v: fmt._id(v / 1e6, 0)
    bn = lambda v: fmt._id(v / 1e9, 0)
    risk = inp["elang_risk"]
    nav_bh, nav_el = base["nav"]["bh"], base["nav"]["elang"]
    per_share = sotp["target_price_idr"]
    rows = [
        ["NAV Batu Hijau (pit, stockpile, pabrik, smelter, PMR)", usd(nav_bh), bn(nav_bh * fx),
         f"LoM DCF USD, WACC {fmt.pct(inp['discount'])}"],
        ["NAV Elang sebelum risiko", usd(nav_el), bn(nav_el * fx),
         f"sampai {int(inp['licence_end'])}; capex dari riset broker"],
        [f"NAV Elang x probabilitas pengembangan {fmt.pct(risk)}", usd(nav_el * risk),
         bn(nav_el * risk * fx), "pra-FID; asumsi analis"],
    ]
    # With a working-capital schedule the product inventory is inside the LoM
    # cash flows (lom.value), so it is not added again at book value.
    inventory = 0.0 if inp.get("wc") else (inp["inventory_usd"] or 0.0)
    if not inp.get("wc"):
        rows.append(["Persediaan logam dan konsentrat", usd(inventory), bn(inventory * fx),
                     "nilai buku 30 Jun 2026"])
    rows += [
        # Template Option C rows: ownership, sum of NAV and the discount to RNAV.
        ["Porsi kepemilikan emiten atas aset", "100%", "100%",
         "aset dikonsolidasi; kepentingan nonpengendali dikurangkan di bawah"],
        ["Jumlah NAV aset", usd(nav_bh + nav_el * risk + inventory),
         bn((nav_bh + nav_el * risk + inventory) * fx), ""],
        ["(-) PV overhead korporat", f"({usd(base['overhead_usd'])})",
         f"({bn(base['overhead_usd'] * fx)})", "beban umum 1H26 x2"],
        ["(+) Kas", usd(b["cash"] / fx), bn(b["cash"]), "neraca 30 Jun 2026"],
        ["(-) Utang finansial", f"({usd(b['debt'] / fx)})", f"({bn(b['debt'])})",
         "neraca 30 Jun 2026"],
        ["(-) Kepentingan nonpengendali", f"({usd(b['minority'] / fx)})",
         f"({bn(b['minority'])})", "neraca 30 Jun 2026"],
        ["Nilai ekuitas", usd(sotp["equity_value_idr"] / fx), bn(sotp["equity_value_idr"]), ""],
        ["Diskon terhadap RNAV", "0,0%", "0,0%",
         "tidak diterapkan; risiko Elang sudah lewat probabilitas pengembangan"],
        ["Nilai per saham (Rp)", "-", f"Rp{fmt.rp(fmt.tick(per_share))}",
         f"{fmt._id(b['shares'] / 1e9, 2)} miliar saham"],
    ]
    sotp_table = {"n": 0, "judul": "SOTP/LoM: nilai aset ke ekuitas", "tipe": "tabel",
                  "data": {"cols": ["Komponen", "US$ juta", "Rp miliar", "Basis"], "rows": rows},
                  "catatan_sumber": (
                      f"Sumber: cadangan, kapasitas, biaya unit dan neraca dari rilis dan laporan "
                      f"keuangan 1H26 AMMAN; semua konversi memakai satu kurs Rp{fmt.rp(fx)}/USD "
                      f"({_lom_fx_source(intake)}); dek harga "
                      f"{inp.get('deck_basis') or 'rata-rata 12 bulan'}; capex Elang dari "
                      f"{inp['assumptions'].get('broker_source_title')} "
                      f"({inp['assumptions'].get('broker_source_date')}), asumsi analis.")}
    flows = base["flows"]

    def phase(label, pick, capex_only=False):
        chosen = [f for f in flows if pick(f)]
        if not chosen:
            return None
        years = sorted({f["year"] for f in chosen})
        span = f"{years[0]}" + (f"-{years[-1]}" if years[-1] != years[0] else "")
        avg = (lambda k: sum(f[k] for f in chosen) / (len(years) if not capex_only else 1))
        return [f"{label} ({span})", fmt._id(avg("feed_mt"), 1), fmt._id(avg("cathode_t") / 1e3, 0),
                fmt._id(avg("refined_oz") / 1e3, 0), fmt._id(avg("conc_cu_t") / 1e3, 0),
                usd(avg("revenue")), usd(avg("ebitda")), usd(avg("capex")), usd(avg("fcff"))]

    phases = [
        phase("2H26 Batu Hijau, panduan FY", lambda f: f["asset"] == "bh" and f["year"] == 2026),
        phase("Pit Batu Hijau, per tahun", lambda f: f["asset"] == "bh" and "pit" in f["kinds"]
              and f["year"] > 2026),
        phase("Stockpile Batu Hijau, per tahun", lambda f: f["asset"] == "bh"
              and "stockpile" in f["kinds"] and "pit" not in f["kinds"]),
        phase("Capex Elang, total", lambda f: "development" in f["kinds"],
              capex_only=True),
        phase("Produksi Elang, per tahun", lambda f: f["asset"] == "elang"
              and "pit" in f["kinds"]),
    ]
    schedule = {"n": 0, "judul": "Jadwal LoM per fase", "tipe": "tabel",
                "data": {"cols": ["Fase", "Umpan (Mt)", "Katoda (kt)", "Emas murni (koz)",
                                  "Cu konsentrat (kt)", "Pendapatan (US$ juta)",
                                  "EBITDA (US$ juta)", "Capex (US$ juta)", "FCFF (US$ juta)"],
                         "rows": [r for r in phases if r]},
                "catatan_sumber": (
                    f"Sumber: umpan pabrik {fmt._id(inp['plant_mtpa'], 0)} Mtpa berurutan (pit, "
                    "stockpile, lalu Elang); recovery Cu "
                    f"{fmt.pct(inp['recovery_cu'])} dan Au {fmt.pct(inp['recovery_au'])} tersirat "
                    "dari 1H26; smelter 220 kt dan PMR 579 koz x utilisasi Juni 2026 "
                    f"{fmt.pct(inp['utilization'])}; kelebihan logam dijual sebagai konsentrat "
                    "dengan bea keluar 7,5%. Royalti PP 19/2025 pada dek harga; pajak "
                    f"{fmt.pct(inp['tax_rate'])} dan PNBP {fmt.pct(inp['ntgr_rate'])} dari 1H26.")}
    grid = lom_res["grid"]
    decks = [("reserve", "Harga cadangan JORC"), ("down20", "Dek -20%"),
             ("base", "Dek dasar"), ("up20", "Dek +20%")]
    rates = sorted({r for (r, _) in grid})
    grid_rows = [[f"Diskonto {fmt.pct(r)}" + (" (basis)" if abs(r - inp["discount"]) < 1e-9
                                             else "")] +
                 [f"Rp{fmt.rp(fmt.tick(grid[(r, d)]))}" for d, _ in decks] for r in rates]
    sensitivity = {"n": 0, "judul": "Sensitivitas SOTP/LoM: tingkat diskonto x dek harga",
                   "tipe": "tabel",
                   "data": {"cols": ["Tingkat diskonto USD"] + [label for _, label in decks],
                            "rows": grid_rows},
                   "catatan_sumber": (
                       f"Sumber: estimasi Sektoral. Dek dasar Cu US${fmt.rp(inp['cu_price'])}/t "
                       f"dan Au US${fmt.rp(inp['au_price'])}/oz ({inp.get('deck_basis') or 'rata-rata 12 bulan'})"
                       f"; harga cadangan JORC Cu US${fmt.rp(inp['reserve_cu_price'])}/t "
                       f"dan Au US${fmt.rp(inp['reserve_au_price'])}/oz dari rilis 1H26.")}
    export_case = ("Izin ekspor konsentrat diperpanjang (umpan penuh 85 Mtpa, sesuai jadwal "
                   "tambang emiten)" if not inp.get("export_base", True) else
                   "Tanpa izin ekspor konsentrat (umpan dibatasi kapasitas smelter)")
    extra_rows = [[export_case, f"Rp{fmt.rp(fmt.tick(lom_res['other_export']))}"]]
    extra_rows += [[f"Probabilitas pengembangan Elang {fmt.pct(r, 0)}", f"Rp{fmt.rp(fmt.tick(v))}"]
                   for r, v in sorted(lom_res["risk_range"].items())]
    ext = lom_res.get("licence_extension")
    if ext and ext["end"] > inp["licence_end"]:
        extra_rows.append([f"Elang ditambang sampai cadangan habis ({ext['end']}), bukan "
                           f"{int(inp['licence_end'])}", f"Rp{fmt.rp(fmt.tick(ext['per_share']))}"])
    extra_rows += [[f"Kurs USD/IDR {'+' if s > 0 else MINUS}{fmt.pct(abs(s), 0)}",
                    f"Rp{fmt.rp(fmt.tick(per_share * (1 + s)))}"] for s in (-0.05, 0.05)]
    tests = {"n": 0, "judul": "Uji tambahan SOTP/LoM", "tipe": "tabel",
             "data": {"cols": ["Skenario", "Nilai per saham"], "rows": extra_rows},
             "catatan_sumber": "Sumber: estimasi Sektoral; semua komponen jembatan dalam USD, "
                               "sehingga kurs mengubah nilai per saham secara proporsional."}
    lom = inp["assumptions"]
    rate = inp.get("discount_build") or {}
    rate_table = {
        "n": 0, "judul": "Komponen WACC US$ untuk NAV aset tambang", "tipe": "tabel",
        "data": {"cols": ["Parameter", "Nilai"], "rows": [
            [f"Risk-free (UST 10Y, {rate.get('rf_date') or '-'})", fmt.pct(rate.get("rf"))],
            ["Country risk premium Indonesia (parameter kebijakan analis)",
             fmt.pct(rate.get("crp"))],
            ["Beta (parameter kebijakan analis)", fmt._id(rate.get("beta") or 0, 2)],
            ["Equity risk premium (parameter kebijakan analis)", fmt.pct(rate.get("erp"))],
            ["Cost of equity (CAPM)", fmt.pct(rate.get("coe"))],
            ["Cost of debt sebelum pajak", fmt.pct(rate.get("kd_pretax"))],
            ["Tarif pajak efektif (PPh + PNBP)", fmt.pct(rate.get("tax"))],
            ["Cost of debt setelah pajak", fmt.pct(rate.get("kd_after"))],
            ["Bobot utang (nilai pasar)", fmt.pct(rate.get("weight_debt"))],
            ["Bobot ekuitas (nilai pasar)", fmt.pct(1 - (rate.get("weight_debt") or 0))],
            ["WACC US$ (Batu Hijau dan Elang)", fmt.pct(inp["discount"])]]},
        "catatan_sumber": (
            f"Sumber: model US$; Rf = UST 10Y ({_rf_source(rate.get('rf_source'))}, "
            f"{rate.get('rf_date')}); CRP Indonesia {fmt.pct(rate.get('crp'))}, beta "
            f"{fmt._id(rate.get('beta'), 2)} dan ERP mature market {fmt.pct(rate.get('erp'))} "
            f"parameter house policy; biaya utang {rate.get('kd_basis')}; bobot "
            f"dari utang finansial jembatan SOTP US${fmt._id((rate.get('debt_usd') or 0) / 1e6, 0)} "
            f"juta dan kapitalisasi pasar US${fmt._id((rate.get('equity_usd') or 0) / 1e6, 0)} "
            f"juta (harga {intake.get('price_date')}, kurs Rp{fmt.rp(fx)}/USD). WACC dibulatkan "
            "ke 0,1pp; Elang memakai WACC yang sama karena risiko pengembangannya sudah lewat "
            "probabilitas pengembangan. Tanpa nilai terminal.")}
    assumption_rows = [
        ["Tingkat diskonto USD", fmt.pct(inp["discount"]),
         "WACC US$ dari UST 10Y, CRP, beta dan ERP sesuai house policy serta "
         "biaya utang berbasis pasar; komponen di tabel WACC US$."],
        ["Probabilitas pengembangan Elang", fmt.pct(risk), lom.get("elang_risk_basis")],
        ["Capex pengembangan Elang",
         f"US${fmt._id(sum(base['elang_capex'].values()) / 1e9, 2)} miliar "
         f"({', '.join(str(y) for y in sorted(base['elang_capex']))})",
         f"{lom.get('elang_development_capex_basis')} Profil broker (bijih pertama 2031) digeser "
         f"agar berakhir setahun sebelum umpan Elang pertama dalam jadwal ini "
         f"({(base.get('elang_feed_years') or ['-'])[0]}): emiten memulai Elang sesudah umur "
         "tambang Batu Hijau, dan pada 85 Mtpa pabrik terisi pit lalu stockpile lebih dahulu."],
        ["Capex pemeliharaan Elang", f"US${usd(inp['elang_sustaining_usd'])} juta/tahun",
         lom.get("elang_sustaining_capex_basis")],
        ["Rehandle stockpile", f"US${fmt._id(inp['rehandle_usd_t'], 2)}/t",
         lom.get("stockpile_rehandle_basis")],
        ["Capex fase stockpile", fmt.pct(inp["stockpile_capex_share"]),
         lom.get("stockpile_phase_sustaining_basis")],
        ["Ekspor konsentrat",
         "tidak" if not inp.get("export_base", True) else "berlanjut",
         (f"Izin ekspor sementara berakhir {inp.get('export_permit_expired')} dan tidak ada bukti "
          "perpanjangan; umpan pabrik dibatasi pada bijih yang tembaganya dapat dilebur smelter "
          "(kapasitas x utilisasi terakhir), sisa bijih diproses kemudian, dan konsentrat 2H26 di "
          "atas kapasitas dilebur lebih dahulu pada 2027. Akibatnya pit dan stockpile berjalan "
          "lebih lama dari jadwal emiten (pit 2031/2032, stockpile 2033/2034) dan Elang mulai "
          "lebih lambat; jadwal emiten dengan ekspor ada di uji tambahan."
          if not inp.get("export_base", True) else lom.get("concentrate_export"))],
    ]
    assumptions = {"n": 0, "judul": "Asumsi analis dalam SOTP/LoM", "tipe": "tabel",
                   "data": {"cols": ["Asumsi", "Nilai", "Dasar"], "rows": assumption_rows},
                   "catatan_sumber": (
                       "Sumber: asumsi analis Sektoral; input lain (cadangan, kapasitas, biaya, "
                       "royalti, pajak, neraca) adalah data resmi emiten atau regulasi.")}
    down = lom_res["per_share_down"]
    last_pit = max((f["year"] for f in flows if f["asset"] == "bh" and "pit" in f["kinds"]),
                   default=inp["pit_end"])
    text = _t(
        (f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai SOTP/LoM, metode utama tambang: "
         f"NAV Batu Hijau US${fmt._id(nav_bh / 1e9, 1)} miliar (pit sampai {last_pit}, lalu "
         f"stockpile"
         + (f"; izin ekspor konsentrat berakhir {inp.get('export_permit_expired')}, sehingga "
            "umpan pabrik dibatasi kapasitas smelter"
            if not inp.get("export_base", True) else "")
         + f"), NAV Elang US${fmt._id(nav_el / 1e9, 1)} miliar dikali probabilitas "
         f"pengembangan {fmt.pct(risk)} karena proyek belum FID, dan persediaan "
         f"US${usd(inp['inventory_usd'])} "
         "juta, dikurangi PV overhead, utang bersih dan minoritas. Arus kas didiskonto WACC US$ "
         f"{fmt.pct(inp['discount'])} (UST 10Y {fmt.pct(rate.get('rf'))} + CRP "
         f"{fmt.pct(rate.get('crp'))} + beta x ERP, biaya utang {fmt.pct(rate.get('kd_pretax'))}) "
         f"sampai {int(inp['licence_end'])} tanpa nilai "
         f"terminal. Dek harga rata-rata 12 bulan kalender terakhir (sumber di tabel "
         f"sensitivitas) dibuat datar; pada harga cadangan JORC emiten nilainya "
         f"Rp{fmt.rp(fmt.tick(grid[(inp['discount'], 'reserve')]))}, "
         + ("bila izin ekspor konsentrat diperpanjang " if not inp.get("export_base", True)
            else "tanpa izin ekspor konsentrat ")
         + f"Rp{fmt.rp(fmt.tick(lom_res['other_export']))}, dan pada diskonto "
         f"{fmt.pct(inp['discount'] + 0.02)} Rp{fmt.rp(fmt.tick(down))}. Capex Elang belum "
         "diungkapkan emiten; angka dari riset broker adalah asumsi analis."),
        (f"We set our target at Rp{fmt.rp(va['tp'])} using SOTP/LoM, the Primary Method for "
         f"miners: Batu Hijau NAV of US${fmt._id(nav_bh / 1e9, 1)} miliar (pit to {last_pit}, "
         f"then stockpile"
         + (f"; the concentrate export permit expired on {inp.get('export_permit_expired')}, so "
            "plant feed is capped by smelter capacity"
            if not inp.get("export_base", True) else "")
         + f"), Elang NAV of US${fmt._id(nav_el / 1e9, 1)} miliar times a development "
         f"probability of {fmt.pct(risk)} as the project is pre-FID, and inventory of "
         f"US${usd(inp['inventory_usd'])} "
         "juta, less PV of overhead, net debt and minorities. Cash flows are discounted at a US$ "
         f"WACC of {fmt.pct(inp['discount'])} (UST 10Y {fmt.pct(rate.get('rf'))} + CRP "
         f"{fmt.pct(rate.get('crp'))} + beta x ERP, cost of debt "
         f"{fmt.pct(rate.get('kd_pretax'))}) to {int(inp['licence_end'])} with no terminal "
         f"value. The price deck, the average of the last 12 calendar months (sources in the "
         f"sensitivity table), is held flat; at the issuer's JORC reserve prices the value is "
         f"Rp{fmt.rp(fmt.tick(grid[(inp['discount'], 'reserve')]))}, "
         + ("with the concentrate export permit extended " if not inp.get("export_base", True)
            else "without a concentrate export permit ")
         + f"Rp{fmt.rp(fmt.tick(lom_res['other_export']))}, and at a discount rate of "
         f"{fmt.pct(inp['discount'] + 0.02)} Rp{fmt.rp(fmt.tick(down))}. The issuer has not "
         "disclosed Elang capex; the broker research figure is an analyst assumption."))
    notes = [
        _t("Rating dan target harga memakai SOTP/LoM, metode utama tambang: NAV per aset dari "
           "rantai fisik (cadangan, umpan, recovery, smelter, harga, biaya, royalti, pajak, capex) "
           "tanpa nilai terminal perpetual.",
           "Rating and Target Price use SOTP/LoM, the Primary Method for miners: NAV per asset "
           "from the physical chain (reserves, feed, recovery, smelter, price, costs, royalty, "
           "tax, capex) with no perpetual terminal value."),
        _t("Input fisik dan biaya dari rilis resmi 1H26, laporan keuangan dan regulasi; recovery "
           "tersirat dari logam dalam konsentrat dibagi logam terkandung umpan 1H26.",
           "Physical and cost inputs come from the official 1H26 release, financial statements "
           "and regulation; recovery is implied from metal in concentrate divided by contained "
           "metal in 1H26 feed."),
        _t("Capex Elang, probabilitas pengembangan Elang, rehandle stockpile dan ekspor konsentrat "
           "adalah asumsi analis berlabel; capex Elang dari riset broker, bukan data emiten. "
           "Tingkat diskonto adalah WACC US$ dari UST 10Y bertanggal + CRP + beta x ERP (parameter "
           "kebijakan analis), sama dengan model US$ lain.",
           "Elang capex, the Elang development probability, stockpile rehandle and concentrate "
           "exports are labelled analyst assumptions; Elang capex comes from broker research, not "
           "issuer data. The discount rate is a US$ WACC from a dated UST 10Y + CRP + beta x ERP "
           "(analyst policy parameters), as in other US$ models."),
        _t("Dek harga rata-rata 12 bulan kalender terakhir dibuat datar (Sectors bila datanya "
           "segar, selain itu seri Yahoo Finance bertanggal); harga cadangan JORC dan guncangan "
           "+/-20% ada di tabel sensitivitas.",
           "The price deck, the average of the last 12 calendar months, is held flat (Sectors when "
           "its data is fresh, otherwise a dated Yahoo Finance series); JORC reserve prices and "
           "+/-20% shocks are in the sensitivity table."),
        _t("EV/EBITDA FY26F 8x menjadi cross-check di rantai metode, tidak dirata-rata.",
           "FY26F EV/EBITDA of 8x is a cross-check in the Method Chain, not averaged."),
        _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
    ]
    walk = _lom_reconciliation(intake, lom_res)
    return {"exhibits": [sotp_table, schedule, rate_table, sensitivity, tests]
            + ([walk] if walk else []) + [assumptions],
            "text": text, "notes": notes}


MINUS = "\u2212"


def _rf_source(source):
    """Reader name of the UST 10Y source: 'Yahoo Finance, imbal hasil UST 10Y
    harian', without the ticker symbol or the provider's own label."""
    text = re.sub(r" [(].*$", "", str(source or "Yahoo Finance ^TNX"))
    return text.replace("^TNX daily close", "imbal hasil UST 10Y harian").replace("^TNX", "UST 10Y")


def _lom_reconciliation(intake, lom_res):
    """Plan 1.3: the target walked, one assumption at a time, towards the
    value on the market's usual assumptions, then to the dated consensus."""
    rows = lom_res.get("reconciliation") or []
    if not rows:
        return None
    rp = lambda v: f"Rp{fmt.rp(fmt.tick(v))}"
    step = lambda v: "" if v is None else f"{'+' if v >= 0 else '-'}Rp{fmt.rp(fmt.tick(abs(v)))}"
    table = [[r["label"], rp(r["per_share"]), step(r["step"])] for r in rows]
    walked = next(r for r in rows if r["key"] == "horizon")["per_share"]
    doc, why = consensus.load(intake.get("ticker"), intake.get("as_of"))
    if doc:
        avg = doc["target_avg"]
        # The consensus average as published (not rounded to a price tick), so
        # it reads the same as in the consensus table.
        table.append([f"Rata-rata target konsensus ({doc['analysts']} analis, {doc['as_of']})",
                      f"Rp{fmt.rp(avg)}", f"sisa sesudah tiga langkah {step(avg - walked)}"])
    else:
        table.append(["Rata-rata target konsensus", "n.a.", why])
    return {"n": 0, "judul": "Rekonsiliasi target ke asumsi pasar dan konsensus", "tipe": "tabel",
            "data": {"cols": ["Langkah (kumulatif)", "Nilai per saham", "Perubahan"],
                     "rows": table},
            "catatan_sumber": (
                "Sumber: Sektoral Estimates; tiap langkah menambah satu asumsi di atas langkah "
                "sebelumnya pada model LoM yang sama. Dua baris terakhir sebelum konsensus adalah "
                "alternatif, masing-masing di atas tiga langkah pertama, bukan kumulatif satu sama "
                "lain." + (f" Konsensus: {doc['source_title']}, diambil {doc['as_of']}." if doc
                           else ""))}


def _lom_fx_source(intake):
    """The one USD/IDR quote of the report, as the SOTP bridge states it."""
    cash = (intake.get("sotp_bridge") or {}).get("cash_idr") or {}
    spot = intake.get("fx_spot") or {}
    if spot.get("rate") and cash.get("fx_rate") == spot["rate"]:
        return f"Yahoo Finance IDR=X, {spot.get('date')}"
    return f"kurs bertanggal {cash.get('fx_date') or '-'}"


def _build_assumption_led(intake, fc, va, s1, method="auto"):
    """Publish the validated FY scenario as the selected multiple-based method."""
    doc = _build_general_draft(intake, fc, va, s1, method=method,
                               illustrative_scenarios=True)
    scenario = fc["interim_scenario"]
    forecast_label = f"FY{scenario['year'] % 100:02d}F"
    value = va["scenario_target"]
    chain = va.get("method_chain") or {}
    lom_detail = (next((t["detail"] for t in chain.get("trace") or []
                        if t["key"] == "sotp_lom"), None)
                  if chain.get("selected") == "sotp_lom" else None)
    lom_page = _lom_exhibits(intake, va, lom_detail) if lom_detail else None
    meta = doc["meta"]
    released = (va.get("release") or {}).get("status")
    meta.update(status=("distributable" if released == "distributable"
                        else "distributable_assumption_led"),
                model_profile=intake.get("model_profile"),
                rating=va["rating"],
                tp=va["tp"], upside_persen=va["upside"] * 100,
                status_rating=va["rating"], illustrative_scenarios=False)
    rail = _market_rail(intake)
    doc["method"] = va["method"]
    doc["log_gate"]["S3"] = va["s3"]
    doc["log_gate"]["release"] = va["release"]
    profit_change = _scenario_profit_change(intake, scenario.get("full_year") or {})
    doc["cover"]["headline"] = _earnings_headline(forecast_label, profit_change)
    doc["cover"]["bullets"][2] = _t(
        (f"Target Rp{fmt.rp(va['tp'])} memberi {fmt.pct(va['upside'])} terhadap "
         f"penutupan Rp{fmt.rp(intake['price'])} pada {intake['price_date']}; "
         "basis 8x EV/EBITDA adalah asumsi analis."),
        (f"Target Rp{fmt.rp(va['tp'])} implies {fmt.pct(va['upside'])} against the "
         f"Rp{fmt.rp(intake['price'])} close on {intake['price_date']}; "
         "the 8x EV/EBITDA basis is an analyst assumption."))
    if lom_page:
        doc["cover"]["headline"] = _earnings_headline(forecast_label, profit_change)
        doc["cover"]["bullets"][2] = _trim(_t(
            f"{va['rating']}: target Rp{fmt.rp(va['tp'])} ({fmt.pct(va['upside'])}) dari "
            "SOTP/LoM Batu Hijau dan Elang, tanpa nilai terminal.",
            f"{va['rating']}: target Rp{fmt.rp(va['tp'])} ({fmt.pct(va['upside'])}) from a "
            "Batu Hijau and Elang SOTP/LoM, with no terminal value."), 30)
    doc["cover"]["paragraf"][2] = {
        "judul": "Target harga berbasis hasil FY",
        "isi": _t(
            (f"EBITDA {forecast_label} US${fmt._id(value['ebitda_usd']/1e6, 1)} "
             "juta berasal dari realisasi interim dan asumsi semester berikutnya. "
             "Kelipatan 8x dipilih di bawah kelipatan implisit harga pasar "
             f"{fmt.mult((intake['price'] * value['shares'] / value['fx']['rate'] + value['net_debt_usd'] + value['minority_interest_usd']) / value['ebitda_usd'], 1)} "
             "untuk mencerminkan ketidakpastian LoM dan capex. Nilai ekuitas "
             "dihitung setelah utang bersih dan "
             "kepentingan nonpengendali. LoM/SOTP per aset belum tersedia; "
             "karena itu risiko umur tambang, capex, dan harga komoditas material."),
            (f"{forecast_label} EBITDA of US${fmt._id(value['ebitda_usd']/1e6, 1)} "
             "juta comes from interim actuals and assumptions for the next half. "
             "The 8x multiple is set below the market-implied multiple of "
             f"{fmt.mult((intake['price'] * value['shares'] / value['fx']['rate'] + value['net_debt_usd'] + value['minority_interest_usd']) / value['ebitda_usd'], 1)} "
             "to reflect LoM and capex uncertainty. Equity value is "
             "calculated after net debt and non-controlling interests. A per-asset LoM/SOTP "
             "is not yet available, so mine-life, capex and commodity-price risks are "
             "material."))}
    if lom_page:
        doc["cover"]["paragraf"][2] = {"judul": "Target harga berbasis SOTP/LoM",
                                       "isi": lom_page["text"]}
    doc["catatan_metodologi"] = [
        _t("Rating dan target harga memakai FY forecast berbasis hasil interim resmi serta "
           "multiple 8x EV/EBITDA sebagai asumsi analis, bukan multiple peer terverifikasi.",
           "Rating and Target Price use an FY forecast built on official interim results and "
           "an 8x EV/EBITDA multiple as an analyst assumption, not a verified peer multiple."),
        _t("Skenario 6x/8x/10x menunjukkan sensitivitas; 8x adalah basis target harga.",
           "The 6x/8x/10x scenarios show sensitivity; 8x is the Target Price basis."),
        _t(f"Harga penutupan {intake['price_date']} bersumber dari "
           f"{(intake.get('market_quote') or {}).get('source_url', 'data pasar bertanggal')}. "
           + (f"ADTV 90 hari memakai {rail['adtv_count']} observasi lokal sampai "
              f"{rail['adtv_end']}. " if rail.get("adtv") is not None else "")
           + ("Porsi Public adalah kategori kepemilikan dari snapshot cache, bukan free float terverifikasi."
              if rail.get("public_ownership") is not None else ""),
           f"The {intake['price_date']} close is sourced from "
           f"{(intake.get('market_quote') or {}).get('source_url', 'dated market data')}. "
           + (f"The 90-day ADTV uses {rail['adtv_count']} local observations to "
              f"{rail['adtv_end']}. " if rail.get("adtv") is not None else "")
           + ("The Public share is an ownership category from the cached snapshot, not a "
              "verified free float."
              if rail.get("public_ownership") is not None else "")),
        _t("LoM/SOTP per aset, capex masa depan, dan perubahan kas/utang setelah neraca "
           "interim belum dimodelkan; audit gate SOTP tetap ada dalam trace.",
           "Per-asset LoM/SOTP, future capex and changes in cash/debt after the interim balance "
           "sheet are not yet modelled; the SOTP gate audit remains in the trace."),
        _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
    ]
    if lom_page:
        doc["catatan_metodologi"] = lom_page["notes"]
    remove_titles = {"Konteks historis dan kepemilikan", "Skenario operasi ilustratif",
                     "Valuasi ilustratif dan keterbatasannya"}
    if not any(effect.get("driver") != "none" for effect in fc.get("news_assumptions") or []):
        remove_titles.add("Berita dan keputusan asumsi")
    doc["bagian"] = [page for page in doc["bagian"] if page["judul"] not in remove_titles]
    forward = fc.get("outyear_scenario")
    lom_schedule = (forward or {}).get("status") == "lom_schedule"
    if forward and forward.get("rows"):
        source_lookup = {"official": (intake.get("official_evidence") or {}).get("latest_actual", {}).get("source_url")}
        news_effects = fc.get("news_assumptions") or []
        source_lookup.update({f"news:{item.get('article_index')}": item.get("source_url")
                              for item in news_effects})
        # The valuation runs five years: FY26F (1H actual + H2 assumption) opens
        # the table so every year of the horizon names its basis.
        full = scenario.get("full_year") or {}
        ratio = lambda key: (fmt.pct(full[key] / full["revenue"])
                             if full.get(key) is not None and full.get("revenue") else "n.m.")
        official_source = ((intake.get("latest_official_actual") or {}).get("source_title") or
                           "rilis interim resmi")
        assumption_rows = [[
            forecast_label,
            (f"EBITDA margin {ratio('ebitda')}; net margin {ratio('net_profit')}; "
             f"capex/revenue {ratio('capital_expenditure') if full.get('capital_expenditure') is not None else ratio('capex')}"),
            f"Aktual {(intake.get('latest_official_actual') or {}).get('period') or '1H'} resmi "
            f"ditambah asumsi H2 analis; rincian di exhibit skenario {forecast_label}. "
            f"Sumber: {official_source}."]]
        cited_urls = [source_lookup["official"]] if source_lookup.get("official") else []
        for row in forward["rows"]:
            sources = [source_lookup[source_id] for source_id in row["source_ids"]
                       if source_lookup.get(source_id)]
            cited_urls.extend(sources)
            assumption_rows.append([
                row["label"],
                (f"Revenue growth {fmt.pct((row['revenue_growth_pct'] or 0) / 100)}; "
                 f"EBITDA margin {fmt.pct(row['ebitda_margin_pct'] / 100)}; "
                 f"net margin {fmt.pct(row['net_income_margin_pct'] / 100)}; "
                 f"capex/revenue {fmt.pct(row['capex_to_revenue_pct'] / 100)}"),
                (row.get("rationale") or "Jadwal LoM yang sama dengan valuasi.")
                + " Bukan panduan emiten." if lom_schedule else
                "Angka kolom ini adalah asumsi analis untuk tahun tersebut, bukan panduan emiten."])
        assumptions_exhibit = {
            "n": len(doc["exhibits"]) + 1,
            "judul": (f"Dasar tiap tahun {forecast_label}-FY30F: skenario interim dan jadwal LoM"
                      if lom_schedule else f"Asumsi skenario laba {forecast_label}-FY30F"),
            "tipe": "tabel",
            "data": {"cols": ["Tahun", "Jadwal LoM" if lom_schedule else "Asumsi analis",
                              "Dasar dan batasan"],
                     "rows": assumption_rows},
            "catatan_sumber": (
                "Sumber referensi: " + "; ".join(dict.fromkeys(cited_urls)) +
                (". Angka tahunan adalah total jadwal LoM yang sama dengan valuasi SOTP/LoM "
                 "(umpan, logam, dek harga, biaya, royalti, pajak), bukan panduan emiten."
                 if lom_schedule else
                 ". Angka tahunan dihitung dari FY26F dan asumsi di tabel; "
                 "bukan panduan emiten atau forecast produksi LoM."))}
        doc["exhibits"].append(assumptions_exhibit)
        anchor = next((index for index, page in enumerate(doc["bagian"])
                       if page["judul"] in ("Skenario FY26 dari rilis terbaru",
                                            f"Forecast {forecast_label} dari rilis terbaru")),
                      len(doc["bagian"]) - 1)
        doc["bagian"].insert(anchor + 1, {
            "halaman": 0,
            "judul": ("Jadwal LoM FY27F-FY30F" if lom_schedule else "Skenario laba FY27F-FY30F"),
            "layout": "stack",
            "paragraf": [
                _t("Tahun sesudah FY26F diambil dari jadwal LoM yang juga menjadi dasar target: "
                   "umpan pabrik, logam yang dilebur, dek harga, biaya unit, royalti dan pajak. "
                   "Laba bersih mengurangkan D&A jadwal, bunga dua kali beban keuangan 1H26, "
                   "serta pajak dan PNBP pada tarif efektif 1H26. Perusahaan tidak memberi "
                   "jadwal tahunan; ini estimasi Sektoral.",
                   "Years after FY26F come from the LoM schedule that also underlies the target: "
                   "plant feed, smelted metal, price deck, unit costs, royalty and tax. Net "
                   "profit deducts scheduled D&A, interest at twice 1H26 finance costs, and tax "
                   "and PNBP at 1H26 effective rates. The company gives no annual schedule; this "
                   "is a Sektoral estimate.") if lom_schedule else
                _t("Estimasi di bawah memperpanjang FY26F memakai pertumbuhan dan "
                   "margin asumsi analis yang diturunkan dari rilis resmi dan konteks "
                   "operasi. Perusahaan belum memberi jadwal tahunan produksi, harga, "
                   "biaya dan capex untuk periode ini; angka ini adalah skenario laba, "
                   "bukan forecast fisik tambang atau SOTP.",
                   "The estimates below extend FY26F using analyst-assumed growth and margins "
                   "derived from the official release and operating context. The company has "
                   "not given an annual schedule of production, prices, costs and capex for "
                   "this period; these figures are an earnings scenario, not a physical mine "
                   "forecast or SOTP.")],
            "exhibit": [assumptions_exhibit],
        })
    for page in doc["bagian"]:
        if page["judul"] == "Skenario FY26 dari rilis terbaru":
            page["judul"] = f"Forecast {forecast_label} dari rilis terbaru"
            page["paragraf"] = [_t(
                "Hasil interim resmi menjadi basis semester pertama. Semester kedua "
                "mengikuti rasio pendapatan dan margin asumsi analis pada exhibit di bawah. "
                "Nilai setahun penuh adalah skenario model, bukan panduan emiten.",
                "Official interim results form the first-half basis. The second half follows "
                "the analyst-assumed revenue ratio and margins in the exhibit below. The "
                "full-year figure is a model scenario, not issuer guidance.")]
        elif page["judul"] == "Cross-check nilai FY26 dari hasil terbaru" and lom_page:
            page["judul"] = f"Cross-check {forecast_label} EV/EBITDA"
            page["paragraf"] = [_t(
                f"EBITDA {forecast_label} diuji pada multiple 6x, 8x dan 10x sebagai cross-check "
                "relatif terhadap SOTP/LoM; nilai ini bukan target harga.",
                f"{forecast_label} EBITDA is tested at 6x, 8x and 10x multiples as a relative "
                "cross-check to SOTP/LoM; these values are not the Target Price.")]
        elif page["judul"] == "Cross-check nilai FY26 dari hasil terbaru":
            page["judul"] = f"Target harga {forecast_label} EV/EBITDA"
            page["paragraf"] = [_t(
                f"Target Rp{fmt.rp(va['tp'])} memakai EBITDA {forecast_label} "
                "dan multiple 8x. Rentang 6x-10x memperlihatkan sensitivitas "
                "terhadap asumsi valuasi; seluruh nilai memakai utang, minoritas, "
                "jumlah saham, dan kurs yang ditampilkan.",
                f"The Rp{fmt.rp(va['tp'])} target uses {forecast_label} EBITDA "
                "and an 8x multiple. The 6x-10x range shows sensitivity to valuation "
                "assumptions; all values use the debt, minorities, share count and "
                "exchange rate shown.")]
        elif page["judul"] == "Valuasi dan kelengkapan bukti" and lom_page:
            page["judul"] = "Target harga berbasis SOTP/LoM"
            page["paragraf"] = [lom_page["text"]]
            base_n = min((float(e.get("n", 20)) for e in page.get("exhibit") or []),
                          default=20.0)
            for i, exhibit in enumerate(lom_page["exhibits"]):
                exhibit["n"] = base_n - 0.5 + i * 0.01
            page["exhibit"] = lom_page["exhibits"] + list(page.get("exhibit") or [])
            doc["exhibits"].extend(lom_page["exhibits"])
        elif page["judul"] == "Valuasi dan kelengkapan bukti":
            page["judul"] = "Valuasi dan batasan model"
            page["paragraf"] = [_t(
                "Metode utama adalah FY forecast EV/EBITDA 8x dengan asumsi analis. "
                "Status rilis distributable_assumption_led berlaku melalui jalur opt-in analyst-target; "
                "pemeriksaan jembatan operasi dan SOTP aset tetap belum lolos. "
                "LoM/SOTP tetap belum lengkap; daftar di bawah menunjukkan bukti "
                "yang diperlukan untuk menguji ulang nilai aset dan capex.",
                "The Primary Method is an FY forecast EV/EBITDA of 8x on analyst assumptions. "
                "The distributable_assumption_led release status applies through the opt-in "
                "analyst-target path; the operating bridge and asset SOTP checks have still not "
                "passed. LoM/SOTP remains incomplete; the list below shows the evidence needed "
                "to retest asset value and capex.")]
        page["halaman"] = doc["bagian"].index(page) + 2
    bridge = _mining_sales_bridge(intake, scenario)
    new_pages = []
    if bridge:
        bridge_rows = []
        gold_row = next((row for row in bridge["rows"]
                         if row["key"] == "refined_gold"), None)
        for row in bridge["rows"]:
            h2_required = (bridge["gold_required"]
                           if row["key"] == "refined_gold" and
                           bridge["gold_required"] is not None else row["h2_sales"])
            bridge_rows.append([
                row["label"],
                _volume_text(row["h1_sold"], row["unit"]),
                fmt._id(row["h1_revenue"] / 1e6, 1),
                (f"Q2 impl. US$ {fmt._id(row['unit_value'], 0)}/{row['unit']}"
                 if row.get("h2_price_basis", "").startswith("Q2 implied") else
                 f"H1 proxy US$ {fmt._id(row['unit_value'], 0)}/{row['unit']}"),
                _volume_text(row["h2_sales"], row["unit"]),
                fmt._id(row["h2_revenue"] / 1e6, 1),
                _volume_text(h2_required, row["unit"]),
            ])
        bridge_rows.extend([
            ["Subtotal pada basis harga H2", "-", fmt._id(
                sum(row["h1_revenue"] for row in bridge["rows"]) / 1e6, 1),
             "-", "-", fmt._id(bridge["base_sum"] / 1e6, 1), "-"],
            ["Skenario pendapatan H2", "-", "-", "-", "-", fmt._id(
                bridge["h2_topdown"] / 1e6, 1), "-"],
            ["Selisih yang belum dijelaskan", "-", "-", "-", "-", fmt._id(
                bridge["residual"] / 1e6, 1), "-"],
        ])
        actual = (intake.get("official_evidence") or {}).get("latest_actual") or {}
        analyst_scenario = intake.get("analyst_scenario") or {}
        market_refs = {row.get("product_key"): row for row in
                       (analyst_scenario.get("market_references") or [])}
        bridge_exhibit = {
            "n": 11.1, "judul": "Jembatan penjualan produk dan revenue H2 2026",
            "tipe": "tabel",
            "data": {"cols": ["Produk", "H1 terjual", "H1 revenue (US$m)",
                              "Basis harga H2", "H2 terjual (basis)",
                              "H2 revenue pada basis harga H2 (US$m)",
                              "H2 terjual untuk rekonsiliasi"],
                     "rows": bridge_rows},
            "catatan_sumber": (
                f"Sumber H1: {actual.get('source_title')}, hlm. 3-4; guidance FY: "
                f"{actual.get('source_title')}, hlm. 7; {str(analyst_scenario.get('basis', 'asumsi analis')).rstrip('. ')}. "
                "Untuk katoda dan emas dipakai estimasi Q2 net realized price dari harga Q1/H1 dan volume sales tertimbang; sumber dibulatkan sehingga harga Q2 ini turunan. Untuk konsentrat, basis H1 menggabungkan net realized Cu/Au dan volume logam; tidak menangkap variasi payability, TC-RC, atau bauran H2.")
        }
        doc["exhibits"].append(bridge_exhibit)
        gold_sellthrough_h1 = (
            gold_row["h1_sold"] / gold_row["h1_production"]
            if gold_row and gold_row["h1_production"] else None)
        bridge_paragraph = (_t(
            f"Pada volume dasar dan basis harga H2 yang memakai estimasi harga Q2 untuk katoda/emas serta net realized H1 untuk konsentrat, produk membentuk revenue H2 US$ {fmt._id(bridge['base_sum']/1e6, 1)} juta, "
            f"di bawah skenario top-down US$ {fmt._id(bridge['h2_topdown']/1e6, 1)} juta; selisih US$ {fmt._id(bridge['residual']/1e6, 1)} juta belum dijelaskan. ",
            f"At base volumes and the H2 price basis, which uses estimated Q2 prices for cathode/gold and H1 net realized prices for concentrate, the products make up H2 revenue of US$ {fmt._id(bridge['base_sum']/1e6, 1)} juta, "
            f"below the top-down scenario of US$ {fmt._id(bridge['h2_topdown']/1e6, 1)} juta; a gap of US$ {fmt._id(bridge['residual']/1e6, 1)} juta is unexplained. ")
            if bridge["residual"] is not None else "")
        if gold_row and bridge["gold_required"] is not None:
            bridge_paragraph += _t(
                f"Jika seluruh selisih ditutup lewat penjualan emas murni pada implied net realized price Q2, volume H2 perlu "
                f"{_volume_text(bridge['gold_required'], gold_row['unit'])}, atau "
                f"{fmt.pct(bridge['gold_required_sellthrough'])} dari output H2 tersirat. "
                f"Rasio penjualan/output H1 adalah {fmt.pct(gold_sellthrough_h1)}. "
                "Volume rekonsiliasi adalah kebutuhan matematis, bukan guidance atau forecast penjualan independen.",
                f"If the whole gap were closed through refined gold sales at the implied Q2 net realized price, H2 volume would need to be "
                f"{_volume_text(bridge['gold_required'], gold_row['unit'])}, or "
                f"{fmt.pct(bridge['gold_required_sellthrough'])} of implied H2 output. "
                f"The H1 sales/output ratio is {fmt.pct(gold_sellthrough_h1)}. "
                "The reconciling volume is an arithmetic requirement, not guidance or an independent sales forecast.")
        q2_conc = next((row for row in
                        (((intake.get("official_evidence") or {}).get("quarterly_actuals") or {})
                         .get("q2_2026_derived") or {}).get("sales_production_bridge") or []
                        if row.get("product_key") == "concentrate"), None)
        conditional_h1_conc = next((row for row in
                                    (analyst_scenario.get("product_sales") or [])
                                    if row.get("product_key") == "concentrate"), {})
        if q2_conc and conditional_h1_conc.get("conditional_case_h2_sales_to_h1"):
            conditional_volume = (conditional_h1_conc["conditional_case_h2_sales_to_h1"] *
                                  next(row["h1_sold"] for row in bridge["rows"]
                                       if row["key"] == "concentrate"))
            q2_conc_value = q2_conc.get("revenue_per_sold_unit_proxy")
            conditional_revenue = conditional_volume * q2_conc_value if q2_conc_value else None
            if conditional_revenue is not None:
                bridge_paragraph += _t(
                    f"Sebagai uji bersyarat, penjualan konsentrat { _volume_text(conditional_volume, 'dmt')} "
                    f"pada proxy revenue Q2 US$ {fmt._id(q2_conc_value, 0)}/dmt memberi sekitar "
                    f"US$ {fmt._id(conditional_revenue/1e6, 1)} juta. Nilai itu hampir menutup gap, "
                    "tetapi bukan realized netback dan bergantung pada izin/kanal serta kontrak yang belum dibuktikan.",
                    f"As a conditional test, concentrate sales of {_volume_text(conditional_volume, 'dmt')} "
                    f"at the Q2 revenue proxy of US$ {fmt._id(q2_conc_value, 0)}/dmt give about "
                    f"US$ {fmt._id(conditional_revenue/1e6, 1)} juta. That nearly closes the gap, "
                    "but it is not a realized netback and depends on permits/channels and contracts not yet evidenced.")
        delivery_commitment = ((intake.get("official_evidence") or {}).get(
            "customer_delivery_commitment") or {})
        if delivery_commitment:
            advance = delivery_commitment.get("prepayment_advance_usd_thousand") or {}
            opening_advance = advance.get("balance_2025_12_31")
            received_advance = advance.get("received_2026_04")
            closing_advance = advance.get("balance_2026_06_30")
            from . import prose_lang
            commitment_text = _t(
                "Kontrak Glencore mendukung keberadaan kanal penjualan katoda: komitmen pengiriman "
                f"berlaku sampai {delivery_commitment.get('delivery_commitment_until')}; "
                "uang muka dikurangkan proporsional dari pengiriman bulanan dan kegagalan memenuhi "
                "komitmen mewajibkan pembayaran kembali uang muka terkait beserta bunga. ",
                "The Glencore contract supports the existence of a cathode sales channel: the "
                "delivery commitment runs to "
                f"{prose_lang.source(delivery_commitment.get('delivery_commitment_until'))}; "
                "the advance is deducted pro rata from monthly deliveries, and failure to meet the "
                "commitment requires repayment of the related advance with interest. "
            )
            if all(value is not None for value in
                   (opening_advance, received_advance, closing_advance)):
                net_change = closing_advance - opening_advance
                commitment_text += _t(
                    f"Catatan mencatat penerimaan uang muka US$ {fmt._id(received_advance/1000, 1)} juta "
                    f"pada April, saldo US$ {fmt._id(opening_advance/1000, 1)} juta pada akhir 2025, "
                    f"dan US$ {fmt._id(closing_advance/1000, 1)} juta pada akhir Juni "
                    f"(perubahan bersih +US$ {fmt._id(net_change/1000, 1)} juta). ",
                    f"The notes record an advance of US$ {fmt._id(received_advance/1000, 1)} juta "
                    f"received in April, a balance of US$ {fmt._id(opening_advance/1000, 1)} juta at "
                    f"end-2025 and US$ {fmt._id(closing_advance/1000, 1)} juta at end-June "
                    f"(net change +US$ {fmt._id(net_change/1000, 1)} juta). "
                )
            commitment_text += _t(
                "Namun volume kontrak dan sisa kewajiban per kuartal, formula harga, serta rekonsiliasi "
                "penerimaan uang muka dengan potongan atas pengiriman tidak diungkap. Karena itu kontrak "
                "tidak membuktikan asumsi penjualan katoda H2 pada tabel. Sumber: "
                f"{delivery_commitment.get('source_title')}, hlm. {delivery_commitment.get('source_page')}; "
                f"{delivery_commitment.get('source_url')}.",
                "However, contract volumes and remaining obligations by quarter, the price formula, "
                "and the reconciliation of advances received with deductions on deliveries are not "
                "disclosed. The contract therefore does not prove the H2 cathode sales assumption in "
                "the table. Source: "
                f"{prose_lang.source(delivery_commitment.get('source_title'))}, p. "
                f"{delivery_commitment.get('source_page')}; {delivery_commitment.get('source_url')}."
            )
            bridge_paragraph += " " + commitment_text
        new_pages.append({
            "halaman": 0, "judul": "Jembatan revenue H2 menurut produk",
            "layout": "stack", "paragraf": [bridge_paragraph],
            "exhibit": [bridge_exhibit]})

        q2 = ((intake.get("official_evidence") or {}).get("quarterly_actuals") or {}).get(
            "q2_2026_derived") or {}
        q2_fin = q2.get("financials_usd_mn") or {}
        q2_sales = q2.get("sales_production_bridge") or []
        if q2_fin and q2_sales:
            q2_rows = []
            for item in q2_sales:
                if not item.get("product_key") in ("concentrate", "cathode_copper", "refined_gold"):
                    continue
                product_label = {"concentrate": "Konsentrat", "cathode_copper": "Katoda tembaga",
                                 "refined_gold": "Emas murni"}[item["product_key"]]
                q2_revenue = item.get("segment_revenue_usd_mn")
                if q2_revenue is None and item["product_key"] == "concentrate":
                    q2_revenue = (q2.get("revenue_by_product_usd_mn") or {}).get("concentrate")
                q2_rows.append([
                    product_label, _volume_text(item.get("production"), item.get("unit")),
                    _volume_text(item.get("sales"), item.get("unit")),
                    (fmt._id(q2_revenue, 0) if q2_revenue is not None else "-"),
                    (f"US$ {fmt._id(item['revenue_per_sold_unit_proxy'], 0)}/{item['unit']}"
                     if item.get("revenue_per_sold_unit_proxy") is not None else "-"),
                    ((f"US$ {fmt._id(item['implied_net_realized_price']['value'], 0)}/"
                      f"{item['implied_net_realized_price']['unit'].replace('USD/', '')}")
                     if item.get("implied_net_realized_price") else "-")])
            for label, key in (("Net sales", "net_sales"), ("EBITDA", "ebitda"),
                               ("Laba bersih", "net_income"), ("Capex", "capex")):
                q2_rows.append([label, "-", "-", fmt._id(q2_fin.get(key), 0), "US$ juta", "-"])
            q2_exhibit = {
                "n": 11.05, "judul": "Q2 2026: angka turunan dari H1 dikurangi Q1",
                "tipe": "tabel",
                "data": {"cols": ["Produk / metrik", "Q2 produksi", "Q2 terjual",
                                  "Revenue / metrik (US$m)", "Revenue per unit, proxy",
                                  "Q2 implied net price"],
                         "rows": q2_rows},
                "catatan_sumber": (
                    "Q2 dihitung sebagai H1 2026 resmi dikurangi Q1 2026 resmi; volume dan finansial adalah angka turunan. "
                    "Revenue segmen dibulatkan dalam rilis, sehingga tidak sama persis dengan net sales; nilai konsentrat/dmt "
                    "adalah proxy campuran, bukan realized price/netback. Q1: AMMAN Q1 2026 Performance Release, hlm. 3-5; "
                    "H1: AMMAN H1 2026 Earnings Release, hlm. 3-4."),
            }
            doc["exhibits"].append(q2_exhibit)
            new_pages.append({
                "halaman": 0, "judul": "Rekonstruksi aktual Q2 2026",
                "layout": "stack",
                "paragraf": [_t(
                    "Rekonstruksi ini mempersempit data aktual terbaru menjadi Q2. Revenue per unit hanya proxy dari revenue segmen dibagi unit terjual; rilis tidak memberi realized price Q2 yang terpisah. Angka ini membantu mengkalibrasi skenario H2, tetapi tidak memvalidasi penjualan atau harga H2.",
                    "This reconstruction narrows the latest actuals down to Q2. Revenue per unit is only a proxy, segment revenue divided by units sold; the release gives no separate Q2 realized price. These figures help calibrate the H2 scenario but do not validate H2 sales or prices.")],
                "exhibit": [q2_exhibit]})

        output_sales_rows = []
        for row in bridge["rows"]:
            if row.get("h2_production") is None:
                continue
            output_sales_rows.append([
                row["label"], _volume_text(row["h1_production"], row["unit"]),
                _volume_text(row["h1_sold"], row["unit"]),
                _volume_text(row["h2_production"], row["unit"]),
                _volume_text(row["h2_sales"], row["unit"]),
                fmt.pct(row["h2_sales"] / row["h2_production"])
                if row["h2_production"] else "-",
            ])
        if output_sales_rows:
            output_sales_exhibit = {
                "n": 11.15, "judul": "Output tersirat dan asumsi penjualan H2",
                "tipe": "tabel",
                "data": {"cols": ["Produk", "H1 produksi", "H1 terjual",
                                  "H2 produksi tersirat", "H2 penjualan skenario",
                                  "H2 terjual / output"],
                         "rows": output_sales_rows},
                "catatan_sumber": (
                    f"Sumber actual dan guidance: {actual.get('source_title')}, hlm. 3 dan 7. "
                    "H2 production adalah sisa panduan FY dikurangi output H1. Penjualan katoda/emas "
                    "memakai rasio sell-through Q2 yang diturunkan dari H1 dikurangi Q1. Base case tidak "
                    "mengasumsikan ekspor konsentrat tanpa bukti izin baru; penjualan nol adalah asumsi skenario, "
                    "bukan aktual. Kasus 120.079 dmt konsentrat H2 hanya conditional pada izin/kanal dan kontrak. "
                    "Selisih output dan penjualan tidak otomatis sama dengan perubahan stockpile.")
            }
            doc["exhibits"].append(output_sales_exhibit)
            new_pages.append({
                "halaman": 0, "judul": "Output dan penjualan H2",
                "layout": "stack",
                "paragraf": [_t(
                    "Tabel membedakan sisa output dari volume penjualan yang diasumsikan. Rasio penjualan/output "
                    "bukan roll-forward persediaan; perubahan stockpile dan umpan internal belum tersedia.",
                    "The table separates remaining output from assumed sales volumes. The sales/output "
                    "ratio is not an inventory roll-forward; stockpile changes and internal feed are not "
                    "yet available.")],
                "exhibit": [output_sales_exhibit]})

        price_detail_rows = []
        def metal_volume(value, unit):
            if unit == "lb":
                return f"{fmt._id(value / 1e6, 1)} Mlbs"
            if unit == "ton":
                return f"{fmt._id(value / 1000, 1)} kt"
            if unit == "oz":
                return f"{fmt._id(value / 1000, 1)} koz"
            return _volume_text(value, unit)
        # Net realized price per refined product comes from the official
        # sales bridge (same source as the draft route's sales table).
        actual_sales = ((intake.get("official_evidence") or {})
                        .get("sales_production_bridge") or [])
        for row in bridge["rows"]:
            if row["key"] == "concentrate":
                for component in row.get("price_components") or []:
                    price_detail_rows.append([
                        component["product"], metal_volume(component["h1_sold"], component["unit"]),
                        f"US$ {fmt._id(component['h1_price'], 2)}/{component['unit']}",
                        metal_volume(component["h2_sold"], component["unit"]),
                        fmt._id(component["h2_revenue"] / 1e6, 1),
                    ])
            elif row["key"] in ("cathode_copper", "refined_gold"):
                product = next((item for item in actual_sales
                                if _product_key(item.get("product")) == row["key"]), {})
                price = product.get("net_realized_price") or {}
                if price.get("value") is not None:
                    price_detail_rows.append([
                        row["label"], metal_volume(row["h1_sold"], row["unit"]),
                        f"US$ {fmt._id(price['value'], 2)}/{_market_price_unit(price.get('unit'))}",
                        metal_volume(row["h2_sales"], row["unit"]),
                        fmt._id(row["h2_revenue"] / 1e6, 1),
                    ])
        if price_detail_rows:
            price_detail_exhibit = {
                "n": 11.18, "judul": "Volume penjualan dan net realized price per logam",
                "tipe": "tabel",
                "data": {"cols": ["Produk", "H1 terjual", "Net realized price H1",
                                  "H2 terjual skenario", "H2 revenue (US$m)"],
                         "rows": price_detail_rows},
                "catatan_sumber": (
                    f"Volume: {actual.get('source_title')}, hlm. 3; harga net realized: AMMAN H1 2026 Earnings Presentation, hlm. 22. "
                    "Harga bersih konsentrat setelah TCR dan "
                    "penyesuaian MTM pengiriman sebelumnya; harga produk murni setelah MTM. Volume logam "
                    "konsentrat H2 mempertahankan komposisi metal terjual per dmt H1; semua volume H2 adalah asumsi analis.")
            }
            doc["exhibits"].append(price_detail_exhibit)
            new_pages.append({
                "halaman": 0, "judul": "Net realized price dan volume logam",
                "layout": "stack",
                "paragraf": [_t(
                    "Harga aktual H1 dipakai sebagai basis nilai H2, bukan dianggap sebagai forward price. Konsentrat dihitung dari Cu dan Au terjual serta net realized price masing-masing; pemisahan ini menjaga kontribusi logam tetap terlihat.",
                    "Actual H1 prices are used as the basis for H2 value, not treated as a forward price. Concentrate is built from Cu and Au sold and the net realized price of each; this split keeps each metal's contribution visible.")],
                "exhibit": [price_detail_exhibit]})

        price_rows = []
        for key, label in (("copper", "Tembaga, benchmark LME"),
                           ("gold", "Emas, benchmark LBMA")):
            ref = market_refs.get(key)
            product_key = "cathode_copper" if key == "copper" else "refined_gold"
            actual_row = next((row for row in bridge["rows"]
                               if row["key"] == product_key), None)
            price_rows.append([
                label,
                (f"US$ {fmt._id(actual_row['unit_value'], 0)}/{actual_row['unit']}"
                 if actual_row else "-"),
                (f"US$ {fmt._id(ref['price'], 2)}/{_market_price_unit(ref['unit'])} ({ref['date']})"
                 if ref else "-"),
                "H1 revenue/unit dipertahankan datar untuk skenario; benchmark spot hanya pembanding.",
            ])
        conc = next((row for row in bridge["rows"]
                     if row["key"] == "concentrate"), None)
        price_rows.append([
            "Konsentrat, nilai penjualan efektif",
            (f"US$ {fmt._id(conc['unit_value'], 0)}/dmt" if conc else "-"),
            "Tidak sebanding dengan benchmark Cu/Au tanpa kadar payable dan TC-RC",
            "H1 revenue/dmt dipakai sebagai proxy datar; belum merupakan netback produk.",
        ])
        price_exhibit = {
            "n": 11.2, "judul": "Benchmark komoditas dan asumsi nilai realisasi",
            "tipe": "tabel",
            "data": {"cols": ["Produk", "Net realized H1 / nilai efektif",
                              "Benchmark pasar terbaru", "Basis harga skenario H2"],
                     "rows": price_rows},
            "catatan_sumber": "; ".join(
                f"{row['source_title']}: {row['source_url']}"
                for row in market_refs.values()) +
                ". Benchmark adalah spot bertanggal, bukan kurva forward atau kontrak penjualan AMMN."
        }
        doc["exhibits"].append(price_exhibit)
        new_pages.append({
            "halaman": 0, "judul": "Harga komoditas dan asumsi realisasi",
            "layout": "stack",
            "paragraf": [_t(
                "Model menahan nilai penjualan per unit H1 untuk skenario H2. Benchmark spot memberi konteks harga, tetapi belum menggantikan harga kontrak, premium katoda, payability, TC-RC, dan timing pengakuan penjualan.",
                "The model holds H1 sales value per unit for the H2 scenario. Spot benchmarks give price context but do not replace contract prices, cathode premiums, payability, TC-RC and the timing of sales recognition.")
            ],
            "exhibit": [price_exhibit]})

        comparison_rows = []
        brids = next((item for item in
                      (analyst_scenario.get("external_estimates") or [])
                      if ("brids" in str(item.get("name") or "").lower() or
                          ("bri" in str(item.get("name") or "").lower() and
                           "danareksa" in str(item.get("name") or "").lower()))), None)
        if brids:
            for label, key in (("Pendapatan", "revenue"),
                               ("EBITDA", "ebitda"),
                               ("Laba bersih", "net_profit")):
                h1 = scenario["h1"][key]
                h2 = scenario["h2"][key]
                fy = scenario["full_year"][key]
                peer = brids[f"{key}_usd_mn"] * 1e6
                comparison_rows.append([
                    label, fmt._id(h1 / 1e6, 1), fmt._id(h2 / 1e6, 1),
                    fmt._id(fy / 1e6, 1), fmt._id(peer / 1e6, 1),
                    fmt.pct(fy / peer - 1),
                ])
            comparison_exhibit = {
                "n": 11.3, "judul": "Estimasi FY26 Sektoral dibanding BRIDS",
                "tipe": "tabel",
                "data": {"cols": ["US$ juta", "1H26 aktual", "2H26 Sektoral",
                                  "FY26 Sektoral", "FY26 BRIDS", "Selisih"],
                         "rows": comparison_rows},
                "catatan_sumber": (
                    f"Sumber BRIDS: {brids['source_title']} ({brids['as_of']}), "
                    f"{brids['source_url']}. Satu house estimate, bukan konsensus; "
                    "manajemen menerbitkan panduan produksi, bukan guidance keuangan FY26.")
            }
            doc["exhibits"].append(comparison_exhibit)
            new_pages.append({
                "halaman": 0, "judul": "Estimasi FY26 dan pembanding",
                "layout": "stack",
                "paragraf": [_t(
                    "Skenario Sektoral berada di atas estimasi BRIDS untuk metrik laba utama, sementara target berbasis multiple belum memasukkan nilai aset Batu Hijau dan Elang melalui SOTP lengkap. Perbedaan ini menyorot dua hal: monetisasi H2 perlu direkonsiliasi ke volume dan harga, sedangkan nilai aset belum masuk ke target.",
                    "The Sektoral scenario sits above the BRIDS estimates on the main earnings metrics, while the multiple-based target does not yet capture Batu Hijau and Elang asset value through a full SOTP. The difference highlights two points: H2 monetisation must be reconciled to volumes and prices, and asset value is not yet in the target.")
                ],
                "exhibit": [comparison_exhibit]})
    forecast_index = next((i for i, page in enumerate(doc["bagian"])
                           if page["judul"].startswith("Forecast ") and
                           "rilis terbaru" in page["judul"]), None)
    if forecast_index is not None and new_pages:
        doc["bagian"][forecast_index + 1:forecast_index + 1] = new_pages
    for exhibit in doc["exhibits"]:
        title = exhibit["judul"]
        if lom_page and title == "Pemeriksaan sebelum rating dan target harga":
            exhibit["judul"] = "Bukti lanjutan untuk menguji target harga"
            exhibit["data"]["rows"][-1][1] = (
                "Target berbasis SOTP/LoM diterbitkan; capex Elang, izin ekspor konsentrat dan "
                "jadwal tambang tahunan emiten akan menguji ulang nilai aset.")
            continue
        if lom_page:
            continue
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
                "dicatat terpisah dari skenario FY EV/EBITDA.")
    doc["bagian"].sort(key=lambda page: min(
        (float(exhibit.get("n", 1e9)) for exhibit in page.get("exhibit") or []),
        default=1e9))
    ordered_exhibits = [doc["exhibits"][0]]
    seen_exhibits = {id(ordered_exhibits[0])}
    for page in doc["bagian"]:
        for exhibit in page.get("exhibit") or []:
            if id(exhibit) not in seen_exhibits:
                ordered_exhibits.append(exhibit)
                seen_exhibits.add(id(exhibit))
    doc["exhibits"] = ordered_exhibits
    for number, exhibit in enumerate(doc["exhibits"], 1):
        exhibit["n"] = number
    for page_number, page in enumerate(doc["bagian"], start=2):
        page["halaman"] = page_number
    if doc["cover"].get("key_financials"):
        rows = doc["cover"]["key_financials"]
        full = scenario["full_year"]
        forecast_values = [{"year": scenario["year"], **full}] + (forward or {}).get("rows", [])
        history = (intake.get("official_evidence") or {}).get("annual_actuals") or []
        prior = next((row for row in history if row.get("year") == scenario["year"] - 1), {})
        attributable_share = None
        if prior.get("net_profit") and prior.get("net_profit_attributable") is not None:
            attributable_share = prior["net_profit_attributable"] / prior["net_profit"]
        fx_rate = value.get("fx", {}).get("rate")
        current_ev_usd = None
        if fx_rate and fx_rate > 0 and value.get("net_debt_usd") is not None:
            current_ev_usd = (
                intake["price"] * value["shares"] / fx_rate
                + value["net_debt_usd"]
                + value.get("minority_interest_usd", 0))
        for row in rows:
            key = ("revenue" if row[0].startswith("Pendapatan") else
                   "ebitda" if row[0].startswith("EBITDA") else
                   "net_profit" if row[0].startswith("Laba bersih") else None)
            growth_key = ("revenue" if row[0].startswith("Pertumbuhan pendapatan") else
                          "ebitda" if row[0].startswith("Pertumbuhan EBITDA") else
                          "net_profit" if row[0].startswith("Pertumbuhan laba bersih") else None)
            metric = key or growth_key
            if metric:
                # Profit is the parent's share, like the actual columns and EPS: the
                # scenario's consolidated profit times the last official parent share.
                parent = metric == "net_profit" and attributable_share is not None
                previous_value = (prior.get("net_profit_attributable") if parent
                                  else prior.get(metric))
                for index, projection in enumerate(forecast_values, start=3):
                    if index >= len(row):
                        break
                    current_value = projection.get(metric)
                    if current_value is None:
                        continue
                    if parent:
                        current_value *= attributable_share
                    if key:
                        row[index] = fmt._id(current_value / 1e6, 1)
                    elif previous_value and previous_value > 0:
                        row[index] = fmt.pct(current_value / previous_value - 1)
                    previous_value = current_value
            elif row[0].startswith("EPS") and attributable_share is not None:
                for index, projection in enumerate(forecast_values, start=3):
                    if index >= len(row) or projection.get("net_profit") is None:
                        break
                    eps_cents = (projection["net_profit"] * attributable_share /
                                 value["shares"] * 100)
                    row[index] = fmt._id(eps_cents, 2)
            elif row[0].startswith("PER") and attributable_share is not None and fx_rate:
                for index, projection in enumerate(forecast_values, start=3):
                    if index >= len(row) or not projection.get("net_profit"):
                        break
                    eps_rupiah = (projection["net_profit"] * attributable_share /
                                  value["shares"] * fx_rate)
                    row[index] = fmt.mult(intake["price"] / eps_rupiah, 1)
            elif row[0].startswith("EV/EBITDA") and current_ev_usd is not None:
                for index, projection in enumerate(forecast_values, start=3):
                    if index >= len(row) or not projection.get("ebitda"):
                        break
                    row[index] = fmt.mult(current_ev_usd / projection["ebitda"], 1)
        doc["exhibits"][0]["catatan_sumber"] = (
            f"Sumber aktual: {(intake.get('official_evidence') or {}).get('annual_source_title')}; "
            f"{forecast_label} adalah estimasi Sektoral dari rilis interim "
            f"{scenario['source_url']} dan asumsi semester kedua. "
            + ("FY27F-FY30F dari jadwal LoM yang sama dengan valuasi SOTP/LoM. "
               if (fc.get("outyear_scenario") or {}).get("status") == "lom_schedule" else
               "FY27F-FY30F adalah skenario laba asumsi analis pada exhibit terpisah; "
               "bukan jadwal produksi LoM. " if forward else
               "FY27F-FY30F belum dimodelkan karena asumsi lanjutan belum tervalidasi. ")
            + "EPS/BVPS historis memakai jumlah saham "
            f"per {value['balance_period']} sebagai basis pro forma. EPS forecast "
            "mengasumsikan porsi laba pemilik induk sama dengan FY terakhir; PER "
            f"memakai harga {intake['price_date']} dan kurs {value['fx']['date']}; "
            "EV/EBITDA memakai harga kini, neraca interim, dan kurs tersebut. "
            "DPS/yield dan PBV forecast tidak dihitung tanpa asumsi dividen dan ekuitas.")
    # The SOTP/LoM valuation paragraph (lom_page["text"]), found by its wording.
    lom_marker = _t("memakai SOTP/LoM", "using SOTP/LoM, the Primary Method for miners")
    paragraph = next((p for p in doc["cover"].get("paragraf") or []
                      if lom_marker in str(p.get("isi") or "")), None)
    rows_fc = [{"year": scenario["year"], **scenario["full_year"]}] + (forward or {}).get("rows", [])
    if paragraph and len(rows_fc) >= 3 and value.get("fx", {}).get("rate"):
        first, third = rows_fc[0], rows_fc[2]
        cagr = lambda key: ((third[key] / first[key]) ** 0.5 - 1
                            if first.get(key) and third.get(key) and first[key] > 0 and third[key] > 0
                            else None)
        from . import forecast_statements
        split = forecast_statements.parent_share(intake, scenario)
        share = split[0] if split else 1.0
        eps_fy = (first["net_profit"] * share / value["shares"] * value["fx"]["rate"]
                  if first.get("net_profit") and value.get("shares") else None)
        pe_tp = va["tp"] / eps_fy if eps_fy and eps_fy > 0 and va.get("tp") else None
        from . import report_extras
        band = ((report_extras._band_data(intake) or {}).get("multiples") or {}).get("P/E")
        band_mean = band["mean"] if band and band["mean"] <= fmt.MULT_CAP else None
        compare = _t(" dan ", " and ").join(
            ([_t(f"median peer {fmt.mult(intake['peer_median_pe'], 1)}",
                 f"a peer median of {fmt.mult(intake['peer_median_pe'], 1)}")]
             if intake.get("peer_median_pe") else [])
            + ([_t(f"rata-rata band P/E historis {fmt.mult(band_mean, 1)}",
                   f"a historical P/E band mean of {fmt.mult(band_mean, 1)}")]
               if band_mean else []))
        extra = ""
        if cagr("ebitda") is not None:
            extra += _t(
                (f" Target ini mengimplikasikan pertumbuhan EBITDA CAGR {forecast_label}-"
                 f"{third['label']} {fmt.pct(cagr('ebitda'))}"
                 + (f", didorong pendapatan CAGR {fmt.pct(cagr('revenue'))} dari jadwal "
                    "LoM (umpan, logam dan dek harga)" if cagr("revenue") is not None else "")
                 + "."),
                (f" The target implies an EBITDA CAGR over {forecast_label}-"
                 f"{third['label']} of {fmt.pct(cagr('ebitda'))}"
                 + (f", driven by a revenue CAGR of {fmt.pct(cagr('revenue'))} from the LoM "
                    "schedule (feed, metal and price deck)" if cagr("revenue") is not None else "")
                 + "."))
        if pe_tp:
            extra += _t(
                (f" Pada target harga, saham diperdagangkan pada PER {forecast_label} "
                 f"{fmt.mult(pe_tp, 1, cap=fmt.MULT_CAP)}"
                 + (f", dibanding {compare}" if compare else "") + "."),
                (f" At the Target Price, the stock trades on a {forecast_label} PER of "
                 f"{fmt.mult(pe_tp, 1, cap=fmt.MULT_CAP)}"
                 + (f", versus {compare}" if compare else "") + "."))
        paragraph["isi"] = paragraph["isi"].rstrip() + extra
    doc["fy26"] = {
        "Pendapatan": fmt._id(scenario["full_year"]["revenue"] * value["fx"]["rate"] / 1e9, 0),
        "EBITDA": fmt._id(scenario["full_year"]["ebitda"] * value["fx"]["rate"] / 1e9, 0),
        "Laba bersih": fmt._id(scenario["full_year"]["net_profit"] * value["fx"]["rate"] / 1e9, 0),
    }
    return doc


def _selected_ddm_detail(va):
    """Return the DDM detail that actually set the selected model value."""
    chain = (va or {}).get("method_chain") or {}
    if chain.get("selected") != "ddm":
        return None
    return next((row.get("detail") for row in chain.get("trace") or []
                 if row.get("key") == "ddm" and isinstance(row.get("detail"), dict)), None)


def _bank_ddm_summary(detail):
    """Describe a selected DDM only when its per-share result is present."""
    if not isinstance(detail, dict):
        return None
    per_share = detail.get("per_share")
    method = "DDM skenario" if per_share is not None else "DDM Gordon"
    method_en = "Scenario DDM" if per_share is not None else "Gordon DDM"
    per_share = per_share if per_share is not None else detail.get("tp_gordon")
    if not isinstance(per_share, (int, float)):
        return None
    text = _t(f"{method} memberi Rp{fmt.rp(fmt.tick(per_share))}/saham; "
              f"{_ddm_payout_summary(detail)}.",
              f"{method_en} gives Rp{fmt.rp(fmt.tick(per_share))}/share; "
              f"{_ddm_payout_summary(detail)}.")
    inverse = detail.get("per_share_inverse", detail.get("tp_inverse"))
    if isinstance(inverse, (int, float)):
        fair = isinstance(detail.get("fair_pbv"), (int, float))
        text += _t(f" Silang cek Inverse CoE Rp{fmt.rp(fmt.tick(inverse))}/saham"
                   + (f" (P/BV wajar {fmt.mult(detail['fair_pbv'], 2)})" if fair else "") + ".",
                   f" Inverse CoE cross-check Rp{fmt.rp(fmt.tick(inverse))}/share"
                   + (f" (fair P/BV {fmt.mult(detail['fair_pbv'], 2)})" if fair else "") + ".")
    return text


def _ddm_payout_summary(detail):
    lines = detail.get("lines") or []
    payouts = [row.get("payout") for row in lines
               if isinstance(row.get("payout"), (int, float))]
    payout = detail.get("payout")
    if payout is None:
        payout = detail.get("payout_used")
    if payouts:
        years = "-".join((lines[0].get("label", "FY"), lines[-1].get("label", "FY")))
        text = (_t(f"payout skenario {years} ", f"scenario payout {years} ")
                + "/".join(fmt.pct(value) for value in payouts))
    elif payout is not None:
        text = f"payout {fmt.pct(payout)}"
    else:
        text = _t("payout skenario", "scenario payout")
    if detail.get("terminal_payout") is not None:
        text += _t(f"; payout terminal {fmt.pct(detail['terminal_payout'])}",
                   f"; terminal payout {fmt.pct(detail['terminal_payout'])}")
    return text


def _scenario_profit_change(intake, forecast):
    """Change in modeled parent profit versus the latest annual actual."""
    evidence = intake.get("official_evidence") or {}
    if evidence.get("reporting_currency") == "USD":
        actuals = [row for row in evidence.get("annual_actuals") or []
                   if isinstance(row, dict)]
    else:
        actuals = [row for row in intake.get("annuals") or [] if isinstance(row, dict)]
    if not actuals or not isinstance(forecast, dict):
        return None
    last = actuals[-1]
    prior = next((last.get(key) for key in
                  ("net_profit_attributable", "earnings", "net_profit")
                  if isinstance(last.get(key), (int, float))), None)
    current = next((forecast.get(key) for key in
                    ("net_profit_attributable", "earnings", "net_profit")
                    if isinstance(forecast.get(key), (int, float))), None)
    return current / prior - 1 if prior not in (None, 0) and current is not None else None


def _earnings_headline(label, profit_change):
    """Describe the FY scenario against the latest annual actual, without a call."""
    if profit_change is None:
        return _t(f"Skenario laba {label} dibanding hasil tahunan terakhir",
                  f"{label} earnings scenario against the latest annual result")
    direction = "naik" if profit_change > 0.02 else "turun" if profit_change < -0.02 else "sejalan"
    direction_en = ("above" if profit_change > 0.02 else "below" if profit_change < -0.02
                    else "in line with")
    return _t(f"Skenario laba {label} {direction} dari aktual tahunan terakhir",
              f"{label} earnings scenario {direction_en} the latest annual actual")


def _card_title(text, cap=7):
    """Short card title: the claim's opening clause, at most ``cap`` words."""
    clause = re.split(r"[,;:.]", text.strip(), maxsplit=1)[0]
    words = clause.split()
    return " ".join(words[:cap]) + ("..." if len(words) > cap else "")


def _shares_source(evidence):
    """Where the share count came from: a pack may take it from a source other
    than the filed balance sheet and says so in ``balance_sheet.shares_source``."""
    return ((evidence or {}).get("balance_sheet") or {}).get("shares_source")


def _thesis_cards_page(intake, thesis, fy, va, label, usd, to_idr, titles=None):
    """Design 'Tesis investasi': each forward claim beside the model figure it
    moves (revenue growth, net margin, upside), all from sourced numbers."""
    annual = [a for a in intake.get("annuals") or [] if a.get("revenue")]
    evidence = intake.get("official_evidence") or {}
    if usd:
        # Sectors history for USD reporters is translated to IDR at the
        # historical rate. Compare the native-currency scenario only with the
        # issuer's native-currency official annual actuals.
        official_annuals = [a for a in evidence.get("annual_actuals") or []
                            if isinstance(a.get("revenue"), (int, float)) and a["revenue"] > 0]
        last_revenue = official_annuals[-1]["revenue"] if official_annuals else None
        last_year = official_annuals[-1].get("year") if official_annuals else None
        current_revenue = fy.get("revenue")
    else:
        last_revenue = annual[-1]["revenue"] if annual else None
        last_year = annual[-1].get("year") if annual else None
        current_revenue = fy.get("revenue")
    metrics = []
    if last_revenue and current_revenue is not None:
        metrics.append((fmt.pct(current_revenue / last_revenue - 1),
                        f"Pendapatan skenario {label} vs {last_year} (mata uang pelaporan)"))
    else:
        metrics.append((None, f"Pendapatan {label} vs aktual tahunan: data sebanding tidak tersedia"))
    if fy.get("revenue"):
        metrics.append((fmt.pct(fy["net_profit"] / fy["revenue"]), f"Margin laba bersih {label}"))
    if va.get("upside") is not None:
        metrics.append((fmt.pct(va["upside"]), f"Ke target Rp{fmt.rp(va['tp'])}"))
    cards = []
    for i, point in enumerate(thesis):
        metric, metric_label = metrics[i] if i < len(metrics) else (None, None)
        title = (titles[i] if titles and i < len(titles) else _card_title(point))
        cards.append({"title": title, "text": point,
                      "metric": metric, "metric_label": metric_label})
    return {"halaman": 0, "judul": "Tesis investasi", "layout": "cards",
            "paragraf": [_t("Pandangan kami tentang driver laba ke depan; angka di kanan "
                            "adalah hasil model yang digerakkan oleh tiap tesis.",
                            "Our view of the forward earnings drivers; the figure on the right "
                            "is the model output each thesis moves.")],
            "cards": cards, "exhibit": []}


def _ddm_scenario_exhibits(intake, ddm_s, label):
    """Opsi B: dividend forecast, terminal value and CoE x g sensitivity."""
    lines = ddm_s["lines"]
    bn = lambda v: fmt._id(v / 1e9, 1)
    cols = ["Rp"] + [x["label"] for x in lines]
    # First-year growth against the last fiscal year's DPS: the payout basis is
    # the dividends of the last twelve months, which are that year's payout.
    last = (intake.get("annuals") or [{}])[-1]
    prior_dps = (intake["payout"] * last["earnings"] / intake["shares"]
                 if str(intake.get("payout_basis") or "").startswith("DPS 12 bulan terakhir")
                 and last.get("earnings") and intake.get("shares") and intake.get("payout")
                 else None)
    cut = [x["label"] for x in lines
           if x.get("payout") is not None and x["payout"] < ddm_s["payout"] - 1e-9]
    growth, gaps = [], []
    for i, x in enumerate(lines):
        value = x.get("dps_growth") if i else (
            x["dps"] / prior_dps - 1 if prior_dps and prior_dps > 0 else None)
        growth.append(fmt.pct(value) if value is not None else "n.m.")
        if value is None:
            gaps.append(x["label"])
    growth_note = (
        (f" Pertumbuhan DPS {lines[0]['label']} terhadap DPS FY{last.get('year')} "
         f"Rp{fmt._id(prior_dps, 1)} (DPS 12 bulan terakhir, data Sectors)." if prior_dps else "")
        + (f" Pertumbuhan DPS {', '.join(gaps)} n.m.: "
           + ("DPS tahun buku sebelumnya tidak tersedia di data Sectors (payout "
              f"{ddm_s['payout_basis']})" if lines[0]["label"] in gaps else
              "DPS tahun sebelumnya nol") + "." if gaps else ""))
    table = {
        "n": 0, "judul": f"Proyeksi dividen dan nilai kini (DDM, {label}-{lines[-1]['label']})",
        "tipe": "tabel",
        "data": {"cols": cols, "rows": [
            ["Laba pemilik induk (Rp miliar)"] + [bn(x["net_attr"]) for x in lines],
            ["Payout ratio"] + [fmt.pct(x.get("payout", ddm_s["payout"])) for x in lines],
            ["DPS (Rp)"] + [fmt.rp(round(x["dps"])) for x in lines],
            ["Pertumbuhan DPS"] + growth,
            ["Waktu terima (tahun)"] + [fmt._id(x["t"], 2) for x in lines],
            [f"Faktor diskonto (CoE {fmt.pct(ddm_s['coe'])})"] + [fmt._id(x["factor"], 3)
                                                                  for x in lines],
            ["PV DPS (Rp)"] + [fmt.rp(round(x["pv"])) for x in lines]]},
        "catatan_sumber": (
            (f"Sumber: laba pemilik induk model driver bank (aktual 1H resmi + H2 model dari "
             f"driver analis untuk {label}, driver tahunan sesudahnya: kredit, NIM, pendapatan "
             f"non-bunga, rasio biaya dan biaya kredit); {_ddm_payout_summary(ddm_s)} "
             if ddm_s.get("profit_basis") == "bank_driver_scenario" else
             f"Sumber: laba pemilik induk skenario analis (aktual 1H resmi + asumsi H2 untuk "
             f"{label}, asumsi tahunan sesudahnya); {_ddm_payout_summary(ddm_s)} ")
            + f"({ddm_s['payout_basis']})"
            + (f", diturunkan pada {', '.join(cut)} oleh batas modal model driver bank (CAR "
               "screening tidak di bawah CAR terendah historis)" if cut else "")
            + f"; saham {ddm_s['shares_basis']}; tanggal valuasi {ddm_s['valuation_date']}, "
            "dividen diasumsikan diterima satu kuartal sesudah tahun buku." + growth_note)}
    terminal = {
        "n": 0, "judul": "Nilai terminal dan nilai wajar per saham (DDM)", "tipe": "tabel",
        "data": {"cols": ["Komponen", "Nilai"], "rows": [
            ["Jumlah PV DPS eksplisit (Rp)", fmt.rp(round(ddm_s["pv_dps"]))],
            ([f"DPS terminal = DPS {lines[-1]['label']} x (1 + g) (Rp)",
              fmt.rp(round(ddm_s["terminal_dps"]))]
             if ddm_s.get("terminal_payout") is None else
             [f"DPS terminal = EPS {lines[-1]['label']} x (1 + g) x payout terminal "
              f"{fmt.pct(ddm_s['terminal_payout'])} (Rp)", fmt.rp(round(ddm_s["terminal_dps"]))]),
            ["Pertumbuhan terminal g", fmt.pct(ddm_s["g"])],
            ["Nilai terminal = DPS terminal / (CoE - g) (Rp)", fmt.rp(round(ddm_s["tv"]))],
            ["PV nilai terminal (Rp)", fmt.rp(round(ddm_s["pv_tv"]))],
            ["Porsi terminal terhadap nilai", fmt.pct(ddm_s["tv_share"])],
            ["Nilai wajar per saham (Rp)", fmt.rp(fmt.tick(ddm_s["per_share"]))]]
            + ([[f"CoE tersirat harga Rp{fmt.rp(intake['price'])} ({intake['price_date']})",
                 fmt.pct(ddm_s["implied_coe"])]] if ddm_s.get("implied_coe") else [])
            + ([[f"Silang cek Inverse CoE: ROAE {ddm_s['fwd_label']}", fmt.pct(ddm_s["roe_fwd"])],
                ["P/BV wajar = (ROAE - g) / (CoE - g)", fmt.mult(ddm_s["fair_pbv"], 2)],
                [f"BVPS {ddm_s['fwd_label']} (Rp)", fmt.rp(round(ddm_s["bvps_fwd"]))],
                ["Nilai Inverse CoE per saham (Rp, silang cek)",
                 fmt.rp(fmt.tick(ddm_s["per_share_inverse"]))]]
               if ddm_s.get("per_share_inverse") else [])},
        "catatan_sumber": ("Sumber: Sektoral Estimates; CoE CAPM dan g menggunakan house policy "
                           + (f" Payout terminal: {ddm_s['terminal_payout_basis']}."
                              if ddm_s.get("terminal_payout") is not None else "")
                           + (f" Inverse CoE memakai ROAE dan BVPS {ddm_s['fwd_label']} model "
                              "driver bank; silang cek, tidak dirata-rata dengan DDM."
                              if ddm_s.get("per_share_inverse") else ""))}
    growths = sorted({gg for (_, gg) in ddm_s["grid"]})
    rows = []
    for delta in sorted({dw for (dw, _) in ddm_s["grid"]}):
        rate = ddm_s["coe"] + delta
        row = [f"CoE {fmt.pct(rate)}" + (" (basis)" if delta == 0 else "")]
        for gg in growths:
            value = ddm_s["grid"].get((delta, gg))
            row.append(f"Rp{fmt.rp(fmt.tick(value))}" if value else "n.m.")
        rows.append(row)
    grid = {"n": 0, "judul": "Sensitivitas nilai DDM: CoE x pertumbuhan terminal",
            "tipe": "tabel",
            "data": {"cols": ["Cost of equity"] + [f"g {fmt.pct(gg)}" for gg in growths],
                     "rows": rows},
            "catatan_sumber": ("Sumber: Sektoral Estimates; basis sama dengan target harga. "
                               "P/BV-ROE FY dan PER FY skenario menjadi cross-check.")}
    return [table, terminal, grid]


def _dcf_scenario_exhibits(intake, dcf_s, label, forward):
    """Opsi A: FCFF forecast, terminal and EV-to-equity bridge, WACC, sensitivity.

    Amounts are in the model currency (a US$ reporter in US$ juta, spec §2);
    the value per share converts to rupiah once, on the bridge's last rows.
    """
    usd_model = dcf_s.get("currency") == "USD"
    money_s = scenario_value.native_view(dcf_s)
    lines = money_s["lines"]
    scale, unit = (1e6, "US$ juta") if usd_model else (1e9, "Rp miliar")
    bn = lambda v: "-" if v is None else (
        f"({fmt._id(abs(v) / scale, 1)})" if v < 0 else fmt._id(v / scale, 1))
    # Columns hold full fiscal years; a year the valuation date splits is
    # counted in PV by its share after that date (the "Porsi periode" row).
    head = [x["label"] for x in lines]
    partial = [x["label"] for x in lines if x.get("share", 1) < 0.999]
    # First-year growth against FY-1 FCFF on this table's definition: Sectors
    # EBIT, D&A and capex of that year, the table's tax rate and working-capital
    # intensity. A US$ reporter's Sectors figures carry historical conversion
    # rates, not the table's spot rate, so its growth would be an FX effect.
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    first_year = int(lines[0]["label"][2:4]) + 2000
    annual = {a.get("year"): a for a in intake.get("annuals") or []}
    last, before = annual.get(first_year - 1) or {}, annual.get(first_year - 2) or {}
    parts = [last.get(k) for k in ("ebit", "da", "capex_out", "revenue")]
    prior_fcff, prior_reason = None, None
    if usd:
        prior_reason = (f"EBIT, D&A dan capex FY{first_year - 1} dalam US$ tidak tersedia; data "
                        "Sectors memuatnya dalam rupiah hasil konversi pada kurs historis")
    elif any(v is None for v in parts) or not before.get("revenue"):
        missing = [name for name, v in zip(("EBIT", "D&A", "capex", "pendapatan"), parts)
                   if v is None] or [f"pendapatan FY{first_year - 2}"]
        prior_reason = (f"{', '.join(missing)} FY{first_year - 1} tidak tersedia (data Sectors "
                        "tidak melaporkannya atau nilainya ditolak intake)")
    else:
        ebit, da, capex, revenue = parts
        prior_fcff = (ebit - max(ebit, 0.0) * dcf_s["tax_rate"] + da - abs(capex)
                      - (dcf_s.get("nwc_ratio") or 0.0) * (revenue - before["revenue"]))
        if prior_fcff <= 0:
            prior_reason = (f"FCFF FY{first_year - 1} Rp{fmt._id(prior_fcff / 1e9, 1)} miliar "
                            "tidak positif")
    fcff_growth, fcff_gaps = [], []
    for i, x in enumerate(lines):
        value = x.get("fcff_growth") if i else (
            x["fcff"] / prior_fcff - 1 if prior_fcff and prior_fcff > 0 and x["fcff"] > 0 else None)
        fcff_growth.append(fmt.pct(value) if value is not None else "n.m.")
        if value is None:
            fcff_gaps.append(x["label"])
    fcff_note = (
        (f" Pertumbuhan FCFF {lines[0]['label']} terhadap FCFF FY{first_year - 1} "
         f"Rp{fmt._id(prior_fcff / 1e9, 1)} miliar (EBIT, D&A dan capex data Sectors; pajak "
         "dan modal kerja dengan asumsi tabel ini)." if prior_fcff and prior_fcff > 0 else "")
        + (f" Pertumbuhan FCFF {', '.join(fcff_gaps)} n.m.: "
           + "; ".join(([prior_reason] if lines[0]["label"] in fcff_gaps and prior_reason else [])
                       + (["FCFF tahun itu atau tahun sebelumnya tidak positif"]
                          if [g for g in fcff_gaps if g != lines[0]["label"]] or
                          (lines[0]["label"] in fcff_gaps and not prior_reason) else []))
           + "." if fcff_gaps else ""))
    fcff = {
        "n": 0, "judul": f"Proyeksi FCFF dan nilai kini ({label}-{lines[-1]['label']})",
        "tipe": "tabel",
        "data": {"cols": [unit] + head, "rows": [
            ["Pendapatan"] + [bn(x["revenue"]) for x in lines],
            ["EBITDA"] + [bn(x["ebitda"]) for x in lines],
            ["(-) D&A"] + [bn(x["da"]) for x in lines],
            ["EBIT"] + [bn(x["ebit"]) for x in lines],
            [f"(-) Pajak atas EBIT ({fmt.pct(dcf_s['tax_rate'])})"] + [bn(x["tax"]) for x in lines],
            ["NOPAT"] + [bn(x["nopat"]) for x in lines],
            ["(+) D&A"] + [bn(x["da"]) for x in lines],
            ["(-) Capex"] + [bn(x["capex"]) for x in lines],
            ["(-) Kenaikan modal kerja"] + [bn(x["dnwc"]) for x in lines],
            ["FCFF"] + [bn(x["fcff"]) for x in lines],
            ["Pertumbuhan FCFF"] + fcff_growth,
            ["Porsi periode sesudah tanggal valuasi"] + [fmt.pct(x["share"]) for x in lines],
            [f"Faktor diskonto (WACC {fmt.pct(dcf_s['wacc'])})"] + [fmt._id(x["factor"], 3)
                                                                   for x in lines],
            ["PV FCFF"] + [bn(x["pv"]) for x in lines]]},
        "catatan_sumber": (
            "Sumber: pendapatan, margin EBITDA dan capex skenario analis (aktual 1H resmi + "
            f"asumsi H2 untuk {label}, asumsi tahunan sesudahnya); D&A {dcf_s['da_basis']}; "
            f"pajak {dcf_s['tax_basis']}; {dcf_s['nwc_basis']}. Konvensi mid-period dari "
            f"tanggal valuasi {dcf_s['valuation_date']}"
            + (f" ({dcf_s['anchor_reason']})" if dcf_s.get("anchor_reason") else "") + "."
            + (f" Kolom {', '.join(partial)} memuat setahun penuh; PV hanya menghitung porsi "
               "sesudah tanggal valuasi." if partial else "")
            + (" Model dalam US$, mata uang pelaporan emiten; konversi ke rupiah hanya pada "
               "nilai per saham." if usd_model else "")
            + fcff_note)}
    exit_col = dcf_s.get("per_share_exit") is not None
    minority = (f"(-) Minoritas ({dcf_s['nci_basis']})" if dcf_s.get("nci") is not None else
                f"(x) Porsi induk ({dcf_s['nci_basis']})")

    paid_out = money_s.get("distributions") or 0.0
    fx_text = (f"Kurs Rp/US$ (Yahoo Finance IDR=X, {dcf_s.get('fx_date') or '-'})"
               if usd_model else None)

    def bridge_rows(ev, tv, pv_tv, per_share, per_share_native):
        # A US$ model: equity and per-share value in US$, then the one
        # conversion to rupiah at the dated spot rate.
        own = per_share_native if usd_model else per_share
        return [bn(tv), fmt._id(pv_tv / tv, 3) if tv else "n.m.",
                bn(pv_tv), bn(money_s["pv_explicit"]), bn(ev), bn(money_s["cash"]),
                bn(-money_s["debt"])] + ([bn(-paid_out)] if paid_out else []) + [
                bn(-money_s["nci"]) if money_s.get("nci") is not None else
                fmt.pct(dcf_s["attributable_share"]),
                bn(own * dcf_s["shares"]), fmt._id(dcf_s["shares"] / 1e9, 2)] + (
                [_usd_per_share(per_share_native), fmt._id(dcf_s["fx"], 0)] if usd_model
                else []) + [
                fmt.rp(fmt.tick(per_share))]

    labels = ["Nilai terminal (tidak didiskonto)", "Faktor diskonto terminal",
              "PV nilai terminal", "Jumlah PV FCFF",
              "Enterprise value", f"(+) Kas ({dcf_s['cash_basis']})",
              f"(-) Utang ({dcf_s['debt_basis']})"] + (
                  [f"(-) Dividen dibagikan sesudah tanggal neraca "
                   f"({dcf_s['distributions_basis']})"] if paid_out else []) + [
              minority, "Nilai ekuitas pemilik induk",
              f"Saham (miliar, {dcf_s['shares_basis']})"] + (
                  ["Ekuitas per saham (US$)", fx_text] if usd_model else []) + [
              "Nilai wajar per saham (Rp)"]
    gordon = bridge_rows(money_s["ev"], money_s["tv"], money_s["pv_tv"], dcf_s["per_share"],
                         money_s.get("per_share_native"))
    exit_values = (bridge_rows(money_s["ev_exit"], money_s["tv_exit"], money_s["pv_tv_exit"],
                               dcf_s["per_share_exit"], money_s.get("per_share_exit_native"))
                   if exit_col else [])
    rows = ([[f"FCFF terminal = FCFF {lines[-1]['label']} dengan capex >= D&A, x (1 + g)",
              bn(money_s["terminal_fcff"])] + (["-"] if exit_col else [])] +
            [[name, g_] + ([x_] if exit_col else []) for name, g_, x_ in
             zip(labels, gordon, exit_values or [""] * len(labels))])
    terminal = {
        "n": 0, "judul": "Nilai terminal dan jembatan EV ke ekuitas", "tipe": "tabel",
        "data": {"cols": [unit, f"Gordon g {fmt.pct(dcf_s['g'])} (basis)"]
                 + ([f"Exit {fmt.mult(dcf_s['exit_multiple'], 1)} (cross-check)"]
                    if exit_col else []),
                 "rows": rows},
        "catatan_sumber": (
            f"Sumber: Sektoral Estimates; porsi terminal {fmt.pct(dcf_s['tv_share'])} dari EV; "
            f"implied exit EV/EBITDA Gordon {fmt.mult(dcf_s['implied_exit'], 1)}"
            + (f"; exit = median EV/EBITDA historis emiten di data Sectors "
               f"({', '.join(fmt.mult(v, 1) for v in dcf_s['exit_points'])}); selisih "
               f"{fmt.pct(dcf_s['exit_gap'])} diungkapkan, tidak dirata-rata."
               if exit_col else "; exit historis kurang dari tiga titik.")
            + (f" Nilai dalam US$ sampai ekuitas per saham, lalu dikonversi ke rupiah satu kali "
               f"pada kurs spot Rp{fmt._id(dcf_s['fx'], 0)}/US$ ({dcf_s.get('fx_date') or '-'})."
               if usd_model else ""))}
    rf_row = ([f"Risk-free (UST 10Y, {dcf_s.get('rf_date') or '-'})", fmt.pct(dcf_s["rf"])]
              if usd_model else ["Risk-free IDR (house policy)", fmt.pct(dcf_s["rf"])])
    crp_rows = ([["Country risk premium Indonesia (parameter kebijakan analis)",
                  fmt.pct(dcf_s["crp"])]] if usd_model else [])
    wacc = {
        "n": 0, "judul": "Komponen WACC" + (" (US$)" if usd_model else ""), "tipe": "tabel",
        "data": {"cols": ["Parameter", "Nilai"], "rows": [
            rf_row, *crp_rows,
            ["Beta", fmt._id(dcf_s["beta"], 2)],
            ["Equity risk premium", fmt.pct(dcf_s["erp"])],
            ["Cost of equity (CAPM)", fmt.pct(dcf_s["coe"])],
            ["Cost of debt sebelum pajak", fmt.pct(dcf_s["kd_pretax"])],
            ["Tarif pajak efektif", fmt.pct(dcf_s["tax_rate"])],
            ["Cost of debt setelah pajak", fmt.pct(dcf_s["kd_after"])],
            ["Bobot utang (nilai pasar)", fmt.pct(dcf_s["weight_debt"])],
            ["Bobot ekuitas (nilai pasar)", fmt.pct(1 - dcf_s["weight_debt"])],
            # Template Exhibit 9: WACC closes the table; implied rates go to the note.
            ["WACC", fmt.pct(dcf_s["wacc"])]]},
        "catatan_sumber": (
            (f"Sumber: model US$; Rf = UST 10Y {fmt.pct(dcf_s['rf'])} "
             f"({_rf_source(dcf_s.get('rf_source'))}, "
             f"{dcf_s.get('rf_date')}); CRP Indonesia {fmt.pct(dcf_s['crp'])}, beta dan ERP "
             f"{fmt.pct(dcf_s['erp'], 0)} (mature market) parameter kebijakan analis; biaya utang "
             f"{dcf_s.get('kd_basis')}; bobot dari kapitalisasi pasar (harga {intake['price_date']}, "
             f"ke US$ pada kurs Rp{fmt._id(dcf_s['fx'], 0)}/US$) dan utang "
             f"({dcf_s['debt_basis']})" if usd_model else
             f"Sumber: rf, beta dan ERP house policy; bobot dari kapitalisasi pasar "
             f"(harga {intake['price_date']}) dan utang ({dcf_s['debt_basis']})")
            + (f"; penyesuaian berita {dcf_s['wacc_bps']:+g} bp" if dcf_s.get("wacc_bps") else "")
            + (f". WACC tersirat harga Rp{fmt.rp(intake['price'])} ({intake['price_date']}) "
               f"{fmt.pct(dcf_s['implied_wacc'])}; CoE tersirat pada bobot utang yang sama "
               f"{fmt.pct(dcf_s['implied_coe'])}"
               if dcf_s.get("implied_wacc") and dcf_s.get("implied_coe") else "")
            + ".")}
    growths = sorted({gg for (_, gg) in dcf_s["grid"]})
    grid_rows = []
    for delta in sorted({dw for (dw, _) in dcf_s["grid"]}):
        rate = dcf_s["wacc"] + delta
        row = [f"WACC {fmt.pct(rate)}" + (" (basis)" if delta == 0 else "")]
        for gg in growths:
            value = dcf_s["grid"].get((delta, gg))
            row.append(f"Rp{fmt.rp(fmt.tick(value))}" if value else "n.m.")
        grid_rows.append(row)
    grid = {"n": 0, "judul": "Sensitivitas nilai DCF: WACC x pertumbuhan terminal",
            "tipe": "tabel",
            "data": {"cols": ["WACC"] + [f"g {fmt.pct(gg)}" for gg in growths],
                     "rows": grid_rows},
            "catatan_sumber": "Sumber: Sektoral Estimates; basis sama dengan target harga (Gordon)."
            + (f" WACC dan g dalam US$; nilai per saham US$ dikonversi ke rupiah pada kurs "
               f"Rp{fmt._id(dcf_s['fx'], 0)}/US$ ({dcf_s.get('fx_date') or '-'})."
               if usd_model else "")}
    return [fcff, terminal, wacc, grid]


def _usd_per_share(value):
    """US$ per share with four significant digits (a Rp56 share is US$0,003140)."""
    return fmt._id(value, 6 if abs(value) < 0.01 else 5 if abs(value) < 0.1 else 4)


def _dcf_bridge_sentence(dcf_s):
    """EV to equity in the model currency; a US$ model states its one conversion."""
    if dcf_s.get("currency") == "USD":
        m = scenario_value.native_view(dcf_s)
        usd = lambda v: fmt._id(v / 1e6, 1)  # noqa: E731
        return _t(
            f"Dalam US$, mata uang pelaporan: EV US${usd(m['ev'])} juta ditambah kas "
            f"US${usd(m['cash'])} juta, dikurangi utang US${usd(m['debt'])} juta dan porsi "
            f"minoritas, memberi ekuitas US${usd(m['equity'])} juta, dikonversi ke rupiah pada "
            f"kurs Rp{fmt._id(dcf_s['fx'], 0)}/US$. ",
            f"In US$, the reporting currency: EV of US${usd(m['ev'])} juta plus cash of "
            f"US${usd(m['cash'])} juta, less debt of US${usd(m['debt'])} juta and minorities, "
            f"gives equity of US${usd(m['equity'])} juta, converted to rupiah at "
            f"Rp{fmt._id(dcf_s['fx'], 0)}/US$. ")
    bn = lambda v: fmt._id(v / 1e9, 1)  # noqa: E731
    return _t(
        f"EV Rp{bn(dcf_s['ev'])} miliar ditambah kas Rp{bn(dcf_s['cash'])} miliar, dikurangi "
        f"utang Rp{bn(dcf_s['debt'])} miliar dan porsi minoritas, memberi ekuitas "
        f"Rp{bn(dcf_s['equity'])} miliar. ",
        f"EV of Rp{bn(dcf_s['ev'])} miliar plus cash of Rp{bn(dcf_s['cash'])} miliar, less "
        f"debt of Rp{bn(dcf_s['debt'])} miliar and minorities, gives equity of "
        f"Rp{bn(dcf_s['equity'])} miliar. ")


def _peer_source_en(text):
    """``method_chain.peer_ev_sources`` in English ('data Sectors dan Yahoo Finance')."""
    for id_text, en_text in (("data Sectors", "Sectors data"), (" dan ", " and "),
                             ("sumber tidak tercatat", "unrecorded sources"),
                             ("tanpa peer", "no peers")):
        text = str(text).replace(id_text, en_text)
    return text


def _scenario_primary_notes(ddm_s, dcf_s, label, forward, ev_s=None, intake_price=None):
    from . import prose_lang
    src = prose_lang.source
    last = forward[-1]["label"] if forward else label
    if ev_s:
        return [
            _t("Rating dan target harga memakai EV/EBITDA peer forward, metode untuk aset yang masih "
               "ramping atau riwayat singkat: EV = median EV/EBITDA "
               f"{ev_s['peer_count']} peer {fmt.mult(ev_s['median_ev_ebitda'], 1)} x EBITDA {label} "
               "skenario analis (aktual 1H resmi + margin EBITDA asumsi agen).",
               "Rating and Target Price use forward peer EV/EBITDA, the method for assets still "
               "ramping up or with a short history: EV = median EV/EBITDA of "
               f"{ev_s['peer_count']} peers {fmt.mult(ev_s['median_ev_ebitda'], 1)} x {label} "
               "EBITDA from the Analyst Scenario (official 1H actuals + agent-assumed EBITDA "
               "margin)."),
            _t(f"EV/EBITDA tiap peer dihitung dari {ev_s['peer_source']}: kapitalisasi pasar "
               "ditambah utang dikurangi kas dan EBITDA terakhir dari laporan peer "
               "(laporan Sectors FY bila di-cache, selain itu snapshot Yahoo Finance bertanggal, "
               "12 bulan terakhir bila empat kuartal tersedia); "
               "peer dianggap sebanding. Peer tanpa laporan di kedua sumber tidak masuk median.",
               f"Each peer's EV/EBITDA is calculated from {_peer_source_en(ev_s['peer_source'])}: "
               "market cap plus debt less cash, and the latest EBITDA from the peer's reports "
               "(Sectors FY reports when cached, otherwise a dated Yahoo Finance snapshot, the "
               "last 12 months when four quarters are available); peers are taken as comparable. "
               "Peers without reports in either source are left out of the median."),
            _t(f"Ekuitas = EV + kas ({ev_s.get('cash_basis') or '-'}) - utang "
               f"({ev_s.get('debt_basis') or '-'}) - minoritas, dibagi saham "
               f"{ev_s.get('shares_basis') or '-'}; tanggal valuasi {ev_s['valuation_date']}. "
               "Kuartil bawah dan atas peer menjadi sensitivitas.",
               f"Equity = EV + cash ({src(ev_s.get('cash_basis') or '-')}) - debt "
               f"({src(ev_s.get('debt_basis') or '-')}) - minorities, divided by shares "
               f"({src(ev_s.get('shares_basis') or '-')}); valuation date "
               f"{ev_s['valuation_date']}. The lower and upper peer quartiles are the "
               "sensitivity."),
            _t("PER FY skenario menjadi langkah berikutnya di rantai metode, tidak dirata-rata "
               "dengan target. DCF menunggu tiga tahun kondisi stabil.",
               "Scenario FY PER is the next step in the Method Chain, not averaged into the "
               "target. DCF waits for three years of steady state."),
            _t("Skenario bukan forecast driver yang sudah direkonsiliasi; statusnya berbasis asumsi.",
               "The scenario is not a reconciled driver forecast; its status is Assumption-Led."),
            _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
        ]
    if ddm_s:
        bank_drivers = ddm_s.get("profit_basis") == "bank_driver_scenario"
        implied = bool(ddm_s.get("implied_coe") and intake_price)
        return [
            _t("Rating dan target harga memakai DDM, metode utama bank: DPS = laba pemilik induk "
               f"skenario analis {label}-{last}; {_ddm_payout_summary(ddm_s)} "
               f"(basis {ddm_s['payout_basis']}), didiskonto dengan Cost of Equity, terminal Gordon.",
               "Rating and Target Price use DDM, the Primary Method for banks: DPS = parent "
               f"profit in the Analyst Scenario {label}-{last}; {_ddm_payout_summary(ddm_s)} "
               f"(basis {src(ddm_s['payout_basis'])}), discounted at the Cost of Equity, Gordon "
               "terminal."),
            (_t(f"Laba {label} dari aktual 1H resmi dan H2 model driver bank; tahun sesudahnya "
                "dari driver bank tahunan asumsi analis (kredit, NIM, pendapatan non-bunga, rasio "
                "biaya, biaya kredit), dengan neraca, pendanaan dan modal pada rasio historis "
                "emiten (screening). Skenario ini bukan forecast driver yang sudah direkonsiliasi, "
                "sehingga statusnya berbasis asumsi.",
                f"{label} profit comes from official 1H actuals and an H2 bank driver model; later "
                "years from analyst-assumed annual bank drivers (loans, NIM, non-interest income, "
                "cost ratio, cost of credit), with the balance sheet, funding and capital at the "
                "issuer's historical ratios (screening). This scenario is not a reconciled driver "
                "forecast, so its status is Assumption-Led.")
             if bank_drivers else
             _t(f"Laba {label} dari aktual 1H resmi dan asumsi H2; tahun sesudahnya asumsi analis "
                "tahunan. Skenario ini bukan forecast driver yang sudah direkonsiliasi, sehingga "
                "statusnya berbasis asumsi.",
                f"{label} profit comes from official 1H actuals and H2 assumptions; later years "
                "from annual analyst assumptions. This scenario is not a reconciled driver "
                "forecast, so its status is Assumption-Led.")),
            _t(f"CoE {fmt.pct(ddm_s['coe'])} dari CAPM (rf IDR house policy, beta dan ERP 4% kebijakan "
               f"analis); g {fmt.pct(ddm_s['g'])}. Tanggal valuasi {ddm_s['valuation_date']}; "
               "dividen diterima satu kuartal sesudah tahun buku."
               + (f" Pada harga Rp{fmt.rp(intake_price)}, jalur dividen yang sama menyiratkan CoE "
                  f"{fmt.pct(ddm_s['implied_coe'])}; target mengandaikan pasar menerima CoE "
                  f"kebijakan {fmt.pct(ddm_s['coe'])}."
                  if implied else ""),
               f"CoE of {fmt.pct(ddm_s['coe'])} from CAPM (IDR rf per house policy, beta and a 4% "
               f"ERP as analyst policy); g {fmt.pct(ddm_s['g'])}. Valuation date "
               f"{ddm_s['valuation_date']}; dividends are received one quarter after the "
               "financial year."
               + (f" At the Rp{fmt.rp(intake_price)} price, the same dividend path implies a CoE "
                  f"of {fmt.pct(ddm_s['implied_coe'])}; the target assumes the market accepts "
                  f"the policy CoE of {fmt.pct(ddm_s['coe'])}."
                  if implied else "")),
            _t("P/BV-ROE FY dan PER FY skenario menjadi cross-check di rantai metode, tidak "
               "dirata-rata dengan target.",
               "Scenario FY P/BV-ROE and FY PER are cross-checks in the Method Chain, not "
               "averaged into the target."),
            _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
        ]
    operating = dcf_s.get("operating_model")
    usd_model = dcf_s.get("currency") == "USD"
    implied = bool(dcf_s.get("implied_wacc") and dcf_s.get("implied_coe") and intake_price)
    return [
        (_t("Rating dan target harga memakai DCF FCFF, metode utama going concern, atas model "
            f"operasional {label}-{last}: volume x harga per segmen, biaya per unit dan tetap, "
            "penyusutan atas aset tetap, capex, modal kerja dan utang dari berkas driver bersumber; "
            "terminal Gordon pada imbal hasil modal baru yang konsisten.",
            "Rating and Target Price use FCFF DCF, the going-concern Primary Method, on the "
            f"Operating Model {label}-{last}: volume x price by segment, unit and fixed costs, "
            "depreciation on fixed assets, capex, working capital and debt from the sourced "
            "driver file; Gordon terminal at a consistent return on new capital.")
         if operating else
         _t("Rating dan target harga memakai DCF FCFF, metode utama going concern, atas skenario "
            f"analis {label}-{last}: pendapatan, margin EBITDA dan capex dari agen, terminal Gordon.",
            "Rating and Target Price use FCFF DCF, the going-concern Primary Method, on the "
            f"Analyst Scenario {label}-{last}: revenue, EBITDA margin and capex from the agent, "
            "Gordon terminal.")),
        _t(f"FCFF = EBIT x (1 - pajak efektif) + D&A - capex - kenaikan modal kerja; D&A "
           f"{dcf_s['da_basis']}; pajak {dcf_s['tax_basis']}; {dcf_s['nwc_basis']}.",
           f"FCFF = EBIT x (1 - effective tax) + D&A - capex - increase in working capital; D&A "
           f"{src(dcf_s['da_basis'])}; tax {src(dcf_s['tax_basis'])}; "
           f"{src(dcf_s['nwc_basis'])}."),
        _t((f"Model dalam US$, mata uang pelaporan: WACC US$ {fmt.pct(dcf_s['wacc'])} dari CAPM (UST "
            f"10Y {fmt.pct(dcf_s['rf'])} + CRP {fmt.pct(dcf_s['crp'])} + beta x ERP) dan biaya utang "
            f"US$ {fmt.pct(dcf_s['kd_pretax'])} sebelum pajak, bobot nilai pasar; nilai per saham "
            f"dikonversi ke rupiah pada kurs Rp{fmt._id(dcf_s['fx'], 0)}/US$. "
            if usd_model else
            f"WACC {fmt.pct(dcf_s['wacc'])} dari CAPM dan biaya utang "
            f"{fmt.pct(dcf_s['kd_pretax'], 0)} sebelum pajak, bobot nilai pasar. ")
           + f"Tanggal valuasi {dcf_s['valuation_date']}"
           + (f" ({dcf_s['anchor_reason']})" if dcf_s.get("anchor_reason") else "")
           + f"; arus kas {label} dihitung sesudah tanggal itu; konvensi mid-period; nilai "
           "terminal di akhir tahun eksplisit terakhir."
           + (f" Pada harga Rp{fmt.rp(intake_price)}, arus kas yang sama menyiratkan WACC "
              f"{fmt.pct(dcf_s['implied_wacc'])} (CoE {fmt.pct(dcf_s['implied_coe'])}); target "
              f"mengandaikan pasar menerima WACC kebijakan {fmt.pct(dcf_s['wacc'])}."
              if implied else ""),
           (f"The model is in US$, the reporting currency: a US$ WACC of "
            f"{fmt.pct(dcf_s['wacc'])} from CAPM (UST 10Y {fmt.pct(dcf_s['rf'])} + CRP "
            f"{fmt.pct(dcf_s['crp'])} + beta x ERP) and a pre-tax US$ cost of debt of "
            f"{fmt.pct(dcf_s['kd_pretax'])}, market-value weights; value per share is converted "
            f"to rupiah at Rp{fmt._id(dcf_s['fx'], 0)}/US$. "
            if usd_model else
            f"WACC of {fmt.pct(dcf_s['wacc'])} from CAPM and a pre-tax cost of debt of "
            f"{fmt.pct(dcf_s['kd_pretax'], 0)}, market-value weights. ")
           + f"Valuation date {dcf_s['valuation_date']}"
           + (f" ({src(dcf_s['anchor_reason'])})" if dcf_s.get("anchor_reason") else "")
           + f"; {label} cash flows are counted after that date; mid-period convention; "
           "terminal value at the end of the last explicit year."
           + (f" At the Rp{fmt.rp(intake_price)} price, the same cash flows imply a WACC of "
              f"{fmt.pct(dcf_s['implied_wacc'])} (CoE {fmt.pct(dcf_s['implied_coe'])}); the "
              f"target assumes the market accepts the policy WACC of {fmt.pct(dcf_s['wacc'])}."
              if implied else "")),
        (_t("Exit EV/EBITDA historis emiten tampil sebagai cross-check; selisih dengan Gordon "
            "diungkapkan, tidak dirata-rata.",
            "The issuer's historical exit EV/EBITDA is shown as a cross-check; the gap to Gordon "
            "is disclosed, not averaged.")
         if dcf_s.get("exit_multiple") is not None else
         _t("Cross-check Exit EV/EBITDA tidak dihitung karena titik historis yang sebanding belum cukup.",
            "The exit EV/EBITDA cross-check is not computed: too few comparable historical "
            "points.")),
        (_t("Model operasional direkonsiliasi (FCFF, neraca dan likuiditas setiap tahun) dan "
            "dihitung ulang secara independen; driver ke depan yang berupa asumsi analis diberi label.",
            "The Operating Model is reconciled (FCFF, balance sheet and liquidity each year) and "
            "recomputed independently; forward drivers that are analyst assumptions are "
            "labelled.")
         if operating else
         _t("Skenario bukan forecast driver yang sudah direkonsiliasi; statusnya berbasis asumsi.",
            "The scenario is not a reconciled driver forecast; its status is Assumption-Led.")),
        _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
    ]


def _extreme_stop_overlay(doc, intake, va):
    """Draft whose selected method stopped at Method Gate 5: say so on the cover.

    Per-share values stay held; the reader sees which method ran, on which
    side of the band it fell and where the cross-checks point.
    """
    chain = va.get("method_chain") or {}
    sel = next((t for t in chain.get("trace") or [] if t.get("decision") == "stop_extreme"), None)
    cover = doc.get("cover") or {}
    if not sel or not cover.get("paragraf"):
        return
    price = intake.get("price")
    above = (sel.get("upside") or 0) > 0
    checks = [t for t in chain.get("trace") or [] if t.get("decision") == "cross_check"]
    checks += [x for x in chain.get("cross_checks") or [] if x.get("status") == "sufficient"]
    exit_value = (sel.get("detail") or {}).get("per_share_exit")
    from . import prose_lang, report_lang
    short_en = lambda text: report_lang.label(text, "en")  # noqa: E731
    sides = {True: [], False: []}
    sides_en = {True: [], False: []}
    if exit_value and price:
        sides[exit_value > price].append("exit EV/EBITDA historis")
        sides_en[exit_value > price].append("historical exit EV/EBITDA")
    for t in checks:
        if t.get("per_share") and price:
            sides[t["per_share"] > price].append(t["short"])
            sides_en[t["per_share"] > price].append(short_en(t["short"]))
    scenario_basis = (sel.get("detail") or {}).get("basis") == "scenario"
    earnings_basis = sel["key"] in ("pe_fy_scenario", "pbv_roe_fy")
    basis = ("skenario analis tervalidasi (aktual 1H resmi, asumsi H2 dan empat tahun "
             "lanjutan)" if scenario_basis else
             "skenario laba analis tervalidasi (aktual 1H resmi dan asumsi H2)"
             if earnings_basis else "input yang tersedia")
    basis_en = ("the validated Analyst Scenario (official 1H actuals, H2 assumptions and four "
                "further years)" if scenario_basis else
                "the validated analyst earnings scenario (official 1H actuals and H2 assumptions)"
                if earnings_basis else "the inputs available")
    direction = ("di atas +100%" if above else "di bawah -50%")
    direction_en = ("more than +100%" if above else "worse than -50%")
    skipped = [f"{t['short']} ({method_chain.reader_reason(t['reasons'][0])})"
               for t in chain.get("trace") or []
               if t.get("decision") == "skipped" and t.get("reasons")]
    # method_chain.reader_reason is Indonesian text from another module: quoted as source.
    skipped_en = [f"{short_en(t['short'])} "
                  f"({prose_lang.source(method_chain.reader_reason(t['reasons'][0]))})"
                  for t in chain.get("trace") or []
                  if t.get("decision") == "skipped" and t.get("reasons")]
    role = ("metode utama rantai" if sel.get("role") == "primary" else
            "metode terpilih sesudah " + "; ".join(skipped) + " dilewati" if skipped else
            "metode terpilih rantai")
    role_en = ("the chain's Primary Method" if sel.get("role") == "primary" else
               "the method selected after " + "; ".join(skipped_en) + " were skipped"
               if skipped_en else "the chain's selected method")
    text = _t(
        (f"{sel['short']}, {role}, dihitung atas {basis}; nilainya {direction} "
         "dari harga penutupan, sehingga Method Gate 5 framework menghentikan rantai dan menandai "
         "Review Required. "
         + (f"Cross-check di atas harga: {', '.join(sides[True])}. " if sides[True] else "")
         + (f"Cross-check di bawah harga: {', '.join(sides[False])}. " if sides[False] else "")
         + "Nilai per saham ditahan sampai tesis fundamental bersumber dan validasi analis "
           "menjelaskan selisih dengan harga pasar."),
        (f"{short_en(sel['short'])}, {role_en}, calculated on {basis_en}; its value is "
         f"{direction_en} from the closing price, so framework Method Gate 5 stops the chain "
         "and flags Review Required. "
         + (f"Cross-checks above the price: {', '.join(sides_en[True])}. "
            if sides_en[True] else "")
         + (f"Cross-checks below the price: {', '.join(sides_en[False])}. "
            if sides_en[False] else "")
         + "The value per share is held until a sourced fundamental thesis and analyst "
           "validation explain the gap to the market price."))
    cover["headline"] = _t("Hasil Valuasi Ekstrem Menunggu Tesis Fundamental",
                           "Extreme Valuation Result Awaits a Fundamental Thesis")
    if len(cover.get("bullets") or []) >= 3:
        cover["bullets"][2] = _trim(_t(
            f"Review Required: {sel['short']} {direction} dari harga; rating ditahan.",
            f"Review Required: {short_en(sel['short'])} {direction_en} from the price; rating "
            "held."), 30)
    cover["paragraf"][-1] = {"judul": "Valuasi: hasil ekstrem ditahan", "isi": text}
    doc["method"] = f"{sel['short']} (ekstrem; Review Required)"


def _ev_ebitda_scenario_exhibit(intake, ev, label):
    """Target table for the forward EV/EBITDA peer: quartile multiples to per-share value."""
    bn = lambda v: fmt._id(v / 1e9, 0)
    rows = []
    for name, mult in (("Kuartil bawah", ev["q1_ev_ebitda"]),
                       ("Median (basis)", ev["median_ev_ebitda"]),
                       ("Kuartil atas", ev["q3_ev_ebitda"])):
        enterprise = mult * ev["ebitda_idr"]
        value = fmt.tick((enterprise + ev["cash"] - ev["debt"] - ev["nci"]
                          - (ev.get("distributions") or 0.0)) / ev["shares"])
        rows.append([name, fmt.mult(mult, 1), f"Rp{bn(enterprise)} miliar",
                     f"Rp{fmt.rp(value)}", fmt.pct(value / intake["price"] - 1)])
    tag = {"sectors": "Sectors", "yahoo": "Yahoo"}
    period = lambda p: p.get("ev_period") or (f"FY{p['ev_year']}" if p.get("ev_year") else "")
    peers = ", ".join(f"{p['symbol']} {fmt.mult(p['ev_ebitda'], 1)} ("
                      + (f"{period(p)}, " if period(p) else "")
                      + f"{tag.get(p.get('source_kind'), '?')})"
                      for p in ev["peers"])
    return {
        "n": 0, "judul": f"Target harga: EV/EBITDA peer x EBITDA {label}", "tipe": "tabel",
        "data": {"cols": ["EV/EBITDA peer", "Kelipatan", "EV", "Nilai per saham",
                          "Terhadap harga"], "rows": rows},
        "catatan_sumber": (
            f"Sumber: EV/EBITDA terakhir tiap peer (12 bulan terakhir bila tersedia, selain itu "
            f"FY terakhir) dari {ev['peer_source']} (kapitalisasi pasar dari tabel peer Sectors "
            f"atau snapshot Yahoo + utang - kas laporan peer): {peers}; EBITDA {label} skenario "
            f"analis; kas "
            f"Rp{bn(ev['cash'])} miliar ({ev.get('cash_basis') or '-'}), utang "
            f"Rp{bn(ev['debt'])} miliar ({ev.get('debt_basis') or '-'}), minoritas "
            f"Rp{bn(ev['nci'])} miliar"
            + (f", dividen sesudah tanggal neraca Rp{bn(ev['distributions'])} miliar "
               f"({ev['distributions_basis']})" if ev.get("distributions") else "")
            + f"; saham {ev.get('shares_basis') or '-'}"
            + (f"; kurs Rp{fmt.rp(ev['fx'])}/USD" if ev.get("fx") else "")
            + f"; harga penutupan {intake['price_date']}.")}


def _bank_driver_text(model, label, money, unit, eps_of, cite, a, forward_rows=()):
    """Bank Driver Scenario prose and exhibits: (H2 sentence, FY bridge, driver table)."""
    rows, anchor, h2 = model["rows"], model["anchor"], model["h2"]
    first = rows[0]
    d = first["drivers"]
    period = anchor["period"]
    pct = lambda v: fmt.pct(v / 100) if isinstance(v, (int, float)) else "n.m."
    requested_loan = d.get("loan_growth_pct")
    effective_loan = first.get("loan_growth")
    capped = (isinstance(effective_loan, (int, float)) and
              isinstance(requested_loan, (int, float)) and
              abs(effective_loan * 100 - requested_loan) > 0.05)
    loan_text = (f"input pertumbuhan kredit bruto {pct(requested_loan)}; setelah batas model "
                 f"pertumbuhan FY {fmt.pct(effective_loan)}"
                 if capped else
                 f"pertumbuhan kredit bruto {pct(requested_loan)} setahun")
    loan_text_en = (f"gross loans at input growth of {pct(requested_loan)}, FY growth of "
                    f"{fmt.pct(effective_loan)} after the model cap"
                    if capped else
                    f"gross loan growth of {pct(requested_loan)} for the year")
    h2_text = _t(
        f"Asumsi semester kedua: kredit bruto tumbuh "
        f"{loan_text}, NIM H2 {pct(d['nim_pct'])}, pendapatan "
        f"non-bunga {pct(d['non_ii_to_nii_pct'])} dari NII, rasio biaya terhadap "
        f"pendapatan {pct(d['cost_to_income_pct'])} dan biaya kredit "
        f"{pct(d['cost_of_credit_pct'])}; model menurunkan NII, provisi, laba, ekuitas dan "
        "CAR dari driver tersebut. Semua angka merupakan asumsi analis, bukan panduan emiten.",
        f"Second-half assumptions: "
        f"{loan_text_en}, H2 NIM {pct(d['nim_pct'])}, non-interest income "
        f"{pct(d['non_ii_to_nii_pct'])} of NII, cost-to-income ratio "
        f"{pct(d['cost_to_income_pct'])} and cost of credit "
        f"{pct(d['cost_of_credit_pct'])}; the model derives NII, provisions, profit, equity and "
        "CAR from these drivers. All figures are analyst assumptions, not issuer guidance.")
    fy_lines = (("Pendapatan bunga bersih", "net_interest_income", "net_interest_income"),
                ("Pendapatan non-bunga", "non_interest_income", "non_interest_income"),
                ("Beban operasional", "operating_expense", "operating_expense"),
                ("Provisi", "provision", "provision"),
                ("Laba sebelum pajak", "earnings_before_tax", "earnings_before_tax"),
                ("Laba bersih", "net_profit", "net_cons"),
                ("Laba pemilik induk", "net_profit_attributable", "earnings"))
    h1_values = {"net_interest_income": anchor["net_interest_income"],
                 "non_interest_income": anchor["other_income"],
                 "net_profit": anchor["net_profit"],
                 "net_profit_attributable": anchor["net_profit_attributable"],
                 **{k: anchor["split"][k] for k in ("operating_expense", "provision",
                                                    "earnings_before_tax")}}
    h2_values = {"net_interest_income": h2["net_interest_income"],
                 "non_interest_income": h2["other_income"], **h2}
    screened = ("operating_expense", "provision", "earnings_before_tax")
    bridge = {
        "n": 0, "judul": f"Model driver bank {label}: aktual {period} dan H2 model",
        "tipe": "tabel",
        "data": {"cols": [unit, f"{period} aktual", "H2 model", label],
                 "rows": [[name, money(h1_values[k1]) + ("*" if k1 in screened else ""),
                           money(h2_values[k1]), money(first[k2])]
                          for name, k1, k2 in fy_lines]
                 + [["Driver H2", "aktual resmi",
                     f"NIM {pct(d['nim_pct'])}; CIR {pct(d['cost_to_income_pct'])}; biaya kredit "
                     f"{pct(d['cost_of_credit_pct'])}; non-bunga/NII "
                     f"{pct(d['non_ii_to_nii_pct'])}",
                     f"kredit input {pct(d['loan_growth_pct'])}; efektif FY "
                     f"{fmt.pct(first['loan_growth'])}; NIM FY "
                     f"{fmt.pct(first['net_interest_margin'])}"]]},
        "catatan_sumber": (
            f"Sumber: rilis {period} resmi (pendapatan, NII dan laba); H2 adalah model driver "
            f"bank dengan asumsi analis ({cite((a.get('bank_drivers') or {}).get('source_ids'))}), "
            f"bukan panduan emiten. *Rilis {period} tidak memisahkan beban operasional, provisi "
            "dan pajak; angka bertanda bintang adalah pemisahan screening pada komposisi FY "
            f"sebelumnya yang totalnya sama dengan laba {period} resmi. EPS memakai "
            f"{anchor['parent_share_basis']}.")}
    forward = None
    if len(rows) > 1:
        basis = {r.get("year"): r for r in [a.get("bank_drivers") or {}] + list(forward_rows)}
        body = []
        applied = (model.get("constraints") or {}).get("applied") or []
        for r in rows:
            x = r["drivers"]
            why = basis.get(r["year"]) or {}
            loan_cap = next((c for c in applied if c.get("year") == r["year"] and
                             c.get("lever") == "loan_growth"), None)
            if loan_cap:
                bound = ("batas pendanaan LDR" if "ldr" in str(loan_cap.get("rule") or "").lower()
                         else "batas kecukupan modal")
                rationale = (f"Kredit efektif dibatasi dari {pct(loan_cap.get('from_pct'))} "
                             f"ke {pct(loan_cap.get('to_pct'))} oleh {bound}.")
            else:
                rationale = "Tidak ada batas kredit yang mengikat pada tahun ini."
            cited = cite(why.get("source_ids"))
            if cited:
                rationale += f" Sumber asumsi: {cited}."
            body.append([r["label"], pct(x["loan_growth_pct"]),
                         fmt.pct(r["loan_growth"]), pct(x["nim_pct"]),
                         pct(x["cost_of_credit_pct"]), pct(x["cost_to_income_pct"]),
                         money(r["earnings"]),
                         fmt.pct(r["roe"]) if r.get("roe") is not None else "n.m.",
                         fmt.pct(r["capital_adequacy_ratio"])
                         if r.get("capital_adequacy_ratio") is not None else "n.m.",
                         rationale])
        forward = {
            "n": 0, "judul": f"Bank Driver Scenario {rows[0]['label']}-{rows[-1]['label']}",
            "tipe": "tabel",
            "data": {"cols": ["Tahun", "Kredit input", "Kredit efektif", "NIM", "Biaya kredit", "CIR",
                              "Laba induk", "ROE", "CAR*", "Dasar"],
                     "rows": body},
            "catatan_sumber": (
                f"Sumber: driver asumsi analis dari rilis resmi dan berita bertanggal, bukan "
                f"panduan emiten; {rows[0]['label']} = aktual {period} + H2 model (NIM, CIR dan "
                "biaya kredit kolom ini adalah driver H2). Laba induk dalam " + unit + ". *CAR "
                "screening: ekuitas x rasio modal regulasi terhadap ekuitas FY terakhir / (total "
                "aset x densitas ATMR FY terakhir), bukan perhitungan regulasi."
                + ("" if not model["checks"]["warnings"] else
                   " " + " ".join(model["checks"]["warnings"])))}
    last = rows[-1]
    car = last.get("capital_adequacy_ratio") is not None
    path = _t(
        f" Model driver bank membawa laba bersih ke Rp{money(last['earnings'])} miliar pada "
        f"{last['label']} dengan NIM {fmt.pct(last['net_interest_margin'])}, biaya kredit "
        f"{fmt.pct(last['cost_of_credit'])} dan ROE {fmt.pct(last['roe'])}"
        + (f"; CAR screening {fmt.pct(last['capital_adequacy_ratio'])}" if car else "") + ".",
        f" The bank driver model takes net profit to Rp{money(last['earnings'])} miliar in "
        f"{last['label']} with NIM of {fmt.pct(last['net_interest_margin'])}, cost of credit of "
        f"{fmt.pct(last['cost_of_credit'])} and ROE of {fmt.pct(last['roe'])}"
        + (f"; screening CAR {fmt.pct(last['capital_adequacy_ratio'])}" if car else "") + ".")
    return h2_text, bridge, forward, path


def _build_earnings_led(intake, fc, va, s1, method="auto"):
    """Going concern / bank: FY PER peer on the validated earnings scenario."""
    from . import prose_lang
    doc = _build_general_draft(intake, fc, va, s1, method=method)
    scenario = fc["earnings_scenario"]
    forward = (fc.get("outyear_scenario") or {}).get("rows") or []
    a = scenario["assumptions"]
    sel = next(t for t in va["method_chain"]["trace"] if t["key"] == "pe_fy_scenario")
    d = sel["detail"]
    # Banks: justified P/BV on the same scenario is the target method; PER
    # stays as the cross-check (framework Method Gate 0).
    pbv = (next((t["detail"] for t in va["method_chain"]["trace"] if t["key"] == "pbv_roe_fy"), None)
           if va["method_chain"].get("selected") == "pbv_roe_fy" else None)
    # Asset-heavy going concern with too few PER peers: peer P/B on reported book.
    book = (next((t["detail"] for t in va["method_chain"]["trace"] if t["key"] == "pbv_book"), None)
            if va["method_chain"].get("selected") == "pbv_book" else None)
    # Primary method valued on the same validated scenario (spec Opsi A/B).
    primary = next((t["detail"] for t in va["method_chain"]["trace"]
                    if t["key"] == va["method_chain"].get("selected")
                    and (t.get("detail") or {}).get("basis") == "scenario"), None)
    sotp_h = (next((t["detail"] for t in va["method_chain"]["trace"]
                    if t["key"] == "holding_sotp"), None)
              if va["method_chain"].get("selected") == "holding_sotp" else None)
    ddm_s = primary if primary and va["method_chain"]["selected"] == "ddm" else None
    dcf_s = (primary if primary and va["method_chain"]["selected"] in ("fcff_dcf", "dcf_reference")
             else None)
    ev_s = primary if primary and va["method_chain"]["selected"] == "ev_ebitda_peer" else None
    label = f"FY{scenario['year'] % 100:02d}F"
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    to_idr = d.get("fx") or 1.0
    scale, unit = (1e6, "US$ juta") if usd else (1e9, "Rp miliar")
    money = lambda v: "-" if v is None else (
        f"({fmt._id(abs(v) / scale, 1)})" if v < 0 else fmt._id(v / scale, 1))
    eps_of = lambda net_attr: net_attr * to_idr / d["shares"]
    actual = intake.get("latest_official_actual") or {}
    actual_title = actual.get("source_title") or "rilis interim resmi"
    refs = a.get("source_refs") or {}
    cite = lambda ids: "; ".join(
        actual_title if x == "official" else
        f"{(refs.get(x) or {}).get('title', 'berita bertanggal')} "
        f"({(refs.get(x) or {}).get('date', '-')})"
        for x in ids or [])
    peers = [p for p in intake.get("peers") or []
             if isinstance(p.get("pe"), (int, float)) and 0 < p["pe"] <= 50]
    peer_names = ", ".join(f"{str(p.get('symbol', '?')).replace('.JK', '')} "
                           f"{fmt.mult(p['pe'], 1)}" for p in sorted(peers, key=lambda p: p["pe"]))

    meta = doc["meta"]
    # A Production-Ready operating model shares this layout; the status is the
    # release's own, never assumed.
    released = (va.get("release") or {}).get("status")
    meta.update(status=("distributable" if released == "distributable"
                        else "distributable_assumption_led"),
                model_profile=intake.get("model_profile"),
                rating=va["rating"],
                tp=va["tp"], upside_persen=va["upside"] * 100,
                status_rating=va["rating"], illustrative_scenarios=False)
    doc["method"] = va["method"]
    doc["log_gate"]["S3"] = va["s3"]
    doc["log_gate"]["release"] = va["release"]

    # --- cover: forward thesis, not draft checklist
    fy = scenario["full_year"]
    path = ""
    bank_fc = fc.get("bank_model") if isinstance(fc.get("bank_model"), dict) else None
    bank_texts = (_bank_driver_text(bank_fc, label, money, unit, eps_of, cite, a, forward)
                  if bank_fc else None)
    if bank_texts and forward:
        path = bank_texts[3]
    elif forward:
        last = forward[-1]
        # Parent's share, the basis of Key Financials and EPS (cover tie-out).
        amount = (f"US${money(last['net_profit_attributable'])} juta" if usd
                  else f"Rp{money(last['net_profit_attributable'])} miliar")
        path = _t(f" Skenario lanjutan membawa laba bersih ke {amount} pada {last['label']} "
                  f"dengan margin {fmt.pct(last['net_income_margin_pct'] / 100)}.",
                  f" The forward scenario takes net profit to {amount} in {last['label']} "
                  f"at a {fmt.pct(last['net_income_margin_pct'] / 100)} margin.")
    doc["cover"]["headline"] = _earnings_headline(label, _scenario_profit_change(intake, fy))
    fy_revenue = (f"US${money(fy.get('revenue'))} juta" if usd else
                  f"Rp{money(fy.get('revenue'))} miliar")
    fy_profit_value = fy.get("net_profit_attributable") or fy.get("net_profit")
    fy_profit = (f"US${money(fy_profit_value)} juta" if usd else
                 f"Rp{money(fy_profit_value)} miliar")
    doc["cover"]["bullets"][1] = _bullet(_t(
        f"Skenario {label}: pendapatan {fy_revenue} dan laba bersih {fy_profit}; "
        "asumsi analis, bukan panduan emiten.",
        f"{label} scenario: revenue {fy_revenue} and net profit {fy_profit}; "
        "analyst assumptions, not company guidance."), 30)
    doc["cover"]["bullets"][2] = _trim(
        _t(f"{va['rating']}: target Rp{fmt.rp(va['tp'])} ({fmt.pct(va['upside'])}) dari ",
           f"{va['rating']}: Target Price Rp{fmt.rp(va['tp'])} ({fmt.pct(va['upside'])}) from ")
        + (_t(f"SOTP holding: {', '.join(c['ticker'] for c in sotp_h['components'])} pada nilai "
              "pasar, landbank pada RNAV, segmen lain pada nilai buku.",
              f"holding SOTP: {', '.join(c['ticker'] for c in sotp_h['components'])} at market "
              "value, landbank at RNAV, other segments at book value.")
           if sotp_h and sotp_h.get("landbank") else
           _t(f"SOTP holding: {', '.join(c['ticker'] for c in sotp_h['components'])} pada nilai "
              "pasar, segmen lain pada nilai buku.",
              f"holding SOTP: {', '.join(c['ticker'] for c in sotp_h['components'])} at market "
              "value, other segments at book value.") if sotp_h else
           _t(f"DDM: dividen {label}-{forward[-1]['label']}, payout mengikuti batas modal model, "
              f"CoE {fmt.pct(ddm_s['coe'])}.",
              f"DDM: {label}-{forward[-1]['label']} dividends, payout within the model's capital "
              f"limit, CoE {fmt.pct(ddm_s['coe'])}.") if ddm_s and forward else
           f"DCF FCFF {label}-{forward[-1]['label']}, WACC {fmt.pct(dcf_s['wacc'])}, "
           f"g {fmt.pct(dcf_s['g'])}." if dcf_s and forward else
           _t(f"EV/EBITDA median {ev_s['peer_count']} peer {fmt.mult(ev_s['median_ev_ebitda'], 1)} "
              f"atas EBITDA {label}.",
              f"median EV/EBITDA of {ev_s['peer_count']} peers "
              f"{fmt.mult(ev_s['median_ev_ebitda'], 1)} on {label} EBITDA.") if ev_s else
           _t(f"P/BV wajar {fmt.mult(pbv['fair_pbv'], 1)} atas ROE {label} "
              f"{fmt.pct(pbv['roe'])}.",
              f"fair P/BV {fmt.mult(pbv['fair_pbv'], 1)} on {label} ROE "
              f"{fmt.pct(pbv['roe'])}.") if pbv else
           _t(f"P/B median peer {fmt.mult(book['median_pb'], 1)} atas nilai buku terlapor.",
              f"median peer P/B {fmt.mult(book['median_pb'], 1)} on reported book value.")
           if book else
           _t(f"PER median peer {fmt.mult(d['median_pe'], 1)} atas EPS {label}.",
              f"median peer PER {fmt.mult(d['median_pe'], 1)} on {label} EPS.")), 30)
    fy_attr = fy["net_profit_attributable"]
    fy_money = (f"US${money(fy_attr)} juta" if usd else f"Rp{money(fy_attr)} miliar")
    from . import report_extras
    eps_fy = eps_of(fy_attr)
    pe_now = intake["price"] / eps_fy if eps_fy > 0 else None
    # Struktur paragraph 1: how much of our FY estimate the latest half delivered.
    h1_share = scenario["h1"]["net_profit"] / fy["net_profit"] if fy["net_profit"] > 0 else None
    if h1_share and doc["cover"]["paragraf"]:
        doc["cover"]["paragraf"][0]["isi"] = (
            doc["cover"]["paragraf"][0]["isi"].rstrip() +
            _t(f" Laba 1H setara {fmt.pct(h1_share)} dari estimasi laba bersih {label} kami.",
               f" 1H profit equals {fmt.pct(h1_share)} of our {label} net profit estimate."))
    # Struktur paragraph 2: report the market move and comparable model metrics
    # without inferring what investors have priced in.
    own_move, ihsg_move = report_extras.price_vs_ihsg(
        intake["ticker"], scenario.get("published_at"), intake.get("as_of"))
    priced = ""
    move_text = (_t(f" Sejak rilis {own_move[1]} saham {'naik' if own_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(own_move[0]))} (IHSG {'naik' if ihsg_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(ihsg_move[0]))})",
                    f" Since the {own_move[1]} release the stock is "
                    f"{'up' if own_move[0] >= 0 else 'down'} {fmt.pct(abs(own_move[0]))} (JCI "
                    f"{'up' if ihsg_move[0] >= 0 else 'down'} {fmt.pct(abs(ihsg_move[0]))})")
                 if own_move and ihsg_move else None)
    if move_text and ddm_s:
        dps1 = ddm_s["lines"][0]["dps"]
        yield_now = dps1 / intake["price"]
        priced = (move_text + _t(f"; DPS skenario {label} Rp{fmt.rp(round(dps1))} per saham "
                                 f"setara rasio dividen/harga indikatif {fmt.pct(yield_now)} pada "
                                 "harga penutupan yang tercantum di laporan.",
                                 f"; the {label} scenario DPS of Rp{fmt.rp(round(dps1))} per share "
                                 f"is an indicative dividend yield of {fmt.pct(yield_now)} at the "
                                 "closing price stated in this report."))
    elif move_text and dcf_s:
        first = dcf_s["lines"][0]
        ev_now = (intake["price"] * dcf_s["shares"] - dcf_s["cash"] + dcf_s["debt"]
                  + (dcf_s.get("nci") or 0.0))
        ev_multiple = ev_now / first["ebitda"] if first["ebitda"] > 0 else None
        hist = dcf_s.get("exit_multiple")
        priced = (move_text + (_t(f"; pada harga kini EV/EBITDA {label} {fmt.mult(ev_multiple, 1)}",
                                  f"; at the current price {label} EV/EBITDA is "
                                  f"{fmt.mult(ev_multiple, 1)}")
                               if ev_multiple else "")
                  + (_t(f", dibanding median historis emiten {fmt.mult(hist, 1)}",
                        f", against the company's historical median of {fmt.mult(hist, 1)}")
                     if hist and ev_multiple else "") + ".")
    elif move_text and ev_s:
        ev_now = intake["price"] * ev_s["shares"] - ev_s["cash"] + ev_s["debt"] + ev_s["nci"]
        multiple_now = ev_now / ev_s["ebitda_idr"] if ev_s["ebitda_idr"] > 0 else None
        priced = (move_text + (_t(f"; EV/EBITDA {label} pada harga penutupan "
                                  f"{fmt.mult(multiple_now, 1)} dibanding median peer "
                                  f"{fmt.mult(ev_s['median_ev_ebitda'], 1)}.",
                                  f"; {label} EV/EBITDA at the closing price is "
                                  f"{fmt.mult(multiple_now, 1)} against a peer median of "
                                  f"{fmt.mult(ev_s['median_ev_ebitda'], 1)}.")
                               if multiple_now else "."))
    elif own_move and ihsg_move and pbv:
        pbv_now = intake["price"] / pbv["bvps"]
        priced = _t(f" Sejak rilis {own_move[1]} saham {'naik' if own_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(own_move[0]))} (IHSG {'naik' if ihsg_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(ihsg_move[0]))}); P/BV pada harga penutupan "
                    f"{fmt.mult(pbv_now, 1)}; P/BV indikatif dari ROE skenario {label} "
                    f"{fmt.mult(pbv['fair_pbv'], 1)}.",
                    f" Since the {own_move[1]} release the stock is "
                    f"{'up' if own_move[0] >= 0 else 'down'} {fmt.pct(abs(own_move[0]))} (JCI "
                    f"{'up' if ihsg_move[0] >= 0 else 'down'} {fmt.pct(abs(ihsg_move[0]))}); "
                    f"P/BV at the closing price is {fmt.mult(pbv_now, 1)}; indicative P/BV from the "
                    f"{label} scenario ROE is {fmt.mult(pbv['fair_pbv'], 1)}.")
    elif own_move and ihsg_move and book:
        pb_now = intake["price"] / book["bvps"]
        priced = _t(f" Sejak rilis {own_move[1]} saham {'naik' if own_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(own_move[0]))} (IHSG {'naik' if ihsg_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(ihsg_move[0]))}); P/B kini {fmt.mult(pb_now, 1)} dibanding median "
                    f"peer {fmt.mult(book['median_pb'], 1)}.",
                    f" Since the {own_move[1]} release the stock is "
                    f"{'up' if own_move[0] >= 0 else 'down'} {fmt.pct(abs(own_move[0]))} (JCI "
                    f"{'up' if ihsg_move[0] >= 0 else 'down'} {fmt.pct(abs(ihsg_move[0]))}); "
                    f"current P/B is {fmt.mult(pb_now, 1)} against a peer median of "
                    f"{fmt.mult(book['median_pb'], 1)}.")
    elif own_move and ihsg_move and pe_now:
        priced = _t(f" Sejak rilis {own_move[1]} saham {'naik' if own_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(own_move[0]))} (IHSG {'naik' if ihsg_move[0] >= 0 else 'turun'} "
                    f"{fmt.pct(abs(ihsg_move[0]))}); PER {label} pada harga penutupan "
                    f"{fmt.mult(pe_now, 1)} dibanding median peer {fmt.mult(d['median_pe'], 1)}.",
                    f" Since the {own_move[1]} release the stock is "
                    f"{'up' if own_move[0] >= 0 else 'down'} {fmt.pct(abs(own_move[0]))} (JCI "
                    f"{'up' if ihsg_move[0] >= 0 else 'down'} {fmt.pct(abs(ihsg_move[0]))}); "
                    f"{label} PER at the closing price is {fmt.mult(pe_now, 1)} against a peer "
                    f"median of {fmt.mult(d['median_pe'], 1)}.")
    if bank_texts:
        scenario_basis = bank_texts[0]
    else:
        fy_ebitda_margin = (fmt.pct(fy["ebitda"] / fy["revenue"])
                            if fy.get("ebitda") is not None and fy.get("revenue") else "n.m.")
        fy_capex = fy.get("capital_expenditure", fy.get("capex"))
        fy_capex_ratio = (fmt.pct(fy_capex / fy["revenue"])
                          if fy_capex is not None and fy.get("revenue") else "n.m.")
        scenario_basis = _t(
            f"Asumsi {label}: pendapatan H2/H1 {fmt._id(a['h2_revenue_to_h1'], 2)}x, "
            f"margin laba bersih H2 {fmt.pct(a['h2_net_margin_pct'] / 100)}, "
            f"margin EBITDA FY {fy_ebitda_margin}, capex/revenue {fy_capex_ratio}. "
            "Angka setelah periode aktual adalah asumsi analis, bukan panduan emiten. ",
            f"{label} assumptions: H2/H1 revenue {fmt._id(a['h2_revenue_to_h1'], 2)}x, "
            f"H2 net margin {fmt.pct(a['h2_net_margin_pct'] / 100)}, "
            f"FY EBITDA margin {fy_ebitda_margin}, capex/revenue {fy_capex_ratio}. "
            "Figures beyond the actual period are analyst assumptions, not company guidance. ")
    doc["cover"]["paragraf"][1] = {
        "judul": "Asumsi skenario dan batasannya",
        "isi": (scenario_basis + _t(f"Laba bersih {label} model {fy_money}.",
                                    f"Model {label} net profit is {fy_money}.") + path + priced)}
    skipped = [_t(t["short"], _SHORT_EN.get(t["key"], t["short"]))
               for t in va["method_chain"]["trace"] if t["decision"] == "skipped"]
    # Struktur paragraph 3: method, forecast linkage, trading multiple (risk is
    # appended by report_extras.attach_risks).
    evidence_annuals = {r["year"]: r for r in
                        (intake.get("official_evidence") or {}).get("annual_actuals") or []}
    base_year = scenario["year"] - 1
    base_attr = ((evidence_annuals.get(base_year) or {}).get("net_profit_attributable")
                 or next((a["earnings"] / to_idr for a in intake.get("annuals") or []
                          if a.get("year") == base_year and a.get("earnings")), None))
    end_row = forward[1] if len(forward) >= 2 else None  # FY28F closes the display horizon
    # Template Slide 1 ¶3: CAGR FY26-28F of EBITDA (profit for a bank) and its driver.
    bank = intake.get("model_profile") == "financial_ddm"
    metric = "net_profit_attributable" if bank or fy.get("ebitda") is None else "ebitda"
    start_v, end_v = fy.get(metric), (end_row or {}).get(metric)
    if start_v and end_v and start_v > 0 and end_v > 0:
        cagr = (end_v / start_v) ** 0.5 - 1
        rev_cagr = ((end_row["revenue"] / fy["revenue"]) ** 0.5 - 1
                    if fy.get("revenue") and end_row.get("revenue") else None)
        margin_key = "net_profit_attributable" if metric != "ebitda" else "ebitda"
        margin = lambda row: row[margin_key] / row["revenue"] if row.get("revenue") else None
        name = _t("laba bersih", "net profit") if metric != "ebitda" else "EBITDA"
        growth = (_t(f"pertumbuhan {name} CAGR {label}-{end_row['label']} {fmt.pct(cagr)}",
                     f"a {label}-{end_row['label']} {name} CAGR of {fmt.pct(cagr)}")
                  + (_t(f", didukung pertumbuhan pendapatan CAGR {fmt.pct(rev_cagr)} dan margin "
                        f"{name} {fmt.pct(margin(fy))} menjadi {fmt.pct(margin(end_row))}",
                        f", supported by a revenue CAGR of {fmt.pct(rev_cagr)} and a {name} "
                        f"margin moving from {fmt.pct(margin(fy))} to {fmt.pct(margin(end_row))}")
                     if rev_cagr is not None and margin(fy) is not None else ""))
    elif base_attr and base_attr > 0 and end_row and end_row.get("net_profit_attributable"):
        cagr = (end_row["net_profit_attributable"] / base_attr) ** (1 / 3) - 1
        growth = _t(f"pertumbuhan laba bersih CAGR FY{base_year % 100:02d}-{end_row['label']} "
                    f"{fmt.pct(cagr)}",
                    f"a FY{base_year % 100:02d}-{end_row['label']} net profit CAGR of "
                    f"{fmt.pct(cagr)}")
    elif base_attr and base_attr > 0:
        growth = _t(f"laba bersih {label} {fmt.pct(fy_attr / base_attr - 1)} yoy",
                    f"a {label} net profit change of {fmt.pct(fy_attr / base_attr - 1)} yoy")
    else:
        growth = None
    driver = next((prose_lang.source(x["item"]) for x in a.get("catalysts_risks") or []
                   if isinstance(x, dict) and x.get("direction") == "Positif"), None)
    band = (report_extras._band_data(intake) or {}).get("multiples", {}).get("P/E")
    pbv_lead = (_t(
        f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai P/BV wajar "
        f"{fmt.mult(pbv['fair_pbv'], 2)} = (ROE {label} {fmt.pct(pbv['roe'])} - g "
        f"{fmt.pct(pbv['g'])}) / (CoE {fmt.pct(pbv['coe'])} - g) atas BVPS "
        f"Rp{fmt.rp(round(pbv['bvps']))} (ekuitas pemilik induk, {pbv['equity_source']}); "
        f"pada CoE +1pp nilainya Rp{fmt.rp(fmt.tick(pbv['fair_pbv_down'] * pbv['bvps']))}. ",
        f"We set the Target Price at Rp{fmt.rp(va['tp'])} on a fair P/BV of "
        f"{fmt.mult(pbv['fair_pbv'], 2)} = ({label} ROE {fmt.pct(pbv['roe'])} - g "
        f"{fmt.pct(pbv['g'])}) / (CoE {fmt.pct(pbv['coe'])} - g) on BVPS of "
        f"Rp{fmt.rp(round(pbv['bvps']))} (parent equity, "
        f"{_EQUITY_SOURCE_EN.get(pbv['equity_source'], pbv['equity_source'])}); "
        f"at CoE +1pp the value is Rp{fmt.rp(fmt.tick(pbv['fair_pbv_down'] * pbv['bvps']))}. ")
        if pbv else "")
    book_lead = (_t(
        f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai P/B median {book['peer_count']} "
        f"peer {fmt.mult(book['median_pb'], 2)} atas BVPS terlapor Rp{fmt.rp(round(book['bvps']))} "
        f"(ekuitas pemilik induk per {book.get('balance_period') or '-'}), dengan kuartil bawah "
        f"Rp{fmt.rp(fmt.tick(book['q1_pb'] * book['bvps']))}. P/BV dipakai karena aset tetap "
        f"{fmt.pct(book['fixed_asset_share'])} dari total aset (FY{book.get('fixed_asset_year')}) "
        f"dan PER peer valid kurang dari tiga. ",
        f"We set the Target Price at Rp{fmt.rp(va['tp'])} on the median P/B of "
        f"{book['peer_count']} peers, {fmt.mult(book['median_pb'], 2)}, applied to reported BVPS of "
        f"Rp{fmt.rp(round(book['bvps']))} (parent equity as of {book.get('balance_period') or '-'}), "
        f"with the lower quartile at Rp{fmt.rp(fmt.tick(book['q1_pb'] * book['bvps']))}. P/BV is "
        f"used because fixed assets are {fmt.pct(book['fixed_asset_share'])} of total assets "
        f"(FY{book.get('fixed_asset_year')}) and fewer than three valid peer PERs exist. ")
        if book else "")
    bn = lambda v: fmt._id(v / 1e9, 1)
    ddm_lead = (_t(
        f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai DDM, metode utama bank: laba "
        f"pemilik induk skenario {label}-{forward[-1]['label']}; {_ddm_payout_summary(ddm_s)}. "
        f"DPS "
        f"Rp{fmt.rp(round(ddm_s['lines'][0]['dps']))} sampai "
        f"Rp{fmt.rp(round(ddm_s['lines'][-1]['dps']))}, didiskonto dengan CoE "
        f"{fmt.pct(ddm_s['coe'])} (bukan WACC) ke {ddm_s['valuation_date']}; nilai terminal "
        f"Gordon g {fmt.pct(ddm_s['g'])} adalah {fmt.pct(ddm_s['tv_share'])} dari nilai. Pada "
        f"CoE +1pp dan g 2,5% nilainya Rp{fmt.rp(va['tp_down'])}. ",
        f"We set the Target Price at Rp{fmt.rp(va['tp'])} using DDM, the Primary Method for "
        f"banks: {label}-{forward[-1]['label']} scenario parent profit; "
        f"{_ddm_payout_summary(ddm_s)}. DPS of "
        f"Rp{fmt.rp(round(ddm_s['lines'][0]['dps']))} to "
        f"Rp{fmt.rp(round(ddm_s['lines'][-1]['dps']))} is discounted at a CoE of "
        f"{fmt.pct(ddm_s['coe'])} (not WACC) to {ddm_s['valuation_date']}; the Gordon terminal "
        f"value at g {fmt.pct(ddm_s['g'])} is {fmt.pct(ddm_s['tv_share'])} of value. At "
        f"CoE +1pp and g 2,5% the value is Rp{fmt.rp(va['tp_down'])}. ")
        if ddm_s and forward else "")
    sotp_lead = ""
    if sotp_h:
        parts = "; ".join(
            _t(f"{c['ticker']} {fmt.pct(c['stake'])} x kapitalisasi Rp{bn(c['market_cap'])} miliar = "
               f"Rp{bn(c['market_value'])} miliar",
               f"{c['ticker']} {fmt.pct(c['stake'])} x market cap Rp{bn(c['market_cap'])} miliar = "
               f"Rp{bn(c['market_value'])} miliar") for c in sotp_h["components"])
        deepest = sotp_h["discounts"][-1]
        sotp_lead = (
            _t(f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai SOTP holding, metode utama "
               "untuk grup dengan lini usaha berbeda: anak usaha tercatat pada nilai pasar "
               f"({parts}) ditambah ekuitas pemilik induk lainnya pada nilai buku "
               f"Rp{bn(sotp_h['remainder_book'])} miliar",
               f"We set the Target Price at Rp{fmt.rp(va['tp'])} using a holding SOTP, the Primary "
               "Method for a group with distinct business lines: listed subsidiaries at market "
               f"value ({parts}) plus the remaining parent equity at book value of "
               f"Rp{bn(sotp_h['remainder_book'])} miliar")
            + (_t(f" dan tambahan nilai landbank Rp{bn(sotp_h['landbank_uplift'])} miliar (RNAV "
                  f"lahan industri dikurangi nilai bukunya, porsi "
                  f"{fmt.pct(sotp_h['landbank']['inputs']['stake'])}; penjualan "
                  f"{fmt._id(sotp_h['landbank']['inputs']['pace_ha'], 0)} ha/tahun)",
                  f" and a landbank uplift of Rp{bn(sotp_h['landbank_uplift'])} miliar (industrial "
                  f"land RNAV less its book value, a "
                  f"{fmt.pct(sotp_h['landbank']['inputs']['stake'])} share; sales of "
                  f"{fmt._id(sotp_h['landbank']['inputs']['pace_ha'], 0)} ha/year)")
               if sotp_h.get("landbank") else "")
            + _t(f", total Rp{bn(sotp_h['total'])} miliar. "
                 f"Dengan diskon holding {fmt.pct(deepest['discount'])} nilainya "
                 f"Rp{fmt.rp(fmt.tick(deepest['per_share']))}. ",
                 f", a total of Rp{bn(sotp_h['total'])} miliar. "
                 f"At a {fmt.pct(deepest['discount'])} holding discount the value is "
                 f"Rp{fmt.rp(fmt.tick(deepest['per_share']))}. ")
            + (_t("Nilai landbank bergantung pada laju penjualan: tabel sensitivitas memuat target "
                  "emiten 135 ha/tahun. ",
                  "The landbank value depends on the pace of sales: the sensitivity table includes "
                  "the company's target of 135 ha/year. ") if sotp_h.get("landbank") else
               _t("Lahan industri tercatat pada biaya perolehan. ",
                  "Industrial land is carried at acquisition cost. "))
            + _t("DCF konsolidasi atas skenario analis menjadi referensi. ",
                 "A consolidated DCF on the analyst scenario serves as the reference. "))
    dcf_lead = ""
    if dcf_s and forward:
        gap_text = (_t(f"Exit EV/EBITDA historis emiten {fmt.mult(dcf_s['exit_multiple'], 1)} "
                       f"memberi Rp{fmt.rp(fmt.tick(dcf_s['per_share_exit']))} (selisih "
                       f"{fmt.pct(dcf_s['exit_gap'])}); ini cross-check yang diungkapkan, tidak "
                       "dirata-rata. ",
                       f"The company's historical exit EV/EBITDA of "
                       f"{fmt.mult(dcf_s['exit_multiple'], 1)} gives "
                       f"Rp{fmt.rp(fmt.tick(dcf_s['per_share_exit']))} (a gap of "
                       f"{fmt.pct(dcf_s['exit_gap'])}); this is a disclosed cross-check, not "
                       "averaged in. ") if dcf_s.get("per_share_exit") else
                    _t("Exit EV/EBITDA historis kurang dari tiga titik, sehingga cross-check exit "
                       "tidak dihitung. ",
                       "Historical exit EV/EBITDA has fewer than three data points, so the exit "
                       "cross-check is not calculated. "))
        dcf_lead = (
            _t(f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai DCF FCFF, metode utama going "
               f"concern: pendapatan, margin EBITDA dan capex skenario {label}-"
               f"{forward[-1]['label']} menjadi FCFF setelah pajak efektif "
               f"{fmt.pct(dcf_s['tax_rate'])}, D&A dan modal kerja, didiskonto WACC "
               f"{fmt.pct(dcf_s['wacc'])} ke {dcf_s['valuation_date']} dengan terminal Gordon g "
               f"{fmt.pct(dcf_s['g'])} ({fmt.pct(dcf_s['tv_share'])} dari EV). ",
               f"We set the Target Price at Rp{fmt.rp(va['tp'])} using FCFF DCF, the Primary "
               f"Method for a going concern: {label}-{forward[-1]['label']} scenario revenue, "
               f"EBITDA margin and capex become FCFF after an effective tax rate of "
               f"{fmt.pct(dcf_s['tax_rate'])}, D&A and working capital, discounted at a WACC of "
               f"{fmt.pct(dcf_s['wacc'])} to {dcf_s['valuation_date']} with a Gordon terminal g of "
               f"{fmt.pct(dcf_s['g'])} ({fmt.pct(dcf_s['tv_share'])} of EV). ")
            + _dcf_bridge_sentence(dcf_s) + gap_text +
            _t(f"Pada WACC +1pp dan g {fmt.pct(min(dcf_s.get('grid_growth') or (0.025,)))} "
               f"nilainya Rp{fmt.rp(va['tp_down'])}. ",
               f"At WACC +1pp and g {fmt.pct(min(dcf_s.get('grid_growth') or (0.025,)))} "
               f"the value is Rp{fmt.rp(va['tp_down'])}. "))
    ev_lead = (_t(
        f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai EV/EBITDA peer forward, metode "
        f"untuk aset yang masih ramping atau riwayat singkat: EV/EBITDA median "
        f"{ev_s['peer_count']} peer {fmt.mult(ev_s['median_ev_ebitda'], 1)} (12 bulan terakhir "
        f"atau FY terakhir tiap peer, {ev_s['peer_source']}) atas EBITDA {label} Rp{bn(ev_s['ebitda_idr'])} miliar (aktual 1H "
        f"resmi dan margin EBITDA asumsi agen) memberi EV Rp{bn(ev_s['ev'])} miliar; ditambah "
        f"kas Rp{bn(ev_s['cash'])} miliar, dikurangi utang Rp{bn(ev_s['debt'])} miliar dan "
        f"minoritas, ekuitas Rp{bn(ev_s['equity'])} miliar per {ev_s['valuation_date']}. "
        f"Rentang kuartil peer memberi Rp{fmt.rp(va['tp_down'])} sampai "
        f"Rp{fmt.rp(fmt.tick(ev_s['per_share_up']))}. ",
        f"We set the Target Price at Rp{fmt.rp(va['tp'])} using forward peer EV/EBITDA, the "
        f"method for assets still ramping up or with a short history: the median EV/EBITDA of "
        f"{ev_s['peer_count']} peers, {fmt.mult(ev_s['median_ev_ebitda'], 1)} (last 12 months "
        f"or latest FY for each peer, {_peer_source_en(ev_s['peer_source'])}), on {label} EBITDA of "
        f"Rp{bn(ev_s['ebitda_idr'])} miliar (official 1H actuals and the agent's assumed EBITDA "
        f"margin) gives an EV of Rp{bn(ev_s['ev'])} miliar; adding cash of "
        f"Rp{bn(ev_s['cash'])} miliar and deducting debt of Rp{bn(ev_s['debt'])} miliar and "
        f"minorities leaves equity of Rp{bn(ev_s['equity'])} miliar as of {ev_s['valuation_date']}. "
        f"The peer quartile range gives Rp{fmt.rp(va['tp_down'])} to "
        f"Rp{fmt.rp(fmt.tick(ev_s['per_share_up']))}. ")
        if ev_s else "")
    per_lead = (_t(
        f"Kami menetapkan target Rp{fmt.rp(va['tp'])} memakai PER median {d['peer_count']} "
        f"peer {fmt.mult(d['median_pe'], 1)} atas EPS {label} Rp{fmt.rp(round(eps_fy))} (laba "
        f"1H resmi dan asumsi semester kedua), dengan rentang kuartil Rp{fmt.rp(va['tp_down'])} "
        f"sampai Rp{fmt.rp(fmt.tick(d['per_share_up']))}. ",
        f"We set the Target Price at Rp{fmt.rp(va['tp'])} on the median PER of {d['peer_count']} "
        f"peers, {fmt.mult(d['median_pe'], 1)}, applied to {label} EPS of "
        f"Rp{fmt.rp(round(eps_fy))} (official 1H profit and second-half assumptions), with a "
        f"quartile range of Rp{fmt.rp(va['tp_down'])} to "
        f"Rp{fmt.rp(fmt.tick(d['per_share_up']))}. ")
        if not (pbv or book or ddm_s or dcf_s or sotp_h or ev_s) else "")
    driver_text = ((driver[:1].lower() + driver[1:] if driver[1:2].islower() else driver)
                   if driver else None)
    # The agent's first positive item is an upcoming catalyst, not evidence
    # for the growth already in the target.
    growth_text = ((_t(f"Target ini mengimplikasikan {growth}. ",
                       f"The target implies {growth}. ") if growth else "")
                   + (_t(f"Katalis positif terdekat: {driver_text}. ",
                         f"Nearest positive catalyst: {driver_text}. ") if driver_text else ""))
    # Template Slide 1 ¶3: the multiple AT the target price against peers and history.
    pe_tp = va["tp"] / eps_fy if va.get("tp") and eps_fy and eps_fy > 0 else None
    band_mean = band["mean"] if band and band["mean"] <= fmt.MULT_CAP else None
    compare = _t(" dan ", " and ").join(
        ([_t(f"median peer {fmt.mult(d['median_pe'], 1)}",
             f"a peer median of {fmt.mult(d['median_pe'], 1)}")] if d.get("median_pe") else [])
        + ([_t(f"rata-rata band P/E historis {fmt.mult(band_mean, 1)}",
               f"a historical P/E band mean of {fmt.mult(band_mean, 1)}")] if band_mean else []))
    multiple_text = (_t(f"Pada target harga, saham diperdagangkan pada PER {label} "
                        f"{fmt.mult(pe_tp, 1, cap=fmt.MULT_CAP)} (harga kini "
                        f"{fmt.mult(pe_now, 1, cap=fmt.MULT_CAP)})",
                        f"At the Target Price the stock trades on a {label} PER of "
                        f"{fmt.mult(pe_tp, 1, cap=fmt.MULT_CAP)} (current price "
                        f"{fmt.mult(pe_now, 1, cap=fmt.MULT_CAP)})")
                     + (_t(f", dibanding {compare}", f", against {compare}") if compare else "")
                     + ". " if pe_tp and pe_now else "")
    # Each skipped method with its own reason (forecast gap, too few peers, ...).
    skipped_reasons = [f"{_t(t['short'], _SHORT_EN.get(t['key'], t['short']))} "
                       f"({method_chain.reader_reason(t['reasons'][0])})"
                       for t in va["method_chain"]["trace"]
                       if t["decision"] == "skipped" and t.get("reasons")]
    skipped_text = (_t(f"Metode sebelumnya dilewati: {'; '.join(skipped_reasons)}.",
                       f"Earlier methods skipped: {'; '.join(skipped_reasons)}.")
                    if skipped_reasons else "")
    valuation_text = (sotp_lead + ddm_lead + dcf_lead + ev_lead + pbv_lead + book_lead + per_lead
                      + growth_text
                      + multiple_text + skipped_text)
    doc["cover"]["paragraf"][2] = {"judul": ("Target harga berbasis SOTP holding" if sotp_h else
                                             "Target harga berbasis DDM" if ddm_s else
                                             "Target harga berbasis DCF FCFF" if dcf_s else
                                             "Target harga berbasis EV/EBITDA peer" if ev_s else
                                             "Target harga berbasis ROE FY" if pbv else
                                             "Target harga berbasis nilai buku" if book
                                             else "Target harga berbasis laba FY"),
                                   "isi": valuation_text}

    # --- body pages: replace draft checklist wording
    if bank_texts:
        h2_text = bank_texts[0]
    else:
        fy_ebitda_margin = (fmt.pct(fy["ebitda"] / fy["revenue"])
                            if fy.get("ebitda") is not None and fy.get("revenue") else "n.m.")
        fy_capex = fy.get("capital_expenditure", fy.get("capex"))
        fy_capex_ratio = (fmt.pct(fy_capex / fy["revenue"])
                          if fy_capex is not None and fy.get("revenue") else "n.m.")
        h2_text = _t(
            f"Asumsi semester kedua: pendapatan H2/H1 {fmt._id(a['h2_revenue_to_h1'], 2)}x, "
            f"margin laba bersih H2 {fmt.pct(a['h2_net_margin_pct'] / 100)}, "
            f"margin EBITDA {label} {fy_ebitda_margin}, capex/revenue {fy_capex_ratio}. "
            "Semua angka adalah asumsi analis, bukan panduan emiten.",
            f"Second-half assumptions: H2/H1 revenue {fmt._id(a['h2_revenue_to_h1'], 2)}x, "
            f"H2 net margin {fmt.pct(a['h2_net_margin_pct'] / 100)}, "
            f"{label} EBITDA margin {fy_ebitda_margin}, capex/revenue {fy_capex_ratio}. "
            "All figures are analyst assumptions, not company guidance.")
    # Spec §5.4 'Risiko utama': the agent's sourced, quantified issuer risks.
    doc["risks"] = [{"kategori": x["category"], "judul": prose_lang.source(x["headline"].strip()),
                     "isi": prose_lang.source(x["explanation"].strip()),
                     "sumber": cite(x.get("source_ids"))}
                    for x in a.get("key_risks") or [] if isinstance(x, dict)]
    catalyst_rows = [[x["item"], f"{x['timing']}. Sumber: {cite(x.get('source_ids'))}",
                      x["driver_path"], x["direction"]]
                     for x in a.get("catalysts_risks") or [] if isinstance(x, dict)]
    for page in doc["bagian"]:
        title = page.get("judul", "")
        if title == "Hasil terbaru dan jembatan laba":
            page["paragraf"] = page["paragraf"][:1] + [h2_text]
        elif title == "Operasi dan posisi keuangan":
            page["paragraf"] = [_t(
                f"Model {label} menggabungkan hasil interim resmi dengan asumsi analis. "
                f"Pendapatan skenario {fy_revenue}; laba bersih {fy_profit}. "
                "Rincian driver, hasil per tahun, dan batas bukti ada pada exhibit skenario; "
                "angka model bukan panduan emiten.",
                f"The {label} model combines official interim results with analyst assumptions. "
                f"Scenario revenue is {fy_revenue}; net profit {fy_profit}. "
                "Driver detail, annual results and evidence limits are in the scenario exhibits; "
                "model figures are not company guidance.")]
        elif title == "Valuasi dan kelengkapan bukti":
            page["judul"] = "Cross-check dan bukti lanjutan"
            page["paragraf"] = [_t(
                f"Target harga dibangun dengan {va['method']} atas skenario yang ditampilkan. "
                "Tabel berikut mencatat cross-check, asumsi yang belum terverifikasi, dan bukti "
                "yang dapat mengubah hasil; skenario ini bukan panduan emiten.",
                f"The Target Price is built with {prose_lang.source(va['method'])} on the "
                "scenario shown. "
                "The following table records cross-checks, unverified assumptions and evidence "
                "that could change the result; the scenario is not company guidance.")]
        for exhibit in page.get("exhibit") or []:
            if exhibit.get("judul") == "Pemeriksaan sebelum rating dan target harga":
                exhibit["judul"] = "Bukti lanjutan untuk menguji target harga"
                selected_short = next(
                    (t["short"] for t in va["method_chain"]["trace"]
                     if t["key"] == va["method_chain"].get("selected")), "metode terpilih")
                exhibit["data"]["rows"][-1][1] = (
                    f"Skenario nilai memakai {selected_short}; tinjau batas bukti pada tabel "
                    "dan catatan metode sebelum menggunakannya.")
            elif exhibit_ids.is_exhibit(exhibit, exhibit_ids.CATALYSTS) and catalyst_rows:
                exhibit["data"] = {"cols": ["Katalis / risiko", "Waktu dan bukti",
                                            "Driver dan jalur dampak", "Arah"],
                                   "rows": catalyst_rows}
                exhibit["catatan_sumber"] = (
                    "Sumber fakta: rilis resmi dan berita bertanggal yang disebut per baris; "
                    "kolom driver dan arah adalah analisis Sektoral.")

    # --- valuation page exhibits
    h1, h2 = scenario["h1"], scenario["h2"]
    bridge = bank_texts[1] if bank_texts else {
        "n": 0, "judul": f"Skenario laba {label}: aktual 1H dan asumsi H2",
        "tipe": "tabel",
        "data": {"cols": [unit, "1H aktual", "H2 asumsi", label],
                 "rows": [
                     ["Pendapatan", money(h1["revenue"]), money(h2["revenue"]),
                      money(fy["revenue"])],
                     ["Laba bersih", money(h1["net_profit"]), money(h2["net_profit"]),
                      money(fy["net_profit"])],
                     ["Laba pemilik induk", "-", "-", money(fy["net_profit_attributable"])],
                     ["Asumsi", "aktual resmi",
                      f"H2/H1 {fmt._id(a['h2_revenue_to_h1'], 2)}x; margin "
                      f"{fmt.pct(a['h2_net_margin_pct'] / 100)}", "1H aktual + H2 asumsi"]]},
        "catatan_sumber": (
            f"Sumber: {actual_title} ({scenario['published_at']}); H2 adalah asumsi analis "
            f"dari rilis dan berita bertanggal ({cite(a.get('source_ids'))}), bukan panduan "
            f"emiten. EPS memakai {scenario['attributable_basis']}.")}
    sensitivity = None
    if d.get("median_pe"):
        rows = []
        for name, pe in (("Kuartil bawah", d["q1_pe"]),
                         ("Median" if sotp_h else "Median (basis)", d["median_pe"]),
                         ("Kuartil atas", d["q3_pe"])):
            value = fmt.tick(pe * d["eps_idr"])
            rows.append([name, fmt.mult(pe, 1), f"Rp{fmt.rp(value)}",
                         fmt.pct(value / intake["price"] - 1)])
        sensitivity = {
            "n": 0, "judul": (f"Silang cek: PER peer x EPS {label}" if sotp_h
                              else f"Target harga: PER peer x EPS {label}"), "tipe": "tabel",
            "data": {"cols": ["PER peer", "Kelipatan", "Nilai per saham", "Terhadap harga"],
                     "rows": rows},
            "catatan_sumber": (
                f"Sumber: PER TTM data Sectors"
                + (f" ({intake['peer_basis']})" if intake.get("peer_basis") else "")
                + f" untuk peer dengan PER 0-50x ({peer_names}); "
                + (f"saham dari {_shares_source(intake.get('official_evidence'))}"
                   if _shares_source(intake.get("official_evidence"))
                   else "saham dari neraca interim resmi")
                + (f"; kurs Rp{fmt.rp(d['fx'])}/USD" if d.get("fx") else "")
                + f"; harga penutupan {intake['price_date']}.")}
    if pbv:
        coes = [pbv["coe"] - 0.01, pbv["coe"], pbv["coe"] + 0.01]
        gs = [pbv["g"] - 0.01, pbv["g"], pbv["g"] + 0.01]
        grid_rows = []
        for coe in coes:
            row = [f"CoE {fmt.pct(coe)}" + (" (basis)" if coe == pbv["coe"] else "")]
            for g_ in gs:
                value = ((pbv["roe"] - g_) / (coe - g_) * pbv["bvps"]
                         if coe > g_ and pbv["roe"] > g_ else None)
                row.append(f"Rp{fmt.rp(fmt.tick(value))}" if value else "n.m.")
            grid_rows.append(row)
        sensitivity = {
            "n": 0, "judul": f"Target harga: P/BV wajar dari ROE {label} (sensitivitas CoE x g)",
            "tipe": "tabel",
            "data": {"cols": ["Cost of equity"] + [f"g {fmt.pct(g_)}" for g_ in gs],
                     "rows": grid_rows},
            "catatan_sumber": (
                f"Sumber: ROE {label} = laba pemilik induk skenario / ekuitas pemilik induk "
                f"({pbv['equity_source']}); CoE CAPM (rf IDR house policy, beta dan ERP 4% kebijakan "
                f"analis); P/BV wajar = (ROE - g) / (CoE - g) x BVPS; "
                + (f"saham dari {_shares_source(intake.get('official_evidence'))}"
                   if _shares_source(intake.get("official_evidence"))
                   else "saham dari neraca interim resmi")
                + f"; harga penutupan {intake['price_date']}. PER peer menjadi cross-check.")}
    if book:
        rows_pb = []
        for name, pb in (("Kuartil bawah", book["q1_pb"]), ("Median (basis)", book["median_pb"]),
                         ("Kuartil atas", book["q3_pb"])):
            value = fmt.tick(pb * book["bvps"])
            rows_pb.append([name, fmt.mult(pb, 2), f"Rp{fmt.rp(value)}",
                            fmt.pct(value / intake["price"] - 1)])
        sensitivity = {
            "n": 0, "judul": "Target harga: P/B peer x nilai buku terlapor", "tipe": "tabel",
            "data": {"cols": ["P/B peer", "Kelipatan", "Nilai per saham", "Terhadap harga"],
                     "rows": rows_pb},
            "catatan_sumber": (
                "Sumber: P/B TTM data Sectors untuk peer dengan P/B 0-10x; ekuitas pemilik induk "
                f"dari neraca interim resmi per {book.get('balance_period') or '-'}"
                + (f"; kurs Rp{fmt.rp(d['fx'])}/USD" if d.get("fx") else "")
                + f"; harga penutupan {intake['price_date']}. Skenario laba FY menjadi konteks "
                  "tesis, bukan dasar target.")}
    if ddm_s:
        sensitivity = _ddm_scenario_exhibits(intake, ddm_s, label)
    if dcf_s:
        sensitivity = _dcf_scenario_exhibits(intake, dcf_s, label, forward)
    if ev_s:
        sensitivity = _ev_ebitda_scenario_exhibit(intake, ev_s, label)
    exhibits = [bridge] + (sensitivity if isinstance(sensitivity, list) else
                           [sensitivity] if sensitivity else [])
    if bank_texts and bank_texts[2]:
        exhibits.append(bank_texts[2])
    elif forward:
        exhibits.append({
            "n": 0, "judul": f"Skenario laba {forward[0]['label']}-{forward[-1]['label']}",
            "tipe": "tabel",
            "data": {"cols": ["Tahun", "Pendapatan", "Tumbuh", "Laba bersih", "Margin bersih",
                              "EPS (Rp)", "Dasar"],
                     "rows": [[r["label"], money(r["revenue"]),
                               fmt.pct(r["revenue_growth_pct"] / 100), money(r["net_profit"]),
                               fmt.pct(r["net_income_margin_pct"] / 100),
                               fmt.rp(round(eps_of(r["net_profit_attributable"]))),
                               "Asumsi analis; bukan panduan emiten."] for r in forward]},
            "catatan_sumber": (
                f"Sumber: asumsi analis tahunan dari rilis resmi dan berita bertanggal; "
                f"bukan panduan emiten. Pendapatan dan laba bersih dalam {unit}. "
                + (f"Skenario nilai memakai seluruh jalur {label}-{forward[-1]['label']}."
                   if primary else f"Skenario nilai memakai {label}."))})
    safe_thesis = [
        _t(f"Skenario {label} menggabungkan hasil interim resmi dengan asumsi semester kedua.",
           f"The {label} scenario combines official interim results with second-half assumptions."),
        _t(f"Laba bersih model {label} {fy_money}; margin bersih {fmt.pct(fy['net_profit'] / fy['revenue']) if fy.get('revenue') else 'n.m.'}.",
           f"Model {label} net profit is {fy_money}; net margin {fmt.pct(fy['net_profit'] / fy['revenue']) if fy.get('revenue') else 'n.m.'}."),
        _t(f"Target harga dihitung dengan {va['method']} dan skenario yang tercantum pada tabel.",
           f"The Target Price is calculated with {prose_lang.source(va['method'])} and the "
           "scenario in the table.")]
    safe_titles = [_t("Hasil interim dan asumsi H2", "Interim results and H2 assumptions"),
                   _t("Laba dan margin skenario", "Scenario profit and margin"),
                   _t("Metode target harga", "Target Price method")]
    doc["bagian"].append(_thesis_cards_page(intake, safe_thesis, fy, va, label, usd, to_idr,
                                            safe_titles))
    doc["bagian"].append({"halaman": 0, "judul": ("Target harga berbasis SOTP holding" if sotp_h
                                                   else "Target harga berbasis DDM" if ddm_s else
                                                   "Target harga berbasis DCF FCFF" if dcf_s else
                                                   "Target harga berbasis EV/EBITDA peer" if ev_s else
                                                   f"Target harga berbasis ROE {label}" if pbv else
                                                   "Target harga berbasis nilai buku" if book
                                                   else f"Target harga berbasis laba {label}"),
                          "layout": "stack", "paragraf": [valuation_text],
                          "exhibit": exhibits})
    doc["exhibits"].extend(exhibits)

    # --- Key Financials: FY forecast columns, EPS and PER
    key_fin = exhibit_ids.find(doc["exhibits"], exhibit_ids.KEY_FINANCIALS)
    if key_fin:
        cols = key_fin["data"]["cols"]
        # Scenario EBITDA is shown wherever the scenario carries it, the same
        # rule as the financial tables and charts, so every table agrees.
        projections = {label: dict(fy)}
        projections.update({r["label"]: r for r in forward})
        modelled_ebitda = any(p.get("ebitda") is not None for p in projections.values())
        # Prior-year base for forecast growth: official annuals, then the scenario.
        raw = {str(r["year"]): r for r in
               (intake.get("official_evidence") or {}).get("annual_actuals") or []}
        raw.update(projections)

        def metric_of(name):
            name = name.lower()
            return ("revenue" if "pendapatan" in name else "ebitda" if "ebitda" in name
                    # Parent's share, like the actual columns and EPS.
                    else "net_profit_attributable" if "laba bersih" in name else None)

        for row in key_fin["data"]["rows"]:
            metric = metric_of(row[0])
            if not metric:
                continue
            for col, name in enumerate(cols):
                value = (projections.get(name) or {}).get(metric)
                if col >= len(row) or name not in projections:
                    continue
                if row[0].startswith("Pertumbuhan"):
                    prior = (raw.get(cols[col - 1]) or {}).get(metric)
                    row[col] = (fmt.pct(value / prior - 1) if value is not None and prior
                                and prior > 0 and value >= 0 else row[col])
                elif value is not None and "Rp miliar" in row[0]:
                    row[col] = fmt._id(value * to_idr / 1e9, 1)
                elif value is not None and unit in row[0]:
                    row[col] = money(value)
        annual = {str(x["year"]): x.get("earnings") for x in intake.get("annuals") or []}
        # A US$ reporter's actual EPS uses its official US$ profit at the same
        # rate as the forecast, so EPS growth is not an FX effect.
        if usd:
            for row in (intake.get("official_evidence") or {}).get("annual_actuals") or []:
                profit = (row.get("net_profit_attributable")
                          if row.get("net_profit_attributable") is not None else row.get("net_profit"))
                if profit is not None:
                    annual[str(row["year"])] = profit * to_idr
        eps_row, per_row = ["EPS (Rp)"], ["PER (x)"]
        eps_values = []
        for name in cols[1:]:
            proj = projections.get(name)
            eps = (eps_of(proj["net_profit_attributable"]) if proj and
                   proj.get("net_profit_attributable") is not None else
                   annual.get(name) / d["shares"] if annual.get(name) else None)
            eps_row.append(fmt.rp(round(eps)) if eps else "-")
            eps_values.append(eps)
            per_row.append(fmt.mult(intake["price"] / eps, 1, cap=fmt.MULT_CAP) if eps and eps > 0 else "-")
        # Replace the official table's per-share rows rather than repeat them,
        # and drop rows with no value in any period (DPS, PBV, ...).
        key_fin["data"]["rows"] = [
            row for row in key_fin["data"]["rows"]
            if not row[0].startswith(("EPS", "PER"))
            and any(cell not in ("-", "NA") for cell in row[1:])] + [
                eps_row,
                # Struktur Exhibit 3: EPS growth sits under EPS.
                ["Pertumbuhan EPS (%)", "-"] + [
                    fmt.pct(now / before - 1) if now and before and before > 0 else "-"
                    for before, now in zip(eps_values, eps_values[1:])],
                per_row]
        # The base note says forecast columns are not modelled; they now are.
        base_note = re.sub(r"\s*(Kolom forecast dan multiple belum tersedia karena model belum lolos "
                           r"validasi \(NA: belum dimodelkan\)\.|\S+-\S+ belum diterbitkan "
                           r"\(NA: belum dimodelkan\)\.)", "", key_fin.get("catatan_sumber") or "")
        key_fin["catatan_sumber"] = (
            base_note +
            f" {label} dan tahun sesudahnya: "
            + ("model driver bank atas driver skenario analis (kredit, NIM, pendapatan "
               "non-bunga, rasio biaya, biaya kredit)" if bank_fc else "skenario laba analis")
            + ("; EBITDA dari margin skenario DCF. " if dcf_s else
               "; EBITDA dari margin skenario analis. " if modelled_ebitda else
               # EBITDA means nothing for a bank; Key Financials leaves it out.
               ". " if intake.get("model_profile") == "financial_ddm" else
               "; EBITDA tidak dimodelkan. ") +
            f"EPS memakai saham {actual.get('period_end', '-')}"
            + (f" dari {_shares_source(intake.get('official_evidence'))}"
               if _shares_source(intake.get("official_evidence")) else " dari neraca")
            + " (pro forma untuk tahun "
            f"historis"
            + (f"; laba US$ aktual resmi dikonversi pada kurs yang sama dengan forecast"
               if usd else "")
            + f"); PER memakai harga {intake['price_date']}.")

    if sotp_h:
        doc["catatan_metodologi"] = [
            _t("Rating dan target harga memakai SOTP holding, metode utama untuk grup dengan lini "
               "usaha berbeda: anak usaha tercatat pada kapitalisasi pasar dikali "
               "kepemilikan, sisa ekuitas pemilik induk pada nilai buku.",
               "Rating and Target Price use a holding SOTP, the Primary Method for a group with "
               "distinct business lines: listed subsidiaries at market capitalisation times "
               "ownership, the remaining parent equity at book value."),
            (_t("Tanah untuk pengembangan dinilai dengan RNAV landbank (laju penjualan historis, "
                "harga marketing terakhir, margin kas segmen properti, CoE kebijakan); hotel dan "
                "utilitas pada nilai buku; diskon holding 20-30% hanya sensitivitas.",
                "Land for development is valued with a landbank RNAV (historical sales pace, "
                "latest marketing price, property segment cash margin, policy CoE); hotels and "
                "utilities at book value; the 20-30% holding discount is a sensitivity only.")
             if (sotp_h or {}).get("landbank") else
             _t("Segmen tanpa harga pasar (lahan industri, hotel, utilitas) dinilai pada nilai buku; "
                "diskon holding 20-30% hanya sensitivitas.",
                "Segments without a market price (industrial land, hotels, utilities) are valued at "
                "book value; the 20-30% holding discount is a sensitivity only.")),
            _t("DCF konsolidasi atas skenario analis menjadi referensi di rantai metode; PER FY "
               "skenario menjadi langkah terakhir.",
               "A consolidated DCF on the analyst scenario is the reference in the Method Chain; "
               "scenario FY PER is the last step."),
            _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
        ]
        return doc
    if primary:
        doc["catatan_metodologi"] = _scenario_primary_notes(ddm_s, dcf_s, label, forward, ev_s,
                                                           intake.get("price"))
        return doc
    doc["catatan_metodologi"] = [
        (_t(f"Rating dan target harga memakai P/BV wajar dari ROE {label} (excess return untuk "
            "bank); ROE memakai laba skenario analis dari aktual 1H resmi dan asumsi H2, dan PER "
            "peer menjadi cross-check.",
            f"Rating and Target Price use a fair P/BV from {label} ROE (excess return for a "
            "bank); ROE uses analyst scenario profit from official 1H actuals and H2 assumptions, "
            "and peer PER is the cross-check.") if pbv else
         _t("Rating dan target harga memakai P/B median peer atas nilai buku terlapor (emiten "
            "aset berat, PER peer valid kurang dari tiga); skenario laba FY menjadi konteks tesis.",
            "Rating and Target Price use the median peer P/B on reported book value (an "
            "asset-heavy company with fewer than three valid peer PERs); the FY profit scenario "
            "is thesis context.")
         if book else
         _t(f"Rating dan target harga memakai PER median peer atas EPS {label}; EPS adalah "
            "skenario analis dari aktual 1H resmi dan asumsi H2, bukan forecast driver.",
            f"Rating and Target Price use the median peer PER on {label} EPS; EPS is an analyst "
            "scenario from official 1H actuals and H2 assumptions, not a driver forecast.")),
        _t(f"Rantai metode: {', '.join(skipped) or '-'} dilewati karena forecast driver belum "
           "direkonsiliasi",
           f"Method Chain: {', '.join(skipped) or '-'} skipped because the driver forecast is not "
           "yet reconciled")
        + ("." if pbv else _t("; P/BV buku adalah langkah terakhir rantai.",
                              "; book P/BV is the last step of the chain.")
           if book else _t("; metode ini adalah langkah terakhir rantai.",
                           "; this method is the last step of the chain.")),
        _t(f"PER peer adalah TTM dari data Sectors ({peer_names}); peer dianggap sebanding, "
           "dan kuartil bawah/atas menjadi sensitivitas.",
           f"Peer PER is TTM from Sectors data ({peer_names}); peers are taken as comparable, "
           "and the lower/upper quartiles are the sensitivity."),
        _t("Skenario tahun lanjutan adalah asumsi analis tahunan dan tidak mengubah tahun dasar target.",
           "Forward-year scenarios are annual analyst assumptions and do not change the target's "
           "base year."),
        _t("Arus kas, capex dan neraca sesudah periode interim belum dimodelkan.",
           "Cash flow, capex and the balance sheet after the interim period are not yet modelled."),
        _t("Tanda '-' berarti angka tidak tersedia, bukan nol.", "A dash (-) means the figure is not available, not zero."),
    ]
    return doc


# English for the fixed source phrases other modules put into this prose
# (valuation's equity source, method_chain's peer EV sources and the short
# method names its trace carries; the rest of method_chain.SHORT is the same
# in both languages).
_EQUITY_SOURCE_EN = {"neraca interim resmi": "official interim balance sheet"}
_SHORT_EN = {"pbv_relative": "relative P/BV", "dcf_reference": "reference DCF",
             "relative_pe": "relative PER", "pbv_roe_fy": "scenario FY P/BV-ROE",
             "pbv_book": "book P/BV", "pe_fy_scenario": "scenario FY PER"}


def _peer_source_en(text):
    return (str(text).replace("data Sectors", "Sectors data")
            .replace("sumber tidak tercatat", "unrecorded source")
            .replace("tanpa peer", "no peers").replace(" dan ", " and "))


# The metric names and comparison period callers pass to _change_sentence.
_CHANGE_TERMS_EN = {"pendapatan": "revenue", "laba usaha": "operating profit",
                    "laba bersih": "net profit", "periode pembanding": "the comparison period"}


def _change_sentence(label, value, prior, period, prior_period, money_phrase):
    """One metric per sentence (spec §5.1: at most three figures per sentence).

    Growth off a near-zero or loss base is described in words, not as a
    four-digit percentage that says nothing about the business.
    """
    label = _t(label, _CHANGE_TERMS_EN.get(label, label))
    prior_period = _t(prior_period, _CHANGE_TERMS_EN.get(prior_period, prior_period))
    subject = label[:1].upper() + label[1:]
    if value is None:
        return ""
    if prior is None:
        return _t(f"{subject} {period} {money_phrase(value)}.",
                  f"{period} {label} was {money_phrase(value)}.")
    if prior < 0 <= value:
        return _t(f"{subject} {period} {money_phrase(value)}, berbalik dari rugi "
                  f"{money_phrase(abs(prior))} pada {prior_period}.",
                  f"{period} {label} was {money_phrase(value)}, reversing a loss of "
                  f"{money_phrase(abs(prior))} in {prior_period}.")
    if prior > 0 and value / prior - 1 > 3:
        return _t(f"{subject} {period} naik ke {money_phrase(value)} dari basis rendah "
                  f"{money_phrase(prior)} pada {prior_period}.",
                  f"{period} {label} rose to {money_phrase(value)} from a low base of "
                  f"{money_phrase(prior)} in {prior_period}.")
    if prior > 0:
        change = value / prior - 1
        return _t(f"{subject} {period} {'naik' if change >= 0 else 'turun'} "
                  f"{fmt.pct(abs(change))} yoy ke {money_phrase(value)}.",
                  f"{period} {label} {'rose' if change >= 0 else 'fell'} "
                  f"{fmt.pct(abs(change))} yoy to {money_phrase(value)}.")
    return _t(f"{subject} {period} {money_phrase(value)}.",
              f"{period} {label} was {money_phrase(value)}.")


def _assumption_headline(rating, forecast_label):
    """Neutral scenario headline; never infer a trading action from the model."""
    return _t(f"Skenario {forecast_label}: estimasi model berbasis asumsi analis",
              f"{forecast_label} scenario: model estimates on analyst assumptions")


def _research_section(intake, page=2):
    """Build print-friendly cards from the upstream-validated research brief."""
    from . import prose_lang
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
        cards.append({"title": _word_cut(prose_lang.source(item.get("title"))
                                         or _t("Temuan", "Finding"), 100),
                      "observation": _word_cut(prose_lang.source(item.get("observation")) or "-", 330),
                      "implication": _word_cut(prose_lang.source(item.get("implication")) or "-", 330),
                      "caveat": _word_cut(prose_lang.source(item.get("caveat")) or "-", 240),
                      "citations": citations[:4]})
    if not cards:
        return None
    paragraphs = []
    summary = brief.get("summary")
    if summary:
        paragraphs.append(_word_cut(prose_lang.source(summary), 320))
    as_of = brief.get("as_of")
    if as_of:
        paragraphs.append(_t(f"Ringkasan riset bertanggal {str(as_of)[:40]}.",
                             f"Research summary dated {str(as_of)[:40]}."))
    limitations = brief.get("limitations")
    if isinstance(limitations, list) and limitations:
        paragraphs.append(_t("Batasan: ", "Limitations: ") + "; ".join(
            _word_cut(prose_lang.source(x), 120) for x in limitations[:4]))
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


def _build_draft(intake, fc, va, s1, method="auto",
                 illustrative_scenarios=False):
    """Build a clearly non-distributable evidence/status report.

    Do not expose the legacy DCF target or imply that the historical-CAGR
    mining screen is a production forecast. All reported facts come from the
    Sectors cache; local research documents and analyst estimate files are
    deliberately excluded.
    """
    if (intake.get("model_profile") != "finite_life_mining" or
            intake.get("official_evidence")):
        return _build_general_draft(intake, fc, va, s1, method=method,
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
    hist_no = add("Laporan historis di data Sectors",
                  ["Metrik"] + [str(a.get("year", "-")) for a in hist], hist_rows,
                  "Sumber: Sectors, company/report; angka historis belum direkonsiliasi ke interim terbaru.")

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
            "Kinerja kuartalan yang tersedia di data Sectors",
            ["Metrik", period_end], quarter_rows,
            f"Sumber: Sectors, financials/quarterly/{t}; tanggal adalah akhir periode. "
            "Data Sectors tidak menyimpan tanggal publikasi/halaman untuk memvalidasi ketersediaan historis.")

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
                "agen tetap merujuk pada judul dan tautan yang sama dengan data Sectors."
            )
        news_no = add(
            "Konteks berita dari Sectors dan implikasi",
            ["Tanggal", "Narasi ulang", "Kaitan ke tesis", "Batasan"], news_rows,
            "Analisis agen atas berita ticker-spesifik di data Sectors /news/. "
            "Berita adalah konteks media, bukan guidance; tidak mengubah forecast numerik "
            "tanpa dukungan data finansial/operasi Sectors. Referensi: " +
            "; ".join(news_sources) + "." + deepdive_note)

    blocker_groups = {}
    chain = va.get("method_chain") or {}
    sotp_skip = next((t for t in chain.get("trace") or []
                      if t["key"] == "sotp_lom" and t["decision"] == "skipped"
                      and t["reasons"]), None)
    shown = list(blockers)
    if sotp_skip and not sotp_skip["reasons"][0].startswith("SOTP"):
        # SOTP/LoM computed but held by its own gate: name that reason.
        blocker_groups["Valuasi SOTP/LoM"] = (
            "SOTP/LoM dihitung tetapi ditahan: "
            f"{method_chain.reader_reason(sotp_skip['reasons'][0])}.")
    elif sotp_skip:
        shown.append(sotp_skip["reasons"][0])
    for item in shown:
        if item.startswith("latest interim actuals"):
            latest_date = ((intake.get("latest_quarterly_actual") or {}).get("date")
                           or "belum tersedia")
            blocker_groups["Validasi interim dari data Sectors"] = (
                f"Baris kuartalan terakhir berakhir {latest_date}; data Sectors belum memberi "
                "tanggal publikasi dan metadata kelengkapan untuk membuktikan data terbaru "
                f"per {intake.get('as_of') or intake.get('price_date')}.")
        elif item.startswith("operating bridge"):
            blocker_groups["Jembatan operasi ke keuangan"] = (
                "Belum ada rangkaian bukti yang menghubungkan produksi fisik ke penjualan, "
                "biaya, EBITDA, capex, modal kerja, utang dan FCFF.")
        elif item.startswith("mining forecast"):
            blocker_groups["Forecast fisik tambang"] = (
                "Forecast fisik-ke-keuangan belum dihitung dan direkonsiliasi; CAGR hanya screening.")
        elif item.startswith("method chain") or item.startswith("extreme "):
            blocker_groups["Rantai metode valuasi"] = _method_chain_text(va) or "Belum terpenuhi."
        elif item.startswith("SOTP"):
            blocker_groups["Valuasi SOTP/LoM"] = (
            "NAV per aset dan/atau jembatan ekuitas belum lengkap; skenario nilai belum dapat disajikan.")
        else:
            blocker_groups[item] = "Belum terpenuhi."
    if chain.get("trace"):
        blocker_groups.setdefault("Rantai metode valuasi", _method_chain_text(va))
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

    # model_profiles writes the basis in English already.
    profile_basis = (intake.get("model_profile_basis")
                     or _t("basis profil tidak tersedia", "profile basis not available"))
    price_date = intake.get("price_date")
    profile_text = _t(f"Model profile: {profile} ({profile_basis}). Fakta yang ditampilkan "
                      "dan angka historis hanya berasal dari data Sectors. Belum ada "
                      "forecast fisik-ke-keuangan yang lolos rekonsiliasi; nilai CAGR dan "
                      "RNAV annuitas tidak dipakai sebagai target.",
                      f"Model profile: {profile} ({profile_basis}). The facts shown and "
                      "historical figures come only from Sectors data. No physical-to-financial "
                      "forecast has passed reconciliation yet; the CAGR values and annuity RNAV "
                      "are not used as a target.")
    release_text = _t("Dokumen ini berstatus DRAFT NON-DISTRIBUTABLE. Skenario nilai belum "
                      "disajikan karena data interim, forecast fisik, dan provenance "
                      "yang tersedia di data Sectors belum lengkap; SOTP/LoM belum dapat direkonsiliasi. "
                      "Tidak ada target DCF substitusi.",
                      "This document is a DRAFT NON-DISTRIBUTABLE. No value scenario is shown "
                      "because the interim data, physical forecast and provenance available in "
                      "Sectors data are incomplete; SOTP/LoM cannot yet be reconciled. "
                      "There is no substitute DCF target.")
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
                         "paragraf": [_t("Ringkasan berikut diparafrase dari berita dalam data Sectors. "
                                         "Kaitan ke operasi/laba dibedakan dari sentimen pasar; "
                                         "berita tidak menjadi asumsi angka tanpa bukti dari data Sectors.",
                                         "The following summary is paraphrased from news in Sectors "
                                         "data. Links to operations and profit are kept apart from "
                                         "market sentiment; news does not become a numeric "
                                         "assumption without evidence from Sectors data.")],
                         "exhibit": [exhibits[news_no - 1]]})
        next_page += 1
    if screening_no:
        sections.append({"halaman": next_page, "judul": "Screen historis untuk diskusi internal",
                         "paragraf": [_t("Angka berikut adalah screening berbasis data historis, "
                                         "bukan estimasi produksi atau guidance.",
                                         "The following figures are a screen based on historical "
                                         "data, not a production estimate or guidance.")],
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
        "headline": _t("Bukti Model Belum Lengkap", "Model Evidence Incomplete"),
            "bullets": [
                _t("Skenario nilai belum disajikan karena bukti penting masih kurang.",
                   "No value scenario is shown because key evidence is still missing."),
                _t("Data historis memakai Sectors; rilis emiten dan berita bertanggal dicatat dengan sumbernya.",
                   "Historical data uses Sectors; company releases and dated news are recorded with "
                   "their sources."),
                _t("Berita yang lolos validasi diparafrase dan dihubungkan ke tesis dengan caveat.",
                   "News that passes validation is paraphrased and linked to the thesis with caveats."),
                _t("SOTP/LoM belum dapat direkonsiliasi dari input yang tersedia.",
                   "SOTP/LoM cannot yet be reconciled from the available inputs."),
            ],
            "paragraf": [
                {"judul": "Status riset", "isi": release_text},
                {"judul": "Basis model", "isi": profile_text},
            ],
            "data_pasar": {"harga": price,
                            "saham": intake["shares"], "market_cap": market_cap,
                            "adtv": "-", "public_ownership": "-"},
            "key_financials": hist_rows,
        },
        "bagian": sections,
        "tabel_asumsi": [],
        "log_gate": {"S1": s1.get("S1", {}), "S2": fc.get("s2", {}),
                     "S3": {}, "release": {"status": release_result.get("status"),
                                              "blocker_count": len(blockers)}},
        "method": ("DDM (dividen, Rp)" if method == "ddm" else
                   "DCF (FCFF, Rp)" if method == "dcf" else
                   "RNAV LoM (Rp)" if method == "rnav" else
                   method_chain.LABELS[method] if method in method_chain.LABELS else
                   _chain_cover_label(va, "SOTP/LoM (belum lengkap)")),
        "method_select": method, "holders": [],
        "catatan_metodologi": (
            [_t(f"metode valuasi dipilih analis: {_method_label(method)}.",
                f"Valuation method chosen by the analyst: {_method_label(method)}.")]
            if method != "auto" else []
        ) + [
            _t("DRAFT NON-DISTRIBUTABLE: skenario nilai belum disajikan karena bukti belum lengkap.",
               "DRAFT NON-DISTRIBUTABLE: no value scenario is shown because the evidence is incomplete."),
            _t("SOTP/LoM memerlukan NAV per aset, kepemilikan, net debt, minority interest, "
               "overhead korporat dan saham terdilusi dengan provenance.",
               "SOTP/LoM needs NAV per asset, ownership, net debt, minority interest, corporate "
               "overhead and diluted shares, each with provenance."),
            _t("Validasi latest interim memakai rilis emiten resmi bila tersedia, dengan tanggal dan sumber tercatat.",
               "Latest Interim Actuals are validated against the official company release where "
               "available, with date and source recorded."),
            _t("Berita ticker-spesifik dari Sectors dan Tavily dapat mendasari asumsi analis yang diberi label dan diuji dampaknya.",
               "Ticker-specific news from Sectors and Tavily can underpin labelled analyst "
               "assumptions whose impact is tested."),
            _t("Forecast tambang harus dihitung dari driver fisik; proyeksi CAGR hanya screening.",
               "A mining forecast must be built from physical drivers; CAGR projections are a "
               "screen only."),
            _t("RNAV annuitas indikatif dari overlay data Sectors bukan nilai wajar karena bukan SOTP asset-level.",
               "The indicative annuity RNAV from the Sectors data overlay is not a fair value "
               "because it is not an asset-level SOTP."),
        ],
        "exhibits": exhibits,
    }


def _build_report(intake, fc, va, s1, method="auto", illustrative_scenarios=False):
    method = (method or "auto").lower()
    # Override analis (gate-driven keys) diterima untuk display; validasi DCF/DDM/RNAV lama dipertahankan.
    from . import method_chain as _mc
    allowed = {"auto", "dcf", "ddm", "rnav"} | set(_mc.LABELS.keys())
    if method not in allowed:
        raise ValueError(f"method tak dikenal: {method} (auto atau method key rantai)")
    if method == "ddm" and intake.get("payout") is None:
        raise ValueError("method ddm ditolak: tanpa payout di data Sectors")
    if method == "rnav" and not intake.get("mineops"):
        raise ValueError("method rnav ditolak: tanpa overlay operasional di data Sectors")
    status = (va.get("release") or {}).get("status")
    operating = (fc.get("earnings_scenario") or {}).get("basis") in (
        "operating_driver_model", "bank_driver_scenario")
    physical = fc.get("forecast_basis") == "physical_driver_forecast"
    # A holding SOTP values listed stakes and assets on the Report Date, not a
    # forecast; Production-Ready or not, it renders through its own layout.
    holding = (va.get("method_chain") or {}).get("selected") == "holding_sotp"
    if status == "distributable_assumption_led" or (status == "distributable"
                                                   and (operating or physical or holding)):
        # A Production-Ready operating model renders through the same scenario
        # layout it was valued on; only the release status differs.
        if intake.get("model_profile") == "finite_life_mining":
            return _build_assumption_led(intake, fc, va, s1, method=method)
        chain = va.get("method_chain") or {}
        selected = chain.get("selected")
        scenario_primary = any(
            t.get("key") == selected and (t.get("detail") or {}).get("basis") == "scenario"
            for t in chain.get("trace") or [])
        if selected in ("pe_fy_scenario", "pbv_roe_fy", "pbv_book", "holding_sotp") or \
                scenario_primary:
            return _build_earnings_led(intake, fc, va, s1, method=method)
        return _build_assumption_led(intake, fc, va, s1, method=method)
    if (va.get("release") or {}).get("status") != "distributable":
        doc = _build_draft(intake, fc, va, s1, method=method,
                           illustrative_scenarios=illustrative_scenarios)
        _extreme_stop_overlay(doc, intake, va)
        return doc
    from . import prose_lang
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
    peer_txt = (_t(f"median PER TTM peer {fmt.mult(intake['peer_median_pe'])} dibanding "
                   f"PER {f1['label']} model {fmt.mult(per1)}",
                   f"a peer median TTM PER of {fmt.mult(intake['peer_median_pe'])} against a "
                   f"model {f1['label']} PER of {fmt.mult(per1)}")
                if intake.get("peer_median_pe") and per1 else
                _t("tanpa pembanding peer yang memadai di data Sectors",
                   "no adequate peer comparison in Sectors data"))

    headline = _headline(intake, fc)
    b1 = _trim(_t(f"Laba {F[0]['label']} diproyeksikan Rp{fmt.miliar(f1['net'])} miliar "
                  f"dengan margin EBITDA {mg}, didorong pertumbuhan pendapatan {rev_g}.",
                  f"{F[0]['label']} profit is projected at Rp{fmt.miliar(f1['net'])} miliar "
                  f"at an EBITDA margin of {mg}, driven by revenue growth of {rev_g}."), 30)
    b2 = _trim(_t(f"Driver utama {F[1]['label']}-{F[-1]['label']} adalah volume dan operating "
                  f"leverage menuju margin {fmt.pct(F[-1]['margin'])}.",
                  f"The main {F[1]['label']}-{F[-1]['label']} drivers are volume and operating "
                  f"leverage towards a {fmt.pct(F[-1]['margin'])} margin."), 30)
    b3 = _trim(_t(f"{va['rating']} dengan Target Harga Rp{modeled_value_s} "
                  f"(upside/downside {fmt.pct(va['upside'])}) berdasarkan {va['method']}.",
                  f"{va['rating']} with a Target Price of Rp{modeled_value_s} "
                  f"({fmt.pct(va['upside'])} upside/downside) based on "
                  f"{prose_lang.source(va['method'])}."), 30)

    p1 = _t(f"{name} menutup {last['year']} dengan pendapatan Rp{fmt.miliar(rev_last)} miliar "
            f"({yoy_rev} yoy) dan EBITDA Rp{fmt.miliar(last['ebitda'] or 0)} miliar ({yoy_eb} yoy) "
            f"pada margin {m_last}. Laba bersih tercatat Rp{fmt.miliar(last['earnings'] or 0)} miliar "
            f"({yoy_net} yoy). Model kami memproyeksikan pendapatan {f1['label']} "
            f"Rp{fmt.miliar(f1['revenue'])} miliar ({rev_g}), dengan EBITDA Rp{fmt.miliar(f1['ebitda'])} miliar "
            f"({ebitda_g}) pada margin {mg}. Laba bersih {f1['label']} diproyeksikan "
            f"Rp{fmt.miliar(f1['net'])} miliar, lalu tumbuh ke Rp{fmt.miliar(f3['net'])} miliar pada "
            f"{f3['label']} seiring operating leverage menuju margin {fmt.pct(f3['margin'])}. Basis ini "
            f"konsisten dengan CAGR historis {fmt.pct(rev_cagr)} sejak {A[0]['year']}, sehingga jalur "
            f"forecast tidak mengasumsikan percepatan di luar rekam jejak. Implikasinya, pertumbuhan "
            f"{f1['label']}-{f3['label']} bertumpu pada ekspansi volume dan disiplin biaya ketimbang "
            f"kenaikan harga.",
            f"{name} closed {last['year']} with revenue of Rp{fmt.miliar(rev_last)} miliar "
            f"({yoy_rev} yoy) and EBITDA of Rp{fmt.miliar(last['ebitda'] or 0)} miliar ({yoy_eb} yoy) "
            f"at a {m_last} margin. Net profit was Rp{fmt.miliar(last['earnings'] or 0)} miliar "
            f"({yoy_net} yoy). Our model projects {f1['label']} revenue of "
            f"Rp{fmt.miliar(f1['revenue'])} miliar ({rev_g}) and EBITDA of Rp{fmt.miliar(f1['ebitda'])} miliar "
            f"({ebitda_g}) at a {mg} margin. {f1['label']} net profit is projected at "
            f"Rp{fmt.miliar(f1['net'])} miliar, rising to Rp{fmt.miliar(f3['net'])} miliar in "
            f"{f3['label']} as operating leverage lifts the margin to {fmt.pct(f3['margin'])}. This "
            f"base is consistent with the historical CAGR of {fmt.pct(rev_cagr)} since {A[0]['year']}, "
            f"so the forecast path assumes no acceleration beyond the track record. "
            f"{f1['label']}-{f3['label']} growth therefore rests on volume expansion and cost "
            f"discipline rather than price increases.")
    p1t = "Hasil terakhir jadi basis forecast"

    p2 = _t(f"Tesis kami untuk {F[1]['label']} sampai {f3['label']} bertumpu pada dua tuas. Pertama, "
            f"kelanjutan pertumbuhan pendapatan hingga Rp{fmt.miliar(f3['revenue'])} miliar pada "
            f"{f3['label']}. Kedua, pengangkatan margin EBITDA ke {fmt.pct(f3['margin'])}, yang masih di "
            f"dalam rentang historis sehingga tidak menuntut efisiensi yang belum pernah dicapai. Belanja "
            f"modal sustaining sekitar Rp{fmt.miliar(f1['capex'])} miliar per tahun, setara D&A, menjaga "
            f"arus kas bebas {f1['label']} Rp{fmt.miliar(f1['fcf'])} miliar dan naik ke "
            f"Rp{fmt.miliar(f3['fcf'])} miliar pada {f3['label']}. Konteks valuasi: {peer_txt}, sehingga "
            f"ekspektasi pasar sudah mencerminkan sebagian tesis ini. KPI pemantau tesis adalah realisasi "
            f"margin EBITDA tiap kuartal terhadap jalur {mg} menuju {fmt.pct(f3['margin'])}; deviasi dua "
            f"kuartal beruntun memicu revisi forecast.",
            f"Our thesis for {F[1]['label']} to {f3['label']} rests on two levers. First, continued "
            f"revenue growth to Rp{fmt.miliar(f3['revenue'])} miliar in {f3['label']}. Second, an "
            f"EBITDA margin lift to {fmt.pct(f3['margin'])}, still within the historical range, so it "
            f"needs no efficiency not achieved before. Sustaining capex of about "
            f"Rp{fmt.miliar(f1['capex'])} miliar a year, in line with D&A, keeps {f1['label']} free "
            f"cash flow at Rp{fmt.miliar(f1['fcf'])} miliar, rising to Rp{fmt.miliar(f3['fcf'])} miliar "
            f"in {f3['label']}. Valuation context: {peer_txt}, so market expectations already reflect "
            f"part of this thesis. The KPI to monitor is quarterly EBITDA margin delivery against the "
            f"path from {mg} to {fmt.pct(f3['margin'])}; two consecutive quarters of deviation trigger "
            f"a forecast revision.")
    p2t = "Volume dan leverage jadi mesin laba"

    r3 = _t("konsentrasi komoditas, eksekusi belanja modal, dan pelemahan harga",
            "commodity concentration, capex execution and weaker prices")
    wacc_in = va["wacc_inputs"]
    p3 = _t(f"Skenario nilai memakai {va['method']}, dengan WACC {fmt.pct(va['wacc'])} (risk-free "
            f"{fmt.pct(wacc_in['rf'])}, beta {fmt._id(wacc_in['beta'], 1)}) dan terminal growth "
            f"{fmt.pct(wacc_in['g'])}. Nilai skenario indikatif Rp{modeled_value_s} per saham "
            f"merupakan rerata Gordon Rp{fmt.rp(va['ps_gordon'])} dan exit EV/EBITDA "
            f"{fmt._id(wacc_in['exit_mult'], 1)}x Rp{fmt.rp(va['ps_exit'])}. Pada skenario ini, saham "
            f"diperdagangkan {fmt.mult(va['implied']['per'] or 0)} PER dan "
            f"{fmt.mult(va['implied']['ev_ebitda'] or 0)} EV/EBITDA {f1['label']}. Utang bersih posisi dasar "
            f"Rp{fmt.miliar(va['net_debt'])} miliar dipakai konsisten di seluruh perhitungan. Skenario "
            f"sensitivitas (WACC +1pp, g -1pp) menghasilkan Rp{fmt.rp(va['tp_down'])}, di bawah skenario dasar. "
            f"Risiko utama: {r3}.",
            f"The value scenario uses {prose_lang.source(va['method'])}, with a WACC of "
            f"{fmt.pct(va['wacc'])} (risk-free "
            f"{fmt.pct(wacc_in['rf'])}, beta {fmt._id(wacc_in['beta'], 1)}) and terminal growth of "
            f"{fmt.pct(wacc_in['g'])}. The indicative scenario value of Rp{modeled_value_s} per share "
            f"is the average of Gordon Rp{fmt.rp(va['ps_gordon'])} and exit EV/EBITDA "
            f"{fmt._id(wacc_in['exit_mult'], 1)}x Rp{fmt.rp(va['ps_exit'])}. In this scenario the "
            f"stock trades on {fmt.mult(va['implied']['per'] or 0)} PER and "
            f"{fmt.mult(va['implied']['ev_ebitda'] or 0)} {f1['label']} EV/EBITDA. Base net debt of "
            f"Rp{fmt.miliar(va['net_debt'])} miliar is used consistently throughout. The sensitivity "
            f"scenario (WACC +1pp, g -1pp) gives Rp{fmt.rp(va['tp_down'])}, below the base scenario. "
            f"Key risks: {r3}.")
    p3t = "Skenario nilai indikatif"

    # Left rail market data calculations: ADTV & public ownership
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

    p_ind1 = _t(f"Emiten beroperasi pada sektor {intake.get('industry') or 'terkait'} "
                f"(sub-sektor {intake.get('sub_sector') or '-'}). Rekam jejak historis "
                f"dari tahun {A[0]['year']} hingga {last['year']} membukukan pertumbuhan "
                f"pendapatan dengan CAGR {fmt.pct(rev_cagr)}, dari Rp{fmt.miliar(A[0]['revenue'])} miliar "
                f"menjadi Rp{fmt.miliar(rev_last)} miliar. Margin EBITDA berfluktuasi antara "
                f"{min_eb_mg} hingga {max_eb_mg} (posisi {last['year']} pada level {m_last}), "
                f"mencerminkan elastisitas operasional dan siklus harga. Total ekuitas bertumbuh ke "
                f"Rp{fmt.miliar(last['equity'] or 0)} miliar dengan akumulasi aset "
                f"Rp{fmt.miliar(last['assets'] or 0)} miliar pada penutupan {last['year']}.",
                (f"The company operates in the {intake.get('industry')} sector "
                 if intake.get('industry') else "The company operates in its sector ")
                + f"(sub-sector {intake.get('sub_sector') or '-'}). From {A[0]['year']} to "
                f"{last['year']} it grew revenue at a CAGR of {fmt.pct(rev_cagr)}, from "
                f"Rp{fmt.miliar(A[0]['revenue'])} miliar to Rp{fmt.miliar(rev_last)} miliar. The "
                f"EBITDA margin ranged from {min_eb_mg} to {max_eb_mg} ({last['year']} at {m_last}), "
                f"reflecting operating elasticity and the price cycle. Total equity grew to "
                f"Rp{fmt.miliar(last['equity'] or 0)} miliar with total assets of "
                f"Rp{fmt.miliar(last['assets'] or 0)} miliar at the close of {last['year']}.")

    p_ind2 = _t(f"Pandangan Kami: proyeksi periode {F[0]['label']}-{F[-1]['label']} tidak "
                "mengasumsikan akselerasi volume di luar rekam jejak historis, melainkan "
                "menumpukan ekspansi laba pada utilisasi kapasitas dan stabilitas biaya "
                f"operasional. Permintaan di sub-sektor {intake.get('sub_sector') or '-'} memberikan "
                "visibilitas pendapatan tahunan, sementara penyelesaian siklus belanja modal "
                "besar menopang pemulihan arus kas bebas menuju margin EBITDA "
                f"{fmt.pct(F[-1]['margin'])} pada {F[-1]['label']}.",
                f"Our view: the {F[0]['label']}-{F[-1]['label']} projections assume no volume "
                "acceleration beyond the historical track record; profit expansion rests on "
                "capacity utilisation and stable operating costs. Demand in the "
                f"{intake.get('sub_sector') or '-'} sub-sector gives visibility on annual revenue, "
                "while the end of a large capex cycle supports a free cash flow recovery towards "
                f"an EBITDA margin of {fmt.pct(F[-1]['margin'])} in {F[-1]['label']}.")

    p_ind3 = _t("Dinamika neraca dan arus kas historis menunjukkan disiplin pendanaan selama "
                f"periode ekspansi. Realisasi belanja modal rata-rata Rp{avg_capex} miliar per "
                "tahun berhasil diserap tanpa mengorbankan solvabilitas dasar, meletakkan "
                f"fondasi neraca yang solid untuk mendukung proyeksi {F[0]['label']}.",
                "The historical balance sheet and cash flow show funding discipline through the "
                f"expansion. Average capex of Rp{avg_capex} miliar a year was absorbed without "
                "weakening basic solvency, laying a solid balance-sheet base for the "
                f"{F[0]['label']} projections.")

    exh, n = [], [0]

    def E(judul, tipe, data, note="Source: Company, Sektoral Estimates"):
        n[0] += 1
        exh.append({"n": n[0], "judul": judul, "tipe": tipe, "data": data,
                    "catatan_sumber": note})
        return n[0]

    def _pct_change(cur, prev):
        try:
            if cur is None or prev in (None, 0):
                return "belum dimodelkan"
            return fmt.pct(cur / prev - 1)
        except (TypeError, ZeroDivisionError):
            return "belum dimodelkan"

    _eps_hist = [(a["earnings"] or 0) / intake["shares"] if a.get("earnings") is not None else None
                 for a in A[-2:]]
    _eps_f = [r.get("eps") for r in F]
    _eps_all = _eps_hist + _eps_f
    _eps_g = ["-"] + [_pct_change(_eps_all[i], _eps_all[i - 1]) if _eps_all[i] is not None and _eps_all[i - 1] not in (None, 0) else "belum dimodelkan"
              for i in range(1, len(_eps_all))]
    _rev_all = [a["revenue"] for a in A[-2:]] + [r["revenue"] for r in F]
    _rev_g = ["-"] + [_pct_change(_rev_all[i], _rev_all[i - 1]) for i in range(1, len(_rev_all))]
    _ebitda_all = [(a.get("ebitda") or 0) for a in A[-2:]] + [r.get("ebitda") for r in F]
    _ebitda_g = ["-"] + [_pct_change(_ebitda_all[i], _ebitda_all[i - 1]) if _ebitda_all[i - 1] else "belum dimodelkan"
                 for i in range(1, len(_ebitda_all))]
    kf_rows = [["Pendapatan (Rp miliar)"] + [fmt.miliar(a["revenue"]) for a in A[-2:]]
               + [fmt.miliar(r["revenue"]) for r in F]]
    kf_rows += [["Pertumbuhan pendapatan (%)"] + _rev_g[1:3] + _rev_g[3:]]
    kf_rows += [["EBITDA (Rp miliar)"] + [fmt.miliar(a["ebitda"] or 0) for a in A[-2:]]
                + [fmt.miliar(r["ebitda"]) for r in F]]
    kf_rows += [["Pertumbuhan EBITDA (%)"] + _ebitda_g[1:3] + _ebitda_g[3:]]
    kf_rows += [["Laba bersih (Rp miliar)"] + [fmt.miliar(a["earnings"] or 0) for a in A[-2:]]
                + [fmt.miliar(r["net"]) for r in F]]
    kf_rows += [["EPS (Rp)"] + [fmt.rp((a["earnings"] or 0) / intake["shares"]) for a in A[-2:]]
                + [fmt.rp(r["eps"]) for r in F]]
    kf_rows += [["Pertumbuhan EPS (%)"] + _eps_g[1:3] + _eps_g[3:]]
    # Multiples: PER/PBV from price, EV/EBITDA where applicable (never for banks).
    _is_bank = (intake.get("model_profile") == "financial_ddm")
    _per_row, _pbv_row, _ev_row = [], [], []
    for a in A[-2:]:
        _eps = (a.get("earnings") or 0) / intake["shares"] if intake.get("shares") else None
        _bvps = (a.get("equity") or 0) / intake["shares"] if intake.get("shares") and a.get("equity") else None
        _per_row.append(fmt.mult(intake["price"] / _eps) if _eps and _eps > 0 else "belum dimodelkan")
        _pbv_row.append(fmt.mult(intake["price"] / _bvps) if _bvps and _bvps > 0 else "belum dimodelkan")
        if _is_bank:
            _ev_row.append("-")
        else:
            _ev = (intake.get("market_cap") or 0)
            _eb = a.get("ebitda") or 0
            _ev_row.append(fmt.mult(_ev / _eb) if _eb and _eb > 0 else "belum dimodelkan")
    for r in F:
        _eps = r.get("eps")
        _per_row.append(fmt.mult(intake["price"] / _eps) if _eps and _eps > 0 else "belum dimodelkan")
        _pbv_row.append("belum dimodelkan")
        _ev_row.append("-" if _is_bank else "belum dimodelkan")
    kf_rows += [["PER (x)"] + _per_row]
    kf_rows += [["PBV (x)"] + _pbv_row]
    kf_rows += [["EV/EBITDA (x)"] + _ev_row]
    if _is_bank:
        # Bank rows only where evidence exists (payout/DPS/equity).
        _roe_row = []
        for a in A[-2:]:
            _roe_row.append(fmt.pct((a.get("earnings") or 0) / a["equity"]) if a.get("equity") else "belum dimodelkan")
        for r in F:
            _roe_row.append(fmt.pct(r["net"] / r["equity"]) if r.get("equity") and r.get("net") else "belum dimodelkan")
        kf_rows += [["ROE (%)"] + _roe_row]
    kf_cols = ["Key Financials"] + [str(a["year"]) for a in A[-2:]] + [r["label"] for r in F]
    E("Key Financials", "tabel", {"cols": kf_cols, "rows": kf_rows})
    exhibit_ids.tag(exh[-1], exhibit_ids.KEY_FINANCIALS)

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
        cup_s = (_t(f"USD {fmt._id(cup['last'])}/ton per {cup['date']} "
                    f"(rata-rata 12 bln USD {fmt._id(cup['avg12'])})",
                    f"USD {fmt._id(cup['last'])}/ton as of {cup['date']} "
                    f"(12-month average USD {fmt._id(cup['avg12'])})") if cup else "-")
        aup_s = (_t(f"USD {fmt._id(aup['last'])}/ton per {aup['date']} "
                    f"(rata-rata 12 bln USD {fmt._id(aup['avg12'])})",
                    f"USD {fmt._id(aup['last'])}/ton as of {aup['date']} "
                    f"(12-month average USD {fmt._id(aup['avg12'])})") if aup else "-")
        p_mine = _t(f"Operasional {mo['year']}: produksi tembaga "
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
                    f"proyek tidak ada di data Sectors sehingga tidak dimodelkan.",
                    f"{mo['year']} operations: copper output of "
                    f"{fmt._id(cu.get('prod') or 0)} kton and gold of "
                    f"{fmt._id(au.get('prod') or 0)} koz from "
                    f"{', '.join(cu.get('blocks') or ['-'])} at grades of "
                    f"{fmt._id(cu.get('cu_grade') or 0, 2)}% Cu and "
                    f"{fmt._id(au.get('au_grade') or 0, 2)} g/t Au. Contained reserves of "
                    f"{fmt._id(cu.get('cu_cont_mt') or 0)} kton Cu and "
                    f"{fmt._id(au.get('au_cont_koz') or 0)} koz Au give a reserve life of about "
                    f"{mo['reserve_life_cu_yr']:.0f} years at the current production rate. "
                    f"Reference prices: copper {cup_s}, gold {aup_s}. Sales volume data and the "
                    f"project capex schedule are not in Sectors data, so they are not modelled.")

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

    # S2.3: operating leverage — ±10% revenue mengalir penuh ke EBITDA
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
                for h in (intake["major_holders"] or [])[:5]] or [["Tidak ada di data Sectors", "-"]]})

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
        _vb = _selected_ddm_detail(va)
        wi = va["wacc_inputs"]
        E("Komponen Cost of Equity", "tabel",
          {"cols": ["Komponen", "Nilai"],
           "rows": [["Jalur CAPM:", ""],
                     ["Risk-free rate IDR (house policy)", fmt.pct(wi["rf"])],
                     ["Beta (kebijakan analis)", fmt.mult(wi["beta"])],
                     ["Equity Risk Premium (kebijakan analis)", fmt.pct(wi["erp"])],
                     ["(=) Cost of Equity dipakai", fmt.pct(wi["re"])],
                     ["Jalur band (pola rentang CoE):", ""],
                     ["CoE mean 5 tahun", "n.a. (tanpa histori CoE di data Sectors)"],
                     ["CoE SD 5 tahun", "n.a. (tanpa histori CoE di data Sectors)"],
                     ["Offset dari mean", "n.a.: dipakai hasil CAPM"]]},
          note="Source: Company, Sektoral Estimates; Rf, beta dan ERP mengikuti house policy, "
               "bukan data Bloomberg/Damodaran. Yield INDOGB bertanggal ditampilkan terpisah.")
        _cg_rows = []
        for _d in (-0.01, -0.005, 0.0, 0.005, 0.01):
            _cg_rows.append(
                [f"CoE {fmt.pct(_re + _d)}" + (" (base)" if _d == 0 else "")] +
                [fmt.rp(fmt.tick(ddm.value_bank(
                    _nets, None, intake.get("dps_hist") or [],
                    intake["shares"], _re + _d, _gg, _roae,
                    _bvps)["tp_gordon"])) +
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
                [fmt.rp(fmt.tick(((_rr - _g) / (_re + _d - _g)) * _bvps))
                 for _rr in (_roae - 0.04, _roae, _roae + 0.04)])
        E("Sensitivitas Inverse CoE (CoE x ROE)", "tabel",
          {"cols": ["CoE / ROE"] + [f"ROE {fmt.pct(_rr)}" for _rr in
                                    (_roae - 0.04, _roae, _roae + 0.04)],
           "rows": _cr_rows},
          note="Source: Sektoral Estimates; sel = P/BV wajar x BVPS; "
               "Fair P/BV = (ROE-g)/(CoE-g)")
        _roe_tr = ("naik" if _roe_h and _roae >= _roe_h[0] else "melandai")
        ddm_summary = _bank_ddm_summary(_vb)
        if ddm_summary:
            p_ddm = _t(f"Driver utama valuasi bank ini adalah lintasan ROE, bukan arus kas: "
                       f"ROAE historis {fmt.pct(_roe_h[0])} {_roe_tr} ke {fmt.pct(_roae)} "
                       f"forward bila laba {F[0]['label']} tercapai. "
                       f"{ddm_summary} {intake.get('dps_basis')}.",
                       f"The main valuation driver for this bank is the ROE path, not cash flow: "
                       f"historical ROAE of {fmt.pct(_roe_h[0])} "
                       f"{'rises' if _roe_tr == 'naik' else 'eases'} to {fmt.pct(_roae)} forward "
                       f"if {F[0]['label']} profit is delivered. "
                       f"{ddm_summary} {prose_lang.source(intake.get('dps_basis'))}.")
    E("Peer", "tabel",
      {"cols": ["Peer", "PER TTM", "PBV"],
       "rows": [[c["symbol"], fmt.mult(c["pe"] or 0), fmt.mult(c["pb"] or 0)]
                for c in intake["peers"][:8]] or [["Tanpa peer di data Sectors", "-", "-"]]})
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
        p_lom = _t(f"Silang cek umur tambang: NAV LoM Rp{fmt.rp(round(lom['rnav_ps']))}/saham "
                   f"(anuitas produksi flat sampai cadangan habis, tanpa terminal, diskon "
                   f"{fmt.pct(va['wacc'])}; {lom['margin_basis']}) dibanding skenario DCF Rp{modeled_value_s}. "
                   f"NAV LoM berbeda karena horizon {(mo.get('reserve_life_cu_yr') or 0):.0f} tahun "
                   f"menangkap nilai cadangan yang dipotong terminal Gordon; skenario DCF "
                   f"dengan kesadaran keterbatasan itu. "
                   f"Diskon RNAV 0% adalah pure judgment assumption tanpa basis "
                   f"pembanding discount historis/sektor di data Sectors.",
                   f"Mine-life cross-check: LoM NAV of Rp{fmt.rp(round(lom['rnav_ps']))}/share "
                   f"(flat production annuity until reserves are exhausted, no terminal value, "
                   f"discount {fmt.pct(va['wacc'])}; {prose_lang.source(lom['margin_basis'])}) "
                   f"against the DCF scenario of Rp{modeled_value_s}. LoM NAV differs because the "
                   f"{(mo.get('reserve_life_cu_yr') or 0):.0f}-year horizon captures reserve value "
                   f"that the Gordon terminal cuts off; the DCF scenario is read with that limit in "
                   f"mind. The 0% RNAV discount is a pure judgment assumption with no historical or "
                   f"sector discount benchmark in Sectors data.")
        _tn, _sh = lom["total_nav_rpbn"], intake["shares"]
        _cb, _db = fc["base"]["cash"] / 1e9, fc["base"]["debt"] / 1e9
        E("Discount Rate per Aset", "tabel",
          {"cols": ["Aset", "Tahap", "Discount rate", "Umur (thn)"],
           "rows": [[s["nama"].split(" (")[0], "produksi", fmt.pct(va["wacc"]),
                     f"{(s['life'] or 0):.0f}"] for s in lom["streams"]]},
          note="Source: Sektoral Estimates; satu tarif (WACC model) untuk "
               "semua aset tahap produksi; tidak ada diferensiasi "
               "matang-vs-development di data Sectors")
        _dp_rows = []
        for _dd in (0.0, 0.10, 0.20, 0.30):
            _dp_rows.append(
                [f"Diskon {fmt.pct(_dd, 0)}"] +
                [fmt.rp(fmt.tick((_tn * _pm + _cb - _db) * 1e9 / _sh * (1 - _dd)))
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
         "paragraf": [_t("Tiap tahun forecast berbeda drivernya: ",
                         "Each forecast year has its own driver: ") +
                      ", ".join(_t(f"{r['label']} tumbuh {fmt.pct(r['revenue']/F[i-1]['revenue']-1) if i else fmt.pct(r['revenue']/rev_last-1)}",
                                   f"{r['label']} revenue grows {fmt.pct(r['revenue']/F[i-1]['revenue']-1) if i else fmt.pct(r['revenue']/rev_last-1)}")
                                for i, r in enumerate(F)) + "."],
         "exhibit": [get("Asumsi forecast"), get("Sensitivitas EBITDA terhadap harga/permintaan")]},
        {"halaman": 4, "judul": "Katalis, risiko, kepemilikan",
         "paragraf": [_t(f"Risiko utama: {r3}. Arah neto insider dan arus asing "
                         "tercatat di tabel kepemilikan sebagai konteks.",
                         f"Key risks: {r3}. Net insider direction and foreign flows are "
                         "recorded in the ownership table as context.")],
         "exhibit": [get("Katalis"), get("Kepemilikan")]},
        {"halaman": 5, "judul": "Skenario nilai",
         "paragraf": [_t(f"Nilai skenario indikatif Rp{modeled_value_s} per saham adalah rerata "
                         f"Gordon Rp{fmt.rp(va['ps_gordon'])} dan exit Rp{fmt.rp(va['ps_exit'])} "
                         f"(WACC {fmt.pct(va['wacc'])}); hasil sensitif terhadap asumsi model.",
                         f"The indicative scenario value of Rp{modeled_value_s} per share is the "
                         f"average of Gordon Rp{fmt.rp(va['ps_gordon'])} and exit "
                         f"Rp{fmt.rp(va['ps_exit'])} (WACC {fmt.pct(va['wacc'])}); the result is "
                         f"sensitive to model assumptions.")] + xtra +
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
         "paragraf": [_t("Kas adalah satu-satunya penyeimbang neraca; D&A, capex, dan tarif "
                         "pajak identik di IS, CF, dan DCF.",
                         "Cash is the only balance-sheet plug; D&A, capex and tax rates are "
                         "identical across the IS, CF and DCF.")],
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

    g32 = va["s3"].get("S3.2_skala")
    mnotes = methodnote.methodology_notes(intake, fc, va, intake.get("mineops"))
    method = (method or "auto").lower()
    if method not in ("auto", "dcf", "ddm", "rnav"):
        raise ValueError(f"method tak dikenal: {method} (auto|dcf|ddm|rnav)")
    if method == "ddm" and intake.get("payout") is None:
        raise ValueError("method ddm ditolak: tanpa payout di data Sectors")
    if method == "rnav" and not intake.get("mineops"):
        raise ValueError("method rnav ditolak: tanpa overlay operasional di data Sectors")
    method_label = {"auto": "DCF (FCFF, Rp)", "dcf": "DCF (FCFF, Rp)",
                    "ddm": "DDM (dividen, Rp)", "rnav": "RNAV LoM (Rp)"}[method]
    if method != "auto":
        mnotes = [_t(f"metode valuasi dipilih analis: {method_label}.",
                     f"Valuation method chosen by the analyst: {method_label}.")] + mnotes
    metodo = ([_t("Angka bersumber dari snapshot data Sectors (salinan lokal yang bisa "
                  "kedaluwarsa; pembacaan tidak memakai kuota API). Tanpa angka karangan "
                  "di luar asumsi berlabel pada tabel Asumsi.",
                  "Figures come from a Sectors data snapshot (a local copy that can go stale; "
                  "reading it uses no API quota). No invented figures beyond the labelled "
                  "assumptions in the Assumptions table.")]
              + ([_t(f"skala valuasi: {g32[1]} (ambang 20-300% dari market cap, "
                     "dicatat sebagai keterbatasan)",
                     f"Valuation scale: {prose_lang.source(g32[1])} (threshold 20-300% of "
                     "market cap, recorded as a limitation)")]
                 if isinstance(g32, tuple) and "gagal" in g32[0] else [])
              + [_t(f"{k}: {v[1]} (dicatat sebagai keterbatasan)",
                    f"{k}: {prose_lang.source(v[1])} (recorded as a limitation)")
                 for k, v in va["s3"].items()
                 if isinstance(v, tuple) and "gagal" in v[0] and k != "S3.2_skala"]
              + mnotes[:2]
              + [methodnote.capex_impact_line(False, _t("volume penjualan dan jadwal investasi",
                                                        "sales volume and investment schedule"))]
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
                                 "public_ownership": ff_str},
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
        "log_gate": {"S1": s1["S1"], "S2": fc["s2"], "S3": {k: (v if isinstance(v, str) else v[0])
                                                          for k, v in va["s3"].items()}},
        "method": "DCF (FCFF, Rp)" if method == "auto" else method_label,
        "method_select": method,
        "fy26": {"Pendapatan": fmt.miliar(f1["revenue"]),
                 "EBITDA": fmt.miliar(f1["ebitda"]),
                 "Laba bersih": fmt.miliar(f1["net"])},
        "holders": holders_display,
        "catatan_metodologi": metodo,
        "exhibits": exh,
    }


_URL = re.compile(r"https?://\S+")


def _client_prose(text):
    """Clean reader-facing prose while preserving figures, links and trace structure.

    Links are copied verbatim: a source URL can contain a spec-like token
    (``S1.2``) and must still resolve."""
    if not isinstance(text, str):
        return text
    parts, last = [], 0
    for match in _URL.finditer(text):
        parts.append(_clean_prose_segment(text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_clean_prose_segment(text[last:]))
    return "".join(parts)


def _clean_prose_segment(text):
    text = re.sub(r"\(news:\s*\d+(?:\s*,\s*news:\s*\d+)*\)",
                  _t("(berita bertanggal)", "(dated news)"), text, flags=re.I)
    text = re.sub(r"\(sectors_annuals\)", _t("(data tahunan Sectors)", "(Sectors annual data)"),
                  text, flags=re.I)
    text = re.sub(r"\(pola BBTN\)", _t("(pola rentang CoE)", "(CoE range pattern)"), text, flags=re.I)
    # A code in its own parentheses is dropped; a bare code is named in words.
    code = r"(?:spesifikasi|spec|framework|Method Gates?\s*\d+|S\d+(?:\.\d+)+|§\s*\d+(?:\.\d+[a-z]?)?)"
    text = re.sub(rf"\s*\((?:\s*{code}\s*[,;]?)+\)", "", text, flags=re.I)
    text = re.sub(r"Method Gates?\s*\d+(?:\s*[-–/]\s*\d+)?", _t("pemeriksaan metode", "method checks"),
                  text, flags=re.I)
    text = re.sub(r"\bS\d+(?:\.\d+)+\b", _t("pemeriksaan model", "model checks"), text)
    text = re.sub(r"§\s*\d+(?:\.\d+[a-z]?)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?",
                  _t("panduan metodologi", "methodology guide"), text, flags=re.I)
    return text


def _client_title(title):
    """Use public value language only for generated report headings."""
    return _client_prose(title)


def _copy_report_paragraph(paragraph):
    if isinstance(paragraph, str):
        return _client_prose(paragraph)
    if not isinstance(paragraph, dict):
        return paragraph
    if "judul" in paragraph:
        paragraph["judul"] = _client_title(paragraph["judul"])
    for key in ("isi", "text"):
        if key in paragraph:
            paragraph[key] = _client_prose(paragraph[key])
    return paragraph


def _copy_table_text(value):
    """Sanitize visible table labels and cells while preserving numeric values."""
    if isinstance(value, str):
        return _client_prose(value)
    if isinstance(value, list):
        return [_copy_table_text(item) for item in value]
    if isinstance(value, dict):
        return {key: (item if str(key).lower() in {"url", "source_url", "href"}
                      else _copy_table_text(item))
                for key, item in value.items()}
    return value


def _copy_exhibit(exhibit):
    if not isinstance(exhibit, dict):
        return exhibit
    exhibit["judul"] = _client_title(exhibit.get("judul"))
    for key in ("catatan_sumber", "catatan"):
        if key in exhibit:
            exhibit[key] = _client_prose(exhibit[key])
    data = exhibit.get("data")
    if isinstance(data, dict):
        for key in ("cols", "rows"):
            if key in data:
                data[key] = _copy_table_text(data[key])
    return exhibit


def _copy_risk(risk):
    if isinstance(risk, str):
        return _client_prose(risk)
    if not isinstance(risk, dict):
        return risk
    for key in ("judul", "isi", "text", "sumber"):
        if key in risk:
            risk[key] = _copy_table_text(risk[key])
    return risk


def client_copy(doc):
    """Copy reader-facing prose, footnotes and cells; preserve traces and source URLs."""
    if not isinstance(doc, dict):
        return doc
    copied = copy.deepcopy(doc)
    cover = copied.get("cover")
    if isinstance(cover, dict):
        cover["headline"] = _client_prose(cover.get("headline"))
        cover["bullets"] = [_client_prose(text) for text in cover.get("bullets") or []]
        cover["paragraf"] = [_copy_report_paragraph(p) for p in cover.get("paragraf") or []]
    methodology = copied.get("catatan_metodologi")
    if isinstance(methodology, list):
        copied["catatan_metodologi"] = [_client_prose(note) for note in methodology]
    elif isinstance(methodology, str):
        copied["catatan_metodologi"] = _client_prose(methodology)
    if isinstance(copied.get("risks"), list):
        copied["risks"] = [_copy_risk(risk) for risk in copied["risks"]]
    for page in copied.get("bagian") or []:
        if not isinstance(page, dict):
            continue
        page["judul"] = _client_title(page.get("judul"))
        page["paragraf"] = [_copy_report_paragraph(p) for p in page.get("paragraf") or []]
        if isinstance(page.get("risks"), list):
            page["risks"] = [_copy_risk(risk) for risk in page["risks"]]
        for card in page.get("cards") or []:
            if isinstance(card, dict):
                for key in ("title", "text", "metric_label"):
                    if key in card:
                        card[key] = _client_prose(card[key])
        for exhibit in page.get("exhibit") or []:
            _copy_exhibit(exhibit)
    for exhibit in copied.get("exhibits") or []:
        _copy_exhibit(exhibit)
    return copied


def build(intake, fc, va, s1, method="auto", illustrative_scenarios=False):
    """Build the report structure; the pipeline applies client copy after enrichment."""
    return _build_report(intake, fc, va, s1, method=method,
                         illustrative_scenarios=illustrative_scenarios)


def _headline(intake, fc):
    F = fc["rows"]
    g = (F[-1]["revenue"] / F[0]["revenue"]) - 1
    up = F[-1]["margin"] >= F[0]["margin"]
    if g > 0.15 and up:
        return _t("Volume Tumbuh, Leverage Angkat Margin", "Volume Growth, Leverage Lifts Margin")
    if g > 0.15:
        return _t("Pendapatan Tumbuh, Margin Dijaga Ketat", "Revenue Grows, Margin Held Tight")
    if up:
        return _t("Efisiensi Angkat Margin di Tengah Perlambatan",
                  "Efficiency Lifts Margin as Growth Slows")
    return _t("Arus Kas Stabil Topang Valuasi", "Stable Cash Flow Supports Valuation")


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
