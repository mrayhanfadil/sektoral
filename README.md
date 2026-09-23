# Sektoral

Sektoral helps Indonesian equity analysts turn fragmented company data into a sourced company update, while showing what the evidence supports and where it is still incomplete.

## How it works

The local browser flow is simple: enter an IDX ticker, follow its research status, then open the company update and agent trace. Behind the form, the research agent selects reads from the ticker's locally cached Sectors data and creates an evidence-linked brief. A deterministic validator checks its citations before the report builder creates the update. If the cache cannot support all sections, the UI labels the result partial and the report shows its evidence limits.

Sectors data is the product's only market-data source. The research run reads `data/sectors_cache.db`; it does not call Sectors upstream or fetch market data from the web. The LLM endpoint is used for agent reasoning, not as a market-data source. No brokerage connection or trade execution is part of the product.

The product provides information and analysis for research. It does not give investment recommendations or financial advice. Outputs should be read as analytical scenarios, not instructions to buy, sell, or hold a security.

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

Replace `BBCA` with another IDX ticker when its required rows are present in the local cache. The deterministic report builder without agent research remains available as `python3 -m app.build BBCA --out out/demo`.

## Evidence and draft policy

- Inputs are limited to the Sectors rows already present in `data/sectors_cache.db`. Missing ticker data is not silently replaced with web research, memory, analyst assumptions, or another local dataset.
- The agent may select only cache endpoints available for that ticker. The host executes the reads and records them in the trace.
- When current ticker-specific news is cached alongside relevant quarterly metrics, the agent paraphrases the article and connects it to the operating context in a single cited insight. The host withholds that link if the evidence or citation does not validate.
- A validation gate checks the research brief's citations against rows actually read. Failed validation or insufficient evidence must remain visible as a partial result or a clear missing-evidence result; do not present it as a completed conclusion.
- Do not record an old artifact as if it came from the current integrated command. Generate the demo output afresh and show the browser status and resulting report/trace.
- No output is an investment recommendation. Remove recommendation labels and price targets from any public-facing demo view unless the team has reviewed them against the hackathon's no-financial-advice rule.

## Project map

| Path | Purpose |
|---|---|
| `app/` | Deterministic report intake, forecast, valuation, narrative, and rendering |
| `agents/research/` | Cache-constrained research agent, evidence checks, and trace data |
| `data/sectors_cache.db` | Local Sectors cache used as the only market-data source |
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
