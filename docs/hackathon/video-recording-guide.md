# Video recording guide

The submission needs two real product recordings: a public teaser of up to 60 seconds and a judging walkthrough of up to three minutes. The main demo should use Sektoral's local browser UI: enter ticker → watch status → open report or agent trace. Record a fresh run from the current checkout and use only outputs it actually produced.

## Before recording

1. From the repository root, start the app with `docker compose up --build` (or `.venv/bin/python -m app.server` after building `web/`), then open `http://127.0.0.1:8765`. The server is reachable on localhost only.
2. Confirm `.env` has the configured LLM key and that the selected ticker has useful rows in `data/sectors_cache.db`. Do not show `.env` or the key. The run needs network access to the LLM endpoint, while market data comes only from the local Sectors cache; the workflow does not call Sectors upstream.
3. On the landing page, select **Coba riset emiten**, enter the ticker on `/research`, and click **Mulai riset**. Keep the actual status visible, including a partial result or error. When completed, open **Buka company update** and **Lihat jejak agent**.
4. Check the actual report and trace for the selected run. The generated files are in `out/demo/<job-id>/` as `<TICKER>.html` and `<TICKER>-trace.html`; the structured report and trace are in the app database (`data/sectoral.db`) and the trace is also shown on the run's **Lihat jejak agent** page. Explain only sources, claims, and evidence gaps visible in those artifacts.
5. The BBCA CLI and browser workflows completed end-to-end QA on this working checkout. Confirm the frozen submission checkout and regenerate its artifacts before recording. Do not combine unrelated runs, invent agent steps, or pass off a stale artifact as the fresh result.

For a terminal-only run, the one-command workflow is `python3 -m app.research BBCA --out out/demo --pdf` (replace the ticker as needed). Omit `--pdf` if PDF support is unavailable; HTML is the default. To capture the real browser workflow, run `python3 scripts/record_demo.py --ticker BBCA`; it opens the landing page, follows the CTA, submits a live job, and saves the raw recording under `out/demo-video/`. The video should still foreground the browser workflow.

## Judging video — target 2:45, maximum 3:00

| Time | Screen and narration |
|---|---|
| 0:00–0:15 | Show the Sektoral landing page. Say: “Equity analysts need to connect company data to evidence they can check. Sektoral helps Indonesian equity analysts turn cached Sectors data into a sourced company update, with evidence gaps visible.” |
| 0:15–0:35 | Enter the ticker used for the real run and click **Mulai riset**. Say that this run reads the ticker's Sectors data already in the local cache; the LLM helps the agent reason over that evidence. |
| 0:35–1:00 | Show the actual status page as it moves through processing to completion. Explain the UI's displayed state. If the run is partial, keep the partial label on screen and say what the page tells you. |
| 1:00–1:40 | Open **Lihat jejak agent**. Show the selected cache endpoints and one actual observation, implication, caveat, and citation (endpoint, field path, and value). Describe what the source supports without adding facts from outside the cache. |
| 1:40–2:20 | Open **Buka company update**. Follow the cited evidence into the report and show a relevant section. If the report marks a draft, partial section, or limitation, explain that evidence gap instead of presenting the output as complete. |
| 2:20–2:40 | Return briefly to the browser status or trace. Explain that market data is read from the local Sectors cache and that each run leaves a report and trace to review. Do not imply a live Sectors API call. |
| 2:40–2:55 | Close: “Sektoral is an information and analysis tool, not investment advice.” Show the public repository URL and AI Agents & Assistants track. |

If the LLM run takes longer than the available time, keep the submitted video within three minutes and preserve truthful sequencing. Show the real status/result relationship; do not splice artifacts from different runs or hide a failure as a successful completion.

## Public teaser — 60 seconds

| Time | Screen and narration |
|---|---|
| 0:00–0:07 | Show the actual browser landing page. On-screen title: “Sourced company updates from cached Sectors data.” |
| 0:07–0:17 | Say: “Sektoral is for Indonesian equity analysts who need to see what company data supports—and where the evidence runs out.” |
| 0:17–0:31 | Enter the demo ticker, click **Mulai riset**, and show the actual status page. Keep the ticker and status visible. |
| 0:31–0:48 | Open the report or trace produced by that run. Show one real citation and its corresponding insight, or the visible partial/missing-evidence state if the run is incomplete. |
| 0:48–1:00 | End card: Sektoral, AI Agents & Assistants, team name, public repository URL, and “Information and analysis only; not investment advice.” |

The teaser must show the product working and be publicly accessible on YouTube or social media. A teaser can use a pre-run artifact only if it is clearly the output of a real run from the submitted build; do not present it as a different run.

## Recording and access checks

- Screen recording with clear voice-over is sufficient. Keep the browser, report, and trace legible on a phone.
- Hide `.env`, API keys, personal information, and unrelated desktop notifications. Avoid copyrighted music or footage you are not allowed to use.
- The judging video may be public or unlisted on YouTube, or hosted on Vimeo, Google Drive with link sharing enabled, or Loom. Open the final URL in a private/incognito browser while signed out and play it through.
- The teaser must be public on YouTube or social media. Verify it from a signed-out browser too.
- Add captions or reviewed subtitles, especially for Indonesian company names and technical terms. Check that each video stays within its time limit and the audio is intelligible.
- The judging video should identify the problem, intended audience, and core workflow. The social post is a separate required submission item; include its URL in the portal.

## Required social post

Publish one project post on **Instagram, LinkedIn, Threads, or TikTok**. Tag the official Sectors account and use the [official thumbnail template](https://www.canva.com/design/DAHUfZI9dJI/rcFmHic2Nn5Hdqj7DLwfmw/edit). The rules say “official Sectors account” without specifying a handle; select the verified/current official account on the channel you use. Save the public post URL for the submission form. Twitter/X alone is not one of the channels listed in the current rules.
