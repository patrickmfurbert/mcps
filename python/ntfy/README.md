# ntfy MCP Server

MCP server for sending push notifications through a self-hosted
[ntfy](https://docs.ntfy.sh) instance (e.g. the HP Z420 on the Tailscale mesh).

## Setup

```bash
cd python/ntfy
cp env-example .env   # edit .env — this file is gitignored, never committed
uv sync
```

## Configuration (`.env`, local only)

| Variable | Description |
|---|---|
| `NTFY_SERVER_URL` | Base URL of the ntfy server, e.g. `http://100.64.0.3:8090` |
| `NTFY_DEFAULT_TOPIC` | Topic used when none is given, e.g. `agent-notifications` |

## Tools

- **send_notification** — publish a message to a topic (auto-created on first
  publish). Optional `title`, `priority` (1–5, where 5 = urgent / bypasses DND),
  `tags`, and `click` URL.
- **check_health** — verify the ntfy server is reachable and healthy.

## Encoding

Every field accepts non-ASCII — em dashes, accents, emoji. HTTP/1.1 header
values are 7-bit and httpx encodes a `str` value with ASCII, so `title`, `tags`
and `click` go out as [RFC 2047](https://datatracker.ietf.org/doc/html/rfc2047)
encoded words (`=?UTF-8?B?...?=`), which ntfy decodes on receipt
([docs](https://docs.ntfy.sh/publish/)). ASCII values are left as they are. Tags
are encoded one element at a time so a list stays a list.

Header values are also cleaned: control characters are removed so a value cannot
split the request or inject a second header, and the edges are trimmed, since a
header value may not begin or end with whitespace.

## Register with Claude Code

```bash
claude mcp add-json ntfy '{
  "command": "<repo>/python/ntfy/.venv/bin/python",
  "args": ["<repo>/python/ntfy/main.py"]
}' --scope user
```
