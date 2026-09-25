"""Run outputs in the app database, addressed by run folder and ticker.

A run writes its readable documents (company update HTML, PDF, standalone
trace HTML) into an output folder; the structured documents that describe it
(report, audit trace, run manifest, batch summary, and the progress events a
run recorded) go to the database under the same folder, so a gallery or job
still finds everything by folder.

Keys are ``<folder>::<TICKER>``. A folder inside the project is written
relative to the project root (``out/reports::AMMN``), so the host and the
Docker image (project at ``/app``) read the same documents from the shared
database. Older keys used the absolute folder path; reads still find them,
and ``python -m app.outputs --migrate`` rewrites them once.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import store

REPORT, TRACE, MANIFEST, BATCH = "report", "trace", "manifest", "batch_summary"
EVENTS = "run_events"


def _prefix(outdir) -> str:
    path = Path(outdir).resolve()
    try:
        return f"{path.relative_to(store.ROOT).as_posix()}::"
    except ValueError:  # a folder outside the project keeps its absolute path
        return f"{path}::"


def _legacy_prefix(outdir) -> str:
    """The absolute-path prefix older versions wrote."""
    return f"{Path(outdir).resolve()}::"


def key(outdir, ticker: str = "") -> str:
    return _prefix(outdir) + str(ticker).upper()


def _read_key(kind: str, outdir, ticker: str, db=None) -> str:
    """The key holding this document: the current one, else a legacy one."""
    k = key(outdir, ticker)
    if k in store.keys(kind, k, db):
        return k
    legacy = _legacy_prefix(outdir) + str(ticker).upper()
    return legacy if legacy != k and legacy in store.keys(kind, legacy, db) else k


def save(kind: str, outdir, ticker: str, document, db=None) -> str:
    """Store one output document; returns its key."""
    k = key(outdir, ticker)
    store.put(kind, k, document, db)
    return k


def load(kind: str, outdir, ticker: str = "", db=None):
    return store.get(kind, _read_key(kind, outdir, ticker, db), db)


def exists(kind: str, outdir, ticker: str, db=None) -> bool:
    k = _read_key(kind, outdir, ticker, db)
    return k in store.keys(kind, k, db)


def tickers(kind: str, outdir, db=None) -> list[str]:
    """Tickers with a ``kind`` document in ``outdir``, sorted."""
    found = set()
    for prefix in {_prefix(outdir), _legacy_prefix(outdir)}:
        found.update(k[len(prefix):] for k in store.keys(kind, prefix, db) if k[len(prefix):])
    return sorted(found)


KINDS = (REPORT, TRACE, MANIFEST, BATCH, EVENTS)


def migrate(roots=(), drop_legacy=False, db=None) -> dict:
    """Rewrite absolute-path keys under the project root (and ``roots``) as relative keys.

    ``roots`` names other places the same project lived when the keys were
    written (e.g. the host checkout, seen from inside the Docker image, or a
    git worktree). An existing relative key is never overwritten.
    """
    bases = [store.ROOT] + [Path(r).resolve() for r in roots]
    counts = {"copied": 0, "kept": 0, "dropped": 0}
    for kind in KINDS:
        for old in store.keys(kind, "", db):
            folder, sep, ticker = old.partition("::")
            if not sep or not folder.startswith("/"):
                continue
            rel = next((Path(folder).relative_to(b).as_posix() for b in bases
                        if Path(folder).is_relative_to(b)), None)
            if rel is None:
                continue
            new = f"{rel}::{ticker}"
            if new in store.keys(kind, new, db):
                counts["kept"] += 1
            else:
                store.put(kind, new, store.get(kind, old, db), db)
                counts["copied"] += 1
            if drop_legacy:
                store.delete(kind, old, db)
                counts["dropped"] += 1
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run outputs in the app database")
    parser.add_argument("--migrate", action="store_true",
                        help="rewrite absolute-path keys as project-relative keys")
    parser.add_argument("--root", action="append", default=[],
                        help="another path this project lived at when keys were written")
    parser.add_argument("--drop-legacy", action="store_true",
                        help="delete the absolute-path keys after copying them")
    args = parser.parse_args(argv)
    if not args.migrate:
        parser.print_help()
        return 1
    print(migrate(args.root, args.drop_legacy))
    return 0


def copy(outdir, ticker: str, destination, db=None) -> None:
    """Copy a run's documents to another folder (publishing to the gallery)."""
    for kind in (REPORT, TRACE, MANIFEST, EVENTS):
        document = load(kind, outdir, ticker, db)
        if document is not None:
            save(kind, destination, ticker, document, db)


if __name__ == "__main__":
    sys.exit(main())
