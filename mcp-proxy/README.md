# FastMCP HTTP-to-SSE Transport Bridge

## Overview

This proxy bridges HTTP MCP servers to SSE transport, enabling vLLM to connect to HTTP-based MCP servers.

## Architecture

```
[vLLM: --tool-server mcp.remodl.ai:443]
    ↓ (vLLM adds /sse internally)
[FastMCP Proxy: SSE endpoint at mcp.remodl.ai/sse]
    ↓ (Proxy converts SSE → HTTP)
[Backend: Firecrawl HTTP MCP at https://mcp.firecrawl.dev/.../v2/mcp]
```

## Build and Deploy

```bash
# Build the image
cd /Users/brianbagdasarian/projects/inferx-2/mcp-proxy
docker build -t remodlai/mcp-proxy:latest .

# Push to registry
docker push remodlai/mcp-proxy:latest

# Deploy to Kubernetes (choose cluster)
kubectl --context inferx apply -f deployment.yaml
# OR
kubectl --context remodl-cluster apply -f deployment.yaml

# Verify deployment
kubectl --context inferx get pods -l app=mcp-proxy
kubectl --context inferx get ingress mcp-proxy-ingress
```

## Testing with vLLM

```bash
# Start vLLM with MCP proxy
vllm serve meta-llama/Llama-3.2-1B-Instruct \
  --tool-server mcp.remodl.ai:443

# The proxy will:
# 1. Receive SSE requests from vLLM at https://mcp.remodl.ai/sse
# 2. Forward them as HTTP to Firecrawl MCP server
# 3. Return responses via SSE to vLLM
```

## Local Testing

```bash
# Run locally
python proxy_server.py

# Test SSE endpoint
curl http://localhost:8080/sse

# vLLM with local proxy
vllm serve meta-llama/Llama-3.2-1B-Instruct \
  --tool-server localhost:8080
```

## Monitoring

```bash
# Check logs
kubectl --context inferx logs -l app=mcp-proxy -f

# Check health
curl https://mcp.remodl.ai/health
```

## Configuration

- **Backend MCP Server**: `https://mcp.firecrawl.dev/fc-9ad2cc3f9da94ad2b56d031ebe8a70e6/v2/mcp`
- **Frontend Transport**: SSE on port 8080
- **Public URL**: `https://mcp.remodl.ai/sse`
- **vLLM Connection**: `mcp.remodl.ai:443` (vLLM adds `/sse`)
