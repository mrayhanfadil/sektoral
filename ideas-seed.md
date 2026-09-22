# Ideas & Track Decision

> **Decision tracker.** We pick exactly one track before writing project code (see [`submission-checklist.md`](submission-checklist.md) Week 1). The brainstorming below is intentionally raw — judges see the final product, not this file.

---

## How to pick

Quick decision rubric (each 0–5):

| Criterion | AI Agents | Automation | Market Intel |
|---|---|---|---|
| How obviously can a real Indonesian use this today? | 4 | 5 | 4 |
| How well does it play to our existing stack (Hermes, NucBox, Cloudflare, Telegram bots)? | 5 | 5 | 4 |
| How *visible* is the Sectors data dependency (judges' "remove Sectors → does it break?" test)? | 5 | 5 | 4 |
| How realistic in 4 weeks for a solo/small team? | 3 | 4 | 4 |
| How exciting will the 3-min judging video be? | 5 | 3 | 4 |

(Totals are personal gut feel — fill in your own.)

**Honest take:** Automation is the most reliable path to a "real person can use it today" product. AI Agents is the most video-exciting but is the highest-risk because the disqualification bar is strict (no off-the-shelf wrappers). Market Intelligence is the middle ground: easier to prove technical depth, easy to demo visually.

---

## Track 01 — AI Agents & Assistants ideas

Each must satisfy "if Sectors data is removed, the product breaks."

1. **"Saham Jujur" — single-ticker due diligence agent.**
   Input: ticker (BBCA, BMRI, TLKM…). Output: structured 5Y revenue trend, profitability vs sector peers, dividend track record, recent disclosures — each answer clickable back to the Sectors endpoint it came from. Citations are mandatory; the user can audit every claim.
   Why it works: clearly an agent (multi-step tool calls, memory of which sub-questions the user already asked), clearly Sectors-core (no ticker → no useful answer), clearly auditable (great judging video).

2. **"Porto Copilot" — held-ticker briefing bot.**
   Input: list of tickers the user owns. Output: daily briefing — peer comp moves, sector rotation, any ticker with material new filings.
   Why it works: memory/state (the user's holdings list), recurring workflow (a daily check), custom tool routing (per-ticker fetch).

3. **"DD for Small Caps" — research agent for thinly-covered IDX names.**
   For IDX small/mid caps with thin coverage, an agent that pulls fundamentals, peer-ranks them, surfaces anomalies vs sector.

---

## Track 02 — Automation & Workflows ideas

Each must satisfy "fires automatically, no human click required."

1. **Pre-market brief Telegram bot.** Cron at 08:00 WIB trading days. Pulls sector signals (top movers, breadth, volume anomalies) from Sectors, assembles a short Telegram message, pushes to subscribers.
   Why it works: trigger = time, output is useful at 08:01 WIB, Sectors-core, easy to demo by showing the morning's message.

2. **Disclosure watcher.** Fires when a watched ticker posts a new event (material disclosure, ownership change, dividend announcement). One-line alert to a Slack channel.

3. **Screener-of-the-day.** A different custom screener runs each day, posts top 10 results to Discord/Telegram channel.

4. **EOD portfolio digest.** 16:30 WIB cron, computes moves vs yesterday's close, posts summary to Telegram/WA.

---

## Track 03 — Market Intelligence ideas

Each must satisfy "adds interpretation on top of raw data, not just re-presentation."

1. **"Dividend Consistency Score"** — cross-sector screener scoring IDX companies on dividend continuity / payout ratio / yield vs history. Output: ranked table.
2. **Sector rotation radar** — weekly comparative view across IDX sectors showing momentum (price + breadth + volume delta).
3. **Material-change detector** — flags tickers where fundamentals moved >N std-dev vs trailing 90 days (revenue surprise, ROE shift, leverage jump).
4. **Liquidity / ownership-concentration screener** — surfaces low-float or high-concentrated-ownership names retail should know about.

---

## What we haven't picked yet (gaps to fill)

- [ ] **One-sentence problem statement** — for each candidate idea, draft one sentence. Use that to break ties.
- [ ] **Audience validation** — who is the first person we'd show this to, and would they actually use it tomorrow? If we can't name them, the idea isn't ready.
- [ ] **Sectors API/MCP coverage check** — for the candidate idea, do we know which Sectors endpoints / tools we'd use? Have we tested them?
- [ ] **Risk register** — what's the #1 thing that could make this fail to ship by 30 Sep? Pick the idea with the lowest #1 risk.

---

## Decision (lock this section once chosen)

> **Track:** TBD
> **Idea:** TBD
> **One-sentence problem statement:** TBD
> **Intended audience:** TBD
> **Locked at:** TBD
