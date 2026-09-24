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
            "gates_unassessed": ["1a_filing_history"],
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


def test_unassessed_gates_are_explicit_not_parsed_from_text():
    v = MP.evaluate({"domain": "single_business"})
    assert {"1a_filing_history", "1b_profitability", "1d_equity_base"} <= set(v.gates_unassessed)
    # Wording of a reason no longer matters: same verdict, reasons removed.
    stripped = dict(v.to_dict(), reasons=[])
    assert MC.chain_for(stripped, "going_concern_fcff")[0] == "fcff_dcf"


def test_short_history_miner_keeps_mining_chain():
    thin = {"primary": "DCF (shortened horizon)", "gates_failed": ["1a_filing_history"],
            "reasons": ["1a filing history 2y < 4y"]}
    assert MC.chain_for(thin, "finite_life_mining") == ("sotp_lom", "rnav_lom", "ev_ebitda_fy")


def test_gate5_percent_is_never_read_as_ratio():
    assert GT.is_extreme_pct(1.5) is False and GT.is_extreme_pct(-1.2) is False
    assert GT.gate_upside_pct({"upside_pct": 1.5}) == 1.5
    assert GT.gate_upside_pct({"upside": 1.5}) == 150.0
    v = MP.evaluate({"domain": "single_business", "upside_pct": 1.5})
    assert v.rating_override is None


# ------------------------------------------------------- PR #5 review fixes

def _built(ticker):
    from app import forecast, intake, valuation
    doc_in, _ = intake.load(ticker, as_of="2026-09-24")
    fc = forecast.build(doc_in)
    return doc_in, fc, valuation.build(doc_in, fc)


def test_usd_reporter_gate_ratios_convert_official_bs_to_idr():
    doc_in, _, va = _built("AMMN")
    nd_ebitda = va["gate_inputs"]["net_debt_to_ebitda"]
    if doc_in.get("fx_spot"):
        assert 0.5 < nd_ebitda < 20  # was ~0.0003 when USD net debt met IDR EBITDA
    else:
        assert nd_ebitda is not None


def test_total_liabilities_is_never_financial_debt(monkeypatch):
    doc_in, fc, _ = _built("JPFA")
    from app import valuation
    bs = doc_in["official_evidence"]["balance_sheet"]
    assert "total_debt" not in bs and "total_liabilities" in bs
    va = valuation.build(doc_in, fc)
    liab_ratio = bs["total_liabilities"] / (bs["total_liabilities"] + bs["total_equity"])
    assert abs(va["gate_inputs"]["d_de_ratio"] - liab_ratio) > 1e-6


def test_nci_share_uses_total_equity():
    doc_in, _, va = _built("SSIA")
    bs = doc_in["official_evidence"]["balance_sheet"]
    expected = bs["non_controlling_interest"] / (
        bs["equity_attributable"] + bs["non_controlling_interest"]) * 100
    assert abs(va["gate_inputs"]["nci_pct"] - expected) < 1e-6


def test_charts_never_plot_the_screening_forecast():
    from app import report_extras as R
    doc_in, fc, _ = _built("JPFA")
    assert fc["forecast_basis"] == "historical_screening_proxy"
    assert R.chart_forecast_rows(doc_in, fc) == []
    scenario = {"year": 2026, "full_year": {"revenue": 70e12, "net_profit": 5e12}}
    rows = R.chart_forecast_rows(doc_in, dict(fc, earnings_scenario=scenario))
    assert rows[0]["label"] == "FY26F" and rows[0]["revenue"] == 70e12


def test_stage_citations_must_be_supplied_and_consistent():
    payload = {"life_cycle_stage": "pre_revenue", "has_steady_state_3y": False,
               "commodity_price_driven": False, "dissimilar_segments": 1,
               "rationale": "Perusahaan masih tahap awal tanpa pendapatan berulang material.",
               "source_ids": ["official"]}
    annuals = [{"revenue": 900, "earnings": 50}, {"revenue": 1000, "earnings": 60}]
    ok, errors, _ = ST.validate(payload, annuals, allowed_sources={"official"})
    assert not ok and any("pre_revenue contradicts" in e for e in errors)
    ghost = dict(payload, life_cycle_stage="decline", source_ids=["news:9"])
    ok, errors, _ = ST.validate(ghost, [{"revenue": 100}, {"revenue": 80}],
                                allowed_sources={"official", "news:0"})
    assert not ok and any("not supplied" in e for e in errors)


def test_draft_cover_never_claims_a_maintained_rating(tmp_path, monkeypatch):
    from app import build, rating_history
    monkeypatch.setattr(rating_history, "DIR", tmp_path)
    (tmp_path / "BBRI.json").write_text(
        '{"history": [{"date": "2026-06-01", "rating": "Buy", "tp": 5000}]}')
    doc = build.build("BBRI", tmp_path, as_of="2026-09-24")
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert doc["meta"]["rating_status"] == "Dalam peninjauan (rating terakhir Buy)"


def test_draft_method_note_uses_chain_label():
    from app import narrative
    assert narrative._method_label("relative_pe") == MC.LABELS["relative_pe"]
    assert narrative._method_label("rnav") == "RNAV LoM (Rp)"
