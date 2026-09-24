"""Auto deep-dive for cached news links + enrichment.

Cache-first design: the Sectors cache snippet stays the market-data source.
This module fetches the full article behind each cached ``source`` URL,
extracts readable text with stdlib only, and stores it under
``data/news_full/`` so reruns and tests stay offline.

Provenance is explicit: every record carries ``source_url``,
``fetch_status`` (``fetched`` or ``unavailable_*``), and ``fetched_at``.
Failures never raise -- they return an ``unavailable_*`` record so the
pipeline falls back to the cache snippet and stays visibly partial.
"""
from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import re
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
NEWS_FULL_DIR = ROOT / "data" / "news_full"

TIMEOUT_S = 12
MAX_HTML_BYTES = 500_000
FULL_TEXT_CAP = 8000
AGENT_TEXT_CAP = 3000
MAX_WORKERS = 4

_UNAVAILABLE_OFFLINE = "unavailable_offline"
_ADVICE = re.compile(
    r"\b(buy|sell|hold|recommend\w*|beli|jual|tahan|rekomendasi|target price|price target|"
    r"target harga|harga target|nilai wajar|fair value)\b", re.I)


def _disabled() -> bool:
    return bool(os.environ.get("SEKTORAL_DISABLE_DEEPDIVE") or os.environ.get("SEKTORAL_OFFLINE"))


def _url_key(url: str) -> str:
    return hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:32]


def _record_path(url: str, cache_dir: Path | None = None) -> Path:
    directory = Path(cache_dir) if cache_dir is not None else NEWS_FULL_DIR
    return directory / f"{_url_key(url)}.json"


