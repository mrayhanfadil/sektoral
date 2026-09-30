"""LLM stage classifier + analyst override (plan §1.2).

Output validated deterministically:
{"life_cycle_stage": ..., "has_steady_state_3y": ..., "commodity_price_driven": ...,
 "dissimilar_segments": ..., "rationale": ..., "source_ids": [...]}

Validation: enum only; non-default classification must cite official or dated
article; rationale consistent with Sectors history. The rationale is Indonesian;
its English twin ``rationale_en`` must read English and state the same figures
(a bad twin is dropped, never the classification). Analyst file
data/method_overrides/<TICKER>.json wins over LLM and is shown in report.
Without validated classification gates use conservative defaults labeled unverified.
"""
from __future__ import annotations

import json
from pathlib import Path

from .scrub import EN_SOFT, english_problems


STAGES = {"pre_revenue", "high_growth_pre_profit", "mature", "decline"}
# high_growth accepted as alias for high_growth_pre_profit in gates
STAGE_ALIASES = {"high_growth": "high_growth_pre_profit"}

DEFAULTS = {
    "life_cycle_stage": "mature",
    "has_steady_state_3y": True,
    "commodity_price_driven": False,
    "dissimilar_segments": 1,
}

OVERRIDE_DIR = Path(__file__).resolve().parent.parent / "data" / "method_overrides"


def _annual_revenue_falling(annuals) -> bool:
    try:
        revs = [float(a.get("revenue")) for a in (annuals or [])[-3:] if a.get("revenue")]
    except (TypeError, ValueError):
        return False
    if len(revs) < 2:
        return False
    return revs[-1] < revs[0]


