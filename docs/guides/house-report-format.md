# House Report Format - Sectors.app Equity Research

Binding rules for every generated report document (all archetypes: `single`, `sotp`,
`infra`, `strategy`, `update`). A document that breaks any rule below is not shippable.

Owner: research. Enforced at: `templates/*.html` + `templates/macros.html` (the Jinja/HTML
render the report API and the front end serve, rendered to PDF by Chromium),
`server/report/house_format.py` (the shared furniture), `server/report/house_rules.py` (the
executable form of §7-§9), `server/report/cover_slide1.py` + `server/report/slide2.py` (the
cover builders), `server/report/text_sanitize.py` (the reader-facing funnel: §12),
`templates/DATA_CONTRACT.md` (data),
`agents/adk/agents/instructions.py` (agent output), `agents/critic.py` (gate).
Guards: `tests/test_house_format_adoption.py`, `tests/test_slide2_forecast.py`,
`tests/test_no_em_dash.py`, `tests/test_design_system_sectoral.py`, `scripts/verify_house_format.py` (artifact level).

The fixed strings live once in `server/report/house_format.py` and as template defaults in
`templates/macros.html`, and the tests assert the two agree - retyping them in either place is
how they drifted apart before.

---

## 1. Exhibit labeling

Every visual object (chart) and every tabular object (table, card-grid) - **without
exception** - carries a label directly ABOVE it and a source line directly BELOW it.

**Label format**

```
Exhibit [nomor]. [deskripsi singkat, deskriptif]
```

- Benar: `Exhibit 4. Revenue and Revenue Growth (2024A-2028F)`
- Salah (generik): `Exhibit 4. Chart`, `Exhibit 4. Table`, `Exhibit 4. Data`

The description must say what is being shown and, where relevant, the horizon or unit
- a reader who never sees the chart should still know what it contains.

**Source line**

The visible line below every object is always, **without exception**:

```
Source: Company, Team Estimates
```

This holds even when the data is purely historical from the financial statements.

> **Reconciliation with the provenance policy.** The real provenance (outlet, url,
> date, engine path) is NOT dropped - it is retained as an internal audit field
> (`source` in the data payload) and surfaced only by audit builds
> (`exhibit-source-detail()`), never in the house PDF. Agents still must supply
> verifiable provenance with url+date; the Critic still rejects fabricated or
> bare institution name-drops. What changed is only *where* it is rendered.

## 2. Exhibit numbering

Numbering runs **continuously from the first page to the last** and never resets per
page: Exhibit 1 on page 1 continues to Exhibit 10 and onward.

**Technical implication (binding):** the number is a **global counter owned by the
generator**, never a per-slide local variable and never a literal string supplied by
an agent. If the number of charts on one page changes, every later exhibit
re-sequences by itself.

In this codebase that counter belongs to the exhibit macro itself (`m.exhibit_auto(...)` in
`templates/macros.html`), so no call site ever writes `Exhibit N`. Data payloads must NOT carry a pre-numbered
`id` such as `"Exhibit 1"` - that is a local variable masquerading as a global one and
it desynchronises the moment a chart moves.

Prose that refers to an exhibit cites it live (`#exhibit-figure(...) <ex-abcd>` then
`@ex-abcd`), so a cross-reference can never go stale.

## 3. Page header (every page)

| Position | Content |
|---|---|
| Top-left | `Equity Research – Company Update` |
| Under it | Publication date, format `DD Mon YYYY` (e.g. `11 Sep 2026`) - amended 13 Sep 2026 from the long `Day, DD Month YYYY` form, which read as noise on every page; `format_house_date(raw, short=False)` still renders the long form where a date is stated in prose |
| Top-right | Sectors.app logo - same size and position on every page |
| Below the block | Horizontal divider, `#0928B1` (Sectoral primary - amended Sep 2026 from `#067647`) |

## 4. Page footer (every page)

| Position | Content |
|---|---|
| Bottom-left | `sectors.app` |
| Bottom-right | `See important disclosure at the back of this report` + page number |

The page number is the real page counter, not a per-page literal.

## 5. Who enforces what

