"""Browser trace only exposes a bounded provenance manifest projection."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    assert view["analyst_problem_notes"] == notes


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
