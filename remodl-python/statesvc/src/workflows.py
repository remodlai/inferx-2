"""
StateSvc Temporal workflow.

Long-running workflow managing InferX cluster state via Temporal messages.
"""

from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, List, Optional

# Import through sandbox
with workflow.unsafe.imports_passed_through():
    from .dataclasses import (
        Tenant, Namespace, Function, FunctionStatus, NodeInfo,
        TenantObject, NamespaceObject, FunctionObject, FunctionStatusDef
    )
    from .activities import (
        # Tenant
        create_tenant_and_grant_role, delete_tenant,
        grant_tenant_admin_role, revoke_tenant_admin_role,
        # Namespace
        create_namespace, update_namespace, delete_namespace,
        grant_namespace_admin_role,
        # Function
        create_function, update_function, delete_function,
        # Function Status
        create_function_status, update_function_status,
        # Node
        register_node, update_node_state, delete_node,
    )


@workflow.defn
class StateSvcWorkflow:
    """
    Long-running workflow managing InferX cluster state.

    This workflow:
    - Runs forever (singleton instance)
    - Stores state in workflow memory (durable)
    - Receives updates via @workflow.update
    - Serves queries via @workflow.query
    - Persists to PostgreSQL via activities
    """

    def __init__(self):
        """Initialize workflow state"""
        # State storage (durable in Temporal)
        self.tenants: Dict[str, Tenant] = {}
        self.namespaces: Dict[str, Namespace] = {}  # Key: "tenant/namespace"
        self.functions: Dict[str, Function] = {}  # Key: "tenant/namespace/name/version"
        self.function_status: Dict[str, FunctionStatus] = {}
        self.nodes: Dict[str, NodeInfo] = {}

        # Metadata
        self.version = "0.2.0-temporal"
        self.svc_ip = "0.0.0.0"  # Will be actual pod IP in production
        self.svc_port = 1237
        self.uid_counter = 10000  # Monotonic counter

    @workflow.run
    async def run(self) -> None:
        """
        Run forever managing state.

        This workflow never completes - it's a singleton service.
        """
        workflow.logger.info("StateSvc workflow started")
        await workflow.wait_condition(lambda: False)  # Wait forever

    # ==================== Tenant Operations ====================

    @workflow.update
    async def create_tenant(self, tenant: Tenant, creator_username: str) -> int:
        """Create tenant and grant admin role"""
        # Validate
        if tenant.tenant != "system" or tenant.namespace != "system":
            raise ValueError("Tenant must have tenant='system' and namespace='system'")

        if tenant.name in self.tenants:
            raise ValueError(f"Tenant {tenant.name} already exists")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            create_tenant_and_grant_role,
            args=[tenant, creator_username],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Update workflow state
        self.tenants[tenant.name] = tenant

        workflow.logger.info(f"Created tenant: {tenant.name}, revision: {revision}")
        return revision

    @workflow.update
    async def delete_tenant(self, tenant_name: str) -> int:
        """Delete tenant"""
        if tenant_name not in self.tenants:
            raise ValueError(f"Tenant {tenant_name} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            delete_tenant,
            tenant_name,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        del self.tenants[tenant_name]

        workflow.logger.info(f"Deleted tenant: {tenant_name}")
        return revision

    @workflow.query
    def get_tenant(self, tenant_name: str) -> Optional[Tenant]:
        """Get tenant from workflow state"""
        return self.tenants.get(tenant_name)

    @workflow.query
    def list_tenants(self) -> List[Tenant]:
        """List all tenants"""
        return list(self.tenants.values())

    # ==================== Namespace Operations ====================

    @workflow.update
    async def create_namespace(self, namespace: Namespace, creator_username: Optional[str] = None) -> int:
        """Create namespace"""
        # Validate tenant exists
        if namespace.tenant not in self.tenants:
            raise ValueError(f"Tenant {namespace.tenant} does not exist")

        key = f"{namespace.tenant}/{namespace.name}"
        if key in self.namespaces:
            raise ValueError(f"Namespace {key} already exists")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            create_namespace,
            namespace,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Grant namespace admin role if creator provided
        if creator_username:
            await workflow.execute_activity(
                grant_namespace_admin_role,
                args=[namespace.tenant, namespace.name, creator_username],
                start_to_close_timeout=timedelta(seconds=5)
            )

        # Update workflow state
        self.namespaces[key] = namespace

        workflow.logger.info(f"Created namespace: {key}, revision: {revision}")
        return revision

    @workflow.update
    async def update_namespace(self, namespace: Namespace) -> int:
        """Update namespace"""
        key = f"{namespace.tenant}/{namespace.name}"
        if key not in self.namespaces:
            raise ValueError(f"Namespace {key} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            update_namespace,
            namespace,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        self.namespaces[key] = namespace

        workflow.logger.info(f"Updated namespace: {key}")
        return revision

    @workflow.update
    async def delete_namespace(self, tenant: str, namespace: str) -> int:
        """Delete namespace"""
        key = f"{tenant}/{namespace}"
        if key not in self.namespaces:
            raise ValueError(f"Namespace {key} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            delete_namespace,
            args=[tenant, namespace],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        del self.namespaces[key]

        workflow.logger.info(f"Deleted namespace: {key}")
        return revision

    @workflow.query
    def get_namespace(self, tenant: str, namespace: str) -> Optional[Namespace]:
        """Get namespace from workflow state"""
        key = f"{tenant}/{namespace}"
        return self.namespaces.get(key)

    @workflow.query
    def list_namespaces(self, tenant: Optional[str] = None) -> List[Namespace]:
        """List namespaces, optionally filtered by tenant"""
        if tenant:
            return [ns for key, ns in self.namespaces.items() if ns.tenant == tenant]
        return list(self.namespaces.values())

    # ==================== Function Operations ====================

    @workflow.update
    async def create_function(self, function: Function) -> int:
        """Create function and auto-create function status"""
        # Validate namespace exists
        ns_key = f"{function.tenant}/{function.namespace}"
        if ns_key not in self.namespaces:
            raise ValueError(f"Namespace {ns_key} does not exist")

        func_key = f"{function.tenant}/{function.namespace}/{function.name}/{function.object.spec.version}"
        if func_key in self.functions:
            raise ValueError(f"Function {func_key} already exists")

        # Persist function to PostgreSQL
        revision = await workflow.execute_activity(
            create_function,
            function,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Auto-create function status
        func_status = FunctionStatus(
            tenant=function.tenant,
            namespace=function.namespace,
            name=function.name,
            object=FunctionStatusDef(
                state="Normal",
                version=function.object.spec.version,
                snapshotingFailureCnt=0,
                resumingFailureCnt=0
            )
        )

        await workflow.execute_activity(
            create_function_status,
            func_status,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        self.functions[func_key] = function
        self.function_status[func_key] = func_status

        workflow.logger.info(f"Created function: {func_key}, revision: {revision}")
        return revision

    @workflow.update
    async def update_function(self, function: Function) -> int:
        """Update function and function status"""
        func_key = f"{function.tenant}/{function.namespace}/{function.name}/{function.object.spec.version}"
        if func_key not in self.functions:
            raise ValueError(f"Function {func_key} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            update_function,
            function,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update function status version
        if func_key in self.function_status:
            status = self.function_status[func_key]
            status.object.version = function.object.spec.version
            await workflow.execute_activity(
                update_function_status,
                status,
                start_to_close_timeout=timedelta(seconds=10)
            )

        # Update workflow state
        self.functions[func_key] = function

        workflow.logger.info(f"Updated function: {func_key}")
        return revision

    @workflow.update
    async def delete_function(self, tenant: str, namespace: str, name: str, version: int) -> int:
        """Delete function and function status"""
        func_key = f"{tenant}/{namespace}/{name}/{version}"
        if func_key not in self.functions:
            raise ValueError(f"Function {func_key} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            delete_function,
            args=[tenant, namespace, name, version],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        del self.functions[func_key]
        if func_key in self.function_status:
            del self.function_status[func_key]

        workflow.logger.info(f"Deleted function: {func_key}")
        return revision

    @workflow.query
    def get_function(self, tenant: str, namespace: str, name: str, version: Optional[int] = None) -> Optional[Function]:
        """Get function from workflow state"""
        if version:
            func_key = f"{tenant}/{namespace}/{name}/{version}"
            return self.functions.get(func_key)

        # If no version, return latest
        matching = [f for k, f in self.functions.items() if f.tenant == tenant and f.namespace == namespace and f.name == name]
        if matching:
            return max(matching, key=lambda f: f.object.spec.version)
        return None

    @workflow.query
    def list_functions(self, tenant: Optional[str] = None, namespace: Optional[str] = None) -> List[Function]:
        """List functions, optionally filtered"""
        funcs = list(self.functions.values())

        if tenant:
            funcs = [f for f in funcs if f.tenant == tenant]
        if namespace:
            funcs = [f for f in funcs if f.namespace == namespace]

        return funcs

    # ==================== Function Status Operations ====================

    @workflow.update
    async def update_function_status(self, status: FunctionStatus) -> int:
        """Update function status"""
        func_key = f"{status.tenant}/{status.namespace}/{status.name}/{status.object.version}"

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            update_function_status,
            status,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        self.function_status[func_key] = status

        workflow.logger.info(f"Updated function status: {func_key}, state: {status.object.state}")
        return revision

    @workflow.query
    def get_function_status(self, tenant: str, namespace: str, name: str, version: int) -> Optional[FunctionStatus]:
        """Get function status from workflow state"""
        func_key = f"{tenant}/{namespace}/{name}/{version}"
        return self.function_status.get(func_key)

    @workflow.query
    def list_function_status(self, tenant: Optional[str] = None, namespace: Optional[str] = None) -> List[FunctionStatus]:
        """List function statuses, optionally filtered"""
        statuses = list(self.function_status.values())

        if tenant:
            statuses = [s for s in statuses if s.tenant == tenant]
        if namespace:
            statuses = [s for s in statuses if s.namespace == namespace]

        return statuses

    # ==================== Node Operations ====================

    @workflow.update
    async def register_node(self, node: NodeInfo) -> int:
        """Register or update node"""
        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            register_node,
            node,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Update workflow state
        self.nodes[node.name] = node

        workflow.logger.info(f"Registered node: {node.name}, IP: {node.object.naIp}, GPUs: {node.object.resources.GPUType}")
        return revision

    @workflow.update
    async def update_node_state(self, node_name: str, state: str) -> int:
        """Update node state"""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            update_node_state,
            args=[node_name, state],
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        self.nodes[node_name].object.state = state

        workflow.logger.info(f"Updated node {node_name} state: {state}")
        return revision

    @workflow.update
    async def delete_node(self, node_name: str) -> int:
        """Delete node"""
        if node_name not in self.nodes:
            raise ValueError(f"Node {node_name} not found")

        # Persist to PostgreSQL
        revision = await workflow.execute_activity(
            delete_node,
            node_name,
            start_to_close_timeout=timedelta(seconds=10)
        )

        # Update workflow state
        del self.nodes[node_name]

        workflow.logger.info(f"Deleted node: {node_name}")
        return revision

    @workflow.query
    def get_node(self, node_name: str) -> Optional[NodeInfo]:
        """Get node from workflow state"""
        return self.nodes.get(node_name)

    @workflow.query
    def list_nodes(self) -> List[NodeInfo]:
        """List all nodes"""
        return list(self.nodes.values())

    # ==================== Utility Operations ====================

    @workflow.query
    def version(self) -> str:
        """Get StateSvc version"""
        return self.version

    @workflow.query
    def get_addr(self) -> dict:
        """Get StateSvc address"""
        return {
            "svcIp": self.svc_ip,
            "port": self.svc_port
        }

    @workflow.query
    def uid(self) -> int:
        """Get unique ID (monotonic counter)"""
        # Note: This is a query, so can't increment state
        # For true unique IDs, would need an update operation
        return self.uid_counter

    @workflow.update
    async def increment_uid(self) -> int:
        """Increment and return unique ID"""
        self.uid_counter += 1
        return self.uid_counter
