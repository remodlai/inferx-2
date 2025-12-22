# Scheduler Data Flow Analysis

**Date:** 2025-12-22
**Purpose:** Trace how data flows through Scheduler to understand dependencies and identify simplification opportunities

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          SCHEDULER POD                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────┐     ┌─────────────────┐                      │
│  │  etcd Lease      │     │  In-Memory      │                      │
│  │  Keepalive       │     │  State          │                      │
│  │  (200ms)         │     │                 │                      │
│  │  TTL: 1 second   │     │  • nodes        │                      │
│  └────────┬─────────┘     │  • pods         │                      │
│           │               │  • functions    │                      │
│           │ PANIC!        │  • gateways     │                      │
│           ▼               │  • idlePods     │                      │
│  ┌──────────────────┐     │  • runningPods  │                      │
│  │ Entire service   │     └─────────────────┘                      │
│  │ crashes          │              ▲                                │
│  └──────────────────┘              │ Populated from                │
│                                    │ StateSvc watch                │
└────────────────────────────────────┼──────────────────────────────┘
                                     │
                                     │
    ┌────────────────────────────────┴────────────────────────────┐
    │                                                              │
    │  StateSvc gRPC Watch Stream (continuous)                    │
    │  ┌───────────────────────────────────────────────┐          │
    │  │ Function created/updated/deleted              │          │
    │  │ Node registered/updated                        │          │
    │  │ Pod state changed                              │          │
    │  │ FuncPolicy modified                            │          │
    │  └───────────────────────────────────────────────┘          │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────────┐
    │                         GATEWAY POD                           │
    ├──────────────────────────────────────────────────────────────┤
    │                                                               │
    │  On inference request:                                        │
    │  ┌─────────────────────────────────────────────┐             │
    │  │ 1. LeaseWorker(public, test, llama, v8912)  │             │
    │  │    ↓                                        │             │
    │  │ 2. Scheduler finds node + creates pod      │             │
    │  │    ↓                                        │             │
    │  │ 3. Returns {id, ip, port}                  │             │
    │  │    ↓                                        │             │
    │  │ 4. Gateway proxies request to pod          │             │
    │  │    ↓                                        │             │
    │  │ 5. ReturnWorker(id, fail=false)            │             │
    │  └─────────────────────────────────────────────┘             │
    │                                                               │
    │  Periodic: RefreshGateway(gateway_id) - Every 5s             │
    │                                                               │
    └───────────────────────────────────────────────────────────────┘
```

---

## Detailed Data Flow: LeaseWorker Request

### Step-by-Step with Data Sources

**Request arrives:** `LeaseWorker(tenant="public", namespace="test", funcname="llama", fprevision=8912)`

#### Step 1: Check Running Pods (In-Memory Cache)

**Source:** `self.runningPods` HashMap
**Populated by:** StateSvc watch stream (pod state changes)

```rust
let funckey = "public/test/llama/8912";
if let Some(pod) = self.runningPods.get(funckey) {
    // Cache hit - pod already running
    return LeaseWorkerResp { id: pod.id, ipaddr: pod.ip, port: 8000 };
}
```

**Data access:** In-memory lookup (µs latency)
**External dependency:** None (if cache warm)

#### Step 2: Check Idle Pods (In-Memory Cache)

**Source:** `self.idlePods` HashMap
**Populated by:** ReturnWorker calls (pods moved to idle after request completion)

```rust
if let Some(pod) = self.idlePods.get(funckey) {
    // Warm start - resume idle pod
    await NodeAgent.ResumePod(pod.id);
    self.idlePods.remove(funckey);
    self.runningPods.insert(funckey, pod);
    return LeaseWorkerResp { id: pod.id, ipaddr: pod.ip, port: 8000 };
}
```

**Data access:** In-memory lookup + HTTP call to NodeAgent
**External dependency:** NodeAgent HTTP endpoint

#### Step 3: Get Function Spec (In-Memory Cache)

**Source:** `self.funcMgr` (FuncMgr)
**Populated by:** StateSvc watch stream (function created/updated events)

```rust
// sched_obj_repo.rs:106
let func = self.funcMgr.Get(tenant, namespace, name)?;

