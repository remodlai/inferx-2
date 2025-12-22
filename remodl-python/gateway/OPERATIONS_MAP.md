# Gateway Operations Mapping

**Date:** 2025-12-22
**Purpose:** Map all Gateway operations to plan LiteLLM + Temporal architecture

---

## Current Architecture

```
Dashboard/API (HTTP) → Gateway (Rust, port 4000) → StateSvc (Rust gRPC, port 1237)
                              ↓                    → Scheduler (Rust gRPC, port 1238)
                              ↓                    → PostgreSQL (audit, logs)
                              ↓                    → vLLM Pods (HTTP proxy)
                              ↓                    → Keycloak (JWT validation)
```

**Gateway:** `ixshare/src/gateway/http_gw.rs` + `http_gateway.rs`

---

## Gateway Operations by Category

### 1. Tenant Management

**HTTP Endpoint:** `POST /funccall/tenant/`

**Flow:**
```
Dashboard → Gateway.CreateTenant() → StateSvc.Create(tenant) → etcd
                   ↓
         Keycloak: GrantTenantAdminPermission() → PostgreSQL (secret-db)
```

**What it does:**
1. Validates: `tenant="system"`, `namespace="system"`
2. Calls StateSvc gRPC: `Create(objType="tenant", ...)`
3. Writes role to PostgreSQL: `INSERT INTO userrole (username, '/tenant/admin/{name}')`

**Proposed (LiteLLM + Temporal):**
```
Dashboard → LiteLLM Extension → Temporal Client → StateSvcWorkflow.create_tenant()
                                                      ↓
                                                 Activity: PostgreSQL write
```

---

**HTTP Endpoint:** `DELETE /funccall/tenant/{name}`

**Flow:**
```
Dashboard → Gateway.DeleteTenant() → StateSvc.Delete(tenant) → etcd
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.delete_tenant()
```

---

**HTTP Endpoint:** `GET /funccall/tenant/`

**Flow:**
```
Dashboard → Gateway.ListTenant() → StateSvc.List(obj_type="tenant") → Return cached list
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.list_tenants() (query)
```

---

### 2. Namespace Management

**HTTP Endpoint:** `POST /funccall/namespace/`

**Flow:**
```
Dashboard → Gateway.CreateNamespace() → StateSvc.Create(namespace) → etcd
```

**Validation:** Checks tenant exists

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.create_namespace()
```

---

**HTTP Endpoint:** `PUT /funccall/namespace/{tenant}/{namespace}`

**Flow:**
```
Dashboard → Gateway.UpdateNamespace() → StateSvc.Update(namespace) → etcd
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.update_namespace()
```

---

**HTTP Endpoint:** `DELETE /funccall/namespace/{tenant}/{namespace}`

**Flow:**
```
Dashboard → Gateway.DeleteNamespace() → StateSvc.Delete(namespace) → etcd
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.delete_namespace()
```

---

**HTTP Endpoint:** `GET /funccall/namespace/`

**Flow:**
```
Dashboard → Gateway.ListNamespace() → StateSvc.List(obj_type="namespace") → Return list
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.list_namespaces()
```

---

### 3. Function (Model) Management

**HTTP Endpoint:** `POST /funccall/function/`

**Flow:**
```
Dashboard → Gateway.CreateFunc() → StateSvc.Create(function) → etcd
                                      ↓
                                 Auto-creates FunctionStatus
```

**Validation:**
- Namespace exists
- Function spec valid (image, commands, resources, policy)

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.create_function()
                                     ↓
                                Activity: PostgreSQL write (function + status)
```

---

**HTTP Endpoint:** `PUT /funccall/function/{tenant}/{namespace}/{name}`

**Flow:**
```
Dashboard → Gateway.UpdateFunc() → StateSvc.Update(function) → etcd
                                      ↓
                                 Update FunctionStatus
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.update_function()
```

---

