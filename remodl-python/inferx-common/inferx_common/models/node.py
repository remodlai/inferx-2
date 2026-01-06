"""
Node models for GPU worker registration.
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, Literal
from datetime import datetime

from .gpu import GPUResourceMap


class NodeResources(BaseModel):
    """Complete node resource specification"""
    nodename: str = Field(description="Kubernetes node name")
    CPU: int = Field(description="Total CPU in milli-cores (e.g., 20000 = 20 cores)")
    Mem: int = Field(description="Total memory in MB")
    CacheMem: int = Field(description="Cache memory in MB")
    GPUType: str = Field(description="GPU model (e.g., 'NVIDIA A100 80GB PCIe')")
    GPUs: GPUResourceMap = Field(description="GPU resource allocation map")
    MaxContextPerGPU: int = Field(default=1, description="Max contexts per GPU")


class NodeSpec(BaseModel):
    """Node specification registered by IxProxy"""
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


class NodeInfo(BaseModel):
    """Complete node object as stored in etcd/database"""
    objType: str = Field(default="node_info", description="Object type identifier")
    tenant: str = Field(default="system", description="Tenant (always 'system' for nodes)")
    namespace: str = Field(default="system", description="Namespace (always 'system' for nodes)")
    name: str = Field(description="Node name (matches nodename in spec)")

    object: NodeSpec = Field(description="Node specification and resources")

    channelRev: Optional[int] = Field(default=0, description="Channel revision for caching")
    revision: Optional[int] = Field(default=0, description="etcd revision")
    srcEpoch: Optional[int] = Field(default=0, description="Source epoch")

    labels: Dict[str, str] = Field(default_factory=dict, description="Node labels")
    annotations: Dict[str, str] = Field(default_factory=dict, description="Node annotations")

    created_at: Optional[datetime] = Field(default=None, description="Registration timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
