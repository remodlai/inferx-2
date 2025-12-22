# Scheduler API Specification

**Date:** 2025-12-22
**Protocol:** gRPC (port 1238)
**Proto:** `ixshare/proto/na.proto`

---

## Service Definition

```protobuf
service SchedulerService {
  rpc ConnectScheduler(ConnectReq)  returns (ConnectResp) {}
  rpc LeaseWorker(LeaseWorkerReq) returns (LeaseWorkerResp) {}
  rpc ReturnWorker(ReturnWorkerReq) returns (ReturnWorkerResp) {}
  rpc RefreshGateway(RefreshGatewayReq) returns (RefreshGatewayResp) {}
}
```

---

## 1. ConnectScheduler

### Purpose
Gateway registers itself with Scheduler and reports existing worker leases. Called on Gateway startup or when connecting to new Scheduler instance.

### Request
```protobuf
message ConnectReq {
  int64  gateway_id = 1;
  repeated WorkerId workers = 2;
}

message WorkerId {
  string tenant = 1;
  string namespace = 2;
  string funcname = 3;
  int64 fprevision = 4;
  string id = 5;
}
```

### Response
```protobuf
message ConnectResp {
  string error = 1;  // Empty string = success
}
```

### Current Behavior

**Gateway side (scheduler_client.rs:51-94):**
```rust
// On Gateway startup
let mut workers = Vec::new();
for w in self.leasedWorkers {
    workers.push(WorkerId { tenant: w.tenant, ... });
}

let response = client.connect_scheduler(ConnectReq {
    gateway_id: GatewayId(),
    workers: workers
}).await?;

// If error, Gateway PANICS (line 85):
panic!("connect to new scheduler fail... need restart to avoid double lease workers")
```

**Scheduler side (scheduler_handler.rs):**
```rust
// Store gateway → worker mapping
self.gateways.insert(gateway_id, GatewayState {
    workers: workers,
    last_refresh: now()
});

// Verify workers are valid (exist in scheduler's state)
// Return error if any worker is unknown
```

### What It Actually Does

- **Data operation:** Register gateway_id in Map
- **Validation:** Check workers exist in scheduler state
- **No GPU access:** Pure metadata

### Why It Exists

**Problem:** If Gateway restarts, it doesn't know which pods it previously leased. Without ConnectScheduler, Scheduler might double-lease workers (one Gateway thinks it owns worker X, restarted Gateway gets same worker X).

**Real solution:** Store leases in PostgreSQL, not in-memory. Then no registration needed.

---

## 2. LeaseWorker

### Purpose
Get a pod to handle an inference request. This is the core scheduling operation.

### Request
```protobuf
message LeaseWorkerReq {
  string tenant = 1;
  string namespace = 2;
  string funcname = 3;
  int64  fprevision = 4;  // Function version/revision
  int64  gateway_id = 5;
}
```

### Response
```protobuf
message LeaseWorkerResp {
  string error = 1;
  string id = 3;          // Pod ID
  uint32 ipaddr = 4;      // Pod IP (as uint32, network byte order)
  bool   keepalive = 5;   // true = call ReturnWorker when done
  uint32 hostipaddr = 6;  // Node IP
  uint32 hostport = 7;    // Node port
}
```

### Current Behavior Flow

**1. Check for existing running pod (cache hit):**
```rust
let funckey = format!("{tenant}/{namespace}/{funcname}/{fprevision}");
if let Some(pod) = self.runningPods.get(&funckey) {
    // Pod already exists and running
    return LeaseWorkerResp {
        id: pod.id,
        ipaddr: pod.ip,
        port: 8000,
        keepalive: false  // Don't return, already running
    };
}
```

**2. Check for idle pod (warm start):**
```rust
if let Some(pod) = self.idlePods.get(&funckey) {
    // Pod exists but idle, resume it
    await NodeAgent.ResumePod(pod.id);
    self.idlePods.remove(&funckey);
    self.runningPods.insert(&funckey, pod);
    return LeaseWorkerResp { id: pod.id, ipaddr: pod.ip, keepalive: true };
}
```

**3. Find node with capacity (bin-packing):**
```rust
// scheduler_handler.rs:2143-2157
let contextCount = nodeStatus.node.object.resources.GPUResource().maxContextCnt;
let reqResource = func.object.spec.SnapshotResource(contextCount).clone();

// Can this node fit the model?
let state = nodeStatus.total.CanAlloc(&reqResource, true);
if !state.Ok() {
    return Err("Node has no enough resource");
}

// Math operation:
// total_vram - used_vram >= required_vram
// total_slots - used_slots >= required_slots
```

