"""Gate estimator: skema + sumber + sanity. Tanpa network, tanpa LLM."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.estimator.validate import gate


def good():
    return {"ticker": "AMMN", "basis": "agent-estimate",
            "as_of": "2026-09-23", "currency": "USD mn (as published)",
            "years": ["2026F", "2027F", "2028F"],
            "drivers": {
                "revenue": {"path": [4001, 4287, 4868],
                            "source": "paparan publik emiten Q2-2026",
                            "note": "ramp Phase-8, fresh ore naik bertahap"},
                "ebitda": {"path": [2024, 2673, 3300],
                           "source": "paparan publik emiten Q2-2026",
                           "note": "margin 50-68%, biaya/ton turun saat ramp"},
                "net_profit": {"path": [909, 1462, 1992],
                               "source": "asumsi-berlabel: ikut margin historis",
                               "note": "asumsi-berlabel: net margin 22-41% bertahap"},
                "capex": {"path": [498, 305, 318],
                          "source": "cache filings FY2025A + normalisasi",
                          "note": "post-build normalisation dari 1.424 FY2025A"},
            }}


def test_lolos():
    assert gate(good()) == []


def test_tolak_tanpa_sumber():
    d = good()
    del d["drivers"]["capex"]["source"]
    assert any("tanpa sumber" in p for p in gate(d))


def test_tolak_path_negatif():
    d = good()
    d["drivers"]["revenue"]["path"][0] = -5
    assert any("negatif" in p for p in gate(d))


def test_tolak_series_hilang():
    d = good()
    del d["drivers"]["ebitda"]
    assert any("ebitda" in p for p in gate(d))


def test_tolak_note_tipis():
    d = good()
    d["drivers"]["capex"]["note"] = "ok"
    assert any("tipis" in p for p in gate(d))


def test_plan_dry_run_tanpa_llm():
    from agents.estimator.run import plan
    p = plan("AMMN", ["2026F", "2027F", "2028F"])
    assert p["n_endpoints"] > 0
    assert "write_drivers" in p["tools"]


def test_live_reads_cache_itself_then_requests_final(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    reads = []
    saved = []
    endpoints = ["/company/report/AMMN/", "/daily/AMMN/",
                 "/financials/quarterly/AMMN/"]
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: endpoints)
    def cache_get(ticker, endpoint):
        reads.append(endpoint)
        return {"endpoint": endpoint, "payload": "verified evidence"}
    monkeypatch.setattr(tools, "cache_get", cache_get)
    monkeypatch.setattr(tools, "write_drivers", lambda ticker, doc: saved.append(doc) or "drivers.json")
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [])
    def chat(messages, **kwargs):
        prompt = messages[-1]["content"]
        assert "verified evidence" in prompt
        assert "missing_evidence" in prompt
        return json.dumps({"final": good()})
    monkeypatch.setattr(run, "_chat", chat)

    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])

    assert result["ok"] is True
    assert set(reads) == {"/company/report/AMMN/", "/financials/quarterly/AMMN/"}
    assert len(saved) == 1


def test_live_gate_repair_includes_candidate_and_gate_reasons(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [])
    monkeypatch.setattr(tools, "cache_get", lambda *args: None)
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [])
    saved = []
    monkeypatch.setattr(tools, "write_drivers", lambda ticker, doc: saved.append(doc) or "drivers.json")
    invalid = good()
    del invalid["drivers"]["ebitda"]
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"final": invalid})
        repair = messages[-1]["content"]
        assert "series wajib hilang: ebitda" in repair
        assert '"ticker": "AMMN"' in repair
        return json.dumps({"final": good()})
    monkeypatch.setattr(run, "_chat", chat)

    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])

    assert result["ok"] is True
    assert len(calls) == 2
    assert len(saved) == 1


def test_live_invalid_json_repair_receives_truncated_response(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [])
    monkeypatch.setattr(tools, "cache_get", lambda *args: None)
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [])
    monkeypatch.setattr(tools, "write_drivers", lambda *args: "drivers.json")
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return '{"final":{"ticker":"AMMN",'
        assert "Respons awal" in messages[-1]["content"]
        assert '{"final":{"ticker":"AMMN",' in messages[-1]["content"]
        return json.dumps({"final": good()})
    monkeypatch.setattr(run, "_chat", chat)

    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])

    assert result["ok"] is True
    assert len(calls) == 2



def test_public_forecast_evidence_exposes_published_driver_paths():
    from agents.estimator.run import public_forecast_evidence
    rows = public_forecast_evidence("AMMN")
    kb = rows[0]
    assert kb["years"] == ["2026F", "2027F", "2028F"]
    assert kb["revenue"] == [3789, 4179, 4475]
    assert kb["ebitda"] == [1937, 2139, 2558]
    assert kb["net_profit"] == [806, 899, 1170]
    assert kb["capex"] == [1137, 1045, 1119]
    assert "kbvalbury.com" in kb["url"]


def test_live_reports_insufficient_evidence_without_calling_write(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: ["/financials/quarterly/AMMN/"])
    monkeypatch.setattr(tools, "cache_get", lambda *args: {"data": []})
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [])
    monkeypatch.setattr(tools, "write_drivers", lambda *args: pytest.fail("must not write"))
    monkeypatch.setattr(run, "_chat", lambda messages, **kwargs: json.dumps({
        "final": {"missing_evidence": ["forecast consensus"], "available_facts": ["quarterly actuals"]}}))

    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])

    assert result["ok"] is False
    assert result["missing_evidence"] == ["forecast consensus"]
    assert "bukti belum cukup" in result["error"]


def test_structured_forecasts_build_driver_paths_without_llm(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    years = ["2026F", "2027F", "2028F"]
    source = {
        "source": "Verified research report",
        "url": "https://example.test/report.pdf",
        "currency": "USD million",
        "years": years,
        "revenue": [10, 11, 12],
        "ebitda": [4, 5, 6],
        "net_profit": [2, 3, 4],
        "capex": [1, 1, 2],
        "capex_basis": "fixed-asset outflow proxy",
    }
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [])
    monkeypatch.setattr(tools, "cache_get", lambda *args: None)
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [source])
    monkeypatch.setattr(run, "_chat", lambda *args, **kwargs: pytest.fail("LLM not needed"))
    saved = []
    monkeypatch.setattr(tools, "write_drivers",
                        lambda ticker, doc: saved.append(doc) or "drivers.json")

    result = run.run_live("TEST", years)

    assert result["ok"] is True
    assert result["method"] == "structured-source"
    assert len(saved) == 1
    doc = saved[0]
    assert doc["ticker"] == "TEST"
    assert doc["drivers"]["revenue"]["path"] == source["revenue"]
    assert doc["drivers"]["capex"]["path"] == source["capex"]
    assert source["url"] in doc["drivers"]["revenue"]["source"]
    assert gate(doc) == []


def test_structured_forecast_requires_complete_year_series():
    from agents.estimator.run import _forecast_candidate
    source = {
        "source": "Verified research report", "url": "https://example.test/report.pdf",
        "currency": "USD million", "years": ["2026F", "2027F"],
        "revenue": [10, 11], "ebitda": [4, 5], "net_profit": [2, 3], "capex": [1, 1],
    }
    assert _forecast_candidate("TEST", ["2026F", "2027F", "2028F"], [source]) is None


def test_chat_sends_supported_completion_token_field(monkeypatch):
    from agents.estimator import run
    import urllib.request
    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return json.dumps({"choices": [{"message": {"content": "{}"},
                                           "finish_reason": "stop"}],
                               "usage": {"completion_tokens": 9}}).encode()
    captured = {}
    def open_request(req, timeout):
        captured["body"] = json.loads(req.data)
        return Reply()
    monkeypatch.setattr(urllib.request, "urlopen", open_request)
    monkeypatch.setenv("MINIMAX_API_KEY", "not-a-real-secret")
    result = run._chat([{"role": "user", "content": "return json"}])
    assert captured["body"]["max_completion_tokens"] == 131072
    assert "max_tokens" not in captured["body"]
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert result["finish_reason"] == "stop"


def test_load_dotenv_reads_missing_keys_without_overriding_environment(monkeypatch, tmp_path):
    from agents.estimator.run import _load_dotenv
    env_file = tmp_path / ".env"
    env_file.write_text('MINIMAX_API_KEY="from file"\n'
                        'SEKTORAL_LLM_MODEL=from-file\n'
                        'SECTORS_API_KEY=must-not-load\n')
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("SEKTORAL_LLM_MODEL", "from-process")
    monkeypatch.delenv("SECTORS_API_KEY", raising=False)

    _load_dotenv(env_file)

    assert os.environ["MINIMAX_API_KEY"] == "from file"
    assert os.environ["SEKTORAL_LLM_MODEL"] == "from-process"
    assert "SECTORS_API_KEY" not in os.environ


def test_live_invalid_json_stops_after_repair_attempt(monkeypatch, tmp_path):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [])
    monkeypatch.setattr(tools, "cache_get", lambda *args: None)
    monkeypatch.setattr(run, "public_forecast_evidence", lambda ticker: [])
    monkeypatch.setattr(tools, "DRIVERS_DIR", tmp_path)
    monkeypatch.setattr(run, "_chat", lambda messages, **kwargs: "not json")
    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])
    assert result["ok"] is False
    assert "JSON" in result["error"]
    assert not (tmp_path / "AMMN.json").exists()
