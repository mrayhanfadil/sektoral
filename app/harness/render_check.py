"""Template checks on what a reader sees: the rendered HTML and the PDF text.

Rules of spec/Struktur-Template.md that only exist after rendering (the exact
source line under every exhibit, the running header and footer, the exhibit
numbers in reading order, highlights, bracketed negatives) are checked here;
``app/harness/template.py`` checks the report document. Mapping and severity
policy: ``docs/harness-template-rules.md``.

The HTML is read with the standard-library parser into visible text lines in
document order (one line per block element, table cell or SVG text), so the
checks follow the reading order and do not depend on class names, except where
a rule is about styling (highlighted rows, dashed band lines).
"""
from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser

BLOCKER, WARNING = "blocker", "warning"
PASS, FAIL, NA = "lolos", "gagal", "tidak_berlaku"
HOUSE_SOURCE = "Source: Company, Sektoral Estimates"
DISCLOSURE = "See important disclosure at the back of this report"

RENDER_CHECKS: dict[str, tuple[str, str, str]] = {
    "T1.source_line": (BLOCKER, "layout", "source line tepat 'Source: Company, Sektoral Estimates' di bawah tiap exhibit"),
    "T1.numbering_rendered": (BLOCKER, "layout", "caption Exhibit N berurutan 1..N"),
    "T1.exhibit_label_rendered": (WARNING, "layout", "setiap objek punya caption 'Exhibit N. judul'"),
    "T1.source_appendix": (WARNING, "layout", "lampiran sumber di akhir laporan untuk tiap exhibit"),
    "T1.header": (WARNING, "layout", "header 'KODE IJ | RATING · TP', 'Equity Research - Company Update | DD Mon YYYY', logo"),
    "T1.footer": (WARNING, "layout", "footer 'sectors.app', disclosure, nomor halaman"),
    "T2.price_box_rendered": (WARNING, "layout", "kotak harga: harga, TP, upside bertanda satu desimal"),
    "T2.relative_chart_rendered": (WARNING, "layout", "chart relatif IHSG 12-24 bulan, label bulan"),
    "T2.analyst_block": (WARNING, "layout", "blok analis 'Equity Analyst'"),
    "T2.company_header": (WARNING, "layout", "nama emiten + (TICKER IJ)"),
    "T4.sensitivity_highlight_rendered": (WARNING, "layout", "sel/baris basis sensitivitas disorot"),
    "T5.peer_highlight_rendered": (WARNING, "layout", "baris emiten dan median/rata-rata peer disorot"),
    "T5.band_lines_rendered": (WARNING, "layout", "band: garis mean dan median beda gaya + penanda kini"),
    "TN.negatives_brackets": (WARNING, "layout", "angka negatif dalam kurung"),
    "T1.source_line.pdf": (BLOCKER, "layout", "source line tepat di PDF"),
    "T1.numbering_rendered.pdf": (BLOCKER, "layout", "caption Exhibit N berurutan di PDF"),
    "T1.header.pdf": (WARNING, "layout", "header tiap halaman PDF"),
    "T1.footer.pdf": (WARNING, "layout", "footer tiap halaman PDF"),
    "R.render_error": (BLOCKER, "layout", "laporan dapat dirender"),
}

_VOID = {"br", "img", "meta", "link", "col", "hr", "input", "source", "wbr", "area", "base"}
_BLOCK = {"div", "p", "caption", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "li", "ul",
          "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br", "section", "article", "header", "footer",
          "svg", "text", "figcaption", "figure", "main", "nav", "aside", "blockquote", "pre",
          "dl", "dt", "dd"}
