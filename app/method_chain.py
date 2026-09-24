"""Rantai metode valuasi: primary → fallback → draft (Instruksi-Report-v3 §4.1a §4.4 §4.6).

Urutan metode dikunci dari verdict Gates 0-5 sebelum nilai dihitung (chain_for).
Metode berikutnya hanya dicoba bila metode sebelumnya *insufficient*: input wajib
hilang atau cek struktural gagal (skala vs market cap, downside tidak lebih
rendah, divergensi Gordon vs exit). Hasil yang tidak disukai bukan alasan
turun rantai: metode pertama yang cukup tetapi ekstrem (upside > +100% atau
downside < -50% per app.gate_thresholds) menghentikan rantai dan laporan tetap
draft sampai ada tesis fundamental bersumber.
"""
from __future__ import annotations

import math

from . import gate_thresholds

CHAINS = {
    "finite_life_mining": ("sotp_lom", "rnav_lom", "ev_ebitda_fy"),
    "going_concern_fcff": ("fcff_dcf", "relative_pe", "pe_fy_scenario"),
    "financial_ddm": ("ddm", "pbv_roe", "relative_pe", "pe_fy_scenario"),
}

LABELS = {
    "sotp_lom": "SOTP/LoM (asset-based, no perpetual terminal)",
    "rnav_lom": "RNAV LoM anuitas (tanpa terminal perpetual)",
    "ev_ebitda_fy": "FY26F EV/EBITDA 8x (asumsi analis)",
    "ev_ebitda_peer": "EV/EBITDA peer forward x EBITDA",
    "ev_sales_peer": "EV/Sales peer x Revenue",
    "ps_peer": "P/S peer x Sales per share",
    "pbv_relative": "P/BV relatif peer x BVPS",
    "holding_sotp": "Holding SOTP per anak usaha/aset",
    "property_nav": "Property NAV per aset",
    "dcf_reference": "DCF konsolidasi (referensi)",
    "fcff_dcf": "DCF FCFF eksplisit + terminal Gordon, dibobot sama dengan exit EV/EBITDA",
    "relative_pe": "Relatif PER peer (median) x EPS forward",
    "ddm": "DDM dividen eksplisit + terminal Gordon (CoE, bukan WACC)",
    "pbv_roe": "P/BV wajar vs ROE (Inverse CoE)",
    "pe_fy_scenario": "FY26F PER median peer x EPS skenario analis",
}

SHORT = {"sotp_lom": "SOTP/LoM", "rnav_lom": "RNAV LoM", "ev_ebitda_fy": "EV/EBITDA FY",
         "ev_ebitda_peer": "EV/EBITDA peer", "ev_sales_peer": "EV/Sales peer",
         "ps_peer": "P/S peer", "pbv_relative": "P/BV relatif",
         "holding_sotp": "Holding SOTP", "property_nav": "Property NAV",
         "dcf_reference": "DCF referensi",
         "fcff_dcf": "DCF FCFF", "relative_pe": "PER relatif", "ddm": "DDM",
         "pbv_roe": "P/BV-ROE", "pe_fy_scenario": "PER FY skenario"}

SCALE_BAND = gate_thresholds.SCALE_BAND
# Deprecated alias: extreme is now asymmetric (+100%/-50%) via gate_thresholds.
EXTREME_UPSIDE = 0.50
PEER_PE_BAND = (0.0, 50.0)
PEER_PB_BAND = (0.0, 10.0)
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


def peer_pbvs(peers) -> list[float]:
    """P/BV peer valid (0 < P/BV <= 10), terurut."""
    lo, hi = PEER_PB_BAND
    return sorted(p.get("pb") for p in peers or []
                  if _finite(p.get("pb")) and lo < p["pb"] <= hi)


def peer_ev_ebitdas(peers) -> list[float]:
    """EV/EBITDA peer valid; cache Sectors saat ini tidak membawa EV."""
    return sorted(p.get("ev_ebitda") for p in peers or []
                  if _finite(p.get("ev_ebitda")) and p["ev_ebitda"] > 0)


