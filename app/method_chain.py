"""Rantai metode valuasi: primary → fallback → draft (Instruksi-Report-v3 §4.1a).

Urutan metode dikunci per ``MODEL_PROFILE`` sebelum nilai dihitung. Metode
berikutnya hanya dicoba bila metode sebelumnya *insufficient*: input wajib
hilang atau cek struktural gagal (skala vs market cap, downside tidak lebih
rendah, divergensi Gordon vs exit). Hasil yang tidak disukai bukan alasan
turun rantai: metode pertama yang cukup tetapi ekstrem (|upside| > 50%)
menghentikan rantai dan laporan tetap draft.
"""
from __future__ import annotations

import math

CHAINS = {
    "finite_life_mining": ("sotp_lom", "rnav_lom", "ev_ebitda_fy"),
    "going_concern_fcff": ("fcff_dcf", "relative_pe", "pe_fy_scenario"),
    "financial_ddm": ("ddm", "pbv_roe", "relative_pe", "pe_fy_scenario"),
}

LABELS = {
    "sotp_lom": "SOTP/LoM (asset-based, no perpetual terminal)",
    "rnav_lom": "RNAV LoM anuitas (tanpa terminal perpetual)",
    "ev_ebitda_fy": "FY26F EV/EBITDA 8x (asumsi analis)",
    "fcff_dcf": "DCF FCFF eksplisit + terminal Gordon, dibobot sama dengan exit EV/EBITDA",
    "relative_pe": "Relatif PER peer (median) x EPS forward",
    "ddm": "DDM dividen eksplisit + terminal Gordon (CoE, bukan WACC)",
    "pbv_roe": "P/BV wajar vs ROE (Inverse CoE)",
    "pe_fy_scenario": "FY26F PER median peer x EPS skenario analis",
}

SHORT = {"sotp_lom": "SOTP/LoM", "rnav_lom": "RNAV LoM", "ev_ebitda_fy": "EV/EBITDA FY",
         "fcff_dcf": "DCF FCFF", "relative_pe": "PER relatif", "ddm": "DDM",
         "pbv_roe": "P/BV-ROE", "pe_fy_scenario": "PER FY skenario"}

SCALE_BAND = (0.2, 3.0)
EXTREME_UPSIDE = 0.50
PEER_PE_BAND = (0.0, 50.0)
MIN_PEERS = 3


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def scale_reasons(per_share, shares, market_cap) -> list[str]:
    """G3.2: ekuitas tersirat harus 20-300% dari market cap."""
    if not (_finite(per_share) and _finite(shares) and _finite(market_cap)) or market_cap <= 0:
        return []
    ratio = per_share * shares / market_cap
    lo, hi = SCALE_BAND
    if lo <= ratio <= hi:
        return []
    return [f"skala: ekuitas {ratio*100:.0f}% dari market cap "
            f"(ambang {lo*100:.0f}-{hi*100:.0f}%)"]


def candidate(key, per_share=None, per_share_down=None, reasons=(),
              labels=(), detail=None) -> dict:
    """Satu metode kandidat. ``reasons`` kosong + nilai valid = sufficient."""
    reasons = [r for r in reasons if r]
    if not reasons and not (_finite(per_share) and per_share > 0):
        reasons.append("nilai per saham tidak terdefinisi atau <= 0")
    if (not reasons and _finite(per_share_down) and per_share_down >= per_share):
        reasons.append("downside sensitivitas tidak lebih rendah dari base")
    return {"key": key, "label": LABELS.get(key, key), "short": SHORT.get(key, key),
            "status": "insufficient" if reasons else "sufficient",
            "per_share": per_share if _finite(per_share) else None,
            "per_share_down": per_share_down if _finite(per_share_down) else None,
            "reasons": reasons, "labels": [l for l in labels if l],
            "detail": detail or {}}


def peer_pes(peers) -> list[float]:
    """PER peer valid (0 < PER <= 50), terurut."""
    lo, hi = PEER_PE_BAND
    return sorted(p.get("pe") for p in peers or []
                  if _finite(p.get("pe")) and lo < p["pe"] <= hi)


def _median(xs):
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2


