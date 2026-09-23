"""Regression coverage for the RNAV exhibit's monetary units."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import forecast, fmt, intake, narrative, valuation  # noqa: E402


def test_ammn_rnav_exhibit_uses_rupiah_consistently():
    doc_in, g1 = intake.load("AMMN")
    fc = forecast.build(doc_in)
    va = valuation.build(doc_in, fc)
    exhibit = narrative._rnav_exhibit(
        va["lom"], fc["base"]["cash"], fc["base"]["debt"], doc_in["shares"])
    rows = {row[0]: row[1] for row in exhibit["data"]["rows"]}

    # Both asset NAVs are positive; neither should be rounded to zero in the
    # Rp billion exhibit after converting from the model's Rp billion units.
    asset_rows = [(label, value) for label, value in rows.items()
                  if label.startswith(("Tembaga", "Emas"))]
    assert len(asset_rows) == 2
    assert all(value != fmt.miliar(0) for _, value in asset_rows)

    # The printed bridge must reconcile to the LoM value calculated by rnav.
    expected_rnav_rpbn = va["lom"]["rnav_rpbn"]
    assert rows["(=) Total RNAV (Rp miliar)"] == fmt.miliar(
        expected_rnav_rpbn * 1e9)
    assert rows["(=) RNAV per saham (Rp)"] == fmt.rp(va["lom"]["rnav_ps"])
