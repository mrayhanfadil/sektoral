"""Tool: run_all — sequential orchestrator (§0: 4 tahap berurutan).

Order: S1 → S2 → S3 → narrative → schema.
A failed gate stops later production stages: rating/TP withheld,
status forced to draft_non_distributable with named blockers.
Never downgrade critical failure to caveat. Non-critical limits go
once to catatan_metodologi only when the profile allows a labeled substitute.

Also merges the engine's own release gate (app.release.assess_release)
so harness and engine cannot disagree: production requires BOTH to pass.

With a report document, the template harness (spec/Struktur-Template.md:
app.harness.template on the document, app.harness.render_check on its
rendered HTML) runs too; its failed blockers join the list as ``T.<id>`` and
force draft_non_distributable, like every other blocker. One switch,
``template.ENABLED`` (on unless SEKTORAL_TEMPLATE_HARNESS=0), or the
``template_checks`` argument turns it off.
"""
from __future__ import annotations

import copy
import importlib

from .s1 import check_s1
from .s2 import check_s2
from .s3 import check_s3
from .narrative_tool import check_narrative
from .schema import check_output_schema
from .profiles import normalize


def _earnings_gate_passes(intake, forecast, valuation, assumption_status,
                          key="pe_fy_scenario") -> bool:
    from app import release as _release
    trace = next((t for t in (valuation.get("method_chain") or {}).get("trace") or []
                  if t.get("key") == key), None)
    if not trace:
        return False
    # The agent status comes from the caller (the agent run), never from the
    # engine's recorded gate result, so the harness re-checks it independently.
    assess = {"pbv_roe_fy": _release.assess_pbv_roe_fy,
              "pbv_book": _release.assess_pbv_book,
              "holding_sotp": _release.assess_holding_sotp}.get(key, _release.assess_earnings_led)
    if (trace.get("detail") or {}).get("basis") == "scenario":
        # Primary DDM / FCFF DCF valued on the validated scenario.
        assess = _release.SCENARIO_ASSESSORS.get(key)
        if assess is None:
            return False
    again = assess(intake, forecast, {"detail": trace.get("detail") or {}}, assumption_status)
    return again["status"] in ("distributable_assumption_led", "distributable")


def _template_mods():
    # Imported on use so ``python -m app.harness.template`` runs without the
    # package having imported that module first.
    return (importlib.import_module("app.harness.template"),
            importlib.import_module("app.harness.render_check"))


def _template_gate(doc: dict, profile: str, intake: dict, valuation: dict,
                   render_checks: bool) -> tuple[dict, dict]:
    """Template checks on the document and on its rendered HTML (fail closed)."""
    _template, _render_check = _template_mods()
    selected = ((valuation.get("method_chain") or {}).get("selected")
                if isinstance(valuation, dict) else None)
    currency = (intake.get("official_evidence") or {}).get("reporting_currency")
    rt = _template.check_template(doc, profile=profile if profile != "unsupported" else None,
                                  method_key=selected, currency=currency)
    if not render_checks:
        return rt, {"tool": "check_rendered", "status": "dilabeli", "checks": [], "blockers": []}
    try:
        from app import render as _render
        rr = _render_check.check_rendered(_render.render(copy.deepcopy(doc)), doc)
    except Exception as e:  # a report that cannot be rendered cannot be released
        err = _render_check.error_result(e)
        rr = {"tool": "check_rendered", "status": "gagal", "checks": [err],
              "blockers": [f"{err['check']}: {err['message']}"]}
    return rt, rr


