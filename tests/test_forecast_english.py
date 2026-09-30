"""English twins (``<field>_en``) of the Forecast Assumption Agent's prose:
asked in the same call, checked like their Indonesian fields, dropped (never
failing the run) when still wrong after the repairs, and quoted by the
English report. No real LLM."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.forecast_assumptions import run as agent  # noqa: E402
from app import build as B, prose_lang, scrub, stage  # noqa: E402
from test_forecast_bank_agent import (NEWS, STAGE, _earnings, _intake, _outyears,  # noqa: E402
                                      _scripted, _source)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _replies(earnings=None, **kw):
    replies = {"NEWS DRIVER ANALYST": [NEWS], "BANK DRIVER SCENARIO ANALYST": [earnings or _earnings()],
               "STAGE CLASSIFIER": [STAGE], "BANK DRIVER OUTYEAR ANALYST": [_outyears()]}
    replies.update(kw)
    return replies


def _without_english(value):
    if isinstance(value, dict):
        return {k: _without_english(v) for k, v in value.items() if not k.endswith("_en")}
    if isinstance(value, list):
        return [_without_english(v) for v in value]
    return value


def _run(monkeypatch, replies):
    chat, calls = _scripted(replies)
    monkeypatch.setattr(agent, "_chat", chat)
    return agent.run_live(_intake()), calls


def test_replies_with_english_twins_pass_on_the_first_call(monkeypatch):
    result, calls = _run(monkeypatch, _replies())
    assert result["status"] == "validated", result["problems"]
    assert len(calls) == 4                      # one call per role, no repair
    plan = result["plan"]
    scenario = plan["earnings_scenario"]
    reply = _earnings()["earnings_scenario"]
    assert scenario["rationale_en"] == reply["rationale_en"]
    assert scenario["thesis_points_en"] == reply["thesis_points_en"]
    assert scenario["thesis_titles_en"] == reply["thesis_titles_en"]
    assert scenario["bank_drivers"]["rationale_en"] == reply["bank_drivers"]["rationale_en"]
    assert [r["headline_en"] for r in scenario["key_risks"]] == [
        r["headline_en"] for r in reply["key_risks"]]
    assert scenario["catalysts_risks"][1]["item_en"] == "Corporate loan demand"
    assert all(row["rationale_en"] for row in plan["bank_outyear_scenario"])
    assert plan["news_effects"][0]["rationale_en"].startswith("The article")
    assert plan["stage_classification"]["rationale_en"].startswith("A mature bank")
    assert not any("english_dropped" in sub for sub in result["subagents"].values())
    # The prompt asks for the twins and their figures.
    system = calls[0][1][0]["content"]
    assert "suffix _en" in system and "Indonesian number format" in system


def test_bad_english_twins_are_dropped_after_the_repairs_and_the_indonesian_kept(monkeypatch):
    reply = _earnings()
    scenario = reply["earnings_scenario"]
    del scenario["rationale_en"]                                       # missing
    scenario["thesis_points_en"][0] = ("Kredit yang tumbuh sekitar 8% menopang NII dan "
                                       "NIM stays around 5,6%.")          # mixed language
    scenario["key_risks"][0]["explanation_en"] = scenario["key_risks"][0][
        "explanation_en"].replace("84%", "85%")                       # other figures
    result, calls = _run(monkeypatch, _replies(earnings=reply))
    assert result["status"] == "validated", result["problems"]
    earnings_calls = [m for role, m in calls if role == "BANK DRIVER SCENARIO ANALYST"]
    assert len(earnings_calls) == 3             # the normal repair attempts ran
    repair = earnings_calls[-1][-1]["content"]
    assert "key_risks[0].explanation_en" in repair and agent._ENGLISH_REPAIR in repair
    out = result["plan"]["earnings_scenario"]
    # The Indonesian is kept as the model wrote it.
    assert _without_english(out)["key_risks"] == _without_english(scenario["key_risks"])
    assert out["thesis_points"] == scenario["thesis_points"]
    assert out["rationale"] == scenario["rationale"]
    # Only the bad twins are gone; a list twin goes whole.
    assert "rationale_en" not in out and "thesis_points_en" not in out
    assert "explanation_en" not in out["key_risks"][0]
    assert out["key_risks"][0]["headline_en"] == scenario["key_risks"][0]["headline_en"]
    assert out["key_risks"][1]["explanation_en"] == scenario["key_risks"][1]["explanation_en"]
    assert out["thesis_titles_en"] == scenario["thesis_titles_en"]
    notes = result["subagents"]["earnings"]["english_dropped"]
    assert len(notes) == 3 and all(n.endswith(scrub.EN_SOFT) for n in notes)
    assert any("figures" in n for n in notes) and any("English only" in n for n in notes)


def test_a_twin_fixed_by_the_repair_is_kept(monkeypatch):
    bad = _earnings()
    risk = bad["earnings_scenario"]["key_risks"][1]
    risk["explanation_en"] = risk["explanation_en"].replace("Rp4", "Rp5")
    result, calls = _run(monkeypatch, _replies(**{"BANK DRIVER SCENARIO ANALYST": [bad, _earnings()]}))
    assert result["earnings_status"] == "validated"
    assert len([c for c in calls if c[0] == "BANK DRIVER SCENARIO ANALYST"]) == 2
    assert result["plan"]["earnings_scenario"]["key_risks"][1]["explanation_en"] == \
        _earnings()["earnings_scenario"]["key_risks"][1]["explanation_en"]
    assert "english_dropped" not in result["subagents"]["earnings"]


def test_replies_without_english_still_validate(monkeypatch):
    replies = {role: [_without_english(r) for r in queue] for role, queue in _replies().items()}
    result, _ = _run(monkeypatch, replies)
    assert result["status"] == "validated", result["problems"]
    assert json.dumps(result["plan"]).count("_en\"") == 0
    assert set(n for n, sub in result["subagents"].items() if sub.get("english_dropped")) == {
        "news", "earnings", "outyears", "stage"}


def test_twins_follow_the_rules_of_their_indonesian_fields():
    source = _source()
    fragment = copy.deepcopy(_earnings())
    scenario = fragment["earnings_scenario"]
    scenario["key_risks"][2]["headline_en"] = "caps"
    scenario["thesis_points_en"][1] = "We keep a hold on costs at 0,4% and ROE above 20%, a good sign."
    scenario["catalysts_risks"][0]["item_en"] = scenario["catalysts_risks"][0]["item"]
    problems = agent._english_problems("earnings", fragment, source)
    assert any("key_risks[2].headline_en" in p and "8-70" in p and "capital" in p
               for p in problems)
    assert any("thesis_points_en [1]" in p and "found 'hold'" in p for p in problems)
    assert any("catalysts_risks[0].item_en repeats the Indonesian" in p for p in problems)
    assert len(problems) == 3
    news = copy.deepcopy(NEWS)
    news["news_effects"][0]["rationale_en"] = "Loans grew 8% and NIM held in the article."
    assert any("figures" in p for p in agent._english_problems("news", news, source))
    rows = _outyears()
    rows["bank_outyear_scenario"][0]["rationale_en"] = "贷款增长" * 12
    assert agent._english_problems("outyears", rows, source) == [
        "bank_outyear_scenario[2027].rationale_en must be English only; must state exactly the "
        "Indonesian figures, written as in the Indonesian" + scrub.EN_SOFT]


def test_interim_twin_obeys_the_interim_evidence_rules():
    source = {"official": {"sales_production_bridge": [{"production": 100, "sales": 60}]}}
    fragment = {"interim_scenario": {
        "rationale": "Penjualan H2 mengikuti produksi 1H26 dengan ketidakpastian stok yang besar.",
        "rationale_en": "H2 sales ≈ production in 1H26, with large uncertainty over inventory."}}
    problems = agent._english_problems("interim", fragment, source)
    assert problems and "sales and production as equal" in problems[0]
    agent._english_problems("interim", fragment, source, drop=True)
    assert "rationale_en" not in fragment["interim_scenario"]


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


def _build(tmp_path, name):
    stored = json.loads((FIXTURES / f"{name}.json").read_text())
    return B.build("BBRI", tmp_path / name, as_of="2026-09-24", assumption_plan=stored["plan"],
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