_SKIP = {"style", "script", "head", "title", "desc", "noscript"}


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent", "data")

    def __init__(self, tag, attrs=None, parent=None, data=None):
        self.tag, self.attrs, self.parent, self.data = tag, dict(attrs or {}), parent, data
        self.children: list[_Node] = []

    def iter(self):
        yield self
        for child in self.children:
            yield from child.iter()

    def text(self):
        return " ".join((n.data or "") for n in self.iter() if n.tag == "#text" and not _skipped(n)).strip()

    def cls(self):
        return set((self.attrs.get("class") or "").split())


def _skipped(node):
    p = node.parent
    while p is not None:
        if p.tag in _SKIP:
            return True
        p = p.parent
    return False


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("#root")
        self.stack = [self.root]
        self.css: list[str] = []

    def handle_starttag(self, tag, attrs):
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(_Node(tag, attrs, self.stack[-1]))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if self.stack[-1].tag == "style":
            self.css.append(data)
        self.stack[-1].children.append(_Node("#text", parent=self.stack[-1], data=data))


def parse(html: str) -> _Builder:
    b = _Builder()
    b.feed(html or "")
    b.close()
    return b


def visible_lines(root: _Node) -> list[str]:
    """Visible text in document order, one line per block element."""
    out: list[str] = []
    buf: list[str] = []

    def flush():
        text = re.sub(r"\s+", " ", "".join(buf)).strip()
        if text:
            out.append(text)
        buf.clear()

    def walk(node):
        if node.tag in _SKIP:
            return
        if node.tag == "#text":
            buf.append(node.data or "")
            return
        block = node.tag in _BLOCK
        if block:
            flush()
        for child in node.children:
            walk(child)
        if block:
            flush()
    walk(root)
    flush()
    return out


def margin_boxes(css: str) -> dict[str, str]:
    """@page margin-box contents: {'bottom-left': "'...'", ...}."""
    boxes: dict[str, str] = {}
    for m in re.finditer(r"@(top|bottom)-(left|center|right)\s*\{([^{}]*)\}", css or ""):
        content = re.search(r"content\s*:\s*(.+?)(?:;|$)", m.group(3))
        if content:
            boxes.setdefault(f"{m.group(1)}-{m.group(2)}", content.group(1).strip())
    return boxes


# --------------------------------------------------------------- results

class _Results:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, cid, ok, message, *, na=False):
        severity, owner, _ = RENDER_CHECKS[cid]
        status = NA if na else (PASS if ok else FAIL)
        self.items.append({"check": cid, "severity": severity, "status": status,
                           "blocker": status == FAIL and severity == BLOCKER,
                           "owner": owner, "message": message})

    def na(self, cid, message):
        self.add(cid, True, message, na=True)

    def summary(self, tool):
        blockers = [f"{c['check']}: {c['message']}" for c in self.items if c["blocker"]]
        warnings = [f"{c['check']}: {c['message']}" for c in self.items
                    if c["status"] == FAIL and c["severity"] == WARNING]
        return {"tool": tool, "status": "lolos" if not blockers else "gagal",
                "checks": self.items, "blockers": blockers, "warnings": warnings}


def error_result(exc) -> dict:
    severity, owner, _ = RENDER_CHECKS["R.render_error"]
    return {"check": "R.render_error", "severity": severity, "status": FAIL, "blocker": True,
            "owner": owner, "message": f"render gagal: {type(exc).__name__}: {exc}"}


def _short(items, limit=5):
    items = list(items)
    text = "; ".join(str(i) for i in items[:limit])
    return text + (f"; +{len(items) - limit} lagi" if len(items) > limit else "")


# ---------------------------------------------------------- line checks

_CAPTION = re.compile(r"^Exhibit\s+(\d+)\s*[.:]\s*(.*)$")
_APPENDIX = re.compile(r"^(lampiran\s*(\d+\s*[.:]\s*)?sumber|lampiran:\s*sumber|sumber exhibit|source appendix|"
                       r"daftar sumber|appendix:?\s*sources?|sumber data exhibit|catatan sumber exhibit)", re.I)
