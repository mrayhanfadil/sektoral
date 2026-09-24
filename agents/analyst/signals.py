"""Deterministic market-intelligence signals from local Sectors data.

Every number the analyst agent talks about comes from here. The agent chooses
which checks to run; this module computes values, peer ranks and flags so the
same inputs always produce the same signals.
"""
from __future__ import annotations

import statistics
from datetime import date

from app import fmt

# id -> (label, unit, higher_is) ; ``higher_is`` only phrases the flag.
PEER_METRICS = {
    "market_cap": ("Kapitalisasi pasar", "rp", "lebih besar"),
    "roe": ("ROE", "pct", "lebih tinggi"),
    "net_margin": ("Margin laba bersih", "pct", "lebih tinggi"),
    "roa": ("ROA", "pct", "lebih tinggi"),
    "leverage": ("Liabilitas / ekuitas", "x", "lebih tinggi"),
    "pe": ("P/E", "x", "lebih mahal"),
    "pb": ("P/B", "x", "lebih mahal"),
    "mcap_change_1y": ("Perubahan kapitalisasi 1 tahun", "pct", "lebih tinggi"),
}
DEFAULT_PEER_METRICS = ("roe", "net_margin", "leverage", "pe", "pb")


def display(value, unit):
    if value is None:
        return "n.a."
    if unit == "pct":
        return fmt.pct(value)
    if unit == "x":
        return fmt.mult(value)
    if unit == "rp":
        return f"Rp{fmt.miliar(value)} miliar"
    if unit == "count":
        return str(int(value))
    return str(value)


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # drop NaN


def _ratio(numerator, denominator):
    numerator, denominator = _num(numerator), _num(denominator)
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def peer_row(symbol, name, *, market_cap=None, pe=None, pb=None, net_income=None,
             revenue=None, equity=None, assets=None, liabilities=None,
             mcap_change_1y=None, year=None, is_self=False):
    """Normalise one company into the metric set used for ranking."""
    equity_value = _num(equity)
    metrics = {
        "market_cap": _num(market_cap),
        "roe": _ratio(net_income, equity) if equity_value and equity_value > 0 else None,
        "net_margin": _ratio(net_income, revenue),
        "roa": _ratio(net_income, assets),
        "leverage": _ratio(liabilities, equity) if equity_value and equity_value > 0 else None,
        # A P/E on negative earnings is not comparable; exclude it from ranks.
        "pe": _num(pe) if (_num(pe) or 0) > 0 else None,
        "pb": _num(pb) if (_num(pb) or 0) > 0 else None,
        "mcap_change_1y": _num(mcap_change_1y),
    }
    return {"symbol": str(symbol).replace(".JK", ""), "name": name or "", "year": year,
            "is_self": bool(is_self), "metrics": metrics}


def rank_peers(rows, metrics, source):
    """Rank the subject company within its peer rows for each metric."""
    subject = next((row for row in rows if row["is_self"]), None)
    if subject is None:
        return []
    signals = []
    for metric in metrics:
        if metric not in PEER_METRICS:
            continue
        label, unit, higher_is = PEER_METRICS[metric]
        values = [(row["symbol"], row["metrics"].get(metric)) for row in rows]
        valid = sorted(((sym, v) for sym, v in values if v is not None),
                       key=lambda item: item[1], reverse=True)
        own = subject["metrics"].get(metric)
        others = [v for sym, v in valid if sym != subject["symbol"]]
        signal = {"id": f"peer.{metric}", "kind": "peer", "label": label, "unit": unit,
                  "value": own, "display": display(own, unit), "source": source,
                  "n": len(valid), "rank": None, "flag": None}
        if others:
            median = statistics.median(others)
            signal["median"] = median
            signal["median_display"] = display(median, unit)
        if own is None:
            signal["note"] = "tidak bermakna atau tidak tersedia untuk emiten ini"
        elif len(valid) >= 3:
            rank = 1 + [sym for sym, _ in valid].index(subject["symbol"])
            signal["rank"] = rank
            signal["note"] = f"peringkat {rank} dari {len(valid)} (1 = {higher_is})"
            if rank == 1 and len(valid) >= 4:
                signal["flag"] = "tertinggi di grup"
            elif rank == len(valid) and len(valid) >= 4:
                signal["flag"] = "terendah di grup"
        signal["peers"] = [{"symbol": sym, "value": v, "display": display(v, unit)}
                           for sym, v in valid]
        signals.append(signal)
    return signals


