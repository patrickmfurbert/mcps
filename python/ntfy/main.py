import os
import base64
import logging
import re
import tempfile
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

# Log file; defaults to the temp dir so hosts without a writable /tmp (Termux)
# work as-is. Override with NTFY_LOG_FILE.
LOG_FILE = os.getenv("NTFY_LOG_FILE") or os.path.join(
    tempfile.gettempdir(), "ntfy-mcp.log"
)

# ntfy priority: 1=min, 2=low, 3=default, 4=high, 5=urgent (bypasses Do-Not-Disturb)
VALID_PRIORITIES = {1, 2, 3, 4, 5}

# Deleted from header values: C0 controls except tab, plus DEL.
# See clean_header_value().
_CONTROL_CHARS = {c: None for c in (*range(0x00, 0x09), *range(0x0A, 0x20), 0x7F)}

# HTTP headers are 7-bit: httpx refuses any header value outside ASCII, so a title
# like "build — done" raises UnicodeEncodeError before a request is ever sent. ntfy
# decodes RFC 2047 encoded words, so non-ASCII is sent that way instead:
# =?UTF-8?B?<base64>?=  (see https://docs.ntfy.sh/publish/). Pure-ASCII values are
# left alone, so ordinary notifications stay readable on the wire.
_RFC2047 = re.compile(r"=\?[-A-Za-z0-9_]+\?[BbQq]\?[A-Za-z0-9+/=]*\?=")


def clean_header_value(value: str) -> str:
    """Strip what a header value may not carry.

    Control characters go because one would split the request or inject a second
    header; h11 rejects them outright, so the notification was lost and reported
    as a server outage. The edges go because a header value may not begin or end
    with whitespace, and every server trims it regardless.
    """
    return value.translate(_CONTROL_CHARS).strip()


def encode_header_value(value: str) -> str:
    """RFC 2047-encode a header value, unless it is ASCII or already encoded."""
    cleaned = clean_header_value(value)
    if cleaned.isascii() or _RFC2047.fullmatch(cleaned):
        return cleaned
    # errors="replace" only bites on lone surrogates, which cannot be encoded;
    # without it a surrogate in a model-emitted title raised UnicodeEncodeError
    # here, exactly the failure this function exists to prevent.
    encoded = base64.b64encode(cleaned.encode("utf-8", errors="replace")).decode("ascii")
    return f"=?UTF-8?B?{encoded}?="


def encode_tags(tags: str) -> str:
    """Encode tags one at a time; ntfy decodes each comma-separated element itself,
    so encoding the whole list as a single word would collapse them into one tag.

    Every element goes through encode_header_value, including the all-ASCII ones,
    because that is also what cleans them.
    """
    return ",".join(encode_header_value(tag) for tag in tags.split(","))


logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        # Explicit UTF-8: under a C/POSIX locale the default encoding is ASCII,
        # which would raise UnicodeEncodeError on a non-ASCII title logged below.
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
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
        headers["Title"] = encode_header_value(title)
    if priority in VALID_PRIORITIES:
        headers["Priority"] = str(priority)
    if tags:
        headers["Tags"] = encode_tags(tags)
    if click:
        headers["Click"] = encode_header_value(click)

    logger.debug(f"POST {url} title={title!r} priority={priority} tags={tags!r}")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            url, headers=headers, content=message.encode("utf-8", errors="replace")
        )
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
    except httpx.ProtocolError as e:
        # h11 rejected the request we built, or ntfy answered with junk: the server
        # is reachable and not at fault. ProtocolError is a subclass of RequestError,
        # so this must stay ahead of the branch below, which means "unreachable".
        logger.error(f"publish protocol error: {type(e).__name__}: {e}")
        return f"ERROR: ntfy request failed protocol validation: {e}"
    except httpx.RequestError as e:
        logger.error(f"publish request failed: {e}")
        return f"ERROR: could not reach ntfy at {NTFY_SERVER_URL}: {e}"
    except Exception as e:
        # Anything else is a bug in this file, not in ntfy — "could not reach
        # ntfy" above stays reserved for requests that never got an answer.
        logger.error(f"publish failed: {type(e).__name__}: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


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
