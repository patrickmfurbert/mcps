# websearch MCP Server

Web search and page-fetching for agents, served over HTTP from a self-hosted
[SearXNG](https://docs.searxng.org/) instance on the HP Z420.

Unlike the other servers in this repo, this one is **not** stdio. It runs as a
container on the Z420 and every machine on the mesh connects to it over HTTP, so
there is nothing to install or configure on the machines that use it — including
the Windows worker testbed, which holds no MCP configuration at all.

## Architecture

```
Claude Code (g14, pixel)  ──HTTP──►  websearch-mcp :8092  ──►  SearXNG :8080 ──► internet
                       (mesh, port 8092)        │
                                                └── container network "search-net"
```

MCP is a **client-side** protocol: Claude Code connects to the server and hands the
resulting tools to whatever model is configured. Ollama is not involved — it is
model-serving only and has no MCP client — so the model behind the tools can be
anything that makes tool calls.

SearXNG publishes on `127.0.0.1:8091` on the Z420 only, and is reached by container
name. It is never exposed to the mesh; only the MCP's port 8092 is.

## Tools

- **web_search** — SearXNG search with `categories`, `time_range` (`day`/`week`/
  `month`/`year`), `language`, and paging. Returns numbered title / URL / snippet.
- **fetch_url** — fetch one page, reduce markup to text, truncate. Use this instead
  of the built-in `WebFetch` for large pages (see below).
- **check_health** — verify SearXNG is reachable *and* has JSON output enabled.

## Why results are truncated

A small worker model given a 100 KB result blob will keep generating until it hits
its output-token ceiling, and then return nothing at all. A 113 KB GitHub API
response reliably produced this on a `qwen3.5:4b` worker: the built-in `WebFetch`
failed with *"response exceeded the 32000 output token maximum"* and returned
nothing. `fetch_url` bounds the payload at the source instead of hoping the caller
summarizes politely:

| Variable | Default | Purpose |
|---|---|---|
| `WEBSEARCH_MAX_RESULTS` | `8` | Default result count (hard max 20) |
| `WEBSEARCH_MAX_SNIPPET_CHARS` | `240` | Per-result snippet cap |
| `WEBSEARCH_MAX_FETCH_CHARS` | `6000` | `fetch_url` text budget (max 60000) |

The same 113 KB page comes back as ~574 characters with `max_chars=500`.

## Configuration

`.env` is local only and gitignored. See `env-example`.

| Variable | Description |
|---|---|
| `SEARXNG_URL` | Base URL of SearXNG. `http://searxng:8080` inside the container network |
| `MCP_HOST` / `MCP_PORT` | Bind address and port (default `0.0.0.0:8092`) |
| `MCP_MOUNT_PATH` | MCP endpoint path, default `/mcp` |
| `ALLOWED_HOSTS` | Comma-separated `Host` values to accept; enables DNS-rebinding protection |
| `SEARXNG_SAFESEARCH` | `0`–`2`, default `1` |
| `WEBSEARCH_DEBUG` | Set `true` for DEBUG logging |

## Deploy (HP Z420, rootless podman)

The Z420's podman is Homebrew-installed and absent from non-interactive SSH PATH,
so the script sets its own PATH prefix; do not remove that line.

```bash
rsync -a --exclude .venv --exclude __pycache__ python/websearch/ \
  pastry@hp-z420-mint-steve:~/websearch-mcp/
ssh -p 22 pastry@hp-z420-mint-steve 'bash ~/websearch-mcp/deploy/deploy-z420.sh'
```

The script creates the `search-net` podman network, generates a SearXNG
`secret_key` on first run (existing `settings.yml` is left untouched), starts both
containers with `--restart=always`, and verifies the JSON API. Auto-start at boot
comes from the existing `podman-restart.service` unit; that path depends on the apt
`uidmap` package staying installed — `apt autoremove` removing `uidmap` takes every
container on this host down.

Re-run the script to redeploy after editing `main.py`. It is idempotent.

## Register with Claude Code

```bash
claude mcp add --transport http websearch http://hp-z420-mint-steve:8092/mcp --scope user
claude mcp list        # should show: websearch: ... (HTTP) - ✔ Connected
```

The same command works on the pixel. Nothing is needed on the Windows box.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `SearXNG refused format=json (HTTP 403)` | `json` missing from `formats:` in `deploy/searxng-settings.yml`. Retrying does not help — it is a config list, not a rate limit. |
| HTTP 421 on every request | `ALLOWED_HOSTS` is set but does not include the address clients actually use. Include the port, e.g. `100.64.0.3:8092`. |
| SearXNG HTTP 429 | `server.limiter` is not `false`. Browser-less clients have no session to fingerprint. |
| SearXNG will not start | `secret_key` placeholder survived into the deployed settings file. |
| `podman: command not found` over SSH | Homebrew PATH prefix missing; not a missing install. |
