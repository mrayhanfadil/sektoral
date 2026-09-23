import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import cache


def test_first_returns_newest_cached_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE sectors_cache (cache_key TEXT, endpoint TEXT, "
        "fetched_at REAL, expires_at REAL, payload_json TEXT)"
    )
    con.executemany(
        "INSERT INTO sectors_cache VALUES (?, ?, ?, ?, ?)",
        [
            ("old", "/company/report/TEST/", 1, 10,
             json.dumps({"overview": {"latest_close_date": "2026-09-11"}})),
            ("new", "/company/report/TEST/", 2, 20,
             json.dumps({"overview": {"latest_close_date": "2026-09-22"}})),
        ],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(cache, "DB_PATH", db_path)

    assert cache.first("/company/report/TEST/")["overview"]["latest_close_date"] == "2026-09-22"


def test_company_report_skips_newer_partial_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "cache.db"
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE sectors_cache (cache_key TEXT, endpoint TEXT, "
        "fetched_at REAL, expires_at REAL, payload_json TEXT)"
    )
    endpoint = "/company/report/TEST/"
    complete = {
        "overview": {"last_close_price": 100, "latest_close_date": "2026-09-11"},
        "financials": {"historical_financials": [
            {"year": year, "revenue": 100, "outstanding_shares": 1000}
            for year in (2023, 2024, 2025)
        ]},
    }
    partial = {"overview": {"last_close_price": 110,
                             "latest_close_date": "2026-09-22"}}
    con.executemany(
        "INSERT INTO sectors_cache VALUES (?, ?, ?, ?, ?)",
        [("complete", endpoint, 1, 10, json.dumps(complete)),
         ("partial", endpoint, 2, 20, json.dumps(partial))],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(cache, "DB_PATH", db_path)

    assert cache.company_report("TEST") == complete
