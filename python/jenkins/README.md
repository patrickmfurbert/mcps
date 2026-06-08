# Jenkins MCP Server

A Python MCP (Model Context Protocol) server that exposes Jenkins as a set of tools for AI assistants. Supports browsing jobs, triggering and monitoring builds, reading console output, managing the build queue, and inspecting nodes — queryable through natural language via Copilot CLI or any MCP-compatible host.

> **Platform:** Assumes a Linux filesystem and OS. Instructions and paths may not work as-is on macOS or Windows.

## Tools

**Jenkins Info**
- `get_jenkins_info` — get overall Jenkins instance info including version and node count

**Jobs**
- `list_jobs` — list top-level jobs or jobs inside a folder
- `get_job` — get job details including build history and parameters
- `enable_job` — enable a disabled job
- `disable_job` — disable a job so it cannot be built

**Builds**
- `list_builds` — list recent builds for a job with statuses and timestamps
- `get_build` — get details for a specific build including result and duration
- `get_last_build` — get the most recent build for a job
- `get_console_output` — get the console log for a build
- `trigger_build` — trigger a new build, optionally with parameters
- `stop_build` — stop a running build

**Queue**
- `list_queue` — list items waiting in the build queue
- `cancel_queue_item` — cancel a queued build before it starts

**Nodes**
- `list_nodes` — list all agents including online/offline status and labels
- `get_node` — get details for a specific node

**Views**
- `list_views` — list all configured views

## Authentication

Jenkins uses HTTP Basic auth with a username and API token. The server constructs a `Basic` authorization header from `JENKINS_USER` and `JENKINS_TOKEN`. Generate an API token in Jenkins under **User → Configure → API Token → Add new Token**.

## CSRF Protection

Jenkins requires a CSRF crumb for all POST requests. The server fetches a crumb automatically from `/crumbIssuer/api/json` before every mutating request — no manual configuration needed.

## Folder-Structured Jobs

Job paths support Jenkins folder nesting using slash-separated paths. For example, a job `my-job` inside `my-folder` is referenced as `my-folder/my-job`. The server translates this to the correct Jenkins URL structure (`/job/my-folder/job/my-job`).

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
cd mcps/python/jenkins
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
cp env-example .env
```

Edit `.env`:
```
JENKINS_URL=https://your-jenkins-instance.com
JENKINS_USER=your-jenkins-username
JENKINS_TOKEN=your-api-token
```

Generate an API token in Jenkins under **User → Configure → API Token → Add new Token**.

### Corporate SSL Certificates

If your Jenkins instance is behind a corporate SSL proxy (common on managed work machines), this server uses the `truststore` package to automatically use your system's native certificate store. No additional configuration is needed — it is handled in code.

### Copilot CLI

Add the following entry to `~/.copilot/mcp-config.json`, creating the file if it does not exist. Replace `your-username` with your actual username and find your `uv` path with `which uv`:
```json
{
  "mcpServers": {
    "jenkins": {
      "type": "stdio",
      "command": "/home/your-username/.local/bin/uv",
      "args": [
        "run",
        "--project", "/home/your-username/projects/mcps/python/jenkins",
        "python", "/home/your-username/projects/mcps/python/jenkins/main.py"
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
list all Jenkins jobs
```
```
what is the status of the last build for my-job?
```
```
show me the console output for build 42 of my-folder/my-job
```
```
trigger a build for my-job with BRANCH=main
```
```
what's in the build queue?
```

## Notes

- The `.env` file is gitignored and never committed. Use `env-example` as the reference for required variables.
- `truststore` is injected at process startup and patches SSL globally — no per-request configuration needed.
- All tools are async and use `httpx` for non-blocking HTTP calls, which is the correct pattern for FastMCP servers.
- Pyright may show an `unknown symbol` warning on the `FastMCP` import. This is a type stub gap in the `mcp` package and does not affect runtime behavior.
