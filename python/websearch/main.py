import os
import html
import html.parser
import logging
import sys
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from typing import Any

truststore.inject_into_ssl()
load_dotenv()

# ---------------------------------------------------------------------------
# Environment variables
# Loaded from .env at startup. See env-example for required variables.
# This server speaks streamable-http and runs on the Z420, so clients dial a URL;
# there is no per-host command line to configure and nothing to install on the
# machine that uses it.
# ---------------------------------------------------------------------------
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://127.0.0.1:8091").rstrip("/")
SEARXNG_TIMEOUT_S = float(os.getenv("SEARXNG_TIMEOUT_S", "20"))
SEARXNG_SAFESEARCH = int(os.getenv("SEARXNG_SAFESEARCH", "1"))

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8092"))
MCP_MOUNT_PATH = os.getenv("MCP_MOUNT_PATH", "/mcp")

# Comma-separated Host values to accept, e.g. "hp-z420-mint-steve:8092,100.64.0.3:8092".
# Setting this turns the SDK's DNS-rebinding protection ON. Leaving it unset keeps the
# SDK default: protection for localhost binds, none for a 0.0.0.0 bind. Enabling it
# without listing the address clients actually use rejects every request with 421.
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "").split(",") if h.strip()]

# Output-size caps. A small worker handed a 100 KB result keeps generating until it
# hits its output-token ceiling and returns nothing at all, so responses are bounded
# here rather than trusting the caller to summarize politely.
MAX_RESULTS = int(os.getenv("WEBSEARCH_MAX_RESULTS", "8"))
MAX_SNIPPET_CHARS = int(os.getenv("WEBSEARCH_MAX_SNIPPET_CHARS", "240"))
MAX_FETCH_CHARS = int(os.getenv("WEBSEARCH_MAX_FETCH_CHARS", "6000"))

# Containers want logs on stdout; WEBSEARCH_LOG_FILE adds a file sink.
LOG_FILE = os.getenv("WEBSEARCH_LOG_FILE", "")

logging.basicConfig(
    level=logging.DEBUG if os.getenv("WEBSEARCH_DEBUG") == "true" else logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
    + ([logging.FileHandler(LOG_FILE)] if LOG_FILE else []),
)
logger = logging.getLogger(__name__)

logger.info("Starting websearch MCP server")
logger.info(f"SEARXNG_URL: {SEARXNG_URL}")
logger.info(f"Listening on {MCP_HOST}:{MCP_PORT}{MCP_MOUNT_PATH}")

# The SDK auto-enables rebinding protection only for localhost binds, so an
# unconditional default here would either do nothing or lock out the whole mesh.
transport_security: TransportSecuritySettings | None = None
if ALLOWED_HOSTS:
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=ALLOWED_HOSTS,
        allowed_origins=[f"http://{h}" for h in ALLOWED_HOSTS],
    )
    logger.info(f"DNS-rebinding protection ON; allowed hosts: {ALLOWED_HOSTS}")

mcp = FastMCP(
    "websearch",
    host=MCP_HOST,
    port=MCP_PORT,
    mount_path=MCP_MOUNT_PATH,
    transport_security=transport_security,
)