def _parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _growth(current, previous):
    current, previous = _num(current), _num(previous)
    if current is None or previous is None or previous == 0:
        return None
    if previous < 0:
        return None  # growth from a loss base is not a meaningful percentage
    return current / previous - 1


def quarter_signals(ticker, rows):
    """Latest quarter against the same quarter one year earlier."""
    dated = sorted(((d, row) for row in rows if isinstance(row, dict)
                    and (d := _parse_date(row.get("date")))), key=lambda item: item[0])
    if not dated:
        return [], []
    latest_date, latest = dated[-1]
    prior = next((row for d, row in dated
                  if d.year == latest_date.year - 1 and d.month == latest_date.month), None)
    source = f"Sectors /financials/quarterly/{ticker}/"
    signals = []
    for key, label in (("revenue", "Pendapatan kuartal terakhir, yoy"),
                       ("earnings", "Laba bersih kuartal terakhir, yoy")):
        growth = _growth(latest.get(key), (prior or {}).get(key)) if prior else None
        signal = {"id": f"quarter.{key}_yoy", "kind": "change", "label": label, "unit": "pct",
                  "value": growth, "display": display(growth, "pct"), "source": source,
                  "period": f"{latest_date.isoformat()} vs {prior.get('date') if prior else 'n.a.'}",
                  "flag": None}
        previous_value = _num((prior or {}).get(key))
        current_value = _num(latest.get(key))
        if growth is None and prior and previous_value is not None and previous_value < 0 \
                and current_value is not None:
            signal["note"] = ("berbalik dari rugi ke laba" if current_value > 0
                              else "masih rugi pada kedua periode")
            if current_value > 0:
                signal["flag"] = "berbalik ke laba"
        elif growth is not None and abs(growth) >= 0.25:
            signal["flag"] = "lonjakan" if growth > 0 else "penurunan tajam"
            if growth >= 5:
                signal["note"] = "basis pembanding tahun lalu sangat kecil; persentase tidak informatif"
        elif not prior:
            signal["note"] = "tidak ada kuartal yang sama tahun sebelumnya di data"
        signals.append(signal)
    table = [{"date": d.isoformat(),
              "revenue": display(_num(row.get("revenue")), "rp"),
              "earnings": display(_num(row.get("earnings")), "rp")}
             for d, row in dated[-5:]]
    return signals, table


def price_signals(ticker, daily_rows, index_rows):
    """Three-month price return, relative to IHSG, and recent volume."""
    rows = sorted((r for r in daily_rows if isinstance(r, dict) and _num(r.get("close"))),
                  key=lambda r: str(r.get("date")))
    if len(rows) < 2:
        return [], {}
    first, last = rows[0], rows[-1]
    stock_return = _num(last["close"]) / _num(first["close"]) - 1
    source = f"Sectors /daily/{ticker}/"
    signals = [{"id": "price.return_window", "kind": "change",
                "label": "Return harga pada jendela data", "unit": "pct",
                "value": stock_return, "display": display(stock_return, "pct"),
                "period": f"{first['date']} s.d. {last['date']}", "source": source, "flag": None}]
    index = sorted((r for r in index_rows if isinstance(r, dict) and _num(r.get("price"))),
                   key=lambda r: str(r.get("date")))
    in_window = [r for r in index if str(first["date"]) <= str(r["date"]) <= str(last["date"])]
    if len(in_window) >= 2:
        index_return = _num(in_window[-1]["price"]) / _num(in_window[0]["price"]) - 1
        relative = stock_return - index_return
        signal = {"id": "price.vs_ihsg", "kind": "change", "label": "Selisih return vs IHSG",
                  "unit": "pct", "value": relative, "display": display(relative, "pct"),
                  "period": f"{in_window[0]['date']} s.d. {in_window[-1]['date']}",
                  "source": source + " dan /index-daily/ihsg/", "flag": None}
        if abs(relative) >= 0.15:
            signal["flag"] = "jauh mengungguli IHSG" if relative > 0 else "jauh tertinggal dari IHSG"
        signals.append(signal)
    volumes = [_num(r.get("volume")) for r in rows if _num(r.get("volume"))]
    if len(volumes) >= 30:
        recent, base = statistics.mean(volumes[-10:]), statistics.mean(volumes[:-10])
        if base:
            ratio = recent / base
            signal = {"id": "price.volume_ratio", "kind": "change",
                      "label": "Volume 10 hari terakhir vs rata-rata sebelumnya", "unit": "x",
                      "value": ratio, "display": display(ratio, "x"), "source": source,
                      "flag": None}
            if ratio >= 1.5:
                signal["flag"] = "volume melonjak"
            elif ratio <= 0.6:
                signal["flag"] = "volume mengering"
            signals.append(signal)
    return signals, {"first": first, "last": last}


