"""Bank driver model: loans, earning assets, funding and capital to profit and
equity (spec §3.1 Institusi keuangan, S2.8; template Slides 6-7).

The Bank Driver Scenario sets five drivers per year: gross loan growth, NIM on
average earning assets, non-interest income as a share of NII, cost-to-income
and cost of credit (optionally deposit growth). The model derives everything
else from the issuer's own Sectors history (FY actuals) and the official
interim release, each rule stated in ``assumptions``:

* balance sheet: gross loans from loan growth; allowance = FY coverage x
  gross loans; deposits = net loans / FY LDR (or the scenario's deposit
  growth), split into current, savings and time deposits at FY shares; other
  interest-bearing and non-interest-bearing liabilities at FY ratios to
  deposits; equity rolled forward (parent profit less dividends at the
  historical payout, minorities with their share of profit); total assets =
  liabilities + equity; non-earning assets (cash, fixed and other assets)
  keep the FY share of total assets, and earning assets other than loans
  (placements, securities, government bonds) are the stated balancing item:
  funding the loans do not use is placed there, and a loan book that
  outgrows funding draws it down (a negative balance is a model problem);
* income statement: NII = NIM x average earning assets; non-interest income =
  ratio x NII; operating expense = cost-to-income x total income; provisions =
  cost of credit x average gross loans; tax at the median effective rate;
  minorities at the official 1H parent share. Interest income and expense are
  split with the FY cost of funds held flat (screening);
* FY of the interim year = official 1H actual + modelled H2: H2 NII on the
  half-year average of earning assets (mid-year from the official total
  assets), H2 provisions on the half-year average of gross loans. The 1H
  release reports revenue, NII and profit only, so 1H operating expense,
  provisions and tax are a screening split at FY composition that adds up to
  the official 1H profit;
* CAR (screening) = equity x FY capital-to-equity / (total assets x FY RWA
  density).

Sectors naming: ``non_loan_earning_assets`` holds total earning assets
including loans (Sectors' NIM = NII / that field), so the model's earning
assets use that key. Non-interest income is the total of every income line
between NII and pre-tax profit (fees, premiums and non-operating income):
pre-tax profit - NII + operating expense + provisions, so a reclassification
between those lines (BBRI FY2025) does not move it. Values are full Rupiah;
ratios are fractions in rows and percent in drivers.
"""
from __future__ import annotations

from statistics import median

from . import fmt

# Drivers the Bank Driver Scenario sets for every year, and one optional.
DRIVERS = ("loan_growth_pct", "nim_pct", "non_ii_to_nii_pct", "cost_to_income_pct",
           "cost_of_credit_pct")
OPTIONAL_DRIVERS = ("deposit_growth_pct",)
BOUNDS = {"loan_growth_pct": (-20.0, 40.0), "nim_pct": (0.5, 15.0),
          "non_ii_to_nii_pct": (0.0, 150.0), "cost_to_income_pct": (10.0, 90.0),
          "cost_of_credit_pct": (0.0, 10.0), "deposit_growth_pct": (-20.0, 40.0)}
# A driver further than this from both the issuer's three-year average and its
# 1H value (annualised, or implied) needs a dated source (percentage points).
TOLERANCE = {"loan_growth_pct": 5.0, "nim_pct": 0.5, "non_ii_to_nii_pct": 10.0,
             "cost_to_income_pct": 5.0, "cost_of_credit_pct": 0.5,
             "deposit_growth_pct": 5.0}
LABELS = {"loan_growth_pct": "pertumbuhan kredit bruto",
          "nim_pct": "NIM atas rata-rata aset produktif",
          "non_ii_to_nii_pct": "pendapatan non-bunga terhadap NII",
          "cost_to_income_pct": "rasio biaya terhadap pendapatan",
          "cost_of_credit_pct": "biaya kredit atas rata-rata kredit bruto",
          "deposit_growth_pct": "pertumbuhan dana pihak ketiga"}

HISTORY_KEYS = ("interest_income", "interest_expense", "net_interest_income",
                "non_interest_income", "net_premium_income", "non_operating_income_or_loss",
                "operating_expense", "provision", "earnings_before_tax", "tax", "earnings",
                "revenue", "gross_loan", "allowance_for_loans", "net_loan",
                "non_loan_earning_assets", "total_assets", "total_deposit", "current_account",
                "savings_account", "time_deposit", "other_interest_bearing_liabilities",
                "non_interest_bearing_liabilities", "total_liabilities", "total_equity",
                "total_risk_weighted_asset", "total_capital", "outstanding_shares")
# Lines the model needs in the base year (and gross loans and earning assets
# in the year before) to run at all.
REQUIRED_BASE = ("gross_loan", "non_loan_earning_assets", "net_interest_income",
                 "operating_expense", "provision", "earnings_before_tax", "tax", "earnings",
                 "total_deposit", "total_equity", "total_assets")


def _num(value):
    return (float(value) if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None)


def _div(top, bottom):
    return top / bottom if top is not None and bottom else None


def _avg(a, b):
    return (a + b) / 2 if a is not None and b is not None else None


def _bn(value):
    return f"Rp{fmt._id(value / 1e12, 1)} triliun"


def _pct(fraction, dec=1):
    return fmt.pct(fraction, dec) if fraction is not None else "n.m."


# --------------------------------------------------------------- history

def history_rows(report_financials):
    """The Sectors bank lines of ``historical_financials``, oldest first.

    A small, JSON-safe subset an intake or a Forecast Plan source can carry.
    """
    rows = (report_financials or {}).get("historical_financials") or []
    out = []
    for row in sorted((r for r in rows if isinstance(r, dict) and r.get("year")),
                      key=lambda r: int(r["year"])):
        out.append({"year": int(row["year"]),
                    **{k: _num(row.get(k)) for k in HISTORY_KEYS}})
    return out


