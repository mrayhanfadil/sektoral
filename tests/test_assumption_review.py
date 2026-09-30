"""Analyst review of the Forecast Plan before publication (app.assumption_review)."""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import assumption_review as R, evidence, outputs, run_manifest  # noqa: E402

PLAN = {"earnings_scenario": {"year": 2026, "h2_revenue_to_h1": 1.1, "h2_net_margin_pct": 5.0,
                              "bank_drivers": {"year": 2026, "nim_pct": 7.5,
                                               "rationale": "NIM 1H26 resmi."},
                              "rationale": "Panduan emiten."},
        "outyear_scenario": [{"year": 2027, "revenue_growth_pct": 8.0, "ebitda_margin_pct": 20.0,
                              "rationale": "Rekam jejak."}],
        "news_effects": [{"article_index": 0, "change": 0}]}


def _test_register(ticker="UJIA"):
    return evidence.with_row_ids({
        "ticker": ticker,
        "as_of": "2026-09-24",
        "rows": [
            {"kind": "official_actual", "period": "1H26", "period_end": "2026-06-30",
             "published_at": "2026-08-01", "source": "https://issuer.example/results",
             "source_title": "Official 1H26 results", "value": {"revenue": 100}, "unit": "IDR"},
            {"kind": "company_guidance", "name": "FY26 production", "value": 200,
             "unit": "kt", "effective_years": [2026], "source": "https://issuer.example/guidance",
             "published_at": "2026-08-01", "scope": "all operations"},
            {"kind": "sectors_article", "title": "Industry context", "url": "https://news.example/story",
             "published_at": "2026-08-02"},
        ],
        "violations": [], "critical_violations": [],
    })


def _attestation(source_ids=None):
    source_ids = source_ids or [row["row_id"] for row in _test_register()["rows"]]
    checklist = {}
    for key in R.REVIEW_CHECKS:
        checklist[key] = {"status": "reviewed", "note": f"Reviewed {key} against the cited evidence.",
                          "source_ids": [source_ids[0]]}
    checklist["latest_official_actual_and_period"]["period"] = "1H26"
    checklist["top_three_value_sensitive_assumptions"]["items"] = [
        {"assumption_id": f"driver-{index}", "description": f"Material valuation driver {index}.",
         "value_sensitivity": f"A movement changes estimated value by scenario {index}.",
         "source_ids": [source_ids[0]]}
        for index in range(1, 4)
    ]
    checklist["consensus_comparison"] = {
        "status": "not_available", "note": "No independent consensus is available for this issuer.",
        "source_ids": [],
    }
    return {
        "schema_version": R.ATTESTATION_SCHEMA,
        "disposition": "approved",
        "reviewed_source_ids": source_ids,
        "checklist": checklist,
        "objections": [],
        "required_edits": [],
        "disclosures": {
            "author_role": "Research analyst",
            "reviewer_role": "Independent reviewing analyst",
            "issuer_relationship": {"status": "none", "details": "No issuer relationship declared."},
            "economic_or_ownership_conflicts": {
                "status": "none", "details": "No known economic or ownership conflicts declared."},
            "scope_limitations": "This is an issuer-level equity research update.",
            "rating_or_scenario_policy": "Rating follows the published upside policy.",
        },
        "overrides": [],
    }


def _reviewer_identity(name):
    return {"id": f"reviewer:{name.casefold().replace(' ', '-')}", "name": name,
            "role": "reviewer", "source": "authenticated_registry"}


def _approve(*args, **kwargs):
    reviewer = args[2] if len(args) > 2 else kwargs.get("reviewer")
    kwargs.setdefault("reviewer_identity", _reviewer_identity(reviewer))
    return R.approve(*args, **kwargs)


