"""TAHAP 1: intake data pasar dari cache dan fakta emiten dari rilis resmi lokal."""
import re
import sqlite3
import time
from datetime import date
from . import cache
from . import fx
from . import mineops
from . import market_quote
from . import model_profiles
from . import issuer_evidence
from . import analyst_scenario
from . import news as news_context
from . import news_fetch
from . import peer_fundamentals
from . import research_context


def _num(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _sotp_bridge_inputs(evidence, as_of):
    """Translate source-backed corporate bridge items, leaving gaps explicit."""
    if not isinstance(evidence, dict):
        return None
    balance = evidence.get("balance_sheet") or {}
    debt_evidence = evidence.get("debt_and_contract_evidence") or {}
    debt = debt_evidence.get("debt_usd_thousand") or {}
    other_financial = debt_evidence.get("other_financial_liabilities_usd_thousand") or {}
    fx_quote = evidence.get("valuation_fx_reference") or {}
    currency = str(evidence.get("reporting_currency") or "").upper()
    if currency == "USD":
        try:
            rate = float(fx_quote["rate"])
            fx_date = date.fromisoformat(str(fx_quote["date"]))
            report_date = date.fromisoformat(str(as_of)[:10])
        except (KeyError, TypeError, ValueError):
            return None
        if rate <= 0 or fx_date > report_date or not fx_quote.get("source_url"):
            return None
        fx = rate
        fx_source = (f"; {fx_quote.get('source_title')} {fx_quote['date']}: "
                     f"{fx_quote['source_url']}")
        fx_source_date = fx_quote["date"]
    elif currency == "IDR":
        fx, fx_source, fx_source_date = 1.0, "", None
    else:
        return None

    statement_title = debt_evidence.get("source_title") or balance.get("source_title")
    statement_url = debt_evidence.get("source_url") or balance.get("source_url")
    statement_date = (evidence.get("latest_actual") or {}).get("published_at")
    period_end = debt_evidence.get("period_end") or balance.get("period_end")
    if not statement_title or not statement_url or not statement_date or not period_end:
        return None

    cash_usd_thousand = debt_evidence.get("cash_and_equivalents_usd_thousand")
    if cash_usd_thousand is None:
        cash_usd_thousand = ((evidence.get("latest_actual") or {})
                             .get("financial_statements_usd_thousand", {})
                             .get("cash_flow", {}).get("closing_cash"))
    if cash_usd_thousand is None and balance.get("cash") is not None:
        cash_usd_thousand = balance["cash"] / 1000
    bank_debt_usd_thousand = None
    if debt.get("short_term_bank_loans") is not None and debt.get("long_term_loans_net") is not None:
        bank_debt_usd_thousand = (debt["short_term_bank_loans"] + debt["long_term_loans_net"])
    other_financial_usd_thousand = other_financial.get("total")
    debt_usd_thousand = (
        bank_debt_usd_thousand + other_financial_usd_thousand
        if bank_debt_usd_thousand is not None and other_financial_usd_thousand is not None
        else None)
    minority_usd_thousand = debt_evidence.get("non_controlling_interest_usd_thousand")
    if minority_usd_thousand is None:
        minority = balance.get("non_controlling_interest")
        minority_usd_thousand = minority / 1000 if minority is not None else None
    shares = debt_evidence.get("shares_outstanding") or balance.get("shares_outstanding")

    def translated(value):
        if not isinstance(value, (int, float)):
            return None
        return value * 1000 * fx if currency == "USD" else value

    statement_ref = f"{statement_title}: {statement_url}"
    translated_source = statement_ref + fx_source
    converted_date = fx_source_date or statement_date

    def amount(value, page, basis):
        return {"value": translated(value), "source": translated_source,
                "source_date": converted_date, "page": page, "unit": "raw IDR",
                "financial_source_date": statement_date,
                "balance_period_end": period_end,
                "fx_date": fx_source_date, "fx_rate": fx if currency == "USD" else None,
                "basis": basis}

    shares_row = {"value": shares, "source": statement_ref,
                  "source_date": statement_date,
                  "page": debt_evidence.get("shares_source_page"),
                  "unit": "shares", "balance_period_end": period_end,
                  "basis": "reported shares outstanding, excluding treasury shares"}
    contract_advance = ((evidence.get("customer_delivery_commitment") or {})
                        .get("prepayment_advance_usd_thousand", {})
                        .get("balance_2026_06_30"))
    return {
        "cash_idr": amount(cash_usd_thousand, debt_evidence.get("cash_source_page"),
                            "Cash and cash equivalents; translated at dated FX."),
        "debt_idr": amount(
            debt_usd_thousand,
            "2, 89, 98",
            "Bank loans net of fees plus present-value lease and finance liabilities. "
            "Customer prepayment is excluded pending operating-delivery reconciliation."),
        "minority_interest_idr": amount(
            minority_usd_thousand, debt_evidence.get("minority_source_page"),
            "Reported non-controlling interest; translated at dated FX."),
        "corporate_overhead_idr": None,
        "shares": shares_row,
        "discount_pct": None,
        "customer_advance_excluded_usd_thousand": contract_advance,
    }


def _driver_evidence_inputs(official_evidence, payout, payout_basis,
                             dps_hist, report_date, profile):
    """Synthesize release-gate driver evidence from the official actual.

    Each series carries an HTTPS source, source_date <= as_of, page, unit,
    and explanatory note. A missing metric yields a missing series (explicit
    blocker) rather than a zero assumption. An analyst payout assumption
    without an HTTPS source stays a blocker: media/assumptions motivate
    bounds but do not become issuer guidance.
    """
    if not isinstance(official_evidence, dict):
        return None
    actual = official_evidence.get("latest_actual") or {}
    source_url = actual.get("source_url")
    published_at = actual.get("published_at")
    if not source_url or not published_at:
        return None
    title = actual.get("source_title") or "official issuer release"
    source_ref = f"{title}: {source_url}"
    source_date = str(published_at)[:10]
    page = actual.get("page")
    unit = actual.get("unit")
    metrics = actual.get("metrics") or {}

    def _row(note):
        return {"source": source_ref, "source_date": source_date,
                "page": page, "unit": unit or "as reported",
                "note": note,
                # Base-period level only: proves the actual exists, not a
                # forward driver chain. forecast.build will not count it as
                # production coverage.
                "origin": "official_actual_base"}

    if profile == "financial_ddm":
        evidence = {}
        if isinstance(metrics.get("revenue"), (int, float)):
            evidence["revenue"] = _row(
                "Sourced operating income trajectory from official interim release; "
                "base for earnings/dividend bridge.")
        if isinstance(metrics.get("net_profit"), (int, float)):
            evidence["net_profit"] = _row(
                "Sourced net profit from official interim release; "
                "anchor for retained earnings and payout.")
        # Equity/book: prefer official balance sheet, fall back to latest actual context.
        balance = official_evidence.get("balance_sheet") or {}
        equity = None
        for key in ("total_equity", "equity_attributable", "equity"):
            if isinstance(balance.get(key), (int, float)):
                equity = balance[key]
                break
        if equity is not None:
            evidence["equity"] = _row(
                f"Sourced book equity {equity:,.0f} from official balance sheet; "
                "base for BVPS/ROE/capital bridge.")
        # Payout provenance follows where the number came from: the 25%
        # analyst default is never sourced; a Sectors payout ratio (with or
        # without DPS history) is cache-sourced, not an interim-release fact.
        if isinstance(payout, (int, float)):
            if str(payout_basis or "").startswith("asumsi analis"):
                evidence["payout"] = {
                    "source": f"asumsi analis {payout*100:.0f}% (tanpa payout historis di data Sectors)",
                    "source_date": source_date, "page": page, "unit": "fraction",
                    "note": f"Unverified payout assumption ({payout_basis}); "
                            "official payout evidence missing."}
            else:
                has_dps = isinstance(dps_hist, list) and len(dps_hist) > 0
                evidence["payout"] = {
                    "source": "sectors_cache dividend payout_ratio"
                              + (" + historical_dividends" if has_dps else ""),
                    "source_date": str(report_date or source_date)[:10],
                    "page": None, "unit": "fraction",
                    "note": f"Payout {payout*100:.1f}% ({payout_basis})"
                            + ("; DPS history supports DDM." if has_dps else "."),
                    "origin": "official_actual_base"}
        # Alias for release compatibility: profit == net_profit.
        if "net_profit" in evidence:
            evidence["profit"] = evidence["net_profit"]
        return evidence or None

    # going_concern_fcff (+ default): revenue/ebitda/net_profit/capex.
    evidence = {}
    labels = {
        "revenue": "Sourced revenue trajectory from official interim release.",
        "ebitda": "Sourced EBITDA from official interim release; anchors margin bridge.",
        "net_profit": "Sourced net profit from official interim release; anchors earnings.",
        "capex": "Sourced capex from official interim release; anchors investment bridge.",
    }
    metric_keys = {"revenue": "revenue", "ebitda": "ebitda",
                   "net_profit": "net_profit", "capex": "capital_expenditure"}
    for series, key in metric_keys.items():
        if isinstance(metrics.get(key), (int, float)):
            evidence[series] = _row(labels[series])
    return evidence or None


def _cache_close_provenance(ticker, price, price_date):
    """Provenance of the Sectors overview close, cross-checked with the cached
    daily series: the same date must carry the same close (0,5% tolerance)."""
    verified = False
    try:
        for _, payload in cache.payloads(f"/daily/{ticker}/"):
            for row in (payload or {}).get("data") or []:
                if (isinstance(row, dict) and str(row.get("date"))[:10] == str(price_date)[:10]
                        and isinstance(row.get("close"), (int, float)) and price
                        and abs(row["close"] / price - 1) <= 0.005):
                    verified = True
    except (OSError, ValueError, FileNotFoundError):
        verified = False
    return {"source": f"sectors_cache /company/report/{ticker}/ overview; /daily/{ticker}/",
            "date": str(price_date)[:10] if price_date else None,
            "kind": "sectors_cache", "verified": verified}


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
    price_provenance = _cache_close_provenance(t, price, price_date)
    quote = market_quote.load(t, report_date, price_date)
    if quote:
        price, price_date = float(quote["price"]), quote["date"]
        price_provenance = {"source": quote.get("source_url"), "date": price_date,
                            "kind": "quote_pack", "verified": True}
        notes.append(f"harga memakai {quote['source_title']} ({price_date}); "
                     f"{quote['source_url']}.")
    official_evidence = issuer_evidence.load(t, report_date) if report_date else None
    analyst_scenario_inputs = analyst_scenario.load(t, report_date) if report_date else None
    fx_spot = fx.load_cached_rate()
    if fx_spot:
        fx_age = (date.fromisoformat(str(report_date)[:10]) -
                  date.fromisoformat(fx_spot["date"])).days
        if not 0 <= fx_age <= 7:
            fx_spot = None

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
            # Working-capital lines for the scenario FCFF (ΔNWC); None when absent.
            "current_assets": _num(h.get("current_assets")),
            "current_liabilities": _num(h.get("current_liabilities")),
            "short_term_debt": _num(h.get("short_term_debt")),
            "ebt": _num(h.get("earnings_before_tax")),
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
                     f"data saham tahun dasar {base['year']} tidak ada di data Sectors.")
    official_balance = (official_evidence or {}).get("balance_sheet") or {}
    official_shares = official_balance.get("shares_outstanding")
    if isinstance(official_shares, (int, float)) and official_shares > 0:
        shares = official_shares
        notes.append(f"jumlah saham beredar memakai "
                     f"{official_balance.get('shares_source') or 'laporan interim resmi'}; "
                     "saham treasuri tidak masuk denominator.")
    market_cap = price * shares

    if da_invalid_years:
        years_str = ", ".join(str(y) for y in sorted(set(da_invalid_years)))
        notes.append(
            f"D&A tahun {years_str} tidak valid di data Sectors "
            f"(EBITDA <= EBIT atau EBITDA 0 dengan EBIT positif); status D&A dan arus kas tidak lengkap."
        )

    if base.get("cash") is None:
        notes.append(f"posisi kas tahun dasar {base['year']} tidak tersedia di data Sectors; kas berstatus n.a.")

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
        notes.append("kaki arus kas tidak lengkap di data Sectors; rekonsiliasi kas tidak diuji.")

    # G1: interim freshness - structured interim not required by spec; label only
    g1["G1_periode"] = "dilabeli"
    notes.append(f"basis tahunan terakhir {base['year']} dipakai sebagai tahun dasar; "
                 "rilis interim hanya konteks narasi.")

    # G1: non-recurring - not detectable from cache granularity
    g1["G1_nonrecurring"] = "dilabeli"
    notes.append("tidak ada item non-recurring teridentifikasi dari granularitas data Sectors; "
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
    relevant_news = news_context.relevant_rows(t, news, report_date)
    news_analysis, news_analysis_status = news_context.load_analysis(
        t, relevant_news, report_date)
    # Auto deep-dive: fetch the full text behind every cached news link.
    # Failures stay as unavailable_* records; the snippet remains the source.
    try:
        news_full = news_fetch.enrich_all(relevant_news)
    except Exception:
        news_full = [news_fetch.enrich_one(row) for row in relevant_news]
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
    peer_basis = None
    if not peers:
        borrowed, lender = _borrowed_peer_report(t)
        if borrowed:
            peers, peer_median_pe, peer_median_pb = _peers(borrowed, t)
            peer_basis = f"tabel peer Sectors milik {lender} yang memuat {t}"
    payout = _num(div.get("payout_ratio"))
    if payout is None or not (0 <= payout <= 1.5):
        payout, payout_basis = 0.25, "asumsi analis 25% (tanpa payout historis di data Sectors)"
    else:
        payout_basis = "payout ratio historis di data Sectors"
    dps_hist, dps_years = [], []
    hist_div = div.get("historical_dividends") or {}
    if isinstance(hist_div, dict):
        for y in sorted(hist_div, key=lambda k: str(k)):
            tot = _num((hist_div[y] or {}).get("total_dividend"))
            if tot is not None:
                dps_hist.append(tot)
                dps_years.append(str(y))
    dps_basis = (f"DPS historis {dps_years[0]}-{dps_years[-1]} di data Sectors"
                 if dps_hist else "tanpa DPS historis di data Sectors")

    intake = {
        "ticker": t, "name": rep.get("company_name", t),
        "model_profile": profile, "model_profile_basis": profile_basis,
        "currency": "Rp", "fx": 1.0,
        "fx_spot": fx_spot,
        "market_quote": quote,
        "price": price, "price_date": price_date, "as_of": report_date,
        "price_provenance": price_provenance,
        "shares": shares, "market_cap": market_cap,
        "annuals": annuals, "base_year": base["year"],
        "payout": payout, "payout_basis": payout_basis,
        "dps_hist": dps_hist, "dps_basis": dps_basis,
        "industry": ov.get("industry"), "sub_sector": ov.get("sub_sector"),
        "major_holders": (own.get("major_shareholders") or [])[:5],
        "free_float": None,
        "daily": drows[-5:] if isinstance(drows, list) else [],
        "news": relevant_news,
        "news_full": news_full,
        "news_analysis": news_analysis,
        "news_analysis_status": news_analysis_status,
        "research_analysis": research_analysis,
        "research_analysis_status": research_analysis_status,
        "filings": (filings.get("results") or []) if isinstance(filings, dict) else [],
        "corp_actions": corp_list,
        "foreign_flow": (flow.get("data") or []) if isinstance(flow, dict) else [],
        "peers": peers, "peer_median_pe": peer_median_pe, "peer_basis": peer_basis,
        # Own-history EV/EBITDA (Sectors valuation.historical_valuation) for the
        # Gate 5 implied-exit check; the Sectors peer tables carry no EV.
        "historical_ev_ebitda": [
            {"year": h.get("year"), "value": _num(h.get("enterprise_to_ebitda"))}
            for h in (val.get("historical_valuation") or [])
            if isinstance(h, dict) and _num(h.get("enterprise_to_ebitda")) is not None
            and 0 < _num(h.get("enterprise_to_ebitda")) <= 100][-5:],
        "peer_median_pb": peer_median_pb,
        "forward_pe_cache": _num(val.get("forward_pe")),
        "mineops": mineops.load(t),
        "quarterly_actuals": quarterly_rows,
        "latest_quarterly_actual": latest_quarter,
        "official_evidence": official_evidence,
        "analyst_scenario": analyst_scenario_inputs,
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
        "sotp_bridge": (_sotp_bridge_inputs(official_evidence, report_date)
                        if profile == "finite_life_mining" else None),
        "driver_evidence": _driver_evidence_inputs(
            official_evidence, payout, payout_basis, dps_hist, report_date, profile),
    }
    return intake, {"G1": g1, "catatan": notes, "fetched_at": time.time()}


def _borrowed_peer_report(t):
    """Sectors has no peer table for ``t``: use another cached issuer's Sectors
    table that lists ``t`` (the analyst agent's rule), with ``t`` as self."""
    for endpoint in sorted(cache.endpoints()):
        match = re.fullmatch(r"/company/report/([A-Z0-9.-]{1,10})/", endpoint)
        other = match.group(1) if match else None
        if not other or other == t:
            continue
        report = cache.company_report(other) or {}
        companies = [c for g in report.get("peers") or []
                     for c in (g.get("peers_data") or {}).get("companies") or []
                     if isinstance(c, dict)]
        if any(str(c.get("symbol") or "").replace(".JK", "") == t for c in companies):
            relabelled = [{**c, "group": ["self"] if str(c.get("symbol") or "").replace(
                ".JK", "") == t else ["peer"]} for c in companies]
            return {"peers": [{"peers_data": {"companies": relabelled}}]}, other
    return None, None


def _peer_ev(symbol, market_cap):
    """Peer EV: the Sectors peer-table market cap plus total debt less cash,
    with EBITDA from the same latest FY. Debt, cash and EBITDA come from the
    peer's own cached Sectors /company/report/<peer>/; when that report is
    not cached, from a stored Yahoo Finance snapshot (app.peer_fundamentals),
    and the row says so in ``ev_source_kind``. A missing part leaves the
    multiple None with a named status; no older year fills the gap."""
    ticker = str(symbol or "").replace(".JK", "").strip().upper()
    try:
        report = cache.company_report(ticker) if ticker else None
    except (OSError, ValueError, sqlite3.Error):
        # One unreadable peer report must not drop the peer's PER/PBV row.
        return {"ev_status": "report_unreadable"}
    if not isinstance(report, dict):
        return _peer_ev_yahoo(ticker, market_cap)
    row = max((r for r in (report.get("financials") or {}).get("historical_financials") or []
               if isinstance(r, dict) and isinstance(r.get("year"), (int, float))),
              key=lambda r: r["year"], default=None)
    if row is None or market_cap is None:
        return {"ev_status": "balance_incomplete" if row is None else "market_cap_missing"}
    debt, ebitda = _num(row.get("total_debt")), _num(row.get("ebitda"))
    cash = _num(row.get("cash_and_equivalents"))
    if cash is None:
        cash = _num(row.get("cash_only"))
    year = int(row["year"])
    if None in (debt, cash, ebitda):
        return {"ev_status": "balance_incomplete", "ev_year": year}
    ev = market_cap + debt - cash
    meaningful = ev > 0 and ebitda > 0
    return {"ev": ev, "ev_year": year, "ev_status": "ok" if meaningful else "not_meaningful",
            "ev_ebitda": ev / ebitda if meaningful else None, "ev_source_kind": "sectors",
            "ev_source": (f"Sectors: market cap tabel peer + total_debt, kas, EBITDA "
                          f"FY{year} /company/report/{ticker}/")}


def _peer_ev_yahoo(ticker, market_cap):
    """Peer EV from a stored Yahoo Finance snapshot, labelled as such."""
    snapshot = peer_fundamentals.load(ticker)
    if snapshot is None:
        return {"ev_status": "report_not_cached"}
    if market_cap is None:
        return {"ev_status": "market_cap_missing"}
    if snapshot.get("currency") not in (None, "IDR"):
        # The peer-table market cap is IDR; a USD reporter needs a dated FX first.
        return {"ev_status": "currency_mismatch", "ev_year": snapshot["fiscal_year"]}
    debt, cash, ebitda = (snapshot["total_debt"], snapshot["cash_and_equivalents"],
                          snapshot["ebitda"])
    year = snapshot["fiscal_year"]
    ev = market_cap + debt - cash
    meaningful = ev > 0 and ebitda > 0
    return {"ev": ev, "ev_year": year, "ev_status": "ok" if meaningful else "not_meaningful",
            "ev_ebitda": ev / ebitda if meaningful else None, "ev_source_kind": "yahoo",
            "ev_source": (f"market cap tabel peer Sectors + total_debt, kas, EBITDA "
                          f"{snapshot['source']} (diambil {snapshot.get('fetched_at')})")}


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
                    mcap, revenue = _num(c.get("market_cap")), _num(c.get("total_revenue"))
                    out.append({"symbol": c.get("symbol"),
                                "name": c.get("company_name", ""),
                                "pe": _num(c.get("pe_ttm")),
                                "pb": _num(c.get("pb_mrq")),
                                "mcap": mcap, "revenue": revenue,
                                # P/S from the same Sectors row: market cap / revenue.
                                "ps": mcap / revenue if mcap and revenue and revenue > 0 else None,
                                **_peer_ev(c.get("symbol"), mcap)})
    except Exception:
        pass
    pes = sorted(p for p in (c["pe"] for c in out) if p and p > 0)
    pbs = sorted(p for p in (c["pb"] for c in out) if p and p > 0)
    med = lambda s: s[len(s) // 2] if s else None
    return out[:12], med(pes), med(pbs)
