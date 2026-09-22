### 2026-09-04 - Gate 1 fallback default = shortened DCF + thin-data disclosure (NOT pure Relative)

User decision: when a ticker has <4y filing history (e.g. CDIA), the gate runner
defaults to DCF with a shorter explicit horizon (e.g. 5y explicit + terminal value)
PLUS a mandatory "⚠ Thin Data" disclosure banner on the PDF cover.

Rationale: pure Relative Valuation produces no defensible fair value (just a peer
average); shortened DCF + honest disclosure preserves the math and surfaces the
caveat to the reader. Rejected: (a) pure Relative Valuation - no actionable number;
(b) skip DCF entirely - throws away the projection work.

### 2026-09-11 - `main` mirrors the product branch (FF-only promotion before submit)

User decision: promote `feat/institutional-report` (188 commits) onto `main` by
fast-forward, and keep `main` as a mirror of the product branch - re-fast-forward
at each milestone and once more before the freeze.

Rationale: the submitted repo URL is public and judges `git clone` it; with `main`
carrying planning docs only (0 code files), a clone yields nothing runnable. FF
keeps the 188-commit history linear (no merge commit, no squash), so blame/log stay
intact and no force-push is ever needed.

Rejected: (a) squash-merge - destroys per-commit history judges may scan;
(b) `--no-ff` marker commit - a promotion commit is not work, and it makes `main`
diverge from the product branch (later FF impossible, merge needed); (c) keeping
`main` docs-only and pointing judges at a branch - the checklist requires a public
repo URL, not a branch URL.

Freeze reminder: the last promotion must land **before 30 Sep 23:59 WIB**; after
freeze the repo accepts zero commits, bug fixes included.