def history(rows):
    """Per fiscal year: the bank lines and the ratios the drivers are read on."""
    years = []
    for row in sorted((r for r in rows or [] if isinstance(r, dict) and r.get("year")),
                      key=lambda r: int(r["year"])):
        y = {"year": int(row["year"]), **{k: _num(row.get(k)) for k in HISTORY_KEYS}}
        for key in ("provision", "allowance_for_loans"):
            if y[key] is not None:
                y[key] = abs(y[key])  # Sectors flips the sign of these between years
        nii, ebt, opex, prov = (y[k] for k in ("net_interest_income", "earnings_before_tax",
                                               "operating_expense", "provision"))
        y["other_income"] = (ebt - nii + opex + prov
                             if None not in (nii, ebt, opex, prov) else None)
        years.append(y)
    by_year = {y["year"]: y for y in years}
    for y in years:
        prev = by_year.get(y["year"] - 1) or {}
        get = lambda key, row=y: row.get(key)
        ea, gl, dep = get("non_loan_earning_assets"), get("gross_loan"), get("total_deposit")
        income = (get("net_interest_income") + get("other_income")
                  if None not in (get("net_interest_income"), get("other_income")) else None)
        ibl = (dep + (get("other_interest_bearing_liabilities") or 0.0)) if dep is not None else None
        prev_ibl = (prev["total_deposit"] + (prev.get("other_interest_bearing_liabilities") or 0.0)
                    if _num(prev.get("total_deposit")) is not None else None)
        casa = (get("current_account") + get("savings_account")
                if None not in (get("current_account"), get("savings_account")) else None)
        y["ratios"] = {
            "nim": _div(get("net_interest_income"), _avg(prev.get("non_loan_earning_assets"), ea)),
            "cost_of_credit": _div(get("provision"), _avg(prev.get("gross_loan"), gl)),
            "cost_to_income": _div(get("operating_expense"), income),
            "non_ii_to_nii": _div(get("other_income"), get("net_interest_income")),
            "loan_growth": (_div(gl, prev.get("gross_loan")) - 1
                            if gl is not None and _num(prev.get("gross_loan")) else None),
            "deposit_growth": (_div(dep, prev.get("total_deposit")) - 1
                               if dep is not None and _num(prev.get("total_deposit")) else None),
            "ldr": _div(get("net_loan"), dep),
            "casa": _div(casa, dep),
            "tax_rate": (_div(get("tax"), get("earnings_before_tax"))
                         if (get("earnings_before_tax") or 0) > 0 else None),
            "loan_share_ea": _div(gl, ea),
            "coverage": _div(get("allowance_for_loans"), gl),
            "capital_to_equity": _div(get("total_capital"), get("total_equity")),
            "rwa_density": _div(get("total_risk_weighted_asset"), get("total_assets")),
            "car": _div(get("total_capital"), get("total_risk_weighted_asset")),
            "cost_of_funds": _div(get("interest_expense"), _avg(prev_ibl, ibl)),
            "roe": _div(get("earnings"), _avg(prev.get("total_equity"), get("total_equity"))),
        }
    return years


def eligible(rows, official, balance=None):
    """Reasons the bank model cannot run on this evidence ([] when it can)."""
    reasons = []
    actual = official or {}
    metrics = actual.get("metrics") or {}
    if not str(actual.get("period") or "").startswith("1H"):
        reasons.append("rilis resmi terbaru bukan periode 1H")
    for key in ("revenue", "net_interest_income", "net_profit"):
        if _num(metrics.get(key)) is None:
            reasons.append(f"rilis 1H resmi tidak memuat {key}")
    try:
        year = int(str(actual.get("period_end") or "")[:4])
    except ValueError:
        year = None
    years = {y["year"]: y for y in history(rows)}
    base = years.get(year - 1) if year else None
    if not base:
        reasons.append("data Sectors tahun fiskal sebelum periode interim tidak tersedia")
        return reasons
    missing = [k for k in REQUIRED_BASE if base.get(k) is None]
    if missing:
        reasons.append(f"data Sectors FY{base['year']} tidak memuat " + ", ".join(missing))
    prev = years.get(base["year"] - 1) or {}
    if prev.get("gross_loan") is None or prev.get("non_loan_earning_assets") is None:
        reasons.append(f"data Sectors FY{base['year'] - 1} tidak memuat kredit bruto dan "
                       "aset produktif")
    return reasons


# ------------------------------------------------------------ 1H anchor

def interim(rows, official, balance=None):
    """The official 1H actual and the mid-year balances the H2 drivers use.

    Returns None when the model is not eligible. ``implied`` holds the 1H
    cost split (screening, FY composition) and the annualised 1H ratios the
    agent and the validator compare drivers with.
    """
    if eligible(rows, official, balance):
        return None
    actual, balance = official or {}, balance or {}
    metrics = actual["metrics"]
    year = int(str(actual["period_end"])[:4])
    years = {y["year"]: y for y in history(rows)}
    base = years[year - 1]
    r = base["ratios"]
    nii, revenue, net = (metrics["net_interest_income"], metrics["revenue"],
                         metrics["net_profit"])
    parent = _num(metrics.get("net_profit_attributable"))
    share, share_basis = ((parent / net, f"porsi induk {actual['period']} resmi")
                          if parent is not None and net > 0 and parent > 0 else
                          (1.0, "laba konsolidasi; porsi induk tidak dilaporkan terpisah"))
    ea0, gl0 = base["non_loan_earning_assets"], base["gross_loan"]
    ta_mid = _num(balance.get("total_assets"))
    ea_ratio = _div(ea0, base["total_assets"])
    if ta_mid is not None and ea_ratio:
        ea_mid = ta_mid * ea_ratio
        ea_mid_basis = (f"total aset {actual['period']} resmi {_bn(ta_mid)} x rasio aset produktif "
                        f"terhadap total aset FY{base['year']} {_pct(ea_ratio)} (screening)")
    else:
        ea_mid, ea_mid_basis = None, None
    loans_mid = _num(balance.get("loans"))
    deposits_mid = _num(balance.get("deposits"))
    tax_rate, tax_basis = tax_rule(rows, base["year"])
    tax = net * tax_rate / (1 - tax_rate) if net > 0 else 0.0
    ebt = net + tax
    costs = revenue - ebt
    opex_share = _div(base["operating_expense"],
                      base["operating_expense"] + base["provision"]) or 1.0
    opex, provision = costs * opex_share, costs * (1 - opex_share)
    implied = {
        "nim": (_div(nii * 2, _avg(ea0, ea_mid)) if ea_mid is not None else None),
        "non_ii_to_nii": _div(revenue - nii, nii),
        "cost_to_income": _div(opex, revenue),
        "cost_of_credit": (_div(provision * 2, _avg(gl0, loans_mid))
                           if loans_mid is not None else None),
        "loan_growth": ((loans_mid / gl0) ** 2 - 1 if loans_mid and gl0 else None),
        "deposit_growth": ((deposits_mid / base["total_deposit"]) ** 2 - 1
                           if deposits_mid and base["total_deposit"] else None),
    }
    return {"year": year, "period": actual["period"], "period_end": actual["period_end"],
            "source_url": actual.get("source_url"), "published_at": actual.get("published_at"),
            "base_year": base["year"],
            "revenue": revenue, "net_interest_income": nii, "other_income": revenue - nii,
            "net_profit": net, "net_profit_attributable": net * share if parent is None else parent,
            "parent_share": share, "parent_share_basis": share_basis,
            "earning_assets_mid": ea_mid, "earning_assets_mid_basis": ea_mid_basis,
            "loans_mid": loans_mid, "deposits_mid": deposits_mid, "total_assets_mid": ta_mid,
            "tax_rate": tax_rate, "tax_rate_basis": tax_basis,
            "split": {"tax": tax, "earnings_before_tax": ebt, "operating_expense": opex,
                      "provision": provision, "opex_share": opex_share},
            "implied": implied}


