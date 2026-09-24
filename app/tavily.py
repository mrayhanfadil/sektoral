"""Dated web news discovery from Tavily.

Articles may support labeled analyst forecast assumptions after source checks;
they do not become issuer actuals or guidance. Keys are read from
``TAVILY_API_KEYS`` (comma separated) or ``TAVILY_API_KEY`` /
``TAVILY_API_KEY_1`` … in the environment or
the repo ``.env``, and requests rotate across them round-robin. A key that is
rejected or out of quota is skipped for the rest of the process. Results are
saved under ``data/web_news/`` so repeating a run does not spend credits.
Key values are never logged, returned or written to disk.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import shlex
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
ENDPOINT = "https://api.tavily.com/search"
STORE_DIR = ROOT / "data" / "web_news"
WINDOW_DAYS = 60
MAX_RESULTS = 6
# Indonesian business press and wire services; keeps results on-topic.
NEWS_DOMAINS = [
    "kontan.co.id", "bisnis.com", "cnbcindonesia.com", "investor.id", "katadata.co.id",
    "idxchannel.com", "emitennews.com", "cnnindonesia.com", "kompas.com", "detik.com",
    "tempo.co", "antaranews.com", "thejakartapost.com", "reuters.com", "bloomberg.com",
    "bloombergtechnoz.com", "idnfinancials.com", "marketeers.com",
]
_FAILOVER_STATUS = {401, 403, 429, 432, 433}
_KEY_ENV = re.compile(r"^TAVILY_API_KEYS?(?:_\d+)?$")


class TavilyError(RuntimeError):
    """A request failed; the message never contains a key."""


def _dotenv_keys(path=ROOT / ".env"):
    found = {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return found
    for raw in lines:
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, sep, value = line.partition("=")
        name = name.strip()
        if sep and _KEY_ENV.fullmatch(name):
            try:
                found[name] = " ".join(shlex.split(value, comments=True, posix=True))
            except ValueError:
                continue
    return found


def load_keys():
    sources = {**_dotenv_keys(), **{k: v for k, v in os.environ.items() if _KEY_ENV.fullmatch(k)}}
    keys = []
    for name in sorted(sources):
        for part in re.split(r"[,\s]+", sources[name] or ""):
            if part and part not in keys:
                keys.append(part)
    return keys


class KeyRing:
    """Round-robin over keys; a key that fails auth or quota is retired."""

    def __init__(self, keys):
        self._keys = list(keys)
        self._retired = set()
        self._lock = threading.Lock()
        # Separate processes (CLI runs) start at different keys.
        self._next = random.randrange(len(self._keys)) if self._keys else 0

    def __len__(self):
        return len(self._keys)

    def take(self):
        with self._lock:
            for _ in range(len(self._keys)):
                index = self._next % len(self._keys)
                self._next += 1
                if index not in self._retired:
                    return index, self._keys[index]
        return None, None

    def retire(self, index):
        with self._lock:
            self._retired.add(index)


_RING = None
_RING_LOCK = threading.Lock()


def _ring():
    global _RING
    with _RING_LOCK:
        if _RING is None:
            _RING = KeyRing(load_keys())
        return _RING


def configured():
    return len(_ring()) > 0


def _post(key, body, timeout=20):
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _search(body, ring=None, post=None):
    ring = ring or _ring()
    post = post or _post
    last = "tidak ada kunci Tavily yang aktif"
    for _ in range(max(1, len(ring))):
        index, key = ring.take()
        if key is None:
            break
        try:
            return post(key, body), index
        except urllib.error.HTTPError as error:
            last = f"HTTP {error.code}"
            if error.code in _FAILOVER_STATUS:
                ring.retire(index)
                continue
            raise TavilyError(f"Tavily menolak permintaan ({last})") from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise TavilyError(f"Tavily tidak terjangkau ({type(error).__name__})") from None
    raise TavilyError(f"semua kunci Tavily gagal atau habis kuota ({last})")


def _published(value):
    if not value:
        return None
    try:
        return parsedate_to_datetime(str(value)).date()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _safe_url(value):
    parts = urlsplit(str(value or ""))
    return str(value) if parts.scheme in ("http", "https") and parts.netloc else None


def news_context(ticker, company_name, end_date, *, ring=None, post=None, store_dir=None):
    """Dated headlines about one issuer, published within the window ending ``end_date``.

    Returns {"items": [...], "fetched_at", "query", "window", "from_store"}.
    """
    end = date.fromisoformat(str(end_date)[:10]) if end_date else date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    name = re.sub(r"\b(PT|Tbk\.?)\b", "", str(company_name or "")).strip(" .,")
    query = f'"{ticker}" {name} saham emiten berita'.strip()
    folder = Path(store_dir or STORE_DIR)
    key = hashlib.sha1(f"{query}|{start}|{end}".encode()).hexdigest()[:16]
    stored = folder / f"{ticker}-{end.isoformat()}-{key}.json"
    try:
        cached = json.loads(stored.read_text(encoding="utf-8"))
        return dict(cached, from_store=True)
    except (OSError, ValueError):
        pass
    body = {"query": query, "topic": "news", "search_depth": "basic",
            "max_results": MAX_RESULTS, "start_date": start.isoformat(),
            "end_date": end.isoformat(), "filter_by_published_date": True,
            "include_domains": NEWS_DOMAINS, "include_answer": False,
            "include_raw_content": False, "chunks_per_source": 1}
    payload, _index = _search(body, ring=ring, post=post)
    items = []
    for row in payload.get("results") or []:
        if not isinstance(row, dict):
            continue
        published = _published(row.get("published_date"))
        url = _safe_url(row.get("url"))
        # Dated and inside the window only: no look-ahead past the data date.
        if not url or published is None or not start <= published <= end:
            continue
        items.append({"title": str(row.get("title") or "")[:200],
                      "url": url, "domain": urlsplit(url).netloc.removeprefix("www."),
                      "date": published.isoformat(),
                      "snippet": re.sub(r"\s+", " ", str(row.get("content") or ""))[:320]})
    result = {"items": items, "query": query,
              "window": f"{start.isoformat()} s.d. {end.isoformat()}",
              "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        folder.mkdir(parents=True, exist_ok=True)
        stored.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass
    return dict(result, from_store=False)
