"""The six questions a Company Update answers first (plan §6), from the model itself.

1. What changed since the last Company Update (rating history, latest actual).
2. What the model expects in the next explicit periods (parent profit path).
3. What must occur for the base case (the most value-sensitive drivers).
4. What the quoted price appears to imply: the move in each top driver that
   brings the value to the price, read linearly from its tested range, and the
   discount rate that equates value and price when the valuation reports it.
5. What would prove the view wrong: the move in each top driver that changes
   the rating band (``app.rating``), again from the tested range.
6. The next observable catalyst: the next statutory filing (OJK POJK 14/2022
   calendar, release policy 1.2.0) with the metric to compare, and the first
   dated catalyst of the report's catalyst table.

Implied moves are linear readings of a +/- step and say so; nothing here is a
probability or a forecast of the price.
"""
from __future__ import annotations

from datetime import date

from . import fmt, release_policy

BUY, SELL = 0.15, -0.10
# A linear reading beyond this many tested steps leaves the tested range too far
# to mean anything (e.g. a probability above 100%); such a driver is reported
# as not changing the value or rating alone.
MAX_STEPS = 5.0


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _move_to(row, target, base):
    """(multiple of the tested step, direction word) that moves value from ``base`` to ``target``.

    ``low``/``high`` of a row name the driver's direction at its adverse and
    favourable ends (a cost rises at its adverse end, a volume falls).
    """
    need = target - base
    effect = row["value_effect_high"] if need > 0 else row["value_effect_low"]
    if not effect or (need > 0) != (effect > 0) or abs(need / effect) > MAX_STEPS:
        return None
    room = row.get("max_steps_high" if need > 0 else "max_steps_low")
    if room is not None and abs(need / effect) > room:
        return None  # the driver would leave its feasible range (e.g. above 100%)
    return need / effect, (row["high"] if need > 0 else row["low"])


def _step_text(row, move):
    """The move in the driver's own unit: a multiple of its tested step."""
    import re
    fraction, direction = move
    match = re.search(r"±\s*([\d.,]+)\s*(pp|bp|%)", row["unit"])
    if match:
        step = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        rest = row["unit"][match.end():].split(",")[0].strip()
        amount = f"{fmt._id(abs(fraction) * step, 1)} {unit}".replace(" %", "%")
        return f"{row['driver']} {direction} {amount}{(' ' + rest) if rest else ''}"
    return f"{row['driver']} {direction} {fmt._id(abs(fraction), 1)} x rentang uji"


def _band(upside):
    return "Buy" if upside > BUY else "Sell" if upside < SELL else "Hold"


def next_filing(as_of, latest_period_end=None):
    """The next statutory filing due after ``as_of`` for a period after the latest
    official actual (period and OJK deadline)."""
    day = _day(as_of)
    latest = _day(latest_period_end)
    if not day:
        return None
    upcoming = []
    for year in (day.year, day.year + 1):
        for period in release_policy.fiscal_periods(year):
            deadline = release_policy.filing_deadline(period["period_end"], period["kind"])
            if deadline > day and (latest is None or period["period_end"] > latest):
                upcoming.append((deadline, period))
    if not upcoming:
        return None
    deadline, period = min(upcoming, key=lambda item: item[0])
    return {"label": period["label"], "period_end": period["period_end"].isoformat(),
            "deadline": deadline.isoformat()}