_DAYS = {"senin": 0, "selasa": 1, "rabu": 2, "kamis": 3, "jumat": 4, "sabtu": 5, "minggu": 6,
         "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
_MONTHS = {m: i for i, names in enumerate(
    (("januari", "january"), ("februari", "february"), ("maret", "march"), ("april",),
     ("mei", "may"), ("juni", "june"), ("juli", "july"), ("agustus", "august"),
     ("september",), ("oktober", "october"), ("november",), ("desember", "december")), 1)
    for m in names}
_DATE = re.compile(r"\b(" + "|".join(_DAYS) + r"),\s+(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})\b",
                   re.I)
# Figma header date: "DD Mon YYYY" (24 Sep 2026), Indonesian or English short month.
_SHORT_MONTHS = {m: i for i, names in enumerate(
    (("jan",), ("feb",), ("mar",), ("apr",), ("mei", "may"), ("jun",), ("jul",),
     ("agu", "aug"), ("sep",), ("okt", "oct"), ("nov",), ("des", "dec")), 1) for m in names}
_SHORT_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_SHORT_MONTHS) + r")\s+(\d{4})\b", re.I)


def _split_main(lines):
    """(main captions [(line_idx, n, title)], appendix start index or None, heading found)."""
    heading = next((i for i, line in enumerate(lines) if _APPENDIX.match(line)), None)
    caps = []
    for i, line in enumerate(lines):
        if heading is not None and i >= heading:
            break
        m = _CAPTION.match(line)
        if m:
            caps.append((i, int(m.group(1)), m.group(2)))
    if heading is None:
        # A second run starting again at Exhibit 1 is an appendix without a heading we know.
        for k in range(1, len(caps)):
            if caps[k][1] == 1 and caps[k - 1][1] >= 1 and caps[k][1] <= caps[k - 1][1]:
                return caps[:k], caps[k][0], False
    return caps, heading, heading is not None


def _numbering(lines):
    caps, _app, _found = _split_main(lines)
    numbers = [n for _i, n, _t in caps]
    if not numbers:
        return False, "tidak ada caption 'Exhibit N.'"
    ok = numbers == list(range(1, len(numbers) + 1))
    return ok, (f"Exhibit 1..{len(numbers)} berurutan" if ok else
                f"urutan caption {numbers[:15]}{'...' if len(numbers) > 15 else ''}")


def _source_lines(lines):
    caps, app, _found = _split_main(lines)
    end_main = app if app is not None else len(lines)
    bad = []
    for k, (i, n, _t) in enumerate(caps):
        stop = caps[k + 1][0] if k + 1 < len(caps) else end_main
        # Only the house form counts: risk cards and notes print "Sumber: ...".
        sources = [line for line in lines[i + 1:stop] if line.startswith("Source:")]
        if not sources:
            bad.append(f"Exhibit {n}: tanpa source line")
        elif len(sources) > 1 and not all(s == HOUSE_SOURCE for s in sources):
            bad.append(f"Exhibit {n}: {len(sources)} source line")
        elif sources[0] != HOUSE_SOURCE:
            bad.append(f"Exhibit {n}: '{sources[0][:70]}'")
    return caps, bad


def _labels(lines):
    caps, app, _found = _split_main(lines)
    end_main = app if app is not None else len(lines)
    cap_idx = [i for i, _n, _t in caps]
    bad = []
    last = -1
    for i, line in enumerate(lines[:end_main]):
        if line.startswith("Source:"):
            if not any(last < c < i for c in cap_idx):
                bad.append(f"source line baris {i} tanpa caption di atasnya")
            last = i
    generic = [f"Exhibit {n}" for _i, n, t in caps
               if not t or t.strip(" .").lower() in ("chart", "grafik", "tabel", "table", "figure")]
    return bad + [f"{g}: judul generik" for g in generic]


