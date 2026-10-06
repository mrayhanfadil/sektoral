"""Run the end-to-end research pipeline for several tickers in parallel.

Each ticker is its own ``app.research`` process (separate interpreter,
LLM/Tavily clients and log file); shared caches live in the app database,
whose writes are atomic, so two runs never share half-written state. Keep --jobs small: every
ticker already runs two LLM subagents at once, so --jobs 2 means about four
concurrent LLM calls.

    python -m app.batch JPFA GMFI INET --jobs 2 --out out/batch --pdf
    python -m app.batch JPFA GMFI --as-of 2026-09-24 --refresh-data   # refresh inputs first

``--refresh-data`` runs ``app.refresh`` for these tickers before the research
runs (FX, copper and gold, closing prices, peer snapshots); a failed step is
reported and the runs use the data already stored.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import outputs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _command(ticker, args):
    cmd = [sys.executable, "-m", "app.research", ticker, "--out", str(args.out),
           "--as-of", args.as_of]
    if args.pdf:
        cmd.append("--pdf")
    if args.refresh_assumptions:
        cmd.append("--refresh-assumptions")
    if args.method and args.method != "auto":
        cmd += ["--method", args.method]
    return cmd


def summarize(ticker, out):
    """One result row from the ticker's stored report document."""
    doc = outputs.load(outputs.REPORT, out, ticker)
    if not isinstance(doc, dict):
        return {"ticker": ticker, "status": "no report"}
    meta = doc.get("meta") or {}
    return {"ticker": ticker, "status": meta.get("status"), "rating": meta.get("rating"),
            "tp": meta.get("tp"), "upside_pct": meta.get("upside_persen"),
            "method": doc.get("method"),
            "blockers": (doc.get("harness") or {}).get("blockers") or []}


def run_one(ticker, args):
    log = Path(args.out) / f"{ticker}.log"
    started = time.time()
    with log.open("w", encoding="utf-8") as stream:
        try:
            code = subprocess.run(_command(ticker, args), cwd=ROOT, stdout=stream,
                                  stderr=subprocess.STDOUT, timeout=args.timeout).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    row = summarize(ticker, args.out)
    row.update(exit=code, minutes=round((time.time() - started) / 60, 1))
    return row


def main(argv=None):
    parser = argparse.ArgumentParser(description="Parallel Sectoral research runs")
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--out", default="out/batch")
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--refresh-assumptions", action="store_true")
    parser.add_argument("--method", default="auto")
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per ticker")
    parser.add_argument("--refresh-data", action="store_true",
                        help="refresh FX, commodity, closing-price and peer data first")
    args = parser.parse_args(argv)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    if args.refresh_data:
        from app import refresh
        refresh.run(args.tickers, args.as_of, log=lambda line: print(f"refresh {line}",
                                                                     flush=True))
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(run_one, t.upper(), args): t for t in args.tickers}
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"done {row['ticker']} exit={row['exit']} {row['minutes']}m "
                  f"{row.get('status')} {row.get('rating') or ''} "
                  f"{row.get('tp') or ''} blockers={len(row.get('blockers') or [])}", flush=True)
    order = {t.upper(): i for i, t in enumerate(args.tickers)}
    rows.sort(key=lambda r: order[r["ticker"]])
    outputs.save(outputs.BATCH, args.out, "", rows)
    return 0 if all(r["exit"] == 0 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
