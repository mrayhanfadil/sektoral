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
document ignores. A table cell the English run wrote in English (a template's
``t``, a ``source`` quote) gets one too: ``data.rows_en`` beside ``data.rows``,
None where the cell has none, so the renderer prints it in place of the
``report_lang`` label. A sibling is attached only where both
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


# Marks a document or news title an English template quotes as published, so
# an English sentence citing an Indonesian title is not taken for one that left
# a clause untranslated; the marks never reach the attached English.
_QUOTE = "⁤"
_QUOTED = re.compile(f"{_QUOTE}[^{_QUOTE}]*{_QUOTE}")


def quoted(text):
    """A title quoted as published: marked in an English build, as is otherwise."""
    if _BUILD.get() != "en" or not isinstance(text, str) or not text:
        return text
    return f"{_QUOTE}{text}{_QUOTE}"


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


def label(id_text, en_text=None):
    """A fixed label or host-written string quoted inside a template (a driver,
    a method line, a release limitation): in an English build `en_text` (an
    agent's twin) when given, else its English from ``report_lang`` or
    ``app.host_lang`` when that states the same figures as written, a code or
    name as it is, else as ``source`` gives it."""
    if _BUILD.get() != "en" or not isinstance(id_text, str) or not id_text.strip():
        return id_text
    if isinstance(en_text, str) and en_text.strip():
        return en_text
    from . import host_lang  # it reads this module's tables
    for found in (report_lang.known(id_text), host_lang.raw(id_text)):
        if isinstance(found, str) and found.strip() and figures(found) == figures(id_text) \
                and not mixed(found):
            return found
    if language_neutral(id_text) or _amount(id_text):
        return id_text
    return source(id_text)


# Units a model value carries ("US$13.002/t", "4.455 US$/oz", "50 bp").
_UNITS = {"t", "oz", "lb", "dmt", "kt", "koz", "ha", "bp", "pp", "x", "m2"}


def _amount(text):
    """True for a figure with its units and nothing else to translate."""
    words = _LETTERS.findall(text)
    return bool(_FIGURE.search(text)) and all(w in _UNITS or w[0].isupper() for w in words) \
        and not _INDONESIAN.search(text)


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


def reads_english(text) -> bool:
    """True when agent-written text reads as English, for the checks on an agent's
    English twin (stricter than ``mixed``, which template English passes): an
    Indonesian function word must stand beside an English one."""
    if not isinstance(text, str) or not text.strip() or mixed(text):
        return False
    return not _INDONESIAN.search(text) or bool(_ENGLISH.search(text))


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
    # A quoted title is the source's own words: no clause to check, no marks kept.
    own = _QUOTED.sub("", en_text)
    en_text = en_text.replace(_QUOTE, "")
    if en_text == id_text or _UNTRANSLATED in en_text:
        return None  # not translated (yet): nothing to attach
    if figures(id_text) != figures(en_text):
        return None
    if scrub.contains_banned(own) and not scrub.contains_banned(id_text):
        return None
    if mixed(own):
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
            _attach_cells(a.get("data"), b.get("data"))


def _attach_cells(id_data, en_data):
    """``rows_en``: the cells the English run wrote in English, row by row
    (None for a row or cell without), on tables of the same shape.

    A builder whose cells later code still reads in Indonesian (the catalyst
    table, matched to model drivers by its words) keeps them Indonesian in the
    English run too and puts their English in that run's own ``rows_en``,
    which takes precedence here."""
    if not isinstance(id_data, dict) or not isinstance(en_data, dict):
        return
    rows, rows_en = id_data.get("rows"), en_data.get("rows")
    if not isinstance(rows, list) or not isinstance(rows_en, list) or len(rows) != len(rows_en):
        return
    late = en_data.get("rows_en") if isinstance(en_data.get("rows_en"), list) else []
    out = []
    for i, (a, b) in enumerate(zip(rows, rows_en)):
        cells = None
        if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
            over = late[i] if i < len(late) and isinstance(late[i], list) else []
            cells = [_pair(x, over[j] if j < len(over) and over[j] is not None else y)
                     for j, (x, y) in enumerate(zip(a, b))]
        out.append(cells if cells and any(c is not None for c in cells) else None)
    if any(row is not None for row in out):
        id_data["rows_en"] = out


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
            if isinstance(exhibit, dict):
                self.cells(exhibit.get("data"))

    @staticmethod
    def cells(data):
        """English cells with English figures; the Indonesian rows stay for the
        renderer's column kinds and row marks."""
        rows = data.get("rows_en") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return
        data["rows_en"] = [[c if c is None or isinstance(c, Translated)
                            else Translated(report_lang.plain(c)) for c in row]
                           if isinstance(row, list) else None for row in rows]


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
