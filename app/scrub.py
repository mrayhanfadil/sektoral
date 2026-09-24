"""Pembersih teks dan baris tabel untuk keluaran laporan.

Menjaga dokumen klien bebas dari istilah internal, memastikan judul
terpotong di batas kata, dan membuang baris tabel yang tidak membawa
informasi.
"""

BANNED = [
    "kurasi skor",
    "skor ",
    "sebelum masuk model",
    "endpoint",
    "payload",
    "cache",
    "scraper",
    "scraping",
    "log ",
    "engine",
    "tanpa tanggal",
    "aksi korporasi tercatat",
    "tanpa judul",
]

_SEL_KOSONG = frozenset({"", "-", "--", "\u2013", "\u2014", "n/a", "na", "tidak tersedia"})

_FRASE_HAMPA = ("tanpa tanggal", "aksi korporasi tercatat", "tanpa judul")


import re as _re

_DASH_RANGE = _re.compile(r"(?<=\d)\s*[\u2013\u2014]\s*(?=\d)")
_DASH_CLAUSE = _re.compile(r"\s*[\u2013\u2014]\s*")


def normalize_dashes(text):
    """Spec §5.1 bans em/en dashes: numeric ranges become '-', clause
    dashes become ', '. Used on LLM prose before it reaches the report."""
    if not isinstance(text, str):
        return text
    return _DASH_CLAUSE.sub(", ", _DASH_RANGE.sub("-", text))


def contains_banned(text):
    """True bila teks memuat salah satu untai BANNED (huruf diabaikan)."""
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(b in t for b in BANNED)


def clean_title(title, maxlen=90):
    """Rapikan judul dan potong di batas kata, tidak pernah tengah kata."""
    if not isinstance(title, str):
        return ""
    s = " ".join(title.split())
    if maxlen <= 0 or not s:
        return ""
    if len(s) <= maxlen:
        return s
    pot = s[:maxlen]
    if s[maxlen] == " " or pot.endswith(" "):
        return pot.rstrip()
    sp = pot.rfind(" ")
    if sp <= 0:
        return ""
    return pot[:sp]


def _sel_hampa(cell):
    if cell is None:
        return True
    if not isinstance(cell, str):
        return False
    s = " ".join(cell.split()).lower()
    if s in _SEL_KOSONG:
        return True
    return any(f in s for f in _FRASE_HAMPA)


def is_junk_row(cells):
    """True bila seluruh sel kosong atau hanya penanda hampa."""
    if cells is None:
        return True
    if isinstance(cells, str):
        return _sel_hampa(cells)
    if not cells:
        return True
    return all(_sel_hampa(c) for c in cells)


def scrub_table_rows(rows):
    """Buang baris sampah, kembalikan daftar baru dengan urutan sama."""
    if not rows:
        return []
    return [r for r in rows if not is_junk_row(r)]


def catalyst_fallback():
    """Satu baris pengganti yang jujur untuk tabel katalis yang kosong."""
    return [
        "Belum ada katalis terkurasi",
        "Menunggu rilis berikutnya",
        "Dampak ke pendorong belum teridentifikasi dari informasi yang tersedia",
        "Netral",
    ]
