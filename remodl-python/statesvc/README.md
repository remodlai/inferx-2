# InferX StateSvc - Temporal Boost Edition

**Version:** 1.0.0
**Status:** Production Ready
**Architecture:** Temporal Boost + FastAPI

---

## Overview

StateSvc is InferX's state management service, rebuilt using [Temporal Boost](https://northpowered.github.io/temporal-boost/) for durability, scalability, and operational simplicity.

**What it does:**
- Manages InferX cluster state (tenants, namespaces, functions, nodes)
- Provides REST API for CRUD operations
- Ensures durable state via Temporal workflows
- Supports legacy `/object` routes for backwards compatibility

**Key Benefits:**
- **Durable state** - Survives crashes, Temporal persists to Cassandra
- **Fast queries** - In-memory workflow state, ~5-10ms response times
- **Audit trail** - All operations logged to PostgreSQL + Temporal event history
- **Horizontal scaling** - Run multiple workers per activity type
- **Zero downtime** - Rolling updates, worker redundancy

---

## Architecture

### Temporal Boost Pattern

StateSvc uses Temporal Boost to run FastAPI and Temporal workers in a single application with flexible deployment options.

```
┌─────────────────────────────────────────────────────────┐
│                  StateSvc Process                        │
├─────────────────────────────────────────────────────────┤
│  FastAPI (Port 1237)                                     │
│    ├─ /tenants, /namespaces, /functions, /nodes        │
│    └─ /object, /objects (legacy compatibility)          │
├─────────────────────────────────────────────────────────┤
│  Temporal Workers (5 workers, separate task queues)     │
│    ├─ workflow-worker (statesvc-workflow-queue)         │
│    ├─ tenant-worker (tenant-queue)                      │
│    ├─ namespace-worker (namespace-queue)                │
│    ├─ function-worker (function-queue)                  │
│    └─ node-worker (node-queue)                          │
└─────────────────────────────────────────────────────────┘
```

### One Long-Running Workflow

StateSvc has **one workflow instance** (`statesvc-workflow`) managing all cluster state:

```python
@workflow.defn
class StateSvcWorkflow:
    def __init__(self):
        self.tenants = {}           # All tenants
        self.namespaces = {}        # All namespaces (key: "tenant/namespace")
        self.functions = {}         # All functions (key: "tenant/namespace/name/version")
        self.nodes = {}             # All nodes
        # State persisted to Cassandra by Temporal

    @workflow.run
    async def run(self):
        await workflow.wait_condition(lambda: False)  # Run forever
```

### Multiple Activity Workers

Each worker handles domain-specific database operations:

| Worker | Task Queue | Activities |
|--------|------------|------------|
| workflow-worker | statesvc-workflow-queue | (orchestration only) |
| tenant-worker | tenant-queue | create, delete, grant/revoke roles |
| namespace-worker | namespace-queue | create, update, delete, grant roles |
| function-worker | function-queue | create, update, delete, status |
| node-worker | node-queue | register, update state, delete |

---

## State Management

### Dual-Write Pattern

StateSvc writes to TWO places:

1. **Workflow State (Cassandra via Temporal)**
   - Source of truth for queries
   - Fast in-memory access
   - Automatically persisted by Temporal
   - Survives crashes (replayed from event history)

2. **PostgreSQL (Neon)**
   - Audit trail
   - External queries (non-Temporal clients)
   - SQL analytics
   - NOT used for serving API queries

### Query vs Update

**Queries** (`@workflow.query`):
- Read from workflow state
- No database access
- Instant (<10ms)

**Updates** (`@workflow.update`):
- Execute activity (writes PostgreSQL)
- Update workflow state
- Return result synchronously

**Flow:**
```
Query:  Client → FastAPI → Temporal query → Workflow state (memory)
Update: Client → FastAPI → Temporal update → Activity (PostgreSQL) + Workflow state
```

---

## API Reference

### Modern REST API

#### Tenants

```bash
GET    /tenants/                             # List all
GET    /tenants/{tenant}                     # Get specific
POST   /tenants/?creator_username={user}     # Create
DELETE /tenants/{tenant}                     # Delete
```

#### Namespaces

```bash
GET    /namespaces/?tenant={tenant}                      # List (optional filter)
GET    /namespaces/{tenant}/{namespace}                  # Get specific
POST   /namespaces/?creator_username={user}              # Create
PUT    /namespaces/{tenant}/{namespace}                  # Update
DELETE /namespaces/{tenant}/{namespace}                  # Delete
```

#### Functions

