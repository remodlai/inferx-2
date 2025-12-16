"""
FastMCP HTTP-to-SSE Transport Bridge

This proxy exposes a remote HTTP MCP server via SSE transport,
allowing vLLM to connect to it using --tool-server.

Backend: HTTP MCP server (Firecrawl)
Frontend: SSE endpoint for vLLM
"""

from fastmcp import FastMCP
from fastmcp.server.proxy import StatefulProxyClient, FastMCPProxy
from starlette.responses import PlainTextResponse

# Create stateful proxy client for SSE (maintains sessions across requests)
stateful_client = StatefulProxyClient("https://mcp.firecrawl.dev/FIRECRAWL_API_KEY/v2/mcp")

# Create proxy using stateful client factory (keeps sessions alive)
remote_proxy = FastMCPProxy(
    client_factory=stateful_client.new_stateful,
    name="firecrawl",
    instructions="exposes the firecrawl mcp tools, enabling web search, url scraping.",
)

# Add health check endpoint
@remote_proxy.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Kubernetes probes"""
    return PlainTextResponse("OK", status_code=200)

if __name__ == "__main__":
    # Run as SSE server for vLLM compatibility
    remote_proxy.run(transport="sse", host="0.0.0.0", port=8080)
