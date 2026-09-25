import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.research import run as research
from app import store


def test_live_reads_cache_then_saves_validated_brief(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"fiscal_period": "2026-Q2", "revenue": 1250}]}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: payload if ep == endpoint else None)
    calls = []

    def chat(messages):
        calls.append(messages)
        if len(calls) == 1:
            return json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]})
        if len(calls) == 2:
            return json.dumps({"final": {
                "summary": "Pendapatan kuartal terbaru menunjukkan skala usaha.",
                "insights": [{
                    "title": "Kinerja kuartal",
                    "observation": "Catatan terbaru menunjukkan pendapatan perusahaan.",
                        "implication": "Skala penjualan memberi konteks untuk menilai kegiatan usaha.",
                    "caveat": "Satu kuartal belum menunjukkan tren tahunan.",
                    "citations": [{"endpoint": endpoint,
                                   "field_path": "/data/0/revenue"}],
                }],
                "limitations": ["Belum ada pembanding kuartal sebelumnya."],
            }})
        raise AssertionError("agent should stop after final")

    monkeypatch.setattr(research, "_chat", chat)
    result = research.run_live("test", db=tmp_path)

    assert result["ok"] is True
    assert result["document"]["ticker"] == "TEST"
    assert result["agent_trace"]["selected_cache_endpoints"] == [endpoint]
    assert result["document"]["insights"][0]["citations"][0]["value"] == 1250
    saved = store.get("research_analysis", "TEST", tmp_path)
    assert saved == result["document"]
    clean, problems = research.validate_against_cache("TEST", saved)
    assert problems == []
    assert clean["insights"][0]["observation"] == saved["insights"][0]["observation"]


def test_validator_rejects_unread_endpoint_and_unsupported_number(monkeypatch):
    endpoint = "/financials/quarterly/TEST/"
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: {"revenue": 1250})
    doc = {
        "ticker": "TEST", "as_of": None, "status": "research_brief",
        "summary": "Brief ini merangkum temuan cache yang lolos validasi.", "limitations": [], "agent_trace": {},
        "insights": [{"observation": "Revenue was 1250.",
                      "implication": "Revenue may support operations, but scale alone is not profitability.",
                      "caveat": "A single observation has no trend.",
                      "citations": [{"endpoint": "/other/TEST/",
                                     "field_path": "/revenue", "value": 1250}]}],
    }
    clean, problems = research.validate_against_cache("TEST", doc)
    assert clean is None
    assert "endpoint was not read" in " ".join(problems)

    doc["insights"][0]["citations"] = [{"endpoint": endpoint,
                                         "field_path": "/revenue", "value": 1250}]
    doc["insights"][0]["implication"] = "A 30% rise could indicate acceleration."
    clean, problems = research.validate_against_cache("TEST", doc)
    assert clean is None
    assert "unsupported numeric claim" in " ".join(problems)


def test_agent_rejected_tool_call_returns_useful_insufficient_brief(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda *args: {"revenue": 1})
    monkeypatch.setattr(research, "_chat", lambda messages: json.dumps({
        "tool": "cache_get", "args": ["OTHER", endpoint]}))

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is False
    assert result["document"]["status"] == "insufficient_evidence"
    assert result["document"]["summary"]
    assert result["agent_trace"]["validation"]["rejected_claims"]
    assert store.get("research_analysis", "TEST", tmp_path) is not None


def test_validator_requires_same_cached_report_as_of(monkeypatch):
    report = "/company/report/TEST/"
    detail = "/financials/quarterly/TEST/"
    payloads = {
        report: {"overview": {"latest_close_date": "2026-09-11"}},
        detail: {"revenue": 1250},
    }
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [report, detail])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payloads[ep])
    doc = {"ticker": "TEST", "as_of": "2026-09-10", "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.", "limitations": [], "agent_trace": {},
           "insights": [{"observation": "Revenue was 1250.",
                         "implication": "This gives operating context.",
                         "caveat": "It does not establish a trend.",
                         "citations": [{"endpoint": detail,
                                        "field_path": "/revenue", "value": 1250}]}]}
    clean, problems = research.validate_against_cache("TEST", doc, as_of="2026-09-11")
    assert clean is None
    assert "as_of" in " ".join(problems)


def test_validator_rejects_investment_action_and_requires_complete_news_provenance(monkeypatch):
    endpoint = "/news/"
    report = "/company/report/TEST/"
    payload = {"results": [{"title": "Test headline", "body": "Copper shipments were delayed.",
                            "timestamp": "2026-09-10T10:00:00Z",
                            "source": "https://news.test/story",
                            "symbols": ["TEST"]}]}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint, report])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: (
        payload if ep == endpoint else
        {"overview": {"latest_close_date": "2026-09-11"}}))
    citations = [{"endpoint": endpoint, "field_path": "/results/0/title"},
                 {"endpoint": endpoint, "field_path": "/results/0/body"},
                 {"endpoint": endpoint, "field_path": "/results/0/timestamp"},
                 {"endpoint": endpoint, "field_path": "/results/0/source"}]
    doc = {"ticker": "TEST", "as_of": "2026-09-11", "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.", "limitations": [], "agent_trace": {},
           "insights": [{"observation": "A headline reports a shipment delay.",
                         "implication": "The report may affect sentiment around near-term supply.",
                         "caveat": "The headline is not independently verified and does not quantify earnings.",
                         "citations": citations}]}
    enriched, enrich_problems = research._host_enrich_citations("TEST", doc, [
        {"endpoint": endpoint, "payload": payload},
        {"endpoint": report, "payload": {"overview": {"latest_close_date": "2026-09-11"}}},
    ])
    assert enrich_problems == []
    doc = enriched
    doc["limitations"] = research._expected_limitations(doc["insights"])
    clean, problems = research.validate_against_cache("TEST", doc, as_of="2026-09-11")
    assert problems == []
    assert clean["insights"]

    doc["insights"][0]["implication"] = "Buy now before the market reacts."
    clean, problems = research.validate_against_cache("TEST", doc, as_of="2026-09-11")
    assert clean is None
    assert "investment action" in " ".join(problems)

    doc["insights"][0]["implication"] = "The report may affect sentiment around near-term supply."
    doc["insights"][0]["citations"] = citations[:2]
    clean, problems = research.validate_against_cache("TEST", doc, as_of="2026-09-11")
    assert clean is None
    assert "news citation requires exact title, body, timestamp, and source" in " ".join(problems)


