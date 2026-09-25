"""Policy-vs-benchmark discount-rate table (app.rate_benchmarks, plan 2.1)."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import rate_benchmarks as R  # noqa: E402

DATA = {
    "rf_idr": {"value": 0.07, "label": "penutupan 23 September 2026", "as_of": "2026-09-23",
               "source_title": "Investing.com", "short_source": "Investing.com, 23 Sep 2026"},
    "erp": {"value": 0.0423, "label": "implied ERP", "as_of": "2026-01-05",
            "source_title": "Damodaran ERP", "short_source": "Damodaran, Jan 2026"},
    "crp": {"value": 0.0246, "default_spread": 0.0162, "label": "CRP Baa2",
            "as_of": "2026-01-05", "source_title": "Damodaran CRP",
            "short_source": "Damodaran, 5 Jan 2026"},
    "growth": {"as_of": "2026-04-14", "source_title": "IMF WEO", "short_source": "IMF WEO",
               "IDR": {"country": "Indonesia", "year": 2031, "real": 0.052, "inflation": 0.025},
               "USD": {"country": "AS", "year": 2031, "real": 0.018, "inflation": 0.022}},
}


def _series(betas, weeks=80, start=date(2024, 7, 1)):
    """Daily points (Mon-Fri) where the stock's weekly return = beta x index's."""
    index, stock, points_i, points_s = 1000.0, 100.0, [], []
    day = start
    for w in range(weeks):
        move = 0.02 if w % 2 else -0.015
        index *= 1 + move
        stock *= 1 + betas * move
        for d in range(5):
            points_i.append((day + timedelta(days=d), index))
            points_s.append((day + timedelta(days=d), stock))
        day += timedelta(days=7)
    return points_s, points_i


@pytest.fixture
def history(monkeypatch):
    stock, index = _series(0.8)

    def load(symbol, as_of=None):
        pts = index if symbol == "IHSG" else stock
        cut = date.fromisoformat(str(as_of)[:10]) if as_of else None
        pts = [p for p in pts if cut is None or p[0] < cut]
        return {"points": pts, "source_title": f"IDX {symbol}"}
    monkeypatch.setattr(R.idx_history, "load", load)


def _va(currency="IDR", g=0.035):
    detail = {"rf": 0.065, "erp": 0.04, "beta": 1.1, "g": g}
    if currency == "USD":
        detail = {"rf": 0.05, "crp": 0.025, "erp": 0.04, "beta": 1.1, "g": 0.03,
                  "currency": "USD"}
    return {"wacc_inputs": {"rf": 0.065, "erp": 0.04, "beta": 1.1, "g": 0.035},
            "method_chain": {"trace": [{"decision": "selected", "short": "DCF",
                                        "detail": detail}]}}


def test_beta_is_the_weekly_regression_on_ihsg_with_blume_adjustment(history):
    b = R.beta("UJI", "2026-09-24")
    assert b["raw"] == pytest.approx(0.8, abs=1e-9)
    assert b["adjusted"] == pytest.approx(0.67 * 0.8 + 0.33)
    assert b["weeks"] == 79
    assert R.beta("UJI", "2024-10-01") is None  # under a year of weeks


def test_rupiah_model_uses_the_local_currency_build(history):
    e = R.exhibit("UJI", "2026-09-24", _va(), DATA)
    rows = {r[0]: r for r in e["data"]["rows"]}
    assert e["data"]["cols"] == ["Parameter", "Kebijakan", "Pembanding", "Sumber, tanggal"]
    assert "5,38% bebas risiko rupiah" in rows["Risk-free (INDOGB 10Y)"][2]
    assert "6,69% ERP total Indonesia" in rows["Equity risk premium (tanpa CRP terpisah)"][2]
    assert "7,8% PDB nominal Indonesia 2031" in rows["Pertumbuhan terminal g (Rp)"][2]
    coe = (0.07 - 0.0162) + (0.67 * 0.8 + 0.33) * (0.0423 + 0.0246)
    assert rows["Cost of equity (CAPM)"][1] == "10,9%"
    assert rows["Cost of equity (CAPM)"][2].startswith(f"{coe * 100:.1f}".replace(".", ",") + "%")
    assert all(len(r) == 4 and r[3] for r in e["data"]["rows"])


def test_dollar_model_shows_the_country_risk_premium_and_mature_erp(history):
    e = R.exhibit("UJI", "2026-09-24", _va("USD"), DATA)
    labels = [r[0] for r in e["data"]["rows"]]
    assert "Country risk premium Indonesia" in labels
    assert "Equity risk premium (mature market)" in labels
    assert "Pertumbuhan terminal g (US$)" in labels


def test_a_benchmark_dated_after_the_report_is_left_out(history):
    e = R.exhibit("UJI", "2026-06-30", _va(), DATA)
    rf = next(r for r in e["data"]["rows"] if r[0].startswith("Risk-free"))
    assert rf[2] == "tidak tersedia pada tanggal laporan"


def test_no_terminal_row_without_a_terminal_growth(history):
    va = _va()
    va["method_chain"]["trace"][0]["detail"].pop("g")
    va["method_chain"]["trace"][0]["detail"] = {"lom": {"discount_build": {
        "rf": 0.05, "crp": 0.025, "erp": 0.04, "beta": 1.1}}}
    e = R.exhibit("UJI", "2026-09-24", va, DATA)
    assert not any(r[0].startswith("Pertumbuhan terminal") for r in e["data"]["rows"])
