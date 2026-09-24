"""Harness G1/G2/G3 + runner compliance with Instruksi-Report-v3."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.harness import check_g1, check_g2, check_g3, run_all  # noqa: E402


def _intake_fcff():
    intake = {
        "model_profile": "going_concern_fcff",
        "currency": "Rp",
        "price": 1000.0, "shares": 10_000_000_000.0, "market_cap": 1e13,
        "as_of": "2026-09-22", "price_date": "2026-09-22",
        "annuals": [
            {"year": 2023, "revenue": 5e12, "ebitda": 1e12, "ocf": 8e11,
             "fcf": 5e11, "capex_out": 3e11},
            {"year": 2024, "revenue": 5.5e12, "ebitda": 1.1e12, "ocf": 9e11,
             "fcf": 5.5e11, "capex_out": 3.5e11},
            {"year": 2025, "revenue": 6e12, "ebitda": 1.3e12, "ocf": 1e12,
             "fcf": 6e11, "capex_out": 4e11},
        ],
        "latest_official_actual": {
            "period": "1H26", "period_end": "2026-06-30",
            "published_at": "2026-08-20",
            "source_url": "https://issuer.example/1h26.pdf",
            "metrics": {"revenue": 3.1e12, "net_profit": 4e11},
        },
        "payout": 0.3,
    }
    fc = {
        "rows": [
            {"label": "FY26F", "revenue": 6.6e12, "margin": 0.21,
             "ebit": 8e11, "interest": 1e11, "tax": 1.5e11,
             "net": 5.5e11, "ebitda": 1.386e12},
            {"label": "FY27F", "revenue": 7.0e12, "margin": 0.215,
             "ebit": 8.5e11, "interest": 1e11, "tax": 1.6e11,
             "net": 5.9e11, "ebitda": 1.5e12},
        ],
        "g2": {"G2.4_konsistensi": "lolos", "G2.5_neraca": "lolos"},
        "forecast_basis": "driver_forecast",
        "production_ready": True,
        "driver_evidence": {
            s: {"source": "https://issuer.example/g.pdf", "source_date": "2026-08-01",
                "page": 3, "note": f"sourced {s}"}
            for s in ("revenue", "ebitda", "net_profit", "capex")},
    }
    return intake, fc


def test_g1_passes_with_valid_actual():
    intake, _ = _intake_fcff()
    r = check_g1(intake)
    assert r["status"] == "lolos", r
    assert r["blockers"] == []


def test_g1_blocks_without_actual():
    r = check_g1({"model_profile": "going_concern_fcff"})
    assert r["status"] == "gagal"
    assert any("G1.periode" in b for b in r["blockers"])


def test_g2_screening_proxy_fails_g29():
    intake, fc = _intake_fcff()
    fc["forecast_basis"] = "historical_screening_proxy"
    fc["production_ready"] = False
    r = check_g2(intake, fc)
    assert r["status"] == "gagal"
    assert any("G2.9" in b for b in r["blockers"])


def test_g2_driver_forecast_passes():
    intake, fc = _intake_fcff()
    r = check_g2(intake, fc)
    assert r["status"] == "lolos", r


def test_g3_extreme_upside_blocks():
    intake, fc = _intake_fcff()
    va = {"tp": 3000.0, "tp_down": 2500.0, "upside": 2.0,
          "tv_share": 0.4, "net_debt": 1e12,
          "implied": {"per": 10.0, "ev_ebitda": 6.0},
          "g3": {"G3.5_keyfin": "lolos"}}
    intake["peers"] = []
    r = check_g3(intake, fc, va)
    assert r["status"] == "gagal"
    assert any("extreme" in b for b in r["blockers"])


def test_runner_fails_closed_on_engine_release():
    # valid G1/G2/G3 math but engine release has no driver evidence provenance → draft
    intake, fc = _intake_fcff()
    del intake["latest_official_actual"]
    va = {"tp": None, "g3": {}}
    r = run_all(intake, fc, va, None)
    assert r["status"] == "draft_non_distributable"
    assert r["blockers"]
