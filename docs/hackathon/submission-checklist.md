# Sectors Hackathon 2026 — submission checklist

**Submission deadline: 8 October 2026, 23:59 WIB** (moved from 30 September; re-checked 24 September 2026). Submission is through the [hackathon portal](https://hackathon.sectors.app/portal/submit). The repository and application freeze as soon as the team submits or at the deadline, whichever comes first. After freeze, do not edit, commit, or push, including fixes. The rules make a narrow exception for leaked credentials: notify Slack `#support`, revoke and rotate the credential, then push a removal-only commit.

Verify details against the [official rules](https://hackathon.sectors.app/rules) and [AI Agents & Assistants track](https://hackathon.sectors.app/tracks/ai-agents-assistants) before submission.

## Project and eligibility

- [ ] Product is a working end-to-end prototype. The judged workflow is shown in the video and works in the submitted repository.
- [ ] Sectors MCP or REST data is central to the product. For the current Sektoral workflow, the agent and report use only ticker-specific rows in `data/sectors_cache.db`; do not describe the demo as making live upstream Sectors requests.
- [ ] AI/LLM and custom-built agent logic/orchestration are core to the declared AI Agents & Assistants track.
- [ ] Every participant completed Sectors App onboarding, the team registration is valid, and the team has 2–4 participants (or one solo participant).
- [ ] The project repository was created during the build period and the project contains no pre-event project code. Check commit history and provenance before submitting.
- [ ] No secrets, API keys, `.env` files, or private credentials are in the public repository or recording.
- [ ] Public-facing screens and narration position the product as information and analysis, not investment recommendations or financial advice. There is no automated trade execution.
- [ ] Drafts, withheld sections, and missing evidence are labeled honestly. The demo uses a freshly generated result and trace from the current checkout.

## Required portal materials

- [ ] **Public repository URL.** Keep the repository public for at least 90 days after winners are announced on 17 October 2026 — through at least **15 January 2027**. Remove keys before making it public.
- [ ] **60-second teaser.** A screen recording of the product working, published publicly on YouTube or social media. Keep it to 60 seconds or less.
- [ ] **Judging video, up to three minutes.** Walk through the problem, intended audience, and core workflow. Accepted hosting: public or unlisted YouTube, Vimeo, Google Drive with link sharing enabled, or Loom. Check access while signed out; inaccessible videos are not judged.
- [ ] **One-sentence problem statement.** Suggested: “Sektoral helps Indonesian equity analysts get a planned, peer-ranked, source-cited company update for any IDX ticker, with every conclusion traced to Sectors data and every evidence gap shown.”
- [ ] **Track selection:** AI Agents & Assistants.
- [ ] **Names of all team participants**, matching the registered team.
- [ ] **Public social post URL.** Post on Instagram, LinkedIn, Threads, or TikTok; tag the official Sectors account and use the [official thumbnail template](https://www.canva.com/design/DAHUfZI9dJI/rcFmHic2Nn5Hdqj7DLwfmw/edit). Save the URL. A post on Twitter/X alone does not satisfy the channels listed in the rules.

## Final run-through

- [ ] Run the exact README command on the exact submission checkout: `python3 -m app.research BBCA --out out/demo --pdf` (or the actual demo ticker). Omit `--pdf` if Playwright is unavailable; HTML is the default output.
- [ ] Confirm the report and machine-readable trace are newly produced and mutually consistent. Inspect every source/citation shown in the video.
- [ ] If the chosen ticker has no relevant cached news or lacks evidence for a section, show that honestly. Do not use an old `out/*.json` or present a failed/draft result as a completed update.
- [ ] Watch both videos from beginning to end. Test each URL in a private/incognito browser without signing in; confirm the teaser is public and the judging video is accessible.
- [ ] Verify the repository opens publicly, README setup matches the submitted version, and no credentials are tracked.
- [ ] Complete portal submission before 23:59 WIB on 8 October. Save the confirmation and verify the submitted links and text.
- [ ] After submission, freeze the repository and application. Do not make routine post-submission edits or pushes.

## Official links

- [Rules and submission requirements](https://hackathon.sectors.app/rules)
- [AI Agents & Assistants track](https://hackathon.sectors.app/tracks/ai-agents-assistants)
- [Team portal](https://hackathon.sectors.app/portal/team)
- [Submission portal](https://hackathon.sectors.app/portal/submit)
- [Official thumbnail template](https://www.canva.com/design/DAHUfZI9dJI/rcFmHic2Nn5Hdqj7DLwfmw/edit)
- [Video scripts and access checks](video-recording-guide.md)
