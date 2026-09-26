"""The coverage dashboard states status and a precise, actionable blocker."""
from app import coverage


def _doc(status, profile, method, blockers=(), as_of="2026-09-24"):
    return {"meta": {"status": status, "model_profile": profile, "rating": "Buy", "tp": 100},
            "log_gate": {"release": {"underlying_primary": list(blockers),
                                     "method_chain": {"selected": method}}},
            "run_manifest": {"as_of": as_of},
            "evidence_register": {"rows": [{"kind": "official_actual", "period": "1H26",
                                            "published_at": "2026-08-31"}]}}


def test_missing_driver_files_and_policy_vintage_are_named_precisely():
    gmfi = coverage.row("GMFI", _doc("distributable_assumption_led", "going_concern_fcff", "fcff_dcf",
                                     ["forecast is not verified as production-ready"]))
    assert any("data/operating_drivers/GMFI.json" in a for a in gmfi["next_actions"])
    bbca = coverage.row("BBCA", _doc("distributable_assumption_led", "financial_ddm", "ddm"))
    assert any("data/bank_drivers/BBCA.json" in a for a in bbca["next_actions"])
    powr = coverage.row("POWR", _doc("distributable_assumption_led", "going_concern_fcff", "fcff_dcf",
                                     ["house-assumption policy became effective after the Report Date"]))
    assert powr["next_actions"] == [
        "house policy 1.2.0 is effective 2026-09-26, after this Report Date; a run dated on or "
        "after it is required"]
    inet = coverage.row("INET", _doc("distributable_assumption_led", "going_concern_fcff", "ev_ebitda_peer"))
    assert any("has no production path" in a for a in inet["next_actions"])
    assert gmfi["days_since_latest_actual"] == 24


def test_a_production_ready_report_has_no_next_action():
    row = coverage.row("POWR", _doc("distributable", "going_concern_fcff", "fcff_dcf", as_of="2026-09-26"))
    assert row["status_label"] == "Production-Ready" and row["next_actions"] == []