def test_invalid_final_gets_one_repair_and_host_enriches_path_only_citation(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"revenue": 1250}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payload)
    responses = [
        json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]}),
        json.dumps({"final": {"summary": "Revenue was 1250.", "limitations": [],
                               "insights": [{"observation": "Revenue was 1250.",
                                             "implication": "This may reflect business momentum.",
                                             "caveat": "One period does not establish a trend.",
                                             "citations": [{"endpoint": endpoint,
                                                            "field_path": "/revenue"}]}]}}),
        json.dumps({"final": {"summary": "The cache provides a recent company snapshot.",
                               "limitations": ["Trend comparison remains unavailable."],
                                   "insights": [{"observation": "The latest company record includes revenue.",
                                                 "implication": "It gives context for monitoring business activity.",
                                                 "caveat": "A single record has limited scope.",
                                             "citations": [{"endpoint": endpoint,
                                                            "field_path": "/revenue"}]}]}}),
    ]
    seen = []

    def chat(messages):
        seen.append(messages)
        return responses.pop(0)

    monkeypatch.setattr(research, "_chat", chat)
    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 3
    assert result["agent_trace"]["validation"]["repair_attempted"] is True
    assert result["document"]["insights"][0]["citations"][0] == {
        "endpoint": endpoint, "field_path": "/revenue", "value": 1250}
    clean, problems = research.validate_against_cache("TEST", result["document"])
    assert problems == []
    assert clean["insights"][0]["citations"][0]["value"] == 1250


def test_summary_is_deterministic_and_never_uses_llm_summary():
    endpoint = "/financials/quarterly/TEST/"
    evidence = [{"endpoint": endpoint, "payload": {"revenue": 1250}}]
    final = {"summary": "Salim is an owner and segment losses increased.",
             "limitations": [], "insights": [{
                 "observation": "A revenue figure appears in the cache.",
                 "implication": "It gives context for reviewing the business.",
                 "caveat": "The figure alone does not establish a trend.",
                 "citations": [{"endpoint": endpoint, "field_path": "/revenue"}],
             }]}
    doc, problems = research._candidate_document("TEST", final, evidence)
    assert problems == []
    assert doc["summary"] == "Brief ini merangkum temuan cache yang lolos validasi."
    assert "Salim" not in doc["summary"]


def test_host_caps_excess_insights_after_validating_published_claims():
    endpoint = "/financials/quarterly/TEST/"
    evidence = [{"endpoint": endpoint, "payload": {"revenue": 1250}}]
    insight = {
        "title": "Catatan pendapatan",
        "observation": "Cache mencatat pendapatan perusahaan pada catatan terbaru.",
        "implication": "Catatan ini memberi konteks untuk memahami aktivitas usaha.",
        "caveat": "Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.",
        "citations": [{"endpoint": endpoint, "field_path": "/revenue"}],
    }
    doc, problems = research._candidate_document(
        "TEST", {"insights": [insight] * 4, "limitations": []}, evidence)
    assert problems == []
    assert len(doc["insights"]) == 3
    assert "capped insight list" in " ".join(
        doc["agent_trace"]["validation"]["rejected_claims"])


def test_trend_claim_requires_period_anchored_same_metric_and_direction(monkeypatch):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [
        {"fiscal_period": "2025-Q4", "operating_cash_flow": -100},
        {"fiscal_period": "2026-Q1", "operating_cash_flow": 50},
    ]}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payload)
    base = {"ticker": "TEST", "as_of": None, "status": "research_brief",
            "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
            "limitations": [], "agent_trace": {}, "insights": [{
                "observation": "Arus kas operasional meningkat dari negatif ke positif.",
                "implication": "The direction may indicate stronger cash generation.",
                "caveat": "The short observation window does not establish durability.",
                "citations": [
                    {"endpoint": endpoint, "field_path": "/data/0/operating_cash_flow", "value": -100},
                    {"endpoint": endpoint, "field_path": "/data/1/operating_cash_flow", "value": 50},
                    ],
                }]}
    base["limitations"] = research._expected_limitations(base["insights"])
    assert research.validate_against_cache("TEST", base)[1] == []

    base["insights"][0]["citations"] = base["insights"][0]["citations"][:1]
    clean, problems = research.validate_against_cache("TEST", base)
    assert clean is None
    assert "at least two distinct period-anchored numeric citations" in " ".join(problems)

    base["insights"][0]["citations"] = [
        {"endpoint": endpoint, "field_path": "/data/0/operating_cash_flow", "value": 50},
        {"endpoint": endpoint, "field_path": "/data/1/operating_cash_flow", "value": -100},
    ]
    clean, problems = research.validate_against_cache("TEST", base)
    assert clean is None
    assert "upward trend claim conflicts" in " ".join(problems)


