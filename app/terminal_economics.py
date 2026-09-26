"""Terminal economics: does the perpetuity agree with its own growth, reinvestment and capital?

One check per Model Profile, each under that profile's economic identity
(plan §5.5), on the valuation detail the model already produced:

- ``going_concern_fcff``: sustainable growth needs net reinvestment. The
  terminal reinvestment rate is ``1 - FCFF / NOPAT`` of the terminal year and
  the implied return on new invested capital is ``g / reinvestment rate``.
  It must be positive when ``g`` is, and not above the return the explicit
  forecast earns on its capital (or twice the WACC when that is unknown):
  excess returns fade in perpetuity, they do not rise.
- ``financial_ddm``: equity grows only from retained earnings, so ``g`` may not
  exceed ``(1 - terminal payout) x terminal ROE``.
- ``finite_life_mining``: the LoM has no perpetuity; nothing to reconcile.

Every profile also checks the rate itself: the discount rate and cash flows
share one currency, and ``g`` is below the discount rate, the nominal
risk-free rate and the dated long-run nominal GDP growth of that currency.
"""
from __future__ import annotations

from datetime import date

RONIC_CEILING_WITHOUT_ROIC = 2.0   # x WACC, when explicit-period ROIC is unknown
TOLERANCE = 1e-6


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _check(name, ok, value, bound, text):
    return {"name": name, "ok": bool(ok), "value": value, "bound": bound, "text": text}


def long_run_nominal_growth(benchmarks, currency, as_of):
    """(1 + real) x (1 + inflation) - 1 from the dated growth benchmark, or None."""
    entry = (benchmarks or {}).get("growth") or {}
    try:
        dated = date.fromisoformat(str(entry.get("as_of"))[:10]) <= date.fromisoformat(str(as_of)[:10])
    except ValueError:
        dated = False
    row = entry.get(currency) if dated else None
    if not isinstance(row, dict) or _num(row.get("real")) is None or _num(row.get("inflation")) is None:
        return None, None
    return ((1 + row["real"]) * (1 + row["inflation"]) - 1,
            f"{entry.get('short_source') or entry.get('source_title')}, {row.get('year')}")


def _rate_checks(g, rate, rf, currency, cash_currency, benchmarks, as_of, rate_name):
    checks = [
        _check("currency", currency == cash_currency, currency, cash_currency,
               "tingkat diskonto dan arus kas dalam mata uang yang sama"),
        _check("g_below_rate", g < rate, g, rate, f"g di bawah {rate_name}"),
    ]
    if _num(rf) is not None:
        checks.append(_check("g_not_above_rf", g <= rf + TOLERANCE, g, rf,
                             "g tidak melebihi suku bunga bebas risiko nominal"))
    nominal, basis = long_run_nominal_growth(benchmarks, currency, as_of)
    if nominal is not None:
        checks.append(_check("g_not_above_nominal_gdp", g <= nominal + TOLERANCE, g, nominal,
                             f"g tidak melebihi pertumbuhan PDB nominal jangka panjang ({basis})"))
    return checks


def _result(profile, checks, measures, notes=()):
    failed = [c for c in checks if not c["ok"]]
    return {"profile": profile,
            "status": "consistent" if not failed else "inconsistent",
            "checks": checks, "measures": measures, "notes": list(notes),
            "blockers": [f"ekonomi terminal: {c['text']} tidak terpenuhi" for c in failed]}


