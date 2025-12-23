# InferX Scheduler - Temporal Implementation

Python-based Scheduler using Temporal workflows, replacing Rust implementation.

## Overview

Scheduler manages pod placement and lifecycle for InferX model deployments.

**Architecture:**
```
Gateway (Rust gRPC) → Scheduler gRPC Server (port 1238) → Temporal Workflow
                      ↓                                   ↓
                   na.proto                         SchedulerWorkflow
                      ↓                                   ↓
        Activities → NodeAgent gRPC               Durable state
```

## Operations

- `ConnectScheduler` - Gateway registration
- `LeaseWorker` - Get pod for inference request
- `ReturnWorker` - Release pod back to pool
- `RefreshGateway` - Gateway heartbeat

## Dependencies

- `inferx-common` - Shared models (NodeInfo, Function, etc.)
- StateSvc workflow - Queries for nodes and functions

## Deployment

Deploy to **inferx cluster** (same as NodeAgent) so activities can reach NodeAgent via cluster networking.

```bash
# Build
./build.sh v0.1.0

# Push
docker push remodlai/inferx-scheduler:v0.1.0

# Deploy
kubectl apply -f k8s/
```

## Configuration

Configured via environment variables:
- `TEMPORAL_TARGET_HOST` - Temporal server address
- `TEMPORAL_NAMESPACE` - Namespace (inferx)
- `SCHEDULER_PORT` - gRPC server port (1238)