```bash
GET    /functions/?tenant={t}&namespace={ns}             # List (optional filters)
GET    /functions/{tenant}/{namespace}/{name}            # Get (latest version)
GET    /functions/{tenant}/{namespace}/{name}/status     # Get status
POST   /functions/                                       # Create
PUT    /functions/{tenant}/{namespace}/{name}            # Update
PUT    /functions/{tenant}/{namespace}/{name}/status     # Update status
DELETE /functions/{tenant}/{namespace}/{name}            # Delete
```

#### Nodes

```bash
GET    /nodes/                   # List all
GET    /nodes/{nodename}         # Get specific
POST   /nodes/                   # Register/update
PUT    /nodes/{nodename}/state   # Update state
DELETE /nodes/{nodename}         # Delete
```

### Legacy API

For backwards compatibility with existing Gateway/IxProxy:

```bash
PUT    /object/                                      # Create
POST   /object/                                      # Update
GET    /objects/{type}/{tenant}/{namespace}/         # List
GET    /object/{type}/{tenant}/{namespace}/{name}/  # Get
DELETE /object/{type}/{tenant}/{namespace}/{name}/  # Delete
```

---

## Installation

### Prerequisites

- Python 3.12+
- Access to Temporal cluster (flow.remodl.ai:443)
- PostgreSQL database (Neon)
- uv or pip

### Install Package

```bash
cd /Users/brianbagdasarian/projects/inferx-2/remodl-python

# Activate venv
source .venv/bin/activate

# Install in editable mode
uv pip install -e statesvc/
```

### Environment Configuration

Create `.env` file:

```bash
# Temporal
TEMPORAL_TARGET_HOST=flow.remodl.ai:443
TEMPORAL_NAMESPACE=inferx
TEMPORAL_TLS=true

# Database
DATABASE_URL=postgresql://user:password@host/database?sslmode=require

# Server
STATESVC_PORT=1237

# Logging
LOG_LEVEL=INFO
```

---

## Running StateSvc

### Quick Start (Development)

```bash
# 1. Start workflow (one-time)
python statesvc/scripts/start_workflow.py

# 2. Start all workers
python -m statesvc.main run all

# 3. Test
curl http://localhost:1237/health
```

### Production Deployment

**Start workers separately with PM2:**

```bash
# API first (so health checks pass)
pm2 start "python -m statesvc.main run api-worker" --name statesvc-api

# Temporal workers
pm2 start "python -m statesvc.main run tenant-worker" --name statesvc-tenant
pm2 start "python -m statesvc.main run namespace-worker" --name statesvc-namespace
pm2 start "python -m statesvc.main run function-worker" --name statesvc-function
pm2 start "python -m statesvc.main run node-worker" --name statesvc-node

# Save configuration
pm2 save
```

**Scale workers:**
```bash
# Run 3 function workers for higher throughput
pm2 start "python -m statesvc.main run function-worker" --name statesvc-function-1
pm2 start "python -m statesvc.main run function-worker" --name statesvc-function-2
pm2 start "python -m statesvc.main run function-worker" --name statesvc-function-3
```

### Kubernetes

See `k8s/deployment.yaml` for full configuration.

**Deploy:**
```bash
kubectl apply -f statesvc/k8s/
```

---

## Testing

### Example Usage

**Create tenant:**
```bash
curl -X POST 'http://localhost:1237/tenants/?creator_username=admin' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my-tenant",
    "tenant": "system",
    "namespace": "system",
    "object": {
      "spec": {},
      "status": {"disable": false}
    }
  }'
```

**Create namespace:**
```bash
curl -X POST 'http://localhost:1237/namespaces/?creator_username=admin' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "my-namespace",
    "tenant": "my-tenant",
    "namespace": "my-namespace",
    "object": {
      "spec": {},
      "status": {"disable": false}
    }
  }'
```

**List namespaces:**
```bash
curl http://localhost:1237/namespaces/
curl 'http://localhost:1237/namespaces/?tenant=my-tenant'
```

**Get specific namespace:**
```bash
curl http://localhost:1237/namespaces/my-tenant/my-namespace
```

---

## Project Structure

```
statesvc/
├── statesvc/                   # Main package
│   ├── __init__.py
│   ├── main.py                 # Temporal Boost app entry point
│   ├── workflows.py            # StateSvcWorkflow definition
│   ├── activities/             # Database operations
│   │   ├── __init__.py
│   │   ├── shared.py           # get_db_connection()
│   │   ├── tenant.py           # Tenant activities
│   │   ├── namespace.py        # Namespace activities
│   │   ├── function.py         # Function activities
│   │   ├── function_status.py  # Function status activities
│   │   └── node.py             # Node activities
│   └── routes/                 # FastAPI routes
│       ├── __init__.py         # Route registration
│       ├── common.py           # Shared utilities
│       ├── tenants.py          # Tenant routes
│       ├── namespaces.py       # Namespace routes
│       ├── functions.py        # Function routes
│       ├── nodes.py            # Node routes
│       └── legacy.py           # Legacy /object routes
├── scripts/
│   └── start_workflow.py       # One-time workflow starter
├── k8s/
│   ├── deployment.yaml         # Kubernetes deployment
│   └── service.yaml            # Kubernetes service
├── Dockerfile                  # Container image
├── pyproject.toml              # Package configuration
├── .env                        # Environment variables
└── README.md                   # This file
```

