FROM python:3.12-slim

WORKDIR /app

# Install FastMCP
RUN pip install --no-cache-dir fastmcp

# Copy proxy server
COPY proxy_server.py .

# Expose SSE port
EXPOSE 8080

# Run the proxy
CMD ["python", "proxy_server.py"]
