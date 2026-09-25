"""Primary DDM and FCFF DCF on the validated analyst scenario (spec §4.3, Opsi A/B).

The screening forecast (historical CAGR, capex = D&A, flat debt) cannot pass
S2.9, so the profile's primary method was always skipped even when the agents
had produced a validated FY path. These functions value that path directly:

* the FY anchor year = official 1H actual + the agent's H2 assumption, and
* four out-years from the out-year agent,

while every other input comes from sourced data: Sectors history for payout,
D&A, effective tax and working capital, and the official interim balance sheet
(else the latest Sectors year) for cash, debt, minorities and shares. Values
are dated to the balance sheet they bridge from. The result is an
assumption-led valuation; it never marks the forecast production-ready.

The FCFF DCF is built in the issuer's reporting currency (spec §2): a US$
reporter's scenario, balance sheet and discount rate stay in US$ and only the
value per share is converted to rupiah, once, at the dated spot rate. The
detail keeps rupiah mirrors (US$ x that rate) in its usual keys for readers
that work in rupiah, and the US$ figures under ``native``.
"""
from __future__ import annotations

import re
from datetime import date
from statistics import median

from . import bank_model, fmt

KD_PRETAX = 0.09          # market cost of debt, policy parameter (as the screen)
STATUTORY_TAX = 0.22      # Indonesian corporate income tax, fallback only
GRID_DELTAS = (-0.01, -0.005, 0.0, 0.005, 0.01)
GRID_GROWTH = (0.025, 0.035, 0.045)

# --- Discount rate of a model built in US$ (spec §2, §4.2, §4.3) -----------
# Rupiah model: Rf = INDOGB 10Y, which already prices Indonesia's country
# risk, so no CRP is added. US$ model: Rf = UST 10Y at the Report Date
# (app.rates) + the Indonesia country risk premium + beta x mature-market ERP.

CRP_INDONESIA = 0.025
# Indonesia country risk premium, US$ models only: parameter kebijakan analis
# like ERP 4% and g 3,5% (spec §4.3), not a figure taken from an outside
# source. UST 10Y prices no Indonesian sovereign, transfer or convertibility
# risk; a US$ investor in an Indonesian issuer asks for it once, on top of
# beta x the mature-market ERP. 2,5% is set for an investment-grade emerging
# sovereign and held stable, like the ERP, rather than tracking daily bond
# spreads; the sensitivity grid's WACC +/-1pp shows what a different premium
# does. Never added to a rupiah model (INDOGB already carries it).

TERMINAL_GROWTH_USD = 0.03
# Terminal growth of a US$ model: parameter kebijakan analis. Nominal US$
# growth = the US central bank's 2% long-run inflation objective plus 1pp real
# growth, 0,5pp below the rupiah policy 3,5% because US$ inflation is lower;
# below UST 10Y, the template's cap (g <= risk-free rate).
GRID_GROWTH_USD = (0.02, 0.03, 0.04)


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


def model_currency(intake):
    """The currency the DCF is built in: the issuer's reporting currency (spec §2)."""
    evidence = intake.get("official_evidence") or {}
    return "USD" if evidence.get("reporting_currency") == "USD" else "IDR"


def _period_months(period):
    """Months an interim period covers: 1H26 -> 6, 9M26 -> 9, Q1/3M -> 3, FY -> 12."""
    text = str(period or "").upper()
    for pattern, months in ((r"^(1H|H1|6M)", 6), (r"^9M", 9), (r"^(3M|1Q|Q1)", 3),
                            (r"^(FY|12M)", 12)):
        if re.match(pattern, text):
            return months
    return None


def _official_debt(balance):
    """Interest-bearing debt on an official balance sheet: total debt, else
    loans + leases; None when neither is reported."""
    debt = _num(balance.get("total_debt"))
    if debt is None:
        parts = [_num(balance.get(k)) for k in ("loans_current", "loans_noncurrent",
                                                  "lease_current", "lease_noncurrent")]
        debt = sum(p for p in parts if p is not None) if any(p is not None for p in parts) else None
    return debt


