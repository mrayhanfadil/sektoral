"""English twins (``<field>_en``) of the Forecast Assumption Agent's prose.

The subagents write Indonesian only, with exactly the prompts they had before
the bilingual work (#39). ``translate_plan`` asks for the English afterwards,
in calls of its own, checks each twin like its Indonesian field, repairs once
and leaves out what still fails; it never changes an Indonesian value and
never fails the run. ``run_live``, ``run_cached`` and ``app.rebuild
--translate-assumptions`` call it. The English report quotes the twins. No
real LLM."""
import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.forecast_assumptions import run as agent  # noqa: E402
from app import build as B, outputs, prose_lang, rebuild, scrub, stage, store  # noqa: E402
from test_forecast_bank_agent import (NEWS, STAGE, _earnings, _intake, _outyears,  # noqa: E402
                                      _scripted)
from test_forecast_earnings_agent import _source as fcff_source  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AS_OF = "2026-09-24"


def _without_english(value):
    if isinstance(value, dict):
        return {k: _without_english(v) for k, v in value.items() if not k.endswith("_en")}
    if isinstance(value, list):
        return [_without_english(v) for v in value]
    return value


def _twins(plan):
    """{path: English twin} of a plan that carries twins, by translate_plan's paths."""
    found = {}
    for field in agent._prose_fields(copy.deepcopy(plan)):
        twin = field.host.get(f"{field.key}_en")
        if field.index is not None:
            twin = twin[field.index] if isinstance(twin, list) else None
        if twin is not None:
            found[field.path] = twin
    return found


# The bank run's replies as the subagents now write them (Indonesian only), and
# the English a translator answers for the plan they make.
BANK_PLAN_EN = {"news_effects": NEWS["news_effects"],
                "earnings_scenario": _earnings()["earnings_scenario"],
                "bank_outyear_scenario": _outyears()["bank_outyear_scenario"],
                "stage_classification": STAGE["stage_classification"]}
BANK_ENGLISH = _twins(BANK_PLAN_EN)


def _replies():
    return {"NEWS DRIVER ANALYST": [_without_english(NEWS)],
            "BANK DRIVER SCENARIO ANALYST": [_without_english(_earnings())],
            "STAGE CLASSIFIER": [_without_english(STAGE)],
            "BANK DRIVER OUTYEAR ANALYST": [_without_english(_outyears())]}


def _asked(messages):
    return json.loads(messages[1]["content"])


def _translator(english, repair=None):
    """A PLAN TRANSLATOR stand-in answering `english` by path (`repair` on a repair call)."""
    calls = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        answers = repair if repair is not None and len(messages) > 2 else english
        return json.dumps({path: answers[path] for path in _asked(messages) if path in answers})
    return chat, calls


def _run(monkeypatch, translator=None):
    """run_live on the bank intake; the subagents answer by role, the translator by path."""
    scripted, calls = _scripted(_replies())
    order = []

    def chat(messages, **kwargs):
        if "Role: PLAN TRANSLATOR" in messages[0]["content"]:
            order.append("translate")
            if translator is None:
                raise RuntimeError("LLM is disabled in tests")
            return translator(messages, **kwargs)
        order.append("subagent")
        return scripted(messages, **kwargs)
    monkeypatch.setattr(agent, "_chat", chat)
    return agent.run_live(_intake()), calls, order


# --- The Indonesian subagents are as they were before #39 -------------------


def _subagent_messages(module):
    """Every message each subagent role sends while the model answers "{}", so
    every repair message is sent too. The spec excerpt is a placeholder."""
    out = {}

    def run(case, name, source, **kw):
        calls = []

        def chat(messages, **_kwargs):
            calls.append(copy.deepcopy(messages))
            return "{}"
        original = module._chat
        module._chat = chat
        try:
            module._run_subagent(name, source, "SPEC", **kw)
        finally:
            module._chat = original
        out[case] = calls

    bank = module._source_payload(_intake())
    for name in ("news", "earnings", "stage"):
        run(f"bank.{name}", name, bank)
    run("bank.outyears", "outyears", bank, news_effects=[], interim_anchor=module._bank_anchor(
        bank, copy.deepcopy(_earnings()["earnings_scenario"])))
    fcff = fcff_source()
    for name in ("news", "earnings", "stage"):
        run(f"fcff.{name}", name, fcff)
    run("fcff.outyears", "outyears", fcff, interim_anchor={"year": 2026, "revenue": 200.0},
        news_effects=[])
    mining = fcff_source(profile="finite_life_mining", official=dict(
        fcff["official"], metrics={"revenue": 100.0, "ebitda": 40.0, "net_profit": 10.0,
                                   "capital_expenditure": 20.0}))
    run("mining.interim", "interim", mining)
    run("mining.outyears", "outyears", mining, interim_anchor={"year": 2026, "revenue": 200.0},
        news_effects=[])
    return out