def _appendix(lines):
    caps, app, found = _split_main(lines)
    if app is None:
        return False, "lampiran sumber tidak ditemukan"
    tail = " ".join(lines[app:])
    listed = {int(m) for m in re.findall(r"Exhibit\s+(\d+)\b", tail)}
    missing = [n for _i, n, _t in caps if n not in listed]
    head = "" if found else " (tanpa judul lampiran yang dikenali)"
    return not missing, (f"lampiran sumber memuat {len(caps)} exhibit{head}" if not missing
                         else f"lampiran sumber tanpa Exhibit {missing[:10]}{head}")


def _date_ok(text, tanggal):
    m = _DATE.search(text or "")
    if not m:
        short = _SHORT_DATE.search(text or "")
        if not short:
            return False, "tanpa tanggal 'DD Mon YYYY'"
        try:
            d = date(int(short.group(3)), _SHORT_MONTHS[short.group(2).lower()], int(short.group(1)))
        except ValueError:
            return False, f"tanggal tidak valid '{short.group(0)}'"
        if tanggal and str(tanggal)[:10] != d.isoformat():
            return False, f"tanggal header {d.isoformat()} bukan tanggal laporan {str(tanggal)[:10]}"
        return True, short.group(0)
    day, dd, month, yyyy = m.group(1).lower(), int(m.group(2)), _MONTHS[m.group(3).lower()], int(m.group(4))
    try:
        d = date(yyyy, month, dd)
    except ValueError:
        return False, f"tanggal tidak valid '{m.group(0)}'"
    if d.weekday() != _DAYS[day]:
        return False, f"hari salah '{m.group(0)}'"
    if tanggal and str(tanggal)[:10] != d.isoformat():
        return False, f"tanggal header {d.isoformat()} bukan tanggal laporan {str(tanggal)[:10]}"
    return True, m.group(0)


def _norm_dash(text):
    return re.sub(r"\s*[–—-]\s*", " - ", text or "")


# -------------------------------------------------------------- HTML

def _highlighted(tr: _Node) -> bool:
    plain = {"cell-num", "cell-text", "cell-date", "short"}
    if tr.attrs.get("class") or tr.attrs.get("style") or tr.attrs.get("bgcolor"):
        return True
    for cell in tr.children:
        if cell.tag in ("td", "th"):
            if cell.attrs.get("style") or (cell.cls() - plain):
                return True
            if any(n.tag in ("b", "strong", "mark") for n in cell.iter()):
                return True
    return False


def _tables_by_caption(root, pattern):
    out = []
    for node in root.iter():
        if node.tag == "table":
            cap = next((c for c in node.iter() if c.tag == "caption"), None)
            if cap and re.search(pattern, cap.text(), re.I):
                out.append(node)
    return out


def _rows(table):
    return [n for n in table.iter() if n.tag == "tr"]


def _first_cell(tr):
    cell = next((c for c in tr.children if c.tag in ("td", "th")), None)
    return cell.text() if cell else ""


