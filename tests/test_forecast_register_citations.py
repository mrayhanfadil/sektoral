"""The Evidence Register a subagent reads cites only what its validator accepts.

BBCA's and AMMN's 2026-10-06 runs failed the earnings and out-year roles on
every attempt with "must cite valid source_ids": the register in the prompt
listed twelve articles as register_id src-N (and filings by row_id), while
the agent is handed, and may cite, only the first six as news:N. No real LLM.
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.forecast_assumptions import run as agent  # noqa: E402
from test_bank_model import OFFICIAL  # noqa: E402
from test_forecast_bank_agent import (  # noqa: E402
    NEWS, STAGE, _earnings, _intake, _outyears, _scripted)


def _article(i):
    return {"title": f"BCA: kabar kredit dan dana pihak ketiga ke-{i}",
            "timestamp": "2026-08-10", "source": f"https://news.example/bca-{i}",
            "origin": "sectors", "register_id": f"src-{i}",
            "body": "Kredit BCA tumbuh 8% yoy; NIM 5,5-5,7% hingga akhir tahun."}


ARTICLES = [_article(i) for i in range(8)]   # two past the six the agent is handed


def _register():
    rows = [{"kind": "official_actual", "source": OFFICIAL["source_url"],
             "row_id": "evidence:official_actual:aaa"},
            {"kind": "official_filing", "name": "bca-1h26-pl",
             "row_id": "evidence:official_filing:bbb"},
            {"kind": "driver_source", "name": "bca-fy25-dividend",
             "row_id": "evidence:driver_source:ccc"},
            {"kind": "company_guidance", "name": "kredit 2026",
             "row_id": "evidence:company_guidance:ddd"}]
    rows += [{"kind": "sectors_article", "register_id": a["register_id"], "url": a["source"],
              "title": a["title"], "published_at": a["timestamp"],
              "row_id": f"evidence:sectors_article:{i}"} for i, a in enumerate(ARTICLES)]
    return {"ticker": "UJIB", "as_of": "2026-09-24", "rows": rows,
            "violations": [], "critical_violations": []}


def _bank_intake():
    intake = _intake()
    intake["news"] = copy.deepcopy(ARTICLES)
    intake["official_evidence"]["management_guidance"] = [
        {"name": "kredit 2026", "value": 8, "unit": "%", "period": 2026,
         "source_url": OFFICIAL["source_url"], "published_at": OFFICIAL["published_at"]}]
    intake["evidence_register"] = _register()
    return intake


def test_the_register_lists_only_supplied_articles_and_how_to_cite_each_row():
    source = agent._source_payload(_bank_intake())
    assert [item["index"] for item in source["news"]] == list(range(6))

    view = agent._agent_register(source["evidence_register"], source,
                                 agent._role_source_ids("earnings", source))
    ids = {row.get("register_id") or row["kind"]: row["source_id"] for row in view["rows"]}
    assert ids == {"official_actual": "official", "official_filing": None,
                   "driver_source": None, "company_guidance": "guidance:0",
                   **{f"src-{i}": f"news:{i}" for i in range(6)}}
    # An article past the supplied news has no news:N, so the agent never sees it.
    assert "src-6" not in ids and "src-7" not in ids
    # The non-bank out-year validator takes no guidance:N.
    outyear = agent._agent_register(source["evidence_register"], source, {"official"} |
                                    {f"news:{i}" for i in range(6)})
    assert next(r for r in outyear["rows"]
                if r["kind"] == "company_guidance")["source_id"] is None
    # The stored register (and so the evidence fingerprint) is left as it was.
    assert len(source["evidence_register"]["rows"]) == 12
    assert all("source_id" not in row for row in source["evidence_register"]["rows"])


def test_an_uncited_register_id_is_named_in_the_repair_with_the_valid_ids(monkeypatch):
    bad = _earnings()
    bad["earnings_scenario"]["key_risks"][0]["source_ids"] = ["official", "src-7"]
    bad["earnings_scenario"]["bank_drivers"]["source_ids"] = ["official", "news:7"]
    chat, calls = _scripted({
        "NEWS DRIVER ANALYST": [{"news_effects": [
            dict(NEWS["news_effects"][0], article_index=i, source_url=a["source"],
                 title=a["title"], timestamp=a["timestamp"])
            for i, a in enumerate(ARTICLES[:6])]}],
        "BANK DRIVER SCENARIO ANALYST": [bad, _earnings()],
        "STAGE CLASSIFIER": [STAGE], "BANK DRIVER OUTYEAR ANALYST": [_outyears()]})
    monkeypatch.setattr(agent, "_chat", chat)
    result = agent.run_live(_bank_intake())
    assert result["earnings_status"] == "validated", result["problems"]

    earnings_calls = [m for role, m in calls if role == "BANK DRIVER SCENARIO ANALYST"]
    assert len(earnings_calls) == 2
    payload = json.loads(earnings_calls[0][1]["content"])
    assert payload["allowed_source_ids"] == sorted(
        ["official", "guidance:0", *[f"news:{i}" for i in range(6)]])
    cited = [row["source_id"] for row in payload["evidence_register"]["rows"]
             if row["kind"] == "sectors_article"]
    assert cited == [f"news:{i}" for i in range(6)]
    assert "only by its source_id" in earnings_calls[0][0]["content"]
    repair = earnings_calls[1][-1]["content"]
    assert "source_ids not supplied to this role: ['news:7', 'src-7']" in repair
    assert "'guidance:0'" in repair and "'news:5'" in repair
