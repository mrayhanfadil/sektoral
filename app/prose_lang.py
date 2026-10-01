"""Report prose in Indonesian and English.

A Company Update's prose is built from templates in ``app.narrative`` and
``app.report_extras``. The pipeline (``app.build``) runs that prose stage twice
over the same inputs: once as today, in Indonesian, and once with ``building("en")``
active, where every ``t(id, en)`` template picks its English sentence. Titles,
headings and table cells stay Indonesian in both runs, so code that finds an
exhibit or a section by its title works on either document; the renderer
translates those labels (``app.report_lang``).

``attach`` then copies the English prose onto the Indonesian document as
``<field>_en`` siblings (``headline_en``, ``bullets_en``, ``paragraf_en``,
``isi_en``, ``text_en``, ``narasi_en``, ``catatan_metodologi_en``, and on the
audit appendix pages ``catatan_sumber_en``), which every other reader of the
document ignores. A sibling is attached only where both
runs produced the same structure and the English text carries exactly the
figures of its Indonesian twin, so the English edition can never state a
number the Indonesian one does not. Anything else falls back to Indonesian.

``english_view`` gives the renderer a copy of the document with the English
prose in place of the Indonesian, figures in English format, and says whether
any prose fell back.
"""
from __future__ import annotations

import contextlib
import contextvars
import copy
import functools
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from . import fmt, report_lang, scrub

LANGS = fmt.LANGS
_BUILD = contextvars.ContextVar("prose_build_lang", default="id")


def lang() -> str:
    """The language the prose stage is building in."""
    return _BUILD.get()


def english() -> bool:
    return _BUILD.get() == "en"


def t(id: str, en: str) -> str:
    """The template for the language being built: `id` unless building English.

    Figures go into both through the same Indonesian ``fmt`` calls; the
    English edition formats them when it renders."""
    return en if _BUILD.get() == "en" else id


# Marks Indonesian source text (an issuer pack, a curated name) that an English
# template had to quote because the source has no English form. Any prose field
# carrying it falls back to Indonesian whole, so no sentence mixes languages.
_UNTRANSLATED = "\u2063"


# English for Indonesian source text (issuer evidence, curated names), one file
# per ticker or topic, keyed by the exact Indonesian text. It lives outside the
# hashed source packs, so a translation never changes their evidence; when the
# source text changes, its old translation no longer matches and the field
# falls back to Indonesian.
SOURCE_TEXT_DIR = Path(__file__).resolve().parent.parent / "data" / "source_text_en"


@functools.lru_cache(maxsize=1)
def _source_text() -> dict:
    found = {}
    for path in sorted(SOURCE_TEXT_DIR.glob("*.json")):
        found.update(json.loads(path.read_text(encoding="utf-8")))
    return found


