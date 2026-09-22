# n8n — AI-Powered Stock Analyst (natural-language screener + parallel enrichment + LLM analysis)

> Source: <https://docs.sectors.app/recipes/non-programmatical-tools/04-n8n/02-n8n-natural-language-screener>
> Author of original recipe: Andreas Christianto, Mar 2026
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

Build an **AI stock analyst chatbot** in n8n:

- User sends a natural-language query (e.g. "top 5 banks by market cap").
- Sectors v2 NLQ screener returns matching companies.
- Each company gets **enriched in parallel** across two API endpoints (valuation + revenue segments).
- All enriched data is bundled and sent to an LLM (Claude / OpenAI / Groq / Gemini) for analysis.
- LLM response is returned to the chat.

This is the canonical **Track 1 (AI agents / assistants)** build. You get a chat UI, an LLM, a tool-call fan-out pattern, and Sectors' NLQ screener all in one workflow.

## When to use this approach

- You're pitching an AI analyst for the hackathon.
- You want to show off **multi-tool LLM orchestration** without writing a ReAct loop in Python.
- You want a public chat URL that judges can paste into a browser tab.

## Hackathon track fit

| Track | Fit | Why |
|-------|-----|-----|
| Track 1 — AI agents / assistants | **highest** | This is literally the brief. |
| Track 2 — Automation workflows | high | Schedule the chat trigger → email the daily analysis. |
| Track 3 — Market intelligence / apps | high | Wrap the chat in a branded web page; the chat IS the app. |

## Cost estimate

| Layer | Cost |
|-------|------|
| n8n Cloud | ~€20/mo (or free if self-hosted) |
| Sectors API per chat turn | ~5 credits (1 screener + 2 × N enrichments) — `N = limit` from screener |
| LLM per turn | varies — Claude Sonnet ~$0.01–0.05 per analysis; GPT-4o-mini cheaper; Groq Llama 3 free tier usable |

For a 5-company result with 2 parallel branches: 1 + 10 = **11 Sectors API calls per chat turn**. At 1,000 hackathon credits you can sustain ~90 chat turns.

## Prerequisites

- Sectors Insider-plan API key (or hackathon onboarding).
- n8n Cloud or self-hosted instance.
- LLM API key for one of: Anthropic Claude, OpenAI, Groq, Gemini (the original guide uses Claude).
- Familiarity with n8n basics — read [`n8n-api.md`](n8n-api.md) first if you're new.

## Architecture: the fan-out / fan-in pattern

```
Chat Trigger
    │
    ▼
Sectors Screener (NLQ via `q` param)
    │
    ▼
Split Out (results[] → one item per company)
    │
    ├──── Branch A ──► HTTP Request (company report, sections=overview,valuation)
    │
    └──── Branch B ──► HTTP Request (revenue segments)
                │
                ▼
           Merge (by Position)
                │
                ▼
           Aggregate (all into single list under `companies`)
                │
                ▼
           Code (build AI prompt from JSON)
                │
                ▼
           AI Agent (Claude/OpenAI/Groq/Gemini)
                │
                ▼
           Chat Response
```

The pattern — **fan out, enrich, fan in** — is reusable any time you need to call multiple APIs per item in a list.

## Workflow configuration (10 nodes)

### 1. Chat Trigger (`When chat message received`)

- Toggle **Make Chat Publicly Available** ON.
- **Initial Message(s)**:

  ```
  Hi! I'm your Sectors AI analyst. Ask me about Indonesian stocks — for example:
  • 'top 5 banks by market cap'
  • 'top 3 coal companies by revenue in 2023'
  • 'top 5 companies in LQ45 by market cap'
  ```

- Copy the **Chat URL** for testing later.

### 2. Sectors Screener (HTTP Request)

| Field | Value |
|-------|-------|
| Method | `GET` |
| URL | `https://api.sectors.app/v2/companies/` |
| Authentication | Header Auth → Sectors credential |
| Query: `q` | `{{ $json.chatInput }}` |
| Query: `limit` | `5` |
| Query: `include_query_values` | `true` |

`include_query_values=true` returns an `llm_translation` field that shows how the API parsed the natural language — useful for debugging when the AI gets weird results.

### 3. Split Out (`Split Companies`)

- **Fields To Split Out**: `results`

After this node, each company becomes an independent item flowing downstream. Change `limit` to 10 and the workflow automatically scales.

### 4. Branch A — Overview and Valuation (HTTP Request)

| Field | Value |
|-------|-------|
| Method | `GET` |
| URL | `https://api.sectors.app/v2/company/report/{{ $json.symbol.replace('.JK', '').replace('.jk', '') }}/` |
| Authentication | Header Auth → Sectors credential |
| Query: `sections` | `overview,valuation` |

The URL expression strips the `.JK` suffix because the Sectors API REST tolerates it but Bare URL expressions are cleaner.

### 5. Branch B — Revenue Segments (HTTP Request)

| Field | Value |
|-------|-------|
| Method | `GET` |
| URL | `https://api.sectors.app/v2/company/segments/{{ $json.symbol.replace('.JK', '').replace('.jk', '') }}/2024/` |
| Authentication | Header Auth → Sectors credential |

No query parameters. Note: the segments endpoint requires `financial_year` in the URL — pick the latest reported fiscal year (use `/v2/company/quarterly-financial-dates/{symbol}/` first if unsure).

### 6. Merge Company Data (`Merge` node)

