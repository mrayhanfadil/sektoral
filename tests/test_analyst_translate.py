"""English twins for a stored Planning Analyst Agent result (``translate_intel``).

Runs stored before the analyst wrote its own English (#39) have Indonesian
prose only. ``translate_intel`` asks for the English afterwards, in calls of
their own, checks each twin with the rules a twin from the run passes, repairs
once and leaves out what still fails; it never changes an Indonesian value.
``app.rebuild --translate-analyst`` stores the translated result in the
rebuilt trace, where the trace view and a Run Replay read it. No real LLM."""
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.analyst import run as analyst  # noqa: E402
from app import build as B, outputs, rebuild, run_events, trace_view  # noqa: E402
from test_forecast_english import _indonesian_doc, _without_english  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AS_OF = "2026-09-24"

QUESTION = "Bagaimana posisi BBRI terhadap bank besar lain?"
HYPOTHESES = ["ROE BBRI di atas median peer.", "Arus bersih asing 20 sesi terakhir negatif."]
WHY = ["Menentukan grup bank pembanding", "Membandingkan ROE dan P/B dengan peer",
       "Memeriksa arus investor asing"]
REASONS = ["ROE berada di atas median peer.", "Sebagian didukung: arus asing bervariasi."]


def _intel():
    """An analyst result as runs stored it before #39: Indonesian prose only."""
    return {
        "ticker": "BBRI", "name": "PT Bank Rakyat Indonesia (Persero) Tbk",
        "market_date": "2026-09-23", "run_at": "2026-09-24T01:00:00+00:00",
        "plan": {"question": QUESTION, "hypotheses": list(HYPOTHESES), "source": "agent",
                 "steps": [{"tool": "find_peers", "args": {}, "why": WHY[0]},
                           {"tool": "rank_peers", "args": {"metrics": ["roe", "pb"]}, "why": WHY[1]},
                           {"tool": "foreign_flow", "args": {}, "why": WHY[2]}]},
        "steps": [{"n": i + 1, "tool": tool, "args": {}, "why": why, "origin": "agent",
                   "status": "ok", "summary": "2 sinyal"}
                  for i, (tool, why) in enumerate(zip(("find_peers", "rank_peers", "foreign_flow"),
                                                      WHY))],
        "signals": [{"id": "peer.roe", "kind": "peer", "label": "ROE", "display": "19,1%"},
                    {"id": "flow.net_20d", "kind": "flow",
                     "label": "Arus bersih asing, 20 sesi terakhir", "display": "-Rp1,2 triliun"}],
        "synthesis": {
            "headline": "ROE memimpin grup, arus bersih asing, 20 sesi terakhir melemah",
            "findings": [{"title": "ROE di atas median", "signal_ids": ["peer.roe"],
                          "interpretation": "ROE bank ini lebih tinggi dari median peer.",
                          "caveat": "Data tahunan terakhir."}],
            "hypotheses": [{"index": 0, "verdict": "didukung", "signal_ids": ["peer.roe"],
                            "reason": REASONS[0], "verdict_code": "supported"},
                           {"index": 1, "verdict": "belum terjawab", "signal_ids": ["flow.net_20d"],
                            "reason": REASONS[1], "verdict_code": "partly_supported"}],
            "next_checks": ["Periksa kualitas aset kuartal berikutnya"], "source": "agent"},
        "status": "ok", "problems": []}


