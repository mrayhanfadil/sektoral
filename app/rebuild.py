"""Offline rebuild: re-render stored Company Updates from what their runs decided.

A research run (``app.research``) stores, per ticker, the report document and
the Audit Trace in the app database under its output folder (``app.outputs``).
The trace holds every input the report builder took from an agent or the
network: the Forecast Plan (``forecast_assumptions``), the dated news register
(``news_sources``), the full-text deep-dive (``news_deepdive``) and the Report
Date (``report.as_of``). This command feeds those stored inputs back into
``build.build`` exactly as ``research._run`` does, without calling an agent,
Tavily or any other network service, and writes a complete run folder that the
Report Gallery and the web app can point at::

    python -m app.rebuild --from out/demo-reports --out out/rebuild [--pdf] [TICKERS...]
    python -m app.rebuild --from out/rebuild --out out/rebuild-2 --changes INET

``--refresh-assumptions`` (explicit tickers only) is the one exception to
"no agent": it re-runs the Forecast Assumption Agent (the paid LLM) on the
evidence the trace stored, the dated news register and deep-dive plus the
official release and Sectors history the intake reads, with ``refresh=True``,
and rebuilds on the new Forecast Plan; the rebuilt trace stores that plan.
Use it after the agent's roles or plan schema change (for example the Bank
Driver Scenario), never to re-roll a plan whose evidence did not change::

    python -m app.rebuild --from out/demo-reports --out out/bank-drivers \
        --refresh-assumptions --pdf BBCA BBRI

``--translate-assumptions`` (explicit tickers only) is the other paid
exception: it keeps the Forecast Plan the trace stored (the plan the builder
reads) and only asks the model for the English twins of its prose
(``agents.forecast_assumptions.run.translate_plan``), then rebuilds on the
translated plan; the rebuilt trace stores it with its twins and the
translation notes (``forecast_assumptions.translation``). No Indonesian value
of the plan changes, so status, rating, Target Price and every Indonesian
figure are those of a plain rebuild; only the English edition gains the
agent's prose. Use it for reports whose plan predates the translation step::

    python -m app.rebuild --from out/demo-reports --out out/english \
        --translate-assumptions BBRI

Use it after a change to presentation, peer groups or valuation code to
re-render every report reproducibly and see exactly what moved. It prints one
line per ticker: release status, rating and Target Price of the rebuilt report;
whether status, rating, Target Price or method changed against the source
report; how many Key Financials cells moved (``--changes`` lists them); which
dated market inputs were pinned; and the peer basis the report valued against
(a peer-pack change moves peer multiples and every method that reads them).
The exit status is non-zero when any ticker fails to rebuild.

Dated market inputs. Besides the trace, the builder reads snapshots that
``app.refresh`` overwrites in place: the USD/IDR quote, the UST 10Y yield
series (the risk-free rate of a model built in US$), the copper and gold
series and the peer fundamentals snapshots. A rebuild records the snapshots it
used in its run manifest (``market_inputs``) and, when the source manifest has
that block, pins the same values, so rebuilding a rebuilt folder reproduces it
exactly even after a data refresh. Runs stored before manifests recorded them
read today's snapshots; for a USD-reporting issuer the rebuild then recovers
the USD/IDR rate the source run used from the source report itself (the ratio
of its forecast revenue in rupiah to the rebuilt one), rebuilds once more with
that rate pinned and keeps the result only when it reproduces the source
revenue. ``--live-inputs`` turns all pinning off and values the report on
today's snapshots.

What goes into ``--out``, per ticker:

- ``{T}.html`` (and ``{T}.pdf`` with ``--pdf``) and the report document;
- the Audit Trace: the stored trace copied unchanged, except the fields that
  must follow the new report (``report`` status, rating, Target Price, method,
  dates; the run manifest and evidence register that ``build.build`` rebuilt
  from the same inputs) and ``{T}-trace.html`` rendered from it;
- the run manifest of the rebuilt report, with ``market_inputs`` and a
  ``rebuild`` block (source folder, source and current code revision, pins);
- the stored run events, copied; when the rebuilt report's Method Gate,
  Method Chain or release events differ, those events are replaced by the new
  ones so a Run Replay shows what this report decided.

Inputs the trace does not carry and the builder still reads from local data:
the Sectors Snapshot, issuer evidence, market-quote packs, curated peer groups,
analyst scenario packs, method and stage overrides and the rating history. A
change to any of them shows up as a move in the summary. ``--analyst-target``
repeats a run started with ``app.research --analyst-target`` (the trace does
not record that flag); a Method Override recorded in the source report's
release is passed on.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import os
import re
import socket
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import (assumption_review, build, commodity, exhibit_ids, fx, intake, outputs,
                 peer_fundamentals, progress, publication_archive, rates, render,
                 rnav, run_manifest)  # noqa: E402

# Trace ``report`` fields that research._run derives from the built report.
REPORT_FIELDS = ("status", "as_of", "market_price_date", "illustrative_scenarios",
                 "target_method", "target_price", "rating", "research_status")
# Relative tolerance for "the same number" between two builds.
SAME = 1e-9


class OfflineError(OSError):
    """Raised when rebuild code tries to open a network connection."""


@contextlib.contextmanager
def offline():
    """No network while the report is rebuilt.

    ``SEKTORAL_OFFLINE`` makes the news deep-dive answer from its store only
    (it would otherwise fetch article text again); the socket guard is a
    backstop for any other path.
    """
    def refuse(*_args, **_kwargs):
        raise OfflineError("app.rebuild runs offline; a network connection was attempted")

    previous = os.environ.get("SEKTORAL_OFFLINE")
    os.environ["SEKTORAL_OFFLINE"] = "1"
    connect, create = socket.socket.connect, socket.create_connection
    socket.socket.connect = refuse
    socket.create_connection = refuse
    try:
        yield
    finally:
        socket.socket.connect, socket.create_connection = connect, create
        if previous is None:
            os.environ.pop("SEKTORAL_OFFLINE", None)
        else:
            os.environ["SEKTORAL_OFFLINE"] = previous


@contextlib.contextmanager
def market_inputs(pins: dict | None, used: dict, seen: dict):
    """Serve pinned snapshots and record every snapshot the build reads.

    ``pins`` has the shape of a manifest's ``market_inputs``: ``fx`` (the
    USD/IDR quote), ``commodities`` {name: series}, ``peer_snapshots``
    {symbol: snapshot} and ``rates`` {name: series} (UST 10Y); a key that is
    present is served as stored (None included), a missing key falls through
    to the app database. ``used`` receives the same shape for what was
    actually read (``rates`` only once a build reads it), and ``seen`` the
    issuer facts of the loaded intake (peer basis, reporting currency).
    """
    pins = pins if isinstance(pins, dict) else {}
    fx_pinned = "fx" in pins
    commodity_pins = pins.get("commodities") if isinstance(pins.get("commodities"), dict) else {}
    peer_pins = pins.get("peer_snapshots") if isinstance(pins.get("peer_snapshots"), dict) else {}
    rate_pins = pins.get("rates") if isinstance(pins.get("rates"), dict) else {}
    used.update(fx=None, commodities={}, peer_snapshots={})
    originals = (fx.load_cached_rate, commodity.load, peer_fundamentals.load, intake.load,
                 rates.load, rnav._FX_QUOTE, rnav.FX_USDIDR, rnav.FX_BASIS)
    load_fx, load_series, load_peer, load_intake, load_rate = originals[:5]

    def fx_rate(db=None):
        quote = copy.deepcopy(pins["fx"]) if fx_pinned else load_fx(db)
        used["fx"] = copy.deepcopy(quote)
        return quote

    def series(name, db=None):
        data = copy.deepcopy(commodity_pins[name]) if name in commodity_pins else load_series(name, db)
        used["commodities"][name] = copy.deepcopy(data)
        return data

    def rate_series(name=rates.UST10Y, db=None):
        data = copy.deepcopy(rate_pins[name]) if name in rate_pins else load_rate(name, db)
        used.setdefault("rates", {})[name] = copy.deepcopy(data)
        return data

    def peer(symbol, db=None):
        key = str(symbol).replace(".JK", "").strip().upper()
        data = copy.deepcopy(peer_pins[key]) if key in peer_pins else load_peer(symbol, db)
        used["peer_snapshots"][key] = copy.deepcopy(data)
        return data

    def issuer(ticker, as_of=None):
        loaded = load_intake(ticker, as_of=as_of)
        doc_in = loaded[0] if isinstance(loaded, tuple) and loaded else {}
        if isinstance(doc_in, dict):
            official = doc_in.get("official_evidence") or {}
            seen.update(peer_basis=doc_in.get("peer_basis"),
                        reporting_currency=str(official.get("reporting_currency") or "IDR").upper(),
                        fx_spot=doc_in.get("fx_spot"))
        return loaded

    fx.load_cached_rate, commodity.load, peer_fundamentals.load, intake.load, rates.load = (
        fx_rate, series, peer, issuer, rate_series)
    if fx_pinned:
        # rnav reads the quote once at import; pin its copy too.
        quote = pins["fx"]
        rnav._FX_QUOTE = quote
        rnav.FX_USDIDR = float(quote["rate"]) if quote else 16000.0
        rnav.FX_BASIS = (f"Yahoo Finance IDR=X ({quote['date']})" if quote else
                         "asumsi analis Rp16.000/USD (rate belum di-refresh; tanpa silent "
                         "network fallback)")
    try:
        yield
    finally:
        (fx.load_cached_rate, commodity.load, peer_fundamentals.load, intake.load,
         rates.load, rnav._FX_QUOTE, rnav.FX_USDIDR, rnav.FX_BASIS) = originals


def assumption_status(forecast_assumptions: dict) -> str | None:
    """The status research._run passes to build.build for this agent result."""
    fa = forecast_assumptions if isinstance(forecast_assumptions, dict) else {}
    return next((fa[key] for key in ("earnings_status", "interim_status")
                 if fa.get(key) not in (None, "not_run")), fa.get("status"))


def build_inputs(trace: dict, source_doc: dict | None = None,
                 analyst_target: bool = False) -> dict:
    """Keyword arguments for build.build, taken from a stored Audit Trace.

    Mirrors research._run. The Forecast Plan is the agent's own plan: when the
    report normalized it, research._run stored the agent's version as
    ``agent_plan_raw`` and the normalized one as ``plan``; the builder was
    given the agent's version. ``report.analyst_target`` and
    ``report.method_override`` are read when the trace records them.
    """
    if not isinstance(trace, dict):
        raise ValueError("no stored audit trace")
    fa = trace.get("forecast_assumptions")
    if not isinstance(fa, dict):
        raise ValueError("trace has no forecast_assumptions")
    plan = fa["agent_plan_raw"] if "agent_plan_raw" in fa else fa.get("plan")
    news = trace.get("news_sources") if isinstance(trace.get("news_sources"), dict) else {}
    report = trace.get("report") if isinstance(trace.get("report"), dict) else {}
    meta = (source_doc or {}).get("meta") or {}
    as_of = report.get("as_of") or meta.get("tanggal")
    if not as_of:
        raise ValueError("trace has no report date (report.as_of)")
    release = ((source_doc or {}).get("log_gate") or {}).get("release") or {}
    override = report.get("method_override") or ((release.get("override") or {}).get("method")
                                                if isinstance(release.get("override"), dict) else None)
    # Runs that record the flag in the trace need no --analyst-target.
    analyst_target = bool(analyst_target or report.get("analyst_target"))
    illustrative = bool(report.get("illustrative_scenarios") or meta.get("illustrative_scenarios"))
    return {
        "as_of": str(as_of)[:10],
        "illustrative_scenarios": illustrative or analyst_target,
        "assumption_plan": copy.deepcopy(plan),
        "news_evidence": {"rows": copy.deepcopy(list(news.get("articles") or [])),
                          "full": copy.deepcopy(list(trace.get("news_deepdive") or [])),
                          "search": copy.deepcopy(dict(news.get("search") or {}))},
        "analyst_target": analyst_target,
        "method_override": override,
        "spec_sha": fa.get("spec_sha256"),
        "assumption_status": assumption_status(fa),
    }


def refreshed_assumptions(trace: dict, as_of: str) -> dict:
    """A fresh Forecast Assumption Agent result on the trace's stored evidence.

    Mirrors research._run: the intake of the Report Date carries the stored
    news register (``news_sources``) and deep-dive (``news_deepdive``); the
    agent runs with ``refresh=True`` so the stored plan is replaced. This
    calls the LLM; it runs outside the offline guard.
    """
    from agents.forecast_assumptions.run import run_cached
    forecast_intake, _ = intake.load(trace["ticker"], as_of=as_of)
    news = trace.get("news_sources") if isinstance(trace.get("news_sources"), dict) else {}
    forecast_intake["news"] = copy.deepcopy(list(news.get("articles") or []))
    forecast_intake["news_full"] = copy.deepcopy(list(trace.get("news_deepdive") or []))
    forecast_intake["news_search"] = copy.deepcopy(dict(news.get("search") or {}))
    return run_cached(forecast_intake, refresh=True)


def translated_assumptions(plan):
    """The stored Forecast Plan with the English twins of its prose, and the
    translation notes (``translate_plan``). This calls the LLM; it runs
    outside the offline guard. The interim rule that reads the official
    release is not applied: the trace does not store that release."""
    from agents.forecast_assumptions.run import translate_plan
    return translate_plan(plan)


def report_fields(doc: dict) -> dict:
    """The trace ``report`` block research._run writes for this report."""
    meta = doc.get("meta") or {}
    return {"status": meta.get("status"), "as_of": meta.get("tanggal"),
            "market_price_date": meta.get("harga_tanggal"),
            "illustrative_scenarios": bool(meta.get("illustrative_scenarios")),
            "target_method": doc.get("method"), "target_price": meta.get("tp"),
            "rating": meta.get("rating"), "research_status": meta.get("research_status")}


def rebuilt_trace(stored: dict, doc: dict) -> dict:
    """The stored trace with only the fields that follow the new report updated."""
    trace = copy.deepcopy(stored)
    report = trace.get("report") if isinstance(trace.get("report"), dict) else {}
    fresh = report_fields(doc)
    report.update({key: fresh[key] for key in REPORT_FIELDS})
    trace["report"] = report
    if doc.get("run_manifest") is not None:
        trace["run_manifest"] = doc["run_manifest"]
    if doc.get("evidence_register") is not None:
        trace["evidence_register"] = doc["evidence_register"]
    for key in ("earnings_quality", "terminal_economics"):
        if doc.get(key) is not None:
            trace[key] = doc[key]
    if "product_sales_scenario" in trace:
        trace["product_sales_scenario"] = (doc.get("forecast_assumptions") or {}).get(
            "product_sales_scenario")
    return trace


def _valuation_event(event: dict) -> bool:
    return isinstance(event, dict) and (event.get("stage") == "gate" or event.get("tool") == "release")


def _content(events):
    return [{k: v for k, v in e.items() if k != "t"} for e in events]


def merged_events(stored, fresh) -> list:
    """Stored run events, with the valuation events replaced when they changed.

    ``fresh`` are the events build.build emitted for the rebuilt report
    (run_events.emit_valuation); they take the place (and timing) of the
    stored Method Gate, Method Chain and release events.
    """
    stored = [e for e in stored if isinstance(e, dict)] if isinstance(stored, list) else []
    fresh = [e for e in fresh or [] if _valuation_event(e)]
    span = [i for i, e in enumerate(stored) if _valuation_event(e)]
    if not stored or not span or not fresh:
        return stored
    old = stored[span[0]:span[-1] + 1]
    if _content(old) == _content(fresh):
        return stored
    start = old[0].get("t") or 0.0
    step = ((old[-1].get("t") or start) - start) / max(1, len(fresh) - 1)
    retimed = [{**event, "t": round(start + i * step, 1)} for i, event in enumerate(fresh)]
    return stored[:span[0]] + retimed + stored[span[-1] + 1:]


PEER_TABLE = "Perbandingan peer "
_NOT_A_PEER = ("(emiten)", "Median", "Rata-rata", "Peringkat")


def peer_set(doc: dict) -> tuple[str, list[str]]:
    """(peer group name, peer tickers) from the report's peer comparison table."""
    exhibit = _exhibit(doc, PEER_TABLE) or {}
    rows = (exhibit.get("data") or {}).get("rows") or []
    tickers = sorted(str(r[0]).strip() for r in rows if isinstance(r, list) and r
                     and not any(mark in str(r[0]) for mark in _NOT_A_PEER))
    return str(exhibit.get("judul") or "")[len(PEER_TABLE):].strip(), tickers


