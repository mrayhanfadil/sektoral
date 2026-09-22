"""Engine fetch+cache: tanpa network di test, tanpa key di repo."""
import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import sectors as S  # noqa: E402
from app import topup as T  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    p = tmp_path / "c.db"
    c = sqlite3.connect(str(p))
    c.execute("CREATE TABLE sectors_cache (cache_key TEXT PRIMARY KEY,"
              " endpoint TEXT NOT NULL, fetched_at REAL NOT NULL,"
              " expires_at REAL NOT NULL, payload_json TEXT NOT NULL)")
    c.commit()
    c.close()
    return p


def seed(db, key, ep, payload, ttl=3600, stale=False):
    now = time.time()
    exp = now - 10 if stale else now + ttl
    c = sqlite3.connect(str(db))
    c.execute("INSERT INTO sectors_cache VALUES (?,?,?,?,?)",
              (key, ep, now, exp, json.dumps(payload)))
    c.commit()
    c.close()


def test_cache_key_deterministik():
    assert S.cache_key("/daily/AMMN/", {"a": 1, "b": 2}) == \
        S.cache_key("/daily/AMMN/", {"b": 2, "a": 1})
    assert S.cache_key("/daily/AMMN/", {}).startswith("sc:/daily/AMMN/:")


def test_hit_tanpa_network(db):
    seed(db, S.cache_key("/daily/AMMN/", {}), "/daily/AMMN/", {"data": [1]})
    cli = S.Client(key=None, db=db)
    r = cli.get("/daily/AMMN/")
    assert r["source"] == "cache" and r["payload"] == {"data": [1]}


def test_stale_dilayani_tanpa_key(db):
    seed(db, S.cache_key("/daily/AMMN/", {}), "/daily/AMMN/", {"old": 1},
         stale=True)
    cli = S.Client(key=None, db=db)
    r = cli.get("/daily/AMMN/")
    assert r["source"] == "stale" and r["expired"] is True


def test_miss_tanpa_key_gagal_keras(db):
    cli = S.Client(key=None, db=db)
    with pytest.raises(S.SectorsError, match="tanpa SECTORS_API_KEY"):
        cli.get("/daily/ZZZZ/")


def test_mining_calls_butuh_discovery_dulu():
    calls = T.mining_calls("AMMN", None)
    eps = [e for e, _ in calls]
    assert "/mining/companies/" in eps  # discovery, bukan tebak slug
    assert "/mining/commodities/Copper/price/" in eps
    assert "/mining/commodities/Gold/price/" in eps
    assert not any("/None/" in e for e in eps)


def test_mining_calls_dengan_slug():
    calls = T.mining_calls("AMMN", "pt-amman-mineral-internasional-tbk")
    eps = [e for e, _ in calls]
    assert any("performance" in e for e in eps)
