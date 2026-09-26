"""Dated corporate-action ledger: share counts, per-share adjustment, financing effects.

Each action is a dated, sourced record. Only actions announced by the Report
Date are known; only ``completed`` actions whose effective date has passed move
the actual share count. ``pending`` actions stay conditional scenarios, never
part of reported shares or per-share history.

Kinds and their terms:

- ``split`` / ``reverse_split`` / ``bonus``: ``ratio`` new shares per old share
  (a 1:5 split is 5, a 5:1 reverse split is 0.2, a 10% bonus issue is 1.1).
- ``rights_issue``: ``new_shares``, ``subscription_price`` and the last
  cum-rights close ``cum_rights_price``; the theoretical ex-rights price (TERP)
  gives the bonus element that restates earlier per-share figures.
- ``private_placement`` / ``warrant_exercise``: ``new_shares``, ``price``.
- ``buyback``: ``shares`` repurchased and ``cash_paid``; ``treasury_resale``:
  ``shares`` and ``proceeds``.
- ``conversion``: ``new_shares`` and ``debt_converted``.
"""
from __future__ import annotations

from datetime import date

_RATIO_KINDS = {"split", "reverse_split", "bonus"}
_ISSUE_KINDS = {"private_placement", "warrant_exercise"}
KINDS = _RATIO_KINDS | _ISSUE_KINDS | {"rights_issue", "buyback", "treasury_resale", "conversion"}
_TERMS = {
    "split": ("ratio",), "reverse_split": ("ratio",), "bonus": ("ratio",),
    "rights_issue": ("new_shares", "subscription_price", "cum_rights_price"),
    "private_placement": ("new_shares", "price"), "warrant_exercise": ("new_shares", "price"),
    "buyback": ("shares", "cash_paid"), "treasury_resale": ("shares", "proceeds"),
    "conversion": ("new_shares", "debt_converted"),
}
STATUSES = {"completed", "pending", "cancelled"}


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _positive(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0)


def validate(actions) -> list[str]:
    """Named errors for a ledger; an empty list means every record is usable."""
    if not isinstance(actions, list):
        return ["corporate-action ledger must be a list"]
    errors, seen = [], set()
    for index, action in enumerate(actions):
        label = f"corporate_action[{index}]"
        if not isinstance(action, dict):
            errors.append(f"{label} is invalid")
            continue
        action_id = action.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            errors.append(f"{label} has no action_id")
        elif action_id in seen:
            errors.append(f"duplicate action_id {action_id!r}")
        else:
            seen.add(action_id)
            label = f"corporate_action {action_id!r}"
        kind = action.get("kind")
        if kind not in KINDS:
            errors.append(f"{label} kind {kind!r} is not supported")
            continue
        if action.get("status") not in STATUSES:
            errors.append(f"{label} status must be completed, pending or cancelled")
        announced = _day(action.get("announced_at"))
        effective = _day(action.get("effective_date"))
        ex_date = _day(action.get("ex_date")) if action.get("ex_date") else None
        if announced is None:
            errors.append(f"{label} announced_at is missing or invalid")
        if action.get("status") == "completed" and effective is None:
            errors.append(f"{label} is completed without a valid effective_date")
        if announced and effective and effective < announced:
            errors.append(f"{label} takes effect before it was announced")
        if announced and ex_date and ex_date < announced:
            errors.append(f"{label} ex_date precedes its announcement")
        if action.get("status") == "pending" and not str(action.get("conditions") or "").strip():
            errors.append(f"{label} is pending without its conditions")
        if not (str(action.get("source_url") or "").strip() and str(action.get("source_title") or "").strip()):
            errors.append(f"{label} needs source_title and source_url")
        for term in _TERMS[kind]:
            if not _positive(action.get(term)):
                errors.append(f"{label} {term} must be a positive number")
        if kind == "reverse_split" and _positive(action.get("ratio")) and action["ratio"] >= 1:
            errors.append(f"{label} reverse split ratio must be below 1")
        if kind in {"split", "bonus"} and _positive(action.get("ratio")) and action["ratio"] <= 1:
            errors.append(f"{label} {kind} ratio must be above 1")
    return errors


