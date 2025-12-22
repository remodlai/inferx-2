"""
InferX common models package.

Organized exports for different services.
"""

# Individual model exports
from .gpu import GPUAlloc, GPUResourceMap, GPUResourceSpec
from .node import NodeResources, NodeSpec, NodeInfo
from .tenant import TenantSpec, TenantStatus, TenantObject, Tenant
from .namespace import NamespaceSpec, NamespaceStatus, NamespaceObject, Namespace
from .function import (
    EndpointConfig, ResourceSpec, ScaleoutPolicy, RuntimeConfig,
    FuncPolicySpec, FuncPolicyObject, StandbyConfig, SampleQuery,
    VolumeMount, FunctionSpec, FunctionObject, Function, FuncPolicy
)
from .function_status import FunctionStatusDef, FunctionStatus


# Grouped exports for StateSvc
statesvc_models = [
    # Core state objects
    Tenant, TenantObject, TenantSpec, TenantStatus,
    Namespace, NamespaceObject, NamespaceSpec, NamespaceStatus,
    Function, FunctionObject, FunctionSpec,
    FunctionStatus, FunctionStatusDef,
    FuncPolicy, FuncPolicySpec, FuncPolicyObject,
    NodeInfo, NodeSpec, NodeResources,
    # Supporting models
    GPUAlloc, GPUResourceMap, GPUResourceSpec,
    EndpointConfig, ResourceSpec, StandbyConfig,
    SampleQuery, VolumeMount,
    ScaleoutPolicy, RuntimeConfig,
]


# Grouped exports for Scheduler
scheduler_models = [
    # Function and node models (scheduler queries these)
    Function, FunctionObject, FunctionSpec,
    NodeInfo, NodeSpec, NodeResources,
    # Resource tracking
    GPUResourceMap, GPUAlloc, GPUResourceSpec,
    ResourceSpec, FuncPolicySpec,
]


__all__ = [
    # GPU
    "GPUAlloc", "GPUResourceMap", "GPUResourceSpec",
    # Node
    "NodeResources", "NodeSpec", "NodeInfo",
    # Tenant
    "TenantSpec", "TenantStatus", "TenantObject", "Tenant",
    # Namespace
    "NamespaceSpec", "NamespaceStatus", "NamespaceObject", "Namespace",
    # Function
    "EndpointConfig", "ResourceSpec", "ScaleoutPolicy", "RuntimeConfig",
    "FuncPolicySpec", "FuncPolicyObject", "StandbyConfig", "SampleQuery",
    "VolumeMount", "FunctionSpec", "FunctionObject", "Function", "FuncPolicy",
    # Function Status
    "FunctionStatusDef", "FunctionStatus",
    # Grouped exports
    "statesvc_models",
    "scheduler_models",
]
