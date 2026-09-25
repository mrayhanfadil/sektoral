"""TAHAP 1B: OVERLAY OPERASIONAL TAMBANG (jawaban kritik #1).

Sumber: endpoint /mining/* di cache (never-expired). Return None bila tidak
ada baris performance untuk ticker — pipeline inti tetap jalan, exhibit
tambahannya absen dengan catatan jujur. Tidak ada angka karangan.
"""
from datetime import date, timedelta

from . import cache, commodity


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


# A deck older than this at the Report Date is stale: the valuation would
# price the mine at a market that no longer exists.
DECK_MAX_AGE_DAYS = 45


def _stats(rows, as_of, source, label):
    """Last close, 12-calendar-month average and yoy from dated rows."""
    rows = sorted((r for r in rows if not as_of or r["date"] <= as_of),
                  key=lambda r: r["date"])
    if not rows:
        return None
    last = rows[-1]
    end = date.fromisoformat(last["date"])
    start = end - timedelta(days=365)
    months = {}
    for r in rows:
        months.setdefault(r["date"][:7], []).append(r["price"])
    # The 12 calendar months ending with the last observation, averaged month
    # by month, so a twice-monthly series and a daily one weigh each month once.
    months = {m: months[m] for m in sorted(months)[-12:]}
    avg12 = sum(sum(v) / len(v) for v in months.values()) / len(months)
    prior = [r for r in rows if date.fromisoformat(r["date"]) <= start]
    yoy = last["price"] / prior[-1]["price"] - 1 if prior and prior[-1]["price"] else None
    age = (date.fromisoformat(as_of) - end).days if as_of else None
    return {"last": last["price"], "date": last["date"], "avg12": avg12, "yoy": yoy,
            "n": len(rows), "months": len(months), "source": source, "source_label": label,
            "window": [min(months), max(months)], "age_days": age,
            "stale": age is not None and age > DECK_MAX_AGE_DAYS}


def _price_stats(name: str, as_of: str | None = None) -> dict | None:
    """Sectors series first; the dated Yahoo series only when Sectors is stale."""
    rows = []
    for _, p in _by_prefix("/mining/commodities/"):
        items = p if isinstance(p, list) else (p.get("data") or [])
        rows.extend({"date": str(r.get("date"))[:10], "price": _num(r.get("price_usd_per_ton"))}
                    for r in items
                    if str(r.get("name") or "").lower() == name.lower()
                    and r.get("date") and _num(r.get("price_usd_per_ton")) is not None)
    sectors = _stats(rows, as_of, "sectors", "data Sectors /mining/commodities") if rows else None
    if sectors and not sectors["stale"]:
        return sectors
    series = commodity.load(name)
    yahoo = (_stats(series["rows"], as_of, "yahoo", series["source"]) if series else None)
    if yahoo and (not sectors or yahoo["date"] > sectors["date"]):
        if sectors:
            yahoo["replaced"] = {"date": sectors["date"], "avg12": sectors["avg12"],
                                 "age_days": sectors["age_days"]}
        return yahoo
    return sectors


def load(ticker: str, as_of=None) -> dict | None:
    """Overlay operasional tambang atau None. Tidak pernah raise untuk miss."""
    t = ticker.upper()
    day = str(as_of)[:10] if as_of else None
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
            "cu_price": _price_stats("Copper", day), "au_price": _price_stats("Gold", day)}