**HTTP Endpoint:** `DELETE /funccall/function/{tenant}/{namespace}/{name}`

**Flow:**
```
Dashboard → Gateway.DeleteFunc() → StateSvc.Delete(function) → etcd
                                      ↓
                                 Delete FunctionStatus
                                      ↓
                                 Delete snapshots
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.delete_function()
                                     ↓
                                Activity: Cascade delete (function, status, snapshots)
```

---

**HTTP Endpoint:** `GET /funccall/function/{tenant}/{namespace}/{name}`

**Flow:**
```
Dashboard → Gateway.GetFunc() → StateSvc.Get(function) → Return from cache/etcd
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.get_function() (query)
```

---

**HTTP Endpoint:** `GET /funccall/function/` or `/funccall/functions/`

**Flow:**
```
Dashboard → Gateway.ListFunc() → StateSvc.List(obj_type="function", tenant, namespace) → Return list
```

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow.list_functions(tenant, namespace)
```

---

### 4. Inference Request Routing

**HTTP Endpoint:** `POST /api/{tenant}/{namespace}/{funcname}/v1/completions`

**Flow:**
```
Client → Gateway (auth, extract tenant/namespace/funcname)
           ↓
       Scheduler.LeaseWorker(tenant, namespace, funcname, version)
           ↓ Returns: {id, ipaddr, port, keepalive}
       HTTP Proxy → vLLM Pod (10.42.x.x:8000/v1/completions)
           ↓ Stream response
       Client ← Gateway (proxy response)
           ↓
       Scheduler.ReturnWorker(id, fail=false)
```

**What Gateway does:**
1. JWT validation (Keycloak)
2. Parse model path (tenant/namespace/funcname)
3. gRPC call: Scheduler.LeaseWorker()
4. HTTP proxy to pod
5. Stream response back
6. gRPC call: Scheduler.ReturnWorker()

**Proposed (LiteLLM):**
```
Client → LiteLLM (native proxy, auth, routing)
           ↓
       Scheduler Workflow (Temporal) - placement decision
           ↓
       Returns pod URL
           ↓
       LiteLLM → vLLM Pod (native proxy)
           ↓
       Client ← LiteLLM
```

**This is what LiteLLM is designed for!**

---

### 5. Pod Management

**HTTP Endpoint:** `GET /funccall/pod/{tenant}/{namespace}/{funcname}`

**Flow:**
```
Dashboard → Gateway.GetFuncPods() → StateSvc.List(obj_type="pod") → Return pods
```

**Note:** Pod data is NOT in etcd. It's managed by NodeAgent in memory, reported to StateSvc via watch.

**Proposed:**
```
Dashboard → LiteLLM Extension → Query PostgreSQL or Temporal workflow state
```

---

**HTTP Endpoint:** `GET /funccall/pod/{tenant}/{namespace}/{funcname}/{id}`

**Flow:**
```
Dashboard → Gateway.GetFuncPod() → StateSvc.Get(obj_type="pod") → Return pod details
```

**Proposed:**
```
Dashboard → LiteLLM Extension → Query pod state
```

---

### 6. Snapshot Management

**HTTP Endpoint:** `GET /funccall/snapshot/{tenant}/{namespace}/{funcname}`

**Flow:**
```
Dashboard → Gateway.GetSnapshots() → StateSvc.List(obj_type="snapshot") → Return snapshots
```

**Proposed:**
```
Dashboard → LiteLLM Extension → Query snapshot metadata
```

---

### 7. Log Retrieval

**HTTP Endpoint:** `GET /funccall/readlog/{tenant}/{namespace}/{funcname}`

**Flow:**
```
Dashboard → Gateway.ReadLog() → NodeAgent.ReadPodLog() → Return container logs
```

**Proposed:**
```
Dashboard → LiteLLM Extension → NodeAgent.ReadPodLog() (keep gRPC call)
```

---

**HTTP Endpoint:** `GET /podlog/{tenant}/{namespace}/{funcname}/{version}/{id}/`

**Flow:**
```
Dashboard → Gateway.ReadPodLog() → Read from filesystem or DIND logs
```

**Proposed:**
```
Dashboard → LiteLLM Extension → Same (filesystem read or DIND API)
```

---

**HTTP Endpoint:** `GET /funccall/reqauditlog/`

**Flow:**
```
Dashboard → Gateway.ReadPodAuditLog() → PostgreSQL:
  SELECT * FROM reqaudit WHERE tenant = ? AND namespace = ? AND funcname = ?
