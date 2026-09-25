# Sektoral

Sektoral helps Indonesian equity analysts turn fragmented company data into a sourced company update, while showing what the evidence supports and where it is still incomplete.

## How it works

The local browser flow is simple: enter an IDX ticker, watch the agents work, then review the market-intelligence view, the company update and the agent trace.

**Planning analyst agent (`agents/analyst/`).** The run starts with an agent that writes a research question and testable hypotheses for the company type, then chooses tool calls turn by turn after seeing each result, and may call tools outside its plan when a result warrants it. Its tools mirror Sectors resources (`find_peers`, `rank_peers`, `quarterly_financials`, `price_history`, `foreign_flow`, `valuation_history`, `news`) but read only the local Sectors snapshot, so a run spends no API credits; a test asserts that the analyst modules never import the network client. An optional `web_news` tool adds dated Tavily headlines from Indonesian business media, limited to the 60 days before the data date (no look-ahead). It is context only: web articles carry no numbers into signals, and every finding and hypothesis verdict must also cite a Sectors signal. Put one or more keys in `.env` as `TAVILY_API_KEYS=key1,key2,...`; requests rotate round-robin and a key that is rejected or out of quota is skipped. Results are saved in the app database (`data/sectoral.db`, git-ignored), so repeating a run spends no Tavily credits; without keys the tool is simply unavailable. The Sectors tools return deterministic signals: peer ranks and medians (the Sectors peer table, or a related company's table that lists the ticker), year-on-year quarter moves, price versus IHSG, volume shifts, foreign-flow streaks, P/E versus history and peers, and a flow-versus-price divergence check. The agent then marks each hypothesis supported, not supported or unanswered, citing signal ids. A validator rejects prose that contains numbers (values are displayed from the cited signals), investment-advice wording or unknown signal ids, and asks the model to repair once; if the model still fails, a labelled host summary is shown instead. Each run is saved to the app database, briefs the next plan, and drives the "since the last run" diff and the research history list. The status page streams each step live.

After that, the research agent selects reads from the ticker's locally cached Sectors data and creates an evidence-linked brief. A deterministic validator checks its citations before the report builder creates the update. If the cache cannot support all sections, the UI labels the result partial and the report shows its evidence limits.

Sectors cache is the default market-price source. A newer dated close in `data/market_quotes/` may override a stale cached quote. The research agent reads `data/sectors_cache.db`; it does not call Sectors upstream. The deterministic report builder may also read dated, source-linked issuer releases from `data/issuer_evidence/`. No brokerage connection or trade execution is part of the product.

The builder shows Buy, Hold or Sell and a target price only when the selected method's release gate passes. An explicit assumption-led FY EV/EBITDA method can publish a mining target while separately retaining incomplete LoM/SOTP findings in the audit trace.

## Quickstart

From the repository root, copy `.env.example` to `.env` and set `MINIMAX_API_KEY` (or `SEKTORAL_LLM_API_KEY`) for the research agent. Never commit `.env` or share it in a recording. The workflow uses the local Sectors cache and does not need a Sectors API key at run time.

The quickest start is Docker, which builds the React app and runs it with the Python API and Chromium for PDFs in one image:

```bash
docker compose up --build
```

Without Docker, build the frontend once and run the Python server (Python 3.12, Node 22):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium
npm --prefix web ci && npm --prefix web run build
.venv/bin/python -m app.server
```

For frontend work, run `npm --prefix web run dev` next to the server; Vite serves the app on port 5173 and proxies `/api` and `/files` to it.

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), select **Coba riset emiten**, enter a ticker, and select **Mulai riset**. Follow the status page, then open **Buka company update** or **Lihat jejak agent** when the run finishes. If evidence is incomplete, the UI says the analysis is partial. The server binds to localhost by default (the Docker port is published on localhost only). The agent needs network access to its configured LLM endpoint. Report builds do not fetch market data: they read the local Sectors cache and the dated snapshots that `app.refresh` stores (below). The BBCA CLI and browser workflows have been end-to-end tested on this working checkout; rerun QA on the frozen submission checkout before recording or submitting.

**Report gallery.** `/laporan` lists every finished company update in a reports folder (rating, target, method, status, cover thumbnail, PDF, web version and audit trace), and the landing page features one real report with its method chain. Fill the folder with a batch run, then point the server at it; add `--pdf` so runs started in the browser also produce a PDF and appear in the gallery when they finish. In Docker the gallery reads `out/reports`, so a batch run there shows up without flags:

```bash
python3 -m app.batch BBCA BBRI AMMN SSIA INET POWR JPFA GMFI --jobs 2 --out out/reports --pdf
.venv/bin/python -m app.server --reports out/reports --pdf
```

**Refresh market data before a run.** Beside the Sectors cache, reports read five dated inputs: the USD/IDR close, the US Treasury 10-year yield (the risk-free rate of a US$ reporter's DCF, which is built and discounted in US$), copper and gold prices (used when the Sectors series is more than 45 days old), each ticker's closing prices in `data/market_quotes/`, and peer snapshots for the curated peer groups in `data/peer_groups/`. One command refreshes all of them from Yahoo Finance (network and `yfinance` required). Pass the report date and the tickers, or add `--refresh-data` to a batch run:

```bash
.venv/bin/python -m app.refresh --as-of 2026-09-24 BBCA BBRI AMMN SSIA INET POWR JPFA GMFI
.venv/bin/python -m app.refresh --as-of 2026-09-24 AMMN --only commodity peers
python3 -m app.batch BBCA AMMN --as-of 2026-09-24 --out out/reports --refresh-data
```

A step that fails is reported and the others still run; a report built on a stale input says so. Review the rewritten `data/market_quotes/*.json` before committing them. The single steps remain available as `python -m app.rates`, `python -m app.commodity`, `python -m app.market_quote`, `python -m app.peer_fundamentals --group <T>` and `python3 scripts/refresh_usd_idr.py`.

For a terminal-only run, use the one-command CLI below. It writes the HTML report and trace to `out/demo/`; `--pdf` is optional and requires PDF support. Omit it to use HTML only.

```bash
python3 -m app.research BBCA --out out/demo --pdf
```

Replace `BBCA` with another IDX ticker when its required rows are present in the local cache. The deterministic report builder without agent research remains available as `python3 -m app.build BBCA --out out/demo`. Both CLI commands use today's date for the report unless `--as-of YYYY-MM-DD` is supplied. The cached market price retains its own date, and issuer facts published later than the report date are excluded.

The one-command research flow now runs specialist assumption passes over dated ticker news and any local official interim release. They read the applicable rules from `spec/Instruksi-Report-v3.md` at run time and record an explicit zero effect for articles that only describe trading or index moves. A supported operating event can adjust the internal revenue or margin screen; macro risk can adjust an illustrative WACC or, for financial firms, Cost of Equity. The exact source, year, driver, magnitude, and rationale are preserved in the trace. On MiniMax-M3, the agents use adaptive thinking with an 8,192-token combined thinking-and-answer cap, the closest budget control exposed by its Chat API; other compatible models receive `reasoning_effort=high`.

For an internal mining draft with the historical extrapolation and valuation screens shown alongside the sourced actuals, add `--illustrative-scenarios`. When official interim evidence is available, the PDF also shows an agent-authored second-half/full-year scenario in the issuer's reporting currency. These screens remain separate when the FX and asset-level bridges are incomplete. The PDF labels the scenarios on every page and keeps the rating and target price withheld while the mining forecast and SOTP gates remain incomplete.

To opt into the validated FY scenario as a formal target and rating, use `--analyst-target`, for example `python3 -m app.research AMMN --out out/AMMN-formal --pdf --as-of 2026-09-24 --analyst-target`. This route requires a validated forecast agent scenario, an official interim release, a fresh post-release close and FX quote, an official balance-sheet bridge, and 6x/8x/10x sensitivity. The selected 8x multiple is an analyst assumption; the PDF discloses missing LoM/SOTP and the trace preserves its original blockers. A separate out-year agent pass supplies bounded FY+1 to FY+4 growth and margin assumptions; the deterministic engine calculates earnings from them and labels the results as analyst scenarios, not physical LoM forecasts.

A validated forecast plan is stored in the app database under a fingerprint of its evidence: the official release, dated headlines, spec version and model. Rerunning a ticker on the same evidence reuses the plan, so the target price does not drift between LLM calls; new evidence triggers a fresh agent pass, and `--refresh-assumptions` forces one. The formal route needs a USD/IDR close dated within seven days of the report date, stored in the app database; `app.refresh` updates it.

Every report also carries sections built directly from the local Sectors snapshot (`app/report_extras.py`): commodity prices and the Sectors sub-sector report, a peer table with P/E and P/B cross-checks (the curated group in `data/peer_groups/` when the issuer has one, with the reason for each peer, else the Sectors peer table), major shareholders and foreign flow, and multi-year income statement, balance sheet and ratios. Mining targets add a commodity-price x USD/IDR sensitivity recomputed through EBITDA, net profit and the target, and a table of interim output against full-year guidance. Pages follow the spec order and exhibits are numbered in reading order.

## Evidence and draft policy

- The research agent's inputs are limited to Sectors rows already present in `data/sectors_cache.db`. The forecast agent may also use reviewed local issuer source packs. The deterministic builder may use those source packs and dated market quote overrides. Assumptions proposed by the forecast agent are labeled, validated, and retained in the trace.
- The agent may select only cache endpoints available for that ticker. The host executes the reads and records them in the trace.
- The forecast assumption agent reads dated, ticker-specific cache news and reviewed local issuer releases. It may propose bounded changes to revenue growth, EBITDA margin, or an illustrative discount rate, with exact article matching and year-by-year provenance. An article about the share price alone receives zero financial effect. Unsupported or malformed proposals are rejected and left in the trace.
- A validation gate checks the research brief's citations against rows actually read. Failed validation or insufficient evidence must remain visible as a partial result or a clear missing-evidence result; do not present it as a completed conclusion.
- Do not record an old artifact as if it came from the current integrated command. Generate the demo output afresh and show the browser status and resulting report/trace.
- The report builder withholds recommendation labels and target prices until the selected method's source, forecast, and valuation checks pass. A formal assumption-led mining report does not mark the separate LoM/SOTP gate complete.
- A report that passes its checks is still a draft until an analyst approves the Forecast Plan it was built on (`app/assumption_review.py`). The approval can come from the review panel on the report's trace page (`/laporan/<T>/jejak`) or from `python -m app.assumption_review approve --folder out/reports --reviewer "Nama" [--edit "path=value:alasan"] <T>`. The analyst can approve the plan as written or change its numeric drivers; every change needs a reason. Changes rebuild the report offline, with no agent call. The approval records the reviewer, the time, each change and the plan fingerprint it covers, both in the app database and in the Audit Trace. A new run replaces the plan, so the report needs review again. The web panel approves only when the server runs with `SECTORAL_REVIEW_TOKEN` set, and the reviewer enters that token.

## Project map

| Path | Purpose |
|---|---|
| `app/` | Deterministic report intake, forecast, valuation, narrative, and rendering; `app/server.py` is the FastAPI web server |
| `web/` | React + TypeScript + Tailwind web app (landing, research, run status, gallery, audit trace) |
| `Dockerfile`, `compose.yaml` | One image with the built web app, the Python API and Chromium for PDFs |
| `agents/analyst/` | Planning analyst agent: local-data tools, peer/anomaly signals, hypothesis verdicts, run memory |
| `agents/research/` | Cache-constrained research agent, evidence checks, and trace data |
| `data/sectors_cache.db` | Local Sectors cache used as the only market-data source |
| `data/issuer_evidence/` | Dated local copies of metrics transcribed from official issuer releases |
| `data/sectoral.db` | App database (git-ignored): agent memory, forecast plans, fetched news, peer and FX snapshots, and the report, trace and manifest of every run. Import older JSON caches with `python -m app.store_import`. Run outputs are keyed by folder relative to the project (`out/reports::AMMN`), so the host and the Docker image share them; rewrite keys written by older versions once with `python -m app.outputs --migrate --root /app --root <host checkout path>` |
| `spec/` | Report and output requirements |
| `docs/` | Sectors API/MCP reference, recipes, and implementation notes |
| `docs/hackathon/` | Rules, submission checklist, and team operations |
| `docs/plans/` | Implementation plans and project planning notes |

## Sectors API and MCP reference

The product's demo path reads the local cache. The API and MCP guides below are reference material for cache intake and other Sectors integrations; do not imply that the integrated report run calls an upstream endpoint live.

- [Sectors API and MCP overview](docs/sectors-api-and-mcp.md)
- [MCP setup](docs/mcp/setup.md) and [tool catalogue](docs/mcp/tools.md)
- [REST endpoint reference](docs/rest/)
- [Agent recipes](docs/recipes/)
- [Cookbooks](docs/cookbook/) and [worked Python examples](docs/cookbook-v2/)

## Hackathon submission

The declared track is **AI Agents & Assistants**: custom-built agent logic and an AI/LLM component must be central to the product. Before submission, check the [official rules](https://hackathon.sectors.app/rules) and [track requirements](https://hackathon.sectors.app/tracks/ai-agents-assistants), then use the [submission checklist](docs/hackathon/submission-checklist.md). The repository must be public at submission and remain public through at least 15 January 2027 (90 days after the announced 17 October winners date). Submissions close 8 October 2026, 23:59 WIB.
