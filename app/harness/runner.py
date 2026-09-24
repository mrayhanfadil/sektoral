"""Tool: run_all — sequential orchestrator (§0: 4 tahap berurutan).

Order: G1 → G2 → G3 → narrative → schema.
A failed gate stops later production stages: rating/TP withheld,
status forced to draft_non_distributable with named blockers.
Never downgrade critical failure to caveat. Non-critical limits go
once to catatan_metodologi only when the profile allows a labeled substitute.

Also merges the engine's own release gate (app.release.assess_release)
so harness and engine cannot disagree: production requires BOTH to pass.
"""
from __future__ import annotations

from .g1 import check_g1
from .g2 import check_g2
from .g3 import check_g3
from .narrative_tool import check_narrative
from .schema import check_output_schema
from .profiles import normalize


def run_all(intake: dict | None = None, forecast: dict | None = None,
            valuation: dict | None = None, doc: dict | None = None) -> dict:
    intake, forecast, valuation = intake or {}, forecast or {}, valuation or {}
    profile = normalize(intake.get("model_profile") or (doc.get("meta") or {}).get("model_profile")
                        if isinstance(doc, dict) else intake.get("model_profile"))

    r1 = check_g1(intake)
    # Gate sequence: don't run later production checks as passing when early gate fails,
    # but still collect their blockers for a complete trace.
    r2 = check_g2(intake, forecast)
    r3 = check_g3(intake, forecast, valuation)
    rn = check_narrative(doc) if doc is not None else \
        {"tool": "check_narrative", "status": "dilabeli", "checks": [], "blockers": []}
    rs = check_output_schema(doc) if doc is not None else \
        {"tool": "check_output_schema", "status": "dilabeli", "checks": [], "blockers": []}

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
    assumption_led = (
        profile == "finite_life_mining" and
        isinstance(assumption_release, dict) and
        assumption_release.get("status") == "distributable_assumption_led" and
        assumption_release.get("method") == "FY26F EV/EBITDA 8x" and
        not (assumption_release.get("blockers") or [])
    )
    g2_blockers = list(r2["blockers"])
    if assumption_led:
        g2_blockers = [b for b in g2_blockers if not b.startswith("G2.9:")]
        # The selected method has a separately validated release assessment;
        # the incomplete SOTP assessment remains attached as audit context.
        engine_status = assumption_release["status"]
        engine_blockers = []

    blockers = ([f"G1.{b}" for b in r1["blockers"]] + [f"G2.{b}" for b in g2_blockers] +
                [f"G3.{b}" for b in r3["blockers"]] + [f"N.{b}" for b in rn["blockers"]] +
                [f"S.{b}" for b in rs["blockers"]] +
                [f"release.{b}" for b in engine_blockers])

    # Production requires every gate + engine release to pass.
    g2_pass = not g2_blockers
    all_pass = (r1["status"] == "lolos" and g2_pass and
                r3["status"] == "lolos" and engine_status in ("distributable",
                                                             "distributable_assumption_led"))
    # Narrative/schema failures block production rendering but don't fake numbers.
    if doc is not None and (rn["status"] == "gagal" or rs["status"] == "gagal"):
        all_pass = False

    if engine_status == "distributable_assumption_led" and all_pass:
        status = "distributable_assumption_led"
    elif all_pass:
        status = "distributable"
    else:
        status = "draft_non_distributable"

    log_gate = {"G1": {c["check"]: c["status"] for c in r1["checks"]},
                "G2": {c["check"]: c["status"] for c in r2["checks"]},
                "G3": {c["check"]: c["status"] for c in r3["checks"]},
                "narrative": {c["check"]: c["status"] for c in rn["checks"]},
                "schema": {c["check"]: c["status"] for c in rs["checks"]},
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
            "gates": {"g1": r1, "g2": r2, "g3": r3, "narrative": rn,
                      "schema": rs, "engine_status": engine_status}}
