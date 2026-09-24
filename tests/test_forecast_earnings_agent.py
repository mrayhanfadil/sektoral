"""Earnings subagent validation (going concern / bank, §4.1a)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.forecast_assumptions import run as agent  # noqa: E402

OFFICIAL = {"source_url": "https://issuer.example/1h26.pdf", "published_at": "2026-08-20",
            "period": "1H26", "period_end": "2026-06-30", "guidance": [],
            "metrics": {"revenue": 100.0, "net_profit": 10.0}}


def _source(profile="going_concern_fcff", official=OFFICIAL, news=1):
    return {"ticker": "UJI", "as_of": "2026-09-24", "model_profile": profile,
            "official": official,
            "news": [{"index": i, "title": f"t{i}", "timestamp": "2026-09-01",
                      "url": f"https://news.example/{i}"} for i in range(news)]}


def _scenario(**kw):
    base = {"h2_revenue_to_h1": 1.05, "h2_net_margin_pct": 11.0,
            "rationale": "Kinerja H2 mengikuti pola musiman tahun lalu tanpa katalis baru.",
            "source_ids": ["official"], "source_url": OFFICIAL["source_url"],
            "published_at": OFFICIAL["published_at"],
            "thesis_points": [
                "Volume penjualan H2 ditopang kapasitas baru sehingga pendapatan naik.",
                "Harga bahan baku yang stabil menjaga margin laba bersih di atas 10%."],
            "catalysts_risks": [
                {"item": "Harga bahan baku", "timing": "Sepanjang H2 2026",
                 "driver_path": "Kenaikan harga jagung menekan margin kotor dan laba bersih.",
                 "direction": "Negatif", "source_ids": ["official"]},
                {"item": "Kapasitas baru", "timing": "Mulai 4Q26",
                 "driver_path": "Tambahan kapasitas menaikkan volume dan pendapatan tahunan.",
                 "direction": "Positif", "source_ids": ["official"]}]}
    base.update(kw)
    return base


def test_run_rate_scenario_is_valid():
    assert agent._validate_earnings(_scenario(), _source()) == []


def test_departure_from_run_rate_needs_news_or_guidance():
    problems = agent._validate_earnings(_scenario(h2_revenue_to_h1=1.6), _source())
    assert any("departs from the 1H run-rate" in p for p in problems)
    ok = _scenario(h2_revenue_to_h1=1.6, source_ids=["official", "news:0"])
    assert agent._validate_earnings(ok, _source()) == []
    guided = dict(OFFICIAL, guidance=[{"fact": "FY revenue +20%"}])
    # Guidance in the pack is not enough; the scenario must cite the item.
    assert agent._validate_earnings(_scenario(h2_net_margin_pct=20), _source(official=guided))
    assert agent._validate_earnings(
        _scenario(h2_net_margin_pct=20, source_ids=["official", "guidance:0"]),
        _source(official=guided)) == []


def test_rejects_bounds_bad_sources_and_mining():
    assert agent._validate_earnings(_scenario(h2_revenue_to_h1=3.0), _source())
    assert agent._validate_earnings(_scenario(source_ids=["news:9"]), _source())
    assert agent._validate_earnings(_scenario(source_url="https://other"), _source())
    assert agent._validate_earnings(_scenario(), _source(profile="finite_life_mining"))
    fy = dict(OFFICIAL, period="FY25")
    assert agent._validate_earnings(_scenario(), _source(official=fy))


def test_earnings_task_is_scheduled_for_banks_and_going_concern():
    assert agent._earnings_eligible(_source())
    assert agent._earnings_eligible(_source(profile="financial_ddm"))
    assert not agent._earnings_eligible(_source(profile="finite_life_mining"))


def test_thesis_and_risks_are_required_and_recommendation_free():
    assert any("thesis_points" in p for p in agent._validate_earnings(
        _scenario(thesis_points=[]), _source()))
    only_upside = [dict(x, direction="Positif") for x in _scenario()["catalysts_risks"]]
    assert any("downside risk" in p for p in agent._validate_earnings(
        _scenario(catalysts_risks=only_upside), _source()))
    advice = _scenario(thesis_points=[
        "Kami merekomendasikan akumulasi saham karena laba H2 membaik tajam.",
        "Harga bahan baku yang stabil menjaga margin laba bersih di atas 10%."])
    assert any("recommendation" in p for p in agent._validate_earnings(advice, _source()))
    # "harga jual" (selling price) is an earnings driver, not advice.
    price = _scenario(thesis_points=[
        "Kenaikan harga jual ayam hidup menaikkan margin laba bersih H2.",
        "Harga bahan baku yang stabil menjaga margin laba bersih di atas 10%."])
    assert agent._validate_earnings(price, _source()) == []


def test_non_mining_outyears_may_leave_ebitda_and_capex_empty():
    rows = [{"year": 2027 + i, "revenue_growth_pct": 8.0, "ebitda_margin_pct": None,
             "net_income_margin_pct": 9.0, "capex_to_revenue_pct": None,
             "rationale": "Pertumbuhan volume moderat dengan margin stabil sesuai 1H.",
             "source_ids": ["official"]} for i in range(4)]
    assert agent._validate_outyears(rows, _source()) == []
    assert agent._validate_outyears(rows, _source(profile="finite_life_mining"))


def test_llm_prose_dashes_are_normalized_but_titles_kept():
    fragment = {"earnings_scenario": {
        "rationale": "Volume naik di sebagian besar segmen — DOC +60% QoQ, rentang 5–7%.",
        "thesis_points": ["Margin pulih – biaya pakan turun."],
        "source_refs": {"news:0": {"title": "Japfa — laba naik"}}}}
    out = agent._normalize_prose(fragment)["earnings_scenario"]
    assert out["rationale"] == "Volume naik di sebagian besar segmen, DOC +60% QoQ, rentang 5-7%."
    assert out["thesis_points"] == ["Margin pulih, biaya pakan turun."]
    assert out["source_refs"]["news:0"]["title"] == "Japfa — laba naik"


def test_prose_periods_and_pipeline_word_are_normalized():
    from app import scrub
    text = ("Volume kuat di semua segmen Q2 2026 menjadi engine revenue H2; "
            "katalis Q3-Q4 2026 dan Kuartal II 2026, hasil H1 2026.")
    assert scrub.normalize_prose(text) == (
        "Volume kuat di semua segmen 2Q26 menjadi penggerak revenue H2; "
        "katalis 3Q26-4Q26 dan 2Q26, hasil 1H26.")
    # Aircraft engines at an MRO stay "engine".
    assert "engine lessor" in scrub.normalize_prose("reaktivasi airframe dan engine lessor")
    plan = {"earnings_scenario": {"rationale": "Q2 2026 — kuat", "source_refs": {
        "news:0": {"title": "Q2 2026 — judul asli"}}}}
    out = scrub.normalize_plan(plan)["earnings_scenario"]
    assert out["rationale"] == "2Q26, kuat"
    assert out["source_refs"]["news:0"]["title"] == "Q2 2026 — judul asli"
