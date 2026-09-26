"""Dated benchmarks beside the analyst policy discount-rate inputs (spec §4.3).

The valuation keeps its policy values (Rf INDOGB 10Y 6,5%, beta 1,1, ERP 4%,
CRP 2,5% for a US$ model, terminal growth 3,5% Rp / 3,0% US$). This module
puts a sourced, dated benchmark next to each so a reader sees where policy
departs from the market, without inventing a number:

* Rf, ERP, CRP and long-run nominal GDP growth come from
  ``data/rate_benchmarks.json`` (source, URL and date per value);
* beta is a regression of the stock's weekly returns on IHSG from the IDX
  daily series in ``data/idx_history`` (raw and Blume-adjusted), computed on
  closes before the Report Date.

A benchmark dated after the Report Date, or older than its maximum age under
release policy 1.3.0, is left out.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from statistics import covariance, variance

from . import fmt, idx_history, release_policy

PATH = Path(__file__).resolve().parent.parent / "data" / "rate_benchmarks.json"
TITLE = "Parameter tingkat diskonto: kebijakan vs pembanding"
MIN_WEEKS = 52


def load(path=PATH) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _dated(entry, as_of, kind=None):
    """The entry when it is dated on or before ``as_of`` and, for a ``kind`` with a
    policy maximum age (release policy 1.3.0), no older than that."""
    if not isinstance(entry, dict) or not entry.get("as_of"):
        return None
    try:
        age = (date.fromisoformat(str(as_of)[:10]) - date.fromisoformat(entry["as_of"])).days
    except ValueError:
        return None
    limit = release_policy.BENCHMARK_MAX_AGE_DAYS.get(kind)
    return entry if age >= 0 and (limit is None or age <= limit) else None


def _weekly(points):
    out = {}
    for day, close in points:
        out[day.isocalendar()[:2]] = (day, close)  # last close of the ISO week
    return out


def beta(ticker, as_of):
    """Weekly-return regression beta against IHSG on closes before ``as_of``.

    {"raw", "adjusted" (Blume: 0,67 x raw + 0,33), "weeks", "start", "end",
    "source"} or None when either series is missing or shorter than a year.
    """
    stock, index = idx_history.load(ticker, as_of), idx_history.load("IHSG", as_of)
    if not stock or not index:
        return None
    ws, wi = _weekly(stock["points"]), _weekly(index["points"])
    keys = sorted(set(ws) & set(wi))
    rs, rm = [], []
    for a, b in zip(keys, keys[1:]):
        rs.append(ws[b][1] / ws[a][1] - 1)
        rm.append(wi[b][1] / wi[a][1] - 1)
    if len(rm) < MIN_WEEKS or variance(rm) <= 0:
        return None
    raw = covariance(rs, rm) / variance(rm)
    return {"raw": raw, "adjusted": 0.67 * raw + 0.33, "weeks": len(rm),
            "start": ws[keys[0]][0].isoformat(), "end": ws[keys[-1]][0].isoformat(),
            "source": f"{stock.get('source_title') or 'IDX'}; {index.get('source_title') or 'IHSG'}"}


def policy(va) -> dict:
    """The policy inputs the selected method discounted at: rf, erp, beta, and
    crp, g and currency where the method uses them."""
    va = va or {}
    out = {k: v for k, v in (va.get("wacc_inputs") or {}).items() if k in ("rf", "erp", "beta")}
    out["currency"] = "IDR"
    chain = va.get("method_chain") or {}
    selected = next((e for e in chain.get("trace") or [] if e.get("decision") == "selected"), None)
    detail = (selected or {}).get("detail") or {}
    found = []

    def walk(o):
        if isinstance(o, dict):
            if "erp" in o and isinstance(o["erp"], (int, float)):
                found.append(o)
                return
            for v in o.values():
                walk(v)
    walk(detail)
    if found:
        rate = found[0]
        out.update({k: rate[k] for k in ("rf", "erp", "beta", "crp") if isinstance(
            rate.get(k), (int, float))})
        if rate.get("crp") is not None or rate.get("currency") == "USD":
            out["currency"] = "USD"
        if isinstance(rate.get("g"), (int, float)):
            out["g"] = rate["g"]
    if "g" not in out and isinstance(detail.get("g"), (int, float)):
        out["g"] = detail["g"]
    out["method"] = (selected or {}).get("short")
    out["terminal"] = "g" in out
    return out


def exhibit(ticker, as_of, va, data=None):
    """The policy-vs-benchmark table, or None when the method discounts at
    no CAPM rate."""
    rates = policy(va)
    if not all(isinstance(rates.get(k), (int, float)) for k in ("rf", "erp", "beta")):
        return None
    data = load() if data is None else data
    usd = rates["currency"] == "USD"
    pct = fmt.pct
    rows, sources = [], []

    rf = None if usd else _dated(data.get("rf_idr"), as_of, "rf_idr")
    crp = _dated(data.get("crp"), as_of, "crp")
    erp = _dated(data.get("erp"), as_of, "erp")
    b = beta(ticker, as_of)
    # Rupiah model, Damodaran's local-currency build: the INDOGB yield less the
    # sovereign default spread is the risk-free rate, and the equity premium is
    # Indonesia's total (mature market + country risk premium).
    local_rf = rf["value"] - crp["default_spread"] if rf and crp else None
    if not usd:
        rows.append(["Risk-free IDR (house policy)", pct(rates["rf"]),
                     (f"{pct(rf['value'], 2)} ({rf['label']})"
                      + (f"; dikurangi default spread {pct(crp['default_spread'], 2)} = "
                         f"{pct(local_rf, 2)} bebas risiko rupiah" if local_rf is not None else ""))
                     if rf else "tidak tersedia pada tanggal laporan",
                     " + ".join(x["short_source"] for x in (rf, crp if local_rf is not None else None)
                                if x) or "-"])
        if rf:
            sources.append(f"Rf: {rf['source_title']}")
    else:
        rows.append(["Risk-free (UST 10Y)", pct(rates["rf"]), "sama dengan nilai kebijakan",
                     "Yahoo Finance (UST 10Y), tanggal laporan"])
    if usd and isinstance(rates.get("crp"), (int, float)):
        rows.append(["Country risk premium Indonesia", pct(rates["crp"]),
                     crp["label"] if crp else "tidak tersedia pada tanggal laporan",
                     crp["short_source"] if crp else "-"])
    if crp:
        sources.append(f"CRP dan default spread: {crp['source_title']}")
    rows.append(["Beta", fmt._id(rates["beta"], 2),
                 (f"{fmt._id(b['adjusted'], 2)} (Blume; regresi {fmt._id(b['raw'], 2)}, "
                  f"{b['weeks']} return mingguan terhadap IHSG sejak {b['start']})")
                 if b else "riwayat harga IDX kurang dari satu tahun",
                 f"regresi Sektoral, harga IDX s.d. {b['end']}" if b else "-"])
    if b:
        sources.append(f"beta: regresi Sektoral atas {b['source']}")
    if usd:
        rows.append(["Equity risk premium (mature market)", pct(rates["erp"]),
                     f"{pct(erp['value'], 2)}: {erp['label']}" if erp else
                     "tidak tersedia pada tanggal laporan", erp["short_source"] if erp else "-"])
    else:
        rows.append(["Equity risk premium (tanpa CRP terpisah)", pct(rates["erp"]),
                     (f"{pct(erp['value'] + crp['value'], 2)} ERP total Indonesia = "
                      f"{pct(erp['value'], 2)} {erp['label']} + {pct(crp['value'], 2)} CRP")
                     if erp and crp else
                     f"{pct(erp['value'], 2)}: {erp['label']}" if erp else
                     "tidak tersedia pada tanggal laporan",
                     " + ".join(x["short_source"] for x in (erp, crp) if x) or "-"])
    if erp:
        sources.append(f"ERP: {erp['source_title']}")
    growth = data.get("growth") if _dated(data.get("growth"), as_of, "growth") else None
    series = (growth or {}).get("USD" if usd else "IDR")
    nominal = ((1 + series["real"]) * (1 + series["inflation"]) - 1) if series else None
    if rates.get("terminal"):
        rows.append([f"Pertumbuhan terminal g ({'US$' if usd else 'Rp'})", pct(rates["g"]),
                     (f"{pct(nominal)} PDB nominal {series['country']} {series['year']} "
                      f"(riil {pct(series['real'])}, inflasi {pct(series['inflation'])})")
                     if series else "tidak tersedia pada tanggal laporan",
                     growth["short_source"] if series else "-"])
        if series:
            sources.append(f"g: {growth['source_title']}")
    # Cost of equity on the benchmark inputs, for scale (not used in the value).
    policy_crp = (rates.get("crp") or 0.0) if usd else 0.0
    coe_policy = rates["rf"] + policy_crp + rates["beta"] * rates["erp"]
    bench_beta = b["adjusted"] if b else rates["beta"]
    bench_erp = erp["value"] if erp else rates["erp"]
    if usd:
        coe_bench = rates["rf"] + (crp["value"] if crp else policy_crp) + bench_beta * bench_erp
    else:
        coe_bench = ((local_rf if local_rf is not None else rf["value"] if rf else rates["rf"])
                     + bench_beta * (bench_erp + (crp["value"] if crp else 0.0)))
    rows.append(["Cost of equity (CAPM)", pct(coe_policy),
                 f"{pct(coe_bench)} pada input pembanding ({'+' if coe_bench >= coe_policy else ''}"
                 f"{fmt._id((coe_bench - coe_policy) * 1e4, 0)} bp); memo",
                 "baris di atas"])
    return {"n": 0, "judul": TITLE, "tipe": "tabel",
            "data": {"cols": ["Parameter", "Kebijakan", "Pembanding", "Sumber, tanggal"],
                     "rows": rows},
            "catatan_sumber": (
                "Sumber: Sektoral Estimates. Nilai kebijakan adalah parameter analis yang dipakai "
                f"valuasi ({rates.get('method') or 'metode terpilih'}); pembanding ditampilkan "
                "agar selisihnya terlihat, bukan untuk dirata-rata. "
                + "; ".join(sources) + ". Pembanding bertanggal sesudah tanggal laporan tidak "
                "dipakai.")}