def tax_rule(rows, base_year):
    """(rate, basis): median effective tax rate of the last three fiscal years."""
    years = [y for y in history(rows) if y["year"] <= base_year][-3:]
    rates = [(y["ratios"]["tax_rate"], y["year"]) for y in years
             if y["ratios"]["tax_rate"] is not None and 0 <= y["ratios"]["tax_rate"] < 0.6]
    if not rates:
        return 0.22, "tarif PPh badan 22% (tarif efektif historis tidak tersedia)"
    span = f"FY{rates[0][1]}-FY{rates[-1][1]}" if len(rates) > 1 else f"FY{rates[0][1]}"
    return median(r for r, _ in rates), f"median tarif efektif {span} data Sectors"


# -------------------------------------------------------- driver reference

_RATIO_OF = {"loan_growth_pct": "loan_growth", "nim_pct": "nim",
             "non_ii_to_nii_pct": "non_ii_to_nii", "cost_to_income_pct": "cost_to_income",
             "cost_of_credit_pct": "cost_of_credit", "deposit_growth_pct": "deposit_growth"}


def reference(rows, official, balance=None):
    """What each driver is judged against: the issuer's own last three fiscal
    years and its 1H value (annualised; CIR and cost of credit implied by the
    screening 1H cost split). Percent values. None when not eligible."""
    anchor = interim(rows, official, balance)
    if not anchor:
        return None
    years = [y for y in history(rows) if y["year"] <= anchor["base_year"]][-3:]
    table = []
    for y in years:
        r = y["ratios"]
        table.append({"year": y["year"],
                      **{driver: _round(r[_RATIO_OF[driver]])
                         for driver in DRIVERS + OPTIONAL_DRIVERS},
                      "ldr_pct": _round(r["ldr"]), "casa_pct": _round(r["casa"]),
                      "roe_pct": _round(r["roe"]), "car_pct": _round(r["car"]),
                      "cost_of_funds_pct": _round(r["cost_of_funds"])})
    average = {}
    for driver in DRIVERS + OPTIONAL_DRIVERS:
        values = [row[driver] for row in table if row[driver] is not None]
        average[driver] = round(sum(values) / len(values), 2) if values else None
    first_half = {driver: _round(anchor["implied"][_RATIO_OF[driver]])
                  for driver in DRIVERS + OPTIONAL_DRIVERS}
    return {"base_year": anchor["base_year"], "interim_year": anchor["year"],
            "period": anchor["period"], "history": table, "three_year_average": average,
            "interim": first_half, "tolerance": dict(TOLERANCE),
            "interim_basis": (f"{anchor['period']} resmi: NIM = NII x 2 / rata-rata aset produktif "
                              f"FY{anchor['base_year']} dan {anchor['period']} (aset produktif "
                              "tengah tahun dari total aset resmi, screening); pertumbuhan kredit "
                              "dan DPK disetahunkan dari saldo 30 Juni neraca resmi terhadap "
                              "kredit bruto dan DPK FY data Sectors (definisi kredit rilis dapat "
                              "berbeda dari kredit bruto Sectors); CIR dan biaya kredit "
                              "tersirat dari pemisahan beban 1H pada komposisi FY (screening)")}


def _round(fraction):
    return round(fraction * 100, 2) if fraction is not None else None


def departures(row, ref):
    """Drivers further than the tolerance from both references (percent)."""
    out = []
    if not ref:
        return out
    for driver in DRIVERS + OPTIONAL_DRIVERS:
        value = _num(row.get(driver))
        if value is None:
            continue
        refs = [x for x in (ref["three_year_average"].get(driver), ref["interim"].get(driver))
                if x is not None]
        if refs and all(abs(value - x) > TOLERANCE[driver] + 1e-9 for x in refs):
            out.append(driver)
    return out


# ------------------------------------------------------------- the model

def _parameters(rows, anchor):
    base = {y["year"]: y for y in history(rows)}[anchor["base_year"]]
    r = base["ratios"]
    dep = base["total_deposit"]
    return {
        "base": base,
        "loan_share_ea": r["loan_share_ea"],
        "coverage": r["coverage"] if r["coverage"] is not None else 0.0,
        "coverage_known": r["coverage"] is not None,
        "ldr": r["ldr"],
        "ca_share": _div(base["current_account"], dep),
        "sa_share": _div(base["savings_account"], dep),
        "oibl_ratio": _div(base["other_interest_bearing_liabilities"], dep),
        "nibl_ratio": _div(base["non_interest_bearing_liabilities"], dep),
        "capital_to_equity": r["capital_to_equity"],
        "rwa_density": r["rwa_density"],
        "rwa_per_loan": _div(base["total_risk_weighted_asset"], base["gross_loan"]),
        "cost_of_funds": r["cost_of_funds"],
        "non_earning_share": _div(base["total_assets"] - base["non_loan_earning_assets"]
                                  + (base["allowance_for_loans"] or 0.0), base["total_assets"]),
    }


def limits(rows, base_year):
    """The capital floor and funding cap the projection holds (S2.8).

    CAR floor = the issuer's lowest capital ratio (total capital / RWA) in the
    Sectors history; LDR cap = its highest LDR (net loans / deposits). Either
    is None when the history does not carry it.
    """
    past = [y for y in history(rows) if y["year"] <= base_year]
    cars = [(y["ratios"]["car"], y["year"]) for y in past if y["ratios"]["car"]]
    ldrs = [(y["ratios"]["ldr"], y["year"]) for y in past if y["ratios"]["ldr"]]
    car, ldr = (min(cars) if cars else None), (max(ldrs) if ldrs else None)
    return {"car_floor": car[0] if car else None,
            "car_floor_basis": (f"CAR terendah FY{car[1]} data Sectors (modal / ATMR)"
                                if car else None),
            "ldr_cap": ldr[0] if ldr else None,
            "ldr_cap_basis": (f"LDR tertinggi FY{ldr[1]} data Sectors (kredit bersih / DPK)"
                              if ldr else None)}


