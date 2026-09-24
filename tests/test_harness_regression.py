"""Regression: harness Tier-1 must not false-positive on Indonesian formatting."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.harness.narrative_tool import _sentences, check_narrative  # noqa: E402


def test_indonesian_thousand_separator_is_one_sentence():
    s = "Pendapatan 1H26 tumbuh 1.021,3% yoy ke US$2.052,0 juta."
    assert len(_sentences(s)) == 1


def test_bare_dollar_flagged_but_usd_allowed():
    base = {
        "meta": {"ticker": "T", "emiten": "E", "tanggal": "2026-09-24",
                 "status": "draft_non_distributable"},
        "cover": {"headline": "Puncak Capex Lewat, Arus Kas Menguat",
                  "bullets": ["Satu dua tiga.", "Empat lima enam.", "Tujuh delapan sembilan."],
                  "paragraf": [], "data_pasar": {}, "forecast_vs_guidance": [],
                  "key_financials": []},
        "bagian": [], "tabel_asumsi": [],
        "log_gate": {"S1": {}, "S2": {}, "S3": {},
                     "release": {"status": "draft_non_distributable", "blockers": []}},
        "catatan_metodologi": [],
    }
    import copy
    ok = copy.deepcopy(base)
    ok["cover"]["paragraf"] = [{"judul": "1H26: margin membaik", "isi": "Laba US$10,0 juta."}]
    ok["bagian"] = [{"halaman": 2, "judul": "Op", "paragraf": [],
                     "exhibit": [{"n": 1, "judul": "E", "tipe": "tabel",
                                  "data": {"cols": ["A"], "rows": [["1"]]},
                                  "catatan_sumber": "Source: Company, Sektoral Estimates"}]}]
    assert check_narrative(ok)["status"] == "lolos"

    bad = copy.deepcopy(ok)
    bad["cover"]["paragraf"] = [{"judul": "1H26: margin membaik", "isi": "Laba $10 miliar."}]
    r = check_narrative(bad)
    assert r["status"] == "gagal"
    assert any("Rupiah" in b for b in r["blockers"])


def test_exhibit_numbering_uses_canonical_list_after_json_roundtrip():
    import copy, json
    ex = {"n": 1, "judul": "E1", "tipe": "tabel",
          "data": {"cols": ["A"], "rows": [["1"]]},
          "catatan_sumber": "Source: Company, Sektoral Estimates"}
    doc = {
        "meta": {"ticker": "T", "emiten": "E", "tanggal": "2026-09-24",
                 "status": "draft_non_distributable"},
        "cover": {"headline": "Puncak Capex Lewat, Arus Kas Menguat",
                  "bullets": ["Satu dua tiga.", "Empat lima enam.", "Tujuh delapan sembilan."],
                  "paragraf": [], "data_pasar": {}, "forecast_vs_guidance": [],
                  "key_financials": []},
        "bagian": [{"halaman": 2, "judul": "Op", "paragraf": [],
                    "exhibit": [copy.deepcopy(ex)]}],
        "exhibits": [ex],
        "tabel_asumsi": [],
        "log_gate": {"S1": {}, "S2": {}, "S3": {},
                     "release": {"status": "draft_non_distributable", "blockers": []}},
        "catatan_metodologi": [],
    }
    doc = json.loads(json.dumps(doc))  # round-trip duplicates exhibit objects
    assert check_narrative(doc)["status"] == "lolos"
