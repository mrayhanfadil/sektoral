"""Analyst review of the Forecast Plan before publication (app.assumption_review)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import assumption_review as R, outputs  # noqa: E402

PLAN = {"earnings_scenario": {"year": 2026, "h2_revenue_to_h1": 1.1, "h2_net_margin_pct": 5.0,
                              "bank_drivers": {"year": 2026, "nim_pct": 7.5,
                                               "rationale": "NIM 1H26 resmi."},
                              "rationale": "Panduan emiten."},
        "outyear_scenario": [{"year": 2027, "revenue_growth_pct": 8.0, "ebitda_margin_pct": 20.0,
                              "rationale": "Rekam jejak."}],
        "news_effects": [{"article_index": 0, "change": 0}]}


def _stored(folder, ticker="UJIA"):
    outputs.save(outputs.REPORT, folder, ticker, {"meta": {"ticker": ticker, "status":
                                                            "distributable_assumption_led",
                                                            "rating": "Buy", "tp": 1000}})
    outputs.save(outputs.TRACE, folder, ticker, {"forecast_assumptions": {"plan": PLAN}})


def test_fields_list_only_the_numeric_drivers_with_labels():
    paths = {f["path"]: f for f in R.fields(PLAN)}
    assert set(paths) == {"earnings_scenario.h2_revenue_to_h1", "earnings_scenario.h2_net_margin_pct",
                          "earnings_scenario.bank_drivers.nim_pct",
                          "outyear_scenario[0].revenue_growth_pct",
                          "outyear_scenario[0].ebitda_margin_pct"}
    assert paths["earnings_scenario.bank_drivers.nim_pct"]["label"] == "NIM"
    assert paths["outyear_scenario[0].revenue_growth_pct"]["year"] == 2027


@pytest.mark.parametrize("edit, message", [
    ({"path": "news_effects[0].change", "value": 1, "reason": "alasan cukup panjang"}, "tidak dapat diedit"),
    ({"path": "outyear_scenario[0].revenue_growth_pct", "value": "x", "reason": "alasan cukup panjang"}, "angka"),
    ({"path": "outyear_scenario[0].revenue_growth_pct", "value": 900, "reason": "alasan cukup panjang"}, "rentang"),
    ({"path": "outyear_scenario[0].revenue_growth_pct", "value": 9, "reason": "pendek"}, "alasan"),
])
def test_bad_edits_are_refused(edit, message):
    with pytest.raises(R.ReviewError, match=message):
        R.apply_edits(PLAN, [edit])


def test_approval_without_edits_records_the_plan_it_covers(tmp_path):
    _stored(tmp_path)
    assert R.status(tmp_path, "UJIA")["state"] == "pending"
    with pytest.raises(R.ReviewError, match="reviewer"):
        R.approve(tmp_path, "UJIA", " ")
    rec = R.approve(tmp_path, "UJIA", "Analis Satu", "Driver sesuai rilis.")
    assert rec["decision"] == "approved" and rec["plan_sha"] == R.plan_sha(PLAN)
    verdict = {"status": "distributable_assumption_led", "rating": "Buy", "tp": 1000}
    assert rec["after"] == verdict and rec["before"] == {**verdict, "plan_sha": rec["plan_sha"]}
    assert R.status(tmp_path, "UJIA")["state"] == "approved"
    assert outputs.load(outputs.TRACE, tmp_path, "UJIA")["assumption_review"]["reviewer"] == "Analis Satu"


def test_edits_rebuild_on_the_edited_plan_and_log_each_change(tmp_path):
    _stored(tmp_path)
    calls = []

    def rebuild(t, source, out, **kw):
        calls.append(kw)
        trace = outputs.load(outputs.TRACE, out, t)
        trace["forecast_assumptions"] = {"plan": kw["plan_override"],
                                         "agent_plan_raw": kw["plan_override"],
                                         "agent_plan_before_review": PLAN}
        outputs.save(outputs.TRACE, out, t, trace)
        outputs.save(outputs.REPORT, out, t, {"meta": {"ticker": t, "status": "distributable_x",
                                                       "rating": "Hold", "tp": 900}})
    rec = R.approve(tmp_path, "UJIA", "Analis Dua", edits=[
        {"path": "earnings_scenario.bank_drivers.nim_pct", "value": 7.2,
         "reason": "NIM H2 turun mengikuti suku bunga acuan."}], rebuild_fn=rebuild)
    assert calls and calls[0]["plan_override"]["earnings_scenario"]["bank_drivers"]["nim_pct"] == 7.2
    assert rec["decision"] == "approved_with_edits"
    assert rec["edits"] == [{"path": "earnings_scenario.bank_drivers.nim_pct", "label": "NIM",
                             "year": 2026, "unit": "%", "from": 7.5, "to": 7.2,
                             "reason": "NIM H2 turun mengikuti suku bunga acuan."}]
    assert rec["after"]["tp"] == 900 and rec["before"]["tp"] == 1000
    assert R.status(tmp_path, "UJIA")["state"] == "approved"


def test_review_endpoints_need_the_reviewer_token(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app import server
    reports = tmp_path / "reports"
    reports.mkdir()
    _stored(reports)
    monkeypatch.delenv("SECTORAL_REVIEW_TOKEN", raising=False)
    body = {"reviewer": "Analis Tiga", "note": "ok", "edits": []}
    with TestClient(server.create_app(tmp_path / "out", reports)) as client:
        view = client.get("/api/reports/UJIA/review").json()
        assert view["state"] == "pending" and not view["enabled"]
        assert any(f["path"] == "earnings_scenario.bank_drivers.nim_pct" for f in view["fields"])
        assert client.post("/api/reports/UJIA/review", json=body).status_code == 403
        monkeypatch.setenv("SECTORAL_REVIEW_TOKEN", "rahasia")
        assert client.post("/api/reports/UJIA/review", json=body,
                           headers={"X-Review-Token": "salah"}).status_code == 403
        bad = client.post("/api/reports/UJIA/review", headers={"X-Review-Token": "rahasia"},
                          json={**body, "edits": [{"path": "news_effects[0].change", "value": 1,
                                                   "reason": "alasan cukup panjang"}]})
        assert bad.status_code == 400 and "tidak dapat diedit" in bad.json()["detail"]
        ok = client.post("/api/reports/UJIA/review", json=body, headers={"X-Review-Token": "rahasia"})
        assert ok.status_code == 200 and ok.json()["state"] == "approved"
        assert client.get("/api/reports/NONE/review").status_code == 404


def test_a_reapproval_keeps_the_earlier_record_and_its_edits(tmp_path):
    _stored(tmp_path)

    def rebuild(t, source, out, **kw):
        trace = outputs.load(outputs.TRACE, out, t)
        trace["forecast_assumptions"] = {"plan": kw["plan_override"], "agent_plan_raw": kw["plan_override"]}
        outputs.save(outputs.TRACE, out, t, trace)
    first = R.approve(tmp_path, "UJIA", "Analis Dua", edits=[
        {"path": "outyear_scenario[0].ebitda_margin_pct", "value": 18.0,
         "reason": "Margin memudar ke rata-rata siklus."}], rebuild_fn=rebuild)
    second = R.approve(tmp_path, "UJIA", "Analis Tiga", "Setuju ulang.")
    assert second["edits"] == [] and second["plan_sha"] == first["plan_sha"]
    assert [h["reviewer"] for h in second["history"]] == ["Analis Dua"]
    assert "history" not in second["history"][0]
    view = R.public(tmp_path, "UJIA")
    assert view["reviewer"] == "Analis Tiga"
    assert [(e["path"], e["reviewer"]) for e in view["edits"]] == [
        ("outyear_scenario[0].ebitda_margin_pct", "Analis Dua")]
    assert view["history"][0]["edits"] == 1
    third = R.approve(tmp_path, "UJIA", "Analis Empat")
    assert [h["reviewer"] for h in third["history"]] == ["Analis Tiga", "Analis Dua"]