NO_LIMITS = {"car_floor": None, "car_floor_basis": None, "ldr_cap": None, "ldr_cap_basis": None}


def project(rows, official, balance, drivers, *, payout, payout_basis, shares=None,
            shares_basis=None, nci=None, nci_basis=None, constrain=True):
    """Five (or fewer) forecast years from the Bank Driver Scenario.

    ``drivers``: rows with ``year`` and the percent drivers; the first is the
    interim year (NIM, non-interest income ratio, CIR and cost of credit for
    H2; loan and deposit growth for the full year), then consecutive years.

    ``constrain`` holds the capital floor and funding cap of ``limits``: a
    year whose net loans would pass the LDR cap grows loans only as far as
    the cap allows; a year whose CAR would fall below the floor pays a lower
    dividend on the prior year's profit (the payout of that profit is cut),
    and when no dividend is left to cut (or it was already declared, the
    first year) its loan growth is capped instead. The payout on the last
    year's profit is tested on one more year at the last year's drivers.
    Every adjustment is listed in ``constraints["applied"]``.

    Returns {"rows", "anchor", "h2", "assumptions", "notes", "checks",
    "parameters", "constraints"} or None when the evidence does not support
    the model.
    """
    anchor = interim(rows, official, balance)
    if not anchor or not drivers or payout is None:
        return None
    p = _parameters(rows, anchor)
    base = p["base"]
    if not p["loan_share_ea"] or (not p["ldr"] and not all(
            _num(d.get("deposit_growth_pct")) is not None for d in drivers)):
        return None
    years = [int(d["year"]) for d in drivers]
    if years != list(range(anchor["year"], anchor["year"] + len(drivers))):
        raise ValueError("bank drivers must start at the interim year and be consecutive")
    tax_rate, share = anchor["tax_rate"], anchor["parent_share"]
    nci0 = _num(nci) or 0.0
    lim = limits(rows, base["year"]) if constrain else dict(NO_LIMITS)
    car_ok = p["capital_to_equity"] is not None and bool(p["rwa_per_loan"])
    floor = lim["car_floor"] if car_ok else None
    notes = {}

    # One shadow year at the last year's drivers tests the payout on the last
    # forecast year's profit, which is paid the year after; its row is dropped.
    run = list(drivers) + [dict(drivers[-1], year=years[-1] + 1)] if constrain else list(drivers)
    payouts = [payout] * len(run)  # payout on each year's parent profit
    paid_rate = payout  # on the base year's profit: declared, paid in the first year
    applied = []

    # Opening balances: the last fiscal year (Sectors).
    prev = {"gross_loan": base["gross_loan"], "earning_assets": base["non_loan_earning_assets"],
            "total_deposit": base["total_deposit"],
            "ibl": base["total_deposit"] + (base["other_interest_bearing_liabilities"] or 0.0),
            "parent_equity": base["total_equity"] - nci0, "nci": nci0,
            "total_equity": base["total_equity"], "total_assets": base["total_assets"],
            "earnings": base["earnings"]}
    out, h2 = [], None
    for i, d in enumerate(run):
        year = int(d["year"])
        label = f"FY{year % 100:02d}F"
        g = d["loan_growth_pct"] / 100
        nim, ratio = d["nim_pct"] / 100, d["non_ii_to_nii_pct"] / 100
        cir, coc = d["cost_to_income_pct"] / 100, d["cost_of_credit_pct"] / 100
        deposit_driver = _num(d.get("deposit_growth_pct")) is not None

        def deposits(gl):
            if deposit_driver:
                return prev["total_deposit"] * (1 + d["deposit_growth_pct"] / 100)
            return (gl - p["coverage"] * gl) / p["ldr"]

        def flows(ea, gl):
            """The year's income statement on year-end earning assets ``ea``."""
            loans_mid = anchor["loans_mid"] if anchor["loans_mid"] is not None else _avg(
                prev["gross_loan"], gl)
            if i == 0:
                ea_mid = anchor["earning_assets_mid"]
                if ea_mid is None:
                    ea_mid = _avg(prev["earning_assets"], ea)
                nii_h2 = nim * _avg(ea_mid, ea) / 2
                other_h2 = ratio * nii_h2
                income_h2 = nii_h2 + other_h2
                opex_h2 = cir * income_h2
                prov_h2 = coc * _avg(loans_mid, gl) / 2
                ebt_h2 = income_h2 - opex_h2 - prov_h2
                tax_h2 = max(ebt_h2, 0.0) * tax_rate
                net_h2 = ebt_h2 - tax_h2
                split = anchor["split"]
                half = {"net_interest_income": nii_h2, "other_income": other_h2,
                        "revenue": income_h2, "operating_expense": opex_h2,
                        "provision": prov_h2, "earnings_before_tax": ebt_h2, "tax": tax_h2,
                        "net_profit": net_h2, "net_profit_attributable": net_h2 * share,
                        "earning_assets_mid": ea_mid, "loans_mid": loans_mid}
                # Full-year averages over three balance dates (year-end, 30 June,
                # year-end), since the 1H actual earned on the mid-year book.
                return {"avg_ea": (prev["earning_assets"] / 2 + ea_mid + ea / 2) / 2,
                        "avg_gl": (prev["gross_loan"] / 2 + loans_mid + gl / 2) / 2,
                        "nii": anchor["net_interest_income"] + nii_h2,
                        "other": anchor["other_income"] + other_h2,
                        "opex": split["operating_expense"] + opex_h2,
                        "prov": split["provision"] + prov_h2,
                        "ebt": split["earnings_before_tax"] + ebt_h2,
                        "tax": split["tax"] + tax_h2, "net": anchor["net_profit"] + net_h2,
                        "parent": anchor["net_profit_attributable"] + net_h2 * share,
                        "h2": half}
            avg_ea, avg_gl = _avg(prev["earning_assets"], ea), _avg(prev["gross_loan"], gl)
            nii = nim * avg_ea
            other = ratio * nii
            opex = cir * (nii + other)
            prov = coc * avg_gl
            ebt = nii + other - opex - prov
            tax = max(ebt, 0.0) * tax_rate
            return {"avg_ea": avg_ea, "avg_gl": avg_gl, "nii": nii, "other": other,
                    "opex": opex, "prov": prov, "ebt": ebt, "tax": tax, "net": ebt - tax,
                    "parent": (ebt - tax) * share, "h2": None}

        def solve(gl, paid):
            """The year on gross loans ``gl`` and dividends paid ``paid``.

            Earning assets close the balance sheet: total assets = liabilities
            + equity, non-earning assets keep the base year's share of total
            assets, and placements and securities absorb what funding leaves
            after loans. Equity depends on this year's NII, so solve by fixed
            point (the feedback is a few percent per step; it converges in a
            handful).
            """
            allowance = p["coverage"] * gl
            dep = deposits(gl)
            oibl = (p["oibl_ratio"] or 0.0) * dep
            nibl = (p["nibl_ratio"] or 0.0) * dep
            liabilities = dep + oibl + nibl
            ea = gl / p["loan_share_ea"]
            for _ in range(100):
                f = flows(ea, gl)
                equity = (prev["parent_equity"] + f["parent"] - paid
                          + prev["nci"] + (f["net"] - f["parent"]))
                new_ea = (liabilities + equity) * (1 - p["non_earning_share"]) + allowance
                if abs(new_ea - ea) <= max(abs(ea) * 1e-12, 1.0):
                    ea = new_ea
                    break
                ea = new_ea
            f = flows(ea, gl)
            parent_equity = prev["parent_equity"] + f["parent"] - paid
            nci_now = prev["nci"] + (f["net"] - f["parent"])
            equity = parent_equity + nci_now
            return {"gl": gl, "allowance": allowance, "dep": dep, "oibl": oibl, "nibl": nibl,
                    "liabilities": liabilities, "ea": ea, "f": f, "paid": paid,
                    "parent_equity": parent_equity, "nci": nci_now, "equity": equity,
                    "assets": liabilities + equity}

        def need(s):
            """Total equity that holds the CAR floor on this loan book."""
            return floor * s["gl"] * p["rwa_per_loan"] / p["capital_to_equity"]

        gl = prev["gross_loan"] * (1 + g)
        if lim["ldr_cap"] and deposit_driver and \
                (gl - p["coverage"] * gl) / deposits(gl) > lim["ldr_cap"] + 1e-12:
            capped = lim["ldr_cap"] * deposits(gl) / (1 - p["coverage"])
            applied.append({"year": year, "label": label, "rule": "ldr_cap",
                            "lever": "loan_growth", "from_pct": g * 100,
                            "to_pct": (capped / prev["gross_loan"] - 1) * 100})
            gl = capped
        paid = paid_rate * max(prev["earnings"], 0.0) if prev["earnings"] is not None else 0.0
        s = solve(gl, paid)
        if floor:
            tol = lambda: max(abs(s["equity"]) * 1e-9, 1.0)
            if i > 0 and s["paid"] > 0 and s["equity"] < need(s) - tol():
                before = payouts[i - 1]
                for _ in range(60):
                    short = need(s) - s["equity"]
                    if short <= tol() or s["paid"] <= 0:
                        break
                    s = solve(gl, max(s["paid"] - short * 1.000001, 0.0))
                payouts[i - 1] = (s["paid"] / prev["earnings"]
                                  if prev["earnings"] and prev["earnings"] > 0 else 0.0)
                applied.append({"year": year - 1, "label": f"FY{(year - 1) % 100:02d}F",
                                "rule": "car_floor", "lever": "payout", "from_pct": before * 100,
                                "to_pct": payouts[i - 1] * 100, "tested_on": label})
            if s["equity"] < need(s) - tol():
                start = s["gl"]
                # The interim year's loans cannot fall below the official 30 June book.
                least = anchor["loans_mid"] if i == 0 and anchor["loans_mid"] else 0.0
                for _ in range(60):
                    most = max(s["equity"] * p["capital_to_equity"] / (floor * p["rwa_per_loan"]),
                               least)
                    if abs(most - s["gl"]) <= max(abs(most) * 1e-12, 1.0):
                        break
                    s = solve(most, s["paid"])
                applied.append({"year": year, "label": label, "rule": "car_floor",
                                "lever": "loan_growth",
                                "from_pct": (start / prev["gross_loan"] - 1) * 100,
                                "to_pct": (s["gl"] / prev["gross_loan"] - 1) * 100})
        paid_rate = payouts[i]
        f = s["f"]
        gl, allowance, dep, ea = s["gl"], s["allowance"], s["dep"], s["ea"]
        nii, other, opex, prov = f["nii"], f["other"], f["opex"], f["prov"]
        ebt, tax, net, parent = f["ebt"], f["tax"], f["net"], f["parent"]
        avg_ea, avg_gl = f["avg_ea"], f["avg_gl"]
        if i == 0:
            h2 = f["h2"]
        income = nii + other
        net_loan = gl - allowance
        parent_equity, nci_now, equity = s["parent_equity"], s["nci"], s["equity"]
        assets = s["assets"]
        non_earning = assets - net_loan - (ea - gl)
        ibl = dep + s["oibl"]
        row = {
            "year": year, "label": label,
            "revenue": income, "net_interest_income": nii, "non_interest_income": other,
            "operating_expense": opex, "ppop": income - opex, "provision": prov,
            "operating_pnl": ebt, "earnings_before_tax": ebt, "tax": tax, "net_cons": net,
            "minority": net - parent, "earnings": parent,
            "gross_loan": gl, "allowance_for_loans": allowance, "net_loan": net_loan,
            "non_loan_earning_assets": ea, "other_earning_assets": ea - gl,
            "non_earning_assets": non_earning, "total_assets": assets,
            "total_deposit": dep,
            "other_interest_bearing_liabilities": s["oibl"],
            "non_interest_bearing_liabilities": s["nibl"],
            "total_liabilities": s["liabilities"],
            "stockholders_equity": parent_equity, "non_controlling_interest": nci_now,
            "total_equity": equity, "dividends_paid": s["paid"],
            "net_interest_margin": nii / avg_ea, "cost_of_credit": prov / avg_gl,
            "average_earning_assets": avg_ea, "average_gross_loan": avg_gl,
            "cost_to_income": opex / income if income else None,
            "non_ii_to_nii": other / nii if nii else None,
            "loan_growth": gl / prev["gross_loan"] - 1,
            "deposit_growth": dep / prev["total_deposit"] - 1,
            "loan_to_deposit_ratio": net_loan / dep if dep else None,
            "roe": _div(parent, _avg(prev["parent_equity"], parent_equity)),
            "roaa": _div(parent, _avg(prev["total_assets"], assets)),
            "tax_rate": tax_rate,
            "drivers": {k: d.get(k) for k in DRIVERS + OPTIONAL_DRIVERS},
        }
        if p["ca_share"] is not None and p["sa_share"] is not None:
            row.update(current_account=p["ca_share"] * dep, savings_account=p["sa_share"] * dep,
                       time_deposit=(1 - p["ca_share"] - p["sa_share"]) * dep,
                       casa_ratio=p["ca_share"] + p["sa_share"])
        if p["cost_of_funds"] is not None:
            expense = p["cost_of_funds"] * _avg(prev["ibl"], ibl)
            row.update(interest_expense=expense, interest_income=nii + expense,
                       cost_of_funds=p["cost_of_funds"],
                       yield_on_earning_assets=(nii + expense) / avg_ea)
        if car_ok:
            capital, rwa = equity * p["capital_to_equity"], gl * p["rwa_per_loan"]
            row.update(total_capital=capital, total_risk_weighted_asset=rwa,
                       capital_adequacy_ratio=capital / rwa)
        out.append(row)
        prev = {"gross_loan": gl, "earning_assets": ea, "total_deposit": dep, "ibl": ibl,
                "parent_equity": parent_equity, "nci": nci_now, "total_equity": equity,
                "total_assets": assets, "earnings": parent}

    out = out[:len(drivers)]
    applied = [a for a in applied if a["year"] <= years[-1]]
    for row, rate in zip(out, payouts):
        row["payout"] = rate
        if shares:
            row.update(eps=row["earnings"] / shares,
                       dps=rate * max(row["earnings"], 0.0) / shares,
                       bvps=row["stockholders_equity"] / shares)
    constraints = {**lim, "applied": applied, "payouts": payouts[:len(drivers)],
                   "historical_payout": payout}
    notes.update(_notes(p, shares))
    return {"rows": out, "anchor": anchor, "h2": h2, "base_year": base["year"],
            "parameters": {k: v for k, v in p.items() if k != "base"},
            "constraints": constraints,
            "assumptions": _assumptions(anchor, p, base, drivers, payout, payout_basis,
                                        shares, shares_basis, nci0, nci_basis, constraints),
            "notes": notes, "checks": checks(out, anchor, h2, base, payout, rows, constraints)}


