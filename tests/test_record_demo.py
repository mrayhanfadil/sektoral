from __future__ import annotations

import pytest

from scripts.record_demo import normalize_ticker


@pytest.mark.parametrize(("value", "expected"), [
    ("ammn", "AMMN"),
    (" brms ", "BRMS"),
    ("A.B-1", "A.B-1"),
])
def test_record_demo_normalizes_valid_tickers(value, expected):
    assert normalize_ticker(value) == expected


@pytest.mark.parametrize("value", ["", "../secret", "A/B", "TOO-LONG-TICKER"])
def test_record_demo_rejects_invalid_tickers(value):
    with pytest.raises(ValueError):
        normalize_ticker(value)
