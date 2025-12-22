# StateSvc Operations - Current Implementation

**Date:** 2025-12-22
**Protocol:** gRPC (ixmeta.proto)
**Port:** 1237

---

## gRPC Service Definition

```protobuf
service IxMetaService {
  rpc Version (VersionRequestMessage) returns (VersionResponseMessage) {}
  rpc GetAddr (GetAddrReqMessage) returns (GetAddrReponseMessage) {}
  rpc Get (GetRequestMessage) returns (GetResponseMessage) {}
  rpc List (ListRequestMessage) returns (ListResponseMessage) {}
  rpc Watch (WatchRequestMessage) returns (stream WEvent) {}
  rpc Create(CreateRequestMessage) returns (CreateResponseMessage) {}
  rpc Update(UpdateRequestMessage) returns (UpdateResponseMessage) {}
  rpc Delete(DeleteRequestMessage) returns (DeleteResponseMessage) {}
  rpc Uid(UidRequestMessage) returns (UidReponseMessage) {}
}

service ReqWatchingService {
  rpc Watch (ReqWatchRequest) returns (stream ReqEvent) {}
}
```

---

## Operations by Category

### 1. Tenant Operations

**Create Tenant**
- **Caller:** Gateway (Dashboard API)
- **Request:** `Create(objType="tenant", tenant="system", namespace="system", name="public", object={spec, status})`
- **Response:** `{error: "", revision: 12345}`
- **Action:** Write to etcd `/registry/tenant/system/system/{name}`
- **Side Effect:** None (permission grant happens in Gateway, not StateSvc)

**Get Tenant**
- **Caller:** Gateway
- **Request:** `Get(obj_type="tenant", tenant="system", namespace="system", name="public")`
- **Response:** `{error: "", obj: {tenant object}}`
- **Action:** Read from etcd or in-memory cache

**List Tenants**
- **Caller:** Gateway, Dashboard
- **Request:** `List(obj_type="tenant", tenant="system", namespace="system")`
- **Response:** `{error: "", revision: 12345, objs: [{tenant1}, {tenant2}]}`
- **Action:** Read from in-memory TenantMgr cache

**Delete Tenant**
- **Caller:** Gateway
- **Request:** `Delete(obj_type="tenant", tenant="system", namespace="system", name="public")`
- **Response:** `{error: "", revision: 12346}`
- **Action:** Delete from etcd, remove from cache

---

### 2. Namespace Operations

**Create Namespace**
- **Caller:** Gateway (Dashboard API)
- **Request:** `Create(objType="namespace", tenant="public", namespace="system", name="test", object={spec, status})`
- **Response:** `{error: "", revision: 12345}`
- **Action:** Write to etcd `/registry/namespace/{tenant}/system/{name}`

**Get Namespace**
- **Caller:** Gateway
- **Request:** `Get(obj_type="namespace", tenant="public", namespace="system", name="test")`
- **Response:** `{error: "", obj: {namespace object}}`
- **Action:** Read from in-memory NamespaceMgr cache

**List Namespaces**
- **Caller:** Gateway, Dashboard
- **Request:** `List(obj_type="namespace", tenant="public", namespace="system")`
- **Response:** `{error: "", objs: [{ns1}, {ns2}]}`
- **Action:** Read from cache

**Update Namespace**
- **Caller:** Gateway
- **Request:** `Update(expect_rev=12345, obj={updated namespace})`
- **Response:** `{error: "", revision: 12346}`
- **Action:** Update etcd, update cache

**Delete Namespace**
- **Caller:** Gateway
- **Request:** `Delete(obj_type="namespace", tenant="public", namespace="system", name="test")`
- **Response:** `{error: "", revision: 12347}`
- **Action:** Delete from etcd, remove from cache

---

### 3. Function (Model) Operations

**Create Function**
- **Caller:** Gateway (Dashboard "Deploy Model" API)
- **Request:** `Create(objType="function", tenant="public", namespace="test", name="glm-flash", object={spec, status})`
- **Response:** `{error: "", revision: 8912}`
- **Action:**
  1. Write function to etcd `/registry/function/{tenant}/{namespace}/{name}`
  2. Automatically create FunctionStatus in etcd (state="Normal", version=8912)
