"""
Function (model deployment) models.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Literal, Any

from .gpu import GPUResourceSpec


class EndpointConfig(BaseModel):
    """Health check endpoint configuration"""
    port: int = Field(default=8000, description="Service port")
    schema: Literal["Http", "Https"] = Field(default="Http", description="Protocol")
    probe: str = Field(default="/health", description="Health check path")
    probeTimeout: int = Field(default=1000, description="Probe timeout in ms")


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
    """Function object as stored in etcd/database"""
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


class FuncPolicy(BaseModel):
    """Function policy object (can be stored separately or embedded in Function)"""
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
