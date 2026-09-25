"""Public view of an audit trace (``<T>-trace.json``) for the web app.

The trace on disk keeps everything the run saw. The browser gets the same
fields the standalone trace HTML shows (see ``research._trace_html``), each
typed and length-bounded; nothing else leaves the server.
"""
from __future__ import annotations

from .jobs import http_url, public_intel, text


def _list(value):
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _status(report: dict) -> dict:
    published = str(report.get("status") or "").startswith("distributable")
    return {
        "release_status": text(report.get("status"), 48),
        "published": published,
        "rating": text(report.get("rating"), 30) if published else None,
        "target_price": report.get("target_price") if published and isinstance(
            report.get("target_price"), (int, float)) else None,
        "method": text(str(report.get("target_method") or "").split(" [")[0], 200) if published else None,
        "as_of": text(report.get("as_of"), 20),
        "market_price_date": text(report.get("market_price_date"), 20),
    }


def _research(research: dict) -> dict:
    brief = research.get("document") if isinstance(research.get("document"), dict) else {}
    agent = brief.get("agent_trace") or research.get("agent_trace") or {}
    return {
        "summary": text(brief.get("summary"), 1200),
        "endpoints": [text(e, 120) for e in (agent.get("selected_cache_endpoints") or [])[:40]
                      if isinstance(e, str)],
        "insights": [{
            "title": text(i.get("title"), 200),
            "observation": text(i.get("observation"), 900),
            "implication": text(i.get("implication"), 900),
            "caveat": text(i.get("caveat"), 600),
            "citations": [{"endpoint": text(c.get("endpoint"), 120), "field_path": text(c.get("field_path"), 160),
                           "value": text(c.get("value"), 180)} for c in _list(i.get("citations"))[:12]],
        } for i in _list(brief.get("insights"))[:8]],
        "limitations": [text(x, 400) for x in (brief.get("limitations") or [])[:10] if isinstance(x, str)],
    }


def _news(sources: dict) -> dict:
    search = sources.get("search") if isinstance(sources.get("search"), dict) else {}
    queries = search.get("queries") or ([search.get("query")] if search.get("query") else [])
    rejected = _list(sources.get("rejected"))
    return {
        "search": {"status": text(search.get("status"), 40), "as_of": text(search.get("as_of"), 20),
                   "queries": [text(q.get("query") if isinstance(q, dict) else q, 120)
                               for q in queries[:6] if q]},
        "articles": [{"id": text(a.get("register_id"), 40), "date": text(a.get("timestamp"), 30),
                      "origins": [text(o, 30) for o in (a.get("origins") or [])[:4]],
                      "title": text(a.get("title"), 200), "url": http_url(a.get("source"))}
                     for a in _list(sources.get("articles"))[:30]],
        "rejected": [{"title": text(r.get("title"), 160), "reason": text(r.get("reason"), 200)}
                     for r in rejected[:10]],
        "rejected_total": len(rejected),
    }


def _forecast(result: dict) -> dict:
    plan = result.get("plan") if isinstance(result.get("plan"), dict) else {}
    interim = plan.get("interim_scenario") if isinstance(plan.get("interim_scenario"), dict) else {}

    def number(value):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    return {
        "status": text(result.get("status"), 60),
        "problems": [text(p, 300) for p in (result.get("problems") or [])[:8] if isinstance(p, str)],
        "news_effects": [{
            "driver": text(e.get("driver"), 80), "change": text(e.get("change"), 80),
            "years": [text(y, 8) for y in (e.get("years") or [])[:6]],
            "rationale": text(e.get("rationale"), 600), "date": text(e.get("timestamp"), 30),
            "url": http_url(e.get("source_url")), "factual_basis": text(e.get("factual_basis"), 400),
            "mechanism": text(e.get("mechanism"), 400), "uncertainty": text(e.get("uncertainty"), 300),
        } for e in _list(plan.get("news_effects"))[:12]],
        "interim": {"rationale": text(interim.get("rationale"), 900),
                    "published_at": text(interim.get("published_at"), 30),
                    "url": http_url(interim.get("source_url"))} if interim else None,
        "outyears": [{
            "year": text(r.get("year"), 8),
            "revenue_growth_pct": number(r.get("revenue_growth_pct")),
            "ebitda_margin_pct": number(r.get("ebitda_margin_pct")),
            "net_income_margin_pct": number(r.get("net_income_margin_pct")),
            "capex_to_revenue_pct": number(r.get("capex_to_revenue_pct")),
            "rationale": text(r.get("rationale"), 600),
            "source_ids": [text(s, 40) for s in (r.get("source_ids") or [])[:8]],
        } for r in _list(plan.get("outyear_scenario"))[:6]],
    }


def _deepdive(items) -> list[dict]:
    out = []
    for item in _list(items)[:20]:
        fetched = str(item.get("fetch_status") or "") == "fetched"
        out.append({"title": text(item.get("title"), 200), "date": text(item.get("timestamp"), 30),
                    "url": http_url(item.get("source_url")), "status": text(item.get("fetch_status"), 30),
                    "length": item.get("full_length") if isinstance(item.get("full_length"), int) else 0,
                    "preview": text(item.get("full_text"), 400) if fetched else None})
    return out


def build(audit: dict | None) -> dict | None:
    """The browser-safe trace, or None when ``audit`` is not a trace."""
    if not isinstance(audit, dict) or not audit.get("ticker"):
        return None
    analyst = audit.get("analyst") if isinstance(audit.get("analyst"), dict) else {}
    return {
        "ticker": text(audit.get("ticker"), 12),
        "report": _status(audit.get("report") if isinstance(audit.get("report"), dict) else {}),
        "analyst": public_intel(analyst),
        "analyst_problems": [text(p, 300) for p in (analyst.get("problems") or [])[:6] if isinstance(p, str)],
        "research": _research(audit.get("research") if isinstance(audit.get("research"), dict) else {}),
        "news": _news(audit.get("news_sources") if isinstance(audit.get("news_sources"), dict) else {}),
        "forecast": _forecast(audit.get("forecast_assumptions")
                              if isinstance(audit.get("forecast_assumptions"), dict) else {}),
        "deepdive": _deepdive(audit.get("news_deepdive")),
    }
