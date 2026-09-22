"""Suite-wide keyless determinism (root conftest, auto-loaded for tests/ and
agents/adk/tests/).

Why this exists: server/main.py force-loads ~/.config/sectors-be/env into
os.environ at import (setdefault), so any test process importing the app -
or any shell with keys exported - would live-fire billable Sectors calls
and warm the prod SQLite cache, masking keyless loud-failure assertions.
Validated Sep 2026: a keyed suite run burned ~12 credits and broke 8 tests.

Live tests stay opt-in via collection-time SECTORS_API_KEY skipif; this
fixture only scrubs the key per-test so everything else runs keyless
against a tmp SQLite cache. It cannot un-skip collection-time skipifs -
run keyed shells only when you intend live billing.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _keyless_tmp_sectors_cache(tmp_path, monkeypatch):
    # SECTORS_LIVE=1 opts into real billing (live-probe); otherwise scrub.
    if os.getenv("SECTORS_LIVE") != "1":
        monkeypatch.delenv("SECTORS_API_KEY", raising=False)

    from server.config import get_settings

    get_settings.cache_clear()

    import server.sectors as _S
    from server.storage import SectorsCache

    iso = SectorsCache(db_path=str(tmp_path / "sectors-iso.db"))
    monkeypatch.setattr(_S, "_cache", iso, raising=False)
    # The collector mirrors into the SAME SQLite cache; without this pin a test run
    # writes fixture rows (ZZZZ/YYYY) into the production data/agent_runs.db, where a
    # later cache probe reads them as a warm cache for a ticker nobody pulled.
    monkeypatch.setenv("SECTORS_CACHE_DB", str(tmp_path / "sectors-iso.db"))
    try:
        yield
    finally:
        iso.close()
        get_settings.cache_clear()