| Rule | Enforced by | Mechanism |
|---|---|---|
| Label above object | `templates/macros.html` | the exhibit macro emits the label immediately above the object, one call per object |
| Descriptive label | template authoring + Critic | titles are template-side; agents never write labels |
| Constant source line | `templates/macros.html` | the source macro stamps `SOURCE_LINE`; per-exhibit provenance is stashed, not printed |
| Global sequential numbering | `templates/macros.html` | the exhibit macro's own counter - it is NEVER offset, so the first rendered label is `Exhibit 1` |
| No hand-numbered exhibits in data | `templates/DATA_CONTRACT.md` + Critic | `exhibits[*].id` banned |
| Header / logo / divider / footer on every page | `server/report/house_format.py` (`header_template()`, `footer_template()`, `PDF_MARGIN`) driven by Chromium `display_header_footer` | repeats on every PHYSICAL page. The per-`<div class="page">` fallback in `templates/macros.html` is used only when Chromium is unavailable, because it cannot survive a page overflow |
| Footer page number = real page counter | Chromium `<span class="pageNumber">` | resolves to the physical page index; never a per-page literal |
| Date format | `house_format.format_house_date()` / `format-date-en()` | `DD Mon YYYY` from the payload's raw date (`short=False` for the long form) |
| Label/object/source not split by a page break | template authoring | `break-after/before: avoid` is a hint Chromium does NOT honour reliably - measure with `scripts/verify_house_format.py` |

Agents do not lay out pages. They supply data and narrative; the renderer owns
every element in the tables above. An agent that emits its own header, footer, page
number, or `Exhibit N` string is producing a duplicate that will drift.

## 6. Deck page order

The deck is generated from the owner's slide numbering. One slide is one page, and the physical
page index is the slide number, so a page cannot be inserted without renumbering what follows.

| Page | Slide | Content | Spec | Contract |
|---|---|---|---|---|
| 1 | 1 | Cover one-pager | `docs/ammn-slides/slide1-cover-spec.md` | §7-§9 below |
| 2 | 2 | Kondisi industri, katalis emiten, sentimen pasar (three narrative paragraphs, **no mandatory object**) | `docs/ammn-slides/slide2-industry-spec.md` | §6.1 below |
| 3 | 3 | Performance visualisation and forecasting (2x2 grid) | `docs/ammn-slides/slide3-visual-spec.md` | §6.2 below |
| 4 | 4 | Valuation methods and assumptions | `docs/ammn-slides/slide4-valuation-spec.md` | pending |
| 5 | 5 | Peer and relative valuation | `docs/ammn-slides/slide5-peer-spec.md` | pending |
| 6-7 | 6-7 | Financial statements and disclosures | `docs/ammn-slides/slide6-statements-spec.md` | §3-§4 furniture |

Pages 3 and later still render in the order the single archetype had before the deck was numbered (Ringkasan Investasi, Tesis, Valuasi, Financials 6Y, Peers, Risiko, Disklaimer); each is realigned when its slide rules are wired.

**Shipped length (owner call, Sep 2026): 11 numbered pages.** Two pages were removed because the
owner read the deck and found them empty for a reader:

- the Exhibit 12 "Metode pembanding" table - a two-row page repeating the valuation ladder from
  the page before it. Exhibits renumber themselves (`ns.ex`), so nothing after it needed editing;
- the audit page as a fixed page. It is now a **conditional appendix printed last**: it renders
  only when there is something to disclose (a non-PASS verdict, a contested price anchor, a
  valuation ladder, or a metric-consistency mismatch) and carries page number 12 when it does.
  A clean PASS prints no audit page at all, which keeps the numbered pages contiguous. The
  disclosure data is still computed into `cover.audit_disclosure` and still gated by the Critic,
  so removing the page removed a print surface, not a check. `tests/test_audit_appendix.py`
  pins both halves: no page on a clean PASS, and the condition that brings it back.

Consequence for the footer rule (§4): the last numbered page is the risk/disclaimer page, so
`pagefoot` literals must run 1..11 with no gap. A test reads the rendered HTML and fails on any
gap or duplicate, which is what caught this change.