def effective_cost_of_debt(intake):
    """(rate, basis): what the issuer pays on its borrowing, from its own release.

    Official interim finance cost, annualised, over interest-bearing debt on
    the balance sheet of the same date; (None, None) when either is missing.
    """
    actual = intake.get("latest_official_actual") or {}
    metrics = actual.get("metrics") or {}
    cost = next((abs(metrics[k]) for k in ("finance_cost", "finance_costs", "interest_expense")
                 if _num(metrics.get(k))), None)
    months = _period_months(actual.get("period"))
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    debt = _official_debt(balance)
    if (not cost or not months or not debt or debt <= 0
            or str(balance.get("period_end")) != str(actual.get("period_end"))):
        return None, None
    period = actual.get("period") or "interim"
    return (cost * 12 / months / debt,
            f"beban keuangan {period} resmi disetahunkan atas utang berbunga neraca resmi "
            f"{balance['period_end']}")


def usd_cost_of_debt(intake, rf):
    """(pre-tax rate, basis, effective rate) of a US$ model, market-based (spec §4.2).

    The market rate is UST 10Y + the Indonesia CRP: what a lender asks for
    Indonesian risk in US$. The issuer's own effective rate is used when it
    is sourced and not below that; a lower one (restructured, subsidised or
    related-party terms) is shown and not used.
    """
    market = rf + CRP_INDONESIA
    effective, basis = effective_cost_of_debt(intake)
    if effective is not None and effective >= market:
        return effective, f"bunga efektif emiten ({basis})", effective
    text = ("UST 10Y + CRP, tingkat pasar pinjaman US$ berisiko Indonesia (parameter kebijakan "
            "analis, §4.2)")
    if effective is not None:
        text += (f"; bunga efektif emiten {fmt.pct(effective)} ({basis}) di bawah tingkat pasar, "
                 "tidak dipakai")
    return market, text, effective


def discount_rates(intake, rf, g):
    """(rates, gaps): the scenario DCF's discount-rate inputs in the model currency.

    Rupiah: the INDOGB policy ``rf`` with no CRP, ``g`` and the 9% policy cost
    of debt. US$: UST 10Y on or before the Report Date (``intake["ust_10y"]``),
    the Indonesia CRP, the US$ terminal growth and a market-based US$ cost of
    debt. A US$ model without a dated UST yield gets a gap, never the rupiah
    rate (spec §2: US$ cash flows are not discounted at a rupiah rate).
    """
    if model_currency(intake) != "USD":
        return {"currency": "IDR", "rf": rf, "rf_label": "INDOGB 10Y", "crp": 0.0, "g": g,
                "grid_growth": GRID_GROWTH, "kd_pretax": KD_PRETAX,
                "kd_basis": "parameter kebijakan analis"}, []
    ust = intake.get("ust_10y") or {}
    rate = _num(ust.get("rate"))
    if rate is None:
        return None, ["imbal hasil UST 10Y bertanggal tidak tersedia pada tanggal laporan; arus "
                      "kas US$ tidak didiskonto dengan tingkat rupiah (spesifikasi §2, §4.2)"]
    kd, kd_basis, effective = usd_cost_of_debt(intake, rate)
    return {"currency": "USD", "rf": rate, "rf_label": "UST 10Y", "rf_date": ust.get("date"),
            "rf_source": ust.get("source"), "crp": CRP_INDONESIA, "g": TERMINAL_GROWTH_USD,
            "grid_growth": GRID_GROWTH_USD, "kd_pretax": kd, "kd_basis": kd_basis,
            "kd_effective": effective}, []


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
    out.update(_distributions(intake, out.get("valuation_date"), out.get("shares")))
    nci_row = source_row if source_row is not None else None
    if (nci_row and _num(nci_row.get("total_equity")) is not None
            and _num(nci_row.get("stockholders_equity")) is not None):
        out.update(nci=max(nci_row["total_equity"] - nci_row["stockholders_equity"], 0.0),
                   nci_basis=f"nilai buku, Sectors {nci_row['date']}")
    elif official(balance.get("non_controlling_interest")) is not None:
        out.update(nci=official(balance["non_controlling_interest"]),
                   nci_basis=f"nilai buku, neraca interim resmi {period}")
    return out


