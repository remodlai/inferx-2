"""
Simple SSE MCP Server for vLLM Testing

A minimal MCP server with one test tool to verify vLLM's SSE transport.
"""

from fastmcp import FastMCP
from starlette.responses import PlainTextResponse

# Create simple MCP server
mcp = FastMCP(name="SimpleTestServer")

@mcp.tool()
def test_tool(name: str) -> str:
    """
    Test tool that returns a confirmation message.

    Args:
        name: The name to include in the confirmation message

    Returns:
        A confirmation message with the provided name
    """
    return f"Test confirmed for: {name}"

# Add health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint for Kubernetes probes"""
    return PlainTextResponse("OK", status_code=200)

# Add test HTML page to verify ingress routing
@mcp.custom_route("/test-page", methods=["GET"])
async def test_page(request):
    """Test HTML page to verify ingress routing"""
    from starlette.responses import HTMLResponse
    return HTMLResponse("<html><body><h1>Ingress routing works!</h1><p>Path: /test-page</p></body></html>")

if __name__ == "__main__":
    # Run as SSE server for vLLM compatibility
    mcp.run(transport="sse", host="0.0.0.0", port=8080)