def test_subagents_send_the_prompts_they_had_before_the_bilingual_change():
    """The digests were taken from the module of commit d0b7f64 (main before
    #39) on these same inputs. A deliberate prompt change updates them."""
    expected = json.loads((FIXTURES / "forecast_prompts_pre39.json").read_text())
    sent = _subagent_messages(agent)
    assert set(sent) == set(expected)
    for case, messages in sent.items():
        digest = hashlib.sha256(json.dumps(messages, ensure_ascii=False, sort_keys=True)
                                .encode()).hexdigest()
        assert digest == expected[case], case


def test_subagents_are_asked_for_no_english():
    for case, calls in _subagent_messages(agent).items():
        for messages in calls:
            for message in messages:
                if message["role"] == "assistant":
                    continue
                text = message["content"]
                assert "English" not in text and "Inggris" not in text, case
                assert not re.search(r"\b[a-z]+(?:_[a-z]+)*_en\b", text), case


# --- translate_plan --------------------------------------------------------


def _earnings_plan():
    """An Indonesian earnings plan whose first catalyst's timing is a code."""
    scenario = _without_english(_earnings()["earnings_scenario"])
    scenario["catalysts_risks"][0]["timing"] = "3Q26"
    return {"earnings_scenario": scenario}


def _earnings_english():
    english = _twins(_earnings())
    english["earnings_scenario.catalysts_risks[0].timing"] = "3Q26"
    return english


def test_translate_plan_attaches_checked_twins_and_changes_no_indonesian():
    plan = _earnings_plan()
    before = copy.deepcopy(plan)
    chat, calls = _translator(_earnings_english())
    out, notes = agent.translate_plan(plan, chat=chat)
    assert plan == before                                   # the input is not touched
    assert _without_english(out) == plan                    # no Indonesian value changed
    assert notes["status"] == "translated" and notes["dropped"] == notes["problems"] == []
    assert notes["attached"] == notes["fields"] == len(_earnings_english())
    assert len(calls) == 1 == notes["calls"]
    # One call: {path: Indonesian} out, {path: English} back.
    assert _asked(calls[0]) == {f.path: f.text for f in agent._prose_fields(plan)}
    assert calls[0][0]["content"].startswith("Role: PLAN TRANSLATOR")
    scenario = out["earnings_scenario"]
    reply = _earnings()["earnings_scenario"]
    assert scenario["rationale_en"] == reply["rationale_en"]
    assert scenario["thesis_points_en"] == reply["thesis_points_en"]
    assert scenario["thesis_titles_en"] == reply["thesis_titles_en"]
    assert scenario["bank_drivers"]["rationale_en"] == reply["bank_drivers"]["rationale_en"]
    assert [r["explanation_en"] for r in scenario["key_risks"]] == [
        r["explanation_en"] for r in reply["key_risks"]]
    # A code is its own English: "3Q26" may come back unchanged.
    assert scenario["catalysts_risks"][0]["timing_en"] == "3Q26"
    assert "source_ids_en" not in json.dumps(out) and "direction_en" not in json.dumps(out)