def flow_signals(ticker, rows):
    """Net foreign flow over the last 20 sessions and the whole window."""
    rows = sorted((r for r in rows if isinstance(r, dict) and
                   _num(r.get("net_foreign_inflow")) is not None),
                  key=lambda r: str(r.get("date")))
    if not rows:
        return []
    values = [_num(r["net_foreign_inflow"]) for r in rows]
    source = f"Sectors /foreign-flow/{ticker}/"
    recent = sum(values[-20:])
    total = sum(values)
    streak = 0
    for value in reversed(values):
        if value == 0 or (streak and (value > 0) != (values[-1] > 0)):
            break
        streak += 1
    signals = [
        {"id": "flow.net_20d", "kind": "flow", "label": "Arus bersih asing, 20 sesi terakhir",
         "unit": "rp", "value": recent, "display": display(recent, "rp"), "source": source,
         "period": f"{rows[max(0, len(rows) - 20)]['date']} s.d. {rows[-1]['date']}", "flag": None},
        {"id": "flow.net_window", "kind": "flow", "label": "Arus bersih asing, seluruh jendela data",
         "unit": "rp", "value": total, "display": display(total, "rp"), "source": source,
         "period": f"{rows[0]['date']} s.d. {rows[-1]['date']}", "flag": None},
        {"id": "flow.streak", "kind": "flow",
         "label": "Sesi berturut-turut dengan arah asing yang sama", "unit": "count",
         "value": streak, "display": f"{streak} sesi {'beli' if values[-1] > 0 else 'jual'} bersih",
         "source": source, "flag": "beruntun" if streak >= 5 else None},
    ]
    if recent and total and (recent > 0) != (total > 0):
        signals[0]["flag"] = "arah asing berbalik"
    return signals


def valuation_signals(ticker, history):
    """Current P/E against the company's own history and the Sectors peer average."""
    rows = sorted((r for r in history if isinstance(r, dict) and r.get("year") is not None),
                  key=lambda r: int(r["year"]))
    if not rows:
        return []
    current = rows[-1]
    source = f"Sectors /company/report/{ticker}/ valuation.historical_valuation"
    signals = []
    pe_now = _num(current.get("pe"))
    past = [_num(r.get("pe")) for r in rows[:-1] if (_num(r.get("pe")) or 0) > 0]
    if pe_now and pe_now > 0 and past:
        diff = pe_now / statistics.mean(past) - 1
        signal = {"id": "valuation.pe_vs_history", "kind": "valuation",
                  "label": "P/E saat ini vs rata-rata tahun sebelumnya", "unit": "pct",
                  "value": diff, "display": display(diff, "pct"), "source": source,
                  "period": f"{rows[0]['year']}–{current['year']}", "flag": None}
        if diff <= -0.33:
            signal["flag"] = "jauh di bawah rata-rata historis"
        elif diff >= 0.5:
            signal["flag"] = "jauh di atas rata-rata historis"
        signals.append(signal)
    peer_avg = _num(current.get("pe_peer_avg"))
    if pe_now and pe_now > 0 and peer_avg and peer_avg > 0:
        diff = pe_now / peer_avg - 1
        signal = {"id": "valuation.pe_vs_peer_avg", "kind": "valuation",
                  "label": "P/E vs rata-rata P/E peer (Sectors)", "unit": "pct",
                  "value": diff, "display": display(diff, "pct"), "source": source,
                  "flag": None}
        if abs(diff) >= 0.5:
            signal["flag"] = "premi besar ke peer" if diff > 0 else "diskon besar ke peer"
        signals.append(signal)
    return signals


def cross_signals(signals):
    """Combine two computed signals into a divergence check."""
    by_id = {s["id"]: s for s in signals}
    flow, price = by_id.get("flow.net_window"), by_id.get("price.return_window")
    if not flow or not price or flow["value"] is None or price["value"] is None:
        return []
    diverges = (flow["value"] > 0) != (price["value"] > 0) and abs(price["value"]) >= 0.05
    return [{"id": "cross.flow_vs_price", "kind": "cross",
             "label": "Arah arus asing vs arah harga", "unit": "text",
             "value": "berlawanan" if diverges else "searah",
             "display": "berlawanan" if diverges else "searah",
             "source": f"{flow['source']} dan {price['source']}",
             "flag": "divergensi asing vs harga" if diverges else None}]