def terminal_payout(model, growth):
    """(payout, basis) for the DDM's terminal DPS on the bank model's path.

    In steady state a bank that grows its book at ``growth`` must retain
    growth / ROE of its profit to hold its capital ratio, so the sustainable
    payout is 1 - growth / ROE of the last forecast year, capped at the
    historical payout. None when the model has no ROE.
    """
    rows = (model or {}).get("rows") or []
    constraints = (model or {}).get("constraints") or {}
    historical = constraints.get("historical_payout")
    roe = _num(rows[-1].get("roe")) if rows else None
    if not roe or roe <= 0 or historical is None:
        return None, None
    sustainable = max(1 - growth / roe, 0.0)
    if sustainable >= historical:
        return historical, "payout historis (di bawah payout berkelanjutan 1 - g / ROE)"
    return sustainable, (f"payout berkelanjutan 1 - g / ROE {rows[-1]['label']} "
                         f"({_pct(growth)} / {_pct(roe)}), di bawah payout historis "
                         f"{_pct(historical)}")


def _notes(p, shares):
    """Reasons for lines the model leaves out."""
    notes = {}
    if p["cost_of_funds"] is None:
        why = ("Data Sectors tidak memuat beban bunga dan DPK dua tahun terakhir, sehingga biaya "
               "dana tidak dapat dihitung; model memproyeksikan NII langsung dari NIM tanpa "
               "memecah pendapatan dan beban bunga.")
        notes.update(dict.fromkeys(("interest_income", "interest_expense", "cost_of_funds",
                                    "yield_on_earning_assets"), why))
    if p["ca_share"] is None or p["sa_share"] is None:
        why = ("Data Sectors FY dasar tidak memisahkan giro dan tabungan, sehingga komposisi DPK "
               "dan rasio CASA tidak diproyeksikan.")
        notes.update(dict.fromkeys(("current_account", "savings_account", "time_deposit",
                                    "casa_ratio"), why))
    if p["capital_to_equity"] is None or not p["rwa_per_loan"]:
        why = ("Data Sectors FY dasar tidak memuat modal regulasi atau ATMR, sehingga CAR tidak "
               "dapat diproyeksikan.")
        notes.update(dict.fromkeys(("total_capital", "total_risk_weighted_asset",
                                    "capital_adequacy_ratio"), why))
    if not shares:
        notes.update(dict.fromkeys(("eps", "dps", "bvps"), "Jumlah saham tidak tersedia."))
    return notes


