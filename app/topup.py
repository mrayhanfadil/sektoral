"""Top-up cache: tarik endpoint yang belum ada, simpan ke SQLite, catat kredit.

Default = --dry-run (daftar panggilan + estimasi kredit, TANPA network).
Jalankan dengan --live untuk benar-benar fetch (butuh SECTORS_API_KEY di env).

Paket:
  mining TICKER  — jawaban kritik #1: harga Cu/Au, performance, detail,
                   sites, sales-destination (+ discovery slug bila perlu)
  idx TICKER     — listing-performance, free-float (validasi rail)
  refresh EP     — refresh satu endpoint yang sudah ada (params JSON opsional)

Contoh:
  python3 -m app.topup mining AMMN
  python3 -m app.topup mining AMMN --live
  python3 -m app.topup idx AMMN --live
"""
import argparse
import json
import os
import sys
from pathlib import Path

from .sectors import Client, DEFAULT_DB

MINING_COMMODITIES = ["Copper", "Gold"]


def mining_calls(ticker: str, slug: str | None) -> list[tuple[str, dict]]:
    calls = [(f"/mining/commodities/{c}/price/", {}) for c in MINING_COMMODITIES]
    if slug:
        calls += [(f"/mining/companies/{slug}/", {}),
                  (f"/mining/companies/performance/{slug}/", {}),
                  (f"/mining/companies/financials/{slug}/", {}),
                  (f"/mining/companies/ownership/{slug}/", {}),
                  (f"/mining/sales-destination/{slug}/", {})]
    else:
        calls.append(("/mining/companies/",
                      {"keyword": ticker, "limit": 20}))
    calls += [("/mining/sites/", {"keyword": ticker, "limit": 20}),
              ("/mining/total-production/", {"commodity": "Copper"}),
              ("/mining/total-production/", {"commodity": "Gold"}),
              ("/mining/exports/", {"commodity": "Copper"}),
              ("/mining/exports/", {"commodity": "Gold"})]
    return calls


def idx_calls(ticker: str) -> list[tuple[str, dict]]:
    return [(f"/listing-performance/{ticker}/", {}),
            ("/free-float/", {"symbol": ticker}),
            ("/brokers/top/", {}),
            ("/most-traded/", {})]


def run(calls: list[tuple[str, dict]], live: bool, db: Path) -> int:
    key = os.environ.get("SECTORS_API_KEY") if live else None
    if live and not key:
        sys.exit("butuh SECTORS_API_KEY di env untuk --live")
    cli = Client(key=key, db=db)
    billed = 0
    for ep, params in calls:
        if not live:
            print(f"  [dry] GET {ep} params={params or '-'}")
            continue
        try:
            r = cli.get(ep, params)
            print(f"  [{r['source']}] {ep} key={r['cache_key'][:40]}...")
            if r["source"] == "live":
                billed += 1
        except Exception as e:  # noqa: BLE001 — topup lanjut ke endpoint berikut
            print(f"  [gagal] {ep}: {e}")
    print(f"panggilan billed: {billed} | cache hits: {cli.hits}")
    return billed


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("paket", choices=["mining", "idx", "refresh"])
    p.add_argument("target", help="ticker (mining/idx) atau endpoint (refresh)")
    p.add_argument("--slug", default="", help="slug mining (skip discovery)")
    p.add_argument("--params", default="{}")
    p.add_argument("--live", action="store_true")
    p.add_argument("--db", default=str(DEFAULT_DB))
    a = p.parse_args()
    if a.paket == "mining":
        calls = mining_calls(a.target.upper(), a.slug or None)
    elif a.paket == "idx":
        calls = idx_calls(a.target.upper())
    else:
        calls = [(a.target, json.loads(a.params))]
    print(f"paket={a.paket} target={a.target} mode={'LIVE' if a.live else 'dry-run'}"
          f" calls={len(calls)} estimasi_kredit<={len(calls)}")
    run(calls, a.live, Path(a.db))


if __name__ == "__main__":
    main()
