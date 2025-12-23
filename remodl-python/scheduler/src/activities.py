"""
Scheduler activities.

Activities that interact with NodeAgent, StateSvc, and perform placement logic.
"""

from temporalio import activity
import grpc
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
import os
from typing import Optional, List
import json

from .generated import na_pb2, na_pb2_grpc
from inferx_common.models import NodeInfo, Function


# ==================== StateSvc Query Activities ====================

@activity.defn
async def query_statesvc_for_nodes() -> List[NodeInfo]:
    """
    Query StateSvc for all available nodes.

    Returns: List of NodeInfo
    """
    # Connect to Temporal to query StateSvc workflow
    client = await Client.connect(
        os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "inferx"),
        tls=True,
        data_converter=pydantic_data_converter
    )

    # Query StateSvc singleton workflow
    handle = client.get_workflow_handle("statesvc-singleton")

    # Import workflow class for type safety
    # Note: This creates circular import, so we'll use string-based query
    nodes = await handle.query("list_nodes")

    await client.close()
    return [NodeInfo(**n) for n in nodes]


@activity.defn
async def query_statesvc_for_function(tenant: str, namespace: str, funcname: str, version: Optional[int]) -> Optional[Function]:
    """
    Query StateSvc for function spec.

    Returns: Function object
    """
    client = await Client.connect(
        os.getenv("TEMPORAL_TARGET_HOST", "flow.remodl.ai:443"),
        namespace=os.getenv("TEMPORAL_NAMESPACE", "inferx"),
        tls=True,
        data_converter=pydantic_data_converter
    )

    handle = client.get_workflow_handle("statesvc-singleton")
    function_data = await handle.query("get_function", args=[tenant, namespace, funcname, version])

    await client.close()

    if function_data:
        return Function(**function_data)
    return None


# ==================== Placement Activities ====================

@activity.defn
async def find_best_node(required_vram: int, gpu_type: str = "Any") -> Optional[str]:
    """
    Find node with sufficient resources.

    Args:
        required_vram: VRAM required in MB
        gpu_type: GPU type or "Any"

    Returns:
        node_name: Name of node to use, or None if no capacity
    """
    # Get all nodes from StateSvc
    nodes = await query_statesvc_for_nodes()

    # Filter by GPU type if specified
    if gpu_type != "Any":
        nodes = [n for n in nodes if n.object.resources.GPUType == gpu_type]

    # Filter by available VRAM (simple first-fit for now)
    # TODO: Track used resources properly
    for node in nodes:
        if node.object.resources.GPUs.vRam >= required_vram:
            if node.object.state == "NodeAgentAvaiable":
                activity.logger.info(f"Selected node: {node.name} (VRAM: {node.object.resources.GPUs.vRam} MB)")
                return node.name

    activity.logger.warning(f"No node found with {required_vram} MB VRAM")
    return None


# ==================== NodeAgent Interaction Activities ====================

@activity.defn
async def create_pod_on_node(node_name: str, func_spec: dict) -> dict:
    """
    Call NodeAgent to create pod.

    Args:
        node_name: Node to create pod on
        func_spec: Function specification with keys: tenant, namespace, funcname, fprevision, id

    Returns:
        {error, id, ipaddr}
    """
    # Get node info to find NodeAgent URL
    nodes = await query_statesvc_for_nodes()
    node = next((n for n in nodes if n.name == node_name), None)

    if not node:
        return {"error": f"Node {node_name} not found", "id": "", "ipaddr": 0}

    # Build NodeAgent gRPC URL
    node_agent_url = f"{node.object.naIp}:{node.object.podMgrPort}"
    activity.logger.info(f"Calling NodeAgent at {node_agent_url}")

    try:
        # Open gRPC channel
        channel = grpc.aio.insecure_channel(node_agent_url)
        stub = na_pb2_grpc.NodeAgentServiceStub(channel)

        # Build CreateFuncPodReq
        request = na_pb2.CreateFuncPodReq(
            tenant=func_spec['tenant'],
            namespace=func_spec['namespace'],
            funcname=func_spec['funcname'],
            fprevision=func_spec['fprevision'],
            id=func_spec['id'],
            funcspec=json.dumps(func_spec),  # Serialize full spec
            create_type=na_pb2.CreatePodType.Normal,
        )

        # Call NodeAgent
        response = await stub.CreateFuncPod(request)

        await channel.close()

        if response.error:
            activity.logger.error(f"NodeAgent error: {response.error}")
            return {"error": response.error, "id": "", "ipaddr": 0}

        activity.logger.info(f"Pod created: id={func_spec['id']}, ip={response.ipaddress}")
        return {
            "error": "",
            "id": func_spec['id'],
            "ipaddr": response.ipaddress
        }

    except Exception as e:
        activity.logger.error(f"Failed to create pod: {e}")
        return {"error": str(e), "id": "", "ipaddr": 0}


@activity.defn
async def resume_pod_on_node(node_name: str, pod_id: str, tenant: str, namespace: str, funcname: str, fprevision: int) -> dict:
    """
    Call NodeAgent to resume idle pod.

    Returns:
        {error}
    """
    nodes = await query_statesvc_for_nodes()
    node = next((n for n in nodes if n.name == node_name), None)

    if not node:
        return {"error": f"Node {node_name} not found"}

    node_agent_url = f"{node.object.naIp}:{node.object.podMgrPort}"

    try:
        channel = grpc.aio.insecure_channel(node_agent_url)
        stub = na_pb2_grpc.NodeAgentServiceStub(channel)

        request = na_pb2.ResumePodReq(
            tenant=tenant,
            namespace=namespace,
            funcname=funcname,
            fprevision=fprevision,
            id=pod_id,
        )

        response = await stub.ResumePod(request)
        await channel.close()

        return {"error": response.error}

    except Exception as e:
        return {"error": str(e)}


@activity.defn
async def terminate_pod_on_node(node_name: str, pod_id: str, tenant: str, namespace: str, funcname: str, fprevision: int) -> dict:
    """
    Call NodeAgent to terminate pod.

    Returns:
        {error}
    """
    nodes = await query_statesvc_for_nodes()
    node = next((n for n in nodes if n.name == node_name), None)

    if not node:
        return {"error": f"Node {node_name} not found"}

    node_agent_url = f"{node.object.naIp}:{node.object.podMgrPort}"

    try:
        channel = grpc.aio.insecure_channel(node_agent_url)
        stub = na_pb2_grpc.NodeAgentServiceStub(channel)

        request = na_pb2.TerminatePodReq(
            tenant=tenant,
            namespace=namespace,
            funcname=funcname,
            fprevision=fprevision,
            id=pod_id,
        )

        response = await stub.TerminatePod(request)
        await channel.close()

        return {"error": response.error}

    except Exception as e:
        return {"error": str(e)}
