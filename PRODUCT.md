# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

A React + TypeScript single-page app (Vite, Tailwind) served with a JSON API by FastAPI, shipped as one Docker image (`docker compose up`). The research pipeline, report and PDF generation stay in Python. See `docs/adr/0007-react-frontend-fastapi-backend-one-docker-image.md`.

## Users

Indonesian equity analysts who need company updates assembled from fragmented company data with visible sources and explicit evidence limits.

## Product Purpose

Sectoral turns locally cached Sectors company data into sourced company updates. The research agent selects data reads, produces an evidence-linked brief, and a deterministic validator checks citations before the report builder creates an update.

## Positioning

The product combines a cache-constrained research agent with deterministic citation validation. It shows what the available evidence supports and marks results partial when the cache cannot support every section.

## Operating Context

The current demo is a local browser workflow: enter an IDX ticker, follow research status, then review the company update and agent trace. Finished company updates are browsable in a report gallery (`/laporan`) with a PDF, a web version and the audit trace; a batch runner produces them for several tickers at once, and the landing page features one real report with its method chain.

The UI and every report are written in Bahasa Indonesia, with an English edition of each report (`*.en.html`, `*.en.pdf`) and an English UI toggle; financial terms stay in English by market convention (EBITDA, FCFF, WACC, capex).

The product is a Sectors Hackathon 2026 submission in the AI Agents & Assistants track: custom agent logic and an LLM component must be central. Submissions close 8 October 2026, 23:59 WIB, and the repository must stay public through at least 15 January 2027.

## Capabilities and Constraints

- A planning analyst agent writes a research question and hypotheses, chooses tool calls after seeing each result, ranks the company against its Sectors peer group, flags anomalies, and marks each hypothesis supported, not supported or unanswered with cited signals. It remembers earlier runs per ticker and reports what changed.
- Agent Sectors tools read only the local Sectors snapshot; no run spends Sectors API credits. An optional `web_news` tool adds dated Tavily headlines from Indonesian business media as context only.

- Market prices come from `data/sectors_cache.db`, or from a newer dated close in `data/market_quotes/` refreshed by `app.refresh`; the report builder can also use dated official issuer facts in `data/issuer_evidence/`.
- The research agent may select only cache endpoints available for the ticker. The host executes reads and records them in the trace.
- The LLM is used for agent reasoning, not as a market-data source.
- Citation validation checks the brief against rows actually read. Insufficient evidence remains visibly partial or missing; it is not silently replaced with web research, memory, analyst assumptions, or another dataset. Optional Tavily web news appears only as labelled, dated context; no figure comes from it, and every conclusion must also cite a Sectors signal.
- The app has no brokerage connection or trade execution.
- Six Method Gates (business model, data eligibility, ownership, cyclicality, life-cycle stage, output sanity) fix the order of valuation methods before any value is computed. The chain moves to the next method only when a method is insufficient, never because its result is unwelcome. This is the product's core differentiator and the landing page presents it as such.
- A company update has one of three release statuses. Production-ready: a sourced, reconciled driver forecast valued with the profile's primary method. Assumption-led: a rating and target price are published on a validated analyst scenario or the chain's last step, with every assumption labelled; the forecast is still not production-ready. Draft: the rating and target price are withheld and every blocker is named. An extreme result (upside above +100% or downside below -50%) is rated Review Required.
- Domain terms (Company Update, Signal, Method Chain, release statuses) are defined in `CONTEXT.md`; product copy follows that vocabulary.

## Brand Commitments

The product name is **Sectoral**, in the UI, reports, wordmark and docs. Only the repository URL (`mrayhanfadil/sektoral`) and a few internal identifiers (`SEKTORAL_LLM_*` variables) keep the older spelling.

The supplied Sectoral Design System sets primary blue `#0928B1`, white `#FFFFFF`, charcoal `#333333`, rule gray `#D9D9D9`, even table row `#B4C7FF`, Roboto typography, and chart series `#0928B1`, `#B4C7FF`, `#3ED628`, `#1DCD9F`, `#0047AB`, `#7596FF`. The wordmark uses an E-shaped three-bar mark in blue, teal, and green followed by `CTORAL`.

## Evidence on Hand

- Product overview, workflow, cache boundaries, and disclaimers: `README.md`.
- Local cache: `data/sectors_cache.db`.
- Report renderer and generated HTML/PDF: `app/render.py`, `app/build.py`.
- Web app: React + TypeScript + Tailwind in `web/` (pages in `web/src/pages/`, brand theme in `web/src/index.css`); API server `app/server.py`, jobs `app/jobs.py`, trace view `app/trace_view.py`, report summaries `app/gallery.py`.
- Docker: `Dockerfile`, `compose.yaml`.
- Batch runner for gallery reports: `app/batch.py`.
- Domain glossary and decisions: `CONTEXT.md`, `docs/adr/`.
- Brand SVG and embedded Roboto assets: `app/assets/brand/sectoral-logo.svg`, `app/assets/fonts/`.
- No verified customer testimonials or external benchmarks are documented. Market inputs beside the Sectors snapshot are dated Yahoo Finance snapshots that `app.refresh` stores; report builds never fetch prices live.

## Product Principles

- Ground every market-data claim in the local cache.
- Make source evidence and evidence gaps visible.
- Keep analytical output distinct from investment advice or execution.
- Prefer explicit partial or missing-evidence states over silent substitution.

## Accessibility & Inclusion

Use semantic, keyboard-accessible controls with visible focus states and readable contrast. The supplied design system specifies high-contrast blue/charcoal text on white and accessible chart labels/tooltips.
