"""TAHAP 1: intake data pasar dari cache dan fakta emiten dari rilis resmi lokal."""
import time
from datetime import date
from . import cache
from . import mineops
from . import model_profiles
from . import issuer_evidence
from . import news as news_context
from . import research_context


def _num(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def load(ticker, as_of=None):
    """Build typed inputs from cache. Returns (intake, g1_log)."""
    t = ticker.upper()
    g1 = {}
    notes = []

    rep_rows = cache.payloads(f"/company/report/{t}/")
    if not rep_rows:
        raise ValueError(f"no verified assumptions: cache has no /company/report/{t}/")
    # Endpoint rows can include newer partial responses. Select the newest
    # report with usable model inputs, matching the agent's cache view.
    rep = cache.company_report(t)
    ov = rep.get("overview", {}) or {}
    val = rep.get("valuation", {}) or {}
    fin = rep.get("financials", {}) or {}
    div = rep.get("dividend", {}) or {}
    own = rep.get("ownership", {}) or {}
    profile, profile_basis = model_profiles.resolve({
        "model_profile": rep.get("model_profile") or ov.get("model_profile"),
        "industry": ov.get("industry"),
        "sub_sector": ov.get("sub_sector"),
        "sector": ov.get("sector"),
    })

    price = _num(ov.get("last_close_price") or val.get("last_close_price"))
    price_date = ov.get("latest_close_date") or val.get("latest_close_date")
    if price is None:
        raise ValueError(f"no last_close_price in cache for {t}")
    report_date = as_of or price_date
    if date.fromisoformat(str(report_date)[:10]) < date.fromisoformat(str(price_date)[:10]):
        raise ValueError("report date cannot precede the cached market price date")
    official_evidence = issuer_evidence.load(t, report_date) if report_date else None

    hist = fin.get("historical_financials") or []
    annuals = []
    da_invalid_years = []
    for h in sorted(hist, key=lambda r: r.get("year", 0)):
        rev = _num(h.get("revenue"))
        if rev is None or rev <= 0:
            continue
        ebitda = _num(h.get("ebitda"))
        ebit = _num(h.get("ebit"))
        earn = _num(h.get("earnings"))
        tax = _num(h.get("tax"), 0.0) or 0.0
        interest = _num(h.get("interest_expense_non_operating"), 0.0) or 0.0
        capex_raw = _num(h.get("capital_expenditure"))
        capex_out = -capex_raw if capex_raw is not None and capex_raw < 0 else (
            capex_raw if capex_raw else None)

        # Sourced depreciation metric if present in cache row
        sourced_da = _num(h.get("depreciation"))
        if sourced_da is None:
            sourced_da = _num(h.get("depreciation_and_amortization"))
        if sourced_da is None:
            sourced_da = _num(h.get("amortization"))
        if sourced_da is None:
            sourced_da = _num(h.get("da"))

        if sourced_da is not None and sourced_da >= 0:
            da = sourced_da
        elif ebitda is not None and ebit is not None:
            diff = ebitda - ebit
            if diff >= 0 and not (ebitda == 0 and ebit > 0):
                da = diff
            else:
                # ebitda == 0 with positive ebit or ebitda < ebit yields invalid D&A.
                # Never hide this with max(0, ...) or assume a value; preserve None.
                da = None
                da_invalid_years.append(h.get("year"))
        else:
            da = None

        # Cash: check cash_and_equivalents, total_cash_and_due_from_banks, cash_only
        cash_val = _num(h.get("cash_and_equivalents"))
        if cash_val is None:
            cash_val = _num(h.get("total_cash_and_due_from_banks"))
        if cash_val is None:
            cash_val = _num(h.get("cash_only"))

        annuals.append({
            "year": h.get("year"), "revenue": rev, "ebitda": ebitda,
            "ebit": ebit, "earnings": earn, "tax": tax, "interest": interest,
            "da": da,
            "capex_out": capex_out,
            "fcf": _num(h.get("free_cash_flow")),
            "ocf": _num(h.get("operating_cash_flow")),
            "total_debt": _num(h.get("total_debt")),
            "cash": cash_val,
            "equity": _num(h.get("total_equity")),
            "assets": _num(h.get("total_assets")),
            "liab": _num(h.get("total_liabilities")),
            "shares": _num(h.get("outstanding_shares")),
        })
    if len(annuals) < 3:
        raise ValueError(f"only {len(annuals)} usable annuals for {t}, need >= 3")

    base = annuals[-1]
    share_row = next((row for row in reversed(annuals) if row["shares"]), None)
    shares = share_row["shares"] if share_row else None
    if not shares:
        raise ValueError(f"no outstanding_shares in cache for {t}")
    if share_row["year"] != base["year"]:
        notes.append(f"jumlah saham memakai data terakhir yang tersedia ({share_row['year']}); "
                     f"data saham tahun dasar {base['year']} tidak ada di cache.")
    market_cap = price * shares

    if da_invalid_years:
        years_str = ", ".join(str(y) for y in sorted(set(da_invalid_years)))
        notes.append(
            f"D&A tahun {years_str} tidak valid di cache "
            f"(EBITDA <= EBIT atau EBITDA 0 dengan EBIT positif); status D&A dan arus kas tidak lengkap."
        )

    if base.get("cash") is None:
        notes.append(f"posisi kas tahun dasar {base['year']} tidak tersedia di cache; kas berstatus n.a.")

    # G1: scale sanity - revenue per share vs price must be same order of magnitude
    rps = base["revenue"] / shares
    g1["G1_skala"] = "lolos" if 0.01 <= rps / price <= 100 else "gagal"
    if g1["G1_skala"] == "gagal":
        notes.append("skala satuan tidak konsisten antara laporan dan harga; lanjut dengan label.")

    # G1: cash reconciliation where CF legs exist
    recon_ok, recon_n = True, 0
    for a in annuals:
        if a["ocf"] is not None and a["fcf"] is not None and a["capex_out"] is not None:
            recon_n += 1
            if abs((a["ocf"] - a["capex_out"]) - a["fcf"]) > 0.01 * max(abs(a["fcf"]), 1):
                recon_ok = False
    g1["G1_kas"] = "lolos" if (recon_n == 0 or recon_ok) else "gagal-dilabeli"
    if recon_n == 0:
        notes.append("kaki arus kas tidak lengkap di cache; rekonsiliasi kas tidak diuji.")

    # G1: interim freshness - structured interim not required by spec; label only
    g1["G1_periode"] = "dilabeli"
    notes.append(f"basis tahunan terakhir {base['year']} dipakai sebagai tahun dasar; "
                 "rilis interim hanya konteks narasi.")

    # G1: non-recurring - not detectable from cache granularity
    g1["G1_nonrecurring"] = "dilabeli"
    notes.append("tidak ada item non-recurring teridentifikasi dari granularitas cache; "
                 "laba dilaporkan = laba inti.")

    # Supporting context (narrative only)
    daily = cache.first(f"/daily/{t}/") or {}
    drows = (daily.get("data") or []) if isinstance(daily, dict) else []
    news = cache.first("/news/") or {}
    filings = cache.first("/filings/") or {}
    corp = cache.first(f"/company/corporate-actions/{t}/") or {}
    ca = corp.get("corporate_actions") if isinstance(corp, dict) else None
    corp_list = ca if isinstance(ca, list) else ([ca] if isinstance(ca, dict) else [])
    flow = cache.first(f"/foreign-flow/{t}/") or {}
    relevant_news = news_context.relevant_rows(t, news, price_date)
    news_analysis, news_analysis_status = news_context.load_analysis(
        t, relevant_news, price_date)
    research_analysis, research_analysis_status = research_context.load_analysis(
        t, price_date)

    quarterly_payload = cache.first(f"/financials/quarterly/{t}/") or {}
    quarterly_rows = quarterly_payload.get("data") or [] if isinstance(
        quarterly_payload, dict) else []
    quarterly_rows = sorted(
        (row for row in quarterly_rows if isinstance(row, dict) and row.get("date")),
        key=lambda row: row["date"],
    )
    latest_quarter = quarterly_rows[-1] if quarterly_rows else None

    peers, peer_median_pe, peer_median_pb = _peers(rep, t)
    payout = _num(div.get("payout_ratio"))
    if payout is None or not (0 <= payout <= 1.5):
        payout, payout_basis = 0.25, "asumsi analis 25% (tanpa payout historis di cache)"
    else:
        payout_basis = "payout ratio historis di cache"
    dps_hist, dps_years = [], []
    hist_div = div.get("historical_dividends") or {}
    if isinstance(hist_div, dict):
        for y in sorted(hist_div, key=lambda k: str(k)):
            tot = _num((hist_div[y] or {}).get("total_dividend"))
            if tot is not None:
                dps_hist.append(tot)
                dps_years.append(str(y))
    dps_basis = (f"DPS historis {dps_years[0]}-{dps_years[-1]} di cache"
                 if dps_hist else "tanpa DPS historis di cache")

    intake = {
        "ticker": t, "name": rep.get("company_name", t),
        "model_profile": profile, "model_profile_basis": profile_basis,
        "currency": "Rp", "fx": 1.0,
        "price": price, "price_date": price_date, "as_of": report_date,
        "shares": shares, "market_cap": market_cap,
        "annuals": annuals, "base_year": base["year"],
        "payout": payout, "payout_basis": payout_basis,
        "dps_hist": dps_hist, "dps_basis": dps_basis,
        "industry": ov.get("industry"), "sub_sector": ov.get("sub_sector"),
        "major_holders": (own.get("major_shareholders") or [])[:5],
        "free_float": None,
        "daily": drows[-5:] if isinstance(drows, list) else [],
        "news": relevant_news,
        "news_analysis": news_analysis,
        "news_analysis_status": news_analysis_status,
        "research_analysis": research_analysis,
        "research_analysis_status": research_analysis_status,
        "filings": (filings.get("results") or []) if isinstance(filings, dict) else [],
        "corp_actions": corp_list,
        "foreign_flow": (flow.get("data") or []) if isinstance(flow, dict) else [],
        "peers": peers, "peer_median_pe": peer_median_pe,
        "peer_median_pb": peer_median_pb,
        "forward_pe_cache": _num(val.get("forward_pe")),
        "mineops": mineops.load(t),
        "quarterly_actuals": quarterly_rows,
        "latest_quarterly_actual": latest_quarter,
        "official_evidence": official_evidence,
        "latest_official_actual": ((official_evidence or {}).get("latest_actual")),
        # Report inputs intentionally come only from sectors_cache. These
        # release-gate inputs remain absent until the cache itself contains
        # enough date/source/coverage metadata to support them.
        "latest_interim_actuals": (
            {"period": official_evidence["latest_actual"]["period"],
             "status": "reported actual", "source_type": "official_issuer",
             "source": official_evidence["latest_actual"]["source_url"],
             "source_date": official_evidence["latest_actual"]["published_at"],
             "page": official_evidence["latest_actual"]["page"],
             "is_latest": True,
             "metrics": {
                 metric: {"value": official_evidence["latest_actual"]["metrics"][key],
                          "unit": official_evidence["latest_actual"]["unit"]}
                 for metric, key in (("revenue", "revenue"), ("ebitda", "ebitda"),
                                     ("net_profit", "net_profit"),
                                     ("capex", "capital_expenditure"))
                 if key in official_evidence["latest_actual"]["metrics"]}}
            if official_evidence and profile == "finite_life_mining" else None),
        "operating_bridge": None,
        "sotp_assets": None,
        "sotp_bridge": None,
    }
    return intake, {"G1": g1, "catatan": notes, "fetched_at": time.time()}


def _peers(rep, t):
    out = []
    try:
        groups = rep.get("peers") or []
        for g in groups:
            data = g.get("peers_data") or {}
            for c in data.get("companies") or []:
                if (c.get("group") or []) == ["self"]:
                    continue
                if c.get("symbol") and c.get("pe_ttm"):
                    out.append({"symbol": c.get("symbol"),
                                "name": c.get("company_name", ""),
                                "pe": _num(c.get("pe_ttm")),
                                "pb": _num(c.get("pb_mrq")),
                                "mcap": _num(c.get("market_cap"))})
    except Exception:
        pass
    pes = sorted(p for p in (c["pe"] for c in out) if p and p > 0)
    pbs = sorted(p for p in (c["pb"] for c in out) if p and p > 0)
    med = lambda s: s[len(s) // 2] if s else None
    return out[:12], med(pes), med(pbs)
