# main_agno_math.py
import os
import asyncio

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.mcp import MCPTools

from dotenv import load_dotenv
load_dotenv()
# Ensure your OPENAI_API_KEY is set in the environment
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")  


# Point to your local MCP server command (stdio transport)
MATH_SERVER_CMD = "python math_server.py"

async def main():
    # Spin up MCPTools as an async context manager.
    # Agno will spawn your server process and talk over stdio.
    async with MCPTools(
        command=MATH_SERVER_CMD,
        env=os.environ.copy(),        # inherit env if you need any vars
        timeout_seconds=60            # tweak as you like
    ) as mcp_tools:

        # Build an Agent and give it the MCP tools
        agent = Agent(
            model=OpenAIChat(id="gpt-4o"),
            markdown=True,
            tools=[mcp_tools],
            instructions=(
                "Use the Math MCP tools when arithmetic is needed. "
                "Prefer calling the 'add' or 'multiply' tools rather than doing math in your head."
            ),
        )

        # Ask something that should trigger tool calls to your server
        prompt = "Compute (12 * 7) + (3 * 5) using the MCP tools and show steps."
        await agent.aprint_response(prompt, stream=True)

if __name__ == "__main__":
    asyncio.run(main())
