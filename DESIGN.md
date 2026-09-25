---
name: Sectoral
description: The Command Deck, a live research console for sourced IDX company updates.
colors:
  brand: "#0928B1"
  brand-hover: "#071F8A"
  brand-ink: "#0928B1"
  brand-50: "#F1F4FF"
  brand-100: "#E0E7FF"
  tint: "#B4C7FF"
  canvas: "#F2F4F9"
  surface: "#FFFFFF"
  raised: "#F7F8FC"
  ink-strong: "#14182A"
  ink: "#333333"
  ink-soft: "#565B69"
  ink-faint: "#676D7E"
  rule-soft: "#E6E9F0"
  rule: "#D9D9D9"
  rule-strong: "#B9BDC6"
  wordmark: "#000000"
  teal: "#1DCD9F"
  live: "#3ED628"
  done: "#0B7A5A"
  ok-bg: "#E6F8F1"
  ok-ink: "#0B6B50"
  warn-bg: "#FFF4DB"
  warn-ink: "#7A4B00"
  warn-rule: "#E3A21A"
  err-bg: "#FDECEC"
  err-ink: "#9B1C1C"
  brand-dark: "#3552F0"
  brand-hover-dark: "#4A66F6"
  brand-ink-dark: "#E4E6EA"
  brand-50-dark: "#1A2036"
  brand-100-dark: "#222A45"
  tint-dark: "#2A3352"
  canvas-dark: "#0F1013"
  surface-dark: "#16181C"
  raised-dark: "#1D2025"
  ink-strong-dark: "#F5F6F8"
  ink-dark: "#E4E6EA"
  ink-soft-dark: "#AAAFB9"
  ink-faint-dark: "#8E94A0"
  rule-soft-dark: "#22252B"
  rule-dark: "#2B2F36"
  rule-strong-dark: "#3B4049"
  wordmark-dark: "#F2F3F5"
  done-dark: "#4FE0B6"
  ok-bg-dark: "#11291F"
  ok-ink-dark: "#E4E6EA"
  warn-bg-dark: "#2D2412"
  warn-ink-dark: "#E4E6EA"
  warn-rule-dark: "#B8871F"
  err-bg-dark: "#321719"
  err-ink-dark: "#E4E6EA"
typography:
  display:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(31px, 2.85vw, 42px)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "clamp(28px, 2.6vw, 36px)"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  ticker:
    fontFamily: "Roboto Mono Variable, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.375
    letterSpacing: "-0.01em"
  region:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  body:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  body-sm:
    fontFamily: "Roboto, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
    fontSize: "13.5px"
    fontWeight: 400
    lineHeight: 1.375
  data:
    fontFamily: "Roboto Mono Variable, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.6
    letterSpacing: "0.02em"
    fontFeature: "tnum"
  status:
    fontFamily: "Roboto Mono Variable, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "10.5px"
    fontWeight: 500
    lineHeight: 1
    letterSpacing: "0.06em"
rounded:
  chip: "3px"
  cap: "4px"
  state: "5px"
  control: "6px"
  panel: "8px"
  palette: "12px"
  full: "9999px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "5": "20px"
  "6": "24px"
  "8": "32px"
  section: "96px"
  section-sm: "64px"
  deck-bar: "52px"
components:
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.surface}"
    typography: "{typography.region}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.brand-hover}"
  button-ghost:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.brand-ink}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  button-ghost-hover:
    backgroundColor: "{colors.brand-50}"
  button-sm:
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "36px"
  pill:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.full}"
    padding: "2px 10px"
  pill-ok:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok-ink}"
  pill-warn:
    backgroundColor: "{colors.warn-bg}"
    textColor: "{colors.warn-ink}"
  pill-err:
    backgroundColor: "{colors.err-bg}"
    textColor: "{colors.err-ink}"
  pill-live:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-ink}"
  panel:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.panel}"
    padding: "32px"
  kbd:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.data}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
    height: "22px"
  state-chip-running:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-ink}"
    rounded: "{rounded.state}"
    padding: "0 8px"
    height: "24px"
  state-chip-done:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.done}"
    rounded: "{rounded.state}"
  engine-tag-llm:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-ink}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
    height: "18px"
  engine-tag-host:
    textColor: "{colors.ink-soft}"
    rounded: "{rounded.cap}"
    padding: "0 6px"
    height: "18px"
  input-ticker:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink-strong}"
    typography: "{typography.ticker}"
    rounded: "{rounded.control}"
    height: "56px"
  input-search:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "36px"
  deck-bar:
    backgroundColor: "{colors.surface}"
    height: "52px"
