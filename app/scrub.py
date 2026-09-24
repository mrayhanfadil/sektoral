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


_ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4"}
_Q_RANGE = _re.compile(r"\bQ([1-4])\s*-\s*Q([1-4])[\s-]*(20\d{2})\b", _re.I)
_Q_ONE = _re.compile(r"\bQ([1-4])[\s-]*(20\d{2})\b", _re.I)
_H_ONE = _re.compile(r"\bH([12])[\s-]*(20\d{2})\b", _re.I)
_KUARTAL = _re.compile(r"\bkuartal\s+(IV|III|II|I|[1-4])\s+(20\d{2})\b", _re.I)
_ENGINE = _re.compile(r"\bengine\b", _re.I)
_MECHANICAL = _re.compile(r"pesawat|airframe|aircraft|lessor|overhaul|\bmro\b|turbin|"
                          r"turbine|mesin|otomotif|kendaraan|motor|jet|propulsi", _re.I)


def normalize_periods(text):
    """Spec §1/§5.1 period format: Q2 2026 -> 2Q26, H1 2026 -> 1H26."""
    if not isinstance(text, str):
        return text
    text = _Q_RANGE.sub(lambda m: f"{m[1]}Q{m[3][2:]}-{m[2]}Q{m[3][2:]}", text)
    text = _Q_ONE.sub(lambda m: f"{m[1]}Q{m[2][2:]}", text)
    text = _H_ONE.sub(lambda m: f"{m[1]}H{m[2][2:]}", text)
    return _KUARTAL.sub(lambda m: f"{_ROMAN.get(m[1].upper(), m[1])}Q{m[2][2:]}", text)


def _replace_engine(text):
    def swap(m):
        window = text[max(0, m.start() - 60):m.end() + 60]
        return m[0] if _MECHANICAL.search(window) else "penggerak"
    return _ENGINE.sub(swap, text)


def normalize_prose(text):
    """Deterministic house-style pass over LLM prose (dashes, periods,
    pipeline word 'engine' outside a mechanical context)."""
    if not isinstance(text, str):
        return text
    return _replace_engine(normalize_periods(normalize_dashes(text)))


# Analyst prose fields that reach the report body. Source titles, URLs and
# timestamps are provenance and must stay exactly as supplied.
PROSE_KEYS = frozenset({"rationale", "factual_basis", "mechanism", "uncertainty", "item",
                        "timing", "driver_path", "thesis_points", "conditions",
                        "headline", "explanation", "thesis_titles"})


def normalize_plan(value, key=None):
    """Apply normalize_prose to prose fields anywhere in an agent plan."""
    if isinstance(value, dict):
        return {k: normalize_plan(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_plan(v, key) for v in value]
    if isinstance(value, str) and key in PROSE_KEYS:
        return normalize_prose(value)
    return value


def normalize_doc_prose(doc):
    """House style over every prose field of a built report (cover, section
    paragraphs, cards, risks, chart narratives). Narrative sentences built
    from issuer packs never passed normalize_plan; table cells and source
    lines are provenance and stay as supplied."""
    cover = doc.get("cover") or {}
    if isinstance(cover.get("headline"), str):
        cover["headline"] = normalize_prose(cover["headline"])
    cover["bullets"] = [normalize_prose(b) for b in cover.get("bullets") or []]
    for para in cover.get("paragraf") or []:
        if isinstance(para, dict):
            para["isi"] = normalize_prose(para.get("isi"))
            para["judul"] = normalize_prose(para.get("judul"))
    for page in doc.get("bagian") or []:
        page["paragraf"] = [normalize_prose(p) for p in page.get("paragraf") or []]
        for card in page.get("cards") or []:
            card["text"] = normalize_prose(card.get("text"))
    for risk in doc.get("risks") or []:
        risk["isi"] = normalize_prose(risk.get("isi"))
    for exhibit in doc.get("exhibits") or []:
        if isinstance(exhibit.get("narasi"), str):
            exhibit["narasi"] = normalize_prose(exhibit["narasi"])
    return doc


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
