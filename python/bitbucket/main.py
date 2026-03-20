import os
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

truststore.inject_into_ssl()
load_dotenv()

BITBUCKET_URL = os.getenv("BITBUCKET_URL", "").rstrip("/")
BITBUCKET_TOKEN = os.getenv("BITBUCKET_TOKEN", "")
API_BASE = f"{BITBUCKET_URL}/rest/api/1.0"

mcp = FastMCP("bitbucket")


def get_headers() -> dict:
    return {
        "Authorization": f"Bearer {BITBUCKET_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def get(path: str, params: dict = {}) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}{path}",
            headers=get_headers(),
            params=params,
        )
        response.raise_for_status()
        return response.json()


async def post(path: str, body: dict = {}) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}{path}",
            headers=get_headers(),
            json=body,
        )
        response.raise_for_status()
        return response.json()


# --- Repositories ---

@mcp.tool()
async def list_projects() -> dict:
    """List all Bitbucket projects accessible to the authenticated user."""
    return await get("/projects", {"limit": 50})


@mcp.tool()
async def list_repos(project_key: str) -> dict:
    """List all repositories in a given Bitbucket project.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
    """
    return await get(f"/projects/{project_key}/repos", {"limit": 50})


@mcp.tool()
async def search_repos(name: str) -> dict:
    """Search for repositories by name across all projects.

    Args:
        name: Partial or full repository name to search for
    """
    return await get("/repos", {"name": name, "limit": 25})


# --- Pull Requests ---

@mcp.tool()
async def list_pull_requests(project_key: str, repo_slug: str, state: str = "OPEN") -> dict:
    """List pull requests for a repository.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        state: PR state to filter by — OPEN, MERGED, or DECLINED (default: OPEN)
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests",
        {"state": state, "limit": 25},
    )


@mcp.tool()
async def get_pull_request(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Get details of a specific pull request including description and reviewers.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}")


@mcp.tool()
async def get_pull_request_diff(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Get the diff for a specific pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/diff")


@mcp.tool()
async def approve_pull_request(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Approve a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await post(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/approve")


@mcp.tool()
async def add_pr_comment(project_key: str, repo_slug: str, pr_id: int, text: str) -> dict:
    """Add a comment to a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
        text: The comment text
    """
    return await post(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/comments",
        {"text": text},
    )


# --- Branches ---

@mcp.tool()
async def list_branches(project_key: str, repo_slug: str) -> dict:
    """List branches for a repository.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/branches",
        {"limit": 50},
    )


@mcp.tool()
async def compare_branches(project_key: str, repo_slug: str, from_branch: str, to_branch: str) -> dict:
    """Get commits that differ between two branches.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        from_branch: The source branch name
        to_branch: The target branch name
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/commits",
        {"since": to_branch, "until": from_branch, "limit": 25},
    )


# --- Pipelines / Build Status ---

@mcp.tool()
async def get_build_status(commit_hash: str) -> dict:
    """Get the build status for a specific commit.

    Args:
        commit_hash: The full commit hash
    """
    return await get(f"/commits/{commit_hash}/builds")


if __name__ == "__main__":
    mcp.run()
