---
version: 1
slug: "web-src-pages-deck-tsx"
primary_target: "web/src/pages/Deck.tsx"
related_targets: ["web/src/pages/Landing.tsx","web/src/pages/Research.tsx","web/src/pages/Gallery.tsx","web/src/pages/Trace.tsx"]
---

# Sektoral Command Deck (web app)

Scope: the React app in web/ (landing, research launcher, live run Deck, run replay, report gallery, audit trace). Visitor mode: Operate for the Deck, launcher, gallery and trace; Persuade for the landing page. Audience: Indonesian equity analysts and hackathon judges watching a recorded demo. Job: start a research run on an IDX ticker, watch every agent, tool call and Method Gate decision as it happens, then open the company update. Constraints: Bahasa Indonesia UI, PRODUCT.md brand commitments (Sektoral blue, Roboto, E-mark three bars, chart series), no invented claims, whitelisted API data only, light and dark, phone to desktop, reduced motion respected.

Memorable moment: a tool call goes out with its reason and comes back with its result while the agent rail lights the agent that made it.

Unresolved: none blocking. The user was not re-asked (session continued unattended); the user-pinned direction is the Command Deck from mrayhanfadil/sectors-hackathon.

## Direction contract

THESIS: The Deck shows a research desk at work: each agent, tool call and Method Gate decision appears live in one console an analyst could audit. It refuses the category default: a chat transcript or a spinner with a step list.

OWN-WORLD: The Command Deck grammar from sectors-hackathon: function-key tabs ([F1] Deck, [F2] Laporan, [F3] Cara kerja), a Cmd-K ticker palette, an agent status rail reading ANTRI / JALAN / SELESAI, and mono data (tool names, endpoints, timestamps, Rp figures). Its materials are Sektoral's:
- a navy console ground drawn from #0928B1 in dark, and paper white in light;
- brand blue #0928B1 / #7596FF for the active agent, teal #1DCD9F for done, and green #3ED628 only for the live pulse; amber is kept for warnings;
- the E-mark's three bars become the live indicator;
- Roboto for text and Roboto Mono for data;
- 1px rules and 6px corners: panels are ruled regions of one console, not a card grid.
Raise, from the gate board: a changed row holds its light until noticed, and rows keep their identity as they move. Raise, from the night six-pack: the six Method Gates are fixed instruments, each owning one truth, with damped motion that never snaps.

STORY: The viewer picks a ticker with Cmd-K and watches:
1. the planner writes its question and hypotheses;
2. each tool call leaves with its reason and returns with its result;
3. the research and forecast subagents fan out;
4. the six gates settle and the method chain picks a valuation.
Then the viewer opens the report or replays the run.

FIRST VIEWPORT: The Deck at 1440px:
- a 52px deck bar: wordmark, F-keys, Cmd-K, clock and theme;
- a run header: the ticker in large mono, the company name, the state with a pulse, an elapsed timer and the replay speed;
- the agent rail: seven nodes in pipeline order;
- a phase bar;
- the event stream at 7/12 width, with tool-call cards;
- a right column: the plan and hypotheses, the six gate instruments, and the method chain;
- the primary action, open the report, in the header once the run is done.
The landing page's first viewport pairs the offer and a ticker launcher with a live replay of a real run.

FORM: The user-pinned Command Deck of sectors-hackathon. A pinned brief beats the roll, so the assigned grounded index 4 was not built. Seed key 499f07da.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