def _known(actions, as_of):
    """Actions announced by the Report Date, split into applied and conditional."""
    cutoff = _day(as_of)
    applied, conditional = [], []
    for action in actions:
        announced = _day(action.get("announced_at"))
        if cutoff is None or announced is None or announced > cutoff:
            continue
        if action.get("status") == "cancelled":
            continue
        effective = _day(action.get("effective_date"))
        if action.get("status") == "completed" and effective and effective <= cutoff:
            applied.append(action)
        else:
            conditional.append(action)
    applied.sort(key=lambda a: (_day(a.get("effective_date")), str(a.get("action_id"))))
    return applied, conditional


def _checked(actions):
    errors = validate(actions)
    if errors:
        raise ValueError("; ".join(errors))


def share_change(action, shares_before):
    """Shares after one action given the count immediately before it."""
    kind = action["kind"]
    if kind in _RATIO_KINDS:
        return shares_before * action["ratio"]
    if kind in _ISSUE_KINDS or kind in {"rights_issue", "conversion"}:
        return shares_before + action["new_shares"]
    if kind == "buyback":
        return shares_before - action["shares"]
    return shares_before + action["shares"]  # treasury_resale


def shares_on(base_shares, base_date, actions, on_date, as_of) -> float:
    """Outstanding shares on ``on_date`` from a sourced count on ``base_date``.

    Applies completed actions effective after ``base_date`` up to ``on_date`` that
    were known by ``as_of``. A pending action never changes the count.
    """
    _checked(actions)
    if not _positive(base_shares):
        raise ValueError("base share count must be positive")
    start, end = _day(base_date), _day(on_date)
    if start is None or end is None or end < start:
        raise ValueError("share-count dates are invalid")
    shares = base_shares
    for action in _known(actions, as_of)[0]:
        effective = _day(action["effective_date"])
        if start < effective <= end:
            shares = share_change(action, shares)
            if shares <= 0:
                raise ValueError(f"share count is not positive after {action['action_id']!r}")
    return shares


def terp(shares_before, action):
    """Theoretical ex-rights price for one rights issue."""
    return ((shares_before * action["cum_rights_price"]
             + action["new_shares"] * action["subscription_price"])
            / (shares_before + action["new_shares"]))


def price_adjustment_factor(actions, from_date, to_date, as_of, shares_before_rights=None) -> float:
    """Factor restating a per-share figure dated ``from_date`` onto the share basis of ``to_date``.

    Multiply an earlier price, EPS or DPS by the factor (divide an earlier share
    count by it). Splits and bonus issues contribute ``1 / ratio``; a rights issue
    contributes TERP / cum-rights price, which needs the share count just before
    it in ``shares_before_rights`` keyed by action_id. Issues at market price,
    buybacks and conversions change the count but carry no bonus element.
    """
    _checked(actions)
    start, end = _day(from_date), _day(to_date)
    if start is None or end is None or end < start:
        raise ValueError("adjustment dates are invalid")
    factor = 1.0
    for action in _known(actions, as_of)[0]:
        ex = _day(action.get("ex_date") or action["effective_date"])
        if not (start < ex <= end):
            continue
        if action["kind"] in _RATIO_KINDS:
            factor /= action["ratio"]
        elif action["kind"] == "rights_issue":
            before = (shares_before_rights or {}).get(action["action_id"])
            if not _positive(before):
                raise ValueError(f"rights issue {action['action_id']!r} needs the share count before it")
            factor *= terp(before, action) / action["cum_rights_price"]
    return factor


def conditional_scenarios(actions, as_of) -> list[dict]:
    """Known actions that have not taken effect: shown as scenarios, never as actual shares."""
    _checked(actions)
    return [{"action_id": a["action_id"], "kind": a["kind"], "status": a["status"],
             "conditions": a.get("conditions"), "announced_at": a["announced_at"],
             "effective_date": a.get("effective_date"), "source_url": a["source_url"]}
            for a in _known(actions, as_of)[1]]


