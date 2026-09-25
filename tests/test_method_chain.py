"""Rantai metode valuasi (§4.1a): primary → fallback → draft."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import fmt, intake, forecast, method_chain as MC, release, valuation  # noqa: E402
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
    # Method Gate 5: upside > +100% stops chain (framework thresholds, shared constant).
    chain = MC.run("going_concern_fcff", {"fcff_dcf": _ok("fcff_dcf", 2200),
                                          "relative_pe": _ok("relative_pe", 1050)}, PRICE)
    assert chain["selected"] == "fcff_dcf" and chain["extreme"] is True
    assert chain["trace"][0]["decision"] == "stop_extreme"
    assert chain["trace"][1]["decision"] == "cross_check"
    assert "extreme fcff_dcf" in MC.summary_blocker(chain)
    # +80% is no longer extreme (needs sourced thesis only above +100%/-50%).
    calm = MC.run("going_concern_fcff", {"fcff_dcf": _ok("fcff_dcf", 1800),
                                         "relative_pe": _ok("relative_pe", 1050)}, PRICE)
    assert calm["extreme"] is False
    assert calm["trace"][0]["decision"] == "selected"
    # Downside beyond -50% is extreme.
    down = MC.run("going_concern_fcff", {"fcff_dcf": _ok("fcff_dcf", 400),
                                         "relative_pe": _ok("relative_pe", 1050)}, PRICE)
    assert down["extreme"] is True
    assert down["trace"][0]["decision"] == "stop_extreme"


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
    assert va["tp"] == fmt.tick(chain["trace"][1]["per_share"])
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
    assert not any("S3.8" in b for b in result["blockers"])


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
                   price_provenance={"source": "sectors_cache /company/report/UJI/ overview",
                                     "date": "2026-09-22", "kind": "sectors_cache",
                                     "verified": True},
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
    # pbv_book (asset-heavy fallback) follows and is not needed once PER FY is selected.
    assert [t["decision"] for t in chain["trace"]] == ["skipped", "skipped", "selected",
                                                       "not_needed"]
    assert va["release"]["status"] == "distributable_assumption_led"
    eps = 9e12 / test_valtables.SHARES
    assert va["tp"] == fmt.tick(2.8 * eps)  # median peer PER, IDX tick
    assert va["tp_down"] == fmt.tick(2.65 * eps)  # interpolated lower quartile
    assert va["method"].startswith("FY26F PER median peer x EPS skenario analis")
    assert abs(va["implied"]["per"] - va["tp"] / eps) < 1e-9
    result = runner.run_all(intake_, fc, va, assumption_status="validated")
    assert result["gates"]["engine_status"] == "distributable_assumption_led"
    assert result["log_gate"]["release"]["route"] == "analyst_target"
    # The harness does not take the agent status from the engine's trace.
    unvalidated = runner.run_all(intake_, fc, va)
    assert unvalidated["log_gate"]["release"]["route"] != "analyst_target"


def test_cache_close_needs_verified_provenance():
    intake_, fc = _earnings_fixture(None)
    unverified = dict(intake_, price_provenance=dict(intake_["price_provenance"], verified=False))
    va = valuation.build(unverified, fc, assumption_status="validated")
    assert va["method_chain"]["selected"] is None
    assert any("fresh sourced close" in r for t in va["method_chain"]["trace"]
               for r in t["reasons"])


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
    # Method Gate 5 points to relative valuation: the peer P/S cross-check is recorded.
    checks = va["method_chain"].get("cross_checks") or []
    assert [x["key"] for x in checks] == ["ps_peer"] and checks[0]["why"].startswith("Method Gate 5")


def test_mining_profile_never_gets_earnings_scenario():
    doc_in, _ = intake.load("AMMN")
    plan = {"earnings_scenario": {"h2_revenue_to_h1": 1.0, "h2_net_margin_pct": 10,
                                  "rationale": "x" * 50, "source_ids": ["official"]}}
    assert forecast.build(doc_in, assumption_plan=plan)["earnings_scenario"] is None


def test_jpfa_report_holds_value_when_template_gate_fails(tmp_path, monkeypatch):
    from app import build
    doc_in, _ = intake.load("JPFA", as_of="2026-09-24")
    actual = doc_in["latest_official_actual"]
    metrics = actual["metrics"]
    plan = {"news_effects": [], "earnings_scenario": {
        "h2_revenue_to_h1": 1.05,
        "h2_net_margin_pct": metrics["net_profit"] / metrics["revenue"] * 100,
        "rationale": "H2 mengikuti run-rate 1H dengan kenaikan musiman ringan.",
        "source_ids": ["official"], "source_url": actual["source_url"],
        "published_at": actual["published_at"],
        "thesis_points": ["Volume pakan dan unggas menjaga pendapatan H2 setara 1H.",
                          "Margin laba bersih bertahan karena biaya bahan baku stabil."],
        "catalysts_risks": [
            {"item": "Harga jagung", "timing": "H2 2026",
             "driver_path": "Kenaikan harga jagung menaikkan biaya pakan dan menekan margin.",
             "direction": "Negatif", "source_ids": ["official"]},
            {"item": "Permintaan unggas", "timing": "Akhir tahun",
             "driver_path": "Permintaan musiman menaikkan volume dan pendapatan kuartal empat.",
             "direction": "Positif", "source_ids": ["official"]}],
        "key_risks": [
            {"category": "Komoditas", "headline": "Harga jagung dan bungkil kedelai",
             "explanation": "Bahan baku pakan setara 60% beban pokok; kenaikan harga jagung "
                            "10% menekan margin kotor sekitar 2pp tanpa kenaikan harga jual.",
             "source_ids": ["official"]},
            {"category": "Operasi", "headline": "Oversupply ayam pedaging",
             "explanation": "Populasi DOC naik 8% yoy; kelebihan pasokan menurunkan harga "
                            "livebird dan margin segmen peternakan komersial.",
             "source_ids": ["official"]},
            {"category": "Pendanaan", "headline": "Utang bank jangka pendek",
             "explanation": "Utang jangka pendek Rp5.000 miliar jatuh tempo dalam 12 bulan; "
                            "kenaikan bunga 100bp menambah beban bunga sekitar Rp50 miliar.",
             "source_ids": ["official"]}]},
        "outyear_scenario": [
            {"year": 2027 + i, "revenue_growth_pct": 6.0, "ebitda_margin_pct": None,
             "net_income_margin_pct": 7.0, "capex_to_revenue_pct": None,
             "rationale": "Pertumbuhan volume moderat dengan margin sedikit normal.",
             "source_ids": ["official"]} for i in range(4)]}
    doc = build.build("JPFA", tmp_path, as_of="2026-09-24", assumption_plan=plan,
                      assumption_status="validated")
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert doc["log_gate"]["release"]["status"] == "distributable_assumption_led"
    assert doc["harness"]["status"] == "draft_non_distributable"
    assert doc["harness"]["blockers"]
    assert "tp" not in doc["meta"] and "rating" not in doc["meta"]
    titles = [e["judul"] for e in doc["exhibits"]]
    assert "Skenario laba FY26F: aktual 1H dan asumsi H2" not in titles
    assert not any("Target harga" in title for title in titles)
    chain = next(e for e in doc["exhibits"] if e["judul"] == "Rantai metode valuasi")
    value_column = next(i for i, label in enumerate(chain["data"]["cols"])
                        if "saham" in str(label).lower())
    assert all(row[value_column] in {"-", "Ditahan"} for row in chain["data"]["rows"]
               if len(row) > value_column and row[value_column]), chain["data"]
    release_row = next((row for row in chain["data"]["rows"]
                        if str(row[0]).lower().startswith("keputusan rilis")), None)
    if release_row:
        assert "ditahan" in str(release_row[1]).lower()
    assert "Skenario laba FY27F-FY30F" not in titles
    risk = next(e for e in doc["exhibits"] if e["judul"].startswith("Katalis"))
    assert risk["data"]["rows"][0][0] == "Harga jagung"
    assert doc["cover"]["bullets"][1].startswith("Skenario FY26F:")
    assert "asumsi analis, bukan panduan emiten" in doc["cover"]["bullets"][1]
    assert doc["exhibits"][0]["tipe"] == "price_chart"
    key_fin = doc["exhibits"][1]
    assert key_fin["judul"] == "Key Financials"
    assert [r["judul"] for r in doc["risks"]][0] == "Harga jagung dan bungkil kedelai"
    assert "Nilai per saham dan sensitivitas valuasi ditahan" in \
        doc["cover"]["paragraf"][-1]["isi"]
    risk_page = next(p for p in doc["bagian"] if p["judul"].startswith("Katalis"))
    assert risk_page["risks"] == doc["risks"] and risk_page["risks_after"] == 1
    labels = [row[0] for row in key_fin["data"]["rows"]]
    assert labels.count("EPS (Rp)") == 1 and labels.count("PER (x)") == 1
    assert labels.index("Pertumbuhan EPS (%)") == labels.index("EPS (Rp)") + 1
    assert not any(all(cell in ("-", "NA") for cell in row[1:])
                   for row in key_fin["data"]["rows"])
    fy27 = key_fin["data"]["cols"].index("FY27F")
    assert all(row[fy27] != "-" for row in key_fin["data"]["rows"]
               if row[0].startswith(("Pendapatan", "Laba bersih", "EPS", "PER")))
    body = " ".join(p for page in doc["bagian"] for p in page["paragraf"])
    assert "Pisahkan driver" not in " ".join(doc["cover"]["bullets"])
    assert "belum cukup untuk menerbitkan" not in body
    # Struktur tie-out: net profit is the same in Key Financials and the income statement.
    number = lambda cell: float(cell.replace(".", "").replace(",", "."))
    income = next(e for e in doc["exhibits"] if e["judul"] == "Laba rugi")
    is_row = dict(zip(income["data"]["cols"], next(
        r for r in income["data"]["rows"] if r[0] == "Laba bersih")))
    kf_row = dict(zip(key_fin["data"]["cols"], next(
        r for r in key_fin["data"]["rows"] if r[0].startswith("Laba bersih"))))
    shared = [("2024A", "2024A"), ("2025A", "2025A"), ("FY26F", "FY26F"), ("FY27F", "FY27F")]
    for is_col, kf_col in shared:
        assert abs(number(is_row[is_col]) - number(kf_row[kf_col])) <= 1, (is_col, is_row, kf_row)
    assert not any("nilai wajar per saham" in str(e).lower() for e in doc["exhibits"])
    # A pack that takes its share count from elsewhere names that source.
    from app import issuer_evidence
    original = issuer_evidence.load

    def relabelled(ticker, as_of):
        evidence = original(ticker, as_of)
        evidence["balance_sheet"]["shares_source"] = "Yahoo Finance (diambil 2026-09-24)"
        return evidence
    monkeypatch.setattr(issuer_evidence, "load", relabelled)
    other = build.build("JPFA", tmp_path / "relabelled", as_of="2026-09-24",
                        assumption_plan=plan, assumption_status="validated")
    key_note = next(e for e in other["exhibits"] if e["judul"] == "Key Financials")["catatan_sumber"]
    assert "dari Yahoo Finance (diambil 2026-09-24)" in key_note
    monkeypatch.setattr(issuer_evidence, "load", original)
    # Without the validated agent scenario the same issuer stays draft.
    draft = build.build("JPFA", tmp_path, as_of="2026-09-24")
    assert draft["meta"]["status"] == "draft_non_distributable"


# --------------------------------------------- PR #4 review fixes (in PR #5)

def test_quartiles_are_interpolated_not_min_max():
    q1, med, q3 = MC.pe_quartiles([3.0, 7.0, 9.0])
    assert (q1, med, q3) == (5.0, 7.0, 8.0)


def test_with_reasons_keeps_every_candidate_field():
    c = dict(MC.candidate("pe_fy_scenario", per_share=10, per_share_down=8),
             gate={"status": "x"}, label="custom")
    out = MC.with_reasons(c, ["data gate"])
    assert out["status"] == "insufficient" and out["reasons"] == ["data gate"]
    assert out["gate"] == {"status": "x"} and out["label"] == "custom"
    assert MC.with_reasons(c, []) is c


def test_skipped_method_value_is_dash_when_released():
    from app import report_extras as R
    va = {"release": {"status": "distributable_assumption_led"},
          "method_chain": {"trace": [
              dict(MC.candidate("fcff_dcf", per_share=100, reasons=["x"]), rank=1,
                   role="primary", decision="skipped"),
              dict(MC.candidate("pe_fy_scenario", per_share=120, per_share_down=90), rank=2,
                   role="fallback", decision="selected")]}}
    rows = R.method_chain_exhibit(va)["data"]["rows"]
    assert rows[0][2] == "-" and rows[1][2].startswith("Rp")


def test_guidance_departure_must_cite_the_guidance_item():
    from agents.forecast_assumptions import run as agent
    official = {"source_url": "https://issuer.example/1h26.pdf", "published_at": "2026-08-20",
                "period": "1H26", "period_end": "2026-06-30",
                "guidance": [{"fact": "capex plan"}],
                "metrics": {"revenue": 100.0, "net_profit": 10.0}}
    source = {"ticker": "UJI", "as_of": "2026-09-24", "model_profile": "going_concern_fcff",
              "official": official, "news": []}
    base = {"h2_revenue_to_h1": 1.6, "h2_net_margin_pct": 11.0,
            "rationale": "Pendapatan H2 naik tajam karena kontrak baru yang sudah diumumkan.",
            "source_url": official["source_url"], "published_at": official["published_at"],
            "thesis_points": ["Kontrak baru menaikkan volume pendapatan H2 secara material.",
                              "Margin laba bersih stabil karena biaya tetap terserap volume."],
            "catalysts_risks": [
                {"item": "Kontrak baru", "timing": "H2 2026",
                 "driver_path": "Volume kontrak menaikkan pendapatan dan laba H2.",
                 "direction": "Positif", "source_ids": ["official"]},
                {"item": "Biaya bahan", "timing": "Sepanjang 2026",
                 "driver_path": "Kenaikan biaya bahan menekan margin laba bersih.",
                 "direction": "Negatif", "source_ids": ["official"]}],
            "key_risks": [
                {"category": "Komoditas", "headline": "Harga jagung dan bungkil kedelai",
                 "explanation": "Bahan baku pakan setara 60% beban pokok; kenaikan harga jagung "
                                "10% menekan margin kotor sekitar 2pp tanpa kenaikan harga jual.",
                 "source_ids": ["official"]},
                {"category": "Operasi", "headline": "Oversupply ayam pedaging",
                 "explanation": "Populasi DOC naik 8% yoy; kelebihan pasokan menurunkan harga "
                                "livebird dan margin segmen peternakan komersial.",
                 "source_ids": ["official"]},
                {"category": "Pendanaan", "headline": "Utang bank jangka pendek",
                 "explanation": "Utang jangka pendek Rp5.000 miliar jatuh tempo dalam 12 bulan; "
                                "kenaikan bunga 100bp menambah beban bunga sekitar Rp50 miliar.",
                 "source_ids": ["official"]}]}
    uncited = agent._validate_earnings(dict(base, source_ids=["official"]), source)
    assert any("departs from the 1H run-rate" in p for p in uncited)
    cited = agent._validate_earnings(dict(base, source_ids=["official", "guidance:0"]), source)
    assert cited == []


def test_failed_scenario_subagent_is_not_cached(tmp_path, monkeypatch):
    from agents.forecast_assumptions import run as agent
    failed = {"status": "partial", "plan": {"news_effects": []}, "interim_status": "not_run",
              "earnings_status": "invalid", "outyears_status": "not_run", "stage_status": "validated"}
    monkeypatch.setattr(agent, "run_live", lambda intake: dict(failed))
    intake_ = {"ticker": "UJI", "as_of": "2026-09-24", "model_profile": "going_concern_fcff",
               "latest_official_actual": {}, "official_evidence": {}, "news": []}
    agent.run_cached(intake_, db=tmp_path)
    assert not list(tmp_path.glob("UJI-*.json"))


def test_prices_round_to_idx_tick_not_flat_rp10():
    from app import fmt
    assert fmt.tick(56.4) == 56 and fmt.tick(30.6) == 31      # < Rp200: Rp1
    assert fmt.tick(333) == 334 and fmt.tick(1234) == 1235   # Rp2 / Rp5 bands
    assert fmt.tick(2533) == 2530 and fmt.tick(6312) == 6300  # Rp10 / Rp25 bands
    assert fmt.tick(None) is None


def test_low_priced_target_keeps_downside_below_base(monkeypatch):
    intake_, fc = _earnings_fixture(None, peers=(0.028, 0.030, 0.033))
    intake_ = dict(intake_, price=30.0, market_cap=30.0 * test_valtables.SHARES)
    va = valuation.build(intake_, fc, assumption_status="validated")
    assert va["tp"] is not None and va["tp_down"] < va["tp"]


def test_cover_bullet_is_one_complete_sentence():
    from app.narrative import _bullet
    long = ("Pemulihan harga livebird dan DOC ke level tertinggi Agustus 2026 menopang ASP "
            "segmen commercial farming, dengan risiko margin squeeze jika harga livebird gagal "
            "menembus Rp 21.000/kg di tengah SBM yang sudah naik 18% sejak Juni.")
    out = _bullet(long)
    assert out.endswith("commercial farming.") and len(out.split()) <= 30
    assert _bullet("Laba naik. Kalimat kedua.") == "Laba naik."


def test_issuer_without_sectors_peers_borrows_the_table_that_lists_it():
    # BBCA has no Sectors peer table; BBRI's Sectors table lists it.
    doc_in, _ = intake.load("BBCA", as_of="2026-09-24")
    assert doc_in["peer_basis"] == "tabel peer Sectors milik BBRI yang memuat BBCA"
    symbols = [p["symbol"] for p in doc_in["peers"]]
    assert "BBRI.JK" in symbols and "BBCA.JK" not in symbols
    assert len([p for p in doc_in["peers"] if 0 < p["pe"] <= 50]) >= 3
    # JPFA has a curated group; four of its peers sit in its own Sectors table.
    own, _ = intake.load("JPFA", as_of="2026-09-24")
    assert own["peer_basis"].startswith("grup peer kurasi")
