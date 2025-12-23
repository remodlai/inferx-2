"""
Scheduler Temporal workflows.

Long-running workflow managing pod placement and lifecycle.
"""

from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, List, Optional
import struct
import socket

# Import through sandbox
with workflow.unsafe.imports_passed_through():
    from inferx_common.models import (
        Function, NodeInfo, PodInfo, WorkerId,
        GatewayConnection, NodeResourceTracking
    )


def ip_to_int(ip_str: str) -> int:
    """Convert IP string to uint32 (network byte order)"""
    return struct.unpack("!I", socket.inet_aton(ip_str))[0]


def int_to_ip(ip_int: int) -> str:
    """Convert uint32 to IP string"""
    return socket.inet_ntoa(struct.pack("!I", ip_int))


@workflow.defn
class SchedulerWorkflow:
    """
    Long-running workflow managing pod placement and lifecycle.

    Tracks:
    - Running pods (funcKey -> PodInfo)
    - Idle pods (funcKey -> PodInfo)
    - Node resources (nodeName -> NodeResourceTracking)
    - Gateway connections (gatewayId -> GatewayConnection)
    """

    def __init__(self):
        """Initialize scheduler state"""
        # Pod tracking
        self.running_pods: Dict[str, PodInfo] = {}  # funcKey -> PodInfo
        self.idle_pods: Dict[str, PodInfo] = {}
        self.pending_pods: Dict[str, PodInfo] = {}

        # Node tracking
        self.nodes: Dict[str, NodeResourceTracking] = {}  # nodeName -> resources

        # Gateway tracking
        self.gateways: Dict[int, GatewayConnection] = {}  # gatewayId -> connection

        # Functions (cached from StateSvc queries)
        self.functions: Dict[str, Function] = {}  # funcKey -> Function

    @workflow.run
    async def run(self) -> None:
        """
        Run forever managing pod placement.

        This workflow never completes - it's a singleton service.
        """
        workflow.logger.info("Scheduler workflow started")
        await workflow.wait_condition(lambda: False)  # Wait forever

    # ==================== Helper Methods ====================

    def _func_key(self, tenant: str, namespace: str, funcname: str, fprevision: int) -> str:
        """Generate function key"""
        return f"{tenant}/{namespace}/{funcname}/{fprevision}"

    def _pod_key(self, tenant: str, namespace: str, funcname: str, fprevision: int, pod_id: str) -> str:
        """Generate pod key"""
        return f"{tenant}/{namespace}/{funcname}/{fprevision}/{pod_id}"

    # ==================== Gateway Operations ====================

    @workflow.update
    async def connect_scheduler(self, gateway_id: int, workers: List[WorkerId]) -> str:
        """
        Gateway registers with scheduler and reports existing workers.

        Args:
            gateway_id: Gateway identifier
            workers: List of workers currently leased by this gateway

        Returns:
            error: Empty string on success, error message on failure
        """
        # Store gateway connection
        self.gateways[gateway_id] = GatewayConnection(
            gateway_id=gateway_id,
            workers=workers,
            last_refresh=workflow.now()
        )

        # Validate workers exist
        # (In production, would check if these pods are actually running)

        workflow.logger.info(f"Gateway {gateway_id} connected with {len(workers)} worker(s)")
        return ""  # Success

    @workflow.update
    async def refresh_gateway(self, gateway_id: int) -> str:
        """
        Gateway heartbeat.

        Args:
            gateway_id: Gateway identifier

        Returns:
            error: Empty string on success, error message on failure
        """
        if gateway_id not in self.gateways:
            return f"Gateway {gateway_id} not registered"

        # Update last refresh time
        self.gateways[gateway_id].last_refresh = workflow.now()

        workflow.logger.debug(f"Gateway {gateway_id} heartbeat")
        return ""  # Success

    # ==================== Pod Lifecycle Operations ====================

    @workflow.update
    async def lease_worker(
        self,
        tenant: str,
        namespace: str,
        funcname: str,
        fprevision: int,
        gateway_id: int
    ) -> dict:
        """
        Get a pod to handle inference request.

        Returns:
            dict with: error, id, ipaddr, port, keepalive, hostipaddr, hostport
        """
        func_key = self._func_key(tenant, namespace, funcname, fprevision)

        # Check if pod already running (cache hit)
        if func_key in self.running_pods:
            pod = self.running_pods[func_key]
            workflow.logger.info(f"Cache hit: returning running pod {pod.id}")
            return {
                "error": "",
                "id": pod.id,
                "ipaddr": ip_to_int(pod.ipaddr),
                "port": pod.port,
                "keepalive": False,  # Already running, don't return
                "hostipaddr": 0,
                "hostport": 0
            }

        # Check if idle pod exists (warm start)
        if func_key in self.idle_pods:
            pod = self.idle_pods[func_key]
            workflow.logger.info(f"Warm start: resuming idle pod {pod.id}")

            # Move from idle to running
            del self.idle_pods[func_key]
            pod.state = "running"
            pod.last_used = workflow.now()
            self.running_pods[func_key] = pod

            # TODO: Call NodeAgent.ResumePod via activity

            return {
                "error": "",
                "id": pod.id,
                "ipaddr": ip_to_int(pod.ipaddr),
                "port": pod.port,
                "keepalive": True,
                "hostipaddr": 0,
                "hostport": 0
            }

        # Cold start - need to create pod
        workflow.logger.info(f"Cold start: need to create pod for {func_key}")

        # TODO: Implement placement algorithm
        # TODO: Call NodeAgent.CreateFuncPod via activity
        # For now, return error
        return {
            "error": "Cold start not implemented yet",
            "id": "",
            "ipaddr": 0,
            "port": 0,
            "keepalive": False,
            "hostipaddr": 0,
            "hostport": 0
        }

    @workflow.update
    async def return_worker(
        self,
        tenant: str,
        namespace: str,
        funcname: str,
        fprevision: int,
        pod_id: str,
        failworker: bool
    ) -> str:
        """
        Release pod back to pool or terminate if failed.

        Args:
            failworker: True if pod failed, should be terminated

        Returns:
            error: Empty string on success
        """
        func_key = self._func_key(tenant, namespace, funcname, fprevision)

        if func_key not in self.running_pods:
            return f"Pod {pod_id} not found in running pods"

        pod = self.running_pods[func_key]

        if failworker:
            # Pod failed - terminate it
            workflow.logger.info(f"Terminating failed pod {pod_id}")
            del self.running_pods[func_key]
            pod.state = "failed"

            # TODO: Call NodeAgent.TerminatePod via activity
            # TODO: Free resources in node tracking

        else:
            # Normal completion - move to idle pool
            workflow.logger.info(f"Moving pod {pod_id} to idle pool")
            del self.running_pods[func_key]
            pod.state = "idle"
            pod.last_used = workflow.now()
            self.idle_pods[func_key] = pod

            # Resources still allocated (pod kept warm)

        return ""  # Success

    # ==================== Query Operations ====================

    @workflow.query
    def get_running_pods(self) -> List[PodInfo]:
        """Get all running pods"""
        return list(self.running_pods.values())

    @workflow.query
    def get_idle_pods(self) -> List[PodInfo]:
        """Get all idle pods"""
        return list(self.idle_pods.values())

    @workflow.query
    def get_node_resources(self) -> List[NodeResourceTracking]:
        """Get resource tracking for all nodes"""
        return list(self.nodes.values())

    @workflow.query
    def get_gateway_connections(self) -> List[GatewayConnection]:
        """Get all connected gateways"""
        return list(self.gateways.values())