def weighted_average_shares(base_shares, base_date, period_start, period_end, actions, as_of,
                            shares_before_rights=None) -> dict:
    """Time-weighted basic share count for an EPS period (IAS 33 / PSAK 56 basis).

    The period runs from ``period_start`` to ``period_end`` inclusive. A split or
    bonus issue restates every earlier segment as if it had always applied; a
    rights issue restates earlier segments by its bonus factor (cum-rights price
    / TERP) and adds its new shares from the effective date; other issues,
    buybacks and conversions count from their effective date only.
    """
    from datetime import timedelta
    _checked(actions)
    start, end = _day(period_start), _day(period_end)
    if start is None or end is None or end < start:
        raise ValueError("EPS period dates are invalid")
    opening = shares_on(base_shares, base_date, actions, start - timedelta(days=1), as_of) \
        if _day(base_date) < start else base_shares
    segments = []  # [shares, first day] with the count in force from that day
    current, cursor = opening, start
    for action in _known(actions, as_of)[0]:
        effective = _day(action["effective_date"])
        if not (start <= effective <= end):
            continue
        segments.append([current, cursor])
        if action["kind"] in _RATIO_KINDS:
            for seg in segments:
                seg[0] *= action["ratio"]
        elif action["kind"] == "rights_issue":
            before = (shares_before_rights or {}).get(action["action_id"], current)
            bonus = action["cum_rights_price"] / terp(before, action)
            for seg in segments:
                seg[0] *= bonus
        current, cursor = share_change(action, current), effective
    segments.append([current, cursor])
    total_days = (end - start).days + 1
    weighted = 0.0
    for index, (shares, first) in enumerate(segments):
        last = segments[index + 1][1] if index + 1 < len(segments) else end + timedelta(days=1)
        weighted += shares * (last - first).days
    return {"weighted_average_shares": weighted / total_days, "closing_shares": current,
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "days": total_days}


def diluted_eps(earnings, basic_shares, instruments=(), average_price=None) -> dict:
    """Basic and diluted EPS with anti-dilutive instruments excluded.

    ``instruments``: ``{"kind": "warrant", "shares", "exercise_price"}`` uses the
    treasury-stock method at ``average_price``; ``{"kind": "convertible",
    "shares", "interest_after_tax"}`` uses the if-converted method. Instruments
    are added from the most dilutive and kept only while they lower EPS.
    """
    if not _positive(basic_shares):
        raise ValueError("basic share count must be positive")
    basic = earnings / basic_shares
    candidates = []
    for item in instruments:
        if item.get("kind") == "warrant":
            if not (_positive(average_price) and _positive(item.get("shares"))
                    and _positive(item.get("exercise_price"))):
                raise ValueError("a warrant needs shares, exercise_price and an average price")
            incremental = item["shares"] * (1 - item["exercise_price"] / average_price)
            if incremental > 0:
                candidates.append((0.0, 0.0, incremental, item))
        elif item.get("kind") == "convertible":
            if not _positive(item.get("shares")) or not isinstance(item.get("interest_after_tax"), (int, float)):
                raise ValueError("a convertible needs shares and interest_after_tax")
            candidates.append((item["interest_after_tax"] / item["shares"],
                               item["interest_after_tax"], item["shares"], item))
        else:
            raise ValueError(f"unsupported dilutive instrument {item.get('kind')!r}")
    num, den, included, excluded = earnings, basic_shares, [], []
    for per_share, add_earnings, add_shares, item in sorted(candidates, key=lambda c: c[0]):
        trial = (num + add_earnings) / (den + add_shares)
        if trial < num / den:
            num, den = num + add_earnings, den + add_shares
            included.append(item.get("kind"))
        else:
            excluded.append(item.get("kind"))
    return {"basic_eps": basic, "diluted_eps": num / den, "diluted_shares": den,
            "included": included, "anti_dilutive_excluded": excluded}


def financing_effects(actions, period_start, period_end, as_of) -> dict:
    """Cash and debt effects of completed actions in a period, counted with their dilution."""
    _checked(actions)
    start, end = _day(period_start), _day(period_end)
    rows = []
    for action in _known(actions, as_of)[0]:
        effective = _day(action["effective_date"])
        if not (start <= effective <= end):
            continue
        kind = action["kind"]
        cash = (action["new_shares"] * action["subscription_price"] if kind == "rights_issue" else
                action["new_shares"] * action["price"] if kind in _ISSUE_KINDS else
                -action["cash_paid"] if kind == "buyback" else
                action["proceeds"] if kind == "treasury_resale" else 0.0)
        debt = -action["debt_converted"] if kind == "conversion" else 0.0
        if cash or debt:
            rows.append({"action_id": action["action_id"], "kind": kind,
                         "effective_date": action["effective_date"],
                         "cash_effect": cash, "debt_effect": debt})
    return {"rows": rows, "net_cash": sum(r["cash_effect"] for r in rows),
            "net_debt_change": sum(r["debt_effect"] for r in rows)}