def _distributions(intake, anchor, shares):
    """Cash dividends with an ex-date after the bridge's balance-sheet date and
    on or before the Report Date: that cash has left the company, so the
    equity a buyer gets today is smaller by it (spec §4.3, post-balance-sheet
    events)."""
    as_of = _day(intake.get("as_of"))
    if not anchor or not as_of or not shares:
        return {"distributions": 0.0}
    paid = [e for e in intake.get("dividend_events") or []
            if anchor.isoformat() < e["date"] <= as_of.isoformat()]
    if not paid:
        return {"distributions": 0.0}
    dps = sum(e["dps"] for e in paid)
    dates = ", ".join(e["date"] for e in paid)
    return {"distributions": dps * shares,
            "distributions_basis": (f"dividen tunai Rp{fmt._id(dps, 2)}/saham, ex-date {dates} "
                                    f"(data Sectors), sesudah tanggal neraca {anchor.isoformat()}")}


def bridge_native(intake):
    """``bridge`` in the model currency (spec §2).

    Rupiah reporters: ``bridge`` unchanged. US$ reporters: the official
    balance sheet in US$ the scenario anchors to (the Sectors year-end is only
    available in rupiah converted at a historical rate), cash including
    short-term investments as the rupiah bridge counts them; dividends paid
    after it convert at the dated spot rate. Without official cash and debt,
    the rupiah bridge is converted at the spot rate and labelled so.
    """
    link = bridge(intake)
    if model_currency(intake) != "USD":
        return link
    fx = link.get("fx")
    balance = (intake.get("official_evidence") or {}).get("balance_sheet") or {}
    period = balance.get("period_end")
    cash, debt = _num(balance.get("cash")), _official_debt(balance)
    spot = f"kurs spot Rp{fmt._id(fx, 0)}/US$" if fx else "kurs spot"
    if cash is not None and debt is not None and _day(period) and fx:
        sti = _num(balance.get("short_term_investments")) or 0.0
        out = {"fx": fx, "official_date": _day(period), "valuation_date": _day(period),
               "shares": link.get("shares"), "shares_basis": link.get("shares_basis"),
               "cash": cash + sti, "debt": debt,
               "cash_basis": ("kas dan investasi jangka pendek" if sti else "kas")
               + f", neraca interim resmi {period}",
               "debt_basis": f"utang berbunga, neraca interim resmi {period}",
               "anchor_reason": "neraca resmi terbaru dalam US$, mata uang model; neraca akhir "
                                "tahun data Sectors hanya tersedia dalam rupiah"}
        nci = _num(balance.get("non_controlling_interest"))
        if nci is not None:
            out.update(nci=nci, nci_basis=f"nilai buku, neraca interim resmi {period}")
        paid = _distributions(intake, out["valuation_date"], out["shares"])
        out["distributions"] = paid["distributions"] / fx
        if paid.get("distributions_basis"):
            out["distributions_basis"] = paid["distributions_basis"] + f"; ke US$ pada {spot}"
        return out
    out = dict(link)
    if fx:
        for key in ("cash", "debt", "nci", "distributions"):
            if _num(out.get(key)) is not None:
                out[key] = out[key] / fx
        for key in ("cash_basis", "debt_basis", "nci_basis", "distributions_basis"):
            if out.get(key):
                out[key] += f"; rupiah ke US$ pada {spot}"
    return out