def fcff(detail, invested_capital, benchmarks, as_of, cash_currency):
    """Going-concern FCFF DCF (``scenario_value.fcff`` detail, model currency)."""
    view = detail.get("native") or detail
    lines = view.get("lines") or []
    g, wacc = _num(detail.get("g")), _num(detail.get("wacc"))
    if not lines or g is None or wacc is None or _num(view.get("terminal_fcff")) is None:
        return {"profile": "going_concern_fcff", "status": "not_assessed",
                "reason": "DCF skenario tidak tersedia", "checks": [], "blockers": []}
    last = lines[-1]
    nopat = last["nopat"] * (1 + g)
    terminal_fcff = view["terminal_fcff"]
    reinvestment = nopat - terminal_fcff
    rate = reinvestment / nopat if nopat > 0 else None
    ronic = g / rate if rate and rate > 0 else None
    roic = None
    if _num(invested_capital) and invested_capital > 0:
        capital = invested_capital + sum(l["capex"] - l["da"] + l["dnwc"] for l in lines[:-1])
        roic = last["nopat"] / capital if capital > 0 else None
    ceiling = max(roic, wacc) if roic is not None else RONIC_CEILING_WITHOUT_ROIC * wacc
    checks = _rate_checks(g, wacc, detail.get("rf"), detail.get("currency"), cash_currency,
                          benchmarks, as_of, "WACC")
    if g > 0:
        checks.append(_check("reinvestment_for_growth", rate is not None and rate > 0, rate, 0.0,
                             "pertumbuhan terminal disertai reinvestasi neto positif"))
        if ronic is not None:
            checks.append(_check("ronic_not_above_explicit", ronic <= ceiling + TOLERANCE, ronic,
                                 ceiling, "imbal hasil modal baru implisit tidak melebihi "
                                 + ("ROIC periode eksplisit" if roic is not None
                                    else "dua kali WACC")))
    consistent_fcff = nopat * (1 - g / ceiling) if ceiling > 0 else None
    measures = {"g": g, "wacc": wacc, "terminal_nopat": nopat, "terminal_fcff": terminal_fcff,
                "reinvestment_rate": rate, "implied_ronic": ronic, "explicit_roic": roic,
                "ronic_ceiling": ceiling,
                "consistent_terminal_fcff": consistent_fcff,
                "terminal_value_ratio": (consistent_fcff / terminal_fcff
                                         if consistent_fcff and terminal_fcff > 0 else None)}
    notes = []
    if roic is None:
        notes.append("modal diinvestasikan tidak tersedia; batas RONIC memakai dua kali WACC")
    return _result("going_concern_fcff", checks, measures, notes)


def ddm(detail, bank_rows, benchmarks, as_of, cash_currency, currency, rf=None):
    """Bank DDM (``scenario_value.ddm`` detail): growth from retained earnings only."""
    g, coe = _num(detail.get("g")), _num(detail.get("coe"))
    if g is None or coe is None:
        return {"profile": "financial_ddm", "status": "not_assessed",
                "reason": "DDM skenario tidak tersedia", "checks": [], "blockers": []}
    last = (bank_rows or [None])[-1] or {}
    roe = _num(last.get("roe")) if last else None
    roe = roe if roe is not None else _num(detail.get("roe"))
    payout = _num(detail.get("terminal_payout"))
    payout = payout if payout is not None else _num(last.get("payout"))
    payout = payout if payout is not None else _num(detail.get("payout"))
    checks = _rate_checks(g, coe, rf, currency, cash_currency, benchmarks, as_of,
                          "Cost of Equity")
    sustainable = (1 - payout) * roe if roe is not None and payout is not None else None
    if sustainable is not None:
        checks.append(_check("growth_from_retention", g <= sustainable + TOLERANCE, g, sustainable,
                             "g tidak melebihi laba ditahan x ROE terminal"))
    measures = {"g": g, "coe": coe, "terminal_roe": roe, "terminal_payout": payout,
                "sustainable_growth": sustainable,
                "payout_for_g": 1 - g / roe if roe else None}
    notes = [] if sustainable is not None else ["ROE atau payout terminal tidak tersedia"]
    return _result("financial_ddm", checks, measures, notes)


def finite_life():
    return {"profile": "finite_life_mining", "status": "not_applicable", "checks": [],
            "measures": {}, "blockers": [],
            "notes": ["umur tambang terbatas; tanpa nilai terminal abadi"]}
