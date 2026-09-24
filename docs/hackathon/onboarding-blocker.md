# Onboarding blocker tracker

> Rules §03 + §04 — every team member must finish sectors.app onboarding **before any project code is written**. Onboarding is verified at eligibility check. A non-onboarded member can disqualify the entire submission.

## Why this exists as its own file

The F1 audit flagged this as **gap G-5**: "Onboarding blocker tracker — Rules §03 onboarding is a hard precondition for eligibility AND for claiming credits. The repo only has it as a checklist line; no Kanban task, no due-date, no escalation rule if a team member doesn't complete it."

This file is the operational version. Mirror status from [`team-roster.md`](team-roster.md) weekly.

## What "onboarding complete" means

Each teammate must:

1. **Create a Sectors account** at [sectors.app](https://sectors.app/auth) (or log in if they already have one).
2. **Complete the in-app onboarding flow** — the Sectors App has a multi-step onboarding tour that includes watching company data render in the dashboard.
3. **Generate an API key** at [sectors.app/api](https://sectors.app/api) after onboarding. Save it locally (`.env`, mode 600) — DO NOT commit.
4. **Onboard, then claim credits.** The 1,000-credit grant only unlocks after every team member's onboarding is verified.

## Onboarding steps per teammate

```markdown
- [ ] Account created at sectors.app
- [ ] In-app onboarding tour completed (can browse a company report end-to-end)
- [ ] API key generated and saved to local `.env` (mode 600, NOT committed)
- [ ] Joined team on https://hackathon.sectors.app/portal/team
- [ ] Confirmed in team roster this file (status = 🟢)
```

## Hard blockers (must clear before any project code)

If **any** teammate is ⚪ on onboarding at the start of project code work:

1. **Pause all coding.** Resume only when roster is fully 🟢 on onboarding.
2. **Escalate to that teammate directly** — rules §03 disqualification is real.
3. **If unresolved within 48 hours**, drop them from the team per [`team-roster.md`](team-roster.md) escalation rule.

## Why rules §03 + §04 are strict

Verbatim from [rules.md](rules.md):

> "Every team participant must create a Sectors account and fully complete the Sectors App onboarding process at sectors.app before the team writes any project code. Onboarding is verified during the eligibility check. A team with any participant who has not completed onboarding by the registration deadline may have its submission deemed invalid."

> "Team rosters are locked once the team claims their team bonus API credits (available after all members complete onboarding)."

## Common onboarding pitfalls (we've seen these in prior hackathons)

- **Skipped the tour.** The "I've used Sectors before, skip onboarding" option exists but **does not satisfy** the onboarding rule. Re-run the full tour.
- **Used a personal email instead of GitHub-verified email.** Onboarding may complete but portal verification fails because portal expects the email registered on the team page.
- **Multiple accounts.** Rules §04 explicitly forbids registering multiple accounts to claim extra credits — disqualification risk.
- **Read-only testing.** Clicking through company reports on the web app is not a substitute for the onboarding flow.

## Once everyone is 🟢

Mark each teammate 🟢 in [`team-roster.md`](team-roster.md). Then the team representative goes to the team page and **claims the 1,000 Sectors API credits**. After that, the team can finally start writing project code.
