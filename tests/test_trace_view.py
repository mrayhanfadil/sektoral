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
                       "explanation_en": "CoF in FY2025 is already 3,51%.", "source_ids": ["official"]}
    assert governance["category_en"] == "Governance"
    assert governance["headline_en"] is None and governance["explanation_en"] is None
    catalyst, = view["catalysts"]
    assert catalyst["item_en"] == "Cost of credit rises gradually to 3,10% in H2"
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
