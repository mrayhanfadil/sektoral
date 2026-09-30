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