def checks(out, anchor, h2, base, payout, rows=None, constraints=None):
    """The model's invariants and warnings (S2.5, S2.8).

    Dividends paid in year t are the payout on year t-1's profit: the
    declared historical payout for the first year, then each row's own
    (possibly constrained) ``payout``.
    """
    problems, warnings = [], []
    tol = lambda x: max(abs(x) * 1e-9, 1.0)
    for r in out:
        if abs(r["total_assets"] - r["total_liabilities"] - r["total_equity"]) > tol(r["total_assets"]):
            problems.append(f"{r['label']}: total aset tidak sama dengan liabilitas + ekuitas")
        if r["other_earning_assets"] < 0:
            problems.append(f"{r['label']}: aset produktif selain kredit (penempatan dan surat "
                            f"berharga, pos penyeimbang) negatif ({_bn(r['other_earning_assets'])}); "
                            "DPK, liabilitas lain dan ekuitas tidak cukup mendanai kredit")
        if r["total_equity"] <= 0:
            problems.append(f"{r['label']}: ekuitas tidak positif")
    prev_equity, prev_parent, prev_payout = base["total_equity"], base["earnings"], payout
    for r in out:
        expected = prev_payout * max(prev_parent, 0.0)
        if abs(r["dividends_paid"] - expected) > tol(expected):
            problems.append(f"{r['label']}: dividen dibayar tidak sama dengan payout x laba induk "
                            "tahun sebelumnya")
        if abs(r["total_equity"] - prev_equity - (r["net_cons"] - r["dividends_paid"])) > \
                tol(r["total_equity"]):
            problems.append(f"{r['label']}: roll-forward ekuitas tidak cocok")
        prev_equity, prev_parent = r["total_equity"], r["earnings"]
        prev_payout = r.get("payout", payout)
    limit = constraints or {}
    floor, cap = limit.get("car_floor"), limit.get("ldr_cap")
    if floor:
        below = [f"{r['label']} {_pct(r['capital_adequacy_ratio'])}" for r in out
                 if r.get("capital_adequacy_ratio") is not None
                 and r["capital_adequacy_ratio"] < floor - 1e-6]
        if below:
            warnings.append(f"CAR screening di bawah batas modal ({_pct(floor)}, "
                            f"{limit.get('car_floor_basis')}): " + ", ".join(below)
                            + "; dividen atas laba FY dasar sudah diumumkan dan kredit tidak "
                            "diturunkan di bawah saldo 30 Juni resmi")
    if cap:
        above = [f"{r['label']} {_pct(r['loan_to_deposit_ratio'])}" for r in out
                 if r.get("loan_to_deposit_ratio") is not None
                 and r["loan_to_deposit_ratio"] > cap + 1e-6]
        if above:
            problems.append(f"LDR di atas batas pendanaan ({_pct(cap)}, "
                            f"{limit.get('ldr_cap_basis')}): " + ", ".join(above))
    first = out[0]
    for key, h1 in (("net_cons", anchor["net_profit"]),
                    ("earnings", anchor["net_profit_attributable"]),
                    ("net_interest_income", anchor["net_interest_income"])):
        h2_key = {"net_cons": "net_profit", "earnings": "net_profit_attributable"}.get(key, key)
        if abs(first[key] - h1 - h2[h2_key]) > tol(first[key]):
            problems.append(f"{first['label']}: {key} tidak sama dengan aktual "
                            f"{anchor['period']} + H2 model")
    past = [y for y in history(rows or []) if y["year"] <= base["year"]]
    for key, name in (("ldr", "LDR"), ("loan_share_ea", "porsi kredit dalam aset produktif")):
        record = [y["ratios"][key] for y in past if y["ratios"][key] is not None]
        field = "loan_to_deposit_ratio" if key == "ldr" else None
        values = [(r["label"], r[field] if field else _div(r["gross_loan"],
                                                           r["non_loan_earning_assets"]))
                  for r in out]
        above = [f"{label} {_pct(v)}" for label, v in values
                 if record and v is not None and v > max(record) + 1e-9]
        if above:
            warnings.append(f"{name} di atas rekor tertinggi historis data Sectors "
                            f"({_pct(max(record))}): " + ", ".join(above)
                            + "; kredit tumbuh lebih cepat dari pendanaan skenario")
    history_car = [y["ratios"]["car"] for y in past if y["ratios"]["car"]]
    cars = [(r["label"], r.get("capital_adequacy_ratio")) for r in out
            if r.get("capital_adequacy_ratio") is not None]
    if history_car and cars and not (constraints or {}).get("car_floor"):
        low = min(history_car)
        below = [f"{label} {_pct(car)}" for label, car in cars if car < low]
        if below:
            warnings.append("CAR screening di bawah CAR terendah historis data Sectors "
                            f"({_pct(low)}): " + ", ".join(below) + "; payout historis "
                            "menekan modal untuk pertumbuhan kredit skenario (S2.8)")
    return {"ok": not problems, "problems": problems, "warnings": warnings,
            "car_min": min((c for _, c in cars), default=None)}


