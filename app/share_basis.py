"""Report-date share count, EPS weighting and dilution from a reviewed share ledger.

The issuer evidence pack's ``share_ledger`` holds dated official register counts
(shares outstanding, net of treasury shares), the corporate actions between
them, the issuer's reported weighted-average counts and any potentially
dilutive instruments. From it this module derives, for one Report Date:

- the share count on the Report Date: the latest official register count on or
  before it, moved by completed, known actions after that count;
- a reconciliation of every pair of consecutive register counts through the
  actions between them (a gap means a missing action and blocks the ledger);
- the first forecast year's weighted-average basic shares (IAS 33 / PSAK 56):
  the issuer's reported first-half count, unless dated actions show it does
  not reconcile, then the flat count on the Report Date for the rest of the year;
- treasury-stock dilution at the Report Date price (for diluted EPS) and at a
  value per share (for a valuation: an instrument dilutes only when the value
  per share is above its exercise price, with its proceeds added).

Actions follow :mod:`app.corporate_actions`. An action may cite ``source_ref``
(a key of the pack's ``filing_sources``) instead of repeating its title and URL.
``timing: "aggregate"`` marks a net change the issuer reports only as a total
over an interval (a buyback programme); it is dated at the interval's end, so
it reconciles the counts but cannot support a derived weighted average.

The pro forma share count the report uses for EPS, PER and value per share in
every year is the Report Date count; the weighted average is recorded for
reconciliation to the issuer's future annual EPS.
"""
from __future__ import annotations

from datetime import date, timedelta

from . import corporate_actions

WASO_TOLERANCE = 0.01   # relative gap between a reported and a derived weighted average
_EXACT = 0.5            # share counts are integers; allow float rounding only


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _sources(pack):
    sources = pack.get("filing_sources")
    return sources if isinstance(sources, dict) else {}


def _with_source(record, sources):
    """A copy with ``source_title``/``source_url`` filled from ``source_ref``."""
    out = dict(record)
    ref = out.get("source_ref")
    source = sources.get(ref) if isinstance(ref, str) else None
    if source:
        out.setdefault("source_title", source.get("title"))
        out.setdefault("source_url", source.get("url"))
    return out


def _register(ledger, sources, errors):
    counts = []
    for index, row in enumerate(ledger.get("register_counts") or []):
        label = f"register_counts[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{label} is invalid")
            continue
        day, shares = _day(row.get("date")), row.get("shares_outstanding")
        if day is None or not _positive(shares):
            errors.append(f"{label} needs a date and positive shares_outstanding")
            continue
        if row.get("source_ref") not in sources:
            errors.append(f"{label} source_ref {row.get('source_ref')!r} is not a filing source")
            continue
        published = _day(sources[row["source_ref"]].get("published_at"))
        if published is None:
            errors.append(f"{label} source has no valid published_at")
            continue
        counts.append({**row, "_day": day, "_published": published})
    counts.sort(key=lambda r: r["_day"])
    if len({r["_day"] for r in counts}) != len(counts):
        errors.append("register_counts has two counts on one date")
    return counts


def _reconcile(counts, actions, as_of):
    rows, blockers = [], []
    for before, after in zip(counts, counts[1:]):
        derived = corporate_actions.shares_on(before["shares_outstanding"], before["date"],
                                              actions, after["date"], as_of)
        ok = abs(derived - after["shares_outstanding"]) <= _EXACT
        rows.append({"from": before["date"], "to": after["date"],
                     "from_shares": before["shares_outstanding"],
                     "to_shares": after["shares_outstanding"],
                     "derived_shares": derived, "reconciles": ok})
        if not ok:
            blockers.append(
                f"register count {after['shares_outstanding']:,.0f} on {after['date']} does not "
                f"follow from {before['shares_outstanding']:,.0f} on {before['date']} and the "
                f"ledger's actions ({derived:,.0f}); an action is missing or misdated")
    return rows, blockers


def _count_on(counts, actions, day, as_of):
    """Shares on ``day`` from the latest register count on or before it."""
    known = [c for c in counts if c["_day"] <= day]
    if not known:
        return None, None
    base = known[-1]
    return (corporate_actions.shares_on(base["shares_outstanding"], base["date"], actions,
                                        day.isoformat(), as_of), base)


