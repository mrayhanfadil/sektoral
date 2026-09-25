"""Tests for explicit USD/IDR refresh and cache behavior."""
import pytest

from app import fx, store


def quote(rate=16_250.5):
    return {
        "pair": "USD/IDR",
        "rate": rate,
        "date": "2026-09-23",
        "source": "Yahoo Finance IDR=X daily close",
    }


def test_refresh_persists_yfinance_rate_and_loads_it(tmp_path):
    fetched = quote()

    saved = fx.refresh_usd_idr(db=tmp_path, fetcher=lambda: fetched)

    assert saved == fetched
    assert store.get(fx.COLLECTION, fx.KEY, tmp_path) == fetched
    assert fx.load_cached_rate(db=tmp_path) == fetched


def test_invalid_or_missing_cache_is_not_used(tmp_path):
    assert fx.load_cached_rate(db=tmp_path) is None
    store.put(fx.COLLECTION, fx.KEY, {"pair": "USD/IDR", "rate": 0, "date": "2026-09-23",
                                      "source": "bad"}, tmp_path)
    assert fx.load_cached_rate(db=tmp_path) is None


def test_refresh_refuses_empty_or_invalid_rate(tmp_path):
    with pytest.raises(ValueError, match="valid USD/IDR"):
        fx.refresh_usd_idr(db=tmp_path, fetcher=lambda: None)


def test_fetch_reads_yahoo_idr_per_usd_close():
    import pandas as pd

    class FakeTicker:
        def __init__(self, symbol):
            assert symbol == "IDR=X"

        def history(self, **kwargs):
            assert kwargs == {"period": "5d", "auto_adjust": False}
            return pd.DataFrame(
                {"Close": [16_200.0, 16_250.5]},
                index=pd.to_datetime(["2026-09-22", "2026-09-23"]),
            )

    assert fx.fetch_usd_idr(ticker_factory=FakeTicker) == quote()
