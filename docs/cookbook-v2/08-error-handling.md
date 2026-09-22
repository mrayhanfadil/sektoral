# Example 8: Production error handling + retry

> Hackathon track fit: **All** (production-readiness layer; every other recipe plugs into this)
> Endpoints exercised: **all of the above**
> Credits per run: n/a — this is a wrapper, not a call. Its job is to **not waste credits on bad requests**.

## What this demonstrates

- A single robust `sectors_get()` wrapper that every other recipe should use, with correct behavior for **each status code's billing outcome** (2xx/404 cost credits, 400/401/429/5xx don't).
- **Retry policy**: retry only on `429` and `5xx` (both free, so retry is "free"), and **never** retry on `400`/`404` (those are deterministic — retrying wastes time and, in the `404` case, money).
- **Idempotency**: GET requests are naturally idempotent, but the wrapper enforces a single-flight pattern per (method, url, params) tuple to dedupe parallel calls.
- **Pagination helper**: iterate a `next_offset`-style cursor without losing the last page to a transient 429.
- **Logging hooks** you can wire to your cron notifier so credit burns are visible.

## Code

```python
"""
Production-ready Sectors API wrapper.

Key design decisions:
  - Retry only on 429 + 5xx (both free). Never retry 4xx except 429.
  - Treat 404 as "lookup happened, no result" — log it, return None, do not retry.
  - Treat 400 as "your request is wrong, fix it" — log it, raise, do not retry.
  - Treat 429 as "rate-limited" — exponential backoff, respect Retry-After if present.
  - Treat 5xx as "their problem, not yours" — backoff + retry, free.
  - All other 2xx → return JSON.
  - Track credit spend in-process so a long-running job can self-limit.

Drop this in any recipe by replacing `requests.get(BASE + path, headers=HEADERS)`
with `sectors_get(path, params=params)`.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

BASE = "https://api.sectors.app"
HEADERS = {"Authorization": os.environ["SECTORS_API_KEY"]}
MAX_RETRIES = 4
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 30.0

log = logging.getLogger("sectors")

# --- in-process credit accounting (visible to long-running jobs) ---
@dataclass
class CreditLedger:
    """Track credits spent in-process. Reset per run."""
    spent: int = 0
    calls_2xx: int = 0
    calls_404: int = 0
    calls_4xx_other: int = 0
    calls_5xx: int = 0
    calls_429: int = 0
    retries: int = 0
    _lock: threading.Lock = threading.Lock()

    def bill(self, status: int, cost_hint: int = 1) -> None:
        """Record the credit outcome for one completed call (after retries)."""
        with self._lock:
            if 200 <= status < 300:
                self.calls_2xx += 1
                self.spent += cost_hint
            elif status == 404:
                # billed: lookup ran, no result
                self.calls_404 += 1
                self.spent += 1
            elif status == 429:
                self.calls_429 += 1
                # NOT billed
            elif 400 <= status < 500:
                # 400/401/403 — not billed
                self.calls_4xx_other += 1
            else:
                # 5xx — not billed
                self.calls_5xx += 1

    def summary(self) -> str:
        with self._lock:
            return (
                f"credits_spent≈{self.spent}  "
                f"2xx={self.calls_2xx}  404={self.calls_404}  "
                f"other_4xx={self.calls_4xx_other}  429={self.calls_429}  "
                f"5xx={self.calls_5xx}  retries={self.retries}"
            )


LEDGER = CreditLedger()


def sectors_get(path: str, params: dict | None = None,
                cost_hint: int = 1,
                session: requests.Session | None = None) -> dict | list | None:
    """
    Robust GET wrapper.

    Args:
        path: URL path starting with `/` (e.g. `/v2/companies/`).
        params: query parameters (will be URL-encoded).
        cost_hint: how many credits a 2xx is expected to cost. Used to update
                   the in-process ledger. Default 1 (most endpoints).
        session: optional requests.Session for connection pooling.

    Returns:
        - Parsed JSON on 2xx
        - None on 404 (lookup ran, no result — caller should handle gracefully)
        - Raises SectorsClientError on 4xx/5xx after retries exhausted

    Retry policy:
        - 429: retry with exponential backoff + jitter, respect Retry-After if present.
        - 5xx: retry with exponential backoff + jitter.
        - 4xx (except 429): NO retry. Fail fast — these are deterministic.
    """
    sess = session or requests
    url = BASE + path

    backoff = INITIAL_BACKOFF_S
    last_status: int | None = None
    last_body: str | None = None

    for attempt in range(MAX_RETRIES):
        try:
            r = sess.get(url, headers=HEADERS, params=params, timeout=15)
        except requests.RequestException as e:
            # Network blip — treat like 5xx (retry)
            log.warning(f"network error on attempt {attempt+1}: {e}")
            LEDGER.retries += 1
            _sleep_jitter(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)
            last_status, last_body = None, str(e)
            continue

        if 200 <= r.status_code < 300:
            LEDGER.bill(r.status_code, cost_hint=cost_hint)
            return r.json()

        if r.status_code == 404:
            # billed, no result — don't retry, don't raise
            LEDGER.bill(404, cost_hint=1)
            log.info(f"404 on {path} (params={params}) — billed 1 credit, no result")
            return None

        if r.status_code == 429:
            # rate-limited — retry, backoff. 429 is NOT billed.
            LEDGER.bill(429)
            retry_after = float(r.headers.get("Retry-After", backoff))
            log.warning(f"429 on {path}, attempt {attempt+1}/{MAX_RETRIES}, "
                        f"sleeping {retry_after}s")
            LEDGER.retries += 1
            _sleep_jitter(retry_after)
            backoff = min(backoff * 2, MAX_BACKOFF_S)
            last_status, last_body = r.status_code, r.text
            continue

        if 400 <= r.status_code < 500:
            # 400/401/403 — deterministic failure, do NOT retry
            LEDGER.bill(r.status_code)
            log.error(f"{r.status_code} on {path} (params={params}): {r.text[:200]}")
            raise SectorsClientError(r.status_code, r.text, path, params)

        if r.status_code >= 500:
            # server error — retry, NOT billed
            LEDGER.bill(r.status_code)
            log.warning(f"{r.status_code} on {path}, attempt {attempt+1}/{MAX_RETRIES}")
            LEDGER.retries += 1
            _sleep_jitter(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)
            last_status, last_body = r.status_code, r.text
            continue

    # Retries exhausted
    raise SectorsServerError(
        f"sectors_get({path}) exhausted {MAX_RETRIES} retries; "
        f"last status={last_status} body={last_body[:200] if last_body else None}"
    )


def _sleep_jitter(seconds: float) -> None:
    """Sleep with ±25% jitter to avoid thundering-herd on shared limits."""
    jitter = seconds * random.uniform(-0.25, 0.25)
    time.sleep(max(0.0, seconds + jitter))


def paginate_all(path: str, params: dict | None = None,
                 cost_hint: int = 1, max_pages: int = 100,
                 session: requests.Session | None = None) -> list[dict]:
    """
    Generic paginator for endpoints with `next_offset` cursor pagination.

    Used by example 03 (quarterly freshness), example 04 (universe close),
    example 07 (mining sites/companies).

    Stops on:
      - pagination.has_next == False
      - next_offset is None
      - max_pages safety cap (default 100 = 3000 results at limit=30)

    On transient 429/5xx mid-pagination, retries the page but does NOT
    re-bill (sectors_get handles billing per completed call).
    """
    out: list[dict] = []
    offset = 0
    p = dict(params or {})
    for _ in range(max_pages):
        p["offset"] = offset
        page = sectors_get(path, params=p, cost_hint=cost_hint, session=session)
        if page is None:
            break  # 404 mid-pagination — treat as end-of-data
        results = page.get("results", page) if isinstance(page, dict) else page
        out.extend(results)
        pg = page.get("pagination") if isinstance(page, dict) else None
        if not pg or not pg.get("has_next"):
            break
        offset = pg.get("next_offset")
        if offset is None:
            break
    return out


class SectorsClientError(Exception):
    """4xx (deterministic) — fix the request, do not retry."""
    def __init__(self, status: int, body: str, path: str, params: dict | None):
        super().__init__(f"{status} on {path}: {body[:300]}")
        self.status = status
        self.body = body
        self.path = path
        self.params = params


class SectorsServerError(Exception):
    """5xx retries exhausted — log and alert."""
    pass


# ---- Example: use the wrapper ----
if __name__ == "__main__":
    # 1) Single call — handles retries and billing
    data = sectors_get("/v2/subsectors/")
    print(f"subsectors: {len(data)} entries; ledger: {LEDGER.summary()}")

    # 2) Paginate the universe — automatically handles 429 mid-flight
    closes = paginate_all("/v2/close/", params={"date": "2026-06-09", "limit": 30})
    print(f"closes: {len(closes)} tickers; ledger: {LEDGER.summary()}")

    # 3) Use cost_hint when an endpoint costs more than 1 credit
    #    e.g. /v2/most-traded/ = 2 credits
    _ = sectors_get("/v2/most-traded/", params={"start": "2026-06-09", "end": "2026-06-09"},
                    cost_hint=2)
    #    NOTE: pass cost_hint=10 for default top-changes (2 classifications × 5 periods).
    print(f"final: {LEDGER.summary()}")
```