def test_a_bad_twin_gets_one_repair_and_is_dropped_if_still_wrong():
    plan = _earnings_plan()
    good = _earnings_english()
    bad = dict(good)
    del bad["earnings_scenario.rationale"]                                        # missing
    bad["earnings_scenario.thesis_points[0]"] = ("Kredit yang tumbuh sekitar 8% menopang NII "
                                                 "dan NIM stays around 5,6%.")  # mixed language
    explanation = "earnings_scenario.key_risks[0].explanation"
    bad[explanation] = good[explanation].replace("84%", "85%")                    # other figures
    repair = dict(bad, **{explanation: good[explanation]})                       # fixes one
    chat, calls = _translator(bad, repair=repair)
    out, notes = agent.translate_plan(plan, chat=chat)
    assert len(calls) == 2 == notes["calls"]
    # The repair asks for the failing paths only, with their errors.
    failing = {"earnings_scenario.rationale", "earnings_scenario.thesis_points[0]", explanation}
    assert set(_asked(calls[1])) == failing
    errors = calls[1][-1]["content"]
    assert "is missing" in errors and "English only" in errors and "figures" in errors
    scenario = out["earnings_scenario"]
    assert _without_english(out) == plan
    assert "rationale_en" not in scenario
    assert "thesis_points_en" not in scenario             # a list twin goes whole
    assert scenario["thesis_titles_en"] == _earnings()["earnings_scenario"]["thesis_titles_en"]
    assert scenario["key_risks"][0]["explanation_en"] == good[explanation]   # fixed by the repair
    assert notes["status"] == "partial"
    assert any(n.startswith("earnings_scenario.rationale:") for n in notes["dropped"])
    assert any("the list stays Indonesian" in n for n in notes["dropped"])


def test_twins_follow_the_rules_of_their_indonesian_fields():
    plan = _earnings_plan()
    english = _earnings_english()
    english["earnings_scenario.key_risks[2].headline"] = "caps"
    english["earnings_scenario.thesis_points[1]"] = (
        "We keep a hold on costs at 0,4% and ROE above 20%, a good sign.")
    english["earnings_scenario.catalysts_risks[0].item"] = plan["earnings_scenario"][
        "catalysts_risks"][0]["item"]                    # Indonesian prose, not a code
    chat, _ = _translator(english)
    _, notes = agent.translate_plan(plan, chat=chat)
    dropped = notes["dropped"]
    assert any(n.startswith("earnings_scenario.key_risks[2].headline:") and "8-70" in n
               and "capital" in n for n in dropped)
    assert any(n.startswith("earnings_scenario.thesis_points[1]:") and "found 'hold'" in n
               for n in dropped)
    assert any(n.startswith("earnings_scenario.catalysts_risks[0].item:") and
               "repeats the Indonesian" in n for n in dropped)
    rows = {"bank_outyear_scenario": _without_english(_outyears())["bank_outyear_scenario"]}
    chat, _ = _translator({"bank_outyear_scenario[0].rationale": "贷款增长" * 12})
    out, notes = agent.translate_plan(rows, chat=chat)
    assert out is rows and notes["status"] == "failed"
    assert notes["dropped"][0] == (
        "bank_outyear_scenario[0].rationale: must be English only; must state exactly the "
        "Indonesian figures, written as in the Indonesian")


def test_interim_twin_obeys_the_interim_evidence_rules():
    official = {"sales_production_bridge": [{"production": 100, "sales": 60}]}
    plan = {"interim_scenario": {
        "rationale": "Penjualan H2 mengikuti produksi 1H26 dengan ketidakpastian stok yang besar."}}
    chat, _ = _translator({"interim_scenario.rationale":
                           "H2 sales ≈ production in 1H26, with large uncertainty over inventory."})
    out, notes = agent.translate_plan(plan, chat=chat, official=official)
    assert "rationale_en" not in out["interim_scenario"]
    assert "sales and production as equal" in notes["dropped"][0]


@pytest.mark.parametrize("reply", [
    RuntimeError("provider down"),
    "Maaf, saya tidak bisa.",
    "[\"not\", \"an object\"]",
    {"content": "{\"earnings_scenario.rationale\": \"H2 profit fol", "finish_reason": "length"},
])
def test_a_failed_translation_leaves_the_plan_unchanged(reply):
    plan = _earnings_plan()
    before = copy.deepcopy(plan)
    calls = []

    def chat(messages, **_kwargs):
        calls.append(messages)
        if isinstance(reply, Exception):
            raise reply
        return reply
    out, notes = agent.translate_plan(plan, chat=chat)
    assert out == before and "_en" not in json.dumps(out)
    assert notes["status"] == "failed" and notes["attached"] == 0 and notes["problems"]
    assert len(calls) == 1                         # a failed call is not repeated
    if isinstance(reply, dict):
        assert "finish_reason=length" in notes["problems"][0]


def test_twins_a_plan_already_had_are_replaced():
    plan = copy.deepcopy(_earnings())
    plan["earnings_scenario"]["rationale_en"] = "An old twin from the same call."
    chat, _ = _translator(_twins(_earnings()))
    out, notes = agent.translate_plan(plan, chat=chat)
    assert out["earnings_scenario"]["rationale_en"] == _earnings()["earnings_scenario"][
        "rationale_en"]
    assert notes["status"] == "translated"


