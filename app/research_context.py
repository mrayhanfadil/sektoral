"""Load an agent briefing only after checking it against the current Sectors cache."""
from __future__ import annotations

from . import store

# The research agent's latest brief per ticker (agents/research/run.py writes it).
COLLECTION = "research_analysis"


def load_analysis(ticker, as_of=None, db=None):
    """Return (validated briefing or None, status) without running an LLM."""
    key = str(ticker).strip().upper()
    path = f"{COLLECTION}/{key}"
    document = store.get(COLLECTION, key, db)
    if not isinstance(document, dict):
        return None, {"status": "missing", "path": path}

    from agents.research.run import validate_against_cache

    validated, problems = validate_against_cache(ticker, document, as_of=as_of)
    if validated is None:
        return None, {"status": "invalid", "path": path, "problems": problems}
    if validated.get("status") != "research_brief" or not validated.get("insights"):
        return None, {"status": "insufficient", "path": path,
                      "problems": ["no validated research insight"]}
    return validated, {"status": "loaded", "path": path}
