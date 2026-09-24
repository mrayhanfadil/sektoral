"""Harness narrative + schema + news curation (§5, §6, §7)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.harness import check_narrative, check_output_schema, score_news  # noqa: E402


def _doc_ok():
    return {
        "meta": {"ticker": "TEST", "emiten": "Test", "tanggal": "2026-09-22",
                 "model_profile": "going_concern_fcff",
                 "status": "draft_non_distributable",
                 "status_rating": "Dalam peninjauan", "harga": 1000},
        "cover": {
            "headline": "Puncak Capex Lewat, Arus Kas Bebas Menguat",
            "bullets": ["Pendapatan 1H26 tumbuh 5% ke Rp3,1 triliun, menopang laba.",
                        "Utilisasi naik mendukung margin ke depan.",
                        "Dalam peninjauan, menunggu model production-ready."],
            "paragraf": [{"judul": "1H26: volume pulih, margin membaik",
                          "isi": "Pendapatan mencapai Rp3,1 triliun. Ini menopang laba."},
                         {"judul": "Utilisasi mendorong laba ke depan",
                          "isi": "Utilisasi naik. Dampaknya ke margin positif."},
                         {"judul": "Valuasi menunggu rekonsiliasi model",
                          "isi": "Model belum production-ready. Rating ditahan."}],
            "data_pasar": {}, "forecast_vs_guidance": [], "key_financials": [],
        },
        "bagian": [
            {"halaman": 2, "judul": "Operasi", "paragraf": ["Utilisasi FY26 naik."],
             "exhibit": [{"n": 1, "judul": "Pendapatan", "tipe": "tabel",
                          "data": {"cols": ["A"], "rows": [["1"]]},
                          "catatan_sumber": "Source: Company, Sektoral Estimates"}]},
            {"halaman": 5, "judul": "Valuasi", "paragraf": ["Menunggu rekonsiliasi."],
             "exhibit": [{"n": 2, "judul": "Bridge", "tipe": "tabel",
                          "data": {"cols": ["A"], "rows": [["2"]]},
                          "catatan_sumber": "Source: Company, Sektoral Estimates"}]},
        ],
        "tabel_asumsi": [],
        "log_gate": {"G1": {}, "G2": {}, "G3": {},
                     "release": {"status": "draft_non_distributable", "blockers": ["x"]}},
        "catatan_metodologi": ["Model dalam peninjauan."],
    }


def test_narrative_passes_clean_doc():
    r = check_narrative(_doc_ok())
    assert r["status"] == "lolos", r


def test_narrative_blocks_pipeline_terms_and_dash():
    d = _doc_ok()
    d["cover"]["paragraf"][0]["isi"] = "Hasil endpoint payload — dengan engine deterministik."
    r = check_narrative(d)
    assert r["status"] == "gagal"
    assert any("pipeline" in b or "dash" in b for b in r["blockers"])


def test_narrative_blocks_bad_period_and_long_headline():
    d = _doc_ok()
    d["cover"]["headline"] = "Multiple 2026 di 17,99x vs mid-cycle 28,42x untuk valuasi saham hari ini esok"
    d["cover"]["paragraf"][0]["isi"] = "Pada Kuartal I 2026 laba naik."
    r = check_narrative(d)
    assert r["status"] == "gagal"
    assert any("headline" in b or "periode" in b for b in r["blockers"])


def test_narrative_blocks_draft_with_tp():
    d = _doc_ok()
    d["meta"]["tp"] = 1500
    r = check_narrative(d)
    assert any("tp_draft" in b.lower() or "TP" in b for b in r["blockers"])


def test_score_news_keeps_only_total_ge_7_max_7():
    items = [
        {"id": "a", "dampak": 3, "materialitas": 3, "durabilitas": 2, "kebaruan": 2,
         "jenis": "operasi"},
        {"id": "b", "dampak": 1, "materialitas": 1, "durabilitas": 1, "kebaruan": 1,
         "jenis": "operasi"},
        {"id": "c", "dampak": 3, "materialitas": 3, "durabilitas": 3, "kebaruan": 3,
         "jenis": "harga_harian"},
    ]
    r = score_news(items)
    assert [x["id"] for x in r["curated"]] == ["a"]
    assert len(r["cover_max_3"]) <= 3
    assert {d["id"] for d in r["dropped"]} == {"b", "c"}


def test_schema_blocks_draft_with_rating():
    d = _doc_ok()
    d["meta"]["rating"] = "Buy"
    r = check_output_schema(d)
    assert r["status"] == "gagal"


def test_schema_passes_clean_doc():
    assert check_output_schema(_doc_ok())["status"] == "lolos"