def test_a_plan_without_prose_needs_no_call():
    chat, calls = _translator({})
    plan = {"interim_scenario": {"year": 2026}, "news_effects": []}
    out, notes = agent.translate_plan(plan, chat=chat)
    assert out is plan and calls == [] and notes["status"] == "nothing_to_translate"


def test_large_plans_are_translated_in_several_calls(monkeypatch):
    monkeypatch.setattr(agent, "TRANSLATE_BATCH_CHARS", 400)
    chat, calls = _translator(_earnings_english())
    out, notes = agent.translate_plan(_earnings_plan(), chat=chat)
    assert notes["status"] == "translated" and len(calls) > 1
    asked = [path for messages in calls for path in _asked(messages)]
    assert len(asked) == len(set(asked)) == notes["fields"]


# --- run_live and run_cached -----------------------------------------------


def test_run_live_translates_after_the_subagents_validate(monkeypatch):
    chat, translations = _translator(BANK_ENGLISH)
    result, calls, order = _run(monkeypatch, chat)
    assert result["status"] == "validated", result["problems"]
    assert len(calls) == 4                                  # one call per role, no repair
    assert order == ["subagent"] * 4 + ["translate"]        # translation comes last
    assert result["translation"]["status"] == "translated", result["translation"]
    plan = result["plan"]
    assert _twins(plan) == {path: scrub.normalize_prose(text, english=True)
                            for path, text in BANK_ENGLISH.items()}
    assert plan["stage_classification"]["rationale_en"].startswith("A mature bank")
    assert plan["news_effects"][0]["rationale_en"].startswith("The article")
    assert all(row["rationale_en"] for row in plan["bank_outyear_scenario"])
    assert all("english_dropped" not in sub for sub in result["subagents"].values())


def test_run_live_indonesian_is_the_same_with_or_without_translation(monkeypatch):
    chat, _ = _translator(BANK_ENGLISH)
    translated, _, _ = _run(monkeypatch, chat)
    untranslated, _, order = _run(monkeypatch, None)       # the translation call fails
    assert order[-1] == "translate"
    assert untranslated["status"] == translated["status"] == "validated"
    assert untranslated["translation"]["status"] == "failed"
    assert "_en\"" not in json.dumps(untranslated["plan"])
    assert _without_english(translated["plan"]) == untranslated["plan"]
    for key in ("problems", "subagents", "earnings_status", "outyears_status", "stage_status"):
        assert translated[key] == untranslated[key]


def _plan_key(intake):
    _, spec_sha = agent._spec_sections()
    return f"{intake['ticker']}-{agent.evidence_fingerprint(agent._source_payload(intake), spec_sha)}"


def test_a_reused_plan_without_twins_is_translated_and_stored(monkeypatch, tmp_path):
    intake = _intake()
    key = _plan_key(intake)
    indonesian = {"news_effects": _without_english(NEWS)["news_effects"],
                  "earnings_scenario": _without_english(_earnings())["earnings_scenario"],
                  "stage_classification": _without_english(STAGE)["stage_classification"]}
    # A plan stored before the translation step: no twins, no translation notes.
    stored = {"status": "validated", "plan": copy.deepcopy(indonesian), "problems": [],
              "subagents": {}, "fingerprint": key.split("-", 1)[1], "reused": False}
    store.put(agent.PLAN_COLLECTION, key, stored, tmp_path)
    chat, calls = _translator(BANK_ENGLISH)
    monkeypatch.setattr(agent, "_chat", chat)
    monkeypatch.setattr(agent, "run_live", lambda _intake: pytest.fail("the plan is reused"))

    first = agent.run_cached(intake, db=tmp_path)
    assert first["reused"] is True and len(calls) == 1
    assert first["translation"]["status"] == "translated"
    assert _without_english(first["plan"]) == indonesian
    assert first["plan"]["earnings_scenario"]["key_risks"][0]["headline_en"] == \
        _earnings()["earnings_scenario"]["key_risks"][0]["headline_en"]
    # Stored under the same key, with its twins; the next run calls nothing.
    assert _plan_key(intake) == key
    kept = store.get(agent.PLAN_COLLECTION, key, tmp_path)
    assert kept["plan"] == first["plan"] and kept["translation"] == first["translation"]
    second = agent.run_cached(intake, db=tmp_path)
    assert len(calls) == 1 and second["plan"] == first["plan"]


