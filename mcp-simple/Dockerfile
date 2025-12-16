FROM python:3.12

WORKDIR /app

# Install FastMCP and MCP
RUN pip install --no-cache-dir fastmcp mcp

# Copy FastMCP server
COPY simple_server.py .

# Expose port
EXPOSE 8080

# Run the FastMCP server
CMD ["python", "simple_server.py"]
