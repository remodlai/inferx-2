# InferX Scheduler - Original Implementation Overview

**Date:** 2025-12-22
**Purpose:** Document current Rust-based Scheduler implementation to inform Python/Temporal rewrite

---

## Executive Summary

The InferX Scheduler is a **pure data/metadata orchestration service** that performs bin-packing to place model deployments on GPU nodes. Despite being implemented as a separate Kubernetes pod with etcd leases, gRPC services, and complex state management, it performs **ZERO direct GPU operations**. All actual GPU work happens in NodeAgent.

**Key Finding:** Scheduler is 100% data operations that could be replaced by:
- PostgreSQL queries for node selection
- Temporal workflows for deployment orchestration
- Simple Python functions for bin-packing logic

---

## Current Architecture

### Deployment

**Pod:** `scheduler` in InferX cluster
**Image:** `inferx/inferx_platform:v0.1.5`
**Language:** Rust (~3,000 lines)
**Protocol:** gRPC (port 1238) + HTTP metrics (port 80)
**Dependencies:** etcd, StateSvc

### Service Discovery Pattern

**Scheduler registers itself in etcd:**
```json
/registry/scheduler/system/system/scheduler
{
  "svcIp": "10.42.4.218",
  "port": 1238
}
```

**With lease:**
- **TTL:** 1 second (!!)
- **Keepalive:** Every 200ms
- **Panic on failure:** `panic!("LeaseKeepalive failed: {:?}", e)` (scheduler.rs:266)

**Why this is problematic:**
- Crashes entire scheduler on network blip
- 1-second TTL means 5 failed keepalives = service deregistered
- Gateway loses scheduler connection → can't route inference requests
- All in-memory state lost on crash

---

## Current Functionality

### 1. Service Discovery & Registration

**Purpose:** Let Gateway know where Scheduler is running

**Current Implementation:**
```rust
// scheduler_register.rs:138
let leaseId = self.store.LeaseGrant(Self::LEASE_TTL).await?;  // 1 second
self.store.Create(&self.info.DataObject(), leaseId).await?;

// scheduler_register.rs:162
loop {
    self.store.LeaseKeepalive(leaseId).await?;  // Every 200ms
    tokio::time::sleep(Duration::from_millis(200)).await;
}
```

**What it actually needs:**
- Kubernetes Service DNS: `scheduler.default.svc:1238`
- Gateway can always find it via DNS
- **No lease needed**

### 2. Gateway Connection Tracking

**Endpoint:** `ConnectScheduler(gateway_id, existing_workers)`

**Purpose:** Gateway reports which pods it currently has leased (on startup/reconnect)

**Current Implementation:**
```rust
// Gateway calls this when connecting to scheduler
let workers = [
    {tenant: "public", namespace: "test", funcname: "llama", id: "12345"},
    {tenant: "public", namespace: "test", funcname: "qwen", id: "67890"}
];
ConnectScheduler(gateway_id=42, workers=workers);
```

**Scheduler does:**
- Stores gateway_id → worker mapping in memory
- Prevents double-leasing same worker across Gateway restarts

**What it actually is:**
- Just a Map: `gateway_id → Set<WorkerId>`
- Could be in PostgreSQL: `leased_workers` table
- Or in Temporal workflow state

### 3. Worker Leasing (Model Pod Allocation)

**Endpoint:** `LeaseWorker(tenant, namespace, funcname, fprevision, gateway_id)`

**Purpose:** "Give me a pod to handle this inference request"

**Current Implementation Flow:**

**Step 1: Check if pod already exists**
```rust
// Look in in-memory cache
if let Some(pod) = self.pods.get(funckey) {
    if pod.state == Running {
        return Ok(LeaseWorkerResp {
            id: pod.id,
            ipaddr: pod.ipaddr,
            port: pod.port,
            keepalive: false  // Already running
        });
    }
}
```

**Step 2: Find node with capacity**
```rust
// scheduler_handler.rs:2143-2146
let contextCount = nodeStatus.node.object.resources.GPUResource().maxContextCnt;
let reqResource = func.object.spec.SnapshotResource(contextCount).clone();
let state = nodeStatus.total.CanAlloc(&reqResource, true);

// Pure math:
// node.total_vram - node.used_vram >= func.required_vram
```

**Step 3: Allocate resources**
```rust
// Just increment counters in memory
nodeStatus.usedGPU += gpuCnt;
nodeStatus.usedVRAM += reqResource.vram;
```

