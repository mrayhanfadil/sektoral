"""Normalized evidence register: official actuals + guidance + news + assumptions.

Built before asking an agent for forecasts. Every run uses only
information published by ``as_of``; an announced future milestone is
allowed only when its announcement was already public (expected event
date recorded separately from publication date). Official filings and
guidance take precedence for issuer numbers; media motivates a bounded
analyst assumption but never becomes an issuer actual/guidance figure.
"""
from __future__ import annotations

from datetime import date


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def official_actual_row(evidence):
    """Base-period level + reconciliation row for the evidence register."""
    actual = (evidence or {}).get("latest_actual") or {}
    if not actual:
        return None
    return {
        "kind": "official_actual",
        "use": "base-period level and reconciliation",
        "period": actual.get("period"),
        "period_end": actual.get("period_end"),
        "published_at": actual.get("published_at"),
        "value": actual.get("metrics"),
        "unit": actual.get("unit"),
        "source": actual.get("source_url"),
        "source_title": actual.get("source_title"),
        "page": actual.get("page"),
    }


def guidance_rows(evidence):
    """Forward operating constraints from company guidance/contracts."""
    out = []
    for row in (evidence or {}).get("management_guidance") or []:
        if not isinstance(row, dict):
            continue
        out.append({
            "kind": "company_guidance",
            "use": "forward operating constraint",
            "name": row.get("name"),
            "value": row.get("value"),
            "unit": row.get("unit"),
            "effective_years": row.get("period") or row.get("fiscal_year"),
            "scope": row.get("scope"),
            "conditions": row.get("conditions"),
            "source": row.get("source_url"),
            "published_at": row.get("published_at") or row.get("source_date"),
        })
    return out


def news_rows(register_articles, news_full=()):
    """Candidate future events with title/URL/publisher/dates/text excerpt."""
    deepdive = {str(i.get("source_url") or ""): i for i in (news_full or [])
                if isinstance(i, dict)}
    out = []
    for article in register_articles or []:
        if not isinstance(article, dict):
            continue
        url = str(article.get("source") or "")
        full = deepdive.get(url) or {}
        out.append({
            "kind": "tavily_article" if (article.get("origin") == "tavily" or
                                         "tavily" in (article.get("origins") or []))
            else "sectors_article",
            "use": "candidate future event",
            "register_id": article.get("register_id"),
            "title": article.get("title"),
            "url": url,
            "publisher": article.get("publisher"),
            "published_at": article.get("timestamp"),
            "text_excerpt": str(article.get("body") or "")[:1400],
            "full_text_status": full.get("fetch_status"),
            "full_text_excerpt": str(full.get("full_text") or "")[:2000],
            "origins": article.get("origins"),
            "event_key": article.get("event_key"),
        })
    return out


def assumption_rows(plan):
    """Quantified scenario judgments with driver/year/base/change/uncertainty."""
    out = []
    for effect in (plan or {}).get("news_effects") or []:
        if not isinstance(effect, dict):
            continue
        out.append({
            "kind": "analyst_assumption",
            "use": "quantified scenario judgment",
            "driver": effect.get("driver"),
            "fiscal_years": effect.get("years"),
            "change": effect.get("change"),
            "base_value": effect.get("base_value"),
            "rationale": effect.get("rationale"),
            "source_ids": [effect.get("source_url")] if effect.get("source_url") else [],
            "uncertainty": effect.get("uncertainty"),
            "assumption_type": effect.get("assumption_type") or "analyst_judgment",
        })
    return out


def build(ticker, as_of, intake=None, register=None, news_full=(), plan=None):
    """Assemble the full normalized register; enforce the as_of cutoff."""
    intake = intake or {}
    cutoff = _day(as_of or intake.get("as_of"))
    evidence = intake.get("official_evidence") or {}
    articles = (register or {}).get("articles") if isinstance(register, dict) else (register or [])
    rows = []
    actual = official_actual_row(evidence)
    if actual:
        rows.append(actual)
    rows.extend(guidance_rows(evidence))
    rows.extend(news_rows(articles, news_full))
    rows.extend(assumption_rows(plan))
    # No look-ahead: every dated row must be published by as_of.
    violations = []
    if cutoff is not None:
        for row in rows:
            pub = row.get("published_at")
            if pub and _day(pub) is not None and _day(pub) > cutoff:
                violations.append(f"{row.get('kind')}: {pub} after as-of {cutoff.isoformat()}")
    return {"ticker": str(ticker or "").upper(), "as_of": cutoff.isoformat() if cutoff else str(as_of),
            "rows": rows, "violations": violations,
            "counts": {kind: sum(1 for r in rows if r.get("kind") == kind)
                       for kind in ("official_actual", "company_guidance",
                                    "sectors_article", "tavily_article",
                                    "analyst_assumption")}}
