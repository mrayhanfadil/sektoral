"""Load an agent briefing only after checking it against the current Sectors cache."""
from __future__ import annotations

import json
from pathlib import Path


ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "data" / "research_analysis"


def load_analysis(ticker, as_of=None, analysis_dir=None):
    """Return (validated briefing or None, status) without running an LLM."""
    directory = Path(analysis_dir) if analysis_dir is not None else ANALYSIS_DIR
    path = directory / f"{str(ticker).strip().upper()}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None, {"status": "missing", "path": str(path)}

    from agents.research.run import validate_against_cache

    validated, problems = validate_against_cache(ticker, document, as_of=as_of)
    if validated is None:
        return None, {"status": "invalid", "path": str(path), "problems": problems}
    if validated.get("status") != "research_brief" or not validated.get("insights"):
        return None, {"status": "insufficient", "path": str(path),
                      "problems": ["no validated research insight"]}
    return validated, {"status": "loaded", "path": str(path)}