ENGLISH = {
    "plan.question": "How does BBRI compare with the other large banks?",
    "plan.hypotheses[0]": "BBRI's ROE is above the peer median.",
    "plan.hypotheses[1]": "Net foreign flow over the last 20 sessions is negative.",
    "plan.steps[0].why": "Set the group of comparison banks",
    "plan.steps[1].why": "Compare ROE and P/B with the peers",
    "plan.steps[2].why": "Check the flows of foreign investors",
    "synthesis.headline": "ROE leads the group while net foreign flow over the last 20 sessions "
                          "weakens",
    "synthesis.findings[0].title": "ROE above the median",
    "synthesis.findings[0].interpretation": "This bank's ROE is higher than the peer median.",
    "synthesis.findings[0].caveat": "The latest annual data.",
    "synthesis.hypotheses[0].reason": "ROE sits above the peer median.",
    "synthesis.hypotheses[1].reason": "Partly supported: foreign flows are mixed.",
    "synthesis.next_checks[0]": "Check asset quality in the next quarter",
}
# The executed steps quote the plan's reasons; each text is asked once.
ASKED = set(ENGLISH)


def _asked(messages):
    return json.loads(messages[1]["content"])


def _translator(english=ENGLISH, repair=None):
    """An ANALYST TRANSLATOR stand-in answering `english` by path (`repair` on a repair call)."""
    calls = []

    def chat(messages, **_kwargs):
        assert messages[0]["content"].startswith("Role: ANALYST TRANSLATOR")
        calls.append(messages)
        answers = repair if repair is not None and len(messages) > 2 else english
        return json.dumps({path: answers[path] for path in _asked(messages) if path in answers})
    return chat, calls


def _twins(intel):
    plan, synthesis = intel["plan"], intel["synthesis"]
    return {"question": plan.get("question_en"), "hypotheses": plan.get("hypotheses_en"),
            "plan_why": [s.get("why_en") for s in plan["steps"]],
            "why": [s.get("why_en") for s in intel["steps"]],
            "headline": synthesis.get("headline_en"),
            "finding": {k: synthesis["findings"][0].get(f"{k}_en")
                        for k in ("title", "interpretation", "caveat")},
            "reasons": [h.get("reason_en") for h in synthesis["hypotheses"]],
            "next_checks": synthesis.get("next_checks_en")}


# --- translate_intel --------------------------------------------------------


def test_translate_intel_attaches_checked_twins_and_changes_no_indonesian():
    intel = _intel()
    before = copy.deepcopy(intel)
    chat, calls = _translator()
    out, notes = analyst.translate_intel(intel, chat=chat)
    assert intel == before                                   # the input is not touched
    assert _without_english(out) == before                   # nor any Indonesian value
    assert notes["status"] == "translated", notes
    assert notes["dropped"] == notes["problems"] == [] and notes["calls"] == 1
    assert notes["fields"] == notes["attached"] == len(ENGLISH) + len(WHY)
    assert set(_asked(calls[0])) == ASKED                    # the same reason is asked once
    twins = _twins(out)
    assert twins["question"] == ENGLISH["plan.question"]
    assert twins["hypotheses"] == [ENGLISH["plan.hypotheses[0]"], ENGLISH["plan.hypotheses[1]"]]
    assert twins["plan_why"] == twins["why"] == [ENGLISH[f"plan.steps[{i}].why"] for i in range(3)]
    assert twins["headline"] == ENGLISH["synthesis.headline"]
    assert twins["finding"]["caveat"] == "The latest annual data."
    assert twins["reasons"][1] == "Partly supported: foreign flows are mixed."
    assert twins["next_checks"] == ["Check asset quality in the next quarter"]
    # The signal names go to the translator in English, as new runs name them.
    assert "Net foreign flow, last 20 sessions" in calls[0][0]["content"]


def test_signal_ids_in_a_twin_read_as_english_labels():
    english = dict(ENGLISH, **{"synthesis.headline": "ROE leads the group while flow.net_20d "
                                                     "weakens"})
    chat, _ = _translator(english)
    out, notes = analyst.translate_intel(_intel(), chat=chat)
    assert notes["status"] == "translated"
    assert out["synthesis"]["headline_en"] == ("ROE leads the group while net foreign flow, last "
                                               "20 sessions weakens")


