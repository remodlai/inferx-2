"""
Pydantic models for InferX StateSvc objects.

These models match the current Rust implementation data structures
stored in etcd, enabling drop-in compatibility with existing IxProxy/NodeAgent.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal, List, Any, Union
from datetime import datetime


# ==================== GPU Resources ====================

class GPUAlloc(BaseModel):
    """GPU allocation tracking for a single GPU device"""
    contextCnt: int = Field(description="Number of active contexts")
    slotCnt: int = Field(description="Number of VRAM slots (256MB each)")
    ncclCnt: int = Field(description="NCCL communication count")


class GPUResourceMap(BaseModel):
    """GPU resource map tracking all GPUs on a node"""
    totalSlotCnt: int = Field(description="Total VRAM slots across all GPUs")
    slotSize: int = Field(default=268435456, description="Size per slot in bytes (256MB)")
    vRam: int = Field(description="Total VRAM in MB")
    map: Dict[str, GPUAlloc] = Field(
        default_factory=dict,
        description="Per-GPU allocation map, keyed by GPU ID (0, 1, 2, ...)"
    )


class NodeResources(BaseModel):
    """Complete node resource specification"""
    nodename: str = Field(description="Kubernetes node name")
    CPU: int = Field(description="Total CPU in milli-cores (e.g., 20000 = 20 cores)")
    Mem: int = Field(description="Total memory in MB")
    CacheMem: int = Field(description="Cache memory in MB")
    GPUType: str = Field(description="GPU model (e.g., 'NVIDIA A100 80GB PCIe')")
    GPUs: GPUResourceMap = Field(description="GPU resource allocation map")
    MaxContextPerGPU: int = Field(default=1, description="Max contexts per GPU")


# ==================== Node Specification ====================

class NodeSpec(BaseModel):
    """
    Node specification registered by IxProxy.

    This matches the Rust NodeSpec structure from:
    ixshare/src/state_svc/IxAggrStore.rs
    """
    nodename: str = Field(description="Kubernetes node name (e.g., 'gpu-workerx2')")
    nodeEpoch: int = Field(description="Node registration epoch/version")

    # Network configuration
    nodeIp: str = Field(description="IxProxy pod IP address")
    naIp: str = Field(description="NodeAgent pod IP address")
    cidr: str = Field(description="Internal container network CIDR")

    # Service ports
    podMgrPort: int = Field(default=1233, description="NodeAgent gRPC service port")
    stateSvcPort: int = Field(default=1236, description="StateSvc port on node")
    tsotSvcPort: int = Field(default=1235, description="Tsot service port")

    # Resources
    resources: NodeResources = Field(description="Node compute and GPU resources")

    # State and capabilities
    state: Literal["NodeAgentAvaiable", "NodeAgentUnavailable", "Draining"] = Field(
        default="NodeAgentAvaiable",
        description="Node availability state"
    )
    blobStoreEnable: bool = Field(default=False, description="Blob storage enabled")
    CUDA_VISIBLE_DEVICES: str = Field(default="None", description="CUDA visible devices")


# ==================== Node Info (Complete Object) ====================

class NodeInfo(BaseModel):
    """
    Complete node object as stored in etcd at:
    /registry/node_info/system/system/{nodename}

    Used for registration and discovery.
    """
    # Metadata
    objType: str = Field(default="node_info", description="Object type identifier")
    tenant: str = Field(default="system", description="Tenant (always 'system' for nodes)")
    namespace: str = Field(default="system", description="Namespace (always 'system' for nodes)")
    name: str = Field(description="Node name (matches nodename in spec)")

    # Node specification
    object: NodeSpec = Field(description="Node specification and resources")

    # Internal tracking
    channelRev: Optional[int] = Field(default=0, description="Channel revision for caching")
    revision: Optional[int] = Field(default=0, description="etcd revision")
    srcEpoch: Optional[int] = Field(default=0, description="Source epoch")

    # Optional labels/annotations
    labels: Dict[str, str] = Field(default_factory=dict, description="Node labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Node annotations")

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Registration timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")


# ==================== Tenant ====================

class TenantSpec(BaseModel):
    """Tenant specification (currently empty in production)"""
    pass


class TenantStatus(BaseModel):
    """Tenant status"""
    disable: bool = Field(default=False, description="Whether tenant is disabled")


class TenantObject(BaseModel):
    """Tenant spec and status combined"""
    spec: TenantSpec = Field(default_factory=TenantSpec)
    status: TenantStatus = Field(default_factory=TenantStatus)


class Tenant(BaseModel):
    """
    Tenant object as stored in etcd at:
    /registry/tenant/system/system/{tenant_name}
    """
    objType: str = Field(default="tenant", description="Object type identifier")
    tenant: str = Field(default="system", description="Parent tenant (always 'system')")
    namespace: str = Field(default="system", description="Parent namespace (always 'system')")
    name: str = Field(description="Tenant name (e.g., 'public')")

    object: TenantObject = Field(description="Tenant spec and status")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


# ==================== Namespace ====================

class NamespaceSpec(BaseModel):
    """Namespace specification (currently empty in production)"""
    pass


class NamespaceStatus(BaseModel):
    """Namespace status"""
    disable: bool = Field(default=False, description="Whether namespace is disabled")


class NamespaceObject(BaseModel):
    """Namespace spec and status combined"""
    spec: NamespaceSpec = Field(default_factory=NamespaceSpec)
    status: NamespaceStatus = Field(default_factory=NamespaceStatus)


class Namespace(BaseModel):
    """
    Namespace object as stored in etcd at:
    /registry/namespace/{tenant}/system/{namespace_name}
    """
    objType: str = Field(default="namespace", description="Object type identifier")
    tenant: str = Field(description="Parent tenant (e.g., 'public')")
    namespace: str = Field(default="system", description="Parent namespace (always 'system')")
    name: str = Field(description="Namespace name (e.g., 'test')")

    object: NamespaceObject = Field(description="Namespace spec and status")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


# ==================== Function (Model Deployment) ====================

class EndpointConfig(BaseModel):
    """Health check endpoint configuration"""
    port: int = Field(default=8000, description="Service port")
    schema: Literal["Http", "Https"] = Field(default="Http", description="Protocol")
    probe: str = Field(default="/health", description="Health check path")
    probeTimeout: int = Field(default=1000, description="Probe timeout in ms")


class GPUResourceSpec(BaseModel):
    """GPU resource requirements"""
    Type: str = Field(default="Any", description="GPU type (e.g., 'A100', 'L40', 'Any')")
    Count: int = Field(default=1, description="Number of GPUs required")
    vRam: int = Field(description="VRAM required in MB")
    contextCount: int = Field(default=0, description="Context count")


class ResourceSpec(BaseModel):
    """Resource requirements for function"""
    CPU: int = Field(description="CPU in milli-cores")
    Mem: int = Field(description="Memory in MB")
    CacheMem: int = Field(default=5000, description="Cache memory in MB")
    ReadyMem: int = Field(default=1000, description="Ready memory in MB")
    GPU: GPUResourceSpec = Field(description="GPU requirements")


class ScaleoutPolicy(BaseModel):
    """Scaleout policy (currently uses WaitQueueRatio)"""
    WaitQueueRatio: Optional[Dict[str, float]] = Field(default=None, description="Wait queue ratio policy")


class RuntimeConfig(BaseModel):
    """Runtime configuration"""
    graph_sync: bool = Field(default=True, description="Graph sync enabled")


class FuncPolicySpec(BaseModel):
    """Function scaling policy"""
    min_replica: int = Field(default=0, description="Minimum replicas")
    max_replica: int = Field(default=10, description="Maximum replicas")
    parallel: int = Field(default=2, description="Parallel processing count")
    queue_len: int = Field(default=1000, description="Queue length")
    queue_timeout: float = Field(default=60.0, description="Queue timeout in seconds")
    scaleout_policy: ScaleoutPolicy = Field(description="Scaleout policy")
    scalein_timeout: float = Field(default=0.01, description="Scale-in timeout in seconds")
    standby_per_node: int = Field(default=1, description="Standby pods per node")
    runtime_config: RuntimeConfig = Field(default_factory=RuntimeConfig, description="Runtime config")


class FuncPolicyObject(BaseModel):
    """Function policy wrapper"""
    Obj: FuncPolicySpec = Field(description="Policy specification")


class StandbyConfig(BaseModel):
    """Snapshot standby configuration"""
    gpu: Literal["File", "Memory"] = Field(default="File", description="GPU memory snapshot location")
    pageable: Literal["File", "Memory"] = Field(default="File", description="Pageable memory location")
    pinned: Literal["File", "Memory"] = Field(default="File", description="Pinned memory location")


class SampleQuery(BaseModel):
    """Sample query for testing the function"""
    apiType: str = Field(description="API type (e.g., 'text2text', 'image2text')")
    path: str = Field(description="API path (e.g., 'v1/completions')")
    prompt: str = Field(default="", description="Sample prompt")
    prompts: List[str] = Field(default_factory=list, description="Multiple prompts")
    imageUrl: str = Field(default="", description="Image URL for multimodal")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body")


class VolumeMount(BaseModel):
    """Volume mount specification"""
    hostpath: str = Field(description="Host path to mount")
    mountpath: str = Field(description="Container mount path")


class FunctionSpec(BaseModel):
    """Function deployment specification"""
    image: str = Field(description="Container image (e.g., 'remodlai/vllm-openai-mcp-tf:v0.12.0')")
    commands: List[str] = Field(description="Command arguments (model path + vLLM flags)")
    entrypoint: List[str] = Field(default_factory=lambda: ["vllm", "serve"], description="Container entrypoint")
    envs: List[List[str]] = Field(default_factory=list, description="Environment variables [[KEY, VALUE], ...]")
    mounts: List[VolumeMount] = Field(default_factory=list, description="Volume mounts")
    endpoint: EndpointConfig = Field(description="Health check endpoint config")
    resources: ResourceSpec = Field(description="Resource requirements")
    policy: FuncPolicyObject = Field(description="Scaling policy")
    standby: StandbyConfig = Field(description="Snapshot configuration")
    sample_query: SampleQuery = Field(description="Sample query for testing")
    version: int = Field(description="Function version/revision")


class FunctionObject(BaseModel):
    """Function spec and status combined"""
    spec: FunctionSpec = Field(description="Function specification")
    status: Dict[str, Any] = Field(default_factory=dict, description="Function status")


class Function(BaseModel):
    """
    Function object as stored in etcd at:
    /registry/function/{tenant}/{namespace}/{funcname}
    """
    objType: str = Field(default="function", description="Object type identifier")
    tenant: str = Field(description="Tenant (e.g., 'public')")
    namespace: str = Field(description="Namespace (e.g., 'test')")
    name: str = Field(description="Function name (e.g., 'glm-flash')")

    object: FunctionObject = Field(description="Function spec and status")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


# ==================== Function Status ====================

class FunctionStatusDef(BaseModel):
    """Function status definition"""
    state: Literal["Normal", "Failed", "Snapshotting", "Resuming"] = Field(
        default="Normal",
        description="Function state"
    )
    version: int = Field(description="Function version")
    snapshotingFailureCnt: int = Field(default=0, description="Snapshot failure count")
    resumingFailureCnt: int = Field(default=0, description="Resume failure count")


class FunctionStatus(BaseModel):
    """
    Function status object as stored in etcd at:
    /registry/funcstatus/{tenant}/{namespace}/{funcname}
    """
    objType: str = Field(default="funcstatus", description="Object type identifier")
    tenant: str = Field(description="Tenant")
    namespace: str = Field(description="Namespace")
    name: str = Field(description="Function name")

    object: FunctionStatusDef = Field(description="Status details")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


# ==================== Function Policy ====================

class FuncPolicy(BaseModel):
    """
    Function policy object as stored in etcd at:
    /registry/funcpolicy/{tenant}/{namespace}/{policy_name}

    Note: This can be embedded in Function.spec.policy or stored separately
    """
    objType: str = Field(default="funcpolicy", description="Object type identifier")
    tenant: str = Field(description="Tenant")
    namespace: str = Field(description="Namespace")
    name: str = Field(description="Policy name")

    object: FuncPolicySpec = Field(description="Policy specification")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)
    labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


# ==================== Scheduler Info ====================

class SchedulerInfo(BaseModel):
    """
    Scheduler registration object as stored in etcd at:
    /registry/scheduler/system/system/scheduler

    Used for service discovery (scheduler IP:port).
    With Temporal, this becomes unnecessary (use Kubernetes DNS).
    """
    objType: str = Field(default="scheduler", description="Object type identifier")
    tenant: str = Field(default="system", description="Tenant (always 'system')")
    namespace: str = Field(default="system", description="Namespace (always 'system')")
    name: str = Field(default="scheduler", description="Name (always 'scheduler')")

    svcIp: str = Field(description="Scheduler service IP")
    port: int = Field(default=1238, description="Scheduler service port")

    channelRev: Optional[int] = Field(default=0)
    revision: Optional[int] = Field(default=0)
    srcEpoch: Optional[int] = Field(default=0)


# ==================== Example (for testing) ====================

# Example NodeInfo matching actual etcd data from gpu-workerx2:
#
# example_node = NodeInfo(
#     objType="node_info",
#     tenant="system",
#     namespace="system",
#     name="gpu-workerx2",
#     object=NodeSpec(
#         nodename="gpu-workerx2",
#         nodeEpoch=9605,
#         nodeIp="10.42.4.234",
#         naIp="10.42.4.235",
#         cidr="10.0.0.0",
#         podMgrPort=1233,
#         stateSvcPort=1236,
#         tsotSvcPort=1235,
#         resources=NodeResources(
#             nodename="gpu-workerx2",
#             CPU=20000,
#             Mem=92160,
#             CacheMem=10240,
#             GPUType="NVIDIA A100 80GB PCIe",
#             GPUs=GPUResourceMap(
#                 totalSlotCnt=279,
#                 slotSize=268435456,
#                 vRam=71424,
#                 map={
#                     "0": GPUAlloc(contextCnt=1, slotCnt=279, ncclCnt=1)
#                 }
#             ),
#             MaxContextPerGPU=1
#         ),
#         state="NodeAgentAvaiable",
#         blobStoreEnable=False,
#         CUDA_VISIBLE_DEVICES="None"
#     ),
#     channelRev=204,
#     revision=9605,
#     srcEpoch=0,
#     labels={},
#     annotations={}
# )
#
# # Test validation
# print(example_node.model_dump_json(indent=2, exclude_none=True))
#
# # Test helper usage (if added later)
# # print(f"Agent URL: {example_node.object.naIp}:{example_node.object.podMgrPort}")
# # print(f"Total VRAM: {example_node.object.resources.GPUs.vRam} MB")
# # print(f"GPU Count: {len(example_node.object.resources.GPUs.map)}")

# Example Tenant matching actual etcd data:
#
# example_tenant = Tenant(
#     objType="tenant",
#     tenant="system",
#     namespace="system",
#     name="public",
#     object=TenantObject(
#         spec=TenantSpec(),
#         status=TenantStatus(disable=False)
#     )
# )

# Example Namespace matching actual etcd data:
#
# example_namespace = Namespace(
#     objType="namespace",
#     tenant="public",
#     namespace="system",
#     name="test",
#     object=NamespaceObject(
#         spec=NamespaceSpec(),
#         status=NamespaceStatus(disable=False)
#     )
# )

# Example Function matching actual etcd data from glm-flash:
#
# example_function = Function(
#     objType="function",
#     tenant="public",
#     namespace="test",
#     name="glm-flash",
#     object=FunctionObject(
#         spec=FunctionSpec(
#             image="remodlai/vllm-openai-mcp-tf:v0.12.0",
#             commands=[
#                 "/root/.cache/huggingface/hub/models--zai-org--GLM-4.6V-Flash/snapshots/411bb4d77144a3f03accbf4b780f5acb8b7cde4e",
#                 "--trust-remote-code",
#                 "--served-model-name", "GLM-4.6V-Flash",
#                 "--tool-call-parser", "glm45",
#                 "--reasoning-parser", "glm45",
#                 "--enable-auto-tool-choice",
#                 "--mm-processor-cache-type", "shm",
#                 "--max-num-batched-tokens", "8192"
#             ],
#             entrypoint=["vllm", "serve"],
#             envs=[
#                 ["LD_LIBRARY_PATH", "/usr/local/lib/python3.12/dist-packages/nvidia/cuda_nvrtc/lib/:$LD_LIBRARY_PATH"],
#                 ["TORCH_CUDA_ARCH_LIST", "8.0;8.0+PTX"],
#                 ["HF_TOKEN", "hf_XXXXXXXXXXXXXXXXXXXXX"],
#                 ["HF_HUB_OFFLINE", "1"],
#                 ["VLLM_LOGGING_LEVEL", "DEBUG"]
#             ],
#             mounts=[
#                 VolumeMount(
#                     hostpath="/opt/inferx/cache",
#                     mountpath="/root/.cache/huggingface"
#                 )
#             ],
#             endpoint=EndpointConfig(
#                 port=8000,
#                 schema="Http",
#                 probe="/health",
#                 probeTimeout=1000
#             ),
#             resources=ResourceSpec(
#                 CPU=15000,
#                 Mem=20000,
#                 CacheMem=5000,
#                 ReadyMem=1000,
#                 GPU=GPUResourceSpec(
#                     Type="Any",
#                     Count=1,
#                     vRam=46000,
#                     contextCount=0
#                 )
#             ),
#             policy=FuncPolicyObject(
#                 Obj=FuncPolicySpec(
#                     min_replica=0,
#                     max_replica=10,
#                     parallel=2,
#                     queue_len=1000,
#                     queue_timeout=60.0,
#                     scaleout_policy=ScaleoutPolicy(
#                         WaitQueueRatio={"wait_ratio": 0.1}
#                     ),
#                     scalein_timeout=0.01,
#                     standby_per_node=1,
#                     runtime_config=RuntimeConfig(graph_sync=True)
#                 )
#             ),
#             standby=StandbyConfig(
#                 gpu="File",
#                 pageable="File",
#                 pinned="File"
#             ),
#             sample_query=SampleQuery(
#                 apiType="text2text",
#                 path="v1/completions",
#                 prompt="def print_hello_world():",
#                 prompts=[],
#                 imageUrl="",
#                 body={
#                     "max_tokens": "120",
#                     "model": "GLM-4.6V-Flash",
#                     "stream": "true",
#                     "temperature": "0.7"
#                 }
#             ),
#             version=8912
#         ),
#         status={}
#     ),
#     revision=0
# )

# Example FunctionStatus matching actual etcd data:
#
# example_funcstatus = FunctionStatus(
#     objType="funcstatus",
#     tenant="public",
#     namespace="test",
#     name="glm-flash",
#     object=FunctionStatusDef(
#         state="Normal",
#         version=8912,
#         snapshotingFailureCnt=0,
#         resumingFailureCnt=0
#     )
# )

# Example SchedulerInfo matching actual etcd data:
#
# example_scheduler = SchedulerInfo(
#     objType="scheduler",
#     tenant="system",
#     namespace="system",
#     name="scheduler",
#     svcIp="10.42.4.218",
#     port=1238
# )
