"""Immutable, approved publication snapshots."""
import json
from pathlib import Path

from app import assumption_review, outputs, publication_archive, run_manifest
from test_assumption_review import _test_register


PLAN = {"earnings_scenario": {"year": 2026, "revenue_growth_pct": 8.0,
                              "rationale": "Panduan emiten."}}


def _attestation():
    source_id = _test_register()["rows"][0]["row_id"]
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
    return {
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


def _approved_bundle(folder: Path, db: Path, ticker="UJIA"):
    folder.mkdir(parents=True, exist_ok=True)
    evidence_register = _test_register(ticker)
    outputs.save(outputs.REPORT, folder, ticker,
                 {"meta": {"ticker": ticker,
                           "status": "distributable_assumption_led",
                           "tanggal": "2026-09-26",
                           "rating": "Buy", "tp": 1000},
                  "evidence_register": evidence_register}, db)
    outputs.save(outputs.TRACE, folder, ticker,
                 {"forecast_assumptions": {"plan": PLAN},
                  "evidence_register": evidence_register}, db)
    (folder / f"{ticker}.html").write_bytes(b"<html>company update</html>")
    (folder / f"{ticker}.pdf").write_bytes(b"%PDF-1.4 company update")
    (folder / f"{ticker}-trace.html").write_bytes(b"<html>audit trace</html>")
    base_manifest = {"ticker": ticker, "as_of": "2026-09-26",
                     "source_tree_sha256": "a" * 64,
                     "spec_sha256": "b" * 64,
                     "evidence_register_sha256": run_manifest.content_hash(evidence_register)}
    manifest = run_manifest.finalize_manifest(base_manifest, folder, ticker)
    outputs.save(outputs.MANIFEST, folder, ticker, manifest, db)
    outputs.save(outputs.EVENTS, folder, ticker,
                 [{"stage": "report", "label": "Rilis selesai"}], db)
    review = assumption_review.approve(
        folder, ticker, "Analis Satu", db=db, attestation=_attestation(),
        reviewer_identity={"id": "reviewer:analis-satu", "name": "Analis Satu",
                           "role": "reviewer", "source": "authenticated_registry"})
    return manifest, review


def test_archive_snapshots_approved_files_and_db_documents(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    manifest, review = _approved_bundle(folder, db)

    archived = publication_archive.archive_approved_bundle(folder, "ujia", db=db)

    assert archived is not None
    assert archived["publication_id"] == manifest["publication_id"]
    assert archived["review_sha"] == review["review_sha"]
    assert archived["archived_at"]
    assert set(archived["artifact_hashes"]) == {
        "html", "pdf", "trace_html", "report", "trace", "manifest", "events"}
    archive_dir = Path(archived["archive_dir"])
    assert (archive_dir / "UJIA.html").read_bytes() == (folder / "UJIA.html").read_bytes()
    assert json.loads((archive_dir / "UJIA-report.json").read_text()) == outputs.load(
        outputs.REPORT, folder, "UJIA", db)
    assert json.loads((archive_dir / "UJIA-trace.json").read_text()) == outputs.load(
        outputs.TRACE, folder, "UJIA", db)
    assert json.loads((archive_dir / "UJIA-manifest.json").read_text()) == outputs.load(
        outputs.MANIFEST, folder, "UJIA", db)
    assert json.loads((archive_dir / "UJIA-events.json").read_text()) == outputs.load(
        outputs.EVENTS, folder, "UJIA", db)

    assert publication_archive.list_archives(folder, "UJIA") == [
        {key: value for key, value in archived.items() if key != "archive_dir"}]
    archived_html = publication_archive.artifact(
        folder, "UJIA", manifest["publication_id"], "html")
    assert archived_html == archive_dir / "UJIA.html"
    assert archived_html.read_bytes() == b"<html>company update</html>"
    assert publication_archive.artifact(
        folder, "UJIA", manifest["publication_id"], "report") == archive_dir / "UJIA-report.json"


def test_archiving_requires_approved_state_and_all_final_hashes(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    _approved_bundle(folder, db)
    # The passed database contains approval; the default database does not.
    assert publication_archive.archive_approved_bundle(folder, "UJIA") is None

    (folder / "UJIA.pdf").write_bytes(b"changed after approval")
    assert publication_archive.archive_approved_bundle(folder, "UJIA", db=db) is None
    assert publication_archive.list_archives(folder, "UJIA") == []


def test_archive_is_idempotent_but_never_replaces_different_snapshot(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    manifest, _ = _approved_bundle(folder, db)
    first = publication_archive.archive_approved_bundle(folder, "UJIA", db=db)
    assert publication_archive.archive_approved_bundle(folder, "UJIA", db=db) == first

    archive_dir = Path(first["archive_dir"])
    original_events = (archive_dir / "UJIA-events.json").read_bytes()
    outputs.save(outputs.EVENTS, folder, "UJIA", [{"label": "changed"}], db)
    assert publication_archive.archive_approved_bundle(folder, "UJIA", db=db) is None
    assert (archive_dir / "UJIA-events.json").read_bytes() == original_events
    assert manifest["publication_id"] == archive_dir.name


def test_archive_artifact_refuses_corruption_and_unsafe_identifiers(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    manifest, _ = _approved_bundle(folder, db)
    archived = publication_archive.archive_approved_bundle(folder, "UJIA", db=db)
    archive_file = Path(archived["archive_dir"]) / "UJIA.pdf"
    archive_file.write_bytes(b"tampered")

    assert publication_archive.artifact(
        folder, "UJIA", manifest["publication_id"], "pdf") is None
    assert publication_archive.list_archives(folder, "UJIA") == []
    assert publication_archive.artifact(folder, "../UJIA", manifest["publication_id"], "pdf") is None
    assert publication_archive.artifact(folder, "UJIA", "../outside", "pdf") is None
    assert publication_archive.artifact(folder, "UJIA", manifest["publication_id"], "../pdf") is None


def test_archive_artifact_refuses_a_symlink_that_escapes_archive(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    manifest, _ = _approved_bundle(folder, db)
    archived = publication_archive.archive_approved_bundle(folder, "UJIA", db=db)
    archive_file = Path(archived["archive_dir"]) / "UJIA.pdf"
    escaped = tmp_path / "outside.pdf"
    escaped.write_bytes(b"outside archive")
    archive_file.unlink()
    archive_file.symlink_to(escaped)

    assert publication_archive.artifact(
        folder, "UJIA", manifest["publication_id"], "pdf") is None
    assert publication_archive.list_archives(folder, "UJIA") == []


def test_unapproved_report_is_not_archived(tmp_path):
    folder, db = tmp_path / "reports", tmp_path / "outputs.db"
    folder.mkdir()
    outputs.save(outputs.REPORT, folder, "UJIA",
                 {"meta": {"ticker": "UJIA", "status": "distributable_assumption_led",
                           "tanggal": "2026-09-26"}}, db)
    outputs.save(outputs.TRACE, folder, "UJIA",
                 {"forecast_assumptions": {"plan": PLAN}}, db)
    (folder / "UJIA.html").write_bytes(b"html")
    (folder / "UJIA.pdf").write_bytes(b"pdf")
    (folder / "UJIA-trace.html").write_bytes(b"trace html")

    assert publication_archive.archive_approved_bundle(folder, "UJIA", db=db) is None
    assert publication_archive.list_archives(folder, "UJIA") == []