def test_non_latin_narrative_is_rejected(monkeypatch):
    endpoint = "/financials/quarterly/TEST/"
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: {"revenue": 10})
    doc = {"ticker": "TEST", "as_of": None, "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
           "limitations": [], "agent_trace": {}, "insights": [{
               "observation": "公司 revenue appears in the record.",
               "implication": "The record gives business context.",
               "caveat": "It does not establish a trend.",
               "citations": [{"endpoint": endpoint, "field_path": "/revenue", "value": 10}],
           }]}
    clean, problems = research.validate_against_cache("TEST", doc)
    assert clean is None
    assert "Latin-script narrative" in " ".join(problems)


def test_third_party_recommendation_language_is_rejected_from_brief():
    problems = research._narrative_problems({
        "ticker": "TEST",
        "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
        "limitations": [],
        "insights": [{"title": "Market context",
                      "observation": "The broker recommends a selective portfolio.",
                      "implication": "This gives context for current sentiment.",
                      "caveat": "The article does not quantify issuer earnings."}],
    })
    assert any("prohibited investment action" in problem for problem in problems)


def test_malformed_persisted_endpoint_fails_closed(monkeypatch):
    endpoint = "/financials/quarterly/TEST/"
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: {"revenue": 10})
    doc = {"ticker": "TEST", "as_of": None, "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
           "limitations": [], "agent_trace": {}, "insights": [{
               "observation": "A revenue value appears in the record.",
               "implication": "It gives context for reviewing the business.",
               "caveat": "The value alone does not establish a trend.",
               "citations": [{"endpoint": ["unhashable"], "field_path": "/revenue", "value": 10}],
           }]}
    clean, problems = research.validate_against_cache("TEST", doc)
    assert clean is None
    assert "endpoint was not read" in " ".join(problems)


def test_two_failed_repairs_fall_back_to_deterministic_non_claiming_brief(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: {"revenue": 100})
    invalid_final = {"final": {"summary": "Invented unsupported story.", "limitations": [],
        "insights": [{"observation": "A revenue record is available.",
                      "implication": "Buy now.",
                      "caveat": "This is not a recommendation.",
                      "citations": [{"endpoint": endpoint, "field_path": "/revenue"}]}]}}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]})] + \
                [json.dumps(invalid_final) for _ in range(3)]
    monkeypatch.setattr(research, "_chat", lambda messages: responses.pop(0))

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is False
    assert len(result["document"]["insights"]) == 0
    assert result["document"]["summary"] == "Belum ada temuan yang lolos validasi."
    assert result["agent_trace"]["validation"]["repair_attempts"] == 2
    assert "Buy now" not in json.dumps(result["document"]["summary"])
    clean, problems = research.validate_against_cache("TEST", result["document"])
    assert problems == []
    assert clean["insights"] == []


def test_empty_final_nudges_agent_to_read_relevant_cache_before_final(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"fiscal_period": "2026-Q2", "revenue": 1250}]}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: payload if ep == endpoint else None)
    responses = [
        json.dumps({"final": {"summary": "", "insights": [], "limitations": []}}),
        json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]}),
        json.dumps({"final": {"summary": "", "limitations": [], "insights": [{
            "observation": "Cache mencatat pendapatan perusahaan pada catatan terbaru.",
            "implication": "Catatan ini memberi konteks untuk memahami aktivitas usaha.",
            "caveat": "Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.",
            "citations": [{"endpoint": endpoint, "field_path": "/data/0/revenue"}],
        }]}}),
    ]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 3
    assert result["agent_trace"]["selected_cache_endpoints"] == [endpoint]
    assert result["document"]["insights"][0]["citations"][0]["value"] == 1250


def test_invalid_json_gets_final_only_format_repair_and_raw_text_is_not_persisted(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"revenue": 1250}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: payload if ep == endpoint else None)
    raw_garbage = "Unstructured private model reasoning that should never be persisted"
    responses = [
        json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]}),
        raw_garbage,
        json.dumps({"final": {"summary": "", "limitations": [], "insights": [{
            "observation": "Cache mencatat pendapatan perusahaan pada catatan terbaru.",
            "implication": "Catatan ini memberi konteks untuk memahami aktivitas usaha.",
            "caveat": "Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.",
            "citations": [{"endpoint": endpoint, "field_path": "/revenue"}],
        }]}}),
    ]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 3
    persisted = json.dumps(store.get("research_analysis", "TEST", tmp_path), ensure_ascii=False)
    assert raw_garbage not in persisted
    assert result["document"]["insights"][0]["citations"][0]["value"] == 1250


def test_format_repair_tool_request_is_never_executed(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    calls = []
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: (calls.append(ep), {"revenue": 1250})[1])
    responses = ["This is malformed JSON", json.dumps({
        "tool": "cache_get", "args": ["TEST", endpoint]})]
    monkeypatch.setattr(research, "_chat", lambda messages: responses.pop(0))

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is False
    assert calls == []
    assert result["document"]["status"] == "insufficient_evidence"