def _stored(folder, ticker="UJIA", status="distributable_assumption_led", english=False):
    evidence_register = _test_register(ticker)
    outputs.save(outputs.REPORT, folder, ticker, {"meta": {"ticker": ticker,
                                                            "tanggal": "2026-09-24",
                                                            "status": status,
                                                            "rating": "Buy", "tp": 1000},
                                                     "evidence_register": evidence_register})
    outputs.save(outputs.TRACE, folder, ticker, {"forecast_assumptions": {"plan": PLAN},
                                                  "evidence_register": evidence_register})
    Path(folder, f"{ticker}.html").write_text("<html>company update</html>")
    Path(folder, f"{ticker}.pdf").write_bytes(b"%PDF-1.4 company update")
    Path(folder, f"{ticker}-trace.html").write_text("<html>audit trace</html>")
    if english:
        Path(folder, f"{ticker}.en.html").write_text("<html lang='en'>company update</html>")
        Path(folder, f"{ticker}.en.pdf").write_bytes(b"%PDF-1.4 english company update")
    manifest = run_manifest.finalize_manifest({
        "ticker": ticker, "code_revision": "test", "source_tree_sha256": "a" * 64,
        "spec_sha256": "b" * 64,
        "evidence_register_sha256": run_manifest.content_hash(evidence_register),
        "as_of": "2026-09-24",
    }, folder, ticker)
    outputs.save(outputs.MANIFEST, folder, ticker, manifest)


def test_fields_list_only_the_numeric_drivers_with_labels():
    paths = {f["path"]: f for f in R.fields(PLAN)}
    assert set(paths) == {"earnings_scenario.h2_revenue_to_h1", "earnings_scenario.h2_net_margin_pct",
                          "earnings_scenario.bank_drivers.nim_pct",
                          "outyear_scenario[0].revenue_growth_pct",
                          "outyear_scenario[0].ebitda_margin_pct"}
    assert paths["earnings_scenario.bank_drivers.nim_pct"]["label"] == "NIM"
    assert paths["outyear_scenario[0].revenue_growth_pct"]["year"] == 2027


def test_fields_carry_english_labels_and_the_agents_english_rationale():
    plan = {**PLAN, "outyear_scenario": [{**PLAN["outyear_scenario"][0],
                                          "rationale_en": "Track record."}]}
    paths = {f["path"]: f for f in R.fields(plan)}
    growth = paths["outyear_scenario[0].revenue_growth_pct"]
    assert growth["label"] == "Pertumbuhan pendapatan" and growth["label_en"] == "Revenue growth"
    assert growth["rationale"] == "Rekam jejak." and growth["rationale_en"] == "Track record."
    # A plan written before the agent's English twins has none.
    nim = paths["earnings_scenario.bank_drivers.nim_pct"]
    assert nim["rationale"] == "NIM 1H26 resmi." and nim["rationale_en"] is None
    assert paths["earnings_scenario.h2_net_margin_pct"]["label_en"] == "H2 net profit margin"
    assert set(R.LABELS_EN) == set(R.LABELS)


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
    with pytest.raises(R.ReviewError, match="attestation wajib"):
        R.approve(tmp_path, "UJIA", "Analis Satu", "Driver sesuai rilis.")
    rec = _approve(tmp_path, "UJIA", "Analis Satu", "Driver sesuai rilis.",
                   attestation=_attestation())
    assert rec["decision"] == "approved" and rec["plan_sha"] == R.plan_sha(PLAN)
    verdict = {"status": "distributable_assumption_led", "rating": "Buy", "tp": 1000}
    assert rec["after"] == verdict and rec["before"] == {**verdict, "plan_sha": rec["plan_sha"]}
    assert R.status(tmp_path, "UJIA")["state"] == "approved"
    assert outputs.load(outputs.TRACE, tmp_path, "UJIA")["assumption_review"]["reviewer"] == "Analis Satu"
    assert set(rec["artifact_hashes"]) == {"html", "pdf", "trace_html"}
    assert rec["attestation"]["publication_fingerprint"]
    assert rec["attestation"]["reviewer"] == rec["reviewer"]
    assert rec["attestation"]["policy_version"] == R.REVIEW_POLICY_VERSION
    assert rec["reviewer_id"] == "reviewer:analis-satu"
    assert rec["reviewer_role"] == "reviewer"
    assert rec["identity_source"] == "authenticated_registry"
    assert rec["attestation"]["reviewer_id"] == rec["reviewer_id"]
    assert rec["attestation"]["reviewer_role"] == rec["reviewer_role"]


