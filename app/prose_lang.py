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
``isi_en``, ``text_en``, ``narasi_en``, ``catatan_metodologi_en``), which every
other reader of the document ignores. A sibling is attached only where both
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
import re
from collections import Counter

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


def source(id_text, en_text=None):
    """Free text from a data source, for quoting inside a template.

    Indonesian builds get `id_text`. English builds get `en_text` when the
    source provides one; otherwise `id_text`, marked so the field it lands in
    stays Indonesian."""
    if _BUILD.get() != "en" or not isinstance(id_text, str) or not id_text:
        return id_text
    if isinstance(en_text, str) and en_text.strip():
        return en_text
    return f"{_UNTRANSLATED}{id_text}{_UNTRANSLATED}"


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
            _attach_items(page.get("risks"), page_en.get("risks"), _RISK_KEYS)
            _attach_exhibits(page.get("exhibit"), page_en.get("exhibit"))
    _attach_items(doc.get("risks"), doc_en.get("risks"), _RISK_KEYS)
    _attach_exhibits(doc.get("exhibits"), doc_en.get("exhibits"))
    notes, notes_en = doc.get("catatan_metodologi"), doc_en.get("catatan_metodologi")
    if isinstance(notes, list):
        _set(doc, "catatan_metodologi", _pair_list(notes, notes_en))
    return doc


class _View:
    """Swaps English siblings in and keeps the prose that fell back."""

    def __init__(self):
        self.missing = []

    @property
    def fallback(self):
        return len(self.missing)

    def text(self, id_text, en_text):
        if isinstance(en_text, str):
            return Translated(fmt.localize(en_text, "en"))
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
