"""Analyst review of the Forecast Plan before a report is published (plan Phase 4).

The Forecast Assumption Agent writes the plan a report is built on. A report
is a draft until an analyst approves that plan: as written, or with edits to
its numeric drivers, each edit carrying the analyst's reason (the same
discipline as ``data/method_overrides``). The approval is recorded in the app
database under the report's folder and ticker (``app.outputs`` keys) and in
the report's Audit Trace (``assumption_review``); it names the reviewer and
role, identity source, time, substantive checklist, bundle fingerprint and
every change. A distributable report requires a complete attestation from an
authenticated reviewer or compliance identity.

An approval is tied to the Forecast Plan and the published result fingerprint
(``review_sha``), including report status, model scenario label, per-share
value, rendered HTML/PDF/trace content (and the English HTML/PDF when the run
manifest lists them, ADR 0015), and the stored trace. A new run or a changed
artifact needs a fresh analyst review.
Edits rebuild the report offline on the edited plan (``app.rebuild``, no agent
call) and return the new bundle to review-pending; a separate attested review
is required for distribution.

    python -m app.assumption_review status --folder out/reports [TICKERS...]
    python -m app.assumption_review approve --folder out/reports --reviewer "Nama" \\
        --note "Driver sesuai rilis 1H" --attestation review.json BBCA
    python -m app.assumption_review approve --folder out/reports --reviewer "Nama" \\
        --edit "earnings_scenario.bank_drivers.nim_pct=5.4:NIM 1H26 resmi" BBCA

Distributable reports require ``--attestation``. The JSON contract is exposed
by :func:`attestation_schema`; older callers may omit it, but their approval
request is refused and the report remains pending.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import evidence as evidence_mod, outputs, run_manifest, store

COLLECTION = "assumption_reviews"
# Plan sections an analyst may edit, and the reader label of each field.
SECTIONS = ("interim_scenario", "earnings_scenario", "outyear_scenario", "bank_outyear_scenario")
LABELS = {
    "h2_revenue_to_h1": ("Pendapatan H2 / H1", "x"),
    "h2_ebitda_margin_pct": ("Margin EBITDA H2", "%"),
    "h2_net_margin_pct": ("Margin laba bersih H2", "%"),
    "h2_capex_to_h1": ("Capex H2 / H1", "x"),
    "fy_ebitda_margin_pct": ("Margin EBITDA FY", "%"),
    "fy_capex_to_revenue_pct": ("Capex / pendapatan FY", "%"),
    "revenue_growth_pct": ("Pertumbuhan pendapatan", "%"),
    "ebitda_margin_pct": ("Margin EBITDA", "%"),
    "net_income_margin_pct": ("Margin laba bersih", "%"),
    "capex_to_revenue_pct": ("Capex / pendapatan", "%"),
    "loan_growth_pct": ("Pertumbuhan kredit", "%"),
    "nim_pct": ("NIM", "%"),
    "non_ii_to_nii_pct": ("Pendapatan non-bunga / NII", "%"),
    "cost_to_income_pct": ("Rasio biaya / pendapatan", "%"),
    "cost_of_credit_pct": ("Biaya kredit", "%"),
    "deposit_growth_pct": ("Pertumbuhan DPK", "%"),
}
# A reviewer's value outside these bounds is a typo, not a view.
BOUNDS = {"%": (-100.0, 300.0), "x": (0.0, 10.0)}
PATH = re.compile(r"^(?P<section>[a-z_]+)(?:\[(?P<index>\d+)\])?(?:\.(?P<sub>[a-z_]+))?"
                  r"\.(?P<field>[a-z0-9_]+)$")
ARTIFACTS = run_manifest.REQUIRED_ARTIFACTS
REQUIRED_PUBLISH_ARTIFACTS = tuple(ARTIFACTS)
ATTESTATION_SCHEMA = "sektoral.institutional-review.v1"
REVIEW_POLICY_VERSION = "institutional-review-2026-09-26.v1"
REVIEW_CHECKS = {
    "latest_official_actual_and_period": "Latest official actual and period",
    "material_source_claims_and_conflicts": "Material source claims and conflicting evidence",
    "top_three_value_sensitive_assumptions": "Three largest value-sensitive assumptions",
    "interim_statement_reconciliation": "Interim and statement reconciliation",
    "model_profile_and_method_chain": "Model Profile and Method Chain",
    "scenario_consistency": "Base, downside and upside consistency",
    "catalyst_and_thesis_change_tests": "Catalysts and thesis-change tests",
    "consensus_comparison": "Independent consensus comparison",
    "limitations_conflicts": "Limitations and conflicts",
    "earnings_normalization": "Earnings normalization",
    "restatements_corporate_actions": "Restatements and corporate actions",
    "house_assumptions_terminal_economics": "House assumptions and terminal economics",
    "independent_validation": "Independent validation results",
    "business_quality": "Business quality",
    "liquidity_limitations": "Liquidity and investability limitations",
}
_CHECK_STATUSES = {"reviewed", "not_available", "not_applicable"}
_REQUIRED_REVIEWER_DISCLOSURES = (
    "author_role", "reviewer_role", "issuer_relationship",
    "economic_or_ownership_conflicts", "scope_limitations", "rating_or_scenario_policy",
)


class ReviewError(ValueError):
    """A review the host refuses: unknown field, bad value, missing reason."""


def plan_sha(plan) -> str | None:
    if not isinstance(plan, dict):
        return None
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def review_sha(plan, report, artifact_hashes=None, trace_sha=None,
               publication_id=None, *, attestation=None) -> str | None:
    """Fingerprint the frozen bundle, and optionally its substantive review."""
    sha = plan_sha(plan)
    if sha is None or not isinstance(report, dict):
        return None
    payload = {"plan_sha": sha, "published_result": _verdict(report),
               "artifacts": artifact_hashes or {}, "trace_sha": trace_sha,
               "publication_id": publication_id}
    bundle_sha = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                           default=str).encode()).hexdigest()
    if attestation is None:
        return bundle_sha
    return hashlib.sha256(json.dumps({"bundle_fingerprint": bundle_sha,
                                      "attestation": attestation},
                                     sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def _clean_text(value, *, minimum=8, maximum=1200):
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:maximum] if len(text) >= minimum else None


def _source_ids(value):
    if not isinstance(value, list) or len(value) > 100:
        return None
    ids = []
    for source_id in value:
        if not isinstance(source_id, str) or not source_id.strip() or len(source_id.strip()) > 240:
            return None
        if source_id.strip() not in ids:
            ids.append(source_id.strip())
    return ids


def attestation_schema() -> dict:
    """JSON Schema contract returned to reviewer-only API clients and UIs."""
    source_ids = {"type": "array", "minItems": 1, "maxItems": 100, "uniqueItems": True,
                  "items": {"type": "string", "minLength": 1, "maxLength": 240}}
    empty_source_ids = {**source_ids, "minItems": 0}
    check_properties = {
        "status": {"type": "string", "enum": sorted(_CHECK_STATUSES)},
        "note": {"type": "string", "minLength": 8, "maxLength": 1200},
        "source_ids": empty_source_ids,
    }
    checklist_properties = {}
    for key, label in REVIEW_CHECKS.items():
        properties = dict(check_properties)
        required = ["status", "note", "source_ids"]
        if key == "latest_official_actual_and_period":
            properties["status"] = {"type": "string", "const": "reviewed"}
            properties["period"] = {"type": "string", "minLength": 2, "maxLength": 80}
            required.append("period")
        if key == "top_three_value_sensitive_assumptions":
            properties["status"] = {"type": "string", "const": "reviewed"}
            properties["items"] = {
                "type": "array", "minItems": 3, "maxItems": 3,
                "items": {"type": "object", "required": ["assumption_id", "description",
                                                               "value_sensitivity", "source_ids"],
                          "properties": {
                              "assumption_id": {"type": "string", "minLength": 2, "maxLength": 160},
                              "description": {"type": "string", "minLength": 8, "maxLength": 800},
                              "value_sensitivity": {"type": "string", "minLength": 8, "maxLength": 800},
                              "source_ids": source_ids,
                          }, "additionalProperties": False},
            }
            required.append("items")
        if key == "consensus_comparison":
            properties["status"] = {"type": "string", "enum": ["reviewed", "not_available"]}
        checklist_properties[key] = {
            "type": "object", "title": label, "required": required,
            "properties": properties, "additionalProperties": False,
        }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["schema_version", "disposition", "reviewed_source_ids", "checklist",
                     "objections", "required_edits", "disclosures", "overrides"],
        "properties": {
            "schema_version": {"const": ATTESTATION_SCHEMA},
            "disposition": {"const": "approved"},
            "reviewed_source_ids": source_ids,
            "checklist": {"type": "object", "required": list(REVIEW_CHECKS),
                          "properties": checklist_properties, "additionalProperties": False},
            "objections": {"type": "array", "items": {
                "type": "object", "required": ["objection", "response", "disposition", "source_ids"],
                "properties": {"objection": {"type": "string", "minLength": 8, "maxLength": 1200},
                               "response": {"type": "string", "minLength": 8, "maxLength": 1200},
                               "disposition": {"type": "string", "enum": ["resolved", "accepted"]},
                               "source_ids": empty_source_ids},
                "additionalProperties": False}},
            "required_edits": {"type": "array", "items": {
                "type": "object", "required": ["description", "status"],
                "properties": {"description": {"type": "string", "minLength": 8, "maxLength": 1200},
                               "status": {"type": "string", "const": "completed"}},
                "additionalProperties": False}},
            "disclosures": {
                "type": "object", "required": list(_REQUIRED_REVIEWER_DISCLOSURES),
                "properties": {
                    "author_role": {"type": "string", "minLength": 3, "maxLength": 1000},
                    "reviewer_role": {"type": "string", "minLength": 3, "maxLength": 1000,
                                      "description": "Replaced with the authenticated registry role"},
                    "issuer_relationship": {"type": "object", "required": ["status", "details"],
                        "properties": {"status": {"type": "string", "enum": ["none", "disclosed", "unknown"]},
                                       "details": {"type": "string", "minLength": 3, "maxLength": 1000}},
                        "additionalProperties": False},
                    "economic_or_ownership_conflicts": {"type": "object", "required": ["status", "details"],
                        "properties": {"status": {"type": "string", "enum": ["none", "disclosed", "unknown"]},
                                       "details": {"type": "string", "minLength": 3, "maxLength": 1000}},
                        "additionalProperties": False},
                    "scope_limitations": {"type": "string", "minLength": 3, "maxLength": 1000},
                    "rating_or_scenario_policy": {"type": "string", "minLength": 3, "maxLength": 1000},
                }, "additionalProperties": False},
            "overrides": {"type": "array", "items": {
                "type": "object", "required": ["description", "justification", "policy_version"],
                "properties": {key: {"type": "string", "minLength": 3, "maxLength": 800}
                               for key in ("description", "justification", "policy_version")},
                "additionalProperties": False}},
        },
        "additionalProperties": False,
        "x-system-recorded": ["reviewer", "reviewer_id", "reviewer_role", "identity_source",
                               "reviewed_at", "policy_version", "publication_fingerprint"],
    }


def _resolve_reviewer_identity(reviewer, attestation, identity, *, distributable):
    """Resolve caller-supplied identity; authenticated values come from the server."""
    if identity is not None:
        if not isinstance(identity, dict):
            raise ReviewError("reviewer_identity harus berupa objek identitas terverifikasi")
        reviewer_id = _clean_text(identity.get("id"), minimum=2, maximum=160)
        name = _clean_text(identity.get("name"), minimum=2, maximum=120)
        role = _clean_text(identity.get("role"), minimum=2, maximum=120)
        source = _clean_text(identity.get("source") or "authenticated_registry",
                             minimum=2, maximum=80)
        if not all((reviewer_id, name, role, source)):
            raise ReviewError("reviewer_identity wajib memuat id, name, role, dan source")
        if source not in {"authenticated_registry", "cli_self_asserted", "caller_self_asserted"}:
            raise ReviewError("reviewer_identity.source tidak dikenali")
        if source == "authenticated_registry" and role.casefold() not in {"reviewer", "compliance"}:
            raise ReviewError("reviewer_identity.role harus reviewer atau compliance")
        return {"reviewer_id": reviewer_id, "reviewer": name, "reviewer_role": role,
                "identity_source": source}
    if not distributable:
        return {"reviewer_id": None, "reviewer": reviewer,
                "reviewer_role": None, "identity_source": "legacy_caller"}
    disclosures = (attestation or {}).get("disclosures") if isinstance(attestation, dict) else {}
    role = _clean_text((disclosures or {}).get("reviewer_role"), minimum=2, maximum=120)
    identity_id = hashlib.sha256(reviewer.casefold().encode()).hexdigest()[:16]
    return {"reviewer_id": f"self-asserted:{identity_id}", "reviewer": reviewer,
            "reviewer_role": role, "identity_source": "caller_self_asserted"}


def attestation_errors(value, *, expected_fingerprint=None,
                       available_source_ids=None) -> list[str]:
    """Validate a complete institutional checklist without mutating its input."""
    if not isinstance(value, dict):
        return ["attestation_missing_or_not_an_object"]
    errors = []
    if value.get("schema_version") != ATTESTATION_SCHEMA:
        errors.append("schema_version_invalid")
    if value.get("disposition") != "approved":
        errors.append("disposition_must_be_approved")
    reviewed_ids = _source_ids(value.get("reviewed_source_ids"))
    if not reviewed_ids:
        errors.append("reviewed_source_ids_required")
    known_source_ids = set(available_source_ids or [])
    if available_source_ids is not None and reviewed_ids is not None:
        unknown = sorted(set(reviewed_ids) - known_source_ids)
        if unknown:
            errors.append("reviewed_source_ids_not_in_evidence_register")
    checklist = value.get("checklist")
    if not isinstance(checklist, dict):
        errors.append("checklist_required")
        checklist = {}
    for key, label in REVIEW_CHECKS.items():
        item = checklist.get(key)
        if not isinstance(item, dict):
            errors.append(f"checklist.{key}_required")
            continue
        status_value = item.get("status")
        if status_value not in _CHECK_STATUSES:
            errors.append(f"checklist.{key}.status_invalid")
        note = _clean_text(item.get("note"))
        if note is None:
            errors.append(f"checklist.{key}.note_required")
        source_ids = _source_ids(item.get("source_ids", []))
        if source_ids is None:
            errors.append(f"checklist.{key}.source_ids_invalid")
        elif reviewed_ids is not None and not set(source_ids).issubset(reviewed_ids):
            errors.append(f"checklist.{key}.source_id_not_in_reviewed_source_ids")
        if source_ids is not None and available_source_ids is not None and not set(source_ids).issubset(known_source_ids):
            errors.append(f"checklist.{key}.source_id_not_in_evidence_register")
        if key == "latest_official_actual_and_period":
            if status_value != "reviewed":
                errors.append("latest_official_actual_must_be_reviewed")
            if _clean_text(item.get("period"), minimum=2, maximum=80) is None:
                errors.append("latest_official_actual_period_required")
            if source_ids == []:
                errors.append("latest_official_actual_source_id_required")
        if key == "material_source_claims_and_conflicts" and source_ids == []:
            errors.append("material_source_claim_source_id_required")
        if key == "interim_statement_reconciliation" and source_ids == []:
            errors.append("interim_reconciliation_source_id_required")
        if key == "consensus_comparison" and status_value not in {"reviewed", "not_available"}:
            errors.append("consensus_must_be_compared_or_marked_unavailable")
        if key == "top_three_value_sensitive_assumptions":
            if status_value != "reviewed":
                errors.append("top_three_assumptions_must_be_reviewed")
            entries = item.get("items")
            if not isinstance(entries, list) or len(entries) != 3:
                errors.append("exactly_three_value_sensitive_assumptions_required")
            else:
                names = []
                for index, entry in enumerate(entries):
                    if not isinstance(entry, dict):
                        errors.append(f"top_three.items.{index}_invalid")
                        continue
                    assumption_id = _clean_text(entry.get("assumption_id"), minimum=2, maximum=160)
                    description = _clean_text(entry.get("description"), minimum=8, maximum=800)
                    sensitivity = _clean_text(entry.get("value_sensitivity"), minimum=8, maximum=800)
                    entry_ids = _source_ids(entry.get("source_ids", []))
                    if assumption_id is None:
                        errors.append(f"top_three.items.{index}.assumption_id_required")
                    elif assumption_id in names:
                        errors.append("top_three_assumption_ids_must_be_unique")
                    else:
                        names.append(assumption_id)
                    if description is None:
                        errors.append(f"top_three.items.{index}.description_required")
                    if sensitivity is None:
                        errors.append(f"top_three.items.{index}.value_sensitivity_required")
                    if entry_ids is None:
                        errors.append(f"top_three.items.{index}.source_ids_invalid")
                    elif reviewed_ids is not None and not set(entry_ids).issubset(reviewed_ids):
                        errors.append(f"top_three.items.{index}.source_id_not_in_reviewed_source_ids")
                    if (entry_ids is not None and available_source_ids is not None
                            and not set(entry_ids).issubset(known_source_ids)):
                        errors.append(f"top_three.items.{index}.source_id_not_in_evidence_register")
                    if entry_ids == []:
                        errors.append(f"top_three.items.{index}.source_id_required")
    if isinstance(checklist, dict):
        for key in checklist:
            if key not in REVIEW_CHECKS:
                errors.append(f"checklist.{key}_unknown")
    disclosures = value.get("disclosures")
    if not isinstance(disclosures, dict):
        errors.append("disclosures_required")
    else:
        for key in _REQUIRED_REVIEWER_DISCLOSURES:
            declaration = disclosures.get(key)
            if key in {"issuer_relationship", "economic_or_ownership_conflicts"}:
                if not isinstance(declaration, dict):
                    errors.append(f"disclosures.{key}_required")
                    continue
                if declaration.get("status") not in {"none", "disclosed", "unknown"}:
                    errors.append(f"disclosures.{key}_status_invalid")
                if _clean_text(declaration.get("details"), minimum=3, maximum=1000) is None:
                    errors.append(f"disclosures.{key}_details_required")
                details = str(declaration.get("details") or "").casefold()
                unknown_markers = ("unknown", "not known", "belum diketahui", "tidak diketahui")
                if (declaration.get("status") == "unknown"
                        or any(marker in details for marker in unknown_markers)):
                    errors.append(f"disclosures.{key}_unknown_blocks_distribution")
            elif _clean_text(declaration, minimum=3, maximum=1000) is None:
                errors.append(f"disclosures.{key}_required")
    for collection, required_fields, allowed_statuses in (
        ("objections", ("objection", "response"), {"resolved", "accepted"}),
        ("required_edits", ("description",), {"completed"}),
    ):
        if collection not in value:
            errors.append(f"{collection}_required")
            continue
        rows = value.get(collection)
        if not isinstance(rows, list):
            errors.append(f"{collection}_must_be_a_list")
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"{collection}.{index}_invalid")
                continue
            for field in required_fields:
                if _clean_text(row.get(field), minimum=8, maximum=1200) is None:
                    errors.append(f"{collection}.{index}.{field}_required")
            status_field = "disposition" if collection == "objections" else "status"
            if row.get(status_field) not in allowed_statuses:
                errors.append(f"{collection}.{index}_unresolved_blocks_distribution")
            ids = _source_ids(row.get("source_ids", []))
            if ids is None:
                errors.append(f"{collection}.{index}.source_ids_invalid")
            elif reviewed_ids is not None and not set(ids).issubset(reviewed_ids):
                errors.append(f"{collection}.{index}.source_id_not_in_reviewed_source_ids")
            if ids is not None and available_source_ids is not None and not set(ids).issubset(known_source_ids):
                errors.append(f"{collection}.{index}.source_id_not_in_evidence_register")
    if "overrides" not in value:
        errors.append("overrides_required")
    overrides = value.get("overrides")
    if not isinstance(overrides, list):
        errors.append("overrides_must_be_a_list")
    else:
        for index, override in enumerate(overrides):
            if not isinstance(override, dict):
                errors.append(f"overrides.{index}_invalid")
                continue
            for field in ("description", "justification", "policy_version"):
                if _clean_text(override.get(field), minimum=3, maximum=800) is None:
                    errors.append(f"overrides.{index}.{field}_required")
    if "publication_fingerprint" in value:
        if (not isinstance(value.get("publication_fingerprint"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", value["publication_fingerprint"])):
            errors.append("publication_fingerprint_invalid")
        elif expected_fingerprint is not None and value["publication_fingerprint"] != expected_fingerprint:
            errors.append("publication_fingerprint_mismatch")
    elif expected_fingerprint is not None:
        errors.append("publication_fingerprint_missing")
    if "reviewer" in value and _clean_text(value.get("reviewer"), minimum=2, maximum=120) is None:
        errors.append("reviewer_invalid")
    if "reviewed_at" in value and _clean_text(value.get("reviewed_at"), minimum=10, maximum=80) is None:
        errors.append("reviewed_at_invalid")
    if "policy_version" in value and value.get("policy_version") != REVIEW_POLICY_VERSION:
        errors.append("policy_version_mismatch")
    for key, minimum, maximum in (("reviewer_id", 2, 160), ("reviewer_role", 2, 120),
                                  ("identity_source", 2, 80)):
        if key in value and _clean_text(value.get(key), minimum=minimum, maximum=maximum) is None:
            errors.append(f"{key}_invalid")
    if expected_fingerprint is not None:
        for key in ("reviewer", "reviewer_id", "reviewer_role", "identity_source",
                    "reviewed_at", "policy_version"):
            if key not in value:
                errors.append(f"{key}_missing")
        if value.get("identity_source") not in {
                "authenticated_registry", "cli_self_asserted", "caller_self_asserted"}:
            errors.append("identity_source_invalid")
    return errors


def _freeze_attestation(value, *, reviewer_identity, reviewed_at, bundle_fingerprint) -> dict:
    """Attach system-controlled identity, time, policy, and bundle binding."""
    frozen = copy.deepcopy(value)
    frozen.setdefault("disclosures", {})["reviewer_role"] = reviewer_identity["reviewer_role"]
    frozen.update({"reviewer": reviewer_identity["reviewer"],
                   "reviewer_id": reviewer_identity["reviewer_id"],
                   "reviewer_role": reviewer_identity["reviewer_role"],
                   "identity_source": reviewer_identity["identity_source"],
                   "reviewed_at": reviewed_at,
                   "policy_version": REVIEW_POLICY_VERSION,
                   "publication_fingerprint": bundle_fingerprint})
    return frozen


def _is_publishable(report) -> bool:
    if not isinstance(report, dict):
        return False
    meta = report.get("meta") or {}
    if not isinstance(meta, dict):
        return False
    return str(meta.get("status") or "").startswith("distributable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_hashes(folder, ticker, manifest=None) -> tuple[dict[str, str], list[str]]:
    """Hash rendered files in this report folder; reject symlinks escaping it.

    The English edition is hashed only when the run manifest lists it (ADR
    0015): a bundle finalized without it keeps the fingerprint it was
    approved with, whatever English file sits beside it."""
    root = Path(folder).resolve()
    hashes = {}
    missing = []
    for name in run_manifest.bundle_kinds(manifest):
        pattern = run_manifest.ARTIFACT_FILES[name]
        candidate = root / pattern.format(ticker=str(ticker).upper())
        try:
            path = candidate.resolve()
            if path.parent != root or not path.is_file():
                missing.append(name)
                continue
            hashes[name] = _sha256_file(path)
        except (OSError, RuntimeError):
            missing.append(name)
    return hashes, missing


def _evidence_register_state(report, trace, manifest) -> tuple[dict | None, list[str], list[str]]:
    """Require one canonical register in report and trace, bound by the manifest."""
    report_register = report.get("evidence_register") if isinstance(report, dict) else None
    trace_register = trace.get("evidence_register") if isinstance(trace, dict) else None
    errors = []
    if not isinstance(report_register, dict):
        errors.append("report Evidence Register is missing or invalid")
    if not isinstance(trace_register, dict):
        errors.append("trace Evidence Register is missing or invalid")
    if errors:
        return None, [], errors
    report_hash = run_manifest.content_hash(report_register)
    trace_hash = run_manifest.content_hash(trace_register)
    manifest_hash = manifest.get("evidence_register_sha256") if isinstance(manifest, dict) else None
    if report_hash == "unhashable" or not run_manifest.re_full_sha(report_hash):
        errors.append("report Evidence Register cannot be hashed")
    if trace_hash == "unhashable" or not run_manifest.re_full_sha(trace_hash):
        errors.append("trace Evidence Register cannot be hashed")
    if not run_manifest.re_full_sha(manifest_hash):
        errors.append("publication manifest Evidence Register hash is missing or invalid")
    if report_hash != trace_hash:
        errors.append("report and trace Evidence Registers do not match")
    if report_hash != manifest_hash:
        errors.append("Evidence Register hash does not match publication manifest")
    rows = report_register.get("rows")
    if not isinstance(rows, list) or not rows:
        errors.append("Evidence Register rows are missing or empty")
        rows = []
    try:
        canonical_register = evidence_mod.with_row_ids(report_register)
        canonical_rows = canonical_register.get("rows") or []
    except Exception:
        canonical_rows = []
        errors.append("Evidence Register row IDs cannot be recomputed")
    ids = []
    for index, row in enumerate(rows):
        row_id = row.get("row_id") if isinstance(row, dict) else None
        if not isinstance(row_id, str) or not row_id.strip():
            errors.append(f"Evidence Register row {index} has no stable row_id")
            continue
        row_id = row_id.strip()
        if row_id in ids:
            errors.append(f"Evidence Register row_id is duplicated: {row_id}")
            continue
        ids.append(row_id)
        if index >= len(canonical_rows) or not isinstance(canonical_rows[index], dict) or \
                row_id != canonical_rows[index].get("row_id"):
            errors.append(f"Evidence Register row {index} row_id is not canonical")
    return report_register, ids, list(dict.fromkeys(errors))


def _evidence_source_options(register) -> list[dict]:
    """Safe reviewer labels paired with IDs from the validated register."""
    rows = register.get("rows") if isinstance(register, dict) else []
    options = []
    for row in rows or []:
        if not isinstance(row, dict) or not isinstance(row.get("row_id"), str):
            continue
        label = row.get("source_title") or row.get("title") or row.get("name") or row.get("driver")
        options.append({"id": row["row_id"], "kind": row.get("kind"),
                        "label": str(label or row.get("kind") or row["row_id"])[:200],
                        "period": row.get("period") or row.get("effective_years") or row.get("fiscal_years"),
                        "source": row.get("source") or row.get("url")})
    return options


def _trace_sha(trace) -> str | None:
    """Hash stored trace content without its embedded review record.

    The review record itself contains this hash. Excluding the top-level field
    that stores it keeps the fingerprint stable after approval is written back
    into the trace.
    """
    if not isinstance(trace, dict):
        return None
    content = copy.deepcopy(trace)
    content.pop("assumption_review", None)
    return hashlib.sha256(json.dumps(content, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def report_plan(trace) -> dict | None:
    """The plan the report was built on, as ``app.rebuild.build_inputs`` reads it."""
    fa = (trace or {}).get("forecast_assumptions")
    if not isinstance(fa, dict):
        return None
    plan = fa["agent_plan_raw"] if "agent_plan_raw" in fa else fa.get("plan")
    return plan if isinstance(plan, dict) else None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def fields(plan) -> list[dict]:
    """Every editable numeric driver: path, label, unit, year, value, rationale."""
    out = []

    def add(path, row, key, year, rationale):
        value = _number(row.get(key))
        if value is None or key not in LABELS:
            return
        label, unit = LABELS[key]
        out.append({"path": path, "field": key, "label": label, "unit": unit, "year": year,
                    "value": value, "rationale": rationale})

    for section in SECTIONS:
        block = (plan or {}).get(section)
        rows = block if isinstance(block, list) else [block] if isinstance(block, dict) else []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            base = f"{section}[{i}]" if isinstance(block, list) else section
            year = row.get("year")
            rationale = str(row.get("rationale") or "")[:600]
            for key in row:
                add(f"{base}.{key}", row, key, year, rationale)
            drivers = row.get("bank_drivers")
            if isinstance(drivers, dict):
                for key in drivers:
                    add(f"{base}.bank_drivers.{key}", drivers, key, drivers.get("year"),
                        str(drivers.get("rationale") or rationale)[:600])
    return out


def _key(folder, ticker):
    return outputs.key(folder, str(ticker).upper())


def record(folder, ticker, db=None) -> dict | None:
    data = store.get(COLLECTION, _key(folder, ticker), db)
    return data if isinstance(data, dict) else None


def status(folder, ticker, db=None) -> dict:
    """Review state, keyed to both plan and published value/rating."""
    trace = outputs.load(outputs.TRACE, folder, ticker, db)
    plan = report_plan(trace)
    sha = plan_sha(plan)
    doc = outputs.load(outputs.REPORT, folder, ticker, db)
    publication_manifest = outputs.load(outputs.MANIFEST, folder, ticker, db)
    artifact_hashes, missing = _artifact_hashes(folder, ticker, publication_manifest)
    manifest_errors = (run_manifest.publication_manifest_errors(
        publication_manifest, ticker, ((doc.get("meta") or {}).get("tanggal")
                                       if isinstance(doc, dict) else None), artifact_hashes)
        if _is_publishable(doc) else [])
    required_missing = (sorted(set(REQUIRED_PUBLISH_ARTIFACTS) & set(missing))
                        if _is_publishable(doc) else [])
    if manifest_errors:
        required_missing.append("publication_manifest")
    evidence_register, available_source_ids, evidence_register_errors = (
        _evidence_register_state(doc, trace, publication_manifest)
        if _is_publishable(doc) else (None, [], []))
    if evidence_register_errors:
        required_missing.append("evidence_register")
    trace_fingerprint = _trace_sha(trace)
    bundle_fingerprint = (None if required_missing else
                          review_sha(plan, doc, artifact_hashes, trace_fingerprint,
                                     publication_manifest.get("publication_id")
                                     if isinstance(publication_manifest, dict) else None))
    rec = record(folder, ticker, db)
    if sha is None:
        return {"state": "no_plan", "plan_sha": None, "record": None,
                "artifact_hashes": artifact_hashes,
                "missing_artifacts": required_missing,
                "manifest_errors": manifest_errors,
                "evidence_register_errors": evidence_register_errors}
    attestation_failures = []
    if _is_publishable(doc):
        attestation = rec.get("attestation") if isinstance(rec, dict) else None
        attestation_failures = attestation_errors(
            attestation, expected_fingerprint=bundle_fingerprint,
            available_source_ids=available_source_ids) if bundle_fingerprint else (
                ["frozen_publication_bundle_invalid"])
        if isinstance(attestation, dict):
            if attestation.get("reviewer") != rec.get("reviewer"):
                attestation_failures.append("reviewer_record_mismatch")
            for field in ("reviewer_id", "reviewer_role", "identity_source"):
                if attestation.get(field) != rec.get(field):
                    attestation_failures.append(f"{field}_record_mismatch")
            if attestation.get("reviewed_at") != rec.get("reviewed_at"):
                attestation_failures.append("review_time_record_mismatch")
        if not isinstance(rec, dict) or rec.get("identity_source") != "authenticated_registry":
            attestation_failures.append("authenticated_reviewer_required")
        elif str(rec.get("reviewer_role") or "").casefold() not in {"reviewer", "compliance"}:
            attestation_failures.append("reviewer_role_not_authorized")
        fingerprint = (review_sha(plan, doc, artifact_hashes, trace_fingerprint,
                                  publication_manifest.get("publication_id")
                                  if isinstance(publication_manifest, dict) else None,
                                  attestation=attestation)
                      if bundle_fingerprint and not attestation_failures else None)
    else:
        fingerprint = bundle_fingerprint
    if fingerprint is None:
        return {"state": "pending", "plan_sha": sha, "review_sha": None,
                "record": None, "stale_record": rec,
                "artifact_hashes": artifact_hashes,
                "missing_artifacts": required_missing,
                "manifest_errors": manifest_errors,
                "evidence_register_errors": evidence_register_errors,
                "attestation_errors": attestation_failures}
    approved = bool(rec and rec.get("review_sha") == fingerprint)
    return {"state": "approved" if approved else "pending", "plan_sha": sha,
            "review_sha": fingerprint,
            "record": rec if approved else None,
            "stale_record": rec if rec and not approved else None,
            "artifact_hashes": artifact_hashes,
            "missing_artifacts": required_missing,
            "manifest_errors": manifest_errors,
            "evidence_register_errors": evidence_register_errors,
            "attestation_errors": attestation_failures}


def apply_edits(plan, edits) -> tuple[dict, list[dict]]:
    """(edited plan, change log). Each edit: {"path", "value", "reason"}."""
    edited = copy.deepcopy(plan)
    known = {f["path"]: f for f in fields(plan)}
    changes = []
    for edit in edits or []:
        path = str((edit or {}).get("path") or "")
        reason = str((edit or {}).get("reason") or "").strip()
        field = known.get(path)
        if field is None:
            raise ReviewError(f"field {path!r} tidak dapat diedit")
        try:
            value = float(edit.get("value"))
        except (TypeError, ValueError):
            raise ReviewError(f"{path}: nilai harus angka") from None
        low, high = BOUNDS[field["unit"]]
        if not low <= value <= high:
            raise ReviewError(f"{path}: {value:g} di luar rentang {low:g}..{high:g}")
        if len(reason) < 10:
            raise ReviewError(f"{path}: alasan perubahan wajib diisi (minimal 10 karakter)")
        if value == field["value"]:
            continue
        match = PATH.match(path)
        node = edited[match["section"]]
        if match["index"] is not None:
            node = node[int(match["index"])]
        if match["sub"]:
            node = node[match["sub"]]
        node[match["field"]] = value
        changes.append({"path": path, "label": field["label"], "year": field["year"],
                        "unit": field["unit"], "from": field["value"], "to": value,
                        "reason": reason[:600]})
    return edited, changes


def approve(folder, ticker, reviewer, note="", edits=None, *, db=None, want_pdf=None,
            rebuild_fn=None, attestation=None, reviewer_identity=None) -> dict:
    """Approve a frozen report after a complete attestation.

    Returns the stored record. Raises ReviewError on a missing reviewer, a
    report without a stored plan, a bad edit, or a missing/incomplete
    institutional attestation for a distributable report. Existing callers
    may omit ``attestation``; that keeps distributable reports pending.
    """
    t = str(ticker).upper()
    reviewer = str(reviewer or "").strip()
    if len(reviewer) < 2 and reviewer_identity is None:
        raise ReviewError("nama reviewer wajib diisi")
    trace = outputs.load(outputs.TRACE, folder, t, db)
    doc = outputs.load(outputs.REPORT, folder, t, db)
    plan = report_plan(trace)
    if plan is None or not isinstance(doc, dict):
        raise ReviewError(f"{t}: laporan atau Forecast Plan tersimpan tidak ditemukan")
    identity = _resolve_reviewer_identity(reviewer, attestation, reviewer_identity,
                                          distributable=_is_publishable(doc))
    reviewer = identity["reviewer"]
    if len(reviewer) < 2:
        raise ReviewError("nama reviewer wajib diisi")
    publication_manifest = outputs.load(outputs.MANIFEST, folder, t, db)
    artifact_hashes, missing = _artifact_hashes(folder, t, publication_manifest)
    manifest_errors = (run_manifest.publication_manifest_errors(
        publication_manifest, t, (doc.get("meta") or {}).get("tanggal"), artifact_hashes)
        if _is_publishable(doc) else [])
    required_missing = (sorted(set(REQUIRED_PUBLISH_ARTIFACTS) & set(missing))
                        if _is_publishable(doc) else [])
    if manifest_errors:
        required_missing.append("publication_manifest")
    if required_missing:
        raise ReviewError(f"{t}: artefak laporan atau manifest wajib belum valid: "
                          f"{', '.join(required_missing)}")
    edited, changes = apply_edits(plan, edits)
    evidence_register, available_source_ids, evidence_register_errors = (
        _evidence_register_state(doc, trace, publication_manifest)
        if _is_publishable(doc) else (None, [], []))
    if _is_publishable(doc) and evidence_register_errors and not changes:
        raise ReviewError(f"{t}: Evidence Register belum valid: "
                          f"{'; '.join(evidence_register_errors)}; distribusi tetap pending")
    before = {"plan_sha": plan_sha(plan), **_verdict(doc)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec = {"ticker": t, "reviewer": reviewer[:120], "reviewed_at": now,
           "reviewer_id": identity["reviewer_id"],
           "reviewer_role": identity["reviewer_role"],
           "identity_source": identity["identity_source"],
           "note": str(note or "").strip()[:1000],
           "decision": "edits_rebuilt_pending_review" if changes else "approved",
           "edits": changes, "before": before}
    if changes:
        if rebuild_fn is None:
            from .rebuild import rebuild_one as rebuild_fn
        folder_path = Path(folder)
        pdf = want_pdf if want_pdf is not None else (folder_path / f"{t}.pdf").is_file()
        rebuild_fn(t, folder_path, folder_path, want_pdf=pdf, db=db, plan_override=edited,
                   trace_extra={"assumption_review": {**rec, "plan_sha": plan_sha(edited)}})
        doc = outputs.load(outputs.REPORT, folder, t, db)
        trace = outputs.load(outputs.TRACE, folder, t, db)
        rec["plan_sha"] = plan_sha(report_plan(trace))
        rec["after"] = _verdict(doc)
        rec["review_sha"] = None
        rec["attestation"] = None
        rec["history"] = history(record(folder, t, db))
        store.put(COLLECTION, _key(folder, t), rec, db)
        trace = dict(trace or {})
        trace["assumption_review"] = rec
        outputs.save(outputs.TRACE, folder, t, trace, db)
        return rec
    rec["plan_sha"] = plan_sha(report_plan(trace))
    publication_manifest = outputs.load(outputs.MANIFEST, folder, t, db)
    artifact_hashes, missing = _artifact_hashes(folder, t, publication_manifest)
    manifest_errors = (run_manifest.publication_manifest_errors(
        publication_manifest, t, (doc.get("meta") or {}).get("tanggal"), artifact_hashes)
        if _is_publishable(doc) else [])
    required_missing = (sorted(set(REQUIRED_PUBLISH_ARTIFACTS) & set(missing))
                        if _is_publishable(doc) else [])
    if manifest_errors:
        required_missing.append("publication_manifest")
    if required_missing:
        raise ReviewError(f"{t}: artefak laporan atau manifest belum valid setelah rebuild: "
                          f"{', '.join(required_missing)}")
    evidence_register, available_source_ids, evidence_register_errors = (
        _evidence_register_state(doc, trace, publication_manifest)
        if _is_publishable(doc) else (None, [], []))
    if _is_publishable(doc) and evidence_register_errors:
        raise ReviewError(f"{t}: Evidence Register belum valid: "
                          f"{'; '.join(evidence_register_errors)}; distribusi tetap pending")
    rec["artifact_hashes"] = artifact_hashes
    rec["trace_sha"] = _trace_sha(trace)
    publication_id = (publication_manifest.get("publication_id")
                      if isinstance(publication_manifest, dict) else None)
    bundle_fingerprint = review_sha(report_plan(trace), doc, artifact_hashes,
                                    rec["trace_sha"], publication_id)
    if _is_publishable(doc):
        if not isinstance(attestation, dict):
            raise ReviewError(f"{t}: institutional review attestation wajib; distribusi tetap pending")
        errors = attestation_errors(attestation, available_source_ids=available_source_ids)
        if errors:
            raise ReviewError(f"{t}: attestation belum lengkap: {', '.join(errors)}")
        rec["attestation"] = _freeze_attestation(
            attestation, reviewer_identity=identity, reviewed_at=now,
            bundle_fingerprint=bundle_fingerprint)
        errors = attestation_errors(rec["attestation"], expected_fingerprint=bundle_fingerprint,
                                    available_source_ids=available_source_ids)
        if errors:
            raise ReviewError(f"{t}: attestation final tidak valid: {', '.join(errors)}")
        rec["review_sha"] = review_sha(report_plan(trace), doc, artifact_hashes,
                                       rec["trace_sha"], publication_id,
                                       attestation=rec["attestation"])
    else:
        rec["review_sha"] = bundle_fingerprint
    rec["publication_id"] = (publication_manifest.get("publication_id")
                              if isinstance(publication_manifest, dict) else None)
    rec["after"] = _verdict(doc)
    rec["history"] = history(record(folder, t, db))
    store.put(COLLECTION, _key(folder, t), rec, db)
    trace = dict(trace or {})
    trace["assumption_review"] = rec
    outputs.save(outputs.TRACE, folder, t, trace, db)
    if _is_publishable(doc):
        # Plan §8: prospective evaluation starts with the approved, frozen forecast.
        from . import forecast_ledger
        rec["forecast_frozen"] = forecast_ledger.freeze(folder, t, db)
    return rec


MAX_HISTORY = 20


def history(previous) -> list[dict]:
    """Earlier approvals, newest first: the previous record (without its own
    history) then its history. A re-approval never erases what came before."""
    if not isinstance(previous, dict):
        return []
    earlier = [x for x in previous.get("history") or [] if isinstance(x, dict)]
    return ([{k: v for k, v in previous.items() if k != "history"}] + earlier)[:MAX_HISTORY]


def plan_edits(rec) -> list[dict]:
    """Every change behind the approved plan: the edits of this approval and of
    any earlier one that produced the same plan, each with who made it and when."""
    if not isinstance(rec, dict):
        return []
    out = []
    for entry in [rec] + [x for x in rec.get("history") or [] if isinstance(x, dict)]:
        if entry.get("plan_sha") != rec.get("plan_sha"):
            continue
        for edit in entry.get("edits") or []:
            out.append({**edit, "reviewer": entry.get("reviewer"),
                        "reviewed_at": entry.get("reviewed_at")})
    return out


def _verdict(doc) -> dict:
    meta = (doc or {}).get("meta") or {}
    return {"status": meta.get("status"), "rating": meta.get("rating"), "tp": meta.get("tp")}


def _rp(value):
    return "Rp" + f"{value:,.0f}".replace(",", ".") if isinstance(value, (int, float)) else "-"


def attestation_draft(folder, ticker, db=None) -> dict | None:
    """A reviewer's starting point, written from the report's own evidence and checks.

    Every note states what the automatic gates recorded for this bundle and the
    register rows it rests on. It is a draft: the reviewer reads, corrects and
    submits it, and declares their own issuer relationship and conflicts, which
    are left blank. Nothing here approves anything.
    """
    t = str(ticker).upper()
    doc = outputs.load(outputs.REPORT, folder, t, db)
    if not isinstance(doc, dict):
        return None
    meta = doc.get("meta") or {}
    rows = [r for r in (doc.get("evidence_register") or {}).get("rows") or [] if r.get("row_id")]
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r.get("kind"), []).append(r)
    ids = lambda kinds: [r["row_id"] for k in kinds for r in by_kind.get(k, [])]  # noqa: E731
    actual = (by_kind.get("official_actual") or [{}])[-1]
    actual_ids = [actual["row_id"]] if actual.get("row_id") else []
    filings = ids(("official_filing",)) or actual_ids
    drivers = ids(("driver_source",)) or actual_ids
    events = ids(("tavily_article", "news", "catalyst")) or actual_ids
    release = (doc.get("log_gate") or {}).get("release") or {}
    production = release.get("production_blockers") or []
    limitations = release.get("limitations") or []
    quality = doc.get("earnings_quality") or {}
    shares = quality.get("share_basis") or {}
    te = doc.get("terminal_economics") or {}
    dv = doc.get("driver_value") or {}
    cases = dv.get("cases") or {}
    investability = doc.get("investability") or {}
    liquidity = investability.get("liquidity") or {}
    status = meta.get("status")
    checks = {}

    def check(key, note, source_ids, state="reviewed", **extra):
        checks[key] = {"status": state, "note": note, "source_ids": list(dict.fromkeys(source_ids)),
                       **extra}

    check("latest_official_actual_and_period",
          f"Aktual resmi {actual.get('period') or '-'} (periode berakhir "
          f"{actual.get('period_end') or '-'}, terbit {actual.get('published_at') or '-'}): "
          f"{actual.get('source_title') or actual.get('source') or '-'}, hal. "
          f"{actual.get('page') or '-'}; dipakai untuk {actual.get('use') or 'level periode dasar'}.",
          actual_ids, period=str(actual.get("period") or ""))
    violations = ((doc.get("evidence_register") or {}).get("violations") or []) + \
        ((doc.get("evidence_register") or {}).get("critical_violations") or [])
    check("material_source_claims_and_conflicts",
          f"Register bukti memuat {len(rows)} baris: {len(by_kind.get('official_filing', []))} "
          f"dokumen resmi, {len(by_kind.get('driver_source', []))} sumber driver; "
          + ("tanpa pelanggaran register." if not violations
             else f"{len(violations)} pelanggaran register: " + "; ".join(map(str, violations[:3])) + "."),
          actual_ids + filings)
    items = []
    for i, r in enumerate((dv.get("rows") or [])[:3]):
        items.append({
            "assumption_id": f"driver-{i + 1}",
            "description": f"{r.get('driver')}: {r.get('base')} ({r.get('basis')}), {r.get('years') or 'FY26F dst.'}",
            "value_sensitivity": (f"{r.get('unit')}: nilai per saham {_rp(r.get('value_low'))} "
                                  f"({r.get('low')}) sampai {_rp(r.get('value_high'))} ({r.get('high')}) "
                                  f"terhadap dasar {_rp(r.get('value_base'))}"),
            "source_ids": drivers[:3]})
    check("top_three_value_sensitive_assumptions",
          "Tiga driver teratas menurut dampak nilai pada tabel driver-ke-nilai laporan ini.",
          drivers[:3], items=items)
    harness = doc.get("harness") or {}
    blockers = harness.get("blockers") or []
    check("interim_statement_reconciliation",
          f"Model berlabuh pada aktual {actual.get('period') or '-'}; pemeriksaan harness "
          + ("lolos tanpa blocker." if not blockers else f"mencatat {len(blockers)} blocker: "
             + "; ".join(map(str, blockers[:3])) + "."),
          actual_ids)
    check("model_profile_and_method_chain",
          f"Model Profile {meta.get('model_profile') or '-'}; metode {doc.get('method') or '-'}.",
          actual_ids)
    if cases:
        check("scenario_consistency",
              f"Nilai per saham downside {_rp((cases.get('downside') or {}).get('per_share'))}, base "
              f"{_rp((cases.get('base') or {}).get('per_share'))}, upside "
              f"{_rp((cases.get('upside') or {}).get('per_share'))}; urutannya konsisten."
              if ((cases.get("downside") or {}).get("per_share") or 0)
              <= ((cases.get("base") or {}).get("per_share") or 0)
              <= ((cases.get("upside") or {}).get("per_share") or 0)
              else "Urutan downside, base dan upside tidak konsisten; periksa sebelum menyetujui.",
              drivers[:3])
    else:
        check("scenario_consistency", "Laporan tidak memuat kasus downside/base/upside.",
              actual_ids, state="not_available")
    check("catalyst_and_thesis_change_tests",
          "Katalis dari tabel katalis laporan; ambang perubahan tesis dari ringkasan keputusan "
          "(pergerakan driver yang mengubah rating, dibaca linear dari rentang uji).",
          events[:5])
    check("consensus_comparison",
          "Konsensus independen tidak tersedia di data laporan ini.", [], state="not_available")
    check("limitations_conflicts",
          "Batasan tercatat: " + ("; ".join(map(str, limitations)) if limitations else "tidak ada")
          + (". Belum Production-Ready: " + "; ".join(map(str, production)) if production else "") + ".",
          actual_ids)
    check("earnings_normalization",
          f"Ledger normalisasi berstatus {(quality.get('normalization') or {}).get('status') or quality.get('status') or '-'}.",
          filings)
    check("restatements_corporate_actions",
          f"Ledger saham berstatus {shares.get('status') or '-'}; saham pada tanggal laporan "
          f"{shares.get('shares_on_report_date') or '-'} dari {(shares.get('basis') or {}).get('source_title') or '-'}.",
          filings)
    te_checks = te.get("checks") or []
    check("house_assumptions_terminal_economics",
          f"Ekonomi terminal berstatus {te.get('status') or '-'}"
          + (f"; {sum(1 for c in te_checks if c.get('ok'))} dari {len(te_checks)} uji lolos." if te_checks else "."),
          actual_ids)
    reference = [b for b in production if "independent reference" in str(b)]
    check("independent_validation",
          ("Status Production-Ready: validasi model referensi independen per run lolos "
           "(kegagalan memblokir status ini)." if status == "distributable" else
           "Validasi referensi: " + ("; ".join(map(str, reference)) if reference else
                                     "tidak ada jalur referensi untuk metode ini") + "."),
          actual_ids)
    from . import investability as investability_mod
    bq = investability_mod.business_quality(t, (doc.get("run_manifest") or {}).get("as_of")) or []
    answered = sum(1 for i in bq if i.get("status") == "answered")
    check("business_quality",
          f"{answered} dari {len(bq)} dimensi kualitas bisnis terjawab dengan sumber bertanggal.",
          filings)
    check("liquidity_limitations",
          f"Likuiditas {liquidity.get('sessions') or '-'} sesi ({liquidity.get('start') or '-'} sampai "
          f"{liquidity.get('end') or '-'}), median nilai harian "
          f"{_rp(liquidity.get('median_value'))}; {liquidity.get('source') or 'data Sectors'}.",
          actual_ids)
    return {
        "checklist": checks,
        "disclosures": {
            "author_role": "Pipeline model Sektoral (build otomatis), bukan analis manusia",
            "scope_limitations": (f"Review atas bundle publikasi {meta.get('tanggal') or '-'}: register "
                                  "bukti, ledger saham dan normalisasi, uji otomatis dan batasan "
                                  "yang tercatat; bukan audit laporan keuangan."),
            "rating_or_scenario_policy": ("Rating dari selisih nilai model terhadap harga: Buy di atas "
                                          "+15%, Sell di bawah -10%, selain itu Hold (app.rating)."),
        },
        "note": ("Draf otomatis dari data laporan. Baca dan koreksi setiap isian, lalu nyatakan "
                 "sendiri hubungan dengan emiten dan konflik kepentingan."),
    }


def public(folder, ticker, db=None) -> dict:
    """The review state and the editable plan, for the web app."""
    st = status(folder, ticker, db)
    trace = outputs.load(outputs.TRACE, folder, ticker, db)
    doc = outputs.load(outputs.REPORT, folder, ticker, db)
    manifest = outputs.load(outputs.MANIFEST, folder, ticker, db)
    register, _, register_errors = _evidence_register_state(doc, trace, manifest)
    rec = st.get("record") or {}
    return {"state": st["state"], "plan_sha": st["plan_sha"],
            "reviewer": rec.get("reviewer"), "reviewed_at": rec.get("reviewed_at"),
            "reviewer_id": rec.get("reviewer_id"), "reviewer_role": rec.get("reviewer_role"),
            "identity_source": rec.get("identity_source"),
            "decision": rec.get("decision"), "note": rec.get("note"),
            "edits": plan_edits(rec) if rec else [],
            "history": [{"reviewer": h.get("reviewer"), "reviewed_at": h.get("reviewed_at"),
                         "decision": h.get("decision"), "edits": len(h.get("edits") or []),
                         "note": h.get("note")}
                        for h in (rec.get("history") or []) if isinstance(h, dict)],
            "stale": bool(st.get("stale_record")),
            "missing_artifacts": st.get("missing_artifacts") or [],
            "manifest_errors": st.get("manifest_errors") or [],
            "evidence_register_errors": st.get("evidence_register_errors") or [],
            "attestation_errors": st.get("attestation_errors") or [],
            "publication_id": rec.get("publication_id"),
            "attestation": rec.get("attestation"),
            "available_source_ids": (_evidence_source_options(register)
                                     if not register_errors else []),
            "attestation_schema": attestation_schema(),
            "fields": fields(report_plan(trace))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "approve"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--folder", required=True)
        cmd.add_argument("tickers", nargs="*" if name == "status" else "+")
        if name == "approve":
            cmd.add_argument("--reviewer", required=True)
            cmd.add_argument("--note", default="")
            cmd.add_argument("--attestation", help="path to institutional review JSON")
            cmd.add_argument("--edit", action="append", default=[],
                             help="path=value:reason, e.g. outyear_scenario[0].ebitda_margin_pct"
                                  "=13.0:alasan")
    args = parser.parse_args(argv)
    tickers = args.tickers or outputs.tickers(outputs.REPORT, args.folder)
    if args.command == "status":
        for t in tickers:
            st = status(args.folder, t)
            rec = st.get("record") or {}
            print(f"{t:5} {st['state']:9} {rec.get('reviewer') or '-'} {rec.get('reviewed_at') or ''}")
        return 0
    if args.edit and len(tickers) > 1:
        parser.error("--edit hanya untuk satu emiten per perintah")
    edits = []
    for text in args.edit:
        path, _, rest = text.partition("=")
        value, _, reason = rest.partition(":")
        edits.append({"path": path.strip(), "value": value.strip(), "reason": reason.strip()})
    failed = 0
    for t in tickers:
        try:
            attestation = None
            if args.attestation:
                try:
                    attestation = json.loads(Path(args.attestation).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as error:
                    raise ReviewError(f"attestation tidak dapat dibaca: {error}") from None
            declared_role = (((attestation or {}).get("disclosures") or {}).get("reviewer_role")
                             if isinstance(attestation, dict) else None)
            reviewer_identity = {"id": "cli:" + hashlib.sha256(args.reviewer.casefold().encode()).hexdigest()[:16],
                                 "name": args.reviewer, "role": declared_role or "Self-declared reviewer",
                                 "source": "cli_self_asserted"}
            rec = approve(args.folder, t, args.reviewer, args.note, edits,
                          attestation=attestation, reviewer_identity=reviewer_identity)
        except ReviewError as error:
            print(f"{t}: DITOLAK {error}", file=sys.stderr)
            failed += 1
            continue
        print(f"{t}: {rec['decision']} oleh {rec['reviewer']} ({len(rec['edits'])} perubahan); "
              f"{rec['before'].get('rating')} Rp{rec['before'].get('tp')} -> "
              f"{rec['after'].get('rating')} Rp{rec['after'].get('tp')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