// Returns: Function spec with resources
{
  "resources": {
    "CPU": 15000,
    "Mem": 20000,
    "GPU": {"Count": 1, "Type": "Any", "vRam": 46000}
  },
  "commands": [...],
  "image": "remodlai/vllm-openai-mcp-tf:v0.12.0"
}
```

**Data access:** In-memory lookup
**External dependency:** StateSvc (for initial cache population)
**Ultimate source:** etcd (`/registry/function/public/test/llama`)

#### Step 4: Find Node with Capacity (In-Memory Cache + Bin-Packing)

**Source:** `self.nodes` HashMap
**Populated by:** StateSvc watch stream (node registered/updated events)

```rust
// scheduler_handler.rs:2143-2157
for (nodename, nodeStatus) in self.nodes.iter() {
    let contextCount = nodeStatus.node.object.resources.GPUResource().maxContextCnt;
    let reqResource = func.object.spec.SnapshotResource(contextCount);

    // Pure math: Can this node fit?
    if nodeStatus.total.CanAlloc(&reqResource, true) {
        selected_node = nodename;
        break;
    }
}
```

**Data read from node object:**
```json
{
  "resources": {
    "CPU": 20000,           // Total mCPU
    "Mem": 92160,           // Total MB
    "GPUType": "NVIDIA A100 80GB PCIe",
    "GPUs": {
      "totalSlotCnt": 279,  // Total GPU memory slots
      "slotSize": 268435456, // Bytes per slot (256MB)
      "vRam": 71424         // Total VRAM in MB
    }
  },
  "naIp": "10.42.4.235",
  "podMgrPort": 1233
}
```

**Bin-packing algorithm:**
```rust
// Simplified logic
let available_vram = node.total_vram - node.used_vram;
let available_slots = node.total_slots - node.used_slots;

if available_vram >= required_vram && available_slots >= required_slots {
    // This node can fit
    return Ok(node);
}
```

**Data access:** In-memory arithmetic
**External dependency:** None (pure computation)
**Ultimate source:** NodeAgent registers in etcd via StateSvc

#### Step 5: Check If Need to Evict Idle Pods

**Source:** `self.idlePods` for this node

```rust
// scheduler_handler.rs:2161
let terminateWorkers = self.TryFreeResources(
    nodename,
    funcId,
    &mut nodeResources,
    &reqResource,
    true
)?;

// Finds idle pods on this node that can be terminated to free space
// Returns list of pods to terminate
```

**Logic:**
```rust
// If node doesn't have enough free resources
if !nodeResources.CanAlloc(&reqResource) {
    // Find idle pods to terminate
    for pod in self.idlePods.iter().filter(|p| p.nodename == selected_node) {
        if freeing_pod_resources_would_make_room {
            terminateWorkers.push(pod);
            nodeResources.Free(&pod.resources);
        }
    }
}
```

**Data access:** In-memory iteration
**External dependency:** None

#### Step 6: Allocate Resources (In-Memory Accounting)

**Source:** `nodeStatus.available` and `nodeStatus.used`

```rust
// scheduler_handler.rs:2184
resources = nodeResources.Alloc(&snapshotResource, true)?;

// Internally just increments counters:
nodeStatus.usedGPU += 1;
nodeStatus.usedVRAM += func.vram;
nodeStatus.usedCPU += func.cpu;
nodeStatus.usedMem += func.mem;
```

**Data access:** In-memory counter increment
**External dependency:** None
**Persistence:** NONE - lost on crash!

#### Step 7: Call NodeAgent to Create Pod

**Source:** `nodeStatus.node.NodeAgentUrl()` (constructed from node metadata)

```rust
// scheduler_handler.rs:2189-2209
let pod_id = self.StartWorker(
    &nodeAgentUrl,  // e.g., "http://10.42.4.235:1233"
    &func,
    &resources,
    na::CreatePodType::Snapshot,
    &terminateWorkers
).await?;

// Internally:
// POST http://10.42.4.235:1233/na.NodeAgentService/CreateFuncPod
// With body: { func_spec, resources, terminateWorkers }
```

**Data access:** HTTP POST with JSON body
**External dependency:** NodeAgent gRPC service
**What NodeAgent does:**
- Creates Docker container via DIND
- Allocates actual GPU memory
- Loads model weights
- Creates snapshot on disk

**This is the ONLY step that touches GPU hardware** (and Scheduler doesn't do it - NodeAgent does!)

#### Step 8: Track Pending Pod

**Source:** Newly created entry in `self.funcs` and `nodeStatus.pendingPods`

```rust
// scheduler_handler.rs:2238-2250
let podKey = FuncPod::FuncPodKey(tenant, namespace, name, version, id);
let pendingPod = PendingPod::New(&nodename, &podKey, funcId, &resources);

