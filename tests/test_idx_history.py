"""IDX price history: continuous tail, closes before publication, labelled IDX."""
import json

from app import idx_history, render
from app import report_extras as X
from app import intake as I


def test_load_keeps_the_continuous_tail_before_the_report_date(tmp_path, monkeypatch):
    monkeypatch.setattr(idx_history, "ROOT", tmp_path)
    obs = ([{"date": "2024-07-22", "close": 1}, {"date": "2024-07-23", "close": 2}] +
           [{"date": f"2025-09-{d:02d}", "close": 10 + d} for d in range(22, 27)])
    (tmp_path / "TEST.json").write_text(json.dumps({"ticker": "TEST", "observations": obs}))
    loaded = idx_history.load("TEST", "2025-09-26")
    assert [d.isoformat() for d, _ in loaded["points"]] == [
        "2025-09-22", "2025-09-23", "2025-09-24", "2025-09-25"]


def test_cover_chart_uses_24_months_of_idx_prices_and_says_so():
    # The footer is the house line; the data source goes to the source appendix.
    notes = []
    token = render._NOTES.set(notes)
    try:
        chart = render._price_chart("JPFA", "2026-09-24", number=1)
    finally:
        render._NOTES.reset(token)
    assert "(24M," in chart and "Source: Company, Sektoral Estimates</p>" in chart
    assert "IDX" in notes[0][2] and "Sectors" not in notes[0][2]
    window = render._price_window("JPFA", "2026-09-24")
    assert (window["price_dates"][-1] - window["price_dates"][0]).days > 540
    assert window["rel_dates"][0] >= window["price_dates"][0]


def test_band_covers_a_year_of_idx_closes():
    doc_in, _ = I.load("JPFA", as_of="2026-09-24")
    data = X._band_data(doc_in)
    assert data["window"] == "12 bulan" and "IDX" in data["source"]
    # FY2025 was published inside the window, so the base changes.
    assert not data["multiples"]["P/E"]["constant_base"]


def test_sido_has_24_months_of_idx_closes_for_the_cover_chart_and_band():
    # SIDO's Sectors cache holds ~3 months; the IDX file carries the same
    # 24-month window as the other issuers, labelled IDX.
    loaded = idx_history.load("SIDO", "2026-09-25")
    assert "IDX" in loaded["source_title"] and loaded["source_url"].startswith("https://www.idx.co.id/")
    assert loaded["retrieved_at"] == "2026-09-25"
    assert loaded["points"][0][0].isoformat() == "2024-07-22"
    assert loaded["points"][-1][0].isoformat() == "2026-09-24" and loaded["points"][-1][1] == 350.0
    window = render._price_window("SIDO", "2026-09-25")
    assert (window["rel_dates"][-1] - window["rel_dates"][0]).days >= 365
    assert "IDX" in window["source"]
    doc_in, _ = I.load("SIDO", as_of="2026-09-25")
    data = X._band_data(doc_in)
    assert data["window"] == "12 bulan" and "IDX" in data["source"]
    assert set(data["multiples"]) >= {"P/E", "P/BV"}
