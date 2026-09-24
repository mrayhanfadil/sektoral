"""Tool: check_g3 — TAHAP 3 VALUATION ENGINE (§4.6, G3.1–G3.7).

Profile-aware. Verifies math the engine already computed; never
re-invents valuation. LoM/SOTP has no perpetual terminal (G3.1 n/a).
"""
from __future__ import annotations

from .profiles import g3_for, normalize

from .. import gate_thresholds


def _v(check_id: str, ok: bool, msg: str, blocker: bool = True,
       status_override: str | None = None) -> dict:
    return {"check": check_id,
            "status": status_override or ("lolos" if ok else "gagal"),
            "blocker": blocker and not ok and (status_override or "") != "dilabeli",
            "message": msg}


def _num(x):
    try:
        if x is None or isinstance(x, bool):
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def check_g3(intake: dict | None, forecast: dict | None, valuation: dict | None) -> dict:
    intake, forecast, valuation = intake or {}, forecast or {}, valuation or {}
    profile = normalize(intake.get("model_profile"))
    applicable = g3_for(profile)
    checks: list[dict] = []

    def applies(g: str) -> bool:
        return g in applicable

    price = _num(intake.get("price"))
    mcap = _num(intake.get("market_cap"))
    tp = _num(valuation.get("tp"))
    chain = valuation.get("method_chain") or {}
    dcf_selected = not chain.get("order") or chain.get("selected") == "fcff_dcf"
    tv_share = _num(valuation.get("tv_share")) if dcf_selected else None
    g3log = valuation.get("g3") or {}

    # G3.1 terminal share >80% flagged. N/A for LoM without terminal.
    if applies("G3.1"):
        if profile == "finite_life_mining":
            checks.append(_v("G3.1", True, "LoM tanpa terminal perpetual; tidak berlaku",
                             False, "dilabeli"))
        elif tv_share is None:
            checks.append(_v("G3.1", True, "porsi terminal tak tersedia; dilabeli", False, "dilabeli"))
        else:
            ok = not gate_thresholds.tv_flagged(tv_share)
            checks.append(_v("G3.1", True,
                             f"porsi terminal {tv_share*100:.0f}% dari EV"
                             + ("" if ok else f" >{gate_thresholds.TV_SHARE_PCT:.0f}%: wajib catatan + uji"),
                             False, "lolos" if ok else "peringatan"))

    # G3.2 equity/TP vs market cap 20–300% same unit/date.
    if applies("G3.2"):
        if tp and mcap and price:
            shares = _num(intake.get("shares")) or (mcap / price if price else None)
            eq = tp * shares if shares else None
            ratio = (eq / mcap) if (eq and mcap) else None
            if ratio is None:
                checks.append(_v("G3.2", True, "skala tak dapat dihitung; dilabeli", False, "dilabeli"))
            else:
                ok = 0.2 <= ratio <= 3.0
                checks.append(_v("G3.2", ok,
                                 f"ekuitas valuasi {ratio*100:.0f}% dari market cap" if ok
                                 else f"ekuitas {ratio*100:.0f}% dari mcap: telusuri + tesis fundamental",
                                 not ok))
        elif isinstance(g3log.get("G3.2_skala"), tuple):
            st, msg = g3log["G3.2_skala"]
            checks.append(_v("G3.2", st == "lolos", msg, st.startswith("gagal")))
        else:
            checks.append(_v("G3.2", True, "TP ditahan (draft); skala diuji saat TP terbit",
                             False, "dilabeli"))

    # G3.3 implied multiples recomputed from forecast; EV multiple not a bank gate.
    if applies("G3.3"):
        if profile == "financial_ddm":
            checks.append(_v("G3.3", True, "PER/PBV dari forecast; EV multiple bukan gate bank",
                             False, "dilabeli"))
        else:
            impl = valuation.get("implied") or {}
            ok = _num(impl.get("per")) is not None or _num(impl.get("ev_ebitda")) is not None or tp is None
            checks.append(_v("G3.3", ok, "implied multiple dari forecast" if ok
                             else "implied multiple tak dapat dihitung", True))

    # G3.4 sensitivity from same TP basis; downside < base.
    if applies("G3.4"):
        tp_down = _num(valuation.get("tp_down"))
        if tp is None:
            checks.append(_v("G3.4", True, "TP ditahan; sensitivitas diuji saat TP terbit",
                             False, "dilabeli"))
        elif tp_down is None:
            # mining SOTP: sensitivity labeled separately
            st = g3log.get("G3.4_sensitivity") or g3log.get("G3.4_downside")
            base = "downside" if isinstance(st, tuple) else str(st or "")
            if base == "dilabeli" or st == "dilabeli":
                checks.append(_v("G3.4", True, "sensitivitas SOTP dilabeli", False, "dilabeli"))
            else:
                checks.append(_v("G3.4", False, "sensitivitas belum dihitung dari basis TP yang sama", True))
        else:
            checks.append(_v("G3.4", tp_down < tp,
                             f"downside {tp_down:.0f} vs base {tp:.0f}" if tp_down < tp
                             else "downside tidak lebih rendah dari base", True))

    # G3.5 Key Financials uses correct BVPS/shares/cash-debt/forecast year per method.
    if applies("G3.5"):
        if isinstance(g3log.get("G3.5_keyfin"), str):
            ok = g3log["G3.5_keyfin"] == "lolos"
            checks.append(_v("G3.5", ok, "metrik Key Financials per metode" if ok
                             else "metrik Key Financials salah tahun/metode", True))
        else:
            # only EV when applicable (never for financial_ddm)
            if profile == "financial_ddm" and valuation.get("ev_gordon") is not None:
                checks.append(_v("G3.5", True, "EV tampil untuk bank; hanya tampilkan bila applicable",
                                 False, "peringatan"))
            else:
                checks.append(_v("G3.5", True, "metrik valuasi per metode", False))

    # G3.6 peer comparability (when peer set used).
    if applies("G3.6"):
        peers = intake.get("peers") or []
        if not peers:
            checks.append(_v("G3.6", True, "tanpa peer set; dilabeli", False, "dilabeli"))
        else:
            checks.append(_v("G3.6", True, f"{len(peers)} peer; model bisnis sebanding dijelaskan di narasi",
                             False))

    # G3.7 historical band (when used).
    if applies("G3.7"):
        checks.append(_v("G3.7", True, "band historis sebanding bila dipakai", False, "dilabeli"))

    # Cross-cutting §4.4: divergence >30% must not be averaged; extreme TP needs thesis.
    upside = _num(valuation.get("upside"))
    if upside is not None and gate_thresholds.is_extreme_ratio(upside):
        checks.append(_v("G3.9_extreme", False,
                         f"TP ekstrem upside>+{gate_thresholds.EXTREME_UPSIDE_PCT:.0f}%/downside<{gate_thresholds.EXTREME_DOWNSIDE_PCT:.0f}%: butuh tesis fundamental + keterbatasan model di hlm 1",
                         True))
    ps_g, ps_x = _num(valuation.get("ps_gordon")), _num(valuation.get("ps_exit"))
    if dcf_selected and ps_g is not None and ps_x is not None:
        div = abs(ps_g - ps_x) / max(abs(ps_g), abs(ps_x), 1)
        if div > 0.30 and valuation.get("dcf_basis") == "gordon":
            # §4.4: the primary (Gordon) stays the TP basis; the exit value is a
            # disclosed cross-check, not averaged, so the gap is labeled.
            checks.append(_v("G3.8_divergence", True,
                             f"selisih Gordon vs exit {div*100:.1f}%: TP memakai Gordon, "
                             "exit hanya cross-check dan selisih diungkapkan",
                             False, "dilabeli"))
        elif div > 0.30:
            checks.append(_v("G3.8_divergence", False,
                             f"selisih Gordon vs exit {div*100:.1f}%: jangan dirata-rata diam-diam",
                             True))

    blockers = [f"{c['check']}: {c['message']}" for c in checks if c.get("blocker")]
    status = "lolos" if not blockers else "gagal"
    return {"tool": "check_g3", "profile": profile, "applicable": list(applicable),
            "status": status, "checks": checks, "blockers": blockers}
