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


def _event_key(title):
    """Normalized event key for syndication dedup; keeps disagreements visible.

    Syndicated copies share near-identical titles; distinct events keep
    distinct keys. Source disagreements (same event, different claims) are
    NOT merged away: they share an event key prefix but remain separate
    rows so the forecast agent must treat them as a scenario range/blocker.
    """
    text = re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()
    words = [w for w in text.split() if len(w) > 2][:10]
    return " ".join(words)


def build_register(ticker, company_name, as_of, sectors_rows, tavily_items,
                   limit=6):
    """Normalized evidence register with stable IDs and explicit rejections.

    Returns {"articles": [...], "rejected": [...], "stats": {...}} where each
    article carries a stable ``register_id`` (src-0, src-1, ...) ordered
    newest-first, plus ``event_key`` for syndication dedup. ``rejected``
    records items dropped for future dating, issuer mismatch, missing title,
    or duplicate URL/event so the trace shows search -> selected source ->
    assumption or explicit rejection.
    """
    cutoff = _day(as_of)
    if cutoff is None:
        raise ValueError("news merge needs a valid report as-of date")
    candidates = []
    rejected = []

    def _reject(item, reason):
        rejected.append({"title": str((item or {}).get("title") or (item or {}).get("url") or "")[:160],
                         "url": str((item or {}).get("source") or (item or {}).get("url") or ""),
                         "reason": reason})

    for row in sectors_rows or []:
        if not isinstance(row, dict):
            continue
        when, key = _day(row.get("timestamp")), _url_key(row.get("source"))
        if when is None or not row.get("title"):
            _reject(row, "missing title or unparsable date")
            continue
        if when > cutoff:
            _reject(row, f"published {row.get('timestamp')} after as-of {as_of}: no look-ahead")
            continue
        if not key:
            _reject(row, "unverifiable URL")
            continue
        candidates.append({**row, "origin": "sectors", "origins": ["sectors"],
                           "event_key": _event_key(row.get("title"))})
    for item in tavily_items or []:
        if not isinstance(item, dict):
            continue
        when, key = _day(item.get("date")), _url_key(item.get("url"))
        if when is None or not item.get("title"):
            _reject(item, "missing title or unparsable date")
            continue
        if when > cutoff:
            _reject(item, f"published {item.get('date')} after as-of {as_of}: no look-ahead")
            continue
        if not key:
            _reject(item, "unverifiable URL")
            continue
        if not _issuer_match(str(ticker).upper(), company_name, item):
            _reject(item, "issuer identity not verified in title/snippet")
            continue
        candidates.append({"title": item["title"], "timestamp": item["date"],
                           "source": item["url"], "body": item.get("snippet") or "",
                           "symbols": [str(ticker).upper()], "origin": "tavily",
                           "origins": ["tavily"], "publisher": item.get("domain"),
                           "tavily_query": item.get("query"),
                           "event_key": _event_key(item.get("title"))})
    # Split per feed for balanced quota, newest first.
    sectors = sorted((c for c in candidates if c["origin"] == "sectors"),
                     key=lambda r: str(r["timestamp"]), reverse=True)
    tavily = sorted((c for c in candidates if c["origin"] == "tavily"),
                    key=lambda r: str(r["timestamp"]), reverse=True)

    chosen, by_url, seen_events = [], {}, set()

    def add(row):
        key = _url_key(row["source"])
        if key in by_url:
            existing = chosen[by_url[key]]
            existing["origins"] = list(dict.fromkeys(existing["origins"] + row["origins"]))
            if row.get("tavily_query") and row["tavily_query"] not in str(existing.get("tavily_query") or ""):
                existing["tavily_query"] = "; ".join(filter(None, [existing.get("tavily_query"), row.get("tavily_query")]))
            _reject(row, f"duplicate URL merged into {existing.get('register_id') or 'existing'}")
            return
        if len(chosen) >= limit:
            _reject(row, f"over limit={limit}: kept newest-first balanced quota")
            return
        # Syndication dedup: same event key from the same origin family is one
        # story; keep the newest, note the merge. Cross-origin same-event rows
        # are KEPT (disagreement visible) with merged origins only on URL match.
        event = row.get("event_key")
        if event and event in seen_events and len(event.split()) >= 4:
            # Only collapse exact-title syndication within the same feed to
            # avoid hiding cross-source disagreement.
            same_title = next((c for c in chosen if c.get("event_key") == event
                               and c.get("origin") == row.get("origin")), None)
            if same_title is not None:
                _reject(row, f"duplicate syndicated event merged into {same_title.get('register_id') or 'existing'}")
                return
        row = dict(row)
        row["register_id"] = f"src-{len(chosen)}"
        by_url[key] = len(chosen)
        if event:
            seen_events.add(event)
        chosen.append(row)

    # Reserve room for both feeds when both have distinct articles.
    quota = max(1, limit // 2)
    for rows in (sectors, tavily):
        for row in rows[:quota]:
            add(row)
    for row in sorted((row for rows in (sectors, tavily) for row in rows[quota:]),
                      key=lambda item: str(item["timestamp"]), reverse=True):
        add(row)
    chosen.sort(key=lambda row: str(row["timestamp"]), reverse=True)
    # Reassign stable IDs after final newest-first sort.
    for index, row in enumerate(chosen):
        row["register_id"] = f"src-{index}"
    stats = {"sectors_candidates": len(sectors), "tavily_candidates": len(tavily),
             "selected": len(chosen), "rejected": len(rejected), "limit": limit,
             "as_of": str(as_of)[:10]}
    return {"articles": chosen, "rejected": rejected, "stats": stats}


def combine(ticker, company_name, as_of, sectors_rows, tavily_items, limit=6):
    """Return a bounded, source-balanced register with stable article indices."""
    return build_register(ticker, company_name, as_of, sectors_rows,
                          tavily_items, limit=limit)["articles"]