def test_complete_attestation_contract_requires_all_review_domains(tmp_path):
    good = _attestation()
    assert R.attestation_errors(good) == []
    assert R.attestation_schema()["properties"]["schema_version"]["const"] == R.ATTESTATION_SCHEMA

    missing_period = _attestation()
    del missing_period["checklist"]["latest_official_actual_and_period"]["period"]
    assert "latest_official_actual_period_required" in R.attestation_errors(missing_period)

    fewer_assumptions = _attestation()
    fewer_assumptions["checklist"]["top_three_value_sensitive_assumptions"]["items"].pop()
    assert "exactly_three_value_sensitive_assumptions_required" in R.attestation_errors(fewer_assumptions)

    unresolved = _attestation()
    unresolved["objections"] = [{"objection": "A source claim remains unresolved.",
                                  "response": "", "disposition": "open", "source_ids": []}]
    assert any("unresolved_blocks_distribution" in error for error in R.attestation_errors(unresolved))


def test_evidence_register_row_ids_are_stable_and_source_specific():
    first = _test_register()
    second = evidence.with_row_ids(first)
    assert [row["row_id"] for row in first["rows"]] == [row["row_id"] for row in second["rows"]]
    assert len({row["row_id"] for row in first["rows"]}) == len(first["rows"])
    changed = {**first, "rows": [{**first["rows"][0], "period": "FY26"}]}
    changed = evidence.with_row_ids(changed)
    assert first["rows"][0]["row_id"] != changed["rows"][0]["row_id"]


def test_unknown_conflict_declaration_blocks_public_distribution():
    attestation = _attestation()
    attestation["disclosures"]["issuer_relationship"] = {
        "status": "unknown", "details": "The issuer relationship has not been checked."}
    assert "disclosures.issuer_relationship_unknown_blocks_distribution" in (
        R.attestation_errors(attestation))


def test_self_asserted_cli_identity_is_auditable_but_cannot_approve_distribution(tmp_path):
    _stored(tmp_path)
    rec = R.approve(tmp_path, "UJIA", "Analis CLI", attestation=_attestation(),
                    reviewer_identity={"id": "cli:123", "name": "Analis CLI",
                                       "role": "reviewer", "source": "cli_self_asserted"})
    assert rec["identity_source"] == "cli_self_asserted"
    assert rec["attestation"]["reviewer_id"] == "cli:123"
    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert "authenticated_reviewer_required" in state["attestation_errors"]


def test_authenticated_review_requires_registry_role(tmp_path):
    _stored(tmp_path)
    with pytest.raises(R.ReviewError, match="role harus reviewer atau compliance"):
        R.approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation(),
                  reviewer_identity={"id": "author:1", "name": "Analis Satu",
                                     "role": "author", "source": "authenticated_registry"})


def test_reviewed_source_ids_must_exist_in_the_hashed_register(tmp_path):
    _stored(tmp_path)
    actual_id = _test_register()["rows"][0]["row_id"]
    attestation = _attestation([actual_id, "fabricated-source-id"])
    with pytest.raises(R.ReviewError, match="reviewed_source_ids_not_in_evidence_register"):
        _approve(tmp_path, "UJIA", "Analis Satu", attestation=attestation)
    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert state["record"] is None


