import os
import base64
import logging
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any

truststore.inject_into_ssl()
load_dotenv()

JENKINS_URL = os.getenv("JENKINS_URL", "").rstrip("/")
JENKINS_USER = os.getenv("JENKINS_USER", "")
JENKINS_TOKEN = os.getenv("JENKINS_TOKEN", "")
API_BASE = JENKINS_URL

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/jenkins-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting jenkins MCP server")
logger.info(f"JENKINS_URL: {JENKINS_URL}")
logger.info(f"JENKINS_USER: {JENKINS_USER}")
logger.info(f"JENKINS_TOKEN set: {'yes' if JENKINS_TOKEN else 'no'}")

mcp = FastMCP("jenkins")


def get_headers() -> dict:
    credentials = base64.b64encode(f"{JENKINS_USER}:{JENKINS_TOKEN}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def job_path_to_url(job_path: str) -> str:
    """Convert a slash-separated job path to a Jenkins URL segment.

    Examples:
        'my-job'          -> '/job/my-job'
        'my-folder/child' -> '/job/my-folder/job/child'
    """
    parts = [p for p in job_path.strip("/").split("/") if p]
    return "/" + "/".join(f"job/{p}" for p in parts)


async def get_crumb() -> dict[str, str]:
    """Fetch a Jenkins CSRF crumb. Included in POST request headers."""
    try:
        url = f"{API_BASE}/crumbIssuer/api/json"
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers())
            response.raise_for_status()
            data = response.json()
            return {data["crumbRequestField"]: data["crumb"]}
    except Exception:
        return {}


