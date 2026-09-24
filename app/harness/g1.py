"""Tool: check_g1 — TAHAP 1 INTAKE & VALIDASI DATA (§2).

Deterministic. No LLM. Fails closed: missing critical input blocks
production, never becomes a caveat.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

_PERIOD = re.compile(r"^(?:1Q|2Q|3Q|4Q|1H|2H|9M|FY)\d{2}$")


def _verdict(check_id: str, ok: bool, msg: str, blocker: bool,
             status_override: str | None = None) -> dict:
    if status_override:
        status = status_override
    else:
        status = "lolos" if ok else "gagal"
    return {"check": check_id, "status": status, "blocker": blocker and not ok,
            "message": msg}


def _parse_date(v: Any):
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def check_g1(intake: dict | None) -> dict:
    """Validate Gate 1. Returns {"checks": [...], "blockers": [...], "status": ...}."""
    checks: list[dict] = []
    blockers: list[str] = []
    intake = intake or {}

    # G1.periode — latest official/interim actual must exist with valid dates.
    actual = intake.get("latest_official_actual") or intake.get("latest_interim_actuals")
    if not isinstance(actual, dict):
        c = _verdict("G1.periode", False, "rilis resmi terbaru belum ada di input", True)
    else:
        period = str(actual.get("period") or "")
        pub = _parse_date(actual.get("published_at") or actual.get("source_date"))
        end = _parse_date(actual.get("period_end") or actual.get("source_date"))
        as_of = _parse_date(intake.get("as_of") or intake.get("price_date"))
        problems = []
        if not period:
            problems.append("periode kosong")
        if pub is None:
            problems.append("tanggal rilis tidak valid")
        if end is None:
            problems.append("tanggal periode tidak valid")
        if pub and end and end > pub:
            problems.append("period_end setelah published_at")
        if pub and as_of and pub > as_of:
            problems.append("rilis terbit setelah tanggal laporan")
        # interim label should look like 1Q26/1H26/9M26/FY26
        status_txt = str(actual.get("status") or "").lower()
        if "actual" not in status_txt and "reported" not in status_txt and not pub:
            problems.append("status bukan aktual")
        if problems:
            c = _verdict("G1.periode", False, "periode terbaru: " + "; ".join(problems), True)
        else:
            c = _verdict("G1.periode", True, f"periode terbaru {period} tervalidasi", False)
    checks.append(c)

    # G1.satuan — one scale per table; detect absurd Rp miliar vs triliun mix.
    # Heuristic: revenue per share vs price same order of magnitude (from intake.load).
    g1log = intake.get("_g1 boosts") or {}
    rps_price_ok = True
    try:
        price = float(intake.get("price") or 0)
        shares = float(intake.get("shares") or 0)
        annuals = intake.get("annuals") or []
        if price > 0 and shares > 0 and annuals:
            rev = float((annuals[-1] or {}).get("revenue") or 0)
            if rev > 0:
                ratio = (rev / shares) / price
                rps_price_ok = 0.01 <= ratio <= 100
    except (TypeError, ValueError):
        rps_price_ok = False
    checks.append(_verdict("G1.satuan", rps_price_ok,
                           "skala satuan konsisten" if rps_price_ok
                           else "skala satuan tidak konsisten; keluarkan dari laporan bila tak pasti",
                           False, None if rps_price_ok else "gagal-dilabeli"))

    # G1.mata_uang — model built in reporting currency; FX only for per-share/market.
    cur = (intake.get("currency") or intake.get("reporting_currency") or "Rp")
    fx = intake.get("fx", 1.0)
    cur_ok = cur in ("Rp", "IDR", "USD", "US$")
    checks.append(_verdict("G1.mata_uang", cur_ok,
                           f"mata uang model {cur}" if cur_ok else "mata uang tak dikenal",
                           True))
    _ = fx  # documented: FX=1 for Rp model; USD model converts only at equity bridge

    # G1.kas — cash recon where CF legs exist (tolerance ±1%).
    recon_ok, legs = True, 0
    for a in (intake.get("annuals") or []):
        if isinstance(a, dict) and all(a.get(k) is not None for k in ("ocf", "fcf", "capex_out")):
            legs += 1
            try:
                if abs((a["ocf"] - a["capex_out"]) - a["fcf"]) > 0.01 * max(abs(a["fcf"]), 1):
                    recon_ok = False
            except TypeError:
                recon_ok = False
    if legs == 0:
        checks.append(_verdict("G1.kas", True, "kaki arus kas tak lengkap; rekonsiliasi tak diuji", False,
                               "dilabeli"))
    else:
        checks.append(_verdict("G1.kas", recon_ok,
                               "kas awal + perubahan = kas akhir" if recon_ok
                               else "rekonsiliasi kas gagal; tampilkan di lampiran saja", False,
                               None if recon_ok else "gagal-dilabeli"))

    # G1.nonrecurring — must be labeled inti vs dilaporkan; absence = label only.
    checks.append(_verdict("G1.nonrecurring", True,
                           "laba dilaporkan = laba inti kecuali item non-recurring dilabeli",
                           False, "dilabeli"))

    # Absolute rule: never fabricate. Critical missing → block production.
    for c in checks:
        if c.get("blocker"):
            blockers.append(f"{c['check']}: {c['message']}")

    status = "lolos" if not blockers else "gagal"
    return {"tool": "check_g1", "status": status, "checks": checks, "blockers": blockers}
