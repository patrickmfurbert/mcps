# Bitbucket MCP Server

A Python MCP (Model Context Protocol) server that exposes Bitbucket Data Center as a set of tools for AI assistants. Supports pull request management, repository browsing, branch comparison, and build status — queryable through natural language via Copilot CLI or any MCP-compatible host.

> **Platform:** Assumes a Linux filesystem and OS. Instructions and paths may not work as-is on macOS or Windows.

## Tools

**Repositories**
- `list_projects` — list all accessible projects
- `list_repos` — list repositories in a project
- `search_repos` — search repositories by name across all projects

**Pull Requests**
- `list_pull_requests` — list PRs for a repo, filterable by state
- `get_pull_request` — get PR details including description and reviewers
- `get_pull_request_diff` — get the diff for a PR
- `approve_pull_request` — approve a PR
- `add_pr_comment` — add a comment to a PR

**Branches**
- `list_branches` — list branches for a repository
- `compare_branches` — get commits that differ between two branches

**Pipelines**
- `get_build_status` — get build status for a specific commit hash

## Prerequisites

### Python
```bash
sudo apt install python3
python3 --version  # 3.10+ required
```

### uv

Do not use the snap package. Use the official installer:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
uv --version
```

### Node.js and npm

Required for the MCP Inspector testing tool:
```bash
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install nodejs
node --version
npm --version
```

## Installation

Clone the repo and navigate to this server:
```bash
git clone https://github.com/patrickmfurbert/mcps.git
cd mcps/python/bitbucket
```

Install dependencies:
```bash
uv sync
```

`uv sync` reads `pyproject.toml` and `uv.lock` and installs all dependencies into a scoped `.venv`. This is the equivalent of `npm install` after cloning a Node project.

## Configuration

### Credentials

Copy the example env file and fill in your values:
```bash
cp .env.example .env
```

Edit `.env`:
```
BITBUCKET_URL=https://your-bitbucket-instance.com
BITBUCKET_TOKEN=your-personal-access-token
```

Generate a personal access token in Bitbucket Data Center under **Profile → Manage Account → Personal Access Tokens**. Read and write permissions are required for full functionality. Read-only is sufficient if you do not need `approve_pull_request` or `add_pr_comment`.

### Corporate SSL Certificates

If your Bitbucket instance is behind a corporate SSL proxy (common on managed work machines), this server uses the `truststore` package to automatically use your system's native certificate store. No additional configuration is needed — it is handled in code.

### Copilot CLI

Add the following entry to `~/.copilot/mcp-config.json`, creating the file if it does not exist. Replace `your-username` with your actual username and find your `uv` path with `which uv`:
```json
{
  "mcpServers": {
    "bitbucket": {
      "type": "stdio",
      "command": "/home/your-username/.local/bin/uv",
      "args": [
        "run",
        "--project", "/home/your-username/projects/mcps/python/bitbucket",
        "python", "/home/your-username/projects/mcps/python/bitbucket/main.py"
      ]
    }
  }
}
```

Restart Copilot CLI and verify the server connected:
```
/restart
/mcp
```

## Testing with MCP Inspector

Stop Copilot CLI before running the inspector — both need to spawn the server process and they will conflict.
```bash
uv run mcp dev main.py
```

Open the URL printed in the terminal in your browser, click **Connect**, and navigate to the **Tools** tab to invoke tools manually.

## Usage

Once connected to Copilot CLI, ask naturally:
```
list my open pull requests in project MYPROJ repo my-repo
```
```
show me the diff for PR 42 in MYPROJ/my-repo
```
```
what branches exist in MYPROJ/my-repo
```
```
approve PR 42 in MYPROJ/my-repo
```

## Notes

- The `.env` file is gitignored and never committed. Use `.env.example` as the reference for required variables.
- `truststore` is injected at process startup and patches SSL globally — no per-request configuration needed.
- All tools are async and use `httpx` for non-blocking HTTP calls, which is the correct pattern for FastMCP servers.
- Pyright may show an `unknown symbol` warning on the `FastMCP` import. This is a type stub gap in the `mcp` package and does not affect runtime behavior.