def _assumptions(anchor, p, base, drivers, payout, payout_basis, shares, shares_basis, nci0,
                 nci_basis, constraints=None):
    y0, period = base["year"], anchor["period"]
    fy = f"FY{y0}"
    first = f"FY{anchor['year'] % 100:02d}F"
    out = [
        (f"Skenario analis (Bank Driver Scenario): per tahun pertumbuhan kredit bruto, NIM atas "
         "rata-rata aset produktif, pendapatan non-bunga terhadap NII, rasio biaya terhadap "
         f"pendapatan dan biaya kredit atas rata-rata kredit bruto; untuk {first} NIM, rasio "
         "non-bunga, CIR dan biaya kredit berlaku untuk H2, pertumbuhan kredit untuk setahun "
         f"penuh terhadap {fy}."),
        (f"Mekanika model: {first} = aktual {period} resmi (pendapatan, NII dan laba) + H2 "
         f"model; NII H2 = NIM H2 x rata-rata aset produktif 30 Juni dan akhir tahun / 2; aset "
         f"produktif 30 Juni = {anchor['earning_assets_mid_basis'] or 'rata-rata awal dan akhir tahun (total aset interim tidak dilaporkan)'}; "
         "provisi H2 = biaya kredit x rata-rata kredit 30 Juni "
         + ("resmi" if anchor["loans_mid"] is not None else "(rata-rata awal dan akhir tahun)")
         + f" dan akhir tahun / 2. NIM dan biaya kredit {first} setahun penuh dihitung atas "
         "rata-rata tiga saldo (akhir tahun lalu, 30 Juni, akhir tahun); tahun berikutnya atas "
         "rata-rata saldo awal dan akhir tahun."),
        (f"Asumsi screening: rilis {period} hanya memuat pendapatan, NII dan laba, sehingga beban "
         f"operasional, provisi dan pajak {period} dipecah dengan tarif pajak efektif dan "
         f"komposisi beban operasional : provisi {fy} ({_pct(anchor['split']['opex_share'])} : "
         f"{_pct(1 - anchor['split']['opex_share'])}); totalnya sama dengan laba {period} resmi."),
        ("Mekanika model: NII = NIM x rata-rata aset produktif awal dan akhir tahun; aset "
         "produktif = kredit bruto + aset produktif selain kredit (penempatan, surat berharga, "
         "obligasi pemerintah), dan yang terakhir adalah pos penyeimbang neraca (lihat total "
         f"aset); porsi kredit dalam aset produktif {fy} {_pct(p['loan_share_ea'])} menjadi "
         "titik awal perhitungan."),
        (f"Asumsi screening: cadangan kerugian kredit = cakupan cadangan terhadap kredit bruto {fy} "
         f"{_pct(p['coverage'])}, dijaga tetap; kredit bersih = kredit bruto - cadangan."
         if p["coverage_known"] else
         f"Asumsi screening: data Sectors {fy} tidak memuat cadangan kerugian kredit; kredit bersih "
         "= kredit bruto."),
        ("Asumsi screening: dana pihak ketiga = kredit bersih / LDR "
         f"{fy} {_pct(p['ldr'])} (kredit bersih / DPK, definisi data Sectors), dijaga tetap"
         + ("; tahun dengan pertumbuhan DPK dari skenario analis memakai angka itu"
            if any(_num(d.get("deposit_growth_pct")) is not None for d in drivers) else "")
         + (f"; giro {_pct(p['ca_share'])} dan tabungan {_pct(p['sa_share'])} dari DPK {fy} "
            "(CASA tetap)" if p["ca_share"] is not None and p["sa_share"] is not None else "")
         + "."),
        ("Asumsi screening: liabilitas berbunga lain "
         f"{_pct(p['oibl_ratio'] or 0.0)} dan liabilitas tanpa bunga {_pct(p['nibl_ratio'] or 0.0)} "
         f"dari DPK, rasio {fy} data Sectors dijaga tetap."),
        (f"Mekanika model: ekuitas induk = saldo akhir tahun sebelumnya + laba induk - dividen; "
         f"dividen tunai yang dibayar tahun t = payout x laba induk tahun t-1 (dividen final "
         f"sesudah RUPS; {first} memakai laba {fy} data Sectors); DPS tahun t = payout x EPS "
         f"tahun t (baris DPS DDM). Payout {_pct(payout)}, sumber {payout_basis or '-'}, dijaga "
         "tetap kecuali diturunkan oleh batas modal (lihat di bawah)."),
        (f"Mekanika model: kepentingan non-pengendali saldo awal {_bn(nci0)} "
         f"({nci_basis or 'tidak dilaporkan terpisah; ekuitas induk = total ekuitas'}) bertambah "
         f"dengan porsi laba non-pengendali ({_pct(1 - anchor['parent_share'])}, "
         f"{anchor['parent_share_basis']}); dividen ke NCI tidak dimodelkan."),
        ("Mekanika model: total aset = liabilitas + ekuitas; aset non-produktif (kas, aset tetap "
         f"dan aset lain) dijaga pada porsi {fy} {_pct(p['non_earning_share'])} dari total aset "
         "(screening); aset produktif selain kredit = total aset - kredit bersih - aset "
         "non-produktif adalah pos penyeimbang: pendanaan yang tidak dipakai kredit ditempatkan "
         "di sana, dan kredit yang tumbuh lebih cepat dari pendanaan menguranginya."),
        (f"Asumsi screening: pajak = {_pct(anchor['tax_rate'])} x laba sebelum pajak, "
         f"{anchor['tax_rate_basis']}; laba induk = {_pct(anchor['parent_share'])} laba "
         f"konsolidasi ({anchor['parent_share_basis']})."),
    ]
    if p["cost_of_funds"] is not None:
        out.append(f"Asumsi screening: biaya dana {fy} {_pct(p['cost_of_funds'])} (beban bunga / "
                   "rata-rata DPK + liabilitas berbunga lain, data Sectors) dijaga tetap; "
                   "beban bunga = biaya dana x rata-rata dana berbiaya; pendapatan bunga = NII + "
                   "beban bunga; imbal hasil aset produktif turunan, bukan driver.")
    if p["capital_to_equity"] is not None and p["rwa_per_loan"]:
        out.append(f"Asumsi screening: CAR = ekuitas x rasio modal regulasi terhadap ekuitas {fy} "
                   f"{fmt._id(p['capital_to_equity'], 2)}x / ATMR; ATMR = kredit bruto x rasio "
                   f"ATMR terhadap kredit bruto {fy} {_pct(p['rwa_per_loan'])} (kredit memikul "
                   "hampir seluruh bobot risiko; penempatan dan obligasi pemerintah hampir nol); "
                   "proksi kecukupan modal, bukan perhitungan regulasi.")
    out += _constraint_text(constraints or {}, first)
    if shares:
        out.append(f"Asumsi valuasi: jumlah saham {fmt._id(shares / 1e9, 2)} miliar lembar "
                   f"({shares_basis or 'sumber tidak tercatat'}), flat; EPS = laba induk, BVPS = "
                   "ekuitas induk per saham.")
    return out