@pytest.mark.parametrize("location", ["checklist", "top_three", "objection"])
def test_every_nested_source_reference_must_exist_in_the_hashed_register(tmp_path, location):
    _stored(tmp_path)
    valid_ids = [row["row_id"] for row in _test_register()["rows"]]
    forged = "fabricated-source-id"
    attestation = _attestation(valid_ids + [forged])
    if location == "checklist":
        attestation["checklist"]["material_source_claims_and_conflicts"]["source_ids"] = [forged]
    elif location == "top_three":
        attestation["checklist"]["top_three_value_sensitive_assumptions"]["items"][0]["source_ids"] = [forged]
    else:
        attestation["objections"] = [{"objection": "A source claim needs an explicit response.",
                                      "response": "The analyst addressed the cited conflict.",
                                      "disposition": "resolved", "source_ids": [forged]}]
    with pytest.raises(R.ReviewError, match="source_id_not_in_evidence_register"):
        _approve(tmp_path, "UJIA", "Analis Satu", attestation=attestation)
    assert R.status(tmp_path, "UJIA")["state"] == "pending"


@pytest.mark.parametrize("missing_from", ["report", "trace", "manifest_hash"])
def test_missing_or_unbound_evidence_register_keeps_review_pending(tmp_path, missing_from):
    _stored(tmp_path)
    if missing_from in {"report", "trace"}:
        category = outputs.REPORT if missing_from == "report" else outputs.TRACE
        doc = outputs.load(category, tmp_path, "UJIA")
        doc.pop("evidence_register", None)
        outputs.save(category, tmp_path, "UJIA", doc)
    else:
        manifest = outputs.load(outputs.MANIFEST, tmp_path, "UJIA")
        manifest["evidence_register_sha256"] = "f" * 64
        outputs.save(outputs.MANIFEST, tmp_path, "UJIA", manifest)

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert "evidence_register" in state["missing_artifacts"]
    assert state["evidence_register_errors"]
    with pytest.raises(R.ReviewError, match="Evidence Register|manifest wajib"):
        _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())


def test_reviewer_preview_lists_only_source_ids_from_the_verified_register(tmp_path):
    _stored(tmp_path)
    view = R.public(tmp_path, "UJIA")
    expected = {row["row_id"] for row in _test_register()["rows"]}
    assert {row["id"] for row in view["available_source_ids"]} == expected

    trace = outputs.load(outputs.TRACE, tmp_path, "UJIA")
    trace["evidence_register"]["rows"][0]["row_id"] = "forged-row-id"
    outputs.save(outputs.TRACE, tmp_path, "UJIA", trace)
    view = R.public(tmp_path, "UJIA")
    assert view["available_source_ids"] == []
    assert "report and trace Evidence Registers do not match" in view["evidence_register_errors"]


def test_register_with_fabricated_row_id_fails_even_if_manifest_hash_is_recomputed(tmp_path):
    _stored(tmp_path)
    report = outputs.load(outputs.REPORT, tmp_path, "UJIA")
    trace = outputs.load(outputs.TRACE, tmp_path, "UJIA")
    register = report["evidence_register"]
    register["rows"][0]["row_id"] = "evidence:official_actual:made-up"
    report["evidence_register"] = register
    trace["evidence_register"] = register
    outputs.save(outputs.REPORT, tmp_path, "UJIA", report)
    outputs.save(outputs.TRACE, tmp_path, "UJIA", trace)
    manifest = outputs.load(outputs.MANIFEST, tmp_path, "UJIA")
    manifest["evidence_register_sha256"] = run_manifest.content_hash(register)
    manifest = run_manifest.finalize_manifest(manifest, tmp_path, "UJIA")
    outputs.save(outputs.MANIFEST, tmp_path, "UJIA", manifest)

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert any("row_id is not canonical" in item for item in state["evidence_register_errors"])
    with pytest.raises(R.ReviewError, match="row_id is not canonical"):
        _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())


