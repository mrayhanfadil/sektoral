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
            "published_at": OFFICIAL["published_at"]}
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
    assert agent._validate_earnings(_scenario(h2_net_margin_pct=20), _source(official=guided)) == []


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
