# Confluence MCP Server

A Python MCP (Model Context Protocol) server that exposes Confluence Data Center as a set of tools for AI assistants. Supports browsing spaces, reading and creating pages, searching with CQL, managing comments and labels — queryable through natural language via Copilot CLI or any MCP-compatible host.

## Platform

These instructions assume a Linux environment. Path references (e.g. `/home/your-username/`) and install commands are Linux-specific. Windows and macOS users will need to adjust paths and package manager commands accordingly.

## Tools

**Spaces**
- `list_spaces` — list all spaces, optionally filtered by type (global or personal)
- `get_space` — get details of a space by key

**Pages**
- `get_page` — get a page by ID (storage XML or rendered HTML)
- `get_page_by_title` — find a page by space key and exact title
- `get_space_pages` — list pages in a space
- `get_page_children` — get direct child pages of a page
- `get_page_ancestors` — get the breadcrumb path to root
- `create_page` — create a new page, optionally under a parent
- `update_page` — update a page body and title (version auto-incremented)

**Comments**
- `get_page_comments` — get all comments on a page
- `add_page_comment` — add a plain text comment to a page

**Labels**
- `get_page_labels` — get labels on a page
- `add_page_label` — add a label to a page

**Attachments**
- `get_page_attachments` — list attachments on a page

**Search**
- `search` — search using CQL (Confluence Query Language)

**Users**
- `get_user` — look up a user by username

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
cd mcps/python/confluence
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
CONFLUENCE_URL=https://your-confluence-instance.com
CONFLUENCE_TOKEN=your-personal-access-token
```

Generate a personal access token in Confluence Data Center under **Profile → Settings → Personal Access Tokens**. Read permissions are sufficient for all read-only tools. Write permissions are required for `create_page`, `update_page`, `add_page_comment`, and `add_page_label`.

### Corporate SSL Certificates

This server uses the `truststore` package to automatically use your system's native certificate store. No additional configuration is needed for corporate SSL proxies.

### Copilot CLI

Add the following entry to `~/.copilot/mcp-config.json`. Replace `your-username` with your actual username and find your `uv` path with `which uv`:
```json
{
  "mcpServers": {
    "confluence": {
      "type": "stdio",
      "command": "/home/your-username/.local/bin/uv",
      "args": [
        "run",
        "--project", "/home/your-username/projects/mcps/python/confluence",
        "python", "/home/your-username/projects/mcps/python/confluence/main.py"
      ]
    }
  }
}
```

If you already have other MCP servers configured, add `confluence` as an additional entry inside the existing `mcpServers` object.

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

Open the URL printed in the terminal in your browser, click **Connect**, and navigate to the **Tools** tab. A good first test is `list_spaces` which requires no arguments and will immediately confirm your credentials are working.

## Usage

Once connected to Copilot CLI, ask naturally:
```
list all spaces in confluence
```
```
find the confluence page called "Deployment Guide" in space MYPROJ
```
```
search confluence for pages about kafka in the PLATFORM space
```
```
add a comment to confluence page 12345 saying "reviewed and approved"
```
```
create a confluence page in space MYPROJ called "Release Notes v2.1"
```

## Logs

Logs are written to `/tmp/confluence-mcp.log`. Tail in a separate terminal for debugging:
```bash
tail -f /tmp/confluence-mcp.log
```

The startup log entries will confirm whether `CONFLUENCE_URL` and `CONFLUENCE_TOKEN` are loading correctly from `.env`.

## Notes

- The `.env` file is gitignored and never committed. Use `env-example` as the reference for required variables.
- `update_page` automatically fetches the current page version and increments it — Confluence requires the correct version number on every update.
- `add_page_comment` accepts plain text and wraps it in Confluence storage XML automatically.
- `search` uses CQL — refer to Atlassian's CQL documentation for query syntax.
- Pyright may show an `unknown symbol` warning on the `FastMCP` import. This is a type stub gap in the `mcp` package and does not affect runtime behavior.

## Windows Configuration

On Windows the path separators and `uv` location differ from Linux. Find your `uv` path with:
```cmd
where.exe uv
```

It will typically be at `C:\Users\your-username\.local\bin\uv.exe` or `C:\Users\your-username\.cargo\bin\uv.exe` depending on how it was installed.

### VS Code

Create or edit `.vscode\mcp.json` in your workspace, or open the user-level config via the Command Palette (`Ctrl+Shift+P`) and search for **MCP: Open User Configuration**. Note that VS Code uses `servers` as the top-level key rather than `mcpServers`:
```json
{
  "servers": {
    "confluence": {
      "type": "stdio",
      "command": "C:\\Users\\your-username\\.local\\bin\\uv.exe",
      "args": [
        "run",
        "--project", "C:\\Users\\your-username\\projects\\mcps\\python\\confluence",
        "python", "C:\\Users\\your-username\\projects\\mcps\\python\\confluence\\main.py"
      ]
    }
  }
}
```

Make sure you are in **Agent mode** in Copilot Chat for MCP tools to be available. Switch to Agent mode using the mode dropdown at the bottom of the chat panel.

### IntelliJ IDEA

Requires IntelliJ IDEA 2025.1 or later with the AI Assistant plugin enabled.

Go to **Settings → Tools → AI Assistant → Model Context Protocol (MCP)** and click **+** to add a new server. Paste the following JSON:
```json
{
  "type": "stdio",
  "command": "C:\\Users\\your-username\\.local\\bin\\uv.exe",
  "args": [
    "run",
    "--project", "C:\\Users\\your-username\\projects\\mcps\\python\\confluence",
    "python", "C:\\Users\\your-username\\projects\\mcps\\python\\confluence\\main.py"
  ]
}
```

Click **OK** and restart IntelliJ. MCP tools are only available when the **Codebase** toggle is enabled in the AI Assistant chat window.

### Installing uv on Windows

Do not use the snap installer. Use the official PowerShell installer:
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:
```cmd
uv --version
```

### Installing Python on Windows

Download from python.org and ensure **Add Python to PATH** is checked during installation. Verify:
```cmd
python --version
```

### Installing Node.js on Windows (for MCP Inspector)

Download the LTS installer from nodejs.org. Verify:
```cmd
node --version
npm --version
```

### Cloning and installing on Windows
```cmd
git clone https://github.com/pastrycak3s/mcps.git
cd mcps\python\confluence
uv sync
copy env-example .env
```

Edit `.env` with your credentials using Notepad or any text editor.
