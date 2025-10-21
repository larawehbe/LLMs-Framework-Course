import asyncio
from pathlib import Path
from textwrap import dedent

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools
from mcp import StdioServerParameters


async def run_mcp_agent(message: str) -> None:
    """Run the filesystem agent with the given message."""

    file_path = str(Path(__file__).parent.parent.parent.parent)

    # Initialize the MCP tools
    mcp_tools = MCPTools(f"npx -y @modelcontextprotocol/server-filesystem {file_path}")

    # Connect to the MCP server
    await mcp_tools.connect()

    # Use the MCP tools with an Agent
    agent = Agent(
        model=OpenAIChat(id="gpt-4o"),
        tools=[mcp_tools],
        instructions=dedent("""\
            You are a filesystem assistant. Help users explore files and directories.

            - Navigate the filesystem to answer questions
            - Use the list_allowed_directories tool to find directories that you can access
            - Provide clear context about files you examine
            - Use headings to organize your responses
            - Be concise and focus on relevant information\
        """),
        markdown=True,
        show_tool_calls=True,
    )

    # Run the agent
    await agent.aprint_response(message, stream=True)

    # Close the MCP connection
    await mcp_tools.close()


# Example usage
if __name__ == "__main__":
    # Basic example - exploring project license
    asyncio.run(run_mcp_agent("What is the license for this project?"))