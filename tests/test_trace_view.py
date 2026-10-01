"""Browser trace only exposes a bounded provenance manifest projection."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import prose_lang, scrub  # noqa: E402
from app.trace_view import build  # noqa: E402


def test_trace_view_projects_bundle_identity_and_hashes_without_local_paths():
    audit = {"ticker": "TEST", "run_manifest": {
        "publication_id": "publication-sha",
        "code_revision": "abc1234",
        "source_tree_sha256": "tree-sha",
        "working_tree": {"dirty": True, "sha256": "work-sha",
                         "changed_files": [{"path": "/secret/private.py"}]},
        "as_of": "2026-09-26", "profile": "going_concern_fcff",
        "forecast_basis": "historical_screening_proxy", "production_ready": False,
        "model": {"forecast_agent": "test-model", "agent_effort": "high",
                  "schema_version": 1},
        "spec_sha256": "spec-sha", "evidence_register_sha256": "evidence-sha",
        "source_text_en_sha256": "translation-sha",
        "release_policy": {"policy": {"version": "1.0.0", "effective_date": "2026-09-26",
                                        "status": "documented_baseline_not_enforced",
                                        "ambiguities": [{"id": "issuer_actual_calendar"}]},
                           "sha256": "policy-sha"},
        "house_assumptions": {"policy": {
            "version": "1.0.0", "documented_as_of": "2026-09-26",
            "effective_from": None, "status": "documented_baseline_not_enforced",
            "discount_rates": {
                "IDR": {"risk_free": 0.065, "risk_free_basis": "analyst policy",
                        "country_risk_premium": 0.0, "beta": 1.1,
                        "equity_risk_premium": 0.04, "cost_of_debt_pretax": 0.09,
                        "terminal_growth": 0.035, "growth_sensitivity": [0.025, 0.035, 0.045],
                        "rate_sensitivity": [-0.01, 0.0, 0.01]},
                "USD": {"risk_free": None, "risk_free_basis": "dated UST",
                        "country_risk_premium": 0.025, "beta": 1.1,
                        "equity_risk_premium": 0.04, "cost_of_debt_pretax": None,
                        "cost_of_debt_basis": "market or issuer", "terminal_growth": 0.03,
                        "growth_sensitivity": [0.02, 0.03, 0.04],
                        "rate_sensitivity": [-0.01, 0.0, 0.01]},
            }, "unresolved": ["terminal reinvestment return"]}, "sha256": "house-sha"},
        "source_pack_sha256": {"data/issuer_evidence/TEST.json": "source-sha"},
        "cache_snapshot_sha256": {"/company/report/TEST/": {
            "cache_key": "/company/report/TEST/", "content_sha256": "cache-sha"}},
        "artifacts": {"pdf": {"file": "TEST.pdf", "sha256": "pdf-sha"},
                      "html_en": {"file": "TEST.en.html", "sha256": "english-sha"}},
        "missing_artifacts": ["trace_html"],
        "private_key": "must not appear",
    }}

    result = build(audit)

    manifest = result["run_manifest"]
    assert manifest["publication_id"] == "publication-sha"
    assert manifest["artifacts"]["pdf"]["sha256"] == "pdf-sha"
    assert manifest["artifacts"]["html_en"] == {"file": "TEST.en.html", "sha256": "english-sha"}
    assert manifest["source_text_en_sha256"] == "translation-sha"
    assert manifest["release_policy"]["version"] == "1.0.0"
    assert manifest["release_policy"]["sha256"] == "policy-sha"
    assert manifest["release_policy"]["ambiguities"] == ["issuer_actual_calendar"]
    assert manifest["house_assumptions"]["sha256"] == "house-sha"
    assert manifest["house_assumptions"]["idr"]["risk_free"] == 0.065
    assert manifest["house_assumptions"]["usd"]["risk_free_basis"] == "dated UST"
    assert manifest["house_assumptions"]["unresolved"] == ["terminal reinvestment return"]
    assert manifest["cache_snapshot_sha256"]["/company/report/TEST/"]["content_sha256"] == "cache-sha"
    assert manifest["working_tree"]["dirty"] is True
    assert "changed_files" not in manifest["working_tree"]
    assert "/secret/private.py" not in str(manifest)
    assert "private_key" not in str(manifest)


def test_trace_view_passes_the_research_english_twins_through():
    card = {"title": "Pendapatan", "observation": "Cache mencatat pendapatan.",
            "implication": "Konteks usaha.", "caveat": "Satu catatan saja.",
            "title_en": "Revenue", "observation_en": "The cache records revenue.",
            "citations": []}
    view = build({"ticker": "TEST", "research": {"document": {"insights": [card]}}})
    shown = view["research"]["insights"][0]
    assert shown["title"] == "Pendapatan" and shown["title_en"] == "Revenue"
    assert shown["observation_en"] == "The cache records revenue."
    assert shown["caveat_en"] is None  # an old brief, or a dropped twin


def test_analyst_validator_notes_split_out_the_words_to_remove():
    problems = [
        "sintesis ditolak: prosa memuat bahasa rekomendasi investasi; hapus kata: beli, akumulasi; "
        "tulis dalam bahasa Indonesia saja; hapus: 中文",
        "sintesis ditolak: prosa tidak boleh memuat angka (angka ditampilkan dari sinyal yang dicite); "
        "hapus: 12, 3,5%, Rp1.234",
        "sintesis: token non-Indonesia dihapus: 公司, 利润",
        "sintesis: JSONDecodeError: bad",
        {"not": "a string"},
    ]
    view = build({"ticker": "TEST", "analyst": {"problems": problems}})
    assert view["analyst_problems"] == problems[:4]  # the strings stay as they are
    assert view["analyst_problems_en"] == [
        "synthesis rejected: prose contains investment-advice wording; remove the words: beli, "
        "akumulasi; write in Indonesian only; remove: 中文",
        "synthesis rejected: prose may not contain figures (figures are shown from the cited "
        "signals); remove: 12, 3.5%, Rp1,234",
        "synthesis: non-Indonesian tokens removed: 公司, 利润", "synthesis: JSONDecodeError: bad"]
    assert [n.pop("message_en") for n in view["analyst_problem_notes"]] == [
        "synthesis rejected: prose contains investment-advice wording; write in Indonesian only",
        "synthesis rejected: prose may not contain figures (figures are shown from the cited signals)",
        "synthesis: non-Indonesian tokens removed",
        "synthesis: JSONDecodeError: bad"]
    assert view["analyst_problem_notes"] == [
        {"message": "sintesis ditolak: prosa memuat bahasa rekomendasi investasi; "
                    "tulis dalam bahasa Indonesia saja", "removed": ["beli", "akumulasi", "中文"]},
        {"message": "sintesis ditolak: prosa tidak boleh memuat angka (angka ditampilkan dari sinyal "
                    "yang dicite)", "removed": ["12", "3,5%", "Rp1.234"]},
        {"message": "sintesis: token non-Indonesia dihapus", "removed": ["公司", "利润"]},
        {"message": "sintesis: JSONDecodeError: bad", "removed": []},
    ]
    assert build({"ticker": "TEST"})["analyst_problem_notes"] == []


def test_analyst_notes_recorded_by_the_run_are_used_as_they_are():
    notes = [{"message": "sintesis: teks Inggris dibuang, bahasa Indonesia dipakai", "removed": []}]
    view = build({"ticker": "TEST", "analyst": {"problems": ["x; hapus: 1"], "problem_notes": notes}})
    assert view["analyst_problem_notes"] == [
        {**notes[0], "message_en": "synthesis: English text dropped, Indonesian kept"}]


def test_trace_view_passes_the_forecast_english_twins_through():
    plan = {"news_effects": [{"rationale": "Alasan.", "rationale_en": "Reason.",
                              "mechanism": "Mekanisme.", "mechanism_en": "Mechanism."}],
            "interim_scenario": {"rationale": "Interim.", "rationale_en": "Interim EN."},
            "outyear_scenario": [{"year": "FY27F", "rationale": "Lanjut.", "rationale_en": "Later."}]}
    view = build({"ticker": "TEST", "forecast_assumptions": {"plan": plan}})["forecast"]
    assert view["news_effects"][0]["rationale_en"] == "Reason."
    assert view["news_effects"][0]["mechanism_en"] == "Mechanism."
    assert view["news_effects"][0]["uncertainty_en"] is None
    assert view["interim"]["rationale_en"] == "Interim EN."
    assert view["outyears"][0]["rationale_en"] == "Later."


def test_trace_view_shows_the_key_risks_and_catalysts_with_their_english():
    scenario = {
        "key_risks": [
            {"category": "Pendanaan", "headline": "Tekanan biaya dana naik",
             "headline_en": "Rising cost of funds",
             "explanation": "CoF FY2025 sudah 3,51%.", "explanation_en": "CoF in FY2025 is already 3,51%.",
             "source_ids": ["official"]},
            {"category": "Tata kelola", "headline": "Risiko konsentrasi kredit UMKM",
             "explanation": "Segmen UMKM dominan.", "source_ids": []}],
        "catalysts_risks": [
            {"item": "Biaya kredit naik bertahap ke 3,10% H2", "timing": "2H26 (forecast)",
             "driver_path": "Provisi naik → laba tertekan", "direction": "Negatif",
             "source_ids": ["official"], "item_en": "Cost of credit rises gradually to 3,10% in H2",
             "driver_path_en": "Provisions rise → profit under pressure"}]}
    view = build({"ticker": "BBRI", "forecast_assumptions": {
        "plan": {"earnings_scenario": scenario}}})["forecast"]
    funding, governance = view["key_risks"]
    assert funding == {"category": "Pendanaan", "category_en": "Funding",
                       "headline": "Tekanan biaya dana naik", "headline_en": "Rising cost of funds",
                       "explanation": "CoF FY2025 sudah 3,51%.",
                       "explanation_en": "CoF in FY2025 is already 3.51%.", "source_ids": ["official"]}
    assert governance["category_en"] == "Governance"
    assert governance["headline_en"] is None and governance["explanation_en"] is None
    catalyst, = view["catalysts"]
    assert catalyst["item_en"] == "Cost of credit rises gradually to 3.10% in H2"
    assert catalyst["timing"] == "2H26 (forecast)" and catalyst["timing_en"] is None
    assert catalyst["driver_path_en"] == "Provisions rise → profit under pressure"
    assert catalyst["direction"] == "Negatif" and catalyst["direction_en"] == "Negative"
    empty = build({"ticker": "BBRI"})["forecast"]
    assert empty["key_risks"] == [] and empty["catalysts"] == []


def test_a_curated_interim_rationale_gets_its_english_from_the_source_text():
    # AMMN's interim rationale comes from data/analyst_scenarios, which drops the
    # agent's twin; its English is kept in data/source_text_en/AMMN.json.
    curated = json.loads((ROOT / "data" / "analyst_scenarios" / "AMMN.json").read_text())[
        "forecast_rationale"]
    view = build({"ticker": "AMMN", "forecast_assumptions": {
        "plan": {"interim_scenario": {"rationale": curated}}}})["forecast"]
    english = view["interim"]["rationale_en"]
    assert english.startswith("As of 24 September 2026, Q2 actuals can be derived")
    # The same figures as the Indonesian, written as there.
    assert prose_lang.figures(english) == prose_lang.figures(curated)
    assert scrub.english_problems(curated, english) == []
    # A twin the plan has wins; Indonesian without one stays without.
    own = build({"ticker": "AMMN", "forecast_assumptions": {"plan": {"interim_scenario": {
        "rationale": curated, "rationale_en": "Own twin."}}}})["forecast"]
    assert own["interim"]["rationale_en"] == "Own twin."
    unknown = build({"ticker": "AMMN", "forecast_assumptions": {"plan": {"interim_scenario": {
        "rationale": "Asumsi interim yang belum diterjemahkan."}}}})["forecast"]
    assert unknown["interim"]["rationale_en"] is None


# An analyst result stored before English twins, with the host fallback synthesis.
OLD_ANALYST = {
    "ticker": "AMMN", "status": "partial",
    "plan": {"question": "Apakah leverage AMMN masih tertinggi?", "source": "agent",
             "hypotheses": ["Leverage tetap tertinggi."]},
    "steps": [{"tool": "find_peers", "why": "Bangun grup peer.", "status": "ok",
               "summary": "6 emiten · peer dipilih menurut model bisnis; alasan tiap peer dan yang "
                          "dikeluarkan ada di paket grup"},
              {"tool": "quarterly_financials", "why": "Cek laba.", "status": "ok",
               "summary": "2 sinyal, 2 bertanda: lonjakan, berbalik ke laba"}],
    "signals": [
        {"id": "quarter.revenue_yoy", "kind": "change", "label": "Pendapatan kuartal terakhir, yoy",
         "display": "38.858,7%", "flag": "lonjakan", "period": "2026-03-31 vs 2025-03-31",
         "note": "basis pembanding tahun lalu sangat kecil; persentase tidak informatif"},
        {"id": "peer.net_margin", "kind": "peer", "label": "Margin laba bersih", "display": "13,5%",
         "note": "peringkat 4 dari 6 (1 = lebih tinggi)", "median_display": "20,1%", "rank": 4, "n": 6,
         "peers": [{"symbol": "PSAB", "display": "65,2%"}]},
        {"id": "flow.net_20d", "kind": "flow", "label": "Arus bersih asing, 20 sesi terakhir",
         "display": "Rp1.234 miliar", "period": "2026-08-14 s.d. 2026-09-11"}],
    "peers": {"basis": "peer dipilih menurut model bisnis; alasan tiap peer dan yang dikeluarkan ada "
                       "di paket grup", "group": "Penambang tembaga dan emas di BEI"},
    "synthesis": {"headline": "Ringkasan sinyal yang ditandai host", "source": "host_fallback",
                  "findings": [{"title": "Pendapatan kuartal terakhir, yoy: lonjakan",
                                "interpretation": "Sinyal ini ditandai aturan host; belum ada tafsir agent.",
                                "caveat": "Perlu dibaca bersama konteks usaha emiten.",
                                "signal_ids": ["quarter.revenue_yoy"]}],
                  "hypotheses": [{"index": 0, "verdict": "belum terjawab", "signal_ids": [],
                                  "reason": "Agent tidak menyelesaikan penilaian hipotesis."}],
                  "next_checks": []},
    "changes": {"first_run": False, "items": [
        {"kind": "rank", "text": "Margin laba bersih: peringkat 7 → 4 dari 6"},
        {"kind": "cleared_flag", "text": "Sinyal Liabilitas / ekuitas (tertinggi di grup) tidak lagi muncul"},
        {"kind": "news", "text": "Berita baru: AS Kerek Impor Tembaga dari Kongo"}]},
}


def test_an_old_analyst_result_gets_english_for_host_text():
    view = build({"ticker": "AMMN", "analyst": OLD_ANALYST})["analyst"]
    revenue, margin, flow = view["signals"]
    assert revenue["label"] == "Pendapatan kuartal terakhir, yoy"  # the Indonesian is unchanged
    assert revenue["label_en"] == "Latest quarter revenue, yoy" and revenue["flag_en"] == "surge"
    assert revenue["note_en"] == ("the year-earlier base is very small; the percentage is not "
                                  "informative")
    assert revenue["display"] == "38.858,7%" and revenue["display_en"] == "38,858.7%"
    assert revenue["period_en"] is None  # the same in both languages
    assert margin["label_en"] == "Net profit margin" and margin["note_en"] == "rank 4 of 6 (1 = higher)"
    assert margin["median_display_en"] == "20.1%" and margin["peers"][0]["display_en"] == "65.2%"
    assert flow["display_en"] == "Rp1,234bn" and flow["period_en"] == "2026-08-14 to 2026-09-11"
    assert [s["summary_en"] for s in view["steps"]] == [
        "6 issuers · peers chosen by business model; the reason for each peer, and for those left "
        "out, is in the group pack", "2 signals, 2 flagged: surge, back to profit"]
    assert [s["why_en"] for s in view["steps"]] == [None, None]  # agent prose without a twin
    assert view["plan"]["question_en"] is None and view["plan"]["hypotheses_en"] is None
    assert view["peers"]["basis_en"].startswith("peers chosen by business model")
    assert view["peers"]["group_en"] == "IDX-listed copper and gold miners"
    synthesis = view["synthesis"]
    assert synthesis["headline_en"] == "Summary of the signals the host flagged"
    finding = synthesis["findings"][0]
    assert finding["title_en"] == "Latest quarter revenue, yoy: surge"
    assert finding["interpretation_en"] == ("The host rules flagged this signal; there is no agent "
                                            "interpretation yet.")
    assert finding["caveat_en"] == "Read it together with the issuer's business context."
    assert synthesis["hypotheses"][0]["reason_en"] == "The agent did not finish assessing the hypothesis."
    assert [i["text_en"] for i in view["changes"]["items"]] == [
        "Net profit margin: rank 7 → 4 of 6",
        "The Liabilities / equity signal (highest in the group) no longer appears",
        "New article: AS Kerek Impor Tembaga dari Kongo"]


def test_the_trace_gives_the_method_and_research_brief_their_english():
    view = build({"ticker": "BBRI",
                  "report": {"status": "distributable_assumption_led",
                             "target_method": "DDM dividen skenario FY26F-FY30F + terminal Gordon "
                                              "(CoE, bukan WACC) [fallback: PER]"},
                  "research": {"document": {
                      "summary": "Brief ini merangkum temuan cache yang lolos validasi.",
                      "limitations": ["Snapshot perusahaan hanya menggambarkan data pada tanggal "
                                      "laporan.", "Catatan agen yang lain."]}}})
    assert view["report"]["method_en"] == ("DDM on scenario dividends FY26F-FY30F + Gordon terminal "
                                           "(CoE, not WACC)")
    research = view["research"]
    assert research["summary"] == "Brief ini merangkum temuan cache yang lolos validasi."
    assert research["summary_en"] == "This brief summarizes the cache findings that passed validation."
    assert research["limitations_en"] == [
        "The company snapshot describes data as of the report date only.", None]
    empty = build({"ticker": "BBRI"})
    assert empty["research"]["summary_en"] is None and empty["research"]["limitations_en"] is None
    assert empty["report"]["method_en"] is None
    # Forecast validator notes are English already: a parallel list without twins.
    forecast = build({"ticker": "BBRI", "forecast_assumptions": {
        "problems": ["news_effects[1] years are invalid"]}})["forecast"]
    assert forecast["problems_en"] == [None] and empty["forecast"]["problems_en"] == []


def test_forecast_twins_reach_the_web_with_english_figures():
    plan = {"news_effects": [{"rationale": "Laba naik 12,4% ke Rp1.234,5 miliar.",
                              "rationale_en": "Profit rose 12,4% to Rp1.234,5 miliar."}],
            "interim_scenario": {"rationale": "Revenue H2 top-down US$2.975bn."}}
    view = build({"ticker": "TEST", "forecast_assumptions": {"plan": plan}})["forecast"]
    assert view["news_effects"][0]["rationale_en"] == "Profit rose 12.4% to Rp1,234.5bn."
    # Curated source English is shown as written (it may already use English figures).
    assert view["interim"]["rationale_en"] is None or "2.975" in view["interim"]["rationale_en"]


# The agent's Bank Driver Scenario and the curated driver file the bank model ran.
AGENT_BANK = {
    "earnings_scenario": {"bank_drivers": {
        "year": 2026, "loan_growth_pct": 10.0, "nim_pct": 7.55, "non_ii_to_nii_pct": 36.0,
        "cost_to_income_pct": 42.0, "cost_of_credit_pct": 3.1, "deposit_growth_pct": 14.0,
        "rationale": "Pertumbuhan kredit FY2026 kami proyeksikan 10,0%.", "source_ids": ["official"]}},
    "bank_outyear_scenario": [{
        "year": 2027, "loan_growth_pct": 10.5, "nim_pct": 7.4, "non_ii_to_nii_pct": 35.5,
        "cost_to_income_pct": 42.0, "cost_of_credit_pct": 3.2, "deposit_growth_pct": 7.5,
        "rationale": "Kredit 10,5% sebagai skenario analis.", "source_ids": ["official", "news:1"]}]}


def _driver(value, kind, why, refs=None):
    return {"value": value, "kind": kind, "rationale": why,
            **({"source_refs": refs} if refs else {})}


CURATED_BANK = {
    "ticker": "BBRI", "reviewed_at": "2026-09-26",
    "payout_path": {"values": [0.7, 0.6], "rationale": "Payout sekitar 70% lalu 60%.",
                    "source_refs": ["bbri-call"]},
    "drivers": [
        {"year": 2026, "loan_growth_pct": _driver(9.0, "company_guidance", "Tetap.", ["bbri-call"]),
         "nim_pct": _driver(7.5, "sourced", "Tetap.", ["bbri-fs", "bbri-call"]),
         "non_ii_to_nii_pct": _driver(34.0, "sourced", "Tetap.", ["bbri-fs"]),
         "cost_to_income_pct": _driver(42.0, "company_guidance", "Tetap.", ["bbri-call"]),
         "cost_of_credit_pct": _driver(3.1, "company_guidance", "Tetap.", ["bbri-call"])},
        {"year": 2027, **{key: _driver(value, "analyst_assumption", "Menuju pertumbuhan nominal.")
                          for key, value in (("loan_growth_pct", 9.0), ("nim_pct", 7.4),
                                             ("non_ii_to_nii_pct", 34.0),
                                             ("cost_to_income_pct", 42.0),
                                             ("cost_of_credit_pct", 3.0))}}]}


def _bank_doc(drivers=CURATED_BANK):
    return {"meta": {"ticker": "BBRI"},
            "model_inputs": {"kind": "bank", "drivers": drivers, "valuation": {}},
            "forecast_assumptions": {"outyear_scenario": {
                "status": "validated_bank_driver_scenario", "rows": []}}}


def test_the_bank_drivers_the_model_ran_come_from_the_report_not_the_agent():
    audit = {"ticker": "BBRI", "forecast_assumptions": {"plan": AGENT_BANK}}
    view = build(audit, _bank_doc())["forecast"]
    # The agent's proposal stays as it was proposed.
    assert [r["loan_growth_pct"] for r in view["bank_drivers"]] == [10.0, 10.5]
    assert view["bank_drivers_used"] is False
    assert view["bank_drivers_note"] == (
        "Model bank tidak memakai driver usulan agent ini: neraca, laba dan dividen dihitung dari "
        "berkas driver kurasi data/bank_drivers/BBRI.json (ditinjau 2026-09-26).")
    assert view["bank_drivers_note_en"].startswith(
        "The bank model did not use the agent's proposed drivers")
    first, second = view["bank_drivers_model"]
    assert first["year"] == "2026" and first["loan_growth_pct"] == 9.0 and first["nim_pct"] == 7.5
    assert first["deposit_growth_pct"] is None and first["payout_pct"] == 70.0
    assert first["kinds"]["loan_growth_pct"] == "company_guidance"
    assert first["source_ids"] == ["bbri-call", "bbri-fs"]
    assert first["source"] == "data/bank_drivers/BBRI.json"
    assert first["rationale"].startswith("Kredit: Tetap.; NIM: Tetap.")
    assert first["rationale_en"].startswith("Loans: Unchanged.; NIM: Unchanged.")
    assert second["payout_pct"] == 60.0 and second["source_ids"] == []
    assert second["kinds"] == {key: "analyst_assumption" for key in (
        "loan_growth_pct", "nim_pct", "non_ii_to_nii_pct", "cost_to_income_pct",
        "cost_of_credit_pct")}
    assert view["bank_payout_rationale"] == "Payout sekitar 70% lalu 60%."
    # A row the agent wrote as an analyst scenario is not tagged official.
    proposed, scenario = view["bank_drivers"]
    assert proposed["source_ids"] == ["official"] and proposed["analyst_assumption"] is False
    assert scenario["source_ids"] == ["news:1"] and scenario["analyst_assumption"] is True


def test_the_agent_bank_drivers_are_used_when_the_model_ran_them():
    same = {**CURATED_BANK, "drivers": [
        {"year": row["year"], **{key: _driver(row[key], "analyst_assumption", "Tetap.")
                                 for key in ("loan_growth_pct", "nim_pct", "non_ii_to_nii_pct",
                                             "cost_to_income_pct", "cost_of_credit_pct")}}
        for row in [AGENT_BANK["earnings_scenario"]["bank_drivers"]]
        + AGENT_BANK["bank_outyear_scenario"]]}
    audit = {"ticker": "BBRI", "forecast_assumptions": {"plan": AGENT_BANK}}
    view = build(audit, _bank_doc(same))["forecast"]
    assert view["bank_drivers_used"] is True
    assert view["bank_drivers_model"] is None and view["bank_drivers_note"] is None
    # Without a driver file the report's bank scenario is the agent's table.
    plain = {"forecast_assumptions": {"outyear_scenario": {
        "status": "validated_bank_driver_scenario",
        "rows": [{"year": 2027, **{k: v for k, v in AGENT_BANK["bank_outyear_scenario"][0].items()
                                   if k.endswith("_pct")}}]}}}
    assert build(audit, plain)["forecast"]["bank_drivers_used"] is True
    # A trace without its report says nothing about what the model ran.
    alone = build(audit)["forecast"]
    assert alone["bank_drivers_used"] is None and alone["bank_drivers_model"] is None


def test_out_years_from_the_model_own_schedule_say_the_agent_table_was_not_used():
    plan = {"outyear_scenario": [
        {"year": 2027, "revenue_growth_pct": 8, "rationale": "Skenario analis: kapasitas penuh.",
         "source_ids": ["official"]},
        {"year": 2028, "revenue_growth_pct": 4, "rationale": "Mengikuti panduan emiten.",
         "source_ids": ["official"]}]}
    audit = {"ticker": "AMMN", "forecast_assumptions": {"plan": plan}}
    lom = {"meta": {"ticker": "AMMN"}, "forecast_assumptions": {"outyear_scenario": {
        "status": "lom_schedule", "rows": [
            {"year": 2027, "revenue_growth_pct": 29.9, "ebitda_margin_pct": 68.1,
             "rationale": "Jadwal LoM: umpan 54 Mt.", "source_ids": ["official"]},
            {"year": 2030, "revenue_growth_pct": 2.2, "rationale": "Jadwal LoM.",
             "source_ids": ["official"]}]}}}
    view = build(audit, lom)["forecast"]
    assert view["outyears_used"] is False
    assert view["outyears_note"] == ("Model tidak memakai tabel tahun lanjutan agent ini: forecast "
                                     "FY27F-FY30F mengikuti jadwal Life-of-Mine (LoM) tambang.")
    assert view["outyears_note_en"] == ("The model did not use the agent's out-year table: the "
                                        "FY27F-FY30F forecast follows the mine's Life-of-Mine (LoM) "
                                        "schedule.")
    assert [r["revenue_growth_pct"] for r in view["outyears_model"]] == [29.9, 2.2]
    assumed, guided = view["outyears"]
    assert assumed["source_ids"] == [] and assumed["analyst_assumption"] is True
    assert guided["source_ids"] == ["official"] and guided["analyst_assumption"] is False
    operating = {"meta": {"ticker": "POWR"}, "forecast_assumptions": {"outyear_scenario": {
        "status": "operating_driver_model", "rows": [{"year": 2027}, {"year": 2030}]}}}
    assert build(audit, operating)["forecast"]["outyears_note"].endswith(
        "mengikuti Operating Model (data/operating_drivers/POWR.json).")
    scenario = {"forecast_assumptions": {"outyear_scenario": {
        "status": "validated_analyst_scenario", "rows": []}}}
    used = build(audit, scenario)["forecast"]
    assert used["outyears_used"] is True and used["outyears_model"] is None
    assert build(audit)["forecast"]["outyears_used"] is None


def _analyst(members, **extra):
    return {"plan": {"question": "Q"}, "market_date": "2026-09-22", "signals": [],
            "peers": {"basis": "peer dipilih menurut model bisnis; alasan tiap peer dan yang "
                               "dikeluarkan ada di paket grup", "group": "Perawatan pesawat (MRO)",
                      "source": "grup peer kurasi Sektoral data/peer_groups/GMFI.json",
                      "members": [{"symbol": "GMFI", "is_self": True}]
                      + [{"symbol": s, "is_self": False} for s in members]}, **extra}


PEER_DOC = {"exhibits": [
    {"judul": "Grup peer: alasan pemilihan", "data": {"rows": []},
     "catatan_sumber": "Sumber: data/peer_groups/GMFI.json (kurasi Sektoral, 2026-09-25). "
                       "Peer hanya emiten BEI."},
    {"judul": "Perbandingan peer Jasa penerbangan di BEI, diperlebar dari MRO pesawat",
     "data": {"rows": [["Garuda Indonesia (GIAA)", "1"], ["Garuda Maintenance (GMFI) (emiten)", "2"],
                       ["Cahaya Aero Services (CASS)", "3"], ["Median peer (tanpa emiten)", "4"]]},
     "catatan_sumber": "Sumber: grup peer kurasi Sektoral data/peer_groups/GMFI.json (tabel peer "
                       "Sectors GMFI) (peer dipilih menurut model bisnis); per 2026-09-24; kriteria"}]}


def test_a_research_run_on_another_peer_group_is_marked_stale():
    view = build({"ticker": "GMFI", "analyst": _analyst(["S59.SI", "S63.SI", "AIR"])},
                 PEER_DOC)["analyst"]
    assert view["peers_stale"] is True
    assert view["peers_current"] == {
        "group": "Jasa penerbangan di BEI, diperlebar dari MRO pesawat",
        "group_en": "IDX-listed aviation services, widened from aircraft MRO",
        "basis": "Peer hanya emiten BEI.", "basis_en": None, "as_of": "2026-09-25",
        "source": "data/peer_groups/GMFI.json", "members": ["GIAA", "CASS"]}
    assert view["market_date"] == "2026-09-22"
    # The run's peer table has no date of its own: null, and a note saying so.
    assert view["peers"]["as_of"] is None
    assert view["peers"]["as_of_note"] == ("Sumber tabel peer riset ini tidak mencantumkan tanggal "
                                           "snapshot; data pasar riset per 2026-09-22.")
    assert view["peers"]["as_of_note_en"] == ("The research run's peer table source states no "
                                              "snapshot date; the run's market data are as of "
                                              "2026-09-22.")
    same = build({"ticker": "GMFI", "analyst": _analyst(["GIAA", "CASS"])}, PEER_DOC)["analyst"]
    assert same["peers_stale"] is False and same["peers_current"] is None
    unknown = build({"ticker": "GMFI", "analyst": _analyst(["GIAA"])})["analyst"]
    assert unknown["peers_stale"] is None and unknown["peers_current"] is None
    dated = _analyst(["GIAA"])
    dated["peers"]["as_of"] = "2026-09-25"
    peers = build({"ticker": "GMFI", "analyst": dated})["analyst"]["peers"]
    assert peers["as_of"] == "2026-09-25" and peers["as_of_note"] is None


def test_every_signal_is_shown_up_to_the_bound_with_its_total():
    signals = [{"id": f"web.{i}", "kind": "web", "label": f"Berita {i}",
                "url": f"https://example.com/{i}"} for i in range(130)]
    items = [{"title": f"T{i}", "url": f"https://example.com/{i}"} for i in range(45)]
    view = build({"ticker": "AMMN", "analyst": _analyst(
        [], signals=signals, web_news={"items": items})})["analyst"]
    assert len(view["signals"]) == 120 and view["signals_total"] == 130
    assert len(view["web_news"]["items"]) == 40 and view["web_news"]["total"] == 45


def test_a_positive_pe_beside_negative_earnings_is_an_outlier():
    pe = {"id": "peer.pe", "kind": "peer", "label": "P/E", "display": "38,6x",
          "peers": [{"symbol": "MDKA", "value": 9141.67, "display": "9.141,7x"},
                    {"symbol": "ANTM", "value": 8.6, "display": "8,6x"}]}
    roe = {"id": "peer.roe", "kind": "peer", "label": "ROE", "display": "4,6%",
           "peers": [{"symbol": "MDKA", "value": -0.021, "display": "-2,1%"},
                     {"symbol": "ANTM", "value": 0.1, "display": "10,0%"}]}
    view = build({"ticker": "AMMN", "analyst": _analyst([], signals=[pe, roe])})["analyst"]
    mdka, antm = view["signals"][0]["peers"]
    assert mdka["outlier"] is True and antm["outlier"] is False
    assert mdka["outlier_note_en"].startswith("A positive P/E while the earnings")
    assert antm["outlier_note"] is None
    # A negative ROE is the data itself, not an outlier.
    assert all(p["outlier"] is False for p in view["signals"][1]["peers"])
