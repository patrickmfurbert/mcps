# Splunk MCP Server

A Python MCP (Model Context Protocol) server that exposes Splunk Enterprise as a set of tools for AI assistants. Supports running SPL searches, browsing indexes and sourcetypes, and managing saved searches — queryable through natural language via Copilot CLI or any MCP-compatible host.

## Platform

These instructions assume a Linux environment. Path references (e.g. `/home/your-username/`) and install commands are Linux-specific. Windows and macOS users will need to adjust paths and package manager commands accordingly.

## Tools

**Search**
- `run_search` — convenience wrapper: submit SPL, poll until done, return results in one call
- `create_search_job` — submit a SPL search job and return the job ID
- `get_search_job_status` — check the status of a running search job
- `get_search_results` — fetch results for a completed search job
- `list_search_jobs` — list recent search jobs

**Indexes and Sourcetypes**
- `list_indexes` — list all accessible indexes
- `get_index` — get details of a specific index including event count and size
- `list_sourcetypes` — list all sourcetypes

**Saved Searches and Alerts**
- `list_saved_searches` — list all saved searches
- `get_saved_search` — get details of a specific saved search including the SPL query
- `run_saved_search` — dispatch a saved search and return the job ID

## How Splunk Search Works

Splunk searches are asynchronous. When you submit a search job it returns a job ID (sid), not results. You then poll the job until it completes and fetch the results separately. The `run_search` tool handles all three steps automatically and is what Copilot will reach for most of the time. The lower level `create_search_job`, `get_search_job_status`, and `get_search_results` tools are available if you need finer control.

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
git clone https://github.com/pastrycak3s/mcps.git
cd mcps/python/splunk
```

Install dependencies:
```bash
uv sync
```

## Configuration

### Credentials

Copy the example env file and fill in your values:
```bash
cp env-example .env
```

Edit `.env`:
```
SPLUNK_URL=https://your-splunk-instance.com:8089
SPLUNK_USERNAME=your-splunk-username
SPLUNK_PASSWORD=your-splunk-password
```

This server uses HTTP basic auth — your Splunk username and password are base64 encoded and sent as an `Authorization` header on every request. Credentials are loaded from `.env` at startup and never committed to the repo.

### Corporate SSL Certificates

If your Splunk instance is behind a corporate SSL proxy, this server uses the `truststore` package to automatically use your system's native certificate store. No additional configuration is needed.

### Copilot CLI

Add the following entry to `~/.copilot/mcp-config.json`, creating the file if it does not exist. Replace `your-username` with your actual username and find your `uv` path with `which uv`:
```json
{
  "mcpServers": {
    "splunk": {
      "type": "stdio",
      "command": "/home/your-username/.local/bin/uv",
      "args": [
        "run",
        "--project", "/home/your-username/projects/mcps/python/splunk",
        "python", "/home/your-username/projects/mcps/python/splunk/main.py"
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

Open the URL printed in the terminal in your browser, click **Connect**, and navigate to the **Tools** tab to invoke tools manually. A good first test is `list_indexes` which requires no arguments and will immediately confirm your credentials are working.

## Usage

Once connected to Copilot CLI, ask naturally:
```
search splunk for errors in the last hour
```
```
run this SPL: index=main sourcetype=syslog error | head 20
```
```
list all my saved searches in splunk
```
```
what indexes do i have access to in splunk
```

## Notes

- The `.env` file is gitignored and never committed. Use `env-example` as the reference for required variables.
- `truststore` is injected at process startup and patches SSL globally — no per-request configuration needed.
- All tools are async and use `httpx` for non-blocking HTTP calls.
- `run_search` polls the job status every second until complete. For long-running searches use `create_search_job` and poll manually with `get_search_job_status`.
- Splunk's REST API uses `application/x-www-form-urlencoded` for POST request bodies, not JSON. This is handled automatically by the server.
- Pyright may show an `unknown symbol` warning on the `FastMCP` import. This is a type stub gap in the `mcp` package and does not affect runtime behavior.