def test_wrong_shape_json_gets_one_final_only_schema_repair(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    payload = {"revenue": 1250}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: payload if ep == endpoint else None)
    final = {"ticker": "TEST", "as_of": None, "status": "research_brief", "summary": "",
             "limitations": [], "insights": [{
                 "observation": "Cache mencatat pendapatan perusahaan pada catatan terbaru.",
                 "implication": "Catatan ini memberi konteks untuk memahami aktivitas usaha.",
                 "caveat": "Satu catatan belum menjelaskan dampak terhadap laba atau arus kas.",
                 "citations": [{"endpoint": endpoint, "field_path": "/revenue"}]}]}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]}),
                 json.dumps({"unexpected": "valid JSON, wrong shape"}),
                 json.dumps({"final": final})]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 3
    schema_prompt = seen[2][-1]["content"]
    assert "wrong schema" in schema_prompt
    assert "final-only schema repair" in schema_prompt
    assert result["document"]["insights"][0]["citations"][0]["value"] == 1250


def test_wrong_shape_schema_repair_tool_call_is_rejected_without_execution(monkeypatch, tmp_path):
    endpoint = "/financials/quarterly/TEST/"
    calls = []
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [endpoint])
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: (calls.append(ep), {"revenue": 1250})[1])
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]}),
                 json.dumps({"unexpected": "valid JSON, wrong shape"}),
                 json.dumps({"tool": "cache_get", "args": ["TEST", endpoint]})]
    monkeypatch.setattr(research, "_chat", lambda messages: responses.pop(0))

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is False
    assert calls == [endpoint]
    assert "schema repair attempted a tool call" in " ".join(
        result["agent_trace"]["validation"]["rejected_claims"])


def test_repetition_claim_requires_multiple_distinct_quarter_anchors():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [
        {"fiscal_period": "2026-Q1", "revenue": 10},
        {"fiscal_period": "2026-Q2", "revenue": 12},
    ]}
    evidence = [{"endpoint": endpoint, "payload": payload}]
    insight = {"title": "Beberapa triwulan terakhir",
               "observation": "Pendapatan tercatat dalam beberapa triwulan terakhir.",
               "implication": "Ini memberi konteks untuk memahami aktivitas usaha.",
               "caveat": "Catatan ini hanya mencakup data yang tersedia.",
               "citations": [{"endpoint": endpoint,
                              "field_path": "/data/0/revenue", "value": 10}]}
    doc = {"ticker": "TEST", "as_of": None, "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
           "limitations": [], "agent_trace": {}, "insights": [insight]}
    doc["limitations"] = research._expected_limitations(doc["insights"])
    problems = research._validate_document("TEST", doc, evidence)
    assert any("repetition claim requires at least two" in problem for problem in problems)

    insight["citations"].append({"endpoint": endpoint,
                                 "field_path": "/data/1/revenue", "value": 12})
    assert research._validate_document("TEST", doc, evidence) == []


def test_foreign_flow_news_cannot_flip_ticker_specific_direction():
    news = "/news/"
    report = "/company/report/TEST/"
    article = {"title": "Foreign flow puts pressure on TEST",
               "body": "Accumulation was reported in copper. Pressure was most evident on TEST.",
               "timestamp": "2026-09-10T10:00:00Z",
               "source": "https://news.test/flow", "symbols": ["TEST"]}
    evidence = [
        {"endpoint": report, "payload": {"overview": {"latest_close_date": "2026-09-11"}}},
        {"endpoint": news, "payload": {"results": [article]}},
    ]
    insight = {"observation": "TEST repeatedly appeared as a foreign-flow destination.",
               "implication": "This indicates foreign accumulation in the ticker.",
               "caveat": "The article does not quantify business effects.",
               "citations": [
                   {"endpoint": news, "field_path": "/results/0/title", "value": article["title"]},
                   {"endpoint": news, "field_path": "/results/0/body", "value": article["body"]},
                   {"endpoint": news, "field_path": "/results/0/timestamp", "value": article["timestamp"]},
                   {"endpoint": news, "field_path": "/results/0/source", "value": article["source"]},
               ]}
    doc = {"ticker": "TEST", "as_of": "2026-09-11", "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
           "limitations": [], "agent_trace": {}, "insights": [insight]}
    doc["limitations"] = research._expected_limitations(doc["insights"])
    problems = research._validate_document("TEST", doc, evidence)
    assert any("positive ticker-specific flow claim conflicts" in problem
               for problem in problems)
    assert any("repetition claim requires at least two" in problem for problem in problems)


def test_ticker_specific_positive_news_flow_cannot_be_reported_as_outflow():
    news = "/news/"
    article = {"title": "TEST foreign inflow",
               "body": "Foreign accumulation was recorded in TEST shares.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/inflow",
               "symbols": ["TEST"]}
    payload = {"results": [article]}
    insight = {"observation": "TEST faced net outflow.",
               "implication": "Foreign selling pressured the ticker.",
               "caveat": "This is limited to the cited article.",
               "citations": [{"endpoint": news, "field_path": f"/results/0/{key}", "value": article[key]}
                             for key in ("title", "body", "timestamp", "source")]}
    problems = research._news_flow_direction_problems("TEST", insight, {news: payload})
    assert any("negative ticker-specific flow claim conflicts" in problem
               for problem in problems)