nodeStatus.AddPendingPod(&pendingPod)?;
self.funcs.get_mut(funcId).unwrap().AddPendingPod(&pendingPod)?;
```

**Data access:** In-memory HashMap insert
**Persistence:** NONE - lost on crash!

#### Step 9: Return Response

```rust
return LeaseWorkerResp {
    id: pod_id,
    ipaddr: pod.ip,
    port: 8000,
    keepalive: true
};
```

**Total external calls in LeaseWorker:**
1. NodeAgent.CreateFuncPod (HTTP) - IF creating new pod
2. NodeAgent.ResumePod (HTTP) - IF resuming idle pod
3. NodeAgent.TerminatePod (HTTP) - IF evicting pods for space

**All other operations:** In-memory lookups and arithmetic

---

## Data Flow: ReturnWorker Request

**Request:** `ReturnWorker(tenant="public", namespace="test", funcname="llama", fprevision=8912, id="12345", failworker=false)`

#### If failworker=true (Pod Failed)

```rust
// 1. Mark pod failed
pod.state = PodState::Failed;

// 2. Call NodeAgent to terminate
await NodeAgent.TerminatePod(pod.id);

// 3. Free resources (in-memory)
nodeStatus.usedVRAM -= pod.allocated_vram;
nodeStatus.usedGPU -= 1;

// 4. Remove from tracking
self.runningPods.remove(&pod.key);
```

**External calls:** 1 HTTP to NodeAgent.TerminatePod

#### If failworker=false (Normal Completion)

```rust
// 1. Move to idle pool (keep warm)
pod.state = PodState::Idle;
pod.last_used = now();
self.runningPods.remove(&pod.key);
self.idlePods.insert(&pod.key, pod);

// 2. Resources still allocated (not freed)
// 3. Background task will terminate if idle > timeout
```

**External calls:** None (immediate)
**Background:** Eventually timeout task calls NodeAgent.TerminatePod

---

## Data Flow: StateSvc Watch Stream

**This is HOW Scheduler learns about cluster state changes.**

### What Scheduler Watches

**From StateSvc gRPC Watch:**
```protobuf
service IxMetaService {
  rpc Watch (WatchRequestMessage) returns (stream WEvent) {}
}
```

**Watches these object types:**
1. `Function` - Model deployments created/updated/deleted
2. `FunctionStatus` - Model deployment state changes
3. `FuncPod` - Pod lifecycle events
4. `Node` - GPU worker registration/updates
5. `ContainerSnapshot` - Snapshot creation/deletion
6. `FuncPolicy` - Scaling policy changes

### How It Populates Cache

**InformerFactory pattern (sched_obj_repo.rs:61-79):**
```rust
let factory = InformerFactory::New(statesvc_addresses, "", "").await?;

// Add informers for each object type
factory.AddInformer(Function::KEY, &ListOption::default())?;
factory.AddInformer(FunctionStatus::KEY, &ListOption::default())?;
factory.AddInformer(FuncPod::KEY, &ListOption::default())?;
factory.AddInformer(Node::KEY, &ListOption::default())?;
factory.AddInformer(ContainerSnapshot::KEY, &ListOption::default())?;
factory.AddInformer(FuncPolicy::KEY, &ListOption::default())?;

// Process watches in background
factory.Process(notify).await?;
```

**When events arrive:**
```rust
// EventHandler trait implementation
async fn handle(&self, _store: &ThreadSafeStore, event: &DeltaEvent) {
    match event.type_ {
        EventType::Added => {
            // Add to in-memory manager (funcMgr, podMgr, etc.)
            self.funcMgr.Add(function)?;
        }
        EventType::Modified => {
            // Update in-memory manager
            self.funcMgr.Update(function)?;
        }
        EventType::Deleted => {
            // Remove from in-memory manager
            self.funcMgr.Remove(function)?;
        }
    }
}
```

**This entire pattern exists to maintain in-memory caches so Scheduler doesn't query StateSvc on every request.**

**Alternative:** Just query PostgreSQL directly. With proper indexing, queries are <10ms.

---

## Data Sources & Dependencies

### Primary Data Source: etcd (via StateSvc)

**What's stored:**
```
/registry/function/{tenant}/{namespace}/{name}
  → Complete model spec (image, commands, resources, policy)