**Method notes print at the back (owner call, Sep 2026).** The eight valuation disclosures
(currency conversion, multiple basis, target-price basis, unresolved terminal gap, finite
reserve, discount convention, forecast path, capex basis) used to print inside the sensitivity
page. The revamp of that page added the levers, the discount-rate chain and the market-price
banner, and the disclosures then either pushed the page onto a second sheet or forced the note
type down to 5.6pt. They now print on the back page as their own section, `Catatan Metode
Valuasi`, in two columns at the deck's normal note size, above the disclaimer. The footer line
("See important disclosure at the back of this report") already promised exactly that. The gate
is unchanged: `audit_valuation_page` still reads `valuation_page.notes` from the payload, so the
disclosure contract is about content, not about which page carries it.

Page 2 is the only page whose content is built outside the templates: `server/report/industry_page.py`
assembles the three paragraphs from the payload and the assumptions file, and
`server/report/house_rules.py::audit_industry_page` gates them. The page is narrative, so §1-§2
(exhibit labeling and numbering) do not apply to the page itself - an optional supporting object
added here still carries `exhibit_auto`, a descriptive title and the constant source line, and the
document-wide figure counter treats it like any other object.

### 6.1 Page 2 - three paragraphs, no forced numbers

| Rule | Enforced by | Mechanism |
|---|---|---|
| Exactly three paragraphs, in order: Kondisi Industri, Katalis Spesifik Emiten, Sentimen Pasar | `server/report/house_rules.py::audit_industry_page` | the Critic gate and the render gate run the same audit; a missing paragraph is a violation, an absent page is not applicable |
| Every paragraph carries its data basis on the page | `server/report/industry_page.py` | each paragraph ships a `basis` string; the page prints its outlets under `Basis data:` |
| Sentiment stays out of valuation | `audit_industry_page` | paragraph 3 is scanned for target price, fair value, multiple and WACC language; a hit is a violation |
| No forced number when the data has no basis | agent instructions (`SLIDE_PAGES_RULE`) + `industry_page.py` | a missing input is written as unavailable or qualitative in the copy, never estimated |
| Optional objects obey the exhibit rules | `templates/macros.html` | `exhibit_auto` + constant source line, global counter |
| Related-party flow reported in both directions | `audit_industry_page(page, payload)` | when the payload's filings block carries buys and sells, paragraph 2 must name both; one side is a violation |
| The CLI/native path cannot dodge the page rules | `scripts/render_pdf.py` (`ensure_industry_page` + `validate`) | attaches the page when the payload predates it, then runs the same `audit_house_rules` |
| The prompt carries the evidence rules, not only the doc | `agents/adk/agents/instructions.py` (`SLIDE_PAGES_RULE`) | widest-Sectors evidence list, both-directions rule, like-for-like comparison, named unavailable metrics |

### 6.2 Page 4 - the 2x2 performance grid

| Rule | Enforced by | Mechanism |
|---|---|---|
| Four quadrants, each chart with its own narrative block | `audit_performance_page` | a quadrant without a narrative of at least 120 characters is a violation, so the narrative cannot drift to the end of the page |
| Actual vs forecast readable without the axis labels | `templates/_slide3_macro.html` | solid navy bars for the actual periods, lighter bars under a hatch pattern for the forecast periods |
| Every period ties out with the Key Financials exhibit | `audit_performance_page(page, payload)` | each bar is compared against the cover table for the same period label; a mismatch names the period and both values |
| Narrative states the drivers, the CAGR comparison, the margin sanity check and the below-line gap | `server/report/performance_page.py` | computed from the series, not written by hand; an assumption the narrative disagrees with is printed on the page |
| The fourth quadrant switches by sector | `performance_page` + page notes | DER/ROE is built for non-banks; the bank and E&P branches are named as unavailable rather than filled with lookalike numbers |

### 6.3 Pages 5-6 - intrinsic valuation

| Rule | Enforced by | Mechanism |
|---|---|---|
| Exhibit 8 is one exhibit with three blocks | `audit_valuation_page` | the 11 block-1 rows must each match the five-period count, and the terminal and bridge rows must all be present |
| Gordon and exit multiple side by side | `audit_valuation_page` | a missing exit-multiple column violates the cross-check the rules require |
| Every WACC parameter names its source | `audit_valuation_page` | risk-free, beta and ERP each need a non-empty source cell |
| Complete sensitivity grid with the base case called out | `audit_valuation_page` | filled cells must equal rows x columns and the base cell must be marked |
| A material terminal gap is an unresolved assumption | `audit_valuation_page` | a gap of 2x or more requires an "UNRESOLVED" note in the disclosure block |
| Method choice is auditable | `audit_valuation_page` | the page must say which option is active and why DDM and RNAV were excluded |
| Numbers tie out with the rest of the deck | builder + gate | the projection columns are the cover's own Key Financials columns, and the bridge reproduces the cover's DCF leg |
| Valuation inputs are Sectors-sourced only | `audit_valuation_page` (RNAV arm) + `valuation_rnav.py` | an asset NAV without a Sectors citation is refused, and the page states which asset broke the rule |

