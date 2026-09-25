"""Sourced data blocks in the issuer evidence packs that the report builders
read or will read: AMMN annual operations (volume and unit cost chart) and
BBCA shareholders (cover stats block)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data" / "issuer_evidence"


def _pack(ticker):
    return json.loads((ROOT / f"{ticker}.json").read_text(encoding="utf-8"))


def test_ammn_annual_operations_are_sourced_actuals_for_2024_and_2025():
    ops = _pack("AMMN")["annual_operations"]
    assert ops["status"] == "aktual"
    rows = {r["year"]: r for r in ops["rows"]}
    assert set(rows) == {2024, 2025}
    for row in rows.values():
        for key in ("source_title", "source_url", "published_at", "page"):
            assert row[key], key
        assert row["source_url"].startswith("https://www.amman.co.id/")
        assert row["published_at"] >= f"{row['year'] + 1}-01-01"
    # FY2025 Earnings Release p.3 (FY2024 column cross-checked to the FY2024 release p.3).
    assert (rows[2024]["copper_mlb"], rows[2024]["gold_koz"], rows[2024]["c1_cost_usd_lb"]) == (395, 802.749, -3.37)
    assert (rows[2025]["copper_mlb"], rows[2025]["gold_koz"], rows[2025]["c1_cost_usd_lb"]) == (209, 102.758, -0.54)


def test_bbca_shareholders_tie_to_listed_shares_and_feed_the_holder_format():
    block = _pack("BBCA")["shareholders"]
    assert block["status"] == "aktual" and block["source_url"].startswith("https://www.idx.co.id/")
    rows = block["rows"]
    # Sectors ownership format: fraction of listed shares, name "Masyarakat" = public.
    for row in rows:
        assert 0 <= row["share_percentage"] < 1
        assert abs(row["share_amount"] / block["listed_shares"] - row["share_percentage"]) < 5e-5
    public = next(r for r in rows if r["name"] == "Masyarakat")
    assert public["share_amount"] == sum(c["share_amount"] for c in public["components"])
    controller = next(r for r in rows if r.get("controlling"))
    assert controller["name"] == "PT Dwimuria Investama Andalan" and controller["share_percentage"] > 0.5
