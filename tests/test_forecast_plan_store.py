"""Stored forecast plans make targets reproducible for identical evidence."""
from __future__ import annotations

import copy

from agents.forecast_assumptions import run as F

INTAKE = {"ticker": "TEST", "as_of": "2026-09-24", "model_profile": "finite_life_mining",
          "latest_official_actual": {"source_url": "https://issuer.test/1h26", "period": "1H26",
                                     "published_at": "2026-09-21", "metrics": {"revenue": 10}},
          "official_evidence": {}, "news": [], "news_full": []}


def _fake(status="validated", interim="validated"):
    calls = []

    def run_live(intake):
        calls.append(intake["as_of"])
        return {"status": status, "interim_status": interim,
                "plan": {"interim_scenario": {"year": 2026}} if status != "invalid" else None,
                "problems": []}
    return run_live, calls


def test_identical_evidence_reuses_plan_even_on_another_day(monkeypatch, tmp_path):
    fake, calls = _fake()
    monkeypatch.setattr(F, "run_live", fake)
    first = F.run_cached(INTAKE, db=tmp_path)
    later = dict(INTAKE, as_of="2026-09-30")
    second = F.run_cached(later, db=tmp_path)
    assert calls == ["2026-09-24"]
    assert first["reused"] is False and second["reused"] is True
    assert second["plan"] == first["plan"]


def test_normalized_evidence_register_does_not_fingerprint_report_date_alone():
    source = {"ticker": "TEST", "model_profile": "going_concern_fcff",
              "evidence_register": {"as_of": "2026-09-24", "rows": [
                  {"kind": "official_actual", "published_at": "2026-08-31",
                   "value": {"revenue": 100}}], "violations": [],
                  "critical_violations": []}}
    later = copy.deepcopy(source)
    later["evidence_register"]["as_of"] = "2026-09-30"
    assert F.evidence_fingerprint(source, "spec") == F.evidence_fingerprint(later, "spec")

    later["evidence_register"]["rows"][0]["value"]["revenue"] = 101
    assert F.evidence_fingerprint(source, "spec") != F.evidence_fingerprint(later, "spec")


def test_new_evidence_or_refresh_calls_the_agent_again(monkeypatch, tmp_path):
    fake, calls = _fake()
    monkeypatch.setattr(F, "run_live", fake)
    F.run_cached(INTAKE, db=tmp_path)
    changed = copy.deepcopy(INTAKE)
    changed["latest_official_actual"]["published_at"] = "2026-10-30"
    F.run_cached(changed, db=tmp_path)
    F.run_cached(INTAKE, db=tmp_path, refresh=True)
    assert len(calls) == 3


def test_failed_plans_are_not_stored(monkeypatch, tmp_path):
    fake, calls = _fake(status="invalid")
    monkeypatch.setattr(F, "run_live", fake)
    F.run_cached(INTAKE, db=tmp_path)
    F.run_cached(INTAKE, db=tmp_path)
    assert len(calls) == 2 and not list(tmp_path.glob("*.json"))


def test_intake_without_identity_runs_agent_without_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(F, "run_live", lambda intake: {"status": "validated", "plan": {}})
    assert F.run_cached({}, db=tmp_path)["status"] == "validated"
    assert not list(tmp_path.glob("*.json"))
