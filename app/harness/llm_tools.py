"""LLM function-calling specs for the harness tools.

Import this to expose Instruksi-Report-v3 gates as tool calls to the
LLM agent. The agent must call check_g1→check_g2→check_g3→check_narrative
in order and stop production rating/TP on any critical blocker.
Deterministic python in app.harness is the implementation; these dicts
are the JSON schemas for function calling.
"""
from __future__ import annotations

TOOLS = [
    {"name": "check_g1",
     "description": "Gate 1 intake validation (§2): periode terbaru, satuan, mata uang, rekonsiliasi kas, non-recurring. Fail-closed.",
     "input_schema": {"type": "object",
                      "properties": {"intake": {"type": "object"}},
                      "required": ["intake"]}},
    {"name": "check_g2",
     "description": "Gate 2 forecast checks (§3.2 G2.1-G2.9) per MODEL_PROFILE. Screening proxy alone fails G2.9.",
     "input_schema": {"type": "object",
                      "properties": {"intake": {"type": "object"},
                                     "forecast": {"type": "object"}},
                      "required": ["intake", "forecast"]}},
    {"name": "check_g3",
     "description": "Gate 3 valuation checks (§4.6 G3.1-G3.7 + §4.4 divergence/extreme) per MODEL_PROFILE.",
     "input_schema": {"type": "object",
                      "properties": {"intake": {"type": "object"},
                                     "forecast": {"type": "object"},
                                     "valuation": {"type": "object"}},
                      "required": ["intake", "forecast", "valuation"]}},
    {"name": "score_news",
     "description": "§5.3 news curation validator. LLM scores each item 0-3 on dampak/materialitas/durabilitas/kebaruan; tool keeps total≥7 (max 7, cover max 3).",
     "input_schema": {"type": "object",
                      "properties": {"items": {"type": "array",
                                              "items": {"type": "object"}}},
                      "required": ["items"]}},
    {"name": "check_narrative",
     "description": "Stage 4 + self-check Tier-1 (§5.1/5.2/5.3/5.5, §6): headline lengths, dashes/emoji, banned strings, period format, exhibit numbering/source, junk rows, draft TP ban.",
     "input_schema": {"type": "object",
                      "properties": {"doc": {"type": "object"}},
                      "required": ["doc"]}},
    {"name": "check_output_schema",
     "description": "Output JSON contract (§7): meta/cover/bagian/tabel_asumsi/log_gate/catatan_metodologi; rating/tp only when production.",
     "input_schema": {"type": "object",
                      "properties": {"doc": {"type": "object"}},
                      "required": ["doc"]}},
    {"name": "run_all",
     "description": "Sequential orchestrator G1→G2→G3→narrative→schema + engine release gate. Returns status distributable/draft_non_distributable + named blockers.",
     "input_schema": {"type": "object",
                      "properties": {"intake": {"type": "object"},
                                     "forecast": {"type": "object"},
                                     "valuation": {"type": "object"},
                                     "doc": {"type": "object"}}}},
]

JUDGE_PROMPT = """You are the §6 self-check judge (subjective Tier-2). Return JSON only.
Checks (pass/fail + fix):
1 headline is forward thesis with verb, not stat (bad: 'Multiple 2026 di 17,99x vs mid-cycle 28,42x').
2 each paragraph follows klaim → angka kunci → implikasi laba/valuasi.
3 max 3 curated news in thesis para, each tied to one driver.
4 catalyst rows each have time/condition + driver + earnings path + direction + source; no daily-price/broker-flow/index-rebalance without earnings transmission.
5 method + base year + multiple identical on p1 and valuation page.
6 downside TP < base TP from same basis.
7 disclaimer consistent with Buy/Hold/Sell (no denial when publishing rating).
8 methodology limits still true after new data (no 'data tidak ada' for exhibited data).
9 house vs guidance/consensus compared on comparable basis when available.
10 upside>+100% atau downside<-50% has 1 fundamental-thesis sentence + 1 model-limitation sentence on p1.
Fix text in place; never narrate the check."""