def prior_revenue(intake, year):
    """Revenue of ``year`` in the model currency, the base of the first
    forecast year's working-capital change: a US$ reporter's official annual
    release when it has the year, else Sectors (rupiah; a US$ reporter's
    converted at the spot rate)."""
    sectors = next((a["revenue"] for a in reversed(intake.get("annuals") or [])
                    if a.get("year") == year and a.get("revenue")), None)
    if model_currency(intake) != "USD":
        return sectors
    official = next((r["revenue"] for r in (intake.get("official_evidence") or {})
                     .get("annual_actuals") or []
                     if r.get("year") == year and _num(r.get("revenue"))), None)
    if official is not None:
        return official
    fx = fx_rate(intake)
    return sectors / fx if sectors and fx else None


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
    official = [a for a in rows if a.get("da_source") == "official"]
    if official:
        return (median(a["da"] / a["revenue"] for a in official),
                f"penyusutan/pendapatan FY{official[0]['year']}"
                + (f"-FY{official[-1]['year']}" if len(official) > 1 else "")
                + " laporan keuangan audit")
    if rows:
        return (median(a["da"] / a["revenue"] for a in rows),
                f"median D&A/pendapatan FY{rows[0]['year']}-FY{rows[-1]['year']} data Sectors")
    return None, "D&A tidak tersedia atau tidak wajar di data Sectors dan rilis resmi"


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


def implied_rate(per_share_at, price, g, high=0.60):
    """Discount rate at which the model's value per share equals the price.

    Value falls as the rate rises, so a bisection between just above g and
    ``high`` finds it; None when the price sits outside that range. Shown
    beside the policy rate so a reader sees what the market is discounting.
    """
    if not price or price <= 0:
        return None
    low = g + 0.001
    try:
        if per_share_at(low) < price or per_share_at(high) > price:
            return None
        for _ in range(60):
            mid = (low + high) / 2
            if per_share_at(mid) > price:
                low = mid
            else:
                high = mid
    except (ZeroDivisionError, OverflowError):
        return None
    return (low + high) / 2


