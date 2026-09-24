"""Sectoral's own database: every document the app writes, in one SQLite file.

Runtime caches (agent memory, forecast plans, fetched news, peer and FX
snapshots) and run outputs (report, audit trace and manifest documents) are
JSON documents addressed by ``(collection, key)``. The generated HTML and PDF
reports stay files, and so do the hand-curated source packs committed to git
(issuer evidence, IDX history, analyst scenarios, method overrides); see
docs/adr/0008-runtime-data-in-sqlite.md.

The database defaults to ``data/sectoral.db`` (``SECTORAL_DB`` overrides it).
Every function takes an optional ``db``: a database file, or a directory that
holds ``sectoral.db`` (tests pass their temp directory).
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Iterator

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = Path(os.environ.get("SECTORAL_DB") or ROOT / "data" / "sectoral.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
  collection TEXT NOT NULL,
  key        TEXT NOT NULL,
  body       TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (collection, key)
)"""


def path(db=None) -> Path:
    target = Path(db) if db else Path(DEFAULT_DB)
    return target / "sectoral.db" if target.is_dir() or target.suffix != ".db" else target


def _connect(db=None) -> sqlite3.Connection:
    file = path(db)
    file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(file, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_SCHEMA)
    return conn


def get(collection: str, key: str, db=None):
    """The stored document, or None."""
    with closing(_connect(db)) as conn:
        row = conn.execute("SELECT body FROM documents WHERE collection=? AND key=?",
                           (collection, key)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except ValueError:
        return None


def put(collection: str, key: str, document, db=None) -> None:
    """Insert or replace one document; the write is atomic."""
    body = json.dumps(document, ensure_ascii=False)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(_connect(db)) as conn, conn:
        conn.execute("INSERT INTO documents(collection, key, body, updated_at) VALUES (?,?,?,?) "
                     "ON CONFLICT(collection, key) DO UPDATE SET body=excluded.body, "
                     "updated_at=excluded.updated_at", (collection, key, body, stamp))


def delete(collection: str, key: str, db=None) -> None:
    with closing(_connect(db)) as conn, conn:
        conn.execute("DELETE FROM documents WHERE collection=? AND key=?", (collection, key))


def keys(collection: str, prefix: str = "", db=None) -> list[str]:
    with closing(_connect(db)) as conn:
        rows = conn.execute("SELECT key FROM documents WHERE collection=? AND substr(key, 1, ?)=? "
                            "ORDER BY key", (collection, len(prefix), prefix)).fetchall()
    return [row[0] for row in rows]


def items(collection: str, prefix: str = "", db=None) -> Iterator[tuple[str, object]]:
    """``(key, document)`` pairs of a collection, ordered by key."""
    with closing(_connect(db)) as conn:
        rows = conn.execute("SELECT key, body FROM documents WHERE collection=? AND "
                            "substr(key, 1, ?)=? ORDER BY key",
                            (collection, len(prefix), prefix)).fetchall()
    for key, body in rows:
        try:
            yield key, json.loads(body)
        except ValueError:
            continue
