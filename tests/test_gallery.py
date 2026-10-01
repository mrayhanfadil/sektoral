"""Report gallery: public summaries and confined file serving."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import assumption_review, gallery, outputs, run_manifest  # noqa: E402
from test_assumption_review import _attestation, _reviewer_identity, _test_register  # noqa: E402


PLAN = {"outyear_scenario": [{"year": 2027, "revenue_growth_pct": 8.0, "ebitda_margin_pct": 20.0,
                               "net_income_margin_pct": 10.0, "capex_to_revenue_pct": 5.0,
                               "rationale": "Driver mengikuti rekam jejak."}]}


def approve(folder: Path, ticker: str):
    """Record an analyst approval of the report's plan (storing one if the trace has none)."""
    trace = outputs.load(outputs.TRACE, folder, ticker) or {}
    report = outputs.load(outputs.REPORT, folder, ticker) or {}
    if not assumption_review.report_plan(trace):
        trace = {**trace, "forecast_assumptions": {**(trace.get("forecast_assumptions") or {}),
                                                   "plan": PLAN}}
    if isinstance(report.get("evidence_register"), dict):
        trace["evidence_register"] = report["evidence_register"]
    outputs.save(outputs.TRACE, folder, ticker, trace)
    return assumption_review.approve(folder, ticker, "Penguji",
                                     attestation=_attestation(),
                                     reviewer_identity=_reviewer_identity("Penguji"))


def _report(folder: Path, ticker: str, published: bool = True, chain=True, reviewed=True,
            english=False):
    evidence_register = _test_register(ticker)
    doc = {"meta": {"ticker": ticker, "emiten": f"PT {ticker} Tbk", "tanggal": "2026-09-24",
                    "harga": 1000.0, "harga_tanggal": "2026-09-23", "status": ("distributable_assumption_led" if published
                                                else "draft_non_distributable"),
                    "rating": "Hold" if published else None, "tp": 1100 if published else None,
                    "upside_persen": 10.0 if published else None,
                    "model_profile": "going_concern_fcff"},
           "method": "FY26F PER median peer x EPS skenario analis [fallback: DCF]",
           "cover": {"headline": "Laba naik"},
           "harness": {"blockers": [] if published else ["release.extreme pe target"]},
           "evidence_register": evidence_register,
           "exhibits": ([{"judul": "Rantai metode valuasi", "data": {"rows": [
               ["1. DCF FCFF (utama)", "Dilewati", "-", "forecast"],
               ["2. PER FY skenario", "Terpilih", "Rp1.100", "ok"],
               ["3. P/BV buku", "Silang cek", "Rp900", "ok"]]}}] if chain else [])}
    outputs.save(outputs.REPORT, folder, ticker, doc)
    outputs.save(outputs.TRACE, folder, ticker,
                 {"forecast_assumptions": {"plan": PLAN}, "evidence_register": evidence_register})
    (folder / f"{ticker}.html").write_text("<html>report</html>")
    (folder / f"{ticker}.pdf").write_bytes(b"%PDF-1.4 test")
    (folder / f"{ticker}-trace.html").write_text("<html>trace</html>")
    if english:  # rendered before the manifest is finalized, so part of the bundle
        (folder / f"{ticker}.en.html").write_text("<html lang='en'>report</html>")
        (folder / f"{ticker}.en.pdf").write_bytes(b"%PDF-1.4 english")
    manifest = run_manifest.finalize_manifest({
        "ticker": ticker, "code_revision": "test", "source_tree_sha256": "a" * 64,
        "spec_sha256": "b" * 64,
        "evidence_register_sha256": run_manifest.content_hash(evidence_register),
        "as_of": "2026-09-24",
    }, folder, ticker)
    outputs.save(outputs.MANIFEST, folder, ticker, manifest)
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
    assert first["release_status"] == "distributable_assumption_led"
    assert first["publication_state"] == "published" and first["analytically_eligible"]
    assert [s["decision"] for s in first["chain"]] == ["Dilewati", "Terpilih", "Silang cek"]
    assert first["chain"][0]["step"] == "DCF FCFF"
    assert [s["decision_code"] for s in first["chain"]] == ["skipped", "selected", "cross_check"]
    # The value as the English report prints it.
    assert [(s["value"], s["value_en"]) for s in first["chain"]] == [
        ("-", "-"), ("Rp1.100", "Rp1,100"), ("Rp900", "Rp900")]
    # The close the price is from, beside the report date.
    assert first["price"] == 1000.0 and first["price_date"] == "2026-09-23"
    assert first["date"] == "2026-09-24"
    assert held["rating"] is None and held["tp"] is None
    assert held["held_reason"] == "laporan belum tersedia untuk umum"
    assert held["method"] == "" and held["headline"] == "" and held["risks"] == []
    assert held["chain"] == [] and held["blockers"] is None
    assert held["publication_state"] == "built" and not held["analytically_eligible"]