def peer_ev_sales(peers) -> list[float]:
    """EV/Sales peer valid; cache Sectors saat ini tidak membawa EV."""
    return sorted(p.get("ev_sales") for p in peers or []
                  if _finite(p.get("ev_sales")) and p["ev_sales"] > 0)


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


def _peer_multiple_candidate(key, multiples, per_share_base, per_share_down_base,
                             shares, market_cap, label_extra="") -> dict:
    """Generic peer-multiple candidate with median>=3 rule and quartile downside."""
    if len(multiples) < MIN_PEERS:
        return candidate(key, reasons=[
            f"peer {key} belum tersedia di cache Sectors "
            f"({len(multiples)} < {MIN_PEERS}); belum dimodelkan"])
    if not (_finite(per_share_base) and per_share_base > 0):
        return candidate(key, reasons=["denominator forecast <= 0; multiple tidak bermakna"])
    q1, median, _q3 = pe_quartiles(sorted(multiples))
    ps = median * per_share_base
    down = q1 * per_share_base
    # per_share_down_base allows EV-based bridges to pass net-debt adjusted downside
    if _finite(per_share_down_base):
        down = per_share_down_base
    return candidate(
        key, per_share=ps, per_share_down=down,
        reasons=scale_reasons(ps, shares, market_cap),
        labels=[label_extra or "median peer; peer dianggap sebanding"],
        detail={"median": median, "q1": q1, "peer_count": len(multiples)})


def ev_ebitda_peer(peers, ebitda_fwd, shares, market_cap, net_debt=0.0) -> dict:
    """Forward EV/EBITDA peer x EBITDA; bridge ke ekuitas via net debt."""
    mults = peer_ev_ebitdas(peers)
    if len(mults) < MIN_PEERS:
        return candidate("ev_ebitda_peer", reasons=[
            f"peer EV/EBITDA belum tersedia di cache Sectors ({len(mults)} < {MIN_PEERS}); "
            "belum dimodelkan"])
    if not (_finite(ebitda_fwd) and ebitda_fwd > 0):
        return candidate("ev_ebitda_peer", reasons=["EBITDA forward <= 0; EV/EBITDA tidak bermakna"])
    q1, median, _q3 = pe_quartiles(sorted(mults))
    ev = median * ebitda_fwd
    ev_down = q1 * ebitda_fwd
    nd = net_debt if _finite(net_debt) else 0.0
    ps = (ev - nd) / shares if _finite(shares) and shares > 0 else None
    down = (ev_down - nd) / shares if _finite(shares) and shares > 0 else None
    return candidate(
        "ev_ebitda_peer", per_share=ps, per_share_down=down,
        reasons=scale_reasons(ps, shares, market_cap) if _finite(ps) else [],
        labels=["EV/EBITDA peer forward; bridge net debt dari neraca resmi"],
        detail={"median_ev_ebitda": median, "q1_ev_ebitda": q1,
                "peer_count": len(mults), "ebitda_fwd": ebitda_fwd, "net_debt": nd})


def ev_sales_peer(peers, revenue_fwd, shares, market_cap, net_debt=0.0) -> dict:
    mults = peer_ev_sales(peers)
    if len(mults) < MIN_PEERS:
        return candidate("ev_sales_peer", reasons=[
            f"peer EV/Sales belum tersedia di cache Sectors ({len(mults)} < {MIN_PEERS}); "
            "belum dimodelkan"])
    if not (_finite(revenue_fwd) and revenue_fwd > 0):
        return candidate("ev_sales_peer", reasons=["revenue forward <= 0; EV/Sales tidak bermakna"])
    q1, median, _q3 = pe_quartiles(sorted(mults))
    ev = median * revenue_fwd
    nd = net_debt if _finite(net_debt) else 0.0
    ps = (ev - nd) / shares if _finite(shares) and shares > 0 else None
    down = (q1 * revenue_fwd - nd) / shares if _finite(shares) and shares > 0 else None
    return candidate(
        "ev_sales_peer", per_share=ps, per_share_down=down,
        reasons=scale_reasons(ps, shares, market_cap) if _finite(ps) else [],
        labels=["EV/Sales peer; untuk rugi operasi kronis"],
        detail={"median_ev_sales": median, "q1_ev_sales": q1, "peer_count": len(mults)})