def check_rendered(html: str, doc: dict | None = None) -> dict:
    """Checks on rendered report HTML."""
    doc = doc or {}
    meta = doc.get("meta") or {}
    r = _Results()
    b = parse(html)
    lines = visible_lines(b.root)
    css = "\n".join(b.css)

    ok, msg = _numbering(lines)
    r.add("T1.numbering_rendered", ok, msg)
    caps, bad = _source_lines(lines)
    if not caps:
        r.add("T1.source_line", False, "tidak ada exhibit berlabel")
    else:
        r.add("T1.source_line", not bad, f"{len(caps)} exhibit dengan '{HOUSE_SOURCE}'" if not bad
              else f"{len(bad)} exhibit: {_short(bad)}")
    bad = _labels(lines)
    r.add("T1.exhibit_label_rendered", not bad, "setiap objek berlabel" if not bad else _short(bad))
    from .. import render  # the renderer's own switch; importing opens nothing
    if render.SHOW_SOURCE_APPENDIX:
        ok, msg = _appendix(lines)
        r.add("T1.source_appendix", ok, msg)
    else:
        r.na("T1.source_appendix", "lampiran sumber disembunyikan (render.SHOW_SOURCE_APPENDIX)")

    # Header: in-page header plus running header boxes.
    boxes = margin_boxes(css)
    problems = []
    head_i = next((i for i, line in enumerate(lines) if "Equity Research" in line and "Company Update" in line), None)
    head_line = " ".join(lines[head_i:head_i + 3]) if head_i is not None else None
    if not head_line:
        problems.append("tanpa 'Equity Research - Company Update'")
    else:
        ok, msg = _date_ok(head_line, meta.get("tanggal"))
        if not ok:
            problems.append(f"header: {msg}")
        code = meta.get("ticker")
        if code and not re.search(rf"\b{re.escape(code)} IJ\b", " ".join(lines[max(0, head_i - 2):head_i + 3])):
            problems.append(f"header tanpa kode '{code} IJ'")
    running = " ".join(v for k, v in boxes.items() if k.startswith("top"))
    if running:
        ok, msg = _date_ok(running, meta.get("tanggal"))
        if not ok:
            problems.append(f"header berjalan: {msg}")
    logo = any(n.tag in ("img", "svg") and re.search(r"logo|wordmark|sektoral|sectors",
                                                     " ".join(str(v) for v in n.attrs.values()), re.I)
               for n in b.root.iter())
    if not logo:
        problems.append("tanpa logo")
    shown = " ".join(lines[max(0, head_i - 1):head_i + 1]) if head_i is not None else ""
    r.add("T1.header", not problems, f"header lengkap ({shown[:90]})" if not problems and head_line
          else "; ".join(problems))

    # Footer: @page bottom boxes (print) or footer text.
    bottom = {k: v for k, v in boxes.items() if k.startswith("bottom")}
    text = " ".join(bottom.values()) or " ".join(lines[-40:])
    problems = []
    if "sectors.app" not in text.lower():
        problems.append("tanpa 'sectors.app'")
    if DISCLOSURE.lower() not in text.lower():
        problems.append("tanpa disclosure")
    if bottom and not any("counter(page)" in v for v in bottom.values()):
        problems.append("tanpa nomor halaman")
    left = bottom.get("bottom-left", "")
    if bottom and DISCLOSURE.lower() in left.lower():
        problems.append("disclosure di kiri (template: kanan, 'sectors.app' di kiri)")
    r.add("T1.footer", not problems, "footer sectors.app, disclosure, nomor halaman" if not problems
          else "; ".join(problems))

    # Price box.
    released = bool(meta.get("rating")) and meta.get("tp") is not None
    up_line = next((line for line in lines if re.search(r"upside|downside", line, re.I)
                    and re.search(r"\(%\)|%", line)), None)
    if not released:
        r.na("T2.price_box_rendered", "tanpa TP terbit")
    else:
        problems = []
        if not any(re.search(r"harga terakhir|last price", line, re.I) for line in lines):
            problems.append("tanpa baris harga terakhir")
        if not any(re.search(r"target harga|target price", line, re.I) for line in lines):
            problems.append("tanpa baris target harga")
        m = re.search(r"([+\-−]?\d[\d.]*(?:,(\d+))?)\s*%\s*$", up_line or "")
        if not m:
            problems.append("upside tidak terbaca")
        else:
            if m.group(1)[0] not in "+-−":
                problems.append(f"upside '{m.group(1)}%' tanpa tanda")
            if len(m.group(2) or "") != 1:
                problems.append(f"upside '{m.group(1)}%' bukan satu desimal")
        r.add("T2.price_box_rendered", not problems, f"'{up_line}'" if not problems else "; ".join(problems))

    # Relative chart on the cover.
    cap = next((line for line in lines if _CAPTION.match(line) and re.search(r"relati", line, re.I)), None)
    if not cap:
        missing = any("belum tersedia" in line.lower() and "harga" in line.lower() for line in lines)
        r.add("T2.relative_chart_rendered", False, "chart harga relatif tidak dirender" +
              (" (data harga belum tersedia)" if missing else ""))
    else:
        problems = []
        m = re.search(r"\((\d+)\s*(?:M\b|bulan)", cap)
        if m and not 12 <= int(m.group(1)) <= 24:
            problems.append(f"jendela {m.group(1)} bulan (template 12-24)")
        if not re.search(r"IHSG|JCI", cap):
            problems.append("judul tanpa IHSG/JCI")
        ticks = [line for line in lines if re.fullmatch(r"[A-Z][a-z]{2}-\d{2}", line)]
        if len(ticks) < 2:
            problems.append("label sumbu bulan (Mmm-YY) kurang dari dua")
        r.add("T2.relative_chart_rendered", not problems, f"'{cap[:70]}'" if not problems
              else "; ".join(problems))

    r.add("T2.analyst_block", any("Equity Analyst" in line for line in lines),
          "blok analis ada" if any("Equity Analyst" in line for line in lines) else "tanpa 'Equity Analyst'")
    ticker = str(meta.get("ticker") or "").upper()
    name = re.sub(r"\s+", " ", str(meta.get("emiten") or "")).strip().lower()
    hit = next((line for line in lines if f"({ticker} IJ)" in line), None) if ticker else None
    ok = bool(hit) and (not name or name in re.sub(r"\s+", " ", hit).lower())
    r.add("T2.company_header", ok, f"'{hit[:70]}'" if ok else f"tanpa '{meta.get('emiten')} ({ticker} IJ)'")

    # Sensitivity base highlight.
    tables = _tables_by_caption(b.root, r"^Exhibit\s+\d+\.\s*Sensitivit")
    if not tables:
        r.na("T4.sensitivity_highlight_rendered", "tanpa tabel sensitivitas")
    else:
        bad = []
        for t in tables:
            base = [tr for tr in _rows(t) if re.search(r"\(basis\)|\bbase\b", _first_cell(tr), re.I)]
            if not base or not any(_highlighted(tr) for tr in base):
                bad.append(next(c for c in t.iter() if c.tag == "caption").text()[:50])
        r.add("T4.sensitivity_highlight_rendered", not bad, "baris/sel basis disorot" if not bad
              else f"basis tidak disorot: {_short(bad, 3)}")

    # Peer table highlights.
    tables = _tables_by_caption(b.root, r"^Exhibit\s+\d+\.\s*(Perbandingan peer|Peer valuation|Perbandingan valuasi peer)")
    if not tables:
        r.na("T5.peer_highlight_rendered", "tanpa tabel peer")
    else:
        problems = []
        for t in tables:
            rows = _rows(t)
            issuer = [tr for tr in rows if "(emiten)" in _first_cell(tr).lower()
                      or (ticker and _first_cell(tr).upper().startswith(ticker))]
            summary = [tr for tr in rows if re.match(r"^(median|rata-rata|average)", _first_cell(tr), re.I)]
            if not issuer or not all(_highlighted(tr) for tr in issuer):
                problems.append("baris emiten tidak disorot")
            if not summary or not all(_highlighted(tr) for tr in summary):
                problems.append("baris median/rata-rata tidak tebal/disorot")
        r.add("T5.peer_highlight_rendered", not problems, "baris emiten dan median/rata-rata disorot"
              if not problems else "; ".join(sorted(set(problems))))

    # Band charts: mean and median lines in two styles and a current marker.
    svgs = [n for n in b.root.iter() if n.tag == "svg" and
            (re.search(r"band", n.attrs.get("class") or "", re.I) or
             re.match(r"band", n.attrs.get("aria-label") or "", re.I))]
    if not svgs:
        r.na("T5.band_lines_rendered", "tanpa grafik band")
    else:
        bad = []
        for svg in svgs:
            dashes = [n.attrs.get("stroke-dasharray") for n in svg.iter()
                      if n.tag in ("line", "path", "polyline") and n.attrs.get("stroke-dasharray")]
            counts = {d: dashes.count(d) for d in set(dashes)}
            grid = max(counts, key=counts.get) if counts and max(counts.values()) >= 3 else None
            styles = {d for d in counts if d != grid}
            marker = any(n.tag in ("circle", "polygon", "path") and not n.attrs.get("stroke-dasharray")
                         for n in svg.iter())
            if len(styles) < 2 or not marker:
                bad.append(f"'{(svg.attrs.get('aria-label') or '')[:30]}': {len(styles)} gaya garis, "
                           f"penanda {'ada' if marker else 'tidak ada'}")
        r.add("T5.band_lines_rendered", not bad, f"{len(svgs)} grafik band: mean/median beda gaya + penanda"
              if not bad else _short(bad, 3))

    # Negatives in brackets (table cells).
    neg = [n.text() for n in b.root.iter() if n.tag == "td"
           and re.match(r"^(?:Rp\s?|US\$\s?)?[-−]\s?\d", n.text())]
    r.add("TN.negatives_brackets", not neg, "angka negatif dalam kurung" if not neg
          else f"{len(neg)} sel bertanda minus: {_short(neg, 6)}")
    return r.summary("check_rendered")


