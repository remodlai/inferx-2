"""
Scheduler-specific models for pod tracking and gateway state.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class WorkerId(BaseModel):
    """Worker identifier"""
    tenant: str
    namespace: str
    funcname: str
    fprevision: int
    id: str


class PodInfo(BaseModel):
    """Pod information tracked by scheduler"""
    id: str
    tenant: str
    namespace: str
    funcname: str
    fprevision: int
    node_name: str
    ipaddr: str  # String representation of IP
    port: int
    state: str  # "pending", "running", "idle", "failed"
    allocated_vram: int
    allocated_cpu: int
    allocated_mem: int
    created_at: datetime
    last_used: Optional[datetime] = None


class GatewayConnection(BaseModel):
    """Gateway connection tracking"""
    gateway_id: int
    workers: List[WorkerId]
    last_refresh: datetime


class NodeResourceTracking(BaseModel):
    """Resource usage tracking for a node"""
    node_name: str
    total_vram: int
    used_vram: int
    available_vram: int
    total_cpu: int
    used_cpu: int
    total_mem: int
    used_mem: int
    total_gpu_slots: int
    used_gpu_slots: int