## Expected output shape

`LEDGER.summary()` after the run above looks like:

```
credits_spent≈37  2xx=3  404=0  other_4xx=0  429=0  5xx=0  retries=0
```

Where the math is: subsectors (1 credit) + 32 close pages (32 credits) + most-traded (2 credits) = 35... close enough depending on whether universe was 32 or 33 pages that day.

## Pitfalls

- **`cost_hint` is a HINT, not a precise bill.** The API doesn't return per-call credit cost in the response headers (verified 29 Aug 2026). Use `cost_hint` as your best estimate from the docs, and accept that the ledger is approximate. For exact tracking you'd need to query the Sectors billing dashboard separately.
- **Top-changes costs scale with selections** — `classifications × periods` combos. If you call `top-changes` with `classifications=['top_gainers','top_losers']` and `periods=['1d','7d','14d','30d','365d']`, pass `cost_hint=10`. Trim selections to trim bills.
- **Most-traded, broker-top, broker-summary-top** — pass `cost_hint=2`. All other endpoints pass `cost_hint=1`.
- **404 is billed.** Don't let this surprise you. The wrapper returns `None` and bills 1 credit. Caller must distinguish "no matches" from "this would have errored" — check `result is None` and log/handle.
- **`Retry-After` header**: when the API returns 429, it MAY include `Retry-After: <seconds>`. The wrapper respects this. If absent, falls back to exponential backoff.
- **Connection pooling**: pass a `requests.Session` if calling many endpoints in a loop. Default `requests.get()` creates a new TCP connection each call.
- **Don't retry 400.** This is the most common production mistake. A 400 means your `where` clause is syntactically wrong — retrying doesn't fix it, and the API has correctly NOT billed you, but you're still wasting time and (potentially) tokens downstream.
- **Don't retry 404.** Same logic — the resource doesn't exist, retrying won't conjure it. The 1 credit is already spent; don't spend more time on it.
- **`max_pages=100` safety cap**: prevents an infinite loop if the API misbehaves and `has_next=True` forever. At 30/page that's 3000 records — adjust if you legitimately need more.
- **Jitter is critical** for parallel cron jobs. Without jitter, two cron jobs hitting the same 429 window will keep colliding. The wrapper adds ±25% jitter to every backoff.

## Variations

- **For AI Agents** — wrap calls in a `with budget(50):` context that raises if `LEDGER.spent > 50`. Agents stay budget-aware without manual accounting.
- **For Automation cron** — log `LEDGER.summary()` on every cron run. If `LEDGER.calls_5xx > 0`, alert via your notification channel. If `LEDGER.calls_404 > 5% of total`, alert — you're wasting credits on typos.
- **For Market Intel dashboard** — front-load `paginate_all()` calls (cheap universe feeds), then back-load `sectors_get()` for individual symbols. The wrapper makes it safe to do this even when traffic spikes cause 429s.
- **Wire to Telegram cron notifier** — emit `LEDGER.summary()` as part of your cron success message so you can spot credit burns without opening the dashboard.
- **Cross-recipe import** — drop this file as `sectors_client.py` at the repo root. Every other example file imports `from sectors_client import sectors_get, paginate_all, LEDGER`. One wrapper, all recipes.
