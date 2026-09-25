"""API routes and trust boundaries of the web server (FastAPI + built React app)."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from app import jobs as jobs_module, outputs, server  # noqa: E402
from test_gallery import _report, approve  # noqa: E402


@pytest.fixture
def make_client(tmp_path):
    clients = []

    def build(outdir=None, reports=None, static_dir=None):
        app = server.create_app(outdir or tmp_path / "out", reports, static_dir=static_dir)
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)


def wait_for_job(client, job_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["state"] in ("completed", "error"):
            return state
        time.sleep(.01)
    raise AssertionError("job did not finish")


def submit(client, ticker):
    response = client.post("/api/jobs", json={"ticker": ticker})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_invalid_ticker_never_submits_a_job(make_client):
    client = make_client()
    response = client.post("/api/jobs", json={"ticker": "../../secret"})
    assert response.status_code == 400
    assert "kode emiten yang valid" in response.json()["detail"]
    assert client.app.state.jobs._jobs == {}


def test_run_returns_partial_status_and_only_known_artifacts(monkeypatch, make_client):
    def fake_run(ticker, outdir, want_pdf=False):
        assert ticker == "AMMN" and want_pdf is False
        (outdir / "AMMN.html").write_text("<h1>Validated company update</h1>", encoding="utf-8")
        (outdir / "AMMN-trace.html").write_text("<h1>Agent trace</h1>", encoding="utf-8")
        outputs.save(outputs.TRACE, outdir, "AMMN", {"ticker": "AMMN", "secret": "x"})
        # Returned arbitrary paths and unexpected fields never reach the response.
        return {"research_ok": False, "report_status": "draft_non_distributable",
                "report_html": "/etc/passwd", "cache": {"private": "must-not-appear"}}

    monkeypatch.setattr(jobs_module.research, "run", fake_run)
    client = make_client()
    job_id = submit(client, "ammn")
    state = wait_for_job(client, job_id)
    assert state["state"] == "completed" and state["quality"] == "partial"
    assert state["report_status"] == "draft_non_distributable"
    dumped = json.dumps(state)
    assert "private" not in dumped and "/etc/passwd" not in dumped
    assert state["report_url"] == f"/files/jobs/{job_id}/AMMN.html"
    assert state["trace_url"] == f"/jobs/{job_id}/jejak"

    report = client.get(state["report_url"])
    assert report.status_code == 200 and report.headers["content-type"].startswith("text/html")
    assert "Validated company update" in report.text
    # The standalone trace links to its report by relative filename.
    assert "Agent trace" in client.get(f"/files/jobs/{job_id}/AMMN-trace.html").text
    for bad in (f"/files/jobs/{job_id}/BBCA.html", f"/files/jobs/{job_id}/AMMN.pdf",
                f"/files/jobs/{job_id}/..%2F..%2Fetc%2Fpasswd", "/api/jobs/..%2F..%2Fetc%2Fpasswd",
                "/api/jobs/not-a-job"):
        assert client.get(bad).status_code == 404, bad
    # The trace JSON is served only as its public view.
    view = client.get(f"/api/jobs/{job_id}/trace").json()
    assert view["ticker"] == "AMMN" and "secret" not in json.dumps(view)


def test_repeated_ticker_runs_keep_artifacts_isolated(monkeypatch, make_client):
    runs = []

    def fake_run(ticker, outdir, want_pdf=False):
        marker = f"run-{len(runs) + 1}"
        runs.append(outdir)
        (outdir / f"{ticker}.html").write_text(marker, encoding="utf-8")
        (outdir / f"{ticker}-trace.html").write_text(marker + " trace", encoding="utf-8")
        return {"research_ok": True, "report_status": "complete"}

    monkeypatch.setattr(jobs_module.research, "run", fake_run)
    client = make_client()
    ids = [submit(client, "AMMN") for _ in range(2)]
    for job_id in ids:
        assert wait_for_job(client, job_id)["state"] == "completed"
    assert len(set(runs)) == 2
    assert client.get(f"/files/jobs/{ids[0]}/AMMN.html").text == "run-1"
    assert client.get(f"/files/jobs/{ids[1]}/AMMN.html").text == "run-2"


def test_failure_detail_is_not_returned_over_http(monkeypatch, make_client):
    def fake_run(*_args, **_kwargs):
        raise RuntimeError("api_key=FAKE_SECRET cache_payload=private-data")

    monkeypatch.setattr(jobs_module.research, "run", fake_run)
    client = make_client()
    state = wait_for_job(client, submit(client, "BBCA"))
    assert state["state"] == "error"
    assert "FAKE_SECRET" not in json.dumps(state) and "private-data" not in json.dumps(state)


def test_symlink_artifact_outside_output_directory_is_not_served(monkeypatch, make_client, tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("outside secret", encoding="utf-8")

    def fake_run(ticker, outdir, want_pdf=False):
        (outdir / f"{ticker}.html").symlink_to(outside)
        (outdir / f"{ticker}-trace.html").write_text("trace", encoding="utf-8")
        return {"research_ok": True, "report_status": "complete"}

    monkeypatch.setattr(jobs_module.research, "run", fake_run)
    client = make_client()
    job_id = submit(client, "TEST")
    assert wait_for_job(client, job_id)["state"] == "error"
    assert client.get(f"/files/jobs/{job_id}/TEST.html").status_code == 404


def test_job_api_streams_progress_and_exposes_only_whitelisted_intel(monkeypatch, make_client):
    from app.progress import emit

    intel = {
        "ticker": "SIDO", "name": "Sido", "status": "ok", "secret_payload": "must-not-appear",
        "plan": {"question": "Q?", "hypotheses": ["H1"], "source": "agent", "raw": "must-not-appear"},
        "steps": [{"tool": "rank_peers", "why": "posisi", "summary": "5 sinyal", "status": "ok",
                   "origin": "agent", "args": {"metrics": ["roe"]}}],
        "signals": [{"id": "peer.roe", "kind": "peer", "label": "ROE", "display": "39,4%", "rank": 1,
                     "n": 10, "value": 0.394, "source": "internal-path", "peers": [{"symbol": "KLBF",
                     "display": "14,6%", "value": 0.146}]}],
        "synthesis": {"headline": "H", "source": "agent", "findings": [{"title": "T", "interpretation": "I",
                      "caveat": "C", "signal_ids": ["peer.roe"]}], "hypotheses": [], "next_checks": []},
        "changes": {"first_run": True, "items": []},
    }

    def fake_run(ticker, outdir, want_pdf=False):
        emit("plan", "Rencana siap", "Q?")
        emit("tool", "rank_peers selesai", "5 sinyal", tool="rank_peers")
        (outdir / "SIDO.html").write_text("report", encoding="utf-8")
        (outdir / "SIDO-trace.html").write_text("trace", encoding="utf-8")
        return {"research_ok": True, "report_status": "draft", "intel": intel}

    monkeypatch.setattr(jobs_module.research, "run", fake_run)
    client = make_client()
    state = wait_for_job(client, submit(client, "SIDO"))
    assert [e["label"] for e in state["events"]] == ["Rencana siap", "rank_peers selesai"]
    assert state["events"][1]["tool"] == "rank_peers"
    public = state["intel"]
    assert public["signals"][0]["rank"] == 1 and public["signals"][0]["peers"][0]["symbol"] == "KLBF"
    assert public["synthesis"]["findings"][0]["signal_ids"] == ["peer.roe"]
    dumped = json.dumps(state)
    for hidden in ("must-not-appear", "internal-path", "secret_payload", "0.146"):
        assert hidden not in dumped


def test_long_agent_text_is_cut_at_a_word_boundary():
    cut = jobs_module.text("kata " * 100, 40)
    assert len(cut) <= 40 and cut.endswith("kata…")


def test_history_lists_remembered_runs(make_client):
    from agents.analyst import memory

    memory.save("SIDO", {"run_at": "2026-09-24T01:00:00+00:00", "market_date": "2026-09-22",
                         "signals": [{"id": "peer.roe", "label": "ROE", "flag": "tertinggi di grup"}],
                         "headlines": []})
    items = make_client().get("/api/history").json()["items"]
    sido = next(i for i in items if i["ticker"] == "SIDO")
    assert sido["flags"] == 1 and sido["market_date"] == "2026-09-22"


def test_reports_api_and_files_are_confined(make_client, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    _report(reports, "BBBB", published=False)
    client = make_client(reports=reports)
    items = client.get("/api/reports").json()["items"]
    assert [i["ticker"] for i in items] == ["AAAA", "BBBB"]
    pdf = client.get("/files/reports/AAAA.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert client.get("/files/reports/AAAA-trace.html").status_code == 200
    for bad in ("/files/reports/AAAA.json", "/files/reports/AAAA-trace.json", "/files/reports/AAAA.secrets",
                "/files/reports/..%2FAAAA.pdf", "/files/reports/ZZZZ.pdf"):
        assert client.get(bad).status_code == 404, bad


def test_report_trace_view_returns_only_public_fields(make_client, tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    audit = {
        "ticker": "AAAA",
        "report": {"status": "distributable_assumption_led", "rating": "Hold", "target_price": 1100,
                   "target_method": "FY26F PER [fallback: DCF]", "as_of": "2026-09-24"},
        "research": {"document": {"summary": "S", "insights": [{"title": "T", "observation": "O",
                     "citations": [{"endpoint": "/daily/AAAA/", "field_path": "close", "value": 1}]}],
                     "agent_trace": {"selected_cache_endpoints": ["/daily/AAAA/"]}},
                     "path": "/home/secret/path"},
        "news_sources": {"search": {"status": "ok", "query": "AAAA"}, "rejected": [{"title": "X", "reason": "r"}],
                         "articles": [{"title": "A", "source": "javascript:alert(1)"}]},
        "forecast_assumptions": {"status": "validated", "plan": {"outyear_scenario": [
            {"year": 2027, "revenue_growth_pct": 5, "rationale": "R"}]}, "api_key": "FAKE"},
        "evidence_register": {"private": "must-not-appear"},
    }
    outputs.save(outputs.TRACE, reports, "AAAA", audit)
    pending = make_client(reports=reports).get("/api/reports/AAAA/trace").json()
    # Until an analyst approves the plan, the gallery trace holds the rating.
    assert pending["review_state"] == "pending" and pending["report"]["target_price"] is None
    approve(reports, "AAAA")
    view = client_view = make_client(reports=reports).get("/api/reports/AAAA/trace")
    assert view.status_code == 200
    body = client_view.json()
    assert body["review_state"] == "approved"
    assert body["report"]["method"] == "FY26F PER" and body["report"]["target_price"] == 1100
    assert body["research"]["endpoints"] == ["/daily/AAAA/"]
    assert body["news"]["articles"][0]["url"] is None  # only http(s) links pass
    assert body["forecast"]["outyears"][0]["revenue_growth_pct"] == 5
    dumped = json.dumps(body)
    for hidden in ("/home/secret/path", "FAKE", "must-not-appear"):
        assert hidden not in dumped
    assert make_client(reports=reports).get("/api/reports/ZZZZ/trace").status_code == 404


def test_spa_fallback_serves_index_but_never_escapes_or_shadows_api(make_client, tmp_path):
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<div id=root></div>")
    (static / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("secret")
    client = make_client(static_dir=static)
    for path in ("/", "/laporan", "/jobs/abc/jejak"):
        response = client.get(path)
        assert response.status_code == 200 and "id=root" in response.text, path
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert "secret" not in client.get("/..%2Fsecret.txt").text
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/files/unknown").status_code == 404


def test_store_import_moves_old_json_into_the_database_once(tmp_path):
    from app import store, store_import

    data = tmp_path / "data"
    (data / "agent_memory").mkdir(parents=True)
    (data / "agent_memory" / "SIDO.json").write_text(json.dumps({"ticker": "SIDO", "runs": [{"run_at": "x"}]}))
    (data / "fx_usdidr.json").write_text(json.dumps({"pair": "USD/IDR", "rate": 16000}))
    run = tmp_path / "out" / "run1"
    run.mkdir(parents=True)
    (run / "AAAA.json").write_text(json.dumps({"meta": {"ticker": "AAAA"}}))
    (run / "AAAA-trace.json").write_text(json.dumps({"ticker": "AAAA"}))
    (run / "summary.json").write_text(json.dumps([{"ticker": "AAAA"}]))
    (run / "notes.json").write_text("{}")

    counts = store_import.import_outputs(tmp_path / "out", counts=store_import.import_caches(data))
    assert counts["agent_memory"] == counts["fx"] == counts["report"] == counts["trace"] == 1
    assert outputs.load(outputs.REPORT, run, "AAAA") == {"meta": {"ticker": "AAAA"}}
    assert outputs.load(outputs.BATCH, run) == [{"ticker": "AAAA"}]
    assert store.get("fx", "USD/IDR")["rate"] == 16000
    # A second import keeps what the database already has.
    again = store_import.import_caches(data)
    assert again == {"kept": 2}
