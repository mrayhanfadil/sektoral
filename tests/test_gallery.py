"""Report gallery: public summaries and confined file serving."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import assumption_review, gallery, outputs  # noqa: E402


PLAN = {"outyear_scenario": [{"year": 2027, "revenue_growth_pct": 8.0, "ebitda_margin_pct": 20.0,
                               "net_income_margin_pct": 10.0, "capex_to_revenue_pct": 5.0,
                               "rationale": "Driver mengikuti rekam jejak."}]}


def approve(folder: Path, ticker: str):
    """Record an analyst approval of the report's plan (storing one if the trace has none)."""
    trace = outputs.load(outputs.TRACE, folder, ticker) or {}
    if not assumption_review.report_plan(trace):
        trace = {**trace, "forecast_assumptions": {**(trace.get("forecast_assumptions") or {}),
                                                   "plan": PLAN}}
        outputs.save(outputs.TRACE, folder, ticker, trace)
    return assumption_review.approve(folder, ticker, "Penguji")


def _report(folder: Path, ticker: str, published: bool = True, chain=True, reviewed=True):
    doc = {"meta": {"ticker": ticker, "emiten": f"PT {ticker} Tbk", "tanggal": "2026-09-24",
                    "harga": 1000.0, "status": ("distributable_assumption_led" if published
                                                else "draft_non_distributable"),
                    "rating": "Hold" if published else None, "tp": 1100 if published else None,
                    "upside_persen": 10.0 if published else None,
                    "model_profile": "going_concern_fcff"},
           "method": "FY26F PER median peer x EPS skenario analis [fallback: DCF]",
           "cover": {"headline": "Laba naik"},
           "harness": {"blockers": [] if published else ["release.extreme pe target"]},
           "exhibits": ([{"judul": "Rantai metode valuasi", "data": {"rows": [
               ["1. DCF FCFF (utama)", "Dilewati", "-", "forecast"],
               ["2. PER FY skenario", "Terpilih", "Rp1.100", "ok"],
               ["3. P/BV buku", "Silang cek", "Rp900", "ok"]]}}] if chain else [])}
    outputs.save(outputs.REPORT, folder, ticker, doc)
    (folder / f"{ticker}.pdf").write_bytes(b"%PDF-1.4 test")
    (folder / f"{ticker}-trace.html").write_text("<html>trace</html>")
    if published and reviewed:
        approve(folder, ticker)


def test_summaries_hold_drafts_and_read_the_method_chain(tmp_path):
    _report(tmp_path, "AAAA")
    _report(tmp_path, "BBBB", published=False)
    outputs.save(outputs.REPORT, tmp_path, "NOTES", {})  # not a report
    items = gallery.load(tmp_path)
    assert [i["ticker"] for i in items] == ["AAAA", "BBBB"]
    first, held = items
    assert first["rating"] == "Hold" and first["method"] == "FY26F PER median peer x EPS skenario analis"
    assert [s["decision"] for s in first["chain"]] == ["Dilewati", "Terpilih", "Silang cek"]
    assert first["chain"][0]["step"] == "DCF FCFF"
    assert held["rating"] is None and held["tp"] is None
    assert held["held_reason"].startswith("Method Gate 5")


def test_a_passing_report_is_a_draft_until_an_analyst_approves_its_plan(tmp_path):
    _report(tmp_path, "AAAA", reviewed=False)
    outputs.save(outputs.TRACE, tmp_path, "AAAA", {"forecast_assumptions": {"plan": PLAN}})
    item = gallery.load(tmp_path)[0]
    assert not item["published"] and item["rating"] is None and item["tp"] is None
    assert item["held_reason"] == "menunggu persetujuan asumsi oleh analis"
    assert item["review"]["state"] == "pending"
    assert {s["value"] for s in item["chain"]} == {"ditahan"}
    record = approve(tmp_path, "AAAA")
    item = gallery.load(tmp_path)[0]
    assert item["published"] and item["rating"] == "Hold"
    assert item["review"] == {"state": "approved", "reviewer": "Penguji",
                              "reviewed_at": record["reviewed_at"], "decision": "approved",
                              "edits": 0}
    # A new plan (a fresh run) needs a new approval.
    outputs.save(outputs.TRACE, tmp_path, "AAAA", {"forecast_assumptions": {
        "plan": {**PLAN, "outyear_scenario": [{**PLAN["outyear_scenario"][0],
                                               "revenue_growth_pct": 9.0}]}}})
    assert not gallery.load(tmp_path)[0]["published"]


def test_artifacts_are_confined_to_the_reports_folder(tmp_path):
    _report(tmp_path, "AAAA")
    assert gallery.artifact(tmp_path, "AAAA", "pdf")[1] == "application/pdf"
    assert gallery.artifact(tmp_path, "../AAAA", "pdf") is None
    assert gallery.artifact(tmp_path, "AAAA", "json") is None
    assert gallery.artifact(tmp_path, "ZZZZ", "pdf") is None


def test_draft_profile_falls_back_to_the_run_manifest(tmp_path):
    _report(tmp_path, "BBBB", published=False)
    doc = outputs.load(outputs.REPORT, tmp_path, "BBBB")
    del doc["meta"]["model_profile"]
    doc["run_manifest"] = {"profile": "financial_ddm"}
    outputs.save(outputs.REPORT, tmp_path, "BBBB", doc)
    assert gallery.load(tmp_path)[0]["profile"] == "Bank"


def test_template_harness_blockers_get_a_reader_reason():
    assert gallery._held_reason(["T.T4.discount_rate_currency: pelapor USD"]) == \
        "discount rate belum sesuai mata uang pelaporan"
    assert gallery._held_reason(["T.TF.bare_na: Laba rugi"]) == "pemeriksaan format laporan belum lolos"
