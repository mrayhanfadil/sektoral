# Track 01 — AI Agents & Assistants

> Source: <https://hackathon.sectors.app/tracks/ai-agents-assistants>

## What this track is

Conversational or autonomous AI products for **Indonesian financial markets**, with an AI/LLM component at their core.

## What qualifies

- Multi-step reasoning flows
- Custom tool-use pipelines
- Routing between data sources
- Memory or state management
- Autonomous task execution
- A purpose-built interface for a specific participant and problem

## What does NOT qualify

> Connecting an off-the-shelf AI client (Claude, OpenClaw, Hermes, etc.) to the Sectors MCP with custom prompts or configuration alone. If the product would disappear when the team's prompt is removed from someone else's client, it does not meet this track's bar.

In other words: **the agent itself + its tool/prompt engineering + its custom-purpose UI/logic must be the product**, not a Claude wrapper. Fine-tuning, custom MCP tool definitions, custom orchestration logic, memory layers, custom dashboards — all count. Just wiring MCP into a stock chatbot does not.

## Example directions (illustrations, not a fixed idea list)

1. A **research agent** that plans and executes a multi-step company comparison using Sectors data
2. A **market assistant** with purpose-built tools, memory, and a workflow for a specific analyst task
3. An **autonomous research pipeline** that chooses which Sectors sources to query and synthesizes the result

## Our brainstorming hooks

(We add these ourselves — judges see the final product, not our notes.)

- A **"Saham Jujur" agent** that takes a ticker (BBCA, BMRI, TLKM…) and answers a structured set of investor questions (5Y revenue, profitability vs sector peers, dividend track record, recent disclosures) with citations back to Sectors endpoints. Each answer is auditable — user can click through.
- A **portfolio copilot** that takes a list of tickers the user already owns and produces a daily briefing: peer comparisons, sector rotation hints, any ticker with material new filings.
- A **due-diligence agent** for IDX small/mid caps that often have thin coverage — pull Sectors fundamentals, peer-rank, surface anything that looks anomalous vs the sector.

## Boundary reminder

A track is determined by what the product **fundamentally does**, not what it looks like. An agent with a dashboard interface still belongs in **AI Agents & Assistants**. (An autonomous pipeline that also produces scores may fit Automation or Market Intelligence — we choose the track that best represents the core.)

## Universal rules (apply to every track)

- Must use Sectors MCP or Sectors REST API as a **core** data source (not decorative).
- Working MVP / prototype with end-to-end workflow.
- No automated trade execution.
- See [`../rules.md`](../rules.md) §06 + §07 for the full set.