**Step 4: Call NodeAgent to create pod**
```rust
// scheduler_handler.rs:2189
let pod_id = self.StartWorker(
    &nodeAgentUrl,  // http://10.42.4.235:1233
    &func,
    &resources,
    na::CreatePodType::Snapshot,
    &terminateWorkers
).await?;

// Internally just does:
// HTTP POST to NodeAgent.CreateFuncPod()
```

**Step 5: Track pending pod**
```rust
// Add to in-memory pending list
nodeStatus.AddPendingPod(&pendingPod)?;
self.funcs.get_mut(funcId).unwrap().AddPendingPod(&pendingPod)?;
```

**Step 6: Return pod info to Gateway**
```rust
return LeaseWorkerResp {
    id: pod_id,
    ipaddr: pod.ip,
    port: 8000,
    keepalive: true  // Gateway should call ReturnWorker when done
};
```

**What it actually is:**
1. SQL query: "Find node with enough VRAM"
2. SQL update: "Reserve VRAM on that node"
3. HTTP POST: "NodeAgent, create this pod"
4. SQL insert: "Track pending pod"
5. Return: pod IP/port

**Zero GPU access.**

### 4. Worker Return (Release Resources)

**Endpoint:** `ReturnWorker(tenant, namespace, funcname, fprevision, id, failworker)`

**Purpose:** "I'm done with this pod, release it"

**Current Implementation:**
```rust
// Decrement resource counters
nodeStatus.usedGPU -= gpuCnt;
nodeStatus.usedVRAM -= pod.allocated_vram;

// Move pod to idle pool
self.idlePods.insert(pod.key, pod);

// If idle too long, terminate
if idle_timeout_exceeded {
    self.TerminatePod(pod).await?;
}
```

**What it actually is:**
- SQL update: "Free resources"
- SQL update: "Mark pod idle with timestamp"
- Optional: HTTP call to NodeAgent.TerminatePod if timeout

**Zero GPU access.**

### 5. Gateway Keepalive

**Endpoint:** `RefreshGateway(gateway_id)`

**Purpose:** "Gateway is still alive, don't timeout its workers"

**Current Implementation:**
```rust
// Update gateway last_seen timestamp
self.gateways.get_mut(gateway_id).unwrap().last_refresh = now();
```

**What it actually is:**
- SQL update: `UPDATE gateways SET last_seen = NOW() WHERE id = $1`

---

## What Scheduler Does NOT Do

❌ **No GPU driver calls** (no CUDA, no nvml)
❌ **No GPU memory operations** (no allocations, no transfers)
❌ **No direct hardware access** (no /dev/nvidia*)
❌ **No container creation** (NodeAgent does this)
❌ **No model loading** (vLLM does this)
❌ **No inference** (vLLM does this)
❌ **No snapshotting** (InferX runtime does this)

**It only:**
✅ Reads node metadata (CPU count, VRAM, GPU type)
✅ Runs bin-packing algorithm (pure math)
✅ Updates resource counters (accounting)
✅ Calls NodeAgent HTTP endpoints
✅ Tracks pod state (pending, running, idle)

---

## Data Sources

**All data comes from:**

1. **etcd (via StateSvc gRPC watch):**
   - Functions (model specs)
   - Nodes (GPU resources)
   - FuncPolicy (scaling rules)

2. **NodeAgent gRPC responses:**
   - Pod creation confirmations
   - Resource availability updates
   - Snapshot status

3. **In-memory state:**
   - Active pods
   - Idle pods
   - Resource allocations
   - Gateway connections

**No GPU hardware access whatsoever.**

---

## The "Kubernetes Theater" Problem

### What They Built (Complex):

**Architecture:**
```
Scheduler Pod
  ├─ etcd lease (1s TTL, 200ms keepalive)
  ├─ gRPC server (port 1238)
  ├─ HTTP metrics (port 80)
  ├─ Informer/Watcher (etcd change events)
  ├─ In-memory caching (nodes, pods, functions)
  ├─ Leader election (even though only 1 scheduler!)
  └─ 3,000 lines of Rust
```

**Failure modes:**
- Lease keepalive fails → Panic → Lost state
- etcd watch disconnects → Stale cache
- Gateway crashes → Lost worker leases
- Scheduler crashes → All state gone

### What They Actually Needed (Simple):

