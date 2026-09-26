"""Terminal growth must agree with reinvestment, returns, retention and currency."""
import pytest

from app import terminal_economics as T

BENCH = {"growth": {"as_of": "2026-04-14", "short_source": "IMF WEO Apr 2026",
                    "IDR": {"year": 2031, "real": 0.052, "inflation": 0.025},
                    "USD": {"year": 2031, "real": 0.018, "inflation": 0.022}}}


def _line(nopat, capex, da, dnwc, fcff):
    return {"nopat": nopat, "capex": capex, "da": da, "dnwc": dnwc, "fcff": fcff}


def _dcf(g=0.035, terminal_fcff=None, lines=None, currency="IDR"):
    lines = lines or [_line(100, 30, 20, 5, 85)] * 5
    last = lines[-1]
    return {"g": g, "wacc": 0.11, "rf": 0.065, "currency": currency, "lines": lines,
            "terminal_fcff": terminal_fcff if terminal_fcff is not None else last["fcff"] * (1 + g)}


def test_nominal_gdp_growth_comes_from_the_dated_benchmark_only():
    value, basis = T.long_run_nominal_growth(BENCH, "IDR", "2026-09-26")
    assert value == pytest.approx(1.052 * 1.025 - 1) and "IMF" in basis
    assert T.long_run_nominal_growth(BENCH, "IDR", "2026-01-01") == (None, None)


def test_consistent_reinvestment_passes_and_reports_the_implied_return():
    # Terminal: NOPAT 103.5, FCFF 87.975 -> reinvestment 15% -> RONIC 3.5% / 15% = 23%.
    record = T.fcff(_dcf(), invested_capital=400, benchmarks=BENCH, as_of="2026-09-26",
                    cash_currency="IDR")
    measures = record["measures"]
    assert measures["reinvestment_rate"] == pytest.approx(0.15)
    assert measures["implied_ronic"] == pytest.approx(0.035 / 0.15)
    # Explicit ROIC: 100 / (400 + 4 x 15) = 21.7% < 23.3% implied -> inconsistent.
    assert measures["explicit_roic"] == pytest.approx(100 / 460)
    assert record["status"] == "inconsistent"
    assert any("ROIC periode eksplisit" in b for b in record["blockers"])
    looser = T.fcff(_dcf(), invested_capital=300, benchmarks=BENCH, as_of="2026-09-26",
                    cash_currency="IDR")
    assert looser["status"] == "consistent" and looser["blockers"] == []


def test_growth_without_net_reinvestment_is_inconsistent():
    lines = [_line(100, 20, 20, 0, 100)] * 5
    record = T.fcff(_dcf(lines=lines), invested_capital=None, benchmarks=BENCH,
                    as_of="2026-09-26", cash_currency="IDR")
    assert record["measures"]["reinvestment_rate"] == pytest.approx(0.0)
    assert any("reinvestasi neto positif" in b for b in record["blockers"])
    assert "dua kali WACC" in record["notes"][0]


def test_growth_above_the_risk_free_rate_or_nominal_gdp_or_in_another_currency_fails():
    high = T.fcff(_dcf(g=0.07), invested_capital=300, benchmarks=BENCH, as_of="2026-09-26",
                  cash_currency="IDR")
    names = {c["name"] for c in high["checks"] if not c["ok"]}
    assert "g_not_above_rf" in names
    usd = T.fcff(_dcf(g=0.045, currency="USD"), invested_capital=300, benchmarks=BENCH,
                 as_of="2026-09-26", cash_currency="USD")
    assert "g_not_above_nominal_gdp" in {c["name"] for c in usd["checks"] if not c["ok"]}
    mixed = T.fcff(_dcf(currency="IDR"), invested_capital=300, benchmarks=BENCH,
                   as_of="2026-09-26", cash_currency="USD")
    assert "currency" in {c["name"] for c in mixed["checks"] if not c["ok"]}


def test_bank_growth_is_bounded_by_retained_earnings():
    detail = {"g": 0.035, "coe": 0.11, "terminal_payout": 0.6, "payout": 0.6}
    ok = T.ddm(detail, [{"roe": 0.18}], BENCH, "2026-09-26", "IDR", "IDR", rf=0.065)
    assert ok["status"] == "consistent"
    assert ok["measures"]["sustainable_growth"] == pytest.approx(0.4 * 0.18)
    tight = T.ddm({**detail, "terminal_payout": 0.85}, [{"roe": 0.18}], BENCH, "2026-09-26",
                  "IDR", "IDR", rf=0.065)
    assert tight["status"] == "inconsistent"
    assert tight["measures"]["payout_for_g"] == pytest.approx(1 - 0.035 / 0.18)


def test_finite_life_has_no_perpetuity_to_reconcile():
    assert T.finite_life()["status"] == "not_applicable"


def test_the_per_share_effect_of_a_consistent_terminal_is_estimated():
    detail = {**_dcf(lines=[_line(100, 20, 20, 0, 100)] * 5), "pv_tv": 1000.0, "shares": 10,
              "attributable_share": 1.0}
    record = T.fcff(detail, invested_capital=300, benchmarks=BENCH, as_of="2026-09-26",
                    cash_currency="IDR")
    ratio = record["measures"]["terminal_value_ratio"]
    assert ratio < 1
    assert record["measures"]["per_share_effect_idr"] == pytest.approx((ratio - 1) * 100)
    assert T.not_applicable("SOTP")["status"] == "not_applicable"
