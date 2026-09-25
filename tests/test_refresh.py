"""One command for the dated market inputs (app.refresh)."""
import json

from app import batch, refresh


def test_steps_run_in_order_and_a_failure_does_not_stop_the_rest():
    calls, lines = [], []

    def ok(name):
        def runner(tickers, as_of):
            calls.append((name, tuple(tickers), as_of))
            return {"stored": {name: "ok"}, "failed": {}}
        return runner

    def boom(tickers, as_of):
        calls.append(("commodity", tuple(tickers), as_of))
        raise RuntimeError("Yahoo down")

    runners = {"fx": ok("fx"), "rates": ok("rates"), "commodity": boom, "quotes": ok("quotes"),
               "peers": ok("peers")}
    results = refresh.run(["ammn", "gmfi"], "2026-09-24", runners=runners, log=lines.append)
    assert [c[0] for c in calls] == ["fx", "rates", "commodity", "quotes", "peers"]
    assert calls[0][1] == ("AMMN", "GMFI") and calls[0][2] == "2026-09-24"
    assert results["commodity"]["failed"] == {"commodity": "RuntimeError: Yahoo down"}
    assert results["peers"]["stored"] == {"peers": "ok"}
    assert "commodity: 0 stored, 1 failed" in lines


def test_only_runs_the_named_steps():
    seen = []
    runner = lambda name: (lambda t, a: seen.append(name) or {"stored": {}, "failed": {}})
    refresh.run(["AMMN"], "2026-09-24", steps=("quotes",),
                runners={k: runner(k) for k in refresh.STEPS}, log=lambda _l: None)
    assert seen == ["quotes"]


def test_peers_use_the_curated_group_else_the_sectors_table():
    symbols, yahoo = refresh.peer_symbols(["AMMN", "BBRI"])
    assert yahoo["ARCI"] == "ARCI.JK" and yahoo["PSAB"] == "PSAB.JK"
    assert all(v == f"{k}.JK" for k, v in yahoo.items())  # curated peers are IDX only
    assert "INCO" not in symbols                     # AMMN's Sectors table is not used
    assert "BMRI" in symbols and "BMRI" not in yahoo  # BBRI has no curated group


def test_a_group_with_too_few_idx_peers_refreshes_the_sectors_table_it_falls_back_to(
        tmp_path, monkeypatch):
    from app import peer_groups
    pack = json.loads((peer_groups.ROOT / "GMFI.json").read_text(encoding="utf-8"))
    pack["peers"] = pack["peers"][:1]                # CASS alone falls back
    (tmp_path / "GMFI.json").write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(peer_groups, "ROOT", tmp_path)
    symbols, yahoo = refresh.peer_symbols(["GMFI"])
    assert yahoo == {"CASS": "CASS.JK"} and {"CASS", "JSMR", "PORT"} <= set(symbols)


def test_batch_refreshes_before_the_runs_when_asked(tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(refresh, "run", lambda tickers, as_of, **kw: order.append(
        ("refresh", tuple(tickers), as_of)))
    monkeypatch.setattr(batch, "run_one", lambda ticker, args: order.append(("run", ticker))
                        or {"ticker": ticker, "exit": 0, "minutes": 0.0})
    monkeypatch.setattr(batch.outputs, "save", lambda *a, **k: None)
    assert batch.main(["AMMN", "--as-of", "2026-09-24", "--out", str(tmp_path),
                       "--refresh-data"]) == 0
    assert order == [("refresh", ("AMMN",), "2026-09-24"), ("run", "AMMN")]