def test_summaries_carry_english_beside_the_indonesian(tmp_path):
    _report(tmp_path, "AAAA")
    _report(tmp_path, "BBBB", published=False)
    first, held = gallery.load(tmp_path)
    # A report stored before its English prose: host labels still have theirs.
    assert first["method"] == "FY26F PER median peer x EPS skenario analis"
    assert first["method_en"] == "FY26F median peer PER x Analyst Scenario EPS"
    assert first["profile"] == "Korporasi" and first["profile_en"] == "Corporate"
    assert [s["step"] for s in first["chain"]] == ["DCF FCFF", "PER FY skenario", "P/BV buku"]
    assert [s["step_en"] for s in first["chain"]] == [None, "Scenario FY PER", "Book P/BV"]
    assert first["headline"] == "Laba naik" and first["headline_en"] is None
    assert first["risks_en"] is None
    assert first["held_reason"] == "" and first["held_reason_en"] is None
    assert held["held_reason"] == "laporan belum tersedia untuk umum"
    assert held["held_reason_en"] == "the report is not yet public"
    assert held["method_en"] is None and held["headline_en"] is None
    # The report's own English prose.
    doc = outputs.load(outputs.REPORT, tmp_path, "AAAA")
    doc["cover"]["headline_en"] = "Profit rises"
    doc["risks"] = [{"judul": "Harga tembaga", "judul_en": "Copper price"}, {"judul": "Regulasi"}]
    outputs.save(outputs.REPORT, tmp_path, "AAAA", doc)
    first = gallery.load(tmp_path)[0]
    assert first["headline"] == "Laba naik" and first["headline_en"] == "Profit rises"
    assert first["risks"] == ["Harga tembaga", "Regulasi"]
    assert first["risks_en"] == ["Copper price", None]


def test_a_stale_label_carries_its_english(tmp_path, monkeypatch):
    from app import publication_monitor
    monkeypatch.setattr(publication_monitor, "assess", lambda folder, ticker: {
        "state": "stale",
        "reason": "Pemicu pembaruan terbuka sejak 2026-10-30; laporan tetap tampil dengan label "
                  "stale sampai ditinjau.",
        "triggers": [{"detail": "Rilis resmi 9M26 terbit 2026-10-30; laporan memakai 1H26."}]})
    freshness = gallery._freshness(tmp_path, "AAAA")
    assert freshness["reason"].startswith("Pemicu pembaruan")
    assert freshness["reason_en"] == ("An update trigger has been open since 2026-10-30; the report "
                                      "stays visible, labelled stale, until it is reviewed.")
    assert freshness["triggers_en"] == [
        "The official 9M26 release came out on 2026-10-30; the report uses 1H26."]


def test_a_passing_report_is_a_draft_until_an_analyst_approves_its_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("SECTORAL_AUTO_PUBLISH", "0")  # review-gated publication
    _report(tmp_path, "AAAA", reviewed=False)
    outputs.save(outputs.TRACE, tmp_path, "AAAA", {"forecast_assumptions": {"plan": PLAN}})
    item = gallery.load(tmp_path)[0]
    assert not item["published"] and item["rating"] is None and item["tp"] is None
    assert item["held_reason"] == "menunggu review publikasi oleh reviewer"
    assert item["review"]["state"] == "pending"
    assert item["publication_state"] == "review_pending" and item["analytically_eligible"]
    assert item["method"] == "" and item["headline"] == "" and item["chain"] == []
    assert item["blockers"] is None and not any(item["files"].values())
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


def test_a_passing_report_publishes_automatically_and_review_adds_the_badge(tmp_path):
    _report(tmp_path, "AAAA", reviewed=False)
    outputs.save(outputs.TRACE, tmp_path, "AAAA", {"forecast_assumptions": {"plan": PLAN}})
    item = gallery.load(tmp_path)[0]
    assert item["published"] and item["rating"] == "Hold"
    assert item["publication_state"] == "auto_published"
    assert item["publication_basis"] == "automatic" and item["review"]["state"] == "pending"
    approve(tmp_path, "AAAA")
    item = gallery.load(tmp_path)[0]
    assert item["publication_state"] == "published"
    assert item["publication_basis"] == "analyst_reviewed"


def test_a_draft_is_never_published_automatically(tmp_path):
    _report(tmp_path, "AAAA", reviewed=False)
    doc = outputs.load(outputs.REPORT, tmp_path, "AAAA")
    doc["meta"]["status"] = "draft_non_distributable"
    outputs.save(outputs.REPORT, tmp_path, "AAAA", doc)
    item = gallery.load(tmp_path)[0]
    assert not item["published"] and item["publication_basis"] is None


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


