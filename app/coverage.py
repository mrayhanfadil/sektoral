"""Coverage dashboard: every supported ticker's truthful status and precise blockers (plan §8, slice H).

Reads the stored reports of one run folder and states, per ticker: Release
Status, rating and value, Model Profile and method, the report and latest
official result dates, and why a report is not Production-Ready in terms a
reviewer can act on (the missing sourced input, the failed per-run check or
the policy vintage), plus the process measures the plan tracks by profile:
evidence completeness, share and normalization ledgers, terminal economics,
independent validation, business-quality coverage and review state.

``python -m app.coverage --folder out/<run> [--markdown out.md]``
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import bank_drivers, investability, operating_model, outputs

STATUS_LABEL = {"distributable": "Production-Ready", "distributable_assumption_led": "Assumption-Led",
                "draft_non_distributable": "Draft"}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _release(doc):
    return (doc.get("log_gate") or {}).get("release") or {}


def next_actions(ticker, doc):
    """Precise, actionable reasons a report is not Production-Ready."""
    meta, rel = doc.get("meta") or {}, _release(doc)
    status = meta.get("status")
    if status == "distributable":
        return []
    as_of = (doc.get("run_manifest") or {}).get("as_of") or meta.get("as_of")
    profile = meta.get("model_profile")
    actions = []
    blockers = list(rel.get("production_blockers") or rel.get("underlying_primary") or [])
    if status == "draft_non_distributable":
        actions.extend(f"release: {b}" for b in (doc.get("harness") or {}).get("blockers") or [])
    if profile == "going_concern_fcff" and operating_model.load(ticker, as_of) is None:
        actions.append(f"no sourced operating driver file (data/operating_drivers/{ticker}.json) "
                       "known by the Report Date")
    elif profile == "financial_ddm" and bank_drivers.load(ticker, as_of) is None:
        actions.append(f"no sourced bank driver file (data/bank_drivers/{ticker}.json) known by "
                       "the Report Date")
    for b in blockers:
        if "effective after the Report Date" in b:
            actions.append("house policy 1.2.0 is effective 2026-09-26, after this Report Date; "
                           "a run dated on or after it is required")
        elif "independent reference" in b or "terminal" in b:
            actions.append(b)
    method = (rel.get("method_chain") or {}).get("selected")
    if method not in (None, "fcff_dcf", "ddm", "sotp_lom"):
        actions.append(f"selected method {method} has no production path; a primary-method "
                       "production model is needed")
    if not actions and blockers:
        actions.extend(blockers)
    return list(dict.fromkeys(actions))


def row(ticker, doc, review=None):
    meta = doc.get("meta") or {}
    manifest = doc.get("run_manifest") or {}
    as_of = manifest.get("as_of")
    register = doc.get("evidence_register") or {}
    quality = doc.get("earnings_quality") or {}
    te = doc.get("terminal_economics") or {}
    bq = investability.business_quality(ticker, as_of) if as_of else []
    latest = None
    for r in register.get("rows") or []:
        if r.get("kind") == "official_actual":
            latest = r
    age = ((_day(as_of) - _day(latest.get("published_at"))).days
           if latest and _day(as_of) and _day(latest.get("published_at")) else None)
    return {
        "ticker": ticker, "status": meta.get("status"),
        "status_label": STATUS_LABEL.get(meta.get("status"), meta.get("status")),
        "rating": meta.get("rating"), "tp": meta.get("tp"),
        "profile": meta.get("model_profile"), "method": doc.get("method"),
        "as_of": as_of, "latest_actual": latest.get("period") if latest else None,
        "latest_actual_published": latest.get("published_at") if latest else None,
        "days_since_latest_actual": age,
        "register_rows": len(register.get("rows") or []),
        "register_violations": len(register.get("violations") or [])
        + len(register.get("critical_violations") or []),
        "share_ledger": (quality.get("share_basis") or {}).get("status"),
        "normalization": (quality.get("normalization") or {}).get("status"),
        "terminal_economics": te.get("status"),
        "driver_table": bool((doc.get("driver_value") or {}).get("rows")),
        "business_quality_answered": sum(1 for i in bq if i["status"] == "answered"),
        "business_quality_dimensions": len(bq),
        "review_state": (review or {}).get("state"),
        "next_actions": next_actions(ticker, doc),
    }


def build(folder, db=None):
    folder = Path(folder)
    rows = []
    for ticker in outputs.tickers(outputs.REPORT, folder, db):
        doc = outputs.load(outputs.REPORT, folder, ticker, db) or {}
        try:
            from . import assumption_review
            review = assumption_review.status(folder, ticker, db)
        except Exception:  # a coverage view never fails on review state
            review = None
        rows.append(row(ticker, doc, review))
    mix = {}
    for r in rows:
        key = (r["profile"], r["status_label"])
        mix[key] = mix.get(key, 0) + 1
    return {"folder": str(folder), "rows": rows,
            "status_mix": [{"profile": p, "status": s, "count": n} for (p, s), n in sorted(mix.items())]}


def markdown(result):
    lines = [f"# Coverage: {result['folder']}", "",
             "| Ticker | Status | Rating / TP | Profile | Report Date | Latest actual (age) | "
             "Register rows (violations) | Share ledger | Normalization | Terminal | "
             "Business quality | Review |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in result["rows"]:
        tp = f"{r['rating'] or '-'} Rp{r['tp']:,.0f}".replace(",", ".") if r["tp"] else (r["rating"] or "-")
        lines.append(
            f"| {r['ticker']} | {r['status_label']} | {tp} | {r['profile']} | {r['as_of']} | "
            f"{r['latest_actual']} ({r['days_since_latest_actual']} d) | {r['register_rows']} "
            f"({r['register_violations']}) | {r['share_ledger']} | {r['normalization']} | "
            f"{r['terminal_economics']} | {r['business_quality_answered']}/"
            f"{r['business_quality_dimensions']} | {r['review_state'] or '-'} |")
    lines += ["", "## Next actions", ""]
    for r in result["rows"]:
        if r["next_actions"]:
            lines.append(f"- **{r['ticker']}**: " + "; ".join(r["next_actions"]))
    lines += ["", "## Status mix by profile", ""]
    for m in result["status_mix"]:
        lines.append(f"- {m['profile']}: {m['status']} x{m['count']}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--folder", required=True)
    parser.add_argument("--markdown")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = build(args.folder)
    text = markdown(result)
    if args.markdown:
        Path(args.markdown).write_text(text, encoding="utf-8")
    print(json.dumps(result, indent=1, default=str) if args.json else text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
