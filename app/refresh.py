"""Refresh every dated market input the reports read, in one command.

    python -m app.refresh --as-of 2026-09-24 AMMN BBCA BBRI
    python -m app.refresh --as-of 2026-09-24 AMMN --only commodity peers

Each step needs the network and writes what the offline report build reads:

1. ``fx``: the USD/IDR close (app.fx, app database).
2. ``rates``: the US Treasury 10-year yield series, the risk-free rate of a
   model built in US$ (app.rates, app database).
3. ``commodity``: the copper and gold series (app.commodity, app database).
4. ``quotes``: each ticker's closing prices (app.market_quote, written to
   ``data/market_quotes/<T>.json`` for review in git).
5. ``peers``: peer snapshots from Yahoo Finance (app.peer_fundamentals, app
   database): the curated group when the ticker has one, else every peer in
   its Sectors peer table.

A step that fails is reported and the others still run; a report built on a
stale input says so (a stale copper series rules out SOTP/LoM, a curated
group without data falls back to the Sectors table).
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable

STEPS = ("fx", "rates", "commodity", "quotes", "peers")


def peer_symbols(tickers) -> tuple[list[str], dict]:
    """Symbols to snapshot for these issuers and the Yahoo ticker of curated peers."""
    from . import peer_fundamentals, peer_groups
    symbols, yahoo = [], {}
    for ticker in tickers:
        group = peer_groups.load(ticker)
        if group:
            for peer in group["peers"]:
                symbol = str(peer["symbol"]).upper()
                yahoo[symbol] = peer.get("yahoo") or f"{symbol}.JK"
                if symbol not in symbols:
                    symbols.append(symbol)
        if not group or len(group["peers"]) < peer_groups.MIN_PEERS:
            # Too few IDX comparables: the report reads the Sectors table instead.
            symbols.extend(s for s in peer_fundamentals.peers_of(ticker) if s not in symbols)
    return symbols, yahoo


def _fx(_tickers, _as_of):
    from . import fx
    quote = fx.refresh_usd_idr()
    return {"stored": {"USD/IDR": f"{quote['rate']:,.0f} ({quote['date']})"}, "failed": {}}


def _rates(_tickers, _as_of):
    from . import rates
    result = rates.refresh()
    return {"stored": {name: (f"{data['rows'][-1]['yield_pct']:.3f}% "
                              f"({data['rows'][-1]['date']})")
                       for name, data in result["stored"].items()},
            "failed": result["failed"]}


def _commodity(_tickers, _as_of):
    from . import commodity
    result = commodity.refresh()
    return {"stored": {name: f"{len(data['rows'])} closes to {data['rows'][-1]['date']}"
                       for name, data in result["stored"].items()},
            "failed": result["failed"]}


def _quotes(tickers, as_of):
    from . import market_quote
    stored, failed = {}, {}
    for ticker in tickers:
        try:
            row = market_quote.fetch_close(ticker, as_of)
            market_quote.write(row)
            stored[row["ticker"]] = f"Rp{row['price']:,} ({row['date']})"
        except Exception as error:  # one ticker must not stop the others
            failed[ticker] = f"{type(error).__name__}: {error}"
    return {"stored": stored, "failed": failed}


def _peers(tickers, _as_of):
    from . import peer_fundamentals
    symbols, yahoo = peer_symbols(tickers)
    if not symbols:
        return {"stored": {}, "failed": {}}
    result = peer_fundamentals.refresh(symbols, yahoo=yahoo)
    return {"stored": {s: d.get("period_label") or str(d.get("fiscal_year"))
                       for s, d in result["stored"].items()},
            "failed": result["failed"]}


RUNNERS: dict[str, Callable] = {"fx": _fx, "rates": _rates, "commodity": _commodity,
                                "quotes": _quotes, "peers": _peers}


def run(tickers, as_of, steps=STEPS, runners=None, log=print) -> dict:
    """Run the refresh steps in order; {step: {"stored": {...}, "failed": {...}}}."""
    runners = runners or RUNNERS
    tickers = [t.strip().upper() for t in tickers]
    results = {}
    for step in steps:
        try:
            result = runners[step](tickers, as_of)
        except Exception as error:  # a failed step leaves the stored data as it was
            result = {"stored": {}, "failed": {step: f"{type(error).__name__}: {error}"}}
        results[step] = result
        log(f"{step}: {len(result['stored'])} stored, {len(result['failed'])} failed")
        for name, why in result["failed"].items():
            log(f"  {name}: FAILED {why}")
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the dated market inputs of the reports")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--as-of", required=True, help="Report Date (YYYY-MM-DD)")
    parser.add_argument("--only", nargs="+", choices=STEPS, help="run only these steps")
    args = parser.parse_args(argv)
    results = run(args.tickers, args.as_of, steps=args.only or STEPS)
    failed_steps = [s for s, r in results.items() if r["failed"] and not r["stored"]]
    return 1 if failed_steps else 0


if __name__ == "__main__":
    sys.exit(main())
