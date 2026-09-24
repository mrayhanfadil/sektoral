"""Per-ticker memory of earlier analyst runs.

Each run appends a compact snapshot (signals, flags, findings, headlines) to
the ``agent_memory`` collection of the app database, keyed by ticker. The next
run reads the latest snapshot to brief the planner and to report what changed.
"""
from __future__ import annotations

import re

from app import store

COLLECTION = "agent_memory"
KEEP_RUNS = 10
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")


def _key(ticker):
    if not _TICKER.fullmatch(ticker):
        raise ValueError("ticker format is invalid")
    return ticker


def load(ticker, db=None):
    data = store.get(COLLECTION, _key(ticker), db)
    return [run for run in data.get("runs", []) if isinstance(run, dict)] \
        if isinstance(data, dict) else []


def latest(ticker, db=None):
    runs = load(ticker, db)
    return runs[-1] if runs else None


def snapshot(result):
    """The part of an analyst result worth remembering."""
    return {
        "run_at": result.get("run_at"),
        "market_date": result.get("market_date"),
        "question": (result.get("plan") or {}).get("question"),
        "signals": {s["id"]: {"display": s.get("display"), "value": s.get("value")
                              if isinstance(s.get("value"), (int, float, str)) else None,
                              "rank": s.get("rank"), "n": s.get("n"), "flag": s.get("flag"),
                              "label": s.get("label")}
                    for s in result.get("signals", []) if s.get("kind") != "web"},
        "findings": [f.get("title") for f in (result.get("synthesis") or {}).get("findings", [])],
        "headlines": [h.get("title") for h in result.get("headlines", [])] +
                     [h.get("title") for h in (result.get("web_news") or {}).get("items", [])
                      if isinstance(result.get("web_news"), dict)],
    }


def save(ticker, result, db=None):
    runs = (load(ticker, db) + [snapshot(result)])[-KEEP_RUNS:]
    store.put(COLLECTION, _key(ticker), {"ticker": ticker, "runs": runs}, db)
    return runs[-1]


def diff(previous, current):
    """Changes between two snapshots, phrased for display."""
    if not previous:
        return {"first_run": True, "items": []}
    items = []
    old_signals, new_signals = previous.get("signals") or {}, current.get("signals") or {}
    for signal_id, now in new_signals.items():
        before = old_signals.get(signal_id)
        label = now.get("label") or signal_id
        if before is None:
            continue
        if now.get("rank") and before.get("rank") and now["rank"] != before["rank"]:
            items.append({"id": signal_id, "kind": "rank",
                          "text": f"{label}: peringkat {before['rank']} → {now['rank']} dari {now.get('n')}"})
        elif now.get("display") != before.get("display"):
            items.append({"id": signal_id, "kind": "value",
                          "text": f"{label}: {before.get('display')} → {now.get('display')}"})
        if now.get("flag") and now.get("flag") != before.get("flag"):
            items.append({"id": signal_id, "kind": "new_flag",
                          "text": f"Sinyal baru pada {label}: {now['flag']}"})
        elif before.get("flag") and not now.get("flag"):
            items.append({"id": signal_id, "kind": "cleared_flag",
                          "text": f"Sinyal {label} ({before['flag']}) tidak lagi muncul"})
    old_headlines = set(previous.get("headlines") or [])
    for title in current.get("headlines") or []:
        if title and title not in old_headlines:
            items.append({"id": "news", "kind": "news", "text": f"Berita baru: {title}"})
    return {"first_run": False, "previous_run_at": previous.get("run_at"),
            "previous_market_date": previous.get("market_date"),
            "same_market_date": previous.get("market_date") == current.get("market_date"),
            "items": items[:12]}


def watchlist(db=None):
    """Tickers researched before, newest first, with their last flags."""
    rows = []
    for ticker, data in store.items(COLLECTION, db=db):
        runs = [run for run in (data or {}).get("runs", []) if isinstance(run, dict)] \
            if _TICKER.fullmatch(ticker) and isinstance(data, dict) else []
        if not runs:
            continue
        last = runs[-1]
        flags = [s.get("flag") for s in (last.get("signals") or {}).values() if s.get("flag")]
        rows.append({"ticker": ticker, "run_at": last.get("run_at"), "runs": len(runs),
                     "market_date": last.get("market_date"), "flags": len(flags)})
    return sorted(rows, key=lambda row: str(row.get("run_at") or ""), reverse=True)
