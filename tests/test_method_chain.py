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
    assert [t["decision"] for t in chain["trace"]] == [
        "selected", "cross_check", "not_needed", "not_needed"]
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


def test_data_gates_make_screening_methods_yield():
    intake_, fc, _ = test_valtables._fixture()
    eps = fc["rows"][0]["eps"]
    intake_["peers"] = [{"pe": test_valtables.PRICE / eps * f} for f in (0.9, 1.0, 1.1)]
    va = valuation.build(intake_, fc)
    trace = {t["key"]: t for t in va["method_chain"]["trace"]}
    # PER on screening EPS is numerically fine but rests on an unreleased forecast.
    assert trace["relative_pe"]["decision"] == "skipped"
    assert any("latest official interim" in r for r in trace["relative_pe"]["reasons"])
    assert trace["pe_fy_scenario"]["decision"] == "skipped"
    assert va["method_chain"]["selected"] is None
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


# ---------------------------------------------------------------- earnings-led

def _earnings_fixture(monkeypatch, h2_ratio=1.0, h2_margin=10.0, peers=(2.5, 2.8, 3.1)):
    intake_, fc, _ = test_valtables._fixture()
    shares = test_valtables.SHARES
    actual = {"period": "1H26", "period_end": "2026-06-30", "published_at": "2026-08-20",
              "source_url": "https://issuer.example/1h26.pdf",
              "metrics": {"revenue": 50e12, "net_profit": 5e12,
                          "net_profit_attributable": 4.5e12}}
    intake_.update(as_of="2026-09-24", price_date="2026-09-22",
                   latest_official_actual=actual,
                   official_evidence={"reporting_currency": "IDR",
                                      "balance_sheet": {"shares_outstanding": shares}},
                   peers=[{"pe": p} for p in peers])
    plan = {"earnings_scenario": {"h2_revenue_to_h1": h2_ratio, "h2_net_margin_pct": h2_margin,
                                  "rationale": "x" * 50, "source_ids": ["official"],
                                  "source_url": actual["source_url"],
                                  "published_at": actual["published_at"]}}
    fc["earnings_scenario"] = forecast._earnings_scenario(intake_, plan)
    return intake_, fc


def test_earnings_scenario_math_uses_attributable_share():
    intake_, fc = _earnings_fixture(None)
    fy = fc["earnings_scenario"]["full_year"]
    assert fy["revenue"] == 100e12 and fy["net_profit"] == 10e12
    assert fy["net_profit_attributable"] == 9e12  # 1H attributable share 90%


def test_going_concern_reaches_earnings_led_route_and_releases():
    intake_, fc = _earnings_fixture(None)
    va = valuation.build(intake_, fc, assumption_status="validated")
    chain = va["method_chain"]
    assert chain["selected"] == "pe_fy_scenario" and chain["route"] == "fallback"
    assert [t["decision"] for t in chain["trace"]] == ["skipped", "skipped", "selected"]
    assert va["release"]["status"] == "distributable_assumption_led"
    eps = 9e12 / test_valtables.SHARES
    assert va["tp"] == round(2.8 * eps / 10) * 10  # median peer PER
    assert va["tp_down"] == round(2.5 * eps / 10) * 10
    assert va["method"].startswith("FY26F PER median peer x EPS skenario analis")
    assert abs(va["implied"]["per"] - va["tp"] / eps) < 1e-9
    result = runner.run_all(intake_, fc, va)
    assert result["gates"]["engine_status"] == "distributable_assumption_led"
    assert result["log_gate"]["release"]["route"] == "analyst_target"


def test_earnings_led_needs_validated_agent_fresh_close_and_peers():
    intake_, fc = _earnings_fixture(None)
    assert valuation.build(intake_, fc)["release"]["status"] == "draft_non_distributable"
    stale = dict(intake_, price_date="2026-08-01")
    va = valuation.build(stale, fc, assumption_status="validated")
    assert va["method_chain"]["selected"] is None
    assert any("fresh sourced close" in r for t in va["method_chain"]["trace"]
               for r in t["reasons"])
    thin, fc2 = _earnings_fixture(None, peers=(2.5, 2.8))
    va = valuation.build(thin, fc2, assumption_status="validated")
    assert va["method_chain"]["selected"] is None


def test_earnings_led_extreme_result_stays_draft():
    intake_, fc = _earnings_fixture(None, h2_margin=60.0, peers=(30.0, 40.0, 50.0))
    va = valuation.build(intake_, fc, assumption_status="validated")
    assert va["method_chain"]["extreme"] is True
    assert va["release"]["status"] == "draft_non_distributable"
    assert va["tp"] is None


def test_mining_profile_never_gets_earnings_scenario():
    doc_in, _ = intake.load("AMMN")
    plan = {"earnings_scenario": {"h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 10,
                                  "rationale": "x" * 50, "source_ids": ["official"]}}
    assert forecast.build(doc_in, assumption_plan=plan)["earnings_scenario"] is None


def test_jpfa_report_publishes_on_validated_earnings_scenario(tmp_path):
    from app import build
    doc_in, _ = intake.load("JPFA", as_of="2026-09-24")
    actual = doc_in["latest_official_actual"]
    metrics = actual["metrics"]
    plan = {"news_effects": [], "earnings_scenario": {
        "h2_revenue_to_h1": 1.05,
        "h2_net_margin_pct": metrics["net_profit"] / metrics["revenue"] * 100,
        "rationale": "H2 mengikuti run-rate 1H dengan kenaikan musiman ringan.",
        "source_ids": ["official"], "source_url": actual["source_url"],
        "published_at": actual["published_at"]}}
    doc = build.build("JPFA", tmp_path, as_of="2026-09-24", assumption_plan=plan,
                      assumption_status="validated")
    assert doc["meta"]["status"] == "distributable_assumption_led"
    assert doc["harness"]["status"] == "distributable_assumption_led"
    assert doc["meta"]["tp"] and doc["meta"]["rating"] in {"Buy", "Hold", "Sell"}
    titles = [e["judul"] for e in doc["exhibits"]]
    assert "Skenario laba FY26F: aktual 1H dan asumsi H2" in titles
    assert "Target harga: PER peer x EPS FY26F" in titles
    assert "Rantai metode valuasi" in titles
    # Without the validated agent scenario the same issuer stays draft.
    draft = build.build("JPFA", tmp_path, as_of="2026-09-24")
    assert draft["meta"]["status"] == "draft_non_distributable"