---

# Design System: Sectoral

## Overview

**Creative North Star: "The Command Deck"**

Sectoral is a research desk seen through one console. Every agent, tool call and Method Gate decision lands as a ruled row in a single instrument an analyst could audit, and the interface's job is to make that work legible while it happens. The grammar is a trading terminal's: function-key tabs (F1 Riset, F2 Laporan, F3 Cara kerja), a Cmd-K ticker palette, an agent rail that reads ANTRI / JALAN / SELESAI, and mono readings for tool names, endpoints, clocks and Rupiah figures. The materials are Sectoral's own: primary blue, Roboto, the E-mark's three bars, and the brand chart series.

The system runs in two grounds. Light is paper: a cool grey canvas under white console panels. Dark is the console: a true dark charcoal field with only a trace of cool, surfaces that lift by lightness rather than shadow, and the brand blue kept as an accent. Density is high but ruled; regions are divided by 1px lines inside one bordered console, never scattered as a card grid. Motion is damped and informational: a changed row holds its light and then settles, a gate needle eases to its reading without overshoot, and nothing bounces.

The system rejects the category defaults it was built against: a chat transcript, or a spinner with a step list.

**Key Characteristics:**
- One console, ruled regions: 1px rules and small corners, not floating cards.
- Two voices: Roboto for prose and headings, Roboto Mono for every machine reading.
- Status as color with a word: blue running, teal done, amber warning, red error, and green only as the live pulse.
- The E-mark's three bars are the running indicator.
- Light and dark are peers; every token has a dark counterpart.
- Damped, overdamped motion that respects reduced-motion.

## Colors

A single committed blue on cool paper or charcoal console, with a small, strictly assigned status set.

### Primary
- **Sectoral Blue** (`brand`): fills primary buttons, the replay play control, the scrub bar and the E-mark's first bar. In dark it brightens to a saturated cobalt (`brand-dark`) so fills keep their weight on charcoal.
- **Blue Ink** (`brand-ink`): blue used as text or a thin mark (links, active tab underline, focus ring, running status word, picked method row). Identical to Sectoral Blue in light; in dark it becomes a pale periwinkle (`brand-ink-dark`) that stays readable on every surface step.
- **Blue Wash** (`brand-50`, `brand-100`): the running/selected field: pressed rail node, active filter chip, palette selection, the hold light for a running row, and `brand-100` as the 3px focus halo of inputs.
- **Table Tint** (`tint`): the brand's even-row blue, carried for brand SVGs and chart series.

### Secondary
- **E-mark Teal** (`teal`): the E-mark's middle bar only.
- **Live Green** (`live`): the running pulse (E-mark third bar, subagent pulse dot). Never text, never a fill larger than a dot or bar.
- **Done Teal** (`done`): the finished state as text and icon (CircleCheck, SELESAI, done rail lines). A darker, text-safe teal in light; a bright mint in dark.

### Tertiary (status)
- **Pass** (`ok-bg` / `ok-ink`): supported verdicts, done chips, completed hold light.
- **Caution Amber** (`warn-bg` / `warn-ink` / `warn-rule`): warnings, "Parsial", unanswered hypotheses, warning counters. Amber is reserved for warnings.
- **Fault Red** (`err-bg` / `err-ink`): errors, failed runs, "tidak didukung" verdicts.

