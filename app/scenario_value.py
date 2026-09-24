"""Primary DDM and FCFF DCF on the validated analyst scenario (spec §4.3, Opsi A/B).

The screening forecast (historical CAGR, capex = D&A, flat debt) cannot pass
G2.9, so the profile's primary method was always skipped even when the agents
had produced a validated FY path. These functions value that path directly:

* the FY anchor year = official 1H actual + the agent's H2 assumption, and
* four out-years from the out-year agent,

while every other input comes from sourced data: Sectors history for payout,
D&A, effective tax and working capital, and the official interim balance sheet
(else the latest Sectors year) for cash, debt, minorities and shares. Values
are dated to the balance sheet they bridge from. The result is an
assumption-led valuation; it never marks the forecast production-ready.
"""
from __future__ import annotations

from datetime import date
from statistics import median

KD_PRETAX = 0.09          # market cost of debt, policy parameter (as the screen)
STATUTORY_TAX = 0.22      # Indonesian corporate income tax, fallback only
GRID_DELTAS = (-0.01, -0.005, 0.0, 0.005, 0.01)
GRID_GROWTH = (0.025, 0.035, 0.045)


def _num(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _years(later, earlier):
    return (later - earlier).days / 365.25


def fx_rate(intake):
    """Reporting currency to Rupiah: 1 for IDR reporters, the dated spot for USD."""
    evidence = intake.get("official_evidence") or {}
    if evidence.get("reporting_currency") != "USD":
        return 1.0
    return _num((intake.get("fx_spot") or {}).get("rate"))


def path(fc):
    """Five FY rows: the anchor year and four out-years, reporting currency.

    None when either half of the validated scenario is missing.
    """
    anchor = fc.get("earnings_scenario") or {}
    outyears = (fc.get("outyear_scenario") or {}).get("rows") or []
    full = anchor.get("full_year") or {}
    if not full or len(outyears) != 4:
        return None
    year = anchor["year"]
    rows = [{"year": year, "label": f"FY{year % 100:02d}F", "revenue": full.get("revenue"),
             "net_profit": full.get("net_profit"),
             "net_profit_attributable": full.get("net_profit_attributable"),
             "ebitda": full.get("ebitda"), "capex": full.get("capex"),
             "ebitda_margin_pct": (anchor.get("assumptions") or {}).get("fy_ebitda_margin_pct"),
             "capex_to_revenue_pct": (anchor.get("assumptions") or {}).get(
                 "fy_capex_to_revenue_pct"),
             "basis": "aktual 1H resmi + asumsi H2"}]
    for row in outyears:
        rows.append({key: row.get(key) for key in (
            "year", "label", "revenue", "net_profit", "net_profit_attributable", "ebitda",
            "capex", "ebitda_margin_pct", "capex_to_revenue_pct")} | {
                "basis": "asumsi analis tahunan"})
    return rows


SHARE_CHANGE_LIMIT = 0.05


def _quarter(intake, year_end=False):
    """Latest Sectors quarterly balance sheet with debt and cash on or before
    as-of; with ``year_end`` only fiscal year-end (December) rows."""
    as_of = _day(intake.get("as_of"))
    rows = [r for r in intake.get("quarterly_actuals") or []
            if isinstance(r, dict) and _day(r.get("date"))
            and (not as_of or _day(r["date"]) <= as_of)
            and (not year_end or str(r["date"])[5:] == "12-31")
            and _num(r.get("total_debt")) is not None
            and (_num(r.get("cash_and_short_term_investments")) is not None
                 or _num(r.get("cash_only")) is not None)]
    return max(rows, key=lambda r: r["date"]) if rows else None


def _quarter_cash(row):
    cash = _num(row.get("cash_and_short_term_investments"))
    return cash if cash is not None else row["cash_only"]


def bridge(intake):
    """Cash, debt, minorities and shares in Rupiah, dated to one balance sheet.

    The DCF values fiscal-year flows, so it bridges from the latest fiscal
    year-end (Sectors): an interim balance sheet carries seasonal working
    capital (e.g. a mid-year inventory build funded by short-term debt) that
    a year-based working-capital line cannot unwind. When the share count
    has moved more than 5% since that year-end (a rights issue), the latest
    interim balance sheet is used instead: official when it reports both
    cash and debt, else the latest Sectors quarter. Minorities are book
    value from the same date where available; shares are the official count.
    """
    evidence = intake.get("official_evidence") or {}
    balance = evidence.get("balance_sheet") or {}
    fx = fx_rate(intake) or None
    period = balance.get("period_end")
    official = lambda value: value * fx if _num(value) is not None and fx else None
    out = {"fx": fx, "official_date": _day(period)}
    shares = _num(balance.get("shares_outstanding")) or _num(balance.get("shares_issued"))
    if shares:
        out.update(shares=shares, shares_basis=f"neraca interim resmi {period}")
    elif _num(intake.get("shares")):
        out.update(shares=intake["shares"], shares_basis="data Sectors")
    annual = next((a for a in reversed(intake.get("annuals") or [])
                   if _num(a.get("total_debt")) is not None and _num(a.get("cash")) is not None),
                  None)
    year_row = _quarter(intake, year_end=True)
    if annual and year_row and str(year_row["date"])[:4] != str(annual["year"]):
        year_row = None
    year_shares = _num((annual or {}).get("shares")) or _num(intake.get("shares"))
    moved = (bool(shares and year_shares) and
             abs(shares / year_shares - 1) > SHARE_CHANGE_LIMIT)
    debt = _num(balance.get("total_debt"))
    if debt is None:
        parts = [_num(balance.get(k)) for k in ("loans_current", "loans_noncurrent",
                                                  "lease_current", "lease_noncurrent")]
        debt = sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None
    quarter = _quarter(intake)
    source_row = None
    if annual and not moved:
        source_row = year_row
        cash = _quarter_cash(year_row) if year_row else annual["cash"]
        out.update(cash=cash, debt=year_row["total_debt"] if year_row else annual["total_debt"],
                   valuation_date=date(int(annual["year"]), 12, 31),
                   cash_basis=f"kas dan investasi jangka pendek, Sectors FY{annual['year']}",
                   debt_basis=f"Sectors FY{annual['year']}",
                   anchor_reason="akhir tahun fiskal, agar modal kerja musiman tidak "
                                 "mendistorsi utang bersih")
    elif official(balance.get("cash")) is not None and debt is not None and fx:
        out.update(cash=official(balance["cash"]), debt=debt * fx, valuation_date=_day(period),
                   cash_basis=f"neraca interim resmi {period}",
                   debt_basis=f"neraca interim resmi {period}",
                   anchor_reason="neraca interim terbaru; jumlah saham berubah material "
                                 "sejak akhir tahun fiskal")
    elif quarter:
        source_row = quarter
        out.update(cash=_quarter_cash(quarter), debt=quarter["total_debt"],
                   valuation_date=_day(quarter["date"]),
                   cash_basis=f"kas dan investasi jangka pendek, Sectors kuartal {quarter['date']}",
                   debt_basis=f"Sectors kuartal {quarter['date']}",
                   anchor_reason="neraca kuartal terbaru; jumlah saham berubah material "
                                 "sejak akhir tahun fiskal")
    nci_row = source_row if source_row is not None else None
    if (nci_row and _num(nci_row.get("total_equity")) is not None
            and _num(nci_row.get("stockholders_equity")) is not None):
        out.update(nci=max(nci_row["total_equity"] - nci_row["stockholders_equity"], 0.0),
                   nci_basis=f"nilai buku, Sectors {nci_row['date']}")
    elif official(balance.get("non_controlling_interest")) is not None:
        out.update(nci=official(balance["non_controlling_interest"]),
                   nci_basis=f"nilai buku, neraca interim resmi {period}")
    return out


def da_intensity(intake):
    """D&A over revenue: official 1H figures first, else the Sectors median."""
    metrics = (intake.get("latest_official_actual") or {}).get("metrics") or {}
    revenue = _num(metrics.get("revenue"))
    period = (intake.get("latest_official_actual") or {}).get("period") or "1H"
    if revenue and _num(metrics.get("depreciation")) is not None:
        return metrics["depreciation"] / revenue, f"penyusutan {period} resmi"
    ebitda, operating = _num(metrics.get("ebitda")), _num(metrics.get("operating_profit"))
    if revenue and ebitda is not None and operating is not None and 0 <= ebitda - operating < ebitda:
        return (ebitda - operating) / revenue, f"EBITDA dikurangi laba usaha {period} resmi"
    rows = [a for a in (intake.get("annuals") or [])[-3:]
            if _num(a.get("da")) is not None and a.get("revenue") and _num(a.get("ebitda"))
            and 0 <= a["da"] < a["ebitda"]]
    if rows:
        return (median(a["da"] / a["revenue"] for a in rows),
                f"median D&A/pendapatan FY{rows[0]['year']}-FY{rows[-1]['year']} data Sectors")
    return 0.0, "D&A tidak tersedia; perisai pajak penyusutan tidak dihitung"


def tax_rate(intake):
    """Median effective tax rate of the last three Sectors years, else statutory."""
    rates, years = [], []
    for a in (intake.get("annuals") or [])[-3:]:
        ebt = _num(a.get("ebt"))
        if ebt is None and _num(a.get("ebit")) is not None:
            ebt = a["ebit"] - (a.get("interest") or 0.0)
        tax = _num(a.get("tax"))
        if ebt and ebt > 0 and tax is not None and 0 <= tax / ebt <= 0.5:
            rates.append(tax / ebt)
            years.append(a["year"])
    if rates:
        return (median(rates),
                f"median tarif efektif FY{years[0]}-FY{years[-1]} data Sectors")
    return STATUTORY_TAX, "tarif PPh badan 22% (tarif efektif historis tidak tersedia)"


def nwc_intensity(intake):
    """Non-cash working capital over revenue in the latest Sectors year.

    Negative working capital is not treated as a source of cash from growth.
    """
    a = next((row for row in reversed(intake.get("annuals") or [])
              if all(_num(row.get(k)) is not None for k in
                     ("current_assets", "current_liabilities", "cash", "revenue"))), None)
    if not a:
        return 0.0, "modal kerja tidak tersedia di data Sectors; ΔNWC dianggap nol"
    nwc = (a["current_assets"] - a["cash"]) - (a["current_liabilities"] -
                                                (a.get("short_term_debt") or 0.0))
    ratio = nwc / a["revenue"]
    if ratio < 0:
        return 0.0, (f"modal kerja non-kas FY{a['year']} negatif ({ratio * 100:.0f}% pendapatan); "
                     "tidak dihitung sebagai sumber kas")
    return ratio, f"modal kerja non-kas FY{a['year']} data Sectors ({ratio * 100:.1f}% pendapatan)"


def _schedule(rows, valuation_date, h2_share, dividends):
    """Cash-flow timing in years from the valuation date, and the share of each
    FY still ahead of it. Operating flows are mid-period; dividends are paid
    about a quarter after the fiscal year closes."""
    out = []
    for row in rows:
        start, end = date(row["year"], 1, 1), date(row["year"], 12, 31)
        if end <= valuation_date:
            out.append((0.0, 0.0))
            continue
        if dividends:
            out.append((1.0, _years(end, valuation_date) + 0.25))
            continue
        begin = max(start, valuation_date)
        if start > valuation_date:
            share = 1.0
        elif valuation_date == date(row["year"], 6, 30):
            share = h2_share          # official 1H close: the H2 assumption
        else:
            share = _years(end, begin) / _years(end, start)
        out.append((share, _years(begin, valuation_date) + _years(end, begin) / 2))
    return out


def ddm(intake, fc, coe, g):
    """Dividend discount on the scenario's parent profit (Opsi B).

    DPS = FY parent profit x Sectors historical payout / official shares,
    discounted at the Cost of Equity; Gordon terminal on the last DPS.
    """
    rows = path(fc)
    if not rows:
        return None, ["skenario laba lima tahun (FY + empat tahun lanjutan) belum tervalidasi"]
    reasons = []
    link = bridge(intake)
    fx, shares = link.get("fx"), link.get("shares")
    when = link.get("official_date") or link.get("valuation_date")
    payout, basis = _num(intake.get("payout")), intake.get("payout_basis") or ""
    if payout is None or basis.startswith("asumsi analis"):
        reasons.append("payout historis tidak tersedia di data Sectors")
    if not fx or not shares or not when:
        reasons.append("jumlah saham atau tanggal neraca resmi tidak tersedia")
    if any(_num(r.get("net_profit_attributable")) is None for r in rows):
        reasons.append("laba pemilik induk skenario tidak lengkap")
    if coe <= g:
        reasons.append("cost of equity tidak melebihi pertumbuhan jangka panjang")
    if reasons:
        return None, reasons

    def value(rate, growth):
        timing = _schedule(rows, when, 1.0, dividends=True)
        lines, pv = [], 0.0
        for row, (share, t) in zip(rows, timing):
            dps = max(row["net_profit_attributable"], 0.0) * fx * payout / shares
            factor = 1 / (1 + rate) ** t
            pv += dps * share * factor
            lines.append({"label": row["label"], "net_attr": row["net_profit_attributable"] * fx,
                          "dps": dps, "t": t, "factor": factor, "pv": dps * share * factor})
        terminal_dps = lines[-1]["dps"] * (1 + growth)
        tv = terminal_dps / (rate - growth)
        pv_tv = tv * lines[-1]["factor"]
        return {"lines": lines, "pv_dps": pv, "terminal_dps": terminal_dps, "tv": tv,
                "pv_tv": pv_tv, "per_share": pv + pv_tv}

    base = value(coe, g)
    grid = {(round(d, 3), gg): (value(coe + d, gg)["per_share"] if coe + d > gg else None)
            for d in GRID_DELTAS for gg in GRID_GROWTH}
    for i, line in enumerate(base["lines"]):
        prior = base["lines"][i - 1]["dps"] if i else None
        line["dps_growth"] = line["dps"] / prior - 1 if prior else None
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    equity = _num(balance.get("equity_attributable"))
    if equity is None and _num(balance.get("total_equity")) is not None:
        equity = balance["total_equity"] - (balance.get("non_controlling_interest") or 0.0)
    bvps = equity * fx / shares if equity else None
    roe = (rows[0]["net_profit_attributable"] * fx / (equity * fx)
           if equity else None)
    detail = {"basis": "scenario", "coe": coe, "g": g, "payout": payout,
              "payout_basis": basis, "shares": shares, "shares_basis": link["shares_basis"],
              "valuation_date": when.isoformat(), "fx": fx if fx != 1.0 else None,
              "lines": base["lines"], "pv_dps": base["pv_dps"],
              "terminal_dps": base["terminal_dps"], "tv": base["tv"], "pv_tv": base["pv_tv"],
              "tv_share": base["pv_tv"] / base["per_share"] if base["per_share"] else None,
              "per_share": base["per_share"], "grid": grid,
              "per_share_down": grid.get((0.01, 0.025)),
              "bvps": bvps, "roe": roe, "year": rows[0]["year"],
              "dps_hist": list(intake.get("dps_hist") or [])}
    return detail, []


def fcff(intake, fc, rf, erp, beta, g, wacc_bps=0.0):
    """FCFF DCF on the scenario path (Opsi A).

    FCFF = EBIT x (1 - effective tax) + D&A - capex - ΔNWC. Revenue, EBITDA
    and capex are the agents' validated scenario; D&A, tax and working
    capital intensity come from sourced history. The Gordon terminal is the
    target basis; the issuer's own historical EV/EBITDA is a side-by-side
    exit cross-check whose gap is disclosed, never averaged (§4.4).
    """
    rows = path(fc)
    if not rows:
        return None, ["skenario laba lima tahun (FY + empat tahun lanjutan) belum tervalidasi"]
    missing = [r["label"] for r in rows
               if _num(r.get("ebitda")) is None or _num(r.get("capex")) is None
               or _num(r.get("revenue")) is None]
    if missing:
        return None, ["skenario belum memuat margin EBITDA dan capex untuk "
                      + ", ".join(missing)]
    link = bridge(intake)
    reasons = []
    fx, shares, when = link.get("fx"), link.get("shares"), link.get("valuation_date")
    if not fx or not shares or not when:
        reasons.append("jumlah saham, kurs atau tanggal neraca tidak tersedia")
    if link.get("cash") is None or link.get("debt") is None:
        reasons.append("kas atau utang untuk jembatan EV ke ekuitas tidak tersedia")
    if reasons:
        return None, reasons

    da_ratio, da_basis = da_intensity(intake)
    tax, tax_basis = tax_rate(intake)
    nwc_ratio, nwc_basis = nwc_intensity(intake)
    anchor = fc["earnings_scenario"]
    h2_share = (anchor["h2"]["revenue"] / anchor["full_year"]["revenue"]
                if anchor["full_year"].get("revenue") else 0.5)
    prior_revenue = next((a["revenue"] for a in reversed(intake.get("annuals") or [])
                          if a.get("year") == rows[0]["year"] - 1 and a.get("revenue")), None)

    lines, previous = [], prior_revenue
    for row in rows:
        revenue, ebitda, capex = (row["revenue"] * fx, row["ebitda"] * fx, row["capex"] * fx)
        da = revenue * da_ratio
        ebit = ebitda - da
        tax_paid = max(ebit, 0.0) * tax
        dnwc = nwc_ratio * (revenue - previous) if previous else 0.0
        flow = ebit - tax_paid + da - capex - dnwc
        lines.append({"label": row["label"], "revenue": revenue, "ebitda": ebitda, "da": da,
                      "ebit": ebit, "tax": tax_paid, "nopat": ebit - tax_paid, "capex": capex,
                      "dnwc": dnwc, "fcff": flow,
                      "net_attr": _num(row.get("net_profit_attributable")) and
                      row["net_profit_attributable"] * fx})
        previous = revenue
    for i, line in enumerate(lines):
        prior = lines[i - 1]["fcff"] if i else None
        line["fcff_growth"] = (line["fcff"] / prior - 1 if prior and prior > 0 and
                               line["fcff"] > 0 else None)

    price = _num(intake.get("price"))
    equity_market = price * shares if price else None
    debt, cash = link["debt"], link["cash"]
    weight_debt = debt / (debt + equity_market) if equity_market and debt + equity_market > 0 else 0
    coe = rf + beta * erp
    kd_after = KD_PRETAX * (1 - tax)
    wacc = coe * (1 - weight_debt) + kd_after * weight_debt + wacc_bps / 10000
    share_parent = anchor.get("attributable_share") or 1.0
    nci = link.get("nci")
    exit_points = [h["value"] for h in intake.get("historical_ev_ebitda") or []
                   if _num(h.get("value")) and h["value"] > 0]
    exit_multiple = median(exit_points) if len(exit_points) >= 3 else None
    timing = _schedule(rows, when, h2_share, dividends=False)
    end_last = _years(date(rows[-1]["year"], 12, 31), when)
    # In perpetuity the asset base must be replaced: terminal capex is at
    # least D&A, so a last-year capex below depreciation is not capitalised.
    last = lines[-1]
    terminal_capex = max(last["capex"], last["da"])
    terminal_base = last["fcff"] + last["capex"] - terminal_capex

    def value(rate, growth):
        pv = 0.0
        out = []
        for line, (share, t) in zip(lines, timing):
            factor = 1 / (1 + rate) ** t
            pv += line["fcff"] * share * factor
            out.append({"share": share, "t": t, "factor": factor,
                        "pv": line["fcff"] * share * factor})
        terminal = terminal_base * (1 + growth)
        tv = terminal / (rate - growth)
        factor_tv = 1 / (1 + rate) ** end_last
        ev = pv + tv * factor_tv

        def to_equity(enterprise):
            equity = enterprise + cash - debt
            if nci is not None:
                return equity - nci
            return equity * share_parent

        result = {"timing": out, "pv_explicit": pv, "terminal_fcff": terminal, "tv": tv,
                  "factor_tv": factor_tv, "pv_tv": tv * factor_tv, "ev": ev,
                  "equity": to_equity(ev), "per_share": to_equity(ev) / shares}
        if exit_multiple:
            tv_exit = lines[-1]["ebitda"] * exit_multiple
            ev_exit = pv + tv_exit * factor_tv
            result.update(tv_exit=tv_exit, pv_tv_exit=tv_exit * factor_tv, ev_exit=ev_exit,
                          per_share_exit=to_equity(ev_exit) / shares)
        return result

    base = value(wacc, g)
    for line, step in zip(lines, base["timing"]):
        line.update(step)
    grid = {(round(d, 3), gg): (value(wacc + d, gg)["per_share"] if wacc + d > gg else None)
            for d in GRID_DELTAS for gg in GRID_GROWTH}
    gap = (abs(base["per_share"] - base["per_share_exit"]) /
           max(abs(base["per_share"]), abs(base["per_share_exit"]), 1)
           if base.get("per_share_exit") is not None else None)
    detail = {"basis": "scenario", "lines": lines, "wacc": wacc, "coe": coe, "rf": rf,
              "erp": erp, "beta": beta, "kd_pretax": KD_PRETAX, "kd_after": kd_after,
              "weight_debt": weight_debt, "wacc_bps": wacc_bps, "g": g,
              "tax_rate": tax, "tax_basis": tax_basis, "da_ratio": da_ratio,
              "da_basis": da_basis, "nwc_ratio": nwc_ratio, "nwc_basis": nwc_basis,
              "h2_share": h2_share, "valuation_date": when.isoformat(),
              "anchor_reason": link.get("anchor_reason"),
              "cash": cash, "cash_basis": link.get("cash_basis"), "debt": debt,
              "debt_basis": link.get("debt_basis"), "nci": nci,
              "nci_basis": link.get("nci_basis") or (
                  f"porsi induk {share_parent * 100:.1f}% dari laba 1H resmi"
                  if share_parent < 1 else "tidak dilaporkan terpisah; dianggap tidak material"),
              "attributable_share": share_parent, "shares": shares,
              "terminal_capex": terminal_capex, "terminal_base": terminal_base,
              "shares_basis": link.get("shares_basis"), "fx": fx if fx != 1.0 else None,
              "equity_market": equity_market,
              "pv_explicit": base["pv_explicit"], "terminal_fcff": base["terminal_fcff"],
              "tv": base["tv"], "pv_tv": base["pv_tv"], "ev": base["ev"],
              "equity": base["equity"], "per_share": base["per_share"],
              "tv_share": base["pv_tv"] / base["ev"] if base["ev"] else None,
              "implied_exit": (base["tv"] / lines[-1]["ebitda"]
                               if lines[-1]["ebitda"] > 0 else None),
              "exit_multiple": exit_multiple,
              "exit_points": exit_points,
              "per_share_exit": base.get("per_share_exit"),
              "ev_exit": base.get("ev_exit"), "tv_exit": base.get("tv_exit"),
              "pv_tv_exit": base.get("pv_tv_exit"),
              "exit_gap": gap, "grid": grid,
              "per_share_down": grid.get((0.01, 0.025)),
              "year": rows[0]["year"]}
    return detail, []
