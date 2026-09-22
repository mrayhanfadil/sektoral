# Official Rules — Sectors Hackathon 2026

> Source: <https://hackathon.sectors.app/rules>
> Copied here for offline reading and quick reference. If the official page changes after 19 Aug 2026, organizers will announce updates through their official channels and won't disadvantage participants who started under the prior rules.

---

## 01. Spirit of the competition

Sectors Hackathon is not a typical coding competition. We don't judge how sophisticated your code is. We judge whether what you build can genuinely be used by real people, today, with Sectors data at its core.

> "Solve an interesting problem thoughtfully with Sectors API."

---

## 02. Key dates

| Milestone | Date |
| --- | --- |
| Registration opens | 19 August 2026 |
| Build period opens | 19 August 2026 |
| Registration closes | 22 September 2026, 23:59 WIB |
| Build period and submissions close | 30 September 2026, 23:59 WIB |
| Judging period | 1–8 October 2026 |
| Winners announced | 9 October 2026 |

Registration closes before the submission deadline so onboarding and credit grants can be verified. A team registering on the final day still has a full week to build.

---

## 03. Eligibility

- Open to Indonesian citizens or residents domiciled in Indonesia.
- Open to all ages. Participants under 18 must provide parental or guardian consent at registration, covering media publication consent and prize acceptance through a guardian.
- Employees, contractors, judges, mentors, and organizers of Supertype, Sectors, and Algoritma, along with their immediate families, are not eligible to participate.
- Registration is free of charge.
- Every team participant must create a Sectors account and fully complete the Sectors App onboarding process at sectors.app before the team writes any project code. Onboarding is verified during the eligibility check. A team with any participant who has not completed onboarding by the registration deadline may have its submission deemed invalid.
- By registering, participants are deemed to have read and agreed to these rules in full.

---

## 04. Teams & API credits

- Participants may compete solo or in teams of 2–4 participants. A solo participant is treated as a team of one.
- Each participant may only register on one team, including a solo team. A participant found on multiple teams is removed from all of them; the teams may continue with their remaining participants unless organizers find deliberate collusion, in which case every team involved is disqualified.
- Each team may submit only one project.
- Team rosters are locked once the team claims their team bonus API credits (available after all members complete onboarding).
- Each team appoints one representative as its official contact, API credit holder, and prize recipient.
- Prizes are awarded per team. How a prize is split is the team's internal matter.

### API credits

