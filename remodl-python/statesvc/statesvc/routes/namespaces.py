"""
Namespace management routes.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from inferx_common.models import Namespace
from ..workflows import StateSvcWorkflow
from .common import get_statesvc_handle

router = APIRouter(prefix="/namespaces", tags=["namespaces"])


@router.get("/", response_model=dict)
async def list_namespaces(tenant: Optional[str] = Query(None)):
    """List all namespaces or filter by tenant"""
    handle = await get_statesvc_handle()
    namespaces = await handle.query(StateSvcWorkflow.list_namespaces, args=[tenant])
    return {"namespaces": namespaces}


@router.get("/{tenant}/{namespace}", response_model=Namespace)
async def get_namespace(tenant: str, namespace: str):
    """Get specific namespace"""
    handle = await get_statesvc_handle()
    ns = await handle.query(StateSvcWorkflow.get_namespace, args=[tenant, namespace])

    if not ns:
        raise HTTPException(404, f"Namespace {tenant}/{namespace} not found")

    return ns


@router.post("/", response_model=dict)
async def create_namespace(namespace: Namespace, creator_username: Optional[str] = None):
    """Create new namespace"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.create_namespace,
            args=[namespace, creator_username]
        )
        return {
            "revision": revision,
            "status": "created",
            "namespace": f"{namespace.tenant}/{namespace.name}"
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@router.put("/{tenant}/{namespace}", response_model=dict)
async def update_namespace(tenant: str, namespace: str, updates: Namespace):
    """Update namespace"""
    handle = await get_statesvc_handle()

    try:
        # Merge tenant/namespace from path into updates
        updates.tenant = tenant
        updates.name = namespace

        revision = await handle.execute_update(
            StateSvcWorkflow.update_namespace,
            args=[updates]
        )
        return {"revision": revision, "status": "updated", "namespace": f"{tenant}/{namespace}"}
    except Exception as e:
        raise HTTPException(400, str(e))


@router.delete("/{tenant}/{namespace}", response_model=dict)
async def delete_namespace(tenant: str, namespace: str):
    """Delete namespace"""
    handle = await get_statesvc_handle()

    try:
        revision = await handle.execute_update(
            StateSvcWorkflow.delete_namespace,
            args=[tenant, namespace]
        )
        return {"revision": revision, "status": "deleted", "namespace": f"{tenant}/{namespace}"}
    except Exception as e:
        raise HTTPException(400, str(e))
