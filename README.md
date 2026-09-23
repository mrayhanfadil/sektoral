# Sektoral

Sektoral helps Indonesian equity analysts turn fragmented company data into a sourced company update, while showing what the evidence supports and where it is still incomplete.

## How it works

The local browser flow is simple: enter an IDX ticker, follow its research status, then open the company update and agent trace. Behind the form, the research agent selects reads from the ticker's locally cached Sectors data and creates an evidence-linked brief. A deterministic validator checks its citations before the report builder creates the update. If the cache cannot support all sections, the UI labels the result partial and the report shows its evidence limits.

Sectors cache is the default market-price source. A newer dated close in `data/market_quotes/` may override a stale cached quote. The research agent reads `data/sectors_cache.db`; it does not call Sectors upstream. The deterministic report builder may also read dated, source-linked issuer releases from `data/issuer_evidence/`. No brokerage connection or trade execution is part of the product.

The builder shows Buy, Hold or Sell and a target price only when the selected method's release gate passes. An explicit assumption-led FY EV/EBITDA method can publish a mining target while separately retaining incomplete LoM/SOTP findings in the audit trace.

## Quickstart

From the repository root, copy `.env.example` to `.env` and set `MINIMAX_API_KEY` (or `SEKTORAL_LLM_API_KEY`) for the research agent. Never commit `.env` or share it in a recording. The workflow uses the local Sectors cache and does not need a Sectors API key at run time.

```bash
python3 -m app.web
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), select **Coba riset emiten**, enter a ticker, and select **Mulai riset**. Follow the status page, then open **Buka company update** or **Lihat jejak agent** when the run finishes. If evidence is incomplete, the UI says the analysis is partial. The browser server binds to localhost by default. The agent needs network access to its configured LLM endpoint, but market data comes only from the local Sectors cache. The BBCA CLI and browser workflows have been end-to-end tested on this working checkout; rerun QA on the frozen submission checkout before recording or submitting.

For a terminal-only run, use the one-command CLI below. It writes the HTML report and trace to `out/demo/`; `--pdf` is optional and requires PDF support. Omit it to use HTML only.

```bash
python3 -m app.research BBCA --out out/demo --pdf
```

Replace `BBCA` with another IDX ticker when its required rows are present in the local cache. The deterministic report builder without agent research remains available as `python3 -m app.build BBCA --out out/demo`. Both CLI commands use today's date for the report unless `--as-of YYYY-MM-DD` is supplied. The cached market price retains its own date, and issuer facts published later than the report date are excluded.

The one-command research flow now runs specialist assumption passes over dated ticker news and any local official interim release. They read the applicable rules from `spec/Instruksi-Report-v3.md` at run time and record an explicit zero effect for articles that only describe trading or index moves. A supported operating event can adjust the internal revenue or margin screen; macro risk can adjust an illustrative WACC or, for financial firms, Cost of Equity. The exact source, year, driver, magnitude, and rationale are preserved in the trace. On MiniMax-M3, the agents use adaptive thinking with an 8,192-token combined thinking-and-answer cap, the closest budget control exposed by its Chat API; other compatible models receive `reasoning_effort=high`.

For an internal mining draft with the historical extrapolation and valuation screens shown alongside the sourced actuals, add `--illustrative-scenarios`. When official interim evidence is available, the PDF also shows an agent-authored second-half/full-year scenario in the issuer's reporting currency. These screens remain separate when the FX and asset-level bridges are incomplete. The PDF labels the scenarios on every page and keeps the rating and target price withheld while the mining forecast and SOTP gates remain incomplete.

To opt into the validated FY scenario as a formal target and rating, use `--analyst-target`, for example `python3 -m app.research AMMN --out out/AMMN-formal --pdf --as-of 2026-09-24 --analyst-target`. This route requires a validated forecast agent scenario, an official interim release, a fresh post-release close and FX quote, an official balance-sheet bridge, and 6x/8x/10x sensitivity. The selected 8x multiple is an analyst assumption; the PDF discloses missing LoM/SOTP and the trace preserves its original blockers.

## Evidence and draft policy

- The research agent's inputs are limited to Sectors rows already present in `data/sectors_cache.db`. The forecast agent may also use reviewed local issuer source packs. The deterministic builder may use those source packs and dated market quote overrides. Assumptions proposed by the forecast agent are labeled, validated, and retained in the trace.
- The agent may select only cache endpoints available for that ticker. The host executes the reads and records them in the trace.
- The forecast assumption agent reads dated, ticker-specific cache news and reviewed local issuer releases. It may propose bounded changes to revenue growth, EBITDA margin, or an illustrative discount rate, with exact article matching and year-by-year provenance. An article about the share price alone receives zero financial effect. Unsupported or malformed proposals are rejected and left in the trace.
- A validation gate checks the research brief's citations against rows actually read. Failed validation or insufficient evidence must remain visible as a partial result or a clear missing-evidence result; do not present it as a completed conclusion.
- Do not record an old artifact as if it came from the current integrated command. Generate the demo output afresh and show the browser status and resulting report/trace.
- The report builder withholds recommendation labels and target prices until the selected method's source, forecast, and valuation checks pass. A formal assumption-led mining report does not mark the separate LoM/SOTP gate complete.

## Project map

| Path | Purpose |
|---|---|
| `app/` | Deterministic report intake, forecast, valuation, narrative, and rendering |
| `agents/research/` | Cache-constrained research agent, evidence checks, and trace data |
| `data/sectors_cache.db` | Local Sectors cache used as the only market-data source |
| `data/issuer_evidence/` | Dated local copies of metrics transcribed from official issuer releases |
| `spec/` | Report and output requirements |
| `docs/` | Sectors API/MCP reference, recipes, and implementation notes |
| `video-recording-guide.md` | Real-workflow video scripts and recording checks |
| `submission-checklist.md` | Hackathon submission requirements and deadline checklist |

## Sectors API and MCP reference

The product's demo path reads the local cache. The API and MCP guides below are reference material for cache intake and other Sectors integrations; do not imply that the integrated report run calls an upstream endpoint live.

- [Sectors API and MCP overview](docs/sectors-api-and-mcp.md)
- [MCP setup](docs/mcp/setup.md) and [tool catalogue](docs/mcp/tools.md)
- [REST endpoint reference](docs/rest/)
- [Agent recipes](docs/recipes/)
- [Cookbooks](docs/cookbook/) and [worked Python examples](docs/cookbook-v2/)

## Hackathon submission

The declared track is **AI Agents & Assistants**: custom-built agent logic and an AI/LLM component must be central to the product. Before submission, check the [official rules](https://hackathon.sectors.app/rules) and [track requirements](https://hackathon.sectors.app/tracks/ai-agents-assistants), then use the [submission checklist](submission-checklist.md). The repository must be public at submission and remain public through at least 7 January 2027 (90 days after the announced 9 October winners date).
