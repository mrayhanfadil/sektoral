# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Indonesian equity analysts who need company updates assembled from fragmented company data with visible sources and explicit evidence limits.

## Product Purpose

Sectoral turns locally cached Sectors company data into sourced company updates. The research agent selects data reads, produces an evidence-linked brief, and a deterministic validator checks citations before the report builder creates an update.

## Positioning

The product combines a cache-constrained research agent with deterministic citation validation. It shows what the available evidence supports and marks results partial when the cache cannot support every section.

## Operating Context

The current demo is a local browser workflow: enter an IDX ticker, follow research status, then review the company update and agent trace.

## Capabilities and Constraints

- Market data is read only from `data/sectors_cache.db`, the local Sectors cache.
- The research agent may select only cache endpoints available for the ticker. The host executes reads and records them in the trace.
- The LLM is used for agent reasoning, not as a market-data source.
- Citation validation checks the brief against rows actually read. Insufficient evidence remains visibly partial or missing; it is not silently replaced with web research, memory, analyst assumptions, or another dataset.
- The app has no brokerage connection or trade execution.
- Outputs are information and analytical scenarios, not investment recommendations or financial advice.

## Brand Commitments

The supplied Sectoral Design System sets primary blue `#0928B1`, white `#FFFFFF`, charcoal `#333333`, rule gray `#D9D9D9`, even table row `#B4C7FF`, Roboto typography, and chart series `#0928B1`, `#B4C7FF`, `#3ED628`, `#1DCD9F`, `#0047AB`, `#7596FF`. The wordmark uses an E-shaped three-bar mark in blue, teal, and green followed by `CTORAL`.

## Evidence on Hand

- Product overview, workflow, cache boundaries, and disclaimers: `README.md`.
- Local cache: `data/sectors_cache.db`.
- Report renderer and generated HTML/PDF: `app/render.py`, `app/build.py`.
- Browser workflow: `app/web.py`.
- Brand SVG and embedded Roboto assets: `app/assets/brand/sectoral-logo.svg`, `app/assets/fonts/`.
- No verified customer testimonials, external benchmarks, or live market-data integrations are documented.

## Product Principles

- Ground every market-data claim in the local cache.
- Make source evidence and evidence gaps visible.
- Keep analytical output distinct from investment advice or execution.
- Prefer explicit partial or missing-evidence states over silent substitution.

## Accessibility & Inclusion

Use semantic, keyboard-accessible controls with visible focus states and readable contrast. The supplied design system specifies high-contrast blue/charcoal text on white and accessible chart labels/tooltips.
