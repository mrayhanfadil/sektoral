"""Planning analyst agent: local-only tools, signals, loop, validation, memory."""
from __future__ import annotations

import ast
import json
import urllib.request
from pathlib import Path

import pytest

from agents.analyst import memory, run as A, signals as S, tools as T
from app import progress, research

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------- local data only

def test_analyst_modules_never_import_the_sectors_network_client():
    for path in (ROOT / "agents" / "analyst").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(f"{node.module}.{alias.name}" for alias in node.names)
        forbidden = {"app.sectors", "urllib.request", "requests", "http.client"}
        assert not imported & forbidden, f"{path.name} imports {imported & forbidden}"


def test_every_tool_runs_from_local_data_without_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
    for ticker in ("AMMN", "BBCA", "SIDO"):
        state = {}
        for name in T.TOOLS:
            args = {"metrics": ["roe", "pe"]} if name == "rank_peers" else {}
            try:
                T.execute(name, ticker, args, state)
            except T.ToolError:
                pass  # missing data is reported to the agent, not fetched


def test_peer_group_uses_related_sectors_table_when_ticker_has_none():
    peers = T.find_peers("BBCA")
    assert peers["basis"].startswith("tabel peer Sectors milik ")
    assert [row["symbol"] for row in peers["rows"] if row["is_self"]] == ["BBCA"]
    assert len(peers["rows"]) >= 5


def test_unknown_tool_and_missing_metrics_are_refused():
    with pytest.raises(T.ToolError):
        T.execute("web_search", "AMMN", {}, {})
    with pytest.raises(T.ToolError):
        T.execute("rank_peers", "AMMN", {"metrics": ["made_up"]}, {})


# ------------------------------------------------------------------- signals

def _rows():
    return [S.peer_row("AAA", "A", net_income=30, equity=100, revenue=300, pe=10, is_self=True),
            S.peer_row("BBB", "B", net_income=10, equity=100, revenue=200, pe=20),
            S.peer_row("CCC", "C", net_income=5, equity=100, revenue=100, pe=-4),
            S.peer_row("DDD", "D", net_income=1, equity=100, revenue=100, pe=8)]


def test_peer_rank_median_and_flags_are_deterministic():
    roe, pe = S.rank_peers(_rows(), ["roe", "pe"], "test")
    assert roe["rank"] == 1 and roe["n"] == 4 and roe["flag"] == "tertinggi di grup"
    assert roe["display"] == "30,0%" and roe["median_display"] == "5,0%"
    # a negative P/E is not comparable and is excluded from the rank
    assert pe["n"] == 3 and pe["rank"] == 2 and pe["flag"] is None


def test_quarter_growth_handles_loss_base_and_missing_comparison():
    rows = [{"date": "2025-06-30", "revenue": 100, "earnings": -10},
            {"date": "2026-06-30", "revenue": 140, "earnings": 20}]
    found, _ = S.quarter_signals("X", rows)
    by_id = {s["id"]: s for s in found}
    assert by_id["quarter.revenue_yoy"]["flag"] == "lonjakan"
    assert by_id["quarter.earnings_yoy"]["value"] is None
    assert by_id["quarter.earnings_yoy"]["flag"] == "berbalik ke laba"
    found, _ = S.quarter_signals("X", rows[1:])
    assert all("tidak ada kuartal" in s["note"] for s in found)


def test_flow_streak_and_price_divergence():
    flow = S.flow_signals("X", [{"date": f"2026-01-{d:02d}", "net_foreign_inflow": v}
                                for d, v in enumerate([5, 5, -1, -2, -3, -4, -5], start=1)])
    streak = next(s for s in flow if s["id"] == "flow.streak")
    assert streak["value"] == 5 and streak["flag"] == "beruntun"
    price = [{"id": "price.return_window", "value": 0.2, "source": "p"}]
    cross = S.cross_signals(flow + price)
    assert cross[0]["flag"] == "divergensi asing vs harga"


# --------------------------------------------------------------- agent loop