def load_cached(url: str, cache_dir: Path | None = None) -> dict | None:
    try:
        return json.loads(_record_path(url, cache_dir).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None


def _save(url: str, record: dict, cache_dir: Path | None = None) -> None:
    try:
        directory = Path(cache_dir) if cache_dir is not None else NEWS_FULL_DIR
        directory.mkdir(parents=True, exist_ok=True)
        # Atomic replace: parallel ticker runs may fetch the same article,
        # and a reader must never see a half-written record.
        target = _record_path(url, directory)
        handle, temp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(record, stream, ensure_ascii=False, indent=1)
            os.replace(temp, target)
        except OSError:
            try:
                os.unlink(temp)
            except OSError:
                pass
    except OSError:
        pass


class _TextExtractor(HTMLParser):
    """Collect title + readable paragraphs, skipping nav/script/style."""

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.paragraphs: list[str] = []
        self._current: list[str] = []
        self._in_body_text = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "nav", "header", "footer", "aside", "form"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in ("p", "h1", "h2", "h3", "li"):
            self._current = []
            self._in_body_text = True

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("script", "style", "nav", "header", "footer", "aside", "form"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False
        elif tag in ("p", "h1", "h2", "h3", "li") and self._in_body_text:
            text = html_mod.unescape("".join(self._current)).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) >= 40:
                self.paragraphs.append(text)
            self._current = []
            self._in_body_text = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title_parts.append(data.strip())
        elif self._in_body_text:
            self._current.append(data)


def extract_text(html_body: str) -> dict:
    parser = _TextExtractor()
    try:
        parser.feed(html_body[:MAX_HTML_BYTES])
    except Exception:
        pass
    title = html_mod.unescape(re.sub(r"\s+", " ", "".join(parser.title_parts)).strip())
    text = "\n\n".join(parser.paragraphs)
    text = re.sub(r"[ \t]+", " ", text).strip()
    return {"title": title[:300], "text": text[:FULL_TEXT_CAP], "length": len(text)}


def _fetch_html(url: str) -> tuple[str, str]:
    parts = urlsplit(str(url))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("unsupported URL scheme")
    request = urllib.request.Request(
        str(url),
        headers={"User-Agent": "Sektoral-deepdive/1.0 (+local research)",
                 "Accept": "text/html,application/xhtml+xml"},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
        final_url = response.geturl() or str(url)
        raw = response.read(MAX_HTML_BYTES + 1)
    if len(raw) > MAX_HTML_BYTES:
        raw = raw[:MAX_HTML_BYTES]
    charset = "utf-8"
    try:
        content_type = response.headers.get_content_charset() if hasattr(response, "headers") else None
        if content_type:
            charset = content_type
    except Exception:
        pass
    try:
        return raw.decode(charset, errors="replace"), final_url
    except (LookupError, ValueError):
        return raw.decode("utf-8", errors="replace"), final_url


def enrich_one(row: dict, cache_dir: Path | None = None) -> dict:
    """Fetch + extract one cached news row. Never raises."""
    url = str((row or {}).get("source") or "")
    title = str((row or {}).get("title") or "")
    timestamp = str((row or {}).get("timestamp") or "")
    base = {"source_url": url, "title": title, "timestamp": timestamp,
            "fetch_status": "unavailable_unknown", "fetched_at": None,
            "full_text": "", "full_length": 0, "title_extracted": ""}
    if not url.startswith(("https://", "http://")):
        return {**base, "fetch_status": "unavailable_bad_url"}
    cached = load_cached(url, cache_dir)
    if isinstance(cached, dict) and cached.get("source_url") == url and cached.get("full_text"):
        # Reuse stored extract; refresh lightweight provenance fields.
        cached = dict(cached)
        cached.setdefault("title", title)
        cached.setdefault("timestamp", timestamp)
        return cached
    if _disabled():
        return {**base, "fetch_status": _UNAVAILABLE_OFFLINE}
    try:
        html_body, final_url = _fetch_html(url)
    except ValueError:
        return {**base, "fetch_status": "unavailable_bad_url"}
    except Exception as error:  # network, timeout, paywall-shaped errors
        record = {**base, "fetch_status": f"unavailable_fetch_{type(error).__name__}"[:48]}
        _save(url, record, cache_dir)
        return record
    extracted = extract_text(html_body)
    text = extracted["text"]
    if len(text) < 200:
        record = {**base, "fetch_status": "unavailable_empty_extract",
                  "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "title_extracted": extracted["title"]}
        _save(url, record, cache_dir)
        return record
    record = {
        "source_url": url, "final_url": final_url, "title": title, "timestamp": timestamp,
        "fetch_status": "fetched",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "title_extracted": extracted["title"], "full_text": text,
        "full_length": extracted["length"],
        "has_advice_language": bool(_ADVICE.search(f"{extracted['title']} {text[:2000]}")),
    }
    _save(url, record, cache_dir)
    return record


def enrich_all(rows: list, cache_dir: Path | None = None, max_workers: int = MAX_WORKERS) -> list:
    """Auto deep-dive every supplied cached article, preserving order."""
    rows = [row for row in (rows or []) if isinstance(row, dict)]
    if not rows:
        return []
    # Fast path: everything already cached or offline -- avoid thread overhead.
    if _disabled() or all(
            isinstance(load_cached(str(r.get("source") or ""), cache_dir), dict)
            for r in rows):
        return [enrich_one(row, cache_dir) for row in rows]
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(rows)))) as pool:
        return list(pool.map(lambda row: enrich_one(row, cache_dir), rows))


def agent_text(record: dict, cap: int = AGENT_TEXT_CAP) -> str:
    text = str((record or {}).get("full_text") or "")
    return text[:cap]


def new_facts(snippet: str, full_text: str, limit: int = 3) -> list[str]:
    """Sentences in the full text that add material beyond the cache snippet."""
    snippet_words = {word.lower() for word in re.findall(r"[a-zA-Z]{4,}", str(snippet or ""))}
    sentences = re.split(r"(?<=[.!?])\s+", str(full_text or ""))
    fresh = []
    for sentence in sentences:
        clean = sentence.strip()
        if len(clean) < 60 or len(clean) > 400:
            continue
        words = [word.lower() for word in re.findall(r"[a-zA-Z]{4,}", clean)]
        if not words:
            continue
        overlap = sum(1 for word in words if word in snippet_words) / len(words)
        if overlap < 0.6:
            fresh.append(clean)
        if len(fresh) >= limit:
            break
    return fresh