### Neutral
- **Cool Paper / Charcoal Field** (`canvas`): the page ground behind the console.
- **Console White / Console Charcoal** (`surface`): panels, deck bar, footer, cards.
- **Lifted Row** (`raised`): a row or control lifted inside a panel: search button, kbd caps, skeleton bars, palette footer.
- **Ink ladder** (`ink-strong`, `ink`, `ink-soft`, `ink-faint`): headings and readings; body (the brand charcoal); secondary labels; timestamps and idle states. In dark, body and secondary ink hold at least 4.5:1 up to `brand-50-dark`.
- **Rules** (`rule-soft`, `rule`, `rule-strong`): inner dividers; region and panel borders (the brand rule grey); hover borders and idle markers.
- **Wordmark** (`wordmark`): the logo's black `CTORAL`, inverted to near-white in dark.

### Named Rules
**The Green Is Only Alive Rule.** `live` marks something running right now, as a bar or a dot. It is never text, never a background, never "success". Finished is `done` teal.

**The One Blue Rule.** Blue means the brand, the active thing, or the primary action. Status never borrows blue except for "running".

**The Paired Ground Rule.** Every color role ships a light and a dark value; a new surface that only works in one theme is not done.

## Typography

**Display Font:** Roboto (with -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif)
**Body Font:** Roboto
**Label/Mono Font:** Roboto Mono Variable (with ui-monospace, SF Mono, Menlo, Consolas)

**Character:** Roboto is the brand face, shared byte-for-byte with the PDF renderer; Roboto Mono is the console's instrument voice. Prose explains, mono reports.

### Hierarchy
- **Display** (700, `clamp(31px, 2.85vw, 42px)`, 1.1, -0.025em): the landing hero headline only.
- **Headline** (700, `clamp(28px, 2.6vw, 36px)`, 1.15, -0.02em): landing section heads, paired with a 16.5px `ink-soft` lede in a 12-column split.
- **Ticker** (Mono 600, 34px / 26px on phones, 1): the run header's ticker, the one large mono reading per screen. Ticker inputs use mono 17–22px, uppercase, +0.04–0.06em.
- **Title** (700, 19–22px): sub-section and panel titles.
- **Region** (700, 14px): the heading of a console region (Aliran kerja agent, Method Gates, Rencana riset), paired right-aligned with a mono reading.
- **Body** (400, 16px, 1.6): page prose; measure 48–72ch (`max-w-[62ch]` typical).
- **Body small** (400–500, 13–14.5px, snug): console rows, reasons, table cells. This band carries most of the Deck.
- **Data** (Mono 500, 12px, +0.02em, tabular): clocks, counters, step counts, durations, `G1`/`H1` indices. Headline readings in the run header go to mono 17px 600.
- **Status** (Mono 500–600, 10.5–12px, +0.06–0.08em, uppercase): the agent status words ANTRI / JALAN / SELESAI / GAGAL / JEDA and the run-state chip. Uppercase is used for these machine states and ticker codes, nowhere else.

### Named Rules
**The Mono Means Machine Rule.** Anything the system measured, read or named from code (tool names, endpoints, tickers, clocks, Rp values, method codes) is Roboto Mono with tabular numerals. Human sentences are Roboto.

**The Balanced Head Rule.** Headings are bold, `ink-strong`, 1.2 line-height, -0.01em by default, and `text-wrap: balance`; paragraphs use `text-wrap: pretty`.

## Layout

The page container is 1320px wide with 24px gutters (16px on phones). The deck bar is a sticky 52px strip: wordmark, F-key tabs, Cmd-K search, Jakarta clock, theme toggle.

The Deck is one bordered console. From 1100px it is a 12-column split: the event stream at 7/12 with a right rule, and a 5/12 column stacking the plan and hypotheses, the six gate instruments, the method chain and the result. Between 768px and 1099px the side column moves first as a two-column block above the stream. Below 768px everything stacks, the agent rail scrolls horizontally with snap and keeps the working agent centred, and the gate board drops from 6 to 3 columns.