def pe_quartiles(pes) -> tuple[float, float, float]:
    """(kuartil bawah, median, kuartil atas) dari PER peer terurut."""
    half = max(1, len(pes) // 2)
    return _median(pes[:half]), _median(pes), _median(pes[-half:])


def relative_pe(peers, eps_fwd, shares, market_cap) -> dict:
    """Median PER peer (0 < PER <= 50) x EPS forward; downside = kuartil bawah."""
    hi = PEER_PE_BAND[1]
    pes = peer_pes(peers)
    reasons = []
    if len(pes) < MIN_PEERS:
        reasons.append(f"peer PER valid {len(pes)} < {MIN_PEERS} (band 0-{hi:.0f}x)")
    if not (_finite(eps_fwd) and eps_fwd > 0):
        reasons.append("EPS forward <= 0; PER tidak bermakna")
    if reasons:
        return candidate("relative_pe", reasons=reasons)
    q1, median, _q3 = pe_quartiles(pes)
    ps = median * eps_fwd
    return candidate(
        "relative_pe", per_share=ps, per_share_down=q1 * eps_fwd,
        reasons=scale_reasons(ps, shares, market_cap),
        labels=["PER peer TTM diterapkan ke EPS forward; peer dianggap sebanding"],
        detail={"median_pe": median, "q1_pe": q1, "peer_count": len(pes),
                "eps_fwd": eps_fwd})


def run(profile: str, candidates: dict, price) -> dict:
    """Jalankan rantai; kembalikan trace lengkap + metode terpilih."""
    order = CHAINS.get(profile, ())
    trace, selected, extreme = [], None, False
    for rank, key in enumerate(order, 1):
        c = dict(candidates.get(key) or candidate(key, reasons=["metode belum dihitung"]))
        c.update(rank=rank, role="primary" if rank == 1 else "fallback")
        up = (c["per_share"] / price - 1) if (c["per_share"] and _finite(price) and price > 0) else None
        c["upside"] = up
        if selected is None:
            if c["status"] == "sufficient":
                selected = key
                extreme = up is not None and abs(up) > EXTREME_UPSIDE
                c["decision"] = "stop_extreme" if extreme else "selected"
            else:
                c["decision"] = "skipped"
        else:
            c["decision"] = "cross_check" if c["status"] == "sufficient" else "not_needed"
        trace.append(c)
    route = None
    if selected:
        route = "primary" if selected == order[0] else "fallback"
    return {"profile": profile, "order": list(order), "selected": selected,
            "route": route, "extreme": extreme, "trace": trace}


_READER_REASONS = (
    ("SOTP incomplete", "NAV per aset dan jembatan ekuitas SOTP belum lengkap"),
    ("forecast agent scenario", "skenario forecast analis belum tervalidasi"),
    ("latest interim actuals", "hasil interim resmi belum tervalidasi"),
    ("source-backed interim scenario", "skenario interim bersumber belum tersedia"),
    ("interim scenario", "skenario interim belum cocok dengan rilis resmi"),
    ("fresh sourced close", "harga penutupan bersumber sesudah rilis belum tersedia"),
    ("fresh sourced USD/IDR", "kurs USD/IDR bersumber belum tersedia"),
    ("official cash/debt/minority/share", "jembatan kas, utang, minoritas dan saham belum lengkap"),
    ("6x/8x/10x", "sensitivitas multiple 6x/8x/10x belum lengkap"),
    ("EV/EBITDA sensitivity", "sensitivitas multiple tidak monoton"),
    ("assumption-led method", "metode multiple hanya untuk profil tambang"),
    ("financial DDM", "hasil DDM belum tersedia"),
    ("mining forecast is not", "forecast fisik tambang masih screening"),
    ("operating bridge missing", "jembatan operasi fisik ke keuangan belum ada"),
    ("forecast gate failed", "forecast belum lolos rekonsiliasi G2.9"),
    ("sourced operating and cash-flow forecast", "forecast driver bersumber belum lengkap"),
    ("forecast is not verified", "forecast masih screening"),
    ("forecast: ", "forecast masih screening"),
    ("driver forecast missing", "seri driver forecast belum bersumber"),
    ("latest official interim actual", "hasil interim resmi belum tervalidasi"),
    ("earnings scenario", "skenario laba FY belum tervalidasi"),
    ("peer PER", "peer PER valid kurang dari tiga"),
    ("official share count", "jumlah saham resmi belum tersedia"),
)


def reader_reason(reason: str) -> str:
    """Alasan untuk pembaca laporan; trace JSON tetap menyimpan teks mesin."""
    for prefix, text in _READER_REASONS:
        if reason.startswith(prefix):
            return text
    return reason


def summary_blocker(chain: dict) -> str | None:
    """Blocker tunggal tingkat rantai (None bila metode terpilih wajar)."""
    sel = chain.get("selected")
    if not chain.get("order"):
        return None
    if not sel:
        parts = [f"{t['key']}: {t['reasons'][0]}" for t in chain["trace"] if t["reasons"]]
        return "method chain: no sufficient valuation method (" + "; ".join(parts) + ")"
    if chain.get("extreme"):
        return f"extreme {sel} target needs a sourced fundamental thesis"
    return None
