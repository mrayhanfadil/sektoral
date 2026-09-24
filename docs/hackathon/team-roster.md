# Team roster

> Single source of truth for who's on the team, their roles, and onboarding status. **Update this file whenever the roster changes.** The hackathon portal team page is the official record; this file is our internal tracker.

## Status legend

- 🟢 = done
- 🟡 = in progress
- 🔴 = blocked
- ⚪ = not started

## Roster

| Name | GitHub handle | Email (login) | Role | Team rep? | Onboarding | API key issued | Credits claimed |
|---|---|---|---|---|---|---|---|
| Fadil (Fadiil) | mrayhanfadil | mrayhanfadil@users.noreply.github.com | Dev + lead | TBD | ⚪ | ⚪ | ⚪ |
| _open slots (up to 3 more)_ | — | — | — | — | — | — | — |

## Roles to fill

Pick roles based on team size. Solo team = one person wears all hats.

- **Team representative (1)** — sole API credit holder + prize recipient. Dotted-line authority on final submission.
- **Backend / data engineer** — Sectors API integration, worker scheduling, cron.
- **Frontend / dashboard engineer** — if product has a UI surface.
- **DevOps / deployment** — CF Worker / Telegram bot / deployment automation.
- **Video producer** — 60s teaser + 3-min judging video. Can be the same person as DevOps.
- **Compliance / writer** — one-sentence problem statement + disclaimer boilerplate + social media post copy.

## Open invite (if team < 4)

If you want collaborators, post to:
- Slack `#discussion` channel of the hackathon
- Tag @sectors + your social circle

Or use `gh api` to invite a GitHub collaborator to this repo:
```bash
gh api -X PUT repos/mrayhanfadil/sectors-hackathon/collaborators/<username>
```

## Escalation rule

If a teammate is ⚪ on onboarding for >3 days before the registration deadline (22 Sep 2026 23:59 WIB), **drop them from the team** and proceed solo or with whoever has onboarded. Rules §03 + §04 are strict: any non-onboarded member can disqualify the entire submission.

## When this file becomes the roster for the submission portal

The submission portal asks for "list of team participant names" (rules §08). Mirror this table's `Name` column into the portal. Names must match exactly what you registered on the portal team page.