The landing uses a `5fr / 7fr` hero (offer and ticker launcher left, a live replay reel right), then sections with 96px vertical padding (64px on phones) separated by full-width rules, each opening with a headline and lede on a 12-column split. Lists on the landing and the report gallery are ruled registers: one row per item, top and bottom rules, grid areas that reflow per breakpoint.

Spacing sits on a 4px base; console regions pad 20px horizontally (16px on phones) and 10–16px vertically. Breakpoints are Tailwind's 640 / 768 / 1024 / 1280 plus the Deck's own 1100px split.

## Elevation & Depth

The system is flat and ruled. Depth inside the console comes from tonal steps (`canvas` → `surface` → `raised`) and from 1px rules, and in dark from lightness alone. Shadows are reserved for things that genuinely float above the console.

### Shadow Vocabulary
- **Card** (`--shadow-card`: `0 1px 2px rgba(16,24,40,.05), 0 8px 24px -12px rgba(16,24,40,.12)`; dark `0 1px 2px rgba(2,6,24,.45), 0 16px 32px -18px rgba(2,6,24,.75)`): a defined token with no consumer in the shipped TSX; reach for it only for a card that genuinely lifts off the canvas, never inside the console.
- **Pop** (`--shadow-pop`: `0 2px 6px rgba(9,18,60,.08), 0 24px 48px -16px rgba(9,18,60,.28)`; dark deeper): the Cmd-K palette and the PDF cover preview.
- **Primary sheen** (`inset 0 1px 0 rgb(255 255 255 / .14)`): the top highlight on filled blue buttons.
- **Focus halo** (`0 0 0 3px var(--color-brand-100)`): text inputs on focus, with the border turning `brand-ink`.
- **Key cap** (`inset 0 -1px 0 var(--color-rule)`): the bottom lip of kbd caps.

### Named Rules
**The Floats Only Rule.** Only overlays (palette, previews) cast a shadow. Console regions, rows and panels are separated by rules and tone, never by drop shadows.

## Shapes

Small, square-shouldered corners scaled to the object: 3px for subagent chips and PDF cover thumbnails, 4px for kbd caps and engine tags, 5px for the run-state chip and ticker badge, 6px for buttons, inputs, rail nodes and rows, 8px for panels and the console frame, 12px only for the Cmd-K palette. Pills and toggles are fully round. Borders are 1px throughout; rails and progress lines are 1–2px. The gate board is a grid with a 1px gap over a `rule` background, so cells read as one instrument panel.

The recurring silhouettes are the E-mark's three horizontal bars (live indicator and brand mark) and the gate needle, a small semicircular gauge.

## Components

### Buttons
Solid, compact, confident.
- **Shape:** gently squared (6px), 44px tall (36px small), bold 15px (13.5px small), 8px icon gap with 16px lucide icons at stroke 2.2.
- **Primary:** Sectoral Blue fill, white text, inset top sheen. Hover deepens to `brand-hover`; disabled drops to 60% opacity with a progress cursor.
- **Ghost:** `surface` fill, `rule` border, Blue Ink text; hover turns the border `brand-ink` and the fill `brand-50`.
- **Press:** every button settles `translateY(1px) scale(.985)` on active; transitions run .18s on ease-out-expo.
- **Icon button:** 36px square, 6px corners (replay play/pause, restart, theme toggle).

### Chips
- **Pill:** fully round, 13px bold, `raised` / `ink-soft` by default; ok, warn, err and live tones pair a tinted background with its ink. Used for verdicts (didukung, Parsial) and small states.
- **Run-state chip:** 24px, 5px corners, mono 12px uppercase +0.08em, bordered in its status ink at ~40%, led by the E-mark live indicator.
- **Engine tag:** 18px mono 10.5px; `LLM` in Blue Wash, `host` as a bare `rule-soft` outline. It tells the viewer whether a model or deterministic code decided.
- **Subagent chip:** 16px, 3px corners, bordered by status, with a live-green dot while running.
- **Filter chip:** 32px, 6px corners; the selected chip gets a Blue Wash fill and `brand-ink` border that slides between chips as a shared layout element.

