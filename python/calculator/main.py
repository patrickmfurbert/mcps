from mcp.server.fastmcp import FastMCP   

mcp = FastMCP("calculator")

@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers together"""
    return a + b

@mcp.tool()
def subtract(a: float, b: float) -> float:
    """Subtract two numbers"""
    return a - b

if __name__ == "__main__":
    mcp.run()