def test_review_fingerprint_binds_the_attestation_to_the_frozen_bundle(tmp_path):
    _stored(tmp_path)
    record = _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())
    attestation = record["attestation"]
    expected = attestation["publication_fingerprint"]
    assert R.attestation_errors(attestation, expected_fingerprint=expected) == []
    assert "publication_fingerprint_mismatch" in R.attestation_errors(
        attestation, expected_fingerprint="0" * 64)
    altered = dict(attestation, disposition="rejected")
    assert R.review_sha(PLAN, outputs.load(outputs.REPORT, tmp_path, "UJIA"),
                        record["artifact_hashes"], record["trace_sha"],
                        record["publication_id"], attestation=altered) != record["review_sha"]


@pytest.mark.parametrize("artifact", ["UJIA.html", "UJIA.pdf", "UJIA-trace.html"])
def test_changed_rendered_artifact_makes_approval_stale(tmp_path, artifact):
    _stored(tmp_path)
    _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())

    path = tmp_path / artifact
    path.write_bytes(path.read_bytes() + b" changed")

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert state["stale_record"] is not None


def test_english_beside_a_bundle_finalized_without_it_leaves_the_approval_unchanged(tmp_path):
    _stored(tmp_path)
    record = _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())
    (tmp_path / "UJIA.en.html").write_text("<html lang='en'>written later</html>")
    (tmp_path / "UJIA.en.pdf").write_bytes(b"%PDF-1.4 written later")

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "approved" and state["review_sha"] == record["review_sha"]
    assert set(state["artifact_hashes"]) == {"html", "pdf", "trace_html"}
    assert state["manifest_errors"] == []


def test_an_approval_covers_the_english_edition_its_manifest_lists(tmp_path):
    _stored(tmp_path, english=True)
    manifest = outputs.load(outputs.MANIFEST, tmp_path, "UJIA")
    assert set(manifest["artifacts"]) == {"html", "pdf", "trace_html", "html_en", "pdf_en"}
    record = _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())
    assert record["artifact_hashes"]["html_en"] == manifest["artifacts"]["html_en"]["sha256"]
    assert record["artifact_hashes"]["pdf_en"] == manifest["artifacts"]["pdf_en"]["sha256"]
    assert R.status(tmp_path, "UJIA")["state"] == "approved"


@pytest.mark.parametrize("kind,artifact", [("html_en", "UJIA.en.html"),
                                           ("pdf_en", "UJIA.en.pdf")])
def test_changed_or_removed_english_edition_makes_approval_stale(tmp_path, kind, artifact):
    _stored(tmp_path, english=True)
    _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())
    path = tmp_path / artifact
    path.write_bytes(path.read_bytes() + b" changed")

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending" and state["stale_record"] is not None
    assert (f"publication manifest {kind} hash does not match current artifact"
            in state["manifest_errors"])
    with pytest.raises(R.ReviewError, match="manifest wajib belum valid"):
        _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())

    path.unlink()
    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending" and kind not in state["artifact_hashes"]


def test_publishable_report_cannot_be_approved_without_required_artifacts(tmp_path):
    _stored(tmp_path)
    (tmp_path / "UJIA.pdf").unlink()

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert "pdf" in state["missing_artifacts"]
    assert "publication_manifest" in state["missing_artifacts"]
    with pytest.raises(R.ReviewError, match="artefak laporan"):
        R.approve(tmp_path, "UJIA", "Analis Satu")


def test_publishable_report_requires_matching_final_publication_manifest(tmp_path):
    _stored(tmp_path)
    manifest = outputs.load(outputs.MANIFEST, tmp_path, "UJIA")
    manifest["publication_id"] = "0" * 64
    outputs.save(outputs.MANIFEST, tmp_path, "UJIA", manifest)

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert "publication_manifest" in state["missing_artifacts"]
    assert state["manifest_errors"]
    with pytest.raises(R.ReviewError, match="manifest wajib belum valid"):
        R.approve(tmp_path, "UJIA", "Analis Satu")