def source_text_sha256() -> str:
    """SHA-256 of the translations loaded from ``data/source_text_en``.

    The run manifest records it (``source_text_en_sha256``), so a translation
    edit that changes a report's English shows up as a new manifest."""
    blob = json.dumps(_source_text(), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def source(id_text, en_text=None):
    """Free text from a data source, for quoting inside a template.

    Indonesian builds get `id_text`. English builds get `en_text`, or the
    English of `id_text` in ``data/source_text_en``; failing both, `id_text`
    marked so the field it lands in stays Indonesian."""
    if _BUILD.get() != "en" or not isinstance(id_text, str) or not id_text:
        return id_text
    if isinstance(en_text, str) and en_text.strip():
        return en_text
    known = _source_text().get(id_text)
    if isinstance(known, str) and known.strip():
        return known
    from . import source_patterns  # model text built before the prose stage
    for pattern, template in source_patterns.PATTERNS:
        found = pattern.fullmatch(id_text)
        if found:
            return template.format(*(g or "" for g in found.groups()))
    return f"{_UNTRANSLATED}{id_text}{_UNTRANSLATED}"


def known(id_text) -> str | None:
    """The English ``source`` gives Indonesian source or model text, or None
    when it has none (the web app's ``_en`` twins, outside a build)."""
    if not isinstance(id_text, str) or not id_text.strip():
        return None
    token = _BUILD.set("en")
    try:
        found = source(id_text)
    finally:
        _BUILD.reset(token)
    if not isinstance(found, str) or found == id_text or _UNTRANSLATED in found:
        return None
    return found


@contextlib.contextmanager
def building(language: str):
    """Build prose in `language` inside the block."""
    if language not in LANGS:
        raise ValueError(f"unknown prose language {language!r}")
    token = _BUILD.set(language)
    try:
        yield
    finally:
        _BUILD.reset(token)


class Translated(str):
    """Prose already in English with English figures: not to be localized again."""


# Figures as the builder writes them (Indonesian format): 1.234,5 / 12,4 / 2026 / 1H26.
_FIGURE = re.compile(r"\d+(?:[.,]\d+)*")


def figures(text) -> Counter:
    """The figures a sentence states, as written, for comparing two editions."""
    return Counter(_FIGURE.findall(text)) if isinstance(text, str) else Counter()


# Indonesian function words. English text holding two or more of them still
# carries an untranslated clause (a helper outside the templates, agent text
# changed only by client copy), so it is not attached.
_INDONESIAN = re.compile(
    r"\b(yang|dan|dari|untuk|pada|dengan|tidak|belum|karena|sebesar|menjadi|adalah|dalam|"
    r"terhadap|sebagai|atau|oleh|akan|ini|itu|naik|turun|tahun|masih|bila|jika|tetap|hanya|"
    r"sudah|agar|serta)\b", re.I)


def indonesian_words(text) -> set:
    """The Indonesian function words `text` holds, lowercase."""
    return {w.lower() for w in _INDONESIAN.findall(text)} if isinstance(text, str) else set()


def mixed(text) -> bool:
    """True when English text still reads partly Indonesian.

    Two words, not one: template English may quote an Indonesian name ("PT
    Industri Jamu Dan Farmasi"). Code that pieces English together from parts
    holds each part it did not translate to ``indonesian_words`` being empty."""
    return len(indonesian_words(text)) >= 2


_ENGLISH = re.compile(
    r"\b(the|a|an|of|to|in|on|for|and|or|with|from|by|at|as|is|are|was|were|be|been|not|no|"
    r"its|their|this|that|these|than|into|over|under|while|after|before|could|may|might|would|"
    r"will|can|has|have|had|does|do|if|but|more|less)\b", re.I)


# Indonesian content words common in issuer evidence, news and report prose:
# finance, operations, time and the verbs analysts use. A short phrase may carry
# no function word at all ("Kualitas aset kredit UMKM"); these give it away.
# None is an English word ("modal", "armada", "jumbo", "data", "margin" stay
# out), and words that often sit in Indonesian names ("sumber", "tengah",
# "baru", "tambang", "listrik", "utama", "antara") stay out too. Checked against
# every English twin stored in Oct 2026: none of them reads Indonesian by it.
_INDONESIAN_CONTENT = frozenset("""
    rilis di ke juga lagi telah sedang bisa dapat harus perlu boleh bukan tanpa agar
    namun tetapi tapi sehingga sejak hingga sampai setelah sebelum saat ketika
    sementara seiring sejalan meski walau maupun bahwa apakah tersebut menuju
    atas bawah dekat jauh luar depan akhir awal tiap setiap semua seluruh
    sebagian lebih kurang sangat cukup sama lainnya sendiri sekaligus terlalu jadi
    satu dua tiga empat enam tujuh delapan sembilan sepuluh ratus ribu
    hari minggu bulan kuartal kuartalan tahunan bulanan harian mingguan musim
    januari februari maret juni juli agustus oktober desember liburan
    laba rugi bersih kotor pendapatan penjualan harga saham emiten biaya beban
    bunga dana kredit utang pinjaman kerja ekuitas aset liabilitas penyusutan
    kas arus neraca pajak dividen tunai nilai valuasi pasar asing pokok cadang
    pertumbuhan kenaikan penurunan pelemahan penguatan perlambatan pemulihan
    tekanan risiko kualitas konsentrasi ekspansi produksi permintaan pasokan
    kapasitas utilisasi kontrak proyek lahan pabrik bahan baku pakan emas
    tembaga katoda konsentrat bijih logam kurs selisih suku kebijakan
    pemangkasan penyesuaian pembayaran pendanaan penyaluran simpanan tabungan
    deposito nasabah pelanggan konsumen daya beli impor ekspor jual swasta
    usaha industri sektor segmen grup induk anak entitas kelompok produsen
    perusahaan kinerja hasil angka rasio skenario asumsi historis analis
    perubahan pergerakan perdagangan transaksi kepemilikan pemegang pendiri
    konsolidasi akuisisi restrukturisasi reorganisasi kuasi provisi cadangan
    persediaan piutang tagihan belanja investasi pemeliharaan operasi
    operasional konstruksi properti pesawat kapal kabel laut
    jadwal tahap rencana metode panduan resmi tercatat terukur terlapor
    laporan keuangan berita artikel kutipan catatan daftar profil metrik
    tabel grafik halaman rincian rentang kisaran batas ambang porsi bobot
    tinggi rendah besar kecil stabil terjaga tipis tebal puncak riwayat
    kuat lemah cepat lambat baik buruk positif negatif moderat agresif murni
    efisiensi efektif profitabilitas dominasi volatilitas visibilitas intensitas
    normalisasi diversifikasi validasi verifikasi regulasi renegosiasi reaktivasi
    eksekusi suksesi transisi generasi sertifikasi sertifikat strategi potensi
    posisi skala akses progres manajemen gangguan lonjakan bantalan pembanding
    pencapaian penyerapan ketidakpastian jangka panjang pendek pihak bukti
    terkini tingkat buku tanah uang muka jumlah faktor tanggal pemerintah
    wajib lengkap kelola sebanding diskonto
    tumbuh melambat melemah menguat meningkat menurun melonjak membaik memburuk
    menekan menopang mendukung menahan menjaga mencapai mencatat mencatatkan
    menunjukkan mencerminkan menjelaskan menyebut memakai membawa memberi
    mengubah menambah mengurangi menurunkan menaikkan meningkatkan membebani
    mendekati menyusun kembali mulai dukung perkuat uji rampung diakses
    berlanjut berulang bertahan bertahap terlihat
    tertekan terkoreksi tertunda tertinggi terendah terbesar terbaru terakhir
    terhadap dibanding dibandingkan didukung ditopang dipakai dihitung
    """.split())

# Figure units, which the builder writes in Indonesian in both editions
# ("Rp84,3miliar"): a word of neither language.
_UNITS = frozenset({"rp", "miliar", "juta", "triliun"})
# Indonesian affixes no lowercase English word takes ("harganya", "menurunkan",
# "alokasi", "likuiditas", "kuantitatif", "mengalami", "eksposur",
# "keterlambatan", "pengakuan", "menjadi"), checked against an English
# dictionary. Capitalised words are left to the list: "Bekasi" is a name.
_INDONESIAN_AFFIX = re.compile(
    r"[a-z]{3,}(?:nya|kan|asi|itas|tif)|(?:meng|meny|peny|eks)[a-z]{3,}"
    r"|(?:ke|pem|pen|per)[a-z]{3,}an|(?:mem|men)[a-z]{3,}(?:kan|i)")
_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_CODE = re.compile(r"[A-Z]+")


def _indonesian_share(text) -> tuple[int, int]:
    """(Indonesian words, words) in `text`, leaving out URLs, codes and names.

    A code ("UMKM", "NIM") or a unit counts as neither. A run of capitalised
    words after the first word is a name ("PT Sumber Gemilang Persada",
    "Bisnis Indonesia") and is left out unless every word in it is Indonesian
    ("Harga Emas")."""
    words = [w for w in _LETTERS.findall(_URL.sub(" ", text))
             if not _CODE.fullmatch(w) and w.lower() not in _UNITS]
    hits = [w.lower() in _INDONESIAN_CONTENT or bool(_INDONESIAN.fullmatch(w))
            or bool(_INDONESIAN_AFFIX.fullmatch(w)) for w in words]
    keep = [True] * len(words)
    i = 1  # the first word is capitalised as the start of the text, not as a name
    while i < len(words):
        j = i
        while j < len(words) and words[j][0].isupper():
            j += 1
        if j - i >= 2 and not all(hits[i:j]):
            keep[i:j] = [False] * (j - i)
        i = max(j, i + 1)
    counted = [hit for hit, kept in zip(hits, keep) if kept]
    return sum(counted), len(counted)


def reads_english(text) -> bool:
    """True when agent-written text reads as English, for the checks on an agent's
    English twin (stricter than ``mixed``, which template English passes): an
    Indonesian function word must stand beside an English one, and fewer than
    half of its words may be Indonesian, so a short Indonesian phrase with no
    function word ("Kualitas aset kredit UMKM") does not pass."""
    if not isinstance(text, str) or not text.strip() or mixed(text):
        return False
    if _INDONESIAN.search(text) and not _ENGLISH.search(text):
        return False
    indonesian, words = _indonesian_share(text)
    return not indonesian or 2 * indonesian < words


# A run of letters, for telling codes and names from prose.
_LETTERS = re.compile(r"[^\W\d_]+")


def language_neutral(text) -> bool:
    """True when agent-written text is the same in both languages: codes, periods,
    figures and names ("3Q26", "FY2026", "2H26", "Bank Indonesia"), with no
    function word of either language and no lowercase word. Its English twin may
    repeat it; a twin repeating Indonesian prose ("Penurunan suku bunga") may not."""
    if not isinstance(text, str) or not text.strip():
        return False
    if _INDONESIAN.search(text) or _ENGLISH.search(text):
        return False
    return all(word[0].isupper() for word in _LETTERS.findall(text))


def _pair(id_text, en_text):
    """The English twin of one prose string, or None when it may not be attached."""
    if not isinstance(id_text, str) or not isinstance(en_text, str) or not en_text.strip():
        return None
    if en_text == id_text or _UNTRANSLATED in en_text:
        return None  # not translated (yet): nothing to attach
    if figures(id_text) != figures(en_text):
        return None
    if scrub.contains_banned(en_text) and not scrub.contains_banned(id_text):
        return None
    if mixed(en_text):
        return None
    return en_text


def _pair_list(id_list, en_list):
    if not isinstance(id_list, list) or not isinstance(en_list, list) or len(id_list) != len(en_list):
        return None
    out = [_pair(a, b) for a, b in zip(id_list, en_list)]
    return out if any(v is not None for v in out) else None


def _set(target: dict, key: str, value):
    if value is not None:
        target[f"{key}_en"] = value


def _attach_paragraphs(id_host: dict, en_host: dict):
    """``paragraf``: a list of strings, or of ``{judul, isi}`` dicts."""
    id_paras, en_paras = id_host.get("paragraf"), en_host.get("paragraf")
    if not isinstance(id_paras, list) or not isinstance(en_paras, list) or len(id_paras) != len(en_paras):
        return
    strings = [None] * len(id_paras)
    for i, (a, b) in enumerate(zip(id_paras, en_paras)):
        if isinstance(a, str):
            strings[i] = _pair(a, b)
        elif isinstance(a, dict) and isinstance(b, dict):
            for key in ("isi", "text"):
                _set(a, key, _pair(a.get(key), b.get(key)))
    if any(v is not None for v in strings):
        id_host["paragraf_en"] = strings


def _attach_items(id_items, en_items, keys):
    """Cards and risks: lists of dicts whose `keys` hold prose."""
    if not isinstance(id_items, list) or not isinstance(en_items, list) or len(id_items) != len(en_items):
        return
    for a, b in zip(id_items, en_items):
        if isinstance(a, dict) and isinstance(b, dict):
            for key in keys:
                _set(a, key, _pair(a.get(key), b.get(key)))


_CARD_KEYS = ("title", "text", "observation", "implication", "caveat")
_RISK_KEYS = ("judul", "isi")
# The research page's cards (``research_cards``): the agent's insight prose.
_RESEARCH_KEYS = ("title", "observation", "implication", "caveat")


def _attach_exhibits(id_exhibits, en_exhibits):
    if not isinstance(id_exhibits, list) or not isinstance(en_exhibits, list) or len(id_exhibits) != len(en_exhibits):
        return
    for a, b in zip(id_exhibits, en_exhibits):
        if isinstance(a, dict) and isinstance(b, dict) and a.get("judul") == b.get("judul"):
            _set(a, "narasi", _pair(a.get("narasi"), b.get("narasi")))


def attach(doc: dict, doc_en: dict) -> dict:
    """Copy the English prose of `doc_en` onto `doc` as ``_en`` siblings (in place)."""
    cover, cover_en = doc.get("cover"), (doc_en or {}).get("cover")
    if isinstance(cover, dict) and isinstance(cover_en, dict):
        _set(cover, "headline", _pair(cover.get("headline"), cover_en.get("headline")))
        _set(cover, "bullets", _pair_list(cover.get("bullets"), cover_en.get("bullets")))
        _attach_paragraphs(cover, cover_en)
    pages, pages_en = doc.get("bagian"), doc_en.get("bagian")
    if isinstance(pages, list) and isinstance(pages_en, list) and len(pages) == len(pages_en):
        for page, page_en in zip(pages, pages_en):
            if not (isinstance(page, dict) and isinstance(page_en, dict)) or \
                    page.get("judul") != page_en.get("judul"):
                continue
            _attach_paragraphs(page, page_en)
            _attach_items(page.get("cards"), page_en.get("cards"), _CARD_KEYS)
            _attach_items(page.get("research_cards"), page_en.get("research_cards"), _RESEARCH_KEYS)
            _attach_items(page.get("risks"), page_en.get("risks"), _RISK_KEYS)
            _attach_exhibits(page.get("exhibit"), page_en.get("exhibit"))
    _attach_items(doc.get("risks"), doc_en.get("risks"), _RISK_KEYS)
    _attach_exhibits(doc.get("exhibits"), doc_en.get("exhibits"))
    notes, notes_en = doc.get("catatan_metodologi"), doc_en.get("catatan_metodologi")
    if isinstance(notes, list):
        _set(doc, "catatan_metodologi", _pair_list(notes, notes_en))
    # The audit appendix is not printed; the web trace page shows it, source notes too.
    audit, audit_en = doc.get("lampiran_audit"), doc_en.get("lampiran_audit")
    if isinstance(audit, list) and isinstance(audit_en, list) and len(audit) == len(audit_en):
        for page, page_en in zip(audit, audit_en):
            if not (isinstance(page, dict) and isinstance(page_en, dict)) or \
                    page.get("judul") != page_en.get("judul"):
                continue
            _attach_paragraphs(page, page_en)
            _attach_exhibits(page.get("exhibit"), page_en.get("exhibit"))
            _attach_source_notes(page.get("exhibit"), page_en.get("exhibit"))
    return doc


def _attach_source_notes(id_exhibits, en_exhibits):
    if not isinstance(id_exhibits, list) or not isinstance(en_exhibits, list) or \
            len(id_exhibits) != len(en_exhibits):
        return
    for a, b in zip(id_exhibits, en_exhibits):
        if isinstance(a, dict) and isinstance(b, dict) and a.get("judul") == b.get("judul"):
            _set(a, "catatan_sumber", _pair(a.get("catatan_sumber"), b.get("catatan_sumber")))


class _View:
    """Swaps English siblings in and keeps the prose that fell back."""

    def __init__(self):
        self.missing = []

    @property
    def fallback(self):
        return len(self.missing)

    def text(self, id_text, en_text):
        if isinstance(en_text, str):
            return Translated(report_lang.plain(en_text))
        if isinstance(id_text, str) and id_text.strip():
            self.missing.append(id_text)
        return id_text

    def field(self, host: dict, key: str):
        # A page's exhibits are the same objects as the document's: swap once.
        if isinstance(host.get(key), Translated):
            return
        if key in host or f"{key}_en" in host:
            host[key] = self.text(host.get(key), host.pop(f"{key}_en", None))

    def strings(self, host: dict, key: str, known=None):
        """A list of prose; `known(text)` says an Indonesian item the renderer translates itself."""
        values = host.get(key)
        if not isinstance(values, list):
            return
        english = host.pop(f"{key}_en", None) or [None] * len(values)
        out = []
        for a, b in zip(values, english):
            if b is None and known and known(a):
                out.append(a)
            else:
                out.append(self.text(a, b))
        host[key] = out

    def paragraphs(self, host: dict):
        paras = host.get("paragraf")
        if not isinstance(paras, list):
            return
        english = host.pop("paragraf_en", None) or [None] * len(paras)
        out = []
        for a, b in zip(paras, english):
            if isinstance(a, dict):
                for key in ("isi", "text"):
                    self.field(a, key)
                out.append(a)
            else:
                out.append(self.text(a, b))
        host["paragraf"] = out

    def items(self, items, keys):
        for item in items or []:
            if isinstance(item, dict):
                for key in keys:
                    self.field(item, key)

    def exhibits(self, exhibits):
        for exhibit in exhibits or []:
            if isinstance(exhibit, dict) and (exhibit.get("narasi") or exhibit.get("narasi_en")):
                self.field(exhibit, "narasi")


def english_view(doc: dict, missing: list | None = None) -> tuple[dict, int]:
    """A copy of `doc` with English prose in place and how many prose fields fell back.

    `missing`, when given, receives the Indonesian prose that fell back."""
    view = copy.deepcopy(doc)
    v = _View()
    cover = view.get("cover")
    if isinstance(cover, dict):
        v.field(cover, "headline")
        v.strings(cover, "bullets")
        v.paragraphs(cover)
    for page in view.get("bagian") or []:
        if isinstance(page, dict):
            v.paragraphs(page)
            v.items(page.get("cards"), _CARD_KEYS)
            v.items(page.get("research_cards"), _RESEARCH_KEYS)
            v.items(page.get("risks"), _RISK_KEYS)
            v.exhibits(page.get("exhibit"))
    v.items(view.get("risks"), _RISK_KEYS)
    v.exhibits(view.get("exhibits"))
    if isinstance(view.get("catatan_metodologi"), list):
        v.strings(view, "catatan_metodologi",
                  known=lambda note: report_lang.note(note, "en") != note)
    if missing is not None:
        missing.extend(v.missing)
    return view, v.fallback
