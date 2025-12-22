"""
Nexus operation handlers for StateSvc.

Implements handlers that call StateSvc workflow updates/queries.
"""

import nexusrpc
from nexusrpc.handler import service_handler, sync_operation
from temporalio import nexus
from typing import Optional, List

from .nexus_service import StateSvcNexusService
from .workflows import StateSvcWorkflow
from .dataclasses import (
    Tenant, Namespace, Function, FunctionStatus, NodeInfo
)


@service_handler(service=StateSvcNexusService)
class StateSvcNexusHandler:
    """
    Nexus operation handlers for StateSvc.

    All operations are synchronous (must complete in <10s).
    They call the singleton StateSvcWorkflow via execute_update or query.
    """

    @property
    def statesvc_handle(self):
        """Get handle to singleton StateSvc workflow"""
        return nexus.client().get_workflow_handle("statesvc-singleton")

    # ==================== Tenant Operations ====================

    @sync_operation
    async def create_tenant(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[Tenant, str]
    ) -> int:
        """Create tenant"""
        tenant, creator_username = input
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.create_tenant,
            args=[tenant, creator_username]
        )

    @nexusrpc.handler.sync_operation
    async def delete_tenant(
        self, ctx: nexusrpc.handler.StartOperationContext, input: str
    ) -> int:
        """Delete tenant"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.delete_tenant,
            input
        )

    @nexusrpc.handler.sync_operation
    async def get_tenant(
        self, ctx: nexusrpc.handler.StartOperationContext, input: str
    ) -> Optional[Tenant]:
        """Get tenant"""
        return await self.statesvc_handle.query(
            StateSvcWorkflow.get_tenant,
            input
        )

    @nexusrpc.handler.sync_operation
    async def list_tenants(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> List[Tenant]:
        """List all tenants"""
        return await self.statesvc_handle.query(StateSvcWorkflow.list_tenants)

    # ==================== Namespace Operations ====================

    @nexusrpc.handler.sync_operation
    async def create_namespace(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[Namespace, Optional[str]]
    ) -> int:
        """Create namespace"""
        namespace, creator_username = input
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.create_namespace,
            args=[namespace, creator_username]
        )

    @nexusrpc.handler.sync_operation
    async def update_namespace(
        self, ctx: nexusrpc.handler.StartOperationContext, input: Namespace
    ) -> int:
        """Update namespace"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.update_namespace,
            input
        )

    @nexusrpc.handler.sync_operation
    async def delete_namespace(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str]
    ) -> int:
        """Delete namespace"""
        tenant, namespace = input
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.delete_namespace,
            args=[tenant, namespace]
        )

    @nexusrpc.handler.sync_operation
    async def get_namespace(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str]
    ) -> Optional[Namespace]:
        """Get namespace"""
        tenant, namespace = input
        return await self.statesvc_handle.query(
            StateSvcWorkflow.get_namespace,
            args=[tenant, namespace]
        )

    @nexusrpc.handler.sync_operation
    async def list_namespaces(
        self, ctx: nexusrpc.handler.StartOperationContext, input: Optional[str]
    ) -> List[Namespace]:
        """List namespaces"""
        return await self.statesvc_handle.query(
            StateSvcWorkflow.list_namespaces,
            input
        )

    # ==================== Function Operations ====================

    @nexusrpc.handler.sync_operation
    async def create_function(
        self, ctx: nexusrpc.handler.StartOperationContext, input: Function
    ) -> int:
        """Create function"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.create_function,
            input
        )

    @nexusrpc.handler.sync_operation
    async def update_function(
        self, ctx: nexusrpc.handler.StartOperationContext, input: Function
    ) -> int:
        """Update function"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.update_function,
            input
        )

    @nexusrpc.handler.sync_operation
    async def delete_function(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str, str, int]
    ) -> int:
        """Delete function"""
        tenant, namespace, name, version = input
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.delete_function,
            args=[tenant, namespace, name, version]
        )

    @nexusrpc.handler.sync_operation
    async def get_function(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str, str, Optional[int]]
    ) -> Optional[Function]:
        """Get function"""
        tenant, namespace, name, version = input
        return await self.statesvc_handle.query(
            StateSvcWorkflow.get_function,
            args=[tenant, namespace, name, version]
        )

    @nexusrpc.handler.sync_operation
    async def list_functions(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[Optional[str], Optional[str]]
    ) -> List[Function]:
        """List functions"""
        tenant, namespace = input
        return await self.statesvc_handle.query(
            StateSvcWorkflow.list_functions,
            args=[tenant, namespace]
        )

    # ==================== Function Status Operations ====================

    @nexusrpc.handler.sync_operation
    async def update_function_status(
        self, ctx: nexusrpc.handler.StartOperationContext, input: FunctionStatus
    ) -> int:
        """Update function status"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.update_function_status,
            input
        )

    @nexusrpc.handler.sync_operation
    async def get_function_status(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str, str, int]
    ) -> Optional[FunctionStatus]:
        """Get function status"""
        tenant, namespace, name, version = input
        return await self.statesvc_handle.query(
            StateSvcWorkflow.get_function_status,
            args=[tenant, namespace, name, version]
        )

    @nexusrpc.handler.sync_operation
    async def list_function_status(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[Optional[str], Optional[str]]
    ) -> List[FunctionStatus]:
        """List function statuses"""
        tenant, namespace = input
        return await self.statesvc_handle.query(
            StateSvcWorkflow.list_function_status,
            args=[tenant, namespace]
        )

    # ==================== Node Operations ====================

    @nexusrpc.handler.sync_operation
    async def register_node(
        self, ctx: nexusrpc.handler.StartOperationContext, input: NodeInfo
    ) -> int:
        """Register node"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.register_node,
            input
        )

    @nexusrpc.handler.sync_operation
    async def update_node_state(
        self, ctx: nexusrpc.handler.StartOperationContext, input: tuple[str, str]
    ) -> int:
        """Update node state"""
        node_name, state = input
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.update_node_state,
            args=[node_name, state]
        )

    @nexusrpc.handler.sync_operation
    async def delete_node(
        self, ctx: nexusrpc.handler.StartOperationContext, input: str
    ) -> int:
        """Delete node"""
        return await self.statesvc_handle.execute_update(
            StateSvcWorkflow.delete_node,
            input
        )

    @nexusrpc.handler.sync_operation
    async def get_node(
        self, ctx: nexusrpc.handler.StartOperationContext, input: str
    ) -> Optional[NodeInfo]:
        """Get node"""
        return await self.statesvc_handle.query(
            StateSvcWorkflow.get_node,
            input
        )

    @nexusrpc.handler.sync_operation
    async def list_nodes(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> List[NodeInfo]:
        """List nodes"""
        return await self.statesvc_handle.query(StateSvcWorkflow.list_nodes)

    # ==================== Utility Operations ====================

    @nexusrpc.handler.sync_operation
    async def version(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> str:
        """Get version"""
        return await self.statesvc_handle.query(StateSvcWorkflow.version)

    @nexusrpc.handler.sync_operation
    async def get_addr(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> dict:
        """Get address"""
        return await self.statesvc_handle.query(StateSvcWorkflow.get_addr)

    @nexusrpc.handler.sync_operation
    async def uid(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> int:
        """Get UID"""
        return await self.statesvc_handle.query(StateSvcWorkflow.uid)

    @nexusrpc.handler.sync_operation
    async def increment_uid(
        self, ctx: nexusrpc.handler.StartOperationContext, input: None
    ) -> int:
        """Increment and get UID"""
        return await self.statesvc_handle.execute_update(StateSvcWorkflow.increment_uid)
