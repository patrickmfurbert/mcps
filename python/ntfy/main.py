import os
import logging
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any

truststore.inject_into_ssl()
load_dotenv()

# ---------------------------------------------------------------------------
# Environment variables
# Loaded from .env at startup. See env-example for required variables.
# ---------------------------------------------------------------------------
NTFY_SERVER_URL = os.getenv("NTFY_SERVER_URL", "").rstrip("/")
NTFY_DEFAULT_TOPIC = os.getenv("NTFY_DEFAULT_TOPIC", "agent-notifications")

# ntfy priority: 1=min, 2=low, 3=default, 4=high, 5=urgent (bypasses Do-Not-Disturb)
VALID_PRIORITIES = {1, 2, 3, 4, 5}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/ntfy-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting ntfy MCP server")
logger.info(f"NTFY_SERVER_URL: {NTFY_SERVER_URL}")
logger.info(f"NTFY_DEFAULT_TOPIC: {NTFY_DEFAULT_TOPIC}")

mcp = FastMCP("ntfy")


async def publish(
    message: str,
    topic: str,
    title: str = "",
    priority: int = 3,
    tags: str = "",
    click: str = "",
) -> dict[str, Any]:
    """POST a message to an ntfy topic. Topics are auto-created on first publish."""
    url = f"{NTFY_SERVER_URL}/{topic}"
    headers: dict[str, str] = {"Content-Type": "text/plain; charset=utf-8"}
    if title:
        headers["Title"] = title
    if priority in VALID_PRIORITIES:
        headers["Priority"] = str(priority)
    if tags:
        headers["Tags"] = tags
    if click:
        headers["Click"] = click

    logger.debug(f"POST {url} title={title!r} priority={priority} tags={tags!r}")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(url, headers=headers, content=message.encode("utf-8"))
        logger.debug(f"POST {url} status={response.status_code}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def send_notification(
    message: str,
    title: str = "",
    topic: str = "",
    priority: int = 3,
    tags: str = "",
    click: str = "",
) -> str:
    """Send a push notification via ntfy.

    Args:
        message: The notification body (supports emoji and markdown-ish text).
        title: Optional notification title, e.g. "Build failed".
        topic: ntfy topic; defaults to NTFY_DEFAULT_TOPIC from .env.
            Topics auto-create on first publish — no server config needed.
        priority: 1=min, 2=low, 3=default, 4=high, 5=urgent (bypasses Do Not Disturb).
        tags: Comma-separated emoji/tags for the notification icon, e.g. "warning,bell".
        click: Optional URL opened when the notification is tapped.

    Returns:
        The ntfy message JSON (id, time, event) or an error description.
    """
    if not NTFY_SERVER_URL:
        return "ERROR: NTFY_SERVER_URL is not set. Copy env-example to .env and configure it."
    topic = topic or NTFY_DEFAULT_TOPIC
    try:
        result = await publish(message, topic, title=title, priority=priority, tags=tags, click=click)
        return f"Sent to /{topic}: id={result.get('id')} time={result.get('time')}"
    except httpx.HTTPStatusError as e:
        logger.error(f"publish HTTP error: {e.response.status_code} {e.response.text}")
        return f"ERROR: ntfy returned HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        logger.error(f"publish failed: {e}")
        return f"ERROR: could not reach ntfy at {NTFY_SERVER_URL}: {e}"


@mcp.tool()
async def check_health() -> str:
    """Check that the configured ntfy server is reachable and healthy."""
    if not NTFY_SERVER_URL:
        return "ERROR: NTFY_SERVER_URL is not set."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{NTFY_SERVER_URL}/v1/health")
            response.raise_for_status()
            return f"ntfy at {NTFY_SERVER_URL} is healthy: {response.json()}"
    except Exception as e:
        return f"ERROR: ntfy at {NTFY_SERVER_URL} unreachable: {e}"


if __name__ == "__main__":
    mcp.run()
