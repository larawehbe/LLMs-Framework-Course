
import asyncio
from agno.agent import Agent
from agno.tools.mcp import MCPTools
from dotenv import load_dotenv
from agno.models.openai import OpenAIChat
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)
import nest_asyncio
import os 
load_dotenv()
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Allow nested event loops
nest_asyncio.apply()


async def run_agent(query: str):
    
    
    async with MCPTools("npx -y @openbnb/mcp-server-airbnb --ignore-robots-txt") as mcp_tools1:
  
    
        try:
            agent = Agent(model=OpenAIChat(id="gpt-4o"), tools=[mcp_tools1], markdown=True, show_tool_calls=True, debug_mode=True)
            await agent.aprint_response("Please use the provided tools and answer the query and also show the exact Tools used: " + query, stream=True)
            
            
        except Exception as ex:
            print(ex)
            


if __name__ == "__main__":      
    query = input("Query: ")
    asyncio.run(run_agent(query))

    

      