"""Tools the analyst agent can call.

The Sectors tools mirror Sectors API resources but read the local Sectors
snapshot (``data/sectors_cache.db``) through ``app.cache`` /
``agents.estimator.tools``. No tool imports ``app.sectors`` (the only module
allowed to reach the Sectors API), so an agent run never spends Sectors API
credits. ``web_news`` is the one outside source: dated Tavily headlines used as
narrative context only, never as a number in a signal.
"""
from __future__ import annotations

import re

from agents.estimator import tools as local_data
from app import cache, tavily

from . import signals as S

# name -> (description for the model, argument schema hint)
TOOLS = {
    "find_peers": ("Susun grup peer emiten: tabel peer Sectors bila ada, jika tidak "
                   "emiten lain di data lokal dengan sub-industri/sub-sektor sama.", "{}"),
    "rank_peers": ("Hitung peringkat emiten di grup peer untuk metrik pilihan. Metrik: " +
                   ", ".join(S.PEER_METRICS) + ".", '{"metrics": ["roe", "pe", ...]}'),
    "quarterly_financials": ("Pendapatan dan laba kuartalan; bandingkan kuartal terakhir "
                             "dengan kuartal yang sama tahun sebelumnya.", "{}"),
    "price_history": ("Harga harian sekitar tiga bulan terakhir, dibandingkan dengan IHSG, "
                      "plus perubahan volume.", "{}"),
    "foreign_flow": ("Arus bersih investor asing harian: 20 sesi terakhir, seluruh jendela, "
                     "dan sesi beruntun.", "{}"),
    "valuation_history": ("P/E saat ini dibanding riwayat P/E emiten dan rata-rata P/E peer.", "{}"),
    "news": ("Judul berita bertanggal yang menyebut emiten ini.", "{}"),
    "web_news": ("Konteks berita web (Tavily, media bisnis Indonesia) dalam jendela sebelum "
                 "tanggal data pasar. Hanya konteks naratif untuk menjelaskan sinyal, bukan "
                 "sumber angka; setiap kesimpulan tetap harus mengutip sinyal Sectors.", "{}"),
}
WEB_SOURCE = "Tavily (web), bukan data Sectors"


class ToolError(ValueError):
    """A tool call the host refuses; the message is shown to the agent."""


def local_tickers():
    """Tickers with a full company report in the local Sectors data."""
    found = set()
    for endpoint in cache.endpoints():
        match = re.fullmatch(r"/company/report/([A-Z0-9.-]{1,10})/", endpoint)
        if match:
            found.add(match.group(1))
    return sorted(found)


def overview(ticker):
    report = cache.company_report(ticker) or {}
    ov = report.get("overview") or {}
    return {"ticker": ticker, "name": report.get("company_name") or ticker,
            "sector": ov.get("sector"), "sub_sector": ov.get("sub_sector"),
            "sub_industry": ov.get("sub_industry"),
            "market_date": ov.get("latest_close_date"),
            "last_close": ov.get("last_close_price"),
            "has_peer_table": bool(_peer_table(report)),
            "available": {name: _available(ticker, name) for name in TOOLS}}


def _available(ticker, tool):
    endpoint = {"quarterly_financials": f"/financials/quarterly/{ticker}/",
                "price_history": f"/daily/{ticker}/",
                "foreign_flow": f"/foreign-flow/{ticker}/"}.get(tool)
    if tool == "web_news":
        return tavily.configured()
    if endpoint is None:
        return True
    return local_data.cache_get(ticker, endpoint) is not None


def _peer_table(report):
    peers = report.get("peers") or []
    if peers and isinstance(peers[0], dict):
        data = peers[0].get("peers_data") or {}
        companies = data.get("companies") or []
        if len(companies) >= 3:
            return data
    return None


def _latest(rows, key="year"):
    rows = [r for r in rows or [] if isinstance(r, dict) and r.get(key) is not None]
    return max(rows, key=lambda r: str(r[key])) if rows else {}


