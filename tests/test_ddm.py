"""Uji DDM bank dan catatan metodologi kondisional. Bahasa Indonesia."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import ddm, methodnote  # noqa: E402


def _miner_intake():
    return {"ticker": "AMMN", "sub_sector": "Metal Mining",
            "industry": "Metals", "currency": "Rp"}


def _bank_intake():
    return {"ticker": "BBCA", "sub_sector": "Bank",
            "industry": "Banks", "currency": "Rp"}


def test_ddm_gordon_exact():
    r = ddm.value_bank([100.0, 110.0, 121.0], [0.4, 0.5, 0.6], [],
                       shares=10.0, coe=0.12, g=0.03, roae_fwd=0.18,
                       bvps=50.0)
    assert r["payout_used"] == 0.5
    dps = [5.0, 5.5, 6.05]
    pv = sum(d / 1.12 ** (i + 0.5) for i, d in enumerate(dps))
    tv = 6.05 * 1.03 / (0.12 - 0.03)
    assert abs(r["pv_dps"] - pv) < 1e-9
    assert abs(r["terminal_dps"] - 6.05 * 1.03) < 1e-9
    assert abs(r["tp_gordon"] - (pv + tv / 1.12 ** 3)) < 1e-9


def test_ddm_inverse_coe_exact():
    r = ddm.value_bank([100.0], [0.4], [], shares=10.0, coe=0.12, g=0.03,
                       roae_fwd=0.18, bvps=50.0)
    assert abs(r["fair_pbv"] - (0.18 - 0.03) / (0.12 - 0.03)) < 1e-12
    assert abs(r["tp_inverse"] - r["fair_pbv"] * 50.0) < 1e-9


def test_ddm_coe_bukan_wacc_terdokumentasi():
    r = ddm.value_bank([100.0], [0.4], [], shares=10.0, coe=0.12, g=0.03,
                       roae_fwd=0.18, bvps=50.0)
    assert "Cost of Equity" in r["method_note"]
    assert "bukan WACC" in r["method_note"]


def test_ddm_payout_announced_menang():
    r = ddm.value_bank([100.0], [0.4, 0.5], [], shares=10.0, coe=0.12,
                       g=0.03, roae_fwd=0.18, bvps=50.0,
                       payout_announced=0.65)
    assert r["payout_used"] == 0.65


def test_methodology_miner_dengan_tahun():
    mineops = {"reserve_life_cu_yr": 38.5,
               "reserve_life_basis": "cadangan Cu dibagi produksi 2024"}
    out = methodnote.methodology_notes(_miner_intake(), {}, {"notes": []},
                                       mineops)
    teks = " ".join(out)
    assert "38,5 tahun" in teks
    assert "umur cadangan tidak ada di data Sectors" not in teks


def test_methodology_miner_tanpa_data_umur_cadangan():
    out = methodnote.methodology_notes(_miner_intake(), {}, {"notes": []},
                                       None)
    teks = " ".join(out)
    assert "tidak ada di data Sectors" in teks


def test_methodology_bank_dan_fx():
    out = methodnote.methodology_notes(_bank_intake(), {}, {"notes": []},
                                       None)
    teks = " ".join(out)
    assert "bank idealnya" in teks
    assert "FX = 1" in teks


def test_extreme_kosong_untuk_20_persen():
    assert methodnote.extreme_tp_lines(0.20, 1200, 1000, "laba tumbuh",
                                       "terminal dominan") == []


def test_extreme_dua_baris_untuk_downside_85_persen():
    lines = methodnote.extreme_tp_lines(-0.85, 150, 1000, "laba anjlok",
                                        "ekuitas DCF kecil vs market cap")
    assert len(lines) == 2
    assert "di bawah" in lines[0]


def test_capex_level4_dampak():
    s = methodnote.capex_impact_line(False, "guidance/timeline smelter")
    assert "Rp0" in s and "overstated" in s


def test_revenue_bridge_flag_30_senyap_10():
    b30 = methodnote.revenue_bridge(130.0, 100.0, 1.0)
    assert b30["needs_explanation"] is True
    assert abs(b30["gap_pct"] - 0.30) < 1e-9
    b10 = methodnote.revenue_bridge(110.0, 100.0, 1.0)
    assert b10["needs_explanation"] is False
