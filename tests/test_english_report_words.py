"""The English Company Update reads English (#41).

Builds BBRI (on a Forecast Plan with its English twins) and AMMN (the
validated interim plan) offline, renders the English edition and reads every
visible text node: none may hold an Indonesian function word
(``prose_lang.indonesian_words``) unless the text is source data the report
quotes as it is: a document or news title, a company name, a URL.
"""
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from app import build, commodity, fx, prose_lang, rates, render, store

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF = "2026-09-24"


class _Text(HTMLParser):
    """Visible text nodes of a page (no script, style or document title)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.open, self.nodes = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in ("br", "wbr", "col", "img", "meta", "link", "input", "hr"):
            self.open.append(tag)

    def handle_endtag(self, tag):
        while self.open and self.open.pop() != tag:
            pass

    def handle_data(self, data):
        if data.strip() and not {"script", "style", "title"} & set(self.open):
            self.nodes.append(data.strip())


def _nodes(page):
    parser = _Text()
    parser.feed(page)
    return parser.nodes


# Source data quoted as it is: names of documents and news items, and companies.
_URL = re.compile(r"https?://\S+")
_SOURCE = [re.compile(p) for p in (
    r"PT [A-Z][\w.&()-]*(?: [A-Z(][\w.&()-]*)*(?: Tbk)?",   # company names
    r"Laporan Keuangan[\w ,()]*\d{4}(?: \(tidak diaudit\))?",  # issuer statement titles
)]


def _indonesian(text, quoted=()):
    text = _URL.sub("", text)
    for title in quoted:
        text = text.replace(title, "")
    for pattern in _SOURCE:
        text = pattern.sub("", text)
    return prose_lang.indonesian_words(text)


def _titles(doc):
    """Titles of the documents and news items the report cites: a title held
    beside the item's URL or publication date."""
    titles = set()

    def walk(value):
        if isinstance(value, dict):
            if {"url", "source_url", "published_at", "timestamp"} & set(value):
                titles.update(v for k, v in value.items()
                              if k in ("title", "source_title") and isinstance(v, str))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(doc)
    return sorted((t for t in titles if len(t) > 12), key=len, reverse=True)


def _english_hits(doc):
    quoted = _titles(doc)
    return [text for text in _nodes(render.render(doc, lang="en")) if _indonesian(text, quoted)]


def test_english_bbri_report_reads_english(tmp_path):
    stored = json.loads((FIXTURES / "bbri_scenario_plan_en.json").read_text())
    doc = build.build("BBRI", tmp_path, as_of=AS_OF, assumption_plan=stored["plan"],
                      assumption_status=stored["status"])
    assert _english_hits(doc) == []


def test_english_ammn_report_reads_english(tmp_path):
    from test_mining_route import COPPER, PLAN, UST_10Y, USD_IDR
    store.put(commodity.COLLECTION, "Copper", COPPER)
    store.put(fx.COLLECTION, fx.KEY, USD_IDR)
    store.put(rates.COLLECTION, rates.UST10Y, UST_10Y)
    doc = build.build("AMMN", tmp_path, as_of=AS_OF, assumption_plan=PLAN,
                      assumption_status="validated")
    assert _english_hits(doc) == []
