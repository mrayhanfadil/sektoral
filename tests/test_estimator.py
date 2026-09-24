"""Gate estimator: skema + sumber + sanity. Tanpa network, tanpa LLM."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.estimator.validate import gate


def good(ticker="AMMN"):
    quarterly = f"/financials/quarterly/{ticker}/"
    return {"ticker": ticker, "basis": "agent-estimate",
            "as_of": "2026-09-23", "currency": "USD mn (as published)",
            "years": ["2026F", "2027F", "2028F"],
            "drivers": {
                "revenue": {"path": [4001, 4287, 4868],
                            "source": f"sectors_cache {quarterly}",
                            "note": "ramp Phase-8, fresh ore naik bertahap"},
                "ebitda": {"path": [2024, 2673, 3300],
                           "source": f"sectors_cache {quarterly}",
                           "note": "margin 50-68%, biaya/ton turun saat ramp"},
                "net_profit": {"path": [909, 1462, 1992],
                               "source": f"sectors_cache {quarterly}",
                               "note": "asumsi-berlabel: net margin 22-41% bertahap"},
                "capex": {"path": [498, 305, 318],
                          "source": f"sectors_cache {quarterly}",
                          "note": "post-build normalisation dari 1.424 FY2025A"},
            }}


def _news_item():
    return {
        "title": "AMMN shares rise as copper prices rally",
        "body": "Cached article says tight copper supply and stronger demand lifted "
                "benchmark prices and supported AMMN share momentum. It cautions that "
                "benchmark moves do not equal realized company prices.",
        "source": "https://news.example.test/ammn-copper-rally",
        "timestamp": "2026-09-09T09:17:00",
        "symbols": ["AMMN.JK"],
    }


def _news_analysis():
    news = _news_item()
    return [{
        "summary": "Copper-market strength coincided with renewed buying interest in AMMN.",
        "connection": "Higher benchmarks can support market sentiment and potential netbacks, "
                      "but the cache has no realized-price bridge to quantify EBITDA or FCF.",
        "caveat": "This is media-reported market context, not company guidance or an earnings fact.",
        "source": f"sectors_cache /news/ | {news['title']} | {news['source']}",
        "timestamp": news["timestamp"],
    }]


def test_lolos():
    assert gate(good()) == []


def test_facts_optional_and_source_backed_rows_pass():
    # Legacy driver payloads remain valid without the optional facts field.
    assert gate(good()) == []

    d = good()
    d["facts"] = [{
        "claim": "Phase 8 ore throughput",
        "value": 18.0,
        "unit": "Mtpa",
        "period": "FY2026F",
        "status": "management guidance",
        "source": "sectors_cache /mining/companies/performance/TEST/",
        "source_date": "2026-06-29",
        "page": 12,
        "asset": "Batu Hijau",
        "project": "Phase 8",
        "bridge_stage": "throughput",
    }, {
        "claim": "Smelter commissioning status",
        "value": "commissioning underway",
        "unit": "text",
        "period": "as of 2026-06-29",
        "status": "reported actual",
        "source": "sectors_cache /mining/companies/performance/TEST/",
        "source_date": "2026-06-29",
        "page": "p. 15",
        "asset": "Smelter",
    }, {
        "claim": "Quarterly revenue",
        "value": 0,
        "unit": "USD mn",
        "period": "1Q2026A",
        "status": "reported actual",
        "source": "sectors_cache /financials/quarterly/TEST/",
        "source_date": "2026-04-30",
        "page": None,
        "metric": "revenue",
    }]
    assert gate(d) == []


def test_cache_news_analysis_schema_passes():
    d = good()
    d["news_analysis"] = _news_analysis()
    assert gate(d) == []


def test_fact_bridge_stage_enum_matches_release_contract():
    from agents.estimator.schema import FACT_BRIDGE_STAGES
    from app.release import OPERATING_BRIDGE_STAGES
    assert FACT_BRIDGE_STAGES == OPERATING_BRIDGE_STAGES


@pytest.mark.parametrize("field,value", [
    ("metric", ""),
    ("metric", "ore_throughput"),
    ("bridge_stage", ""),
    ("bridge_stage", "unknown_stage"),
])
def test_facts_reject_empty_or_unknown_optional_tags(field, value):
    d = good()
    d["facts"] = [{
        "claim": "Ore throughput",
        "value": 18,
        "unit": "Mtpa",
        "period": "FY2026F",
        "status": "management guidance",
        "source": "sectors_cache /mining/companies/performance/AMMN/",
        "source_date": "2026-06-29",
        "page": 12,
        field: value,
    }]
    assert any(f"facts[0].{field}" in issue for issue in gate(d))


@pytest.mark.parametrize("field,value", [
    ("claim", ""),
    ("value", None),
    ("unit", ""),
    ("period", ""),
    ("status", ""),
    ("source", ""),
    ("source_date", "29-06-2026"),
    ("page", 0),
])
def test_facts_reject_invalid_required_fields(field, value):
    d = good()
    d["facts"] = [{
        "claim": "Ore throughput",
        "value": 18,
        "unit": "Mtpa",
        "period": "FY2026F",
        "status": "management guidance",
        "source": "sectors_cache /mining/companies/performance/AMMN/",
        "source_date": "2026-06-29",
        "page": 12,
    }]
    d["facts"][0][field] = value
    assert any(f"facts[0].{field}" in issue for issue in gate(d))


def test_facts_reject_missing_provenance_and_malformed_collections():
    d = good()
    d["facts"] = [{"claim": "Ore throughput", "value": 18}]
    issues = gate(d)
    assert any("field hilang: source" in issue for issue in issues)
    assert any("field hilang: source_date" in issue for issue in issues)
    assert any("field hilang: page" in issue for issue in issues)

    d["facts"] = {"claim": "not a list"}
    assert any("facts harus list" in issue for issue in gate(d))


def test_facts_reject_empty_asset_or_project_when_provided():
    d = good()
    d["facts"] = [{
        "claim": "Ore throughput",
        "value": 18,
        "unit": "Mtpa",
        "period": "FY2026F",
        "status": "management guidance",
        "source": "sectors_cache /mining/companies/performance/AMMN/",
        "source_date": "2026-06-29",
        "page": 12,
        "project": " ",
    }]
    assert any("facts[0].project" in issue for issue in gate(d))


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
    assert "fetch_public" not in p["tools"]


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
    endpoint = "/financials/quarterly/AMMN/"
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(tools, "cache_get", lambda *args: {"data": []})
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
    endpoint = "/financials/quarterly/AMMN/"
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(tools, "cache_get", lambda *args: {"data": []})
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



def test_live_reports_insufficient_evidence_without_calling_write(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: ["/financials/quarterly/AMMN/"])
    monkeypatch.setattr(tools, "cache_get", lambda *args: {"data": []})
    monkeypatch.setattr(tools, "write_drivers", lambda *args: pytest.fail("must not write"))
    monkeypatch.setattr(run, "_chat", lambda messages, **kwargs: json.dumps({
        "final": {"missing_evidence": ["forecast consensus"], "available_facts": ["quarterly actuals"]}}))

    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])

    assert result["ok"] is False
    assert result["missing_evidence"] == ["forecast consensus"]
    assert "bukti belum cukup" in result["error"]


def test_agentic_mode_chooses_and_executes_cache_tool_before_writing(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    years = ["2026F", "2027F", "2028F"]
    endpoint = "/financials/quarterly/TEST/"
    reads = []
    saved = []
    calls = []
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: [endpoint])
    def cache_get(ticker, requested_endpoint):
        reads.append((ticker, requested_endpoint))
        return {"data": [{"date": "2026-03-31", "revenue": 9}]}
    monkeypatch.setattr(tools, "cache_get", cache_get)
    monkeypatch.setattr(tools, "write_drivers",
                        lambda ticker, doc: saved.append(doc) or "drivers.json")
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]})
        assert "2026-03-31" in messages[-1]["content"]
        return json.dumps({"final": good("TEST")})
    monkeypatch.setattr(run, "_chat", chat)

    result = run.run_live("TEST", years, agentic=True)

    assert result["ok"] is True
    assert result["method"] == "agentic-cache-only"
    assert result["agent_tool_calls"] == 1
    assert result["agent_decision"] == {"decision": "drivers_submitted",
                                         "selected_cache_endpoints": [endpoint]}
    assert reads == [("TEST", endpoint)]
    assert len(calls) == 2
    assert len(saved) == 1
    assert saved[0]["drivers"]["revenue"]["source"] == \
        "sectors_cache /financials/quarterly/TEST/"


def test_agentic_news_is_paraphrased_and_connected_to_drivers(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    quarter = "/financials/quarterly/TEST/"
    endpoints = [quarter, "/news/"]
    news = _news_item()
    monkeypatch.setattr(tools, "cache_endpoints", lambda ticker: endpoints)
    def cache_get(ticker, endpoint):
        if endpoint == "/news/":
            return {"results": [news]}
        return {"data": [{"date": "2026-03-31", "revenue": 9}]}
    monkeypatch.setattr(tools, "cache_get", cache_get)
    monkeypatch.setattr(tools, "write_drivers", lambda ticker, doc: "drivers.json")
    saved_news = []
    monkeypatch.setattr(tools, "write_news_analysis",
                        lambda ticker, doc: saved_news.append(doc) or "news.json")
    calls = []
    def chat(messages, **kwargs):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"tool": "cache_get", "args": ["TEST", quarter]})
        if len(calls) == 2:
            return json.dumps({"tool": "cache_get", "args": ["TEST", "/news/"]})
        assert "parafrasa" in messages[1]["content"]
        assert news["body"] in messages[-1]["content"]
        result = good("TEST")
        result["news_analysis"] = _news_analysis()
        return json.dumps({"final": result})
    monkeypatch.setattr(run, "_chat", chat)

    result = run.run_live("TEST", ["2026F", "2027F", "2028F"], agentic=True)

    assert result["ok"] is True
    assert result["agent_tool_calls"] == 2
    assert result["agent_decision"]["selected_cache_endpoints"] == sorted(["/news/", quarter])
    assert result["news_analysis_path"] == "news.json"
    assert saved_news[0]["news_analysis"] == _news_analysis()


def test_news_gate_requires_exact_cached_timestamp_and_url():
    from agents.estimator.run import _news_analysis_problems

    article = _news_item()
    analysis = _news_analysis()[0]
    assert _news_analysis_problems({"news_analysis": [analysis]}, [article]) == []

    bad_timestamp = {**analysis, "timestamp": "2026-09-08T09:17:00"}
    assert any("timestamp" in problem for problem in _news_analysis_problems(
        {"news_analysis": [bad_timestamp]}, [article]))

    bad_url = {**analysis, "source": analysis["source"] + " https://outside.test/story"}
    assert any("URL" in problem for problem in _news_analysis_problems(
        {"news_analysis": [bad_url]}, [article]))


def test_agentic_mode_rejects_endpoint_outside_allowlist(monkeypatch):
    from agents.estimator import run
    from agents.estimator import tools
    monkeypatch.setattr(tools, "cache_endpoints",
                        lambda ticker: ["/financials/quarterly/TEST/"])
    monkeypatch.setattr(run, "_chat", lambda *args, **kwargs: json.dumps({
        "tool": "cache_get", "args": ["TEST", "/company/secret/TEST/"]}))
    monkeypatch.setattr(tools, "cache_get",
                        lambda *args: pytest.fail("outside endpoint must not execute"))

    result = run.run_live("TEST", ["2026F", "2027F", "2028F"], agentic=True)

    assert result["ok"] is False
    assert "allowlist" in result["error"]


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
    assert captured["body"]["max_completion_tokens"] == run.LLM_GENERATION_BUDGET
    assert "max_tokens" not in captured["body"]
    assert captured["body"]["thinking"] == {"type": "adaptive"}
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
    monkeypatch.setattr(tools, "DRIVERS_DIR", tmp_path)
    monkeypatch.setattr(run, "_chat", lambda messages, **kwargs: "not json")
    result = run.run_live("AMMN", ["2026F", "2027F", "2028F"])
    assert result["ok"] is False
    assert "JSON" in result["error"]
    assert not (tmp_path / "AMMN.json").exists()


def test_news_cache_is_ticker_filtered_and_cut_off_at_cached_as_of(monkeypatch, tmp_path):
    import sqlite3
    from agents.estimator import tools

    db = tmp_path / "cache.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sectors_cache (cache_key TEXT PRIMARY KEY, endpoint TEXT, "
                "fetched_at REAL, expires_at REAL, payload_json TEXT)")
    report = {"overview": {"latest_close_date": "2026-09-11"}}
    news = {"results": [
        {"title": "AMMN before as-of", "timestamp": "2026-09-10T12:00:00",
         "symbols": ["AMMN.JK"]},
        {"title": "AMMN after as-of", "timestamp": "2026-09-12T12:00:00",
         "symbols": ["AMMN.JK"]},
        {"title": "Other ticker", "timestamp": "2026-09-10T12:00:00",
         "symbols": ["BBCA.JK"]},
    ]}
    con.executemany("INSERT INTO sectors_cache VALUES (?,?,?,?,?)", [
        ("report", "/company/report/AMMN/", 1, 2, json.dumps(report)),
        ("news", "/news/", 1, 2, json.dumps(news)),
    ])
    con.commit()
    con.close()
    monkeypatch.setattr(tools, "CACHE_DB", db)

    endpoints = tools.cache_endpoints("AMMN")
    payload = tools.cache_get("AMMN", "/news/")

    assert "/news/" in endpoints
    assert [row["title"] for row in payload["results"]] == ["AMMN before as-of"]
