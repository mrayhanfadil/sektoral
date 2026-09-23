"""Chart comparison uses the same trading dates and a common base."""
from datetime import date

import pytest

from app import render


def test_issuer_vs_ihsg_uses_common_dates_and_latest_cached_values(monkeypatch):
    def payloads(endpoint):
        if endpoint == "/daily/TEST/":
            return [
                ("older", {"data": [
                    {"date": "2026-01-02", "close": 100},
                    {"date": "2026-01-03", "close": 200},
                    {"date": "2026-01-04", "close": 300},
                ]}),
                ("newer", {"data": [{"date": "2026-01-04", "close": 400}]}),
            ]
        if endpoint == "/index-daily/ihsg/":
            return [("index", {"data": [
                {"date": "2026-01-02", "price": 1000},
                {"date": "2026-01-04", "price": 1100},
                {"date": "2026-01-05", "price": 1200},
            ]})]
        raise AssertionError(endpoint)

    monkeypatch.setattr(render.cache_mod, "payloads", payloads)

    dates, issuer, ihsg = render._comparison_series("TEST", "2026-01-04")
    assert dates == [date(2026, 1, 2), date(2026, 1, 4)]
    assert issuer == pytest.approx([100, 400])
    assert ihsg == pytest.approx([100, 110])

    chart = render._price_chart("TEST", "2026-01-04")
    assert "TEST +300,0%" in chart
    assert "IHSG +10,0%" in chart
    assert "Selisih +290,0 poin persentase" in chart
    assert "2026-01-02 - 2026-01-04" in chart


def test_comparison_requires_two_shared_trading_dates(monkeypatch):
    def payloads(endpoint):
        if endpoint == "/daily/TEST/":
            return [("issuer", {"data": [
                {"date": "2026-01-02", "close": 100},
                {"date": "2026-01-03", "close": 110},
            ]})]
        return [("index", {"data": [{"date": "2026-01-03", "price": 1000}]})]

    monkeypatch.setattr(render.cache_mod, "payloads", payloads)

    assert render._comparison_series("TEST", "2026-01-04") is None
    assert "kurang dari dua tanggal perdagangan" in render._price_chart("TEST", "2026-01-04")


def test_stacked_report_layout_keeps_wide_evidence_tables_full_width():
    section = {
        "halaman": 2,
        "layout": "stack",
        "paragraf": ["Evidence first."],
        "exhibit": [
            {"n": 1, "judul": "Forecast", "tipe": "tabel",
             "data": {"cols": ["Metric", "2026F"], "rows": [["Revenue", "100"]]},
             "catatan_sumber": "Source A"},
            {"n": 2, "judul": "Operations", "tipe": "tabel",
             "data": {"cols": ["Claim", "Value", "Period", "Source"],
                      "rows": [["Ore mined", "38", "1Q26", "Report p. 1"]]},
             "catatan_sumber": "Source B"},
        ],
    }

    rendered = render._render_page_content(section)

    assert "grid-2" not in rendered
    assert rendered.index("Evidence first.") < rendered.index("Forecast")
    assert rendered.index("Forecast") < rendered.index("Operations")