def peer_kind(basis) -> str:
    """Short label of an intake ``peer_basis``: curated pack or Sectors table."""
    text = str(basis or "")
    if text.startswith("grup peer kurasi"):
        missing = re.search(r"tanpa data: (.+)$", text)
        return "kurasi" + (f" (tanpa data: {missing.group(1)})" if missing else "")
    found = re.search(r"tabel peer Sectors milik (\w+)", text)
    return f"Sectors milik {found.group(1)}" if found else "Sectors"


def _exhibit(doc: dict, title: str) -> dict | None:
    """The first exhibit whose stored (Indonesian) title starts with `title`."""
    return next((e for e in doc.get("exhibits") or [] if isinstance(e, dict)
                 and str(e.get("judul") or "").startswith(title)), None)


def _key_financials(doc: dict) -> dict:
    data = (exhibit_ids.find(doc.get("exhibits"), exhibit_ids.KEY_FINANCIALS) or {}).get("data") or {}
    cols = [str(c) for c in data.get("cols") or []]
    out = {}
    for row in data.get("rows") or []:
        if isinstance(row, list) and row:
            for col, cell in zip(cols[1:], row[1:]):
                out[(str(row[0]), col)] = str(cell)
    return out


def key_financials_changes(source: dict, rebuilt: dict) -> list[tuple[str, str, str, str]]:
    """(row, column, source value, rebuilt value) for every Key Financials cell that moved."""
    before, after = _key_financials(source), _key_financials(rebuilt)
    return [(row, col, before.get((row, col), "∅"), after.get((row, col), "∅"))
            for row, col in sorted(set(before) | set(after))
            if before.get((row, col)) != after.get((row, col))]