- **Side Effect:** Creates corresponding FunctionStatus object

**Get Function**
- **Caller:** Gateway, Scheduler
- **Request:** `Get(obj_type="function", tenant="public", namespace="test", name="glm-flash")`
- **Response:** `{error: "", obj: {function spec with image, commands, resources, policy, etc.}}`
- **Action:** Read from FuncMgr cache

**List Functions**
- **Caller:** Gateway, Dashboard, Scheduler
- **Request:** `List(obj_type="function", tenant="public", namespace="test", label_selector="", field_selector="")`
- **Response:** `{error: "", objs: [{func1}, {func2}, ...]}`
- **Action:** Read from cache, filter by selectors

**Update Function**
- **Caller:** Gateway (Dashboard "Update Model Config")
- **Request:** `Update(expect_rev=8912, obj={updated function spec})`
- **Response:** `{error: "", revision: 8913}`
- **Action:**
  1. Update function in etcd
  2. Update FunctionStatus (version=8913)
- **Side Effect:** Updates corresponding FunctionStatus

**Delete Function**
- **Caller:** Gateway (Dashboard "Delete Model")
- **Request:** `Delete(obj_type="function", tenant="public", namespace="test", name="glm-flash", expect_rev=8912)`
- **Response:** `{error: "", revision: 8913}`
- **Action:**
  1. Delete function from etcd
  2. Delete corresponding FunctionStatus
- **Side Effect:** Removes FunctionStatus

---

### 4. Function Status Operations

**Get Function Status**
- **Caller:** Dashboard (status queries)
- **Request:** `Get(obj_type="funcstatus", tenant="public", namespace="test", name="glm-flash")`
- **Response:** `{error: "", obj: {state: "Normal", version: 8912, snapshotingFailureCnt: 0, resumingFailureCnt: 0}}`
- **Action:** Read from etcd

**List Function Statuses**
- **Caller:** Dashboard
- **Request:** `List(obj_type="funcstatus", tenant="public", namespace="test")`
- **Response:** `{error: "", objs: [{status1}, {status2}]}`

**Update Function Status**
- **Caller:** NodeAgent (via StateSvc internal logic)
- **Request:** `Update(obj={funcstatus with state="Snapshotting"})`
- **Response:** `{error: "", revision: 12346}`
- **Action:** Update state, increment failure counters if needed

---

### 5. Node Operations

**Register Node** (via Create/Update)
- **Caller:** IxProxy (on startup and periodically)
- **Request:** `Create(objType="node_info", tenant="system", namespace="system", name="gpu-workerx2", object={nodeSpec})`
- **Response:** `{error: "", revision: 9605}`
- **Action:** Write to etcd `/registry/node_info/system/system/{nodename}`
- **NodeSpec contains:**
  - IPs: nodeIp, naIp
  - Ports: podMgrPort (1233), stateSvcPort, tsotSvcPort
  - Resources: CPU, Mem, GPUs (totalSlotCnt, vRam, map)
  - State: "NodeAgentAvaiable"

**Get Node**
- **Caller:** Scheduler (for placement decisions)
- **Request:** `Get(obj_type="node_info", tenant="system", namespace="system", name="gpu-workerx2")`
- **Response:** `{error: "", obj: {node with resources}}`
- **Action:** Read from cache (populated via watch)

**List Nodes**
- **Caller:** Scheduler (find available nodes), Dashboard
- **Request:** `List(obj_type="node_info", tenant="system", namespace="system")`
- **Response:** `{error: "", objs: [{node1}, {node2}]}`
- **Action:** Read all nodes from cache

**Update Node**
- **Caller:** IxProxy (resource updates, state changes)
- **Request:** `Update(expect_rev=9605, obj={updated node})`
- **Response:** `{error: "", revision: 9606}`
- **Action:** Update etcd, broadcast to watchers

---

### 6. Function Policy Operations

