# Merge plan — pre-build reference-branch consolidation

> Goal: merge the three parallel `references/*` extraction branches into `main` without breaking the 19 cross-lane links the F1 audit found.

## Context (from F1 audit)

We have 3 reference extraction branches + 3 audit branches all hanging off `main`:

| Branch | Type | Last known SHA (29 Aug 2026) |
|---|---|---|
| `references/rest-idx-mining-2026-08-29` | Doc extraction | `75a1aaf` (rest idx + mining) |
| `references/mcp-idx-mining-2026-08-29` | Doc extraction | `681ce21` (mcp + recipes) |
| `references/cookbook-idx-mining-2026-08-29` | Doc extraction | `8d8ecf7` (quickstart + cookbook) |
| `references/audit/f1-repo-2026-08-29` | Audit | `75a1aaf` |
| `references/audit/f2-cookbook-2026-08-29` | Audit | `952e6bb` |
| `references/audit/f3-ideas-2026-08-29` | Audit | `2230ccb` |

The cookbooks branch (`references/cookbook-idx-mining-2026-08-29`) has **14 cross-references** to `references/rest/idx-screener.md`, `references/rest/idx-company.md`, etc. that don't exist on `main` and won't exist until the rest branch is merged.

## Canonical merge order

Merging in the wrong order → broken links on `main` for hours/days.

### Step 1: Plan-only main updates (no code, no content from other branches)

Already done on `fix/f1-audit-2026-08-29`:

- README TOC
- New planning files: `merge-plan.md` (this file), `team-roster.md`, `onboarding-blocker.md`, `credit-calculator.md`, `video-recording-guide.md`, `disclaimer-template.md`
- `ideas.md` updates (problem-statement template, risk register, stack decision matrix per track)

This step does NOT merge any `references/*` content. It only adds new planning files + small edits to `main`-only files.

### Step 2: Merge `references/rest-idx-mining-2026-08-29` first

This is the **leaf branch** — it has the fewest cross-lane dependencies (cookbook links TO it, not the other way around).

```bash
git checkout main
git merge --no-ff references/rest-idx-mining-2026-08-29 -m "merge: bring IDX + Mining REST catalog into main"
```

After merge: `references/rest/*.md` exist on `main`.

### Step 3: Merge `references/mcp-idx-mining-2026-08-29` second

Cookbook will reference MCP docs in step 4. Merging MCP now means cross-refs from `references/recipes/*.md` and `references/mcp/*.md` land on main.

```bash
git merge --no-ff references/mcp-idx-mining-2026-08-29 -m "merge: bring MCP setup + agent recipes into main"
```

After merge: `references/mcp/*.md` and `references/recipes/*.md` exist on `main`.

**Cross-link caveat:** `references/mcp/tools.md` has 55 dead REST cross-refs (per F1 audit). These should be fixed in this same merge, not deferred. See "Cleanup step 3a" below.

#### Step 3a: Cleanup — fix `mcp/tools.md` dead cross-refs

55 dead links in `mcp/tools.md` (one per MCP tool that points to a non-existent per-endpoint REST stub). Two acceptable fixes per F1 audit recommendation:

- **Option (b) — recommended, ~30 min:** Rewrite all 55 cross-refs to point at the 7 actual rest-lane files (`idx-screener.md`, `idx-company.md`, `idx-financials-transactions.md`, `idx-rankings-brokers-news.md`, `mining-companies.md`, `mining-commodities-trade.md`, `mining-sites-licenses.md`) with anchor fragments. Lower effort, acceptable UX.
- **Option (a) — better UX, ~2h:** Create one stub file per MCP tool under `references/rest/mcp-tool-stubs/` with a one-hop deep link. Worth it only if the team plans to use MCP extensively.

Pick option (b) unless a teammate volunteers for (a).

### Step 4: Merge `references/cookbook-idx-mining-2026-08-29` last

Cookbook has the most cross-lane references (14 to `references/rest/idx-*.md`, 19 to sibling lane files). All 14 REST cross-refs should resolve after step 2.

```bash
git merge --no-ff references/cookbook-idx-mining-2026-08-29 -m "merge: bring quickstart + 14 cookbooks into main"
```

After merge: `references/quickstart.md` and `references/cookbook/*.md` exist on `main`.

### Step 5: Audit branches (optional — read-only context, can stay as references)

`references/audit/f1-repo-2026-08-29`, `references/audit/f2-cookbook-2026-08-29`, `references/audit/f3-ideas-2026-08-29` are point-in-time audit deliverables. **Don't merge into `main`.** Leave them as standalone branches so they remain searchable / citable. If you want them visible on `main`, copy `references/audit/` directories from each branch into a single commit — but this is optional.

### Step 6: Final cleanup

After all merges, on `main`:

```bash
# Re-run the F1 audit's link-resolution pass
# (or manually grep broken links)
grep -rn '\[.*\](\.\./' references/ | grep -v 'http'
```

If any links are still broken, fix in a follow-up commit.

## Validation matrix (run after each step)

| Step | Test | Expected |
|---|---|---|
| 1 | `git grep` for `references/rest` | Should NOT exist on main yet (only after step 2) |
| 2 (post-merge) | `git grep "references/rest/idx-screener"` | Should resolve to a real file |
| 3 (post-merge) | `git grep "references/recipes"` | Should resolve to real files |
| 4 (post-merge) | `git grep "../rest/idx-.*\.md"` from cookbook files | All 14 should resolve |
| 5 | `git log --graph --oneline main` | Should show 3 merge commits in canonical order |

## Anti-patterns (do NOT do)

- ❌ Merge cookbook before rest or mcp → 14 broken cross-refs
- ❌ Force-push to `main` to "fix" a bad merge
- ❌ Skip step 3a — the 55 dead links WILL be judged by reviewers scanning the repo
- ❌ Squash-merge the reference branches (we lose the per-file commit history the F1 audit tracked)

## When NOT to follow this plan

If the team decides to keep `main` strictly planning-only (no reference docs at all), then steps 2-4 are skipped — reference docs stay in their branches and `main` only carries planning + (eventually) project code under `experiment/<track>/`.

This is **not** the recommended approach because it makes judges' review harder (they'd have to switch branches to verify the docs claim). The plan above is the cleaner path.
