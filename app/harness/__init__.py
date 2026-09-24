"""Harness tools for Instruksi-Report-v3 compliance.

Each spec gate is a callable tool returning JSON-serializable verdicts.
Deterministic engine and LLM agents call the same tools, so compliance
is enforced identically on both paths.

Tools:
  check_g1            §2  intake & validation
  check_g2            §3  forecast engine
  check_g3            §4  valuation engine
  check_narrative     §5  + §6 self-check (Tier-1 deterministic)
  score_news          §5.3 news curation
  check_output_schema §7  JSON contract for renderer
  run_all             sequential orchestrator (G1→G2→G3→narrative→schema)

Every tool returns {"status": lolos|gagal|peringatan|dilabeli|..., "blockers": [...], ...}.
Critical blockers force draft_non_distributable; never downgrade to caveat.
"""
from .g1 import check_g1
from .g2 import check_g2
from .g3 import check_g3
from .narrative_tool import check_narrative, score_news
from .schema import check_output_schema
from .runner import run_all

__all__ = ["check_g1", "check_g2", "check_g3", "check_narrative",
           "score_news", "check_output_schema", "run_all"]