def _first_half(ledger, counts, actions, as_of, sources, year, warnings):
    """Chosen first-half weighted average for ``year`` and how it was chosen."""
    start, end = date(year, 1, 1), date(year, 6, 30)
    reported = next((r for r in ledger.get("reported_weighted_average") or []
                     if isinstance(r, dict) and _day(r.get("start")) == start
                     and _day(r.get("end")) == end and _positive(r.get("shares"))), None)
    if reported and (reported.get("source_ref") not in sources or
                     (_day(sources[reported["source_ref"]].get("published_at")) or date.max)
                     > _day(as_of)):
        reported = None
    opening = next((c for c in counts if c["_day"] == start - timedelta(days=1)), None)
    in_half = [a for a in actions if a.get("status") == "completed"
               and start <= (_day(a.get("effective_date")) or date.min) <= end]
    derived = None
    if opening and not any(a.get("timing") == "aggregate" for a in in_half):
        before = {a["action_id"]: a["shares_before"] for a in in_half
                  if a.get("kind") == "rights_issue" and _positive(a.get("shares_before"))}
        derived = corporate_actions.weighted_average_shares(
            opening["shares_outstanding"], opening["date"], start.isoformat(), end.isoformat(),
            actions, as_of, shares_before_rights=before)["weighted_average_shares"]
    record = {"period": f"1H{year % 100:02d}", "issuer_reported": (reported or {}).get("shares"),
              "issuer_source_ref": (reported or {}).get("source_ref"), "derived": derived}
    if reported and derived is not None:
        gap = derived / reported["shares"] - 1
        record["gap"] = gap
        if abs(gap) > WASO_TOLERANCE:
            warnings.append(
                f"issuer-reported 1H{year % 100:02d} weighted average {reported['shares']:,.0f} "
                f"does not reconcile to the dated register and actions ({derived:,.0f}, "
                f"{gap * 100:+.1f}%); the derived figure is used and the issuer figure is "
                "flagged for review")
            return derived, "derived_from_dated_actions", record
        return reported["shares"], "issuer_reported", record
    if reported:
        return reported["shares"], "issuer_reported", record
    if derived is not None:
        return derived, "derived_from_dated_actions", record
    return None, None, record


def _fy_weighted(ledger, counts, actions, as_of, sources, year, warnings):
    """FY weighted average: chosen 1H, then day-by-day counts known by the Report Date."""
    h1, basis, record = _first_half(ledger, counts, actions, as_of, sources, year, warnings)
    if h1 is None:
        return {**record, "year": year, "shares": None,
                "reason": "no reported or derivable first-half weighted average"}
    report_day = _day(as_of)
    start, end = date(year, 7, 1), date(year, 12, 31)
    total, day = 0.0, start
    last_known = None
    # Each second-half day counts the shares known on it; days after the Report
    # Date hold the Report Date count (no forecast of future actions).
    while day <= end:
        count, _ = _count_on(counts, actions, min(day, report_day), as_of)
        if count is None:
            return {**record, "year": year, "shares": None,
                    "reason": "no register count for the second half"}
        total += count
        last_known = count
        day += timedelta(days=1)
    h2 = total / ((end - start).days + 1)
    days_h1 = (date(year, 6, 30) - date(year, 1, 1)).days + 1
    days = (end - date(year, 1, 1)).days + 1
    return {**record, "year": year, "h1_basis": basis, "h1_shares": h1, "h2_shares": h2,
            "shares": (h1 * days_h1 + h2 * (days - days_h1)) / days,
            "h2_basis": ("register counts and completed actions to the Report Date, "
                         "held flat to year end"), "closing_shares": last_known}


def _instruments(ledger, sources, as_of, errors):
    out = []
    report_day = _day(as_of)
    for index, item in enumerate(ledger.get("dilutive_instruments") or []):
        label = f"dilutive_instruments[{index}]"
        if not isinstance(item, dict) or item.get("kind") != "warrant":
            errors.append(f"{label} must be a warrant record")
            continue
        if not (_positive(item.get("shares")) and _positive(item.get("exercise_price"))):
            errors.append(f"{label} needs positive shares and exercise_price")
            continue
        if item.get("source_ref") not in sources:
            errors.append(f"{label} source_ref is not a filing source")
            continue
        expires = _day(item.get("expires_at"))
        if expires and report_day and expires < report_day:
            continue
        out.append(item)
    return out