def ddm(intake, fc, coe, g):
    """Dividend discount on the scenario's parent profit (Opsi B).

    DPS = FY parent profit x Sectors historical payout / official shares,
    discounted at the Cost of Equity; Gordon terminal on the last DPS.

    On the Bank Driver Scenario each year's payout is the bank model's own
    (``app.bank_model``: lowered where the capital floor binds), and the
    terminal DPS pays the sustainable payout 1 - g / ROE of the last year,
    capped at the historical payout (``bank_model.terminal_payout``).
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
    model = fc.get("bank_model") if isinstance(fc.get("bank_model"), dict) else None
    constrained = bool(model and model.get("constraints"))
    model_payout = {r["year"]: _num(r.get("payout")) for r in (model or {}).get("rows") or []}

    def value(rate, growth):
        timing = _schedule(rows, when, 1.0, dividends=True)
        lines, pv = [], 0.0
        for row, (share, t) in zip(rows, timing):
            ratio = model_payout.get(row["year"]) if constrained else None
            ratio = payout if ratio is None else ratio
            eps = max(row["net_profit_attributable"], 0.0) * fx / shares
            dps = eps * ratio
            factor = 1 / (1 + rate) ** t
            pv += dps * share * factor
            lines.append({"label": row["label"], "net_attr": row["net_profit_attributable"] * fx,
                          "payout": ratio, "dps": dps, "t": t, "factor": factor,
                          "pv": dps * share * factor})
        terminal, terminal_basis = (bank_model.terminal_payout(model, growth) if constrained
                                    else (None, None))
        if terminal is None:
            terminal_dps = lines[-1]["dps"] * (1 + growth)
        else:
            terminal_dps = eps * (1 + growth) * terminal
        tv = terminal_dps / (rate - growth)
        pv_tv = tv * lines[-1]["factor"]
        return {"lines": lines, "pv_dps": pv, "terminal_dps": terminal_dps, "tv": tv,
                "pv_tv": pv_tv, "per_share": pv + pv_tv, "terminal_payout": terminal,
                "terminal_payout_basis": terminal_basis}

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
              "terminal_payout": base["terminal_payout"],
              "terminal_payout_basis": base["terminal_payout_basis"],
              "tv_share": base["pv_tv"] / base["per_share"] if base["per_share"] else None,
              "per_share": base["per_share"], "grid": grid,
              "per_share_down": grid.get((0.01, 0.025)),
              "bvps": bvps, "roe": roe, "year": rows[0]["year"],
              "dps_hist": list(intake.get("dps_hist") or []),
              "implied_coe": implied_rate(lambda r: value(r, g)["per_share"],
                                          _num(intake.get("price")), g)}
    model = fc.get("bank_model") if isinstance(fc.get("bank_model"), dict) else None
    if model and model.get("rows"):
        # Bank Driver Scenario: the profit path is the bank model's, and the
        # Inverse CoE cross-check (spec Opsi B) reads its forward ROAE and BVPS.
        first = model["rows"][0]
        roe_fwd, bvps_fwd = _num(first.get("roe")), _num(first.get("bvps"))
        detail.update(profit_basis="bank_driver_scenario", roe_fwd=roe_fwd,
                      bvps_fwd=bvps_fwd * fx if bvps_fwd is not None else None,
                      fwd_label=first["label"])
        if roe_fwd is not None and bvps_fwd and coe > g:
            detail["fair_pbv"] = (roe_fwd - g) / (coe - g)
            detail["per_share_inverse"] = detail["fair_pbv"] * bvps_fwd * fx
    return detail, []


# Money fields of a DCF line and of the detail: model currency under
# ``native``, rupiah mirror (x the spot rate) in the usual keys.
_LINE_MONEY = ("revenue", "ebitda", "da", "ebit", "tax", "nopat", "capex", "dnwc", "fcff",
               "net_attr", "pv")
_DETAIL_MONEY = ("cash", "debt", "nci", "distributions", "equity_market", "terminal_capex",
                 "terminal_base", "pv_explicit", "terminal_fcff", "tv", "pv_tv", "ev", "equity",
                 "ev_exit", "tv_exit", "pv_tv_exit", "equity_exit", "prior_revenue")


def fcff(intake, fc, rf, erp, beta, g, wacc_bps=0.0, rates=None):
    """FCFF DCF on the scenario path (Opsi A), in the model currency.

    FCFF = EBIT x (1 - effective tax) + D&A - capex - ΔNWC. Revenue, EBITDA
    and capex are the agents' validated scenario; D&A, tax and working
    capital intensity come from sourced history. The Gordon terminal is the
    target basis; the issuer's own historical EV/EBITDA is a side-by-side
    exit cross-check whose gap is disclosed, never averaged (§4.4).

    ``rates`` (``discount_rates``) sets Rf, CRP, g and the cost of debt in the
    model currency; without it the positional ``rf`` and ``g`` are used with
    no CRP and the 9% policy cost of debt. A US$ reporter is valued in US$:
    flows, balance sheet (``bridge_native``), EV and equity; the value per
    share alone converts to rupiah at the dated spot rate. The detail's usual
    money keys hold rupiah mirrors (US$ x that one rate), ``native`` the US$.
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
    currency = model_currency(intake)
    rates = rates or {"currency": currency, "rf": rf, "crp": 0.0, "g": g,
                      "grid_growth": GRID_GROWTH, "kd_pretax": KD_PRETAX,
                      "kd_basis": "parameter kebijakan analis"}
    rf, crp, g = rates["rf"], rates.get("crp") or 0.0, rates["g"]
    kd_pretax = rates.get("kd_pretax", KD_PRETAX)
    growths = tuple(rates.get("grid_growth") or GRID_GROWTH)
    link = bridge_native(intake)
    reasons = []
    fx, shares, when = link.get("fx"), link.get("shares"), link.get("valuation_date")
    if not fx or not shares or not when:
        reasons.append("jumlah saham, kurs atau tanggal neraca tidak tersedia")
    if link.get("cash") is None or link.get("debt") is None:
        reasons.append("kas atau utang untuk jembatan EV ke ekuitas tidak tersedia")
    if reasons:
        return None, reasons

    da_ratio, da_basis = da_intensity(intake)
    if da_ratio is None:
        return None, [da_basis]
    tax, tax_basis = tax_rate(intake)
    nwc_ratio, nwc_basis = nwc_intensity(intake)
    anchor = fc["earnings_scenario"]
    h2_share = (anchor["h2"]["revenue"] / anchor["full_year"]["revenue"]
                if anchor["full_year"].get("revenue") else 0.5)
    # The scenario is in the reporting currency, which is the model currency.
    prior = prior_revenue(intake, rows[0]["year"] - 1)

    lines, previous = [], prior
    for row in rows:
        revenue, ebitda, capex = row["revenue"], row["ebitda"], row["capex"]
        da = revenue * da_ratio
        ebit = ebitda - da
        tax_paid = max(ebit, 0.0) * tax
        dnwc = nwc_ratio * (revenue - previous) if previous else 0.0
        flow = ebit - tax_paid + da - capex - dnwc
        lines.append({"label": row["label"], "revenue": revenue, "ebitda": ebitda, "da": da,
                      "ebit": ebit, "tax": tax_paid, "nopat": ebit - tax_paid, "capex": capex,
                      "dnwc": dnwc, "fcff": flow,
                      "net_attr": _num(row.get("net_profit_attributable"))})
        previous = revenue
    for i, line in enumerate(lines):
        prior_flow = lines[i - 1]["fcff"] if i else None
        line["fcff_growth"] = (line["fcff"] / prior_flow - 1 if prior_flow and prior_flow > 0 and
                               line["fcff"] > 0 else None)

    # Rupiah per model-currency unit: 1 for a rupiah model, the spot for US$.
    to_idr = fx if currency == "USD" else 1.0
    price = _num(intake.get("price"))
    equity_market = price * shares / to_idr if price else None
    debt, cash = link["debt"], link["cash"]
    paid_out = link.get("distributions") or 0.0
    weight_debt = debt / (debt + equity_market) if equity_market and debt + equity_market > 0 else 0
    coe = rf + crp + beta * erp
    kd_after = kd_pretax * (1 - tax)
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
            # Dividends went to the parent's shareholders; minorities are
            # bridged before them.
            equity = enterprise + cash - debt
            if nci is not None:
                return equity - nci - paid_out
            return equity * share_parent - paid_out

        result = {"timing": out, "pv_explicit": pv, "terminal_fcff": terminal, "tv": tv,
                  "factor_tv": factor_tv, "pv_tv": tv * factor_tv, "ev": ev,
                  "equity": to_equity(ev), "per_share": to_equity(ev) / shares}
        if exit_multiple:
            tv_exit = lines[-1]["ebitda"] * exit_multiple
            ev_exit = pv + tv_exit * factor_tv
            result.update(tv_exit=tv_exit, pv_tv_exit=tv_exit * factor_tv, ev_exit=ev_exit,
                          equity_exit=to_equity(ev_exit),
                          per_share_exit=to_equity(ev_exit) / shares)
        return result

    # The one conversion: value per share in the model currency to rupiah.
    rupiah = lambda per_share: per_share * to_idr  # noqa: E731
    base = value(wacc, g)
    implied_wacc = implied_rate(lambda r: rupiah(value(r, g)["per_share"]), price, g)
    implied_coe = ((implied_wacc - kd_after * weight_debt) / (1 - weight_debt)
                   if implied_wacc is not None and weight_debt < 1 else None)
    for line, step in zip(lines, base["timing"]):
        line.update(step)
    grid = {(round(d, 3), gg): (rupiah(value(wacc + d, gg)["per_share"]) if wacc + d > gg
                                else None)
            for d in GRID_DELTAS for gg in growths}
    per_share = rupiah(base["per_share"])
    per_share_exit = (rupiah(base["per_share_exit"]) if base.get("per_share_exit") is not None
                      else None)
    gap = (abs(per_share - per_share_exit) / max(abs(per_share), abs(per_share_exit), 1)
           if per_share_exit is not None else None)
    native = {"lines": lines, "cash": cash, "debt": debt, "nci": nci, "distributions": paid_out,
              "equity_market": equity_market, "terminal_capex": terminal_capex,
              "terminal_base": terminal_base, "pv_explicit": base["pv_explicit"],
              "terminal_fcff": base["terminal_fcff"], "tv": base["tv"], "pv_tv": base["pv_tv"],
              "ev": base["ev"], "equity": base["equity"], "per_share": base["per_share"],
              "ev_exit": base.get("ev_exit"), "tv_exit": base.get("tv_exit"),
              "pv_tv_exit": base.get("pv_tv_exit"), "equity_exit": base.get("equity_exit"),
              "per_share_exit": base.get("per_share_exit"), "prior_revenue": prior}
    mirror = lambda v: v * to_idr if _num(v) is not None else v  # noqa: E731
    detail = {"basis": "scenario", "currency": currency,
              "lines": [{k: (mirror(v) if k in _LINE_MONEY else v) for k, v in line.items()}
                        for line in lines],
              "wacc": wacc, "coe": coe, "rf": rf, "crp": crp,
              "rf_label": rates.get("rf_label"), "rf_date": rates.get("rf_date"),
              "rf_source": rates.get("rf_source"),
              "erp": erp, "beta": beta, "kd_pretax": kd_pretax, "kd_after": kd_after,
              "kd_basis": rates.get("kd_basis"), "kd_effective": rates.get("kd_effective"),
              "weight_debt": weight_debt, "wacc_bps": wacc_bps, "g": g,
              "implied_wacc": implied_wacc, "implied_coe": implied_coe,
              "tax_rate": tax, "tax_basis": tax_basis, "da_ratio": da_ratio,
              "da_basis": da_basis, "nwc_ratio": nwc_ratio, "nwc_basis": nwc_basis,
              "h2_share": h2_share, "valuation_date": when.isoformat(),
              "anchor_reason": link.get("anchor_reason"),
              "cash_basis": link.get("cash_basis"),
              "distributions_basis": link.get("distributions_basis"),
              "debt_basis": link.get("debt_basis"),
              "nci_basis": link.get("nci_basis") or (
                  f"porsi induk {share_parent * 100:.1f}% dari laba 1H resmi"
                  if share_parent < 1 else "tidak dilaporkan terpisah; dianggap tidak material"),
              "attributable_share": share_parent, "shares": shares,
              "shares_basis": link.get("shares_basis"), "fx": fx if fx != 1.0 else None,
              "fx_date": (intake.get("fx_spot") or {}).get("date") if fx != 1.0 else None,
              "per_share": per_share,
              "tv_share": base["pv_tv"] / base["ev"] if base["ev"] else None,
              "implied_exit": (base["tv"] / lines[-1]["ebitda"]
                               if lines[-1]["ebitda"] > 0 else None),
              "exit_multiple": exit_multiple,
              "exit_points": exit_points,
              "per_share_exit": per_share_exit,
              "exit_gap": gap, "grid": grid, "grid_growth": growths,
              "per_share_down": grid.get((0.01, min(growths))),
              "year": rows[0]["year"],
              "native": native if currency == "USD" else None}
    detail.update({k: mirror(native[k]) for k in _DETAIL_MONEY})
    return detail, []