def forecast_revenue(doc: dict) -> dict:
    """{category: rupiah revenue} for the forecast years of the revenue chart."""
    chart = next((e for e in doc.get("exhibits") or [] if isinstance(e, dict)
                  and e.get("tipe") in ("combo_panel", "combo_chart")
                  and exhibit_ids.is_exhibit(e, exhibit_ids.REVENUE_PANEL)), None)
    data = (chart or {}).get("data") or {}
    cols = data.get("cols") or []
    for series in data.get("series") or []:
        bars, flags = series.get("bars") or [], series.get("is_forecast") or []
        return {str(c): v for c, v, f in zip(cols, bars, flags)
                if f and isinstance(v, (int, float)) and not isinstance(v, bool) and v}
    return {}


def implied_fx(source: dict, rebuilt: dict, rate: float | None) -> float | None:
    """The USD/IDR rate the source report converted its forecast with.

    For a USD reporter the forecast is modelled in USD and converted at one
    rate, so the first forecast year's rupiah revenue scales with the rate:
    source rate = rebuilt rate x source revenue / rebuilt revenue. None when
    the first forecast year is missing or already equal.
    """
    before, after = forecast_revenue(source), forecast_revenue(rebuilt)
    first = next((c for c in after if c in before), None)
    if not rate or first is None:
        return None
    ratio = before[first] / after[first]
    return rate * ratio if abs(ratio - 1) > SAME else None


