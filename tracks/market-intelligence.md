# Track 03 — Market Intelligence

> Source: <https://hackathon.sectors.app/tracks/market-intelligence>

## What this track is

Products that **turn Sectors data into insight** for financial market decisions.

## What qualifies

- Signals or scores
- Rankings
- Screeners with custom logic
- Anomaly detection
- Comparative analysis
- Synthesized research outputs

## What does NOT qualify

> A product that only displays raw Sectors data in a different visual form, however well presented, does not qualify for this track.

Translation: **must add interpretation, ranking, scoring, or anomaly detection on top of the raw data**. Don't just repaint a chart. We need a derived signal that a person can act on.

## Example directions (illustrations, not a fixed idea list)

1. A **custom screener** that ranks companies using a team's own financial logic
2. An **anomaly detector** that surfaces unusual market or company behavior
3. A **comparative research product** that turns multiple Sectors data points into a decision-support view

## Our brainstorming hooks

(We add these ourselves.)

- **"Dividend Consistency Score"** — cross-sector screener scoring IDX-listed companies on a dividend continuity / payout-ratio / yield-vs-history composite. Output: ranked table user can drill into.
- **Sector rotation radar** — weekly comparative output across IDX sectors showing which ones are gaining vs losing momentum (price action + breadth + volume delta from Sectors).
- **"Material change detector"** — flags tickers where fundamentals moved >N std-dev vs trailing 90 days (revenue surprise, ROE shift, leverage jump). Useful for catching stories before they hit the news.
- **Liquidity / ownership concentration screener** — surfaces low-float or high-concentrated-ownership names that retail investors should know about before they trade.

## Boundary reminder

Track is determined by **what the product fundamentally does**. A screener or dashboard that recomputes scores from Sectors data fits here. If it has a chat interface and an agent loop as its core, it belongs in AI Agents. If it fires automatically on a schedule/event, it belongs in Automation. We pick one.

## Universal rules (apply to every track)

- Must use Sectors MCP or Sectors REST API as a **core** data source (not decorative).
- Working MVP / prototype with end-to-end workflow.
- No automated trade execution.
- See [`../rules.md`](../rules.md) §06 + §07 for the full set.