# --------------------------------------------------------------- PDF

def check_pdf_text(pages: list[str], doc: dict | None = None) -> dict:
    """Checks on PDF page texts (pypdf/pdfplumber extraction)."""
    doc = doc or {}
    meta = doc.get("meta") or {}
    r = _Results()
    lines = [re.sub(r"\s+", " ", line).strip() for page in pages for line in (page or "").splitlines()]
    lines = [line for line in lines if line]
    ok, msg = _numbering(lines)
    r.add("T1.numbering_rendered.pdf", ok, msg)
    caps, bad = _source_lines(lines)
    stray = [line[:70] for line in lines if line.startswith("Source:") and line != HOUSE_SOURCE]
    if not caps:
        r.add("T1.source_line.pdf", False, "tidak ada exhibit berlabel di PDF")
    else:
        problems = bad or ([f"source line lain: {_short(stray, 3)}"] if stray else [])
        r.add("T1.source_line.pdf", not problems, f"{len(caps)} exhibit dengan '{HOUSE_SOURCE}'"
              if not problems else f"{len(problems)} temuan: {_short(problems)}")
    head_bad, foot_bad = [], []
    for i, page in enumerate(pages, 1):
        text = re.sub(r"\s+", " ", page or "")
        norm = _norm_dash(text)
        if "Equity Research - Company Update" not in norm:
            head_bad.append(f"hlm {i}: tanpa header")
        else:
            ok, msg = _date_ok(text, meta.get("tanggal"))
            if not ok:
                head_bad.append(f"hlm {i}: {msg}")
        missing = []
        if "sectors.app" not in text.lower():
            missing.append("sectors.app")
        if DISCLOSURE.lower() not in text.lower():
            missing.append("disclosure")
        if not re.search(rf"Page\s+{i}\b|\b{i}\s+of\s+\d+|Halaman\s+{i}\b", text):
            missing.append("nomor halaman")
        if missing:
            foot_bad.append(f"hlm {i}: tanpa {', '.join(missing)}")
    r.add("T1.header.pdf", not head_bad, f"{len(pages)} halaman dengan header" if not head_bad
          else f"{len(head_bad)}/{len(pages)} halaman: {_short(head_bad, 4)}")
    r.add("T1.footer.pdf", not foot_bad, f"{len(pages)} halaman dengan footer" if not foot_bad
          else f"{len(foot_bad)}/{len(pages)} halaman: {_short(foot_bad, 4)}")
    return r.summary("check_pdf_text")