def build(doc, intake, fc, va):
    meta = doc.get("meta") or {}
    dv = doc.get("driver_value") or {}
    price, tp = intake.get("price"), meta.get("tp")
    rows = []
    actual = intake.get("latest_official_actual") or {}
    rating = meta.get("rating")
    history = "-"
    if rating in ("Buy", "Hold", "Sell"):
        from . import rating_history
        history = rating_history.cover_status(intake["ticker"], rating)
        history = (history.get("label") if isinstance(history, dict) else history) or "-"
    rows.append(["Yang berubah", f"Rating {rating or '-'} ({history}); aktual resmi terbaru "
                 f"{actual.get('period') or '-'} (terbit {actual.get('published_at') or '-'})."])
    path = []
    scenario = (fc or {}).get("earnings_scenario") or {}
    full = scenario.get("full_year") or {}
    if full.get("net_profit_attributable") is not None:
        path.append((scenario.get("year"), full["net_profit_attributable"]))
    for r in ((fc or {}).get("outyear_scenario") or {}).get("rows") or []:
        path.append((r.get("year"), r.get("net_profit_attributable")))
    usd = (intake.get("official_evidence") or {}).get("reporting_currency") == "USD"
    money = (lambda v: f"US${fmt._id(v / 1e6, 1)} juta") if usd else \
        (lambda v: f"Rp{fmt._id(v / 1e9, 1)} miliar")
    if path:
        rows.append(["Ekspektasi model", "Laba induk " + ", ".join(
            f"FY{y % 100:02d}F {money(v)}" for y, v in path[:3] if y and v is not None) + "."])
    top = (dv.get("rows") or [])[:3]
    if top:
        rows.append(["Yang harus terjadi", "; ".join(
            f"{r['driver']} {r['base']} ({r['basis']})" for r in top) + "."])
    base = ((dv.get("cases") or {}).get("base") or {}).get("per_share")
    if top and price and base:
        implied = [(_step_text(r, m) if m is not None else None) for r in top
                   for m in [_move_to(r, price, base)]]
        implied = [t for t in implied if t]
        detail = next((t.get("detail") for t in ((va or {}).get("method_chain") or {}).get("trace") or []
                       if t.get("key") == ((va or {}).get("method_chain") or {}).get("selected")), {}) or {}
        rate = detail.get("implied_wacc") or detail.get("implied_coe")
        text = ("Harga Rp" + fmt._id(price, 0) + " setara dengan satu dari: " + "; ".join(implied)
                + " dari rentang uji (pembacaan linear)") if implied else \
            "Harga di luar jangkauan rentang uji setiap driver"
        if rate:
            text += f"; tingkat diskonto tersirat {fmt.pct(rate)}"
        rows.append(["Yang disiratkan harga", text + "."])
        rating = meta.get("rating")
        if rating in ("Buy", "Hold", "Sell"):
            bounds = {"Buy": [price * (1 + BUY)], "Hold": [price * (1 + BUY), price * (1 + SELL)],
                      "Sell": [price * (1 + SELL)]}[rating]
            tests = []
            for bound in bounds:
                for r in top[:2]:
                    f = _move_to(r, bound, base)
                    if f is not None:
                        tests.append(f"{_step_text(r, f)} (nilai Rp{fmt._id(bound, 0)}, rating "
                                     f"menjadi {_band(bound / price - 1 + (1e-6 if bound > base else -1e-6))})")
            rows.append(["Yang membuktikan salah", ("Rating " + rating + " berubah bila "
                         + "; atau ".join(tests)) if tests else
                         "Tidak ada driver dalam rentang uji yang mengubah rating sendirian."])
    filing = next_filing(intake.get("as_of"), actual.get("period_end"))
    catalyst = None
    for page in doc.get("bagian") or []:
        for exhibit in page.get("exhibit") or []:
            if exhibit.get("judul") == "Katalis, risiko, dan indikator pemantauan":
                data = (exhibit.get("data") or {}).get("rows") or []
                # The next catalyst is one still ahead: skip rows marked completed.
                ahead = [r for r in data if not any(word in str(r[1]).lower()
                                                    for word in ("rampung", "selesai", "completed"))]
                catalyst = ahead[0] if ahead else None
    parts = []
    if filing:
        parts.append(f"laporan {filing['label']} (batas OJK {filing['deadline']}): bandingkan "
                     "laba induk, volume dan margin dengan jalur model")
    if catalyst:
        parts.append(f"{catalyst[0]} ({catalyst[1].split('. Sumber')[0]})")
    if parts:
        rows.append(["Katalis berikutnya", "; ".join(parts) + "."])
    limitation = next(iter(((va or {}).get("release") or {}).get("limitations") or []), None)
    rows.append(["Status dan batas", f"Tanggal laporan {intake.get('as_of')}; harga {intake.get('price_date')}; "
                 f"status {meta.get('status')}; metode {va.get('method') if va else '-'}; "
                 f"batas utama: {limitation or '-'}."])
    return rows