def test_a_bad_twin_gets_one_repair_and_is_dropped_if_still_wrong():
    bad = dict(ENGLISH, **{
        "synthesis.findings[0].interpretation": "ROE is 19.1% versus a median of 15%.",   # figures
        "synthesis.hypotheses[0].reason": "Investors should buy the shares.",             # advice
        "plan.question": "Bagaimana posisi BBRI terhadap bank besar lain?",               # Indonesian
        "plan.hypotheses[1]": "Net foreign flow over the last 30 sessions is negative.",  # figure
    })
    repair = {"synthesis.findings[0].interpretation": "This bank's ROE is higher than the median.",
              "synthesis.hypotheses[0].reason": "Still advice: investors should buy.",
              "plan.question": "How does BBRI compare with the other large banks?",
              "plan.hypotheses[1]": "Foreign flow is negative over the last 31 sessions."}
    intel = _intel()
    before = copy.deepcopy(intel)
    chat, calls = _translator(bad, repair)
    out, notes = analyst.translate_intel(intel, chat=chat)
    assert len(calls) == 2                                   # one call, one repair call
    assert set(_asked(calls[1])) == set(repair)
    assert _without_english(out) == before
    assert out["plan"]["question_en"] == repair["plan.question"]
    assert out["synthesis"]["findings"][0]["interpretation_en"] == repair[
        "synthesis.findings[0].interpretation"]
    assert "reason_en" not in out["synthesis"]["hypotheses"][0]       # still advice: dropped
    assert out["synthesis"]["hypotheses"][1]["reason_en"] == ENGLISH["synthesis.hypotheses[1].reason"]
    assert "hypotheses_en" not in out["plan"]               # a list is whole or not at all
    assert notes["status"] == "partial"
    assert any(d.startswith("synthesis.hypotheses[0].reason: prosa memuat bahasa rekomendasi")
               for d in notes["dropped"])
    assert any(d.startswith("plan.hypotheses[1]: angka harus sama") for d in notes["dropped"])
    assert any(d.startswith("plan.hypotheses: every item needs its English")
               for d in notes["dropped"])


@pytest.mark.parametrize("reply", [
    RuntimeError("provider down"),
    "Maaf, saya tidak bisa.",
    "[\"not\", \"an object\"]",
])
def test_a_failed_translation_leaves_the_result_unchanged(reply):
    intel = _intel()
    before = copy.deepcopy(intel)
    calls = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        if isinstance(reply, Exception):
            raise reply
        return reply
    out, notes = analyst.translate_intel(intel, chat=chat)
    assert out is intel and out == before and "_en\"" not in json.dumps(out)
    assert notes["status"] == "failed" and notes["attached"] == 0 and notes["problems"]
    assert len(calls) == 1                                   # a failed call is not repeated


def test_a_cut_off_translation_is_asked_again_in_halves():
    cut = {"content": "{\"plan.question\": \"How does BB", "finish_reason": "length"}
    calls = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        asked = _asked(messages)
        if len(asked) > len(ASKED) // 2 + 1:                 # the whole result does not fit
            return cut
        return json.dumps({path: ENGLISH[path] for path in asked})
    out, notes = analyst.translate_intel(_intel(), chat=chat)
    assert notes["status"] == "translated" and not notes["problems"]
    assert len(calls) == 3
    assert out["plan"]["question_en"] == ENGLISH["plan.question"]


def test_a_reply_always_cut_off_leaves_the_result_unchanged():
    intel = _intel()
    calls = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        return {"content": "{\"x\": \"cut", "finish_reason": "length"}
    out, notes = analyst.translate_intel(intel, chat=chat)
    assert out is intel and notes["status"] == "failed"
    assert len(calls) == 2 * len(ASKED) - 1                  # halved down to single fields
    assert len(notes["problems"]) == len(ASKED)
    assert all("finish_reason=length" in p for p in notes["problems"])