**4. Check if need to evict idle pods:**
```rust
// scheduler_handler.rs:2161
let terminateWorkers = self.TryFreeResources(
    nodename,
    funcId,
    &mut nodeResources,
    &reqResource,
    true
)?;

// Find idle pods on this node that can be terminated to free resources
```

**5. Allocate resources (accounting):**
```rust
// Increment counters
nodeStatus.usedGPU += 1;
nodeStatus.usedVRAM += func.spec.resources.GPU.vRam;
nodeStatus.usedCPU += func.spec.resources.CPU;
nodeStatus.usedMem += func.spec.resources.Mem;
```

**6. Create pod on NodeAgent:**
```rust
// HTTP POST to NodeAgent
let pod_id = await http_client.post(
    format!("{}/create_pod", node.agent_url),
    json!(func_spec)
).await?;

// NodeAgent does the actual GPU work:
// - Allocates GPU memory
// - Loads model weights
// - Starts vLLM container
// - Creates snapshot
```

**7. Track pending pod:**
```rust
// Add to pending list
nodeStatus.AddPendingPod(&pendingPod)?;

// Wait for NodeAgent to report pod as Running
// (happens via separate watch/stream)
```

**8. Return pod info:**
```rust
return LeaseWorkerResp {
    id: pod_id,
    ipaddr: pod.ip,
    port: 8000,
    keepalive: true  // Gateway must call ReturnWorker when request completes
};
```

### What It Actually Is

**Pseudocode equivalent:**
```python
async def lease_worker(func_spec):
    # 1. Check cache
    pod = await db.fetchrow("SELECT * FROM pods WHERE func_id = $1 AND state = 'running'", func_spec.id)
    if pod:
        return {"id": pod.id, "ipaddr": pod.ip, "port": 8000, "keepalive": False}

    # 2. Find node
    node = await db.fetchrow("""
        SELECT name, agent_url
        FROM nodes
        WHERE available_vram >= $1 AND state = 'ready'
        ORDER BY available_vram ASC
        LIMIT 1
    """, func_spec.vram)

    if not node:
        raise NoCapacityError()

    # 3. Reserve resources
    await db.execute("UPDATE nodes SET used_vram = used_vram + $1 WHERE name = $2", func_spec.vram, node.name)

    # 4. Create pod
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{node.agent_url}/create_pod", json=func_spec.dict())

    pod_id = resp.json()['id']
    pod_ip = resp.json()['ip']

    # 5. Track
    await db.execute("INSERT INTO pods (id, node, func_id, ip, port, state) VALUES ($1, $2, $3, $4, $5, 'pending')",
                     pod_id, node.name, func_spec.id, pod_ip, 8000)

    return {"id": pod_id, "ipaddr": pod_ip, "port": 8000, "keepalive": True}
```

**That's the entire LeaseWorker operation. ~40 lines of Python.**

### Performance Analysis

**At current scale (10 models, 4 nodes):**
- Node query: ~5ms
- Resource update: ~2ms
- NodeAgent HTTP call: ~50ms
- Pod tracking insert: ~2ms
- **Total: ~60ms**

**At theoretical scale (100 models, 100 nodes):**
- Node query with index: ~10ms
- Resource update: ~5ms
- NodeAgent HTTP call: ~50ms
- Pod tracking insert: ~5ms
- **Total: ~70ms**

**Model loading time: 2,000-8,000ms**

**Scheduling is <1% of the operation.**

---

## 3. ReturnWorker

### Purpose
Release a leased worker back to the pool. Called by Gateway when inference request completes or worker fails.

### Request
```protobuf
message ReturnWorkerReq {
  string tenant = 1;
  string namespace = 2;
  string funcname = 3;
  int64 fprevision = 4;
  string id = 5;          // Pod ID
  bool  failworker = 6;   // true = pod failed, terminate it
}
```

### Response
```protobuf
message ReturnWorkerResp {
  string error = 1;
}
```

### Current Behavior

**If failworker = true:**
```rust
// Mark pod as failed
pod.state = PodState::Failed;

// Call NodeAgent to terminate
await NodeAgent.TerminatePod(pod.id);

// Free resources
nodeStatus.usedVRAM -= pod.allocated_vram;
nodeStatus.usedGPU -= pod.gpu_count;

// Remove from tracking
self.runningPods.remove(&pod.key);
```

**If failworker = false (normal completion):**
```rust
// Move pod to idle pool
pod.state = PodState::Idle;
pod.last_used = now();
self.runningPods.remove(&pod.key);
self.idlePods.insert(&pod.key, pod);

// Don't free resources immediately (keep pod warm)
// Separate timeout task will terminate if idle too long
```