def pbv_relative(peers, bvps_fwd, shares, market_cap) -> dict:
    """Median P/BV peer x BVPS; downside kuartil bawah. Butuh >=3 peer P/BV."""
    pbvs = peer_pbvs(peers)
    if len(pbvs) < MIN_PEERS:
        return candidate("pbv_relative", reasons=[
            f"peer P/BV valid {len(pbvs)} < {MIN_PEERS}; belum dimodelkan"])
    if not (_finite(bvps_fwd) and bvps_fwd > 0):
        return candidate("pbv_relative", reasons=["BVPS <= 0; P/BV tidak bermakna"])
    q1, median, _q3 = pe_quartiles(pbvs)
    ps = median * bvps_fwd
    return candidate(
        "pbv_relative", per_share=ps, per_share_down=q1 * bvps_fwd,
        reasons=scale_reasons(ps, shares, market_cap),
        labels=["P/BV peer x BVPS forecast; peer dianggap sebanding"],
        detail={"median_pbv": median, "q1_pbv": q1, "peer_count": len(pbvs)})


def unavailable(key, reason="belum tersedia; belum dimodelkan") -> dict:
    """SOTP/NAV tanpa evidence pack: muncul di rantai sebagai belum tersedia."""
    return candidate(key, reasons=[reason])


def chain_for(verdict, profile: str) -> tuple:
    """Order rantai dari verdict Gates 0-5 (plan §1.3). Fixed sebelum nilai dihitung."""
    primary = ""
    failed: set = set()
    reasons: list = []
    if isinstance(verdict, dict):
        primary = str(verdict.get("primary") or "")
        failed = set(verdict.get("gates_failed") or [])
        reasons = list(verdict.get("reasons") or [])
    else:
        primary = str(getattr(verdict, "primary", "") or "")
        failed = set(getattr(verdict, "gates_failed", []) or [])
        reasons = list(getattr(verdict, "reasons", []) or [])
    prof = (profile or "").strip().lower()
    joined = " ".join(reasons).lower()

    def _assessed(gate_id: str) -> bool:
        """True bila gate gagal karena nilai nyata, bukan 'tidak dapat dinilai'."""
        if gate_id not in failed:
            return False
        # Unassessed gates record tidak dapat dinilai; keep default DCF order.
        # Heuristic: if any tidak-dapat-dinilai reason mentions the gate number, treat as unassessed.
        gate_num = gate_id.split("_")[0]  # e.g. 1a, 1b, 1d
        for r in reasons:
            rl = str(r).lower()
            if "tidak dapat dinilai" in rl and gate_num in rl:
                return False
        # Generic tidak-dapat-dinilai without gate number: check overall.
        if "tidak dapat dinilai" in joined and gate_id in ("1a_filing_history", "1b_profitability", "1d_equity_base"):
            # If primary was not forced by that gate, it was unassessed.
            if primary in ("FCFF/WACC DCF", "DCF (shortened horizon)", ""):
                # For 1a: thin_data would be True if truly <4y; check primary.
                if gate_id == "1a_filing_history" and primary != "DCF (shortened horizon)":
                    return False
                if gate_id in ("1b_profitability", "1d_equity_base") and primary != "Relative Valuation":
                    return False
        return True

    # Financial institution
    if primary.startswith("DDM") or prof == "financial_ddm":
        return ("ddm", "pbv_roe", "relative_pe", "pe_fy_scenario")
    # REIT / property investment (subset finite; NAV first)
    if "REIT" in primary.upper() or "PROPERTY" in primary.upper():
        return ("property_nav", "pbv_relative", "pe_fy_scenario")
    # Holding / NCI>40% / dissimilar segments
    if primary == "SOTP":
        return ("holding_sotp", "dcf_reference", "pe_fy_scenario")
    # Finite reserves / commodity-driven
    if primary in ("NAV / Reserve-based",):
        return ("sotp_lom", "rnav_lom", "ev_ebitda_fy")
    # History <4y or ramping (thin_data or 1a assessed)
    if primary == "DCF (shortened horizon)" or _assessed("1a_filing_history"):
        # ramping vs thin: both use forward EV/EBITDA peer first
        return ("ev_ebitda_peer", "pe_fy_scenario")
    # Chronic operating losses -> Relative Valuation via EV/Sales (assessed only)
    if primary == "Relative Valuation" and _assessed("1b_profitability"):
        # negative equity handled below; chronic loss uses EV/Sales -> P/S
        return ("ev_sales_peer", "ps_peer")
    # Negative equity: EV-only, no PER/PBV (assessed only)
    if _assessed("1d_equity_base"):
        return ("ev_ebitda_peer", "ev_sales_peer")
    # Decline / turnaround
    if primary == "P/BV":
        return ("pbv_relative", "dcf_reference")
    # Pre-revenue / high growth -> EV/Sales
    if primary == "EV/Sales":
        return ("ev_sales_peer", "ps_peer")
    # Passes all gates
    if prof == "finite_life_mining":
        return ("sotp_lom", "rnav_lom", "ev_ebitda_fy")
    if prof == "financial_ddm":
        return ("ddm", "pbv_roe", "relative_pe", "pe_fy_scenario")
    return ("fcff_dcf", "relative_pe", "pe_fy_scenario")