def dilute_at_value(per_share, shares, instruments):
    """Value per share after in-the-money warrants at ``per_share``, with proceeds.

    An instrument is included only when the undiluted value per share exceeds its
    exercise price; ``(equity + proceeds) / (shares + new shares)``.
    """
    if not (_positive(per_share) and _positive(shares)):
        return {"per_share": per_share, "included": [], "excluded": [], "new_shares": 0.0}
    equity, count = per_share * shares, shares
    included, excluded = [], []
    for item in sorted(instruments, key=lambda i: i["exercise_price"]):
        if per_share > item["exercise_price"]:
            equity += item["shares"] * item["exercise_price"]
            count += item["shares"]
            included.append(item.get("instrument_id"))
        else:
            excluded.append(item.get("instrument_id"))
    return {"per_share": equity / count, "included": included, "excluded": excluded,
            "new_shares": count - shares}


def assess(pack, as_of, price=None, fiscal_year=None) -> dict:
    """Share basis for one issuer at one Report Date (see module docstring)."""
    pack = pack if isinstance(pack, dict) else {}
    ledger = pack.get("share_ledger")
    if not isinstance(ledger, dict):
        return {"status": "not_assessed",
                "reason": "Source pack has no reviewed share ledger; the share count is the "
                          "latest balance-sheet figure without later actions."}
    sources = _sources(pack)
    errors, warnings = [], []
    counts = _register(ledger, sources, errors)
    report_day = _day(as_of)
    if report_day is None:
        errors.append("report date is invalid")
    actions = [_with_source(a, sources) for a in ledger.get("actions") or []
               if isinstance(a, dict)]
    errors.extend(corporate_actions.validate(actions))
    known_counts = [c for c in counts if report_day and c["_day"] <= report_day
                    and c["_published"] <= report_day]
    if not known_counts:
        errors.append("no official register count is published by the Report Date")
    if errors:
        return {"status": "incomplete", "blockers": errors, "warnings": warnings}
    reconciliation, blockers = _reconcile(known_counts, actions, as_of)
    base = known_counts[-1]
    current = corporate_actions.shares_on(base["shares_outstanding"], base["date"], actions,
                                          as_of, as_of)
    year = fiscal_year or report_day.year
    weighted = _fy_weighted(ledger, known_counts, actions, as_of, sources, year, warnings)
    instruments = _instruments(ledger, sources, as_of, blockers)
    dilution = None
    if instruments and _positive(price):
        dilution = corporate_actions.diluted_eps(1.0, current, instruments, average_price=price)
        dilution = {"price": price, "diluted_shares": dilution["diluted_shares"],
                    "incremental_shares": dilution["diluted_shares"] - current,
                    "basis": "treasury-stock method at the Report Date price"}
    return {
        "status": "incomplete" if blockers else "assessed",
        "shares_on_report_date": current,
        "basis": {"date": base["date"], "shares_outstanding": base["shares_outstanding"],
                  "source_ref": base["source_ref"],
                  "source_title": sources[base["source_ref"]].get("title"),
                  "page": sources[base["source_ref"]].get("page")},
        "reconciliation": reconciliation,
        "fy_weighted_average": weighted,
        "instruments": instruments,
        "dilution_at_price": dilution,
        "conditional_scenarios": corporate_actions.conditional_scenarios(actions, as_of),
        "review": {k: ledger.get(k) for k in ("reviewed_through", "review_basis", "notes")
                   if ledger.get(k) is not None},
        "blockers": blockers, "warnings": warnings,
    }


def model_shares(record):
    """The share count the model uses, or None when the ledger is not usable."""
    if isinstance(record, dict) and record.get("status") == "assessed" and \
            _positive(record.get("shares_on_report_date")):
        return record["shares_on_report_date"]
    return None


def official_count(balance):
    """Latest balance-sheet count: outstanding (net of treasury), else issued."""
    balance = balance if isinstance(balance, dict) else {}
    for key in ("shares_outstanding", "shares_issued"):
        if _positive(balance.get(key)):
            return balance[key]
    return None


def report_date_shares(intake):
    """(shares, basis) for every per-share figure: the reviewed ledger when usable,
    else the official balance sheet, else the cache count."""
    record = (intake or {}).get("share_basis")
    shares = model_shares(record)
    if shares:
        basis = record.get("basis") or {}
        return shares, (f"register saham resmi {basis.get('date')}, "
                        f"disesuaikan aksi korporasi hingga {intake.get('as_of')}")
    balance = ((intake or {}).get("official_evidence") or {}).get("balance_sheet") or {}
    shares = official_count(balance)
    if shares:
        return shares, f"neraca interim resmi {balance.get('period_end')}"
    if _positive((intake or {}).get("shares")):
        return intake["shares"], "data Sectors"
    return None, None
