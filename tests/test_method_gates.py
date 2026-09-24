"""Tests for Method Routing & Valuation Gates 0-5.

Covers:
- RATU: full-pass DCF (FCFF/WACC DCF)
- CDIA: thin-data + ramping relative valuation
- MTEL: NCI 15-40% band with mandatory SOTP cross-check
- BBCA: financial institution DDM primary
- ADRO: finite-reserves / extractive NAV primary
- Unknown / missing metadata -> unsupported fail-closed
- Holding dissimilar subsidiaries with multiple segments -> SOTP primary
- Gate 1-4 boundary conditions (EBIT profitability, leverage breach, negative equity, decline, pre-revenue)
- Gate 5 output sanity (extreme upside/downside override, terminal share flag, peer exit range check)
- Valuation engine integration (valuation.build carries gate_verdict)
"""
from __future__ import annotations

import pytest

from app.model_profiles import GateVerdict, evaluate
from app import intake, forecast, valuation


def test_ratu_full_pass_dcf():
    """Mature single-business with full history, positive EBIT, healthy balance sheet -> FCFF/WACC DCF."""
    inputs = {
        "domain": "single_business",
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "d_de_ratio": 0.30,
        "net_debt_to_ebitda": 1.5,
        "icr": 5.0,
        "equity_positive": True,
        "nci_pct": 5.0,
        "revenue_drivers": ["volume_consumer"],
        "has_steady_state_3y": True,
        "life_cycle_stage": "mature",
    }
    verdict = evaluate(inputs)
    assert isinstance(verdict, GateVerdict)
    assert verdict.primary == "FCFF/WACC DCF"
    assert verdict.secondary == "Relative Valuation"
    assert verdict.thin_data is False
    assert verdict.rating_override is None
    assert verdict.gates_failed == []

    # Unpacking compatibility check:
    primary, secondary, thin_data, rating_override, reasons = evaluate(inputs)
    assert primary == "FCFF/WACC DCF"
    assert secondary == "Relative Valuation"
    assert thin_data is False
    assert rating_override is None
    assert isinstance(reasons, list)


def test_cdia_thin_and_ramping_relative():
    """Newly listed / ramping asset with <4y history and <3y steady-state -> Relative Valuation + thin_data."""
    inputs = {
        "domain": "single_business",
        "filing_history_years": 2,
        "has_steady_state_3y": False,
        "ebit_positive_count": 2,
        "equity_positive": True,
    }
    verdict = evaluate(inputs)
    assert verdict.primary == "Relative Valuation"
    assert verdict.thin_data is True
    assert "1a_filing_history" in verdict.gates_failed
    assert any("shortened-horizon" in r.lower() or "thin data" in r.lower() for r in verdict.reasons)
    assert any("ramping" in r.lower() or "steady-state" in r.lower() for r in verdict.reasons)


def test_mtel_nci_band_sotp_cross_check():
    """Significant non-controlling interest in 15-40% band -> DCF primary with mandatory SOTP cross-check."""
    inputs = {
        "domain": "single_business",
        "nci_pct": 25.0,
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "equity_positive": True,
        "has_steady_state_3y": True,
    }
    verdict = evaluate(inputs)
    assert verdict.primary == "FCFF/WACC DCF"
    assert verdict.secondary == "SOTP"
    assert any("15–40%" in r or "15-40%" in r for r in verdict.reasons)


def test_bbca_bank_ddm():
    """Bank / financial institution -> DDM primary (debt is raw material, EV undefined)."""
    inputs = {
        "domain": "bank",
        "filing_history_years": 10,
    }
    verdict = evaluate(inputs)
    assert "DDM" in verdict.primary
    assert verdict.thin_data is False
    assert any("financial institution" in r.lower() for r in verdict.reasons)


def test_adro_mining_nav():
    """Finite reserves / mining asset -> reserve-based NAV primary."""
    inputs = {
        "domain": "mining",
        "revenue_drivers": ["commodity_coal"],
    }
    verdict = evaluate(inputs)
    assert verdict.primary == "NAV / Reserve-based"
    assert verdict.secondary == "FCFF/WACC DCF"
    assert any("finite reserves" in r.lower() or "commodity-driven" in r.lower() for r in verdict.reasons)


def test_unknown_or_missing_metadata_unsupported():
    """Missing or unrecognized domain / metadata fails closed as unsupported."""
    assert evaluate({}).primary == "unsupported"
    assert evaluate({"domain": "unknown"}).primary == "unsupported"
    assert evaluate({"domain": "unsupported"}).primary == "unsupported"
    assert evaluate({"model_profile": "unsupported"}).primary == "unsupported"


