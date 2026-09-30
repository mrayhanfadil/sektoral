"""Public view of an audit trace (``<T>-trace.json``) for the web app.

The trace on disk keeps everything the run saw. The browser gets the same
fields the standalone trace HTML shows (see ``research._trace_html``), each
typed and length-bounded; nothing else leaves the server.
"""
from __future__ import annotations

import re

from .jobs import http_url, public_intel, text


def _list(value):
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


# The analyst validator's "...; hapus kata: a, b" / "...; hapus: 12, 3,5%" and
# "token non-Indonesia dihapus: x, y": what the model had to drop, as a list.
_REMOVED = re.compile(r"(?:; hapus(?: kata)?|(?<= dihapus)): ([^;]*)")


def problem_notes(problems) -> list[dict]:
    """Analyst validator notes as {message, removed}: the note without its
    word lists, and the words it names to remove (stored notes are strings)."""
    notes = []
    for problem in (problems if isinstance(problems, list) else [])[:6]:
        if not isinstance(problem, str):
            continue
        removed = [word.strip() for found in _REMOVED.findall(problem)
                   for word in found.split(", ") if word.strip()]
        message = _REMOVED.sub("", problem).strip() or problem
        notes.append({"message": text(message, 300),
                      "removed": [text(word, 60) for word in removed[:12]]})
    return notes


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
            # English twins the agent wrote beside each field; None when absent.
            "title_en": text(i.get("title_en"), 200),
            "observation_en": text(i.get("observation_en"), 900),
            "implication_en": text(i.get("implication_en"), 900),
            "caveat_en": text(i.get("caveat_en"), 600),
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
            # English twins (#34); None for plans written before them.
            "rationale_en": text(e.get("rationale_en"), 600),
            "factual_basis_en": text(e.get("factual_basis_en"), 400),
            "mechanism_en": text(e.get("mechanism_en"), 400),
            "uncertainty_en": text(e.get("uncertainty_en"), 300),
        } for e in _list(plan.get("news_effects"))[:12]],
        "interim": {"rationale": text(interim.get("rationale"), 900),
                    "rationale_en": text(interim.get("rationale_en"), 900),
                    "published_at": text(interim.get("published_at"), 30),
                    "url": http_url(interim.get("source_url"))} if interim else None,
        "outyears": [{
            "year": text(r.get("year"), 8),
            "revenue_growth_pct": number(r.get("revenue_growth_pct")),
            "ebitda_margin_pct": number(r.get("ebitda_margin_pct")),
            "net_income_margin_pct": number(r.get("net_income_margin_pct")),
            "capex_to_revenue_pct": number(r.get("capex_to_revenue_pct")),
            "rationale": text(r.get("rationale"), 600),
            "rationale_en": text(r.get("rationale_en"), 600),
            "source_ids": [text(s, 40) for s in (r.get("source_ids") or [])[:8]],
        } for r in _list(plan.get("outyear_scenario"))[:6]],
        # Bank Driver Scenario (financial_ddm): the interim-year H2 drivers and
        # the four out-years, in percent.
        "bank_drivers": [{
            "year": text(r.get("year"), 8),
            **{key: number(r.get(key)) for key in (
                "loan_growth_pct", "nim_pct", "non_ii_to_nii_pct", "cost_to_income_pct",
                "cost_of_credit_pct", "deposit_growth_pct")},
            "rationale": text(r.get("rationale"), 600),
            "rationale_en": text(r.get("rationale_en"), 600),
            "source_ids": [text(s, 40) for s in (r.get("source_ids") or [])[:8]],
        } for r in [(plan.get("earnings_scenario") or {}).get("bank_drivers")]
            + _list(plan.get("bank_outyear_scenario"))[:4] if isinstance(r, dict)],
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


