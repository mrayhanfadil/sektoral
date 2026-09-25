"""Bank Driver Scenario subagents (financial_ddm): validation, the scripted
two-role run and the fallback to the earnings scenario. No real LLM."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.forecast_assumptions import run as agent  # noqa: E402
from app import bank_model  # noqa: E402
from test_bank_model import BALANCE, HISTORY, OFFICIAL  # noqa: E402

ARTICLE = {"title": "BCA: kredit tumbuh 8% yoy, NIM tertekan suku bunga", "timestamp": "2026-08-10",
           "source": "https://news.example/bca-kredit", "origin": "sectors",
           "body": "Kredit BCA tumbuh 8% yoy; manajemen memperkirakan NIM 5,5-5,7% hingga akhir tahun."}


def _intake(profile="financial_ddm", history=True):
    return {"ticker": "UJIB", "as_of": "2026-09-24", "model_profile": profile,
            "latest_official_actual": copy.deepcopy(OFFICIAL),
            "official_evidence": {"balance_sheet": copy.deepcopy(BALANCE)},
            "news": [dict(ARTICLE)], "news_full": [],
            "bank_history": copy.deepcopy(HISTORY) if history else None,
            "payout": 0.8, "payout_basis": "payout ratio historis di data Sectors",
            "annuals": [{"year": 2025, "revenue": 110.0, "earnings": 57.5}]}


def _source(**kw):
    return agent._source_payload(_intake(**kw))


def _row(year, **kw):
    row = {"year": year, "loan_growth_pct": 8.0, "nim_pct": 5.6, "non_ii_to_nii_pct": 33.0,
           "cost_to_income_pct": 33.0, "cost_of_credit_pct": 0.4, "deposit_growth_pct": None,
           "rationale": "Kredit tumbuh sejalan rekam jejak; NIM dekat 1H26 karena biaya dana stabil.",
           "source_ids": ["official"]}
    row.update(kw)
    return row


def _thesis():
    return {
        "thesis_points": [
            "Kredit tumbuh sekitar 8% menopang NII walau NIM tertahan di kisaran 5,6%.",
            "Biaya kredit rendah 0,4% menjaga laba bersih dan ROE di atas 20%."],
        "thesis_titles": ["Kredit menopang NII", "Biaya kredit tetap rendah"],
        "catalysts_risks": [
            {"item": "Penurunan suku bunga", "timing": "Semester II 2026",
             "driver_path": "Suku bunga turun -> yield kredit turun lebih cepat dari biaya dana -> NIM dan NII tertekan.",
             "direction": "Negatif", "source_ids": ["news:0"]},
            {"item": "Permintaan kredit korporasi", "timing": "Sepanjang 2026",
             "driver_path": "Kredit korporasi naik -> aset produktif bertambah -> NII dan laba naik.",
             "direction": "Positif", "source_ids": ["official"]}],
        "key_risks": [
            {"category": "Pendanaan", "headline": "Biaya dana saat likuiditas ketat",
             "explanation": "CASA 84% menopang biaya dana 1,1%; kenaikan biaya dana 20bp menekan NIM "
                            "dan laba bersih bila deposito tumbuh lebih cepat dari giro dan tabungan.",
             "source_ids": ["official"]},
            {"category": "Operasi", "headline": "Kualitas aset kredit konsumer",
             "explanation": "Biaya kredit 0,4% berada di dekat titik terendah; kenaikan ke 0,8% "
                            "memangkas laba sebelum pajak sekitar Rp4 triliun per tahun.",
             "source_ids": ["official"]},
            {"category": "Regulasi", "headline": "Batas suku bunga dan biaya layanan",
             "explanation": "Pendapatan non-bunga setara 33% NII; aturan biaya transaksi yang lebih "
                            "ketat dapat mengurangi pendapatan fee dan laba bersih.",
             "source_ids": ["official"]}]}


def _earnings(**drivers):
    return {"earnings_scenario": {
        "bank_drivers": _row(2026, **drivers),
        "rationale": "Laba H2 mengikuti 1H26: kredit tumbuh sejalan rekam jejak, NIM dekat run-rate 1H.",
        "source_ids": ["official", "news:0"], **_thesis()}}


def _outyears(**drivers):
    return {"bank_outyear_scenario": [_row(2027 + i, **drivers) for i in range(4)]}


NEWS = {"news_effects": [{
    "article_index": 0, "source_url": ARTICLE["source"], "title": ARTICLE["title"],
    "timestamp": ARTICLE["timestamp"], "driver": "none", "change": 0, "years": [],
    "rationale": "Artikel memuat pertumbuhan kredit dan NIM; dipakai di skenario bank, bukan CoE."}]}
STAGE = {"stage_classification": {
    "life_cycle_stage": "mature", "has_steady_state_3y": True, "commodity_price_driven": False,
    "dissimilar_segments": 1, "source_ids": ["official"],
    "rationale": "Bank matang dengan laba stabil tiga tahun terakhir dari rilis resmi emiten."}}


def _scripted(replies):
    """A chat stand-in answering by role; ``replies`` maps a role marker to a list."""
    calls = []

    def chat(messages, **_kwargs):
        system = messages[0]["content"]
        role = next(marker for marker in replies if marker in system)
        calls.append((role, messages))
        queue = replies[role]
        return json.dumps(queue.pop(0) if len(queue) > 1 else queue[0])
    return chat, calls


def test_source_carries_the_bank_reference_only_for_banks():
    source = _source()
    assert agent._bank_mode(source)
    ref = source["bank"]["reference"]
    assert ref["interim_year"] == 2026 and len(ref["history"]) == 3
    assert agent._source_payload(_intake(profile="going_concern_fcff"))["bank"] is None
    assert not agent._bank_mode(_source(history=False))


def test_bank_row_bounds_sources_and_record():
    source = _source()
    assert agent._validate_bank_row(_row(2026), source, 2026, "r") == []
    assert any("nim_pct outside bounds" in p for p in
               agent._validate_bank_row(_row(2026, nim_pct=20.0), source, 2026, "r"))
    assert any("must cite official" in p for p in
               agent._validate_bank_row(_row(2026, source_ids=["news:0"]), source, 2026, "r"))
    assert any("year must be 2026" in p for p in
               agent._validate_bank_row(_row(2027), source, 2026, "r"))
    assert any("Indonesian" in p for p in agent._validate_bank_row(
        _row(2026, rationale="贷款增长" * 12), source, 2026, "r"))
    assert agent._validate_bank_row(_row(2026, deposit_growth_pct=9.0), source, 2026, "r") == []


def test_a_driver_far_from_the_record_needs_a_dated_source():
    source = _source()
    ref = source["bank"]["reference"]
    high = max(ref["three_year_average"]["nim_pct"], ref["interim"]["nim_pct"]) + 1.0
    problems = agent._validate_bank_row(_row(2026, nim_pct=high), source, 2026, "r")
    assert any("departs from the issuer's record" in p and "nim_pct" in p for p in problems)
    assert agent._validate_bank_row(_row(2026, nim_pct=high, source_ids=["official", "news:0"]),
                                    source, 2026, "r") == []
    fast = ref["three_year_average"]["loan_growth_pct"] + 12
    assert agent._validate_bank_row(_row(2026, loan_growth_pct=fast), source, 2026, "r")


def test_bank_earnings_and_outyears_validation():
    source = _source()
    scenario = dict(_earnings()["earnings_scenario"], source_url=OFFICIAL["source_url"],
                    published_at=OFFICIAL["published_at"])
    assert agent._validate_bank_earnings(scenario, source) == []
    assert any("does not match official" in p for p in agent._validate_bank_earnings(
        dict(scenario, source_url="https://other"), source))
    assert any("not a bank driver" in p for p in agent._validate_bank_earnings(
        dict(scenario, h2_revenue_to_h1=1.0), source))
    assert any("thesis_points" in p for p in agent._validate_bank_earnings(
        dict(scenario, thesis_points=[]), source))
    rows = _outyears()["bank_outyear_scenario"]
    assert agent._validate_bank_outyears(rows, source) == []
    assert agent._validate_bank_outyears(rows[:3], source) == [
        "bank_outyear_scenario must contain exactly four annual rows"]
    shifted = [dict(r, year=r["year"] + 1) for r in rows]
    assert agent._validate_bank_outyears(shifted, source)


def test_bank_run_sets_drivers_and_passes_the_model_anchor(monkeypatch):
    chat, calls = _scripted({
        "NEWS DRIVER ANALYST": [NEWS], "BANK DRIVER SCENARIO ANALYST": [_earnings()],
        "STAGE CLASSIFIER": [STAGE], "BANK DRIVER OUTYEAR ANALYST": [_outyears()]})
    monkeypatch.setattr(agent, "_chat", chat)
    result = agent.run_live(_intake())
    assert result["status"] == "validated", result["problems"]
    assert result["earnings_status"] == "validated" and result["outyears_status"] == "validated"
    plan = result["plan"]
    drivers = plan["earnings_scenario"]["bank_drivers"]
    assert drivers["year"] == 2026 and drivers["nim_pct"] == 5.6
    assert "h2_revenue_to_h1" not in plan["earnings_scenario"]
    assert plan["earnings_scenario"]["source_url"] == OFFICIAL["source_url"]
    assert set(plan["earnings_scenario"]["source_refs"]) == {"official", "news:0"}
    assert [r["year"] for r in plan["bank_outyear_scenario"]] == [2027, 2028, 2029, 2030]
    assert plan["outyear_scenario"] is None
    roles = [role for role, _ in calls]
    assert "FY EARNINGS SCENARIO ANALYST" not in " ".join(roles)
    outyear_payload = json.loads(next(m for role, m in calls
                                      if role == "BANK DRIVER OUTYEAR ANALYST")[1]["content"])
    anchor = outyear_payload["anchor"]
    expected = bank_model.project(HISTORY, OFFICIAL, BALANCE, [drivers], payout=0.8,
                                  payout_basis="x")["rows"][0]
    assert anchor["year"] == 2026
    assert anchor["full_year"]["net_profit"] == round(expected["net_cons"] / 1e12, 1)
    assert anchor["full_year"]["nim_pct"] == round(expected["net_interest_margin"] * 100, 2)
    assert outyear_payload["required_years"] == [2027, 2028, 2029, 2030]


def test_bank_outyears_are_repaired_when_a_driver_departs_without_a_source(monkeypatch):
    ref = _source()["bank"]["reference"]
    far = max(ref["three_year_average"]["cost_of_credit_pct"], ref["interim"]["cost_of_credit_pct"]) + 1
    chat, calls = _scripted({
        "NEWS DRIVER ANALYST": [NEWS], "BANK DRIVER SCENARIO ANALYST": [_earnings()],
        "STAGE CLASSIFIER": [STAGE],
        "BANK DRIVER OUTYEAR ANALYST": [_outyears(cost_of_credit_pct=far), _outyears()]})
    monkeypatch.setattr(agent, "_chat", chat)
    result = agent.run_live(_intake())
    assert result["outyears_status"] == "validated"
    outyear_calls = [m for role, m in calls if role == "BANK DRIVER OUTYEAR ANALYST"]
    assert len(outyear_calls) == 2
    assert "departs from the issuer's record" in outyear_calls[1][-1]["content"]


def test_a_bank_without_sectors_bank_history_keeps_the_earnings_role(monkeypatch):
    legacy = {"earnings_scenario": {
        "h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 51.0, "source_ids": ["official"],
        "rationale": "Laba H2 mengikuti run-rate 1H26 tanpa katalis baru yang terukur.",
        **_thesis()}}
    chat, calls = _scripted({
        "NEWS DRIVER ANALYST": [NEWS], "FY EARNINGS SCENARIO ANALYST": [legacy],
        "STAGE CLASSIFIER": [STAGE], "OUTYEAR EARNINGS SCENARIO ANALYST": [{"outyear_scenario": [
            {"year": 2027 + i, "revenue_growth_pct": 5.0, "ebitda_margin_pct": None,
             "net_income_margin_pct": 50.0, "capex_to_revenue_pct": None,
             "rationale": "Pertumbuhan moderat sejalan rekam jejak dengan margin stabil.",
             "source_ids": ["official"]} for i in range(4)]}]})
    monkeypatch.setattr(agent, "_chat", chat)
    result = agent.run_live(_intake(history=False))
    assert result["status"] == "validated", result["problems"]
    assert "bank_drivers" not in result["plan"]["earnings_scenario"]
    assert len(result["plan"]["outyear_scenario"]) == 4


def test_plan_schema_moves_the_fingerprint():
    source = _source()                      # a financial_ddm source
    before = agent.evidence_fingerprint(source, "spec")
    original = dict(agent.PLAN_SCHEMA_BY_PROFILE)
    try:
        agent.PLAN_SCHEMA_BY_PROFILE["financial_ddm"] = 4
        assert agent.evidence_fingerprint(source, "spec") != before
    finally:
        agent.PLAN_SCHEMA_BY_PROFILE.clear()
        agent.PLAN_SCHEMA_BY_PROFILE.update(original)
    assert agent.plan_schema("financial_ddm") == 5


def test_a_bank_schema_bump_keeps_other_profiles_plans():
    assert agent.plan_schema("going_concern_fcff") == agent.PLAN_SCHEMA_DEFAULT
    assert agent.plan_schema("finite_life_mining") == agent.PLAN_SCHEMA_DEFAULT


def test_the_plan_is_pinned_to_the_sections_the_agents_read():
    text, sha = agent._spec_sections()
    import hashlib
    assert sha == hashlib.sha256(text.encode()).hexdigest()


def test_long_bank_rationale_is_cut_to_whole_sentences():
    long = "Kredit tumbuh sejalan rekam jejak tiga tahun dan hasil 1H26 resmi. " * 10
    row = agent._bank_row(_row(2026, rationale=long, extra="drop me"))
    assert "extra" not in row
    assert len(row["rationale"]) <= 450 and row["rationale"].endswith(".")
    assert agent._validate_bank_row(row, _source(), 2026, "r") == []


def test_advice_problem_names_the_phrase_for_the_repair():
    thesis = _thesis()
    thesis["thesis_points"] = ["BCA akan hold CASA di atas 80% sehingga biaya dana tetap rendah.",
                               thesis["thesis_points"][1]]
    problems = agent._validate_thesis(thesis, {"official", "news:0"})
    assert any("found 'hold'" in p for p in problems)