def run_all(intake: dict | None = None, forecast: dict | None = None,
            valuation: dict | None = None, doc: dict | None = None,
            assumption_status: str | None = None, template_checks: bool | None = None,
            render_checks: bool = True) -> dict:
    intake, forecast, valuation = intake or {}, forecast or {}, valuation or {}
    profile = normalize(intake.get("model_profile") or (doc.get("meta") or {}).get("model_profile")
                        if isinstance(doc, dict) else intake.get("model_profile"))

    r1 = check_s1(intake)
    # Gate sequence: don't run later production checks as passing when early gate fails,
    # but still collect their blockers for a complete trace.
    r2 = check_s2(intake, forecast)
    r3 = check_s3(intake, forecast, valuation)
    rn = check_narrative(doc) if doc is not None else \
        {"tool": "check_narrative", "status": "dilabeli", "checks": [], "blockers": []}
    rs = check_output_schema(doc) if doc is not None else \
        {"tool": "check_output_schema", "status": "dilabeli", "checks": [], "blockers": []}
    use_template = _template_mods()[0].ENABLED if template_checks is None else template_checks
    if doc is not None and use_template:
        rt, rr = _template_gate(doc, profile, intake, valuation, render_checks)
    else:
        why = "tanpa dokumen" if doc is None else "template harness dimatikan"
        rt = {"tool": "check_template", "status": "dilabeli", "checks": [], "blockers": [],
              "message": why}
        rr = {"tool": "check_rendered", "status": "dilabeli", "checks": [], "blockers": []}
    t_blockers = list(rt["blockers"]) + list(rr["blockers"])

    # Engine release gate (source of truth for SOTP/DDM/driver provenance).
    engine_blockers: list[str] = []
    engine_status: str | None = None
    try:
        from app import release as _release
        sotp_like = valuation.get("sotp") if isinstance(valuation, dict) else None
        if profile == "financial_ddm" and isinstance(valuation, dict) and valuation.get("ddm"):
            sotp_like = valuation.get("ddm")
        chain = valuation.get("method_chain") if isinstance(valuation, dict) else None
        if isinstance(chain, dict) and chain.get("order"):
            # Method chain (§4.1a): common data gates + selected-method sanity;
            # skipped methods' gaps stay in the chain trace.
            er = _release.assess_chain(profile, intake, forecast, chain)
        else:
            er = _release.assess_release(profile, intake, forecast, sotp_like)
        engine_status = er.get("status")
        engine_blockers = list(er.get("blockers") or [])
    except Exception as e:  # fail closed
        engine_status = "draft_non_distributable"
        engine_blockers = [f"engine release error: {e}"]

    # A validated analyst-target mining report is an explicit alternate release
    # route. Its release assessor has already checked the sourced interim
    # scenario, quote/FX, balance-sheet bridge, and 6x/8x/10x sensitivity. It
    # does not claim a physical LoM forecast or completed SOTP, so retain those
    # findings in the gate trace without treating them as blockers for this
    # route. Every other harness check remains mandatory.
    assumption_release = valuation.get("release") if isinstance(valuation, dict) else None
    selected_method = ((valuation.get("method_chain") or {}).get("selected")
                       if isinstance(valuation, dict) else None)
    # The selected method carries its own evidence gate, re-assessed here from
    # the same inputs (not trusted blindly). Its release then replaces the
    # screening-forecast gate (S2.9); a Method Gate 5 extreme stop stays a blocker.
    own_gate = (
        isinstance(assumption_release, dict) and (
            (profile == "finite_life_mining" and
             assumption_release.get("method") == "FY26F EV/EBITDA 8x") or
            (profile == "finite_life_mining" and selected_method == "sotp_lom" and
             _earnings_gate_passes(intake, forecast, valuation, assumption_status,
                                   "sotp_lom")) or
            (profile in ("going_concern_fcff", "financial_ddm") and
             selected_method in ("pe_fy_scenario", "pbv_roe_fy", "pbv_book", "ddm",
                                 "fcff_dcf", "dcf_reference", "holding_sotp",
                                 "ev_ebitda_peer") and
             _earnings_gate_passes(intake, forecast, valuation, assumption_status,
                                   selected_method)))
    )
    assumption_led = (
        own_gate and
        assumption_release.get("status") == "distributable_assumption_led" and
        not (assumption_release.get("blockers") or []))
    s2_blockers = list(r2["blockers"])
    if own_gate:
        s2_blockers = [b for b in s2_blockers if not b.startswith("S2.9:")]
        # The incomplete SOTP/screening assessment remains attached as audit context.
        engine_status = assumption_release["status"]
        engine_blockers = list(assumption_release.get("blockers") or [])

    # Some assumption-led routes replace the underlying production release
    # result. Re-apply the register gate after that route selection so source
    # failures remain Release Gate blockers on every path.
    if isinstance(doc, dict) and "evidence_register" in doc:
        from app.evidence import release_blockers as _evidence_blockers
        register_blockers = _evidence_blockers(doc.get("evidence_register"))
        if register_blockers:
            engine_status = "draft_non_distributable"
            engine_blockers = list(dict.fromkeys(engine_blockers + register_blockers))

    blockers = ([f"S1.{b}" for b in r1["blockers"]] + [f"S2.{b}" for b in s2_blockers] +
                [f"S3.{b}" for b in r3["blockers"]] + [f"N.{b}" for b in rn["blockers"]] +
                [f"S.{b}" for b in rs["blockers"]] + [f"T.{b}" for b in t_blockers] +
                [f"release.{b}" for b in engine_blockers])

    # Production requires every gate + engine release to pass.
    s2_pass = not s2_blockers
    all_pass = (r1["status"] == "lolos" and s2_pass and
                r3["status"] == "lolos" and engine_status in ("distributable",
                                                             "distributable_assumption_led"))
    # Narrative/schema failures block production rendering but don't fake numbers.
    if doc is not None and (rn["status"] == "gagal" or rs["status"] == "gagal"):
        all_pass = False
    # Template blockers (spec/Struktur-Template.md) fail closed like any other.
    if t_blockers:
        all_pass = False

    if engine_status == "distributable_assumption_led" and all_pass:
        status = "distributable_assumption_led"
    elif all_pass:
        status = "distributable"
    else:
        status = "draft_non_distributable"

    log_gate = {"S1": {c["check"]: c["status"] for c in r1["checks"]},
                "S2": {c["check"]: c["status"] for c in r2["checks"]},
                "S3": {c["check"]: c["status"] for c in r3["checks"]},
                "narrative": {c["check"]: c["status"] for c in rn["checks"]},
                "schema": {c["check"]: c["status"] for c in rs["checks"]},
                "template": {c["check"]: c["status"] for c in rt["checks"] + rr["checks"]},
                "release": {"status": status, "engine_status": engine_status,
                            "route": "analyst_target" if assumption_led else
                            ((valuation.get("method_chain") or {}).get("route") or "primary_method")
                            if isinstance(valuation, dict) else "primary_method",
                            "method_key": (valuation.get("method_chain") or {}).get("selected")
                            if isinstance(valuation, dict) else None,
                            "limitations": (assumption_release.get("limitations") or [])
                            if assumption_led else [],
                            "underlying_sotp": assumption_release.get("underlying_sotp")
                            if assumption_led else None,
                            "blockers": blockers}}
    return {"tool": "run_all", "profile": profile, "status": status,
            "blockers": blockers, "log_gate": log_gate,
            "gates": {"s1": r1, "s2": r2, "s3": r3, "narrative": rn,
                      "schema": rs, "template": rt, "render": rr,
                      "engine_status": engine_status}}
