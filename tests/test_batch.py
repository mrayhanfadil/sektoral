"""Parallel batch runner (app.batch)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import batch, outputs  # noqa: E402


def test_runs_tickers_in_parallel_and_writes_summary(tmp_path, monkeypatch):
    seen = []

    def fake_run(cmd, cwd, stdout, stderr, timeout):
        ticker = cmd[cmd.index("app.research") + 1]
        seen.append(ticker)
        outputs.save(outputs.REPORT, tmp_path, ticker,
                     {"meta": {"status": "draft_non_distributable"}, "method": "m",
                      "harness": {"blockers": ["x"]}})
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    code = batch.main(["jpfa", "gmfi", "--jobs", "2", "--out", str(tmp_path),
                       "--as-of", "2026-09-24", "--pdf"])
    assert code == 0 and sorted(seen) == ["GMFI", "JPFA"]
    rows = outputs.load(outputs.BATCH, tmp_path)
    assert not list(tmp_path.glob("*.json"))
    assert [r["ticker"] for r in rows] == ["JPFA", "GMFI"]
    assert rows[0]["blockers"] == ["x"] and rows[0]["exit"] == 0


def test_news_full_is_stored_in_the_database_not_as_files(tmp_path):
    from app import news_fetch, store
    news_fetch._save("https://example.com/a", {"full_text": "isi"}, tmp_path)
    assert not list(tmp_path.glob("*.json"))
    assert store.keys(news_fetch.COLLECTION, db=tmp_path) == [news_fetch._url_key("https://example.com/a")]
    assert news_fetch.load_cached("https://example.com/a", tmp_path)["full_text"] == "isi"
