# Video recording guide

> Two videos required (rules §08): a 60-second teaser (public, on social media) and a judging video of up to three minutes. Both must be accessible — inaccessible videos are not judged.

## F1 audit gap that motivated this file

Gap **G-6**: "How do we use the videos we record? The submission checklist asks for two videos. Nothing in the repo tells the team how to record, host (YouTube unlisted vs Vimeo vs Drive), or test accessibility."

## Hard requirements (rules §08)

- **60-second teaser** — screen recording of the product working, published publicly on YouTube or social media.
- **Judging video** — up to 3 minutes, full walkthrough of problem, intended audience, core workflow. Accepted formats:
  - YouTube (public or unlisted)
  - Vimeo
  - Google Drive (link sharing enabled)
  - Loom
- **Inaccessible videos are not judged.** Test on a fresh browser / incognito window before submitting.

## Recommended stack (zero-budget)

| Component | Tool | Cost |
|---|---|---|
| Screen recorder | OBS Studio (Linux/Mac/Win) | Free |
| Webcam (optional) | Built-in laptop cam | Free |
| Mic | Built-in mic + noise suppression (OBS has it) | Free |
| Editor (basic cuts) | DaVinci Resolve or Kdenlive | Free |
| Hosting (judging video) | YouTube unlisted | Free |
| Hosting (teaser) | YouTube public OR TikTok/Instagram Reels | Free |

## Recording workflow

### Before recording

- [ ] **Disable notifications.** OS-level "Do Not Disturb" + browser profile in incognito with no notifications.
- [ ] **Pre-fill test data.** Have one ticker + one good answer ready to demo end-to-end without thinking aloud on camera.
- [ ] **Pick the one visual frame that opens.** The 3-min judging video's first 5 seconds carry the whole real-world-usability story. For Asing Radar: a screenshot of yesterday's foreign-flow Telegram message.

### Teaser (60s)

| Time | What to show |
|---|---|
| 0–5s | The visual frame (one screenshot of the product output, full screen, big text overlay). |
| 5–20s | Problem statement in 1-2 sentences. |
| 20–45s | Live product demo — one short scenario end-to-end, no narration gaps. |
| 45–55s | Call to action: what to do next, where to sign up. |
| 55–60s | Track name + repo link on screen. |

### Judging video (up to 3 min)

| Time | What to show |
|---|---|
| 0–15s | Problem + audience. (Judge §09: real-world usability.) |
| 15–45s | Live core workflow end-to-end. (One run, no skipped steps.) |
| 45–90s | Why this is interesting — the Sectors data dependency, the novel interpretation. (Judge §09: technical depth.) |
| 90–120s | "What I'd do next" — one honest 30-day roadmap sentence. |
| 120–150s | Outro + repo link + social post URL. |

For Track 02 (Asing Radar), the 3-min video can be **mostly silent**: screen recording of a real Telegram channel where the bot has been posting for 2 weeks, with a 30-second voice-over intro.

### After recording

- [ ] **Export at 1080p / 30fps, mp4 (H.264).** Some platforms reject MOV or WEBM. mp4 is the universal safe choice.
- [ ] **Closed captions if you speak.** YouTube auto-captions are good; review them once.
- [ ] **Watch on a fresh device.** Test the public link in an incognito window with no cookies — judges see what the public sees.
- [ ] **Verify on mobile.** 60% of judges will watch on phone. Make sure text is readable at 360p.
- [ ] **Mute the tab audio before screen recording.** Background music copyright can get you auto-muted.

## Hosting checklist (run the night before submit)

For both videos:

- [ ] Public URL works without login (test in incognito)
- [ ] Video plays to completion on slow 4G (test with throttling)
- [ ] Closed captions are visible (or auto-generated review accepted)
- [ ] Description includes: team name, track, repo URL, problem statement one-liner, social post URL
- [ ] Thumbnail is one strong frame, not the auto-generated placeholder
- [ ] Comments are not disabled (judges may want to ask)

## Social post (also required by rules §08)

- Post the teaser on **at least one social channel** — Twitter/X is the easiest (tag @sectors or @sectorsapp).
- Make sure to include `#sectorshackathon` if a hashtag is being tracked.
- Save the URL — paste into submission portal "Social media post" field.

## Common pitfalls

- **Wrong format.** MOV from QuickTime, WEBM from OBS default — both rejected by some platforms. Always export to mp4.
- **No audio.** A 3-min video with no voice-over is technically allowed but judges weight storytelling (30%) — silence hurts.
- **Cuts too fast.** Showing every endpoint for 5 seconds each is the #1 way to get a 30% technical depth score. Pick ONE flow, narrate it.
- **B-roll over narration.** If voice is talking and screen is doing something unrelated, judges can't follow. Sync cuts to narration beats.

## What NOT to do

- ❌ Record with the live Sectors dashboard in the same frame as your code. (It looks like you're claiming their UI is your product.)
- ❌ Use copyrighted music or stock footage with no license.
- ❌ Apologize in the video ("sorry, this is rough, we ran out of time"). Replace with "what I'd do next" framing.
- ❌ Promise features you haven't built. Judges will check the repo.
