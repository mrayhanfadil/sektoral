"""Check that reference-style fields are tied to sourced release evidence."""
from app import build, intake, rating


def test_gmfi_uses_official_1h26_without_promoting_screen_to_rating(tmp_path):
    raw, _ = intake.load("GMFI")
    actual = raw["latest_official_actual"]
    assert actual["period"] == "1H26"
    assert actual["metrics"]["revenue"] == 270_288_955
    assert raw["official_evidence"]["balance_sheet"]["shares_issued"] == 124_835_258_434

    doc = build.build("GMFI", tmp_path)
    assert doc["meta"]["status"] == "draft_non_distributable"
    assert "rating" not in doc["meta"] and "tp" not in doc["meta"]
    assert doc["cover"]["data_pasar"]["saham"] == 124_835_258_434
    latest = next(e for e in doc["exhibits"] if e["judul"].startswith("Hasil interim resmi"))
    assert latest["data"]["cols"] == ["Metrik", "1H25", "1H26", "yoy"]
    assert latest["data"]["rows"][0] == ["Pendapatan (US$ juta)", "179,0", "270,3", "51,0%"]
    assert "Target Harga (Rp)" in (tmp_path / "GMFI.html").read_text()


def test_rating_bands_are_used_only_after_release():
    assert rating.classify(0.151) == "Buy"
    assert rating.classify(0.15) == "Hold"
    assert rating.classify(-0.10) == "Hold"
    assert rating.classify(-0.101) == "Sell"
