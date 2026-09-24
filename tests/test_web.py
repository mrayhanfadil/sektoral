"""Route and trust-boundary checks for the local browser workflow."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import web


class RunningServer:
    def __init__(self, outdir):
        self.server = web.create_server(outdir, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.server.research_app.close()
        self.thread.join(timeout=2)


def request(server, path, method="GET", data=None):
    req = Request(server.base + path, data=data, method=method)
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    try:
        with build_opener(NoRedirect()).open(req, timeout=3) as response:
            return response.status, response.headers, response.read()
    except HTTPError as error:
        return error.code, error.headers, error.read()


def wait_for_job(server, job_id):
    import time

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        _, _, body = request(server, f"/api/jobs/{job_id}")
        state = json.loads(body)
        if state["state"] in ("completed", "error"):
            return state
        time.sleep(.01)
    raise AssertionError("job did not finish")


def test_research_route_shows_ticker_form_and_non_advisory_context(tmp_path):
    server = RunningServer(tmp_path)
    try:
        status, headers, body = request(server, "/research")
        page = body.decode()
        assert status == 200
        assert headers.get_content_type() == "text/html"
        assert 'name="ticker"' in page
        assert "Mulai riset" in page
        assert "bukan rekomendasi investasi" in page
    finally:
        server.close()


def test_invalid_ticker_never_submits_a_job(tmp_path):
    server = RunningServer(tmp_path)
    try:
        status, _, body = request(server, "/run", "POST", urlencode({"ticker": "../../secret"}).encode())
        assert status == 400
        assert "kode emiten yang valid" in body.decode()
        assert server.server.research_app._jobs == {}
    finally:
        server.close()


def test_run_returns_partial_status_and_only_known_html_artifacts(monkeypatch, tmp_path):
    def fake_run(ticker, outdir, want_pdf=False):
        assert ticker == "AMMN"
        assert want_pdf is False
        (outdir / "AMMN.html").write_text("<h1>Validated company update</h1>", encoding="utf-8")
        (outdir / "AMMN-trace.html").write_text("<h1>Agent trace</h1>", encoding="utf-8")
        # Returned arbitrary paths and any unexpected fields are not reflected
        # in the HTTP response; the web layer derives known artifact names.
        return {"research_ok": False, "report_status": "draft_non_distributable",
                "report_html": "/etc/passwd", "trace_json": str(outdir / "AMMN-trace.json"),
                "cache": {"private": "must-not-appear"}}

    monkeypatch.setattr(web.research, "run", fake_run)
    server = RunningServer(tmp_path)
    try:
        status, headers, _ = request(server, "/run", "POST", urlencode({"ticker": "ammn"}).encode())
        assert status == 303
        location = headers["Location"]
        job_id = location.split("/")[-1]
        state = wait_for_job(server, job_id)
        assert state["state"] == "completed"
        assert state["quality"] == "partial"
        assert state["report_status"] == "draft_non_distributable"
        assert "private" not in json.dumps(state)
        assert "/etc/passwd" not in json.dumps(state)
        assert state["report_url"] == f"/artifact/{job_id}/report"
        assert state["trace_url"] == f"/artifact/{job_id}/trace"

        report_status, report_headers, report = request(server, state["report_url"])
        trace_status, _, trace = request(server, state["trace_url"])
        assert report_status == trace_status == 200
        assert report_headers.get_content_type() == "text/html"
        assert b"Validated company update" in report
        assert b"Agent trace" in trace
        # The trace's relative "TICKER.html" report link resolves to the same report.
        linked_status, _, linked = request(server, f"/artifact/{job_id}/AMMN.html")
        assert linked_status == 200 and linked == report
        assert request(server, f"/artifact/{job_id}/BBCA.html")[0] == 404
        assert request(server, f"/artifact/{job_id}/AMMN-trace.html")[0] == 404
        assert request(server, f"/artifact/{job_id}/trace-json")[0] == 404
        assert request(server, f"/artifact/{job_id}/../../etc/passwd")[0] == 404
        assert request(server, "/api/jobs/../../etc/passwd")[0] == 404
    finally:
        server.close()


def test_repeated_ticker_runs_keep_artifacts_isolated(monkeypatch, tmp_path):
    runs = []

    def fake_run(ticker, outdir, want_pdf=False):
        marker = f"run-{len(runs) + 1}"
        runs.append((outdir, marker))
        (outdir / f"{ticker}.html").write_text(marker, encoding="utf-8")
        (outdir / f"{ticker}-trace.html").write_text(marker + " trace", encoding="utf-8")
        return {"research_ok": True, "report_status": "complete"}

    monkeypatch.setattr(web.research, "run", fake_run)
    server = RunningServer(tmp_path)
    try:
        job_ids = []
        for _ in range(2):
            _, headers, _ = request(server, "/run", "POST", urlencode({"ticker": "AMMN"}).encode())
            job_id = headers["Location"].split("/")[-1]
            assert wait_for_job(server, job_id)["state"] == "completed"
            job_ids.append(job_id)

        assert len({directory for directory, _marker in runs}) == 2
        first_status, _, first_report = request(server, f"/artifact/{job_ids[0]}/report")
        second_status, _, second_report = request(server, f"/artifact/{job_ids[1]}/report")
        assert first_status == second_status == 200
        assert first_report == b"run-1"
        assert second_report == b"run-2"
    finally:
        server.close()


def test_failure_detail_is_not_returned_over_http(monkeypatch, tmp_path):
    def fake_run(*_args, **_kwargs):
        raise RuntimeError("api_key=FAKE_SECRET cache_payload=private-data")

    monkeypatch.setattr(web.research, "run", fake_run)
    server = RunningServer(tmp_path)
    try:
        _, headers, _ = request(server, "/run", "POST", urlencode({"ticker": "BBCA"}).encode())
        job_id = headers["Location"].split("/")[-1]
        state = wait_for_job(server, job_id)
        response = json.dumps(state)
        assert state["state"] == "error"
        assert "FAKE_SECRET" not in response
        assert "private-data" not in response
        _, _, page = request(server, f"/jobs/{job_id}")
        assert b"FAKE_SECRET" not in page
        assert b"private-data" not in page
    finally:
        server.close()


def test_symlink_artifact_outside_output_directory_is_not_served(monkeypatch, tmp_path):
    outside = tmp_path / "outside.html"
    outside.write_text("outside secret", encoding="utf-8")

    def fake_run(ticker, outdir, want_pdf=False):
        (outdir / f"{ticker}.html").symlink_to(outside)
        (outdir / f"{ticker}-trace.html").write_text("trace", encoding="utf-8")
        return {"research_ok": True, "report_status": "complete"}

    monkeypatch.setattr(web.research, "run", fake_run)
    server = RunningServer(tmp_path / "out")
    try:
        _, headers, _ = request(server, "/run", "POST", urlencode({"ticker": "TEST"}).encode())
        job_id = headers["Location"].split("/")[-1]
        state = wait_for_job(server, job_id)
        # Symlinks are resolved and checked before any content is returned.
        assert state["state"] == "error"
        assert request(server, f"/artifact/{job_id}/report")[0] == 404
    finally:
        server.close()


def test_job_api_streams_progress_and_exposes_only_whitelisted_intel(monkeypatch, tmp_path):
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

    monkeypatch.setattr(web.research, "run", fake_run)
    server = RunningServer(tmp_path)
    try:
        _, headers, _ = request(server, "/run", "POST", urlencode({"ticker": "SIDO"}).encode())
        state = wait_for_job(server, headers["Location"].split("/")[-1])
        assert [e["label"] for e in state["events"]] == ["Rencana siap", "rank_peers selesai"]
        assert state["events"][1]["tool"] == "rank_peers"
        public = state["intel"]
        assert public["signals"][0]["rank"] == 1 and public["signals"][0]["peers"][0]["symbol"] == "KLBF"
        assert public["synthesis"]["findings"][0]["signal_ids"] == ["peer.roe"]
        dumped = json.dumps(state)
        for hidden in ("must-not-appear", "internal-path", "secret_payload", "0.146"):
            assert hidden not in dumped
    finally:
        server.close()


def test_research_page_lists_remembered_runs(monkeypatch, tmp_path):
    from agents.analyst import memory

    memory.save("SIDO", {"run_at": "2026-09-24T01:00:00+00:00", "market_date": "2026-09-22",
                         "signals": [{"id": "peer.roe", "label": "ROE", "flag": "tertinggi di grup"}],
                         "headlines": []})
    page = web._page().decode("utf-8")
    assert "Riwayat riset" in page and 'data-ticker="SIDO"' in page
    assert "1 sinyal bertanda" in page