def test_a_failed_translation_of_a_reused_plan_is_retried_next_time(monkeypatch, tmp_path):
    intake = _intake()
    key = _plan_key(intake)
    indonesian = {"stage_classification": _without_english(STAGE)["stage_classification"]}
    store.put(agent.PLAN_COLLECTION, key, {"status": "validated", "plan": indonesian,
                                           "problems": [], "subagents": {}}, tmp_path)
    failed = agent.run_cached(intake, db=tmp_path)          # conftest: no LLM
    assert failed["translation"]["status"] == "failed" and failed["plan"] == indonesian
    assert "translation" not in store.get(agent.PLAN_COLLECTION, key, tmp_path)
    chat, calls = _translator(BANK_ENGLISH)
    monkeypatch.setattr(agent, "_chat", chat)
    later = agent.run_cached(intake, db=tmp_path)
    assert len(calls) == 1 and later["translation"]["status"] == "translated"
    assert later["plan"]["stage_classification"]["rationale_en"].startswith("A mature bank")


# --- Checks and house style shared with app.stage and app.scrub -------------


def test_stage_checks_the_english_rationale_beside_the_indonesian():
    payload = dict(STAGE["stage_classification"])
    ok, errors, normalized = stage.validate(payload, require_english=True)
    assert ok and normalized["rationale_en"] == payload["rationale_en"]
    bad = dict(payload, rationale_en="A mature bank with profit stable for 3 years dari rilis resmi.")
    ok, errors, normalized = stage.validate(bad)
    assert not ok and all(e.endswith(scrub.EN_SOFT) for e in errors)
    assert normalized["verified"] and "rationale_en" not in normalized
    # A stored classification with a bad twin still classifies; without one it always did.
    assert stage.classify({"ticker": "UJIB"}, {"stage_classification": bad})["source"] == "llm"
    old = {k: v for k, v in payload.items() if k != "rationale_en"}
    assert stage.validate(old)[0] and not stage.validate(old, require_english=True)[0]


def test_house_style_writes_driver_in_english_text():
    text = "Volume Q2 2026 menjadi engine revenue H2."
    plan = {"earnings_scenario": {"rationale": text,
                                  "rationale_en": "Volume in Q2 2026 is the engine of H2 revenue.",
                                  "thesis_points_en": ["Engine of growth — fees"]}}
    out = scrub.normalize_plan(plan)["earnings_scenario"]
    assert out["rationale"] == "Volume 2Q26 menjadi penggerak revenue H2."
    assert out["rationale_en"] == "Volume in 2Q26 is the driver of H2 revenue."
    assert out["thesis_points_en"] == ["Driver of growth, fees"]
    # The English report pass writes English; the Indonesian one is unchanged.
    assert scrub.normalize_prose("engine laba") == "penggerak laba"
    with prose_lang.building("en"):
        assert scrub.normalize_prose("the profit engine") == "the profit driver"
        assert scrub.normalize_prose("engine laba", english=False) == "penggerak laba"


def test_english_problems_compare_figures_after_house_style():
    assert scrub.english_problems("Laba H1 2026 naik 12,4%.", "Profit rose 12,4% in 1H26.") == []
    assert scrub.english_problems("Laba naik 12,4%.", "Profit rose 12.4%.") == [
        "must state exactly the Indonesian figures, written as in the Indonesian"]
    assert scrub.english_problems("Laba naik.", None) == ["is missing"]
    assert scrub.english_problems("Laba naik.", "The cache shows profit rose.") == [
        "uses a term the report does not allow"]


# --- The English report ---------------------------------------------------


def _build(tmp_path, name):
    stored = json.loads((FIXTURES / f"{name}.json").read_text())
    return B.build("BBRI", tmp_path / name, as_of=AS_OF, assumption_plan=stored["plan"],
                   assumption_status=stored["status"])