PLAN = {"question": "Bagaimana posisi SIDO terhadap peer farmasi?",
        "hypotheses": ["Profitabilitas di atas median peer", "Laba kuartalan melemah"],
        "steps": [{"tool": "find_peers", "args": {}, "why": "grup"},
                  {"tool": "rank_peers", "args": {"metrics": ["roe", "net_margin"]}, "why": "posisi"},
                  {"tool": "quarterly_financials", "args": {}, "why": "tren"}]}
SYNTHESIS = {"headline": "Profitabilitas memimpin grup, laba kuartalan melemah",
             "findings": [{"title": "Margin teratas", "signal_ids": ["peer.net_margin"],
                           "interpretation": "Margin tertinggi di grup.", "caveat": "Data tahunan."}],
             "hypotheses": [{"index": 0, "verdict": "didukung", "signal_ids": ["peer.roe"],
                             "reason": "Peringkat teratas."},
                            {"index": 1, "verdict": "didukung", "signal_ids": ["quarter.earnings_yoy"],
                             "reason": "Laba turun."}],
             "next_checks": ["Periksa segmen"]}


def scripted(*responses):
    queue = [json.dumps(r) if isinstance(r, dict) else r for r in responses]
    calls = []

    def chat(messages):
        calls.append(messages)
        return queue.pop(0)
    chat.calls = calls
    return chat


def test_agent_plans_adapts_and_concludes_with_cited_signals(tmp_path):
    chat = scripted(PLAN,
                    {"calls": PLAN["steps"][:2]},
                    {"calls": [{"tool": "quarterly_financials", "args": {}, "why": "cek laba"},
                               {"tool": "foreign_flow", "args": {}, "why": "cek asing"}]},
                    {"done": True, "why": "cukup"},
                    SYNTHESIS)
    events = []
    with progress.capture(events.append):
        result = A.run("SIDO", chat=chat, memory_dir=tmp_path)
    assert result["status"] == "ok" and result["problems"] == []
    assert [(s["tool"], s["origin"]) for s in result["steps"]] == [
        ("find_peers", "agent"), ("rank_peers", "agent"),
        ("quarterly_financials", "agent"), ("foreign_flow", "agent_adaptive")]
    assert {"peer.roe", "quarter.earnings_yoy", "flow.net_20d"} <= {s["id"] for s in result["signals"]}
    assert result["synthesis"]["source"] == "agent"
    assert [e["stage"] for e in events][:3] == ["memory", "plan", "plan"]
    assert memory.latest("SIDO", tmp_path)["question"] == PLAN["question"]


def test_invalid_synthesis_is_repaired_then_accepted(tmp_path):
    bad = dict(SYNTHESIS, headline="Laba turun 49% dan saham layak dibeli")
    chat = scripted(PLAN, {"done": True}, bad, SYNTHESIS)
    result = A.run("SIDO", chat=chat, memory_dir=tmp_path)
    assert result["synthesis"]["source"] == "agent"
    repair = chat.calls[-1][-1]["content"]
    assert "49%" in repair and "layak dibeli" in repair
    # the planned steps the agent skipped were completed by the host
    assert {s["origin"] for s in result["steps"]} == {"host"}


def test_unrecoverable_synthesis_falls_back_to_labelled_host_summary(tmp_path):
    bad = dict(SYNTHESIS, findings=[dict(SYNTHESIS["findings"][0], signal_ids=["invented"])])
    result = A.run("SIDO", chat=scripted(PLAN, {"done": True}, bad, bad), memory_dir=tmp_path)
    assert result["status"] == "partial"
    assert result["synthesis"]["source"] == "host_fallback"
    assert all(v["verdict"] == "belum terjawab" for v in result["synthesis"]["hypotheses"])


