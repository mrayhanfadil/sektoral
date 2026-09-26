"""Staleness and withdrawal monitoring for published Company Updates.

Applies release policy 1.2.0 (``app.release_policy``) to each approved report in
a reports folder:

- a newer official period due under the OJK filing calendar, or a newer
  official actual in the issuer's source pack, is a trigger;
- a trigger labels the publication ``stale`` and opens a review; the report
  stays visible;
- the publication becomes ``withdrawal_due`` only when a rebuilt candidate shows
  a material change and no approved replacement exists after the grace window.

Withdrawal itself stays an authenticated publication event
(``publication_archive.withdraw_publication``): ``--apply`` needs a reviewer or
compliance token from the ``SECTORAL_MONITOR_TOKEN`` environment variable, so the
policy decides and a named identity is recorded as the actor.

    python -m app.publication_monitor --folder out/reports [--as-of YYYY-MM-DD]
        [--candidate-folder out/reports-new] [--apply] [TICKERS...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from . import assumption_review, issuer_evidence, outputs, release_policy


def summarize_model(fc, va) -> dict:
    """The materiality bases of one build, stored with the report.

    Values are raw currency units (the forecast's own unit) and CAR as a
    fraction; a basis the model did not compute is left out, never zero.
    """
    summary = {}
    anchor = ((fc or {}).get("outyear_scenario") or {}).get("anchor") or {}
    earnings = anchor.get("net_profit_attributable")
    if earnings is None:
        rows = ((fc or {}).get("bank_model") or {}).get("rows") or []
        earnings = rows[0].get("earnings") if rows else None
    if isinstance(earnings, (int, float)):
        summary["fy1_attributable_earnings"] = earnings
    bank_rows = ((fc or {}).get("bank_model") or {}).get("rows") or []
    car = bank_rows[0].get("capital_adequacy_ratio") if bank_rows else None
    if isinstance(car, (int, float)):
        summary["capital_adequacy_ratio"] = car
    nav = ((va or {}).get("sotp") or {}).get("attributable_asset_nav_idr")
    if isinstance(nav, (int, float)):
        summary["attributable_asset_nav"] = nav
    return summary


def _bases(doc) -> dict:
    """Model summary plus the published value per share of a stored report."""
    meta = (doc or {}).get("meta") or {}
    bases = dict((doc or {}).get("model_summary") or {})
    if isinstance(meta.get("tp"), (int, float)):
        bases["value_per_share"] = meta["tp"]
    return bases


def _calendar(ticker) -> dict:
    """Issuer calendar overrides from the source pack's optional ``fiscal_calendar``.

    Read from the raw pack: the calendar is standing issuer metadata, not a dated
    fact, so it applies whatever the pack's latest actual was published."""
    path = issuer_evidence.ROOT / f"{str(ticker).upper()}.json"
    try:
        pack = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        pack = {}
    cal = pack.get("fiscal_calendar") if isinstance(pack, dict) else None
    cal = cal if isinstance(cal, dict) else {}
    out = {}
    if isinstance(cal.get("fiscal_year_end_month"), int):
        out["fiscal_year_end_month"] = cal["fiscal_year_end_month"]
    if isinstance(cal.get("interim_assurance"), dict):
        out["interim_assurance"] = cal["interim_assurance"]
    return out


def _latest_official_actual(ticker, as_of) -> dict | None:
    """The source pack's latest official actual published by ``as_of`` (point in time)."""
    try:
        pack = issuer_evidence.load(ticker, as_of) or {}
    except (OSError, ValueError):
        return None
    latest = pack.get("latest_actual") if isinstance(pack, dict) else None
    return latest if isinstance(latest, dict) else None


def assess(folder, ticker, as_of=None, candidate_folder=None, db=None) -> dict:
    """Policy decision for one ticker's published Company Update."""
    t = str(ticker).upper()
    day = str(as_of or date.today().isoformat())[:10]
    review = assumption_review.status(folder, t, db)
    doc = outputs.load(outputs.REPORT, folder, t, db)
    manifest = outputs.load(outputs.MANIFEST, folder, t, db) or {}
    if review.get("state") != "approved" or not isinstance(doc, dict):
        return {"ticker": t, "state": "not_published", "review_state": review.get("state"),
                "triggers": [], "reason": "Tidak ada Company Update yang disetujui."}
    filing = manifest.get("official_filing") or {}
    used_end = str(filing.get("period_end") or "")[:10]
    triggers = []
    if used_end:
        overdue = release_policy.filing_overdue(used_end, day, **_calendar(t))
        if overdue["overdue"]:
            triggers.append({"kind": "filing_due", "date": overdue["required"]["due"],
                             "period": overdue["required"]["label"],
                             "detail": (f"Periode {overdue['required']['label']} wajib terbit paling "
                                        f"lambat {overdue['required']['due']} (batas OJK); laporan "
                                        f"memakai {filing.get('period')}.")})
    latest = _latest_official_actual(t, day)
    if latest and used_end and str(latest.get("period_end") or "")[:10] > used_end \
            and str(latest.get("published_at") or "")[:10] <= day:
        triggers.append({"kind": "new_official_actual", "date": str(latest["published_at"])[:10],
                         "period": latest.get("period"),
                         "detail": (f"Rilis resmi {latest.get('period')} terbit "
                                    f"{str(latest['published_at'])[:10]}; laporan memakai "
                                    f"{filing.get('period')}.")})
    profile = (doc.get("meta") or {}).get("model_profile") or manifest.get("profile")
    materiality, replacement_approved = None, False
    if candidate_folder is not None:
        candidate = outputs.load(outputs.REPORT, candidate_folder, t, db)
        if isinstance(candidate, dict) and profile in release_policy.MATERIALITY:
            materiality = release_policy.materiality_assessment(
                profile, _bases(doc), _bases(candidate))
            replacement_approved = assumption_review.status(
                candidate_folder, t, db).get("state") == "approved"
    decision = release_policy.publication_decision(
        triggers, day, materiality=materiality, replacement_approved=replacement_approved)
    return {"ticker": t, "as_of": day, "profile": profile,
            "publication_id": manifest.get("publication_id"),
            "report_period": filing.get("period"), **decision}


def _tickers(folder, db=None) -> list[str]:
    return sorted(outputs.tickers(outputs.REPORT, folder, db))


def _apply(folder, row, token, db=None) -> str:
    from . import publication_archive
    if not row.get("publication_id"):
        return "tidak diterapkan: publication_id tidak tercatat"
    try:
        publication_archive.withdraw_publication(
            folder, row["ticker"], row["publication_id"], reason=row["reason"],
            reviewer_token=token, db=db)
    except Exception as exc:  # the denial is the reported outcome
        return f"tidak diterapkan: {exc}"
    return "ditarik"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--folder", required=True, help="reports folder served by the gallery")
    parser.add_argument("--as-of", help="assessment date (default: today)")
    parser.add_argument("--candidate-folder",
                        help="rebuilt replacement reports used to measure materiality")
    parser.add_argument("--apply", action="store_true",
                        help="withdraw publications whose withdrawal is due "
                             "(needs SECTORAL_MONITOR_TOKEN)")
    parser.add_argument("--json", action="store_true", help="print one JSON object per ticker")
    parser.add_argument("tickers", nargs="*")
    args = parser.parse_args(argv)
    token = os.environ.get("SECTORAL_MONITOR_TOKEN") if args.apply else None
    if args.apply and not token:
        parser.error("--apply needs a reviewer or compliance token in SECTORAL_MONITOR_TOKEN")
    folder = Path(args.folder)
    candidate = Path(args.candidate_folder) if args.candidate_folder else None
    tickers = [t.upper() for t in args.tickers] or _tickers(folder)
    for ticker in tickers:
        row = assess(folder, ticker, args.as_of, candidate)
        if args.apply and row["state"] == "withdrawal_due":
            row["applied"] = _apply(folder, row, token)
        if args.json:
            print(json.dumps(row, ensure_ascii=False, default=str))
            continue
        line = f"{ticker:<5} {row['state']:<15}"
        if row.get("triggers"):
            line += " " + "; ".join(t["detail"] for t in row["triggers"])
        if row.get("applied"):
            line += f" -> {row['applied']}"
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
