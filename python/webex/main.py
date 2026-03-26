import os
import asyncio
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
WEBEX_TOKEN = os.getenv("WEBEX_TOKEN", "")
WEBEX_ROOM_ID = os.getenv("WEBEX_ROOM_ID", "")

# ---------------------------------------------------------------------------
# API base URL — Webex is always cloud hosted, no instance URL needed
# ---------------------------------------------------------------------------
API_BASE = "https://webexapis.com/v1"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/webex-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting webex MCP server")
logger.info(f"WEBEX_TOKEN set: {'yes' if WEBEX_TOKEN else 'no'}")
logger.info(f"WEBEX_ROOM_ID: {WEBEX_ROOM_ID}")

mcp = FastMCP("webex")


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {WEBEX_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get(path: str, params: dict[str, Any] = {}) -> dict:
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


async def delete(path: str) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"DELETE {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                url,
                headers=get_headers(),
            )
            logger.debug(f"DELETE {url} status={response.status_code}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"DELETE {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"DELETE {url} error: {e}")
        raise


# --- Bot identity ---

@mcp.tool()
async def get_me() -> dict:
    """Get the bot's own details including display name and email."""
    logger.info("get_me called")
    return await get("/people/me")


# --- Rooms ---

@mcp.tool()
async def list_rooms(room_type: str = "") -> dict:
    """List Webex rooms the bot is a member of.

    Args:
        room_type: Optional filter — 'direct' for DMs or 'group' for group spaces. Leave empty for all.
    """
    logger.info(f"list_rooms room_type={room_type}")
    params: dict[str, Any] = {"max": 50}
    if room_type:
        params["type"] = room_type
    return await get("/rooms", params)


@mcp.tool()
async def get_room(room_id: str) -> dict:
    """Get details of a specific Webex room.

    Args:
        room_id: The room ID
    """
    logger.info(f"get_room room_id={room_id}")
    return await get(f"/rooms/{room_id}")


# --- Messages ---

@mcp.tool()
async def get_messages(room_id: str = "", max_messages: int = 10) -> dict:
    """Get recent messages from a Webex room. Defaults to the configured direct message room.

    Args:
        room_id: The room ID to fetch messages from. Defaults to WEBEX_ROOM_ID from .env if not provided.
        max_messages: Maximum number of messages to return (default: 10)
    """
    target_room = room_id or WEBEX_ROOM_ID
    logger.info(f"get_messages room_id={target_room}")
    return await get("/messages", {
        "roomId": target_room,
        "max": max_messages,
    })


@mcp.tool()
async def send_message(text: str, room_id: str = "") -> dict:
    """Send a message to a Webex room. Defaults to the configured direct message room.

    Args:
        text: The message text to send
        room_id: The room ID to send the message to. Defaults to WEBEX_ROOM_ID from .env if not provided.
    """
    target_room = room_id or WEBEX_ROOM_ID
    logger.info(f"send_message room_id={target_room}")
    return await post("/messages", {
        "roomId": target_room,
        "text": text,
    })


@mcp.tool()
async def delete_message(message_id: str) -> dict:
    """Delete a message from a Webex room.

    Args:
        message_id: The message ID to delete
    """
    logger.info(f"delete_message message_id={message_id}")
    return await delete(f"/messages/{message_id}")


# --- People ---

@mcp.tool()
async def get_person(person_id: str) -> dict:
    """Get details of a Webex user by their person ID.

    Args:
        person_id: The person ID
    """
    logger.info(f"get_person person_id={person_id}")
    return await get(f"/people/{person_id}")


@mcp.tool()
async def search_people(query: str) -> dict:
    """Search for Webex users by display name or email.

    Args:
        query: The search query — partial name or email address
    """
    logger.info(f"search_people query={query}")
    return await get("/people", {"displayName": query, "max": 25})


# --- Room membership ---

@mcp.tool()
async def list_room_members(room_id: str = "") -> dict:
    """List members of a Webex room. Defaults to the configured direct message room.

    Args:
        room_id: The room ID. Defaults to WEBEX_ROOM_ID from .env if not provided.
    """
    target_room = room_id or WEBEX_ROOM_ID
    logger.info(f"list_room_members room_id={target_room}")
    return await get("/memberships", {"roomId": target_room})


# --- Blocking message wait ---

@mcp.tool()
async def wait_for_message(last_message_id: str = "", room_id: str = "") -> dict:
    """Block and wait for a new message in the Webex direct message room.
    Polls every 5 seconds until a new message arrives, then returns it.
    Use last_message_id to avoid returning messages already seen.
    Note: this tool blocks until a message is received — be aware of host tool call timeouts.

    Args:
        last_message_id: The ID of the last seen message. Only returns messages newer than this.
        room_id: The room ID to watch. Defaults to WEBEX_ROOM_ID from .env if not provided.
    """
    target_room = room_id or WEBEX_ROOM_ID
    logger.info(f"wait_for_message room_id={target_room} last_message_id={last_message_id}")
    while True:
        try:
            messages = await get("/messages", {
                "roomId": target_room,
                "max": 1,
            })
            items = messages.get("items", [])
            if items:
                latest = items[0]
                if latest["id"] != last_message_id:
                    logger.info(f"New message received id={latest['id']}")
                    return latest
        except Exception as e:
            logger.error(f"wait_for_message poll error: {e}")
        await asyncio.sleep(5)


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
