import os
import sys
import json
import asyncio
from contextlib import AsyncExitStack
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import logging
logger = logging.getLogger(__name__)
load_dotenv()

# Pick a current model you have access to (examples: "gpt-4.1-mini", "gpt-4o-mini")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

class OpenAIMCPClient:
    def __init__(self):
        self._stack = AsyncExitStack()
        self.session: Optional[ClientSession] = None
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.messages = []  # running chat transcript

    async def connect(self, server_path: str):
        # Decide how to run the server (python or node)
        cmd = "python" if server_path.endswith(".py") else "node"
        params = StdioServerParameters(command=cmd, args=[server_path], env=None)

        # Establish stdio transport and MCP session
        stdio, write = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(ClientSession(stdio, write))
        await self.session.initialize()

        # Show available tools from the server
        tools_meta = await self.session.list_tools()
        print("Connected. Tools:", [t.name for t in tools_meta.tools])

    async def list_tools_as_openai_schemas(self):
        """
        Convert MCP tool metadata to OpenAI function-calling schema.
        """
        tools_meta = await self.session.list_tools()
        tools = []
        for t in tools_meta.tools:
            # t.inputSchema is already JSON Schema for inputs
            tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.inputSchema or {"type": "object", "properties": {}},
                },
            })
        return tools

    async def run_chat_turn(self, user_text: str):
        """
        Send user text to OpenAI with server tools advertised.
        Handle tool calls: execute via MCP, then feed results back, and get final answer.
        """
        if not self.session:
            raise RuntimeError("MCP session not initialized")

        self.messages.append({"role": "user", "content": user_text})

        # Advertise the server's tools to the model
        tools = await self.list_tools_as_openai_schemas()

        # First assistant call (may request tools)
        completion = self.openai.chat.completions.create(
            model=OPENAI_MODEL,
            messages=self.messages,
            tools=tools,
            tool_choice="auto",
        )

        choice = completion.choices[0]
        msg = choice.message
        tool_calls = getattr(msg, "tool_calls", None)

        # If the model requested tool calls, execute them via MCP
        if tool_calls:
            # Append assistant message that issued tool calls
            self.messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                } for tc in tool_calls
            ]})

            # Execute each tool call and append results
            for tc in tool_calls:
                name = tc.function.name
                try:
                    print(f"\n[Calling tool {name} with args: {tc.function.arguments}]")
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = await self.session.call_tool(name, args)

                # Send tool result back to the model
                
                try:   
                    print(result.content[0].text)
                except:
                    print("failed to print dict")
                
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result.content[0].text),
                })

            # Ask the model again, now that it has tool results
            completion2 = self.openai.chat.completions.create(
                model=OPENAI_MODEL,
                messages=self.messages,
            )
            final_text = completion2.choices[0].message.content or ""
            print("\nAssistant:\n" + final_text)
            self.messages.append({"role": "assistant", "content": final_text})
            return

        # No tool calls—just print the assistant text
        final_text = msg.content or ""
        print("\nAssistant:\n" + final_text)
        self.messages.append({"role": "assistant", "content": final_text})

    async def repl(self):
        print("\nMCP x OpenAI client ready. Type 'quit' to exit.")
        while True:
            q = input("\nYou: ").strip()
            if q.lower() in {"quit", "exit"}:
                break
            await self.run_chat_turn(q)

    async def close(self):
        await self._stack.aclose()

async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run client_openai.py <path_to_mcp_server_script>")
        sys.exit(1)

    client = OpenAIMCPClient()
    try:
        await client.connect(sys.argv[1])
        await client.repl()
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