def test_llm_outage_still_finishes_with_host_plan(tmp_path):
    def down(_messages):
        raise TimeoutError("provider timeout")
    result = A.run("AMMN", chat=down, memory_dir=tmp_path)
    assert result["status"] == "partial"
    assert result["plan"]["source"] == "host_fallback"
    assert result["signals"] and all(s["origin"] == "host" for s in result["steps"])
    assert any("TimeoutError" in p for p in result["problems"])


def test_plan_with_advice_or_unavailable_tool_is_rejected():
    available = {name: True for name in T.TOOLS}
    available["foreign_flow"] = False
    bad = dict(PLAN, question="Apakah SIDO layak dibeli?",
               steps=PLAN["steps"] + [{"tool": "foreign_flow", "args": {}}])
    problems = A._plan_problems(bad, available)
    assert any("rekomendasi" in p for p in problems)
    assert any("foreign_flow tidak tersedia" in p for p in problems)


def test_flow_descriptions_are_not_mistaken_for_advice():
    assert A._advice_terms("Asing mencatat jual bersih; aksi beli mereda") == []
    assert A._advice_terms("Investor sebaiknya jual") == ["jual"]
    assert A._advice_terms("valuasi sudah menarik") == ["valuasi sudah menarik"]


# ------------------------------------------------------------------- memory

def test_memory_diff_reports_rank_moves_new_flags_and_news(tmp_path):
    before = {"run_at": "2026-09-01", "market_date": "2026-08-29", "headlines": ["Lama"],
              "signals": {"peer.roe": {"label": "ROE", "display": "10%", "rank": 3, "n": 9, "flag": None}}}
    after = {"run_at": "2026-09-20", "market_date": "2026-09-19", "headlines": ["Lama", "Baru"],
             "signals": {"peer.roe": {"label": "ROE", "display": "14%", "rank": 1, "n": 9,
                                      "flag": "tertinggi di grup"}}}
    items = [i["kind"] for i in memory.diff(before, after)["items"]]
    assert items == ["rank", "new_flag", "news"]
    assert memory.diff(None, after) == {"first_run": True, "items": []}


def test_memory_keeps_recent_runs_and_lists_watchlist(tmp_path):
    for i in range(memory.KEEP_RUNS + 3):
        memory.save("SIDO", {"run_at": f"2026-09-{i + 1:02d}", "signals": [], "headlines": []}, tmp_path)
    assert len(memory.load("SIDO", tmp_path)) == memory.KEEP_RUNS
    assert memory.watchlist(tmp_path)[0]["ticker"] == "SIDO"
    with pytest.raises(ValueError):
        memory.save("../x", {}, tmp_path)


# ---------------------------------------------------------------- pipeline

def test_analyst_failure_never_blocks_the_company_update(monkeypatch):
    def broken(_ticker):
        raise KeyError("bad data")
    monkeypatch.setattr("agents.analyst.run.run", broken)
    result = research.run_analyst("AMMN")
    assert result["status"] == "error" and "KeyError" in result["problems"][0]


def test_leaked_non_latin_tokens_are_stripped_or_rejected():
    assert A._clean("grup peer untuk perbandingan接下来.") == "grup peer untuk perbandingan ."
    bad = dict(SYNTHESIS, headline="Profitabilitas memimpin接下来")
    problems = A._synthesis_problems(bad, {"peer.net_margin", "peer.roe", "quarter.earnings_yoy"}, 2)
    assert any("bahasa Indonesia" in p for p in problems)


# --------------------------------------------------------------- web context

import urllib.error  # noqa: E402

from app import tavily  # noqa: E402


def _http_error(code):
    return urllib.error.HTTPError(tavily.ENDPOINT, code, "err", {}, None)


def test_tavily_keys_rotate_round_robin_and_retire_on_quota():
    ring = tavily.KeyRing(["k1", "k2", "k3", "k4"])
    ring._next = 0
    assert [ring.take()[1] for _ in range(5)] == ["k1", "k2", "k3", "k4", "k1"]
    used = []

    def post(key, body):
        used.append(key)
        if key == "k2":
            raise _http_error(432)  # plan limit: move to the next key
        return {"results": []}

    ring._next = 1
    tavily._search({}, ring=ring, post=post)
    assert used == ["k2", "k3"]
    used.clear()
    ring._next = 1
    tavily._search({}, ring=ring, post=post)
    assert used == ["k3"]  # k2 stays retired


