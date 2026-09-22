# API Security — Best Practices for Safely Using the Sectors Financial API

> Source: <https://docs.sectors.app/recipes/api-security/01-securing-api-usage>
> Author of original recipe: Gladbert Sogo, Feb 2025
> Adapted 29 Aug 2026 for the Sectors Hackathon build.

## Goal

The Sectors API key is your **credential**. It identifies your team and your Sectors plan. Every request is metered against it. Leaked keys waste your 1,000 hackathon credits and can violate Sectors' terms of service.

This file is a checklist of habits every Sectors integration should follow. It's short on purpose — read it once.

## Why API security matters (skip if you already get it)

- **Protecting proprietary market data** — your Sectors key gives access to curated IDX data that took Supertype years to build.
- **Maintaining trust** — if your key leaks and someone redistributes the data, your team is associated with the breach.
- **Preventing unauthorised usage** — leaked keys get abused. Sectors will rotate or revoke them, and you lose access during the hackathon.

Common threats:

- **Man-in-the-Middle attacks** — using plain HTTP exposes data in transit. Sectors is HTTPS-only, but verify your client doesn't downgrade.
- **Credential exposure** — hardcoding keys in source files, committing them to public repos, pasting them in chat.

## Environment isolation

Use a virtual environment so dependencies are scoped to one project:

```bash
# Python
python -m venv env
source env/bin/activate

# Conda
conda create --name sectors-py python=3.11
conda activate sectors-py
```

Benefits:

- Reproducible dependency versions (`requirements.txt` / `environment.yml`).
- No cross-project contamination.
- Easy to nuke and rebuild if something breaks.

## Dependency management

```bash
pip freeze > requirements.txt
pip install --upgrade <package>
```

For production:

- Pin versions: `streamlit==1.35.0` (the SectorScan recipe is pinned to that exact version).
- Use `pipenv`, `poetry`, or `uv` for lockfiles.
- Audit with `pip-audit` or `safety` periodically.

## Storing secrets safely

The cardinal rule: **never put your Sectors key in source code, never commit it to git, never paste it in chat.**

### Pattern A — `.env` file (Python)

```ini
# .env (NEVER commit this file)
SECTORS_API_KEY=your_actual_api_key_here
```

```python
# In your code
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("SECTORS_API_KEY")
```

`.env` must be in `.gitignore`. Verify:

```bash
git check-ignore .env   # prints the path → ignored
git ls-files .env       # prints nothing → not tracked
```

### Pattern B — Streamlit secrets

`.streamlit/secrets.toml`:

```toml
SECTORS_KEY = "your_actual_api_key_here"
```

Read in code:

```python
api_key = st.secrets["SECTORS_KEY"]
```

`secrets.toml` must be in `.gitignore`. For Streamlit Cloud deploys, paste the same TOML in the dashboard's **Secrets** field.

### Pattern C — n8n credentials

In n8n, store the API key as a **Header Auth credential**, not as a literal URL value. n8n encrypts credentials at rest and never logs them. Configure once:

- `Credentials` → `New` → `Header Auth`
- Header Name: `Authorization`
- Header Value: `<raw key>`
- Save with a meaningful name (e.g. "Sectors API — Hackerlab").

Then in any HTTP Request node, pick that credential from the dropdown — don't paste the key into the URL field.

### Pattern D — Apps Script (Sheets)

`Project Settings` → **Script Properties** → add `SECTORS_API_KEY` = `<key>`. Read in code:

```javascript
const api_key = PropertiesService.getScriptProperties().getProperty('SECTORS_API_KEY');
```

Never put the key in a cell. Anyone with edit access can grab it from a cell.

### Pattern E — Environment variables (system-level)

```bash
export SECTORS_API_KEY="your_key_here"
```

```python
import os
api_key = os.environ["SECTORS_API_KEY"]
```

Use this in production containers (Docker, systemd, Cloudflare Workers secrets). Don't use it for local dev — `.env` is more portable.

## What NEVER to do

- ❌ `api_key = "sk-actual-key-here"` hardcoded in a script you commit.
- ❌ Pasting your key in a chat, a Slack DM, an email, a Notion page.
- ❌ Committing `.env` / `secrets.toml` and pushing to GitHub.
- ❌ Logging `print(f"Using key: {api_key}")` anywhere.
- ❌ Putting the key in a URL query param like `?api_key=...` — Sectors doesn't use this pattern, and URLs get logged everywhere.
- ❌ Sharing a screenshot of your terminal that includes the key.
- ❌ Putting the key in a cell, a row, or a Notion database.

## What to do if your key leaks

1. **Revoke immediately** — go to <https://sectors.app/api>, click the API key, click **Revoke**.
2. **Generate a new key** — same page, click **Create API Key**.
3. **Update your `.env` / `secrets.toml` / credential store** with the new value. Restart anything that cached the old one.
4. **Audit usage logs** if available (Sectors Insider plan has request logs).
5. **Investigate how it leaked** — was it git? A screenshot? A shared laptop?

Treat the leak as compromised even if the leak was "just to my teammate." The teammate's laptop might be compromised, or their accounts might be.

## Network and transport security

- **HTTPS only.** Sectors forces HTTPS, but verify your client doesn't downgrade (some old `requests` setups do).
- **Certificate pinning** is overkill for most hackathon work — skip unless you're shipping to a regulated audience.
- **OAuth 2.0 / OpenID Connect** is supported by Sectors only via the MCP OAuth flow. For REST/MCP server integrations you use the API key directly.

## Monitoring and logging

For a hackathon: log response codes only, not full payloads. Log the endpoint, status, and a UTC timestamp:

```python
import logging, time

logging.basicConfig(level=logging.INFO)

def fetch(url, headers):
    t0 = time.time()
    r  = requests.get(url, headers=headers)
    logging.info(f"{r.status_code} {url} ({time.time()-t0:.2f}s)")
    r.raise_for_status()
    return r.json()
```

This is enough to debug 401/429/500 patterns. **Don't log the request headers** — they contain the API key.

For production (post-hackathon):

- Ship logs to a centralised sink (ELK, Grafana Loki, Datadog).
- Set up alerts on 401 (key revoked), 429 (rate-limited), and 5xx (provider outage).
- Track credit usage — if your team is burning 100 credits/hour and you have 500 left, slow down.

## Dependency supply-chain

- Pin versions. `requests>=2.31` is fine; `requests` (no version) will break your build in 6 months.
- Audit regularly: `pip-audit`, `npm audit`, `cargo audit`.
- Use lockfiles for reproducible installs (uv, Poetry, pipenv, npm ci, cargo lock).

## Pre-deploy checklist

- [ ] `.env` / `secrets.toml` / credentials NOT committed (`git ls-files .env` is empty).
- [ ] API key read from environment / secrets store, never hardcoded.
- [ ] No `print(api_key)` / `console.log(api_key)` anywhere.
- [ ] HTTPS verified (no `http://` URLs to Sectors).
- [ ] Error logs scrub the key (`logger.error(...)` doesn't include the headers).
- [ ] On Streamlit Cloud / n8n Cloud: secrets pasted via the dashboard, not committed.

## Cross-links

- Quickstart that touches every stack: [`../quickstart.md`](../quickstart.md)
- Streamlit pattern: [`sectorscan-part2.md`](sectorscan-part2.md)
- n8n credential pattern: [`n8n-api.md`](n8n-api.md), [`n8n-ai-screener.md`](n8n-ai-screener.md)
- Apps Script pattern: [`sheets.md`](sheets.md)
- REST endpoint reference: [`../rest/idx-screener.md`](../rest/idx-screener.md) (Lane 1)