# ---------------------------------------------------------------------------
# HTML -> text
# Minimal on purpose: no HTML-parser dependency, script/style dropped entirely,
# entities unescaped. Line structure is preserved so code blocks and lists survive.
# ---------------------------------------------------------------------------
class _TextExtractor(html.parser.HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}
    BREAKS = {"p", "br", "li", "tr", "h1", "h2", "h3", "h4", "div", "pre"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BREAKS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(raw: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(raw)
    except Exception:  # noqa: BLE001 - malformed markup still yields partial text
        pass
    return parser.text()


def compact(text: str, limit: int, keep_newlines: bool = False) -> str:
    """Collapse runs of whitespace and hard-cap the result.

    keep_newlines retains paragraph structure (fetch_url); flattening to single
    spaces suits one-line fields such as search snippets.
    """
    if not text:
        return ""
    if keep_newlines:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        collapsed = "\n".join(line for line in lines if line)
    else:
        collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rstrip() + "…"


# ---------------------------------------------------------------------------
# SearXNG client
# ---------------------------------------------------------------------------
async def searxng_search(
    query: str,
    categories: str,
    language: str,
    time_range: str,
    page: int,
) -> dict[str, Any]:
    """Query SearXNG's JSON API. Requires 'json' in settings.yml `formats:`."""
    params: dict[str, Any] = {
        "q": query,
        "format": "json",
        "categories": categories or "general",
        "language": language or "all",
        "pageno": max(page, 1),
        "safesearch": SEARXNG_SAFESEARCH,
    }
    if time_range:
        params["time_range"] = time_range

    url = f"{SEARXNG_URL}/search"
    logger.debug(f"GET {url} q={query!r} categories={params['categories']}")
    async with httpx.AsyncClient(timeout=SEARXNG_TIMEOUT_S) as client:
        response = await client.get(url, params=params)
        if response.status_code == 403:
            # SearXNG answers HTML-only unless json is whitelisted; the raw 403
            # would otherwise look like an unexplained permission failure.
            raise RuntimeError(
                "SearXNG refused format=json (HTTP 403). Add 'json' to the `formats:` "
                "list in SearXNG's settings.yml and restart it."
            )
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def web_search(
    query: str,
    max_results: int = 0,
    categories: str = "",
    time_range: str = "",
    language: str = "",
    page: int = 1,
) -> str:
    """Search the web via a self-hosted SearXNG instance and return ranked results.

    Args:
        query: The search query, in plain words.
        max_results: Results to return (default 8, maximum 20). Output is size-capped,
            so a focused query beats a large max_results.
        categories: Comma-separated SearXNG categories: general, news, images, it,
            science, videos. Empty means "general".
        time_range: Restrict to recent results: "day", "week", "month", or "year".
        language: Two-letter language code such as "en". Empty means all languages.
        page: Result page, 1-based. Prefer refining the query over deep paging.

    Returns:
        Numbered results as "title / url / snippet", or a short message if none matched.
    """
    if not SEARXNG_URL:
        return "ERROR: SEARXNG_URL is not set. Copy env-example to .env and configure it."
    limit = min(max_results or MAX_RESULTS, 20)
    try:
        data = await searxng_search(query, categories, language, time_range, page)
    except httpx.RequestError as e:
        logger.error(f"search request failed: {e}")
        return f"ERROR: could not reach SearXNG at {SEARXNG_URL}: {e}"
    except Exception as e:  # noqa: BLE001 - tool errors return text, never raise
        logger.error(f"search failed: {type(e).__name__}: {e}")
        return f"ERROR: {type(e).__name__}: {e}"

    results = data.get("results", [])[:limit]
    if not results:
        answers = data.get("answers") or []
        if answers:
            return f"SearXNG answer: {compact(str(answers[0]), MAX_SNIPPET_CHARS)}"
        return f"No results for {query!r}."

    blocks = []
    for i, result in enumerate(results, 1):
        title = compact(result.get("title"), 200) or "(no title)"
        snippet = compact(result.get("content"), MAX_SNIPPET_CHARS) or "(no snippet)"
        blocks.append(f"{i}. {title}\n   {result.get('url', '')}\n   {snippet}")
    logger.info(f"web_search {query!r} -> {len(results)} results")
    return "\n".join(blocks)


@mcp.tool()
async def fetch_url(url: str, max_chars: int = 0) -> str:
    """Fetch one web page and return its readable text, truncated to a safe size.

    Prefer this over the built-in WebFetch for large pages: markup is reduced to text
    and truncated server-side, so a big page cannot overrun the caller's output budget.

    Args:
        url: Absolute http(s) URL to fetch.
        max_chars: Character budget for the returned text (default 6000, maximum 60000).

    Returns:
        The status line followed by the page text, or a one-line error.
    """
    if not url.lower().startswith(("http://", "https://")):
        return "ERROR: url must start with http:// or https://"
    limit = min(max_chars or MAX_FETCH_CHARS, 60000)
    headers = {"User-Agent": os.getenv("WEBSEARCH_USER_AGENT", "websearch-mcp/1.0")}
    try:
        async with httpx.AsyncClient(
            timeout=SEARXNG_TIMEOUT_S, follow_redirects=True, max_redirects=6
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError as e:
        logger.error(f"fetch_url {url} failed: {e}")
        return f"ERROR: could not fetch {url}: {e}"

    content_type = response.headers.get("content-type", "")
    body = response.text
    # Keep JSON and plain text verbatim; strip markup from everything else.
    if "html" in content_type:
        body = html_to_text(body)
    text = compact(body, limit, keep_newlines=True)
    logger.info(f"fetch_url {url} -> HTTP {response.status_code} {len(body)} chars")
    if not text:
        return f"HTTP {response.status_code} from {url}: no readable text (content-type {content_type or 'unknown'})"
    return f"HTTP {response.status_code} {url}\n\n{text}"


@mcp.tool()
async def check_health() -> str:
    """Check that the SearXNG backend is reachable and configured for JSON output."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{SEARXNG_URL}/search", params={"q": "ping", "format": "json"}
            )
            if response.status_code == 403:
                return (
                    "SearXNG is reachable but rejects format=json (HTTP 403). Add 'json' "
                    "to the `formats:` list in settings.yml and restart SearXNG."
                )
            response.raise_for_status()
            return f"SearXNG at {SEARXNG_URL} is healthy (HTTP {response.status_code})"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: SearXNG at {SEARXNG_URL} unreachable: {e}"


if __name__ == "__main__":
    logger.info("MCP server starting, transport=streamable-http")
    mcp.run(transport="streamable-http")