**Create Function Policy**
- **Caller:** Gateway (if using external policy objects)
- **Request:** `Create(objType="funcpolicy", obj={policy spec})`
- **Response:** `{error: "", revision: 12345}`
- **Action:** Write to etcd
- **Note:** Often embedded in Function.spec.policy instead

**Get Function Policy**
- **Request:** `Get(obj_type="funcpolicy", ...)`
- **Response:** `{error: "", obj: {policy with min_replica, max_replica, scaleout_policy, etc.}}`

---

### 7. Scheduler Registration

**Register Scheduler**
- **Caller:** Scheduler (on startup)
- **Request:** `Create(objType="scheduler", tenant="system", namespace="system", name="scheduler", object={svcIp, port})`
- **Response:** `{error: "", revision: 12345}`
- **Action:** Write to etcd with lease (1-second TTL)
- **Note:** Used for service discovery (Gateway finds Scheduler)

---

### 8. Utility Operations

**Version**
- **Caller:** Any (health check)
- **Request:** `Version()`
- **Response:** `{version: "0.1"}`
- **Action:** Return StateSvc version

**GetAddr**
- **Caller:** Services discovering StateSvc
- **Request:** `GetAddr()`
- **Response:** `{error: "", svcIp: "10.42.2.121", port: 1237}`
- **Action:** Return StateSvc's own IP and port

**Uid**
- **Caller:** Internal (generates unique IDs)
- **Request:** `Uid()`
- **Response:** `{error: "", uid: 9605}`
- **Action:** Query etcd for `/registry/unique_id` revision, return as monotonic counter

---

### 9. Watch Operations (Event Streaming)

**Watch (IxMetaService)**
- **Caller:** Scheduler, Gateway (continuous)
- **Request:** `Watch(obj_type="function", tenant="public", namespace="test")`
- **Response:** Stream of `WEvent` messages:
  ```
  {event_type: Add|Update|Delete, obj: {object}}
  ```
- **Action:** Stream etcd watch events to caller
- **Purpose:** Keep Scheduler/Gateway caches in sync

**Watch (ReqWatchingService)**
- **Caller:** Dashboard (for real-time request logs)
- **Request:** `Watch(tenant, namespace, funcname)`
- **Response:** Stream of `ReqEvent` from PostgreSQL
- **Action:** Listen to PostgreSQL `ReqAudit_insert` table, stream changes
- **Purpose:** Real-time inference request monitoring

---

## Message Types Summary

**For Temporal Implementation:**

| Operation | Temporal Message | Returns | Example |
|-----------|------------------|---------|---------|
| **Create** | `@workflow.update` | revision | Create tenant, namespace, function, node |
| **Update** | `@workflow.update` | revision | Update function spec, node state |
| **Delete** | `@workflow.update` | revision | Delete function, namespace |
| **Get** | `@workflow.query` | object | Get node, function, tenant |
| **List** | `@workflow.query` | objects | List functions, nodes |
| **Watch** | Stream/webhook | events | Real-time change notifications |
| **Version** | `@workflow.query` | version | Health check |
| **GetAddr** | `@workflow.query` | IP:port | Service discovery |
| **Uid** | `@workflow.query` | counter | Unique ID generation |

**Updates = Mutations (Create/Update/Delete)**
**Queries = Reads (Get/List/Version/GetAddr/Uid)**
**Watch = Special case (streaming)**

---

## Object Types Managed

From `state_svc.rs:59-67`:

1. **Node** (`node_info`) - GPU worker registrations
2. **Namespace** - Namespace definitions
3. **Function** - Model deployment specs
4. **FunctionStatus** (`funcstatus`) - Deployment state
5. **Tenant** - Tenant definitions
6. **FuncPolicy** (`funcpolicy`) - Scaling policies
7. **SchedulerInfo** (`scheduler`) - Scheduler service discovery

---

## Next Steps for Temporal Implementation

Map these operations to:
1. Nexus service definition (contract)
2. Workflow update handlers (Create/Update/Delete)
3. Workflow query handlers (Get/List/Version/GetAddr/Uid)
4. Activities for PostgreSQL persistence
