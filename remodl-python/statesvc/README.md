# InferX StateSvc - Temporal Implementation

Python-based StateSvc using Temporal workflows, replacing Rust implementation.

## Architecture

```
IxProxy (Rust gRPC) → Python gRPC Server (port 1237) → Temporal Workflow
                      ↓                                 ↓
                   ixmeta.proto                    StateSvcWorkflow
                      ↓                                 ↓
                  Containerized                    Durable state
```

**Single process runs:**
1. Temporal worker (polls `statesvc-tasks` queue)
2. gRPC server (port 1237, implements `ixmeta.proto`)

## Quick Start

### 1. Install Dependencies

```bash
uv pip install -e .
```

### 2. Start Singleton Workflow

```bash
python -m src.starter
```

### 3. Run Worker + gRPC Server

```bash
python -m src.main
```

## Testing

```bash
# Test direct workflow calls
python -m src.test_statesvc

# Verify PostgreSQL data
psql "$DATABASE_URL" -c "SELECT * FROM inferx.tenants"
```

## Build & Deploy

### Build Docker Image

```bash
chmod +x build.sh
./build.sh v0.2.0
```

Or manually:
```bash
docker buildx build --platform linux/amd64 -t remodlai/inferx-statesvc:latest .
```

### Push to Registry

```bash
docker push remodlai/inferx-statesvc:latest
```

### Deploy to Kubernetes

```bash
# Create secret
kubectl apply -f k8s/secret.yaml

# Create configmap
kubectl apply -f k8s/configmap.yaml

# Deploy StateSvc
kubectl apply -f k8s/deployment.yaml

# Create service
kubectl apply -f k8s/service.yaml
```

### Verify Deployment

```bash
# Check pod status
kubectl --context inferx get pods -l app=statesvc-temporal

# Check logs
kubectl --context inferx logs -l app=statesvc-temporal -f

# Check service
kubectl --context inferx get svc statesvc-temporal
```

## Configuration

### Environment Variables

Configured via ConfigMap (`k8s/configmap.yaml`):

```yaml
TEMPORAL_TARGET_HOST: "flow.remodl.ai:443"
TEMPORAL_NAMESPACE: "inferx"
TEMPORAL_TLS: "true"
TEMPORAL_TASK_QUEUE: "statesvc-tasks"
STATESVC_PORT: "1237"
LOG_LEVEL: "INFO"
```

### Secrets

Database URL in Secret (`k8s/secret.yaml`):

```yaml
DATABASE_URL: "postgresql://..."
```

## Migration from Rust StateSvc

### Step 1: Deploy Alongside

Deploy Python StateSvc as `statesvc-temporal` service (doesn't conflict with existing `statesvc`).

### Step 2: Test Compatibility

Point one IxProxy to new service:
```yaml
env:
  - name: STATESVC_ADDR
    value: "http://statesvc-temporal:1237"
```

### Step 3: Cutover

Update all IxProxy/NodeAgent pods to use new service.

### Step 4: Remove Old StateSvc

```bash
kubectl delete deployment statesvc -n inferx
kubectl delete svc statesvc -n inferx
```

## Development

### Project Structure

```
statesvc/
├── pyproject.toml           # Dependencies
├── Dockerfile               # Container image
├── build.sh                 # Build script
├── proto/
│   └── ixmeta.proto         # gRPC service definition
├── src/
│   ├── dataclasses.py       # Pydantic models
│   ├── activities/          # Database operations
│   │   ├── tenant.py
│   │   ├── namespace.py
│   │   ├── function.py
│   │   ├── function_status.py
│   │   ├── node.py
│   │   └── shared.py        # DB connection
│   ├── workflows.py         # StateSvcWorkflow
│   ├── grpc_server.py       # gRPC servicer
│   ├── main.py              # Entry point (worker + gRPC)
│   ├── worker.py            # Standalone worker
│   ├── starter.py           # Launch singleton
│   └── generated/           # Proto-generated code
│       ├── ixmeta_pb2.py
│       └── ixmeta_pb2_grpc.py
└── k8s/
    ├── configmap.yaml
    ├── secret.yaml
    ├── deployment.yaml
    └── service.yaml
```

### Regenerate Proto Code

If `ixmeta.proto` changes:

```bash
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./src/generated \
    --grpc_python_out=./src/generated \
    proto/ixmeta.proto
```

## Database Schema

Tables in `inferx` schema (Neon PostgreSQL):

- `tenants` - Tenant definitions
- `namespaces` - Namespace definitions
- `functions` - Model deployment specifications
- `function_status` - Deployment state tracking
- `nodes` - GPU worker registrations
- `userrole` - User role assignments
- `apikey` - API keys

## Operations

StateSvc implements all operations from Rust version:

**Updates (writes):**
- Tenant: create, delete
- Namespace: create, update, delete
- Function: create, update, delete
- Function Status: update
- Node: register, update_state, delete

**Queries (reads):**
- Tenant: get, list
- Namespace: get, list
- Function: get, list
- Function Status: get, list
- Node: get, list
- Utility: version, get_addr, uid

## Monitoring

### Temporal Web UI

View workflow state: https://flow.remodl.ai/admin/

- Search for workflow ID: `statesvc-singleton`
- See all updates/queries
- View execution history

### Logs

```bash
kubectl --context inferx logs -l app=statesvc-temporal --tail=100 -f
```

### Health Check

```bash
# TCP check (gRPC server running)
nc -zv statesvc-temporal.inferx.svc 1237

# Query version via gRPC
grpcurl -plaintext statesvc-temporal.inferx.svc:1237 ixmeta.IxMetaService/Version
```

## Troubleshooting

### Worker not connecting to Temporal

Check logs for connection errors:
```bash
kubectl logs -l app=statesvc-temporal | grep -i "error\|failed"
```

Verify Temporal endpoint is accessible from pod:
```bash
kubectl exec -it deployment/statesvc-temporal -- nc -zv flow.remodl.ai 443
```

### gRPC server not responding

Check if port 1237 is listening:
```bash
kubectl exec -it deployment/statesvc-temporal -- netstat -ln | grep 1237
```

### Database connection errors

Verify DATABASE_URL secret is correct:
```bash
kubectl get secret statesvc-secrets -o jsonpath='{.data.database-url}' | base64 -d
```

Test connection from pod:
```bash
kubectl exec -it deployment/statesvc-temporal -- python -c "import asyncpg; asyncio.run(asyncpg.connect('$DATABASE_URL'))"
```

### Workflow not found

Start the singleton workflow:
```bash
python -m src.starter
```

Verify it's running:
```bash
temporal workflow describe --workflow-id statesvc-singleton --env remodl
```
