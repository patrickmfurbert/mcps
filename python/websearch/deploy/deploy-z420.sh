#!/usr/bin/env bash
# Deploy the websearch MCP + SearXNG to the HP Z420 (rootless podman).
#
# Run from a synced copy of python/websearch on the Z420:
#   rsync -a --exclude .venv python/websearch/ pastry@hp-z420-mint-steve:~/websearch-mcp/
#   ssh pastry@hp-z420-mint-steve 'bash ~/websearch-mcp/deploy/deploy-z420.sh'
#
# Podman on this host is Homebrew-installed and invisible to non-interactive SSH
# until its bin dir is on PATH — hence the explicit PATH line below.
set -euo pipefail

export PATH=/home/linuxbrew/.linuxbrew/bin:$PATH

SEARXNG_PORT="${SEARXNG_PORT:-8091}"   # host port, loopback-only
MCP_PORT="${MCP_PORT:-8092}"           # host port, reachable from the mesh
NETWORK=search-net
STATE_DIR="${STATE_DIR:-$HOME/websearch-state}"
SEARXNG_CONFIG="$STATE_DIR/searxng"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== websearch MCP deploy ==================================="
command -v podman >/dev/null || { echo "FATAL: podman not on PATH (missing Homebrew PATH prefix?)"; exit 1; }

# --- network ---------------------------------------------------
# SearXNG is reached by container name, so it never needs a routable host port.
podman network exists "$NETWORK" 2>/dev/null || podman network create "$NETWORK" >/dev/null
echo "network: $NETWORK"

# --- SearXNG ---------------------------------------------------
mkdir -p "$SEARXNG_CONFIG"
# The SearXNG process inside the container runs as an unprivileged uid that is not
# this user's; the bind mount must be writable or it dies at startup writing its
# carousel/cache files.
#
# A previous run leaves this directory owned by that mapped container uid, and only
# root can chown or chmod it — so a re-deploy must not die here when it is already
# world-writable, which is the state the chmod was only ever trying to achieve.
chmod 777 "$SEARXNG_CONFIG" 2>/dev/null \
  || echo "note: left $(stat -c '%a' "$SEARXNG_CONFIG") as-is (owned by uid $(stat -c '%u' "$SEARXNG_CONFIG"), not this user)"

if [ ! -f "$SEARXNG_CONFIG/settings.yml" ]; then
  secret="$(openssl rand -hex 32)"
  sed "s/REPLACED_AT_DEPLOY/$secret/" "$SRC_DIR/deploy/searxng-settings.yml" \
    > "$SEARXNG_CONFIG/settings.yml"
  chmod 644 "$SEARXNG_CONFIG/settings.yml"
  echo "wrote $SEARXNG_CONFIG/settings.yml (generated secret_key)"
else
  echo "settings.yml already present; leaving it untouched"
fi

podman rm -f searxng >/dev/null 2>&1 || true
podman run -d --name searxng \
  --network "$NETWORK" \
  --restart=always \
  -p "127.0.0.1:${SEARXNG_PORT}:8080" \
  -v "$SEARXNG_CONFIG:/etc/searxng:rw" \
  docker.io/searxng/searxng:latest >/dev/null
echo "searxng: started (host loopback :$SEARXNG_PORT)"

echo "waiting for SearXNG to accept JSON queries..."
json_status=000
for _ in $(seq 1 30); do
  # A 403 here means SearXNG is up but json is not in settings.yml `formats:`,
  # so it is captured rather than retried away — retrying cannot fix that.
  json_status="$(curl -s -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${SEARXNG_PORT}/search?q=ping&format=json" || echo 000)"
  if [ "$json_status" = "200" ]; then break; fi
  if [ "$json_status" = "403" ]; then break; fi
  sleep 2
done
case "$json_status" in
  200) echo "SearXNG JSON API: OK" ;;
  403) echo "WARN: SearXNG is up but refuses format=json — add 'json' to settings.yml formats:" ;;
  *)   echo "WARN: SearXNG JSON query returned HTTP $json_status; check: podman logs searxng" ;;
esac

# --- websearch MCP ---------------------------------------------
podman rm -f websearch-mcp >/dev/null 2>&1 || true
podman build -t websearch-mcp -f "$SRC_DIR/Containerfile" "$SRC_DIR" >/dev/null
echo "image: built websearch-mcp"

podman rm -f websearch-mcp >/dev/null 2>&1 || true
podman run -d --name websearch-mcp \
  --network "$NETWORK" \
  --restart=always \
  -p "${MCP_PORT}:8092" \
  -e SEARXNG_URL="http://searxng:8080" \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8092 \
  -e MCP_MOUNT_PATH=/mcp \
  websearch-mcp >/dev/null
echo "websearch-mcp: started (:$MCP_PORT/mcp)"

echo "done."
