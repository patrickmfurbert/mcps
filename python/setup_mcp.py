import os
import sys
import subprocess
from pathlib import Path


def prompt(label: str, default: str = "") -> str:
    if default:
        value = input(f"{label} [{default}]: ").strip()
        return value if value else default
    value = input(f"{label}: ").strip()
    return value


def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_mcp.py <server-name>")
        sys.exit(1)

    name = sys.argv[1].lower().strip()
    base_dir = Path(__file__).parent
    server_dir = base_dir / name

    if server_dir.exists():
        print(f"Directory '{server_dir}' already exists. Aborting.")
        sys.exit(1)

    print(f"\nSetting up MCP server: {name}")
    print("-" * 40)

    # Collect env vars
    env_vars = []
    print("\nDefine environment variables for env-example.")
    print("Press Enter with no name to finish.\n")
    while True:
        var_name = input("Env var name (e.g. JIRA_URL): ").strip().upper()
        if not var_name:
            break
        var_description = input(f"Placeholder value for {var_name}: ").strip()
        env_vars.append((var_name, var_description))

    if not env_vars:
        print("No env vars defined. Aborting.")
        sys.exit(1)

    # Create directory
    server_dir.mkdir(parents=True)
    print(f"\nCreated {server_dir}")

    # uv init
    print("Running uv init...")
    subprocess.run(["uv", "init"], cwd=server_dir, check=True)

    # uv add dependencies
    print("Installing dependencies...")
    subprocess.run(
        ["uv", "add", "mcp[cli]", "python-dotenv", "httpx", "truststore"],
        cwd=server_dir,
        check=True,
    )

    # pyrightconfig.json
    pyrightconfig = server_dir / "pyrightconfig.json"
    pyrightconfig.write_text(
        '{\n  "venvPath": ".",\n  "venv": ".venv"\n}\n'
    )
    print("Created pyrightconfig.json")

    # env-example
    env_example = server_dir / "env-example"
    env_lines = "\n".join(f"{var}={placeholder}" for var, placeholder in env_vars)
    env_example.write_text(env_lines + "\n")
    print("Created env-example")

    # main.py
    log_path = f"/tmp/{name}-mcp.log"
    env_getenv_lines = "\n".join(
        f'{var} = os.getenv("{var}", "")'
        for var, _ in env_vars
    )
    env_log_lines = "\n".join(
        f'logger.info(f"{var}: {{{var}}}")'
        for var, _ in env_vars
    )

    main_py = server_dir / "main.py"
    main_py.write_text(f"""import os
import logging
import httpx
import truststore
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Any

truststore.inject_into_ssl()
load_dotenv()

{env_getenv_lines}

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("{log_path}"),
    ]
)
logger = logging.getLogger(__name__)

logger.info("Starting {name} MCP server")
{env_log_lines}

mcp = FastMCP("{name}")


def get_headers() -> dict:
    return {{
        "Content-Type": "application/json",
        "Accept": "application/json",
    }}


async def get(path: str, params: dict[str, Any] = {{}}) -> dict:
    url = f"{{API_BASE}}{{path}}"
    logger.debug(f"GET {{url}} params={{params}}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=get_headers(),
                params=params,
            )
            logger.debug(f"GET {{url}} status={{response.status_code}}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"GET {{url}} HTTP error: {{e.response.status_code}} {{e.response.text}}")
        raise
    except Exception as e:
        logger.error(f"GET {{url}} error: {{e}}")
        raise


async def post(path: str, body: Any = {{}}) -> dict:
    url = f"{{API_BASE}}{{path}}"
    logger.debug(f"POST {{url}} body={{body}}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=get_headers(),
                json=body,
            )
            logger.debug(f"POST {{url}} status={{response.status_code}}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"POST {{url}} HTTP error: {{e.response.status_code}} {{e.response.text}}")
        raise
    except Exception as e:
        logger.error(f"POST {{url}} error: {{e}}")
        raise


async def put(path: str, body: Any = {{}}) -> dict:
    url = f"{{API_BASE}}{{path}}"
    logger.debug(f"PUT {{url}} body={{body}}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers=get_headers(),
                json=body,
            )
            logger.debug(f"PUT {{url}} status={{response.status_code}}")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"PUT {{url}} HTTP error: {{e.response.status_code}} {{e.response.text}}")
        raise
    except Exception as e:
        logger.error(f"PUT {{url}} error: {{e}}")
        raise


if __name__ == "__main__":
    logger.info("MCP server starting stdio loop")
    mcp.run()
""")
    print("Created main.py")

    # README.md
    readme = server_dir / "README.md"
    readme.write_text(f"# {name.capitalize()} MCP Server\n")
    print("Created README.md")

    print(f"""
Setup complete. Next steps:

  cd {server_dir}
  cp env-example .env
  # edit .env with your real credentials
  nvim main.py
  # define your API_BASE and add tools
""")


if __name__ == "__main__":
    main()
