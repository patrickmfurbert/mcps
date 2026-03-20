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


async def delete(path: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{API_BASE}{path}",
            headers=get_headers(),
        )
        response.raise_for_status()
        return response.json()


# --- Users ---

@mcp.tool()
async def get_current_user() -> dict:
    """Get the currently authenticated user."""
    return await get("/users/current")


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
async def get_repo(project_key: str, repo_slug: str) -> dict:
    """Get details of a single repository including description, default branch, and clone URLs.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}")


@mcp.tool()
async def search_repos(name: str) -> dict:
    """Search for repositories by name across all projects.

    Args:
        name: Partial or full repository name to search for
    """
    return await get("/repos", {"name": name, "limit": 25})


@mcp.tool()
async def get_file_contents(project_key: str, repo_slug: str, file_path: str, branch: str = "main") -> dict:
    """Read the contents of a file from a repository at a given branch.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        file_path: Path to the file within the repo (e.g. 'src/main/java/App.java')
        branch: Branch name to read from (default: main)
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/browse/{file_path}",
        {"at": branch},
    )


# --- Commits ---

@mcp.tool()
async def list_commits(project_key: str, repo_slug: str, branch: str = "main", limit: int = 25) -> dict:
    """List recent commits on a branch with messages and authors.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        branch: Branch name (default: main)
        limit: Number of commits to return (default: 25)
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/commits",
        {"until": branch, "limit": limit},
    )


@mcp.tool()
async def get_commit(project_key: str, repo_slug: str, commit_hash: str) -> dict:
    """Get details of a specific commit including changed files.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        commit_hash: The full commit hash
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/commits/{commit_hash}")


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
async def get_pr_commits(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """List all commits included in a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/commits")


@mcp.tool()
async def get_pr_activities(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Get the full activity log of a pull request including comments, approvals, and commits pushed.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/activities",
        {"limit": 50},
    )


@mcp.tool()
async def get_pr_reviewers(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """List reviewers on a pull request and their current approval status.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    pr = await get(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}")
    return {"reviewers": pr.get("reviewers", [])}


@mcp.tool()
async def get_pr_participants(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """List all participants in a pull request including author, reviewers, and commenters.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    pr = await get(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}")
    return {"participants": pr.get("participants", [])}


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
async def unapprove_pull_request(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Remove approval from a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await delete(f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/approve")


@mcp.tool()
async def request_changes_pull_request(project_key: str, repo_slug: str, pr_id: int) -> dict:
    """Mark a pull request as needs work.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
    """
    return await post(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/participants/current",
        {"status": "NEEDS_WORK"},
    )


@mcp.tool()
async def merge_pull_request(project_key: str, repo_slug: str, pr_id: int, version: int) -> dict:
    """Merge a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
        version: The current version of the PR (from get_pull_request response — required to prevent conflicting merges)
    """
    return await post(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/merge",
        {"version": version},
    )


@mcp.tool()
async def decline_pull_request(project_key: str, repo_slug: str, pr_id: int, version: int) -> dict:
    """Decline a pull request.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        pr_id: The pull request ID
        version: The current version of the PR (from get_pull_request response)
    """
    return await post(
        f"/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/decline",
        {"version": version},
    )


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
async def get_default_branch(project_key: str, repo_slug: str) -> dict:
    """Get the default branch for a repository.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/branches/default")


@mcp.tool()
async def create_branch(project_key: str, repo_slug: str, branch_name: str, start_point: str) -> dict:
    """Create a new branch from a given start point.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        branch_name: Name of the new branch
        start_point: Branch name or commit hash to branch from
    """
    return await post(
        f"/projects/{project_key}/repos/{repo_slug}/branches",
        {"name": branch_name, "startPoint": start_point},
    )


# @mcp.tool()
# async def delete_branch(project_key: str, repo_slug: str, branch_name: str) -> dict:
#     """Delete a branch from a repository.
#
#     Args:
#         project_key: The project key (e.g. 'MYPROJ')
#         repo_slug: The repository slug (e.g. 'my-repo')
#         branch_name: Name of the branch to delete
#     """
#     return await delete(f"/projects/{project_key}/repos/{repo_slug}/branches/{branch_name}")


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


# --- Tags ---

@mcp.tool()
async def list_tags(project_key: str, repo_slug: str) -> dict:
    """List tags for a repository.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
    """
    return await get(
        f"/projects/{project_key}/repos/{repo_slug}/tags",
        {"limit": 50},
    )


@mcp.tool()
async def create_tag(project_key: str, repo_slug: str, tag_name: str, commit_hash: str, message: str = "") -> dict:
    """Create a tag at a specific commit.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
        tag_name: Name of the tag (e.g. 'v1.2.0')
        commit_hash: The commit hash to tag
        message: Optional tag message for annotated tags
    """
    body: dict = {"name": tag_name, "startPoint": commit_hash}
    if message:
        body["message"] = message
    return await post(f"/projects/{project_key}/repos/{repo_slug}/tags", body)


# --- Pipelines / Build Status ---

@mcp.tool()
async def get_build_status(commit_hash: str) -> dict:
    """Get the build status for a specific commit.

    Args:
        commit_hash: The full commit hash
    """
    return await get(f"/commits/{commit_hash}/builds")


# --- Webhooks ---

@mcp.tool()
async def list_webhooks(project_key: str, repo_slug: str) -> dict:
    """List configured webhooks for a repository.

    Args:
        project_key: The project key (e.g. 'MYPROJ')
        repo_slug: The repository slug (e.g. 'my-repo')
    """
    return await get(f"/projects/{project_key}/repos/{repo_slug}/webhooks")


if __name__ == "__main__":
    mcp.run()