- **Mode**: `Combine`
- **Combine By**: `Position`

Position-based merging pairs item 1 from Branch A with item 1 from Branch B (and so on). Both branches inherit the company order from `Split Out`, so position is reliable.

### 7. Aggregate Reports (`Aggregate` node)

- **Aggregate**: `All Item Data (Into a Single List)`
- **Put Output in Field**: `companies`

After this node, you have a single item whose `companies` array contains every enriched company.

### 8. Build AI Prompt (`Code` node, JavaScript)

```javascript
const data = $input.all()[0].json;
const userQuery = data.chatInput ?? data.query ?? '(no query)';
const companies = data.companies ?? [];

const lines = companies.map(c => {
  const v = c?.overview_valuation ?? {};
  const segs = c?.revenue_segments ?? {};
  return [
    `Company: ${v.symbol ?? '?'} (${v.company_name ?? '?'})`,
    `Sector: ${v.sector ?? '?'} / Sub-sector: ${v.sub_sector ?? '?'}`,
    `Market cap: Rp ${(v.market_cap ?? 0).toLocaleString('id-ID')}`,
    `P/E: ${v.pe_ratio?.toFixed(2) ?? 'n/a'} | P/B: ${v.pb_ratio?.toFixed(2) ?? 'n/a'} | ROE: ${v.roe_pct?.toFixed(2) ?? 'n/a'}%`,
    `Revenue breakdown: ${JSON.stringify(segs)}`,
    '---',
  ].join('\n');
});

const prompt = [
  `You are an equity research analyst. The user asked: "${userQuery}".`,
  '',
  'Below are the matching companies from the Sectors API with valuation and revenue-segments data:',
  ...lines,
  '',
  'Write a concise comparative analysis (3 short paragraphs). Highlight why each company is on the list, contrast valuation profiles, and flag any single-stock risks (high P/E, weak revenue diversification). Avoid generic boilerplate.',
].join('\n');

return [{ json: { prompt } }];
```

(Adjust the field names to match your actual response shape — `overview_valuation` and `revenue_segments` are positional merge products here.)

### 9. AI Agent (`@n8n/n8n-nodes-langchain.agent`)

- **Prompt**: `{{ $json.prompt }}`
- Connect a chat-model sub-node (next step).

### 10. Chat Model sub-node

Pick one:
- **Anthropic Chat Model** (Claude Sonnet 4.5 / Haiku 4.5)
- **OpenAI Chat Model** (gpt-4o-mini for cost, gpt-4o for quality)
- **Groq Chat Model** (Llama 3 free tier — fast and cheap)
- **Google Gemini Chat Model** (gemini-2.0-flash for cost, gemini-2.5-pro for quality)

Plug in your API key for whichever provider you pick.

### Test and publish

1. Click `Execute workflow`.
2. Open the **Chat URL** from Step 1 in a browser.
3. Try a query: "top 5 banks by market cap".
4. Verify the AI returns a structured analysis (not just a list of tickers).
5. Click `Publish`, name it (`v1.0`).

## NLQ query patterns that work well

The Sectors v2 NLQ screener translates natural language to structured filters. Patterns that consistently work:

| Pattern | Example |
|---------|---------|
| Index membership | "top 5 companies in LQ45 by market cap" |
| Sector + sub-sector | "top 5 banks by market cap" |
| Time-filtered revenue | "top 3 coal mining companies by revenue in 2023" |
| Financial metric | "companies with highest dividend yield" |
| Combined | "top 5 companies by revenue growth in 2023" |

Patterns to avoid: vague superlatives without a metric ("best", "hottest"), long compound sentences with multiple filters.

## Known pitfalls

- **`.JK` stripping**: when the screener returns symbols, they include `.JK`. Always strip before composing downstream URLs.
- **`limit` cost**: every additional company adds two API calls (Branch A + Branch B). `limit=10` = 21 calls per chat turn. Don't exceed your plan's comfort zone.
- **LLM hallucinations**: the AI will sometimes invent valuation numbers if your prompt is missing fields. Always use the actual JSON fields from the API, not paraphrases.
- **Empty results**: if the screener returns 0 companies, the LLM gets an empty array. Defensive code in the Code node — fall back to a "no companies matched" message.
- **Branch A response shape**: the `sections=overview,valuation` response combines both sections into a flat object, but the **merge expects a specific shape**. Run the workflow once with only Branch A wired up and inspect the output before enabling Branch B. Adjust the Code node field names to match.
- **`include_query_values=true`** is for debugging. Disable it in production to save a few hundred bytes of response.

## Production hardening (post-hackathon)

- **Cache the screener response** for ~5 minutes to absorb duplicate queries.
- **Rate-limit the chat trigger** via n8n's built-in rate limiter or a Redis-based limiter.
- **Log every LLM call** to a `chat_logs` table (Postgres, Supabase, Sheets) — useful for debugging hallucinations.
- **Set max tokens** on the LLM node (~500) to prevent runaway responses.
- **Switch to Anthropic Haiku 4.5 or Groq Llama 3** if cost is the dominant concern.

## Cross-links

- General n8n integration (Workflows 1+2): [`n8n-api.md`](n8n-api.md)
- MCP equivalent (no n8n needed): [`../mcp/setup.md`](../mcp/setup.md) (Lane 2)
- ReAct / multi-agent in Python: [`../recipes/`](../recipes/) (Lane 2)
- Endpoint reference: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)