def _same_revenue(source: dict, rebuilt: dict) -> bool:
    before, after = forecast_revenue(source), forecast_revenue(rebuilt)
    first = next((c for c in after if c in before), None)
    return first is not None and abs(before[first] / after[first] - 1) <= SAME


def compare(source: dict, rebuilt: dict) -> dict:
    """What moved between the source report and its rebuild."""
    before, after = source.get("meta") or {}, rebuilt.get("meta") or {}
    return {"status": after.get("status"), "rating": after.get("rating"), "tp": after.get("tp"),
            "method": str(rebuilt.get("method") or "").split(" [")[0],
            "source_status": before.get("status"), "source_rating": before.get("rating"),
            "source_tp": before.get("tp"),
            "status_changed": before.get("status") != after.get("status"),
            "rating_changed": before.get("rating") != after.get("rating"),
            "tp_changed": before.get("tp") != after.get("tp"),
            "method_changed": rebuilt.get("method") != source.get("method"),
            "key_financials_changes": key_financials_changes(source, rebuilt),
            "peers": peer_set(rebuilt), "source_peers": peer_set(source)}


def _build_once(t, out, kwargs, pins):
    """One offline build; (doc, valuation events, builder output, inputs used, intake facts)."""
    used, seen, captured = {}, {}, io.StringIO()
    with offline(), market_inputs(pins, used, seen), progress.recording() as events, \
            contextlib.redirect_stdout(captured):
        doc = build.build(t, out, want_pdf=False, **copy.deepcopy(kwargs))
    return doc, list(events), captured.getvalue(), used, seen


