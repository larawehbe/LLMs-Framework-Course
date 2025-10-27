from dotenv import load_dotenv
load_dotenv()
# Ensure your OPENAI_API_KEY is set in the environment
import os
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")  


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
    mcp_tools = MCPTools(f"python3 ../mcp-live-coding/math_server.py")

    # Connect to the MCP server


    # Use the MCP tools with an Agent
    agent = Agent(
        model=OpenAIChat(id="gpt-4o"),
        tools=[mcp_tools],
        instructions=dedent("""\
            You are a an assistant. help users with what they ask for 

            - Use headings to organize your responses
            - Be concise and focus on relevant information\
        """),
        markdown=True,
    )

    # Run the agent
    await agent.aprint_response(message, stream=True)

    # Close the MCP connection
    await mcp_tools.close()


# Example usage
if __name__ == "__main__":
    # Basic example - exploring project license
    asyncio.run(run_mcp_agent("1 + 1 ? "))