"""Output keys are relative to the project root, so host and Docker share them."""
from pathlib import Path

from app import outputs, store


def test_folders_inside_the_project_get_relative_keys(tmp_path):
    folder = store.ROOT / "out" / "reports"
    assert outputs.key(folder, "ammn") == "out/reports::AMMN"
    assert outputs.key(tmp_path, "ammn") == f"{tmp_path.resolve()}::AMMN"   # outside: absolute


def test_legacy_absolute_keys_are_still_read(tmp_path):
    folder = store.ROOT / "out" / "reports"
    store.put(outputs.REPORT, f"{folder.resolve()}::BBCA", {"meta": {"ticker": "BBCA"}})
    assert outputs.load(outputs.REPORT, folder, "BBCA") == {"meta": {"ticker": "BBCA"}}
    assert outputs.exists(outputs.REPORT, folder, "BBCA")
    assert outputs.tickers(outputs.REPORT, folder) == ["BBCA"]


def test_migrate_maps_host_and_container_keys_without_overwriting():
    store.put(outputs.REPORT, "/home/me/sektoral/out/reports::AMMN", {"v": "host"})
    store.put(outputs.TRACE, "/app/out/reports::AMMN", {"v": "container"})
    store.put(outputs.REPORT, "out/reports::BBRI", {"v": "new"})
    store.put(outputs.REPORT, "/home/me/sektoral/out/reports::BBRI", {"v": "old"})
    counts = outputs.migrate(roots=["/home/me/sektoral", "/app"], drop_legacy=True)
    assert store.get(outputs.REPORT, "out/reports::AMMN") == {"v": "host"}
    assert store.get(outputs.TRACE, "out/reports::AMMN") == {"v": "container"}
    assert store.get(outputs.REPORT, "out/reports::BBRI") == {"v": "new"}
    assert counts["kept"] == 1 and not store.keys(outputs.REPORT, "/home/me")