def rebuild_one(ticker: str, source, out, *, want_pdf: bool = False,
                analyst_target: bool = False, live_inputs: bool = False,
                refresh_assumptions: bool = False, translate_assumptions: bool = False,
                db=None, log=None,
                plan_override: dict | None = None, trace_extra: dict | None = None,
                as_of: str | None = None) -> dict:
    """Rebuild one ticker from ``source`` into ``out``; returns the comparison.

    ``refresh_assumptions`` re-runs the Forecast Assumption Agent on the stored
    evidence first (see ``refreshed_assumptions``) and stores its new plan.
    ``translate_assumptions`` adds the English twins to the stored plan
    (``translated_assumptions``) and stores the translated plan.
    ``plan_override`` builds on a reviewed plan instead (app.assumption_review:
    the analyst's edits); the trace stores it as the plan, keeps the agent's
    as ``agent_plan_before_review`` and takes ``trace_extra`` keys as given.
    """
    t = str(ticker).strip().upper()
    source, out = Path(source), Path(out)
    stored_trace = outputs.load(outputs.TRACE, source, t, db)
    source_doc = outputs.load(outputs.REPORT, source, t, db)
    if not isinstance(stored_trace, dict):
        raise ValueError(f"{t}: no stored audit trace in {source}")
    if not isinstance(source_doc, dict):
        raise ValueError(f"{t}: no stored report in {source}")
    source_manifest = outputs.load(outputs.MANIFEST, source, t, db) or \
        stored_trace.get("run_manifest") or {}
    kwargs = build_inputs(stored_trace, source_doc, analyst_target=analyst_target)
    if as_of:
        # A later Report Date on the same stored evidence: the evidence cutoff,
        # price and policy vintages are re-checked against it; nothing newer
        # than the pinned snapshot is fetched.
        if str(as_of)[:10] < str(kwargs.get("as_of") or "")[:10]:
            raise ValueError(f"{t}: --as-of {as_of} precedes the source Report Date "
                             f"{kwargs.get('as_of')}")
        kwargs["as_of"] = str(as_of)[:10]
    fresh_plan = None
    if refresh_assumptions:
        fresh_plan = refreshed_assumptions(dict(stored_trace, ticker=t), kwargs["as_of"])
        if not fresh_plan.get("plan"):
            raise ValueError(f"{t}: forecast agent returned no plan ({fresh_plan.get('status')}: "
                             + "; ".join(str(p) for p in (fresh_plan.get("problems") or [])[:3])
                             + ")")
        kwargs.update(assumption_plan=copy.deepcopy(fresh_plan["plan"]),
                      assumption_status=assumption_status(fresh_plan),
                      spec_sha=fresh_plan.get("spec_sha256"))
    translation = translated_plan = None
    if translate_assumptions and isinstance(kwargs.get("assumption_plan"), dict):
        translated_plan, translation = translated_assumptions(kwargs["assumption_plan"])
        kwargs["assumption_plan"] = copy.deepcopy(translated_plan)
    if plan_override is not None:
        kwargs["assumption_plan"] = copy.deepcopy(plan_override)
    recorded = source_manifest.get("market_inputs") if isinstance(
        source_manifest.get("market_inputs"), dict) else None
    pins = None if live_inputs else copy.deepcopy(recorded)
    pinned = [] if pins is None else ["snapshot pasar dari manifest sumber"]
    out.mkdir(parents=True, exist_ok=True)
    # Rebuild may target an existing reports folder. Archive the old approved
    # bundle before its report, HTML, trace or manifest can be replaced.
    review = assumption_review.status(out, t, db)
    if (review.get("state") == "approved" and
            all(kind in (review.get("artifact_hashes") or {})
                for kind in assumption_review.REQUIRED_PUBLISH_ARTIFACTS)):
        archived = publication_archive.archive_approved_bundle(out, t, db=db)
        if archived is None:
            raise OSError(f"refusing to rebuild approved {t}: publication archive failed")
    # The rebuild writes a fresh trace and only writes a PDF when requested.
    # Clear old rendered files now so a failed/HTML-only rebuild cannot leave
    # artifacts from the previous publication attached to the new manifest.
    (out / f"{t}.pdf").unlink(missing_ok=True)
    (out / f"{t}-trace.html").unlink(missing_ok=True)
    (out / f"{t}.en.html").unlink(missing_ok=True)
    (out / f"{t}.en.pdf").unlink(missing_ok=True)
    doc, events, text, used, seen = _build_once(t, out, kwargs, pins)
    last_built = doc
    if log:
        log(text)
    if pins is None and not live_inputs and seen.get("reporting_currency") == "USD":
        rate = (used.get("fx") or {}).get("rate")
        inferred = implied_fx(source_doc, doc, rate)
        if inferred:
            quote = {**(used.get("fx") or {}), "rate": inferred,
                     "note": "tersirat dari report sumber (app.rebuild)"}
            second = _build_once(t, out, kwargs, {"fx": quote})
            last_built = second[0]
            if log:
                log(second[2])
            if _same_revenue(source_doc, second[0]):
                doc, events, text, used, seen = second
                pinned = [f"kurs Rp{_num(inferred, 1)}/USD tersirat dari report sumber "
                          f"(snapshot kini Rp{_num(rate, 1)})"]
    manifest = doc.get("run_manifest") if isinstance(doc.get("run_manifest"), dict) else {}
    manifest["market_inputs"] = used
    manifest["rebuild"] = {
        "from": str(source.resolve()),
        "source_code_revision": source_manifest.get("code_revision"),
        "code_revision": run_manifest.git_revision(),
        "rebuilt_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pinned": pinned, "live_inputs": live_inputs,
        "analyst_target": kwargs["analyst_target"], "method_override": kwargs["method_override"],
        "refreshed_assumptions": bool(refresh_assumptions),
        "translated_assumptions": bool(translate_assumptions),
        "as_of_override": as_of,
    }
    doc["run_manifest"] = manifest
    outputs.save(outputs.REPORT, out, t, doc, db)
    if doc is not last_built:  # build.build wrote the HTML of the rejected second pass
        (out / f"{t}.html").write_text(render.render(doc))
        build.render_english(doc, out, t)
    trace = rebuilt_trace(stored_trace, doc)
    if fresh_plan is not None:
        # The trace records the plan this report was built on, as research._run does.
        normalized = (doc.get("forecast_assumptions") or {}).get("plan")
        if isinstance(normalized, dict) and normalized != fresh_plan["plan"]:
            fresh_plan["agent_plan_raw"] = fresh_plan["plan"]
            fresh_plan["plan"] = normalized
            fresh_plan["plan_normalized_for_report"] = True
        trace["forecast_assumptions"] = fresh_plan
    if translation is not None:
        # The trace records the translated plan, as research._run records a plan.
        fa = dict(trace.get("forecast_assumptions") or {})
        if translation["status"] != "failed":
            fa.pop("agent_plan_raw", None)
            fa.pop("plan_normalized_for_report", None)
            fa["plan"] = translated_plan
            normalized = (doc.get("forecast_assumptions") or {}).get("plan")
            if isinstance(normalized, dict) and normalized != translated_plan:
                fa["agent_plan_raw"] = translated_plan
                fa["plan"] = normalized
                fa["plan_normalized_for_report"] = True
        fa["translation"] = translation
        trace["forecast_assumptions"] = fa
    if plan_override is not None:
        fa = dict(trace.get("forecast_assumptions") or {})
        before = fa.get("agent_plan_raw") if "agent_plan_raw" in fa else fa.get("plan")
        fa.setdefault("agent_plan_before_review", before)
        fa["plan"] = (doc.get("forecast_assumptions") or {}).get("plan") or plan_override
        fa["agent_plan_raw"] = copy.deepcopy(plan_override)
        trace["forecast_assumptions"] = fa
    trace.update(copy.deepcopy(trace_extra or {}))
    outputs.save(outputs.TRACE, out, t, trace, db)
    stored_events = outputs.load(outputs.EVENTS, source, t, db)
    if isinstance(stored_events, list) and stored_events:
        outputs.save(outputs.EVENTS, out, t, merged_events(stored_events, events), db)
    from . import research  # the trace view; importing it opens no connection
    (out / f"{t}-trace.html").write_text(research._trace_html(
        t, trace.get("research") or {}, f"{t}.html", trace.get("forecast_assumptions"),
        trace.get("news_deepdive"), analyst=trace.get("analyst"),
        news_sources=trace.get("news_sources"), report=trace.get("report")), encoding="utf-8")
    pdf_path = None
    if want_pdf:
        if build.pdf_mod is None:
            raise RuntimeError("PDF requested but Playwright is not available")
        pdf_path = str(build.print_pdfs(t, out))
    publication_manifest = run_manifest.finalize_manifest(manifest, out, t)
    trace["run_manifest"] = publication_manifest
    outputs.save(outputs.TRACE, out, t, trace, db)
    outputs.save(outputs.MANIFEST, out, t, publication_manifest, db)
    from . import forecast_ledger
    forecast_ledger.freeze_if_auto_published(out, t, db)
    result = {"ticker": t, **compare(source_doc, doc), "pinned": pinned,
              "intake_peer_basis": seen.get("peer_basis"), "pdf": pdf_path}
    if translation is not None:
        result["translation"] = translation
    return result


