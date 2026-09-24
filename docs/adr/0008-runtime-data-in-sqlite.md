# Runtime data and run outputs live in one SQLite database

Everything the app writes at run time is stored as JSON documents in `data/sectoral.db` (`app/store.py`), addressed by collection and key: agent memory, forecast plans, fetched web news and article text, Yahoo peer and USD/IDR snapshots, research and news analyses, estimator drivers, and each run's report, audit trace, manifest and batch summary (`app/outputs.py`, keyed by run folder and ticker). Before this, each store was its own folder of JSON files, written with hand-rolled atomic-rename code and scattered across `data/` and every output folder. One file gives atomic writes, safe concurrent access from parallel batch runs, a single Docker mount and a single backup. SQLite is used because the Sectors snapshot already is one: nothing new to install or run.

Two things stay files on purpose. The company update HTML, PDF and standalone trace HTML are documents people open. The hand-curated source packs committed to git (`issuer_evidence`, `idx_history`, `market_quotes`, `market_history`, `analyst_scenarios`, `method_overrides`, `rating_history`) are reviewed as diffs, which a database would hide. The 14 article snapshots committed under `data/news_full/` remain read-only fixtures behind the database.

## Considered Options

- **PostgreSQL**: rejected for now; a second service to run and back up for a single-user local tool, with no query the app needs that SQLite lacks.
- **Moving the curated source packs into the database too**: rejected; they are evidence, and their review history in git is part of the audit trail.

## Consequences

- JSON written by older versions is imported with `python -m app.store_import`; it never overwrites a newer record and deletes nothing.
- Tests point `store.DEFAULT_DB` at a per-test temp file (`tests/conftest.py`); functions take an optional `db` argument instead of a directory.