def native_view(detail):
    """The DCF detail in its model currency: US$ figures for a US$ model
    (``native``), the detail itself for a rupiah model. Rupiah per-share values
    (``per_share``, ``per_share_exit``, ``grid``) and rates stay the detail's
    own; the US$ per-share values are ``per_share_native`` and
    ``per_share_exit_native``."""
    native = (detail or {}).get("native")
    if not native:
        return detail
    per_share = ("per_share", "per_share_exit")
    return {**detail, **{k: v for k, v in native.items() if k not in per_share},
            "per_share_native": native["per_share"],
            "per_share_exit_native": native.get("per_share_exit")}


def ev_ebitda_peer(intake, fc, peers):
    """Forward EV/EBITDA peer on the scenario FY EBITDA (§4.1a: history < 4y
    or ramping asset, where an explicit cash-flow horizon is not yet credible).

    EV = median peer EV/EBITDA (each peer's latest FY from its own Sectors
    report) x FY EBITDA from the validated earnings scenario (official 1H
    actual + the agent's FY EBITDA margin), then cash less debt and
    minorities from one balance sheet, over official shares. Lower and upper
    quartiles are the sensitivity. One forward year: no out-year rows.
    """
    from . import method_chain
    scenario = fc.get("earnings_scenario") or {}
    if not scenario:
        return None, ["skenario laba FY (aktual 1H resmi + asumsi H2) belum tervalidasi"]
    reasons = []
    ebitda = _num((scenario.get("full_year") or {}).get("ebitda"))
    if ebitda is None:
        reasons.append("margin EBITDA FY skenario belum tersedia dari agen")
    elif ebitda <= 0:
        reasons.append("EBITDA FY skenario tidak positif; EV/EBITDA tidak bermakna")
    gap = method_chain.peer_ev_ebitda_gap(peers)
    if gap:
        reasons.append(gap)
    link = bridge(intake)
    fx, shares, when = link.get("fx"), link.get("shares"), link.get("valuation_date")
    cash, debt, nci = link.get("cash"), link.get("debt"), link.get("nci")
    if not fx or not shares or not when:
        reasons.append("jumlah saham resmi, kurs atau tanggal neraca tidak tersedia")
    if cash is None or debt is None:
        reasons.append("jembatan kas dan utang dari satu neraca belum tersedia")
    if reasons:
        return None, reasons
    mults = method_chain.peer_ev_ebitdas(peers)
    q1, med, q3 = method_chain.pe_quartiles(mults)
    ebitda_idr = ebitda * fx
    nci = nci or 0.0
    paid_out = link.get("distributions") or 0.0

    def per_share(multiple):
        return (multiple * ebitda_idr + cash - debt - nci - paid_out) / shares

    ev = med * ebitda_idr
    equity = ev + cash - debt - nci - paid_out
    lo, hi = method_chain.PEER_EV_BAND
    used = [p for p in peers or []
            if _num(p.get("ev_ebitda")) is not None and lo < p["ev_ebitda"] <= hi]
    detail = {"basis": "scenario", "year": scenario["year"], "ebitda": ebitda,
              "ebitda_idr": ebitda_idr, "fx": fx if fx != 1.0 else None,
              "median_ev_ebitda": med, "q1_ev_ebitda": q1, "q3_ev_ebitda": q3,
              "peer_count": len(mults), "peer_source": method_chain.peer_ev_sources(peers),
              "peers": [{"symbol": str(p.get("symbol") or "?").replace(".JK", ""),
                         "ev_ebitda": p["ev_ebitda"], "ev_year": p.get("ev_year"),
                         "ev_period": p.get("ev_period"),
                         "source_kind": p.get("ev_source_kind")}
                        for p in sorted(used, key=lambda p: p["ev_ebitda"])],
              "ev": ev, "cash": cash, "debt": debt, "nci": nci, "equity": equity,
              "distributions": paid_out, "distributions_basis": link.get("distributions_basis"),
              "shares": shares, "shares_basis": link.get("shares_basis"),
              "cash_basis": link.get("cash_basis"), "debt_basis": link.get("debt_basis"),
              "nci_basis": link.get("nci_basis"), "valuation_date": when.isoformat(),
              "per_share": equity / shares, "per_share_down": per_share(q1),
              "per_share_up": per_share(q3), "grid": {}}
    return detail, []
