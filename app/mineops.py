"""TAHAP 1B: OVERLAY OPERASIONAL TAMBANG (jawaban kritik #1).

Sumber: endpoint /mining/* di cache (never-expired). Return None bila tidak
ada baris performance untuk ticker — pipeline inti tetap jalan, exhibit
tambahannya absen dengan catatan jujur. Tidak ada angka karangan.
"""
from . import cache


def _num(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _find_slug(ticker: str) -> str | None:
    for _, p in cache.payloads("/mining/companies/"):
        for r in (p.get("results") or []):
            sym = str(r.get("symbol") or "")
            if sym.upper().startswith(ticker.upper()):
                return r.get("slug")
    return None


def _by_prefix(prefix: str):
    out = []
    for ep in cache.endpoints():
        if ep.startswith(prefix):
            for key, p in cache.payloads(ep):
                out.append((ep, p))
    return out


def _price_stats(name: str) -> dict | None:
    rows = []
    for _, p in _by_prefix("/mining/commodities/"):
        items = p if isinstance(p, list) else (p.get("data") or [])
        rows.extend(r for r in items
                    if str(r.get("name") or "").lower() == name.lower()
                    and _num(r.get("price_usd_per_ton")) is not None)
    if not rows:
        return None
    rows.sort(key=lambda r: r.get("date") or "")
    last = rows[-1]
    tail = [r for r in rows[-12:] if _num(r.get("price_usd_per_ton")) is not None]
    if not tail:
        return None
    avg12 = sum(_num(r["price_usd_per_ton"]) for r in tail) / len(tail)
    yoy = None
    if len(rows) >= 13 and _num(rows[-13]["price_usd_per_ton"]):
        yoy = last["price_usd_per_ton"] / rows[-13]["price_usd_per_ton"] - 1
    return {"last": _num(last["price_usd_per_ton"]), "date": last.get("date"),
            "avg12": avg12, "yoy": yoy, "n": len(rows)}


def load(ticker: str) -> dict | None:
    """Overlay operasional tambang atau None. Tidak pernah raise untuk miss."""
    t = ticker.upper()
    slug = _find_slug(t)
    if not slug:
        return None
    perf_rows = []
    for ep, p in _by_prefix("/mining/companies/performance/"):
        if slug not in ep:
            continue
        data = p.get("data") or []
        if data:
            perf_rows = data
            break
    if not perf_rows:
        return None
    by_year = {}
    for r in perf_rows:
        by_year.setdefault(r.get("year"), []).append(r)
    year = max(y for y in by_year if y is not None)
    comms = {}
    for r in by_year[year]:
        st = r.get("commodity_stats") or {}
        res = st.get("resources_reserves") or {}
        prods = [p.get("product_name") for p in (st.get("products") or [])
                 if p.get("product_name")]
        comms[r.get("commodity_type")] = {
            "unit": st.get("unit"),
            "status": st.get("mining_operation_status"),
            "prod": _num(st.get("production_volume")),
            "sales": _num(st.get("sales_volume")),
            "res_mt": _num(res.get("total_reserves_Mt")),
            "cu_cont_mt": _num(res.get("Cu_reserves_Mt")),
            "cu_grade": _num(res.get("Cu_reserves_pct")),
            "au_cont_koz": _num(res.get("Au_reserves_koz")),
            "au_grade": _num(res.get("Au_reserves_g_per_ton")),
            "blocks": prods,
        }
    cu, au = comms.get("Copper") or {}, comms.get("Gold") or {}
    life = None
    life_basis = None
    # Satuan API tertulis "Mt" tetapi nilainya konsisten dengan kton
    # (13.149 kton = 13,1 Mt, cocok dengan 3.936 Mt bijih x 0,33%).
    # Dipakai sebagai kton, berlabel eksplisit di bawah.
    if cu.get("cu_cont_mt") and cu.get("prod") and cu["prod"] > 0:
        life = cu["cu_cont_mt"] / cu["prod"]  # kton dibagi kton/thn
        life_basis = ("cadangan Cu terkandung (nilai API, dibaca sebagai kton) "
                      "dibagi produksi Cu 2024")
    return {"ticker": t, "slug": slug, "year": year,
            "available_years": sorted(y for y in by_year if y is not None),
            "comms": comms, "reserve_life_cu_yr": life,
            "reserve_life_basis": life_basis,
            "cu_price": _price_stats("Copper"), "au_price": _price_stats("Gold")}