def run(profile: str, candidates: dict, price, order=None, override_key=None) -> dict:
    """Jalankan rantai; kembalikan trace lengkap + metode terpilih.

    order: urutan dari chain_for(verdict, profile); bila None pakai CHAINS legacy.
    override_key: analis override; sistem tetap simpan proposed order di trace.
    """
    base_order = tuple(order) if order else tuple(CHAINS.get(profile, ()))
    trace, selected, extreme = [], None, False
    proposed = list(base_order)
    eff_order = list(base_order)
    if override_key:
        # Override: analis memilih metode; urutan sistem tetap tercatat.
        if override_key not in eff_order:
            eff_order = [override_key] + eff_order
        else:
            eff_order = [override_key] + [k for k in eff_order if k != override_key]
    for rank, key in enumerate(eff_order, 1):
        c = dict(candidates.get(key) or candidate(key, reasons=["metode belum dihitung"]))
        # role primary hanya untuk rank 1 tanpa override; override selalu fallback/override
        if override_key and key == override_key and rank == 1:
            role = "override"
        else:
            role = "primary" if rank == 1 and not override_key else "fallback"
        c.update(rank=rank, role=role)
        up = (c["per_share"] / price - 1) if (c["per_share"] and _finite(price) and price > 0) else None
        c["upside"] = up
        if selected is None:
            if c["status"] == "sufficient":
                selected = key
                extreme = up is not None and gate_thresholds.is_extreme_ratio(up)
                c["decision"] = "stop_extreme" if extreme else "selected"
            else:
                c["decision"] = "skipped"
        else:
            c["decision"] = "cross_check" if c["status"] == "sufficient" else "not_needed"
        trace.append(c)
    route = None
    if selected:
        if override_key and selected == override_key:
            route = "override"
        elif selected == (base_order[0] if base_order else None) and not override_key:
            route = "primary"
        else:
            route = "fallback" if not override_key else "override"
    return {"profile": profile, "order": list(eff_order), "proposed_order": proposed,
            "selected": selected, "route": route, "extreme": extreme,
            "trace": trace, "override": override_key}


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
    ("peer EV/EBITDA", "peer EV/EBITDA belum tersedia di cache"),
    ("peer EV/Sales", "peer EV/Sales belum tersedia di cache"),
    ("peer P/BV", "peer P/BV valid kurang dari tiga"),
    ("peer holding_sotp", "SOTP holding belum tersedia"),
    ("peer property_nav", "NAV properti belum tersedia"),
    ("Holding SOTP", "SOTP holding memerlukan evidence pack per anak usaha"),
    ("Property NAV", "NAV properti memerlukan evidence pack per aset"),
    ("official share count", "jumlah saham resmi belum tersedia"),
    ("belum tersedia", "belum dimodelkan"),
    ("tidak dapat dinilai", "tidak dapat dinilai"),
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
