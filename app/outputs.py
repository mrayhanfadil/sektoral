"""Run outputs in the app database, addressed by run folder and ticker.

A run writes its readable documents (company update HTML, PDF, standalone
trace HTML) into an output folder; the structured documents that describe it
(report, audit trace, run manifest, batch summary) go to the database under
the same folder, so a gallery or job still finds everything by folder.
"""
from __future__ import annotations

from pathlib import Path

from . import store

REPORT, TRACE, MANIFEST, BATCH = "report", "trace", "manifest", "batch_summary"


def _prefix(outdir) -> str:
    return f"{Path(outdir).resolve()}::"


def key(outdir, ticker: str = "") -> str:
    return _prefix(outdir) + str(ticker).upper()


def save(kind: str, outdir, ticker: str, document, db=None) -> str:
    """Store one output document; returns its key."""
    k = key(outdir, ticker)
    store.put(kind, k, document, db)
    return k


def load(kind: str, outdir, ticker: str = "", db=None):
    return store.get(kind, key(outdir, ticker), db)


def exists(kind: str, outdir, ticker: str, db=None) -> bool:
    k = key(outdir, ticker)
    return k in store.keys(kind, k, db)


def tickers(kind: str, outdir, db=None) -> list[str]:
    """Tickers with a ``kind`` document in ``outdir``, sorted."""
    prefix = _prefix(outdir)
    return [k[len(prefix):] for k in store.keys(kind, prefix, db) if k[len(prefix):]]


def copy(outdir, ticker: str, destination, db=None) -> None:
    """Copy a run's documents to another folder (publishing to the gallery)."""
    for kind in (REPORT, TRACE, MANIFEST):
        document = load(kind, outdir, ticker, db)
        if document is not None:
            save(kind, destination, ticker, document, db)