def test_changed_release_policy_invalidates_current_publication(tmp_path):
    _stored(tmp_path)
    manifest = outputs.load(outputs.MANIFEST, tmp_path, "UJIA")
    manifest["release_policy"]["policy"]["version"] = "0.9.0"
    manifest["release_policy"]["sha256"] = run_manifest.content_hash(
        manifest["release_policy"]["policy"])
    finalized = run_manifest.finalize_manifest(manifest, tmp_path, "UJIA")
    outputs.save(outputs.MANIFEST, tmp_path, "UJIA", finalized)

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert any("release policy is stale" in error for error in state["manifest_errors"])


def test_stored_review_record_does_not_recurse_but_changed_trace_stales_it(tmp_path):
    _stored(tmp_path)
    _approve(tmp_path, "UJIA", "Analis Satu", attestation=_attestation())

    # approve() writes its record into the stored trace after computing the
    # fingerprint; excluding that field keeps the freshly saved record valid.
    assert R.status(tmp_path, "UJIA")["state"] == "approved"
    trace = outputs.load(outputs.TRACE, tmp_path, "UJIA")
    trace["new_source_note"] = "A source was added after review."
    outputs.save(outputs.TRACE, tmp_path, "UJIA", trace)

    state = R.status(tmp_path, "UJIA")
    assert state["state"] == "pending"
    assert state["stale_record"] is not None


def test_nonpublishable_test_flow_can_approve_without_rendered_artifacts(tmp_path):
    _stored(tmp_path, status="draft_non_distributable")
    for suffix in (".html", ".pdf", "-trace.html"):
        (tmp_path / f"UJIA{suffix}").unlink()

    record = R.approve(tmp_path, "UJIA", "Analis Satu")

    assert record["artifact_hashes"] == {}
    assert R.status(tmp_path, "UJIA")["state"] == "approved"


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
    rec = _approve(tmp_path, "UJIA", "Analis Dua", edits=[
        {"path": "earnings_scenario.bank_drivers.nim_pct", "value": 7.2,
         "reason": "NIM H2 turun mengikuti suku bunga acuan."}], rebuild_fn=rebuild)
    assert calls and calls[0]["plan_override"]["earnings_scenario"]["bank_drivers"]["nim_pct"] == 7.2
    assert rec["decision"] == "edits_rebuilt_pending_review"
    assert rec["edits"] == [{"path": "earnings_scenario.bank_drivers.nim_pct", "label": "NIM",
                             "year": 2026, "unit": "%", "from": 7.5, "to": 7.2,
                             "reason": "NIM H2 turun mengikuti suku bunga acuan."}]
    assert rec["after"]["tp"] == 900 and rec["before"]["tp"] == 1000
    assert R.status(tmp_path, "UJIA")["state"] == "pending"