def test_holding_dissimilar_segments():
    """Holding company with dissimilar lines requires SOTP primary when segments > 1."""
    # Dissimilar with multiple segments -> SOTP primary
    verdict_multi = evaluate({"domain": "holding_dissimilar", "segments_count": 3})
    assert verdict_multi.primary == "SOTP"
    assert any("dissimilar" in r.lower() for r in verdict_multi.reasons)

    # Dissimilar with single segment -> candidates proceed to Gate 1 (DCF)
    verdict_single = evaluate({
        "domain": "holding_dissimilar",
        "segments_count": 1,
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "equity_positive": True,
        "has_steady_state_3y": True,
    })
    assert verdict_single.primary == "FCFF/WACC DCF"


def test_gate1_subgates():
    """Gate 1: profitability, leverage breach, and negative equity edge cases."""
    # Gate 1b: EBIT < 2/3y -> Relative only
    v_ebit = evaluate({
        "domain": "single_business",
        "filing_history_years": 5,
        "ebit_positive_count": 1,
        "equity_positive": True,
    })
    assert v_ebit.primary == "Relative Valuation"
    assert "1b_profitability" in v_ebit.gates_failed

    # Gate 1c: Leverage breach -> DCF + mandatory Relative cross-check
    v_lev = evaluate({
        "domain": "single_business",
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "d_de_ratio": 0.85,
        "equity_positive": True,
    })
    assert v_lev.primary == "FCFF/WACC DCF"
    assert v_lev.secondary == "Relative Valuation"
    assert "1c_capital_structure" in v_lev.gates_failed

    # Gate 1d: Negative equity -> Relative Valuation (EV multiples only)
    v_neg_eq = evaluate({
        "domain": "single_business",
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "equity_positive": False,
    })
    assert v_neg_eq.primary == "Relative Valuation"
    assert "1d_equity_base" in v_neg_eq.gates_failed


def test_gate2_high_nci():
    """Gate 2: NCI > 40% makes SOTP primary."""
    v = evaluate({
        "domain": "single_business",
        "nci_pct": 45.0,
        "filing_history_years": 5,
        "ebit_positive_count": 3,
        "equity_positive": True,
    })
    assert v.primary == "SOTP"
    assert "2_nci" in v.gates_failed


def test_gate4_lifecycle_stages():
    """Gate 4: decline -> P/BV; pre-revenue/high growth -> EV/Sales."""
    v_dec = evaluate({"domain": "single_business", "life_cycle_stage": "decline"})
    assert v_dec.primary == "P/BV"

    v_pre = evaluate({"domain": "single_business", "life_cycle_stage": "pre_revenue"})
    assert v_pre.primary == "EV/Sales"

    v_hg = evaluate({"domain": "single_business", "life_cycle_stage": "high_growth_pre_profit"})
    assert v_hg.primary == "EV/Sales"


def test_gate5_output_sanity():
    """Gate 5: upside extremes trigger Review Required; tv_share > 80% flags warning without override."""
    # Extreme upside > 100%
    v_up = evaluate({"domain": "single_business", "upside_pct": 115.0})
    assert v_up.rating_override == "Review Required"
    assert "5_upside_extreme" in v_up.gates_failed

    # Extreme downside < -50%
    v_down = evaluate({"domain": "single_business", "upside_pct": -55.0})
    assert v_down.rating_override == "Review Required"
    assert "5_downside_extreme" in v_down.gates_failed

    # High TV share (>80%) -> flag without rating override
    v_tv = evaluate({"domain": "single_business", "terminal_value_pct_of_ev": 82.0})
    assert v_tv.rating_override is None
    assert "5_tv_share_high" in v_tv.gates_failed

    # Exit multiple outside peer range -> flag for cross check
    v_exit = evaluate({
        "domain": "single_business",
        "implied_exit_ev_ebitda": 15.0,
        "peer_exit_low": 6.0,
        "peer_exit_high": 10.0,
    })
    assert "5_exit_multiple_out_of_range" in v_exit.gates_failed


def test_valuation_build_attaches_gate_verdict():
    """valuation.build() output must carry gate_verdict dictionary."""
    doc_in, _ = intake.load("BBCA")
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    assert "gate_verdict" in va
    assert isinstance(va["gate_verdict"], dict)
    assert "primary" in va["gate_verdict"]
    assert "gates_passed" in va["gate_verdict"]