def test_twins_and_host_text_are_left_as_they_are():
    intel = _intel()
    intel["plan"]["question_en"] = "The run's own English question?"
    intel["steps"].append({"n": 4, "tool": "news", "why": "langkah standar host",
                           "origin": "host", "status": "ok"})
    chat, calls = _translator()
    out, notes = analyst.translate_intel(intel, chat=chat)
    asked = _asked(calls[0])
    assert "plan.question" not in asked and "steps[3].why" not in asked
    assert out["plan"]["question_en"] == "The run's own English question?"
    assert "why_en" not in out["steps"][3]                   # app.host_lang gives its English
    assert notes["status"] == "translated"


def test_a_result_with_every_twin_needs_no_call():
    chat, _ = _translator()
    out, _ = analyst.translate_intel(_intel(), chat=chat)
    calls = []
    again, notes = analyst.translate_intel(out, chat=lambda *a, **k: calls.append(a))
    assert again is out and calls == [] and notes["status"] == "nothing_to_translate"
    assert analyst.translate_intel(None, chat=chat)[1]["status"] == "nothing_to_translate"


# --- app.rebuild --translate-analyst ----------------------------------------


OLD_EVENTS = [
    {"stage": "plan", "label": "Rencana siap", "detail": QUESTION, "t": 1.0},
    {"stage": "plan", "label": "Hipotesis 1", "detail": HYPOTHESES[0], "tool": "hypothesis",
     "data": {"index": "1", "kind": "hypothesis"}, "t": 1.1},
    {"stage": "plan", "label": "Hipotesis 2", "detail": HYPOTHESES[1], "tool": "hypothesis",
     "data": {"index": "2", "kind": "hypothesis"}, "t": 1.2},
    *[{"stage": "tool", "label": f"Menjalankan {tool}", "detail": why, "status": "run",
       "tool": tool, "t": 2.0 + i}
      for i, (tool, why) in enumerate(zip(("find_peers", "rank_peers", "foreign_flow"), WHY))],
    {"stage": "synthesis", "label": "H1 didukung", "detail": REASONS[0], "tool": "verdict",
     "t": 9.0},
]


def _source(tmp_path):
    stored = json.loads((FIXTURES / "bbri_scenario_plan.json").read_text())
    source = tmp_path / "src"
    B.build("BBRI", source, as_of=AS_OF, assumption_plan=copy.deepcopy(stored["plan"]),
            assumption_status=stored["status"])
    outputs.save(outputs.TRACE, source, "BBRI", {
        "ticker": "BBRI", "report": {"as_of": AS_OF}, "analyst": _intel(),
        "forecast_assumptions": {"status": stored["status"], "plan": stored["plan"]}})
    outputs.save(outputs.EVENTS, source, "BBRI", copy.deepcopy(OLD_EVENTS))
    return source