### What It Actually Is

```python
async def return_worker(pod_id, fail=False):
    if fail:
        # Terminate immediately
        await http_post(f"{node.agent_url}/terminate_pod", {"pod_id": pod_id})
        await db.execute("UPDATE pods SET state = 'failed' WHERE id = $1", pod_id)
        await db.execute("UPDATE nodes SET used_vram = used_vram - $1 WHERE ...", pod.vram)
    else:
        # Mark idle, keep warm
        await db.execute("UPDATE pods SET state = 'idle', last_used = NOW() WHERE id = $1", pod_id)
        # Resources still reserved for fast re-use
```

**Data operations only.**

---

## 4. RefreshGateway

### Purpose
Gateway heartbeat to prevent timeout. Called periodically by Gateway (every few seconds).

### Request
```protobuf
message RefreshGatewayReq {
  int64  gateway_id = 1;
}
```

### Response
```protobuf
message RefreshGatewayResp {
  string error = 1;
}
```

### Current Behavior

```rust
// Update gateway last_seen timestamp
match self.gateways.get_mut(&gateway_id) {
    Some(gateway) => gateway.last_refresh = now(),
    None => return Err("Gateway not registered")
}

// Background task checks for stale gateways
// If last_refresh > 30s ago, reclaim its workers
```

### What It Actually Is

```python
async def refresh_gateway(gateway_id):
    await db.execute("UPDATE gateways SET last_seen = NOW() WHERE id = $1", gateway_id)
```

**Simple timestamp update.**

---

## HTTP Endpoints

### `GET /metrics` (Port 80)

**Purpose:** Prometheus metrics scraping

**Returns:**
```
# HELP inferx_scheduler_total_gpu Total GPU count
# TYPE inferx_scheduler_total_gpu gauge
inferx_scheduler_total_gpu{node="gpu-workerx2"} 1.0

# HELP inferx_scheduler_used_gpu Used GPU count
# TYPE inferx_scheduler_used_gpu gauge
inferx_scheduler_used_gpu{node="gpu-workerx2"} 0.0
```

**Implementation:** `scheduler_http.rs:11-24`

### `GET /` (Port 80)

**Purpose:** Health check

**Returns:** `"InferX Scheduler"`

---

## Who Calls Scheduler

### Gateway

**On startup:**
- `ConnectScheduler()` - Register and report existing leases

**On inference request:**
- `LeaseWorker()` - Get pod for model

**On request completion:**
- `ReturnWorker()` - Release pod

**Periodically:**
- `RefreshGateway()` - Heartbeat every few seconds

### NodeAgent

**Does NOT call Scheduler directly.** NodeAgent only:
- Receives calls FROM Scheduler (via gRPC)
- Reports pod status to StateSvc (which Scheduler watches)

---

## Data Dependencies

**Scheduler reads from:**
1. **StateSvc gRPC watch stream:**
   - Functions (model specs)
   - Nodes (GPU resources)
   - Pods (current state)
   - FuncPolicy (scaling rules)

2. **Gateway gRPC calls:**
   - LeaseWorker requests
   - ReturnWorker confirmations
   - RefreshGateway heartbeats

**Scheduler writes to:**
1. **etcd (via direct EtcdStore):**
   - `/registry/scheduler/system/system/scheduler` (self-registration with lease)

2. **NodeAgent (via gRPC):**
   - CreateFuncPod (start new pod)
   - TerminatePod (cleanup)
   - ResumePod (wake from idle)

3. **In-memory state only:**
   - Gateway connections
   - Worker leases
   - Resource accounting (used_vram, used_gpu, etc.)

**Critical:** All the important state is in-memory and lost on crash!

---

## Call Patterns

### Successful Inference Request Flow

```
1. User → Gateway: POST /v1/completions
2. Gateway → Scheduler: LeaseWorker(public, test, llama, v1)
3. Scheduler: Check cache (miss), find node, allocate resources
4. Scheduler → NodeAgent: CreateFuncPod(llama spec)
5. NodeAgent: Creates vLLM container, loads model, snapshots
6. NodeAgent → Scheduler: Pod ready (via StateSvc watch stream)
7. Scheduler → Gateway: LeaseWorkerResp(id=123, ip=10.42.x.x, port=8000)
8. Gateway → Pod: Forward inference request
9. Pod → Gateway: Streaming response
10. Gateway → User: Stream results
11. Gateway → Scheduler: ReturnWorker(id=123, fail=false)
12. Scheduler: Move pod to idle pool
```

