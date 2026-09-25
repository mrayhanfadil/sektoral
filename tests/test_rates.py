"""Dated UST 10Y yield series (app.rates) and its refresh step."""
from datetime import date, timedelta

import pandas as pd
import pytest

from app import rates, refresh, store


class _Ticker:
    def __init__(self, closes):
        self.closes = closes

    def history(self, period, auto_adjust):
        index = pd.to_datetime(list(self.closes))
        return pd.DataFrame({"Close": list(self.closes.values())}, index=index)


def _series(rows):
    return {"name": rates.UST10Y, "symbol": "^TNX", "unit": "percent",
            "source": "Yahoo Finance ^TNX daily close (imbal hasil US Treasury 10 tahun)",
            "fetched_at": "2026-09-25", "rows": rows}


def test_fetch_keeps_completed_sessions_as_percent_yields():
    today = date.today()
    closes = {(today - timedelta(days=2)).isoformat(): 4.95, (today - timedelta(days=1)).isoformat(): 5.162,
              today.isoformat(): 5.30, (today - timedelta(days=3)).isoformat(): float("nan")}
    data = rates.fetch(ticker_factory=lambda symbol: _Ticker(closes))
    assert data["symbol"] == "^TNX" and data["source"].startswith("Yahoo Finance ^TNX")
    # Today's bar is still trading; NaN closes are dropped.
    assert [r["yield_pct"] for r in data["rows"]] == [4.95, 5.162]


def test_the_report_reads_the_last_close_on_or_before_its_date():
    store.put(rates.COLLECTION, rates.UST10Y, _series([
        {"date": "2026-09-21", "yield_pct": 4.963}, {"date": "2026-09-24", "yield_pct": 5.162},
        {"date": "2026-09-25", "yield_pct": 5.2}]))
    quote = rates.on_or_before("2026-09-24")
    assert quote["rate"] == pytest.approx(0.05162) and quote["date"] == "2026-09-24"
    assert rates.on_or_before("2026-09-23")["date"] == "2026-09-21"
    # A close more than a week old is stale; nothing before the series is missing.
    assert rates.on_or_before("2026-10-10") is None
    assert rates.on_or_before("2026-09-01") is None


def test_a_malformed_series_is_not_read():
    store.put(rates.COLLECTION, rates.UST10Y, _series([{"date": "2026-09-24", "yield_pct": 51.6}]))
    assert rates.load() is None and rates.on_or_before("2026-09-24") is None


def test_a_failed_refresh_leaves_the_stored_series():
    store.put(rates.COLLECTION, rates.UST10Y, _series([{"date": "2026-09-24", "yield_pct": 5.162}]))

    def boom(_name):
        raise RuntimeError("Yahoo down")

    result = rates.refresh(fetcher=boom)
    assert result["failed"] == {rates.UST10Y: "RuntimeError: Yahoo down"}
    assert rates.on_or_before("2026-09-24")["rate"] == pytest.approx(0.05162)


def test_refresh_command_has_a_rates_step(monkeypatch):
    assert refresh.STEPS.index("rates") == 1
    monkeypatch.setattr(rates, "refresh", lambda: {"stored": {rates.UST10Y: _series(
        [{"date": "2026-09-24", "yield_pct": 5.162}])}, "failed": {}})
    out = refresh.RUNNERS["rates"](["GMFI"], "2026-09-24")
    assert out == {"stored": {"UST10Y": "5.162% (2026-09-24)"}, "failed": {}}
