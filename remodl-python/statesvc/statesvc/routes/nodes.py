"""
Node management routes.
"""

from fastapi import APIRouter, HTTPException

from inferx_common.models import NodeInfo
from ..workflows import StateSvcWorkflow
from .common import get_statesvc_handle

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/", response_model=dict)
async def list_nodes():
    """List all GPU nodes"""
    handle = await get_statesvc_handle()
    nodes = await handle.query(StateSvcWorkflow.list_nodes)
    return {"nodes": nodes}


@router.get("/{nodename}", response_model=NodeInfo)
async def get_node(nodename: str):
    """Get specific node"""
    handle = await get_statesvc_handle()
    node = await handle.query(StateSvcWorkflow.get_node, args=[nodename])

    if not node:
        raise HTTPException(404, f"Node {nodename} not found")

    return node


@router.post("/", response_model=dict)
async def register_node(node: NodeInfo):
    """Register or update node"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.register_node,
            args=[node]
        )
        return {"revision": revision, "status": "registered", "node": node.name}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{nodename}/state", response_model=dict)
async def update_node_state(nodename: str, state: dict):
    """Update node state"""
    handle = await get_statesvc_handle()

    try:
        state_value = state.get("state")
        if not state_value:
            raise HTTPException(400, "state field required in body")

        revision = await handle.execute_update(
            StateSvcWorkflow.update_node_state,
            args=[nodename, state_value]
        )
        return {"revision": revision, "status": "updated", "node": nodename, "state": state_value}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/{nodename}", response_model=dict)
async def delete_node(nodename: str):
    """Delete node"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.delete_node,
            args=[nodename]
        )
        return {"revision": revision, "status": "deleted", "node": nodename}
    except Exception as e:
        raise HTTPException(400, str(e))