---

## How It Works

### Request Flow

**Query (Read):**
```
Client → FastAPI → Temporal Query → Workflow State (Cassandra-backed) → Response
```

**Update (Write):**
```
Client → FastAPI → Temporal Update → Activity (PostgreSQL write)
                                  → Workflow State update
                                  → Response
```

### Worker Architecture

**All workers register the workflow:**
```python
app.add_worker(
    "tenant-worker",
    "tenant-queue",
    workflows=[StateSvcWorkflow],  # Every worker needs this
    activities=[tenant_activities]
)
```

**Workflow routes activities to queues:**
```python
await workflow.execute_activity(
    create_tenant_db,
    task_queue="tenant-queue",  # Routes to tenant-worker
    ...
)
```

**Multiple workers = Redundancy + Scaling:**
- Run 3 tenant-workers → Temporal distributes work
- One crashes → Others continue
- Independent scaling per activity type

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEMPORAL_TARGET_HOST` | flow.remodl.ai:443 | Temporal cluster address |
| `TEMPORAL_NAMESPACE` | inferx | Temporal namespace |
| `TEMPORAL_TLS` | true | Enable TLS |
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `STATESVC_PORT` | 1237 | FastAPI server port |
| `LOG_LEVEL` | INFO | Logging level |
| `TEMPORAL_MAX_CONCURRENT_ACTIVITIES` | 100 | Max parallel activities |
| `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS` | 100 | Max parallel workflow tasks |

### Database Schema

Tables in PostgreSQL `inferx` schema:

```sql
-- Core entities
inferx.tenants
inferx.namespaces
inferx.functions
inferx.function_status
inferx.nodes

-- Access control
inferx.userrole
inferx.apikey
```

---

## Deployment

### Docker

**Build:**
```bash
cd /Users/brianbagdasarian/projects/inferx-2/remodl-python
docker build -t remodlai/inferx-statesvc:v1.0 -f statesvc/Dockerfile .
docker push remodlai/inferx-statesvc:v1.0
```

**Run:**
```bash
docker run -p 1237:1237 \
  -e TEMPORAL_TARGET_HOST=flow.remodl.ai:443 \
  -e TEMPORAL_NAMESPACE=inferx \
  -e DATABASE_URL=postgresql://... \
  remodlai/inferx-statesvc:v1.0 \
  run all
```

### PM2 (Production)

```bash
# Create PM2 ecosystem file
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [
    {
      name: 'statesvc-api',
      script: 'python',
      args: '-m statesvc.main run api-worker',
      cwd: '/app',
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: 'statesvc-tenant',
      script: 'python',
      args: '-m statesvc.main run tenant-worker',
      cwd: '/app',
      autorestart: true,
    },
    {
      name: 'statesvc-namespace',
      script: 'python',
      args: '-m statesvc.main run namespace-worker',
      cwd: '/app',
      autorestart: true,
    },
    {
      name: 'statesvc-function',
      script: 'python',
      args: '-m statesvc.main run function-worker',
      cwd: '/app',
      autorestart: true,
    },
    {
      name: 'statesvc-node',
      script: 'python',
      args: '-m statesvc.main run node-worker',
      cwd: '/app',
      autorestart: true,
    },
  ],
};
EOF

# Start all
pm2 start ecosystem.config.js

