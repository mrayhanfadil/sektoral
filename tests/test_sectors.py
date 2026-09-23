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


def test_lama_tetap_dilayani_tanpa_key(db):
    seed(db, S.cache_key("/daily/AMMN/", {}), "/daily/AMMN/", {"old": 1},
         stale=True)
    cli = S.Client(key=None, db=db)
    r = cli.get("/daily/AMMN/")
    assert r["source"] == "cache" and r["expired"] is False  # never-expired


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


def test_mineops_ammn_dari_cache():
    from app import mineops
    m = mineops.load("AMMN")
    assert m is not None
    assert m["year"] == 2024
    assert m["comms"]["Copper"]["prod"] == 179.1
    assert m["comms"]["Gold"]["prod"] == 463.5
    assert 70 < m["reserve_life_cu_yr"] < 80
    assert m["cu_price"]["n"] >= 30 and m["au_price"]["n"] >= 30


def test_mineops_non_tambang_none():
    from app import mineops
    assert mineops.load("BBCA") is None
    assert mineops.load("ZZZZ") is None


def test_keyless_503_behavior(db):
    cli = S.Client(key=None, db=db)
    with pytest.raises(S.SectorsNotConfigured) as exc_info:
        cli.get("/daily/ZZZZ/")
    assert exc_info.value.status_code == 503
    assert "tanpa SECTORS_API_KEY" in str(exc_info.value)


def test_minimal_sections():
    # String input with duplicates and extra spaces
    res = S.minimal_sections("overview, peers, overview, valuation,  peers ")
    assert res == "overview,peers,valuation"

    # List input
    res_list = S.minimal_sections(["overview", "peers", "overview"])
    assert res_list == "overview,peers"

    # Empty raises ValueError
    with pytest.raises(ValueError, match="At least one section"):
        S.minimal_sections("")


def test_credit_policy_budget_rules():
    import docs.integration.credit_policy as cp

    # Rule: 1 credit per endpoint / section, 3 for NL, 1 for 404
    assert cp.COST_PER_ENDPOINT == 1
    assert cp.COST_PER_SECTION == 1
    assert cp.COST_NL_QUERY == 3
    assert cp.COST_404_LOOKUP == 1

    # Rule: Reject or warn against natural language queries (?q=)
    with pytest.warns(cp.NLQueryWarning, match="costs 3 credits"):
        cp.check_query_params({"q": "best mining stocks in Indonesia"})
    with pytest.raises(ValueError, match="costs 3 credits"):
        cp.check_query_params({"q": "best mining stocks"}, strict=True)
    # Structured queries pass silently
    cp.check_query_params({"where": "market_cap > 1000000"})

    # Rule: Validate ticker existence before dispatch (404 penalty)
    assert cp.validate_ticker("BBCA") == "BBCA"
    assert cp.validate_ticker("bbca.jk") == "BBCA"
    with pytest.raises(ValueError, match="Invalid IDX ticker"):
        cp.validate_ticker("TOOLONG123")
    with pytest.raises(ValueError, match="Invalid ticker"):
        cp.validate_ticker("")

    # Rule: Check quarterly-financial-dates before pulling full quarterly
    with pytest.raises(ValueError, match="quarterly-financial-dates"):
        cp.check_quarterly_dates_first("BBCA", None)
    assert cp.check_quarterly_dates_first("BBCA", ["2024-Q1", "2024-Q2"]) is True
    assert cp.check_quarterly_dates_first("BBCA", []) is False

    # Rule: Prefer minimal sections= parameter over bloated payloads
    deduped = cp.validate_minimal_sections("overview, peers, overview, valuation")
    assert deduped == ["overview", "peers", "valuation"]
    with pytest.warns(UserWarning, match="exceeds recommended minimal limit"):
        cp.validate_minimal_sections("overview,peers,future,valuation,financials,dividend,ownership,management")

    # Rule: Assert total dry-run budget for a quintet harvest remains < 100 credits
    total = cp.assert_quintet_budget()
    assert total < 100
    assert total == 97
