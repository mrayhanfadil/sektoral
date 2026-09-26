"""Investability: dated liquidity, free float, trading status, business quality (plan §6.1).

Liquidity comes from the Sectors daily series on or before the Report Date
(close x volume per session over a stated window); free float from the
public shareholding the report already shows, with its source; the listing
board from the Sectors company overview. Suspension or special-notation
status is not in the data, so it is stated as unavailable, never assumed.

The illustrative position table states the assumed position sizes and a
participation rate; days to trade = position / (participation x median daily
value). It does not imply execution at the quoted price.

Business quality (``data/business_quality/<TICKER>.json``) is an issuer-
specific, dated assessment per dimension; a dimension without dated evidence
stays unanswered, and each answered one states its effect on the model.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

from . import cache

ROOT = Path(__file__).resolve().parent.parent / "data" / "business_quality"
WINDOW = 60                     # trading sessions (about three months)
PARTICIPATION = 0.20            # share of daily value an order may take
POSITIONS_IDR = (10e9, 50e9, 100e9)
DIMENSIONS = (
    ("competitive_position", "Posisi kompetitif"),
    ("concentration", "Konsentrasi pelanggan dan pemasok"),
    ("pricing_power", "Daya penetapan harga"),
    ("cyclicality", "Siklikalitas"),
    ("capital_allocation", "Alokasi modal manajemen"),
    ("ownership_control", "Kepemilikan dan pengendalian"),
    ("related_party", "Eksposur pihak berelasi"),
    ("governance", "Tata kelola"),
)


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def liquidity(ticker, as_of):
    payload = cache.first(f"/daily/{ticker}/") or {}
    rows = payload.get("data") if isinstance(payload, dict) else None
    cutoff = _day(as_of)
    rows = [r for r in rows or [] if isinstance(r, dict) and _day(r.get("date"))
            and cutoff and _day(r["date"]) <= cutoff]
    rows.sort(key=lambda r: r["date"])
    window = rows[-WINDOW:]
    values = [r["close"] * r["volume"] for r in window
              if _num(r.get("close")) and _num(r.get("volume")) is not None]
    if len(values) < 20:
        return {"status": "unavailable",
                "reason": f"kurang dari 20 sesi harga dan volume sampai {as_of} di data Sectors"}
    median = statistics.median(values)
    return {"status": "available", "sessions": len(values),
            "start": window[0]["date"], "end": window[-1]["date"],
            "mean_value": statistics.mean(values), "median_value": median,
            "zero_volume_sessions": sum(1 for r in window if not r.get("volume")),
            "source": f"data Sectors harian {ticker} (harga penutupan x volume)",
            "positions": [{"position": p, "participation": PARTICIPATION,
                           "days": p / (PARTICIPATION * median) if median else None}
                          for p in POSITIONS_IDR]}


def free_float(intake):
    holders = intake.get("major_holders") or []
    for holder in holders:
        name = str(holder.get("name") or "").lower()
        if name in ("public", "publik", "masyarakat"):
            pct = _num(holder.get("share_percentage"))
            if pct is not None:
                pct = pct if pct > 1 else pct * 100
                return {"status": "available", "pct": pct,
                        "value": (intake.get("market_cap") or 0) * pct / 100 or None,
                        "source": intake.get("major_holders_source") or "data kepemilikan Sectors"}
    return {"status": "unavailable", "reason": "porsi publik tidak tersedia di data kepemilikan"}


# Why a dimension is unanswered when its file gives no dated evidence (plan
# Checkpoint 4: never unanswered without a stated reason).
GOVERNANCE_REASON = ("tidak dijawab: Sektoral Team belum menetapkan sumber penilaian tata kelola "
                     "bertanggal yang dapat diterima (keputusan D8, 2026-09-26)")
DEFAULT_REASON = ("tidak dijawab: belum ditelaah; berkas kualitas bisnis tidak memuat bukti "
                  "bertanggal untuk dimensi ini")


def business_quality(ticker, as_of, root=ROOT):
    path = Path(root) / f"{str(ticker).upper()}.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    cutoff = _day(as_of)
    out = []
    for key, label in DIMENSIONS:
        item = (data.get("dimensions") or {}).get(key)
        evidence = [e for e in (item or {}).get("evidence") or []
                    if isinstance(e, dict) and str(e.get("url") or "").startswith("https://")
                    and _day(e.get("published_at")) and cutoff and _day(e["published_at"]) <= cutoff]
        if not item or not evidence or not str(item.get("assessment") or "").strip():
            reason = ((item or {}).get("unanswered_reason")
                      or (GOVERNANCE_REASON if key == "governance" else DEFAULT_REASON))
            out.append({"dimension": key, "label": label, "status": "unanswered",
                        "assessment": reason, "reason": reason,
                        "model_effect": None, "evidence": []})
            continue
        out.append({"dimension": key, "label": label, "status": "answered",
                    "assessment": item["assessment"], "model_effect": item.get("model_effect"),
                    "evidence": evidence})
    return out


def assess(intake):
    ticker, as_of = intake["ticker"], intake.get("as_of")
    overview = ((cache.company_report(ticker) or {}).get("overview") or {})
    return {"as_of": as_of, "liquidity": liquidity(ticker, as_of),
            "free_float": free_float(intake),
            "board": overview.get("listing_board"),
            "board_source": "profil emiten data Sectors" if overview.get("listing_board") else None,
            "trading_status": {"status": "unavailable",
                               "reason": "status suspensi dan notasi khusus tidak ada di data; "
                                         "tidak diasumsikan normal"},
            "business_quality": business_quality(ticker, as_of)}