```

**Proposed:**
```
Dashboard → LiteLLM Extension → PostgreSQL query (same)
```

---

**HTTP Endpoint:** `GET /funccall/podlog/fail/`

**Flow:**
```
Dashboard → Gateway.ReadPodFailLogs() → PostgreSQL:
  SELECT * FROM podfaillog
```

**Proposed:**
```
Dashboard → LiteLLM Extension → PostgreSQL query
```

---

### 8. Resource Summary

**HTTP Endpoint:** `GET /funccall/resource/`

**Flow:**
```
Dashboard → Gateway.GetResourceSummary() → StateSvc.List(nodes) + List(functions)
              ↓
         Aggregate: Total GPUs, used GPUs, total functions, etc.
```

**What it does:**
- Query all nodes (get total GPU capacity)
- Query all functions (get resource allocations)
- Calculate totals, aggregates
- Return summary JSON

**Proposed:**
```
Dashboard → LiteLLM Extension → StateSvcWorkflow queries
                                    ↓
                               Python aggregation logic
```

---

### 9. Authentication

**All Endpoints:** JWT validation via Keycloak

**Flow:**
```
Request with Bearer token → Gateway.auth_layer
                               ↓
                          Keycloak: Validate JWT
                               ↓
                          Extract: username, tenant, roles
                               ↓
                          PostgreSQL (secret-db): Check permissions
                               ↓
                          Allow/Deny request
```

**Proposed:**
```
Request → LiteLLM (native JWT validation, OAuth)
            ↓
        Check permissions (PostgreSQL or Keycloak)
```

**LiteLLM already has:** JWT auth, API keys, OAuth, rate limiting, cost tracking

---

### 10. API Key Management

**HTTP Endpoint:** `POST /apikey/`

**Flow:**
```
Dashboard → Gateway.CreateAPIKey() → PostgreSQL (secret-db):
  INSERT INTO apikey (key, username, description)
```

**Proposed:**
```
Dashboard → LiteLLM (native API key management)
```

---

**HTTP Endpoint:** `GET /apikey/`

**Flow:**
```
Dashboard → Gateway.ListAPIKeys() → PostgreSQL:
  SELECT * FROM apikey WHERE username = ?
```

**Proposed:**
```
Dashboard → LiteLLM API key endpoint
```

---

**HTTP Endpoint:** `DELETE /apikey/{key}`

**Flow:**
```
Dashboard → Gateway.DeleteAPIKey() → PostgreSQL:
  DELETE FROM apikey WHERE key = ?
