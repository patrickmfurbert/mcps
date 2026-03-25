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
JIRA_URL = os.getenv("JIRA_URL", "").rstrip("/")
JIRA_TOKEN = os.getenv("JIRA_TOKEN", "")

# ---------------------------------------------------------------------------
# API base URLs
# Jira Data Center exposes two separate REST APIs:
#   - Core API (/rest/api/2) — issues, projects, users, comments
#   - Agile API (/rest/agile/1.0) — boards, sprints
# ---------------------------------------------------------------------------
API_BASE = f"{JIRA_URL}/rest/api/2"
AGILE_BASE = f"{JIRA_URL}/rest/agile/1.0"

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("/tmp/jira-mcp.log"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting jira MCP server")
logger.info(f"JIRA_URL: {JIRA_URL}")
logger.info(f"JIRA_TOKEN set: {'yes' if JIRA_TOKEN else 'no'}")

mcp = FastMCP("jira")


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {JIRA_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get(path: str, params: dict[str, Any] = {}, base: str = "") -> dict:
    url = f"{base or API_BASE}{path}"
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


async def post(path: str, body: Any = {}, base: str = "") -> dict:
    url = f"{base or API_BASE}{path}"
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


async def put(path: str, body: Any = {}, base: str = "") -> dict:
    url = f"{base or API_BASE}{path}"
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


# --- Issues ---

@mcp.tool()
async def get_issue(issue_key: str) -> dict:
    """Get a Jira issue by key including summary, status, assignee, and description.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
    """
    logger.info(f"get_issue issue_key={issue_key}")
    return await get(f"/issue/{issue_key}")


@mcp.tool()
async def search_issues(jql: str, max_results: int = 25) -> dict:
    """Search Jira issues using JQL (Jira Query Language).

    Args:
        jql: JQL query string (e.g. 'project=PROJ AND status="In Progress" AND assignee=currentUser()')
        max_results: Maximum number of results to return (default: 25)
    """
    logger.info(f"search_issues jql={jql}")
    return await post("/search", {
        "jql": jql,
        "maxResults": max_results,
        "fields": [
            "summary", "status", "assignee", "reporter",
            "priority", "issuetype", "created", "updated",
            "description", "comment", "labels", "fixVersions"
        ],
    })


@mcp.tool()
async def create_issue(project_key: str, summary: str, issue_type: str, description: str = "", assignee: str = "") -> dict:
    """Create a new Jira issue.

    Args:
        project_key: The project key (e.g. 'PROJ')
        summary: The issue summary
        issue_type: The issue type (e.g. 'Bug', 'Story', 'Task')
        description: Optional issue description
        assignee: Optional assignee username
    """
    logger.info(f"create_issue project_key={project_key} summary={summary}")
    body: dict[str, Any] = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
    }
    if description:
        body["fields"]["description"] = description
    if assignee:
        body["fields"]["assignee"] = {"name": assignee}
    return await post("/issue", body)


@mcp.tool()
async def update_issue(issue_key: str, summary: str = "", description: str = "", assignee: str = "", priority: str = "") -> dict:
    """Update fields on a Jira issue.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
        summary: Optional new summary
        description: Optional new description
        assignee: Optional new assignee username
        priority: Optional new priority (e.g. 'High', 'Medium', 'Low')
    """
    logger.info(f"update_issue issue_key={issue_key}")
    fields: dict[str, Any] = {}
    if summary:
        fields["summary"] = summary
    if description:
        fields["description"] = description
    if assignee:
        fields["assignee"] = {"name": assignee}
    if priority:
        fields["priority"] = {"name": priority}
    return await put(f"/issue/{issue_key}", {"fields": fields})


@mcp.tool()
async def get_issue_transitions(issue_key: str) -> dict:
    """Get available transitions for a Jira issue. Use this before transition_issue to find the correct transition ID.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
    """
    logger.info(f"get_issue_transitions issue_key={issue_key}")
    return await get(f"/issue/{issue_key}/transitions")


@mcp.tool()
async def transition_issue(issue_key: str, transition_id: str) -> dict:
    """Move a Jira issue to a new status using a transition ID. Use get_issue_transitions first to find the correct ID.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
        transition_id: The transition ID (from get_issue_transitions)
    """
    logger.info(f"transition_issue issue_key={issue_key} transition_id={transition_id}")
    return await post(f"/issue/{issue_key}/transitions", {
        "transition": {"id": transition_id}
    })


@mcp.tool()
async def assign_issue(issue_key: str, username: str) -> dict:
    """Assign a Jira issue to a user.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
        username: The Jira username to assign to
    """
    logger.info(f"assign_issue issue_key={issue_key} username={username}")
    return await put(f"/issue/{issue_key}/assignee", {"name": username})


@mcp.tool()
async def get_comments(issue_key: str) -> dict:
    """Get all comments on a Jira issue.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
    """
    logger.info(f"get_comments issue_key={issue_key}")
    return await get(f"/issue/{issue_key}/comment")


@mcp.tool()
async def add_comment(issue_key: str, text: str) -> dict:
    """Add a comment to a Jira issue.

    Args:
        issue_key: The issue key (e.g. 'PROJ-123')
        text: The comment text
    """
    logger.info(f"add_comment issue_key={issue_key}")
    return await post(f"/issue/{issue_key}/comment", {"body": text})


# --- Projects ---

@mcp.tool()
async def list_projects() -> dict:
    """List all Jira projects accessible to the authenticated user."""
    logger.info("list_projects called")
    return await get("/project", {"expand": "description"})


@mcp.tool()
async def get_project(project_key: str) -> dict:
    """Get details of a specific Jira project.

    Args:
        project_key: The project key (e.g. 'PROJ')
    """
    logger.info(f"get_project project_key={project_key}")
    return await get(f"/project/{project_key}")


# --- Boards and Sprints ---

@mcp.tool()
async def list_boards(project_key: str = "") -> dict:
    """List Jira boards, optionally filtered by project.

    Args:
        project_key: Optional project key to filter boards by (e.g. 'PROJ')
    """
    logger.info(f"list_boards project_key={project_key}")
    params: dict[str, Any] = {"maxResults": 50}
    if project_key:
        params["projectKeyOrId"] = project_key
    return await get("/board", params, base=AGILE_BASE)


@mcp.tool()
async def get_active_sprint(board_id: int) -> dict:
    """Get the active sprint for a Jira board.

    Args:
        board_id: The board ID (from list_boards)
    """
    logger.info(f"get_active_sprint board_id={board_id}")
    return await get(f"/board/{board_id}/sprint", {"state": "active"}, base=AGILE_BASE)


@mcp.tool()
async def get_sprint_issues(board_id: int, sprint_id: int) -> dict:
    """Get all issues in a specific sprint.

    Args:
        board_id: The board ID (from list_boards)
        sprint_id: The sprint ID (from get_active_sprint)
    """
    logger.info(f"get_sprint_issues board_id={board_id} sprint_id={sprint_id}")
    return await get(
        f"/board/{board_id}/sprint/{sprint_id}/issue",
        {"maxResults": 50},
        base=AGILE_BASE,
    )


# --- Users ---

@mcp.tool()
async def get_current_user() -> dict:
    """Get the currently authenticated Jira user."""
    logger.info("get_current_user called")
    return await get("/myself")


@mcp.tool()
async def search_users(query: str) -> dict:
    """Search for Jira users by display name or username.

    Args:
        query: The search query (partial name or username)
    """
    logger.info(f"search_users query={query}")
    return await get("/user/search", {"query": query, "maxResults": 25})


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
