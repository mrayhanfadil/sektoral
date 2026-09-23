"""Opsi C ringan: NAV LoM per aliran logam (produksi flat sampai cadangan habis).

Bukan DCF perpetual: tiap aliran didiskonto sebagai anuitas selama
umur = cadangan / produksi tahunan. Tanpa terminal value. Semua proksi
(margin, FX, harga) berlabel eksplisit.
"""

from .fx import load_cached_rate


_FX_QUOTE = load_cached_rate()
FX_USDIDR = float(_FX_QUOTE["rate"]) if _FX_QUOTE else 16000.0
FX_BASIS = (
    f"Yahoo Finance IDR=X ({_FX_QUOTE['date']})" if _FX_QUOTE else
    "asumsi analis Rp16.000/USD (rate belum di-refresh; tanpa silent network fallback)"
)
OZT_PER_TON = 32150.7


def nav_stream(annual_prod, reserve, price_usd, margin, discount):
    """Anuitas arus kas flat selama umur cadangan. Satuan konsisten per aliran."""
    life = reserve / annual_prod if annual_prod and annual_prod > 0 else None
    if not life or discount <= 0:
        return {"life": life, "annual_cf": None, "pv": None}
    annual_cf = annual_prod * price_usd * margin
    pv = annual_cf * (1 - (1 + discount) ** (-life)) / discount
    return {"life": life, "annual_rev": annual_prod * price_usd,
            "annual_cf": annual_cf, "pv": pv}


def metal_gross_usd(mo):
    """Nilai logam bruto tahunan (produksi x harga rata-rata 12 bln), USD."""
    cu, au = (mo["comms"].get("Copper") or {}), (mo["comms"].get("Gold") or {})
    cup, aup = (mo.get("cu_price") or {}), (mo.get("au_price") or {})
    cu_rev = (cu.get("prod") or 0) * 1000 * (cup.get("avg12") or 0)
    au_rev = (au.get("prod") or 0) * 1000 * (aup.get("avg12") or 0)
    return cu_rev + au_rev


def build(mo, margin, discount, cash_bn, debt_bn, reported_rev_bn):
    """mo = mineops.load(); margin = proksi margin kas (berlabel); discount = WACC."""
    cu, au = (mo["comms"].get("Copper") or {}), (mo["comms"].get("Gold") or {})
    cup, aup = (mo.get("cu_price") or {}), (mo.get("au_price") or {})
    # Satuan API dibaca sebagai: produksi Cu kton, cadangan Cu kton,
    # produksi Au koz, cadangan Au koz, harga USD/ton.
    cu_nav = nav_stream((cu.get("prod") or 0) * 1000, (cu.get("cu_cont_mt") or 0) * 1000,
                        (cup.get("avg12") or 0), margin, discount)
    # Harga Au di API berunit USD/oz (orde 4 ribuan), bukan USD/ton.
    au_nav = nav_stream((au.get("prod") or 0) * 1000, (au.get("au_cont_koz") or 0) * 1000,
                        (aup.get("avg12") or 0), margin, discount)
    streams = [
        {"nama": "Tembaga (Batu Hijau & Elang)", "ukuran":
         f"cadangan {(cu.get('cu_cont_mt') or 0):,.0f} kton, produksi "
         f"{(cu.get('prod') or 0):,.1f} kton/thn".replace(",", "."),
         "kepemilikan": 1.0, "life": cu_nav["life"],
         "nav_usd": cu_nav["pv"]},
        {"nama": "Emas (Batu Hijau & Elang)", "ukuran":
         f"cadangan {(au.get('au_cont_koz') or 0):,.0f} koz, produksi "
         f"{(au.get('prod') or 0):,.1f} koz/thn".replace(",", "."),
         "kepemilikan": 1.0, "life": au_nav["life"],
         "nav_usd": au_nav["pv"]},
    ]
    for s in streams:
        s["nav_rpbn"] = (s["nav_usd"] or 0) * FX_USDIDR / 1e9
        s["nav"] = s["nav_rpbn"]
    # Jembatan pendapatan: nilai logam bruto vs pendapatan tercatat.
    gross_usd = metal_gross_usd(mo)
    reported_usd = reported_rev_bn * 1e9 / FX_USDIDR
    payability = reported_usd / gross_usd if gross_usd else None
    gap = abs(1 - payability) if payability is not None else None
    total_nav = sum(s["nav_rpbn"] for s in streams)
    rnav = total_nav + (cash_bn or 0) - (debt_bn or 0)
    return {
        "streams": streams,
        "margin_basis": ("proksi margin kas = margin EBITDA forecast "
                         "(bukan C1 cash cost, tidak ada di cache)"),
        "fx": FX_USDIDR, "fx_basis": FX_BASIS,
        "price_basis": ("rata-rata 12 bulan: Cu USD/ton per "
                        f"{(cup.get('date') or '-')} (n={(cup.get('n') or 0)}), Au "
                        f"USD/oz per {(aup.get('date') or '-')} (n={(aup.get('n') or 0)})"),
        "bridge": {"gross_usd_bn": gross_usd / 1e9 if gross_usd else None,
                   "reported_usd_bn": reported_usd / 1e9,
                   "payability": payability, "gap_pct": gap,
                   "needs_explanation": gap is not None and gap > 0.25},
        "total_nav_rpbn": total_nav, "rnav_rpbn": rnav,
    }