def _row_from_report(ticker, report, is_self=False):
    ov = report.get("overview") or {}
    financials = _latest((report.get("financials") or {}).get("historical_financials"))
    valuation = _latest((report.get("valuation") or {}).get("historical_valuation"))
    return S.peer_row(ticker, report.get("company_name"), market_cap=ov.get("market_cap"),
                      pe=valuation.get("pe"), pb=valuation.get("pb"),
                      net_income=financials.get("earnings"), revenue=financials.get("revenue"),
                      equity=financials.get("total_equity"), assets=financials.get("total_assets"),
                      liabilities=financials.get("total_liabilities"),
                      year=financials.get("year"), is_self=is_self)


def find_peers(ticker):
    report = cache.company_report(ticker) or {}
    table = _peer_table(report)
    if table:
        rows = []
        for company in table["companies"]:
            if not isinstance(company, dict):
                continue
            is_self = "self" in (company.get("group") or [])
            rows.append(S.peer_row(
                company.get("symbol"), company.get("company_name"),
                market_cap=company.get("market_cap"), pe=company.get("pe_ttm"),
                pb=company.get("pb_mrq"), net_income=company.get("net_income"),
                revenue=company.get("total_revenue"), equity=company.get("total_equity"),
                assets=company.get("total_assets"), liabilities=company.get("total_liabilities"),
                mcap_change_1y=company.get("yearly_mcap_chg"), year=company.get("year"),
                is_self=is_self))
        group = table.get("group_name") or {}
        return {"source": f"Sectors /company/report/{ticker}/ peers",
                "basis": "tabel peer Sectors",
                "group": group.get("sub_industry") or group.get("sub_sector") or "",
                "rows": rows}
    reports = {t: cache.company_report(t) or {} for t in local_tickers()}
    # Another company's Sectors peer table that lists this ticker is the next
    # best source: same peer definition, one hop away.
    for other, other_report in sorted(reports.items()):
        other_table = _peer_table(other_report) if other != ticker else None
        symbols = [str((c or {}).get("symbol") or "").replace(".JK", "")
                   for c in (other_table or {}).get("companies") or []]
        if ticker in symbols:
            rows = [S.peer_row(
                c.get("symbol"), c.get("company_name"), market_cap=c.get("market_cap"),
                pe=c.get("pe_ttm"), pb=c.get("pb_mrq"), net_income=c.get("net_income"),
                revenue=c.get("total_revenue"), equity=c.get("total_equity"),
                assets=c.get("total_assets"), liabilities=c.get("total_liabilities"),
                mcap_change_1y=c.get("yearly_mcap_chg"), year=c.get("year"),
                is_self=str(c.get("symbol") or "").replace(".JK", "") == ticker)
                for c in other_table["companies"] if isinstance(c, dict)]
            group = other_table.get("group_name") or {}
            return {"source": f"Sectors /company/report/{other}/ peers",
                    "basis": f"tabel peer Sectors milik {other} yang memuat {ticker}",
                    "group": group.get("sub_industry") or group.get("sub_sector") or "",
                    "rows": rows}
    own = report.get("overview") or {}
    for level in ("sub_industry", "sub_sector", "sector"):
        key = own.get(level)
        members = [t for t, rep in reports.items()
                   if key and (rep.get("overview") or {}).get(level) == key]
        if ticker in members and len(members) >= 3:
            rows = [_row_from_report(t, reports[t], is_self=(t == ticker)) for t in members]
            return {"source": "Sectors /company/report/{emiten}/ (data lokal, "
                              f"{len(members)} emiten)",
                    "basis": f"emiten data lokal dengan {level.replace('_', '-')} sama",
                    "group": key, "rows": rows}
    return {"source": "", "basis": "tidak ada grup peer", "group": "", "rows": []}


