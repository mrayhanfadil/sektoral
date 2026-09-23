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
- REST catalog: `docs/rest/` — idx-screener, idx-company, idx-financials-transactions, idx-rankings-brokers-news, sgx, klse, mining + mining 3-file split (commodities-trade, companies, sites-licenses)
- Agent recipes: `docs/recipes/` (01–06 + human-agent framework)
- Cookbooks: `docs/cookbook/` (00-quickstart + excel, sheets, looker, n8n, sectorscan, gnn, portfolio, banking, R, api-security) + `docs/cookbook-v2/` (01–08 worked Python: screener → error-handling)
- Sectors ops: `docs/sectors/` (swap, valuation-framework, credit-burn-discipline) + `docs/integration/` (client/cache gates, credit policy, financial-tools + MCP snapshots, offline toggle, backfill/harvest, conftest discipline — snapshots, not runnable product)

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
│   ├── cookbook/                  ← 14 cookbooks + quickstart
│   ├── cookbook-v2/               ← 8 worked Python recipes
│   ├── sectors/                   ← swap, valuation, credit discipline
│   ├── integration/               ← sectors client/tools snapshots (ref only)
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

## Sistem ringan v3 (app/)

Pipeline deterministik sesuai `spec/Instruksi-Report-v3.md`, contoh layout
`spec/GMFI-Company-Update-contoh.pdf`. Tanpa agen, tanpa LLM, tanpa upstream.

```bash
python3 -m app.build AMMN --out out   # JSON + HTML printable
python3 -m pytest tests/ -q
```

- `app/cache.py` intake hanya dari `data/sectors_cache.db` (stale-ok, 0 kredit).
  Ticker tanpa data cache ditolak keras (`no verified assumptions`).
- `app/forecast.py` saat ini masih memakai driver generik 3 tahun (CAGR historis,
  margin + operating leverage, sustaining = D&A); belum production-grade untuk
  emiten tambang. Rebuild AMMN direncanakan berbasis operasi pada `docs/plans/2026-09-23-ammn-issuer-specific-rebuild.md`.
- `app/valuation.py` saat ini masih DCF 3 tahun + terminal Gordon dirata-rata dengan
  exit EV/EBITDA; ini bukan metode produksi yang dapat diterima untuk finite-life
  mining. Instruksi v3.2 menetapkan LoM/SOTP sebagai valuasi inti.
- `app/narrative.py` JSON §7 (headline ≤10 kata, bullet ≤30, paragraf 90-160,
  exhibit bernomor, tanpa istilah pipeline) + `app/render.py` HTML.
- Status 22 Sep 2026: AMMN/BBCA/ADRO/RATU build hijau; MTEL (tanpa
  outstanding_shares) dan CDIA (2 annual) ditolak jujur. Paragraf cover 90-104
  kata (spec 110-150, residual v1).

## Adopted from hackathon

- `rules.md`, `tracks/`, `submission-checklist.md`, `ideas-seed.md` — from `references/mcp-and-recipes-2026-08-29` + planning commit `4aad52e`
- `docs/mcp/`, `docs/recipes/`, `docs/sectors-api-and-mcp.md` — same MCP branch
- `docs/rest/` — from `references/rest-catalog-2026-08-29` + mining 3-file split from `references/rest-idx-mining-2026-08-29`
- `docs/cookbook/` — from `references/cookbook-idx-mining-2026-08-29`
- `docs/cookbook-v2/` — from `audit/f2-cookbook-2026-08-29`
- `docs/sectors/` + `docs/integration/` — live `sectors-hackathon` sectors ops (snapshot @614aca7, ref only)
- `.env.example`, `.gitignore` — hackathon root

Hackathon guides + all Sectors info — no runnable product, integration files are snapshots.
