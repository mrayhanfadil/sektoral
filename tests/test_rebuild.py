"""Offline rebuild of stored company updates (app.rebuild).

A synthetic stored run stands in for the developer's database, and a fake
``build.build`` records what it was given, so these tests never depend on the
Sectors Snapshot or the real app database (conftest points the store at
tmp_path).
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import build, commodity, fx, gallery, intake, outputs, peer_fundamentals, rates, rebuild, store  # noqa: E402

AS_OF = "2026-09-24"
RAW_PLAN = {"earnings_scenario": {"h2_revenue": 10.0}, "source": "agent"}
NORMALIZED_PLAN = {"earnings_scenario": {"h2_revenue": 10.0}, "source": "agent", "normalized": True}
ARTICLES = [{"source": "https://example.test/a", "title": "A", "timestamp": "2026-09-20"}]
DEEPDIVE = [{"source_url": "https://example.test/a", "fetch_status": "fetched", "full_text": "x"}]
SEARCH = {"status": "searched", "as_of": AS_OF, "queries": [{"query": "AAAA"}]}


def _doc(ticker, rating="Hold", tp=1100, revenue=("1.000,0", "1.100,0"), bars=None):
    fc_cols = ["FY26F", "FY27F"]
    return {
        "meta": {"ticker": ticker, "emiten": f"PT {ticker} Tbk", "tanggal": AS_OF,
                 "harga_tanggal": AS_OF, "harga": 1000.0, "status": "distributable_assumption_led",
                 "rating": rating, "tp": tp, "upside_persen": tp / 10 - 100,
                 "illustrative_scenarios": False, "research_status": "validated",
                 "model_profile": "going_concern_fcff"},
        "method": "DCF FCFF skenario FY26F-FY30F",
        "log_gate": {"release": {"route": "primary"}},
        "harness": {"blockers": []},
        "forecast_assumptions": {"plan": NORMALIZED_PLAN, "product_sales_scenario": None},
        "exhibits": [
            {"judul": "Key Financials", "tipe": "tabel",
             "data": {"cols": ["Tahun buku 31 Des", "2025", *fc_cols],
                      "rows": [["Pendapatan (Rp miliar)", "900,0", *revenue]]}},
            {"judul": "Pendapatan dan pertumbuhan (2021-FY28F)", "tipe": "combo_panel",
             "data": {"cols": ["2025", *fc_cols],
                      "series": [{"label": "Pendapatan", "bars": [9e11, *(bars or (1e12, 1.1e12))],
                                  "line": [None, 11.1, 10.0], "is_forecast": [False, True, True]}]}},
            {"judul": "Perbandingan peer Contoh", "tipe": "tabel",
             "data": {"cols": ["Emiten"], "rows": [["BBBB"], [f"{ticker} (emiten)"], ["CCCC"],
                                                  ["Median peer (tanpa emiten)"]]}},
        ],
        "run_manifest": {"ticker": ticker, "code_revision": "new"},
        "evidence_register": {"ticker": ticker, "rows": []},
    }


def _trace(ticker, raw_plan=True):
    fa = {"status": "partial", "earnings_status": "validated", "interim_status": "not_run",
          "plan": NORMALIZED_PLAN, "spec_sha256": "abc123"}
    if raw_plan:
        fa.update(agent_plan_raw=RAW_PLAN, plan_normalized_for_report=True)
    return {"ticker": ticker, "analyst": {"status": "ok", "plan": {"question": "Q?"}},
            "research": {"ok": True, "document": {"summary": "brief"}},
            "forecast_assumptions": fa,
            "news_sources": {"search": SEARCH, "articles": ARTICLES, "rejected": [], "stats": {}},
            "evidence_register": {"ticker": ticker, "rows": ["old"]},
            "run_manifest": {"ticker": ticker, "code_revision": "old"},
            "product_sales_scenario": None,
            "news_deepdive": DEEPDIVE,
            "report": {"status": "distributable_assumption_led", "as_of": AS_OF,
                       "market_price_date": AS_OF, "illustrative_scenarios": False,
                       "target_method": "DCF FCFF skenario FY26F-FY30F", "target_price": 1100,
                       "rating": "Hold", "research_status": "validated"}}


def _stored_run(folder: Path, ticker="AAAA", manifest=None, events=None, **doc):
    outputs.save(outputs.REPORT, folder, ticker, _doc(ticker, **doc))
    outputs.save(outputs.TRACE, folder, ticker, _trace(ticker))
    outputs.save(outputs.MANIFEST, folder, ticker,
                 manifest or {"ticker": ticker, "code_revision": "old"})
    if events is not None:
        outputs.save(outputs.EVENTS, folder, ticker, events)


class FakeBuild:
    """Stands in for build.build: records its arguments and writes like it."""

    def __init__(self, make_doc=None):
        self.calls = []
        self.make_doc = make_doc or (lambda ticker, kwargs: _doc(ticker))

    def __call__(self, ticker, outdir, want_pdf=False, **kwargs):
        self.calls.append({"ticker": ticker, "outdir": outdir, "want_pdf": want_pdf, **kwargs})
        doc = self.make_doc(ticker, kwargs)
        outputs.save(outputs.REPORT, outdir, ticker, doc)
        (outdir / f"{ticker}.html").write_text("<html>report</html>")
        print(f"{ticker} built")  # the builder's own output is captured, not printed
        return doc


@pytest.fixture
def fake_build(monkeypatch):
    fake = FakeBuild()
    monkeypatch.setattr(build, "build", fake)
    return fake


def test_rebuild_gives_build_the_stored_inputs_like_research_run(tmp_path, fake_build, capsys):
    source, out = tmp_path / "src", tmp_path / "out"
    events = [{"stage": "news", "label": "Mencari berita", "t": 1.0}]
    _stored_run(source, events=events)

    assert rebuild.main(["--from", str(source), "--out", str(out)]) == 0

    call, = fake_build.calls
    assert call["want_pdf"] is False and call["as_of"] == AS_OF
    # The agent's own plan, as research._run handed it to the builder.
    assert call["assumption_plan"] == RAW_PLAN
    assert call["news_evidence"] == {"rows": ARTICLES, "full": DEEPDIVE, "search": SEARCH}
    assert call["assumption_status"] == "validated"  # earnings_status wins over status
    assert call["spec_sha"] == "abc123"
    assert call["method_override"] is None and call["analyst_target"] is False
    assert call["illustrative_scenarios"] is False
    line = capsys.readouterr().out
    assert "AAAA" in line and "rating/TP sama" in line and "Key Financials: sama" in line
    assert "built" not in line
    assert "'Contoh' 2 peer" in line
    # A complete run folder: report, trace, manifest, events, HTML, trace HTML.
    trace = outputs.load(outputs.TRACE, out, "AAAA")
    stored = _trace("AAAA")
    for key in ("analyst", "research", "forecast_assumptions", "news_sources", "news_deepdive"):
        assert trace[key] == stored[key]
    manifest = outputs.load(outputs.MANIFEST, out, "AAAA")
    assert manifest["rebuild"]["source_code_revision"] == "old"
    assert trace["run_manifest"] == manifest
    assert outputs.load(outputs.EVENTS, out, "AAAA") == events
    assert (out / "AAAA.html").is_file() and (out / "AAAA-trace.html").is_file()
    assert [item["ticker"] for item in gallery.load(out)] == ["AAAA"]


def test_trace_without_a_normalized_plan_passes_the_stored_plan():
    trace = _trace("AAAA", raw_plan=False)
    trace["forecast_assumptions"].update(earnings_status="not_run", interim_status="validated")
    inputs = rebuild.build_inputs(trace, _doc("AAAA"))
    assert inputs["assumption_plan"] == NORMALIZED_PLAN
    assert inputs["assumption_status"] == "validated"
    trace["forecast_assumptions"].update(interim_status="not_run")
    assert rebuild.build_inputs(trace)["assumption_status"] == "partial"


def test_a_recorded_method_override_is_passed_on():
    doc = _doc("AAAA")
    doc["log_gate"]["release"] = {"route": "override", "override": {"method": "relative_pe"}}
    assert rebuild.build_inputs(_trace("AAAA"), doc)["method_override"] == "relative_pe"


def test_run_flags_recorded_in_the_trace_are_repeated():
    trace = _trace("AAAA")
    trace["report"].update(analyst_target=True, method_override="ev_ebitda_fy")
    inputs = rebuild.build_inputs(trace, _doc("AAAA"))
    assert inputs["analyst_target"] is True and inputs["illustrative_scenarios"] is True
    assert inputs["method_override"] == "ev_ebitda_fy"


def test_moves_are_reported_and_the_trace_follows_the_new_report(tmp_path, monkeypatch, capsys):
    source, out = tmp_path / "src", tmp_path / "out"
    _stored_run(source)
    monkeypatch.setattr(build, "build", FakeBuild(
        lambda ticker, _: _doc(ticker, rating="Buy", tp=1500, revenue=("1.000,0", "1.250,0"))))

    assert rebuild.main(["--from", str(source), "--out", str(out), "--changes"]) == 0

    printed = capsys.readouterr().out
    assert "BERUBAH: rating, TP (sumber: Hold Rp1.100)" in printed
    assert "Key Financials: 1 sel berubah" in printed
    assert "Pendapatan (Rp miliar) FY27F: 1.100,0 -> 1.250,0" in printed
    report = outputs.load(outputs.TRACE, out, "AAAA")["report"]
    assert report["rating"] == "Buy" and report["target_price"] == 1500
    assert report["target_method"] == "DCF FCFF skenario FY26F-FY30F"


def test_changed_valuation_events_replace_the_stored_ones():
    stored = [{"stage": "news", "label": "berita", "t": 1.0},
              {"stage": "gate", "label": "Gerbang", "t": 10.0},
              {"stage": "report", "label": "Status rilis: lama", "tool": "release", "t": 12.0},
              {"stage": "done", "label": "Selesai", "t": 20.0}]
    fresh = [{"stage": "report", "label": "unrelated", "t": 0.1},
             {"stage": "gate", "label": "Gerbang", "t": 0.2},
             {"stage": "report", "label": "Status rilis: baru", "tool": "release", "t": 0.3}]
    merged = rebuild.merged_events(stored, fresh)
    assert [e["label"] for e in merged] == ["berita", "Gerbang", "Status rilis: baru", "Selesai"]
    assert [e["t"] for e in merged] == [1.0, 10.0, 12.0, 20.0]
    same = [dict(e, t=0.0) for e in stored[1:3]]
    assert rebuild.merged_events(stored, same) == stored


def test_a_failed_ticker_fails_the_command_but_not_the_others(tmp_path, fake_build, capsys):
    source, out = tmp_path / "src", tmp_path / "out"
    _stored_run(source, "AAAA")
    outputs.save(outputs.REPORT, source, "BBBB", _doc("BBBB"))  # report without a trace

    assert rebuild.main(["--from", str(source), "--out", str(out)]) == 1

    printed = capsys.readouterr().out
    assert "BBBB  GAGAL" in printed and "no stored audit trace" in printed
    assert outputs.load(outputs.REPORT, out, "AAAA") is not None


def test_the_build_runs_offline(tmp_path, monkeypatch):
    source, out = tmp_path / "src", tmp_path / "out"
    _stored_run(source)
    seen = {}

    def networked(ticker, kwargs):
        seen["offline"] = os.environ.get("SEKTORAL_OFFLINE")
        with pytest.raises(rebuild.OfflineError):
            socket.create_connection(("example.test", 443), timeout=1)
        return _doc(ticker)

    monkeypatch.delenv("SEKTORAL_OFFLINE", raising=False)
    monkeypatch.setattr(build, "build", FakeBuild(networked))
    rebuild.rebuild_one("AAAA", source, out)
    assert seen["offline"] == "1"
    assert "SEKTORAL_OFFLINE" not in os.environ
    assert socket.create_connection is not None and socket.socket.connect.__name__ != "refuse"


def _reads_market_inputs(ticker, _kwargs):
    """A build that reads the three dated snapshots and shows them in the report."""
    doc = _doc(ticker)
    quote, copper = fx.load_cached_rate(), commodity.load("Copper")
    peer = peer_fundamentals.load("BBBB.JK")
    doc["meta"]["seen"] = {"fx": (quote or {}).get("rate"),
                           "copper": ((copper or {}).get("rows") or [{}])[-1].get("price"),
                           "peer": (peer or {}).get("ebitda")}
    return doc


def test_recorded_market_inputs_are_pinned_and_recorded_again(tmp_path, monkeypatch, capsys):
    source, out, again = tmp_path / "src", tmp_path / "out", tmp_path / "again"
    pins = {"fx": {"pair": "USD/IDR", "rate": 17000.0, "date": AS_OF, "source": "Yahoo"},
            "commodities": {"Copper": {"rows": [{"date": AS_OF, "price": 9000.0}]}},
            "peer_snapshots": {"BBBB": {"ebitda": 5.0}}}
    _stored_run(source, manifest={"ticker": "AAAA", "code_revision": "old", "market_inputs": pins})
    # Today's snapshots in the database differ from what the source run read.
    store.put(fx.COLLECTION, fx.KEY, {"pair": "USD/IDR", "rate": 18000.0, "date": AS_OF,
                                      "source": "Yahoo Finance IDR=X daily close"})
    monkeypatch.setattr(build, "build", FakeBuild(_reads_market_inputs))

    rebuild.main(["--from", str(source), "--out", str(out)])

    doc = outputs.load(outputs.REPORT, out, "AAAA")
    assert doc["meta"]["seen"] == {"fx": 17000.0, "copper": 9000.0, "peer": 5.0}
    assert outputs.load(outputs.MANIFEST, out, "AAAA")["market_inputs"] == pins
    assert "snapshot pasar dari manifest sumber" in capsys.readouterr().out
    assert fx.load_cached_rate()["rate"] == 18000.0  # loaders restored

    rebuild.main(["--from", str(source), "--out", str(again), "--live-inputs"])
    assert outputs.load(outputs.REPORT, again, "AAAA")["meta"]["seen"]["fx"] == 18000.0


def test_a_pinned_ust_series_is_served_and_recorded(tmp_path, monkeypatch):
    source, out = tmp_path / "src", tmp_path / "out"
    series = {"name": "UST10Y", "symbol": "^TNX", "source": "Yahoo Finance ^TNX daily close",
              "rows": [{"date": AS_OF, "yield_pct": 4.5}]}
    _stored_run(source, manifest={"ticker": "AAAA", "code_revision": "old",
                                  "market_inputs": {"rates": {"UST10Y": series}}})
    # Today's series in the database differs from what the source run read.
    store.put(rates.COLLECTION, rates.UST10Y, {**series, "rows": [{"date": AS_OF, "yield_pct": 5.2}]})

    def reads_ust(ticker, _kwargs):
        doc = _doc(ticker)
        doc["meta"]["seen"] = rates.on_or_before(AS_OF)["rate"]
        return doc

    monkeypatch.setattr(build, "build", FakeBuild(reads_ust))
    rebuild.main(["--from", str(source), "--out", str(out)])
    assert outputs.load(outputs.REPORT, out, "AAAA")["meta"]["seen"] == pytest.approx(0.045)
    assert outputs.load(outputs.MANIFEST, out, "AAAA")["market_inputs"]["rates"] == {
        "UST10Y": series}
    assert rates.on_or_before(AS_OF)["rate"] == pytest.approx(0.052)  # loader restored


def _usd_rebuild(monkeypatch, usd_revenue):
    monkeypatch.setattr(intake, "load", lambda ticker, as_of=None: (
        {"official_evidence": {"reporting_currency": "USD"}, "peer_basis": None}, {}))

    def usd_build(ticker, _kwargs):
        intake.load(ticker, as_of=AS_OF)
        rate = fx.load_cached_rate()["rate"]
        return _doc(ticker, bars=tuple(v * rate for v in usd_revenue))

    fake = FakeBuild(usd_build)
    monkeypatch.setattr(build, "build", fake)
    return fake


def test_a_usd_reporters_source_fx_is_recovered_from_the_source_report(tmp_path, monkeypatch, capsys):
    """No stored close for the source's price date: the source report's own
    rate is recovered and labelled as implied, never as a Yahoo close."""
    source, out = tmp_path / "src", tmp_path / "out"
    usd_revenue = (100.0e6, 110.0e6)
    _stored_run(source, bars=tuple(v * 17893.0 for v in usd_revenue))
    store.put(fx.COLLECTION, fx.KEY, {"pair": "USD/IDR", "rate": 17837.3, "date": "2026-09-25",
                                      "source": "Yahoo Finance IDR=X daily close"})
    fake = _usd_rebuild(monkeypatch, usd_revenue)

    assert rebuild.main(["--from", str(source), "--out", str(out)]) == 0

    assert len(fake.calls) == 2  # today's snapshot, then the recovered source rate
    doc = outputs.load(outputs.REPORT, out, "AAAA")
    assert doc["exhibits"][1]["data"]["series"][0]["bars"][1] == pytest.approx(100.0e6 * 17893.0)
    quote = outputs.load(outputs.MANIFEST, out, "AAAA")["market_inputs"]["fx"]
    assert quote == {"pair": "USD/IDR", "rate": pytest.approx(17893.0), "date": AS_OF,
                     "source": fx.IMPLIED_SOURCE}
    assert fx.basis(quote) == "kurs tersirat dari report sumber"
    assert fx.dated(quote) == f"tersirat dari report sumber, harga {AS_OF}"
    assert "kurs Rp17.893,0/USD tersirat dari report sumber" in capsys.readouterr().out


def test_the_stored_close_for_the_source_price_date_is_kept(tmp_path, monkeypatch):
    """The database holds the close for the source report's price date: that
    quote is the rate of record, not one back-solved from the source report."""
    source, out = tmp_path / "src", tmp_path / "out"
    usd_revenue = (100.0e6, 110.0e6)
    _stored_run(source, bars=tuple(v * 17893.0 for v in usd_revenue))
    close = {"pair": "USD/IDR", "rate": 17837.3, "date": AS_OF,
             "source": "Yahoo Finance IDR=X daily close"}
    store.put(fx.COLLECTION, fx.KEY, close)
    fake = _usd_rebuild(monkeypatch, usd_revenue)

    assert rebuild.main(["--from", str(source), "--out", str(out)]) == 0

    assert len(fake.calls) == 1
    assert outputs.load(outputs.MANIFEST, out, "AAAA")["market_inputs"]["fx"] == close
    doc = outputs.load(outputs.REPORT, out, "AAAA")
    assert doc["exhibits"][1]["data"]["series"][0]["bars"][1] == pytest.approx(100.0e6 * 17837.3)


def test_a_pinned_rate_recorded_as_a_yahoo_close_is_corrected(tmp_path, monkeypatch, capsys):
    """Earlier rebuilds pinned the recovered rate under the Yahoo quote's date
    and source. The stored close for that date replaces it; without one the
    rate stays, labelled as implied."""
    usd_revenue = (100.0e6, 110.0e6)
    legacy = {"pair": "USD/IDR", "rate": 17893.0, "date": AS_OF,
              "source": "Yahoo Finance IDR=X daily close",
              "note": "tersirat dari report sumber (app.rebuild)"}
    close = {"pair": "USD/IDR", "rate": 17837.3, "date": AS_OF,
             "source": "Yahoo Finance IDR=X daily close"}
    source = tmp_path / "src"
    _stored_run(source, manifest={"ticker": "AAAA", "code_revision": "old",
                                  "market_inputs": {"fx": legacy}})
    _usd_rebuild(monkeypatch, usd_revenue)

    store.put(fx.COLLECTION, fx.KEY, close)
    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "a")]) == 0
    assert outputs.load(outputs.MANIFEST, tmp_path / "a", "AAAA")["market_inputs"]["fx"] == close
    assert "kurs Rp17.893,0/USD tersirat diganti kurs tersimpan Rp17.837,3/USD" in \
        capsys.readouterr().out

    store.put(fx.COLLECTION, fx.KEY, {**close, "date": "2026-09-25"})
    assert rebuild.main(["--from", str(source), "--out", str(tmp_path / "b")]) == 0
    quote = outputs.load(outputs.MANIFEST, tmp_path / "b", "AAAA")["market_inputs"]["fx"]
    assert quote == fx.implied_quote(17893.0, AS_OF)


def test_pinned_fx_leaves_a_market_quote_alone():
    close = {"pair": "USD/IDR", "rate": 17837.3, "date": AS_OF, "source": "Yahoo"}
    assert rebuild.pinned_fx(close, {**close, "rate": 1.0}, AS_OF) == (close, None)
    assert rebuild.pinned_fx(None, close, AS_OF) == (None, None)
    assert fx.basis(close) == "Yahoo Finance IDR=X" and fx.dated(close) == AS_OF


def test_out_must_differ_from_the_source(tmp_path):
    with pytest.raises(SystemExit):
        rebuild.main(["--from", str(tmp_path), "--out", str(tmp_path)])


FRESH_PLAN = {"earnings_scenario": {"bank_drivers": {"year": 2026, "nim_pct": 5.6}},
              "bank_outyear_scenario": [{"year": 2027}]}


def test_refresh_assumptions_reruns_the_agent_on_stored_evidence(tmp_path, fake_build,
                                                                 monkeypatch):
    """--refresh-assumptions: the agent (no real LLM here) reads the stored news
    register and deep-dive, the rebuild uses its new plan and the rebuilt trace
    stores it."""
    source, out = tmp_path / "src", tmp_path / "out"
    _stored_run(source)
    seen = {}

    def fake_agent(intake_, refresh=False, db=None):
        seen.update(intake=intake_, refresh=refresh)
        return {"status": "validated", "earnings_status": "validated", "plan": dict(FRESH_PLAN),
                "problems": [], "spec_sha256": "new-spec", "fingerprint": "f1"}

    from agents.forecast_assumptions import run as agent
    monkeypatch.setattr(agent, "run_cached", fake_agent)
    monkeypatch.setattr(intake, "load", lambda ticker, as_of=None: (
        {"ticker": ticker, "as_of": as_of, "model_profile": "financial_ddm"}, {}))
    assert rebuild.main(["--from", str(source), "--out", str(out), "--refresh-assumptions",
                         "AAAA"]) == 0
    assert seen["refresh"] is True
    assert seen["intake"]["news"] == ARTICLES and seen["intake"]["news_full"] == DEEPDIVE
    assert seen["intake"]["news_search"] == SEARCH and seen["intake"]["as_of"] == AS_OF
    call, = fake_build.calls
    assert call["assumption_plan"] == FRESH_PLAN and call["spec_sha"] == "new-spec"
    trace = outputs.load(outputs.TRACE, out, "AAAA")
    fa = trace["forecast_assumptions"]
    # The fake report normalized the plan differently: the trace keeps both.
    assert fa["agent_plan_raw"] == FRESH_PLAN and fa["plan"] == NORMALIZED_PLAN
    assert fa["fingerprint"] == "f1"
    manifest = outputs.load(outputs.MANIFEST, out, "AAAA")
    assert manifest["rebuild"]["refreshed_assumptions"] is True


def test_refresh_assumptions_needs_named_tickers(tmp_path, fake_build):
    source, out = tmp_path / "src", tmp_path / "out"
    _stored_run(source)
    with pytest.raises(SystemExit):
        rebuild.main(["--from", str(source), "--out", str(out), "--refresh-assumptions"])
    assert fake_build.calls == []
