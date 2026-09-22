"""TAHAP 1: INTAKE & VALIDASI DATA (GATE 1). Cache-only, never-expired."""
import time
from . import cache
from . import mineops


def _num(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def load(ticker):
    """Build typed inputs from cache. Returns (intake, g1_log)."""
    t = ticker.upper()
    g1 = {}
    notes = []

    rep_rows = cache.payloads(f"/company/report/{t}/")
    if not rep_rows:
        raise ValueError(f"no verified assumptions: cache has no /company/report/{t}/")
    rep = rep_rows[0][1]
    ov = rep.get("overview", {}) or {}
    val = rep.get("valuation", {}) or {}
    fin = rep.get("financials", {}) or {}
    div = rep.get("dividend", {}) or {}
    own = rep.get("ownership", {}) or {}

    price = _num(ov.get("last_close_price") or val.get("last_close_price"))
    price_date = ov.get("latest_close_date") or val.get("latest_close_date")
    if price is None:
        raise ValueError(f"no last_close_price in cache for {t}")

    hist = fin.get("historical_financials") or []
    annuals = []
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
        annuals.append({
            "year": h.get("year"), "revenue": rev, "ebitda": ebitda,
            "ebit": ebit, "earnings": earn, "tax": tax, "interest": interest,
            "da": (ebitda - ebit) if ebitda is not None and ebit is not None else None,
            "capex_out": capex_out,
            "fcf": _num(h.get("free_cash_flow")),
            "ocf": _num(h.get("operating_cash_flow")),
            "total_debt": _num(h.get("total_debt")),
            "cash": _num(h.get("cash_and_equivalents")),
            "equity": _num(h.get("total_equity")),
            "assets": _num(h.get("total_assets")),
            "liab": _num(h.get("total_liabilities")),
            "shares": _num(h.get("outstanding_shares")),
        })
    if len(annuals) < 3:
        raise ValueError(f"only {len(annuals)} usable annuals for {t}, need >= 3")

    base = annuals[-1]
    shares = base["shares"]
    if not shares:
        raise ValueError(f"no outstanding_shares in cache for {t}")
    market_cap = price * shares

    # G1: scale sanity — revenue per share vs price must be same order of magnitude
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

    # G1: interim freshness — structured interim not required by spec; label only
    g1["G1_periode"] = "dilabeli"
    notes.append(f"basis tahunan terakhir {base['year']} dipakai sebagai tahun dasar; "
                 "rilis interim hanya konteks narasi.")

    # G1: non-recurring — not detectable from cache granularity
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

    peers, peer_median_pe, peer_median_pb = _peers(rep, t)
    payout = _num(div.get("payout_ratio"))
    if payout is None or not (0 <= payout <= 1.5):
        payout, payout_basis = 0.25, "asumsi analis 25% (tanpa payout historis di cache)"
    else:
        payout_basis = "payout ratio historis di cache"

    intake = {
        "ticker": t, "name": rep.get("company_name", t),
        "currency": "Rp", "fx": 1.0,
        "price": price, "price_date": price_date,
        "shares": shares, "market_cap": market_cap,
        "annuals": annuals, "base_year": base["year"],
        "payout": payout, "payout_basis": payout_basis,
        "industry": ov.get("industry"), "sub_sector": ov.get("sub_sector"),
        "major_holders": (own.get("major_shareholders") or [])[:5],
        "free_float": None,
        "daily": drows[-5:] if isinstance(drows, list) else [],
        "news": (news.get("results") or [])[:12] if isinstance(news, dict) else [],
        "filings": (filings.get("results") or []) if isinstance(filings, dict) else [],
        "corp_actions": corp_list,
        "foreign_flow": (flow.get("data") or []) if isinstance(flow, dict) else [],
        "peers": peers, "peer_median_pe": peer_median_pe,
        "peer_median_pb": peer_median_pb,
        "forward_pe_cache": _num(val.get("forward_pe")),
        "mineops": mineops.load(t),
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
