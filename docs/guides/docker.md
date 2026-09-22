# Docker

Two images, one origin. `web` serves the built front-end with nginx and proxies `/api` to `api`, so the browser
never makes a cross-origin request and the same image works behind any hostname.

```bash
cp .env.example .env      # fill in the keys (the file is gitignored)
make build                # first build is the slow one
make up                   # http://127.0.0.1:8080
make pdf TICKER=AMMN      # render the deck inside the container
```

## What each image is

| Image | Base | Why that base |
|---|---|---|
| `api` | `mcr.microsoft.com/playwright/python:v1.60.0-noble` | the deck is rendered by Chromium, so the image ships the browser build that matches the library. Nothing is downloaded at build time and the two cannot drift, because the tag is pinned to the `playwright` version in `server/requirements.txt`. |
| `web` | `node:22-alpine` build, `nginx:1.27-alpine` runtime | the front-end is static after `vite build`; the runtime image only has to serve files and proxy. |

The Playwright base carries three browsers (~3.4 GB). The app launches chromium only, so `api.Dockerfile` removes
firefox and webkit - about a gigabyte off the image, and nothing can reach for them.

## Caching, which is the part that matters day to day

Rebuild cost is decided by layer order, not by the tool:

- **Manifests before source.** Both Dockerfiles copy `requirements.txt` / `package-lock.json` first and install, then
  copy the code. Editing a component reuses the dependency layer.
- **Cache mounts.** pip (`/root/.cache/pip`) and npm (`/root/.npm`) are mounted as BuildKit caches, so even a
  manifest change keeps the wheels and tarballs instead of re-downloading them.
- **Build context.** `.dockerignore` drops `.venv`, `node_modules`, `.git` and `output` from the context - without it
  every build uploads ~1.8 GB before doing any work.
- The browser prune sits above the source copy, so it stays cached across code changes.

Practical result: a source edit rebuilds in seconds; a dependency edit rebuilds in the time it takes to install.

## Keys

Provider keys live in `~/.config/sectors-be/env` (outside the repository, never copied into an image). Compose loads
that file directly as a second `env_file`, so the container and the host read the SAME secrets and cannot drift:

```yaml
    env_file:
      - path: .env                               # dev-only extras
        required: false
      - path: /home/fadil/.config/sectors-be/env # the file the retired systemd unit used
        required: true                           # missing file = compose refuses to start, loudly
```

Hand-copying keys into `.env` is what let the container run for two days without `SECTORS_API_KEY` (caught during the
15 Sep 2026 cutover) - one source of truth, or the two silently diverge.

Check what the container actually received without printing values:

```bash
docker compose exec api python -c "import os; print({k: bool(os.environ.get(k)) for k in \
  ('SECTORS_API_KEY','ADK_PROVIDER','SPARK13_MAX_TOKENS','MINIMAX_API_KEY')})"
```

Without `SECTORS_API_KEY` the report endpoints still answer, but any path that needs fresh market data fails loudly
instead of guessing - which is the intended behaviour, not a bug to work around.

## Ports

The container owns `8777` - the port the Cloudflare tunnel already targets, so the cutover needed no dashboard change.
`sectors-be.service` was the previous owner; it was stopped and disabled on 15 Sep 2026. Two listeners on one port is
a silent "which one answered?" bug, and two writers on one SQLite file (`data/agent_runs.db`) is worse, so the two
runtimes never coexist. `web` still publishes 8080 for local browsing.

## State

`data/` and `output/` are bind-mounted from the host, deliberately:

- `data/assumptions/*.json` stays editable without rebuilding the image, and a rebuilt image keeps using it;
- `output/cache/` (the harvest cache) survives a container rebuild, which is the difference between a fast start and
  a long one.

Everything else - the app, the fonts, the browser - lives in the image and is immutable at runtime.

## Development

```bash
docker compose --profile dev up api-dev   # source bind-mounted, uvicorn --reload on 18778
```

The dev service uses the same image as production, so the thing you develop against is the thing that ships; only the
mount and the reload flag differ.

## Known edges

- `agents/adk/providers/__init__.py` and `agents/adk/app.py` read `/home/fadil/.env` by absolute path. That is the
  agent path only (the report and PDF path never touches it), and inside a container the file does not exist, so the
  ADK provider keys come from the environment - `SECTORS_API_KEY`, `MINIMAX_API_KEY` and `SPARK13_MAX_TOKENS` all
  arrive through the compose `env_file` pair above.
- The app also tries `~/.config/sectors-be/env` at startup. Environment variables win; in the container the compose
  `env_file` is the source of truth, and it points at that very file.
- `WITH_ADK=false make build-slim` produces a report-only image: no Google ADK stack, smaller and faster, and the
  `/agent` routes stop working. The report, valuation, PDF and test paths do not need it.

## Production

This stack **is** production since the 15 Sep 2026 cutover: `report.server-fadil.my.id` → cloudflared → `127.0.0.1:8777`
→ this container. Deploy is:

```bash
make build && make up      # rebuild the api image, recreate the container
make ps && curl -s localhost:8777/api/agent/health   # verify
```

Pitfalls worth remembering, both of which cost real debugging time:

- **A running container is not proof of current code.** `docker images --format '{{.CreatedSince}}' | grep sectors-api`
  tells you when the image was built; if it is older than the last commit, `make build` before believing any fix is
  live. The same trap killed a systemd deploy: the unit served pre-fix code for hours because nobody restarted it.
- **Never run the container and the host unit together.** Both bind-mount `./data`, so they share
  `data/agent_runs.db` - the Sectors credit cache and the run history. Two writers on one SQLite file is how you lose
  paid cache rows. `sectors-be.service` is disabled; leave it that way.
