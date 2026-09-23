"""Cache-backed news filtering and validation of agent-written context."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NEWS_ANALYSIS_DIR = ROOT / "data" / "news_analysis"
_ADVICE = re.compile(
    r"\b(buy|sell|hold|recommend\w*|beli|jual|tahan|rekomendasi|target price|price target|"
    r"target harga|harga target|nilai wajar|fair value)\b", re.I)


def relevant_rows(ticker, payload, as_of=None, limit=10):
    """Return ticker-matched cached articles no later than the report as-of date."""
    rows = payload.get("results") or [] if isinstance(payload, dict) else []
    symbol = str(ticker).strip().upper()
    symbols = {symbol, f"{symbol}.JK"}
    selected = [row for row in rows if isinstance(row, dict) and
                symbols.intersection(str(item).upper()
                                     for item in row.get("symbols", [])) and
                (not as_of or str(row.get("timestamp") or "")[:10] <= str(as_of)[:10])]
    selected.sort(key=lambda row: str(row.get("timestamp") or ""), reverse=True)
    return selected[:limit]


def _valid_iso_day(value):
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def validate_analysis(ticker, rows, news_rows, as_of=None):
    """Keep only paraphrased agent text tied to exact articles in current cache."""
    if not isinstance(rows, list) or not isinstance(news_rows, list):
        return []
    symbol = str(ticker).strip().upper()
    valid = []
    for row in rows[:3]:
        if not isinstance(row, dict):
            continue
        if not all(isinstance(row.get(field), str) and row[field].strip()
                   for field in ("summary", "connection", "caveat", "source", "timestamp")):
            continue
        if _ADVICE.search(" ".join(row[field] for field in
                                   ("summary", "connection", "caveat"))):
            continue
        if "/news/" not in row["source"] or not _valid_iso_day(row["timestamp"]):
            continue
        if as_of and row["timestamp"][:10] > str(as_of)[:10]:
            continue
        article = next((item for item in news_rows
                        if isinstance(item, dict) and
                        (symbol in {str(s).upper() for s in item.get("symbols", [])} or
                         f"{symbol}.JK" in {str(s).upper() for s in item.get("symbols", [])}) and
                        item.get("title") and item["title"] in row["source"] and
                        (not item.get("source") or item["source"] in row["source"]) and
                        str(item.get("timestamp") or "") == row["timestamp"]), None)
        if article is None:
            continue
        # A third-party recommendation headline must not become public-facing
        # content through the provenance/source column either.
        if _ADVICE.search(str(article.get("title") or "")):
            continue
        cached_urls = {str(item.get("source")) for item in news_rows
                       if isinstance(item, dict) and item.get("source")}
        cited_urls = re.findall(r"https?://\S+", row["source"], flags=re.I)
        if any(url.rstrip(".,;)") not in cached_urls for url in cited_urls):
            continue
        summary = row["summary"].strip()
        body = str(article.get("body") or "")
        if summary == str(article.get("title") or "").strip() or (summary and summary in body):
            continue
        if len(row["connection"].strip()) < 20:
            continue
        valid.append({field: row[field] for field in
                      ("summary", "connection", "caveat", "source", "timestamp")})
    return valid


def load_analysis(ticker, news_rows, as_of=None, analysis_dir=None):
    """Load only source-checked narrative; ignores cached/offline stale artifacts."""
    directory = Path(analysis_dir) if analysis_dir is not None else NEWS_ANALYSIS_DIR
    path = directory / f"{str(ticker).upper()}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return [], {"status": "missing", "path": str(path)}
    if not isinstance(document, dict) or \
            str(document.get("ticker") or "").strip().upper() != str(ticker).upper():
        return [], {"status": "invalid", "path": str(path),
                    "reason": "ticker mismatch or invalid document"}
    analysis = validate_analysis(ticker, document.get("news_analysis"), news_rows, as_of)
    status = "loaded" if analysis else "invalid"
    return analysis, {"status": status, "path": str(path),
                      "reason": None if analysis else "no cache-matched news analysis"}
