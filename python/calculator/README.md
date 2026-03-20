# Calculator MCP Server

A simple MCP (Model Context Protocol) server written in Python that exposes basic arithmetic tools to AI assistants. Built as a learning project to understand MCP server development.

> **Platform:** Assumes a Linux filesystem and OS. Instructions and paths may not work as-is on macOS or Windows.

## What is MCP?

MCP is an open protocol that allows AI assistants to interact with external tools and data sources in a standardized way. Instead of HTTP endpoints, you define Python functions decorated as tools. The AI decides when to call them based on context and the tool descriptions you provide.

For stdio transport (used here), the MCP host (e.g. Copilot CLI) spawns your server as a child process and communicates via stdin/stdout using JSON-RPC 2.0 messages. There is no port, no socket, and no HTTP — just a process reading from stdin and writing to stdout.

## Tools

- `add(a, b)` — adds two numbers together
- `subtract(a, b)` — subtracts b from a

## Dependencies

- **Python 3.10+** — tested on 3.12.3
- **uv** — Python project and package manager (replaces pip + venv)
- **mcp[cli] 1.26.0+** — the official Anthropic MCP Python SDK, which includes FastMCP

## Installation

### 1. Install Python

On Ubuntu:
```bash
sudo apt install python3
```

Verify:
```bash
python3 --version
```

### 2. Install uv

Do not use the snap package. Use the official installer:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then reload your shell:
```bash
source ~/.bashrc
```

Verify:
```bash
uv --version
```

### 3. Clone the repo and navigate to this server
```bash
git clone https://github.com/pastrycak3s/mcps.git
cd mcps/python/calculator
```

### 4. Install dependencies
```bash
uv add mcp[cli]
```

This creates a `.venv` scoped to this project and installs the MCP SDK into it.

## Testing with MCP Inspector

The MCP Inspector lets you test your server without needing an AI client. It runs a local web UI where you can manually invoke tools and inspect responses.

Start the inspector:
```bash
uv run mcp dev main.py
```

Then open the URL printed in the terminal in your browser (typically `http://localhost:6274`). Click **Connect**, navigate to the **Tools** tab, and invoke `add` or `subtract` with your chosen arguments.

Stop the inspector with `Ctrl+C` before connecting via Copilot CLI.

## Configuration with Copilot CLI

Copilot CLI reads MCP server config from `~/.copilot/mcp-config.json`. Add the following entry:
```json
{
  "mcpServers": {
    "calculator": {
      "type": "stdio",
      "command": "/home/your-username/.local/bin/uv",
      "args": [
        "run",
        "--project", "/home/your-username/projects/mcps/python/calculator",
        "python", "/home/your-username/projects/mcps/python/calculator/main.py"
      ]
    }
  }
}
```

Replace `your-username` with your actual username. The full path to `uv` is required because Copilot CLI spawns the process without your full user PATH. Find your `uv` path with `which uv`.

The `--project` flag is required so `uv` can locate the correct `.venv` regardless of what working directory Copilot uses when spawning the process.

After editing the config, restart Copilot CLI with `/restart` and verify the server connected with `/mcp`.

## Usage

Once connected, ask Copilot naturally:
```
use the calculator tool to add 10 and 25
```

or just:
```
what is 17 plus 8
```

Copilot will recognize the available tools and invoke them automatically based on context.

## Notes

- Pyright may show an `unknown symbol` warning on the `FastMCP` import. This is a type stub gap in the `mcp` package and does not affect runtime behavior.
- The long traceback printed when you `Ctrl+C` the server is expected — it is the async event loop unwinding on interrupt, not an error.
- The MCP Inspector must be stopped before connecting via Copilot CLI, as both need to spawn your server process.
