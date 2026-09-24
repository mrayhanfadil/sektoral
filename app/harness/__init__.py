"""Harness tools for Instruksi-Report-v3 compliance.

Each spec gate is a callable tool returning JSON-serializable verdicts.
Deterministic engine and LLM agents call the same tools, so compliance
is enforced identically on both paths.

Tools:
  check_s1            §2  intake & validation
  check_s2            §3  forecast engine
  check_s3            §4  valuation engine
  check_narrative     §5  + §6 self-check (Tier-1 deterministic)
  score_news          §5.3 news curation
  check_output_schema §7  JSON contract for renderer
  run_all             sequential orchestrator (S1→S2→S3→narrative→schema)

Every tool returns {"status": lolos|gagal|peringatan|dilabeli|..., "blockers": [...], ...}.
Critical blockers force draft_non_distributable; never downgrade to caveat.
"""
from .s1 import check_s1
from .s2 import check_s2
from .s3 import check_s3
from .narrative_tool import check_narrative, score_news
from .schema import check_output_schema
from .runner import run_all

__all__ = ["check_s1", "check_s2", "check_s3", "check_narrative",
           "score_news", "check_output_schema", "run_all"]
