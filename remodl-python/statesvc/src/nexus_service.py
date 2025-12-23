"""
Nexus service definition for StateSvc.

Exposes StateSvc operations as Nexus operations that can be called
from external services (IxProxy, Gateway) via HTTP.
"""

import nexusrpc
from typing import Optional, List

# Import through passthrough if needed in handlers
from inferx_common.models import (
    Tenant, Namespace, Function, FunctionStatus, NodeInfo
)


# ==================== Request/Response Models ====================

# Using the existing dataclasses as Nexus operation input/output


# ==================== Nexus Service Definition ====================

@nexusrpc.service
class StateSvcNexusService:
    """
    StateSvc Nexus service contract.

    Defines all operations that external services can call.
    """

    # Tenant operations
    create_tenant: nexusrpc.Operation[tuple[Tenant, str], int]  # (tenant, creator_username) -> revision
    delete_tenant: nexusrpc.Operation[str, int]  # tenant_name -> revision
    get_tenant: nexusrpc.Operation[str, Optional[Tenant]]  # tenant_name -> Tenant or None
    list_tenants: nexusrpc.Operation[None, List[Tenant]]  # () -> [Tenant]

    # Namespace operations
    create_namespace: nexusrpc.Operation[tuple[Namespace, Optional[str]], int]  # (namespace, creator) -> revision
    update_namespace: nexusrpc.Operation[Namespace, int]  # namespace -> revision
    delete_namespace: nexusrpc.Operation[tuple[str, str], int]  # (tenant, namespace) -> revision
    get_namespace: nexusrpc.Operation[tuple[str, str], Optional[Namespace]]  # (tenant, namespace) -> Namespace or None
    list_namespaces: nexusrpc.Operation[Optional[str], List[Namespace]]  # tenant -> [Namespace]

    # Function operations
    create_function: nexusrpc.Operation[Function, int]  # function -> revision
    update_function: nexusrpc.Operation[Function, int]  # function -> revision
    delete_function: nexusrpc.Operation[tuple[str, str, str, int], int]  # (tenant, ns, name, version) -> revision
    get_function: nexusrpc.Operation[tuple[str, str, str, Optional[int]], Optional[Function]]  # -> Function or None
    list_functions: nexusrpc.Operation[tuple[Optional[str], Optional[str]], List[Function]]  # (tenant, ns) -> [Function]

    # Function status operations
    update_function_status: nexusrpc.Operation[FunctionStatus, int]  # status -> revision
    get_function_status: nexusrpc.Operation[tuple[str, str, str, int], Optional[FunctionStatus]]  # -> FunctionStatus or None
    list_function_status: nexusrpc.Operation[tuple[Optional[str], Optional[str]], List[FunctionStatus]]  # -> [FunctionStatus]

    # Node operations
    register_node: nexusrpc.Operation[NodeInfo, int]  # node -> revision
    update_node_state: nexusrpc.Operation[tuple[str, str], int]  # (node_name, state) -> revision
    delete_node: nexusrpc.Operation[str, int]  # node_name -> revision
    get_node: nexusrpc.Operation[str, Optional[NodeInfo]]  # node_name -> NodeInfo or None
    list_nodes: nexusrpc.Operation[None, List[NodeInfo]]  # () -> [NodeInfo]

    # Utility operations
    version: nexusrpc.Operation[None, str]  # () -> version string
    get_addr: nexusrpc.Operation[None, dict]  # () -> {svcIp, port}
    uid: nexusrpc.Operation[None, int]  # () -> unique_id
    increment_uid: nexusrpc.Operation[None, int]  # () -> incremented_uid
