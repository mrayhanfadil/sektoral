# Submission Checklist

> **Hard deadline: 30 September 2026, 23:59 WIB.** Build period freezes on submit or at deadline, whichever first. After freeze: **no commits, pushes, edits, or changes of any kind** — even bug fixes — or we get disqualified. The only freeze exception is a leaked credential (notify `#support` first, rotate, then removal-only commit).

Cut this checklist up into weekly targets. Today is **29 Aug 2026** → we have ~32 days.

---

## Pre-build prerequisites (BEFORE any project code)

- [ ] **All team members onboarded at sectors.app.** Required for eligibility + API credit unlock. Verified by organizers.
- [ ] **Team registered on hackathon portal.** https://hackathon.sectors.app/portal/team
- [ ] **Team rep appointed** (single contact + prize + API credit holder).
- [ ] **1,000 Sectors API credits claimed** via team page (only after all onboarded).
- [ ] **Track chosen** — read [`tracks/`](tracks/) + [`ideas.md`](ideas.md), decide.
- [ ] **Repo created during build period.** ✅ Done 29 Aug 2026 with planning artifacts only.
- [ ] **No project code from before 19 Aug 2026.** ✅ This repo's first commit is 29 Aug 2026; no migration of code from other repos.

---

## Build phase — week-by-week

### Week 1 (29 Aug – 4 Sep) — scope & skeleton

- [ ] Lock track. Document the choice in [`ideas.md`](ideas.md) "Decision" section.
- [ ] Define the **one-sentence problem statement** (used verbatim on submission).
- [ ] Identify the **intended audience** (used in judging video).
- [ ] Sketch the **core workflow** end-to-end (user → product → Sectors data → result).
- [ ] Pick stack. Add to [`experiment/<track-slug>/README.md`](../../) once created.
- [ ] Confirm the product **breaks if Sectors data is removed** (organizers' litmus test).

### Week 2 (5–11 Sep) — MVP loop

- [ ] Integrate Sectors REST or MCP — prove it works on a single endpoint.
- [ ] Build the smallest end-to-end core workflow (input → Sectors fetch → output).
- [ ] Cache / rate-limit awareness — 1,000 credits is the cap; budget it.
- [ ] Add error handling — product must not silently fail.

### Week 3 (12–18 Sep) — polish + edge cases

- [ ] Add the "second" feature that makes it actually useful (the one a real person would use today).
- [ ] Document setup & run in README (so judges can `git clone` and try it).
- [ ] **Strip all API keys / secrets from the repo.** Use `.env.example` not `.env`.
- [ ] Add a disclaimer that the product is **information, not financial advice** (rules §12).

### Week 4 (19–25 Sep) — videos

- [ ] **60-second teaser video** — public YouTube or social media. Screen recording of the product working.
- [ ] **Up-to-3-minute judging video** — public/unlisted YouTube, Vimeo, Google Drive (sharing on), or Loom. Problem → audience → core workflow → result. **Test the link on a fresh browser** before submitting.
- [ ] **One-sentence problem statement** finalized.
- [ ] **Social media post** — tag the official Sectors account. Save URL.

### Final 5 days (26–30 Sep) — submit

- [ ] Day-of buffer: stop coding by 28 Sep EOD. Last 2 days for review + portal submission only.
- [ ] **Confirm repo is public.** It must stay public for **≥90 days after winners announced** (9 Oct 2026) → at least until **7 Jan 2027**.
- [ ] **Confirm no API keys committed.** Grep for tokens, secret patterns, `.env` files.
- [ ] Submit through https://hackathon.sectors.app/portal/submit BEFORE 30 Sep 23:59 WIB.
- [ ] Capture the **submission confirmation** screenshot/URL.

---

## At-the-portal submission form (what we'll need ready)

| Field | Content |
|---|---|
| Public repo URL | https://github.com/mrayhanfadil/sectors-hackathon (or experiment-branch link) |
| 60-second teaser URL | (YouTube/social link) |
| Judging video URL | (YouTube unlisted / Vimeo / Drive / Loom) |
| One-sentence problem statement | (locked from Week 1) |
| Track selection | (ai-agents / automation / market-intelligence) |
| Team participant names | (per roster) |
| Social media post URL | (tagging official Sectors account) |

---

## Post-freeze DO-NOT list (after we hit submit / 30 Sep 23:59 WIB)

- ❌ Do **not** commit, push, edit anything in the repo (no bug fixes, no README tweaks, no doc fixes).
- ❌ Do **not** make the repo private within 90 days of winners announced.
- ❌ Do **not** submit to any other hackathon or competition.

**Only exception:** leaked credential → Slack `#support` notify → rotate → removal-only commit.

---

## Useful links (mirror of README)

- Rules: https://hackathon.sectors.app/rules
- Team portal: https://hackathon.sectors.app/portal/team
- Submission portal: https://hackathon.sectors.app/portal/submit
- Slack invite: https://join.slack.com/t/sectorshackathon/shared_invite/zt-47a8tdhhz-FgREdKQ46lUETWErcIwNcQ
- Email: ask+hackathon@incoming.supertype.ai