Each registered team receives **1,000 Sectors API credits**, which can be claimed via the [team page](https://hackathon.sectors.app/portal/team) in the hackathon portal once all team members have completed onboarding.

- Registering additional accounts to obtain extra credits for the same project is a rules violation → disqualification.
- Credits are exclusively for developing the team's competition project during the build period.
- Non-transferable, cannot be exchanged for cash or other compensation, expire when the event concludes unless organizers state otherwise.

---

## 05. Build period & work restrictions

Build period runs from **19 Aug 2026** through **30 Sep 2026, 23:59 WIB**. Teams may start whenever they are ready during that window; there is no separate fixed build week.

- **Before the build period**: ideas, research, sketches, designs, and planning are allowed. **No project code may be written before 19 August 2026.**
- **Repo creation**: The project repository must be created during the build period. Judges may inspect commit history. Repositories created before 19 August 2026, or code migrated from previous projects, may result in disqualification. Multiple repositories are allowed if all were created within the build period.
- **Templates & OSS**: Starting from a public template or boilerplate is allowed, as long as the first commit falls within the build period. Boilerplate, templates, frameworks, libraries, and public open-source code may be used, provided they are not a finished product. Open-sourcing your own prior project before the event solely to reuse its code during the event is prohibited.
- **Single competition**: Projects must be exclusive to Sectors Hackathon. No work from previous projects, no submission to other competitions or hackathons.
- **Freeze**: A team's repository and application freeze on submit, or at the 30 Sep deadline — whichever first. After freezing, **no commits, pushes, edits, or changes of any kind are allowed, including bug fixes**. Violation → disqualification.
- **Freeze exception (only)**: a leaked API key / credential — notify organizers on Slack `#support`, revoke + rotate the credential first, then push a commit containing only its removal.

---

## 06. Project requirements

### General requirements for every track

- Projects must use **Sectors MCP or the Sectors REST API as a core data source**, not as a single decorative call. The product should **lose its core functionality if Sectors data is removed**. Any track may use MCP, REST, or both.
- Projects must be a **working prototype or MVP** with a core workflow that functions end to end. Rough edges are acceptable; a product that does not work will not pass judging.
- **Live deployment is not required.** A public repository + judging video showing the core workflow end to end are sufficient to clear eligibility. (But real-world usability carries the highest judging weight, so a product judges can see working convincingly will score better.)
- Stack, tools, programming languages, licenses, and platforms are unrestricted. Public repo is sufficient; no specific OSS license required.
- **Automated trade execution is prohibited in every track.** Products may analyze, screen, score, alert, and support decisions, but may **not** place, execute, or automate buy/sell orders on real or brokerage-connected accounts.

### Track summary (full briefs in [`tracks/`](tracks/))

- **Track 01 — AI Agents & Assistants.** Conversational or autonomous AI products for Indonesian financial markets, with an AI/LLM component at their core.
- **Track 02 — Automation & Workflows.** Products in which Sectors data works inside real, recurring routines.
- **Track 03 — Market Intelligence.** Products that turn Sectors data into insight for financial market decisions.

### Track boundaries and support

Track is determined by **what the product fundamentally does**, not what it looks like. Examples from organizers:

- An agent with a dashboard interface still belongs in **AI Agents & Assistants**.
- An autonomous pipeline that also produces scores may fit **Automation & Workflows** or **Market Intelligence** — team chooses.

If a project does not meet its declared track's requirement, judges may move it to the track that fits rather than disqualify. Track-based disqualification applies only when the project fits no track. Unsure teams should ask on Slack `#discussion` during the build period.

---

## 07. Use of AI

The use of AI coding tools (code generation, completion, agents, similar) is **fully permitted, without restriction and without a disclosure requirement**. It's 2026, so use your best tools. What we judge is the result.

---

## 08. Submission requirements

Submissions must be made through the [hackathon portal](https://hackathon.sectors.app/portal/submit) before **30 Sep 2026, 23:59 WIB**. Submissions must include:

- **A public repository link.** Must remain public for **≥90 days after winners are announced**. Making it private before then forfeits prize eligibility, and a replacement winner may be selected. **Remove all API keys before submitting.**
- **A one-minute teaser video**: screen recording of the product working, published publicly on YouTube or social media.
- **A judging video of up to three minutes**: full walkthrough of the problem, intended audience, and core workflow. Accepted: public/unlisted YouTube, Vimeo, Google Drive with link sharing on, Loom. **Inaccessible videos will not be judged.**
- **A one-sentence problem statement** explaining who the product is for and what problem it solves.
- **Track selection + list of team participant names.**
- **A social media post** publishing the project, tagging the official Sectors account.

Submissions and videos may be in Bahasa Indonesia or English. Neither language is favored in scoring.

---

## 09. Judging

Judging is **fully asynchronous from 1–8 Oct 2026**, based on submission materials. **No live presentation sessions.** Make sure video and repo speak for themselves.

### Eligibility check — pass or fail

The submission is complete, the product works, Sectors data is used as a core source, and every team participant's Sectors onboarding is verified.

### Scoring

| Criterion | Weight | What it rewards |
| --- | --- | --- |
| **Real-world usability** | **40%** | How well does the project address a real-world problem? Can someone use it today and benefit from it? |
| **Video demo & storytelling** | **30%** | How exciting, engaging, well-produced is the video? Does it communicate the problem effectively for the intended audience? |
| **Technical depth & execution** | **30%** | Verified against the GitHub repo, how innovative is the use of Sectors API/MCP? Is the project real, functional, well-engineered, and not faked for the demo? |

Judges' decisions are final and binding.

---

## 10. Prizes

Total prize pool: **IDR 50,000,000** = IDR 30M cash + IDR 20M Sectors API credits.

- Cash prizes go to the team representative. Prize taxes follow applicable Indonesian law.
- API credit prizes are credited directly to the team representative's Sectors account.
- Winners under 18 receive prizes through a parent or guardian.
- Organizers may require identity verification before prize delivery. Failure to verify within 7 days may result in prize being reassigned.

---

## 11. Publicity & content rights

- By submitting, participants grant Sectors and Supertype permission to display, publish, and promote the submission — including videos, screenshots, project names, and participant names — on their websites, social media, newsletters, and promotional materials, without additional compensation.
- Intellectual property in the project remains entirely with the participants. Sectors and Supertype claim no ownership rights over any code or product built during the event.
- Participants are responsible for ensuring their project does not infringe the IP rights of others.

---

## 12. Code of conduct

- All participants must maintain a safe, welcoming, harassment-free environment on Slack, social media, and every event channel.
- Projects containing discriminatory (SARA), harassing, or unlawful content → automatic disqualification.
- **Projects must not provide financial advice.** Products must position themselves as information and analysis tools, not investment recommendations. Include a disclaimer where relevant.
- Violations may be reported in the `#support` channel on the official Slack.

---

## 13. Disqualification

Organizers may disqualify any participant or team at their sole discretion, including for:

- Violating these rules
- Cheating — including pre-event code and code-freeze violations
- Creating multiple accounts for additional API credits
- Duplicate submissions
- Code of conduct violations
- Other unsporting behavior

---

## 14. Support

Organizers may update these rules before 19 August 2026. Changes made after registration opens will be announced across all official channels and will not disadvantage participants who have already begun under the previous rules.

Questions: `ask+hackathon@incoming.supertype.ai` or Slack `#discussion` channel.
