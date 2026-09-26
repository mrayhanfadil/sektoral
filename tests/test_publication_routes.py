"""Archived bundles have explicit, hash-verified public routes."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

pytest.importorskip("fastapi")

from app import assumption_review, outputs, publication_archive, server  # noqa: E402
from test_assumption_review import _attestation, _test_register  # noqa: E402
from test_gallery import PLAN, _report  # noqa: E402


def _endpoint(app, path, method="GET"):
    return next(route.endpoint for route in app.routes
                if getattr(route, "path", None) == path
                and method in getattr(route, "methods", set()))


def test_archived_publication_is_listed_and_served_with_its_identity(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA", reviewed=False)
    outputs.save(outputs.TRACE, reports, "AAAA", {
        "forecast_assumptions": {"plan": PLAN}, "evidence_register": _test_register("AAAA")})
    assumption_review.approve(
        reports, "AAAA", "A. Reviewer", attestation=_attestation(),
        reviewer_identity={"id": "reviewer-route", "name": "A. Reviewer",
                           "role": "reviewer", "source": "authenticated_registry"})
    archived = publication_archive.archive_approved_bundle(reports, "AAAA")
    assert archived is not None
    publication_id = archived["publication_id"]

    app = server.create_app(tmp_path / "jobs", reports, static_dir=None)
    response = _endpoint(app, "/api/reports/{ticker}/archives")("AAAA")
    payload = json.loads(response.body)
    assert payload["ticker"] == "AAAA"
    assert payload["items"] == [{
        # No supersession event was recorded, so the bundle is only archived.
        "state": "archived", "publication_state": "archived", "ticker": "AAAA",
        "publication_id": publication_id,
        "predecessor_publication_id": None, "successor_publication_id": None,
        "supersession_reason": None, "withdrawal_reason": None, "withdrawn_at": None,
        "archived_at": archived["archived_at"], "review_sha": archived["review_sha"],
        "artifact_hashes": {key: archived["artifact_hashes"].get(key)
                             for key in ("html", "pdf", "trace_html")},
        "files": {
            "html": f"/files/reports/AAAA/archives/{publication_id}/html",
            "pdf": f"/files/reports/AAAA/archives/{publication_id}/pdf",
            "trace": f"/files/reports/AAAA/archives/{publication_id}/trace",
        },
    }]

    file_response = _endpoint(
        app, "/files/reports/{ticker}/archives/{publication_id}/{kind}")(
            "AAAA", publication_id, "pdf")
    assert Path(file_response.path).read_bytes() == b"%PDF-1.4 test"
    assert file_response.headers["x-sektoral-artifact-state"] == "archived"
    assert file_response.headers["cache-control"].endswith("immutable")


def test_archive_route_rejects_unknown_or_tampered_bundle(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    app = server.create_app(tmp_path / "jobs", reports, static_dir=None)
    route = _endpoint(app, "/files/reports/{ticker}/archives/{publication_id}/{kind}")
    from fastapi import HTTPException

    for args in (("../AAAA", "a" * 64, "pdf"), ("AAAA", "../secret", "pdf"),
                 ("AAAA", "a" * 64, "json")):
        with pytest.raises(HTTPException) as error:
            route(*args)
        assert error.value.status_code == 404


def test_review_api_uses_token_identity_and_ignores_client_name(tmp_path, monkeypatch):
    reports = tmp_path / "reports"
    reports.mkdir()
    _report(reports, "AAAA", reviewed=False)
    outputs.save(outputs.TRACE, reports, "AAAA", {
        "forecast_assumptions": {"plan": PLAN}, "evidence_register": _test_register("AAAA")})
    reviewer_token = "reviewer-token-for-publication-test-0001"
    analyst_token = "analyst-token-for-publication-test-0001"
    monkeypatch.setenv("SECTORAL_REVIEWERS", json.dumps([
        {"id": "named-reviewer", "name": "Configured Reviewer", "role": "reviewer",
         "token_sha256": hashlib.sha256(reviewer_token.encode()).hexdigest()},
        {"id": "research-author", "name": "Research Author", "role": "analyst",
         "token_sha256": hashlib.sha256(analyst_token.encode()).hexdigest()},
    ]))
    app = server.create_app(tmp_path / "jobs", reports, static_dir=None)
    route = _endpoint(app, "/api/reports/{ticker}/review", "POST")
    body = server.ReviewRequest(
        reviewer="Client Spoof Name", note="Reviewed the frozen publication bundle.",
        attestation=_attestation())

    response = route("AAAA", body, reviewer_token)
    record = json.loads(response.body)["record"]
    assert record["reviewer"] == "Configured Reviewer"
    assert record["reviewer_id"] == "named-reviewer"
    assert record["reviewer_role"] == "reviewer"
    assert record["identity_source"] == "authenticated_registry"
    assert record["attestation"]["reviewer"] == "Configured Reviewer"

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        route("AAAA", body, analyst_token)
    assert error.value.status_code == 403
