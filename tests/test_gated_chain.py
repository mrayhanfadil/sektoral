"""Phase 1 acceptance: gate-driven chain, stage validator, Method Gate 5 shared constant."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import gate_thresholds as GT, method_chain as MC, model_profiles as MP, stage as ST


def test_method_gate5_shared_constant():
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
        "fcff_dcf", "relative_pe", "pe_fy_scenario", "pbv_book")
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


def test_method_gate5_percent_is_never_read_as_ratio():
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


def test_method_gate5_exit_range_is_own_ev_ebitda_history_not_peer_pe():
    from app import intake as I
    doc_in, _ = I.load("SSIA", as_of="2026-09-24")
    values = [h["value"] for h in doc_in["historical_ev_ebitda"]]
    assert values and all(0 < v <= 100 for v in values) and len(values) <= 5
    from app import forecast, valuation
    va = valuation.build(doc_in, forecast.build(doc_in))
    gate = va["gate_inputs"]
    assert (gate["peer_exit_low"], gate["peer_exit_high"]) == (min(values), max(values))


def test_holding_sotp_values_listed_stakes_at_market_and_the_rest_at_book():
    listed = [{"ticker": "SUB", "segment": "Konstruksi", "stake": 0.6, "market_cap": 1000.0,
               "book_equity": 800.0}]
    c = MC.holding_sotp(listed, parent_equity=5000.0, shares=10.0)
    d = c["detail"]
    assert c["status"] == "sufficient"
    assert d["remainder_book"] == 5000.0 - 0.6 * 800.0
    assert d["total"] == 0.6 * 1000.0 + d["remainder_book"]
    assert [x["discount"] for x in d["discounts"]] == [0.0, 0.2, 0.3]
    assert c["per_share_down"] < c["per_share"]
    assert MC.holding_sotp([], 5000.0, 10.0)["status"] == "insufficient"


def test_ssia_nci_band_runs_holding_sotp_as_cross_check_not_target(tmp_path):
    from app import build as B
    doc = B.build("SSIA", tmp_path, as_of="2026-09-24")
    chain = doc["exhibits"]
    sotp = next(e for e in chain if e["judul"].startswith("Cross-check SOTP holding"))
    labels = [r[0] for r in sotp["data"]["rows"]]
    assert labels[0].startswith("PT Nusa Raya Cipta Tbk (NRCA)")
    assert "Total nilai SOTP" in labels
    table = next(e for e in chain if e["judul"] == "Rantai metode valuasi")
    assert any(r[0].startswith("x. ") and "Method Gate 2" in r[3] for r in table["data"]["rows"])
    assert doc["meta"].get("method") != "Holding SOTP"


def test_bank_chain_puts_justified_pbv_before_peer_per():
    order = MC.chain_for(_verdict("DDM / Excess Return"), "financial_ddm")
    assert order.index("pbv_roe_fy") < order.index("relative_pe") < order.index("pe_fy_scenario")


def test_justified_pbv_gate_needs_coe_and_roe_above_growth():
    from app import release
    base = {"model_profile": "financial_ddm"}
    ok = release.assess_pbv_roe_fy(base, {}, {"detail": {"equity": 100.0, "coe": 0.109,
                                                         "g": 0.035, "roe": 0.2, "shares": 10}},
                                   "validated")
    assert not any("growth" in b for b in ok["blockers"])
    assert not any(b.startswith("peer PER") for b in ok["blockers"])
    bad = release.assess_pbv_roe_fy(base, {}, {"detail": {"equity": 100.0, "coe": 0.03,
                                                          "g": 0.035, "roe": 0.02, "shares": 10}},
                                    "validated")
    assert any("cost of equity must exceed" in b for b in bad["blockers"])
    assert any("ROE does not exceed" in b for b in bad["blockers"])
    other = release.assess_pbv_roe_fy({"model_profile": "going_concern_fcff"}, {}, {"detail": {}},
                                      "validated")
    assert any("bank method" in b for b in other["blockers"])


def test_ps_peer_uses_market_cap_over_revenue_in_band():
    peers = [{"ps": v} for v in (0.5, 1.0, 1.5, 2.0, 45.0, None)]
    c = MC.ps_peer(peers, revenue_fwd=1000.0, shares=100.0, market_cap=2000.0)
    assert c["status"] == "sufficient" and c["detail"]["peer_count"] == 4
    assert c["per_share"] == c["detail"]["median_ps"] * 10.0
    assert MC.ps_peer(peers[:2], 1000.0, 100.0, 2000.0)["status"] == "insufficient"
    from app import intake as I
    doc_in, _ = I.load("JPFA", as_of="2026-09-24")
    assert any(p.get("ps") for p in doc_in["peers"])


def test_pbv_book_gate_requires_asset_heavy_issuer_and_three_pb_peers():
    from app import release
    base = {"model_profile": "going_concern_fcff"}
    ok = release.assess_pbv_book(base, {}, {"detail": {"equity": 100.0, "shares": 10,
                                                       "fixed_asset_share": 0.64,
                                                       "peer_count": 6}}, "validated")
    assert not any(k in b for b in ok["blockers"]
                   for k in ("fixed assets", "peer P/BV", "peer PER", "parent equity"))
    light = release.assess_pbv_book(base, {}, {"detail": {"equity": 100.0, "shares": 10,
                                                          "fixed_asset_share": 0.2,
                                                          "peer_count": 2}}, "validated")
    assert any("fixed assets below half" in b for b in light["blockers"])
    assert any("peer P/BV set" in b for b in light["blockers"])


def test_going_concern_chain_ends_with_book_value_fallback():
    order = MC.chain_for(_verdict("FCFF/WACC DCF"), "going_concern_fcff")
    assert order[-1] == "pbv_book" and order.index("pe_fy_scenario") < order.index("pbv_book")


# ------------------------------------------- Method Gate 3 ramping -> forward EV/EBITDA

_HEALTHY = {"filing_history_years": 6, "ebit_positive_count": 3, "d_de_ratio": 0.2,
            "net_debt_to_ebitda": 0.5, "icr": 8.0, "equity_positive": True, "nci_pct": 2.0,
            "life_cycle_stage": "mature"}


def test_method_gate3_ramping_verdict_routes_to_forward_ev_ebitda_chain():
    v = MP.evaluate(dict(_HEALTHY, domain="going_concern_fcff", has_steady_state_3y=False))
    assert v.primary == "Relative Valuation" and v.ramping is True
    assert any(r.startswith("3 newly commissioned") for r in v.reasons)
    # Same order as the thin-history branch (spec §4.1a), dataclass or stored dict.
    assert MC.chain_for(v, "going_concern_fcff") == ("ev_ebitda_peer", "pe_fy_scenario")
    assert MC.chain_for(v.to_dict(), "going_concern_fcff") == ("ev_ebitda_peer", "pe_fy_scenario")
    steady = MP.evaluate(dict(_HEALTHY, domain="going_concern_fcff", has_steady_state_3y=True))
    assert steady.ramping is False
    assert MC.chain_for(steady, "going_concern_fcff")[0] == "fcff_dcf"


def test_method_gate1b_chronic_losses_keep_ev_sales_not_the_ramping_chain():
    v = MP.evaluate(dict(_HEALTHY, domain="going_concern_fcff", ebit_positive_count=1,
                         has_steady_state_3y=True))
    assert v.primary == "Relative Valuation" and v.ramping is False
    assert MC.chain_for(v, "going_concern_fcff") == ("ev_sales_peer", "ps_peer")


def test_structural_primaries_ignore_the_ramping_gate():
    holding = MP.evaluate(dict(_HEALTHY, domain="holding_dissimilar", segments_count=3,
                               has_steady_state_3y=False))
    assert (holding.primary, holding.ramping) == ("SOTP", False)
    assert MC.chain_for(holding, "going_concern_fcff")[0] == "holding_sotp"
    miner = MP.evaluate(dict(_HEALTHY, domain="finite_life_mining", has_steady_state_3y=False))
    assert (miner.primary, miner.ramping) == ("NAV / Reserve-based", False)
    assert MC.chain_for(miner, "finite_life_mining")[0] == "sotp_lom"
    bank = MP.evaluate(dict(_HEALTHY, domain="financial_ddm", has_steady_state_3y=False))
    assert (bank.primary, bank.ramping) == ("DDM / Excess Return", False)
    assert MC.chain_for(bank, "financial_ddm")[0] == "ddm"
    # The flag alone never moves a non-Relative primary.
    assert MC.chain_for({"primary": "SOTP", "ramping": True}, "going_concern_fcff")[0] == "holding_sotp"


def test_method_gate4_stage_still_overrides_a_ramping_primary():
    v = MP.evaluate(dict(_HEALTHY, domain="going_concern_fcff", has_steady_state_3y=False,
                         life_cycle_stage="decline"))
    assert v.primary == "P/BV"
    assert MC.chain_for(v, "going_concern_fcff")[0] == "pbv_relative"


def _peer_report(year_rows):
    return {"financials": {"historical_financials": year_rows}}


def test_peer_ev_uses_sectors_market_cap_debt_cash_and_latest_fy_only(monkeypatch):
    from app import cache, intake as I
    reports = {
        "OK": _peer_report([{"year": 2024, "total_debt": 1.0, "cash_and_equivalents": 1.0,
                             "ebitda": 1.0},
                            {"year": 2025, "total_debt": 300.0, "cash_and_equivalents": 100.0,
                             "ebitda": 120.0}]),
        # Latest year lacks debt: no fallback to an older year.
        "GAP": _peer_report([{"year": 2024, "total_debt": 5.0, "cash_and_equivalents": 1.0,
                              "ebitda": 10.0},
                             {"year": 2025, "total_debt": None, "cash_and_equivalents": 1.0,
                              "ebitda": 10.0}]),
        "LOSS": _peer_report([{"year": 2025, "total_debt": 10.0, "cash_only": 5.0,
                               "ebitda": -3.0}]),
    }
    monkeypatch.setattr(cache, "company_report", lambda t: reports.get(t))
    ok = I._peer_ev("OK.JK", 1000.0)
    assert ok["ev"] == 1000.0 + 300.0 - 100.0 and ok["ev_year"] == 2025
    assert ok["ev_ebitda"] == 1200.0 / 120.0 and ok["ev_status"] == "ok"
    assert ok["ev_source"].startswith("Sectors:") and "/company/report/OK/" in ok["ev_source"]
    gap = I._peer_ev("GAP.JK", 1000.0)
    assert gap["ev_status"] == "balance_incomplete" and "ev_ebitda" not in gap
    loss = I._peer_ev("LOSS.JK", 1000.0)
    assert loss["ev_status"] == "not_meaningful" and loss["ev_ebitda"] is None
    assert I._peer_ev("NONE.JK", 1000.0) == {"ev_status": "report_not_cached"}
    assert I._peer_ev("OK.JK", None) == {"ev_status": "market_cap_missing"}


def test_unreadable_peer_report_keeps_the_peer_row(monkeypatch):
    from app import cache, intake as I

    def broken(_ticker):
        raise ValueError("bad payload")
    monkeypatch.setattr(cache, "company_report", broken)
    rep = {"peers": [{"peers_data": {"companies": [
        {"symbol": "AAA.JK", "pe_ttm": 10.0, "pb_mrq": 1.5, "market_cap": 100.0,
         "total_revenue": 50.0, "group": ["peer"]}]}}]}
    peers, median_pe, _ = I._peers(rep, "TGT")
    assert [p["symbol"] for p in peers] == ["AAA.JK"] and median_pe == 10.0
    assert peers[0]["ev_status"] == "report_unreadable"


def test_ev_ebitda_peer_labels_sectors_peers_and_the_real_bridge_source():
    peers = [{"ev_ebitda": v, "ev_status": "ok", "ev_source_kind": "sectors"}
             for v in (6.0, 8.0, 10.0)]
    c = MC.ev_ebitda_peer(peers, ebitda_fwd=100.0, shares=10.0, market_cap=700.0,
                          net_debt=50.0, net_debt_source="data Sectors FY2025")
    assert c["status"] == "sufficient"
    assert c["per_share"] == (8.0 * 100.0 - 50.0) / 10.0
    assert any("peer dari data Sectors" in label for label in c["labels"])
    assert "bridge net debt dari data Sectors FY2025" in c["labels"]
    assert not any("neraca resmi" in label for label in c["labels"])
    assert c["detail"]["peer_source"] == "data Sectors"
    official = MC.ev_ebitda_peer(peers, 100.0, 10.0, 700.0, 50.0, net_debt_source="neraca resmi")
    assert "bridge net debt dari neraca resmi" in official["labels"]


def test_ev_ebitda_peer_names_uncached_peer_reports():
    peers = [{"ev_status": "report_not_cached"}] * 8 + [{"ev_status": "ok", "ev_ebitda": 9.0}]
    c = MC.ev_ebitda_peer(peers, 100.0, 10.0, 700.0)
    assert c["status"] == "insufficient"
    assert "(1 < 3; laporan Sectors atau snapshot Yahoo 8/9 peer belum tersedia)" in c["reasons"][0]
    assert MC.reader_reason(c["reasons"][0]) == "peer EV/EBITDA belum tersedia di cache"


_RAMPING_STAGE = {"stage_classification": {
    "life_cycle_stage": "mature", "has_steady_state_3y": False,
    "commodity_price_driven": False, "dissimilar_segments": 1,
    "rationale": "Pendapatan melonjak dari basis kecil setelah aset baru beroperasi; "
                 "belum ada tiga tahun kondisi stabil.",
    "source_ids": ["official"]}}


def test_inet_and_gmfi_ramping_stage_moves_the_chain_off_dcf(tmp_path, monkeypatch):
    from app import forecast, intake, peer_fundamentals, valuation
    for ticker in ("INET", "GMFI"):
        doc_in, _ = intake.load(ticker, as_of="2026-09-24")
        fc = forecast.build(doc_in)
        steady = valuation.build(doc_in, fc)
        assert steady["method_chain"]["order"][0] == "fcff_dcf"
        va = valuation.build(doc_in, fc, assumption_plan=_RAMPING_STAGE)
        assert va["gate_verdict"]["primary"] == "Relative Valuation"
        assert va["gate_verdict"]["ramping"] is True
        chain = va["method_chain"]
        assert chain["order"] == ["ev_ebitda_peer", "pe_fy_scenario"]
        assert chain["verdict_order"] == ["ev_ebitda_peer", "pe_fy_scenario"]
        first = chain["trace"][0]
        assert first["key"] == "ev_ebitda_peer" and first["status"] == "insufficient"
        # No peer of either issuer has a cached Sectors company report, and
        # without a Yahoo snapshot store the multiple stays unavailable.
        peers = doc_in["peers"]
        assert peers and all(p["ev_status"] == "report_not_cached" for p in peers)
        assert f"{len(peers)}/{len(peers)} peer belum tersedia" in first["reasons"][0]


def test_ramping_going_concern_publishes_on_forward_ev_ebitda_peer(tmp_path, monkeypatch):
    """JPFA under a ramping stage with Sectors peer EV cached (synthetic here):
    the forward EV/EBITDA peer values the agent's FY EBITDA scenario behind
    its own gate and sets the target; DCF and PER stay out of the chain."""
    import itertools
    from app import build, intake as I
    multiples = itertools.cycle([6.0, 7.0, 8.0, 9.0, 10.0])
    monkeypatch.setattr(I, "_peer_ev", lambda symbol, mcap: {
        "ev_ebitda": next(multiples), "ev_status": "ok", "ev_year": 2025,
        "ev_source_kind": "sectors"})
    doc_in, _ = I.load("JPFA", as_of="2026-09-24")
    actual = doc_in["latest_official_actual"]
    metrics = actual["metrics"]
    plan = {"news_effects": [], "earnings_scenario": {
        "h2_revenue_to_h1": 1.05,
        "h2_net_margin_pct": metrics["net_profit"] / metrics["revenue"] * 100,
        "fy_ebitda_margin_pct": 10.0, "fy_capex_to_revenue_pct": 4.0,
        "rationale": "H2 mengikuti run-rate 1H dengan kenaikan musiman ringan.",
        "source_ids": ["official"], "source_url": actual["source_url"],
        "published_at": actual["published_at"],
        "thesis_points": ["Kapasitas baru menaikkan volume H2.",
                          "Margin EBITDA menuju tingkat peer matang."],
        "catalysts_risks": [],
        "key_risks": [
            {"category": "Komoditas", "headline": "Harga jagung dan bungkil kedelai",
             "explanation": "Bahan baku pakan setara 60% beban pokok; kenaikan harga jagung "
                            "10% menekan margin kotor sekitar 2pp tanpa kenaikan harga jual.",
             "source_ids": ["official"]},
            {"category": "Operasi", "headline": "Ramp-up kapasitas baru",
             "explanation": "Utilisasi pabrik baru di bawah 70% menahan margin EBITDA di "
                            "bawah tingkat peer matang yang dipakai multiple.",
             "source_ids": ["official"]},
            {"category": "Pendanaan", "headline": "Utang bank jangka pendek",
             "explanation": "Utang jangka pendek Rp5.000 miliar jatuh tempo dalam 12 bulan; "
                            "kenaikan bunga 100bp menambah beban bunga sekitar Rp50 miliar.",
             "source_ids": ["official"]}]},
        **_RAMPING_STAGE}
    doc = build.build("JPFA", tmp_path, as_of="2026-09-24", assumption_plan=plan,
                      assumption_status="validated")
    chain = doc["log_gate"]["release"]["method_chain"]
    assert chain == {"selected": "ev_ebitda_peer", "route": "primary"}
    assert doc["meta"]["status"] == "distributable_assumption_led"
    assert doc["harness"]["status"] == "distributable_assumption_led"
    assert doc["meta"]["tp"] and doc["meta"]["rating"] in {"Buy", "Hold", "Sell"}
    assert doc["method"].startswith("FY26F EV/EBITDA median peer x EBITDA skenario analis")
    titles = [e["judul"] for e in doc["exhibits"]]
    assert "Target harga: EV/EBITDA peer x EBITDA FY26F" in titles
    assert "Target harga: PER peer x EPS FY26F" not in titles
    target = next(e for e in doc["exhibits"] if e["judul"].startswith("Target harga: EV/EBITDA"))
    assert [r[0] for r in target["data"]["rows"]] == ["Kuartil bawah", "Median (basis)", "Kuartil atas"]
    assert target["catatan_sumber"].startswith("Sumber: EV/EBITDA FY terakhir tiap peer dari data Sectors")
    rows = next(e for e in doc["exhibits"] if e["judul"] == "Rantai metode valuasi")["data"]["rows"]
    assert rows[0][0] == "1. EV/EBITDA peer (utama)" and rows[0][1] == "Terpilih"
    assert not any("DCF" in r[0] for r in rows)
    cover = doc["cover"]["paragraf"][2]
    assert cover["judul"] == "Target harga berbasis EV/EBITDA peer"
    assert "EV/EBITDA peer forward" in cover["isi"] and "PER median" not in cover["isi"]
    page = next(p for p in doc["bagian"] if p["judul"] == "Target harga berbasis EV/EBITDA peer")
    assert page["exhibit"][1]["judul"] == "Target harga: EV/EBITDA peer x EBITDA FY26F"


# ------------------------------------------- Yahoo Finance peer fallback

class _Frame:
    """Minimal stand-in for the pandas frames yfinance returns."""
    def __init__(self, rows, columns):
        self.index, self.columns, self._rows = list(rows), list(columns), rows
        self.empty = not rows

    class _Loc:
        def __init__(self, frame):
            self.frame = frame

        def __getitem__(self, key):
            row, column = key
            return self.frame._rows[row][self.frame.columns.index(column)]
    loc = property(_Loc)


class _FakeTicker:
    def __init__(self, symbol):
        self.symbol = symbol
        cols = ["2025-12-31", "2024-12-31"]
        self.balance_sheet = _Frame({"Total Debt": [None, 300.0],
                                     "Cash And Cash Equivalents": [50.0, 100.0]}, cols)
        self.income_stmt = _Frame({"EBITDA": [130.0, 120.0], "Total Revenue": [900.0, 800.0]},
                                  cols)
        self.info = {"financialCurrency": "IDR", "marketCap": 5000.0}


def test_yahoo_snapshot_takes_the_latest_year_with_debt_cash_and_ebitda_together(tmp_path):
    from app import peer_fundamentals as PF
    data = PF.fetch("MORA", ticker_factory=_FakeTicker)
    # FY2025 lacks debt, so FY2024 is used for every field; no mixing of years.
    assert data["fiscal_year"] == 2024 and data["period_end"] == "2024-12-31"
    assert (data["total_debt"], data["cash_and_equivalents"], data["ebitda"]) == (300.0, 100.0, 120.0)
    assert data["source"] == "Yahoo Finance MORA.JK annual statements FY2024"
    assert data["symbol"] == "MORA" and data["currency"] == "IDR"
    result = PF.refresh(["MORA", "BAD"], db=tmp_path, pause=0,
                        fetcher=lambda s: PF.fetch(s, _FakeTicker) if s == "MORA" else 1 / 0)
    assert list(result["stored"]) == ["MORA"] and "BAD" in result["failed"]
    assert PF.load("MORA.JK", db=tmp_path)["ebitda"] == 120.0
    # A snapshot that does not carry Yahoo provenance is never read.
    (tmp_path / "XXX.json").write_text('{"source": "Sectors", "total_debt": 1, '
                                       '"cash_and_equivalents": 1, "ebitda": 1, "fiscal_year": 2025}')
    assert PF.load("XXX", db=tmp_path) is None


def test_peer_ev_falls_back_to_a_yahoo_snapshot_and_says_so(tmp_path, monkeypatch):
    from app import cache, intake as I, peer_fundamentals as PF
    monkeypatch.setattr(cache, "company_report", lambda t: None)
    PF.refresh(["MORA"], db=tmp_path, pause=0,
               fetcher=lambda s: PF.fetch(s, _FakeTicker))
    row = I._peer_ev("MORA.JK", 1000.0)
    assert row["ev_source_kind"] == "yahoo" and row["ev_status"] == "ok"
    assert row["ev"] == 1000.0 + 300.0 - 100.0 and row["ev_ebitda"] == 1200.0 / 120.0
    assert row["ev_year"] == 2024
    assert "Yahoo Finance MORA.JK" in row["ev_source"] and not row["ev_source"].startswith("Sectors")
    assert I._peer_ev("NONE.JK", 1000.0) == {"ev_status": "report_not_cached"}
    usd = dict(PF.load("MORA", db=tmp_path), currency="USD", symbol="USDX")
    __import__("app.store").store.put(PF.COLLECTION, "USDX", usd, tmp_path)
    assert I._peer_ev("USDX", 1000.0)["ev_status"] == "currency_mismatch"


def test_peer_ev_source_wording_never_calls_yahoo_data_sectors():
    sectors = {"ev_ebitda": 6.0, "ev_source_kind": "sectors"}
    yahoo = {"ev_ebitda": 8.0, "ev_source_kind": "yahoo"}
    unknown = {"ev_ebitda": 9.0}
    assert MC.peer_ev_sources([sectors, sectors]) == "data Sectors"
    assert MC.peer_ev_sources([yahoo]) == "Yahoo Finance"
    assert MC.peer_ev_sources([sectors, yahoo]) == "data Sectors dan Yahoo Finance"
    assert MC.peer_ev_sources([unknown]) == "sumber tidak tercatat"
    assert MC.peer_ev_sources([{"ev_status": "report_not_cached"}]) == "tanpa peer"
    c = MC.ev_ebitda_peer([yahoo, yahoo, yahoo], 100.0, 10.0, 700.0)
    assert c["detail"]["peer_source"] == "Yahoo Finance"
    assert any("peer dari Yahoo Finance" in label for label in c["labels"])
    assert not any("dari data Sectors" in label for label in c["labels"])