## 7. Cover slide - the one-pager

The cover is **one physical page**. Sidebar (~30%, left) and main column (~70%, right)
carry, in this order:

| Sidebar | Main column |
|---|---|
| rating (large) + change status in italics - `Buy` / `(Initiation)`, `(Maintained)`, `(Upgrade from X)`, `(Downgrade from X)` | company name + `(TICKER IJ)` |
| price box: Last Price (Rp), Target Price (Rp), **Previous TP (Rp)** (reads `Initiation` when there is no prior target), Potensi naik/turun (%) with an explicit sign | theme title - the thesis with a figure, never a generic product name |
| secondary stats: No. of Shares (mn), Mkt Cap (Rpbn/US$mn), Rata-rata transaksi harian 3 bulan (Rpbn/US$mn) **with its window stated**, Free Float (%) | three highlights, each a quantitative claim, in a tinted callout box |
| Major Shareholder (%) - every holder ≥5% | paragraph 1, 2, 3 (§8) |
| relative-performance chart vs the index, source line directly beneath it | Key Financials exhibit (§9) |
| analyst block (name + title) | |

Rationale for the ordering: an institutional reader scans the rating, its change status
and the price box before reading a single sentence, and reads the change status
specifically to see whether the rating moved - so both are above everything else and the
status is never omitted or folded into prose.

The cover is rendered from `templates/report_single.html` off the `cover.slide1` /
`cover.slide2` payload block. The copy budget below is what keeps the Key Financials exhibit on
the same physical page, so it binds every render path.

**Copy budget (binding):** paragraphs 1–3 together are limited to **2.600 characters**.
Measured at the typography in `templates/macros.html`, that is the point at which the Key
Financials exhibit stops fitting on the same page; past it the exhibit is pushed to page 2
and the one-pager contract silently breaks. The budget is asserted by
`tests/test_house_format_adoption.py` and by the Critic gate, not by eyeballing the PDF.

## 8. Narrative paragraphs (cover)

Three paragraphs, each with a bold subheading, each claim attached to an explicit figure:

1. **Financial performance** - current-period revenue and net profit against the prior
   quarter (and the prior year *where the base is meaningful*; a ramp-up quarter is named as
   such instead of being used as a growth base), the running rate against any verified
   full-year estimate, the margin/cost drivers, and positioning against management guidance.
   Where a comparison cannot be computed from verified figures, the paragraph says so
   explicitly - it does not substitute a number.
2. **News, sentiment, catalysts** - the period's concrete catalysts with their figures
   (news flow, corporate action, regulation, macro), the quantified impact on earnings or
   valuation **where a basis exists**, and an explicit statement of *why* it cannot be
   quantified where one does not exist. It closes with a verdict on whether the market has
   already priced the catalysts in, read off relative performance versus the index and the
   sector. Silence about an unquantifiable catalyst reads as an implied zero.
3. **Valuation** - four blocks in order: methodology (target price, method, key parameter);
   forecast linkage (the implied CAGR and its driver); the trading multiple at the target
   price versus the historical average and versus peers, naming any leg that is unavailable
   instead of substituting one that exists; and the risk to view with the direction of impact,
   quantified where the arithmetic allows.

## 9. Key Financials exhibit (cover)

Two actual columns, then three forecast columns: `2024A`, `2025A`, `2026F`, `2027F`,
`2028F`, under a first header cell reading `Year to 31 Dec`. Nine rows, in this order:
Revenue, EBITDA, EBITDA Growth (%), Net Profit, EPS, EPS Growth (%), PER (x), PBV (x),
EV/EBITDA (x). Units sit inside the row labels (`Revenue (Rpbn)`, `EPS (Rp)`); the absolute
Rp rows carry no decimals, percentages, multiples and EPS carry exactly one; negative values
use the accounting parenthesis form `(28,8)`, never `-28,8`. Header row navy with white text,
figures right-aligned.