**Total Scheduler involvement:** 2 gRPC calls (LeaseWorker, ReturnWorker)

**Scheduler work:** Database lookups + bin-packing math + HTTP proxy to NodeAgent

---

## Error Handling

### Current Approach (Problematic)

**Gateway panics on Scheduler errors:**
```rust
// scheduler_client.rs:85
panic!("connect to new scheduler fail... need restart to avoid double lease workers")

// func_worker.rs:48
.unwrap()  // Crash Gateway if LeaseWorker fails
```

**Scheduler panics on internal errors:**
```rust
// scheduler.rs:76, 96, 110, 120
.unwrap()  // Crash on send failures

// scheduler.rs:266
panic!("LeaseKeepalive failed: {:?}", e);  // Crash on etcd lease failure
```

### Improved Approach (Proposed)

**Gateway should handle errors gracefully:**
```python
try:
    worker = await scheduler.lease_worker(func_spec)
except NoCapacityError:
    return 503  # Service Unavailable
except SchedulerUnavailableError:
    # Retry with backoff or return error
    return 502  # Bad Gateway
```

**Scheduler should never panic:**
```python
try:
    pod = await create_pod_on_node(node, func_spec)
except NodeAgentError as e:
    logger.error(f"Failed to create pod on {node}: {e}")
    # Try different node or return error to caller
    raise
```

---

## Scalability Analysis

### Current Implementation Limits

**In-memory state:**
- All nodes (~100 max)
- All pods (~1,000 max)
- All functions (~100 max)
- All gateway connections (~10 max)

**Estimated memory:** ~100MB for 1,000 pods

**Bottleneck:** Not memory or CPU, but single-pod architecture (no horizontal scaling)

### With Database-Backed Approach

**PostgreSQL can handle:**
- 10,000+ nodes easily
- 100,000+ pods easily
- Complex queries with indexes
- Horizontal read replicas if needed

**With proper indexing:**
```sql
CREATE INDEX idx_nodes_capacity ON nodes(state, available_vram, gpu_type);
CREATE INDEX idx_pods_function ON pods(tenant, namespace, funcname, fprevision, state);
```

**Query performance:** <10ms even at 100,000 pods

---

## Proposed Simplification

### Replace with Temporal Workflow

**LeaseWorker becomes:**
```python
@workflow.defn
class LeaseWorkerWorkflow:
    @workflow.run
    async def run(self, request: LeaseWorkerRequest) -> LeaseWorkerResponse:
        # Temporal handles durability, retries, compensation

        # Activity 1: Find pod (with cache check)
        pod = await workflow.execute_activity(
            find_or_create_pod,
            request,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        return LeaseWorkerResponse(
            id=pod.id,
            ipaddr=pod.ip,
            port=pod.port
        )

@activity.defn
async def find_or_create_pod(request: LeaseWorkerRequest) -> Pod:
    # Check PostgreSQL for existing pod
    pod = await db.fetchrow("""
        SELECT id, ip, port, state
        FROM pods
        WHERE tenant = $1 AND namespace = $2 AND funcname = $3 AND fprevision = $4
        ORDER BY
            CASE state
                WHEN 'running' THEN 1
                WHEN 'idle' THEN 2
                ELSE 3
            END
        LIMIT 1
    """, request.tenant, request.namespace, request.funcname, request.fprevision)

    if pod and pod['state'] == 'running':
        # Cache hit - already running
        return Pod(**pod)

    if pod and pod['state'] == 'idle':
        # Resume idle pod
        await resume_pod(pod['id'], node.agent_url)
        return Pod(**pod)

    # No pod - create new
    node = await find_best_node(request.resource_requirements)
    pod = await create_pod_on_node(node, request)
    return pod
```

**Durability:** If Temporal worker crashes during create_pod_on_node, workflow resumes automatically. No lost state.

**Retries:** If NodeAgent is temporarily down, activity retries automatically.

**Observability:** Every lease operation visible in Temporal Web UI.

---

## Summary

**Current Scheduler API:**
- 4 gRPC endpoints (ConnectScheduler, LeaseWorker, ReturnWorker, RefreshGateway)
- 2 HTTP endpoints (/metrics, /)
- All perform **data operations only**
- No GPU hardware access
- Pure bin-packing + accounting + HTTP proxying

**Replacement options:**
1. **Temporal workflows** - Durable, observable, resilient
2. **PostgreSQL + simple Python service** - Straightforward, no ceremony
3. **LiteLLM extension** - Leverage existing proxy infrastructure

**The complexity is not justified by the actual workload.**