def test_the_english_report_quotes_the_risk_and_catalyst_twins(tmp_path):
    plan = json.loads((FIXTURES / "bbri_scenario_plan_en.json").read_text())["plan"]
    doc = _build(tmp_path, "bbri_scenario_plan_en")
    old = _build(tmp_path, "bbri_scenario_plan")
    risks = plan["earnings_scenario"]["key_risks"]
    assert [r["judul_en"] for r in doc["risks"]] == [r["headline_en"] for r in risks]
    assert [r["isi_en"] for r in doc["risks"]] == [r["explanation_en"] for r in risks]
    cover_en = " ".join(p.get("isi_en") or "" for p in doc["cover"]["paragraf"]
                        if isinstance(p, dict))
    assert "Nearest positive catalyst: 3Q26 earnings release." in cover_en
    # The Indonesian edition is the same with or without the twins.
    assert _without_english(doc["risks"]) == _without_english(old["risks"])
    assert _without_english(doc["cover"]) == _without_english(old["cover"])
    assert "Katalis positif terdekat: rilis earnings 3Q26." in " ".join(
        p["isi"] for p in doc["cover"]["paragraf"] if isinstance(p, dict))
    # A stored plan without twins still builds; its risks have no English of their own.
    assert all("judul_en" not in r for r in old["risks"])


# --- app.rebuild --translate-assumptions ----------------------------------


VOLATILE = {"run_manifest", "generated_at", "built_at", "created_at"}


def _indonesian_doc(doc):
    def strip(value):
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items()
                    if k not in VOLATILE and not k.endswith("_en")}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value
    return strip(doc)


def test_rebuild_translate_assumptions_adds_english_and_keeps_the_indonesian(tmp_path,
                                                                            monkeypatch, capsys):
    """A stored BBRI run whose Forecast Plan predates the translation step:
    ``--translate-assumptions`` rebuilds the same Indonesian report as a plain
    rebuild, and the English edition gains the plan's twins."""
    stored = json.loads((FIXTURES / "bbri_scenario_plan.json").read_text())
    english = _twins(json.loads((FIXTURES / "bbri_scenario_plan_en.json").read_text())["plan"])
    source = tmp_path / "src"
    B.build("BBRI", source, as_of=AS_OF, assumption_plan=copy.deepcopy(stored["plan"]),
            assumption_status=stored["status"])
    outputs.save(outputs.TRACE, source, "BBRI", {
        "ticker": "BBRI", "report": {"as_of": AS_OF},
        "forecast_assumptions": {"status": stored["status"], "plan": stored["plan"]}})
    chat, calls = _translator(english)
    monkeypatch.setattr(agent, "_chat", chat)

    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "plain"), "BBRI"]) == 0
    assert calls == []                                       # a plain rebuild calls no model
    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "en"),
                         "--translate-assumptions", "BBRI"]) == 0
    assert calls                                             # the translation ran
    assert "terjemahan: partial" in capsys.readouterr().out

    plain = outputs.load(outputs.REPORT, tmp_path / "plain", "BBRI")
    translated = outputs.load(outputs.REPORT, tmp_path / "en", "BBRI")
    assert _indonesian_doc(translated) == _indonesian_doc(plain)
    assert translated["meta"]["rating"] == plain["meta"]["rating"]
    assert translated["meta"]["tp"] == plain["meta"]["tp"]
    risks = translated["risks"]
    assert [r.get("judul_en") for r in risks] == [
        english[f"earnings_scenario.key_risks[{i}].headline"] for i in range(len(risks))]
    assert all("judul_en" not in r for r in plain["risks"])
    # The rebuilt trace stores the translated plan and the notes.
    fa = outputs.load(outputs.TRACE, tmp_path / "en", "BBRI")["forecast_assumptions"]
    agent_plan = fa.get("agent_plan_raw", fa["plan"])
    assert _without_english(agent_plan) == stored["plan"]
    assert _twins(agent_plan) == {path: scrub.normalize_prose(text, english=True)
                                  for path, text in english.items()}
    assert fa["translation"]["status"] == "partial"          # the fixture lacks some twins
    manifest = outputs.load(outputs.MANIFEST, tmp_path / "en", "BBRI")
    assert manifest["rebuild"]["translated_assumptions"] is True


def test_translate_assumptions_needs_named_tickers(tmp_path):
    with pytest.raises(SystemExit):
        rebuild.main(["--from", str(tmp_path / "src"), "--out", str(tmp_path / "out"),
                      "--translate-assumptions"])
    with pytest.raises(SystemExit):
        rebuild.main(["--from", str(tmp_path / "src"), "--out", str(tmp_path / "out"),
                      "--translate-assumptions", "--refresh-assumptions", "BBRI"])
