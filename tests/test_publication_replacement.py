"""Replacement paths preserve approved runs and discard stale rendered files."""
from pathlib import Path

import pytest

from app import (assumption_review, build, jobs, outputs, publication_archive,
                 rebuild, run_manifest)
from test_assumption_review import _test_register


PLAN = {"earnings_scenario": {"year": 2026, "revenue_growth_pct": 8.0,
                              "rationale": "Panduan emiten."}}


def _approved_bundle(folder: Path, ticker: str, english=False):
    folder.mkdir(parents=True, exist_ok=True)
    evidence_register = _test_register(ticker)
    report = {"meta": {"ticker": ticker, "status": "distributable_assumption_led",
                       "tanggal": "2026-09-26", "rating": "Buy", "tp": 1000},
              "method": "DCF contoh", "exhibits": [], "evidence_register": evidence_register}
    trace = {"forecast_assumptions": {"plan": PLAN},
             "report": {"as_of": "2026-09-26"}, "evidence_register": evidence_register}
    outputs.save(outputs.REPORT, folder, ticker, report)
    outputs.save(outputs.TRACE, folder, ticker, trace)
    (folder / f"{ticker}.html").write_bytes(b"old approved html")
    (folder / f"{ticker}.pdf").write_bytes(b"old approved pdf")
    (folder / f"{ticker}-trace.html").write_bytes(b"old approved trace")
    if english:
        (folder / f"{ticker}.en.html").write_bytes(b"old approved english html")
        (folder / f"{ticker}.en.pdf").write_bytes(b"old approved english pdf")
    manifest = run_manifest.finalize_manifest({
        "ticker": ticker, "as_of": "2026-09-26", "source_tree_sha256": "a" * 64,
        "spec_sha256": "b" * 64,
        "evidence_register_sha256": run_manifest.content_hash(evidence_register),
    }, folder, ticker)
    outputs.save(outputs.MANIFEST, folder, ticker, manifest)
    source_id = evidence_register["rows"][0]["row_id"]
    checklist = {
        key: {"status": "reviewed", "note": f"Reviewed {label.lower()} against the source pack.",
              "source_ids": [source_id]}
        for key, label in assumption_review.REVIEW_CHECKS.items()
    }
    checklist["latest_official_actual_and_period"]["period"] = "1H26"
    checklist["top_three_value_sensitive_assumptions"]["items"] = [
        {"assumption_id": f"driver_{index}", "description": f"Material forecast driver {index}.",
         "value_sensitivity": f"A change in driver {index} changes the equity value.",
         "source_ids": [source_id]}
        for index in range(1, 4)
    ]
    checklist["consensus_comparison"]["status"] = "not_available"
    attestation = {
        "schema_version": assumption_review.ATTESTATION_SCHEMA,
        "disposition": "approved", "reviewed_source_ids": [source_id],
        "checklist": checklist, "objections": [], "required_edits": [], "overrides": [],
        "disclosures": {
            "author_role": "Research analyst.", "reviewer_role": "Independent reviewer.",
            "issuer_relationship": {"status": "none", "details": "No issuer relationship identified."},
            "economic_or_ownership_conflicts": {
                "status": "none", "details": "No economic or ownership conflicts identified."},
            "scope_limitations": "Review is limited to the supplied source and model pack.",
            "rating_or_scenario_policy": "Rating reflects the approved base case.",
        },
    }
    review = assumption_review.approve(
        folder, ticker, "Analis Satu", attestation=attestation,
        reviewer_identity={"id": "reviewer:analis-satu", "name": "Analis Satu",
                           "role": "reviewer", "source": "authenticated_registry"})
    return manifest, review


def test_jobs_publish_archives_approved_bundle_and_removes_missing_pdf(tmp_path):
    reports, job_out = tmp_path / "reports", tmp_path / "job"
    ticker = "UJIA"
    prior, _ = _approved_bundle(reports, ticker)
    job_out.mkdir()
    (job_out / f"{ticker}.html").write_bytes(b"new html")
    (job_out / f"{ticker}-trace.html").write_bytes(b"new trace")
    outputs.save(outputs.REPORT, job_out, ticker,
                 {"meta": {"ticker": ticker, "status": "draft_non_distributable",
                           "tanggal": "2026-09-27"}})
    outputs.save(outputs.TRACE, job_out, ticker,
                 {"forecast_assumptions": {"plan": PLAN}})
    manifest = run_manifest.finalize_manifest({"ticker": ticker, "as_of": "2026-09-27"},
                                              job_out, ticker)
    outputs.save(outputs.MANIFEST, job_out, ticker, manifest)

    registry = jobs.ResearchJobs(tmp_path / "jobs", reports=reports)
    try:
        registry._publish(job_out, ticker)
    finally:
        registry.close()

    old_pdf = publication_archive.artifact(
        reports, ticker, prior["publication_id"], "pdf")
    assert old_pdf is not None and old_pdf.read_bytes() == b"old approved pdf"
    assert (reports / f"{ticker}.html").read_bytes() == b"new html"
    assert (reports / f"{ticker}-trace.html").read_bytes() == b"new trace"
    assert not (reports / f"{ticker}.pdf").exists()
    assert outputs.load(outputs.REPORT, reports, ticker)["meta"]["status"] == \
        "draft_non_distributable"


