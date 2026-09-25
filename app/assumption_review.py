"""Analyst review of the Forecast Plan before a report is published (plan Phase 4).

The Forecast Assumption Agent writes the plan a report is built on. A report
is a draft until an analyst approves that plan: as written, or with edits to
its numeric drivers, each edit carrying the analyst's reason (the same
discipline as ``data/method_overrides``). The approval is recorded in the app
database under the report's folder and ticker (``app.outputs`` keys) and in
the report's Audit Trace (``assumption_review``); it names the reviewer, the
time, the plan fingerprint it approved and every change.

An approval is tied to the plan's fingerprint (``plan_sha``). A new run
replaces the plan, so its report is a draft again until someone reviews it.
Edits rebuild the report offline on the edited plan (``app.rebuild``, no
agent call); the approval then covers the rebuilt plan.

    python -m app.assumption_review status --folder out/reports [TICKERS...]
    python -m app.assumption_review approve --folder out/reports --reviewer "Nama" \\
        --note "Driver sesuai rilis 1H" BBCA
    python -m app.assumption_review approve --folder out/reports --reviewer "Nama" \\
        --edit "earnings_scenario.bank_drivers.nim_pct=5.4:NIM 1H26 resmi" BBCA
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import outputs, store

COLLECTION = "assumption_reviews"
# Plan sections an analyst may edit, and the reader label of each field.
SECTIONS = ("interim_scenario", "earnings_scenario", "outyear_scenario", "bank_outyear_scenario")
LABELS = {
    "h2_revenue_to_h1": ("Pendapatan H2 / H1", "x"),
    "h2_ebitda_margin_pct": ("Margin EBITDA H2", "%"),
    "h2_net_margin_pct": ("Margin laba bersih H2", "%"),
    "h2_capex_to_h1": ("Capex H2 / H1", "x"),
    "fy_ebitda_margin_pct": ("Margin EBITDA FY", "%"),
    "fy_capex_to_revenue_pct": ("Capex / pendapatan FY", "%"),
    "revenue_growth_pct": ("Pertumbuhan pendapatan", "%"),
    "ebitda_margin_pct": ("Margin EBITDA", "%"),
    "net_income_margin_pct": ("Margin laba bersih", "%"),
    "capex_to_revenue_pct": ("Capex / pendapatan", "%"),
    "loan_growth_pct": ("Pertumbuhan kredit", "%"),
    "nim_pct": ("NIM", "%"),
    "non_ii_to_nii_pct": ("Pendapatan non-bunga / NII", "%"),
    "cost_to_income_pct": ("Rasio biaya / pendapatan", "%"),
    "cost_of_credit_pct": ("Biaya kredit", "%"),
    "deposit_growth_pct": ("Pertumbuhan DPK", "%"),
}
# A reviewer's value outside these bounds is a typo, not a view.
BOUNDS = {"%": (-100.0, 300.0), "x": (0.0, 10.0)}
PATH = re.compile(r"^(?P<section>[a-z_]+)(?:\[(?P<index>\d+)\])?(?:\.(?P<sub>[a-z_]+))?"
                  r"\.(?P<field>[a-z0-9_]+)$")


class ReviewError(ValueError):
    """A review the host refuses: unknown field, bad value, missing reason."""


def plan_sha(plan) -> str | None:
    if not isinstance(plan, dict):
        return None
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False,
                                     default=str).encode()).hexdigest()


def report_plan(trace) -> dict | None:
    """The plan the report was built on, as ``app.rebuild.build_inputs`` reads it."""
    fa = (trace or {}).get("forecast_assumptions")
    if not isinstance(fa, dict):
        return None
    plan = fa["agent_plan_raw"] if "agent_plan_raw" in fa else fa.get("plan")
    return plan if isinstance(plan, dict) else None


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def fields(plan) -> list[dict]:
    """Every editable numeric driver: path, label, unit, year, value, rationale."""
    out = []

    def add(path, row, key, year, rationale):
        value = _number(row.get(key))
        if value is None or key not in LABELS:
            return
        label, unit = LABELS[key]
        out.append({"path": path, "field": key, "label": label, "unit": unit, "year": year,
                    "value": value, "rationale": rationale})

    for section in SECTIONS:
        block = (plan or {}).get(section)
        rows = block if isinstance(block, list) else [block] if isinstance(block, dict) else []
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            base = f"{section}[{i}]" if isinstance(block, list) else section
            year = row.get("year")
            rationale = str(row.get("rationale") or "")[:600]
            for key in row:
                add(f"{base}.{key}", row, key, year, rationale)
            drivers = row.get("bank_drivers")
            if isinstance(drivers, dict):
                for key in drivers:
                    add(f"{base}.bank_drivers.{key}", drivers, key, drivers.get("year"),
                        str(drivers.get("rationale") or rationale)[:600])
    return out


def _key(folder, ticker):
    return outputs.key(folder, str(ticker).upper())


def record(folder, ticker, db=None) -> dict | None:
    data = store.get(COLLECTION, _key(folder, ticker), db)
    return data if isinstance(data, dict) else None


def status(folder, ticker, db=None) -> dict:
    """{"state": "approved" | "pending" | "no_plan", "plan_sha", "record"}."""
    trace = outputs.load(outputs.TRACE, folder, ticker, db)
    sha = plan_sha(report_plan(trace))
    if sha is None:
        return {"state": "no_plan", "plan_sha": None, "record": None}
    rec = record(folder, ticker, db)
    approved = bool(rec and rec.get("plan_sha") == sha)
    return {"state": "approved" if approved else "pending", "plan_sha": sha,
            "record": rec if approved else None,
            "stale_record": rec if rec and not approved else None}


def apply_edits(plan, edits) -> tuple[dict, list[dict]]:
    """(edited plan, change log). Each edit: {"path", "value", "reason"}."""
    edited = copy.deepcopy(plan)
    known = {f["path"]: f for f in fields(plan)}
    changes = []
    for edit in edits or []:
        path = str((edit or {}).get("path") or "")
        reason = str((edit or {}).get("reason") or "").strip()
        field = known.get(path)
        if field is None:
            raise ReviewError(f"field {path!r} tidak dapat diedit")
        try:
            value = float(edit.get("value"))
        except (TypeError, ValueError):
            raise ReviewError(f"{path}: nilai harus angka") from None
        low, high = BOUNDS[field["unit"]]
        if not low <= value <= high:
            raise ReviewError(f"{path}: {value:g} di luar rentang {low:g}..{high:g}")
        if len(reason) < 10:
            raise ReviewError(f"{path}: alasan perubahan wajib diisi (minimal 10 karakter)")
        if value == field["value"]:
            continue
        match = PATH.match(path)
        node = edited[match["section"]]
        if match["index"] is not None:
            node = node[int(match["index"])]
        if match["sub"]:
            node = node[match["sub"]]
        node[match["field"]] = value
        changes.append({"path": path, "label": field["label"], "year": field["year"],
                        "unit": field["unit"], "from": field["value"], "to": value,
                        "reason": reason[:600]})
    return edited, changes


def approve(folder, ticker, reviewer, note="", edits=None, *, db=None, want_pdf=None,
            rebuild_fn=None) -> dict:
    """Approve the report's plan, rebuilding it first when there are edits.

    Returns the stored record. Raises ReviewError on a missing reviewer, a
    report without a stored plan, or a bad edit.
    """
    t = str(ticker).upper()
    reviewer = str(reviewer or "").strip()
    if len(reviewer) < 2:
        raise ReviewError("nama reviewer wajib diisi")
    trace = outputs.load(outputs.TRACE, folder, t, db)
    doc = outputs.load(outputs.REPORT, folder, t, db)
    plan = report_plan(trace)
    if plan is None or not isinstance(doc, dict):
        raise ReviewError(f"{t}: laporan atau Forecast Plan tersimpan tidak ditemukan")
    edited, changes = apply_edits(plan, edits)
    before = {"plan_sha": plan_sha(plan), **_verdict(doc)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rec = {"ticker": t, "reviewer": reviewer[:120], "reviewed_at": now,
           "note": str(note or "").strip()[:1000],
           "decision": "approved_with_edits" if changes else "approved",
           "edits": changes, "before": before}
    if changes:
        if rebuild_fn is None:
            from .rebuild import rebuild_one as rebuild_fn
        folder_path = Path(folder)
        pdf = want_pdf if want_pdf is not None else (folder_path / f"{t}.pdf").is_file()
        rebuild_fn(t, folder_path, folder_path, want_pdf=pdf, db=db, plan_override=edited,
                   trace_extra={"assumption_review": {**rec, "plan_sha": plan_sha(edited)}})
        doc = outputs.load(outputs.REPORT, folder, t, db)
        trace = outputs.load(outputs.TRACE, folder, t, db)
    rec["plan_sha"] = plan_sha(report_plan(trace))
    rec["after"] = _verdict(doc)
    rec["history"] = history(record(folder, t, db))
    store.put(COLLECTION, _key(folder, t), rec, db)
    trace = dict(trace or {})
    trace["assumption_review"] = rec
    outputs.save(outputs.TRACE, folder, t, trace, db)
    return rec


MAX_HISTORY = 20


def history(previous) -> list[dict]:
    """Earlier approvals, newest first: the previous record (without its own
    history) then its history. A re-approval never erases what came before."""
    if not isinstance(previous, dict):
        return []
    earlier = [x for x in previous.get("history") or [] if isinstance(x, dict)]
    return ([{k: v for k, v in previous.items() if k != "history"}] + earlier)[:MAX_HISTORY]


def plan_edits(rec) -> list[dict]:
    """Every change behind the approved plan: the edits of this approval and of
    any earlier one that produced the same plan, each with who made it and when."""
    if not isinstance(rec, dict):
        return []
    out = []
    for entry in [rec] + [x for x in rec.get("history") or [] if isinstance(x, dict)]:
        if entry.get("plan_sha") != rec.get("plan_sha"):
            continue
        for edit in entry.get("edits") or []:
            out.append({**edit, "reviewer": entry.get("reviewer"),
                        "reviewed_at": entry.get("reviewed_at")})
    return out


def _verdict(doc) -> dict:
    meta = (doc or {}).get("meta") or {}
    return {"status": meta.get("status"), "rating": meta.get("rating"), "tp": meta.get("tp")}


def public(folder, ticker, db=None) -> dict:
    """The review state and the editable plan, for the web app."""
    st = status(folder, ticker, db)
    trace = outputs.load(outputs.TRACE, folder, ticker, db)
    rec = st.get("record") or {}
    return {"state": st["state"], "plan_sha": st["plan_sha"],
            "reviewer": rec.get("reviewer"), "reviewed_at": rec.get("reviewed_at"),
            "decision": rec.get("decision"), "note": rec.get("note"),
            "edits": plan_edits(rec) if rec else [],
            "history": [{"reviewer": h.get("reviewer"), "reviewed_at": h.get("reviewed_at"),
                         "decision": h.get("decision"), "edits": len(h.get("edits") or []),
                         "note": h.get("note")}
                        for h in (rec.get("history") or []) if isinstance(h, dict)],
            "stale": bool(st.get("stale_record")),
            "fields": fields(report_plan(trace))}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "approve"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--folder", required=True)
        cmd.add_argument("tickers", nargs="*" if name == "status" else "+")
        if name == "approve":
            cmd.add_argument("--reviewer", required=True)
            cmd.add_argument("--note", default="")
            cmd.add_argument("--edit", action="append", default=[],
                             help="path=value:reason, e.g. outyear_scenario[0].ebitda_margin_pct"
                                  "=13.0:alasan")
    args = parser.parse_args(argv)
    tickers = args.tickers or outputs.tickers(outputs.REPORT, args.folder)
    if args.command == "status":
        for t in tickers:
            st = status(args.folder, t)
            rec = st.get("record") or {}
            print(f"{t:5} {st['state']:9} {rec.get('reviewer') or '-'} {rec.get('reviewed_at') or ''}")
        return 0
    if args.edit and len(tickers) > 1:
        parser.error("--edit hanya untuk satu emiten per perintah")
    edits = []
    for text in args.edit:
        path, _, rest = text.partition("=")
        value, _, reason = rest.partition(":")
        edits.append({"path": path.strip(), "value": value.strip(), "reason": reason.strip()})
    failed = 0
    for t in tickers:
        try:
            rec = approve(args.folder, t, args.reviewer, args.note, edits)
        except ReviewError as error:
            print(f"{t}: DITOLAK {error}", file=sys.stderr)
            failed += 1
            continue
        print(f"{t}: {rec['decision']} oleh {rec['reviewer']} ({len(rec['edits'])} perubahan); "
              f"{rec['before'].get('rating')} Rp{rec['before'].get('tp')} -> "
              f"{rec['after'].get('rating')} Rp{rec['after'].get('tp')}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
