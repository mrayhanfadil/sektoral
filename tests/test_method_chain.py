"""Rantai metode valuasi (§4.1a): primary → fallback → draft."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import intake, forecast, method_chain as MC, release, valuation  # noqa: E402
from app.harness import runner  # noqa: E402

import test_valtables  # noqa: E402

PRICE = 1_000.0


def _ok(key, ps, down=None):
    return MC.candidate(key, per_share=ps, per_share_down=down if down is not None else ps * 0.9)


def test_primary_sufficient_is_selected_and_rest_are_cross_checks():
    chain = MC.run("financial_ddm", {"ddm": _ok("ddm", 1100), "pbv_roe": _ok("pbv_roe", 900),
                                     "relative_pe": MC.candidate("relative_pe", reasons=["x"])},
                   PRICE)
    assert chain["selected"] == "ddm" and chain["route"] == "primary"
    assert [t["decision"] for t in chain["trace"]] == ["selected", "cross_check", "not_needed"]
    assert MC.summary_blocker(chain) is None


def test_insufficient_primary_falls_back_in_fixed_order():
    chain = MC.run("going_concern_fcff", {
        "fcff_dcf": MC.candidate("fcff_dcf", per_share=300, reasons=["skala: ekuitas 12%"]),
        "relative_pe": _ok("relative_pe", 1200)}, PRICE)
    assert chain["selected"] == "relative_pe" and chain["route"] == "fallback"
    assert chain["trace"][0]["decision"] == "skipped"
    assert chain["trace"][0]["reasons"] == ["skala: ekuitas 12%"]


def test_extreme_result_stops_chain_instead_of_shopping_for_a_nicer_method():
    chain = MC.run("going_concern_fcff", {"fcff_dcf": _ok("fcff_dcf", 1800),
                                          "relative_pe": _ok("relative_pe", 1050)}, PRICE)
    assert chain["selected"] == "fcff_dcf" and chain["extreme"] is True
    assert chain["trace"][0]["decision"] == "stop_extreme"
    assert chain["trace"][1]["decision"] == "cross_check"
    assert "extreme fcff_dcf" in MC.summary_blocker(chain)


def test_no_sufficient_method_names_every_gap():
    chain = MC.run("finite_life_mining", {}, PRICE)
    assert chain["selected"] is None and chain["route"] is None
    blocker = MC.summary_blocker(chain)
    assert all(key in blocker for key in ("sotp_lom", "rnav_lom", "ev_ebitda_fy"))


def test_unsupported_profile_has_no_chain():
    chain = MC.run("unsupported", {}, PRICE)
    assert chain["order"] == [] and MC.summary_blocker(chain) is None


def test_candidate_rejects_missing_value_and_non_decreasing_downside():
    assert MC.candidate("ddm", per_share=None)["status"] == "insufficient"
    assert MC.candidate("ddm", per_share=-5)["status"] == "insufficient"
    bad = MC.candidate("ddm", per_share=100, per_share_down=100)
    assert bad["reasons"] == ["downside sensitivitas tidak lebih rendah dari base"]


def test_scale_band():
    assert MC.scale_reasons(100, 10, 1000) == []
    assert MC.scale_reasons(10, 10, 1000)[0].startswith("skala: ekuitas 10%")
    assert MC.scale_reasons(400, 10, 1000)[0].startswith("skala: ekuitas 400%")


def test_relative_pe_drops_outliers_and_needs_three_peers():
    peers = [{"pe": p} for p in (8.0, 10.0, 12.0, 14.0, -300.0, 9000.0, None)]
    c = MC.relative_pe(peers, eps_fwd=100.0, shares=10, market_cap=10_000)
    assert c["status"] == "sufficient"
    assert c["detail"]["peer_count"] == 4 and c["detail"]["median_pe"] == 11.0
    assert c["per_share"] == 1100.0 and c["per_share_down"] < c["per_share"]
    thin = MC.relative_pe(peers[:2], eps_fwd=100.0, shares=10, market_cap=10_000)
    assert thin["status"] == "insufficient"
    loss = MC.relative_pe(peers, eps_fwd=-1.0, shares=10, market_cap=10_000)
    assert "EPS forward <= 0" in loss["reasons"][0]


def _going_concern_with_peers(monkeypatch):
    monkeypatch.setattr(release, "common_blockers", lambda *a, **k: [])
    intake_, fc, _ = test_valtables._fixture()
    eps = fc["rows"][0]["eps"]
    pe = test_valtables.PRICE * 1.1 / eps  # median PER → +10% vs price
    intake_["peers"] = [{"pe": pe * f} for f in (0.9, 1.0, 1.1)]
    return intake_, fc


def test_dcf_failure_falls_back_to_relative_and_releases(monkeypatch):
    intake_, fc = _going_concern_with_peers(monkeypatch)
    va = valuation.build(intake_, fc)
    chain = va["method_chain"]
    assert chain["trace"][0]["key"] == "fcff_dcf"
    assert chain["trace"][0]["decision"] == "skipped"
    assert chain["selected"] == "relative_pe" and chain["route"] == "fallback"
    assert va["release"]["status"] == "distributable"
    assert va["release"]["route"] == "fallback"
    assert va["method"].startswith(MC.LABELS["relative_pe"])
    assert "[fallback: DCF FCFF tidak memadai]" in va["method"]
    assert va["tp"] == round(chain["trace"][1]["per_share"] / 10) * 10
    assert va["tp_down"] < va["tp"] and va["rating"] in {"Buy", "Hold", "Sell"}
    assert any(n.startswith("rantai metode: DCF FCFF dilewati") for n in va["notes"])
    # DCF screen stays available for exhibits without becoming the TP.
    assert va["dcf_blend"] != va["tp"]


def test_harness_follows_chain_not_skipped_primary(monkeypatch):
    intake_, fc = _going_concern_with_peers(monkeypatch)
    va = valuation.build(intake_, fc)
    result = runner.run_all(intake_, fc, va)
    assert result["gates"]["engine_status"] == "distributable"
    assert result["log_gate"]["release"]["route"] == "fallback"
    assert result["log_gate"]["release"]["method_key"] == "relative_pe"
    assert not any("G3.8" in b for b in result["blockers"])


def test_data_gates_still_block_a_sufficient_fallback():
    intake_, fc, _ = test_valtables._fixture()
    eps = fc["rows"][0]["eps"]
    intake_["peers"] = [{"pe": test_valtables.PRICE / eps * f} for f in (0.9, 1.0, 1.1)]
    va = valuation.build(intake_, fc)
    assert va["method_chain"]["selected"] == "relative_pe"
    assert va["release"]["status"] == "draft_non_distributable"
    assert va["tp"] is None and va["rating"] == "DRAFT NON-DISTRIBUTABLE"


def test_ammn_screening_forecast_blocks_asset_methods_and_stays_draft():
    doc_in, _ = intake.load("AMMN")
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    trace = {t["key"]: t for t in va["method_chain"]["trace"]}
    assert trace["sotp_lom"]["decision"] == "skipped"
    # RNAV values the screening forecast margin, so it cannot be the basis
    # and must not block the assumption-led multiple route behind it.
    assert trace["rnav_lom"]["decision"] == "skipped"
    assert any("physical-driver" in r for r in trace["rnav_lom"]["reasons"])
    assert trace["rnav_lom"]["per_share_down"] < trace["rnav_lom"]["per_share"]
    assert trace["ev_ebitda_fy"]["decision"] == "skipped"
    # Mining never falls back to a perpetual-growth DCF.
    assert "fcff_dcf" not in trace
    assert va["release"]["status"] == "draft_non_distributable"
    assert va["tp"] is None
    assert not any(b.startswith("SOTP incomplete") for b in va["release"]["blockers"])


def test_mining_reaches_assumption_led_route_when_its_gate_passes(monkeypatch):
    doc_in, _ = intake.load("AMMN")
    fc = forecast.build(doc_in)
    passed = lambda intake_, fc_, target, status, underlying: {
        "status": "distributable_assumption_led", "method": "FY26F EV/EBITDA 8x",
        "blockers": [], "underlying_sotp": underlying, "limitations": ["8x asumsi"]}
    target = {"values": [{"multiple": m, "per_share_idr": v} for m, v in
                         ((6.0, 4200.0), (8.0, 5000.0), (10.0, 5800.0))]}
    monkeypatch.setattr(release, "assess_assumption_led", passed)
    monkeypatch.setattr(valuation, "scenario_ev_ebitda_crosscheck", lambda *a: target)
    va = valuation.build(doc_in, fc, assumption_status="validated")
    assert va["method_chain"]["selected"] == "ev_ebitda_fy"
    assert va["method_chain"]["route"] == "fallback"
    assert va["release"]["status"] == "distributable_assumption_led"
    assert va["tp"] == 5000 and va["scenario_target"] is target