def _constraint_text(constraints, first):
    """The capital floor and funding cap, and every year they bound."""
    floor, cap = constraints.get("car_floor"), constraints.get("ldr_cap")
    if not floor and not cap:
        return []
    rules = []
    if floor:
        rules.append(f"CAR screening tidak turun di bawah {_pct(floor)} "
                     f"({constraints.get('car_floor_basis')})")
    if cap:
        rules.append(f"LDR tidak melewati {_pct(cap)} ({constraints.get('ldr_cap_basis')})")
    text = [("Mekanika model (batas modal dan pendanaan): " + "; ".join(rules) + ". Tahun yang "
             "melanggar batas modal membayar dividen lebih kecil atas laba tahun sebelumnya "
             f"(payout laba tahun itu diturunkan); dividen atas laba FY dasar yang dibayar {first} "
             "sudah diumumkan, sehingga pada tahun itu, atau bila tidak ada dividen tersisa, "
             "pertumbuhan kredit yang dibatasi. Tahun yang melewati batas pendanaan menumbuhkan "
             "kredit hanya sampai batas LDR. Payout atas laba tahun terakhir diuji pada satu tahun "
             "tambahan dengan driver tahun terakhir.")]
    applied = constraints.get("applied") or []
    if not applied:
        text.append("Batas modal dan pendanaan tidak mengikat pada tahun forecast mana pun; "
                    "driver analis dan payout historis dipakai apa adanya.")
    for a in applied:
        if a["lever"] == "payout":
            text.append(f"Batas modal mengikat: payout atas laba {a['label']} diturunkan dari "
                        f"{fmt._id(a['from_pct'], 1)}% ke {fmt._id(a['to_pct'], 1)}% agar CAR "
                        f"{a['tested_on']} tidak di bawah batas.")
        else:
            why = "batas modal" if a["rule"] == "car_floor" else "batas pendanaan (LDR)"
            text.append(f"{why[0].upper()}{why[1:]} mengikat: pertumbuhan kredit bruto "
                        f"{a['label']} dibatasi dari {fmt._id(a['from_pct'], 1)}% ke "
                        f"{fmt._id(a['to_pct'], 1)}%; dana yang tidak disalurkan ditempatkan "
                        "di aset produktif lain.")
    return text
