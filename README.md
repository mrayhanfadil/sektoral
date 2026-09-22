# Sektoral

IDX intelligence on the Sectors licensed dataset. Product continuation of the
Sectors Hackathon 2026 work — clean repo, docs-first, no frozen product code.

Origin: `mrayhanfadil/sectors-hackathon` (planning + `feat/institutional-report`
product). This repo adopts the hackathon guides + data-access docs so future
work starts from one place.

## Data access — Sectors API / MCP

Two ways, same key (from sectors.app/api, Insider plan or hackathon onboarding):

| | REST | MCP |
|---|---|---|
| Base | `https://api.sectors.app/v2/...` | `https://sectors-mcp.supertype.ai/mcp` |
| Auth | `Authorization: <key>` (raw, no Bearer) | `Authorization: Bearer <key>` |
| Use | cron / automation / scripts | AI agent (Claude Code, Cursor, VS Code, Windsurf) |
| Coverage | IDX + SGX + KLSE + mining + brokers + filings + news | same, 65+ tools |

- Start: `docs/sectors-api-and-mcp.md` (v2 only — v1 is 410 Gone, tickers without `.JK`)
- MCP setup per client: `docs/mcp/setup.md` + `docs/mcp/tools.md`
- Claude web / ChatGPT OAuth path: `docs/mcp/claude-integration.md`, `docs/mcp/chatgpt-integration.md`
- REST catalog: `docs/rest/idx-screener.md`, `idx-company.md`, `idx-financials-transactions.md`, `idx-rankings-brokers-news.md`, `sgx.md`, `klse.md`, `mining.md`
- Agent recipes: `docs/recipes/` (01–06 + human-agent framework)

Billing: 2xx billed per endpoint cost, 404 on addressed resource bills 1, routing 404 / 4xx / 5xx free. Natural-language `?q=` costs 3, structured `where` costs 1. Budget in `credit-calculator.md`.

## Repo structure

```
sektoral/
├── README.md
├── rules.md, submission-checklist.md, credit-calculator.md
├── onboarding-blocker.md, team-roster.md, video-recording-guide.md
├── disclaimer-template.md, merge-plan.md, ideas-seed.md
├── tracks/                        ← 3 hackathon track briefs
├── docs/
│   ├── sectors-api-and-mcp.md     ← start here
│   ├── mcp/                       ← setup, tools, claude, chatgpt
│   ├── rest/                      ← per-endpoint catalog
│   ├── recipes/                   ← agent recipes 01–06
├── .env.example
└── .gitignore
```

## Quickstart

```bash
cp .env.example .env   # fill SECTORS_API_KEY, never commit .env
# MCP (Claude Code):
claude mcp add -t http sectors https://sectors-mcp.supertype.ai/mcp -H "Authorization: Bearer $SECTORS_API_KEY"
# REST smoke:
curl -s -H "Authorization: $SECTORS_API_KEY" "https://api.sectors.app/v2/companies/?limit=1" | head -c 500
```

Product code lives under `experiment/<track-slug>/` once a track locks (see hackathon `merge-plan.md` — not copied as history, only as guide).

## Adopted from hackathon

- `rules.md`, `tracks/`, `submission-checklist.md`, `ideas-seed.md` — from `references/mcp-and-recipes-2026-08-29` + planning commit `4aad52e`
- `docs/mcp/`, `docs/recipes/`, `docs/sectors-api-and-mcp.md` — same MCP branch
- `docs/rest/` — from `references/rest-catalog-2026-08-29`
- `.env.example`, `.gitignore` — hackathon root

Hackathon guides only — no product code, no product learnings.
