import os
import time
import base64
import logging
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

truststore.inject_into_ssl()
load_dotenv()

SPLUNK_URL = os.getenv("SPLUNK_URL", "").rstrip("/")
SPLUNK_USERNAME = os.getenv("SPLUNK_USERNAME", "")
SPLUNK_PASSWORD = os.getenv("SPLUNK_PASSWORD", "")
API_BASE = f"{SPLUNK_URL}/services"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/splunk-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"Starting Splunk MCP server")
logger.info(f"SPLUNK_URL: {SPLUNK_URL}")
logger.info(f"SPLUNK_USERNAME: {SPLUNK_USERNAME}")
logger.info(f"SPLUNK_PASSWORD set: {'yes' if SPLUNK_PASSWORD else 'no'}")

mcp = FastMCP("splunk")


def get_basic_auth() -> str:
    credentials = f"{SPLUNK_USERNAME}:{SPLUNK_PASSWORD}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def get_headers() -> dict:
    return {
        "Authorization": get_basic_auth(),
        "Content-Type": "application/x-www-form-urlencoded",
    }


def get_json_headers() -> dict:
    return {
        "Authorization": get_basic_auth(),
        "Accept": "application/json",
    }


async def get(path: str, params: dict = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"GET {url} params={params}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=get_json_headers(),
                params={"output_mode": "json", **params},
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


async def post(path: str, data: dict = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"POST {url} data={data}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=get_headers(),
                data={"output_mode": "json", **data},
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


# --- Search ---

@mcp.tool()
async def run_search(spl: str, earliest: str = "-24h", latest: str = "now", max_results: int = 100) -> dict:
    """Run a SPL search and return results in one call. Submits the job, polls until complete, then returns results.

    Args:
        spl: The SPL search string (e.g. 'index=main error | head 10')
        earliest: Earliest time for the search (default: -24h)
        latest: Latest time for the search (default: now)
        max_results: Maximum number of results to return (default: 100)
    """
    logger.info(f"run_search spl={spl} earliest={earliest} latest={latest}")
    job = await post("/search/jobs", {
        "search": f"search {spl}",
        "earliest_time": earliest,
        "latest_time": latest,
    })
    sid = job["sid"]
    logger.info(f"run_search job created sid={sid}")

    async with httpx.AsyncClient() as client:
        while True:
            status_response = await client.get(
                f"{API_BASE}/search/jobs/{sid}",
                headers=get_json_headers(),
                params={"output_mode": "json"},
            )
            status_response.raise_for_status()
            status_data = status_response.json()
            dispatch_state = status_data["entry"][0]["content"]["dispatchState"]
            logger.debug(f"run_search sid={sid} dispatchState={dispatch_state}")
            if dispatch_state == "DONE":
                logger.info(f"run_search sid={sid} complete")
                break
            if dispatch_state == "FAILED":
                logger.error(f"run_search sid={sid} failed")
                return {"error": "Search job failed", "sid": sid}
            time.sleep(1)

    return await get(f"/search/jobs/{sid}/results", {"count": max_results})


@mcp.tool()
async def create_search_job(spl: str, earliest: str = "-24h", latest: str = "now") -> dict:
    """Submit a SPL search job and return the job ID (sid). Use get_search_job_status to poll and get_search_results to fetch results.

    Args:
        spl: The SPL search string (e.g. 'index=main error | head 10')
        earliest: Earliest time for the search (default: -24h)
        latest: Latest time for the search (default: now)
    """
    logger.info(f"create_search_job spl={spl}")
    return await post("/search/jobs", {
        "search": f"search {spl}",
        "earliest_time": earliest,
        "latest_time": latest,
    })


@mcp.tool()
async def get_search_job_status(sid: str) -> dict:
    """Check the status of a running search job.

    Args:
        sid: The search job ID returned by create_search_job
    """
    logger.info(f"get_search_job_status sid={sid}")
    return await get(f"/search/jobs/{sid}")


@mcp.tool()
async def get_search_results(sid: str, max_results: int = 100) -> dict:
    """Fetch results for a completed search job.

    Args:
        sid: The search job ID returned by create_search_job
        max_results: Maximum number of results to return (default: 100)
    """
    logger.info(f"get_search_results sid={sid} max_results={max_results}")
    return await get(f"/search/jobs/{sid}/results", {"count": max_results})


@mcp.tool()
async def list_search_jobs() -> dict:
    """List recent search jobs for the authenticated user."""
    logger.info("list_search_jobs called")
    return await get("/search/jobs", {"count": 25})


# --- Indexes and Sourcetypes ---

@mcp.tool()
async def list_indexes() -> dict:
    """List all Splunk indexes accessible to the authenticated user."""
    logger.info("list_indexes called")
    return await get("/data/indexes", {"count": 100})


@mcp.tool()
async def get_index(index_name: str) -> dict:
    """Get details of a specific index including event count and size.

    Args:
        index_name: The name of the index (e.g. 'main')
    """
    logger.info(f"get_index index_name={index_name}")
    return await get(f"/data/indexes/{index_name}")


@mcp.tool()
async def list_sourcetypes() -> dict:
    """List all sourcetypes available in Splunk."""
    logger.info("list_sourcetypes called")
    return await get("/saved/sourcetypes", {"count": 100})


# --- Saved Searches and Alerts ---

@mcp.tool()
async def list_saved_searches() -> dict:
    """List all saved searches accessible to the authenticated user."""
    logger.info("list_saved_searches called")
    return await get("/saved/searches", {"count": 50})


@mcp.tool()
async def get_saved_search(name: str) -> dict:
    """Get details of a specific saved search including the SPL query.

    Args:
        name: The name of the saved search
    """
    logger.info(f"get_saved_search name={name}")
    return await get(f"/saved/searches/{name}")


@mcp.tool()
async def run_saved_search(name: str) -> dict:
    """Dispatch a saved search and return the job ID.

    Args:
        name: The name of the saved search to run
    """
    logger.info(f"run_saved_search name={name}")
    return await post(f"/saved/searches/{name}/dispatch")


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
