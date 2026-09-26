"""Forward-looking equity research pipeline: Tavily, register, manifest, profile gates."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import evidence as evidence_mod  # noqa: E402
from app import intake  # noqa: E402
from app import news_sources  # noqa: E402
from app import run_manifest  # noqa: E402
from app import tavily  # noqa: E402
from app import forecast as forecast_mod  # noqa: E402
from app import release as release_mod  # noqa: E402
from agents.forecast_assumptions import run as assumption_run  # noqa: E402


def _fake_post_factory(batches):
    calls = {"n": 0}

    def _post(key, body, timeout=20):
        index = min(calls["n"], len(batches) - 1)
        calls["n"] += 1
        return batches[index]

    _post.calls = calls
    return _post


def test_tavily_builds_profile_queries():
    base = tavily.build_queries("BBRI", "Bank Rakyat Indonesia", None)
    # Issuer query plus a brand query: Indonesian press often omits the ticker.
    assert base == ['"BBRI" Bank Rakyat Indonesia saham emiten berita',
                    "Bank Rakyat kinerja laba pendapatan semester",
                    "Bank Rakyat risiko utang gugatan regulasi pelanggan kerugian"]
    bank = tavily.build_queries("BBRI", "Bank Rakyat Indonesia", "financial_ddm",
                                industry="Banks")
    assert len(bank) == 5  # industry driver query is for going concern only
    assert bank[0] == base[0]
    feed = tavily.build_queries("JPFA", "PT JAPFA Comfeed Indonesia Tbk",
                                "going_concern_fcff", industry="Agricultural Products")
    assert feed[-2] == "JAPFA Comfeed Agricultural Products harga jual volume biaya bahan baku"
    assert feed[-1] == "JAPFA Comfeed risiko utang gugatan regulasi pelanggan kerugian"
    assert any("kredit" in q for q in bank[1:])
    mining = tavily.build_queries("AMMN", "Amman Mineral", "finite_life_mining")
    assert any("produksi" in q or "komoditas" in q for q in mining[1:])


def test_tavily_multi_query_merges_and_dedups(tmp_path):
    batch_base = {"results": [
        {"title": "BBRI catat laba", "url": "https://kontan.co.id/bbri-laba",
         "published_date": "2026-09-10", "content": "laba naik"},
        {"title": "Future news", "url": "https://kontan.co.id/future",
         "published_date": "2026-09-25", "content": "look-ahead"},
    ]}
    batch_hint = {"results": [
        {"title": "BBRI catat laba", "url": "https://kontan.co.id/bbri-laba?utm_source=x",
         "published_date": "2026-09-10", "content": "duplikat sindikasi"},
        {"title": "BBRI tambah modal", "url": "https://bisnis.com/bbri-modal",
         "published_date": "2026-09-12", "content": "modal kuat"},
    ]}
    post = _fake_post_factory([batch_base, batch_hint])
    ring = tavily.KeyRing(["test-key"])
    result = tavily.news_context(
        "BBRI", "Bank Rakyat Indonesia", "2026-09-23",
        profile="financial_ddm", post=post, ring=ring, db=tmp_path)
    urls = [i["url"] for i in result["items"]]
    # Look-ahead filtered, URL deduped (utm stripped logically via lower/strip).
    assert "https://kontan.co.id/future" not in urls
    assert len(urls) == len(set(u.strip().rstrip("/").lower() for u in urls))
    assert len(result["items"]) == 2
    assert result["query"].startswith('"BBRI"')
    assert len(result["queries"]) == 3 - 1 or len(result["queries"]) >= 2


def test_news_register_stable_ids_and_rejections():
    sectors = [
        {"title": "Sektor berita", "timestamp": "2026-09-10",
         "source": "https://kontan.co.id/sektor-1", "body": "isi"},
        {"title": "Masa depan", "timestamp": "2026-09-30",
         "source": "https://kontan.co.id/future", "body": "no look-ahead"},
    ]
    tavily_items = [
        {"title": "BBRI catat laba bersih", "date": "2026-09-11",
         "url": "https://bisnis.com/bbri-laba", "snippet": "BBRI laba",
         "domain": "bisnis.com"},
        {"title": "Saham global menguat", "date": "2026-09-11",
         "url": "https://reuters.com/global", "snippet": "pasar global",
         "domain": "reuters.com"},
        {"title": "BBRI catat laba bersih", "date": "2026-09-11",
         "url": "https://bisnis.com/bbri-laba", "snippet": "BBRI laba duplikat",
         "domain": "bisnis.com"},
    ]
    register = news_sources.build_register(
        "BBRI", "Bank Rakyat Indonesia", "2026-09-23", sectors, tavily_items)
    articles = register["articles"]
    assert [a["register_id"] for a in articles] == [f"src-{i}" for i in range(len(articles))]
    # Future-dated Sectors rejected, global news rejected for issuer mismatch,
    # duplicate URL merged.
    reasons = " ".join(r["reason"] for r in register["rejected"])
    assert "no look-ahead" in reasons
    assert "issuer identity" in reasons
    # A merged duplicate is kept (origins combined), so it is not a rejection.
    assert "duplicate URL" not in reasons
    assert [m["url"] for m in register["merged"]] == ["https://bisnis.com/bbri-laba"]
    assert register["stats"]["merged"] == 1
    assert any("tavily" in (a.get("origins") or []) for a in articles)


def test_run_manifest_has_contract_fields():
    manifest = run_manifest.build_manifest(
        ticker="BBRI", as_of="2026-09-23",
        intake={"model_profile": "financial_ddm", "price": 4000,
                "price_date": "2026-09-23",
                "official_evidence": {"latest_actual": {
                    "period": "1H26", "period_end": "2026-06-30",
                    "published_at": "2026-08-31",
                    "source_title": "Release", "source_url": "https://issuer.example/r.pdf"}},
                "market_quote": {}},
        forecast={"forecast_basis": "historical_screening_proxy",
                  "production_ready": False},
        valuation={"method": "DDM", "tp": None,
                   "release": {"status": "draft_non_distributable",
                               "blockers": ["missing equity"]}},
        news_evidence={"rows": [{"source": "https://a.example/1"}],
                       "search": {"status": "searched", "query": "q"}},
        assumption_plan={"news_effects": []},
        release={"status": "draft_non_distributable", "blockers": ["missing equity"]})
    for key in ("code_revision", "as_of", "market_close", "official_filing",
                "tavily", "selected_news_urls", "assumption_plan_hash",
                "profile", "release_status", "blockers", "source_tree_sha256",
                "working_tree", "source_pack_sha256", "cache_snapshot_sha256",
                "evidence_register_sha256", "release_policy"):
        assert key in manifest
    assert manifest["release_policy"]["sha256"]
    assert manifest["release_policy"]["policy"]["status"] == "mixed_enforcement_and_documentation"
    assert manifest["house_assumptions"]["sha256"]
    assert manifest["house_assumptions"]["policy"]["status"] == \
        "approved_not_independently_validated"
    assert manifest["ticker"] == "BBRI"
    assert manifest["selected_news_urls"] == ["https://a.example/1"]


def test_evidence_register_counts_and_no_lookahead():
    intake = {"as_of": "2026-09-23",
              "official_evidence": {"latest_actual": {
                  "period": "1H26", "period_end": "2026-06-30",
                  "published_at": "2026-08-31", "source_url": "https://i.example/r.pdf",
                  "source_title": "R", "page": 1, "unit": "IDR",
                  "metrics": {"revenue": 1}},
                  "management_guidance": [{"name": "capex FY26", "value": 10,
                                           "source_url": "https://i.example/g.pdf"}]}}
    register = {"articles": [
        {"register_id": "src-0", "title": "T", "source": "https://n.example/1",
         "timestamp": "2026-09-10", "body": "b", "origins": ["sectors"]}]}
    out = evidence_mod.build("BBRI", "2026-09-23", intake, register, [], None)
    assert out["counts"]["official_actual"] == 1
    assert out["counts"]["company_guidance"] == 1
    assert out["violations"] == []
    future = {"as_of": "2026-09-23",
              "official_evidence": {"latest_actual": {
                  "period": "1H26", "period_end": "2026-06-30",
                  "published_at": "2026-09-30", "source_url": "https://i.example/r.pdf",
                  "source_title": "R", "page": 1, "unit": "IDR", "metrics": {"revenue": 1}}}}
    out2 = evidence_mod.build("BBRI", "2026-09-23", future, [], [], None)
    assert out2["violations"]


def test_ammn_official_guidance_units_pass_material_evidence_validation():
    issuer, _ = intake.load("AMMN", as_of="2026-09-24")

    register = evidence_mod.build(
        "AMMN", "2026-09-24", issuer, issuer.get("news") or [],
        issuer.get("news_full") or [], None)

    assert [row["unit"] for row in register["rows"]
            if row.get("kind") == "company_guidance"] == ["dmt", "Mlbs", "koz", "kt", "koz"]
    assert not any("company_guidance" in violation
                   for violation in register["critical_violations"])


def test_evidence_register_flags_malformed_material_publication_date():
    intake = {"official_evidence": {"latest_actual": {
        "period": "1H26", "period_end": "2026-06-30",
        "published_at": "31-08-2026", "source_url": "https://i.example/r.pdf",
        "source_title": "Release", "page": 1, "unit": "IDR",
        "metrics": {"revenue": 1}}}}

    result = evidence_mod.build("TEST", "2026-09-23", intake, [], [], None)

    assert "official_actual: malformed published_at '31-08-2026'" in result[
        "critical_violations"]
    assert any("critical violation" in blocker
               for blocker in evidence_mod.release_blockers(result))


def test_evidence_register_allows_absent_optional_assumption_publication_date():
    register = evidence_mod.build(
        "TEST", "2026-09-23", {}, [], [],
        {"news_effects": [{"driver": "none", "years": [], "change": 0,
                           "rationale": "No issuer effect", "source_url": None}]})

    assert register["critical_violations"] == []
    assert not any("published_at" in blocker
                   for blocker in evidence_mod.release_blockers(register))


def test_empty_or_error_evidence_register_cannot_pass_release_checks():
    empty = {"ticker": "TEST", "as_of": "2026-09-23", "rows": [],
             "violations": [], "critical_violations": []}
    failed = {**empty, "error": "source normalizer failed"}

    assert evidence_mod.release_blockers(empty) == [
        "evidence register contains no eligible source rows"]
    assert "evidence register construction failed: source normalizer failed" in \
        evidence_mod.release_blockers(failed)


def _fcff_intake(driver_evidence):
    annuals = [
        {"year": 2023, "revenue": 5e12, "ebitda": 1e12, "ebit": 8e11,
         "earnings": 5e11, "tax": 1e11, "interest": 5e10, "da": 2e11,
         "capex_out": 2e11, "fcf": 5e11, "ocf": 7e11, "total_debt": 1e12,
         "cash": 5e11, "equity": 3e12, "assets": 5e12, "liab": 2e12,
         "shares": 1e10},
        {"year": 2024, "revenue": 5.5e12, "ebitda": 1.1e12, "ebit": 9e11,
         "earnings": 5.5e11, "tax": 1.1e11, "interest": 5e10, "da": 2e11,
         "capex_out": 2e11, "fcf": 5.5e11, "ocf": 7.5e11, "total_debt": 1e12,
         "cash": 5e11, "equity": 3.2e12, "assets": 5.2e12, "liab": 2e12,
         "shares": 1e10},
        {"year": 2025, "revenue": 6e12, "ebitda": 1.3e12, "ebit": 1e12,
         "earnings": 6e11, "tax": 1.2e11, "interest": 5e10, "da": 3e11,
         "capex_out": 3e11, "fcf": 6e11, "ocf": 9e11, "total_debt": 1e12,
         "cash": 5e11, "equity": 3.5e12, "assets": 5.5e12, "liab": 2e12,
         "shares": 1e10},
    ]
    return {"ticker": "UJI", "model_profile": "going_concern_fcff",
            "as_of": "2026-09-23", "price": 1000, "price_date": "2026-09-23",
            "shares": 1e10, "market_cap": 1e13, "payout": 0.3,
            "payout_basis": "x", "annuals": annuals,
            "latest_official_actual": {"period": "1H26", "period_end": "2026-06-30",
                                       "published_at": "2026-08-20",
                                       "source_url": "https://issuer.example/1h.pdf",
                                       "metrics": {"revenue": 3e12, "net_profit": 3e11}},
            "driver_evidence": driver_evidence}


def _sourced_driver(series):
    return {s: {"source": "https://issuer.example/g.pdf",
                "source_date": "2026-08-01", "page": 3,
                "note": f"sourced {s}"} for s in series}


def test_sourced_driver_metadata_does_not_promote_screening_rows():
    complete = _fcff_intake(_sourced_driver(("revenue", "ebitda", "net_profit", "capex")))
    fc = forecast_mod.build(complete)
    assert fc["forecast_basis"] == "historical_screening_proxy"
    assert fc["production_ready"] is False
    assert fc["s2"]["S2.9_driver_forecast"] == "gagal"
    assert all(row["capex"] == row["da"] for row in fc["rows"])
    assert any("driver-to-FCFF bridge is not calculated" in reason
               for reason in fc["production_blockers"])
    assert any("driver-to-FCFF bridge is not calculated" in reason
               for reason in release_mod._check_driver_forecast(fc, complete))

    partial = _fcff_intake(_sourced_driver(("revenue", "net_profit")))
    fc2 = forecast_mod.build(partial)
    assert fc2["forecast_basis"] == "historical_screening_proxy"
    assert fc2["production_ready"] is False
    assert fc2["s2"]["S2.9_driver_forecast"] == "gagal"


def test_bank_source_metadata_does_not_promote_screening_rows():
    intake = _fcff_intake(_sourced_driver(("net_profit", "equity", "payout")))
    intake["model_profile"] = "financial_ddm"
    fc = forecast_mod.build(intake)
    assert fc["forecast_basis"] == "historical_screening_proxy"
    assert fc["production_ready"] is False
    assert fc["s2"]["S2.9_driver_forecast"] == "gagal"
    assert any("driver-to-earnings/capital bridge is not calculated" in reason
               for reason in fc["production_blockers"])


def test_release_ddm_does_not_require_fcff_capex():
    intake = _fcff_intake(_sourced_driver(("net_profit", "equity", "payout")))
    intake["model_profile"] = "financial_ddm"
    forecast = forecast_mod.build(intake)
    ddm = {"status": "complete", "method": "ddm", "tp_gordon": 1000}
    result = release_mod.assess_release("financial_ddm", intake, forecast, ddm)
    assert result["status"] == "draft_non_distributable"
    assert not any("capex" in blocker.lower() or "fcff" in blocker.lower()
                   for blocker in result["blockers"])
    # The DDM-specific missing valuation remains visible independently of
    # production-model blockers.
    result2 = release_mod.assess_release("financial_ddm", intake, forecast, None)
    assert result2["status"] == "draft_non_distributable"
    assert any("DDM" in b for b in result2["blockers"])


def test_assumption_event_chain_and_no_tp_write():
    source = {"ticker": "BBRI", "as_of": "2026-09-23",
              "model_profile": "financial_ddm",
              "official": None,
              "news": [{"index": 0, "title": "T", "timestamp": "2026-09-10",
                        "url": "https://n.example/1", "origin": "sectors",
                        "full_text": "", "full_text_status": "unavailable"}]}
    good = {"news_effects": [{"article_index": 0, "source_url": "https://n.example/1",
                              "title": "T", "timestamp": "2026-09-10",
                              "driver": "none", "change": 0, "years": [],
                              "factual_basis": "fakta ringkas berita",
                              "mechanism": "tidak ada transmisi laba",
                              "uncertainty": "tidak ada ketidakpastian material",
                              "rationale": "berita sentimen tanpa katalis operasi, dampak nol",
                              "event_date": "2026-10-01",
                              "conditions": "tunduk pada realisasi kredit",
                              "assumption_type": "analyst_judgment"}],
            "interim_scenario": None}
    assert assumption_run._validate(good, source) == []
    bad_tp = {"news_effects": [], "target_price": 1000}
    assert any("target_price" in p for p in assumption_run._validate(bad_tp, source))
    bad_type = {"news_effects": [dict(good["news_effects"][0],
                                     assumption_type="issuer_fact")]}
    assert any("assumption_type" in p for p in assumption_run._validate(bad_type, source))


def test_tavily_hint_query_failure_keeps_base_results(tmp_path):
    ok = {"results": [{"title": "BBRI catat laba", "url": "https://kontan.co.id/a",
                       "published_date": "2026-09-10", "content": "laba"}]}
    calls = {"n": 0}

    def post(key, body, timeout=20):
        calls["n"] += 1
        if calls["n"] > 1:
            raise tavily.TavilyError("rate limited")
        return ok

    result = tavily.news_context("BBRI", "Bank Rakyat Indonesia", "2026-09-23",
                                 profile="financial_ddm", post=post,
                                 ring=tavily.KeyRing(["k"]), db=tmp_path)
    assert len(result["items"]) == 1
    assert result["partial_failures"]
    assert not list(tmp_path.glob("*.json"))  # partial results are not cached


def test_validator_rejects_nested_forbidden_key_and_bad_change():
    problems = assumption_run._validate(
        {"news_effects": [{"target_price": 1, "change": "x", "driver": "none",
                          "uncertainty_range": [0, 1]}]},
        {"news": []}, require_news_coverage=False)
    assert any("target_price" in p for p in problems)


# ---------------------------------------------------------- PR #3 review fixes

def test_method_gate5_extreme_rule_is_framework_asymmetric():
    from app import model_profiles
    assert model_profiles.is_extreme_upside(1.2) and model_profiles.is_extreme_upside(-0.6)
    assert not model_profiles.is_extreme_upside(0.7)   # +70% is not extreme
    assert not model_profiles.is_extreme_upside(-0.4)
    assert not model_profiles.is_extreme_upside(None)


def test_bank_method_gate5_uses_ddm_upside_not_fcff_screen():
    from app import forecast, intake, valuation
    doc_in, _ = intake.load("BBCA")
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    tp_ddm = (va["ddm"] or {}).get("tp_gordon")
    reasons = " ".join(va["gate_verdict"]["reasons"])
    if tp_ddm:
        ddm_up = (tp_ddm / doc_in["price"] - 1) * 100
        assert ("5_upside_extreme" in va["gate_verdict"]["gates_failed"]) == (ddm_up > 100)
    assert "terminal value" not in reasons  # DCF-only check skipped for banks


def test_payout_provenance_follows_its_source():
    from app.intake import _driver_evidence_inputs
    official = {"latest_actual": {"source_url": "https://bank.example/1h26.pdf",
                                  "published_at": "2026-08-20", "page": 3, "unit": "IDR",
                                  "metrics": {"net_profit": 10.0}},
                "balance_sheet": {"total_equity": 100.0}}
    default = _driver_evidence_inputs(official, 0.25,
                                      "asumsi analis 25% (tanpa payout historis di data Sectors)",
                                      [100.0], "2026-09-24", "financial_ddm")["payout"]
    assert default["source"].startswith("asumsi analis")
    assert "official_actual_base" not in default.values()
    sectors = _driver_evidence_inputs(official, 0.45, "payout ratio historis di data Sectors",
                                      [], "2026-09-24", "financial_ddm")["payout"]
    assert sectors["source"].startswith("sectors_cache") and "45.0%" in sectors["note"]
    assert "bank.example" not in sectors["source"]


def test_manifest_snapshot_is_ticker_scoped():
    snapshot = run_manifest.cache_snapshot_ids("BBRI")
    assert snapshot and all("/BBRI/" in endpoint for endpoint in snapshot)


def test_finalized_manifest_binds_final_artifact_bytes(tmp_path):
    from app import run_manifest

    for name, content in (("TEST.html", b"html-v1"), ("TEST.pdf", b"pdf-v1"),
                          ("TEST-trace.html", b"trace-v1")):
        (tmp_path / name).write_bytes(content)
    base = {"ticker": "TEST", "source_tree_sha256": "code",
            "market_inputs": {"fx": {"date": "2026-09-24", "rate": 16000}}}

    first = run_manifest.finalize_manifest(base, tmp_path, "TEST")
    (tmp_path / "TEST.pdf").write_bytes(b"pdf-v2")
    second = run_manifest.finalize_manifest(base, tmp_path, "TEST")

    assert first["missing_artifacts"] == []
    assert first["artifacts"]["pdf"]["sha256"] != second["artifacts"]["pdf"]["sha256"]
    assert first["publication_id"] != second["publication_id"]
    assert first["market_inputs_sha256"] == run_manifest.content_hash(base["market_inputs"])


def test_build_manifest_records_forecast_status_and_final_release(tmp_path):
    from app import build
    from app import outputs
    doc = build.build("BBRI", tmp_path, as_of="2026-09-24", spec_sha="abc")
    manifest = doc["run_manifest"]
    assert manifest["forecast_basis"] == "historical_screening_proxy"
    assert manifest["production_ready"] is False
    assert manifest["release_status"] == doc["meta"]["status"]
    assert manifest["spec_sha256"] == "abc"
    published = outputs.load(outputs.MANIFEST, tmp_path, "BBRI")
    assert published["artifacts"]["html"]["sha256"]
    assert "trace_html" in published["missing_artifacts"]
