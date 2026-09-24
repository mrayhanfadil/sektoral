"""Phase 1 acceptance: gate-driven chain, stage validator, Gate 5 shared constant."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import gate_thresholds as GT, method_chain as MC, model_profiles as MP, stage as ST


def test_gate5_shared_constant():
    assert GT.EXTREME_UPSIDE_PCT == 100.0
    assert GT.EXTREME_DOWNSIDE_PCT == -50.0
    assert GT.TV_SHARE_PCT == 80.0
    # Ratio domain (chain/harness)
    assert GT.is_extreme_ratio(1.2) is True
    assert GT.is_extreme_ratio(0.8) is False
    assert GT.is_extreme_ratio(-0.6) is True
    assert GT.is_extreme_ratio(-0.4) is False
    # Percent domain (gates)
    assert GT.is_extreme_pct(115.0) is True
    assert GT.is_extreme_pct(80.0) is False
    assert GT.is_extreme_pct(-55.0) is True
    assert GT.is_extreme_pct(-40.0) is False
    # TV 80% flag, not blocker
    assert GT.tv_flagged(0.85) is True
    assert GT.tv_flagged(82.0) is True
    assert GT.tv_flagged(0.75) is False
    assert GT.tv_flagged(75.0) is False


def _verdict(primary, failed=None, reasons=None):
    return {"primary": primary, "gates_failed": failed or [], "reasons": reasons or []}


def test_chain_for_verdict_orders():
    assert MC.chain_for(_verdict("DDM / Excess Return"), "financial_ddm")[0] == "ddm"
    assert MC.chain_for(_verdict("NAV / Reserve-based"), "finite_life_mining") == (
        "sotp_lom", "rnav_lom", "ev_ebitda_fy")
    assert MC.chain_for(_verdict("SOTP"), "going_concern_fcff")[0] == "holding_sotp"
    assert MC.chain_for(_verdict("FCFF/WACC DCF"), "going_concern_fcff") == (
        "fcff_dcf", "relative_pe", "pe_fy_scenario")
    # Thin history assessed -> EV/EBITDA peer first
    v_thin = {"primary": "DCF (shortened horizon)", "gates_failed": ["1a_filing_history"],
              "reasons": ["1a filing history 2y < 4y → shortened-horizon"]}
    assert MC.chain_for(v_thin, "going_concern_fcff")[0] == "ev_ebitda_peer"
    # Unassessed 1a keeps DCF order
    v_un = {"primary": "FCFF/WACC DCF", "gates_failed": ["1a_filing_history"],
            "reasons": ["1a filing history tidak dapat dinilai (data belum tersedia)"]}
    assert MC.chain_for(v_un, "going_concern_fcff")[0] == "fcff_dcf"
    # Decline / pre-revenue
    assert MC.chain_for(_verdict("P/BV"), "going_concern_fcff")[0] == "pbv_relative"
    assert MC.chain_for(_verdict("EV/Sales"), "going_concern_fcff")[0] == "ev_sales_peer"


def test_missing_inputs_stay_unassessed():
    v = MP.evaluate({"domain": "single_business"})
    assert "1a_filing_history" in v.gates_failed
    assert "1b_profitability" in v.gates_failed
    assert "1c_capital_structure" in v.gates_failed
    assert "1d_equity_base" in v.gates_failed
    assert "2_nci" in v.gates_failed
    assert any("tidak dapat dinilai" in r for r in v.reasons)


def test_stage_validator_and_override(tmp_path, monkeypatch):
    ok_payload = {"life_cycle_stage": "decline", "has_steady_state_3y": True,
                  "commodity_price_driven": False, "dissimilar_segments": 1,
                  "rationale": "Pendapatan turun dua tahun beruntun karena restrukturisasi pabrik.",
                  "source_ids": ["news:0"]}
    annuals = [{"revenue": 100}, {"revenue": 90}, {"revenue": 80}]
    ok, _, norm = ST.validate(ok_payload, annuals)
    assert ok and norm["life_cycle_stage"] == "decline"
    bad = dict(ok_payload, life_cycle_stage="mature", has_steady_state_3y=True,
               commodity_price_driven=False, dissimilar_segments=1)
    # Non-default without citation fails
    bad2 = dict(ok_payload, life_cycle_stage="decline", source_ids=[])
    ok2, errs, _ = ST.validate(bad2, annuals)
    assert not ok2 and any("cite" in e or "must cite" in e for e in errs)
    # Override precedence
    monkeypatch.setattr(ST, "OVERRIDE_DIR", tmp_path)
    (tmp_path / "UJI.json").write_text(
        '{"life_cycle_stage": "decline", "has_steady_state_3y": false, '
        '"reason": "analis", "analyst": "A", "date": "2026-09-24"}')
    res = ST.classify({"ticker": "UJI", "annuals": annuals}, None)
    assert res["source"] == "override"
    assert res["values"]["life_cycle_stage"] == "decline"


def test_override_route_keeps_proposed_order():
    cands = {k: MC.candidate(k, per_share=1100, per_share_down=900)
             for k in ("fcff_dcf", "relative_pe", "pe_fy_scenario")}
    chain = MC.run("going_concern_fcff", cands, 1000.0,
                   order=("fcff_dcf", "relative_pe", "pe_fy_scenario"),
                   override_key="relative_pe")
    assert chain["route"] == "override"
    assert chain["selected"] == "relative_pe"
    assert chain["proposed_order"] == ["fcff_dcf", "relative_pe", "pe_fy_scenario"]
    assert chain["trace"][0]["role"] == "override"