def test_foreign_flow_direction_recognizes_report_company_name_alias():
    news = "/news/"
    report = "/company/report/TEST/"
    article = {"title": "Foreign net selling accelerates",
               "body": "Net selling was led by PT Bank Central Asia Tbk, while accumulation focused on copper.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/bbca-flow",
               "symbols": ["TEST"]}
    payloads = {
        report: {"company_name": "PT Bank Central Asia Tbk",
                 "overview": {"latest_close_date": "2026-09-11"}},
        news: {"results": [article]},
    }
    insight = {"observation": "TEST was a foreign-flow destination.",
               "implication": "This indicates foreign accumulation in the ticker.",
               "caveat": "The article does not quantify business effects.",
               "citations": [{"endpoint": news, "field_path": f"/results/0/{key}",
                              "value": article[key]}
                             for key in ("title", "body", "timestamp", "source")]}
    problems = research._news_flow_direction_problems("TEST", insight, payloads)
    assert any("positive ticker-specific flow claim conflicts" in problem
               for problem in problems)


def test_search_completeness_claim_requires_cited_pagination_metadata():
    news = "/news/"
    report = "/company/report/TEST/"
    article = {"title": "TEST market context", "body": "The report describes market conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/test",
               "symbols": ["TEST"]}
    payload = {"results": [article]}
    evidence = [{"endpoint": report, "payload": {"overview": {"latest_close_date": "2026-09-11"}}},
                {"endpoint": news, "payload": payload}]
    insight = {"observation": "Hanya satu halaman awal hasil pencarian tersedia.",
               "implication": "This describes the available search coverage.",
               "caveat": "The article does not quantify issuer-level earnings.",
               "citations": [{"endpoint": news, "field_path": f"/results/0/{key}",
                              "value": article[key]}
                             for key in ("title", "body", "timestamp", "source")]}
    doc = {"ticker": "TEST", "as_of": "2026-09-11", "status": "research_brief",
           "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
           "limitations": [], "agent_trace": {}, "insights": [insight]}
    doc["limitations"] = research._expected_limitations(doc["insights"])
    problems = research._validate_document("TEST", doc, evidence)
    assert any("search-page or result-completeness claim requires" in problem
               for problem in problems)

    payload["pagination"] = {"offset": 0, "limit": 30, "has_next": True}
    insight["citations"].append({"endpoint": news, "field_path": "/pagination/has_next", "value": True})
    assert research._validate_document("TEST", doc, evidence) == []


def test_news_citation_triggers_single_quarterly_cache_nudge_and_connects_metric(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    news = "/news/"
    quarterly = "/financials/quarterly/TEST/"
    article = {"title": "TEST loan market context", "body": "The article discusses bank lending conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/loan",
               "symbols": ["TEST"]}
    report_payload = {"overview": {"latest_close_date": "2026-09-11"}}
    news_payload = {"results": [article]}
    quarterly_payload = {"data": [{"fiscal_period": "2026-Q2", "loans": 1500}]}
    endpoints = [report, news, quarterly]
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: endpoints)
    payloads = {news: news_payload, quarterly: quarterly_payload}
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: report_payload if ep == report else payloads.get(ep))

    news_citations = [{"endpoint": news, "field_path": f"/results/0/{key}"}
                      for key in ("title", "body", "timestamp", "source")]
    news_insight = {"observation": "The article discusses bank lending conditions.",
                    "implication": "This provides market context for reviewing lending activity.",
                    "caveat": "The article does not measure issuer-level earnings.",
                    "citations": news_citations}
    connected_insight = {"observation": "Cache mengaitkan TEST dengan artikel tentang market lending.",
                         "implication": "Catatan kuartalan TEST mencatat loan balance; ini memberi konteks untuk membaca market lending.",
                         "caveat": "The media report does not establish a causal effect on the company metric.",
                         "citations": news_citations + [{"endpoint": quarterly,
                                                        "field_path": "/data/0/loans"}]}
    responses = [
        json.dumps({"tool": "cache_get", "args": ["TEST", news]}),
        json.dumps({"final": {"summary": "", "limitations": [], "insights": [news_insight]}}),
        json.dumps({"tool": "cache_get", "args": ["TEST", quarterly]}),
        json.dumps({"final": {"summary": "", "limitations": [], "insights": [connected_insight]}}),
    ]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 4
    assert result["agent_trace"]["selected_cache_endpoints"] == [report, news, quarterly]
    assert result["document"]["insights"][0]["citations"][-1]["value"] == 1500


def test_news_quarterly_nudge_does_not_loop_when_final_stays_news_only(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    news = "/news/"
    quarterly = "/financials/quarterly/TEST/"
    article = {"title": "TEST market context", "body": "A market report discusses lending.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/context",
               "symbols": ["TEST"]}
    report_payload = {"overview": {"latest_close_date": "2026-09-11"}}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [report, news, quarterly])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: {
        report: report_payload, news: {"results": [article]}, quarterly: {"data": []}}[ep])
    insight = {"observation": "The article discusses lending conditions.",
               "implication": "This provides market context for reviewing lending activity.",
               "caveat": "The article does not measure issuer-level earnings.",
               "citations": [{"endpoint": news, "field_path": f"/results/0/{key}"}
                             for key in ("title", "body", "timestamp", "source")]}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", news]}),
                 json.dumps({"final": {"summary": "", "limitations": [], "insights": [insight]}}),
                 json.dumps({"tool": "cache_get", "args": ["TEST", quarterly]}),
                 json.dumps({"final": {"summary": "", "limitations": [], "insights": [insight]}})]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 4
    assert result["agent_trace"]["selected_cache_endpoints"] == [report, news, quarterly]