def test_jobs_publish_archives_the_english_edition_and_drops_it_when_the_run_has_none(tmp_path):
    reports, job_out = tmp_path / "reports", tmp_path / "job"
    ticker = "UJIA"
    prior, _ = _approved_bundle(reports, ticker, english=True)
    job_out.mkdir()
    (job_out / f"{ticker}.html").write_bytes(b"new html")
    (job_out / f"{ticker}-trace.html").write_bytes(b"new trace")
    outputs.save(outputs.REPORT, job_out, ticker,
                 {"meta": {"ticker": ticker, "status": "draft_non_distributable",
                           "tanggal": "2026-09-27"}})

    registry = jobs.ResearchJobs(tmp_path / "jobs", reports=reports)
    try:
        registry._publish(job_out, ticker)
    finally:
        registry.close()

    for kind, content in (("html_en", b"old approved english html"),
                          ("pdf_en", b"old approved english pdf")):
        archived = publication_archive.artifact(reports, ticker, prior["publication_id"], kind)
        assert archived is not None and archived.read_bytes() == content
    assert not (reports / f"{ticker}.en.html").exists()
    assert not (reports / f"{ticker}.en.pdf").exists()


def test_jobs_refuses_completion_when_approved_bundle_cannot_be_archived(tmp_path, monkeypatch):
    reports, job_out = tmp_path / "reports", tmp_path / "job"
    ticker = "UJIA"
    _approved_bundle(reports, ticker)
    job_out.mkdir()
    (job_out / f"{ticker}.html").write_bytes(b"replacement")
    monkeypatch.setattr(publication_archive, "archive_approved_bundle", lambda *_a, **_k: None)

    registry = jobs.ResearchJobs(tmp_path / "jobs", reports=reports)
    try:
        with pytest.raises(OSError, match="refusing to replace approved"):
            registry._publish(job_out, ticker)
    finally:
        registry.close()

    assert (reports / f"{ticker}.html").read_bytes() == b"old approved html"


def test_rebuild_archives_approved_destination_and_clears_old_pdf(tmp_path, monkeypatch):
    ticker = "UJIA"
    source, out = tmp_path / "source", tmp_path / "out"
    _approved_bundle(source, ticker)
    prior, _ = _approved_bundle(out, ticker, english=True)

    def fake_build(symbol, folder, want_pdf=False, **_kwargs):
        doc = {"meta": {"ticker": symbol, "status": "draft_non_distributable",
                        "tanggal": "2026-09-27"},
               "run_manifest": {"ticker": symbol, "as_of": "2026-09-27"},
               "exhibits": [], "method": "DCF rebuilt"}
        outputs.save(outputs.REPORT, folder, symbol, doc)
        (folder / f"{symbol}.html").write_text("new rebuilt html")
        return doc

    monkeypatch.setattr(build, "build", fake_build)
    monkeypatch.setattr(rebuild, "_build_once",
                        lambda ticker, out, kwargs, pins: (fake_build(ticker, out, **kwargs),
                                                            [], "", {}, {}))
    # Let the normal trace renderer run over the stored input trace.
    result = rebuild.rebuild_one(ticker, source, out)

    archived_html = publication_archive.artifact(
        out, ticker, prior["publication_id"], "html")
    assert archived_html is not None and archived_html.read_bytes() == b"old approved html"
    archived_pdf = publication_archive.artifact(
        out, ticker, prior["publication_id"], "pdf")
    assert archived_pdf is not None and archived_pdf.read_bytes() == b"old approved pdf"
    assert result["ticker"] == ticker
    assert (out / f"{ticker}.html").read_text() == "new rebuilt html"
    assert not (out / f"{ticker}.pdf").exists()
    assert (out / f"{ticker}-trace.html").read_text() != "old approved trace"
    assert "pdf" in outputs.load(outputs.MANIFEST, out, ticker)["missing_artifacts"]
    # The old English edition is archived, not carried into the rebuilt bundle.
    archived_en = publication_archive.artifact(out, ticker, prior["publication_id"], "html_en")
    assert archived_en is not None and archived_en.read_bytes() == b"old approved english html"
    assert not (out / f"{ticker}.en.html").exists() and not (out / f"{ticker}.en.pdf").exists()
    assert not {"html_en", "pdf_en"} & set(outputs.load(outputs.MANIFEST, out, ticker)["artifacts"])


def test_direct_build_archives_approved_bundle_and_removes_stale_files(tmp_path):
    ticker = "AMMN"
    prior, _ = _approved_bundle(tmp_path, ticker, english=True)

    build.build(ticker, tmp_path, as_of="2026-09-24")

    archived = publication_archive.artifact(
        tmp_path, ticker, prior["publication_id"], "pdf")
    assert archived is not None and archived.read_bytes() == b"old approved pdf"
    assert not (tmp_path / f"{ticker}.pdf").exists()
    assert not (tmp_path / f"{ticker}-trace.html").exists()
    manifest = outputs.load(outputs.MANIFEST, tmp_path, ticker)
    assert {"pdf", "trace_html"}.issubset(set(manifest["missing_artifacts"]))
    archived_en = publication_archive.artifact(tmp_path, ticker, prior["publication_id"], "pdf_en")
    assert archived_en is not None and archived_en.read_bytes() == b"old approved english pdf"
    assert not (tmp_path / f"{ticker}.en.pdf").exists()
    # The fresh English HTML is this run's, and its manifest lists it.
    assert (tmp_path / f"{ticker}.en.html").read_bytes() != b"old approved english html"
    assert manifest["artifacts"]["html_en"]["sha256"] == run_manifest.file_sha256(
        tmp_path / f"{ticker}.en.html")
