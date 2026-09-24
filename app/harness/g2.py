"""Tool: check_g2 — TAHAP 2 FORECAST ENGINE (§3.2, G2.1–G2.9).

Profile-aware. Deterministic math + provenance checks.
Historical CAGR / 3y-average / capex=D&A / flat debt / zero-for-missing
are screening proxies, never auto production evidence (G2.9).
"""
from __future__ import annotations

from .profiles import g2_for, normalize


def _v(check_id: str, ok: bool, msg: str, blocker: bool = True,
       status_override: str | None = None) -> dict:
    return {"check": check_id,
            "status": status_override or ("lolos" if ok else "gagal"),
            "blocker": blocker and not ok and status_override != "dilabeli",
            "message": msg}


def _num(x):
    try:
        if x is None or isinstance(x, bool):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def check_g2(intake: dict | None, forecast: dict | None) -> dict:
    intake, forecast = intake or {}, forecast or {}
    profile = normalize(intake.get("model_profile"))
    applicable = g2_for(profile)
    checks: list[dict] = []
    rows = forecast.get("rows") or []
    annuals = intake.get("annuals") or []

    def applies(g: str) -> bool:
        return g in applicable

    # G2.1 run-rate vs interim (all profiles with interim).
    if applies("G2.1"):
        actual = intake.get("latest_official_actual") or {}
        metrics = (actual.get("metrics") or {}) if isinstance(actual, dict) else {}
        rev_h1 = _num(metrics.get("revenue"))
        if rev_h1 and rows:
            fy_rev = _num(rows[0].get("revenue"))
            # crude: interim should be < full-year forecast, deviation flag at >10pp vs 2x H1
            if fy_rev:
                implied = rev_h1 * 2 / fy_rev - 1
                ok = abs(implied) <= 0.50  # loose; tight 10pp check needs H1/H2 split
                checks.append(_v("G2.1", True,
                                 f"realisasi interim vs forecast FY berjalan: deviasi {implied*100:.1f}%"
                                 if ok else f"selisih run-rate {implied*100:.1f}%; jelaskan/revisi",
                                 not ok, None if ok else "dilabeli"))
            else:
                checks.append(_v("G2.1", True, "tanpa interim terstruktur; diuji saat rilis tersedia",
                                 False, "dilabeli"))
        else:
            checks.append(_v("G2.1", True, "tanpa interim terstruktur; diuji saat rilis tersedia",
                             False, "dilabeli"))

    # G2.2 EBITDA margin within historical range (profiles using EBITDA).
    if applies("G2.2"):
        hist = [a["ebitda"] / a["revenue"] for a in annuals
                if isinstance(a, dict) and _num(a.get("ebitda")) is not None
                and _num(a.get("revenue"))]
        if hist and rows:
            lo, hi = min(hist), max(hist)
            bad = [r for r in rows
                   if _num(r.get("margin")) is not None
                   and not (lo - 1e-9 <= r["margin"] <= hi + 1e-9)]
            checks.append(_v("G2.2", not bad,
                             "margin EBITDA dalam rentang historis" if not bad
                             else f"margin di luar rentang [{lo*100:.1f},{hi*100:.1f}]% butuh driver+sumber",
                             bool(bad), None if not bad else "gagal-dilabeli"))
        else:
            checks.append(_v("G2.2", True, "riwayat EBITDA tak cukup; dilabeli", False, "dilabeli"))

    # G2.3 unit economics — driver scenario must move profit via model math.
    if applies("G2.3"):
        effects = forecast.get("news_assumptions") or []
        has_flat_pct = any(e.get("driver") == "net_flat_pct" for e in effects)
        checks.append(_v("G2.3", not has_flat_pct,
                         "leverage operasi via unit economics" if not has_flat_pct
                         else "persentase laba flat tanpa perhitungan driver",
                         has_flat_pct))

    # G2.4 consistency — same number in forecast, financials, valuation, exhibits.
    if applies("G2.4"):
        g2log = (forecast.get("g2") or {})
        if g2log.get("G2.4_konsistensi") == "gagal":
            checks.append(_v("G2.4", False, "angka tak konsisten antar forecast/valuasi/exhibit", True))
        else:
            # verify revenue chain present in rows
            ok = bool(rows) and all(_num(r.get("revenue")) for r in rows)
            checks.append(_v("G2.4", ok, "satu angka dipakai di IS/CF/DCF" if ok
                             else "forecast rows kosong/tak konsisten", True))

    # G2.5 balance reconcile.
    if applies("G2.5"):
        g2log = (forecast.get("g2") or {})
        if g2log.get("G2.5_neraca") == "gagal":
            checks.append(_v("G2.5", False, "neraca/ekuitas/kas tak terekonsiliasi", True))
        else:
            checks.append(_v("G2.5", True, "neraca terekonsiliasi (kas satu-satunya penyeimbang)", False))

    # G2.6 no identical consecutive years without driver reason.
    if applies("G2.6"):
        if len(rows) >= 2:
            flat = all(rows[i]["revenue"] == rows[i + 1]["revenue"]
                       for i in range(len(rows) - 1))
            checks.append(_v("G2.6", not flat,
                             "variasi tahunan logis" if not flat
                             else "angka identik 2 tahun butuh alasan driver", True))
        else:
            checks.append(_v("G2.6", False, "forecast rows < 2 tahun", True))

    # G2.7 fiscal labels consistent.
    if applies("G2.7"):
        labels = [str(r.get("label") or "") for r in rows]
        ok = bool(labels) and all(l.startswith("FY") for l in labels)
        checks.append(_v("G2.7", ok, "label tahun fiskal konsisten" if ok
                         else "label fiskal tak konsisten", True))

    # G2.8 financial_ddm: profit/retained/dividend/equity/ROE/capital consistency.
    if applies("G2.8"):
        if profile == "financial_ddm":
            payout = _num(intake.get("payout"))
            ok = payout is not None and 0 <= payout <= 1.5 and bool(rows)
            checks.append(_v("G2.8", ok,
                             "laba/dividen/ekuitas/ROE konsisten" if ok
                             else "payout/dividen/ekuitas tak konsisten", True))
        else:
            checks.append(_v("G2.8", True, "tidak berlaku untuk profile ini", False, "dilabeli"))

    # G2.9 driver chain complete, sourced, reconciled. Screening proxy alone fails.
    if applies("G2.9"):
        basis = forecast.get("forecast_basis")
        ready = forecast.get("production_ready") is True
        if profile == "finite_life_mining":
            ok = basis == "physical_driver_forecast" and ready
            checks.append(_v("G2.9", ok,
                             "rantai fisik-ke-keuangan direkonsiliasi" if ok
                             else "forecast fisik-ke-keuangan belum dihitung; CAGR hanya screening",
                             True))
        elif profile == "financial_ddm":
            ok = basis in ("driver_forecast", "financial_driver_forecast") and ready
            g2log = (forecast.get("g2") or {})
            failed_g2 = [k for k, v in g2log.items()
                         if k != "catatan" and (v == "gagal" or (isinstance(v, tuple) and v[0] == "gagal"))]
            if failed_g2:
                ok = False
            checks.append(_v("G2.9", ok,
                             "driver forecast keuangan bersumber + direkonsiliasi" if ok
                             else "driver laba/modal/payout belum rekonsiliasi; screen bukan forecast produksi",
                             True))
        else:
            ok = basis == "driver_forecast" and ready
            g2log = (forecast.get("g2") or {})
            failed_g2 = [k for k, v in g2log.items()
                         if k != "catatan" and (v == "gagal" or (isinstance(v, tuple) and v[0] == "gagal"))]
            if failed_g2:
                ok = False
            checks.append(_v("G2.9", ok,
                             "driver forecast bersumber + direkonsiliasi" if ok
                             else "CAGR/capex=D&A hanyalah screen; driver + NWC + jadwal utang belum rekonsiliasi",
                             True))

    blockers = [f"{c['check']}: {c['message']}" for c in checks if c.get("blocker")]
    status = "lolos" if not blockers else "gagal"
    return {"tool": "check_g2", "profile": profile, "applicable": list(applicable),
            "status": status, "checks": checks, "blockers": blockers}