```

**Proposed:**
```
Dashboard → LiteLLM API key endpoint
```

---

## Summary: What Gateway Actually Does

**1. HTTP Server (Port 4000):**
- Receives REST API requests from Dashboard
- Returns JSON responses

**2. gRPC Client:**
- Calls StateSvc (Create, Get, List, Update, Delete)
- Calls Scheduler (LeaseWorker, ReturnWorker, RefreshGateway)

**3. PostgreSQL Client:**
- Queries audit logs (reqaudit, podfaillog, snapshotscheduleaudit)
- Queries API keys (apikey table)
- Writes API keys

**4. HTTP Proxy:**
- Routes inference requests to vLLM pods
- Streams responses back to clients

**5. JWT Validation:**
- Validates tokens against Keycloak
- Checks permissions in PostgreSQL

**6. Data Aggregation:**
- Combines data from multiple sources
- Calculates summaries, aggregates

**ZERO GPU operations. ZERO performance-critical code.**

---

## Proposed Architecture

### Replace Gateway with LiteLLM + InferX Extension

**LiteLLM provides:**
- ✅ HTTP server (FastAPI-based)
- ✅ Inference proxy (to vLLM pods)
- ✅ Auth (JWT, API keys, OAuth)
- ✅ Rate limiting, cost tracking
- ✅ Load balancing, fallbacks
- ✅ Logging, metrics

**InferX Extension adds:**
- ✅ Model management (Create/Update/Delete via StateSvc Temporal)
- ✅ Tenant/Namespace operations (via StateSvc Temporal)
- ✅ Resource queries (via StateSvc queries)
- ✅ Scheduling (via Scheduler Temporal workflows)
- ✅ Pod/snapshot queries (PostgreSQL or Temporal state)
- ✅ Audit log queries (PostgreSQL)

**Services needed:**

**1. StateSvc (Python + Temporal):**
- gRPC server on port 1237 (for IxProxy compatibility)
- Temporal workflow for state management
- Activities → PostgreSQL

**2. Scheduler (Python + Temporal):**
- Temporal workflows for placement, deployment
- No separate pod needed (just workflows)
- Or: gRPC server on port 1238 if Gateway Rust needs compatibility

**3. LiteLLM + InferX Extension:**
- Replaces Gateway Rust HTTP server
- FastAPI endpoints for Dashboard
- Inference proxy (native LiteLLM)
- Calls StateSvc/Scheduler via Temporal client

**4. Dashboard:**
- Calls LiteLLM HTTP endpoints (instead of Gateway)
- Some endpoints unchanged (inference), some new (management)

---

## Operation Mapping: Gateway → LiteLLM Extension

| Current Gateway Endpoint | What It Does | LiteLLM Equivalent |
|--------------------------|--------------|-------------------|
| `POST /funccall/tenant/` | Create tenant | Extension: Call StateSvc Temporal |
| `DELETE /funccall/tenant/{name}` | Delete tenant | Extension: Call StateSvc Temporal |
| `GET /funccall/tenant/` | List tenants | Extension: Query StateSvc Temporal |
| `POST /funccall/namespace/` | Create namespace | Extension: Call StateSvc Temporal |
| `PUT /funccall/namespace/{tenant}/{ns}` | Update namespace | Extension: Call StateSvc Temporal |
| `DELETE /funccall/namespace/{tenant}/{ns}` | Delete namespace | Extension: Call StateSvc Temporal |
| `GET /funccall/namespace/` | List namespaces | Extension: Query StateSvc Temporal |
| `POST /funccall/function/` | Deploy model | Extension: Trigger deployment workflow |
| `PUT /funccall/function/{tenant}/{ns}/{name}` | Update model | Extension: Update via StateSvc |
| `DELETE /funccall/function/{tenant}/{ns}/{name}` | Delete model | Extension: Delete via StateSvc |
| `GET /funccall/function/{tenant}/{ns}/{name}` | Get model | Extension: Query StateSvc |
| `GET /funccall/function/` | List models | Extension: Query StateSvc |
| `POST /api/{tenant}/{ns}/{func}/v1/completions` | Inference | **Native LiteLLM** (no change needed!) |
| `GET /funccall/pod/` | List pods | Extension: Query PostgreSQL or workflow |
| `GET /funccall/snapshot/` | List snapshots | Extension: Query PostgreSQL or workflow |
| `GET /funccall/readlog/` | Read logs | Extension: Query PostgreSQL |
| `POST /apikey/` | Create API key | **Native LiteLLM** API key management |
| `GET /apikey/` | List API keys | **Native LiteLLM** |
| `DELETE /apikey/{key}` | Delete API key | **Native LiteLLM** |

---

## What Needs gRPC Translation

**StateSvc:**
- IxProxy calls gRPC `IxMetaService.Create/Update/Delete/Get/List`
- Needs: Python gRPC server (port 1237) → Temporal workflow

**Scheduler (if keeping Gateway Rust temporarily):**
- Gateway calls gRPC `SchedulerService.LeaseWorker/ReturnWorker`
- Needs: Python gRPC server (port 1238) → Temporal workflow
- OR: Rewrite Gateway in Python (call Temporal directly, no gRPC)

**NodeAgent:**
- No change needed (Scheduler/IxProxy call NodeAgent, not Gateway)

---

## Migration Path Options

### Option A: Big Bang (Replace Everything)

**Week 1-2:**
- StateSvc: gRPC server + Temporal workflow
- Scheduler: Temporal workflows only (no gRPC yet)

**Week 3:**
- LiteLLM + InferX Extension
- Replace Gateway entirely

**Week 4:**
- Dashboard updates (point to LiteLLM endpoints)
- Remove Gateway Rust, StateSvc Rust, Scheduler Rust

**Risk:** High (everything changes at once)

---

### Option B: Incremental (Parallel Deployment)

**Phase 1: StateSvc (Week 1)**
- Deploy Python StateSvc with gRPC server (port 1237)
- Run alongside Rust StateSvc (port 1237 on different service name)
- Point IxProxy at new StateSvc via STATESVC_ADDR env var
- Validate compatibility

**Phase 2: Scheduler (Week 2)**
- Implement Scheduler Temporal workflows
- Deploy Python gRPC server (port 1238) or direct Temporal calls from Gateway
- Test in parallel with Rust Scheduler

**Phase 3: Gateway → LiteLLM (Week 3-4)**
- Deploy LiteLLM + InferX Extension
- Route some Dashboard traffic to new endpoints
- Validate feature parity
- Gradual cutover

**Phase 4: Cleanup (Week 5)**
- Remove Rust services
- Remove etcd
- Update documentation

**Risk:** Lower (incremental validation)

---

## Decision Points

**1. Do we keep Gateway Rust temporarily?**
- **YES:** StateSvc + Scheduler need gRPC servers for compatibility
- **NO:** Rewrite Gateway in Python, call Temporal directly

**2. Do we use LiteLLM or custom FastAPI?**
- **LiteLLM:** Get proxy, auth, routing, metrics for free
- **FastAPI:** More control, but reinvent features

**3. Do we containerize each service separately?**
- **StateSvc:** Separate pod (gRPC server + Temporal worker)
- **Scheduler:** Just Temporal workflows (no pod) OR separate gRPC server pod
- **LiteLLM Extension:** Separate pod with Temporal client

**4. Do we need etcd at all?**
- **NO:** Temporal workflow state + PostgreSQL replaces it completely
- Can remove etcd pod after migration

---

## Next Steps

1. **Decide migration path** (Big Bang vs Incremental)
2. **Create StateSvc gRPC server** (Python grpcio, implements ixmeta.proto)
3. **Test IxProxy → Python gRPC → Temporal workflow**
4. **Decide on LiteLLM integration** (extension pattern)
5. **Plan Gateway replacement** or keep temporarily

---

## Files Referenced

**Current Implementation:**
- Gateway: `ixshare/src/gateway/http_gw.rs`, `http_gateway.rs`
- StateSvc: `ixshare/src/state_svc/state_svc.rs`
- Scheduler: `ixshare/src/scheduler/scheduler.rs`
- Proto: `ixshare/proto/ixmeta.proto`, `na.proto`

**New Implementation:**
- StateSvc: `/remodl-python/statesvc/src/`
- Scheduler: `/remodl-python/scheduler/src/` (TBD)
- Gateway: Use LiteLLM or create in `/remodl-python/gateway/` (TBD)