def test_failed_quarterly_followup_preserves_only_prior_valid_news_candidate(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    news = "/news/"
    quarterly = "/financials/quarterly/TEST/"
    article = {"title": "TEST lending context", "body": "The article discusses lending conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/lending",
               "symbols": ["TEST"]}
    report_payload = {"overview": {"latest_close_date": "2026-09-11"}}
    news_payload = {"results": [article]}
    quarter_payload = {"data": [{"fiscal_period": "2026-Q2", "loans": 1500}]}
    monkeypatch.setattr(research.cache_tools, "cache_endpoints",
                        lambda ticker: [report, news, quarterly])
    cache_payloads = {report: report_payload, news: news_payload, quarterly: quarter_payload}
    monkeypatch.setattr(research.cache_tools, "cache_get",
                        lambda ticker, ep: cache_payloads.get(ep))
    news_row = {"observation": "The article discusses lending conditions.",
                "implication": "This provides context for reviewing lending activity.",
                "caveat": "The media report does not measure issuer-level earnings.",
                "citations": [{"endpoint": news, "field_path": f"/results/0/{key}"}
                              for key in ("title", "body", "timestamp", "source")]}
    invalid_quarter = {"observation": "A quarterly company record includes loans.",
                       "implication": "This gives context for reviewing the company.",
                       "caveat": "A single record has limited scope.",
                       "citations": [{"endpoint": quarterly,
                                      "field_path": "/data/9/unsupported_metric"}]}
    bad_followup = {"final": {"summary": "", "limitations": [],
                              "insights": [news_row, invalid_quarter]}}
    responses = [
        json.dumps({"tool": "cache_get", "args": ["TEST", news]}),
        json.dumps({"final": {"summary": "", "limitations": [], "insights": [news_row]}}),
        json.dumps({"tool": "cache_get", "args": ["TEST", quarterly]}),
        json.dumps(bad_followup),
        json.dumps(bad_followup),
        json.dumps(bad_followup),
    ]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is False
    assert len(seen) == 6
    assert result["document"]["insights"] == []
    assert result["document"]["status"] == "insufficient_evidence"


def test_host_recovers_wrong_pointer_only_for_one_exact_terminal_key():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"revenue": 250}]}
    final = {"insights": [{"observation": "A record lists company revenue.",
                            "implication": "It gives context for understanding business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/wrong/path/revenue"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert problems == []
    assert enriched["insights"][0]["citations"] == [{
        "endpoint": endpoint, "field_path": "/data/0/revenue", "value": 250}]


def test_host_recovers_structural_suffix_to_unique_canonical_pointer():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"financials_sector_metrics": {"gross_loan": 250}}]}
    final = {"insights": [{"observation": "A record lists company loans.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/0/gross_loan"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert problems == []
    assert enriched["insights"][0]["citations"] == [{
        "endpoint": endpoint,
        "field_path": "/data/0/financials_sector_metrics/gross_loan",
        "value": 250}]


def test_host_rejects_ambiguous_structural_suffix_recovery():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"left": {"data": [{"revenue": 250}]},
               "right": {"data": [{"revenue": 300}]}}
    final = {"insights": [{"observation": "A record lists company revenue.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/0/revenue"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert enriched["insights"][0]["citations"] == []
    assert "does not resolve uniquely" in " ".join(problems)


def test_quarterly_ordered_subsequence_recovers_metric_for_one_row():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [
        {"period": "2026-Q2", "financials_sector_metrics": {"total_deposit": 250}},
        {"period": "2026-Q1", "financials_sector_metrics": {"total_deposit": 220}},
    ]}
    final = {"insights": [{"observation": "A record lists company deposits.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/0/total_deposit"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert problems == []
    assert enriched["insights"][0]["citations"] == [{
        "endpoint": endpoint,
        "field_path": "/data/0/financials_sector_metrics/total_deposit",
        "value": 250}]


def test_quarterly_key_only_recovery_rejects_ambiguous_metric_rows():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [
        {"financials_sector_metrics": {"total_deposit": 250}},
        {"financials_sector_metrics": {"total_deposit": 220}},
    ]}
    final = {"insights": [{"observation": "A record lists company deposits.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/total_deposit"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert enriched["insights"][0]["citations"] == []
    assert "does not resolve uniquely" in " ".join(problems)


def test_quarterly_row_and_metric_anchors_recover_wrong_parent_uniquely():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"non_interest_income": 250}]}
    final = {"insights": [{"observation": "A record lists company income.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/0/financials_sector_metrics/non_interest_income"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert problems == []
    assert enriched["insights"][0]["citations"] == [{
        "endpoint": endpoint, "field_path": "/data/0/non_interest_income", "value": 250}]


def test_quarterly_row_and_metric_anchors_reject_same_row_duplicates():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"data": [{"segment_a": {"non_interest_income": 250},
                         "segment_b": {"non_interest_income": 220}}]}
    final = {"insights": [{"observation": "A record lists company income.",
                            "implication": "It gives context for business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/0/financials_sector_metrics/non_interest_income"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert enriched["insights"][0]["citations"] == []
    assert "does not resolve uniquely" in " ".join(problems)


def test_host_rejects_ambiguous_terminal_pointer_recovery():
    endpoint = "/financials/quarterly/TEST/"
    payload = {"quarterly": {"revenue": 250}, "annual": {"revenue": 900}}
    final = {"insights": [{"observation": "A record lists company revenue.",
                            "implication": "It gives context for understanding business activity.",
                            "caveat": "A single record does not establish a trend.",
                            "citations": [{"endpoint": endpoint,
                                           "field_path": "/wrong/path/revenue"}]}]}
    enriched, problems = research._host_enrich_citations(
        "TEST", final, [{"endpoint": endpoint, "payload": payload}])
    assert enriched["insights"][0]["citations"] == []


def test_news_and_quarter_metric_must_share_one_insight():
    ticker = "TEST"
    news = "/news/"
    quarter = "/financials/quarterly/TEST/"
    article = {"title": "TEST lending context", "body": "The article discusses lending conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/lending",
               "symbols": ["TEST"]}
    evidence = [
        {"endpoint": "/company/report/TEST/",
         "payload": {"overview": {"latest_close_date": "2026-09-11"}}},
        {"endpoint": news, "payload": {"results": [article]}},
        {"endpoint": quarter, "payload": {"data": [{"fiscal_period": "2026-Q2", "gross_loan": 1500}]}},
    ]
    news_citations = [{"endpoint": news, "field_path": f"/results/0/{key}", "value": article[key]}
                      for key in ("title", "body", "timestamp", "source")]
    quarter_citation = {"endpoint": quarter, "field_path": "/data/0/gross_loan", "value": 1500}
    news_insight = {"observation": "The article discusses lending conditions.",
                    "implication": "This gives market context for reviewing company activity.",
                    "caveat": "The article does not measure issuer-level earnings.",
                    "citations": news_citations}
    quarter_insight = {"observation": "The cached quarter records the company loan balance.",
                       "implication": "This offers company-level operating context.",
                       "caveat": "A single quarter does not establish a trend.",
                       "citations": [quarter_citation]}

    def document(insights):
        return {"ticker": ticker, "as_of": "2026-09-11", "status": "research_brief",
                "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
                "limitations": research._expected_limitations(insights),
                "agent_trace": {}, "insights": insights}

    split = document([news_insight, quarter_insight])
    problems = research._validate_document(ticker, split, evidence)
    assert "relevant cached news and quarterly evidence must be connected in the same insight" in problems

    connected = {"observation": "Cache mengaitkan TEST dengan artikel tentang lending.",
                 "implication": "Catatan gross loan TEST memberi konteks untuk membaca pembahasan lending.",
                 "caveat": "The article does not measure issuer-level earnings or explain the metric.",
                 "citations": news_citations + [quarter_citation]}
    problems = research._validate_document(ticker, document([connected]), evidence)
    assert problems == []


def test_quarter_only_final_checks_news_and_accepts_when_no_relevant_article(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    quarter = "/financials/quarterly/TEST/"
    news = "/news/"
    endpoints = [report, quarter, news]
    payloads = {
        report: {"overview": {"latest_close_date": "2026-09-11"}},
        quarter: {"data": [{"fiscal_period": "2026-Q2", "revenue": 100}]},
        news: {"results": [{"title": "Other issuer update", "body": "A separate company reports news.",
                             "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/other",
                             "symbols": ["OTHER"]}]},
    }
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: endpoints)
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payloads.get(ep))
    quarter_insight = {"observation": "The cached quarter records company revenue.",
                       "implication": "This provides context about business activity.",
                       "caveat": "A single record does not establish a trend.",
                       "citations": [{"endpoint": quarter, "field_path": "/data/0/revenue"}]}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", quarter]}),
                 json.dumps({"final": {"summary": "", "limitations": [],
                                      "insights": [quarter_insight]}})]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 2
    assert result["agent_trace"]["selected_cache_endpoints"] == [report, quarter, news]


def test_quarter_only_final_checks_relevant_news_and_requires_connected_insight(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    quarter = "/financials/quarterly/TEST/"
    news = "/news/"
    article = {"title": "TEST lending context", "body": "The article discusses lending conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/lending",
               "symbols": ["TEST"]}
    payloads = {
        report: {"overview": {"latest_close_date": "2026-09-11"}},
        quarter: {"data": [{"fiscal_period": "2026-Q2", "revenue": 100}]},
        news: {"results": [article]},
    }
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [report, quarter, news])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payloads.get(ep))
    quarter_insight = {"observation": "The cached quarter records company revenue.",
                       "implication": "This provides context about business activity.",
                       "caveat": "A single record does not establish a trend.",
                       "citations": [{"endpoint": quarter, "field_path": "/data/0/revenue"}]}
    connected = {"observation": "Cache mengaitkan TEST dengan artikel tentang lending.",
                 "implication": "Pendapatan TEST memberi konteks kuartalan untuk membaca pembahasan lending.",
                 "caveat": "The article does not measure issuer-level earnings.",
                 "citations": [{"endpoint": news, "field_path": f"/results/0/{key}"}
                               for key in ("title", "body", "timestamp", "source")] +
                              [{"endpoint": quarter, "field_path": "/data/0/revenue"}]}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", quarter]}),
                 json.dumps({"final": {"summary": "", "limitations": [],
                                      "insights": [quarter_insight]}}),
                 json.dumps({"final": {"summary": "", "limitations": [],
                                      "insights": [quarter_insight]}}),
                 json.dumps({"final": {"summary": "", "limitations": [], "insights": [connected]}})]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 4
    continuation_prompt = seen[2][-1]["content"]
    assert "/results/0/title" in continuation_prompt
    assert "/results/0/body" in continuation_prompt
    assert "/results/0/timestamp" in continuation_prompt
    assert "/results/0/source" in continuation_prompt
    assert "/data/0/revenue" in continuation_prompt
    assert "tepat SATU insight" in continuation_prompt
    assert "TEST" in continuation_prompt
    assert "lending" in continuation_prompt
    assert "revenue" in continuation_prompt
    assert [message["role"] for message in seen[3]] == ["system", "user", "user"]
    assert "/data/0/revenue" in seen[3][1]["content"]
    assert "Preserve one insight" in seen[3][2]["content"]
    assert result["agent_trace"]["selected_cache_endpoints"] == [report, quarter, news]
    assert {c["endpoint"] for c in result["document"]["insights"][0]["citations"]} == {news, quarter}


def test_model_read_news_and_quarter_split_final_uses_compact_join_repair(monkeypatch, tmp_path):
    report = "/company/report/TEST/"
    news = "/news/"
    quarter = "/financials/quarterly/TEST/"
    article = {"title": "TEST lending context", "body": "The article discusses lending conditions.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/lending",
               "symbols": ["TEST"]}
    payloads = {
        report: {"overview": {"latest_close_date": "2026-09-11"}},
        news: {"results": [article]},
        quarter: {"data": [{"revenue": 100}]},
    }
    monkeypatch.setattr(research.cache_tools, "cache_endpoints", lambda ticker: [report, news, quarter])
    monkeypatch.setattr(research.cache_tools, "cache_get", lambda ticker, ep: payloads.get(ep))
    news_only = {"observation": "The article discusses lending conditions.",
                 "implication": "This gives context for business activity.",
                 "caveat": "The article does not measure issuer-level earnings.",
                 "citations": [{"endpoint": news, "field_path": f"/results/0/{key}"}
                               for key in ("title", "body", "timestamp", "source")]}
    quarter_only = {"observation": "The cached quarter records company revenue.",
                    "implication": "This gives context for business activity.",
                    "caveat": "A single quarter does not establish a trend.",
                    "citations": [{"endpoint": quarter, "field_path": "/data/0/revenue"}]}
    joined = {"observation": "Cache mengaitkan TEST dengan artikel tentang lending.",
              "implication": "Pendapatan TEST memberi konteks kuartalan untuk membaca pembahasan lending.",
              "caveat": "Artikel tidak mengukur dampak pada kinerja emiten.",
              "citations": news_only["citations"] + quarter_only["citations"]}
    responses = [json.dumps({"tool": "cache_get", "args": ["TEST", news]}),
                 json.dumps({"tool": "cache_get", "args": ["TEST", quarter]}),
                 json.dumps({"final": {"summary": "", "limitations": [],
                                      "insights": [news_only, quarter_only]}}),
                 json.dumps({"final": {"summary": "", "limitations": [], "insights": [joined]}})]
    seen = []
    monkeypatch.setattr(research, "_chat", lambda messages: (seen.append(messages), responses.pop(0))[1])

    result = research.run_live("TEST", db=tmp_path)
    assert result["ok"] is True
    assert len(seen) == 4
    assert [message["role"] for message in seen[3]] == ["system", "user", "user"]
    assert "/results/0/title" in seen[3][1]["content"]
    assert "/data/0/revenue" in seen[3][1]["content"]
    assert result["agent_trace"]["selected_cache_endpoints"] == [report, news, quarter]


def test_crosslink_quality_rejects_boilerplate_and_accepts_specific_bbca_paraphrase():
    ticker = "BBCA"
    report = "/company/report/BBCA/"
    news = "/news/"
    quarter = "/financials/quarterly/BBCA/"
    article = {"title": "Global markets face pressure", "body": "Global market pressure affects banks.",
               "timestamp": "2026-09-10T10:00:00Z", "source": "https://news.test/global-pressure",
               "symbols": ["BBCA"]}
    evidence = [
        {"endpoint": report, "payload": {"overview": {"latest_close_date": "2026-09-11"}}},
        {"endpoint": news, "payload": {"results": [article]}},
        {"endpoint": quarter, "payload": {"data": [{"interest_income": 900}]}},
    ]
    citations = [{"endpoint": news, "field_path": f"/results/0/{key}", "value": article[key]}
                 for key in ("title", "body", "timestamp", "source")] + [
        {"endpoint": quarter, "field_path": "/data/0/interest_income", "value": 900}]

    def document(insight):
        return {"ticker": ticker, "as_of": "2026-09-11", "status": "research_brief",
                "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
                "limitations": research._expected_limitations([insight]),
                "agent_trace": {}, "insights": [insight]}

    boilerplate = {"observation": "Artikel membahas konteks operasional perusahaan.",
                   "implication": "Catatan kuartalan memberi konteks perusahaan di samping berita.",
                   "caveat": "Artikel tidak mengukur dampak pada kinerja emiten.",
                   "citations": citations}
    problems = research._validate_document(ticker, document(boilerplate), evidence)
    assert any("must name the ticker" in issue for issue in problems)
    assert any("must describe the cited quarterly metric" in issue for issue in problems)
    assert any("meaningful subject" in issue for issue in problems)

    specific = {"observation": "Cache mengaitkan BBCA dengan artikel tentang pasar global.",
                "implication": "Pendapatan bunga BBCA memberi konteks untuk membaca tekanan pasar global.",
                "caveat": "Artikel tidak mengukur dampak pada kinerja emiten.",
                "citations": citations}
    generic_global = {"observation": "Cache mengaitkan BBCA dengan artikel tentang global.",
                      "implication": "Pendapatan bunga BBCA memberi konteks untuk membaca bahasan global.",
                      "caveat": "Artikel tidak mengukur dampak pada kinerja emiten.",
                      "citations": citations}
    problems = research._validate_document(ticker, document(generic_global), evidence)
    assert any("meaningful subject" in issue for issue in problems)
    assert research._validate_document(ticker, document(specific), evidence) == []
