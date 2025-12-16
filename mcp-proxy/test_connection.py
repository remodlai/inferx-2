"""
Test FastMCP proxy connection and list available tools
"""
import asyncio
from mcp.client.sse import sse_client
from mcp import ClientSession

async def test_proxy():
    """Test connection to FastMCP SSE proxy and list tools"""

    # Connect to the proxy
    url = "http://mcp-proxy:8080/sse"

    print(f"Connecting to FastMCP proxy at {url}...")

    async with sse_client(url=url) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the session
            print("Initializing MCP session...")
            init_result = await session.initialize()
            print(f"Initialized: {init_result.serverInfo.name} v{init_result.serverInfo.version}")

            # List available tools
            print("\nListing tools from backend...")
            tools_result = await session.list_tools()

            print(f"\nFound {len(tools_result.tools)} tools:")
            for tool in tools_result.tools:
                print(f"  - {tool.name}: {tool.description}")

            return tools_result.tools

if __name__ == "__main__":
    asyncio.run(test_proxy())