def _manifest(value: object) -> dict | None:
    """Whitelisted identity for the source and rendered artifact bundle."""
    if not isinstance(value, dict):
        return None
    working = value.get("working_tree") if isinstance(value.get("working_tree"), dict) else {}
    model = value.get("model") if isinstance(value.get("model"), dict) else {}
    artifact_hashes = value.get("artifacts") if isinstance(value.get("artifacts"), dict) else {}
    source_packs = value.get("source_pack_sha256") if isinstance(
        value.get("source_pack_sha256"), dict) else {}
    cache_hashes = value.get("cache_snapshot_sha256") if isinstance(
        value.get("cache_snapshot_sha256"), dict) else {}
    policy_snapshot = value.get("release_policy") if isinstance(value.get("release_policy"), dict) else {}
    policy_body = policy_snapshot.get("policy") if isinstance(policy_snapshot.get("policy"), dict) else {}
    house_snapshot = (value.get("house_assumptions")
                      if isinstance(value.get("house_assumptions"), dict) else {})
    house_body = (house_snapshot.get("policy")
                  if isinstance(house_snapshot.get("policy"), dict) else {})
    house_rates = (house_body.get("discount_rates")
                   if isinstance(house_body.get("discount_rates"), dict) else {})

    def house_currency(code):
        source = house_rates.get(code) if isinstance(house_rates.get(code), dict) else {}
        return {key: source.get(key) for key in (
            "risk_free", "risk_free_basis", "country_risk_premium", "beta",
            "equity_risk_premium", "cost_of_debt_pretax", "cost_of_debt_basis",
            "terminal_growth", "growth_sensitivity", "rate_sensitivity")}

    artifacts = {text(kind, 20): {
        "file": text(row.get("file"), 80), "sha256": text(row.get("sha256"), 64),
    } for kind, row in artifact_hashes.items() if isinstance(row, dict)}
    return {
        "publication_id": text(value.get("publication_id"), 64),
        "code_revision": text(value.get("code_revision"), 40),
        "source_tree_sha256": text(value.get("source_tree_sha256"), 64),
        "working_tree": {"dirty": working.get("dirty") if isinstance(
            working.get("dirty"), bool) else None,
            "sha256": text(working.get("sha256"), 64)},
        "as_of": text(value.get("as_of"), 20),
        "profile": text(value.get("profile"), 40),
        "forecast_basis": text(value.get("forecast_basis"), 50),
        "production_ready": value.get("production_ready") if isinstance(
            value.get("production_ready"), bool) else None,
        "model": {"forecast_agent": text(model.get("forecast_agent"), 100),
                  "agent_effort": text(model.get("agent_effort"), 40),
                  "schema_version": model.get("schema_version") if isinstance(
                      model.get("schema_version"), int) else None},
        "spec_sha256": text(value.get("spec_sha256"), 64),
        "evidence_register_sha256": text(value.get("evidence_register_sha256"), 64),
        "source_text_en_sha256": text(value.get("source_text_en_sha256"), 64),
        "release_policy": {
            "version": text(policy_body.get("version"), 24),
            "effective_date": text(policy_body.get("effective_date"), 20),
            "status": text(policy_body.get("status"), 40),
            "sha256": text(policy_snapshot.get("sha256"), 64),
            "ambiguities": [text(item.get("id"), 80) for item in
                            (policy_body.get("ambiguities") or [])[:16]
                            if isinstance(item, dict)],
        } if policy_body else None,
        "house_assumptions": {
            "version": text(house_body.get("version"), 24),
            "documented_as_of": text(house_body.get("documented_as_of"), 20),
            "effective_from": text(house_body.get("effective_from"), 20),
            "status": text(house_body.get("status"), 40),
            "sha256": text(house_snapshot.get("sha256"), 64),
            "idr": house_currency("IDR"),
            "usd": house_currency("USD"),
            "unresolved": [text(item, 240) for item in (house_body.get("unresolved") or [])[:8]
                           if isinstance(item, str)],
        } if house_body else None,
        "source_pack_sha256": {text(path, 120): text(digest, 64) for path, digest
                                in source_packs.items()
                                if isinstance(path, str) and isinstance(digest, str)},
        "cache_snapshot_sha256": {text(endpoint, 180): {
            "cache_key": text(row.get("cache_key"), 180),
            "content_sha256": text(row.get("content_sha256"), 64),
        } for endpoint, row in cache_hashes.items()
                                  if isinstance(row, dict)},
        "artifacts": artifacts,
        "missing_artifacts": [text(kind, 20) for kind in
                              (value.get("missing_artifacts") or [])[:4]],
    }


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
        # The analyst records structured notes since #34; older runs are parsed.
        "analyst_problem_notes": (analyst["problem_notes"]
                                  if isinstance(analyst.get("problem_notes"), list)
                                  and len(analyst["problem_notes"])
                                  == sum(isinstance(p, str) for p in analyst.get("problems") or [])
                                  else problem_notes(analyst.get("problems"))),
        "research": _research(audit.get("research") if isinstance(audit.get("research"), dict) else {}),
        "news": _news(audit.get("news_sources") if isinstance(audit.get("news_sources"), dict) else {}),
        "forecast": _forecast(audit.get("forecast_assumptions")
                              if isinstance(audit.get("forecast_assumptions"), dict) else {}),
        "run_manifest": _manifest(audit.get("run_manifest")),
        "deepdive": _deepdive(audit.get("news_deepdive")),
    }