/registry/node_info/system/system/{nodename}
  → GPU capacity, IP addresses, ports

/registry/funcstatus/{tenant}/{namespace}/{name}
  → Deployment state, failure counts

/registry/scheduler/system/system/scheduler
  → Scheduler self-registration (with 1s lease)
```

**How Scheduler accesses it:**
- Does NOT query etcd directly (except for lease operations)
- Watches StateSvc gRPC stream for changes
- Maintains in-memory cache of all objects

**Why this is fragile:**
- Cache is in-memory only (lost on crash)
- Watch stream can disconnect (stale cache)
- No persistence of scheduling decisions

### Secondary Data Source: NodeAgent Responses

**When Scheduler calls NodeAgent.CreateFuncPod:**
```json
{
  "id": "9613",
  "ip": "10.0.0.5",
  "port": 8000,
  "state": "pending"
}
```

**Scheduler stores this in `pendingPods` map (in-memory).**

**Later, NodeAgent updates pod state via StateSvc:**
```
StateSvc receives: Pod state changed to "Running"
  ↓
StateSvc broadcasts via watch stream
  ↓
Scheduler receives event
  ↓
Scheduler moves pod from pendingPods → runningPods
```

**This entire dance exists to track pod lifecycle. Could be in PostgreSQL.**

---

## Resource Accounting Data Flow

### Initial State (Node Registers)

**NodeAgent starts → Registers with StateSvc:**
```json
{
  "nodename": "gpu-workerx2",
  "resources": {
    "GPUs": {"totalSlotCnt": 279, "vRam": 71424}  // 279 slots × 256MB = 71424 MB
  }
}
```

**StateSvc writes to etcd → Broadcasts to Scheduler**

**Scheduler initializes node tracking:**
```rust
nodeStatus.total = NodeResources {
    gpu_slots: 279,
    vram_mb: 71424,
    cpu_milli: 20000,
    mem_mb: 92160
};

nodeStatus.used = NodeResources::zero();  // Nothing allocated yet
nodeStatus.available = nodeStatus.total.clone();
```

### Pod Allocation (LeaseWorker)

**Function requires:**
```json
{
  "resources": {
    "GPU": {"Count": 1, "vRam": 46000},  // 46GB VRAM
    "CPU": 15000,  // 15 cores
    "Mem": 20000   // 20GB RAM
  }
}
```

**Scheduler updates accounting (in-memory):**
```rust
// Before allocation
nodeStatus.available.vram = 71424 MB

// Allocate
nodeStatus.used.vram += 46000;
nodeStatus.available.vram -= 46000;