**Option A - Database + Simple Service:**
```python
# PostgreSQL tables
CREATE TABLE nodes (name, agent_url, total_vram, used_vram, state);
CREATE TABLE pods (id, node, func_id, ip, port, state, last_used);
CREATE TABLE leased_workers (gateway_id, pod_id, leased_at);

# Placement logic (50 lines)
async def lease_worker(func_spec):
    node = await db.fetchrow("SELECT ... WHERE available_vram >= $1 ...")
    await db.execute("UPDATE nodes SET used_vram = ...")
    pod = await http_post(f"{node.agent_url}/create_pod", func_spec)
    await db.execute("INSERT INTO pods ...")
    return pod
```

**Option B - Temporal Workflow:**
```python
@workflow.defn
class DeployModelWorkflow:
    async def run(self, func_spec):
        node = await workflow.execute_activity(find_best_node, func_spec)
        pod = await workflow.execute_activity(create_pod, node, func_spec)
        await workflow.wait_condition(lambda: pod.status == "ready", timeout=300)
        return pod
```

**Benefits:**
- No leases needed (Kubernetes DNS is stable)
- Temporal handles durability (state survives crashes)
- PostgreSQL handles queries (no in-memory cache needed)
- 500 lines of Python vs 3,000 lines of Rust

---

## Current vs Proposed at Scale

### Current Architecture (100 models, 100 GPUs):

**Scheduler overhead:**
- etcd lease keepalive: 200ms interval → 5 requests/sec
- Informer watching etcd: Continuous stream
- In-memory cache: ~100 nodes × ~100 pods = 10,000 objects
- gRPC connections: 1 per Gateway
- Leader election overhead

**Performance:** Fine, but complex

### Proposed Architecture (100 models, 100 GPUs):

**PostgreSQL queries:**
- Find node: `SELECT ... LIMIT 1` → 5-10ms
- Update resources: `UPDATE nodes SET ...` → 2-5ms
- Track pod: `INSERT INTO pods ...` → 2-5ms

**Total scheduling time:** 10-20ms per request

**Network latency to NodeAgent:** 10-50ms

**Model loading time:** 2,000-8,000ms

**Scheduling is 0.5% of total time.**

---

## Why Over-Engineering Happened

**Hypothesis:** InferX team mimicked Kubernetes Scheduler architecture because:

1. **Familiar pattern** - That's how "real" schedulers work
2. **Assumed scale** - Built for 1000s of nodes from day 1
3. **Distributed systems** - Used distributed primitives (etcd, leases) because "that's what you do"
4. **Separation of concerns** - Scheduler "should" be separate from Gateway

**But reality:**
- InferX schedules ~10 models on ~2-4 nodes
- Even at 100×100 scale, simple SQL is more than adequate
- Kubernetes Scheduler is complex because it's scheduling 100,000 pods/sec on 10,000 nodes
- InferX is scheduling ~1 pod/sec on ~4 nodes

**The complexity is pure theater.**

---

## Key Takeaways for Rewrite

1. **Scheduler is pure data operations** - No GPU hardware access
2. **Current leases are unnecessary** - Kubernetes DNS provides stable endpoints
3. **In-memory caching is premature optimization** - PostgreSQL can handle the query load
4. **Durability is critical** - Deployment state must survive crashes (Temporal provides this)
5. **Intelligence is easy to add** - When it's just Python/SQL, adding tags/preferences is trivial

---

## Files Referenced

**Rust Implementation:**
- `ixshare/src/scheduler/scheduler.rs` (763 lines)
- `ixshare/src/scheduler/scheduler_handler.rs` (~3,000 lines)
- `ixshare/src/scheduler/scheduler_svc.rs` (90 lines - gRPC service)
- `ixshare/src/scheduler/scheduler_http.rs` (41 lines - metrics endpoint)
- `ixshare/src/scheduler/scheduler_register.rs` (168 lines - etcd lease management)
- `ixshare/src/scheduler/sched_obj_repo.rs` (in-memory cache)

**Proto Definition:**
- `ixshare/proto/na.proto` (SchedulerService definition)

**Kubernetes:**
- `k8s/remodl-cluster/scheduler_with_remodl_node_selector.yaml`

---

## Next Steps

See companion documents:
- `API.md` - Complete API specification
- `DATA_FLOW.md` - How data flows through the system
- `SIMPLIFICATION.md` - How to replace with Temporal/PostgreSQL