def test_tavily_errors_never_expose_keys():
    ring = tavily.KeyRing(["tvly-SECRET1", "tvly-SECRET2"])

    def post(key, body):
        raise _http_error(401)

    with pytest.raises(tavily.TavilyError) as error:
        tavily._search({}, ring=ring, post=post)
    assert "SECRET" not in str(error.value)


def test_keys_are_read_from_list_and_numbered_variables(monkeypatch, tmp_path):
    monkeypatch.setattr(tavily, "ROOT", tmp_path)
    monkeypatch.setattr(tavily, "_dotenv_keys", lambda path=None: {})
    monkeypatch.setenv("TAVILY_API_KEYS", "a, b")
    monkeypatch.setenv("TAVILY_API_KEY_3", "c")
    monkeypatch.setenv("TAVILY_API_KEY_4", "a")
    assert sorted(tavily.load_keys()) == ["a", "b", "c"]


def test_web_news_keeps_only_dated_items_inside_window_and_reuses_store(tmp_path):
    calls = []

    def post(key, body):
        calls.append(body)
        return {"results": [
            {"title": "Dalam jendela", "url": "https://www.kontan.co.id/a", "content": "isi",
             "published_date": "Tue, 08 Sep 2026 10:00:00 GMT"},
            {"title": "Setelah tanggal data", "url": "https://bisnis.com/b",
             "published_date": "2026-09-20T01:00:00Z"},
            {"title": "Tanpa tanggal", "url": "https://bisnis.com/c", "published_date": None},
            {"title": "Skema aneh", "url": "javascript:alert(1)",
             "published_date": "Tue, 08 Sep 2026 10:00:00 GMT"}]}

    ring = tavily.KeyRing(["k"])
    first = tavily.news_context("AMMN", "PT Amman Mineral Internasional Tbk.", "2026-09-11",
                                ring=ring, post=post, store_dir=tmp_path)
    assert [i["title"] for i in first["items"]] == ["Dalam jendela"]
    assert first["items"][0]["domain"] == "kontan.co.id"
    assert calls[0]["topic"] == "news" and calls[0]["end_date"] == "2026-09-11"
    again = tavily.news_context("AMMN", "PT Amman Mineral Internasional Tbk.", "2026-09-11",
                                ring=ring, post=post, store_dir=tmp_path)
    assert again["from_store"] is True and len(calls) == 1


def test_web_news_is_unavailable_without_keys_and_cannot_be_sole_evidence():
    assert T.overview("AMMN")["available"]["web_news"] is False
    with pytest.raises(T.ToolError):
        T.execute("web_news", "AMMN", {}, {})
    web_only = dict(SYNTHESIS, findings=[dict(SYNTHESIS["findings"][0], signal_ids=["web.0"])])
    problems = A._synthesis_problems(web_only, {"web.0", "peer.roe", "quarter.earnings_yoy"}, 2)
    assert any("sinyal Sectors" in p for p in problems)


def test_web_news_tool_turns_articles_into_citable_context(monkeypatch):
    monkeypatch.setattr(tavily, "configured", lambda: True)
    monkeypatch.setattr(tavily, "news_context", lambda *a, **k: {
        "window": "2026-07-13 s.d. 2026-09-11",
        "items": [{"title": "Smelter AMMN", "url": "https://kontan.co.id/x", "domain": "kontan.co.id",
                   "date": "2026-09-01", "snippet": "konteks"}]})
    state = {}
    result, found = T.execute("web_news", "AMMN", {}, state)
    assert result["articles"][0]["id"] == "web.0"
    assert found[0]["kind"] == "web" and found[0]["source"] == T.WEB_SOURCE
    assert found[0]["value"] is None and found[0]["flag"] is None