def execute(name, ticker, args, state):
    """Run one tool. Returns (compact result for the model, new signals)."""
    if name not in TOOLS:
        raise ToolError(f"tool {name!r} tidak dikenal")
    args = args if isinstance(args, dict) else {}
    if name == "find_peers":
        peers = find_peers(ticker)
        state["peers"] = peers
        if not peers["rows"]:
            raise ToolError("tidak ada grup peer di data lokal untuk emiten ini")
        return ({"basis": peers["basis"], "group": peers["group"],
                 "members": [r["symbol"] for r in peers["rows"]]}, [])
    if name == "rank_peers":
        peers = state.get("peers") or find_peers(ticker)
        state["peers"] = peers
        if not peers["rows"]:
            raise ToolError("tidak ada grup peer untuk diperingkat")
        metrics = [m for m in (args.get("metrics") or []) if m in S.PEER_METRICS]
        if not metrics:
            raise ToolError("sebutkan minimal satu metrik valid: " + ", ".join(S.PEER_METRICS))
        ranked = S.rank_peers(peers["rows"], metrics[:6], peers["source"])
        return ([_brief(s) for s in ranked], ranked)
    if name == "quarterly_financials":
        payload = local_data.cache_get(ticker, f"/financials/quarterly/{ticker}/")
        rows = (payload or {}).get("data") or []
        if not rows:
            raise ToolError("data kuartalan tidak tersedia")
        found, table = S.quarter_signals(ticker, rows)
        return ({"signals": [_brief(s) for s in found], "last_quarters": table}, found)
    if name == "price_history":
        payload = local_data.cache_get(ticker, f"/daily/{ticker}/")
        rows = (payload or {}).get("data") or []
        if not rows:
            raise ToolError("harga harian tidak tersedia")
        index_rows = (cache.first("/index-daily/ihsg/") or {}).get("data") or []
        found, _ = S.price_signals(ticker, rows, index_rows)
        return ({"signals": [_brief(s) for s in found]}, found)
    if name == "foreign_flow":
        payload = local_data.cache_get(ticker, f"/foreign-flow/{ticker}/")
        rows = (payload or {}).get("data") or []
        if not rows:
            raise ToolError("data arus asing tidak tersedia")
        found = S.flow_signals(ticker, rows)
        return ({"signals": [_brief(s) for s in found]}, found)
    if name == "valuation_history":
        history = ((cache.company_report(ticker) or {}).get("valuation") or {}).get(
            "historical_valuation") or []
        found = S.valuation_signals(ticker, history)
        if not found:
            raise ToolError("riwayat valuasi tidak cukup")
        return ({"signals": [_brief(s) for s in found]}, found)
    if name == "news":
        payload = local_data.cache_get(ticker, "/news/") or {}
        items = [{"title": str(row.get("title") or "")[:200],
                  "date": str(row.get("timestamp") or "")[:10],
                  "source": str(row.get("source") or "")}
                 for row in (payload.get("results") or []) if isinstance(row, dict)][:6]
        state["news"] = items
        if not items:
            raise ToolError("tidak ada berita yang menyebut emiten ini")
        signal = {"id": "news.count", "kind": "news", "label": "Berita bertanggal yang menyebut emiten",
                  "unit": "count", "value": len(items), "display": str(len(items)),
                  "source": "Sectors /news/", "flag": None}
        return ({"headlines": [{"title": i["title"], "date": i["date"]} for i in items]}, [signal])
    if name == "web_news":
        if not tavily.configured():
            raise ToolError("konteks berita web tidak dikonfigurasi")
        info = cache.company_report(ticker) or {}
        market_date = (info.get("overview") or {}).get("latest_close_date")
        try:
            found = tavily.news_context(ticker, info.get("company_name") or ticker, market_date)
        except tavily.TavilyError as error:
            raise ToolError(str(error)) from None
        items = found["items"]
        state["web_news"] = items
        state["web_window"] = found.get("window")
        if not items:
            raise ToolError(f"tidak ada berita web bertanggal dalam jendela {found.get('window')}")
        web_signals = [{"id": f"web.{i}", "kind": "web", "label": item["title"],
                        "display": f"{item['date']} · {item['domain']}", "value": None,
                        "note": item["snippet"][:200], "url": item["url"],
                        "source": WEB_SOURCE, "flag": None}
                       for i, item in enumerate(items)]
        return ({"window": found.get("window"), "articles": [
            {"id": sig["id"], "title": item["title"], "date": item["date"],
             "domain": item["domain"], "snippet": item["snippet"]}
            for sig, item in zip(web_signals, items)]}, web_signals)
    raise ToolError(f"tool {name!r} belum diimplementasikan")


def _brief(signal):
    """What the model sees of a signal: id, meaning, formatted value, rank and flag."""
    brief = {"id": signal["id"], "label": signal["label"], "value": signal["display"]}
    for key in ("note", "flag", "period", "median_display"):
        if signal.get(key):
            brief["median" if key == "median_display" else key] = signal[key]
    return brief
