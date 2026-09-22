# Track 02 — Automation & Workflows

> Source: <https://hackathon.sectors.app/tracks/automation-workflows>

## What this track is

Products in which **Sectors data works inside real, recurring routines**.

## What qualifies

- A workflow that **fires on a market event**
- A scheduled pipeline that runs every trading day
- A bot that pushes alerts when defined conditions are met
- Custom scripts, n8n, messaging bots, CI schedulers
- Any other platform that can run a **repeatable routine autonomously**

## What does NOT qualify

> A workflow that requires a human to manually run it each time does not qualify for this track.

Translation: **must be trigger-based or scheduled**. If the user has to remember to click "Run" every time, this isn't Automation.

## Example directions (illustrations, not a fixed idea list)

1. A **daily market brief** generated and delivered automatically before the market opens
2. A bot that **watches defined Sectors signals** and pushes an alert when conditions are met
3. A triggered workflow that **updates a recurring research process** when market data changes

## Our brainstorming hooks

(We add these ourselves.)

- **Pre-market brief bot** — every trading day at 08:00 WIB, the bot pulls sector-level signals from Sectors (top movers, breadth, volume anomalies), assembles a Telegram message, and pushes to subscribers.
- **Disclosure watcher** — fires when a watched ticker posts a new Sectors-tracked event (material disclosure, ownership change, dividend announcement); posts a single-line alert to a Slack channel.
- **"Screener-of-the-day"** — runs a different custom screener daily on Sectors universe, posts the top 10 results to a Discord or channel.
- **End-of-day portfolio pnl digest** — cron at 16:30 WIB, computes moves vs yesterday's close, posts summary to WA/Telegram.

## Boundary reminder

Track is determined by **what the product fundamentally does**. An autonomous pipeline that produces scores may fit here OR Market Intelligence — we pick the one that best represents the core. If a chat-style interface is the primary surface, it belongs in AI Agents instead.

## Universal rules (apply to every track)

- Must use Sectors MCP or Sectors REST API as a **core** data source (not decorative).
- Working MVP / prototype with end-to-end workflow.
- No automated trade execution.
- See [`../rules.md`](../rules.md) §06 + §07 for the full set.
