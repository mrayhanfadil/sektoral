"""Five-year valuation exhibit (spec §3: valuation tables show all five forecast years)."""
from app import report_extras as RX


def _rows(bank=False):
    out = []
    for i, year in enumerate(range(2026, 2031)):
        row = {"label": f"FY{year % 100:02d}F", "earnings": 1e12 * (1 + i / 10), "eps": 100.0 + 10 * i,
               "bvps": 1000.0 + 50 * i, "dps": 50.0, "roe": 0.15, "ebitda": 2e12}
        out.append(row)
    return out


def _doc(tp=1500, rating="Buy"):
    return {"meta": {"tp": tp, "rating": rating}, "bagian": [
        {"judul": "Valuasi", "exhibit": [{"judul": "Proyeksi dividen dan nilai kini"},
                                         {"judul": "Nilai terminal dan nilai wajar per saham (DDM)"},
                                         {"judul": "Sensitivitas"}]}]}


def test_every_forecast_year_gets_price_and_target_multiples():
    intake = {"price": 1200.0, "price_date": "2026-09-24", "model_profile": "financial_ddm"}
    ex = RX.valuation_by_year(_doc(), intake, {"rows": _rows()})
    assert ex["data"]["cols"] == ["Rp", "FY26F", "FY27F", "FY28F", "FY29F", "FY30F"]
    rows = {r[0]: r[1:] for r in ex["data"]["rows"]}
    assert rows["PER pada harga (x)"][0] == "12,0x" and rows["PER pada target (x)"][0] == "15,0x"
    assert rows["PBV pada target (x)"][0] == "1,5x"
    assert rows["Dividend yield pada harga (%)"][0].startswith("4,2")


def test_it_sits_after_the_terminal_value_table_and_drafts_get_none():
    intake = {"price": 1200.0, "model_profile": "financial_ddm"}
    doc = _doc()
    RX.attach_valuation_by_year(doc, intake, {"rows": _rows()})
    titles = [e["judul"] for e in doc["bagian"][0]["exhibit"]]
    assert titles[2].startswith("Valuasi per tahun") and titles[3] == "Sensitivitas"
    assert RX.valuation_by_year(_doc(rating=None), intake, {"rows": _rows()}) is None