async def get(path: str, params: dict[str, Any] = {}) -> dict:
    url = f"{API_BASE}{path}"
    logger.debug(f"GET {url} params={params}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers(), params=params)
            logger.debug(f"GET {url} status={response.status_code}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"GET {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"GET {url} error: {e}")
        raise


async def get_text(path: str) -> str:
    """GET a plain-text endpoint (e.g. console output)."""
    url = f"{API_BASE}{path}"
    logger.debug(f"GET (text) {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=get_headers())
            logger.debug(f"GET (text) {url} status={response.status_code}")
            response.raise_for_status()
            return response.text
    except httpx.HTTPStatusError as e:
        logger.error(f"GET (text) {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"GET (text) {url} error: {e}")
        raise


async def post(path: str, params: dict[str, Any] = {}, body: dict[str, Any] | None = None) -> dict:
    url = f"{API_BASE}{path}"
    crumb = await get_crumb()
    headers = {**get_headers(), **crumb}
    logger.debug(f"POST {url} params={params}")
    try:
        async with httpx.AsyncClient() as client:
            kwargs: dict[str, Any] = {"headers": headers, "params": params}
            if body is not None:
                kwargs["json"] = body
            response = await client.post(url, **kwargs)
            logger.debug(f"POST {url} status={response.status_code}")
            response.raise_for_status()
            if response.content:
                try:
                    return response.json()
                except Exception:
                    return {"status": response.status_code, "text": response.text}
            return {"status": response.status_code}
    except httpx.HTTPStatusError as e:
        logger.error(f"POST {url} HTTP error: {e.response.status_code} {e.response.text}")
        raise
    except Exception as e:
        logger.error(f"POST {url} error: {e}")
        raise


# --- Jenkins Info ---

@mcp.tool()
async def get_jenkins_info() -> dict:
    """Get overall Jenkins instance information including version, description, and node count."""
    logger.info("get_jenkins_info called")
    return await get("/api/json")


# --- Jobs ---

@mcp.tool()
async def list_jobs(folder: str = "") -> dict:
    """List Jenkins jobs. Optionally list jobs inside a folder.

    Args:
        folder: Optional folder job path (e.g. 'my-folder') to list jobs within. Leave empty for top-level jobs.
    """
    logger.info(f"list_jobs folder={folder}")
    path = job_path_to_url(folder) if folder else ""
    return await get(f"{path}/api/json", {"tree": "jobs[name,url,color,description,buildable]"})


@mcp.tool()
async def get_job(job_path: str) -> dict:
    """Get details for a Jenkins job including build history, parameters, and current status.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
    """
    logger.info(f"get_job job_path={job_path}")
    return await get(f"{job_path_to_url(job_path)}/api/json")


@mcp.tool()
async def enable_job(job_path: str) -> dict:
    """Enable a disabled Jenkins job.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
    """
    logger.info(f"enable_job job_path={job_path}")
    return await post(f"{job_path_to_url(job_path)}/enable")


@mcp.tool()
async def disable_job(job_path: str) -> dict:
    """Disable a Jenkins job so it cannot be built.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
    """
    logger.info(f"disable_job job_path={job_path}")
    return await post(f"{job_path_to_url(job_path)}/disable")


# --- Builds ---

@mcp.tool()
async def list_builds(job_path: str, count: int = 10) -> dict:
    """List recent builds for a Jenkins job with their numbers, statuses, and timestamps.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
        count: Number of recent builds to return (default: 10)
    """
    logger.info(f"list_builds job_path={job_path} count={count}")
    tree = f"builds[number,url,result,timestamp,duration,building]{{{count}}}"
    return await get(f"{job_path_to_url(job_path)}/api/json", {"tree": tree})


@mcp.tool()
async def get_build(job_path: str, build_number: int) -> dict:
    """Get details for a specific build including result, duration, parameters, and test summary.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
        build_number: The build number
    """
    logger.info(f"get_build job_path={job_path} build_number={build_number}")
    return await get(f"{job_path_to_url(job_path)}/{build_number}/api/json")


@mcp.tool()
async def get_last_build(job_path: str) -> dict:
    """Get details for the most recent build of a Jenkins job.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
    """
    logger.info(f"get_last_build job_path={job_path}")
    return await get(f"{job_path_to_url(job_path)}/lastBuild/api/json")


@mcp.tool()
async def get_console_output(job_path: str, build_number: int) -> str:
    """Get the console log output for a specific build.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
        build_number: The build number
    """
    logger.info(f"get_console_output job_path={job_path} build_number={build_number}")
    return await get_text(f"{job_path_to_url(job_path)}/{build_number}/consoleText")


@mcp.tool()
async def trigger_build(job_path: str, parameters: dict[str, str] = {}) -> dict:
    """Trigger a new build for a Jenkins job. Optionally pass build parameters.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
        parameters: Optional key-value pairs for parameterized builds (e.g. {"BRANCH": "main", "ENV": "staging"})
    """
    logger.info(f"trigger_build job_path={job_path} parameters={parameters}")
    if parameters:
        return await post(f"{job_path_to_url(job_path)}/buildWithParameters", params=parameters)
    return await post(f"{job_path_to_url(job_path)}/build")


@mcp.tool()
async def stop_build(job_path: str, build_number: int) -> dict:
    """Stop a running Jenkins build.

    Args:
        job_path: The job name or slash-separated folder path (e.g. 'my-job' or 'my-folder/my-job')
        build_number: The build number to stop
    """
    logger.info(f"stop_build job_path={job_path} build_number={build_number}")
    return await post(f"{job_path_to_url(job_path)}/{build_number}/stop")


# --- Queue ---

@mcp.tool()
async def list_queue() -> dict:
    """List all items currently waiting in the Jenkins build queue."""
    logger.info("list_queue called")
    return await get("/queue/api/json")


@mcp.tool()
async def cancel_queue_item(item_id: int) -> dict:
    """Cancel a queued build item before it starts.

    Args:
        item_id: The queue item ID (from list_queue)
    """
    logger.info(f"cancel_queue_item item_id={item_id}")
    return await post("/queue/cancelItem", params={"id": item_id})


# --- Nodes ---

@mcp.tool()
async def list_nodes() -> dict:
    """List all Jenkins nodes (agents) including their online/offline status and assigned labels."""
    logger.info("list_nodes called")
    return await get("/computer/api/json")


@mcp.tool()
async def get_node(node_name: str) -> dict:
    """Get details for a specific Jenkins node including status, executors, and labels.

    Args:
        node_name: The node name. Use '(built-in)' or 'master' for the controller node.
    """
    logger.info(f"get_node node_name={node_name}")
    return await get(f"/computer/{node_name}/api/json")


# --- Views ---

@mcp.tool()
async def list_views() -> dict:
    """List all configured Jenkins views."""
    logger.info("list_views called")
    return await get("/api/json", {"tree": "views[name,url,description]"})


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
