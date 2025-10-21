# math_server.py
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Math") #creates a new MCP server instance named "Math"

@mcp.tool() #decorator to register a function as a tool
def add(a: int, b: int) -> int: 
    """
    You define a Python function add that takes two integers and returns their sum.
    By decorating it with @mcp.tool(), you’re saying:
    “This is not just a Python function, it’s an MCP tool exposed to clients.”
    The docstring (\"\"\"Add two numbers\"\"\") becomes the tool description in the manifest.
    The type hints (a: int, b: int -> int) are converted into JSON Schema automatically, so the client knows exactly what inputs/outputs are valid.
    """
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two numbers"""
    return a * b



@mcp.tool()
def subtract(a: int, b: int) -> int:
    """Subtract two numbers"""
    return a - b


@mcp.tool()
def search_web(query: str) -> str:
    """Search the web for information"""
  
    return f"Search results for '{query}': [Placeholder for web search results]"

if __name__ == "__main__":
    """
    transport="stdio" means:
    The server will read/write JSON-RPC messages via standard input/output.
    That’s the normal way MCP clients (like Claude Desktop or a LangChain bridge) talk to servers: they spawn the process and communicate over stdio.
    """
    mcp.run(transport="stdio")