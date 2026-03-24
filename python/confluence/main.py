import os
import logging
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any

truststore.inject_into_ssl()
load_dotenv()

CONFLUENCE_URL = os.getenv("CONFLUENCE_URL", "").rstrip("/")
CONFLUENCE_TOKEN = os.getenv("CONFLUENCE_TOKEN", "")
API_BASE = f"{CONFLUENCE_URL}/rest/api"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/confluence-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting Confluence MCP server")
logger.info(f"CONFLUENCE_URL: {CONFLUENCE_URL}")
logger.info(f"CONFLUENCE_TOKEN set: {'yes' if CONFLUENCE_TOKEN else 'no'}")

mcp = FastMCP("confluence")


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {CONFLUENCE_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get(path: str, params: dict = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"GET {url} params={params}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=get_headers(),
                params=params,
            )
            logger.debug(f"GET {url} status={response.status_code}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"GET {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"GET {url} error: {e}")
        raise


async def post(path: str, body: Any = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"POST {url} body={body}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=get_headers(),
                json=body,
            )
            logger.debug(f"POST {url} status={response.status_code}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"POST {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"POST {url} error: {e}")
        raise


async def put(path: str, body: dict = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"PUT {url} body={body}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers=get_headers(),
                json=body,
            )
            logger.debug(f"PUT {url} status={response.status_code}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"PUT {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"PUT {url} error: {e}")
        raise


# --- Spaces ---

@mcp.tool()
async def list_spaces(space_type: str = "") -> dict:
    """List all Confluence spaces, optionally filtered by type.

    Args:
        space_type: Optional filter — 'global' or 'personal'. Leave empty for all spaces.
    """
    logger.info(f"list_spaces space_type={space_type}")
    params: dict[str, Any] = {"limit": 50}
    if space_type:
        params["type"] = space_type
    return await get("/space", params)


@mcp.tool()
async def get_space(space_key: str) -> dict:
    """Get details of a Confluence space by its key.

    Args:
        space_key: The space key (e.g. 'MYPROJ')
    """
    logger.info(f"get_space space_key={space_key}")
    return await get(f"/space/{space_key}")


# --- Pages ---

@mcp.tool()
async def get_page(page_id: str, expand: str = "body.storage") -> dict:
    """Get a Confluence page by ID.

    Args:
        page_id: The page ID
        expand: Fields to expand — use 'body.storage' for raw storage XML or 'body.view' for rendered HTML (default: body.storage)
    """
    logger.info(f"get_page page_id={page_id}")
    return await get(f"/content/{page_id}", {"expand": expand})


@mcp.tool()
async def get_page_by_title(space_key: str, title: str) -> dict:
    """Find a Confluence page by space key and exact title.

    Args:
        space_key: The space key (e.g. 'MYPROJ')
        title: The exact page title
    """
    logger.info(f"get_page_by_title space_key={space_key} title={title}")
    return await get("/content", {
        "spaceKey": space_key,
        "title": title,
        "expand": "body.storage",
    })


@mcp.tool()
async def get_space_pages(space_key: str, limit: int = 25) -> dict:
    """List pages in a Confluence space with pagination.

    Args:
        space_key: The space key (e.g. 'MYPROJ')
        limit: Number of pages to return (default: 25)
    """
    logger.info(f"get_space_pages space_key={space_key}")
    return await get("/content", {
        "spaceKey": space_key,
        "type": "page",
        "limit": limit,
    })


@mcp.tool()
async def get_page_children(page_id: str) -> dict:
    """Get direct child pages of a Confluence page.

    Args:
        page_id: The parent page ID
    """
    logger.info(f"get_page_children page_id={page_id}")
    return await get(f"/content/{page_id}/child/page")


@mcp.tool()
async def get_page_ancestors(page_id: str) -> dict:
    """Get the breadcrumb path from a page to the root.

    Args:
        page_id: The page ID
    """
    logger.info(f"get_page_ancestors page_id={page_id}")
    return await get(f"/content/{page_id}", {"expand": "ancestors"})


@mcp.tool()
async def create_page(space_key: str, title: str, body: str, parent_id: str = "") -> dict:
    """Create a new Confluence page.

    Args:
        space_key: The space key to create the page in (e.g. 'MYPROJ')
        title: The page title
        body: The page body in Confluence storage XML format
        parent_id: Optional parent page ID to nest under
    """
    logger.info(f"create_page space_key={space_key} title={title}")
    payload: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {
            "storage": {
                "value": body,
                "representation": "storage",
            }
        },
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]
    return await post("/content", payload)


@mcp.tool()
async def update_page(page_id: str, title: str, body: str) -> dict:
    """Update a Confluence page body and title. Version is auto-incremented.

    Args:
        page_id: The page ID to update
        title: The new page title
        body: The new page body in Confluence storage XML format
    """
    logger.info(f"update_page page_id={page_id} title={title}")
    current = await get(f"/content/{page_id}", {"expand": "version"})
    current_version = int(current["version"]["number"])
    return await put(f"/content/{page_id}", {
        "type": "page",
        "title": title,
        "version": {"number": current_version + 1},
        "body": {
            "storage": {
                "value": body,
                "representation": "storage",
            }
        },
    })


# --- Comments ---

@mcp.tool()
async def get_page_comments(page_id: str) -> dict:
    """Get all comments on a Confluence page.

    Args:
        page_id: The page ID
    """
    logger.info(f"get_page_comments page_id={page_id}")
    return await get(f"/content/{page_id}/child/comment", {
        "expand": "body.view",
        "limit": 50,
    })


@mcp.tool()
async def add_page_comment(page_id: str, text: str) -> dict:
    """Add a comment to a Confluence page.

    Args:
        page_id: The page ID to comment on
        text: The comment text in plain text — will be wrapped in Confluence storage XML automatically
    """
    logger.info(f"add_page_comment page_id={page_id}")
    return await post("/content", {
        "type": "comment",
        "container": {"id": page_id, "type": "page"},
        "body": {
            "storage": {
                "value": f"<p>{text}</p>",
                "representation": "storage",
            }
        },
    })


# --- Labels ---

@mcp.tool()
async def get_page_labels(page_id: str) -> dict:
    """Get labels on a Confluence page.

    Args:
        page_id: The page ID
    """
    logger.info(f"get_page_labels page_id={page_id}")
    return await get(f"/content/{page_id}/label")


@mcp.tool()
async def add_page_label(page_id: str, label: str) -> dict:
    """Add a label to a Confluence page.

    Args:
        page_id: The page ID
        label: The label name to add (e.g. 'needs-review')
    """
    logger.info(f"add_page_label page_id={page_id} label={label}")
    return await post(f"/content/{page_id}/label", [{"name": label}])


# --- Attachments ---

@mcp.tool()
async def get_page_attachments(page_id: str) -> dict:
    """List attachments on a Confluence page.

    Args:
        page_id: The page ID
    """
    logger.info(f"get_page_attachments page_id={page_id}")
    return await get(f"/content/{page_id}/child/attachment")


# --- Search ---

@mcp.tool()
async def search(cql: str, limit: int = 25) -> dict:
    """Search Confluence using CQL (Confluence Query Language).

    Args:
        cql: CQL query string (e.g. 'space=MYPROJ AND type=page AND text~"deployment"')
        limit: Number of results to return (default: 25)
    """
    logger.info(f"search cql={cql}")
    return await get("/content/search", {"cql": cql, "limit": limit})


# --- Users ---

@mcp.tool()
async def get_user(username: str) -> dict:
    """Look up a Confluence user by username.

    Args:
        username: The Confluence username
    """
    logger.info(f"get_user username={username}")
    return await get("/user", {"username": username})


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