def test_every_chain_decision_cell_reads_back_to_its_code():
    from app import report_extras
    assert {cell: report_extras.decision_code(cell) for cell in report_extras._DECISION.values()} == {
        "Terpilih": "selected", "Terpilih, ekstrem (rantai berhenti)": "stop_extreme",
        "Dilewati": "skipped", "Silang cek": "cross_check", "Tidak dijalankan": "not_needed",
        "Belum tersedia": "unavailable"}
    assert report_extras.decision_code("lain") is None


def _render_covers(monkeypatch) -> list[str]:
    """Stub pdftoppm: each render writes the PDF's bytes as the PNG; returns the PDFs rendered."""
    rendered = []

    def render(command, **_kwargs):
        rendered.append(Path(command[-2]).name)
        Path(command[-1] + ".png").write_bytes(Path(command[-2]).read_bytes())

    monkeypatch.setattr(gallery.shutil, "which", lambda _name: "/usr/bin/pdftoppm")
    monkeypatch.setattr(gallery.subprocess, "run", render)
    return rendered


def test_an_approved_report_gets_its_cover_from_the_approved_pdf_hash(tmp_path, monkeypatch):
    rendered = _render_covers(monkeypatch)
    _report(tmp_path, "AAAA")
    record = assumption_review.record(tmp_path, "AAAA")
    png = gallery.cover(tmp_path, "AAAA")
    assert png.name == f"AAAA-{record['artifact_hashes']['pdf'][:16]}-cover.png"
    assert png.read_bytes() == b"%PDF-1.4 test"
    assert gallery.cover(tmp_path, "AAAA") == png and rendered == ["AAAA.pdf"]  # cached


def test_an_auto_published_report_gets_its_cover_from_the_run_manifest(tmp_path, monkeypatch):
    rendered = _render_covers(monkeypatch)
    _report(tmp_path, "AAAA", reviewed=False)
    assert gallery.load(tmp_path)[0]["publication_basis"] == "automatic"
    manifest = outputs.load(outputs.MANIFEST, tmp_path, "AAAA")
    png = gallery.cover(tmp_path, "AAAA")
    assert png.name == f"AAAA-{manifest['artifacts']['pdf']['sha256'][:16]}-cover.png"
    assert rendered == ["AAAA.pdf"]
    # Not published (review-gated, not approved): no cover.
    monkeypatch.setenv("SECTORAL_AUTO_PUBLISH", "0")
    assert gallery.cover(tmp_path, "AAAA") is None


def test_a_pdf_that_no_longer_matches_its_bundle_gets_no_cover(tmp_path, monkeypatch):
    rendered = _render_covers(monkeypatch)
    _report(tmp_path, "AAAA", reviewed=False)
    (tmp_path / "AAAA.pdf").write_bytes(b"%PDF-1.4 rebuilt after the run")
    assert gallery.cover(tmp_path, "AAAA") is None and rendered == []
    # A draft never has one, whatever PDF exists.
    _report(tmp_path, "BBBB", published=False)
    assert gallery.cover(tmp_path, "BBBB") is None and rendered == []


def test_an_english_reader_gets_the_english_pdf_cover_while_it_is_in_the_bundle(tmp_path, monkeypatch):
    rendered = _render_covers(monkeypatch)
    _report(tmp_path, "AAAA", reviewed=False, english=True)
    english = gallery.cover(tmp_path, "AAAA", "en")
    assert english.read_bytes() == b"%PDF-1.4 english" and rendered == ["AAAA.en.pdf"]
    assert gallery.cover(tmp_path, "AAAA", "id").read_bytes() == b"%PDF-1.4 test"
    assert gallery.cover(tmp_path, "AAAA", "fr") is None
    (tmp_path / "AAAA.en.pdf").write_bytes(b"%PDF-1.4 replaced")
    assert gallery.cover(tmp_path, "AAAA", "en") is None
    # A bundle without English has no English cover.
    _report(tmp_path, "BBBB")
    assert gallery.cover(tmp_path, "BBBB", "en") is None
    assert gallery.cover(tmp_path, "BBBB", "id") is not None


def test_a_price_date_that_is_not_a_date_is_left_out(tmp_path):
    _report(tmp_path, "AAAA")
    doc = outputs.load(outputs.REPORT, tmp_path, "AAAA")
    doc["meta"]["harga_tanggal"] = "24 Sep"
    assert gallery.summary(doc, tmp_path, "AAAA")["price_date"] is None
    del doc["meta"]["harga_tanggal"]
    assert gallery.summary(doc, tmp_path, "AAAA")["price_date"] is None
