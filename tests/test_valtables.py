"""Uji builder exhibit valuasi di app/valtables.py (fixture sintetis)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import fmt  # noqa: E402
from app import valuation  # noqa: E402
from app import valtables as V  # noqa: E402

SHARES, PRICE = 10_000_000_000, 2_500.0


def _fixture():
    rows = []
    rev = 100e12
    for i, (g, ebitda) in enumerate([(0.08, 40e12), (0.06, 41e12),
                                     (0.05, 42e12)]):
        rev = rev * (1 + g) if i else rev
        da = rev * 0.05
        ebit = ebitda - da
        interest = rev * 0.01
        ebt = ebit - interest
        tax = ebt * 0.22
        net = ebt - tax
        ocf = net + da
        cx = da
        fcf = ocf - cx
        rows.append({"year": 2026 + i, "label": f"FY{(26+i)%100:02d}F",
                     "revenue": rev, "ebitda": ebitda,
                     "margin": ebitda / rev, "da": da, "ebit": ebit,
                     "interest": interest, "tax": tax, "net": net,
                     "ocf": ocf, "capex": cx, "fcf": fcf, "div": net * 0.3,
                     "cash": 5e12, "debt": 20e12, "equity": 60e12,
                     "assets": 100e12, "eps": net / SHARES})
    intake = {"ticker": "UJI", "model_profile": "going_concern_fcff",
              "shares": SHARES, "price": PRICE,
              "market_cap": PRICE * SHARES, "payout": 0.3, "peers": []}
    fc = {"rows": rows,
          "base": {"cash": 5e12, "debt": 20e12, "equity": 55e12,
                   "other_liab": 8e12, "noncash": 95e12}}
    val = valuation.build(intake, fc)
    return intake, fc, val


def _shape(ex):
    assert ex["n"] is None
    assert ex["tipe"] == "tabel"
    assert set(ex["data"]) == {"cols", "rows"}
    assert ex["catatan_sumber"]
    for r in ex["data"]["rows"]:
        assert isinstance(r, list) and len(r) == len(ex["data"]["cols"])


def test_fcff_bridge_ties():
    intake, fc, val = _fixture()
    ex = V.fcff_exhibit(intake, fc, val)
    _shape(ex)
    assert ex["data"]["cols"][0] == "Uraian"
    assert len(ex["data"]["cols"]) == 5  # uraian + 3 tahun + terminal/total
    by = {r[0]: r for r in ex["data"]["rows"]}
    assert by["(=) Enterprise Value (Rp miliar)"][-1] == fmt.miliar(
        val["ev_gordon"])
    assert abs(val["ev_gordon"] - (val["pv_explicit"] + val["pv_terminal"])) \
        < max(val["ev_gordon"] * 1e-9, 1.0)
    assert by["(=) Nilai Wajar per Saham Gordon (Rp)"][-1] == fmt.rp(
        val["ps_gordon"])
    tp = round((val["ps_gordon"] + val["ps_exit"]) / 2 / 10) * 10
    assert tp == val["tp"]
    assert by["Nilai Wajar per Saham rata-rata Gordon+exit (Rp)"][-1] == \
        fmt.rp(val["tp"])
    # FCFF baris = fcf forecast tiap tahun (persis, bukan turunan ulang).
    fcff_row = [r for r in ex["data"]["rows"] if r[0] == "FCFF"][0]
    assert fcff_row[1:-1] == [fmt.miliar(r["fcf"]) for r in fc["rows"]]


def test_wacc_components():
    intake, fc, val = _fixture()
    ex = V.wacc_exhibit(intake, fc, val)
    _shape(ex)
    by = {r[0]: r[1] for r in ex["data"]["rows"]}
    assert by["WACC"] == fmt.pct(val["wacc"])
    assert by["(=) Cost of Equity (Rf + Beta x ERP)"] == fmt.pct(
        val["wacc_inputs"]["re"])
    rd_pre = val["wacc_inputs"]["rd_after_tax"] / (1 - (fc["rows"][0]["tax"] /
        max(fc["rows"][0]["ebit"] - fc["rows"][0]["interest"], 1)))
    assert by["Cost of Debt pra-pajak"] == fmt.pct(rd_pre)


def test_sens_base_cell():
    intake, fc, val = _fixture()
    ex = V.sens_matrix_5x3(intake, fc, val)
    _shape(ex)
    assert len(ex["data"]["rows"]) == 5  # WACC base, +-0,5pp, +-1pp
    assert len(ex["data"]["cols"]) == 4  # label + 3 g
    base = [r for r in ex["data"]["rows"] if "(base)" in r[0]][0]
    assert base[0] == f"WACC {fmt.pct(val['wacc'])} (base)"
    g0 = val["wacc_inputs"]["g"]
    gcol = [i for i, c in enumerate(ex["data"]["cols"])
            if f"g {fmt.pct(g0)} (base)" == c][0]
    assert base[gcol] == fmt.rp(val["tp"]) + " *"


def test_ddm_exact():
    bvps, coe, roae, payout, g = 1_000.0, 0.12, 0.15, 0.40, 0.035
    ex = V.ddm_exhibits(payout, roae, bvps, coe)
    _shape(ex)
    by = {r[0]: r[1] for r in ex["data"]["rows"]}
    pbv = (roae - g) / (coe - g)
    assert by["Fair P/BV (= (ROAE-g)/(CoE-g))"] == fmt.mult(pbv, dec=2)
    assert by["Nilai Wajar (= P/BV x BVPS, Rp)"] == fmt.rp(pbv * bvps)
    dps_t = roae * bvps * payout * (1 + g)
    tv = dps_t / (coe - g)
    assert by["Terminal Value (= DPS terminal/(CoE-g), Rp)"] == fmt.rp(tv)
    assert by["Nilai Wajar per Saham Gordon (Rp)"] == fmt.rp(tv / (1 + coe))


def test_rnav_exact():
    assets = [{"nama": "Tambang A", "nav": 30e12, "kepemilikan": 0.8,
               "ukuran": "100 juta ton"},
              {"nama": "Smelter B", "nav": 10e12, "kepemilikan": 0.5}]
    cash, debt, ovh, disc = 5e12, 12e12, 1e12, 0.20
    ex = V.rnav_exhibits(assets, cash, debt, ovh, SHARES, disc)
    _shape(ex)
    by = {r[0]: r[1] for r in ex["data"]["rows"]}
    total = 30e12 * 0.8 + 10e12 * 0.5
    rnav = total + cash - debt - ovh
    assert by["Jumlah NAV atribuibel (Rp miliar)"] == fmt.miliar(total)
    assert by["(=) Total RNAV (Rp miliar)"] == fmt.miliar(rnav)
    assert by["(=) Target Price (= RNAVps x (1-diskon), Rp)"] == \
        fmt.rp(rnav / SHARES * (1 - disc))
