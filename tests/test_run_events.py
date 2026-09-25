"""Run events: gate and chain decisions as events, recorded runs, and replays."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import outputs, progress, run_events  # noqa: E402
from test_gallery import _report  # noqa: E402

VERDICT_BANK = {"primary": "DDM / Excess Return", "secondary": "Relative Valuation",
                "gates_passed": ["0_business_model", "5_upside_band"], "gates_failed": [],
                "gates_unassessed": []}


def test_gate_rows_read_every_gate_for_a_bank():
    rows = run_events.gate_rows(VERDICT_BANK)
    assert [r["gate"] for r in rows] == [0, 1, 2, 3, 4, 5]
    assert rows[0]["detail"] == "metode utama DDM / Excess Return, pembanding Relative Valuation"
    assert [r["verdict"] for r in rows[1:5]] == ["tidak berlaku"] * 4
    assert rows[5]["verdict"] == "lolos" and rows[5]["detail"] == "upside dalam rentang wajar"


def test_an_unassessed_check_is_not_reported_as_failed():
    verdict = {"primary": "FCFF/WACC DCF", "gates_passed": ["0_business_model", "1a_filing_history"],
               "gates_failed": ["1c_capital_structure", "5_upside_extreme"],
               "gates_unassessed": ["1c_capital_structure"]}
    rows = {r["gate"]: r for r in run_events.gate_rows(verdict)}
    assert rows[1]["verdict"] == "tidak dapat dinilai" and "struktur modal" in rows[1]["detail"]
    assert rows[5]["verdict"] == "gagal" and rows[5]["detail"] == "upside ekstrem"
    assert rows[1]["ok"] is False and rows[5]["ok"] is False


def _doc(published=True):
    return {"meta": {"ticker": "AAAA", "emiten": "PT AAAA Tbk", "status": (
                "distributable_assumption_led" if published else "draft_non_distributable"),
                     "rating": "Hold", "tp": 1100, "upside_persen": 10.0},
            "method": "FY26F PER [fallback: DCF]",
            "log_gate": {"release": {"gate_verdict": VERDICT_BANK}},
            "harness": {"blockers": [] if published else ["x", "y"]},
            "exhibits": [{"judul": "Rantai metode valuasi", "data": {"rows": [
                ["1. DDM (utama)", "Terpilih", "Rp1.100", "alasan"],
                ["2. PER FY skenario", "Silang cek", "Rp900", "silang"]]}}]}


def test_valuation_events_carry_gates_chain_and_release():
    events = run_events.valuation_events(_doc())
    gates = [e for e in events if str(e.get("tool", "")).startswith("gate_")]
    assert len(gates) == 6 and gates[1]["data"] == {"gate": 1, "verdict": "tidak berlaku"}
    chain = [e for e in events if e.get("tool") == "chain_step"]
    assert [(e["label"], e["data"]["decision"], e["data"]["value"]) for e in chain] == [
        ("DDM", "Terpilih", "Rp1.100"), ("PER FY skenario", "Silang cek", "Rp900")]
    release = events[-1]
    assert release["tool"] == "release" and release["data"]["tp"] == "Rp1.100"
    assert release["data"]["upside"] == "+10,0%"
    held = run_events.valuation_events(_doc(published=False))[-1]
    assert held["status"] == "warn" and "rating" not in held["data"]
    assert held["detail"] == "2 pemeriksaan menahan rating dan target harga"


def test_emit_is_bounded_and_drops_unknown_fields():
    seen = []
    with progress.capture(seen.append):
        progress.emit("gate", "x" * 300, "d" * 900, status="weird", tool="gate_1",
                      agent="Robert'); DROP", data={"gate": 1, "Bad Key": "v", "verdict": None})
    (event,) = seen
    assert event["stage"] == "gate" and len(event["label"]) == 160 and len(event["detail"]) == 400
    assert event["status"] == "ok" and "agent" not in event
    assert event["data"] == {"gate": "1"}


def test_recording_keeps_events_and_still_feeds_the_outer_listener():
    outer = []
    with progress.capture(outer.append):
        with progress.recording() as kept:
            progress.emit("plan", "Rencana siap", agent="analis")
        progress.emit("done", "Selesai")
    assert [e["label"] for e in kept] == ["Rencana siap"]
    assert [e["label"] for e in outer] == ["Rencana siap", "Selesai"]
    with progress.recording() as alone:          # no outer listener: still recorded
        progress.emit("done", "Selesai")
    assert len(alone) == 1


def _audit():
    return {"ticker": "AAAA",
            "analyst": {"ticker": "AAAA", "plan": {"question": "Q?", "source": "agent",
                                                   "hypotheses": ["H1: satu", "H2: dua"]},
                        "steps": [{"tool": "find_peers", "why": "peer", "summary": "5 emiten", "status": "ok"},
                                  {"tool": "foreign_flow", "why": "asing", "summary": "kosong",
                                   "status": "error"}],
                        "signals": [{"id": "s1", "flag": "lonjakan"}, {"id": "s2"}],
                        "synthesis": {"headline": "Head", "source": "agent",
                                      "hypotheses": [{"index": 0, "verdict": "didukung", "reason": "r"}]},
                        "changes": {"first_run": True}},
            "research": {"ok": True, "document": {"insights": [{"title": "T", "citations": []}],
                         "agent_trace": {"selected_cache_endpoints": ["/company/report/AAAA/"]}}},
            "news_sources": {"search": {"status": "searched", "queries": ["AAAA"], "as_of": "2026-09-24"},
                             "articles": [{"title": "A", "source": "https://x.id/a"}],
                             "rejected": [{"title": "R", "reason": "lain"}]},
            "forecast_assumptions": {"status": "validated", "reused": False, "subagents": {
                "news": {"status": "validated", "problems": []},
                "interim": {"status": "invalid", "problems": ["JSONDecodeError: bad"]},
                "secret_agent": {"status": "validated"}},
                "api_key": "FAKE"}}


def test_derived_replay_follows_the_pipeline_and_stays_public():
    events = run_events.derive(_audit(), _doc())
    labels = [e["label"] for e in events]
    assert labels[0] == "Membaca memori riset" and labels[-1] == "Selesai"
    assert labels.index("Rencana siap") < labels.index("Menjalankan find_peers") < labels.index(
        "Agent riset membaca data dan menyusun brief bersitasi") < labels.index(
        "Mencari berita bertanggal") < labels.index("Gerbang metode menilai emiten")
    assert "foreign_flow: data tidak tersedia" in labels
    assert "2 sinyal dihitung, 1 bertanda" in labels
    assert "1 artikel relevan, 1 ditolak" in labels
    verdict = next(e for e in events if e.get("tool") == "verdict")
    assert verdict["label"] == "H1 didukung" and verdict["data"]["index"] == "1"
    agents = {e.get("agent") for e in events}
    assert {"riset", "berita", "gerbang", "forecast.news", "forecast.interim"} <= agents
    assert "forecast.secret_agent" not in agents
    times = [e["t"] for e in events]
    assert times == sorted(times)
    assert "FAKE" not in json.dumps(events)


def test_replay_endpoint_prefers_recorded_events(tmp_path):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient
    from app import server

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    outputs.save(outputs.TRACE, reports, "AAAA", _audit())
    with TestClient(server.create_app(tmp_path / "out", reports)) as client:
        derived = client.get("/api/reports/AAAA/run").json()
        assert derived["source"] == "derived" and derived["report"]["rating"] == "Hold"
        assert derived["events"][-1]["label"] == "Selesai"
        outputs.save(outputs.EVENTS, reports, "AAAA", [
            {"stage": "plan", "label": "Rencana siap", "status": "ok", "t": 1.25, "detail": "Q",
             "agent": "analis", "secret": "must-not-appear"}])
        recorded = client.get("/api/reports/AAAA/run").json()
        assert recorded["source"] == "recorded"
        assert recorded["events"] == [{"stage": "plan", "label": "Rencana siap", "status": "ok", "t": 1.2,
                                       "detail": "Q", "agent": "analis"}]
        assert client.get("/api/reports/ZZZZ/run").status_code == 404
        assert client.get("/api/reports/..%2Fx/run").status_code == 404


def test_a_research_run_stores_its_events_with_its_outputs(monkeypatch, tmp_path):
    from app import research

    def fake(ticker, outdir, **_kwargs):
        progress.emit("plan", "Rencana siap")
        progress.emit("done", "Selesai")
        return {"ticker": ticker}

    monkeypatch.setattr(research, "_run", fake)
    research.run("AAAA", tmp_path)
    stored = outputs.load(outputs.EVENTS, tmp_path, "AAAA")
    assert [e["label"] for e in stored] == ["Rencana siap", "Selesai"]
    outputs.copy(tmp_path, "AAAA", tmp_path / "published")
    assert outputs.load(outputs.EVENTS, tmp_path / "published", "AAAA") == stored