### Cards / Containers
- **Corner Style:** 8px (`panel`).
- **Background:** `surface` on `canvas`.
- **Shadow Strategy:** none; see Elevation.
- **Border:** 1px `rule`; internal regions split by `rule` and `rule-soft`.
- **Internal Padding:** 20px regions; the generic card is 32px (18–22px on phones).

### Inputs / Fields
- **Ticker input:** 56px, `raised` field, 6px corners, mono 22px bold uppercase with sans placeholder; focus-within turns the border `brand-ink` and adds the 3px `brand-100` halo.
- **Search input:** 36px, `surface`, `rule` border, `rule-strong` on hover, same focus treatment.
- **Error:** an `err-bg` band with `err-ink` text and `role="alert"`.
- **Global focus:** 2px `brand-ink` outline at 2px offset.

### Navigation
The deck bar: F-key tabs pair a kbd cap with a 14px medium label, `ink-soft` at rest and `ink-strong` when active; the active tab gets a 2px Blue Ink underline that springs between tabs, and its cap takes a blue border and text. F1–F3 work from the keyboard. On phones the caps hide, F3 becomes an icon and "Cara", and search collapses to a 36px icon button. A skip link sits above the bar.

### Command Palette
A 620px sheet with 12px corners and the Pop shadow over a dimmed scrim, 12vh from the top. Mono uppercase ticker entry at 17px, grouped results with mono data headers, a Blue Wash selection that slides between rows, and a `raised` footer of key hints.

### Agent Rail (signature)
Seven nodes in pipeline order on one line, joined by 1px segments colored by the neighbouring agent's status (idle `rule`, running `brand-ink`, done `done` at 60%). Each node shows its status glyph (the breathing E-mark while running, a check/alert/x icon once settled, a hollow ring when idle), a bold 14px name, its engine tag, and a mono status word with its call count. Clicking a node filters the event stream; the pressed state is a sliding Blue Wash frame.

### Event Stream (signature)
Ruled rows on a `16px glyph | content | mono time` grid. A tool call shows the mono tool name, its reason in 14px ink, and while it is out a thin blue sweep runs along its bottom edge; when it returns, a nested 6px-cornered result row opens with a spring height, a return-arrow icon, and a mono duration. A follow toggle keeps the newest row in view.

### Gate Instruments (signature)
Six fixed cells (G0–G5) in a 1px-gapped grid: mono index, a semicircular needle that settles with an overdamped spring, a bold 11.5px short name, and a colored reading word. Each gate owns one truth and never moves position.

### Hold Light
When a row's status changes in view, a background in the status wash (`brand-50`, `ok-bg`, `warn-bg`, `err-bg`) holds for about 55% of 2.6s and then fades to transparent, so a change stays noticed without a toast.

## Do's and Don'ts

### Do:
- **Do** put every measured value (tickers, tool names, endpoints, clocks, counts, Rp) in Roboto Mono 500–600 with tabular numerals.
- **Do** build new regions as ruled parts of the console: 1px `rule` borders, 8px outer corners, 20px padding, a 14px bold region head with a mono reading on the right.
- **Do** pair every status color with a status word or icon; color alone never carries meaning.
- **Do** use the E-mark three-bar live indicator for "running", and damped springs (stiffness 420, damping 40) or ease-out-expo for state changes.
- **Do** give every new token a dark value along the brand blue's hue, keeping body and secondary ink at 4.5:1 or better.
- **Do** honour reduced motion: the global media query flattens durations, and tweened numbers jump straight to their value.

### Don't:
- **Don't** use `live` green for text, fills or "success"; finished is `done` teal.
- **Don't** use amber for anything but warnings.
- **Don't** lay out Deck content as a grid of shadowed cards or as a chat transcript; it is one ruled console.
- **Don't** cast shadows on console regions or rows; only overlays float.
- **Don't** let motion overshoot or bounce; gate needles and springs are critically or over-damped.
- **Don't** uppercase anything except machine state words and ticker codes.
