"""Uji scrubber keluaran laporan (app/scrub.py)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import scrub as S  # noqa: E402


def test_banned_huruf_diabaikan():
    assert S.contains_banned("Data diambil dari Cache internal")
    assert S.contains_banned("Hasil ENDPOINT terbaru")
    assert not S.contains_banned("Volume penjualan tembaga membaik")


def test_banned_untai_eksak_spesifikasi():
    for b in ["kurasi skor", "sebelum masuk model", "tanpa judul",
              "aksi korporasi tercatat", "tanpa tanggal", "payload",
              "scraper", "scraping", "engine"]:
        assert S.contains_banned(f"xx {b} yy"), b
    assert not S.contains_banned("Laba bersih naik 12% yoy")


def test_clean_title_tidak_terpenggal_tengah_kata():
    t = "Kinerja kuartal ketiga dan prospek pemulihan harga komoditas"
    out = S.clean_title(t, maxlen=30)
    assert len(out) <= 30
    assert out
    awalan_asli = t[: len(out)]
    assert awalan_asli == out
    assert out == out.rstrip()
    # Tidak ada kata terpenggal: potongan satu kata lebih panjang dari kata aslinya
    for i, kata in enumerate(out.split()):
        assert kata in t.split(), (i, kata)


def test_clean_title_kasus_batas():
    t = "Smelter rampung awal tahun"
    assert S.clean_title(t, maxlen=90) == t
    assert S.clean_title(t + "  ", maxlen=90) == t
    assert S.clean_title("", maxlen=10) == ""
    assert S.clean_title("abcdefghij", maxlen=4) == ""


def test_junk_row_dibuang():
    assert S.is_junk_row(["-", "tanpa tanggal", "  "])
    assert S.is_junk_row(["-", "-", "aksi korporasi tercatat", "-"])
    assert S.is_junk_row([])
    assert not S.is_junk_row(["Harga tembaga rekor", "1Q26", "Dampak ke margin", "Positif"])
    assert not S.is_junk_row(["-", "1Q26", "penting", "Netral"])
    rows = [
        ["Harga tembaga rekor", "1Q26", "Pendukung margin", "Positif"],
        ["-", "tanpa tanggal", "-", "-"],
        ["-", "-", "-", "-"],
    ]
    bersih = S.scrub_table_rows(rows)
    assert bersih == [rows[0]]
    assert S.scrub_table_rows(None) == []


def test_fallback_jujur_tidak_kosong():
    baris = S.catalyst_fallback()
    assert isinstance(baris, list) and len(baris) == 4
    assert all(isinstance(c, str) and c.strip() for c in baris)
    gabung = " ".join(baris)
    assert not S.contains_banned(gabung)
    assert not S.is_junk_row(baris)