// After allocation
nodeStatus.available.vram = 25424 MB  // 71424 - 46000
```

**This happens ONLY in Scheduler's memory. Not persisted anywhere.**

### Pod Return (ReturnWorker)

**If pod terminated:**
```rust
nodeStatus.used.vram -= 46000;
nodeStatus.available.vram += 46000;
```

**If pod moved to idle:**
```rust
// Resources still allocated (not freed)
// Pod kept warm for fast re-use
// Eventually timeout task frees resources
```

### The Problem with In-Memory Accounting

**If Scheduler crashes:**
- Lost track of which resources are allocated
- NodeAgent still has pods running
- Gateway thinks workers are leased
- **State mismatch:** Scheduler thinks resources free, but they're actually used

**Recovery:**
- Restart Scheduler
- Rebuild cache from StateSvc watch stream
- But lost knowledge of which Gateway has which workers
- Gateway must call ConnectScheduler to re-register

**This is fragile.**

---

## Data Flow: RefreshGateway

**Purpose:** Prevent Gateway timeout

**Current Implementation:**
```rust
// func_agent_mgr.rs:92
tokio::spawn(async {
    loop {
        tokio::select! {
            _ = interval.tick() => {  // Every 5 seconds
                SCHEDULER_CLIENT.RefreshGateway().await.ok();
            }
        }
    }
});
```

**Scheduler receives:**
```rust
// Update timestamp
match self.gateways.get_mut(&gateway_id) {
    Some(gateway) => gateway.last_refresh = now(),
    None => return Err("Gateway not registered")
}
```

**Background task checks for stale gateways:**
```rust
// Every 10 seconds
for (gateway_id, gateway) in self.gateways.iter() {
    if now() - gateway.last_refresh > Duration::from_secs(30) {
        // Gateway hasn't refreshed in 30s - assume dead
        // Reclaim all its workers
        for worker in gateway.workers {
            self.ReturnWorker(worker, fail=true).await;
        }
        self.gateways.remove(gateway_id);
    }
}
```

**What it actually is:**
- Heartbeat mechanism
- Could be: Gateway writes timestamp to PostgreSQL periodically
- Or: Temporal signal to keep workflow alive

---

## External Dependencies Summary

| Dependency | Purpose | Failure Impact |
|------------|---------|----------------|
| **etcd** | Lease registration (1s TTL) | Scheduler deregisters → Gateway can't find it → **CRITICAL** |
| **StateSvc gRPC** | Watch stream for cache population | Stale cache → Wrong scheduling decisions → **HIGH** |
| **NodeAgent HTTP** | Create/Resume/Terminate pods | Can't deploy models → **CRITICAL** |
| **Gateway gRPC** | Receives LeaseWorker requests | No requests → Scheduler idle → **LOW** |

**All dependencies are network services (I/O bound), not hardware.**

---

## Performance Characteristics

### Typical LeaseWorker Latency Breakdown

**Cache hit (pod already running):**
- In-memory lookup: <1ms
- **Total: <1ms**

**Warm start (resume idle pod):**
- In-memory lookup: <1ms
- NodeAgent.ResumePod HTTP: 20-50ms
- **Total: 20-50ms**

**Cold start (create new pod):**
- In-memory cache lookups: ~1ms
- Bin-packing algorithm: <1ms (even with 100 nodes)
- NodeAgent.CreateFuncPod HTTP: 50-100ms
- NodeAgent creates container: 2,000-8,000ms
- **Total: 2,050-8,100ms**

**Scheduler's contribution:** <2ms (0.02% of cold start time)

**Bottleneck:** NOT Scheduler logic, but NodeAgent pod creation + model loading

---

## Crash Recovery Scenarios

### Scenario 1: Scheduler Crashes (Current)

**Before crash:**
- 5 pods running
- 3 pods idle
- 2 gateways connected
- Resource counters accurate

**After crash (pod restarts):**
- ❌ All in-memory state lost
- ❌ Don't know which pods are running/idle
- ❌ Don't know which gateways have which workers
- ❌ Resource counters reset to zero

**Recovery process:**
1. Scheduler starts, creates etcd lease
2. StateSvc watch stream repopulates cache (Functions, Nodes)
3. **BUT:** Pod state is NOT in etcd (managed by NodeAgent)
4. Gateways must call ConnectScheduler to re-register workers
5. Resource accounting is WRONG until pods are reconciled

**Time to full recovery:** 30-60 seconds

**Risk during recovery:** Double-booking resources, lost workers

### Scenario 2: Scheduler Crashes (With PostgreSQL)

**Before crash:**
- All state in PostgreSQL

**After crash:**
- ✅ All state intact in database
- ✅ Query for running pods: immediate
- ✅ Resource counters: accurate
- ✅ Gateway leases: preserved

**Recovery process:**
1. Start new Scheduler instance
2. Query PostgreSQL for current state
3. Ready to serve requests

**Time to full recovery:** <5 seconds

### Scenario 3: Scheduler Crashes (With Temporal)

**Before crash:**
- Workflow state in Temporal

**After crash:**
- ✅ Workflows automatically resume
- ✅ Deployment in progress continues from last checkpoint
- ✅ No state lost

**Recovery process:**
- Temporal worker restarts
- Workflows resume automatically
- No manual intervention needed

**Time to full recovery:** <1 second

---

## Data That Actually Needs to Persist

### Critical (Must survive crashes):

1. **Function specs** - Model deployment configs
2. **Node inventory** - Available GPU resources
3. **Pod assignments** - Which pods are on which nodes
4. **Resource allocations** - How much VRAM/CPU is used per node
5. **Gateway → Worker leases** - Which Gateway owns which pods

**Current:** Items 1-2 in etcd, items 3-5 in-memory ONLY

**Should be:** All 5 in PostgreSQL or Temporal workflow state

### Ephemeral (Can rebuild quickly):

1. **Idle pod list** - Can query PostgreSQL: `SELECT * FROM pods WHERE state='idle'`
2. **Running pod list** - Can query: `SELECT * FROM pods WHERE state='running'`
3. **Gateway heartbeats** - Can timeout and reconnect

---

## Simplification Opportunities

### Replace Informer/Watcher with Direct Queries

**Current:**
```rust
// Continuous watch stream from StateSvc
// Maintains in-memory cache of all functions
// On every LeaseWorker: Check cache (in-memory lookup)
```

**Proposed:**
```python
# On every LeaseWorker: Query PostgreSQL
func = await db.fetchrow(
    "SELECT * FROM functions WHERE tenant=$1 AND namespace=$2 AND name=$3",
    tenant, namespace, funcname
)
```

**Performance difference:**
- Current: <1ms (in-memory)
- Proposed: 5-10ms (PostgreSQL with index)
- **Acceptable:** 9ms extra on a 2,000-8,000ms operation = 0.1% overhead

**Benefit:** No cache invalidation, no watch streams, no stale data

### Replace etcd Lease with Kubernetes Service

**Current:**
```rust
// Register in etcd with 1s TTL
store.Create("/registry/scheduler/...", leaseId);