def _latest(annuals, key):
    for row in reversed(annuals or []):
        value = row.get(key) if isinstance(row, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
    return None


def rationale_en_problems(payload: dict, required=False) -> list[str]:
    """The English twin of the rationale: English, 40-600 characters, the
    Indonesian's figures. Each problem ends with ``EN_SOFT``; a missing twin
    is one only when `required` (a stored plan need not carry one)."""
    rationale = payload.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip() or (
            "rationale_en" not in payload and not required):
        return []
    twin = payload.get("rationale_en")
    problems = english_problems(rationale, twin)
    if not problems and not 40 <= len(twin) <= 600:
        problems.append("must be English 40-600 characters")
    return [f"rationale_en {problem}{EN_SOFT}" for problem in problems]


def validate(payload: dict, annuals=None, allowed_sources=None,
             require_english=False) -> tuple[bool, list[str], dict]:
    """Validate stage payload. Returns (ok, errors, normalized).

    ``allowed_sources`` is the set of citable ids actually supplied to the
    agent ("official" only when an official release exists, "news:N" only for
    supplied articles). When given, every cited id must be in it.
    ``require_english`` makes a missing ``rationale_en`` an error too. Errors
    about the English twin end with ``EN_SOFT``; ``normalized`` keeps the twin
    only when it is valid, and they do not unverify the classification.
    """
    errors = []
    if not isinstance(payload, dict):
        return False, ["stage payload must be an object"], {}
    stage = str(payload.get("life_cycle_stage") or "").strip().lower()
    stage = STAGE_ALIASES.get(stage, stage)
    if stage not in STAGES:
        errors.append(f"life_cycle_stage must be one of {sorted(STAGES)}")
    steady = payload.get("has_steady_state_3y")
    if not isinstance(steady, bool):
        errors.append("has_steady_state_3y must be boolean")
    comm = payload.get("commodity_price_driven")
    if not isinstance(comm, bool):
        errors.append("commodity_price_driven must be boolean")
    segs = payload.get("dissimilar_segments")
    if not isinstance(segs, int) or isinstance(segs, bool) or not 1 <= segs <= 10:
        errors.append("dissimilar_segments must be int 1-10")
    rationale = payload.get("rationale") or ""
    if not isinstance(rationale, str) or not 40 <= len(rationale) <= 600:
        errors.append("rationale must be Bahasa Indonesia 40-600 karakter")
    sources = payload.get("source_ids") or []
    if not isinstance(sources, list):
        errors.append("source_ids must be a list")
        sources = []
    if allowed_sources is not None:
        unknown = [str(x) for x in sources if str(x) not in allowed_sources]
        if unknown:
            errors.append(f"source_ids not supplied to the agent: {unknown}")
            sources = [x for x in sources if str(x) in allowed_sources]
    is_default = (stage == "mature" and steady is True and comm is False and segs == 1)
    if not is_default:
        has_official = any(str(s) == "official" for s in sources)
        has_news = any(str(s).startswith("news:") for s in sources)
        if not (has_official or has_news):
            errors.append("non-default classification must cite official or dated article")
    # Non-default stages must also agree with the reported numbers; a citation
    # alone cannot turn a profitable, revenue-earning issuer into early stage.
    revenue, earnings = _latest(annuals, "revenue"), _latest(annuals, "earnings")
    if stage == "pre_revenue" and revenue is not None and revenue > 0:
        errors.append("pre_revenue contradicts reported revenue in latest annuals")
    if stage == "high_growth_pre_profit" and earnings is not None and earnings > 0:
        errors.append("high_growth_pre_profit contradicts positive latest annual earnings")
    if stage == "decline" and not errors:
        if not _annual_revenue_falling(annuals):
            # Allow a cited restructuring article as the alternative evidence.
            has_news = any(str(s).startswith("news:") for s in sources)
            if not has_news:
                errors.append("decline requires falling revenue in latest annuals or cited restructuring")
    english = rationale_en_problems(payload, required=require_english)
    verified = not errors
    errors += english
    normalized = {
        "life_cycle_stage": stage if stage in STAGES else "mature",
        "has_steady_state_3y": steady if isinstance(steady, bool) else True,
        "commodity_price_driven": comm if isinstance(comm, bool) else False,
        "dissimilar_segments": segs if isinstance(segs, int) and 1 <= segs <= 10 else 1,
        "rationale": rationale if isinstance(rationale, str) else "",
        "source_ids": [str(s) for s in sources if isinstance(s, str)],
        "verified": verified,
    }
    if isinstance(payload.get("rationale_en"), str) and not english:
        normalized["rationale_en"] = payload["rationale_en"]
    return (not errors), errors, normalized


def load_override(ticker: str) -> dict | None:
    """Load analyst override file data/method_overrides/<TICKER>.json if present."""
    if not ticker:
        return None
    path = OVERRIDE_DIR / f"{str(ticker).upper()}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def classify(intake: dict, assumption_plan: dict | None = None) -> dict:
    """Return stage classification with provenance.

    Precedence: analyst file > validated LLM plan > conservative defaults (unverified).
    Return {"values": {...}, "source": "override|llm|default_unverified", "override": {...}|None}
    """
    ticker = (intake or {}).get("ticker") or ""
    override = load_override(ticker)
    if isinstance(override, dict):
        vals = {}
        for key in ("life_cycle_stage", "has_steady_state_3y", "commodity_price_driven",
                    "dissimilar_segments"):
            if key in override:
                vals[key] = override[key]
        # Fill defaults for missing keys
        for k, v in DEFAULTS.items():
            vals.setdefault(k, v)
        # Normalize alias
        stage = str(vals.get("life_cycle_stage") or "").lower()
        vals["life_cycle_stage"] = STAGE_ALIASES.get(stage, stage)
        if vals["life_cycle_stage"] not in STAGES:
            vals["life_cycle_stage"] = "mature"
        return {"values": vals, "source": "override", "override": {
            "field": "stage", "value": vals, "reason": override.get("reason"),
            "analyst": override.get("analyst"), "date": override.get("date")},
            "method_override": override.get("method"),
            "method_reason": override.get("method_reason") or override.get("reason")}
    # LLM plan: forecast agent may embed stage subagent output under stage_classification
    plan_stage = None
    if isinstance(assumption_plan, dict):
        plan_stage = assumption_plan.get("stage_classification") or assumption_plan.get("stage")
    if isinstance(plan_stage, dict):
        _, _, normalized = validate(plan_stage, (intake or {}).get("annuals"))
        if normalized["verified"]:
            found = {"values": {k: normalized[k] for k in DEFAULTS}, "source": "llm",
                     "override": None, "method_override": None, "method_reason": None,
                     "rationale": normalized.get("rationale"),
                     "source_ids": normalized.get("source_ids")}
            if "rationale_en" in normalized:
                found["rationale_en"] = normalized["rationale_en"]
            return found
    # Conservative defaults, unverified
    return {"values": dict(DEFAULTS), "source": "default_unverified", "override": None,
            "method_override": None, "method_reason": None}
