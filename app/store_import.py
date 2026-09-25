"""Import JSON files written before the app database existed.

    python -m app.store_import            # data/ caches and every run under out/
    python -m app.store_import out/demo   # only these output folders

Existing database records are never overwritten, and no file is deleted; once
the import reports what it stored, the old JSON folders can be removed by hand.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import outputs, store

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# data/<folder>/<key>.json -> collection
CACHE_FOLDERS = {
    "agent_memory": "agent_memory",
    "forecast_plans": "forecast_plans",
    "web_news": "web_news",
    "yahoo_fundamentals": "yahoo_fundamentals",
    "research_analysis": "research_analysis",
    "news_analysis": "news_analysis",
    "news_full": "news_full",
    "drivers": "drivers",
}


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _put_new(collection, key, document, db, counts):
    if document is None:
        return
    if store.get(collection, key, db) is not None:
        counts["kept"] = counts.get("kept", 0) + 1
        return
    store.put(collection, key, document, db)
    counts[collection] = counts.get(collection, 0) + 1


def import_caches(data=DATA, db=None, counts=None) -> dict:
    counts = counts if counts is not None else {}
    for folder, collection in CACHE_FOLDERS.items():
        for path in sorted((Path(data) / folder).glob("*.json")):
            key = path.stem.upper() if collection in ("research_analysis", "news_analysis", "drivers") else path.stem
            _put_new(collection, key, _read(path), db, counts)
    fx = _read(Path(data) / "fx_usdidr.json")
    if isinstance(fx, dict):
        _put_new("fx", "USD/IDR", fx, db, counts)
    return counts


def import_outputs(root, db=None, counts=None) -> dict:
    """Report, trace and manifest documents, and batch summaries, under ``root``."""
    counts = counts if counts is not None else {}
    for path in sorted(Path(root).rglob("*.json")):
        folder, name = path.parent, path.name
        if name == "summary.json":
            document = _read(path)
            if isinstance(document, list):
                _put_new(outputs.BATCH, outputs.key(folder), document, db, counts)
            continue
        for suffix, kind in (("-trace.json", outputs.TRACE), ("-manifest.json", outputs.MANIFEST)):
            if name.endswith(suffix):
                _put_new(kind, outputs.key(folder, name[:-len(suffix)]), _read(path), db, counts)
                break
        else:
            document = _read(path)
            meta = document.get("meta") if isinstance(document, dict) else None
            if isinstance(meta, dict) and str(meta.get("ticker") or "").upper() == path.stem.upper():
                _put_new(outputs.REPORT, outputs.key(folder, path.stem), document, db, counts)
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="*", help="output folders to import (default: data/ caches and out/)")
    parser.add_argument("--db", default=None, help="database (default: SECTORAL_DB or data/sectoral.db)")
    args = parser.parse_args(argv)
    counts: dict = {}
    if args.folders:
        for folder in args.folders:
            import_outputs(folder, args.db, counts)
    else:
        import_caches(DATA, args.db, counts)
        import_outputs(ROOT / "out", args.db, counts)
    kept = counts.pop("kept", 0)
    for collection, n in sorted(counts.items()):
        print(f"{collection}: {n} imported")
    print(f"already in the database: {kept}; database: {store.path(args.db)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
