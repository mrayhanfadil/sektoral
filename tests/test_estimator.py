"""Gate estimator: skema + sumber + sanity. Tanpa network, tanpa LLM."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.estimator.validate import gate


def good():
    return {"ticker": "AMMN", "basis": "agent-estimate",
            "as_of": "2026-09-23", "currency": "USD mn (as published)",
            "years": ["2026F", "2027F", "2028F"],
            "drivers": {
                "revenue": {"path": [4001, 4287, 4868],
                            "source": "paparan publik emiten Q2-2026",
                            "note": "ramp Phase-8, fresh ore naik bertahap"},
                "ebitda": {"path": [2024, 2673, 3300],
                           "source": "paparan publik emiten Q2-2026",
                           "note": "margin 50-68%, biaya/ton turun saat ramp"},
                "net_profit": {"path": [909, 1462, 1992],
                               "source": "asumsi-berlabel: ikut margin historis",
                               "note": "asumsi-berlabel: net margin 22-41% bertahap"},
                "capex": {"path": [498, 305, 318],
                          "source": "cache filings FY2025A + normalisasi",
                          "note": "post-build normalisation dari 1.424 FY2025A"},
            }}


def test_lolos():
    assert gate(good()) == []


def test_tolak_tanpa_sumber():
    d = good()
    del d["drivers"]["capex"]["source"]
    assert any("tanpa sumber" in p for p in gate(d))


def test_tolak_path_negatif():
    d = good()
    d["drivers"]["revenue"]["path"][0] = -5
    assert any("negatif" in p for p in gate(d))


def test_tolak_series_hilang():
    d = good()
    del d["drivers"]["ebitda"]
    assert any("ebitda" in p for p in gate(d))


def test_tolak_note_tipis():
    d = good()
    d["drivers"]["capex"]["note"] = "ok"
    assert any("tipis" in p for p in gate(d))


def test_plan_dry_run_tanpa_llm():
    from agents.estimator.run import plan
    p = plan("AMMN", ["2026F", "2027F", "2028F"])
    assert p["n_endpoints"] > 0
    assert "write_drivers" in p["tools"]