def test_rebuild_translate_analyst_keeps_the_report_and_gives_the_trace_english(
        tmp_path, monkeypatch, capsys):
    source = _source(tmp_path)
    chat, calls = _translator()
    monkeypatch.setattr(analyst, "_chat", chat)

    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "plain"), "BBRI"]) == 0
    assert calls == []                                       # a plain rebuild calls no model
    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "en"),
                         "--translate-analyst", "BBRI"]) == 0
    assert len(calls) == 1
    assert "terjemahan analis: translated 16/16 teks" in capsys.readouterr().out

    plain = outputs.load(outputs.REPORT, tmp_path / "plain", "BBRI")
    translated = outputs.load(outputs.REPORT, tmp_path / "en", "BBRI")
    # The report builder does not read the analyst result: the same document.
    assert _indonesian_doc(translated) == _indonesian_doc(plain)
    without = {k: v for k, v in translated.items() if k != "run_manifest"}
    assert without == {k: v for k, v in plain.items() if k != "run_manifest"}
    assert translated["meta"]["rating"] == plain["meta"]["rating"]
    assert translated["meta"]["tp"] == plain["meta"]["tp"]
    manifest = outputs.load(outputs.MANIFEST, tmp_path / "en", "BBRI")
    assert manifest["rebuild"]["translated_analyst"] is True
    assert outputs.load(outputs.MANIFEST, tmp_path / "plain", "BBRI")["rebuild"][
        "translated_analyst"] is False

    # The trace stores the translated result and its notes; its Indonesian is the stored one.
    trace = outputs.load(outputs.TRACE, tmp_path / "en", "BBRI")
    plain_trace = outputs.load(outputs.TRACE, tmp_path / "plain", "BBRI")
    stored = trace["analyst"]
    assert stored.pop("translation")["status"] == "translated"
    assert _without_english(stored) == _intel() == plain_trace["analyst"]
    assert _twins(stored)["question"] == ENGLISH["plan.question"]

    # The trace view serves the twins.
    view = trace_view.build(trace)["analyst"]
    assert view["plan"]["question_en"] == ENGLISH["plan.question"]
    assert view["plan"]["hypotheses_en"] == [ENGLISH["plan.hypotheses[0]"],
                                             ENGLISH["plan.hypotheses[1]"]]
    assert [s["why_en"] for s in view["steps"]] == [ENGLISH[f"plan.steps[{i}].why"]
                                                    for i in range(3)]
    synthesis = view["synthesis"]
    assert synthesis["headline_en"] == ENGLISH["synthesis.headline"]
    assert synthesis["findings"][0]["interpretation_en"] == ENGLISH[
        "synthesis.findings[0].interpretation"]
    assert [h["reason_en"] for h in synthesis["hypotheses"]] == [
        ENGLISH["synthesis.hypotheses[0].reason"], ENGLISH["synthesis.hypotheses[1].reason"]]
    assert synthesis["next_checks_en"] == [ENGLISH["synthesis.next_checks[0]"]]
    assert trace_view.build(plain_trace)["analyst"]["plan"]["question_en"] is None

    # A replay of the stored events reads the twins: question, hypotheses, step reasons.
    english = {e["label"]: e.get("detail_en")
               for e in run_events.replay(tmp_path / "en", "BBRI")["events"]}
    assert english["Rencana siap"] == ENGLISH["plan.question"]
    assert english["Hipotesis 1"] == ENGLISH["plan.hypotheses[0]"]
    assert english["Hipotesis 2"] == ENGLISH["plan.hypotheses[1]"]
    assert [english[f"Menjalankan {t}"] for t in ("find_peers", "rank_peers", "foreign_flow")] == [
        ENGLISH[f"plan.steps[{i}].why"] for i in range(3)]
    assert english["H1 didukung"] == ENGLISH["synthesis.hypotheses[0].reason"]
    plain_replay = run_events.replay(tmp_path / "plain", "BBRI")["events"]
    assert not any(e.get("detail_en") for e in plain_replay if e["label"] == "Rencana siap")


def test_rebuild_combines_both_translations(tmp_path, monkeypatch, capsys):
    from agents.forecast_assumptions import run as forecast
    source = _source(tmp_path)
    analyst_chat, analyst_calls = _translator()
    monkeypatch.setattr(analyst, "_chat", analyst_chat)
    forecast_calls = []

    def forecast_chat(messages, **_kwargs):
        forecast_calls.append(messages)
        raise RuntimeError("LLM is disabled in tests")
    monkeypatch.setattr(forecast, "_chat", forecast_chat)
    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "en"),
                         "--translate-assumptions", "--translate-analyst", "BBRI"]) == 0
    out = capsys.readouterr().out
    assert "terjemahan: failed" in out and "terjemahan analis: translated" in out
    assert analyst_calls and forecast_calls
    manifest = outputs.load(outputs.MANIFEST, tmp_path / "en", "BBRI")["rebuild"]
    assert manifest["translated_analyst"] is True and manifest["translated_assumptions"] is True


def test_translate_analyst_needs_named_tickers(tmp_path):
    with pytest.raises(SystemExit):
        rebuild.main(["--from", str(tmp_path / "src"), "--out", str(tmp_path / "out"),
                      "--translate-analyst"])