Every forecast cell must be derivable from a stated input, and the derivation is printed as
a note under the table - the same standard as any other number in the document. A forecast
column that cannot be derived is not filled with a plausible curve; the derivation note says
which input is missing.

## 10. Who enforces what (slide rules)

| Rule | Enforced by | Mechanism |
|---|---|---|
| Cover block order, price-box rows, shareholder block | `server/report/cover_slide1.py` + `templates/report_single.html` | the builder derives the fields, the template only lays them out |
| Paragraph mandates (§8) | `server/report/house_rules.py` (`audit_katalis`, `audit_valuasi`) | `agents/critic.py` REJECTs the document |
| Copy budget (§7) | `server/report/house_rules.py` (`audit_copy_budget`) | Critic REJECT + `tests/test_house_format_adoption.py` |
| Highlights are quantitative | `server/report/house_rules.py` (`audit_cover`) | Critic REJECT |
| Key Financials rows/units/decimals (§9) | `server/report/house_rules.py` (`audit_key_financials`) | Critic REJECT |
| Agent-facing statement of §7–§9 | `agents/adk/agents/instructions.py` (`HOUSE_FORMAT_RULE`) | travels with every prompt that can put an object into the report |

The audit result is attached to the render payload as `house_rules` (`{ok, applicable,
violations, copy_chars, copy_budget}`) and the Critic verdict as `critic`, both persisted in
`output/cache/render_<TICKER>/report_data.json`, so the gate, the guards and a human
inspecting the document payload read the same verdict. (`/api/report/{ticker}` is a
different payload - Sectors data, not the cover spread.) `applicable` is false for documents that
carry no cover spread, so the gate never rejects a document for a section it never had.

## 11. Verification

```bash
# convention guards (static + render-level geometry)

# adoption guards (data contract, agent instructions, critic gate, render path)
.venv/bin/python -m pytest tests/test_house_format_adoption.py -q

# artifact check - the only layer that sees PHYSICAL pages. Source-level guards pass
# even when per-page furniture got lost to a page overflow, when an exhibit label is
# orphaned from its object by a page break, or when footer page numbers repeat.
.venv/bin/python scripts/verify_house_format.py output/<ticker>_report.pdf

# slide rules §7-§9 on the payload - the SAME audit the Critic gate runs, so a green
# gate and a green payload mean the same thing
.venv/bin/python -c "import json,sys; from server.report.house_rules import audit_house_rules; \
print(json.dumps(audit_house_rules(json.load(open(sys.argv[1]))), indent=2, ensure_ascii=False))" \
output/cache/render_<TICKER>/report_data.json
```

Render-level evidence for a generated document:

```bash
# the served path: Jinja/HTML templates -> Chromium -> PDF
.venv/bin/python scripts/render_pdf.py output/cache/render_<TICKER>/report_data.json --out /tmp/r.pdf
```

Check on the produced PDF: label sequence is `1..N` with no gaps, source lines equal
the exhibit count, header/divider/logo/footer present on 100% of pages, footer page
numbers complete. `scripts/verify_house_format.py` runs those checks mechanically.
§12 (typography) is checked by the same verifier and by `tests/test_no_em_dash.py -q`.

## 12. Typography - no em dash

The document never prints an em dash (U+2014) or a horizontal bar (U+2015). The separator between
a statement and its qualifier is a **hyphen with a space on each side**:

- Benar: `Opsi A - DCF FCFF`, `Multiple 2026 17,99x vs mid-cycle 28,42x - re-rating belum tercermin`
- Salah: `Opsi A — DCF FCFF`, `Blok 1 — Periode proyeksi eksplisit` (em dash, U+2014)

The mark is a publisher's habit, not part of this house style: an em dash arrives in a document
from a PDF someone quoted, from a model writing prose, or from a template imported from
somewhere else. The en dash (U+2013) is **not** banned - it is reserved for the two places this
house format already prints it (the page header of §3 and numeric range labels such as
`Rp 5.000 – Rp 7.000`); it is not added anywhere new.

**Why a funnel and not only a guard.** Two of the three writers of an em dash do not exist in the
repository at review time, so no source scan can see them:

| Writer | Where the string is born | Visible to a source scan |
|---|---|---|
| An agent's paragraph | the model, at run time | no |
| A `note` / `source` field | `data/assumptions/<T>.json`, `data/drivers/<T>.json` | yes |
| A sentence quoted from a research PDF | the publisher's own file | no - the quote is faithful, the typography is not ours |
| A template written by hand | `templates/*.html`, `server/report/*.py` | yes |

So the rule is enforced at three layers, and all three run:

| Layer | Enforced by | Mechanism |
|---|---|---|
| Writers (static) | `tests/test_no_em_dash.py::test_no_em_dash_in_shipped_sources` | scans `templates/`, `server/`, `agents/`, `scripts/`, `tests/`, `data/`, `docker/` and the front end for U+2014/U+2015; a hit is a hand-written string to fix |
| Funnel (run time) | `server/report/text_sanitize.py` (`normalize_dashes`, applied by `clean_text`/`clean`) | rewrites every printable string of the payload. Both served surfaces pass through it - the PDF (`server/routers/pdf.py`) and the front end (`server/routers/endpoints.py`, `/api/report/{ticker}`) - so the page and the web page cannot disagree about the same report. An em dash surrounded by spaces becomes `" - "`; one inside a token (a range) becomes `"-"`; a lone one becomes the `-` placeholder |
| Page (artifact) | `scripts/verify_house_format.py` (`rule 12`) | reads the PHYSICAL pages of the shipped PDF; any occurrence is a FAIL, because a hit there means a string bypassed the funnel |

Every agent is told the rule, in a block of its own. `TYPOGRAPHY_RULE` in
`agents/adk/agents/instructions.py` attaches to ALL of them - including the data-only agents
(`collector`, `news_harvester`, `risk`) that deliberately do NOT receive `HOUSE_FORMAT_RULE`,
because their snippets, source strings and labels are quoted into the document downstream and the
typography rule is about the TEXT, not about exhibit labels. `HOUSE_FORMAT_RULE` composes the same
block, so the content agents carry it once, not twice. The legacy builder in `agents/collector.py`
imports it as well, and the guard BUILDS the real ADK graph
(`tests/test_no_em_dash.py::test_every_agent_is_told_the_typography_rule`) and fails if any agent
comes out without it - so an agent added later cannot ship silently. Run-time prose therefore stops
producing the mark instead of relying on the rewrite: a rewritten string prints in house style, but
it is a rewrite of a sentence nobody wrote in house style.

The em dash is not normalised anywhere else on purpose - `templates/macros.html` and the
`house_format` constants keep the en dash they are specified with, and the guards in
`tests/test_no_em_dash.py` assert that normalisation leaves it alone.

## 13. Design System - Sectoral tokens (friend-supplied, Sep 2026)

The full Sectoral design system text is `docs/design-system-friend.md` (ignore the
base64 image blobs - the values below are the normative tokens). Roboto only: no
other family ships in the report surfaces.

| Token | Value | Where it is wired |
|---|---|---|
| Primary | `#0928B1` | header divider (`DIVIDER_COLOR`), table header band, chart series 1 |
| Background | `#FFFFFF` | page background |
| Text | `#333333` | body text |
| Grid / lines | `#D9D9D9`, `#E0E0E0` | chart gridlines |
| Table header | `#0928B1` bg, white text | `templates/macros.html` table CSS |
| Table even row | `#B4C7FF` | `templates/macros.html` table CSS |
| Chart series (in order) | `#0928B1`, `#B4C7FF`, `#3ED628`, `#1DCD9F`, `#0047AB`, `#7596FF` | FE chart tokens / `sectoralSeries`, `house_format.SECTORAL_CHART_PALETTE` |
| Type | Roboto (H1 Bold 24, H2 Medium 20, H3 Medium 16, Body Regular 14, Caption 12) | `src/fe/index.html`, `templates/macros.html` |
| Logo | Sectoral mark (E-bars `#0928B1` / `#1DCD9F` / `#3ED628` + `CTORAL`) | `assets/brand/sectoral*.svg`, `src/fe/public/sectoral*.svg` |

Guarded by `tests/test_design_system_sectoral.py` (source wiring) and the sectoral
checks in `scripts/verify_house_format.py` (printed PDF: Roboto used, primary present).


## 14. Plain language (reader-facing surfaces)

