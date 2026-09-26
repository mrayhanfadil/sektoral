"""Normalized evidence register: official actuals + guidance + news + assumptions.

Built before asking an agent for forecasts. Every run uses only
information published by ``as_of``; an announced future milestone is
allowed only when its announcement was already public (expected event
date recorded separately from publication date). Official filings and
guidance take precedence for issuer numbers; media motivates a bounded
analyst assumption but never becomes an issuer actual/guidance figure.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from urllib.parse import urlsplit

from . import house_assumptions


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _has_http_source(value):
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlsplit(value.strip())
        return (parsed.scheme.lower() in {"http", "https"} and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None)
    except ValueError:
        return False


def _row_identity(row):
    """Stable identity from evidence kind, period, source, metric, and scope."""
    value = row.get("value")
    metric = (row.get("name") or row.get("metric") or row.get("driver") or
              row.get("title") or (sorted(value) if isinstance(value, dict) else None))
    return {
        "kind": row.get("kind"),
        "period": row.get("period") or row.get("effective_years") or row.get("fiscal_years"),
        "period_end": row.get("period_end"),
        "published_at": row.get("published_at"),
        "source": row.get("source") or row.get("url") or row.get("source_ids"),
        "metric": metric,
        "scope": row.get("scope"),
        "unit": row.get("unit"),
    }


def with_row_ids(register):
    """Return a copy whose rows carry deterministic reviewer-selectable IDs."""
    if not isinstance(register, dict):
        return register
    result = dict(register)
    rows = result.get("rows")
    if not isinstance(rows, list):
        return result
    counts = {}
    identified = []
    for row in rows:
        if not isinstance(row, dict):
            identified.append(row)
            continue
        identity = _row_identity(row)
        canonical = json.dumps(identity, sort_keys=True, ensure_ascii=False,
                                default=str, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).hexdigest()[:20]
        prefix = f"evidence:{str(row.get('kind') or 'unknown')}:{digest}"
        occurrence = counts.get(prefix, 0) + 1
        counts[prefix] = occurrence
        row_id = prefix if occurrence == 1 else f"{prefix}:{occurrence}"
        identified.append({**row, "row_id": row_id})
    result["rows"] = identified
    return result


def release_blockers(register):
    """Return fail-closed publication blockers for a normalized register."""
    if not isinstance(register, dict):
        return ["evidence register is missing or invalid"]
    blockers = []
    if register.get("error"):
        blockers.append(f"evidence register construction failed: {register['error']}")
    violations = register.get("violations")
    if violations is not None and not isinstance(violations, list):
        blockers.append("evidence register violations are invalid")
    else:
        blockers.extend(f"evidence register violation: {item}" for item in violations or [])
    critical = register.get("critical_violations")
    if critical is not None and not isinstance(critical, list):
        blockers.append("evidence register critical violations are invalid")
    else:
        blockers.extend(f"evidence register critical violation: {item}"
                        for item in critical or [])
    rows = register.get("rows")
    if not isinstance(rows, list):
        blockers.append("evidence register rows are invalid")
    elif not rows:
        blockers.append("evidence register contains no eligible source rows")
    if not _day(register.get("as_of")):
        blockers.append("evidence register report as-of date is missing or invalid")
    return list(dict.fromkeys(blockers))


def add_plan(register, plan):
    """Attach the post-evidence analyst plan without rebuilding source rows."""
    if not isinstance(register, dict):
        return {"rows": [], "violations": [], "critical_violations": [],
                "error": "pre-agent evidence register is missing or invalid"}
    result = dict(register)
    result["rows"] = list(register.get("rows") or []) + assumption_rows(plan)
    counts = dict(register.get("counts") or {})
    counts["analyst_assumption"] = sum(
        row.get("kind") == "analyst_assumption" for row in result["rows"]
        if isinstance(row, dict))
    result["counts"] = counts
    return with_row_ids(result)


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


def filing_rows(evidence):
    """Official filing pages the pack's ledgers cite (``filing_sources``).

    Each key becomes one row whose ``name`` is that key, so a ledger record can
    cite a filing by key and resolve it to the row's canonical ``row_id``.
    """
    sources = (evidence or {}).get("filing_sources")
    out = []
    for key, source in sorted((sources or {}).items()) if isinstance(sources, dict) else ():
        if not isinstance(source, dict):
            continue
        out.append({
            "kind": "official_filing",
            "use": "source of a reviewed normalization or share-ledger record",
            "name": key,
            "period": source.get("period"),
            "published_at": source.get("published_at"),
            "available_at": source.get("available_at"),
            "currency": source.get("currency"),
            "unit": source.get("unit"),
            "source": source.get("url"),
            "source_title": source.get("title"),
            "page": source.get("page"),
        })
    return out


def driver_source_rows(ticker, as_of):
    """Sources of the ticker's operating or bank driver file known by ``as_of``.

    Each becomes a ``driver_source`` row named by its key, so every driver in
    the driver-to-value table resolves to a register row.
    """
    from . import bank_drivers, operating_model
    out = []
    for loader in (operating_model.load, bank_drivers.load):
        try:
            data = loader(ticker, as_of) if ticker and as_of else None
        except (OSError, ValueError):
            data = None
        for key, source in sorted(((data or {}).get("sources") or {}).items()):
            out.append({"kind": "driver_source", "use": "source of a forward driver",
                        "name": key, "published_at": source.get("published_at"),
                        "source": source.get("url"), "source_title": source.get("title"),
                        "page": source.get("page")})
    return out


def row_ids_by_name(register, kind="official_filing"):
    """``{name: row_id}`` for one row kind of a register with row IDs."""
    return {row["name"]: row["row_id"] for row in (register or {}).get("rows") or []
            if isinstance(row, dict) and row.get("kind") == kind
            and row.get("name") and row.get("row_id")}


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
    # A filing published after the Report Date did not exist yet: leave it out
    # rather than list it as a violation (point-in-time, like the pack loader).
    rows.extend(row for row in filing_rows(evidence)
                if cutoff is None or (_day(row.get("published_at")) or cutoff) <= cutoff)
    rows.extend(driver_source_rows(ticker, cutoff.isoformat() if cutoff else None))
    rows.extend(guidance_rows(evidence))
    rows.extend(news_rows(articles, news_full))
    rows.extend(assumption_rows(plan))
    # Critical provenance failures are kept as named register violations so
    # neither an agent nor a later release check can treat them as absence.
    violations = []
    critical_violations = []
    if cutoff is None:
        critical_violations.append(f"invalid report as-of date: {as_of!r}")
    critical_violations.extend(house_assumptions.deviation_violations(evidence))
    for row in rows:
        kind = row.get("kind")
        pub = row.get("published_at")
        date_required = kind in {"official_actual", "official_filing", "driver_source",
                                 "company_guidance",
                                 "sectors_article", "tavily_article"}
        if pub in (None, ""):
            if date_required:
                critical_violations.append(f"{kind}: missing published_at")
        else:
            published = _day(pub)
            if published is None:
                critical_violations.append(f"{kind}: malformed published_at {pub!r}")
            elif cutoff is not None and published > cutoff:
                violations.append(
                    f"{kind}: {pub} after as-of {cutoff.isoformat()}")

        if kind in {"official_actual", "official_filing", "driver_source", "company_guidance",
                    "sectors_article", "tavily_article"}:
            source = row.get("source") or row.get("url")
            if not _has_http_source(source):
                critical_violations.append(f"{kind}: source URL is missing or invalid")
        if kind == "official_actual":
            if not row.get("period"):
                critical_violations.append("official_actual: material period is missing")
            if not row.get("unit"):
                critical_violations.append("official_actual: material unit is missing")
            if not isinstance(row.get("value"), dict) or not row["value"]:
                critical_violations.append("official_actual: material metrics are missing")
        elif kind == "company_guidance" and isinstance(row.get("value"), (int, float)):
            if not row.get("unit"):
                critical_violations.append("company_guidance: material unit is missing")
            if not row.get("effective_years"):
                critical_violations.append("company_guidance: material period is missing")
    return with_row_ids({"ticker": str(ticker or "").upper(),
            "as_of": cutoff.isoformat() if cutoff else str(as_of),
            "rows": rows, "violations": violations,
            "critical_violations": list(dict.fromkeys(critical_violations)),
            "counts": {kind: sum(1 for r in rows if r.get("kind") == kind)
                       for kind in ("official_actual", "official_filing",
                                    "company_guidance", "sectors_article",
                                    "tavily_article", "analyst_assumption")}})
