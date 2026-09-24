"""One-command research workflow and report intake boundary."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import research, research_context


def test_research_command_writes_report_and_readable_trace(monkeypatch, tmp_path):
    from agents.research import run as agent

    document = {
        "ticker": "TEST", "as_of": "2026-09-11", "status": "research_brief",
        "summary": "Cached financials and a market headline were reviewed together.",
        "insights": [{
            "title": "A change in market context",
            "observation": "The cached article describes firmer commodity prices.",
            "implication": "That can affect sentiment, while earnings depend on realized prices and sales.",
            "caveat": "A media report is not company guidance.",
            "citations": [{"endpoint": "/news/", "field_path": "/results/0/title",
                           "value": "Commodity prices firm"}],
        }],
        "limitations": ["No realized price bridge in the cache."],
        "agent_trace": {"selected_cache_endpoints": ["/news/"], "tool_calls": [],
                        "validation": {"accepted": True, "rejected_claims": []}},
    }
    monkeypatch.setattr(agent, "run_live", lambda ticker: {
        "ok": True, "document": document, "path": "research.json",
        "agent_trace": document["agent_trace"]})

    def fake_build(ticker, outdir, want_pdf=False, as_of=None,
                   illustrative_scenarios=False, **kwargs):
        assert as_of == "2026-09-23"
        assert illustrative_scenarios is False
        (outdir / "TEST.html").write_text("<h1>Report</h1>", encoding="utf-8")
        return {"meta": {"status": "draft_non_distributable",
                         "tanggal": "2026-09-23", "harga_tanggal": "2026-09-11",
                         "research_status": "loaded"}}

    monkeypatch.setattr(research.build, "build", fake_build)
    monkeypatch.setattr(research.intake, "load", lambda ticker, as_of=None: ({}, {}))
    monkeypatch.setattr("agents.forecast_assumptions.run.run_live",
                        lambda intake: {"status": "validated", "interim_status": "validated",
                                        "plan": {}})
    def fake_load_analysis(ticker, as_of):
        assert as_of == "2026-09-11"
        return document, {"status": "loaded"}
    monkeypatch.setattr(research.research_context, "load_analysis", fake_load_analysis)
    output = research.run("TEST", tmp_path, as_of="2026-09-23")

    assert output["research_ok"] is True
    assert output["report_status"] == "draft_non_distributable"
    trace_html = (tmp_path / "TEST-trace.html").read_text(encoding="utf-8")
    assert "Commodity prices firm" in trace_html
    assert "earnings depend" in trace_html
    trace = json.loads((tmp_path / "TEST-trace.json").read_text(encoding="utf-8"))
    assert trace["report"]["research_status"] == "loaded"
    assert trace["report"]["as_of"] == "2026-09-23"
    assert trace["report"]["market_price_date"] == "2026-09-11"


def test_rejected_agent_prose_is_not_published_in_trace(monkeypatch, tmp_path):
    from agents.research import run as agent

    monkeypatch.setattr(agent, "run_live", lambda ticker: {
        "ok": False,
        "document": {"summary": "UNVALIDATED MODEL CLAIM", "insights": []},
        "agent_trace": {"selected_cache_endpoints": ["/news/"],
                        "validation": {"accepted": False,
                                       "rejected_claims": ["citation mismatch"]}},
    })
    monkeypatch.setattr(research.build, "build", lambda ticker, outdir, want_pdf=False,
                        as_of=None, illustrative_scenarios=False, **kwargs: {
        "meta": {"status": "draft_non_distributable", "tanggal": "2026-09-23",
                 "harga_tanggal": "2026-09-11",
                 "research_status": "insufficient"}})
    monkeypatch.setattr(research.intake, "load", lambda ticker, as_of=None: ({}, {}))
    monkeypatch.setattr("agents.forecast_assumptions.run.run_live",
                        lambda intake: {"status": "invalid", "interim_status": "invalid",
                                        "plan": None})
    monkeypatch.setattr(research.research_context, "load_analysis",
                        lambda ticker, as_of: (None, {"status": "insufficient"}))

    output = research.run("AMMN", tmp_path, as_of="2026-09-23")

    assert output["research_ok"] is False
    assert "UNVALIDATED MODEL CLAIM" not in (tmp_path / "AMMN-trace.html").read_text()
    assert "UNVALIDATED MODEL CLAIM" not in (tmp_path / "AMMN-trace.json").read_text()


def test_invalid_persisted_research_does_not_enter_report(monkeypatch, tmp_path):
    from agents.research import run as agent

    (tmp_path / "AMMN.json").write_text(json.dumps({
        "ticker": "AMMN", "summary": "Forged", "insights": []}), encoding="utf-8")
    monkeypatch.setattr(agent, "validate_against_cache",
                        lambda ticker, document, as_of=None: (None, ["citation mismatch"]))

    analysis, status = research_context.load_analysis(
        "AMMN", "2026-09-11", analysis_dir=tmp_path)

    assert analysis is None
    assert status["status"] == "invalid"
    assert status["problems"] == ["citation mismatch"]
