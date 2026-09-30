"""Run events: gate and chain decisions as events, recorded runs, and replays."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import outputs, progress, run_events  # noqa: E402
from test_gallery import _report, approve  # noqa: E402

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
    assert len(gates) == 6 and gates[1]["data"] == {"kind": "gate", "gate": 1, "verdict": "tidak berlaku",
                                                     "verdict_code": "not_applicable"}
    assert [g["data"]["verdict_code"] for g in gates] == ["pass"] + ["not_applicable"] * 4 + ["pass"]
    chain = [e for e in events if e.get("tool") == "chain_step"]
    assert [(e["label"], e["data"]["decision"], e["data"]["value"]) for e in chain] == [
        ("DDM", "Terpilih", "Rp1.100"), ("PER FY skenario", "Silang cek", "Rp900")]
    assert [e["data"]["kind"] for e in chain] == ["chain_row"] * 2
    assert [e["data"]["decision_code"] for e in chain] == ["selected", "cross_check"]
    primary = events[-2]
    assert primary["label"] == "Metode utama FY26F PER"
    # data.method is the short name of the chain row the target uses.
    assert primary["data"] == {"kind": "primary_method", "method": "DDM"}
    unchained = run_events.valuation_events({**_doc(), "exhibits": []})[-2]
    assert unchained["data"] == {"kind": "primary_method", "method": "FY26F PER"}
    release = events[-1]
    assert release["tool"] == "release" and release["data"]["tp"] == "Rp1.100"
    assert release["data"]["upside"] == "+10,0%"
    assert release["data"]["kind"] == "release"
    assert release["data"]["tp_value"] == 1100 and release["data"]["upside_pct"] == 10.0
    held = run_events.valuation_events(_doc(published=False))[-1]
    assert held["status"] == "warn" and "rating" not in held["data"]
    assert held["data"] == {"kind": "release", "status": "draft_non_distributable"}
    assert held["detail"] == "2 pemeriksaan menahan rating dan target harga"
    no_method = run_events.valuation_events({**_doc(), "method": ""})[-2]
    assert no_method["label"] == "Rantai metode selesai" and no_method["data"] == {"kind": "chain_done"}


def test_emitted_codes_stay_within_the_event_bounds():
    seen = []
    doc = _doc()
    doc["meta"].update(tp=4125.0, upside_persen=-20.94)
    with progress.capture(seen.append):
        run_events.emit_valuation(doc)
    release = seen[-1]["data"]
    # Raw numbers stay numbers; every other value is a short string.
    assert release == {"kind": "release", "status": "distributable_assumption_led", "rating": "Hold",
                       "tp": "Rp4.125", "upside": "−20,9%", "tp_value": 4125.0, "upside_pct": -20.9}
    assert seen[0].get("data") is None and seen[1]["data"]["gate"] == "0"
    assert all(len(e.get("data") or {}) <= 8 for e in seen)
    assert all(isinstance(v, str) and len(v) <= 120 for e in seen for k, v in (e.get("data") or {}).items()
               if k not in progress.NUMBERS)
    bad = progress.event("report", "x", data={"tp_value": float("nan"), "upside_pct": True, "kind": "release"})
    assert bad["data"] == {"kind": "release"}


def test_hypothesis_codes_read_partial_support_from_the_reason():
    assert run_events.hypothesis_code("didukung") == "supported"
    assert run_events.hypothesis_code("tidak didukung", "x") == "not_supported"
    assert run_events.hypothesis_code("belum terjawab", "data kurang") == "unanswered"
    assert run_events.hypothesis_code("belum terjawab", "Sebagian didukung: laba naik") == "partly_supported"
    assert run_events.hypothesis_code("lain") is None


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
    assert verdict["data"]["kind"] == "hypothesis" and verdict["data"]["verdict_code"] == "supported"
    kinds = {e["label"]: (e.get("data") or {}).get("kind") for e in events}
    assert kinds["Hipotesis 1"] == "hypothesis"
    assert kinds["Menjalankan find_peers"] == "tool_start" and kinds["find_peers selesai"] == "tool_done"
    assert kinds["foreign_flow: data tidak tersedia"] == "tool_empty"
    assert kinds["Metode utama FY26F PER"] == "primary_method"
    assert kinds["Status rilis: dapat didistribusikan, berbasis asumsi analis"] == "release"
    agents = {e.get("agent") for e in events}
    assert {"riset", "berita", "gerbang", "forecast.news", "forecast.interim"} <= agents
    assert "forecast.secret_agent" not in agents
    times = [e["t"] for e in events]
    assert times == sorted(times)
    assert "FAKE" not in json.dumps(events)


def test_derived_verdicts_read_partial_support_from_the_reason():
    audit = _audit()
    audit["analyst"]["synthesis"]["hypotheses"] = [
        {"index": 0, "verdict": "belum terjawab", "reason": "Sebagian didukung: laba naik"},
        {"index": 1, "verdict": "tidak didukung", "reason": "r"},
        {"index": 2, "verdict": "belum terjawab", "reason": "data kurang"}]
    verdicts = [e for e in run_events.derive(audit, _doc()) if e.get("tool") == "verdict"]
    assert [e["data"]["verdict_code"] for e in verdicts] == ["partly_supported", "not_supported",
                                                            "unanswered"]


# Events as research.run recorded them before codes existed.
OLD_EVENTS = [
    {"stage": "plan", "label": "Hipotesis 1", "tool": "hypothesis", "data": {"index": "1"}, "t": 0.1},
    {"stage": "tool", "label": "Menjalankan find_peers", "tool": "find_peers", "status": "run", "t": 1},
    {"stage": "tool", "label": "find_peers selesai", "tool": "find_peers", "t": 2},
    {"stage": "tool", "label": "foreign_flow: data tidak tersedia", "tool": "foreign_flow",
     "status": "warn", "t": 3},
    {"stage": "tool", "label": "Agent menilai bukti sudah cukup", "t": 3.5},
    {"stage": "synthesis", "label": "H1 belum terjawab", "tool": "verdict", "t": 4,
     "detail": "Sebagian didukung: laba naik", "data": {"index": "1", "verdict": "belum terjawab"}},
    {"stage": "gate", "label": "Kelayakan data", "tool": "gate_1", "agent": "gerbang", "t": 5,
     "data": {"gate": "1", "verdict": "tidak dapat dinilai"}},
    {"stage": "gate", "label": "DDM", "tool": "chain_step", "agent": "gerbang", "t": 6,
     "data": {"decision": "Terpilih, ekstrem (rantai berhenti)", "value": "ditahan"}},
    {"stage": "gate", "label": "PSR", "tool": "chain_step", "agent": "gerbang", "t": 6.1,
     "data": {"decision": "Belum tersedia", "value": "-"}},
    {"stage": "gate", "label": "Metode utama DDM", "agent": "gerbang", "t": 7},
    {"stage": "report", "label": "Status rilis: siap produksi", "tool": "release", "t": 8,
     "data": {"status": "production_ready", "rating": "Sell", "tp": "Rp12.350", "upside": "−20,9%"}},
    {"stage": "done", "label": "Selesai", "t": 9}]


def test_old_recorded_events_get_their_codes_on_replay():
    events = progress.public([run_events.coded(e) for e in progress.public(OLD_EVENTS)])
    data = {e["label"]: e.get("data") for e in events}
    assert data["Hipotesis 1"] == {"index": "1", "kind": "hypothesis"}
    assert data["Menjalankan find_peers"] == {"kind": "tool_start"}
    assert data["find_peers selesai"] == {"kind": "tool_done"}
    assert data["foreign_flow: data tidak tersedia"] == {"kind": "tool_empty"}
    assert data["Agent menilai bukti sudah cukup"] is None
    assert data["H1 belum terjawab"]["verdict_code"] == "partly_supported"
    assert data["Kelayakan data"] == {"gate": "1", "verdict": "tidak dapat dinilai", "kind": "gate",
                                      "verdict_code": "not_assessable"}
    assert data["DDM"]["decision_code"] == "stop_extreme" and data["PSR"]["decision_code"] == "unavailable"
    assert data["Metode utama DDM"] == {"kind": "primary_method", "method": "DDM"}
    primary = {"stage": "gate", "label": "Metode utama FY26F PER", "agent": "gerbang", "t": 7}
    assert run_events.coded(primary, _doc())["data"] == {"kind": "primary_method", "method": "DDM"}
    assert data["Status rilis: siap produksi"] == {
        "status": "production_ready", "rating": "Sell", "tp": "Rp12.350", "upside": "−20,9%",
        "kind": "release", "tp_value": 12350, "upside_pct": -20.9}
    assert data["Selesai"] is None
    # Codes a run recorded itself are kept as they are.
    live = {"stage": "gate", "label": "X", "tool": "chain_step", "t": 1,
            "data": {"kind": "chain_row", "decision": "Terpilih", "decision_code": "selected"}}
    assert run_events.coded(live) is live


def test_replay_endpoint_prefers_recorded_events(tmp_path):
    fastapi = pytest.importorskip("fastapi")  # noqa: F841
    from fastapi.testclient import TestClient
    from app import server

    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    outputs.save(outputs.TRACE, reports, "AAAA", _audit())
    approve(reports, "AAAA")
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
                                       "label_en": "Plan ready", "detail": "Q", "agent": "analis"}]
        outputs.save(outputs.EVENTS, reports, "AAAA", OLD_EVENTS)
        old = client.get("/api/reports/AAAA/run").json()["events"]
        release = next(e for e in old if e.get("tool") == "release")
        assert release["data"]["tp_value"] == 12350 and release["data"]["upside_pct"] == -20.9
        assert client.get("/api/reports/ZZZZ/run").status_code == 404
        assert client.get("/api/reports/..%2Fx/run").status_code == 404


def test_events_carry_english_beside_their_indonesian():
    seen = []
    with progress.capture(seen.append):
        progress.emit("signals", "38 sinyal dihitung, 3 bertanda")
        progress.emit("plan", "Rencana siap", "Apa yang berubah?", detail_en="What changed?")
        progress.emit("plan", "Hipotesis 1", "Laba naik karena harga.")  # agent prose, no twin
    assert [e["label"] for e in seen] == ["38 sinyal dihitung, 3 bertanda", "Rencana siap", "Hipotesis 1"]
    assert [e["label_en"] for e in seen] == ["38 signals computed, 3 flagged", "Plan ready", "Hypothesis 1"]
    assert seen[1]["detail"] == "Apa yang berubah?" and seen[1]["detail_en"] == "What changed?"
    assert seen[2]["detail"] == "Laba naik karena harga." and "detail_en" not in seen[2]
    bounded = progress.event("plan", "x", "d", label_en="E" * 300, detail_en="F" * 900)
    assert len(bounded["label_en"]) == 160 and len(bounded["detail_en"]) == 400
    # Stored English passes through a replay's re-validation as it is.
    assert progress.public([{**seen[1], "label_en": "Ready"}])[0]["label_en"] == "Ready"


def test_valuation_events_carry_english():
    seen = []
    with progress.capture(seen.append):
        run_events.emit_valuation(_doc())
        run_events.emit_valuation(_doc(published=False))
    held = seen.pop()
    english = {e["label"]: (e.get("label_en"), e.get("detail_en")) for e in seen}
    assert english["Gerbang metode menilai emiten"] == (
        "Method Gates assess the issuer",
        "Method Gates 0-5 choose the method before any value is computed")
    assert english["Model bisnis"] == (
        "Business model", "primary method DDM / Excess Return, comparison Relative Valuation")
    assert english["Kelayakan data"] == (
        "Data eligibility", "a financial institution is valued on equity; this gate is skipped")
    assert english["PER FY skenario"][0] == "Scenario FY PER"
    assert english["Status rilis: dapat didistribusikan, berbasis asumsi analis"] == (
        "Release status: distributable, Assumption-Led", "rating and Target Price published")
    assert held["detail_en"] == "2 checks hold back the rating and Target Price"


def test_derived_replay_has_english_for_host_text_and_agent_twins():
    audit = _audit()
    analyst = audit["analyst"]
    analyst["plan"].update(question_en="Q in English?", hypotheses_en=["H1: one", "H2: two"])
    analyst["steps"][0]["why_en"] = "peers"
    analyst["synthesis"]["headline_en"] = "Headline"
    analyst["synthesis"]["hypotheses"][0]["reason_en"] = "the reason"
    events = run_events.derive(audit, _doc())
    before = [e["label"] for e in run_events.derive(_audit(), _doc())]
    assert [e["label"] for e in events] == before  # the Indonesian is unchanged
    by_label = {e["label"]: e for e in events}
    assert by_label["Membaca memori riset"]["label_en"] == "Reading the research memory"
    assert by_label["Membaca memori riset"]["detail_en"] == "no earlier research"
    assert by_label["Rencana siap"]["detail_en"] == "Q in English?"
    assert by_label["Hipotesis 2"]["label_en"] == "Hypothesis 2"
    assert by_label["Hipotesis 2"]["detail_en"] == "H2: two"
    assert by_label["Menjalankan find_peers"]["detail_en"] == "peers"
    assert by_label["foreign_flow: data tidak tersedia"]["label_en"] == "foreign_flow: data not available"
    assert by_label["2 sinyal dihitung, 1 bertanda"]["label_en"] == "2 signals computed, 1 flagged"
    assert by_label["Temuan tervalidasi"]["detail_en"] == "Headline"
    assert by_label["H1 didukung"]["label_en"] == "H1 supported"
    assert by_label["H1 didukung"]["detail_en"] == "the reason"
    assert by_label["1 artikel relevan, 1 ditolak"]["label_en"] == "1 relevant article, 1 rejected"
    assert by_label["Subagent Dampak berita"]["label_en"] == "Subagent News impact"
    assert by_label["Skenario interim ditolak validator"]["label_en"] == (
        "Interim scenario rejected by the validator")
    assert by_label["Selesai"]["label_en"] == "Done"


def test_old_recorded_events_get_english_on_replay(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA")
    doc = outputs.load(outputs.REPORT, reports, "AAAA")
    doc["exhibits"][0]["data"]["rows"][1][3] = ("EPS FY adalah skenario analis dari aktual 1H + "
                                                "asumsi H2, bukan forecast driver terekonsiliasi; "
                                                "peer dianggap sebanding")
    outputs.save(outputs.REPORT, reports, "AAAA", doc)
    audit = _audit()
    audit["analyst"]["plan"]["hypotheses_en"] = ["H1: one", "H2: two"]
    outputs.save(outputs.TRACE, reports, "AAAA", audit)
    approve(reports, "AAAA")
    outputs.save(outputs.EVENTS, reports, "AAAA", OLD_EVENTS + [
        {"stage": "plan", "label": "Hipotesis 2", "tool": "hypothesis", "detail": "H2: dua", "t": 0.2},
        {"stage": "gate", "label": "PER FY skenario", "tool": "chain_step", "agent": "gerbang",
         "detail": "EPS FY adalah skenario analis dari aktual 1H + asumsi H2, bukan forecast driver "
                   "terek", "t": 6.2}])
    replay = run_events.replay(reports, "AAAA")
    assert replay["source"] == "recorded"
    by_label = {e["label"]: e for e in replay["events"]}
    assert [e["label"] for e in replay["events"]] == [e["label"] for e in OLD_EVENTS] + [
        "Hipotesis 2", "PER FY skenario"]
    assert by_label["Menjalankan find_peers"]["label_en"] == "Running find_peers"
    assert by_label["Kelayakan data"]["label_en"] == "Data eligibility"
    assert by_label["Status rilis: siap produksi"]["label_en"] == "Release status: Production-Ready"
    assert by_label["Hipotesis 2"]["detail"] == "H2: dua"
    assert by_label["Hipotesis 2"]["detail_en"] == "H2: two"  # the analyst's own twin
    # A chain row's recorded detail is cut; its English comes from the whole reason.
    assert by_label["PER FY skenario"]["detail_en"] == (
        "FY EPS is an Analyst Scenario from 1H actuals + H2 assumptions, not a reconciled driver "
        "forecast; peers taken as comparable")
    # Agent prose without a twin stays Indonesian only.
    assert "detail_en" not in by_label["H1 belum terjawab"]


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
