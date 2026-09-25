"""One command for the dated market inputs (app.refresh)."""
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

    runners = {"fx": ok("fx"), "commodity": boom, "quotes": ok("quotes"), "peers": ok("peers")}
    results = refresh.run(["ammn", "gmfi"], "2026-09-24", runners=runners, log=lines.append)
    assert [c[0] for c in calls] == ["fx", "commodity", "quotes", "peers"]
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
    symbols, yahoo = refresh.peer_symbols(["GMFI", "BBRI"])
    assert yahoo["S59.SI"] == "S59.SI" and yahoo["AIR"] == "AIR"
    assert "JSMR" not in symbols                     # GMFI's Sectors table is not used
    assert "BMRI" in symbols and "BMRI" not in yahoo  # BBRI has no curated group


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
