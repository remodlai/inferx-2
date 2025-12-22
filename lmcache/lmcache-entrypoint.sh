#!/bin/bash
# LMCache entrypoint wrapper for InferX DIND containers
# This script sets LMCache environment variables before launching vLLM
# Mount location: /opt/inferx/cache/lmcache-entrypoint.sh (host) → /root/.cache/huggingface/lmcache-entrypoint.sh (container)

# LMCache Configuration
export LMCACHE_CONFIG_FILE=/root/.cache/huggingface/lmcache-config.yaml
export LMCACHE_USE_EXPERIMENTAL=True
export PYTHONHASHSEED=0

# Launch vLLM with all arguments passed through
exec /opt/venv/bin/vllm serve "$@"
