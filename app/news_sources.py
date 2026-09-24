"""Combine dated Sectors and Tavily articles for forecast research."""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _url_key(value):
    parts = urlsplit(str(value or ""))
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = urlencode(sorted((key, val) for key, val in parse_qsl(parts.query)
                             if not key.lower().startswith("utm_") and
                             key.lower() not in {"fbclid", "gclid"}))
    return f"{host}{path}?{query}" if query else f"{host}{path}"


def _issuer_match(ticker, company_name, item):
    text = " ".join(str(item.get(field) or "") for field in ("title", "snippet"))
    if re.search(rf"(?<!\w){re.escape(ticker)}(?!\w)", text, re.I):
        return True
    name = re.sub(r"\b(?:PT|Tbk)\.?\b", "", str(company_name or ""), flags=re.I)
    words = [word for word in re.findall(r"[\w]+", name.lower()) if len(word) > 2]
    return bool(len(words) >= 2 and " ".join(words[:2]) in text.lower())


def combine(ticker, company_name, as_of, sectors_rows, tavily_items, limit=6):
    """Return a bounded, source-balanced register with stable article indices."""
    cutoff = _day(as_of)
    if cutoff is None:
        raise ValueError("news merge needs a valid report as-of date")
    sources = ([], [])
    for row in sectors_rows or []:
        if not isinstance(row, dict):
            continue
        when, key = _day(row.get("timestamp")), _url_key(row.get("source"))
        if when is None or when > cutoff or not key or not row.get("title"):
            continue
        sources[0].append({**row, "origin": "sectors", "origins": ["sectors"]})
    for item in tavily_items or []:
        if not isinstance(item, dict):
            continue
        when, key = _day(item.get("date")), _url_key(item.get("url"))
        if (when is None or when > cutoff or not key or not item.get("title") or
                not _issuer_match(str(ticker).upper(), company_name, item)):
            continue
        sources[1].append({"title": item["title"], "timestamp": item["date"],
                           "source": item["url"], "body": item.get("snippet") or "",
                           "symbols": [str(ticker).upper()], "origin": "tavily",
                           "origins": ["tavily"], "publisher": item.get("domain")})
    for rows in sources:
        rows.sort(key=lambda row: str(row["timestamp"]), reverse=True)

    chosen, by_url = [], {}

    def add(row):
        key = _url_key(row["source"])
        if key in by_url:
            existing = chosen[by_url[key]]
            existing["origins"] = list(dict.fromkeys(existing["origins"] + row["origins"]))
            return
        if len(chosen) < limit:
            by_url[key] = len(chosen)
            chosen.append(dict(row))

    # Reserve room for both feeds when both have distinct articles.
    quota = max(1, limit // 2)
    for rows in sources:
        for row in rows[:quota]:
            add(row)
    for row in sorted((row for rows in sources for row in rows[quota:]),
                      key=lambda item: str(item["timestamp"]), reverse=True):
        add(row)
    chosen.sort(key=lambda row: str(row["timestamp"]), reverse=True)
    return chosen