// Keepalive every 200ms
loop {
    store.LeaseKeepalive(leaseId).await?;  // PANIC on failure
    sleep(200ms);
}
```

**Proposed:**
```yaml
# Kubernetes Service (already exists!)
apiVersion: v1
kind: Service
metadata:
  name: scheduler
spec:
  selector:
    app: scheduler
  ports:
  - port: 1238
```

**Gateway finds Scheduler:**
```python
# Current: Query etcd for scheduler IP
scheduler_info = await etcd.get("/registry/scheduler/...")
scheduler_url = f"http://{scheduler_info.svcIp}:{scheduler_info.port}"

# Proposed: Just use Kubernetes DNS
scheduler_url = "http://scheduler.default.svc:1238"
```

**No lease needed. DNS is stable.**

### Replace In-Memory State with PostgreSQL

**Current:**
```rust
self.runningPods: HashMap<String, Pod>  // Lost on crash
self.idlePods: HashMap<String, Pod>     // Lost on crash
self.nodes: HashMap<String, NodeStatus> // Rebuilt from watch, but accounting LOST
```

**Proposed:**
```sql
CREATE TABLE pods (
    id VARCHAR PRIMARY KEY,
    tenant VARCHAR,
    namespace VARCHAR,
    funcname VARCHAR,
    fprevision BIGINT,
    node_name VARCHAR,
    ip VARCHAR,
    port INT,
    state VARCHAR,  -- 'pending', 'running', 'idle', 'failed'
    allocated_vram INT,
    last_used TIMESTAMP,
    created_at TIMESTAMP
);

CREATE TABLE nodes (
    name VARCHAR PRIMARY KEY,
    agent_url VARCHAR,
    total_vram INT,
    used_vram INT,
    total_slots INT,
    used_slots INT,
    state VARCHAR,
    last_updated TIMESTAMP
);

CREATE TABLE gateway_leases (
    gateway_id BIGINT,
    pod_id VARCHAR,
    leased_at TIMESTAMP,
    PRIMARY KEY (gateway_id, pod_id)
);
```

**Benefits:**
- Survives crashes
- Queryable from anywhere
- No cache invalidation logic
- Transaction support (atomic updates)
- Built-in durability

---

## The Core Insight

**Every operation Scheduler performs is:**
1. Read from database/cache
2. Run algorithm (bin-packing)
3. Write to database/cache
4. Call NodeAgent HTTP endpoint

**Steps 1, 2, 3:** Data operations (no GPU)
**Step 4:** HTTP proxy to NodeAgent (which DOES GPU work)

**Scheduler is a stateful HTTP proxy with a bin-packing algorithm.**

**This does not require:**
- Separate pod
- etcd leases
- gRPC
- Rust
- 3,000 lines of code

**This could be:**
- 500 lines of Python
- PostgreSQL for state
- Temporal for durability
- HTTP endpoints (or Nexus operations)

---

## Conclusion

Scheduler is **100% data/metadata operations** with **ZERO GPU hardware access**.

The complexity exists because it mimics Kubernetes Scheduler architecture, which is designed for:
- 10,000 nodes
- 100,000 pods
- Millisecond scheduling decisions
- Distributed consensus

InferX needs:
- 4 nodes
- 10 pods
- 60ms scheduling is fine
- Single cluster (no distribution needed)

**The complexity is not justified.**