Rule (owner call, 19 Sep 2026; amended 22 Sep 2026, owner call: full-English deck): every surface a lay investor reads is written in plain
English. Translate the METHOD, never the FIGURE - a number is exact or it is a
fabrication, so plain wording never rounds, drops, merges or re-derives one.

Surfaces: cover theme title, cover highlights, paragraph 1 (financial performance),
paragraph 2 (news/sentiment/catalysts), paragraph 3 (valuation) except its four mandated
markers, the thesis rail, risk details, the industry page prose, the KPI prose and the SOTP
prose. Valuation/audit page TABLES keep precise method terms - they are read by analysts -
but their sentences still obey the rule.

Banned tokens and code-shaped year tags: `server/report/house_rules.py::PLAIN_JARGON` and
`PLAIN_JARGON_PATTERNS` are the executable list. The agent instruction
(`agents/adk/agents/instructions.py::PLAIN_LANGUAGE_RULE`) carries the same list and
`tests/test_plain_language_instructions.py` fails if the two drift apart, so a token added
to the gate must be added to the instruction in the same commit.

Carve-out: paragraph 3's mandate requires `CAGR` and `CAGR EBITDA FY26F-FY28F` verbatim.
Those are carved out BY NAME (`VALUASI_MANDATE_TOKENS`) and everything else in P3 is scanned;
the carve-out cannot be used to smuggle jargon in beside them.

Roster: the ADK agents that write or judge printed prose carry the rule - writer, critic,
industry, kpi, analyst, risk, sotp. Agents that gather, compute or design (collector,
modeler, news_harvester, the search sub-agents, visualizer, adversarial) do not: a narrative
rule on a calculator dilutes the agents whose output reaches a reader. Both directions are
pinned by tests, so a new agent either gets the rule or fails the build.

Enforcement: `server/report/house_rules.py::audit_plain_language` runs inside
`audit_house_rules` on the shipped payload (render path + Critic). A hit names the surface
and the token and flips the verdict to REJECT - a blocked publication, not a style note.

## 15. No machine traces

Rule (owner critique, 19 Sep 2026; amended 22 Sep 2026, owner call: full-English deck): the printed document describes the COMPANY, never the
machinery that produced it. The shipped PDF carried "yang dikembalikan endpoint", "via
AMMN.json", "Asumsi kolom F", "feed yang dipakai" and "kriteria evaluasi gate terpenuhi" - debug
output wearing a research note's clothes, on a page a retail reader is meant to read.

Banned on any printed surface: `endpoint`, `kolom`/`kolom F`, `feed`, `payload`, `artifact`,
`harvester`, `renderer`, `pipeline`, `gate`, `deterministik`, `tenant`, `JSON`/`.json`, `freeze`,
`screener`, `filings`, `engine`, `raw`, `file asumsi`, `file jalur proyeksi`, `LEVEL NORMALISED`.
Plain forms: "available in the data", "IDX disclosures", "automated calculation", "team assumptions file",
"projection columns (2026-2028)", "normalised basis".

Two exemptions, both deliberate:

- **Citations.** A source line may name the dataset it came from ("Sectors filings", "Sectors
  screener"): attribution is owed to the reader. Prose may not.
- **Bookkeeping that never prints.** The Critic's reasons, the house-rule report and the fill
  manifest are machine fields; scanning them would flag our own audit text.

Enforcement is two-layered, and the second layer is the important one:

- `server/report/house_rules.py::audit_plumbing` walks the WHOLE payload (every string, with its
  dotted path in the message) and runs inside `audit_house_rules`, so the Critic rejects on it.
  It walks everything because the bug it exists to stop is "a page nobody remembered to scan":
  the plain-language scan enumerated surfaces by hand and the industry page was not on the list.
- `server/report/house_rules.py::audit_printed_html` strips the rendered HTML to visible text and
  runs in `server/routers/pdf.py::render_pdf_bytes_for_ticker` BEFORE Chromium starts. A hit is a
  422 (`printed_machine_trace`), not a style note: the document does not ship. This is the layer
  that catches template copy, which the payload scan cannot see.

Guarded by `tests/test_no_machine_traces.py` (walk-everything, both exemptions, word-boundary
matching, the HTML layer, the live payload, and the doc/instruction wiring).