def test_review_endpoints_need_the_reviewer_token(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app import server
    reports = tmp_path / "reports"
    reports.mkdir()
    _stored(reports)
    monkeypatch.delenv("SECTORAL_REVIEWERS", raising=False)
    body = {"reviewer": "Analis Tiga", "note": "ok", "edits": []}
    with TestClient(server.create_app(tmp_path / "out", reports)) as client:
        view = client.get("/api/reports/UJIA/review").json()
        assert view["state"] == "pending" and not view["enabled"]
        # Without a reviewer token the editable Forecast Plan values stay private.
        assert "fields" not in view
        assert client.post("/api/reports/UJIA/review", json=body).status_code == 403
        token = "reviewer-token-" + "x" * 32
        monkeypatch.setenv("SECTORAL_REVIEWERS", json.dumps([{
            "id": "reviewer-1", "name": "Analis Tiga", "role": "reviewer",
            "token_sha256": hashlib.sha256(token.encode()).hexdigest()}]))
        reviewer_view = client.get("/api/reports/UJIA/review",
                                   headers={"X-Review-Token": token}).json()
        assert any(f["path"] == "earnings_scenario.bank_drivers.nim_pct"
                   for f in reviewer_view["fields"])
        assert client.post("/api/reports/UJIA/review", json=body,
                           headers={"X-Review-Token": "salah"}).status_code == 403
        bad = client.post("/api/reports/UJIA/review", headers={"X-Review-Token": token},
                          json={**body, "edits": [{"path": "news_effects[0].change", "value": 1,
                                                   "reason": "alasan cukup panjang"}]})
        assert bad.status_code == 400 and "tidak dapat diedit" in bad.json()["detail"]
        ok = client.post("/api/reports/UJIA/review", json=body, headers={"X-Review-Token": token})
        assert ok.status_code == 400 and "attestation wajib" in ok.json()["detail"]
        assert R.status(reports, "UJIA")["state"] == "pending"
        assert client.get("/api/reports/NONE/review").status_code == 404


def test_a_reapproval_keeps_the_earlier_record_and_its_edits(tmp_path):
    _stored(tmp_path)

    def rebuild(t, source, out, **kw):
        trace = outputs.load(outputs.TRACE, out, t)
        trace["forecast_assumptions"] = {"plan": kw["plan_override"], "agent_plan_raw": kw["plan_override"]}
        outputs.save(outputs.TRACE, out, t, trace)
    first = _approve(tmp_path, "UJIA", "Analis Dua", edits=[
        {"path": "outyear_scenario[0].ebitda_margin_pct", "value": 18.0,
         "reason": "Margin memudar ke rata-rata siklus."}], rebuild_fn=rebuild)
    assert first["decision"] == "edits_rebuilt_pending_review"
    second = _approve(tmp_path, "UJIA", "Analis Tiga", "Setuju ulang.",
                      attestation=_attestation())
    assert second["edits"] == [] and second["plan_sha"] == first["plan_sha"]
    assert [h["reviewer"] for h in second["history"]] == ["Analis Dua"]
    assert "history" not in second["history"][0]
    view = R.public(tmp_path, "UJIA")
    assert view["reviewer"] == "Analis Tiga"
    assert [(e["path"], e["reviewer"]) for e in view["edits"]] == [
        ("outyear_scenario[0].ebitda_margin_pct", "Analis Dua")]
    assert view["history"][0]["edits"] == 1
    third = _approve(tmp_path, "UJIA", "Analis Empat", attestation=_attestation())
    assert [h["reviewer"] for h in third["history"]] == ["Analis Tiga", "Analis Dua"]


def test_plan_without_report_is_pending_and_keeps_its_plan_fingerprint(tmp_path):
    outputs.save(outputs.TRACE, tmp_path, "UJIA",
                 {"forecast_assumptions": {"plan": PLAN}})

    state = R.status(tmp_path, "UJIA")

    assert state["state"] == "pending"
    assert state["plan_sha"] == R.plan_sha(PLAN)
    assert state["review_sha"] is None


def test_the_attestation_draft_is_written_from_the_report_and_leaves_conflicts_to_the_reviewer(tmp_path):
    _stored(tmp_path)
    draft = R.attestation_draft(tmp_path, "UJIA")
    assert set(draft["checklist"]) == set(R.REVIEW_CHECKS)
    actual = draft["checklist"]["latest_official_actual_and_period"]
    assert actual["period"] == "1H26" and "terbit 2026-08-01" in actual["note"]
    # The reviewer's own declarations are never pre-asserted.
    assert "issuer_relationship" not in draft["disclosures"]
    assert "economic_or_ownership_conflicts" not in draft["disclosures"]
    attestation = {"schema_version": R.ATTESTATION_SCHEMA, "disposition": "approved",
                   "checklist": draft["checklist"], "objections": [], "required_edits": [],
                   "overrides": [],
                   "reviewed_source_ids": sorted({i for c in draft["checklist"].values()
                                                  for i in c["source_ids"]}),
                   "disclosures": {**draft["disclosures"], "reviewer_role": "reviewer"}}
    errors = R.attestation_errors(attestation)
    assert errors and all("issuer_relationship" in e or "economic_or_ownership" in e
                          or "top_three" in e or "exactly_three" in e for e in errors)
    assert R.attestation_draft(tmp_path, "NONE") is None