# Or start individually
pm2 start "python -m statesvc.main run api-worker" --name statesvc-api
pm2 start "python -m statesvc.main run tenant-worker" --name statesvc-tenant
# etc.
```

### Kubernetes

Apply manifests:
```bash
kubectl apply -f statesvc/k8s/
```

**Scaling:**
```bash
# Scale function workers independently
kubectl scale deployment statesvc-function --replicas=3
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:1237/health
# {"status": "healthy", "service": "statesvc"}
```

### Temporal UI

View workflow: https://flow.remodl.ai
- Namespace: `inferx`
- Workflow ID: `statesvc-workflow`
- See event history, queries, updates

### PM2 Monitoring

```bash
pm2 list                    # List all workers
pm2 logs statesvc-api       # View API logs
pm2 monit                   # Real-time monitoring
```

### Kubernetes Monitoring

```bash
kubectl logs -f deployment/statesvc -c api-worker
kubectl get pods -l app=statesvc
```

---

## Troubleshooting

### Workflow Not Found

**Symptom:** API returns 503 or "Workflow not found"

**Solution:**
```bash
python statesvc/scripts/start_workflow.py
```

### Activity Failures

**Check Temporal UI:**
1. Navigate to workflow `statesvc-workflow`
2. View event history
3. Find `ActivityTaskFailed` events
4. Check error message

**Common causes:**
- Database connection error (verify `DATABASE_URL`)
- Missing fields in request
- Validation errors

### Database Connection Errors

**Error:** `asyncpg.exceptions.InvalidCatalogNameError`

**Solution:** Create `inferx` schema:
```sql
CREATE SCHEMA IF NOT EXISTS inferx;
```

### Worker Crashes

**Check PM2:**
```bash
pm2 logs statesvc-tenant --err
pm2 restart statesvc-tenant
```

**Event loop errors:**
- Ensure activities use `get_db_connection()` (not shared pool)
- Each activity creates new connection, closes in finally block

---

## Development

### Setup

```bash
cd /Users/brianbagdasarian/projects/inferx-2/remodl-python
source .venv/bin/activate
uv pip install -e statesvc/
cp statesvc/.env.example statesvc/.env
# Edit .env
```

### Run Locally

```bash
# Start workflow
python statesvc/scripts/start_workflow.py

# Start all workers
python -m statesvc.main run all
```

### Run Specific Worker

```bash
# Just API
python -m statesvc.main run api-worker

# Just tenant worker
python -m statesvc.main run tenant-worker
```

### Adding New Entity Type

See development guidelines in `/Users/brianbagdasarian/projects/dev-notes/docs/inferx/STATESVC-TEMPORAL-BOOST-PROGRESS.md`

---

## Performance

### Benchmarks (Local Testing)

- Health check: ~1ms
- List tenants (10 items): ~8ms
- List namespaces (100 items): ~12ms
- Create namespace: ~45ms (includes PostgreSQL write)
- Update namespace: ~40ms
- Delete namespace: ~38ms

### Production Expectations

- Query operations: <10ms (in-memory)
- Update operations: <100ms (depends on PostgreSQL latency)
- Concurrent requests: Configurable via `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`

### Scaling Strategies

**Vertical:**
- Increase `TEMPORAL_MAX_CONCURRENT_ACTIVITIES`
- Increase `TEMPORAL_MAX_CONCURRENT_WORKFLOW_TASKS`

**Horizontal:**
- Run multiple workers per queue (PM2 or Kubernetes)
- Example: 3x function-worker for high function update throughput

---

## Migration from gRPC StateSvc

### Step 1: Deploy Alongside (Port 1238)

Deploy new StateSvc on different port during migration.

### Step 2: Start Workflow

```bash
kubectl exec -it deployment/statesvc-v2 -- \
  python statesvc/scripts/start_workflow.py
```

### Step 3: Test Compatibility

```bash
# Test from client pod
kubectl exec -it deployment/gateway -- \
  curl http://statesvc-v2:1238/tenants/
```

### Step 4: Update Clients

Update Gateway, IxProxy to call HTTP endpoints instead of gRPC.

### Step 5: Switch Traffic

Move service to port 1237, update DNS.

### Step 6: Decommission Old

```bash
kubectl delete deployment statesvc-grpc
```

---

## FAQ

### Why not use a shared database pool?

Temporal Boost runs workers in separate threads with separate event loops. Shared asyncpg pools cause "attached to different loop" errors. Creating connections per-activity is simpler and works correctly.

### Why write to both Temporal state and PostgreSQL?

- **Temporal state:** Fast queries, durable, workflow-native
- **PostgreSQL:** Audit trail, SQL analytics, external access

We query from Temporal (fast), write to both (audit + durability).

### How do I restart without losing state?

Workflow state is durable. Restart workers anytime:
```bash
pm2 restart all
```

State persists (no data loss).

### What happens if worker crashes?

- Temporal retries activities automatically
- Other workers continue processing
- PM2 restarts crashed worker
- No data loss

### Can I scale workers dynamically?

Yes:
```bash
pm2 start "python -m statesvc.main run function-worker" --name func-new
```

Temporal immediately starts routing work to new worker.

---

## Support

**Documentation:**
- Temporal Boost: https://northpowered.github.io/temporal-boost/
- Temporal Python SDK: https://docs.temporal.io/develop/python
- InferX Dev Notes: /Users/brianbagdasarian/projects/dev-notes/docs/inferx/

**Issues:**
- Temporal workflow issues → Check Temporal UI event history
- Database issues → Check PostgreSQL logs
- Worker issues → Check PM2 logs (`pm2 logs`)

---

## License

Proprietary - Remodl AI
