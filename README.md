# Sectoral

Sectoral helps Indonesian equity analysts turn fragmented company data into a sourced company update, while showing what the evidence supports and where it is still incomplete.

> **INFORMATION, NOT INVESTMENT ADVICE.** Sectoral is an information and analysis tool built on the Sectors Financial API. Its ratings and target prices are conditional model outputs, not recommendations. See [Disclaimer](#disclaimer).

## See it without running anything

[`samples/`](samples/) holds three finished company updates rebuilt from stored agent runs: a bank (BBRI), a copper and gold miner (AMMN) and an aviation-services company (GMFI). Each comes as a PDF and a web version in Indonesian and English (`*.en.*`), plus the audit trace that shows every tool call, agent decision and validation behind the report.

| Ticker | Report (PDF) | English (PDF) | Audit trace |
|---|---|---|---|
| BBRI | [BBRI.pdf](samples/BBRI.pdf) | [BBRI.en.pdf](samples/BBRI.en.pdf) | [BBRI-trace.html](samples/BBRI-trace.html) |
| AMMN | [AMMN.pdf](samples/AMMN.pdf) | [AMMN.en.pdf](samples/AMMN.en.pdf) | [AMMN-trace.html](samples/AMMN-trace.html) |
| GMFI | [GMFI.pdf](samples/GMFI.pdf) | [GMFI.en.pdf](samples/GMFI.en.pdf) | [GMFI-trace.html](samples/GMFI-trace.html) |

<!-- Demo videos: add the 60-second teaser and the judging video links here once uploaded. -->

## How it works

The local browser flow is simple: enter an IDX ticker, watch the agents work, then review the market-intelligence view, the company update and the agent trace.

**Planning analyst agent (`agents/analyst/`).** The run starts with an agent that writes a research question and testable hypotheses for the company type, then chooses tool calls turn by turn after seeing each result, and may call tools outside its plan when a result warrants it. Its tools mirror Sectors resources (`find_peers`, `rank_peers`, `quarterly_financials`, `price_history`, `foreign_flow`, `valuation_history`, `news`) but read only the local Sectors snapshot, so a run spends no API credits; a test asserts that the analyst modules never import the network client. An optional `web_news` tool adds dated Tavily headlines from Indonesian business media, limited to the 60 days before the data date (no look-ahead). It is context only: web articles carry no numbers into signals, and every finding and hypothesis verdict must also cite a Sectors signal. Put one or more keys in `.env` as `TAVILY_API_KEYS=key1,key2,...`; requests rotate round-robin and a key that is rejected or out of quota is skipped. Results are saved in the app database (`data/sectoral.db`, git-ignored), so repeating a run spends no Tavily credits; without keys the tool is simply unavailable. The Sectors tools return deterministic signals: peer ranks and medians (the Sectors peer table, or a related company's table that lists the ticker), year-on-year quarter moves, price versus IHSG, volume shifts, foreign-flow streaks, P/E versus history and peers, and a flow-versus-price divergence check. The agent then marks each hypothesis supported, not supported or unanswered, citing signal ids. A validator rejects prose that contains numbers (values are displayed from the cited signals), investment-advice wording or unknown signal ids, and asks the model to repair once; if the model still fails, a labelled host summary is shown instead. Each run is saved to the app database, briefs the next plan, and drives the "since the last run" diff and the research history list. The status page streams each step live.

After that, the research agent selects reads from the ticker's locally cached Sectors data and creates an evidence-linked brief. A deterministic validator checks its citations before the report builder creates the update. If the cache cannot support all sections, the UI labels the result partial and the report shows its evidence limits.

Sectors cache is the default market-price source. A newer dated close in `data/market_quotes/` may override a stale cached quote. The research agent reads `data/sectors_cache.db`; it does not call Sectors upstream. The deterministic report builder may also read dated, source-linked issuer releases from `data/issuer_evidence/`. No brokerage connection or trade execution is part of the product.

The builder shows Buy, Hold or Sell and a target price only when the selected method's release gate passes. An explicit assumption-led FY EV/EBITDA method can publish a mining target while separately retaining incomplete LoM/SOTP findings in the audit trace.

## Quickstart

From the repository root, copy `.env.example` to `.env` and set `MINIMAX_API_KEY` (or `SEKTORAL_LLM_API_KEY`) for the research agent. Never commit `.env` or share it in a recording. The workflow uses the local Sectors cache and does not need a Sectors API key at run time.

The quickest start is Docker, which builds the React app and runs it with the Python API and Chromium for PDFs in one image. The port is published on localhost only, and anyone who opens it may start a live run with your LLM key (`SECTORAL_LIVE_RUNS=open`, the default; see below for a public deployment):

```bash
docker compose up --build
```

Without Docker, build the frontend once and run the Python server (Python 3.12, Node 22):

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install chromium
npm --prefix web ci && npm --prefix web run build
.venv/bin/python -m app.server
```

Run the tests with `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest -q` and `npm --prefix web test`.

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

- **Agents read only the local evidence.** The research agent reads the ticker's rows in `data/sectors_cache.db`, and the host runs and logs every read. The forecast agent also reads dated news and reviewed issuer releases.
- **Every claim is checked.** A validator matches the brief's citations to the rows actually read. Forecast assumptions must cite a source the validator accepts, and an article about the share price alone changes nothing. Rejected proposals stay in the audit trace.
- **No rating until the gates pass.** The rating and target price appear only when the chosen method's source, forecast and valuation checks pass. Otherwise the report is a labelled draft that names every blocker, and partial evidence is shown as partial.
- **Publishing.** A report that clears the gates publishes automatically. Set `SECTORAL_AUTO_PUBLISH=0` to require an authenticated reviewer to approve it first (`SECTORAL_REVIEWERS` in `.env.example`; only SHA-256 token digests are stored).
- **Stale reports are flagged.** When a newer official period is due or out, the report is labelled stale. `python -m app.publication_monitor --folder out/reports` lists each report as current, stale or due for withdrawal; the rules live in `app/release_policy.py`.
- **Live runs cost credits.** `SECTORAL_LIVE_RUNS` sets who may start one: `open` (the local default), `token` (only with `SECTORAL_RUN_TOKEN`; use it for any public deployment) or `off`. Anyone can still replay a stored run from its audit trace.

## Project map

| Path | Purpose |
|---|---|
| `app/` | Deterministic report intake, forecast, valuation, narrative, and rendering; `app/server.py` is the FastAPI web server |
| `web/` | React + TypeScript + Tailwind web app (landing, research, run status, gallery, audit trace) |
| `Dockerfile`, `compose.yaml` | One image with the built web app, the Python API and Chromium for PDFs |
| `agents/analyst/` | Planning analyst agent: local-data tools, peer/anomaly signals, hypothesis verdicts, run memory |
| `agents/research/` | Cache-constrained research agent, evidence checks, and trace data |
| `data/sectors_cache.db` | Snapshot of Sectors REST v2 responses, the core data source of every run |
| `app/sectors.py`, `app/topup.py` | Sectors REST v2 client and the top-up command that fills the snapshot (credits logged in `data/credit_log.jsonl`) |
| `samples/` | Finished sample reports and audit traces |
| `data/issuer_evidence/` | Dated local copies of metrics transcribed from official issuer releases |
| `data/sectoral.db` | App database (git-ignored): agent memory, forecast plans, fetched news, peer and FX snapshots, and the report, trace and manifest of every run. Import older JSON caches with `python -m app.store_import`. Run outputs are keyed by folder relative to the project (`out/reports::AMMN`), so the host and the Docker image share them; rewrite keys written by older versions once with `python -m app.outputs --migrate --root /app --root <host checkout path>` |
| `spec/` | Report and output requirements |
| `docs/` | Sectors API/MCP reference, recipes, and implementation notes |
| `docs/hackathon/` | Rules, submission checklist, and team operations |
| `docs/plans/` | Implementation plans and project planning notes |

## How Sectors data powers Sectoral

Sectors is Sectoral's core data source; without it the agents have no tools and the report builder has no financials. `app/sectors.py` is a Sectors REST v2 client (`https://api.sectors.app/v2`), and `python -m app.topup <package> <target> --live` uses it to fetch the endpoints a ticker needs into `data/sectors_cache.db`. Every upstream call is recorded in `data/credit_log.jsonl`. The committed snapshot holds 314 responses from 150 endpoints, fetched 12 to 23 September 2026, across the `company`, `financials`, `daily`, `index-daily`, `foreign-flow`, `broker-summary`, `subsector(s)`, `mining`, `filings`, `news`, `close`, `listing-performance` and `suspensions` families.

Research runs then read that snapshot instead of calling Sectors live. A run is reproducible, it spends no Sectors credits, and the release gate (`app/release.py`) blocks a rating unless the reported actuals cite a `sectors_cache` row or an official issuer release. The analyst agent's tools (`find_peers`, `rank_peers`, `quarterly_financials`, `price_history`, `foreign_flow`, `valuation_history`, `news`) are thin wrappers over these Sectors resources.

### Sectors API and MCP reference

The guides below are reference material for snapshot intake and other Sectors integrations.

- [Sectors API and MCP overview](docs/sectors-api-and-mcp.md)
- [MCP setup](docs/mcp/setup.md) and [tool catalogue](docs/mcp/tools.md)
- [REST endpoint reference](docs/rest/)
- [Agent recipes](docs/recipes/)
- [Cookbooks](docs/cookbook/) and [worked Python examples](docs/cookbook-v2/)

## Hackathon submission

The declared track is **AI Agents & Assistants**: custom-built agent logic and an AI/LLM component must be central to the product. Before submission, check the [official rules](https://hackathon.sectors.app/rules) and [track requirements](https://hackathon.sectors.app/tracks/ai-agents-assistants), then use the [submission checklist](docs/hackathon/submission-checklist.md). The repository must be public at submission and remain public through at least 15 January 2027 (90 days after the announced 17 October winners date). Submissions close 8 October 2026, 23:59 WIB.

## Data sources and attribution

- **Sectors Financial API** ([sectors.app](https://sectors.app)): company profiles, financials, prices, IHSG, foreign flow, broker summary, sub-sector reports, filings and news. This is the core data source.
- **Issuer releases** (`data/issuer_evidence/`): metrics transcribed from official IDX filings, each with its source link and date.
- **Yahoo Finance via `yfinance`** (`app.refresh`): dated closes, USD/IDR, the US 10-year Treasury yield, commodity prices and peer snapshots, stored with their dates.
- **Consensus estimates** (`data/consensus/`): dated Investing.com snapshots, shown beside the model's target for comparison and cited by URL.
- **News** (Tavily search and cited outlets): headlines and article text used only as dated context. Each item is cited by URL, and no number is taken from it.

## Disclaimer

**INFORMASI, BUKAN SARAN INVESTASI.** Sectoral adalah alat informasi dan analisis data pasar modal Indonesia berdasarkan data dari Sectors Financial API. Rating dan target harga di laporan adalah hasil model bersyarat atas asumsi dan sumber yang dinyatakan, bukan rekomendasi, prediksi, atau saran investasi. Keputusan investasi sepenuhnya tanggung jawab pembaca. Selalu lakukan riset mandiri dan konsultasikan dengan penasihat keuangan berlisensi sebelum berinvestasi. Kinerja masa lalu tidak menjamin hasil di masa depan. Data bersumber dari Sectors (https://sectors.app) dan IDX; akurasinya tunduk pada kualitas data sumber.

**INFORMATION, NOT INVESTMENT ADVICE.** Sectoral is an information and analysis tool for Indonesian capital-market data sourced from the Sectors Financial API. The ratings and target prices in its reports are conditional model outputs of stated assumptions and sources, not recommendations, predictions or investment advice. Investment decisions are the reader's sole responsibility. Always do independent research and consult a licensed financial advisor before investing. Past performance does not guarantee future results. Data is sourced from Sectors (https://sectors.app) and IDX; its accuracy is subject to source quality. Sectoral is not connected to any broker and does not execute trades.