def _num(value, digits=0) -> str:
    """Indonesian number format: 17.893,0."""
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _tp(value) -> str:
    return f"Rp{_num(value)}" if isinstance(value, (int, float)) else "-"


def line(result: dict) -> str:
    """One summary line per ticker."""
    if result.get("error"):
        return f"{result['ticker']:<5} GAGAL  {result['error']}"
    status = str(result.get("status") or "-")
    moved = [label for key, label in (("status_changed", "status"), ("rating_changed", "rating"),
                                      ("tp_changed", "TP"), ("method_changed", "metode"))
             if result.get(key)]
    was = (f" (sumber: {result.get('source_rating') or '-'} {_tp(result.get('source_tp'))}"
           + (f", {result.get('source_status')}" if result.get("status_changed") else "") + ")")
    kf = len(result.get("key_financials_changes") or [])
    group, tickers = result.get("peers") or ("", [])
    source_group, source_tickers = result.get("source_peers") or ("", [])
    peers = (f"{peer_kind(result.get('intake_peer_basis'))} '{group or '-'}' "
             f"{len(tickers)} peer")
    added = sorted(set(tickers) - set(source_tickers))
    dropped = sorted(set(source_tickers) - set(tickers))
    if group != source_group:
        peers += f" (grup sumber '{source_group or '-'}')"
    if added or dropped:
        peers += " (" + " ".join([f"+{t}" for t in added] + [f"-{t}" for t in dropped]) + ")"
    pinned = "; ".join(result.get("pinned") or []) or "snapshot kini"
    translation = result.get("translation")
    translated = (f" | terjemahan: {translation.get('status')} "
                  f"{translation.get('attached', 0)}/{translation.get('fields', 0)} teks"
                  if isinstance(translation, dict) else "")
    return (f"{result['ticker']:<5} {status:<30} {str(result.get('rating') or '-'):<6} "
            f"TP {_tp(result.get('tp')):<9} "
            + ("BERUBAH: " + ", ".join(moved) + was if moved else "rating/TP sama")
            + f" | Key Financials: {'sama' if not kf else f'{kf} sel berubah'}"
            + f" | input: {pinned} | peer: {peers}" + translated)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Rebuild stored company updates offline from their audit traces")
    parser.add_argument("--from", dest="source", required=True,
                        help="run folder whose stored reports and traces are rebuilt")
    parser.add_argument("--out", required=True, help="folder for the rebuilt run")
    parser.add_argument("--pdf", action="store_true", help="also print each report to PDF")
    parser.add_argument("--analyst-target", action="store_true",
                        help="the source run used app.research --analyst-target")
    parser.add_argument("--live-inputs", action="store_true",
                        help="value on today's FX, commodity and peer snapshots (no pinning)")
    parser.add_argument("--changes", action="store_true",
                        help="list every Key Financials cell that moved")
    parser.add_argument("--verbose", action="store_true", help="show the builder's own output")
    parser.add_argument("--refresh-assumptions", action="store_true",
                        help="re-run the forecast assumption agent (paid LLM) on the stored "
                             "evidence of the named tickers before rebuilding")
    parser.add_argument("--translate-assumptions", action="store_true",
                        help="translate the stored forecast plan's prose to English (paid "
                             "LLM) for the named tickers before rebuilding")
    parser.add_argument("--as-of", dest="as_of",
                        help="a later Report Date for the rebuild (same stored evidence)")
    parser.add_argument("tickers", nargs="*", help="default: every report in --from")
    args = parser.parse_args(argv)
    source, out = Path(args.source), Path(args.out)
    if source.resolve() == out.resolve():
        parser.error("--out must differ from --from; the source run is the reference")
    if args.refresh_assumptions and not args.tickers:
        parser.error("--refresh-assumptions calls the LLM; name the tickers to refresh")
    if args.translate_assumptions and not args.tickers:
        parser.error("--translate-assumptions calls the LLM; name the tickers to translate")
    if args.translate_assumptions and args.refresh_assumptions:
        parser.error("--refresh-assumptions already translates the new plan; "
                     "drop --translate-assumptions")
    tickers = [t.upper() for t in args.tickers] or outputs.tickers(outputs.REPORT, source)
    if not tickers:
        print(f"tidak ada report tersimpan di {source}", file=sys.stderr)
        return 1
    failed = 0
    for ticker in tickers:
        try:
            result = rebuild_one(ticker, source, out, want_pdf=args.pdf,
                                 analyst_target=args.analyst_target,
                                 live_inputs=args.live_inputs,
                                 refresh_assumptions=args.refresh_assumptions,
                                 translate_assumptions=args.translate_assumptions,
                                 as_of=args.as_of,
                                 log=(lambda text: print(text, end="")) if args.verbose else None)
        except Exception as error:  # report every ticker, then fail the command
            failed += 1
            result = {"ticker": ticker, "error": f"{type(error).__name__}: {str(error)[:300]}"}
            if args.verbose:
                traceback.print_exc()
        print(line(result), flush=True)
        if args.changes:
            for row, col, before, after in result.get("key_financials_changes") or []:
                print(f"      {row} {col}: {before} -> {after}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
